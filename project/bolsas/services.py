"""
.. topic:: Bolsas (services)

    Camada de regra de negócio do módulo de bolsas, separada das rotas
    (views.py). Aqui ficam as operações de banco de dados e as conversões
    de formato (valores monetários), sem nenhuma dependência de Flask
    (request, redirect, render_template, flash).

    Isso facilita testar a lógica isoladamente e mantém o views.py como
    uma camada fina, só de roteamento.
"""

import locale

from project import db
from project.models import Bolsa
from project.demandas.views import registra_log_auto


def _parse_valor(valor_str):
    """Converte string de valor monetário BR ('1.234,56') para float."""
    return float(valor_str.replace('.', '').replace(',', '.'))


def _formata_valor(valor):
    """Formata um float como string monetária BR, sem símbolo de moeda."""
    return locale.currency(valor, symbol=False, grouping=True)


def buscar_bolsa(bolsa_id):
    """Busca uma bolsa pelo ID, ou levanta 404 se não existir."""
    return Bolsa.query.get_or_404(bolsa_id)


def criar_bolsa(mod, niv, mensalidade_str, auxilio_str, usuario_id):
    """Registra uma nova bolsa e grava o log automático da ação."""
    bolsa = Bolsa(
        mod=mod,
        niv=niv,
        mensalidade=_parse_valor(mensalidade_str),
        auxilio=_parse_valor(auxilio_str),
    )
    db.session.add(bolsa)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'bol')

    return bolsa


def atualizar_bolsa(bolsa_id, mod, niv, mensalidade_str, auxilio_str, usuario_id):
    """Atualiza os dados de uma bolsa existente e grava o log automático."""
    bolsa = buscar_bolsa(bolsa_id)

    bolsa.mod = mod
    bolsa.niv = niv
    bolsa.mensalidade = _parse_valor(mensalidade_str)
    bolsa.auxilio = _parse_valor(auxilio_str)

    db.session.commit()

    registra_log_auto(usuario_id, None, 'bol')

    return bolsa


def formata_bolsa_para_edicao(bolsa):
    """Retorna os campos de uma bolsa formatados para popular o form (GET)."""
    return {
        'mod': bolsa.mod,
        'niv': bolsa.niv,
        'mensalidade': _formata_valor(bolsa.mensalidade),
        'auxilio': _formata_valor(bolsa.auxilio),
    }


def listar_bolsas():
    """
    Retorna as bolsas cadastradas em duas versões:
    - bolsas: dados crus, direto da query
    - bolsas_formatadas: mesma lista, com valores monetários formatados
    """
    bolsas = db.session.query(
        Bolsa.id, Bolsa.mod, Bolsa.niv, Bolsa.mensalidade, Bolsa.auxilio
    ).all()

    bolsas_formatadas = []
    for bolsa in bolsas:
        linha = list(bolsa)
        linha[3] = _formata_valor(linha[3])
        linha[4] = _formata_valor(linha[4])
        bolsas_formatadas.append(linha)

    return bolsas, bolsas_formatadas
