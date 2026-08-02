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

import requests
from sqlalchemy import or_

from project import db
from project.models import (
    TED_Programa, TED_PlanoAcao, TED_TermoExecucao, TED_Execucao_Interna,
    TED_Vinculo_ProgramaCNPq, TED_Vinculo_Instrumento, Programa_CNPq, Coords,
)

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

    return {
        'programas': len(programas),
        'planos': len(planos),
        'termos': len(termos),
    }


def listar_teds(filtros=None):
    """
    Monta a listagem da tela de gestão: TED_PlanoAcao + TED_Programa +
    TED_TermoExecucao (situação do termo) + estado de curadoria
    (Programa CNPq vinculado? execução interna registrada? instrumento
    vinculado?), com filtros opcionais.
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

    linhas = query.order_by(TED_PlanoAcao.ano.desc()).all()

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

    instrumentos_vinculados = {
        v.id_plano_acao: v
        for v in TED_Vinculo_Instrumento.query.filter(TED_Vinculo_Instrumento.id_plano_acao.in_(ids_plano)).all()
    } if ids_plano else {}

    if filtros.get('programa_cnpq') == 'vinculado':
        linhas = [(p, prog) for p, prog in linhas if p.id in programas_vinculados]
    elif filtros.get('programa_cnpq') == 'pendente':
        linhas = [(p, prog) for p, prog in linhas if p.id not in programas_vinculados]

    resultado = []
    for plano, programa in linhas:
        vinculo_prog = programas_vinculados.get(plano.id)
        programa_cnpq_nome = None
        if vinculo_prog:
            pc = Programa_CNPq.query.get(vinculo_prog.id_programa_cnpq)
            programa_cnpq_nome = pc.SIGLA_PROGRAMA if pc else None

        instrumento = instrumentos_vinculados.get(plano.id)

        resultado.append({
            'plano': plano,
            'programa': programa,
            'situacao_termo': situacoes_termo.get(plano.id),
            'programa_cnpq_nome': programa_cnpq_nome,
            'execucoes': execucoes_por_plano.get(plano.id, []),
            'instrumento': instrumento,
        })

    return resultado


def opcoes_filtro():
    """Opções para os selects de filtro da tela de gestão."""
    orgaos = [o.unidade_descentralizadora for o in db.session.query(TED_Programa.unidade_descentralizadora)
              .filter(TED_Programa.unidade_descentralizadora.isnot(None))
              .distinct().order_by(TED_Programa.unidade_descentralizadora).all()]
    situacoes = [s.situacao_plano for s in db.session.query(TED_PlanoAcao.situacao_plano)
                 .filter(TED_PlanoAcao.situacao_plano.isnot(None))
                 .distinct().order_by(TED_PlanoAcao.situacao_plano).all()]
    anos = [a.ano for a in db.session.query(TED_PlanoAcao.ano)
            .filter(TED_PlanoAcao.ano.isnot(None), TED_PlanoAcao.ano != '')
            .distinct().order_by(TED_PlanoAcao.ano.desc()).all()]
    return {'orgaos': orgaos, 'situacoes': situacoes, 'anos': anos}


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
    """Vincula (ou atualiza) um TED a um Convênio ou Acordo já existente — curadoria manual."""
    existente = TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano_acao).first()
    if existente:
        existente.tipo_instrumento = tipo_instrumento
        existente.nr_convenio = nr_convenio
        existente.id_acordo = id_acordo
        existente.usuario_curador_id = usuario_id
        existente.data_vinculo = dt.datetime.now()
    else:
        db.session.add(TED_Vinculo_Instrumento(
            id_plano_acao=id_plano_acao,
            tipo_instrumento=tipo_instrumento,
            nr_convenio=nr_convenio,
            id_acordo=id_acordo,
            usuario_curador_id=usuario_id,
            data_vinculo=dt.datetime.now(),
        ))
    db.session.commit()
