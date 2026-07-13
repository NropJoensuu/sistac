"""
.. topic:: Instrumentos (views)

    Os Instrumentos são objetos que a coordenação necessita de um registro mínimo para referência em demandas.

    Um instrumento tem atributos que são registrados no momento de sua criação. Todos são obrigatórios:

    * Título
    * Contraparte
    * Número do processo SEI
    * Data de início
    * Data de término
    * Valor associado
    * Descrição

.. topic:: Ações relacionadas aos instrumentos

    * Listar instrumentos por edição do programa: lista_instrumentos
    * Atualizar/visualizar dados de um instrumento: update
    * Registrar um instrumento no sistema: cria_instrumento
    * Listar demandas de um determinado instrumento: instrumento_demandas

    Esta camada (views.py) cuida apenas de roteamento: recebe a requisição,
    delega a regra de negócio para o módulo services.py, e decide o que
    renderizar ou para onde redirecionar. Nenhuma consulta ao banco ou
    conversão de dados deve acontecer aqui.
"""

# views.py na pasta instrumentos

from flask import render_template, url_for, flash, redirect, request, Blueprint, abort
from flask_login import current_user, login_required
from project.instrumentos.forms import InstrumentoForm, ListaForm
from project.instrumentos import services

instrumentos = Blueprint('instrumentos',__name__,
                            template_folder='templates/instrumentos')


@instrumentos.route('/<lista>/<coord>/lista_instrumentos', methods=['GET', 'POST'])
def lista_instrumentos(lista,coord):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos instrumentos por edição do programa.                           |
    |                                                                                       |
    |O instrumento é algo tratado pela área técnica que justifica um registro específico.   |
    |e que não pode ser caracterizado como convênio ou acordo.                              |
    |Um contratao é um exemplo de instrumento.                                              |
    |                                                                                       |
    |No topo da tela há a opção de se inserir um novo instrumento e o número sequencial     |
    |de cada instrumento (#), ao ser clicado, permite que seus dados possam ser editados.   |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    form = ListaForm()

    if form.validate_on_submit():

        coord_form = form.coord.data

        if coord_form == '' or coord_form is None:
            coord_form = '*'

        return redirect(url_for('instrumentos.lista_instrumentos',lista=lista,coord=coord_form))

    instrumentos_lista, coord_normalizado = services.listar_instrumentos(lista, coord)
    form.coord.data = coord_normalizado

    return render_template('lista_instrumentos.html', instrumentos=instrumentos_lista,
                            quantidade=len(instrumentos_lista), lista=lista, form=form)


### ATUALIZAR Instrumento

@instrumentos.route("/<int:instrumento_id>/update", methods=['GET', 'POST'])
@login_required
def update(instrumento_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite atualizar os dados de um instrumento selecionado na tela de consulta.          |
    |                                                                                       |
    |Recebe o ID do instrumento como parâmetro.                                             |
    +---------------------------------------------------------------------------------------+
    """

    instrumento = services.buscar_instrumento(instrumento_id)

    form = InstrumentoForm()

    if form.validate_on_submit():

        services.atualizar_instrumento(
            instrumento_id=instrumento_id,
            coord=form.coord.data,
            nome=form.nome.data,
            contraparte=form.contraparte.data,
            sei=form.sei.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            valor_str=form.valor.data,
            descri=form.descri.data,
            usuario_id=current_user.id,
        )

        flash('Instrumento atualizado!')
        return redirect(url_for('instrumentos.lista_instrumentos',lista='todos',coord = '*'))
    # traz a informação atual do instrumento
    elif request.method == 'GET':
        dados = services.formata_instrumento_para_edicao(instrumento)
        form.coord.data        = dados['coord']
        form.nome.data         = dados['nome']
        form.sei.data          = dados['sei']
        form.contraparte.data  = dados['contraparte']
        form.data_inicio.data  = dados['data_inicio']
        form.data_fim.data     = dados['data_fim']
        form.valor.data        = dados['valor']
        form.descri.data       = dados['descri']

    return render_template('add_instrumento.html', title='Update',
                           form=form, id=instrumento_id)

### CRIAR Instrumento

@instrumentos.route("/criar", methods=['GET', 'POST'])
@login_required
def cria_instrumento():
    """
    +---------------------------------------------------------------------------------------+
    |Permite registrar os dados de um instrumento.                                               |
    +---------------------------------------------------------------------------------------+
    """

    form = InstrumentoForm()

    if form.validate_on_submit():
        services.criar_instrumento(
            coord=form.coord.data,
            nome=form.nome.data,
            contraparte=form.contraparte.data,
            sei=form.sei.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            valor_str=form.valor.data,
            descri=form.descri.data,
            usuario_id=current_user.id,
        )

        flash('Instrumento criado!')
        return redirect(url_for('instrumentos.lista_instrumentos',lista='todos',coord = '*'))


    return render_template('add_instrumento.html', form=form, id=0 )


# lista das demandas relacionadas a um instrumento

@instrumentos.route('/<instrumento_id>/instrumento_demandas')
def instrumento_demandas (instrumento_id):
    """+--------------------------------------------------------------------------------------+
       |Mostra as demandas relacionadas a um instrumento quando seu NUP é selecionado em uma  |
       |lista de instrumentos.                                                                |
       |Recebe o id do instrumento como parâmetro.                                            |
       +--------------------------------------------------------------------------------------+
    """

    dados = services.demandas_do_instrumento(instrumento_id)

    return render_template('SEI_demandas.html', demandas_count=dados['demandas_count'],
                            demandas=dados['demandas'], sei=dados['sei'],
                            autores=dados['autores'], dados=dados['dados'])

#
#removendo uma atividade do plano de trabalho

@instrumentos.route('/<int:instrumento_id>/delete', methods=['GET','POST'])
@login_required
def delete_instrumento(instrumento_id):
    """+----------------------------------------------------------------------+
       |Permite que o chefe, se logado, a remova um um instrumento.           |
       |                                                                      |
       |Recebe o ID do instrumento como parâmetro.                            |
       +----------------------------------------------------------------------+

    """
    if current_user.ativo == 0 or (current_user.despacha0 == 0 and current_user.despacha == 0 and current_user.despacha2 == 0):
        abort(403)

    services.excluir_instrumento(instrumento_id, current_user.id)

    flash ('Instrumento excluído!','sucesso')

    return redirect(url_for('instrumentos.lista_instrumentos',lista='todos',coord = '*'))
