"""
.. topic:: Core (views)

    Este é o módulo inicial do sistema.

    Apresenta as telas de início, informação, o procedimento para carga de dados de pagamento de bolsistas: planilha COSAO
    e carga dos dados do SICONV (convênios). Aqui também estão os procedimentos das Chamadas.

.. topic:: Ações relacionadas aos bolsistas

    * Tela inicial: index
    * Tela de informações: info
    * Carregar dados PDCTR: carregaPDCTR
    * Carregar dados SICONV: carregaSICONV
    * Inserir dados de chamadas homologadas: cria_chamada
    * Atualizar dados de chamada homologada: update_chamada
    * Pega dados de projetos homologados em um arquivo: carrega_homologados
    * Gera lista de homologados de um chamada: lista_homologados
    * Altera dados de um homologado: edita_homologado
    * Remove registro na lista de homologados: deleta_homologado
    * Carregar mensagens do SICONV: carregaMSG


"""

# core/views.py

from flask import render_template,url_for,flash, redirect,request,Blueprint,abort
from flask_login import login_required, current_user
from project.demandas.views import registra_log_auto
from project.convenios.forms import ChamadaForm, SEIForm
from project.acordos.forms import ArquivoForm, HomologadoForm

core = Blueprint("core",__name__)

from project.core import services


@core.route('/')
def index():
    """
    +---------------------------------------------------------------------------------------+
    |Ações quando o aplicativo é colocado no ar.                                            |
    +---------------------------------------------------------------------------------------+
    """
    sistema = services.dados_sistema()

    services.agendar_cargas_iniciais()

    return render_template ('index.html',sistema=sistema) 

@core.route('/inicio')
def inicio():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a tela inicial do aplicativo.                                                |
    +---------------------------------------------------------------------------------------+
    """
    sistema = services.dados_sistema()

    return render_template ('index.html',sistema=sistema)    

@core.route('/info')
def info():
    """
    +---------------------------------------------------------------------------------------+
    |Apresenta a tela de informações do aplicativo.                                         |
    +---------------------------------------------------------------------------------------+
    """

    return render_template('info.html')

@core.route('/carregaPDCTR', methods=['GET', 'POST'])
@login_required
def carregaPDCTR():
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga dos dados de folha de pagamento enviados via planilha  |
    |excel, pela COSAO: planilha COSAO.                                                     |
    |                                                                                       |
    |O módulo pede que seja informado o local onde a planilha COSAO foi salva e armazena os |
    |dados úteis ao aplicativo em tabela própria do banco de dados.                         |
    |                                                                                       |
    |Somente são gravados registros que não existam previamente no banco de dados, ou seja, |
    |caso a planilha COSAO tenha dados previamente carregados, não ocorre a duplicação.     |
    |                                                                                       |
    | *É muito importante que a planilha a ser carregada seja da folha de pagamento*        |
    | *imediatamente superior à da última carga de forma a não causar hiato na sequência*   |
    | *dos dados.*                                                                          |
    +---------------------------------------------------------------------------------------+

    .. warning:: A data de referência da tabela a ser carregada não pode ser distante mais do que um mês da data de referência da última carga!
    """

    form = ArquivoForm()

    if form.validate_on_submit():

        folha_pag = services.salvar_arquivo_upload(form.arquivo.data)

        print ('***  ARQUIVO ***',folha_pag)
        services.cargaPDCTR(folha_pag)

        registra_log_auto(current_user.id,None,'car')

        return redirect(url_for('core.inicio'))

    data_ref = services.data_referencia_ultima_carga_pdctr()

    return render_template('grab_file.html',form=form,data_ref=data_ref.dr)

@core.route('/carregaSICONV', methods=['GET', 'POST'])
@login_required
def carregaSICONV():
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga dos dados do SICONV.                                   |
    |                                                                                       |
    |Faz o dowload dos aquivos compactados diretamente do site do SICONV, descompacta e     |
    |carrega as respectivas tabelas do banco de dados.                                      |
    |                                                                                       |
    |Os dados anteriores são apagados e os novos inseridos nas tabelas.                     |
    |                                                                                       |
    | Para algumas tabelas, somente campos de interesse são carregados.                     |
    +---------------------------------------------------------------------------------------+
    """

    #assíncrono (dispara a carga em thread separada)
    services.thread_cargaSICONV()

    registra_log_auto(current_user.id,None,'car - carga SICONV')

    #return render_template('index.html')
    return redirect(url_for('core.inicio'))


#
### inserir chamadas

@core.route("/<id_acordo_convenio>/criar_chamada", methods=['GET', 'POST'])
@login_required
def cria_chamada(id_acordo_convenio):
    """
    +---------------------------------------------------------------------------------------+
    |Permite registrar os dados de uma chamada e associa-la a um acordo/convenio.           |
    |                                                                                       |
    |Recebe o id do acordo/convênio.                                                        |
    +---------------------------------------------------------------------------------------+
    """

    form = ChamadaForm()

    if form.validate_on_submit():

        services.criar_chamada(
            id_acordo_convenio=id_acordo_convenio,
            sei=form.sei.data,
            chamada_nome=form.chamada.data,
            qtd_projetos=form.qtd_projetos.data,
            vl_total_chamada_str=form.vl_total_chamada.data,
            doc_sei=form.doc_sei.data,
            obs=form.obs.data,
            usuario_id=current_user.id,
        )

        flash('Chamada registrada!','sucesso')

        if str(id_acordo_convenio).isdigit():
            return redirect(url_for('acordos.update', acordo_id=int(id_acordo_convenio), lista='todos'))
        else:
            return redirect(url_for('convenios.convenio_detalhes', conv=str(id_acordo_convenio)[1:], form = SEIForm()))

    return render_template('add_chamada.html', form=form)

#
### altera dados de uma chamada

@core.route("/<int:id>/update_chamada", methods=['GET', 'POST'])
@login_required
def update_chamada(id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite alterar os dados de uma chamada.                                               |
    |                                                                                       |
    |Recebe o id da chamada como parâmetro.                                                 |
    +---------------------------------------------------------------------------------------+
    """

    chamada = services.buscar_chamada(id)

    form = ChamadaForm()

    if form.validate_on_submit():

        services.atualizar_chamada(
            id=id,
            sei=form.sei.data,
            chamada_nome=form.chamada.data,
            qtd_projetos=form.qtd_projetos.data,
            vl_total_chamada_str=form.vl_total_chamada.data,
            doc_sei=form.doc_sei.data,
            obs=form.obs.data,
            usuario_id=current_user.id,
        )

        flash('Chamada homologada atualizada!','sucesso')
        return redirect(url_for('core.inicio'))
    #
    # traz a informação atual do registro SEI
    elif request.method == 'GET':
        dados = services.formata_chamada_para_edicao(chamada)
        form.sei.data              = dados['sei']
        form.chamada.data          = dados['chamada']
        form.qtd_projetos.data     = dados['qtd_projetos']
        form.vl_total_chamada.data = dados['vl_total_chamada']
        form.doc_sei.data          = dados['doc_sei']
        form.obs.data              = dados['obs']

    return render_template('add_chamada.html', form=form)

#
## carregar homologados a partir de arquivo excel
#
@core.route('/<chamada_id>/carrega_homologados', methods=['GET', 'POST'])
@login_required
def carrega_homologados(chamada_id):
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga de homologados via planilha excel gerada pelo usuário. |
    |                                                                                       |
    |O módulo pede que seja informado o local onde a planilha está e armazena os dados em   |
    |tabela própria do banco de dados.                                                      |
    |                                                                                       |
    |Somente são gravados registros que não tenham o mesmo nome e cpf em uma mesma          |
    |chamada, visando evitar duplicação.                                                    |
    |                                                                                       |
    +---------------------------------------------------------------------------------------+
    """

    form = ArquivoForm()

    if form.validate_on_submit():

        homologados = services.salvar_arquivo_upload(form.arquivo.data)

        print ('***  ARQUIVO ***',homologados)

        services.carregar_homologados(chamada_id, homologados)

        registra_log_auto(current_user.id,None,'car')

        return redirect(url_for('core.lista_homologados', chamada_id=chamada_id))


    return render_template('grab_file.html',form=form,data_ref='homologados')


### LISTAR projetos ou bolsistas homologados

@core.route("/<int:chamada_id>/homologados")
def lista_homologados(chamada_id):
    """
    +---------------------------------------------------------------------------------------+
    |Lista os projetos ou bolsistas de uma chamada que foram homologados.                   |
    +---------------------------------------------------------------------------------------+
    """

    chamada, homologados = services.buscar_chamada_e_homologados(chamada_id)

    return render_template('lista_homologados.html', chamada_id=chamada_id,
                                                     chamada=chamada,
                                                     homologados=homologados,
                                                     qtd_homologados=len(homologados))


### inserir ou alterar projeto/bolsista homologado

@core.route("/<int:chamada_id>/<int:homologado_id>/edita_homologado", methods=['GET', 'POST'])
@login_required
def edita_homologado(chamada_id,homologado_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite inserir ou alterar um projeto ou bolsista aprovado na chamada informada e      |
    | homologado pelo CNPq.                                                                 |
    |                                                                                       |
    |Recebe id da chamada e id do homologado como parâmetros.                               |
    +---------------------------------------------------------------------------------------+
    """

    form = HomologadoForm()

    if form.validate_on_submit():

        if homologado_id == 0:
            services.criar_homologado(
                chamada_id=chamada_id, prioridade=form.prioridade.data, nota_str=form.nota.data,
                cpf=form.cpf.data, nome=form.nome.data, mod=form.mod.data, niv=form.niv.data,
                titulo=form.titulo.data, area=form.area.data, valor_str=form.valor.data,
                usuario_id=current_user.id,
            )
        else:
            services.atualizar_homologado(
                homologado_id=homologado_id, chamada_id=chamada_id, prioridade=form.prioridade.data,
                nota_str=form.nota.data, cpf=form.cpf.data, nome=form.nome.data, mod=form.mod.data,
                niv=form.niv.data, titulo=form.titulo.data, area=form.area.data, valor_str=form.valor.data,
                usuario_id=current_user.id,
            )

        flash('Projeto ou bolsista registrado!','sucesso')

        return redirect(url_for('core.lista_homologados', chamada_id=chamada_id))
    #
    # traz formulário em branco
    else:

        if homologado_id != 0:

            homologado = services.buscar_homologado(homologado_id)
            dados = services.formata_homologado_para_edicao(homologado)

            form.prioridade.data = dados['prioridade']
            form.nota.data       = dados['nota']
            form.cpf.data        = dados['cpf']
            form.nome.data       = dados['nome']
            form.mod.data        = dados['mod']
            form.niv.data        = dados['niv']
            form.titulo.data     = dados['titulo']
            form.area.data       = dados['area']
            form.valor.data      = dados['valor']

    return render_template('add_homologado.html', form=form, homologado_id=homologado_id)
#
### DELETAR projeto ou bolsista da lista de homologados de uma chamada

@core.route('/<int:chamada_id>/<int:homologado_id>/deleta_homologado',methods=['GET','POST'])
@login_required
def deleta_homologado(chamada_id,homologado_id):
    """
    +---------------------------------------------------------------------------------------+
    |Deleta um registro da lista de homologados de uma chamada.                             |
    |                                                                                       |
    |Recebe o id da chamada e id do homologado como parâmetros.                             |
    +---------------------------------------------------------------------------------------+
    """
    services.excluir_homologado(homologado_id, current_user.id)

    flash ('Homologado deletado!','sucesso')

    return redirect(url_for('core.lista_homologados', chamada_id=chamada_id))

#
# função que executa carga de mensagens do SICONV
@core.route('/carregaMSG', methods=['GET', 'POST'])
@login_required
def carregaMSG():
    """
    +---------------------------------------------------------------------------------------+
    |Executa o procedimento de carga das mensagens emitidas pelo SICONV que indicam situa-  |
    |ções a verifica.                                                                       |
    |                                                                                       |
    |O módulo pede que seja informado o local onde a planilha de mensagens salva e armazena |
    |os em tabela própria do banco de dados.                                                |
    |                                                                                       |
    |Em cada carga, os dados anteriores são excluidos.                                      |
    +---------------------------------------------------------------------------------------+

    .. warning:: A data de referência é a data do dia da carga e não a data de criação da planilha de entrada!
    """
    #
    form = ArquivoForm()

    if form.validate_on_submit():

        msg_siconv = services.salvar_arquivo_upload(form.arquivo.data)

        print ('***  ARQUIVO ***',msg_siconv)

        services.carregar_mensagens_siconv(msg_siconv)

        registra_log_auto(current_user.id,None,'msg')

        return redirect(url_for('core.inicio'))

    data_ref = ''

    return render_template('grab_file.html',form=form,data_ref=data_ref)



