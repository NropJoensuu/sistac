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

from flask import render_template, url_for, flash, request, redirect, Blueprint, abort, send_from_directory
from flask_login import current_user, login_required
from flask_mail import Message
from threading import Thread
from sqlalchemy import or_, and_, func, cast, String
from sqlalchemy.sql import label
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import coalesce
from project import db, mail, app
from project.models import Demanda, Providencia, Despacho, User, Tipos_Demanda, DadosSEI, Acordo, Log_Auto, Plano_Trabalho,\
                           Sistema, Ativ_Usu, Passos_Tipos, Msgs_Recebidas, Proposta, Convenio, grupo_programa_cnpq, Coords
from project.demandas.forms import DemandaForm1, DemandaForm, Demanda_ATU_Form, DespachoForm, ProvidenciaForm, PesquisaForm,\
                                   Tipos_DemandaForm, TransferDemandaForm, Admin_Altera_Demanda_Form, PesosForm, Afere_Demanda_Form,\
                                   Plano_TrabalhoForm, Pdf_Form, CoordForm, Passos_Tipos_Form
#from project.users.views import send_email, send_async_email
from datetime import datetime, date, timedelta
from fpdf import FPDF
#from apiclient.discovery import build
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle
import os.path
import sys

from calendar import monthrange

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

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]    

    # o choices do campo tipo são definidos aqui e não no form
    tipos = db.session.query(Tipos_Demanda.tipo)\
                      .filter(Tipos_Demanda.unidade.in_(l_unid))\
                      .order_by(Tipos_Demanda.tipo)\
                      .all()
    lista_tipos = [(t.tipo,t.tipo) for t in tipos]
    lista_tipos.insert(0,('',''))

    form = DemandaForm1()

    form.tipo.choices = lista_tipos

    if form.validate_on_submit():

        verif_demanda = db.session.query(Demanda)\
                                  .filter(Demanda.sei == form.sei.data,
                                          Demanda.tipo == form.tipo.data,
                                          Demanda.conclu == '0')\
                                  .first()

        if verif_demanda == None:
            mensagem = 'OK'
        else:
            mensagem = 'KO'+str(verif_demanda.id)

        if '/' in str(form.sei.data):
            sei=str(form.sei.data).split('/')[0]+'_'+str(form.sei.data).split('/')[1]
        else:
            sei = str(form.sei.data)

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
    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    sistema = db.session.query(Sistema.funcionalidade_conv,Sistema.funcionalidade_acordo).first()

    # o choices do campo atividade são definidos aqui e não no form
    atividades = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla)\
                           .filter(Plano_Trabalho.unidade.in_(l_unid))\
                           .order_by(Plano_Trabalho.atividade_sigla).all()
    lista_atividades = [(str(a.id),a.atividade_sigla) for a in atividades]
    lista_atividades.insert(0,('',''))

    form = DemandaForm()

    form.atividade.choices = lista_atividades

    if form.validate_on_submit():

        sei = str(sei).split('_')[0]+'/'+str(sei).split('_')[1]

        if form.convênio.data != '' and form.convênio.data != None:

            verif_sei = db.session.query(DadosSEI).filter(DadosSEI.nr_convenio == str(form.convênio.data)).first()

            if verif_sei == None:
                dadosSEI = DadosSEI(nr_convenio = str(form.convênio.data),
                                    sei         = sei,
                                    epe         = '*',
                                    fiscal      = '')
                db.session.add(dadosSEI)
                db.session.commit()

                registra_log_auto(current_user.id,None,'sei')

                flash('Registro SEI criado a partir desta demanda!','sucesso')

        data_conclu = None
        data_env_despacho = None

        if form.conclu.data != '0':
            form.necessita_despacho.data = False
            data_conclu = datetime.now()

        # verifica se o SEI informado é de um convênio, acordo ou instrumentos
        if form.convênio.data == ''  or form.convênio.data == None:
            tem_conv = db.session.query(DadosSEI.nr_convenio).filter(DadosSEI.sei == sei).first()
            if tem_conv == None:
                conv = ''
            else:
                conv = tem_conv.nr_convenio
        else:
            conv = form.convênio.data

        if form.necessita_despacho.data == True:
            desp = 1
            data_env_despacho = datetime.now()
        else:
            desp = 0

        demanda = Demanda(programa              = form.atividade.data,
                          sei                   = sei,
                          convênio              = conv,
                          ano_convênio          = '',
                          tipo                  = tipo,
                          data                  = datetime.now(),
                          user_id               = current_user.id,
                          titulo                = form.titulo.data,
                          desc                  = form.desc.data,
                          necessita_despacho    = desp,
                          necessita_despacho_cg = 0,
                          conclu                = form.conclu.data,
                          data_conclu           = data_conclu,
                          urgencia              = form.urgencia.data,
                          data_env_despacho     = data_env_despacho,
                          nota                  = None,
                          data_verific          = None)

        db.session.add(demanda)
        db.session.commit()

        registra_log_auto(current_user.id,demanda.id,'inc')

        flash ('Demanda criada!','sucesso')

        # enviar e-mail para chefes sobre demanda concluida
        if form.conclu.data != '0':

            chefes_emails = db.session.query(User.email)\
                                      .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                              User.coord == current_user.coord)

            destino = []
            for email in chefes_emails:
                destino.append(email[0])
            destino.append(current_user.email)

            if len(destino) > 1:

                sistema = db.session.query(Sistema.nome_sistema).first()

                html = render_template('email_demanda_conclu.html',demanda=demanda.id,user=current_user.username,
                                        titulo=form.titulo.data, sistema=sistema.nome_sistema)

                pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id == form.atividade.data).first()

                send_email('Demanda ' + str(demanda.id) + ' foi concluída (' + pt.atividade_sigla + ')', destino,'', html)

                msg = Msgs_Recebidas(user_id    = demanda.user_id,
                                     data_hora  = datetime.now(),
                                     demanda_id = demanda.id,
                                     msg        = 'A demanda foi concluída!')

                db.session.add(msg)
                db.session.commit()

        # enviar e-mail para chefes sobre necessidade de despacho
        if form.necessita_despacho.data == True:

            chefes_emails = db.session.query(User.email, User.id)\
                                      .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                              User.coord == current_user.coord)

            destino = []
            for email in chefes_emails:
                destino.append(email[0])
            destino.append(current_user.email)

            if len(destino) > 1:

                sistema = db.session.query(Sistema.nome_sistema).first()

                html = render_template('email_pede_despacho.html',demanda=demanda.id,user=current_user.username,
                                        titulo=form.titulo.data,sistema=sistema.nome_sistema)

                pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==form.atividade.data).first()

                send_email('Demanda ' + str(demanda.id) + ' requer despacho (' + pt.atividade_sigla + ')', destino,'', html)

                for user in chefes_emails:
                    msg = Msgs_Recebidas(user_id    = user.id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda.id,
                                         msg        = 'Chefia, a demanda está pedindo um despacho!')
                    db.session.add(msg)

                    msg = Msgs_Recebidas(user_id    = current_user.id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda.id,
                                         msg        = 'Você marcou a opção -Necessita despacho?- na demanda!')
                    db.session.add(msg)

                db.session.commit()

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

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]    

    # o choices do campo tipo são definidos aqui e não no form
    tipos = db.session.query(Tipos_Demanda.tipo)\
                      .filter(Tipos_Demanda.unidade.in_(l_unid))\
                      .order_by(Tipos_Demanda.tipo)\
                      .all()
    lista_tipos = [(t.tipo,t.tipo) for t in tipos]
    lista_tipos.insert(0,('',''))

    form = DemandaForm1()

    form.tipo.choices = lista_tipos

    if form.validate_on_submit():

        verif_demanda = db.session.query(Demanda)\
                                  .filter(Demanda.sei == form.sei.data,
                                          Demanda.tipo == form.tipo.data,
                                          Demanda.conclu == '0')\
                                  .first()

        if verif_demanda == None:
            mensagem = 'OK'
        else:
            mensagem = 'KO'+str(verif_demanda.id)

        atividade = db.session.query(Plano_Trabalho.id)\
                              .filter(Plano_Trabalho.atividade_sigla == prog).first()

        if atividade == None:
            atividade = db.session.query(Plano_Trabalho.id)\
                                  .filter(Plano_Trabalho.atividade_sigla == "Diversos").first()

        return redirect(url_for('demandas.confirma_acordo_convenio_demanda',
                                                        prog=atividade.id,
                                                        sei=str(form.sei.data).split('/')[0]+'_'+str(form.sei.data).split('/')[1],
                                                        conv=conv,
                                                        ano=ano,
                                                        tipo=form.tipo.data,
                                                        mensagem=mensagem))

    form.sei.data = str(sei).split('_')[0]+'/'+str(sei).split('_')[1]

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

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    sistema = db.session.query(Sistema.funcionalidade_conv,Sistema.funcionalidade_acordo).first()

    # o choices do campo atividade são definidos aqui e não no form
    atividades = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla)\
                           .filter(Plano_Trabalho.unidade.in_(l_unid))\
                           .order_by(Plano_Trabalho.atividade_sigla).all()
    lista_atividades = [(str(a.id),a.atividade_sigla) for a in atividades]
    lista_atividades.insert(0,('',''))

    form = DemandaForm()

    form.atividade.choices= lista_atividades

    if form.validate_on_submit():

        data_conclu = None
        data_env_despacho = None

        if form.conclu.data != '0':
            form.necessita_despacho.data = False
            data_conclu = datetime.now()

            if form.convênio.data == ''  or form.convênio.data == None:
                conv = ''
            else:
                conv = form.convênio.data

        if form.necessita_despacho.data == True:
            data_env_despacho = datetime.now()
            desp = 1
        else:
            desp = 0

        demanda = Demanda(programa              = form.atividade.data,
                          sei                   = str(sei).split('_')[0]+'/'+str(sei).split('_')[1],
                          convênio              = conv,
                          ano_convênio          = '',
                          tipo                  = tipo,
                          data                  = datetime.now(),
                          user_id               = current_user.id,
                          titulo                = form.titulo.data,
                          desc                  = form.desc.data,
                          necessita_despacho    = desp,
                          necessita_despacho_cg = 0,
                          conclu                = form.conclu.data,
                          data_conclu           = data_conclu,
                          urgencia              = form.urgencia.data,
                          data_env_despacho     = data_env_despacho,
                          nota                  = None,
                          data_verific          = None)

        db.session.add(demanda)
        db.session.commit()

        registra_log_auto(current_user.id,demanda.id,'inc')

        flash ('Demanda criada!','sucesso')

        # enviar e-mail para chefes sobre demanda concluida
        if form.conclu.data != '0':

            chefes_emails = db.session.query(User.email)\
                                      .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                              User.coord == current_user.coord)

            destino = []
            for email in chefes_emails:
                destino.append(email[0])
            destino.append(current_user.email)

            if len(destino) > 1:

                sistema = db.session.query(Sistema.nome_sistema).first()

                html = render_template('email_demanda_conclu.html',demanda=demanda.id,user=current_user.username,
                                        titulo=form.titulo.data,sistema=sistema.nome_sistema)

                pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==form.atividade.data).first()

                send_email('Demanda ' + str(demanda.id) + ' foi concluída (' + pt.atividade_sigla + ')', destino,'', html)

                msg = Msgs_Recebidas(user_id    = demanda.user_id,
                                     data_hora  = datetime.now(),
                                     demanda_id = demanda.id,
                                     msg        = 'A demanda foi concluída!')

                db.session.add(msg)
                db.session.commit()

        # enviar e-mail para chefes sobre necessidade de despacho
        if form.necessita_despacho.data == True:

            chefes_emails = db.session.query(User.email,User.id)\
                                      .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                              User.coord == current_user.coord)

            destino = []
            for email in chefes_emails:
                destino.append(email[0])
            destino.append(current_user.email)

            if len(destino) > 1:

                sistema = db.session.query(Sistema.nome_sistema).first()

                html = render_template('email_pede_despacho.html',demanda=demanda.id,user=current_user.username,
                                        titulo=form.titulo.data,sistema=sistema.nome_sistema)

                pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==form.atividade.data).first()

                send_email('Demanda ' + str(demanda.id) + ' requer despacho (' + pt.atividade_sigla + ')', destino,'', html)

                for user in chefes_emails:
                    msg = Msgs_Recebidas(user_id    = user.id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda.id,
                                         msg        = 'Chefia, a demanda está pedindo um despacho!')
                    db.session.add(msg)

                    msg = Msgs_Recebidas(user_id    = current_user.id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda.id,
                                         msg        = 'Você marcou a opção -Necessita despacho?- na demanda!')
                    db.session.add(msg)

                db.session.commit()

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

    demanda = db.session.query(Demanda.id,
                                Demanda.programa,
                                Demanda.sei,
                                Demanda.convênio,
                                Demanda.ano_convênio,
                                Demanda.tipo,
                                Demanda.data,
                                Demanda.user_id,
                                Demanda.titulo,
                                Demanda.desc,
                                Demanda.necessita_despacho,
                                Demanda.conclu,
                                Demanda.data_conclu,
                                Demanda.necessita_despacho_cg,
                                Demanda.urgencia,
                                Demanda.data_env_despacho,
                                Demanda.nota,
                                Plano_Trabalho.atividade_sigla,
                                User.coord,
                                User.username,
                                Demanda.data_verific)\
                         .filter(Demanda.id == demanda_id)\
                         .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                         .outerjoin(User, User.id == Demanda.user_id)\
                         .first()

    providencias = db.session.query(Providencia.demanda_id,
                                    Providencia.texto,
                                    Providencia.data,
                                    Providencia.user_id,
                                    label('username',User.username),
                                    User.despacha,
                                    User.despacha2,
                                    Providencia.programada,
                                    Providencia.passo,
                                    Providencia.duracao)\
                                    .outerjoin(User, Providencia.user_id == User.id)\
                                    .filter(Providencia.demanda_id == demanda_id)\
                                    .order_by(Providencia.data.desc()).all()

    despachos = db.session.query(Despacho.demanda_id,
                                 Despacho.texto,
                                 Despacho.data,
                                 Despacho.user_id,
                                 label('username',User.username +' - DESPACHO'),
                                 User.despacha,
                                 User.despacha2,
                                 User.despacha0,
                                 Despacho.passo)\
                                .filter_by(demanda_id=demanda_id)\
                                .outerjoin(User, Despacho.user_id == User.id)\
                                .order_by(Despacho.data.desc()).all()

    pro_des = providencias + despachos
    pro_des.sort(key=lambda ordem: ordem.data,reverse=True)

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

    acordo = db.session.query(Acordo.id, Acordo.uf, grupo_programa_cnpq.cod_programa)\
                       .join(grupo_programa_cnpq,grupo_programa_cnpq.id_acordo==Acordo.id)\
                       .filter(Acordo.sei == demanda.sei)\
                       .first()
    if acordo != None:
        acordo_id = acordo.id
        lista = 'uf'+str(acordo.uf)+str(acordo.cod_programa)
    else:
        acordo_id = ''
        lista = ''

    # resgata tipo_id do tipo da demanda para resgatar os passos
    tipo_demanda = db.session.query(Tipos_Demanda.id).filter(Tipos_Demanda.tipo == demanda.tipo).first()

    # gera um pdf com todo o histórico da demanda

    form = Pdf_Form()

    if form.validate_on_submit():

        class PDF(FPDF):
            # cabeçalho com dados da demanda
            def header(self):
                # Logo
                # self.image('logo_pb.png', 10, 8, 33)
                self.set_font('Arial', 'B', 13)
                self.set_text_color(127,127,127)
                self.cell(0, 10, 'Relatório de Demanda - gerado em '+date.today().strftime('%d/%m/%Y'), 1, 1,'C')
                # Nº da demanda, coordenação e atividade
                if demanda.atividade_sigla == None:
                    self.set_text_color(127,127,127)
                    self.cell(25, 8, 'Demanda: ', 0, 0)
                    self.set_text_color(0,0,0)
                    self.cell(35, 8, str(demanda.id)+' ('+demanda.coord+')', 0, 0,'C')
                    self.set_text_color(0,0,0)
                    self.cell(0, 8, ' Atividade não definida', 0, 1)
                else:
                    self.set_text_color(127,127,127)
                    self.cell(25, 8, 'Demanda: ', 0, 0)
                    self.set_text_color(0,0,0)
                    self.cell(35, 8, str(demanda.id)+' ('+demanda.coord+')', 0, 0,'C')
                    self.set_text_color(127,127,127)
                    self.cell(25, 8, ' Atividade: ', 0, 0)
                    self.set_text_color(0,0,0)
                    self.cell(0, 8, demanda.atividade_sigla, 0, 1)
                # título da demanda
                self.set_text_color(127,127,127)
                self.cell(18, 6, 'Título: ', 0, 0)
                self.set_text_color(0,0,0)
                titulo = demanda.titulo.encode('latin-1', 'replace').decode('latin-1')
                tamanho_titulo = self.get_string_width(titulo)
                self.multi_cell(0, 6, titulo)
                if tamanho_titulo <= 100:
                    pdf.ln(12)
                else:
                    pdf.ln(tamanho_titulo/10)
                # tipo e SEI
                self.set_text_color(127,127,127)
                self.cell(12, 8, 'Tipo: ', 0, 0)
                self.set_text_color(0,0,0)
                self.cell(90, 8, demanda.tipo, 0, 0)
                self.set_text_color(127,127,127)
                self.cell(12, 8, 'SEI: ', 0, 0)
                self.set_text_color(0,0,0)
                self.cell(0, 8, demanda.sei, 0, 1)
                # responsável
                self.set_text_color(127,127,127)
                self.cell(16, 8, 'Resp.: ', 0, 0)
                self.set_text_color(0,0,0)
                self.cell(0, 8, demanda.username, 0, 1)
                # datas
                if demanda.conclu:
                    self.set_text_color(127,127,127)
                    self.cell(25, 8, 'Criada em: ', 0, 0)
                    self.set_text_color(0,0,0)
                    self.cell(30, 8, demanda.data.strftime('%d/%m/%Y'), 0, 0)
                    self.set_text_color(127,127,127)
                    self.cell(33, 8, 'Finalizada em: ', 0, 0)
                    self.set_text_color(0,0,0)
                    x = lambda x: 'N.I.' if x == None else x.strftime('%d/%m/%Y')
                    self.cell(0, 8, x(demanda.data_conclu), 0, 1)
                else:
                    self.set_text_color(127,127,127)
                    self.cell(25, 8, 'Criada em: ', 0, 0)
                    self.set_text_color(0,0,0)
                    self.cell(30, 8, demanda.data.strftime('%d/%m/%Y'), 0, 0)
                    self.cell(0, 8,'Não concluída', 0, 1)
                # descrição
                self.set_text_color(127,127,127)
                self.cell(27, 6, 'Descrição: ', 0, 0)
                self.set_text_color(0,0,0)
                desc = demanda.desc.encode('latin-1', 'replace').decode('latin-1')
                tamanho_desc = self.get_string_width(desc)
                self.multi_cell(0, 6, desc)
                if tamanho_desc <= 100:
                    pdf.ln(6)
                else:
                    pdf.ln(tamanho_desc/12)
                # se necessita despachos
                if demanda.necessita_despacho == 1:
                    self.cell(0, 10, 'Aguarda despacho', 0, 1)
                if demanda.necessita_despacho_cg == 1:
                    self.cell(0, 10, 'Aguarda despacho Coord. Geral ou sup.', 0, 1)
                # Line break
                self.ln(10)
                self.set_text_color(127,127,127)
                self.cell(0, 10, 'Providências e Despachos', 1, 1,'C')

            # Rodape da página
            def footer(self):
                # Posicionado a 1,5 cm do final da página
                self.set_y(-15)
                # Arial italic 8 cinza
                self.set_font('Arial', 'I', 8)
                self.set_text_color(127,127,127)
                # Numeração de página
                self.cell(0, 10, 'Página ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

        # Instanciando a classe herdada
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_font('Times', '', 12)
        # Providêcias e Despachos: responsável, data e descrição
        for item in pro_des:
            pdf.set_text_color(0,0,0)
            pdf.cell(50, 10, item.username, 0, 0)
            pdf.set_text_color(127,127,127)
            pdf.cell(8, 10, 'Em: ', 0, 0)
            pdf.set_text_color(0,0,0)
            pdf.cell(0, 10, item.data.strftime('%d/%m/%Y'), 0, 1)
            texto = item.texto.encode('latin-1', 'replace').decode('latin-1')
            tamanho_texto = pdf.get_string_width(texto)
            pdf.multi_cell(0, 5, texto)
            if tamanho_texto <= 100:
                pdf.ln(15)
            else:
                pdf.ln(tamanho_texto/10)
            pdf.dashed_line(pdf.get_x(), pdf.get_y(), pdf.get_x()+190, pdf.get_y(), 2, 3)


        pasta_pdf = os.path.normpath('/app/project/static/demanda.pdf')

        pdf.output(pasta_pdf, 'F')

        # o comandinho mágico que permite fazer o download de um arquivo
        send_from_directory('/app/project/static', 'demanda.pdf')

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

    demanda = Demanda.query.get_or_404(demanda_id)

    demanda.data_verific = datetime.today()

    db.session.commit()

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

    providencias = db.session.query(Providencia.demanda_id,
                                    Providencia.texto,
                                    Providencia.data,
                                    Providencia.user_id,
                                    label('username',User.username),
                                    Providencia.programada,
                                    Providencia.passo)\
                                    .outerjoin(User, Providencia.user_id == User.id)\
                                    .order_by(Providencia.data.desc()).all()

    despachos = db.session.query(Despacho.demanda_id,
                                 Despacho.texto,
                                 Despacho.data,
                                 Despacho.user_id,
                                 label('username',User.username +' - DESPACHO'),
                                 User.despacha,
                                 User.despacha2,
                                 User.despacha0,
                                 Despacho.passo)\
                                .outerjoin(User, Despacho.user_id == User.id)\
                                .order_by(Despacho.data.desc()).all()

    pro_des = providencias + despachos
    pro_des.sort(key=lambda ordem: ordem.data,reverse=True)

    demandas_count = Demanda.query.count()

    demandas = db.session.query(Demanda.id,
                                Demanda.programa,
                                Demanda.sei,
                                Demanda.convênio,
                                Demanda.ano_convênio,
                                Demanda.tipo,
                                Demanda.data,
                                Demanda.user_id,
                                Demanda.titulo,
                                Demanda.desc,
                                Demanda.necessita_despacho,
                                Demanda.conclu,
                                Demanda.data_conclu,
                                Demanda.necessita_despacho_cg,
                                Demanda.urgencia,
                                Demanda.data_env_despacho,
                                Demanda.nota,
                                Plano_Trabalho.atividade_sigla,
                                User.coord,
                                User.username)\
                         .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                         .outerjoin(User, User.id == Demanda.user_id)\
                         .order_by(Demanda.data.desc())\
                         .paginate(page=page,per_page=8)


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

        hoje = datetime.today()

        ## calcula vida média por tipo de demanda

        demandas_conclu_por_tipo = db.session.query(Demanda.tipo,label('qtd',func.count(Demanda.id)))\
                                      .filter(Demanda.conclu == '1')\
                                      .order_by(Demanda.tipo)\
                                      .group_by(Demanda.tipo)

        vida_m_por_tipo_dict = {}

        for tipo in demandas_conclu_por_tipo:
            demandas_datas = db.session.query(Demanda.data,Demanda.data_conclu)\
                                        .filter(Demanda.tipo == tipo.tipo, Demanda.data_conclu != None)

            vida = 0
            vida_m = 0

            for dia in demandas_datas:

                vida += (dia.data_conclu - dia.data).days

            if len(list(demandas_datas)) > 0:
                vida_m = round(vida/len(list(demandas_datas)))
            else:
                vida_m = 0

            vida_m_por_tipo_dict[tipo.tipo] = vida_m

        ##

        demandas_s = []

        if coord == '*' and resp == '*':
            demandas       = db.session.query(Demanda.id,
                                              Plano_Trabalho.atividade_sigla,
                                              Demanda.sei,
                                              Demanda.tipo,
                                              Demanda.data,
                                              Demanda.necessita_despacho,
                                              Demanda.necessita_despacho_cg,
                                              Demanda.urgencia,
                                              Demanda.convênio,
                                              User.username)\
                            .join(User, Demanda.user_id == User.id)\
                            .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                            .order_by(Demanda.data)\
                            .filter(Demanda.conclu == '0')\
                            .all()
        else:

            if coord == '*':
                coord = '%'
            if resp == '*':
                resp = '%'

            demandas       = db.session.query(Demanda.id,
                                              Plano_Trabalho.atividade_sigla,
                                              Demanda.sei,
                                              Demanda.tipo,
                                              Demanda.data,
                                              Demanda.necessita_despacho,
                                              Demanda.necessita_despacho_cg,
                                              Demanda.urgencia,
                                              Demanda.convênio,
                                              User.username)\
                            .join(User, Demanda.user_id == User.id)\
                            .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                            .order_by(Demanda.data)\
                            .filter(Demanda.conclu == '0',
                                    User.coord.like(coord),
                                    User.id.like(resp))\
                            .all()

        quantidade = len(demandas)

        for demanda in demandas:
            # identifica UF
            if demanda.convênio != 0 and demanda.convênio != '':
                uf = db.session.query(Proposta.UF_PROPONENTE)\
                               .filter(Convenio.NR_CONVENIO == demanda.convênio)\
                               .join(Convenio, Proposta.ID_PROPOSTA == Convenio.ID_PROPOSTA)\
                               .first()
            else:
                uf = db.session.query(Acordo.uf).filter_by(sei=demanda.sei).first()
            if uf == None:
                uf = ('*',)

            # identifica relevância
            relev = db.session.query(Tipos_Demanda.relevancia).filter_by(tipo=demanda.tipo).first()

            # calcula distância (momento)
            try:
                alvo = vida_m_por_tipo_dict[demanda.tipo]
            except KeyError:
                alvo = 999

            vigencia = (hoje - demanda.data).days

            if alvo == 0:
                distancia = 1
            else:
                if vigencia/alvo > 1.50:
                    distancia = 1
                elif vigencia/alvo < 0.5:
                    distancia = 3
                else:
                    distancia = 2

            # identifica urgência
            # --> constante no campo demanda.urgencia

            if relev:
                r_relevancia = relev.relevancia
            else:
                r_relevancia = 0

            demanda_s = list(demanda)
            demanda_s.append(float(peso_R)*r_relevancia + float(peso_D)*distancia + float(peso_U)*demanda.urgencia)
            demanda_s.append(str(r_relevancia)+','+str(distancia)+','+str(demanda.urgencia))
            demanda_s.append(uf)

            demandas_s.append(demanda_s)

        # ordenar lista de demanda
        demandas_s.sort(key=lambda x: x[10])

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
#
    l_act = {}

    demandas = db.session.query(Demanda.id,
                                Demanda.programa,
                                Demanda.sei,
                                Demanda.convênio,
                                Demanda.ano_convênio,
                                Demanda.tipo,
                                Demanda.data,
                                Demanda.user_id,
                                Demanda.titulo,
                                Demanda.desc,
                                Demanda.necessita_despacho,
                                Demanda.conclu,
                                Demanda.data_conclu,
                                Demanda.necessita_despacho_cg,
                                Demanda.urgencia,
                                Demanda.data_env_despacho,
                                Demanda.nota,
                                Plano_Trabalho.atividade_sigla,
                                Demanda.data_verific,
                                User.username,
                                User.coord)\
                         .join(User, Demanda.user_id == User.id)\
                         .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                         .filter(Demanda.tipo == tipo)\
                         .order_by(Demanda.id.desc())\
                         .all()

    # verificar se tem despacho novo

    for demanda in demandas:

        prov = db.session.query(Providencia.data,
                                Providencia.texto,
                                Providencia.passo)\
                                .filter(Providencia.demanda_id == demanda.id)\
                                .order_by(Providencia.data.desc()).first()

        desp = db.session.query(Despacho.data,
                                Despacho.texto,
                                Despacho.passo)\
                                .filter(Despacho.demanda_id == demanda.id)\
                                .order_by(Despacho.data.desc()).first()

        if prov != None and desp != None:
            if prov.data > desp.data:
                ultima = prov
                if ultima.passo != None:
                    l_act[demanda.id] = ('P - ' + ultima.passo + ultima.texto)
                else:
                    l_act[demanda.id] = ('P - ' + ultima.texto)
            else:
                ultima = desp
                if ultima.passo != None:
                    l_act[demanda.id] = ('D - ' + ultima.passo + ultima.texto)
                else:
                    l_act[demanda.id] = ('D - ' + ultima.texto)
        elif prov != None:
            ultima = prov
            if ultima.passo != None:
                l_act[demanda.id] = ('P - ' + ultima.passo + ultima.texto)
            else:
                l_act[demanda.id] = ('P - ' + ultima.texto)
        elif desp != None:
            ultima = desp
            if ultima.passo != None:
                l_act[demanda.id] = ('D - ' + ultima.passo + ultima.texto)
            else:
                l_act[demanda.id] = ('D - ' + ultima.texto)
        else:
            l_act[demanda.id] = 'sem registro'

    qtd = len(demandas)

    return render_template ('demandas_por_tipo.html',demandas=demandas, qtd = qtd, l_act = l_act, tipo = tipo)



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
    sistema = db.session.query(Sistema.funcionalidade_conv, Sistema.funcionalidade_acordo).first()

    if demanda.author != current_user:
        abort(403)

    if current_user.ativo == 0:
        abort(403)

    unidade = current_user.coord

    # se unidade for pai, junta ela com seus filhos
    hierarquia = db.session.query(Coords.sigla).filter(Coords.pai == unidade).all()

    if hierarquia:
        l_unid = [f.sigla for f in hierarquia]
        l_unid.append(unidade)
    else:
        l_unid = [unidade]

    # o choices do campo tipo e do campo atividade são definidos aqui e não no form
    tipos = db.session.query(Tipos_Demanda.tipo)\
                      .filter(Tipos_Demanda.unidade.in_(l_unid))\
                      .order_by(Tipos_Demanda.tipo)\
                      .all()
    lista_tipos = [(t.tipo,t.tipo) for t in tipos]
    lista_tipos.insert(0,('',''))

    atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                           .filter(Plano_Trabalho.unidade.in_(l_unid))\
                           .order_by(Plano_Trabalho.atividade_sigla)\
                           .all()
    lista_atividades = [(str(a.id),a.atividade_sigla) for a in atividades]
    lista_atividades.insert(0,('',''))

    form = Demanda_ATU_Form()

    form.tipo.choices = lista_tipos
    form.atividade.choices = lista_atividades

    if form.validate_on_submit():

        demanda.programa              = form.atividade.data
        demanda.sei                   = form.sei.data

        if form.convênio.data == ''  or form.convênio.data == None:
            demanda.convênio = ''
            demanda.ano_convênio  = ''
        else:
            demanda.convênio = form.convênio.data
            demanda.ano_convênio = form.ano_convênio.data

        demanda.tipo                  = form.tipo.data
        demanda.titulo                = form.titulo.data
        demanda.desc                  = form.desc.data

        if form.tipo_despacho.data == '0':
            demanda.necessita_despacho_cg = 0

        if form.tipo_despacho.data == '2':
            demanda.necessita_despacho_cg = 1

        if form.tipo_despacho.data == '1':

            # enviar e-mail para chefes sobre necessidade de despacho
            if demanda.necessita_despacho == 0:

                chefes_emails = db.session.query(User.email,User.id)\
                                          .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                                  User.coord == current_user.coord)

                destino = []
                for email in chefes_emails:
                    destino.append(email[0])
                destino.append(current_user.email)

                if len(destino) > 1:

                    sistema = db.session.query(Sistema.nome_sistema).first()

                    html = render_template('email_pede_despacho.html',demanda=demanda_id,user=current_user.username,
                                            titulo=form.titulo.data,sistema=sistema.nome_sistema)

                    pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==form.atividade.data).first()

                    send_email('Demanda ' + str(demanda_id) + ' requer despacho (' + pt.atividade_sigla + ')', destino,'', html)

                    for user in chefes_emails:
                        msg = Msgs_Recebidas(user_id    = user.id,
                                             data_hora  = datetime.now(),
                                             demanda_id = demanda_id,
                                             msg        = 'Chefia, a demanda está pedindo um despacho!')
                        db.session.add(msg)

                        msg = Msgs_Recebidas(user_id    = current_user.id,
                                             data_hora  = datetime.now(),
                                             demanda_id = demanda_id,
                                             msg        = 'Você marcou a opção -Necessita despacho?- na demanda!')
                        db.session.add(msg)

                    db.session.commit()

                demanda.necessita_despacho    = 1
                demanda.data_env_despacho     = datetime.now()

            demanda.necessita_despacho_cg = 0

        else:

            demanda.necessita_despacho    = 0

        if form.conclu.data != '0':

            demanda.necessita_despacho    = 0
            demanda.necessita_despacho_cg = 0

            if demanda.conclu == '0':

                demanda.data_conclu = datetime.now()

                # enviar e-mail para chefes sobre demanda concluida
                chefes_emails = db.session.query(User.email)\
                                          .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                                  User.coord == current_user.coord)

                destino = []
                for email in chefes_emails:
                    destino.append(email[0])
                destino.append(current_user.email)

                if len(destino) > 1:

                    sistema = db.session.query(Sistema.nome_sistema).first()

                    html = render_template('email_demanda_conclu.html',demanda=demanda_id,user=current_user.username,
                                            titulo=form.titulo.data,sistema=sistema.nome_sistema)

                    pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==form.atividade.data).first()

                    send_email('Demanda ' + str(demanda_id) + ' foi concluída (' + pt.atividade_sigla + ')', destino,'', html)

                    msg = Msgs_Recebidas(user_id    = demanda.user_id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda_id,
                                         msg        = 'A demanda foi concluída!')

                    db.session.add(msg)
                    db.session.commit()

        else:
            demanda.data_conclu = None

        demanda.conclu                = form.conclu.data

        demanda.urgencia              = form.urgencia.data

        db.session.commit()

        registra_log_auto(current_user.id,demanda_id,'alt')

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

        demanda.user_id   = int(form.pessoa.data)

        db.session.commit()

        registra_log_auto(current_user.id,demanda_id,'tra')

        recebedor = db.session.query(User.username,User.email).filter(User.id==int(form.pessoa.data)).first()

        providencia = Providencia(demanda_id = demanda_id,
                                  data       = datetime.now(),
                                  texto      = 'DEMANDA TRANSFERIDA para '+recebedor.username+'!    ',
                                  user_id    = current_user.id,
                                  duracao    = 5,
                                  programada = 0,
                                  passo      = '')

        db.session.add(providencia)
        db.session.commit()

        sistema = db.session.query(Sistema.nome_sistema).first()

        destino = []
        destino.append(recebedor.email)
        destino.append(current_user.email)

        html = render_template('email_demanda_transf.html',demanda=demanda_id,user=current_user.username,
                                titulo=demanda.titulo,receb=recebedor.username,sistema=sistema.nome_sistema)

        send_email('A demanda ' + str(demanda_id) + ' foi transferida para você!', destino,'', html)

        msg = Msgs_Recebidas(user_id    = demanda.user_id,
                             data_hora  = datetime.now(),
                             demanda_id = demanda_id,
                             msg        = 'A demanda foi transferida para você!')

        db.session.add(msg)
        db.session.commit()

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

    demanda = Demanda.query.get_or_404(demanda_id)

    providencia = Providencia(demanda_id = demanda_id,
                              data       = datetime.now(),
                              texto      = 'DEMANDA AVOCADA! Resp. anterior: ' + demanda.author.username + '.',
                              user_id    = current_user.id,
                              duracao    = 5,
                              programada = 0,
                              passo      = '')

    db.session.add(providencia)
    db.session.commit()

    demanda.user_id   = current_user.id
    db.session.commit()

    registra_log_auto(current_user.id,demanda_id,'avo')

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

        demanda.data_conclu = form.data_conclu.data

        db.session.commit()

        registra_log_auto(current_user.id,demanda_id,'dat')

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

    db.session.delete(demanda)
    db.session.commit()

    registra_log_auto(current_user.id,demanda_id,'del')

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

    # os choices dos campos de escolha são definidos aqui e não no form

    coords = db.session.query(Coords.sigla)\
                      .order_by(Coords.sigla).all()
    lista_coords = [(c[0],c[0]) for c in coords]
    lista_coords.insert(0,('',''))

    tipos = db.session.query(Tipos_Demanda.tipo)\
                      .order_by(Tipos_Demanda.tipo).all()
    lista_tipos = [(t[0],t[0]) for t in tipos]
    lista_tipos.insert(0,('',''))

    pessoas = db.session.query(User.username, User.id)\
                      .order_by(User.username).all()
    lista_pessoas = [(str(p[1]),p[0]) for p in pessoas]
    lista_pessoas.insert(0,('',''))

    atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                      .order_by(Plano_Trabalho.atividade_sigla).all()
    lista_atividades = [(str(a[1]),a[0]) for a in atividades]
    lista_atividades.insert(0,('',''))

    form = PesquisaForm()

    form.coord.choices = lista_coords
    form.tipo.choices = lista_tipos
    form.autor.choices = lista_pessoas
    form.atividade.choices = lista_atividades

    if form.validate_on_submit():
        # a / do campo sei precisou ser trocada por _ para poder ser passado no URL da pesquisa
        if str(form.sei.data).find('/') != -1:

            pesq = str(form.sei.data).split('/')[0]+'_'+str(form.sei.data).split('/')[1]+';'+\
                   str(form.titulo.data)+';'+\
                   str(form.tipo.data)+';'+\
                   str(form.necessita_despacho.data)+';'+\
                   str(form.conclu.data)+';'+\
                   str(form.convênio.data)+';'+\
                   str(form.autor.data)+';'+\
                   str(form.demanda_id.data)+';'+\
                   str(form.atividade.data)+';'+\
                   str(form.coord.data)+';'+\
                   str(form.necessita_despacho_cg.data)

        else:

            pesq = str(form.sei.data)+';'+\
                   str(form.titulo.data)+';'+\
                   str(form.tipo.data)+';'+\
                   str(form.necessita_despacho.data)+';'+\
                   str(form.conclu.data)+';'+\
                   str(form.convênio.data)+';'+\
                   str(form.autor.data)+';'+\
                   str(form.demanda_id.data)+';'+\
                   str(form.atividade.data)+';'+\
                   str(form.coord.data)+';'+\
                   str(form.necessita_despacho_cg.data)

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

    pesq_l = pesq.split(';')

    sei = pesq_l[0]
    if sei.find('_') != -1:
        sei = str(pesq_l[0]).split('_')[0]+'/'+str(pesq_l[0]).split('_')[1]

    if pesq_l[2] == 'Todos':
        p_tipo_pattern = ''
    else:
        p_tipo_pattern = pesq_l[2]

    p_n_d = 'Todos'
    if pesq_l[3] == 'Sim':
        p_n_d = '1'
    if pesq_l[3] == 'Não':
        p_n_d = '0'

    p_n_dcg = 'Todos'
    if pesq_l[10] == 'Sim':
        p_n_dcg = '1'
    if pesq_l[10] == 'Não':
        p_n_dcg = '0'

    # p_conclu = 'Todos'
    if pesq_l[4] == 'Todos':
        p_conclu = ''
    else:
        p_conclu = pesq_l[4]

    if pesq_l[5] != '':
        conv = pesq_l[5]
    else:
        conv = '%'

    if pesq_l[6] != '':
        autor_id = pesq_l[6]
    else:
        autor_id = '%'

    if pesq_l[7] == '':
        pesq_l[7] = '%'+str(pesq_l[7])+'%'
    else:
        pesq_l[7] = str(pesq_l[7])
    #atividade
    if pesq_l[8] == '':
        pesq_l[8] = '%'+str(pesq_l[8])+'%'
    else:
        pesq_l[8] = str(pesq_l[8])

    if pesq_l[9] == '':
        pesq_l[9] = '%'
    else:
        pesq_l[9] = str(pesq_l[9])



    demandas = db.session.query(Demanda.id,
                                Demanda.programa,
                                Demanda.sei,
                                Demanda.convênio,
                                Demanda.ano_convênio,
                                Demanda.tipo,
                                Demanda.data,
                                Demanda.user_id,
                                Demanda.titulo,
                                Demanda.desc,
                                Demanda.necessita_despacho,
                                Demanda.conclu,
                                Demanda.data_conclu,
                                Demanda.necessita_despacho_cg,
                                Demanda.urgencia,
                                Demanda.data_env_despacho,
                                Demanda.nota,
                                Plano_Trabalho.atividade_sigla,
                                User.coord,
                                User.username)\
                         .join(User, User.id == Demanda.user_id)\
                         .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                         .filter(Demanda.sei.like('%'+sei+'%'),
                                 coalesce(Demanda.convênio,'').like(conv),
                                 Demanda.titulo.like('%'+pesq_l[1]+'%'),
                                 Demanda.tipo.like('%'+p_tipo_pattern+'%'),
                                 cast(Demanda.necessita_despacho,String) != p_n_d,
                                 cast(Demanda.necessita_despacho_cg,String) != p_n_dcg,
                                 cast(Demanda.conclu,String).like('%'+p_conclu+'%'),
                                 cast(Demanda.user_id,String).like (autor_id),
                                 cast(Demanda.id,String).like (pesq_l[7]),
                                 cast(Demanda.programa,String).like (pesq_l[8]),
                                 cast(User.coord,String).like (pesq_l[9]))\
                         .order_by(Demanda.data.desc())\
                         .paginate(page=page,per_page=8)

    demandas_count  = demandas.total

    providencias = db.session.query(Providencia.demanda_id,
                                    Providencia.texto,
                                    Providencia.data,
                                    Providencia.user_id,
                                    label('username',User.username),
                                    Providencia.programada,
                                    Providencia.passo)\
                                    .outerjoin(User, Providencia.user_id == User.id)\
                                    .order_by(Providencia.data.desc()).all()

    despachos = db.session.query(Despacho.demanda_id,
                                 Despacho.texto,
                                 Despacho.data,
                                 Despacho.user_id,
                                 label('username',User.username +' - DESPACHO'),
                                 User.despacha,
                                 User.despacha2,
                                 User.despacha0,
                                 Despacho.passo)\
                                .outerjoin(User, Despacho.user_id == User.id)\
                                .order_by(Despacho.data.desc()).all()

    pro_des = providencias + despachos
    pro_des.sort(key=lambda ordem: ordem.data,reverse=True)

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

    # o choices do campo passos são definidos aqui e não no form
    passos = db.session.query(Passos_Tipos.passo, Passos_Tipos.ordem).filter(Passos_Tipos.tipo_id == tipo.id).order_by(Passos_Tipos.ordem).all()
    qtd = len(passos)
    lista_passos = [('('+str(p[1])+'/'+str(qtd)+') '+p[0],'('+str(p[1])+'/'+str(qtd)+') '+p[0]) for p in passos]
    lista_passos.insert(0,('',''))
    form = DespachoForm()
    form.passo.choices = lista_passos

    if form.validate_on_submit():

        if form.passo.data == None:
            passo = ''
        else:
            passo = form.passo.data

        despacho = Despacho(data       = datetime.now(),
                            user_id    = current_user.id,
                            demanda_id = demanda_id,
                            texto      = form.texto.data,
                            passo      = passo)

        db.session.add(despacho)
        db.session.commit()

        registra_log_auto(current_user.id,demanda_id,'des')

        # marca a demanda quanto à necessidade de despacho da CG
        # e desmarca, dependendo de quem deu o despacho.
        if form.necessita_despacho_cg.data:
            demanda.necessita_despacho_cg = 1
        else:
            demanda.necessita_despacho_cg = 0

        if form.necessita_despacho_cg == 1:
            demanda.data_env_despacho = datetime.now()

        if current_user.despacha == 1 or current_user.despacha0 == 1:
            demanda.necessita_despacho = 0

        if current_user.despacha2 == 1 and current_user.despacha == 0:
            demanda.necessita_despacho_cg = 0

        db.session.commit()

        # registra data de conclusão da demanda, caso o despachante use desta prerrogativa
        if form.conclu.data != '0':

            demanda.necessita_despacho    = 0
            demanda.necessita_despacho_cg = 0

            if demanda.conclu == '0':

                # enviar e-mail para chefes sobre demanda concluida
                chefes_emails = db.session.query(User.email)\
                                          .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                                  User.coord == current_user.coord)

                destino = []
                for email in chefes_emails:
                    destino.append(email[0])
                destino.append(current_user.email)

                if len(destino) > 1:

                    sistema = db.session.query(Sistema.nome_sistema).first()

                    html = render_template('email_demanda_conclu.html',demanda=demanda_id,user=current_user.username,
                                            titulo=demanda.titulo, sistema=sistema.nome_sistema)

                    pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==demanda.programa).first()

                    send_email('Demanda ' + str(demanda_id) + ' foi concluída (' + pt.atividade_sigla + ')', destino,'', html)

                    msg = Msgs_Recebidas(user_id    = demanda.user_id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda_id,
                                         msg        = 'A demanda foi concluída!')

                    db.session.add(msg)
                    db.session.commit()

            demanda.conclu      = form.conclu.data
            demanda.data_conclu = datetime.now()
            db.session.commit()
            registra_log_auto(current_user.id,demanda_id,'alt')

        else:

            demanda.conclu = '0'
            db.session.commit()

        #
        # envia e-mail par ao responsável pela demanda

        dono_email = db.session.query(User.email,User.username).filter(User.id == demanda.user_id).first()

        destino = []

        destino.append(dono_email.email)
        destino.append(current_user.email)

        sistema = db.session.query(Sistema.nome_sistema).first()

        html = render_template('email_despacho_emitido.html',demanda=demanda_id,user=current_user.username,
                                dono=dono_email.username,titulo=demanda.titulo, sistema=sistema.nome_sistema)

        pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==demanda.programa).first()

        send_email('Demanda ' + str(demanda_id) + ' recebeu um Despacho (' + pt.atividade_sigla + ')', destino,'', html)

        msg = Msgs_Recebidas(user_id    = demanda.user_id,
                             data_hora  = datetime.now(),
                             demanda_id = demanda_id,
                             msg        = 'A demanda recebeu um despacho!')

        db.session.add(msg)
        db.session.commit()

        # avisa que despacho foi criado e mostra a demanda

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

        demanda.nota = form.nota.data

        db.session.commit()

        registra_log_auto(current_user.id,demanda_id,'afe')

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

    # o choices do campo passos são definidos aqui e não no form
    passos = db.session.query(Passos_Tipos.passo, Passos_Tipos.ordem).filter(Passos_Tipos.tipo_id == tipo.id).order_by(Passos_Tipos.ordem).all()
    qtd = len(passos)
    lista_passos = [('('+str(p[1])+'/'+str(qtd)+') '+p[0],'('+str(p[1])+'/'+str(qtd)+') '+p[0]) for p in passos]
    lista_passos.insert(0,('',''))
    form = ProvidenciaForm()
    form.passo.choices = lista_passos

    if form.validate_on_submit():

        if form.data_hora.data > datetime.now():
            programada = 1
        else:
            programada = 0

        if form.passo.data == None:
            passo = ''
        else:
            passo = form.passo.data

        providencia = Providencia(demanda_id = demanda_id,
                                  data       = form.data_hora.data,
                                  texto      = form.texto.data,
                                  user_id    = current_user.id,
                                  duracao    = form.duracao.data,
                                  programada = programada,
                                  passo      = passo)

        db.session.add(providencia)
        db.session.commit()

        if programada == 1:
            registra_log_auto(current_user.id,demanda_id,'age',demanda.programa,form.duracao.data)
        else:
            registra_log_auto(current_user.id,demanda_id,'pro',demanda.programa,form.duracao.data)

# para o caso da providência exigir um despacho
        if form.necessita_despacho.data == True:

            # enviar e-mail para chefes, user que registrou a providência e dono da demanda
            if demanda.necessita_despacho == 0:

                chefes_emails = db.session.query(User.email,User.id)\
                                          .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                                  User.coord == current_user.coord)

                dono_email = db.session.query(User.email,User.id).filter(User.id == demanda.user_id).first()

                destino = []
                for email in chefes_emails:
                    destino.append(email[0])
                destino.append(current_user.email)
                destino.append(dono_email.email)

                if len(destino) > 1:

                    sistema = db.session.query(Sistema.nome_sistema).first()

                    html = render_template('email_pede_despacho.html',demanda=demanda_id,user=current_user.username,
                                            titulo=demanda.titulo,sistema=sistema.nome_sistema,tipo=demanda.tipo)

                    pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==demanda.programa).first()

                    send_email('Demanda ' + str(demanda_id) + ' requer despacho (' + pt.atividade_sigla + ')', destino,'', html)

                    for user in chefes_emails:
                        msg = Msgs_Recebidas(user_id    = user.id,
                                             data_hora  = datetime.now(),
                                             demanda_id = demanda_id,
                                             msg        = 'Chefia, a demanda está pedindo um despacho!')
                        db.session.add(msg)

                    msg = Msgs_Recebidas(user_id    = current_user.id,
                                         data_hora  = datetime.now(),
                                         demanda_id = demanda_id,
                                         msg        = 'Você marcou a opção -Necessita despacho?- na demanda!')
                    db.session.add(msg)

                    if dono_email.id != current_user.id:

                        msg = Msgs_Recebidas(user_id    = dono_email.id,
                                             data_hora  = datetime.now(),
                                             demanda_id = demanda_id,
                                             msg        = 'A opção -Necessita despacho?- foi marcada na sua demanda!')
                        db.session.add(msg)

                    db.session.commit()

            demanda.necessita_despacho = 1
            demanda.necessita_despacho_cg = 0
            demanda.data_env_despacho = datetime.now()

        else:

            demanda.necessita_despacho = 0

        if demanda.user_id == current_user.id:

            if form.conclu.data != '0':

                if demanda.conclu == '0':
                    demanda.conclu = form.conclu.data
                    demanda.data_conclu = datetime.now()
                    demanda.necessita_despacho = 0
                    demanda.necessita_despacho_cg = 0
                    #
                    # enviar e-mail para chefes sobre demanda concluida
                    chefes_emails = db.session.query(User.email)\
                                              .filter(or_(User.despacha == 1,User.despacha0 == 1),
                                                      User.coord == current_user.coord)

                    destino = []
                    for email in chefes_emails:
                        destino.append(email[0])
                    destino.append(current_user.email)

                    if len(destino) > 1:

                        sistema = db.session.query(Sistema.nome_sistema).first()

                        html = render_template('email_demanda_conclu.html',demanda=demanda_id,user=current_user.username,
                                                titulo=demanda.titulo,sistema=sistema.nome_sistema)

                        pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==demanda.programa).first()

                        send_email('Demanda ' + str(demanda_id) + ' foi concluída (' + pt.atividade_sigla + ')', destino,'', html)

                        msg = Msgs_Recebidas(user_id    = demanda.user_id,
                                             data_hora  = datetime.now(),
                                             demanda_id = demanda_id,
                                             msg        = 'A demanda foi concluída!')

                        db.session.add(msg)
                        db.session.commit()


                    registra_log_auto(current_user.id,demanda_id,'alt')
            else:
                demanda.conclu = '0'
                demanda.data_conclu = None

        db.session.commit()

        if demanda.user_id != current_user.id:

            dono_email = db.session.query(User.email,User.username).filter(User.id == demanda.user_id).first()

            destino = []

            destino.append(dono_email.email)
            destino.append(current_user.email)

            if len(destino) > 1:

                sistema = db.session.query(Sistema.nome_sistema).first()

                html = render_template('email_provi_alheia.html',demanda=demanda_id,user=current_user.username,
                                        dono=dono_email.username,titulo=demanda.titulo,sistema=sistema.nome_sistema)

                pt = db.session.query(Plano_Trabalho.atividade_sigla).filter(Plano_Trabalho.id==demanda.programa).first()

                send_email('Demanda ' + str(demanda_id) + ' com providência alheia (' + pt.atividade_sigla + ')', destino,'', html)

                msg = Msgs_Recebidas(user_id    = demanda.user_id,
                                     data_hora  = datetime.now(),
                                     demanda_id = demanda_id,
                                     msg        = 'A demanda recebeu uma providência alheia!')

                db.session.add(msg)
                db.session.commit()


        if programada == 1 and form.agenda.data:

            # cria evento no google agenda quando a providência for futura e o usuário assim o desejar
            scopes = ['https://www.googleapis.com/auth/calendar.events']

            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
                client_file = os.path.join(base_path, 'client.json')
            else:
                client_file = 'client.json'

            flow = InstalledAppFlow.from_client_secrets_file(client_file, scopes=scopes)

            # o flow acima apresenta um link enorme para que o usário concorde com o
            # SICOPES acessando sua agenda, mas isto só precisa ser feito uma vez, abaixo
            # as credenciais são armazenadas e usadas nos outros agendamentos

            pasta_token_antiga = os.path.normpath('/temp/token.pkl')
            pasta_token = os.path.normpath('/temp/token/token.pkl')

            if os.path.exists(pasta_token_antiga):
                os.makedirs(os.path.normpath('/temp/token/'))
                os.system('copy '+ pasta_token_antiga +' '+pasta_token)
                os.remove(pasta_token_antiga)

            if os.path.exists(pasta_token):
                credentials = pickle.load(open(pasta_token, "rb"))
            else:
                credentials = flow.run_console()
                pickle.dump(credentials, open(pasta_token, "wb"))

            service = build("calendar", "v3", credentials=credentials)

            ini = form.data_hora.data
            fim = ini + timedelta(minutes=form.duracao.data)
            timezone = 'America/Sao_Paulo'

            event = {
                      'summary': 'Demanda ' + str(demanda.id) + ' - Providência agendada',
                      'location': 'CNPq',
                      'description': form.texto.data,
                      'start': {
                        'dateTime': ini.strftime("%Y-%m-%dT%H:%M:%S"),
                        'timeZone': timezone,
                      },
                      'end': {
                        'dateTime': fim.strftime("%Y-%m-%dT%H:%M:%S"),
                        'timeZone': timezone,
                      },
                      'reminders': {
                        'useDefault': False,
                        'overrides': [
                          {'method': 'email', 'minutes': 24 * 60},
                          {'method': 'popup', 'minutes': 15},
                        ],
                      },
                    }

            service.events().insert(calendarId='primary', body=event).execute()

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

    hoje = date.today()
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

        ## conta demandas por tipo, destacando a quantidade concluída e a vida média
        demandas_count = db.session.query(Demanda,User.coord)\
                                   .join(User, Demanda.user_id == User.id)\
                                   .filter(User.coord.like(coord))\
                                   .count()

        demandas_por_tipo = db.session.query(Demanda.tipo,label('qtd_por_tipo',func.count(Demanda.id)))\
                                      .join(User, Demanda.user_id == User.id)\
                                      .order_by(func.count(Demanda.id).desc())\
                                      .filter(User.coord.like(coord))\
                                      .group_by(Demanda.tipo)

        demandas_por_tipo_ano_anterior = db.session.query(Demanda.tipo,label('qtd_por_tipo',func.count(Demanda.id)))\
                                                   .join(User, Demanda.user_id == User.id)\
                                                   .filter(Demanda.data >= str(hoje.year - 1) + '-1-1',
                                                           Demanda.data <= str(hoje.year - 1) + '-12-31',
                                                           User.coord.like(coord))\
                                                   .group_by(Demanda.tipo)

        demandas_por_tipo_ano_corrente = db.session.query(Demanda.tipo,label('qtd_por_tipo',func.count(Demanda.id)))\
                                                   .join(User, Demanda.user_id == User.id)\
                                                   .filter(Demanda.data >= str(hoje.year) + '-1-1',
                                                           User.coord.like(coord))\
                                                   .group_by(Demanda.tipo)

        m_top = hoje.month
        y_top = hoje.year
        m_ini = m_top - 11
        y_ini = y_top
        if m_ini < 1:
            m_ini += 12
            y_ini -= 1
        s_m_ini = str(m_ini)
        s_y_ini = str(y_ini)
        s_m_top = str(m_top)
        s_y_top = str(y_top)

        demandas_por_tipo_12meses = db.session.query(Demanda.tipo,label('qtd_por_tipo',func.count(Demanda.id)))\
                                              .join(User, Demanda.user_id == User.id)\
                                              .filter(Demanda.data >= s_y_ini+'-'+s_m_ini+'-1',
                                                      Demanda.data <= s_y_top+'-'+s_m_top+'-'+str(monthrange(y_top,m_top)[1]),
                                                      User.coord.like(coord))\
                                              .group_by(Demanda.tipo)

        demandas_tipos = db.session.query(Tipos_Demanda.tipo).filter(Tipos_Demanda.unidade.like(coord)).order_by(Tipos_Demanda.tipo).all()

        ## calcula a vida média das demandas por tipo
        vida_m_por_tipo = []

        for demanda in demandas_por_tipo:
            demandas_datas = db.session.query(Demanda.data,
                                              Demanda.data_conclu)\
                                        .join(User, Demanda.user_id == User.id)\
                                        .filter(Demanda.tipo == demanda.tipo,
                                                Demanda.conclu == '1',
                                                Demanda.data_conclu != None,
                                                User.coord.like(coord))

            demandas_conclu_por_tipo = db.session.query(Demanda.tipo,
                                                        label('qtd_conclu',func.count(Demanda.id)))\
                                                 .join(User, Demanda.user_id == User.id)\
                                                 .filter(Demanda.tipo == demanda.tipo,
                                                         Demanda.conclu == '1',
                                                         User.coord.like(coord))\
                                                 .group_by(Demanda.tipo)      

            vida = 0
            vida_m = 0

            for dia in demandas_datas:

                vida += (dia.data_conclu - dia.data).days

            if len(list(demandas_datas)) > 0:
                vida_m = round(vida/len(list(demandas_datas)))
            else:
                vida_m = 0

            if len(demandas_conclu_por_tipo.all()) != 0:
                vida_m_por_tipo.append([demanda.tipo,demandas_conclu_por_tipo[0][1],vida_m])

        ## calcula a vida média das demandas (geral)
        demandas_datas = db.session.query(Demanda.data,
                                          Demanda.data_conclu)\
                                    .join(User, Demanda.user_id == User.id)\
                                    .filter(Demanda.conclu == '1',
                                            Demanda.data_conclu != None,
                                            User.coord.like(coord))

        vida = 0
        vida_m = 0

        for dia in demandas_datas:
            vida += (dia.data_conclu - dia.data).days

        if len(list(demandas_datas)) > 0:
            vida_m = round(vida/len(list(demandas_datas)))
        else:
            vida_m = 0

        ## calcula a vida média das demandas (ano corrente)

        inic_ano = str(hoje.year) + '-01-01'

        demandas_ano = db.session.query(Demanda.data,
                                        Demanda.data_conclu)\
                                  .join(User, Demanda.user_id == User.id)\
                                  .filter(Demanda.conclu == '1',
                                          Demanda.data > inic_ano,
                                          User.coord.like(coord))
        vida = 0
        vida_m_ano = 0

        for dia in demandas_ano:
            vida += (dia.data_conclu - dia.data).days

        if len(list(demandas_ano)) > 0:
            vida_m_ano = round(vida/len(list(demandas_ano)))
        else:
            vida_m_ano = 0


        ## calcula o prazo médio dos despachos
        despachos = db.session.query(label('c_data',Despacho.data),
                                     Despacho.demanda_id,
                                     Demanda.id,
                                     label('i_data',Demanda.data))\
                               .join(User, Despacho.user_id == User.id)\
                               .outerjoin(Demanda, Despacho.demanda_id == Demanda.id)\
                               .filter(User.coord.like(coord))\
                               .all()

        desp = 0
        desp_m = 0

        for despacho in despachos:
            desp += (despacho.c_data - despacho.i_data).days

        if len(list(despachos)) > 0:
            desp_m = round(desp/len(list(despachos)))
        else:
            desp_m = 0

        # porcentagem de conclusão das demandas

        demandas_total = demandas_count

        demandas_conclu = db.session.query(Demanda,User.coord)\
                                    .join(User, Demanda.user_id == User.id)\
                                    .filter(Demanda.conclu == '1',
                                            User.coord.like(coord))\
                                    .count()

        if demandas_total != 0:
            percent_conclu = round((demandas_conclu / demandas_total) * 100)
        else:
            percent_conclu = 0

        # média, maior quantidade e menor quantidade de demandas por colaborador ativo.

        colaborador_demandas = db.session.query(Demanda.user_id,
                                                label('qtd',func.count(Demanda.user_id)))\
                                         .join(User, Demanda.user_id == User.id)\
                                         .filter(User.coord.like(coord))\
                                         .group_by(Demanda.user_id)

        pessoas = db.session.query(User.id,User.ativo)\
                            .filter(User.coord.like(coord))\
                            .all()

        qtd_demandas = []
        for c_d in colaborador_demandas:
            for p in pessoas:
                if c_d.user_id == p.id:
                    if p.ativo == 1:
                        qtd_demandas.append(c_d.qtd)

        if len(qtd_demandas) > 0:
            qtd_demandas_max = max(qtd_demandas)
            qtd_demandas_min = min(qtd_demandas)
            qtd_demandas_avg = round(sum(qtd_demandas)/len(qtd_demandas))
        else:
            qtd_demandas_max = 0
            qtd_demandas_min = 0
            qtd_demandas_avg = 0

        # média de demandas, providêndcias e despachos por mês nos últimos 12 meses

        meses = []
        for i in range(12):
            m = hoje.month-i
            y = hoje.year
            if m < 1:
                m += 12
                y -= 1
            if m >= 0 and m < 10:
                m = '0' + str(m)
            meses.append((str(m),str(y)))

        demandas_12meses = [db.session.query(Demanda)\
                                      .join(User, Demanda.user_id == User.id)\
                                      .filter(Demanda.data >= mes[1]+'-'+mes[0]+'-01',
                                              Demanda.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                              User.coord.like(coord))\
                                      .count()
                            for mes in meses]

        med_dm = round(sum(demandas_12meses)/len(demandas_12meses))
        max_dm = max(demandas_12meses)
        min_dm = min(demandas_12meses)
        if med_dm != 0:
            mes_max_dm = meses[demandas_12meses.index(max_dm)]
            mes_min_dm = meses[demandas_12meses.index(min_dm)]
        else:
            mes_max_dm = 0
            mes_min_dm = 0

        providencias_12meses = [db.session.query(Providencia)\
                                          .join(User, Providencia.user_id == User.id)\
                                          .filter(Providencia.data >= mes[1]+'-'+mes[0]+'-01',
                                                  Providencia.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                  User.coord.like(coord))\
                                          .count()
                                for mes in meses]

        med_pr = round(sum(providencias_12meses)/len(providencias_12meses))
        max_pr = max(providencias_12meses)
        min_pr = min(providencias_12meses)
        if med_pr != 0:
            mes_max_pr = meses[providencias_12meses.index(max_pr)]
            mes_min_pr = meses[providencias_12meses.index(min_pr)]
        else:
            mes_max_pr = 0
            mes_min_pr = 0

        despachos_12meses = [db.session.query(Despacho)\
                                       .join(User, Despacho.user_id == User.id)\
                                       .filter(Despacho.data >= mes[1]+'-'+mes[0]+'-01',
                                               Despacho.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                               User.coord.like(coord))\
                                       .count()
                             for mes in meses]

        med_dp = round(sum(despachos_12meses)/len(despachos_12meses))
        max_dp = max(despachos_12meses)
        min_dp = min(despachos_12meses)
        if med_dp != 0:
            mes_max_dp = meses[despachos_12meses.index(max_dp)]
            mes_min_dp = meses[despachos_12meses.index(min_dp)]
        else:
            mes_max_dp = 0
            mes_min_dp = 0

        return render_template ('demandas_resumo.html', demandas_count = demandas_count,
                                                        demandas_por_tipo = demandas_por_tipo,
                                                        demandas_por_tipo_ano_anterior=demandas_por_tipo_ano_anterior,
                                                        demandas_por_tipo_ano_corrente=demandas_por_tipo_ano_corrente,
                                                        demandas_por_tipo_12meses=demandas_por_tipo_12meses,
                                                        demandas_tipos=demandas_tipos,
                                                        vida_m_por_tipo = vida_m_por_tipo,
                                                        vida_m = vida_m,
                                                        desp_m = desp_m,
                                                        percent_conclu = percent_conclu,
                                                        vida_m_ano = vida_m_ano,
                                                        qtd_demandas_max=qtd_demandas_max,
                                                        qtd_demandas_min=qtd_demandas_min,
                                                        qtd_demandas_avg=qtd_demandas_avg,
                                                        med_dm=med_dm,
                                                        max_dm=max_dm,
                                                        mes_max_dm=mes_max_dm,
                                                        min_dm=min_dm,
                                                        mes_min_dm=mes_min_dm,
                                                        med_pr=med_pr,
                                                        max_pr=max_pr,
                                                        mes_max_pr=mes_max_pr,
                                                        min_pr=min_pr,
                                                        mes_min_pr=mes_min_pr,
                                                        med_dp=med_dp,
                                                        max_dp=max_dp,
                                                        mes_max_dp=mes_max_dp,
                                                        min_dp=min_dp,
                                                        mes_min_dp=mes_min_dp,
                                                        form=form)


# números por usuário

@demandas.route('<int:usu>/numeros_usu', methods=['GET','POST'])
@login_required
def numeros_usu(usu):
    """+--------------------------------------------------------------------------------------+                                                                          |
       |Mostra estatísticas do usuário.                                                       |
       +--------------------------------------------------------------------------------------+
    """
    hoje = date.today()

    #dados usuário
    usuario = db.session.query(User).filter(User.id == usu).first()

    # calcula quantidade de demandas do usuário
    user_demandas = db.session.query(Demanda.user_id,func.count(Demanda.user_id))\
                                .filter(Demanda.user_id == usu)\
                                .group_by(Demanda.user_id)

    qtd_demandas = user_demandas[0][1]

    # calcula quantidade de demandas concluídas do usuário
    user_demandas_conclu = db.session.query(Demanda.user_id,func.count(Demanda.user_id))\
                                        .filter(Demanda.user_id == usu, Demanda.conclu == '1')\
                                        .group_by(Demanda.user_id)

    qtd_demandas_conclu = user_demandas_conclu[0][1]

    if qtd_demandas != 0:
        percent_conclu = round((qtd_demandas_conclu / qtd_demandas) * 100)
    else:
        percent_conclu = 0

    ## calcula a vida média das demandas do usuário
    demandas_datas = db.session.query(Demanda.data,Demanda.data_conclu)\
                                .filter(Demanda.conclu == '1', Demanda.data_conclu != None, Demanda.user_id == usu)

    vida = 0
    vida_m = 0

    for dia in demandas_datas:
        vida += (dia.data_conclu - dia.data).days

    if len(list(demandas_datas)) > 0:
        vida_m = round(vida/len(list(demandas_datas)))
    else:
        vida_m = 0

    ## calcula o prazo médio dos despachos
    despachos = db.session.query(label('c_data',Despacho.data), Despacho.demanda_id, Demanda.id, label('i_data',Demanda.data))\
                            .outerjoin(Demanda, Despacho.demanda_id == Demanda.id)\
                            .filter(Demanda.user_id == usu)\
                            .all()

    desp = 0
    desp_m = 0

    for despacho in despachos:
        desp += (despacho.c_data - despacho.i_data).days

    if len(list(despachos)) > 0:
        desp_m = round(desp/len(list(despachos)))
    else:
        desp_m = 0

    ## média de demandas, providêndcias e despachos por mês nos últimos 12 meses

    meses = []
    for i in range(12):
        m = hoje.month-i-1
        y = hoje.year
        if m < 1:
            m += 12
            y -= 1
        if m >= 0 and m < 10:
            m = '0' + str(m)
        meses.append((str(m),str(y)))

    demandas_12meses = [Demanda.query.filter(Demanda.data >= mes[1]+'-'+mes[0]+'-01',
                                                Demanda.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                Demanda.user_id == usu).count()
                                                for mes in meses]

    med_dm = round(sum(demandas_12meses)/len(demandas_12meses))
    max_dm = max(demandas_12meses)
    mes_max_dm = meses[demandas_12meses.index(max_dm)]
    min_dm = min(demandas_12meses)
    mes_min_dm = meses[demandas_12meses.index(min_dm)]

    providencias_12meses = [Providencia.query.filter(Providencia.data >= mes[1]+'-'+mes[0]+'-01',
                                                Providencia.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                Providencia.user_id == usu).count()
                                                for mes in meses]

    med_pr = round(sum(providencias_12meses)/len(providencias_12meses))
    max_pr = max(providencias_12meses)
    mes_max_pr = meses[providencias_12meses.index(max_pr)]
    min_pr = min(providencias_12meses)
    mes_min_pr = meses[providencias_12meses.index(min_pr)]

    minutos_dedicados_12meses = [db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= mes[1]+'-'+mes[0]+'-01',
                                                Providencia.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                Providencia.user_id == usu).all()
                                                for mes in meses]

    minutos_log_man_12meses = [db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= mes[1]+'-'+mes[0]+'-01',
                                                Log_Auto.data_hora <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                Log_Auto.user_id == usu).all()
                                                for mes in meses]

    hd_p = [min[0][0] if min[0][0] is not None else 0 for min in minutos_dedicados_12meses]
    hd_l = [min[0][0] if min[0][0] is not None else 0 for min in minutos_log_man_12meses]
    hd_z = zip(hd_p,hd_l)
    hd = [x+y for (x,y) in hd_z]

    med_hd = round((sum(hd)/len(hd))/60)
    max_hd = round(max(hd)/60)
    mes_max_hd = meses[hd.index(max(hd))]
    min_hd = round(min(hd)/60)
    mes_min_hd = meses[hd.index(min(hd))]

    start = hoje - timedelta(days=hoje.weekday())
    end = start + timedelta(days=6)

    minutos_dedicados_semana_p = db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= start,
                                                Providencia.data <= end,
                                                Providencia.user_id == usu).all()

    minutos_dedicados_semana_l = db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= start,
                                            Log_Auto.data_hora <= end,
                                            Log_Auto.user_id == usu).all()

    md_p = minutos_dedicados_semana_p[0][0]
    md_l = minutos_dedicados_semana_l[0][0]

    if md_p is None:
        md_p = 0

    if md_l is None:
        md_l = 0

    horas_dedicadas_semana = round((md_p + md_l) / 60)

    return render_template('numeros_usu.html',qtd_demandas=qtd_demandas,
                                          qtd_demandas_conclu=qtd_demandas_conclu,
                                          percent_conclu=percent_conclu,
                                          vida_m=vida_m,
                                          desp_m=desp_m,
                                          med_dm=med_dm,
                                          max_dm=max_dm,
                                          mes_max_dm=mes_max_dm,
                                          min_dm=min_dm,
                                          mes_min_dm=mes_min_dm,
                                          med_pr=med_pr,
                                          max_pr=max_pr,
                                          mes_max_pr=mes_max_pr,
                                          min_pr=min_pr,
                                          mes_min_pr=mes_min_pr,
                                          med_hd=med_hd,
                                          max_hd=max_hd,
                                          mes_max_hd=mes_max_hd,
                                          min_hd=min_hd,
                                          mes_min_hd=mes_min_hd,
                                          horas=horas_dedicadas_semana,
                                          usuario=usuario)

