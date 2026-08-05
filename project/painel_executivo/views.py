"""
.. topic:: Painel Executivo (views)

    Etapa 4 do roadmap_bi_sistac.md — visão consolidada por Programa CNPq
    dos 3 instrumentos (Convênio, Acordo, TED). Rota pública, sem login,
    mesmo padrão dos outros BIs (Sistema.bi_painel_executivo controla a
    visibilidade).

.. topic:: Ações relacionadas ao Painel Executivo

    * Apresenta o Painel Executivo: painel_executivo
"""

from flask import render_template, request, Blueprint
from project.models import Sistema
from project.painel_executivo import services

painel_executivo = Blueprint('painel_executivo', __name__, template_folder='templates/painel_executivo')


@painel_executivo.route('/')
def painel_executivo_view():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta o Painel Executivo: Captado (TED) e Executado (Convênio+Acordo) separados,    |
    |sem soma entre os dois (ver docstring de services.painel_executivo — evita dupla        |
    |contagem, dinheiro captado via TED que financia um Acordo/Convênio do mesmo Programa    |
    |CNPq). Ranking por Programa CNPq, evolução temporal e cobertura de curadoria por         |
    |instrumento.                                                                            |
    |                                                                                         |
    |Rota pública, sem login — controlada apenas pelo interruptor de sistema                |
    |Sistema.bi_painel_executivo (ligado/desligado só pelo admin master).                     |
    +---------------------------------------------------------------------------------------+
    """
    if Sistema.query.first().bi_painel_executivo != 1:
        return render_template('bi_indisponivel.html', modulo='Painel Executivo')

    filtros = {
        'programa': request.args.get('programa') or None,
        'ano': request.args.get('ano') or None,
    }

    dados = services.painel_executivo(filtros)

    return render_template('painel_executivo.html', **dados)
