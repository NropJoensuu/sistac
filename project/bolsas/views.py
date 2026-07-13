"""
.. topic:: Bolsas (views)

    As bolsas são o instrumento básico de fomento dos Acordos, pois o repasse é feito diretamente ao beneficiário,
    sem movimentação financeira entre partícipes.

    No caso do PDCTR, por exemplo, somente uma modalidade de bolsa é utilizada: DCR, cujos níveis e valores ficam
    registrados neste módulo.

    Uma bolsa tem atributos que são registrados no momento de sua criação. Todos são obrigatórios:

    * Modalidade
    * Nível
    * Valor de mensalidade
    * Valor de auxílios

.. topic:: Ações relacionadas às bolsas

    * Listar bolsas cadastradas: lista_bolsas
    * Registrar uma bolsa: cria_bolsa
    * Atualizar dados de uma bolsa: update

    Esta camada (views.py) cuida apenas de roteamento: recebe a requisição,
    delega a regra de negócio para o módulo services.py, e decide o que
    renderizar ou para onde redirecionar. Nenhuma consulta ao banco ou
    conversão de dados deve acontecer aqui.
"""

# views.py na pasta bolsas

from flask import render_template, url_for, flash, redirect, request, Blueprint
from flask_login import login_required, current_user
from project.bolsas.forms import BolsaForm
from project.bolsas import services

bolsas = Blueprint('bolsas', __name__,
                            template_folder='templates/bolsas')

### ATUALIZAR Bolsa

@bolsas.route("/<int:bolsa_id>/update", methods=['GET', 'POST'])
@login_required
def update(bolsa_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite atualizar os dados de uma bolsa selecionado na tela de consulta.               |
    |                                                                                       |
    |Recebe o ID da bolsa como parâmetro.                                                   |
    +---------------------------------------------------------------------------------------+
    """

    bolsa = services.buscar_bolsa(bolsa_id)

    form = BolsaForm()

    if form.validate_on_submit():

        services.atualizar_bolsa(
            bolsa_id=bolsa_id,
            mod=form.mod.data,
            niv=form.niv.data,
            mensalidade_str=form.mensalidade.data,
            auxilio_str=form.auxilio.data,
            usuario_id=current_user.id,
        )

        flash('Modalidade atualizada!')
        return redirect(url_for('bolsas.lista_bolsas'))
    # traz a informação atual da bolsa
    elif request.method == 'GET':
        dados = services.formata_bolsa_para_edicao(bolsa)
        form.mod.data = dados['mod']
        form.niv.data = dados['niv']
        form.mensalidade.data = dados['mensalidade']
        form.auxilio.data = dados['auxilio']

    return render_template('add_bolsa.html', title='Update',
                           form=form)

### CRIAR bolsa

@bolsas.route("/criar", methods=['GET', 'POST'])
@login_required
def cria_bolsa():
    """
    +---------------------------------------------------------------------------------------+
    |Permite registrar, ou alterar, os dados de um bolsa.                                   |
    +---------------------------------------------------------------------------------------+
    """

    form = BolsaForm()

    if form.validate_on_submit():
        services.criar_bolsa(
            mod=form.mod.data,
            niv=form.niv.data,
            mensalidade_str=form.mensalidade.data,
            auxilio_str=form.auxilio.data,
            usuario_id=current_user.id,
        )

        flash('Bolsa registrada!')
        return redirect(url_for('bolsas.lista_bolsas'))

    return render_template('add_bolsa.html', form=form)


## lista bolsas - todos

@bolsas.route('/bolsas')
def lista_bolsas():
    """
    +---------------------------------------------------------------------------------------+
    |Lista as bolsas cadastradas no sistema.                                                |
    +---------------------------------------------------------------------------------------+
    """

    bolsas_dados, bolsas_formatadas = services.listar_bolsas()

    return render_template('list_bolsas.html', quantidade=len(bolsas_dados),
                            bolsas=bolsas_dados, bolsas_s=bolsas_formatadas)
