"""
.. topic:: Instrumentos (services)

    Camada de regra de negócio do módulo de instrumentos, separada das
    rotas (views.py). Aqui ficam as consultas ao banco e as conversões
    de formato (datas, valores monetários), sem nenhuma dependência de
    Flask (request, redirect, render_template, flash).
"""

import locale
from datetime import datetime

from project import db
from project.models import User, Demanda, Coords, Instrumento
from project.demandas.views import registra_log_auto


def _parse_valor(valor_str):
    """Converte string de valor monetário BR ('1.234,56') para float."""
    return float(valor_str.replace('.', '').replace(',', '.'))


def _formata_valor(valor):
    """Formata um float como string monetária BR, sem símbolo de moeda."""
    return locale.currency(valor, symbol=False, grouping=True)


def listar_instrumentos(lista, coord):
    """
    Retorna a lista de instrumentos filtrada por coordenação e critério
    ('todos' ou 'em execução'), já formatada para exibição, junto com o
    valor de coordenação normalizado (para popular o form de filtro).
    """
    hoje = datetime.today()

    if coord == '*':
        coord_normalizado = ''
        coordenacao = db.session.query(Coords.id, Coords.sigla).subquery()
    else:
        coord_normalizado = coord
        coordenacao = db.session.query(Coords.id, Coords.sigla)\
                                .filter(Coords.sigla == coord)\
                                .subquery()

    query = db.session.query(
        Instrumento.id, Instrumento.coord, Instrumento.nome,
        Instrumento.contraparte, Instrumento.sei, Instrumento.descri,
        Instrumento.data_inicio, Instrumento.data_fim, Instrumento.valor,
        coordenacao.c.sigla
    ).join(coordenacao, coordenacao.c.sigla == Instrumento.coord)

    if lista == 'todos':
        instrumentos_v = query.order_by(Instrumento.nome).all()
    elif lista == 'em execução':
        instrumentos_v = query.filter(
            Instrumento.data_fim >= hoje,
            Instrumento.data_inicio <= hoje
        ).order_by(Instrumento.data_fim, Instrumento.nome).all()
    else:
        instrumentos_v = []

    instrumentos = []
    for instrumento in instrumentos_v:
        inicio = instrumento.data_inicio.strftime('%x') if instrumento.data_inicio is not None else None

        if instrumento.data_fim is not None:
            fim = instrumento.data_fim.strftime('%x')
            dias = (instrumento.data_fim - hoje).days
        else:
            fim = None
            dias = 999

        valor = _formata_valor(instrumento.valor)

        instrumentos.append([
            instrumento.id, instrumento.sigla, instrumento.nome,
            instrumento.contraparte, instrumento.sei, inicio, fim,
            valor, dias, instrumento.descri
        ])

    return instrumentos, coord_normalizado


def buscar_instrumento(instrumento_id):
    """Busca um instrumento pelo ID, ou levanta 404 se não existir."""
    return Instrumento.query.get_or_404(instrumento_id)


def criar_instrumento(coord, nome, contraparte, sei, data_inicio, data_fim,
                       valor_str, descri, usuario_id):
    """Registra um novo instrumento e grava o log automático da ação."""
    instrumento = Instrumento(
        coord=coord, nome=nome, contraparte=contraparte, sei=sei,
        data_inicio=data_inicio, data_fim=data_fim,
        valor=_parse_valor(valor_str), descri=descri,
    )
    db.session.add(instrumento)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'itm')

    return instrumento


def atualizar_instrumento(instrumento_id, coord, nome, contraparte, sei,
                           data_inicio, data_fim, valor_str, descri, usuario_id):
    """Atualiza os dados de um instrumento existente e grava o log automático."""
    instrumento = buscar_instrumento(instrumento_id)

    instrumento.coord = coord
    instrumento.nome = nome
    instrumento.sei = sei
    instrumento.contraparte = contraparte
    instrumento.data_inicio = data_inicio
    instrumento.data_fim = data_fim
    instrumento.valor = _parse_valor(valor_str)
    instrumento.descri = descri

    db.session.commit()

    registra_log_auto(usuario_id, None, 'itm')

    return instrumento


def formata_instrumento_para_edicao(instrumento):
    """Retorna os campos de um instrumento formatados para popular o form (GET)."""
    return {
        'coord': instrumento.coord,
        'nome': instrumento.nome,
        'sei': instrumento.sei,
        'contraparte': instrumento.contraparte,
        'data_inicio': instrumento.data_inicio,
        'data_fim': instrumento.data_fim,
        'valor': _formata_valor(instrumento.valor),
        'descri': instrumento.descri,
    }


def demandas_do_instrumento(instrumento_id):
    """
    Retorna os dados necessários para exibir as demandas relacionadas
    a um instrumento: contagem, lista de demandas, SEI e autores.
    """
    instrumento_SEI = db.session.query(Instrumento.sei, Instrumento.nome)\
                                .filter_by(id=instrumento_id).first()

    SEI = instrumento_SEI.sei
    SEI_s = str(SEI).split('/')[0] + '_' + str(SEI).split('/')[1]

    demandas_count = Demanda.query.filter(Demanda.sei.like('%' + SEI + '%')).count()

    demandas = Demanda.query.filter(Demanda.sei.like('%' + SEI + '%'))\
                            .order_by(Demanda.data.desc()).all()

    autores = []
    for demanda in demandas:
        autores.append(str(User.query.filter_by(id=demanda.user_id).first()).split(';')[0])

    dados = [instrumento_SEI.nome, SEI_s, '0', '0']

    return {
        'demandas_count': demandas_count,
        'demandas': demandas,
        'sei': SEI,
        'autores': autores,
        'dados': dados,
    }


def excluir_instrumento(instrumento_id, usuario_id):
    """Remove um instrumento e grava o log automático da exclusão."""
    instrumento = buscar_instrumento(instrumento_id)

    db.session.delete(instrumento)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'xtm')
