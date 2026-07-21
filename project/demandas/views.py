"""
.. topic:: Demandas (views)

    Compõe o trabalho diário da coordenação. Surgem na medida que as tarefas são executadas na coordenação.
    O técnico cria a demanda para si em função de uma solicitação superior, de um colega, vinda de fora ou até mesmo
    por iniciativa própria, quando se tratar de necessidade de trabalho.

    Uma demanda tem atributos que são registrados no momento de sua criação:

    * Processo SEI relacionado (obrigatório)
    * Tipo (obrigatório e conforme valores prédefinidos)
    * Convênio e ano do convênio (quando for o caso)
    * Atividade do plano de trabalho
    * Título
    * Descrição
    * Se necessita despacho/apreciação superior
    * Se está concluída ou em andamento

.. topic:: Ações relacionadas às demandas

    * Listar atividades do plano de trabalho: plano_trabalho
    * Atualizar atividade do plano de trabalho: update_plano_trabalho
    * Inserir atividade no plano de trabalho: cria_atividade
    * Deleta um tipo de demanda: delete_tipo_demanda
    * Listar tipos de demanda: lista_tipos
    * Atualizar tipos de demandas: tipos_update
    * Inserir novo tipo de demanda: cria_tipo_demanda
    * Inserir novo passo para um tipo de demanda: cria_passo_tipo
    * Atualizar um passo de um tipo de demanda: update_passo_tipo
    * Listar passos de um tipo de demanda: lista_passos_tipos
    * Criar demandas: cria_demanda
    * Confirma criação de demanda: confirma_cria_demanda
    * Criar demamanda a partir de um acordo ou convênio: acordo_convenio_demanda
    * Confirma criação de demanda a partir de acordo ou convênio: confirma_acordo_convenio_demanda
    * Ler demandas: demanda
    * Registrar data de verificação de uma demanda: verifica
    * Listar demandas: list_demandas
    * Lista demandas não concluídas - lista RDU: prioriza
    * Atualizar demandas: update_demanda
    * Transferir demanda: transfer_demanda
    * Avocar demanda: avocar_demanda
    * Admin altera data de conclusão: admin_altera_demanda
    * Remover demandas: delete_demanda
    * Procurar demandas: pesquisa_demanda
    * Lista resultado da procura: list_pesquisa
    * Registrar despachos: cria_despacho
    * Aferir demandas: afere_demanda
    * Registrar providências: cria_providencia
    * Resumo e estatísticas das demandas: demandas_resumo

"""

# views.py dentro da pasta demandas

from flask import render_template, url_for, flash, request, redirect, Blueprint, abort
from flask_login import current_user, login_required
from project import db
from project.models import Demanda, User, Tipos_Demanda
from project.demandas.forms import DemandaForm1, DemandaForm, Demanda_ATU_Form, DespachoForm, ProvidenciaForm, PesquisaForm,\
                                   Tipos_DemandaForm, TransferDemandaForm, Admin_Altera_Demanda_Form, PesosForm, Afere_Demanda_Form,\
                                   Plano_TrabalhoForm, Pdf_Form, CoordForm, Passos_Tipos_Form
from datetime import datetime

demandas = Blueprint("demandas",__name__,
                        template_folder='templates/demandas')

from project.demandas import services
# Re-exportado para não quebrar os 7+ módulos que já fazem
# "from project.demandas.views import registra_log_auto".
from project.demandas.services import registra_log_auto, send_email, send_async_email

#
## lista plano de trabalho

@demandas.route('/plano_trabalho')
@login_required
def plano_trabalho():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta o plano de trabalho da unidade do usuário logado.                            |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    atividades = services.listar_plano_trabalho(current_user.coord)

    return render_template('plano_trabalho.html', atividades = atividades, quantidade=len(atividades))

#
### atualiza atividade no plano de trabalho

@demandas.route("/<int:id>/update_plano_trabalho", methods=['GET', 'POST'])
@login_required
def update_plano_trabalho(id):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite atualizar as atividades cadastradas no plano de trabalho.                             |
    |                                                                                              |
    |Recebe o id da atividade no plano como parâmetro.                                             |
    +----------------------------------------------------------------------------------------------+
    """

    atividade = services.buscar_atividade(id)

    form = Plano_TrabalhoForm()

    form.unidade.choices = services.unidades_choices(current_user.coord)

    if form.validate_on_submit():

        services.atualizar_atividade(
            id=id,
            atividade_sigla=form.atividade_sigla.data,
            atividade_desc=form.atividade_desc.data,
            natureza=form.natureza.data,
            meta=form.horas_semana.data,
            situa=form.situa.data,
            unidade=form.unidade.data,
            usuario_id=current_user.id,
        )

        flash('Atividade atualizada no Plano de Trabalho!')
        return redirect(url_for('demandas.plano_trabalho'))

    elif request.method == 'GET':

        form.atividade_sigla.data = atividade.atividade_sigla
        form.atividade_desc.data  = atividade.atividade_desc
        form.natureza.data        = atividade.natureza
        form.horas_semana.data    = atividade.meta
        form.situa.data           = atividade.situa
        form.unidade.data         = atividade.unidade

    return render_template('add_atividade.html', form=form, id=id)

### inserir atividade no plano de trabalho

@demandas.route("/cria_atividade", methods=['GET', 'POST'])
@login_required
def cria_atividade():
    """
    +---------------------------------------------------------------------------------------+
    |Permite inserir atividade no plano de trabalho.                                        |
    +---------------------------------------------------------------------------------------+
    """

    form = Plano_TrabalhoForm()

    form.unidade.choices = services.unidades_choices(current_user.coord)

    if form.validate_on_submit():

        services.criar_atividade(
            atividade_sigla=form.atividade_sigla.data,
            atividade_desc=form.atividade_desc.data,
            natureza=form.natureza.data,
            meta=form.horas_semana.data,
            situa=form.situa.data,
            unidade=form.unidade.data,
            usuario_id=current_user.id,
        )

        flash('Atividade inserida no plano de trabalho!')
        return redirect(url_for('demandas.plano_trabalho'))

    return render_template('add_atividade.html', form=form, id=0)
#
#removendo uma atividade do plano de trabalho

@demandas.route('/<int:atividade_id>/delete', methods=['GET','POST'])
@login_required
def delete_atividade(atividade_id):
    """+----------------------------------------------------------------------+
       |Permite que o chefe, se logado, a remova uma atividade do plano de    |
       |trabalho.                                                             |
       |Recebe o ID da atividade como parâmetro.                              |
       +----------------------------------------------------------------------+

    """
    if current_user.ativo == 0 or (current_user.despacha0 == 0 and current_user.despacha == 0 and current_user.despacha2 == 0):
        abort(403)

    services.excluir_atividade(atividade_id, current_user.id)

    flash ('Atividade excluída!','sucesso')

    return redirect(url_for('demandas.plano_trabalho'))


## lista tipos de demanda

@demandas.route('/lista_tipos', methods=['GET','POST'])
@login_required
def lista_tipos():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta uma lista dos tipos de demanda.                                              |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    form = Tipos_DemandaForm()

    tipos_s = services.listar_tipos_demanda(current_user.coord, form.relevancia.choices)

    #
    # gera um pdf com lista de todos os procedimentos (tipos e passos)

    form2 = Pdf_Form()

    if form2.validate_on_submit():

        services.gerar_pdf_procedimentos(tipos_s)

        return redirect(url_for('static', filename='procedimentos.pdf'))

    return render_template('lista_tipos.html', tipos = tipos_s, quantidade=len(tipos_s), form = form2)

#
#removendo um tipo de demanda

@demandas.route('/<int:id>/delete_tipo_demanda', methods=['GET','POST'])
@login_required
def delete_tipo_demanda(id):
    """+----------------------------------------------------------------------+
       |Permite que um tipo de demanda seja removido.                         |
       |                                                                      |
       |Recebe o ID do tipo de demanda como parâmetro.                        |
       +----------------------------------------------------------------------+
    """

    if current_user.ativo == 0:
        abort(403)

    status, tipo, demandas_qtd = services.excluir_tipo_demanda(id, current_user.id)

    if status == 'excluido':
        flash ('Tipo de demanda '+ tipo.tipo + ' excluído!','sucesso')
    else:
        flash ('O tipo: '+ tipo.tipo + ' não pode ser excluído, pois há '+ str(demandas_qtd) +' demanda(s) associada(s) a ele!','erro')

    return redirect(url_for('demandas.lista_tipos'))

### atualiza lista de tipos de demanda

@demandas.route("/<int:id>/update_tipo", methods=['GET', 'POST'])
@login_required
def tipos_update(id):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite atualizar os tipos de demanda.                                                        |
    |                                                                                              |
    |Recebe o id do tipo de demanda como parâmetro.                                                |
    +----------------------------------------------------------------------------------------------+
    """

    tipo = services.buscar_tipo(id)

    form = Tipos_DemandaForm()

    if form.validate_on_submit():

        services.atualizar_tipo_demanda(id, form.tipo.data, form.relevancia.data, current_user.coord, current_user.id)

        flash('Tipo de demanda atualizado!')
        return redirect(url_for('demandas.lista_tipos'))

    elif request.method == 'GET':

        form.tipo.data       = tipo.tipo
        form.relevancia.data = str(tipo.relevancia)

    return render_template('add_tipo.html',
                           form=form, id=id)

### inserir tipo de demanda

@demandas.route("/cria_tipo_demanda", methods=['GET', 'POST'])
@login_required
def cria_tipo_demanda():
    """
    +---------------------------------------------------------------------------------------+
    |Permite inserir tipo na lista de tipos de demanda.                                     |
    +---------------------------------------------------------------------------------------+
    """

    form = Tipos_DemandaForm()

    if form.validate_on_submit():

        services.criar_tipo_demanda(form.tipo.data, form.relevancia.data, current_user.coord, current_user.id)

        flash('Tipo de demanda inserido!')
        return redirect(url_for('demandas.lista_tipos'))

    return render_template('add_tipo.html', form=form, id=0)

#
### inserir passos para tipos de demandas

@demandas.route("/<int:tipo_id>/cria_passo_tipo", methods=['GET', 'POST'])
@login_required
def cria_passo_tipo(tipo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite inserir passos para os tipos de demanda.                                       |
    +---------------------------------------------------------------------------------------+
    """

    tipo = services.nome_do_tipo(tipo_id)

    form = Passos_Tipos_Form()

    if form.validate_on_submit():

        services.criar_passo_tipo(tipo_id, form.ordem.data, form.passo.data, form.desc.data, current_user.id)

        flash('Passo de tipo de demanda inserido!')
        return redirect(url_for('demandas.lista_passos_tipos', tipo_id=tipo_id))

    return render_template('add_passo_tipo.html', tipo_id = tipo_id, tipo = tipo, form=form)

#
### atualiza um passo de um tipo de demanda

@demandas.route("/<int:id>/<int:tipo_id>/update_passo_tipo", methods=['GET', 'POST'])
@login_required
def update_passo_tipo(id,tipo_id):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite atualizar os passos de um tipo de demanda.                                            |
    |                                                                                              |
    |Recebe o id do passo como parâmetro.                                                          |
    +----------------------------------------------------------------------------------------------+
    """

    tipo = services.nome_do_tipo(tipo_id)

    passo = services.buscar_passo(id)

    form = Passos_Tipos_Form()

    if form.validate_on_submit():

        services.atualizar_passo_tipo(id, form.ordem.data, form.passo.data, form.desc.data, current_user.id)

        flash('Passo de Tipo de demanda atualizado!')
        return redirect(url_for('demandas.lista_passos_tipos', tipo_id=tipo_id))

    elif request.method == 'GET':
        form.ordem.data = passo.ordem
        form.passo.data = passo.passo
        form.desc.data  = passo.desc

    return render_template('add_passo_tipo.html', tipo = tipo, form=form)

## lista passos de um tipo de demanda

@demandas.route('/<int:tipo_id>/lista_passos_tipos')
def lista_passos_tipos(tipo_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os passos de um tipo de demanda.                                                 |
    +---------------------------------------------------------------------------------------+
    """
    tipo, passos, quantidade = services.listar_passos_tipo(tipo_id)

    return render_template('lista_passos_tipos.html', tipo_id = tipo_id, tipo = tipo, passos = passos, quantidade=quantidade)


######################
# CRIANDO uma demanda
##############################

# Verificando se já existe demanda semelhante

@demandas.route('/criar',methods=['GET','POST'])
@login_required
def cria_demanda():
    """+--------------------------------------------------------------------------------------+
       |Inicia o procedimento de registro de uma demanda.                                     |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    form = DemandaForm1()

    form.tipo.choices = services.tipos_choices(current_user.coord)

    if form.validate_on_submit():

        mensagem = services.verificar_demanda_duplicada(form.sei.data, form.tipo.data)

        sei = services.formata_sei_para_url(form.sei.data)

        return redirect(url_for('demandas.confirma_cria_demanda',sei=sei,
                                                                 tipo=form.tipo.data,
                                                                 mensagem=mensagem))

    return render_template('add_demanda1.html', form = form)

# CONFIRMANDO CRIAÇÃO DE demanda

@demandas.route('/<sei>/<tipo>/<mensagem>/confirma_criar',methods=['GET','POST'])
@login_required
def confirma_cria_demanda(sei,tipo,mensagem):
    """+--------------------------------------------------------------------------------------+
       |Confirma criação de demanda com os dados inseridos no respectivo formulário.          |
       |O título tem no máximo 140 caracteres.                                                |
       +--------------------------------------------------------------------------------------+
    """
    sistema = services.dados_funcionalidade_sistema()

    form = DemandaForm()

    form.atividade.choices = services.atividades_choices(current_user.coord)

    if form.validate_on_submit():

        demanda = services.criar_demanda_via_sei(
            sei_url=sei,
            tipo=tipo,
            atividade_id=form.atividade.data,
            titulo=form.titulo.data,
            desc=form.desc.data,
            necessita_despacho=form.necessita_despacho.data,
            conclu=form.conclu.data,
            urgencia=form.urgencia.data,
            convenio_data=form.convênio.data,
            usuario=current_user,
        )

        flash ('Demanda criada!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    if mensagem != 'OK':
        flash ('ATENÇÃO: Existe uma demanda não concluída para este processo sob o mesmo tipo. Verifique demanda '+mensagem[2:],'perigo')
    else:
        flash ('OK, favor preencher os demais campos.','sucesso')

    return render_template('add_demanda.html', form = form, sei=sei, tipo=tipo, sistema=sistema)



#CRIANDO uma demanda a partir de um acordo ou convênio

# VERIFICANDO
@demandas.route('/<prog>/<sei>/<conv>/<ano>/criar',methods=['GET','POST'])
@login_required
def acordo_convenio_demanda(prog,sei,conv,ano):
    """+--------------------------------------------------------------------------------------+
       |Inicia o procedimento de registro de uma demanda a partir de um acordo ou convênio.   |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    form = DemandaForm1()

    form.tipo.choices = services.tipos_choices(current_user.coord)

    if form.validate_on_submit():

        mensagem = services.verificar_demanda_duplicada(form.sei.data, form.tipo.data)

        atividade = services.atividade_id_por_programa(prog)

        return redirect(url_for('demandas.confirma_acordo_convenio_demanda',
                                                        prog=atividade.id,
                                                        sei=services.formata_sei_para_url(form.sei.data),
                                                        conv=conv,
                                                        ano=ano,
                                                        tipo=form.tipo.data,
                                                        mensagem=mensagem))

    form.sei.data = services.formata_sei_de_url(sei)

    return render_template('add_demanda1.html', form = form)


# CONFIRMANDO

@demandas.route('/<prog>/<sei>/<conv>/<ano>/<tipo>/<mensagem>/criar',methods=['GET','POST'])
@login_required
def confirma_acordo_convenio_demanda(prog,sei,conv,ano,tipo,mensagem):
    """+--------------------------------------------------------------------------------------+
       |Registra uma demanda a partir de um acordo ou convênio.                               |
       |                                                                                      |
       |Atenção para o Título da Demanda que não pode passar de 140 caracteres.               |
       +--------------------------------------------------------------------------------------+
    """
    sistema = services.dados_funcionalidade_sistema()

    form = DemandaForm()

    form.atividade.choices= services.atividades_choices(current_user.coord)

    if form.validate_on_submit():

        demanda = services.criar_demanda_de_acordo_convenio(
            sei_url=sei,
            tipo=tipo,
            atividade_id=form.atividade.data,
            conv_param=conv,
            titulo=form.titulo.data,
            desc=form.desc.data,
            necessita_despacho=form.necessita_despacho.data,
            conclu=form.conclu.data,
            urgencia=form.urgencia.data,
            convenio_data=form.convênio.data,
            usuario=current_user,
        )

        flash ('Demanda criada!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    form.atividade.data       = prog

    if conv == '0':
        form.convênio.data   = ''
    else:
        form.convênio.data   = conv

    if mensagem != 'OK':
        flash ('ATENÇÃO: Existe uma demanda não concluída para este processo sob o mesmo tipo. Verifique demanda '+mensagem[2:],'perigo')
    else:
        flash ('OK, favor preencher os demais campos.','sucesso')

    return render_template('add_demanda.html', form = form, sei = sei, tipo = tipo, sistema=sistema)


#lendo uma demanda

@demandas.route('/demanda/<int:demanda_id>',methods=['GET','POST'])
def demanda(demanda_id):
    """+---------------------------------------------------------------------------------+
       |Resgata, para leitura, uma demanda, bem como providências e despachos associados.|
       |                                                                                 |
       |Recebe o ID da demanda como parâmetro.                                           |
       +---------------------------------------------------------------------------------+
    """

    demanda = services.buscar_dados_demanda(demanda_id)

    if demanda is None:
        abort(404)

    pro_des = services.providencias_e_despachos(demanda_id)

    if current_user.is_anonymous:
        leitor_despacha = 'False'
    else:
        if current_user.despacha == 1 or current_user.despacha0 == 1 or current_user.despacha2 == 1:
            leitor_despacha = 'True'
        else:
            leitor_despacha = 'False'

    if demanda.data_conclu != None:
        data_conclu = demanda.data_conclu.strftime('%d/%m/%Y')
    else:
        data_conclu = ''

    # verifica se a demanda tem relação com um acordo

    acordo = services.acordo_relacionado(demanda.sei)
    if acordo != None:
        acordo_id = acordo.id
        lista = 'uf'+str(acordo.uf)+str(acordo.cod_programa)
    else:
        acordo_id = ''
        lista = ''

    # resgata tipo_id do tipo da demanda para resgatar os passos
    tipo_demanda = services.tipo_id_da_demanda(demanda.tipo)

    # gera um pdf com todo o histórico da demanda

    form = Pdf_Form()

    if form.validate_on_submit():

        services.gerar_pdf_demanda(demanda, pro_des)

        return redirect(url_for('static', filename='demanda.pdf'))

    return render_template('ver_demanda.html',
                            id                    = demanda.id,
                            programa              = demanda.atividade_sigla,
                            sei                   = demanda.sei,
                            convênio              = demanda.convênio,
                            ano_convênio          = demanda.ano_convênio,
                            data                  = demanda.data,
                            tipo                  = demanda.tipo,
                            tipo_demanda_id       = tipo_demanda.id,
                            titulo                = demanda.titulo,
                            desc                  = demanda.desc,
                            necessita_despacho    = demanda.necessita_despacho,
                            necessita_despacho_cg = demanda.necessita_despacho_cg,
                            conclu                = demanda.conclu,
                            data_conclu           = data_conclu,
                            post                  = demanda,
                            leitor_despacha       = leitor_despacha,
                            pro_des               = pro_des,
                            data_verific          = demanda.data_verific,
                            acordo_id             = acordo_id,
                            lista                 = lista,
                            form                  = form)

#
#registrando a data de verificação da demanda

@demandas.route('/<int:demanda_id>/verifica')
def verifica(demanda_id):
    """
        +----------------------------------------------------------------------+
        |Registra a data de veriicação de uma demanda.                         |
        +----------------------------------------------------------------------+
    """

    services.marcar_verificacao(demanda_id)

    return redirect(url_for('demandas.demanda',demanda_id=demanda_id))


#vendo ultimas demandas

@demandas.route('/demandas')
def list_demandas():
    """
        +----------------------------------------------------------------------+
        |Lista todas as demandas, bem como providências e despachos associados.|
        +----------------------------------------------------------------------+
    """
    pesquisa = False

    page = request.args.get('page', 1, type=int)

    pro_des = services.providencias_e_despachos_todos()

    demandas_count = Demanda.query.count()

    demandas = services.listar_demandas_paginado(page)

    return render_template ('demandas.html',pesquisa=pesquisa,demandas=demandas,
                            pro_des = pro_des, demandas_count = demandas_count)

#
#lista das demandas que aguardam despacho seguindo ordem de prioridades

@demandas.route('/<peso_R>/<peso_D>/<peso_U>/<coord>/<resp>/prioriza', methods=['GET', 'POST'])
def prioriza(peso_R,peso_D,peso_U,coord,resp):
    """
        +---------------------------------------------------------------------------+
        |Lista as demandas não concluídas em uma ordem de prioridades - lista RDU.  |
        +---------------------------------------------------------------------------+
    """

    #
    form = PesosForm()

    if form.validate_on_submit():

        peso_R = form.peso_R.data
        peso_D = form.peso_D.data
        peso_U = form.peso_U.data

        if form.coord.data != '':
            coord  = form.coord.data
        else:
            coord = '*'

        if form.pessoa.data != '':
            resp  = form.pessoa.data
        else:
            resp = '*'

        return redirect(url_for('demandas.prioriza',peso_R=peso_R,peso_D=peso_D,peso_U=peso_U,coord=coord,resp=resp))

    else:

        form.peso_R.data = peso_R
        form.peso_D.data = peso_D
        form.peso_U.data = peso_U
        form.coord.data  = coord
        form.pessoa.data = resp

        demandas_s, quantidade = services.priorizar_demandas(peso_R, peso_D, peso_U, coord, resp)

        return render_template ('prioriza.html',demandas=demandas_s,quantidade=quantidade,form=form)

#
#lista demandas por tipo e última providência/despacho de cada uma

@demandas.route('/<tipo>/demandas_por_tipo')
def demandas_por_tipo(tipo):
    """
        +-----------------------------------------------------------------------------------+
        |Gera uma tabela de demandas por tipo com a última providência/despacho de cada uma.|
        +-----------------------------------------------------------------------------------+
    """

    demandas, qtd, l_act = services.demandas_por_tipo_com_ultima_acao(tipo)

    return render_template ('demandas_por_tipo.html',demandas=demandas, qtd = qtd, l_act = l_act, tipo = tipo)



#atualizando uma demanda
#atualizando uma demanda

@demandas.route("/<int:demanda_id>/update_demanda", methods=['GET','POST'])
@login_required
def update_demanda(demanda_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o autor da demanda, se logado, altere dados desta.                         |
    |                                                                                       |
    |Recebe o ID da demanda como parâmetro.                                                 |
    |                                                                                       |
    |Uma vez que a demanda é marcada como concluída, a necessidade de despacho é desmarcada.|
    +---------------------------------------------------------------------------------------+
    """
    demanda = Demanda.query.get_or_404(demanda_id)
    sistema = services.dados_funcionalidade_sistema()

    if demanda.author != current_user:
        abort(403)

    if current_user.ativo == 0:
        abort(403)

    form = Demanda_ATU_Form()

    form.tipo.choices = services.tipos_choices(current_user.coord)
    form.atividade.choices = services.atividades_choices(current_user.coord)

    if form.validate_on_submit():

        services.atualizar_demanda(
            demanda_id=demanda_id,
            atividade=form.atividade.data,
            sei=form.sei.data,
            convenio_data=form.convênio.data,
            ano_convenio_data=form.ano_convênio.data,
            tipo=form.tipo.data,
            titulo=form.titulo.data,
            desc=form.desc.data,
            tipo_despacho=form.tipo_despacho.data,
            conclu=form.conclu.data,
            urgencia=form.urgencia.data,
            usuario=current_user,
        )

        flash ('Demanda atualizada!','sucesso')
        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    elif request.method == 'GET':
        form.atividade.data             = str(demanda.programa)
        form.sei.data                   = demanda.sei
        form.convênio.data              = demanda.convênio
        form.ano_convênio.data          = demanda.ano_convênio
        form.tipo.data                  = demanda.tipo
        form.titulo.data                = demanda.titulo
        form.desc.data                  = demanda.desc
        if demanda.necessita_despacho == 1:
            form.tipo_despacho.data     = '1'
        elif demanda.necessita_despacho_cg == 1:
            form.tipo_despacho.data     = '2'
        else:
            form.tipo_despacho.data     = '0'
        form.conclu.data                = str(demanda.conclu)
        form.urgencia.data              = str(demanda.urgencia)

    return render_template('atualiza_demanda.html', title='Update',form = form, demanda_id=demanda_id,sistema=sistema)

#
#transferir uma demanda para outro responsável

@demandas.route("/<int:demanda_id>/transfer_demanda", methods=['GET','POST'])
@login_required
def transfer_demanda(demanda_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o autor da demanda, se logado, passe sua demanda para outra pessoa.        |
    |                                                                                       |
    |Recebe o ID da demanda como parâmetro.                                                 |
    |                                                                                       |
    |É criada automaticamente uma providência, registrando a ação.                          |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    demanda = Demanda.query.get_or_404(demanda_id)

    if demanda.author != current_user:
        abort(403)

    pessoas = db.session.query(User.username, User.id)\
                        .filter(User.coord == current_user.coord)\
                        .order_by(User.username).all()
    lista_pessoas = [(str(p[1]),p[0]) for p in pessoas]
    lista_pessoas.insert(0,('',''))    

    form = TransferDemandaForm()

    form.pessoa.choices = lista_pessoas

    if form.validate_on_submit():

        services.transferir_demanda(demanda_id, form.pessoa.data, current_user)

        flash ('Demanda transferida!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    return render_template('transfer_demanda.html', title='Update',form = form)

#
#avocar uma demanda

@demandas.route("/<int:demanda_id>/avocar_demanda", methods=['GET','POST'])
@login_required
def avocar_demanda(demanda_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o usuário corrente avoque uma demanda de outra pessoa                      |
    |                                                                                       |
    |Recebe o ID da demanda como parâmetro.                                                 |
    |                                                                                       |
    |É criada automaticamente uma providência, registrando a ação.                          |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    demanda = services.avocar_demanda_service(demanda_id, current_user)

    flash ('Demanda avocada!','sucesso')

    return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

#
#admin altera data de conclusão de uma demanda

@demandas.route("/<int:demanda_id>/admin_altera_demanda", methods=['GET','POST'])
@login_required
def admin_altera_demanda(demanda_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o admin altere a data de conclusão de uma demanda.                         |
    |                                                                                       |
    |Recebe o ID da demanda como parâmetro.                                                 |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    if current_user.role[0:5] != 'admin':
        abort(403)

    demanda = Demanda.query.get_or_404(demanda_id)

    form = Admin_Altera_Demanda_Form()

    if form.validate_on_submit():

        services.alterar_data_conclusao(demanda_id, form.data_conclu.data, current_user.id)

        flash ('Data de conclusão alterada!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    elif request.method == 'GET':

        form.data_conclu.data = demanda.data_conclu

    return render_template('admin_altera_demanda.html', title='Update',form = form, demanda_id=demanda_id,conclu=demanda.conclu)

#removendo uma demanda

@demandas.route('/<int:demanda_id>/delete_demanda', methods=['GET','POST'])
@login_required
def delete_demanda(demanda_id):
    """+----------------------------------------------------------------------+
       |Permite que o autor da demanda, se logado, a remova do banco de dados.|
       |                                                                      |
       |Recebe o ID da demanda como parâmetro.                                |
       +----------------------------------------------------------------------+
    """

    if current_user.ativo == 0:
        abort(403)

    demanda = Demanda.query.get_or_404(demanda_id)

    if demanda.author != current_user:
        abort(403)

    services.excluir_demanda(demanda_id, current_user.id)

    flash ('Demanda excluída!','sucesso')

    return redirect(url_for('demandas.list_demandas'))


# procurando uma demanda

@demandas.route('/pesquisa', methods=['GET','POST'])
def pesquisa_demanda():
    """+--------------------------------------------------------------------------------------+
       |Permite a procura por demandas conforme os campos informados no respectivo formulário.|
       |                                                                                      |
       |Envia a string pesq para a função list_pesquisa, que executa a busca.                 |
       +--------------------------------------------------------------------------------------+
    """

    pesquisa = True

    lista_coords, lista_tipos, lista_pessoas, lista_atividades = services.pesquisa_choices()

    form = PesquisaForm()

    form.coord.choices = lista_coords
    form.tipo.choices = lista_tipos
    form.autor.choices = lista_pessoas
    form.atividade.choices = lista_atividades

    if form.validate_on_submit():

        pesq = services.montar_string_pesquisa(
            sei=form.sei.data,
            titulo=form.titulo.data,
            tipo=form.tipo.data,
            necessita_despacho=form.necessita_despacho.data,
            conclu=form.conclu.data,
            convenio=form.convênio.data,
            autor=form.autor.data,
            demanda_id=form.demanda_id.data,
            atividade=form.atividade.data,
            coord=form.coord.data,
            necessita_despacho_cg=form.necessita_despacho_cg.data,
        )

        return redirect(url_for('demandas.list_pesquisa',pesq = pesq))

    return render_template('pesquisa_demanda.html', form = form)

# lista as demandas com base em uma procura

@demandas.route('/<pesq>/list_pesquisa')
def list_pesquisa(pesq):
    """+--------------------------------------------------------------------------------------+
       |Com os dados recebidos da formulário de pesquisa, traz as demandas, bem como          |
       |providências e despachos, encontrados no banco de dados.                              |
       |                                                                                      |
       |Recebe a string pesq (dados para pesquisa) como parâmetro.                            |
       +--------------------------------------------------------------------------------------+
    """

    pesquisa = True

    page = request.args.get('page', 1, type=int)

    demandas, demandas_count, pro_des, pesq_l = services.executar_pesquisa(pesq, page)

    return render_template ('pesquisa.html', demandas_count = demandas_count, demandas = demandas,
                             pro_des = pro_des, pesq = pesq, pesq_l = pesq_l)

#################################################################

#CRIANDO um despacho

@demandas.route('/<int:demanda_id>/cria_despacho',methods=['GET','POST'])
@login_required
def cria_despacho(demanda_id):
    """+--------------------------------------------------------------------------------------+
       |Registra, para uma demanda, um despacho do chefe.                                     |
       |A opção de criar despacho só aparece para o usuário logado e que tem o                |
       |status de Chefe.                                                                      |
       |                                                                                      |
       |Inserido um despacho, a situação de necessidade de despacho da demanda é desmarcada.  |
       |                                                                                      |
       |Recebe o ID da demanda como parâmetro.                                                |
       +--------------------------------------------------------------------------------------+
    """

    demanda = Demanda.query.get_or_404(demanda_id)

    tipo = db.session.query(Tipos_Demanda.id).filter(Tipos_Demanda.tipo == demanda.tipo).first()

    form = DespachoForm()
    form.passo.choices = services.passos_choices_do_tipo(tipo.id)

    if form.validate_on_submit():

        services.criar_despacho(
            demanda_id=demanda_id,
            texto=form.texto.data,
            passo_data=form.passo.data,
            necessita_despacho_cg=form.necessita_despacho_cg.data,
            conclu=form.conclu.data,
            usuario=current_user,
        )

        flash ('Despacho criado!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    form.conclu.data = str(demanda.conclu)

    return render_template('add_despacho.html', form                  = form,
                                                sei                   = demanda.sei,
                                                convênio              = demanda.convênio,
                                                ano_convênio          = demanda.ano_convênio,
                                                data                  = demanda.data,
                                                tipo                  = demanda.tipo,
                                                tipo_demanda_id       = tipo.id,
                                                titulo                = demanda.titulo,
                                                desc                  = demanda.desc,
                                                necessita_despacho    = demanda.necessita_despacho,
                                                necessita_despacho_cg = demanda.necessita_despacho_cg,
                                                conclu                = demanda.conclu,
                                                post                  = demanda)

#################################################################

# Aferindo uma demanda

@demandas.route('/<int:demanda_id>/afere_demanda',methods=['GET','POST'])
@login_required
def afere_demanda(demanda_id):

    """+--------------------------------------------------------------------------------------+
       |Registra em uma demanda concluída a nota de aferição.                                 |
       |                                                                                      |
       |Recebe o ID da demanda como parâmetro.                                                |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    if current_user.despacha == 0:
        abort(403)

    demanda = Demanda.query.get_or_404(demanda_id)

    form = Afere_Demanda_Form()

    if form.validate_on_submit():

        services.aferir_demanda(demanda_id, form.nota.data, current_user.id)

        flash ('Demanda aferida!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    elif request.method == 'GET':

        form.nota.data = str(demanda.nota)

    return render_template('aferir_demanda.html', title='Update',form = form, demanda_id=demanda_id,conclu=demanda.conclu)


#################################################################

#CRIANDO uma providência

@demandas.route('/<int:demanda_id>/cria_providencia',methods=['GET','POST'])
@login_required
def cria_providencia(demanda_id):
    """+--------------------------------------------------------------------------------------+
       |Registra, para uma demanda, uma providência tomada por um técnico.                    |
       |A opção de criar proviência aparece qualquer usuário logado, independemtemente de     |
       |ser, ou não, o autor da demanda consultada.                                           |
       |Este tem a opção de marcar a demanda com a necessidade de despacho.                   |
       |Inserido um despacho, a situação de necessidade de despacho da demanda é desmarcada.  |
       |                                                                                      |
       |Recebe o ID da demanda como parâmetro.                                                |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.ativo == 0:
        abort(403)

    demanda = Demanda.query.get_or_404(demanda_id)

    tipo = db.session.query(Tipos_Demanda.id).filter(Tipos_Demanda.tipo == demanda.tipo).first()

    form = ProvidenciaForm()
    form.passo.choices = services.passos_choices_do_tipo(tipo.id)

    if form.validate_on_submit():

        demanda, agendada = services.criar_providencia(
            demanda_id=demanda_id,
            data_hora=form.data_hora.data,
            texto=form.texto.data,
            duracao=form.duracao.data,
            passo_data=form.passo.data,
            necessita_despacho=form.necessita_despacho.data,
            conclu=form.conclu.data,
            agenda=form.agenda.data,
            usuario=current_user,
        )

        if agendada:
            flash ('Providência agendada!','sucesso')
        else:
            flash ('Providência criada!','sucesso')

        return redirect(url_for('demandas.demanda',demanda_id=demanda.id))

    if demanda.necessita_despacho:
        form.necessita_despacho.data = True

    form.data_hora.data = datetime.now()
    form.duracao.data   = 15

    # if demanda.conclu:
    form.conclu.data = str(demanda.conclu)

    if current_user.despacha == 1 and demanda.user_id != current_user.id:
        flash ('Você tem perfil de chefe e esta demanda não é sua. Não seria o caso de registrar um DESPACHO?','perigo')

    return render_template('add_providencia.html',
                            form               = form,
                            demanda_user_id    = demanda.user_id,
                            sei                = demanda.sei,
                            convênio           = demanda.convênio,
                            ano_convênio       = demanda.ano_convênio,
                            data               = demanda.data,
                            tipo               = demanda.tipo,
                            tipo_demanda_id    = tipo.id,
                            titulo             = demanda.titulo,
                            desc               = demanda.desc,
                            necessita_despacho = demanda.necessita_despacho,
                            conclu             = demanda.conclu,
                            post               = demanda)

#
#Um resumo das demandas

@demandas.route('/<coord>/demandas_resumo', methods=['GET', 'POST'])
def demandas_resumo(coord):
    """
        +----------------------------------------------------------------------+
        |Agrega informações básicas de todas as demandas.                      |
        +----------------------------------------------------------------------+
    """

    form = CoordForm()

    if form.validate_on_submit():

        if form.coord.data != '':
            coord  = form.coord.data
        else:
            coord = '*'

        return redirect(url_for('demandas.demandas_resumo',coord=coord))

    else:

        form.coord.data  = coord

        if coord == '*':
            coord = '%'

        dados = services.resumo_demandas(coord)

        return render_template ('demandas_resumo.html', form=form, **dados)


# números por usuário

@demandas.route('<int:usu>/numeros_usu', methods=['GET','POST'])
@login_required
def numeros_usu(usu):
    """+--------------------------------------------------------------------------------------+                                                                          |
       |Mostra estatísticas do usuário.                                                       |
       +--------------------------------------------------------------------------------------+
    """
    dados = services.estatisticas_usuario(usu)

    return render_template('numeros_usu.html', **dados)
