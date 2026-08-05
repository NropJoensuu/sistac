"""
.. topic:: Painel Executivo (services) — Etapa 4 do roadmap_bi_sistac.md

    Visão consolidada por Programa CNPq dos 3 instrumentos (Convênio,
    Acordo, TED), para a alta gestão. Ver `etapa4_painel_executivo.md`
    (proposta funcional) e a correção registrada em
    `correcao_painel_executivo_dupla_contagem.txt`.

    **Captado x Executado — por que não existe "valor total consolidado"
    único nesta tela**: TED representa dinheiro CAPTADO pelo CNPq (de
    outro órgão — MCTI, FNDCT etc.), que o CNPq depois EXECUTA via
    Convênio ou Acordo. Se um TED financia um Acordo/Convênio do mesmo
    Programa CNPq, somar os três instrumentos num total único conta o
    mesmo real duas vezes (uma como captação, outra como execução) — o
    tipo de erro caro num painel para Presidência/Diretoria. Por isso,
    todo indicador aqui é reportado em **dois grupos separados, nunca
    somados entre si**: "Captado" (TED) e "Executado" (Convênio +
    Acordo — esses dois são seguros de somar, são instrumentos de
    execução paralelos sem sobreposição conhecida). A reconciliação
    exata de qual TED financiou qual Acordo/Convênio específico é item
    futuro (proposta_melhorias.md, item 6.6), fora do escopo desta etapa.

    **Cobertura de vínculo a Programa CNPq**: nem todo Convênio/Acordo/
    TED já tem um Programa CNPq confirmado (curadoria manual, em graus
    de maturidade bem diferentes por instrumento — ver
    `etapa4_painel_executivo.md`, seção 2). Só o valor com vínculo
    confirmado entra no ranking por programa (Nível 2); o indicador de
    cobertura mostra que fração do valor total isso representa, pra não
    esconder o quanto ainda está pendente de curadoria.

    "Programa Estratégico" (Nível 3 do esboço original) fica de fora
    desta etapa: exige uma tabela nova (`ProgramaEstrategico` + vínculo
    N:N com Programa CNPq) e curadoria manual própria, ainda não feita
    — decisão já registrada antes de começar a programar.
"""

from project import db
from project.convenios.services import none_0
from project.models import (
    Convenio, Convenio_Programa_CNPq, Acordo, grupo_programa_cnpq, Programa_CNPq,
)
from project.ted.services import listar_teds


def _executado_convenios(filtro_ano=None, filtro_programa=None):
    """
    Valor "Executado" via Convênio: total (repasse + contrapartida) e
    por Programa CNPq (só os já vinculados via Convenio_Programa_CNPq,
    curadoria manual histórica da COPES).
    """
    convenios = Convenio.query.all()
    if filtro_ano:
        convenios = [c for c in convenios if c.ANO == filtro_ano]

    valor_total = sum(none_0(c.VL_REPASSE_CONV) + none_0(c.VL_CONTRAPARTIDA_CONV) for c in convenios)

    vinculos = {v.nr_convenio: v.id_programa for v in Convenio_Programa_CNPq.query.all()}
    programas = {p.ID_PROGRAMA: p.SIGLA_PROGRAMA for p in Programa_CNPq.query.all()}

    valor_vinculado = 0.0
    por_programa = {}
    por_ano = {}

    for c in convenios:
        valor = none_0(c.VL_REPASSE_CONV) + none_0(c.VL_CONTRAPARTIDA_CONV)

        ano = c.ANO or 'Não informado'
        por_ano.setdefault(ano, 0.0)
        por_ano[ano] += valor

        id_programa = vinculos.get(c.NR_CONVENIO)
        if id_programa is None:
            continue
        sigla = programas.get(id_programa) or 'Não identificado'
        if filtro_programa and sigla != filtro_programa:
            continue

        valor_vinculado += valor
        por_programa.setdefault(sigla, 0.0)
        por_programa[sigla] += valor

    return {
        'valor_total': valor_total, 'valor_vinculado': valor_vinculado,
        'por_programa': por_programa, 'por_ano': por_ano,
    }


def _executado_acordos(filtro_ano=None, filtro_programa=None):
    """
    Valor "Executado" via Acordo: total (CNPq + EPE) e por Programa
    CNPq (via grupo_programa_cnpq — vínculo já existe desde o cadastro
    do acordo, ao contrário da curadoria Processo-Mãe <-> Acordo, que é
    sobre uma dimensão diferente e não entra aqui, ver docstring do
    módulo).
    """
    acordos = Acordo.query.all()
    if filtro_ano:
        acordos = [a for a in acordos if a.data_inicio and str(a.data_inicio.year) == filtro_ano]

    valor_total = sum(none_0(a.valor_cnpq) + none_0(a.valor_epe) for a in acordos)

    vinculos_rows = db.session.query(grupo_programa_cnpq.id_acordo, Programa_CNPq.SIGLA_PROGRAMA)\
                              .join(Programa_CNPq, Programa_CNPq.ID_PROGRAMA == grupo_programa_cnpq.id_programa)\
                              .all()
    programa_por_acordo = {}
    for id_acordo, sigla in vinculos_rows:
        programa_por_acordo.setdefault(id_acordo, sigla)

    valor_vinculado = 0.0
    por_programa = {}
    por_ano = {}

    for a in acordos:
        valor = none_0(a.valor_cnpq) + none_0(a.valor_epe)

        ano = str(a.data_inicio.year) if a.data_inicio else 'Não informado'
        por_ano.setdefault(ano, 0.0)
        por_ano[ano] += valor

        sigla = programa_por_acordo.get(a.id)
        if sigla is None:
            continue
        if filtro_programa and sigla != filtro_programa:
            continue

        valor_vinculado += valor
        por_programa.setdefault(sigla, 0.0)
        por_programa[sigla] += valor

    return {
        'valor_total': valor_total, 'valor_vinculado': valor_vinculado,
        'por_programa': por_programa, 'por_ano': por_ano,
    }


def _captado_ted(filtro_ano=None, filtro_programa=None):
    """
    Valor "Captado" via TED: reaproveita listar_teds() (mesma
    query/curadoria já usada na Gestão/BI de TED) e agrega em Python.
    Só entra em "por_programa" o TED já vinculado a um Programa CNPq
    (TED_Vinculo_ProgramaCNPq) — curadoria ainda pouco madura pra TED
    (ver etapa4_painel_executivo.md, seção 2).
    """
    itens = listar_teds({'ano': filtro_ano} if filtro_ano else None)

    valor_total = 0.0
    valor_vinculado = 0.0
    por_programa = {}
    por_ano = {}

    for item in itens:
        plano = item['plano']
        valor = none_0(plano.valor_beneficiario_especifico) + none_0(plano.valor_chamamento_publico)
        valor_total += valor

        ano = plano.ano or 'Não informado'
        por_ano.setdefault(ano, 0.0)
        por_ano[ano] += valor

        sigla = item['programa_cnpq_nome']
        if sigla is None:
            continue
        if filtro_programa and sigla != filtro_programa:
            continue

        valor_vinculado += valor
        por_programa.setdefault(sigla, 0.0)
        por_programa[sigla] += valor

    return {
        'valor_total': valor_total, 'valor_vinculado': valor_vinculado,
        'por_programa': por_programa, 'por_ano': por_ano,
    }


def _cobertura(valor_vinculado, valor_total):
    return round(100 * valor_vinculado / valor_total) if valor_total else 0


def painel_executivo(filtros=None):
    """
    Monta os indicadores do Painel Executivo: cards de Captado/Executado
    (separados, nunca somados — ver docstring do módulo), ranking Top
    Programas CNPq (ordenado por Executado, com TED como coluna
    separada, não empilhada no mesmo total), evolução temporal com 2
    séries (Captado/Executado), e cobertura de curadoria por instrumento.

    Filtros aceitos: `ano`, `programa` (SIGLA_PROGRAMA), `instrumento`
    ('executado'/'captado'/None para mostrar os dois).
    """
    filtros = filtros or {}
    filtro_ano = filtros.get('ano') or None
    filtro_programa = filtros.get('programa') or None

    conv = _executado_convenios(filtro_ano, filtro_programa)
    acordo = _executado_acordos(filtro_ano, filtro_programa)
    ted = _captado_ted(filtro_ano, filtro_programa)

    valor_total_executado = conv['valor_total'] + acordo['valor_total']
    valor_vinculado_executado = conv['valor_vinculado'] + acordo['valor_vinculado']
    cobertura_executado = _cobertura(valor_vinculado_executado, valor_total_executado)

    valor_total_captado = ted['valor_total']
    valor_vinculado_captado = ted['valor_vinculado']
    cobertura_captado = _cobertura(valor_vinculado_captado, valor_total_captado)

    # ranking por Programa CNPq — Executado (Convênio+Acordo) como
    # critério de ordenação, TED mostrado como coluna separada
    programas = set(conv['por_programa']) | set(acordo['por_programa']) | set(ted['por_programa'])
    ranking = []
    for sigla in programas:
        valor_convenio = conv['por_programa'].get(sigla, 0.0)
        valor_acordo = acordo['por_programa'].get(sigla, 0.0)
        valor_ted = ted['por_programa'].get(sigla, 0.0)
        ranking.append({
            'programa': sigla,
            'executado': valor_convenio + valor_acordo,
            'convenio': valor_convenio,
            'acordo': valor_acordo,
            'captado_ted': valor_ted,
        })
    ranking.sort(key=lambda x: x['executado'], reverse=True)

    qtd_programas_com_instrumento = len(programas)

    # evolução temporal — 2 séries (Captado / Executado), não somadas
    anos = set(conv['por_ano']) | set(acordo['por_ano']) | set(ted['por_ano'])
    evolucao = sorted([
        {
            'ano': ano,
            'executado': conv['por_ano'].get(ano, 0.0) + acordo['por_ano'].get(ano, 0.0),
            'captado': ted['por_ano'].get(ano, 0.0),
        }
        for ano in anos
    ], key=lambda x: x['ano'])

    opcoes_programa = sorted(programas)
    opcoes_ano = sorted({a for a in anos if a != 'Não informado'}, reverse=True)

    return {
        'valor_total_executado': valor_total_executado,
        'valor_total_captado': valor_total_captado,
        'cobertura_executado': cobertura_executado,
        'cobertura_captado': cobertura_captado,
        'qtd_programas_com_instrumento': qtd_programas_com_instrumento,
        'ranking': ranking[:15],
        'evolucao': evolucao,
        'filtros': filtros,
        'opcoes_programa': opcoes_programa,
        'opcoes_ano': opcoes_ano,
    }
