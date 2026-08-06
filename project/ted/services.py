"""
.. topic:: TED (services)

    Camada de regra de negócio do módulo TED (Etapa 3 do roadmap de BI):
    carga a partir da API pública do TransfereGov, listagem/filtros da
    tela de gestão, e curadoria manual (execução interna, vínculo a
    Programa CNPq, vínculo a Convênio/Acordo). Sem dependência de
    objetos de request/response do Flask — as rotas (views.py) decidem
    o que fazer com o resultado.
"""

import datetime as dt
import locale
import math
import os.path

import requests
from sqlalchemy import or_

from project import db, app, sched
from project.models import (
    TED_Programa, TED_PlanoAcao, TED_TermoExecucao, TED_Execucao_Interna,
    TED_Vinculo_ProgramaCNPq, TED_Vinculo_Instrumento, TED_Carga_Status, Programa_CNPq, Coords,
    Acordo,
)
from project.convenios.services import cria_csv

API_BASE = 'https://api.transferegov.gestao.gov.br/ted'
UNIDADE_CNPQ = 'CNPq'


def _parse_data(valor):
    """Converte 'YYYY-MM-DD' (formato da API) para date. None se vazio."""
    if not valor:
        return None
    return dt.datetime.strptime(valor, '%Y-%m-%d').date()


def cargaTED():
    """
    Carrega os TEDs do CNPq a partir da API pública do TransfereGov,
    filtrando direto na consulta (sigla_unidade_descentralizada=CNPq —
    testado e confirmado que filtra no servidor, sem precisar baixar
    tudo). Delete-and-reload nas 3 tabelas espelho (mesmo padrão de
    cargaSICONV em project/core/services.py) — não toca nas tabelas de
    curadoria manual, que referenciam essas linhas pela própria chave
    da API (estável entre cargas).

    Retorna um dict com as contagens carregadas, para exibir na tela.
    """
    resp_planos = requests.get(
        f'{API_BASE}/plano_acao',
        params={'sigla_unidade_descentralizada': f'eq.{UNIDADE_CNPQ}'},
        timeout=30,
    )
    resp_planos.raise_for_status()
    planos = resp_planos.json()

    ids_programa = sorted({p['id_programa'] for p in planos if p.get('id_programa')})
    programas = []
    if ids_programa:
        resp_prog = requests.get(
            f'{API_BASE}/programa',
            params={'id_programa': 'in.(' + ','.join(str(i) for i in ids_programa) + ')'},
            timeout=30,
        )
        resp_prog.raise_for_status()
        programas = resp_prog.json()

    ids_plano = [p['id_plano_acao'] for p in planos]
    termos = []
    if ids_plano:
        resp_termo = requests.get(
            f'{API_BASE}/termo_execucao',
            params={'id_plano_acao': 'in.(' + ','.join(str(i) for i in ids_plano) + ')'},
            timeout=30,
        )
        resp_termo.raise_for_status()
        termos = resp_termo.json()

    # delete-and-reload — mesma ordem inversa das FKs (termo -> plano -> programa)
    TED_TermoExecucao.query.delete()
    TED_PlanoAcao.query.delete()
    TED_Programa.query.delete()
    db.session.commit()

    for prog in programas:
        db.session.add(TED_Programa(
            id=prog['id_programa'],
            codigo_programa=prog.get('tx_codigo_programa'),
            nome=prog.get('tx_nome_programa'),
            unidade_descentralizadora=prog.get('unidade_descentralizadora'),
            sigla_unidade_descentralizadora=prog.get('sigla_unidade_descentralizadora'),
            ano=str(prog.get('aa_ano_programa') or ''),
        ))
    db.session.commit()

    for plano in planos:
        db.session.add(TED_PlanoAcao(
            id=plano['id_plano_acao'],
            numero_ted=plano.get('sq_instrumento'),
            id_programa=plano.get('id_programa'),
            unidade_descentralizada=plano.get('unidade_descentralizada'),
            situacao_plano=plano.get('tx_situacao_plano_acao'),
            objeto=plano.get('tx_objeto_plano_acao'),
            valor_beneficiario_especifico=plano.get('vl_beneficiario_especifico'),
            valor_chamamento_publico=plano.get('vl_chamamento_publico'),
            vigencia_inicio=_parse_data(plano.get('dt_inicio_vigencia')),
            vigencia_fim=_parse_data(plano.get('dt_fim_vigencia')),
            ano=str(plano.get('aa_ano_plano_acao') or ''),
        ))
    db.session.commit()

    for termo in termos:
        db.session.add(TED_TermoExecucao(
            id=termo['id_termo'],
            id_plano_acao=termo.get('id_plano_acao'),
            situacao_termo=termo.get('tx_situacao_termo'),
            data_assinatura=_parse_data(termo.get('dt_assinatura_termo')),
            numero_ns_termo=termo.get('tx_numero_ns_termo'),
            referencia_externa=termo.get('tx_num_processo_sei'),
        ))
    db.session.commit()

    status = TED_Carga_Status.query.first()
    if status:
        status.data_ultima_carga = dt.datetime.now()
    else:
        db.session.add(TED_Carga_Status(data_ultima_carga=dt.datetime.now()))
    db.session.commit()

    return {
        'programas': len(programas),
        'planos': len(planos),
        'termos': len(termos),
    }


def agendar_carga_ted_diaria():
    """
    Agenda a carga de TED (API do TransfereGov) uma vez por dia, de
    forma incondicional — ao contrário de agendar_cargas_iniciais()
    (SICONV/DW, em project/core/services.py), que só agenda se
    Sistema.carga_auto estiver ligado, a carga de TED não depende desse
    interruptor (pedido explícito de Igor: a atualização deve rodar
    automaticamente todo dia, sem depender de configuração). Idempotente
    via sched.get_job(), mesmo padrão de agendar_cargas_iniciais().
    """
    id_job = 'carga_ted_diaria'

    try:
        job_existente = sched.get_job(id_job)
        executa = not job_existente
    except Exception:
        executa = True

    if executa:
        hora, minuto = 6, 0
        print(f'*** Agendamento inicial {id_job}, rodando todo dia, às {hora}:{minuto:02d} ***')
        try:
            sched.add_job(trigger='cron', id=id_job, func=cargaTED, hour=hora, minute=minuto,
                           misfire_grace_time=3600, coalesce=True)
            sched.start()
        except Exception:
            sched.reschedule_job(id_job, trigger='cron', hour=hora, minute=minuto)


def dados_ultima_carga_ted():
    """Retorna a data/hora da última carga de TED bem-sucedida, ou None se nunca rodou."""
    status = TED_Carga_Status.query.first()
    return status.data_ultima_carga if status else None


# campo de filtro/exibição -> função que extrai a chave de ordenação de um item de listar_teds()
_CHAVES_ORDENACAO = {
    'ted': lambda item: (item['plano'].numero_ted or '', item['plano'].id),
    'orgao': lambda item: (item['programa'].unidade_descentralizadora if item['programa'] else ''),
    'situacao': lambda item: (item['plano'].situacao_plano or ''),
    'valor': lambda item: (item['plano'].valor_beneficiario_especifico or 0) + (item['plano'].valor_chamamento_publico or 0),
    # 'vigencia' (coluna única, início–fim numa string só) foi separada em
    # duas colunas independentes na tela, cada uma com sua própria ordenação
    'vigencia_inicio': lambda item: (item['plano'].vigencia_inicio or dt.date.min),
    'vigencia_fim': lambda item: (item['plano'].vigencia_fim or dt.date.min),
}


def listar_teds(filtros=None, page=None, per_page=25, sort=None, direcao='asc'):
    """
    Monta a listagem da tela de gestão: TED_PlanoAcao + TED_Programa +
    TED_TermoExecucao (situação do termo) + estado de curadoria
    (Programa CNPq vinculado? execução interna registrada? instrumento
    vinculado? coordenação(ões) do CNPq envolvida(s)?), com filtros
    opcionais.

    Sem `page` (comportamento padrão, usado por cargaTED/testes e por
    exportar_teds_csv), retorna a lista completa filtrada — sem
    paginar. Com `page`, retorna `(pagina, paginacao)`, onde `paginacao`
    é um dict com os campos que o template de paginação precisa (mesmo
    espírito do Pagination do Flask-SQLAlchemy, mas calculado em Python:
    o filtro de programa_cnpq vinculado/pendente já é feito em Python
    hoje, sobre a lista inteira, então paginar no banco antes dele
    devolveria páginas com contagem errada).

    `sort` (um dos campos de _CHAVES_ORDENACAO) e `direcao` ('asc'/'desc')
    reordenam o resultado; sem `sort`, mantém a ordem padrão (ano desc,
    já aplicada na consulta).
    """
    filtros = filtros or {}

    query = db.session.query(TED_PlanoAcao, TED_Programa)\
                      .outerjoin(TED_Programa, TED_Programa.id == TED_PlanoAcao.id_programa)

    if filtros.get('orgao'):
        query = query.filter(TED_Programa.unidade_descentralizadora == filtros['orgao'])
    if filtros.get('situacao'):
        query = query.filter(TED_PlanoAcao.situacao_plano == filtros['situacao'])
    if filtros.get('ano'):
        query = query.filter(TED_PlanoAcao.ano == filtros['ano'])
    if filtros.get('busca'):
        termo = f"%{filtros['busca']}%"
        query = query.filter(or_(
            TED_PlanoAcao.numero_ted.ilike(termo),
            TED_PlanoAcao.objeto.ilike(termo),
        ))

    # tiebreaker por id: sem ele, empates em 'ano' (a maioria dos TEDs, já que
    # há poucos anos distintos) deixam a ordem entre duas execuções da mesma
    # query sujeita ao plano de execução do Postgres — não garantida estável.
    # Bug real encontrado via teste: paginação podia repetir/pular TEDs entre
    # página 1 e 2 quando isso acontecia.
    linhas = query.order_by(TED_PlanoAcao.ano.desc(), TED_PlanoAcao.id.asc()).all()

    ids_plano = [p.id for p, _ in linhas]
    situacoes_termo = {
        t.id_plano_acao: t.situacao_termo
        for t in TED_TermoExecucao.query.filter(TED_TermoExecucao.id_plano_acao.in_(ids_plano)).all()
    } if ids_plano else {}

    programas_vinculados = {
        v.id_plano_acao: v
        for v in TED_Vinculo_ProgramaCNPq.query.filter(TED_Vinculo_ProgramaCNPq.id_plano_acao.in_(ids_plano)).all()
    } if ids_plano else {}

    execucoes_por_plano = {}
    if ids_plano:
        for e in TED_Execucao_Interna.query.filter(TED_Execucao_Interna.id_plano_acao.in_(ids_plano)).all():
            execucoes_por_plano.setdefault(e.id_plano_acao, []).append(e)

    # Bug real corrigido: a versão antiga guardava um dict {id_plano_acao: vinculo},
    # descartando silenciosamente qualquer vínculo além do primeiro — um TED pode
    # financiar vários Acordos/Convênios (até 27, segundo Igor). Agora é uma lista
    # por TED, mesmo padrão de execucoes_por_plano acima.
    instrumentos_por_plano = {}
    if ids_plano:
        for v in TED_Vinculo_Instrumento.query.filter(TED_Vinculo_Instrumento.id_plano_acao.in_(ids_plano)).all():
            instrumentos_por_plano.setdefault(v.id_plano_acao, []).append(v)

    ids_acordo_vinculados = sorted({
        v.id_acordo for lista in instrumentos_por_plano.values() for v in lista if v.id_acordo
    })
    acordos_vinculados = {
        a.id: a for a in Acordo.query.filter(Acordo.id.in_(ids_acordo_vinculados)).all()
    } if ids_acordo_vinculados else {}

    if filtros.get('programa_cnpq') == 'vinculado':
        linhas = [(p, prog) for p, prog in linhas if p.id in programas_vinculados]
    elif filtros.get('programa_cnpq') == 'pendente':
        linhas = [(p, prog) for p, prog in linhas if p.id not in programas_vinculados]

    hoje = dt.date.today()

    resultado = []
    for plano, programa in linhas:
        vinculo_prog = programas_vinculados.get(plano.id)
        programa_cnpq_nome = None
        if vinculo_prog:
            pc = Programa_CNPq.query.get(vinculo_prog.id_programa_cnpq)
            programa_cnpq_nome = pc.SIGLA_PROGRAMA if pc else None

        instrumentos = []
        for v in instrumentos_por_plano.get(plano.id, []):
            if v.tipo_instrumento == 'acordo':
                acordo = acordos_vinculados.get(v.id_acordo)
                # identificador real do Acordo é o SEI (ver item C2 do backlog), não o id interno
                if acordo and acordo.sei:
                    rotulo = f"Acordo {acordo.sei}"
                elif acordo:
                    rotulo = f"Acordo {acordo.nome}"
                else:
                    rotulo = f"Acordo #{v.id_acordo}"
            else:
                rotulo = f"Convênio {v.nr_convenio}"
            instrumentos.append(rotulo)

        execucoes = execucoes_por_plano.get(plano.id, [])
        coordenacoes = sorted({e.coordenacao for e in execucoes if e.coordenacao})

        # dias até o fim da vigência, pra colorir a coluna "Fim" na tela
        # (mesmo padrão de Convênios). None quando não há data de fim —
        # vários TEDs vêm da API sem vigência preenchida.
        prazo = (plano.vigencia_fim - hoje).days if plano.vigencia_fim else None

        resultado.append({
            'plano': plano,
            'programa': programa,
            'situacao_termo': situacoes_termo.get(plano.id),
            'programa_cnpq_nome': programa_cnpq_nome,
            'execucoes': execucoes,
            'coordenacoes': coordenacoes,
            'instrumentos': instrumentos,
            'prazo': prazo,
        })

    if sort in _CHAVES_ORDENACAO:
        resultado.sort(key=_CHAVES_ORDENACAO[sort], reverse=(direcao == 'desc'))

    if page is None:
        return resultado

    total = len(resultado)
    pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, pages))
    inicio = (page - 1) * per_page

    paginacao = {
        'page': page, 'per_page': per_page, 'total': total, 'pages': pages,
        'has_prev': page > 1, 'has_next': page < pages,
        'prev_num': page - 1, 'next_num': page + 1,
    }
    return resultado[inicio:inicio + per_page], paginacao


def sigla_ou_nome_orgao(programa):
    """
    Sigla do órgão de origem (ex: "MCTI") com fallback pro nome por
    extenso quando a API não mandou sigla — vários programas antigos
    vêm sem esse campo preenchido, e mostrar vazio seria pior que
    mostrar o nome longo.
    """
    if programa is None:
        return None
    return programa.sigla_unidade_descentralizadora or programa.unidade_descentralizadora


def opcoes_filtro():
    """
    Opções para os selects de filtro da tela de gestão.

    `orgaos` continua sendo a lista de nomes por extenso (é o valor
    usado no filtro, casando com TED_Programa.unidade_descentralizadora
    na query) — mantido assim de propósito pra não quebrar o BI de TED,
    que consome a mesma função. `orgaos_siglas` é o de-para nome
    completo -> sigla, usado só na exibição (item A5).
    """
    orgaos = [o.unidade_descentralizadora for o in db.session.query(TED_Programa.unidade_descentralizadora)
              .filter(TED_Programa.unidade_descentralizadora.isnot(None))
              .distinct().order_by(TED_Programa.unidade_descentralizadora).all()]

    orgaos_siglas = {
        p.unidade_descentralizadora: p.sigla_unidade_descentralizadora
        for p in db.session.query(TED_Programa.unidade_descentralizadora,
                                  TED_Programa.sigla_unidade_descentralizadora)
                 .filter(TED_Programa.unidade_descentralizadora.isnot(None))
                 .distinct().all()
        if p.sigla_unidade_descentralizadora
    }
    situacoes = [s.situacao_plano for s in db.session.query(TED_PlanoAcao.situacao_plano)
                 .filter(TED_PlanoAcao.situacao_plano.isnot(None))
                 .distinct().order_by(TED_PlanoAcao.situacao_plano).all()]
    anos = [a.ano for a in db.session.query(TED_PlanoAcao.ano)
            .filter(TED_PlanoAcao.ano.isnot(None), TED_PlanoAcao.ano != '')
            .distinct().order_by(TED_PlanoAcao.ano.desc()).all()]
    return {'orgaos': orgaos, 'orgaos_siglas': orgaos_siglas, 'situacoes': situacoes, 'anos': anos}


def coordenacoes_choices():
    """Lista de coordenações (todas, não só a hierarquia do usuário) para o form de execução interna."""
    coords = db.session.query(Coords.sigla).order_by(Coords.sigla).all()
    lista = [(c.sigla, c.sigla) for c in coords]
    lista.insert(0, ('', ''))
    return lista


def programas_cnpq_choices():
    """Lista de Programa_CNPq (sigla + código) para o form de vínculo."""
    programas = Programa_CNPq.query.filter(Programa_CNPq.SIGLA_PROGRAMA.isnot(None))\
                                    .order_by(Programa_CNPq.SIGLA_PROGRAMA).all()
    lista = [(str(p.ID_PROGRAMA), f"{p.SIGLA_PROGRAMA} ({p.COD_PROGRAMA})") for p in programas]
    lista.insert(0, ('', ''))
    return lista


def registrar_execucao_interna(id_plano_acao, coordenacao, sei_cnpq, observacao, usuario_id):
    """Registra uma linha de execução interna (curadoria) para um TED. Não sobrescreve as anteriores."""
    execucao = TED_Execucao_Interna(
        id_plano_acao=id_plano_acao,
        coordenacao=coordenacao,
        sei_cnpq=sei_cnpq,
        observacao=observacao,
        usuario_curador_id=usuario_id,
        data_registro=dt.datetime.now(),
    )
    db.session.add(execucao)
    db.session.commit()
    return execucao


def vincular_programa_cnpq(id_plano_acao, id_programa_cnpq, tipo_evidencia, usuario_id):
    """
    Vincula (ou atualiza o vínculo existente) de um TED a um Programa
    CNPq — curadoria manual, um vínculo por TED.
    """
    existente = TED_Vinculo_ProgramaCNPq.query.filter_by(id_plano_acao=id_plano_acao).first()
    if existente:
        existente.id_programa_cnpq = id_programa_cnpq
        existente.tipo_evidencia = tipo_evidencia
        existente.usuario_curador_id = usuario_id
        existente.data_vinculo = dt.datetime.now()
    else:
        db.session.add(TED_Vinculo_ProgramaCNPq(
            id_plano_acao=id_plano_acao,
            id_programa_cnpq=id_programa_cnpq,
            tipo_evidencia=tipo_evidencia,
            usuario_curador_id=usuario_id,
            data_vinculo=dt.datetime.now(),
        ))
    db.session.commit()


def vincular_instrumento(id_plano_acao, tipo_instrumento, nr_convenio, id_acordo, usuario_id):
    """
    Vincula um TED a um Convênio ou Acordo já existente — curadoria manual.
    Sempre cria uma linha nova (mesmo padrão de registrar_execucao_interna):
    um TED pode financiar vários Acordos/Convênios (até 27, segundo Igor).

    Corrige bug real: a versão antiga buscava um vínculo existente por
    id_plano_acao e sobrescrevia, permitindo só 1 vínculo por TED — os
    demais eram perdidos silenciosamente.
    """
    db.session.add(TED_Vinculo_Instrumento(
        id_plano_acao=id_plano_acao,
        tipo_instrumento=tipo_instrumento,
        nr_convenio=nr_convenio,
        id_acordo=id_acordo,
        usuario_curador_id=usuario_id,
        data_vinculo=dt.datetime.now(),
    ))
    db.session.commit()


def desvincular_instrumento(id_vinculo, usuario_id):
    """Remove um vínculo TED-Convênio/Acordo específico (pode haver vários por TED)."""
    vinculo = TED_Vinculo_Instrumento.query.get_or_404(id_vinculo)
    db.session.delete(vinculo)
    db.session.commit()


def teds_vinculados(tipo_instrumento, nr_convenio=None, id_acordo=None):
    """
    Lista os vínculos de TED_Vinculo_Instrumento pra um Convênio ou Acordo
    específico (tipo_instrumento='convenio'/'acordo'), com o TED_PlanoAcao
    correspondente já carregado — usado nas telas de Convênio/Acordo pra
    mostrar/desvincular os TEDs já associados.
    """
    query = TED_Vinculo_Instrumento.query.filter_by(tipo_instrumento=tipo_instrumento)
    if tipo_instrumento == 'acordo':
        query = query.filter_by(id_acordo=id_acordo)
    else:
        query = query.filter_by(nr_convenio=nr_convenio)
    vinculos = query.all()

    ids_plano = [v.id_plano_acao for v in vinculos]
    planos = {
        p.id: p for p in TED_PlanoAcao.query.filter(TED_PlanoAcao.id.in_(ids_plano)).all()
    } if ids_plano else {}

    return [{'vinculo': v, 'plano': planos.get(v.id_plano_acao)} for v in vinculos]


def teds_choices():
    """
    Lista de TEDs pro campo de busca das telas de Acordo/Convênio: rótulo
    legível (número do TED + início do objeto) em vez do id_plano_acao
    cru — decisão de Igor, mesmo espírito do item C2 do backlog.
    """
    planos = TED_PlanoAcao.query.order_by(TED_PlanoAcao.ano.desc(), TED_PlanoAcao.id.asc()).all()
    lista = []
    for p in planos:
        numero = f"TED {p.numero_ted}" if p.numero_ted else f"Plano {p.id}"
        objeto = (p.objeto or '')[:60]
        rotulo = f"{numero} — {objeto}" if objeto else numero
        lista.append({'id': p.id, 'label': rotulo})
    return lista


def exportar_teds_csv(filtros=None):
    """
    Gera project/static/ted.csv com o conjunto de TEDs que bate no
    filtro atual (igual ao que aparece na tela, mas sem paginar — o
    arquivo sai com todas as linhas filtradas, não só a página visível).
    Mesmo padrão de cria_csv já usado em Convênios/Acordos.
    """
    itens = listar_teds(filtros)

    linhas = []
    for item in itens:
        plano = item['plano']
        valor_total = (plano.valor_beneficiario_especifico or 0) + (plano.valor_chamamento_publico or 0)
        linhas.append([
            plano.numero_ted or f'Plano {plano.id}',
            item['programa'].unidade_descentralizadora if item['programa'] else '',
            plano.situacao_plano or '',
            item['situacao_termo'] or '',
            valor_total,
            plano.vigencia_inicio.strftime('%d/%m/%Y') if plano.vigencia_inicio else '',
            plano.vigencia_fim.strftime('%d/%m/%Y') if plano.vigencia_fim else '',
            plano.ano or '',
            ', '.join(item['coordenacoes']),
            item['programa_cnpq_nome'] or '',
        ])

    caminho_csv = os.path.join(app.root_path, 'static', 'ted.csv')
    cria_csv(
        caminho_csv,
        ['TED', 'Órgão de origem', 'Situação do plano', 'Situação do termo', 'Valor total',
         'Vigência início', 'Vigência fim', 'Ano', 'Coordenação do CNPq', 'Programa CNPq'],
        linhas,
    )
    return caminho_csv


def bi_ted(filtros=None):
    """
    Monta os indicadores da tela de BI de TED (Etapa 3 do roadmap de BI):
    valor total por órgão de origem (no lugar de UF — TED não tem UF
    associada), quantidade por situação, percentual de curadoria (TEDs
    já vinculados a um Programa CNPq) e evolução temporal por ano.

    Reaproveita listar_teds(filtros) — mesma consulta/filtragem/curadoria
    já usada na tela de Gestão — e agrega em Python, em vez de duplicar
    a lógica de join numa query nova.
    """
    itens = listar_teds(filtros)

    valor_total = 0.0
    vinculados = 0

    por_orgao = {}
    por_situacao = {}
    por_ano = {}

    for item in itens:
        plano = item['plano']
        valor = (plano.valor_beneficiario_especifico or 0) + (plano.valor_chamamento_publico or 0)
        valor_total += valor

        if item['programa_cnpq_nome']:
            vinculados += 1

        orgao = item['programa'].unidade_descentralizadora if item['programa'] else 'Não informado'
        item_orgao = por_orgao.setdefault(orgao, {'qtd': 0, 'valor': 0.0})
        item_orgao['qtd'] += 1
        item_orgao['valor'] += valor

        situacao = plano.situacao_plano or 'Não informado'
        item_situacao = por_situacao.setdefault(situacao, {'qtd': 0, 'valor': 0.0})
        item_situacao['qtd'] += 1
        item_situacao['valor'] += valor

        ano = plano.ano or 'Não informado'
        item_ano = por_ano.setdefault(ano, {'qtd': 0, 'valor': 0.0})
        item_ano['qtd'] += 1
        item_ano['valor'] += valor

    total = len(itens)
    percentual_curadoria = round(100 * vinculados / total) if total else 0

    orgaos = sorted(
        [{'orgao': nome, 'qtd': i['qtd'], 'valor': i['valor']} for nome, i in por_orgao.items()],
        key=lambda x: x['valor'], reverse=True,
    )
    situacoes = sorted(
        [{'situacao': nome, 'qtd': i['qtd'], 'valor': i['valor']} for nome, i in por_situacao.items()],
        key=lambda x: x['qtd'], reverse=True,
    )
    evolucao = sorted(
        [{'ano': ano, 'qtd': i['qtd'], 'valor': i['valor']} for ano, i in por_ano.items()],
        key=lambda x: x['ano'],
    )

    # opcoes_filtro() usa as chaves 'orgaos'/'situacoes'/'anos' pras opções de
    # <select> (listas de strings) — nomes diferentes das chaves acima
    # (dados agregados pros gráficos), pra não colidir na hora de montar o retorno
    opcoes = opcoes_filtro()

    return {
        'valor_total': locale.currency(valor_total, symbol=False, grouping=True),
        'quantidade_total': total,
        'percentual_curadoria': percentual_curadoria,
        'vinculados': vinculados,
        'orgaos': orgaos,
        'situacoes': situacoes,
        'evolucao': evolucao,
        'opcoes_orgaos': opcoes['orgaos'],
        'opcoes_situacoes': opcoes['situacoes'],
        'opcoes_anos': opcoes['anos'],
    }
