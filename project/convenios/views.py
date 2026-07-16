"""
.. topic:: Convênios (views)

    Os Convênios são instrumentos de parceria entre o CNPq e Entidades Parceiras Estaduais - EPEs onde
    há repasse direto de recursos das partes para a conta do convênio.

    Os convênios são gerenciados por meio do SICONV, contudo o trâmite administrativo no CNPq demanda os registros em processo
    SEI.

    Um convênio tem atributos relativos ao SEI registrados manualmente. Demais dados podem ser importados do SICONV.

    Os campos relativos ao SEI são:

    * Número do convênio no SICONV
    * Ano do convênio no SICONV
    * Número do processo SEI
    * Sigla da EPE
    * Unidade da Federação da EPE
    * Sigla do programa

    Dados relativos ao importado do SICONV estão em implementação...

.. topic:: Ações relacionadas aos convênios

    * Lista programas da coordenação: lista_programas_pref
    * Atualiza lista de programas da coordenação: prog_pref_update
    * Atualizar dados SEI de um convenio: update_SEI (a ser retirado)
    * Registrar um dados SEI de um convê no sistema: cria_SEI
    * Listar convênios SICONV: lista_convenios_SICONV
    * Mostra detalhes de um determinado convênio: convenio_detalhes
    * Listar demandas de um determinado Convênio: SEI_demandas
    * Listar mensagens SICONV previamente carregadas: msg_siconv
    * Mostra quadro de convênios por UF: quadro_convenios
    * Mostra mapa do Brasil com dados dos convênios: brasil_convenios
    * Lista os convênios conforme selecionado no quado de convênios: lista_convenios_mapa
    * Lista todos os convênios de uma UF selecionada no quado de convênios: lista_convenios_uf
    * Mostra dados gerais dos programas e seus convênios: resumo_convenios

"""

# views.py na pasta convenios

from flask import render_template,url_for,flash, redirect,request,Blueprint
from flask_login import current_user,login_required
from project.convenios.forms import SEIForm, ProgPrefForm, ListaForm, NDForm, ChamadaConvForm
from project.convenios import services


convenios = Blueprint('convenios',__name__,
                            template_folder='templates/convenios')

## lista programas da coordenação

@convenios.route('/lista_programas_pref')
def lista_programas_pref():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos programas da instituição.                                      |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    progs, cod_inst = services.listar_programas()

    return render_template('lista_programas_pref.html', progs=progs, quantidade=len(progs), cod_inst=cod_inst)

#
### ATUALIZAR LISTA DE PROGRAMAS PREFERENCIAIS (PROGRAMAS DA COORDENAÇÃO)

@convenios.route("/<int:cod_prog>/update", methods=['GET', 'POST'])
@login_required
def prog_pref_update(cod_prog):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite atualizar os dados de um programa preferencial (programa da coordenação).             |
    |                                                                                              |
    |Recebe o código do progrma como parâmetro.                                                    |
    +----------------------------------------------------------------------------------------------+
    """

    programa = services.buscar_programa(cod_prog)
    programa_interesse = services.buscar_programa_interesse(cod_prog)

    form = ProgPrefForm()

    if form.validate_on_submit():

        _, status = services.salvar_programa_interesse(
            programa.COD_PROGRAMA, form.sigla.data, form.coord.data, current_user.id)

        if status == 'inserido':
            flash('Programa preferencial inserido!','sucesso')
        else:
            flash('Programa preferencial atualizado!','sucesso')

        return redirect(url_for('convenios.lista_programas_pref'))
    # traz a informação atual do programa
    elif request.method == 'GET':

        form.cod_programa.data = programa.COD_PROGRAMA
        form.desc.data         = programa.NOME_PROGRAMA
        if programa_interesse is None:
            form.sigla.data        = ''
            form.coord.data        = ''
        else:
            form.sigla.data        = programa_interesse.sigla
            form.coord.data        = programa_interesse.coord

    return render_template('add_prog_pref.html',
                           form=form)

## lista convênios

@convenios.route('/<lista>/<coord>/lista_convenios_SICONV', methods=['GET', 'POST'])
def lista_convenios_SICONV(lista,coord):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios.                                                     |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    unidade_coord = services.coord_do_usuario(current_user.id)

    form = ListaForm()

    if form.validate_on_submit():

        coord_form = form.coord.data

        if coord_form == '' or coord_form is None:
            coord_form = '*'

        return redirect(url_for('convenios.lista_convenios_SICONV',lista=lista,coord=coord_form))

    convenio, coord_normalizado, data_carga = services.listar_convenios_siconv(lista, coord, unidade_coord)
    form.coord.data = coord_normalizado

    return render_template('list_convenios.html', convenio = convenio,
                                                  quantidade = len(convenio),
                                                  lista = lista,
                                                  form = form,
                                                  data_carga = data_carga)

#
## Mostra detalhes SICONV de um convênio e permite alterar dados SEI
@convenios.route('/<conv>/convenio_detalhes', methods=['GET', 'POST'])
def convenio_detalhes(conv):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta os dados de um convênio específico.                                          |
    |Recebe o número do convênio como parâmetros.                                           |
    +---------------------------------------------------------------------------------------+
    """
    dadosSEI = services.buscar_dados_sei(conv)

    form = SEIForm()

    if form.validate_on_submit():

        _, status = services.salvar_dados_sei(
            conv, dadosSEI, form.sei.data, form.epe.data, form.fiscal.data, current_user.id)

        if status == 'inserido':
            flash('Inserido registro SEI do convênio!','sucesso')
        else:
            flash('Registro SEI do convênio atualizado!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes',conv=conv,form=form))

    # popula os campos do form quando da consulta (GET ou POST inválido)
    if dadosSEI != None:
        form.nr_convenio.data = conv
        form.sei.data         = dadosSEI.sei
        form.epe.data         = dadosSEI.epe
        form.fiscal.data      = dadosSEI.fiscal
    else:
        form.nr_convenio.data = conv
        form.sei.data         = ''
        form.epe.data         = ''
        form.fiscal.data      = ''

    # calcula os dados de exibição sempre (GET normal ou POST com dados inválidos),
    # evitando o antigo bug de UnboundLocalError quando o form era submetido com erro
    dados = services.detalhes_convenio(conv, dadosSEI)

    services.gerar_pdf_convenio(conv, dados)

    return render_template('convenio_detalhes.html', form=form, **dados)


### associar chamada a Convênio

@convenios.route("/associa_chamada/<conv>", methods=['GET', 'POST'])
@login_required
def associa_chamada(conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite associar uma chamada presente em uma lista a um convênio.                      |
    +---------------------------------------------------------------------------------------+
    """

    form = ChamadaConvForm()
    form.chamada.choices = services.chamadas_disponiveis()

    if form.validate_on_submit():

        services.associar_chamadas(conv, form.chamada.data)

        flash('Chamada(s) associada(s) ao Convênio!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes', conv=conv))

    return render_template('add_chamada_convenio.html',
                            conv=conv,
                            form=form)   


### desassociar chamada de Convênio

@convenios.route("<int:id>/<conv>/desassocia_chamada", methods=['GET', 'POST'])
@login_required
def desassocia_chamada(id,conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite desassociar uma chamada de um convênio.                                        |
    +---------------------------------------------------------------------------------------+
    """

    services.desassociar_chamada(id)

    flash('Chamada desassociada do Convênio!','sucesso')

    return redirect(url_for('convenios.convenio_detalhes', conv=conv))
 

### altera dados de natureza de despesa

@convenios.route("/<id>/<conv>/update_nd", methods=['GET', 'POST'])
@login_required
def update_nd(id,conv):
    """
    +---------------------------------------------------------------------------------------+
    |Permite alterar os dados de natureza de despesa de um empenho.                         |
    |                                                                                       |
    |Recebe o id do empenho como parâmetro.                                                 |
    +---------------------------------------------------------------------------------------+
    """

    nd = services.buscar_nd(id)

    form = NDForm()

    if form.validate_on_submit():

        services.salvar_nd(id, nd, form.nd.data, current_user.id)

        flash('ND atualizada!','sucesso')

        return redirect(url_for('convenios.convenio_detalhes', conv=conv))
    #
    # traz a informação atual
    elif request.method == 'GET':

        if nd != None:
            form.nd.data = nd.nd

    emp = services.buscar_numero_empenho(id)

    return render_template('add_nd.html', form=form, emp=emp)

# lista das demandas relacionadas a um convênio

@convenios.route('/<conv>')
def SEI_demandas (conv):
    """+--------------------------------------------------------------------------------------+
       |Mostra as demandas relacionadas a um processo SEI quando seu NUP é selecionado em uma |
       |lista de convênios.                                                                   |
       |Recebe o número do convênio como parâmetro.                                           |
       +--------------------------------------------------------------------------------------+
    """

    dados = services.demandas_do_convenio(conv)

    return render_template('SEI_demandas.html', **dados)


# lista as mensagens SICONV carregadas

@convenios.route('/msg_siconv')
def msg_siconv ():
    """+--------------------------------------------------------------------------------------+
       |Lista as mensagens da tela inicial do SICONV que foram previamente carregadas em      |
       |procedimento próprio.                                                                 |
       +--------------------------------------------------------------------------------------+
    """

    msgs, data_ref = services.mensagens_siconv()

    return render_template('MSG_Siconv.html',msgs=msgs,data_ref=data_ref)

#
## quadro dos convênios

@convenios.route('/quadro_convenios')
def quadro_convenios():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um quadro de convênios selecionáveis por UF e Programa que estejam           |
    |em execução.                                                                           |
    +---------------------------------------------------------------------------------------+
    """
    dados = services.quadro_convenios(current_user.coord)

    return render_template('quadro_convenios.html', **dados)

#
## convênios no mapa do Brasil

@convenios.route('/brasil_convenios')
def brasil_convenios():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um mapa onde se pode verificar os convênios por UF.                          |
    |Para constar no mapa, o convênio deve ter dados sei.                                   |
    +---------------------------------------------------------------------------------------+
    """
    mapa_html = services.gerar_mapa_brasil_convenios()

    return render_template('brasil_convenios.html', m=mapa_html)
#
## lista convênios do quadro por UF e por programa

@convenios.route('/<uf>/<programa>/lista_convenios_quadro')
def lista_convenios_quadro(uf,programa):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios de uma determinada UF em um programa específico      |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    dados = services.listar_convenios_quadro(current_user.coord, uf, programa)

    return render_template('list_convenios_quadro.html', **dados)

#
## lista convênios do quadro por UF (todos os programas)

@convenios.route('/<uf>/lista_convenios_uf')
def lista_convenios_uf(uf):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios de uma determinada UF (todos os programas)           |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    dados = services.listar_convenios_uf(current_user.coord, uf)

    return render_template('list_convenios_quadro.html', **dados)

## lista convênios do quadro por programa

@convenios.route('/<programa>/lista_convenios_prog')
def lista_convenios_prog(programa):
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos convênios de um programa específico                            |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    dados = services.listar_convenios_prog(current_user.coord, programa)

    return render_template('list_convenios_quadro.html', **dados)


#
## RESUMO convênios

@convenios.route('/resumo_convenios')
def resumo_convenios():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta um resumo dos convênios por programa da coordenação.                         |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    programas_s, data_carga = services.resumo_convenios(current_user.coord)

    return render_template('resumo_convenios.html', programas=programas_s, data_carga=data_carga)
