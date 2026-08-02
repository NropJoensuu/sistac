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
    * Vincula um TED a um Convênio ou Acordo existente: vincula_instrumento
"""

from flask import render_template, url_for, flash, redirect, request, Blueprint
from flask_login import current_user, login_required

from project.ted import services
from project.ted.forms import ExecucaoInternaForm, VinculoProgramaCNPqForm, VinculoInstrumentoForm
from project.models import TED_PlanoAcao


ted = Blueprint('ted', __name__, template_folder='templates/ted')


@ted.route('/gestao')
@login_required
def gestao():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a listagem de TEDs do CNPq, com filtros (órgão de origem, situação, Programa |
    |CNPq, ano, busca) e o estado de curadoria de cada um (execução interna, Programa CNPq, |
    |Convênio/Acordo vinculado).                                                             |
    +---------------------------------------------------------------------------------------+
    """
    filtros = {
        'orgao': request.args.get('orgao') or None,
        'situacao': request.args.get('situacao') or None,
        'ano': request.args.get('ano') or None,
        'programa_cnpq': request.args.get('programa_cnpq') or None,
        'busca': request.args.get('busca') or None,
    }

    teds = services.listar_teds(filtros)
    opcoes = services.opcoes_filtro()

    return render_template('gestao.html', teds=teds, filtros=filtros, **opcoes)


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


@ted.route('/<int:id_plano_acao>/vincula_instrumento', methods=['GET', 'POST'])
@login_required
def vincula_instrumento(id_plano_acao):
    """
    +---------------------------------------------------------------------------------------+
    |Vincula um TED a um Convênio ou Acordo já existente no SISTAC (curadoria manual — não  |
    |há chave comum entre os sistemas para automatizar).                                    |
    +---------------------------------------------------------------------------------------+
    """
    plano = TED_PlanoAcao.query.get_or_404(id_plano_acao)

    form = VinculoInstrumentoForm()

    if form.validate_on_submit():
        nr_convenio = form.identificador.data if form.tipo_instrumento.data == 'convenio' else None
        id_acordo = int(form.identificador.data) if form.tipo_instrumento.data == 'acordo' else None

        services.vincular_instrumento(
            id_plano_acao=id_plano_acao,
            tipo_instrumento=form.tipo_instrumento.data,
            nr_convenio=nr_convenio,
            id_acordo=id_acordo,
            usuario_id=current_user.id,
        )
        flash('Instrumento vinculado!', 'sucesso')
        return redirect(url_for('ted.gestao'))

    return render_template('vincula_instrumento.html', form=form, plano=plano)
