"""
.. topic:: TED (views)

    Módulo TED (Etapa 3 do roadmap de BI) — tela de gestão dos Termos de
    Execução Descentralizada recebidos pelo CNPq, carregados da API
    pública do TransfereGov, com curadoria manual de execução interna
    (coordenação/SEI), Programa CNPq e vínculo a Convênio/Acordo.

.. topic:: Ações relacionadas ao TED

    * Lista os TEDs do CNPq, com filtros: gestao
    * Dispara a carga a partir da API do TransfereGov: carrega
    * Registra execução interna (coordenação/SEI) de um TED: registra_execucao
    * Vincula um TED a um Programa CNPq: vincula_programa_cnpq

    O vínculo de um TED a um Convênio/Acordo existente (curadoria manual,
    services.vincular_instrumento/desvincular_instrumento/teds_vinculados/
    teds_choices) é feito a partir da tela de Convênio/Acordo, nunca daqui
    — decisão de Igor (ver proposta_melhorias.md, itens A6/B14/C6): o TED
    pode financiar até 27 Acordos/Convênios, então o caminho natural é
    vincular a partir de quem está sendo financiado, não o inverso. A
    antiga rota /ted/<id>/vincula_instrumento (formulário que pedia o id
    cru do Acordo/Convênio) foi removida por virar código morto depois
    dessa mudança.
"""

from flask import render_template, url_for, flash, redirect, request, Blueprint, abort
from flask_login import current_user, login_required

from project.ted import services
from project.ted.forms import ExecucaoInternaForm, VinculoProgramaCNPqForm
from project.models import TED_PlanoAcao, Sistema


ted = Blueprint('ted', __name__, template_folder='templates/ted')


def _filtro_coord_padrao():
    """
    Resolve o filtro de coordenação da Gestão de TED a partir do parâmetro
    de rota `coord`, mesmo espírito do valor mágico 'usu'/'*' já usado em
    Convênios/Acordos (ver coord_do_usuario em project/convenios/services.py),
    adaptado pro TED — aqui é sigla exata (current_user.coord), sem
    hierarquia de coordenações filhas, já que TED_Execucao_Interna.coordenacao
    é preenchida por curadoria manual, avulsa por TED, não por uma cadeia
    de Programa_Interesse como em Convênios/Acordos.

    Sem `coord` na URL (primeiro acesso), o padrão é 'usu': filtra pela
    coordenação do usuário logado, deixando de fora os TEDs sem nenhuma
    execução interna registrada (não triados) — decisão de Igor, ver
    proposta_melhorias.md. `coord=*` remove o filtro (mostra todos,
    inclusive os não triados).
    """
    coord_param = request.args.get('coord') or 'usu'
    if coord_param == '*':
        return None
    if coord_param == 'usu':
        return current_user.coord
    return coord_param


@ted.route('/gestao')
@login_required
def gestao():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a listagem de TEDs do CNPq, com filtros (órgão de origem, situação, Programa |
    |CNPq, ano, coordenação, busca) e o estado de curadoria de cada um (execução interna,    |
    |Programa CNPq, Convênio/Acordo vinculado). Sem filtro explícito de coordenação na URL,   |
    |vem pré-filtrada pela coordenação do usuário logado (pedido de Igor).                    |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.trab_ted != 1:
        abort(403)

    filtros = {
        'orgao': request.args.get('orgao') or None,
        'situacao': request.args.get('situacao') or None,
        'ano': request.args.get('ano') or None,
        'programa_cnpq': request.args.get('programa_cnpq') or None,
        'busca': request.args.get('busca') or None,
        'coord': _filtro_coord_padrao(),
    }
    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort') or None
    direcao = request.args.get('dir') or 'asc'

    teds, paginacao = services.listar_teds(filtros, page=page, sort=sort, direcao=direcao)
    opcoes = services.opcoes_filtro()
    ultima_carga = services.dados_ultima_carga_ted()
    total_sem_coordenacao = services.total_teds_sem_coordenacao()
    # nome diferente do 'coordenacoes' que já vem em **opcoes (esse é só as
    # coordenações com curadoria já registrada, pro BI) -- aqui é a lista
    # completa de Coords.sigla, pra dar pra escolher qualquer uma no filtro
    # da Gestão, mesmo sem nenhum TED curado ainda nela
    coord_choices = services.coordenacoes_choices()

    return render_template('gestao.html', teds=teds, filtros=filtros, paginacao=paginacao,
                            sort=sort, direcao=direcao, ultima_carga=ultima_carga,
                            total_sem_coordenacao=total_sem_coordenacao,
                            coord_choices=coord_choices, **opcoes)


@ted.route('/carrega', methods=['GET', 'POST'])
@login_required
def carrega():
    """
    +---------------------------------------------------------------------------------------+
    |Dispara a carga dos TEDs do CNPq a partir da API pública do TransfereGov.              |
    +---------------------------------------------------------------------------------------+
    """
    try:
        resultado = services.cargaTED()
        flash(
            f"Carga concluída: {resultado['planos']} planos de ação, "
            f"{resultado['programas']} programas, {resultado['termos']} termos de execução.",
            'sucesso',
        )
    except Exception as e:
        flash(f'Falha ao carregar dados do TransfereGov: {e}', 'perigo')

    return redirect(url_for('ted.gestao'))


@ted.route('/exporta_csv')
@login_required
def exporta_csv():
    """
    +---------------------------------------------------------------------------------------+
    |Gera o CSV com o conjunto de TEDs do filtro atual (mesmo padrão de download já usado    |
    |em Convênios/Acordos) e redireciona pro arquivo estático gerado. Mesmo filtro padrão de |
    |coordenação da tela de Gestão, pra bater com o que está na tela quando o botão é clicado.|
    +---------------------------------------------------------------------------------------+
    """
    if current_user.trab_ted != 1:
        abort(403)

    filtros = {
        'orgao': request.args.get('orgao') or None,
        'situacao': request.args.get('situacao') or None,
        'ano': request.args.get('ano') or None,
        'programa_cnpq': request.args.get('programa_cnpq') or None,
        'busca': request.args.get('busca') or None,
        'coord': _filtro_coord_padrao(),
    }
    services.exportar_teds_csv(filtros)

    return redirect(url_for('static', filename='ted.csv'))


@ted.route('/<int:id_plano_acao>/registra_execucao', methods=['GET', 'POST'])
@login_required
def registra_execucao(id_plano_acao):
    """
    +---------------------------------------------------------------------------------------+
    |Registra uma execução interna (coordenação + SEI do CNPq, curadoria manual) de um TED. |
    |Um TED pode ter mais de uma execução registrada (mais de uma coordenação envolvida).   |
    +---------------------------------------------------------------------------------------+
    """
    plano = TED_PlanoAcao.query.get_or_404(id_plano_acao)

    form = ExecucaoInternaForm()
    form.coordenacao.choices = services.coordenacoes_choices()

    if form.validate_on_submit():
        services.registrar_execucao_interna(
            id_plano_acao=id_plano_acao,
            coordenacao=form.coordenacao.data,
            sei_cnpq=form.sei_cnpq.data,
            observacao=form.observacao.data,
            usuario_id=current_user.id,
        )
        flash('Execução interna registrada!', 'sucesso')
        return redirect(url_for('ted.gestao'))

    return render_template('registra_execucao.html', form=form, plano=plano)


@ted.route('/<int:id_plano_acao>/vincula_programa_cnpq', methods=['GET', 'POST'])
@login_required
def vincula_programa_cnpq(id_plano_acao):
    """
    +---------------------------------------------------------------------------------------+
    |Vincula um TED a um Programa CNPq (curadoria manual — o mesmo "de-para" já usado em     |
    |Acordos, via grupo_programa_cnpq).                                                      |
    +---------------------------------------------------------------------------------------+
    """
    plano = TED_PlanoAcao.query.get_or_404(id_plano_acao)

    form = VinculoProgramaCNPqForm()
    form.programa_cnpq.choices = services.programas_cnpq_choices()

    if form.validate_on_submit():
        services.vincular_programa_cnpq(
            id_plano_acao=id_plano_acao,
            id_programa_cnpq=int(form.programa_cnpq.data),
            tipo_evidencia=form.tipo_evidencia.data,
            usuario_id=current_user.id,
        )
        flash('Programa CNPq vinculado!', 'sucesso')
        return redirect(url_for('ted.gestao'))

    return render_template('vincula_programa_cnpq.html', form=form, plano=plano)


@ted.route('/bi_ted')
def bi_ted():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a visão consolidada de BI de TED: valor por órgão de origem (sigla), quantidade|
    |por situação e por coordenação do CNPq, percentual de curadoria (vínculo a Programa      |
    |CNPq) e evolução temporal.                                                               |
    |                                                                                         |
    |Rota pública, sem login — controlada apenas pelo interruptor de sistema                |
    |Sistema.bi_ted (ligado/desligado só pelo admin master). Por isso o filtro de coordenação |
    |aqui é uma sigla exata escolhida no <select> — sem o valor mágico 'usu' da Gestão, que    |
    |depende de current_user (visitante anônimo não tem coordenação).                         |
    +---------------------------------------------------------------------------------------+
    """
    if Sistema.query.first().bi_ted != 1:
        return render_template('bi_indisponivel.html', modulo='TED')

    filtros = {
        'orgao': request.args.get('orgao') or None,
        'situacao': request.args.get('situacao') or None,
        'ano': request.args.get('ano') or None,
        'programa_cnpq': request.args.get('programa_cnpq') or None,
        'coord': request.args.get('coord') or None,
    }

    dados = services.bi_ted(filtros)

    return render_template('bi_ted.html', filtros=filtros, **dados)
