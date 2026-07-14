"""
.. topic:: Usuários (views)

    Usuários registrados são os técnicos que administram suas demandas neste aplicativo.
    Cada usuário tem seu ID, nome, e-mail e senha únicos, podendo ter também uma imagem personalizada
    de perfil, caso deseje.

    O registro é feito por meio da respectiva opção no menu do aplicativo, com o preenchimento dos dados
    básicos do usuário. Este registro precisa ser confirmado com o token enviado pelo sistema, por e-mail,
    ao usúario.

    Para entrar no aplicativo, o usuário se idenfica com seu e-mail e informa sua senha pessoal.

    O usuário pode alterar seus dados de perfil, contudo, para alterar sua senha, seja por motivo de
    esquecimento, ou simplemente porque quer alterá-la, o procedimento envolve o envio de um e-mail
    do sistema para seu endereço de e-mail registrado, com o token que abre uma tela para registro de
    nova senha. Este token tem validade de uma hora.

    As funções relativas ao tratamento de demandas só ficam disponíveis no menu para usuários registrados.

.. topic:: Ações relacionadas aos usuários:

    * Funções auxiliares:
        * Envia e-mail de forma assincrona: send_async_email
        * Prepara e-mail: send_email
        * Dados para e-mail de confirmação: send_confirmation_email
        * Dados para e-mail de troca de senha: send_password_reset_email
    * Registro de usuário: register
    * Trata retorno da confirmação: confirm_email
    * Trata pedido de troca de senha: reset
    * Realiza troca de senha: reset_with_token
    * Entrada de usuário: login
    * Saída de usuário: logout
    * Atualizar dados do usuário: account
    * Demandas de um usuário: user_posts
    * Lista plano de trabalho (atividades) de um usuário: user_pt
    * Registrar versão do sistema: admin_reg_ver
    * Visão dos usuários pelo admin: admin_view_users
    * Log de atividades: user_log
    * Registro de observações do usuário no log: user_obs
    * Lista mensagens recentes recebidas pelo usuário: user_msgs_recebidas
    * Relatório de atividades: user_rel
    * Ver lista de usuários ativos da coordenação: coord_view_users
    * Registrar atividade para usuário: user_ativ
    * Removendo atividade de um usuário: delete_atividade_usu

"""
# views.py na pasta users

from itsdangerous import URLSafeTimedSerializer
from flask import render_template, url_for, flash, redirect, request, Blueprint, abort
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
from wtforms import ValidationError
from threading import Thread
from datetime import datetime, date, timedelta, time
from calendar import monthrange
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from sqlalchemy.sql import label
from sqlalchemy.orm import aliased
from collections import Counter

from project import db, mail, app, sched
from project.models import User, Demanda, Despacho, Providencia, Coords, Log_Auto,\
                           Log_Desc, Plano_Trabalho, Sistema, RefSICONV, Ativ_Usu, Msgs_Recebidas
from project.users.forms import RegistrationForm, LoginForm, UpdateUserForm, EmailForm, PasswordForm, AdminForm,\
                                LogForm, LogFormMan, VerForm, RelForm, AtivUsu, TrocaPasswordForm, CoordForm, TipoLogForm
from project.core.views import cargaSICONV, chamadas_DW
from project.demandas.views import registra_log_auto
from project.users import services

users = Blueprint('users',__name__)

# registrar

@users.route('/register', methods=['GET','POST'])
def register():
    """+--------------------------------------------------------------------------------------+
       |Efetua o registro de um usuário. Este recebe o aviso para verificar sua caixa de      |
       |e-mails, pois o aplicativo envia uma mensagem sobre a confirmação do registro.        |
       +--------------------------------------------------------------------------------------+
    """

    form = RegistrationForm()

    if form.validate_on_submit():

        try:
            form.check_username(form.username)
            form.check_email(form.email)
        except ValidationError:
            return render_template('register.html', form=form)

        services.registrar_usuario(
            email=form.email.data,
            username=form.username.data,
            password=form.password.data,
            coord=form.coord.data,
            despacha0=form.despacha0,
            despacha=form.despacha,
            despacha2=form.despacha2,
        )

        flash('Usuário registrado! Verifique sua caixa de e-mail para confirmar o endereço.','sucesso')
        return redirect(url_for('core.inicio'))

    return render_template('register.html',form=form)

# confirmar registro

@users.route('/confirm/<token>')
def confirm_email(token):
    """+--------------------------------------------------------------------------------------+
       |Trata o retorno do e-mail de confirmação de registro, verificano se o token enviado   |
       |é válido (igual ao enviado no momento do registro e tem menos de 1 hora de vida).     |
       +--------------------------------------------------------------------------------------+
    """
    status, user = services.confirmar_email(token)

    if status == 'invalido':
        flash('O link de confirmação é inválido ou expirou.', 'erro')
    elif status == 'ja_confirmado':
        flash('Confirmação já realizada. Por favor, faça o login.', 'erro')
    else:
        flash('Obrigado por confirmar seu endereço de e-mail! Caso já tenha uma janela do sistema aberta, pode fechar a anterior.','sucesso')

    return redirect(url_for('users.login'))

# gera token para resetar senha

@users.route('/reset', methods=["GET", "POST"])
def reset():
    """+--------------------------------------------------------------------------------------+
       |Trata o pedido de troca de senha. Enviando um e-mail para o usuário.                  |
       |O usuário deve estar registrado (com registro confirmado) antes de poder efetuar uma  |
       |troca de senha.                                                                       |
       |O aplicativo envia uma mensagem ao usuário sobre o procedimento de troca de senha.    |
       +--------------------------------------------------------------------------------------+
    """
    form = EmailForm()

    if form.validate_on_submit():

        status = services.solicitar_reset_senha(form.email.data)

        if status == 'nao_encontrado':
            flash('Endereço de e-mail inválido!', 'erro')
            return render_template('email.html', form=form)
        elif status == 'nao_confirmado':
            flash('Seu endereço de e-mail precisa ser confirmado antes de tentar efetuar uma troca de senha.', 'erro')
        else:
            flash('Verifique a caixa de entrada de seu e-mail. Uma mensagem com o link de atualização de senha foi enviado.', 'sucesso')

        return redirect(url_for('users.login'))

    return render_template('email.html', form=form)

# trocar ou gerar nova senha via link

@users.route('/reset/<token>', methods=["GET", "POST"])
def reset_with_token(token):
    """+--------------------------------------------------------------------------------------+
       |Trata o retorno do e-mail enviado ao usuário com token de troca de senha.             |
       |Verifica se o token é válido.                                                         |
       |Abre tela para o usuário informar nova senha.                                         |
       +--------------------------------------------------------------------------------------+
    """
    form = PasswordForm()

    if form.validate_on_submit():

        status, user = services.redefinir_senha_com_token(token, form.password.data)

        if status == 'token_invalido':
            flash('O link de atualização de senha é inválido ou expirou.', 'erro')
            return redirect(url_for('users.login'))
        elif status == 'usuario_invalido':
            flash('Endereço de e-mail inválido!', 'erro')
            return redirect(url_for('users.login'))

        flash('Sua senha foi atualizada!', 'sucesso')
        return redirect(url_for('users.login'))

    return render_template('troca_senha_com_token.html', form=form, token=token)

# trocar ou gerar nova senha via app

@users.route('/troca_senha', methods=["GET", "POST"])
def troca_senha():
    """+--------------------------------------------------------------------------------------+
       |Abre tela para o usuário informar nova senha.                                         |
       +--------------------------------------------------------------------------------------+
    """

    form = TrocaPasswordForm()

    if form.validate_on_submit():

        status = services.trocar_senha(current_user, form.password_atual.data, form.password_nova.data)

        if status == 'inativo':
            flash('Usuário deve ser ativado antes de poder trocar senha!', 'erro')
            return redirect(url_for('users.login'))
        elif status == 'trocada':
            logout_user()
            flash('Sua senha foi atualizada!', 'sucesso')
            return redirect(url_for('users.login'))

    return render_template('troca_senha.html', form=form)


# login

@users.route('/login', methods=['GET','POST'])
def login():
    """+--------------------------------------------------------------------------------------+
       |Fornece a tela para que o usuário entre no sistema (login).                           |
       |O acesso é feito por e-mail e senha cadastrados.                                      |
       |Antes do primeiro acesso após o registro, o usuário precisa cofirmar este registro    |
       |para poder fazer o login, conforme mensagem enviada.                                  |
       +--------------------------------------------------------------------------------------+
    """
    form = LoginForm()

    if form.validate_on_submit():

        status, user = services.autenticar(form.email.data, form.password.data)

        if status == 'autenticado':
            login_user(user)

            flash('Login bem sucedido!','sucesso')

            next = request.args.get('next')

            if next == None or not next[0] == '/':
                next = url_for('core.inicio')

            return redirect(next)

        elif status == 'nao_encontrado':
            flash('E-mail informado não encontrado, favor verificar!','erro')
        elif status == 'senha_incorreta':
            flash('Senha não confere, favor verificar!','erro')
        elif status == 'nao_confirmado':
            flash('Endereço de e-mail não confirmado ainda!','erro')

    return render_template('login.html',form=form)

# logout

@users.route('/logout')
def logout():
    """+--------------------------------------------------------------------------------------+
       |Efetua a saída do usuário do sistema.                                                 |
       +--------------------------------------------------------------------------------------+
    """
    logout_user()
    return redirect(url_for("core.inicio"))

# conta (update UserForm)

@users.route('/account', methods=['GET','POST'])
@login_required
def account():
    """+--------------------------------------------------------------------------------------+
       |Permite que o usuário atualize seus dados.                                            |
       |A tela é acessada quando o usuário clica em seu nome na barra de menus.               |
       |Este pode atualizar seu nome de usuário, seu endereço de e-mail e sua imagem          |
       |de perfil .                                                                           |
       |Mostra estatísticas do usuário.                                                       |
       +--------------------------------------------------------------------------------------+
    """
    hoje = date.today()

    form = UpdateUserForm()

    if form.validate_on_submit():

        current_user.username = form.username.data
        current_user.email = form.email.data

        #if form.picture.data:

        #    pic = add_profile_pic(form.picture.data)
        #    current_user.profile_image = pic

        db.session.commit()

        registra_log_auto(current_user.id,None,'usu')

        flash('Usuário atualizado!','sucesso')
        return redirect (url_for('users.account'))

    elif request.method == "GET":

        form.username.data = current_user.username
        form.email.data = current_user.email

        # calcula quantidade de demandas do usuário
        user_demandas = db.session.query(Demanda.user_id,func.count(Demanda.user_id))\
                                  .filter(Demanda.user_id == current_user.id)\
                                  .group_by(Demanda.user_id)

        qtd_demandas = user_demandas[0][1]

        # calcula quantidade de demandas concluídas do usuário
        user_demandas_conclu = db.session.query(Demanda.user_id,func.count(Demanda.user_id))\
                                         .filter(Demanda.user_id == current_user.id, Demanda.conclu == '1')\
                                         .group_by(Demanda.user_id)

        qtd_demandas_conclu = user_demandas_conclu[0][1]

        if qtd_demandas != 0:
            percent_conclu = round((qtd_demandas_conclu / qtd_demandas) * 100)
        else:
            percent_conclu = 0

        ## calcula a vida média das demandas do usuário
        demandas_datas = db.session.query(Demanda.data,Demanda.data_conclu)\
                                    .filter(Demanda.conclu == '1', Demanda.data_conclu != None, Demanda.user_id == current_user.id)

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
                              .filter(Demanda.user_id == current_user.id)\
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
                                                 Demanda.user_id == current_user.id).count()
                                                 for mes in meses]

        med_dm = round(sum(demandas_12meses)/len(demandas_12meses))
        max_dm = max(demandas_12meses)
        mes_max_dm = meses[demandas_12meses.index(max_dm)]
        min_dm = min(demandas_12meses)
        mes_min_dm = meses[demandas_12meses.index(min_dm)]

        providencias_12meses = [Providencia.query.filter(Providencia.data >= mes[1]+'-'+mes[0]+'-01',
                                                 Providencia.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                 Providencia.user_id == current_user.id).count()
                                                 for mes in meses]

        med_pr = round(sum(providencias_12meses)/len(providencias_12meses))
        max_pr = max(providencias_12meses)
        mes_max_pr = meses[providencias_12meses.index(max_pr)]
        min_pr = min(providencias_12meses)
        mes_min_pr = meses[providencias_12meses.index(min_pr)]

        minutos_dedicados_12meses = [db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= mes[1]+'-'+mes[0]+'-01',
                                                 Providencia.data <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                 Providencia.user_id == current_user.id).all()
                                                 for mes in meses]

        minutos_log_man_12meses = [db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= mes[1]+'-'+mes[0]+'-01',
                                                 Log_Auto.data_hora <= mes[1]+'-'+mes[0]+'-'+str(monthrange(int(mes[1]),int(mes[0]))[1]),
                                                 Log_Auto.user_id == current_user.id).all()
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
                                                 Providencia.user_id == current_user.id).all()

        minutos_dedicados_semana_l = db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= start,
                                              Log_Auto.data_hora <= end,
                                              Log_Auto.user_id == current_user.id).all()

        md_p = minutos_dedicados_semana_p[0][0]
        md_l = minutos_dedicados_semana_l[0][0]

        if md_p is None:
            md_p = 0

        if md_l is None:
            md_l = 0

        horas_dedicadas_semana = round((md_p + md_l) / 60)

    return render_template('account.html',form=form,
                                          qtd_demandas=qtd_demandas,
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
                                          horas=horas_dedicadas_semana)

# lista das demandas de um usuário

@users.route('/user_posts/<filtro>/<username>')
def user_posts (username,filtro):
    """+--------------------------------------------------------------------------------------+
       |Mostra as demandas de um usuário quando seu nome é selecionado em uma tela de         |
       |consulta de demandas.                                                                 |
       |Recebe o nome do usuário como parâmetro e o tipo de consulta (filtro)                 |
       +--------------------------------------------------------------------------------------+
    """

    qtd = 0

    com_despacho_novo = []
    com_despacho_novo_data = {}
    para_despacho = []
    com_usu = []

    if username == 'todos':
        user_id = '%'
        user = None
    else:
        user = User.query.filter_by(username=username).first_or_404()
        user_id = user.id


    # DEMANDAS NÃO CONCLUÍDAS
    if filtro[0:2] == 'nc':

        if user_id == '%':
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
                                        Demanda.data_verific)\
                                .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                                .filter(Demanda.conclu == '0')\
                                .order_by(Demanda.urgencia,Demanda.data.desc())\
                                .all()
        else:
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
                                        Demanda.data_verific)\
                                .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                                .filter(Demanda.user_id == user_id,
                                        Demanda.conclu == '0')\
                                .order_by(Demanda.urgencia,Demanda.data.desc())\
                                .all()


        # verificar se tem despacho novo
        for demanda in demandas:

            providencias = db.session.query(Providencia.data,
                                            label('tipo','PROV - '+ Providencia.texto))\
                                            .filter(Providencia.demanda_id == demanda.id)\
                                            .order_by(Providencia.data.desc()).all()

            despachos = db.session.query(Despacho.data,
                                         label('tipo','DESP - '+Despacho.texto))\
                                        .filter_by(demanda_id=demanda.id)\
                                        .order_by(Despacho.data.desc()).all()

            pro_des = providencias + despachos
            pro_des.sort(key=lambda ordem: ordem.data,reverse=True)

            if pro_des != []:
                if pro_des[0].tipo[0:6] == 'DESP -':
                    com_despacho_novo.append(demanda.id)
                    com_despacho_novo_data[demanda.id] = pro_des[0].data

            if demanda.necessita_despacho == 1 or demanda.necessita_despacho_cg == 1:
                para_despacho.append(demanda.id)

            if demanda.id not in com_despacho_novo and demanda.necessita_despacho == 0 and demanda.necessita_despacho_cg == 0:
                com_usu.append(demanda.id)

    # DEMANDAS CONCLUÍDAS
    elif filtro == 'conclu':

        if user_id == '%':
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
                                        Plano_Trabalho.atividade_sigla)\
                                        .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                                        .filter(Demanda.conclu != '0')\
                                        .order_by(Demanda.data_conclu.desc())\
                                        .all()
        else:
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
                                        Plano_Trabalho.atividade_sigla)\
                                        .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                                        .filter(Demanda.user_id == user_id,
                                                Demanda.conclu != '0')\
                                        .order_by(Demanda.data_conclu.desc())\
                                        .all()

    # TODAS AS DEMANDAS
    else:

        if user_id == '%':
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
                                        Plano_Trabalho.atividade_sigla)\
                                        .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                                        .order_by(Demanda.urgencia,Demanda.data.desc())\
                                        .all()
        else:
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
                                        Plano_Trabalho.atividade_sigla)\
                                        .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)\
                                        .filter(Demanda.user_id == user_id)\
                                        .order_by(Demanda.urgencia,Demanda.data.desc())\
                                        .all()


    qtd = len(demandas)

    return render_template('user_demandas.html',demandas=demandas,user=user, filtro=filtro, qtd = qtd,\
                            com_despacho_novo=com_despacho_novo, qtd_cdn=len(com_despacho_novo), qtd_pdes=len(para_despacho),\
                            qtd_com_usu=len(com_usu),com_despacho_novo_data=com_despacho_novo_data)

#
# lista plano de trabalho (atividades) de um usuário

@users.route('/user_pt/int:<user_id>')
def user_pt (user_id):
    """+--------------------------------------------------------------------------------------+
       |Mostra as atividades designadas a um usuário no plano de trabalho da                  |
       |coordenação.                                                                          |
       |Recebe o id do usuário como parâmetro.                                                |
       +--------------------------------------------------------------------------------------+
    """

    user = User.query.get_or_404(user_id)

    atividades_1 = db.session.query(Plano_Trabalho.id,
                                    Plano_Trabalho.atividade_sigla,
                                    Plano_Trabalho.atividade_desc,
                                    Plano_Trabalho.natureza,
                                    Plano_Trabalho.meta)\
                                    .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                    .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Titular')\
                                    .order_by(Plano_Trabalho.natureza,Plano_Trabalho.atividade_sigla).all()

    quantidade_1 = len(atividades_1)

    carga_1 = db.session.query(label('total',func.sum(Plano_Trabalho.meta)))\
                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                        .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Titular').all()

    if carga_1[0][0] == 0 or carga_1[0][0] == None:
        carga_1_total = 0
    else:
        carga_1_total = carga_1[0][0]

    atividades_2 = db.session.query(Plano_Trabalho.id,
                                    Plano_Trabalho.atividade_sigla,
                                    Plano_Trabalho.atividade_desc,
                                    Plano_Trabalho.natureza,
                                    Plano_Trabalho.meta)\
                                    .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                    .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Suplente')\
                                    .order_by(Plano_Trabalho.natureza,Plano_Trabalho.atividade_sigla).all()

    quantidade_2 = len(atividades_2)

    carga_2 = db.session.query(label('total',func.sum(Plano_Trabalho.meta)))\
                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                        .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Suplente').all()

    if carga_2[0][0] == 0 or carga_2[0][0] == None:
        carga_2_total = 0
    else:
        carga_2_total = carga_2[0][0]


    return render_template('user_pt.html',user=user, atividades_1=atividades_1, atividades_2=atividades_2,\
                            quantidade_1=quantidade_1, quantidade_2=quantidade_2, carga_1=carga_1_total, carga_2=carga_2_total)

# admim registra nova versão do sistema no banco de dadosSEI e outras condições

@users.route('/admin_reg_ver', methods=['GET', 'POST'])
@login_required

def admin_reg_ver():
    """+--------------------------------------------------------------------------------------+
       |O admin atualiza no banco de dados (tabela Users) a versão do sistema após uma        |
       |atualização e outros parâmetros do sistema.                                           |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)
    else:
        users   = User.query.order_by(User.id).all()
        sistema = Sistema.query.first()
        inst    = RefSICONV.query.first()

        form = VerForm()

        if form.validate_on_submit():

            for user in users:

                user.sversion = form.ver.data
                if not form.funcionalidade_conv.data:
                    user.trab_conv = 0
                if not form.funcionalidade_acordo.data:
                    user.trab_acordo = 0
                if not form.funcionalidade_instru.data:
                    user.trab_instru = 0

            db.session.commit()

            sistema.nome_sistema          = form.nome_sistema.data
            sistema.descritivo            = form.descritivo.data
            if form.funcionalidade_conv.data:
                sistema.funcionalidade_conv   = '1'
            else:
                sistema.funcionalidade_conv   = '0'
            if form.funcionalidade_acordo.data:
                sistema.funcionalidade_acordo = '1'
            else:
                 sistema.funcionalidade_acordo = '1'
            if form.funcionalidade_instru.data:
                sistema.funcionalidade_instru = '1'
            else:
                sistema.funcionalidade_instru = '0'
            inst.cod_inst                 = form.cod_inst.data

            
            id_1 = 'carga_siconv'
            id_2 = 'carga_chamadas_DW'      
            
            if form.carga_auto.data: 

                sistema.carga_auto   = '1'   

                # VERIFICA E, SER FOR O CASO, AGENDA CARGA SICONV

                try:
                    job_existente = sched.get_job(id_1)
                    if job_existente:
                        executa = False
                    else:
                        executa = True      
                except:
                    executa = True

                if executa:

                    dia_semana = 'mon-fri'
                    hora       = 8
                    minuto     = 13

                    msg = ('*** Agendamento acionado '+id_1+', rodando '+dia_semana+', às '+str(hora)+':'+str(minuto)+' ***')
                    print(msg)
                    try:
                        sched.add_job(trigger='cron', id=id_1, func=cargaSICONV, day_of_week=dia_semana, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
                        sched.start()
                    except:
                        sched.reschedule_job(id_1, trigger='cron', day_of_week=dia_semana, hour=hora, minute=minuto)

                    registra_log_auto(current_user.id,None,'agc')    

                # VERIFICA E, SER FOR O CASO, AGENDA CARGA DW                                                        

                try:
                    job_existente = sched.get_job(id_2)
                    if job_existente:
                        executa = False
                    else:
                        executa = True      
                except:
                    executa = True

                if executa:

                    dia    ='2nd tue'
                    hora   = 18
                    minuto = 18

                    msg = ('*** Agendamento inicial '+id_2+', rodando '+dia+', às '+str(hora)+':'+str(minuto)+' ***')
                    print(msg)
                    try:
                        sched.add_job(trigger='cron', id=id_2, func=chamadas_DW, day=dia, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
                        sched.start()
                    except:
                        sched.reschedule_job(id_2, trigger='cron', day=dia, hour=hora, minute=minuto)

                    registra_log_auto(current_user.id,None,'agc')         

            else:
                sistema.carga_auto = '0' 
                msg =  ('*** Jobs de carga serão CANCELADOS. Não haverá cargas automáticas. ***')
                print(msg)
                try:
                    sched.remove_job(id_1) 
                except:
                    print('*** Não há job '+id_1+' para cancelar. ***')  
                try:      
                    sched.remove_job(id_2)
                except:
                    print('*** Não há job '+id_2+' para cancelar. ***')
                registra_log_auto(current_user.id,None,'agx')    


            registra_log_auto(current_user.id,None,'ver')

            flash('Dados gerais do sistema atualizados!','sucesso')

            return redirect(url_for('core.inicio'))

        # traz a versão atual
        elif request.method == 'GET':

            form.ver.data                   = users[0].sversion
            form.nome_sistema.data          = sistema.nome_sistema
            form.descritivo.data            = sistema.descritivo
            form.funcionalidade_conv.data   = sistema.funcionalidade_conv
            form.funcionalidade_acordo.data = sistema.funcionalidade_acordo
            form.funcionalidade_instru.data = sistema.funcionalidade_instru
            form.cod_inst.data              = inst.cod_inst
            form.carga_auto.data            = sistema.carga_auto

        return render_template('admin_reg_ver.html', title='Update', form=form)


# Lista dos usuários vista pelo admin

@users.route('/admin_view_users')
@login_required

def admin_view_users():
    """+--------------------------------------------------------------------------------------+
       |Mostra lista dos usuários cadastrados.                                                |
       |Visto somente por admin.                                                              |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)
    else:
        users = User.query.order_by(User.id).all()
        return render_template('admin_view_users.html', users=users)

#
## alterações em users pelo admin

@users.route("/<int:user_id>/admin_update_user", methods=['GET', 'POST'])
@login_required
def admin_update_user(user_id):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite ao admin atualizar dados de um user.                                                  |
    |                                                                                              |
    |Recebe o id do user como parâmetro.                                                           |
    +----------------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':

        abort(403)

    else:

        user = User.query.get_or_404(user_id)
        sistema = Sistema.query.first()

        coords = db.session.query(Coords.sigla)\
                          .order_by(Coords.sigla).all()
        lista_coords = [(c[0],c[0]) for c in coords]
        lista_coords.insert(0,('',''))

        form = AdminForm()

        form.coord.choices = lista_coords

        if form.validate_on_submit():

            user.coord = form.coord.data

            if form.despacha0.data:
                user.despacha0 = 1
            else: 
                user.despacha0 = 0
            if form.despacha.data:
                user.despacha = 1
            else: 
                user.despacha = 0
            if form.despacha2.data:
                user.despacha2 = 1
            else: 
                user.despacha2 = 0      

            if form.ativo.data:
                user.ativo = 1
            else: 
                user.ativo = 0      

            user.role        = form.role.data
            user.cargo_func  = form.cargo_func.data

            if sistema.funcionalidade_conv == 1:
                user.trab_conv   = int(form.trab_conv.data)
            if sistema.funcionalidade_acordo == 1:
                user.trab_acordo = int(form.trab_acordo.data)
            if sistema.funcionalidade_instru == 1:
                user.trab_instru = int(form.trab_instru.data)

            db.session.commit()

            registra_log_auto(current_user.id,None,'adm')

            flash('Usuário atualizado!','sucesso')

            return redirect(url_for('users.admin_view_users'))

        # traz a informação atual do usuário
        elif request.method == 'GET':

            form.coord.data       = user.coord
            form.despacha0.data   = user.despacha0
            form.despacha.data    = user.despacha
            form.despacha2.data   = user.despacha2
            form.role.data        = user.role
            form.cargo_func.data  = user.cargo_func
            form.ativo.data       = user.ativo
            form.trab_conv.data   = user.trab_conv
            form.trab_acordo.data = user.trab_acordo
            form.trab_instru.data = user.trab_instru

        return render_template('admin_update_user.html', title='Update', name=user.username,
                               form=form)



# Lista unidades

@users.route('/admin_view_coords')
@login_required

def admin_view_coords():
    """+--------------------------------------------------------------------------------------+
       |Mostra lista das unidades cadastratas.                                                |
       |Visto somente por admin.                                                              |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)
    else:
        coords = db.session.query(Coords).order_by(Coords.sigla).all()
        return render_template('admin_view_coords.html', coords=coords)

## inserção de nova unidade pelo admin

@users.route("/admin_insere_coord", methods=['GET', 'POST'])
@login_required
def admin_insere_coord():
    """
    +----------------------------------------------------------------------------------------------+
    |Permite ao admin inserir nova unidade no sitema.                                              |
    |                                                                                              |
    +----------------------------------------------------------------------------------------------+
    """

    if current_user.role[0:5] != 'admin':

        abort(403)

    else:

        form = CoordForm()

        if form.validate_on_submit():

            print ('**** ','inserino nova coord')

            nova_coord = Coords(sigla = form.coord.data,
                                pai   = form.pai.data)
            db.session.add(nova_coord)
            db.session.commit()

            flash('Unidade '+form.coord.data+' inserida no sistema!','sucesso')

            return redirect(url_for('users.admin_view_coords'))

        return render_template('admin_update_coord.html', form=form)



## alterações em coords pelo admin

@users.route("/admin_update_coord/<int:id>", methods=['GET', 'POST'])
@login_required
def admin_update_coord(id):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite ao admin atualizar dados de coords.                                                   |
    |                                                                                              |
    +----------------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':

        abort(403)

    else:

        coord = Coords.query.get_or_404(id)

        form = CoordForm()

        if form.validate_on_submit():

            coord.sigla = form.coord.data
            coord.pai   = form.pai.data
            db.session.commit()

            flash('Unidade '+form.coord.data+' alterada!','sucesso')

            return redirect(url_for('users.admin_view_coords'))

        elif request.method == 'GET':    

            form.coord.data  = coord.sigla
            form.pai.data    = coord.pai 

        return render_template('admin_update_coord.html', form=form)


#
# diário do usuário

@users.route("/<usu>/user_log", methods=['GET', 'POST'])
@login_required
def user_log (usu):
    """+--------------------------------------------------------------------------------------+
       |Mostra a atividade do usuário em função dos principais commits.                       |
       |                                                                                      |
       +--------------------------------------------------------------------------------------+
    """

    def is_integer(n):
        try:
            float(n)
        except ValueError:
            return False
        else:
            return float(n).is_integer()

    if usu == 'todos':
        user_id = '%'
    elif is_integer(usu) is True:
        user_id = usu
    else:
        user_id = current_user.id

    form = LogForm()
    form2 = LogFormMan()

    if form.validate_on_submit():

        data_ini = form.data_ini.data
        data_fim = form.data_fim.data
        log_part = form.log_part.data

        if user_id == '%':
            log = db.session.query(Log_Auto.id,
                                Log_Auto.data_hora,
                                Log_Auto.demanda_id,
                                Log_Auto.tipo_registro,
                                Log_Auto.atividade,
                                Log_Desc.desc_registro,
                                User.username,
                                Demanda.programa,
                                label('ativ_sigla',Plano_Trabalho.atividade_sigla),
                                Log_Auto.duracao)\
                            .outerjoin(Log_Desc, Log_Auto.tipo_registro == Log_Desc.tipo_registro)\
                            .join(User, Log_Auto.user_id == User.id)\
                            .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
                            .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
                            .filter(Log_Auto.data_hora >= datetime.combine(data_ini,time.min),
                                    Log_Auto.data_hora <= datetime.combine(data_fim,time.max),
                                    Log_Auto.tipo_registro.like('%'+log_part+'%'))\
                            .order_by(Log_Auto.id.desc())\
                            .subquery()

        else:
            log = db.session.query(Log_Auto.id,
                                Log_Auto.data_hora,
                                Log_Auto.demanda_id,
                                Log_Auto.tipo_registro,
                                Log_Auto.atividade,
                                Log_Desc.desc_registro,
                                User.username,
                                Demanda.programa,
                                label('ativ_sigla',Plano_Trabalho.atividade_sigla),
                                Log_Auto.duracao)\
                            .outerjoin(Log_Desc, Log_Auto.tipo_registro == Log_Desc.tipo_registro)\
                            .join(User, Log_Auto.user_id == User.id)\
                            .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
                            .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
                            .filter(Log_Auto.user_id == user_id,
                                    Log_Auto.data_hora >= datetime.combine(data_ini,time.min),
                                    Log_Auto.data_hora <= datetime.combine(data_fim,time.max),
                                    Log_Auto.tipo_registro.like('%'+log_part+'%'))\
                            .order_by(Log_Auto.id.desc())\
                            .subquery()


        atividades = db.session.query(log,
                                      Plano_Trabalho.atividade_sigla)\
                               .outerjoin(Plano_Trabalho, Plano_Trabalho.id == log.c.programa)\
                               .order_by(log.c.id.desc())\
                               .all()

        # cria lista com ocorrências de tipo de registro

        l_log = [entrada.desc_registro for entrada in atividades]

        # conta entradas no log por tipo de registro, gerando um dicionário classificado

        agregado = {k: v for k, v in sorted(Counter(l_log).items(), key=lambda item: item[1])}

        return render_template('user_log.html', log=log, atividades = atividades, name=current_user.username,
                               form=form, usu=usu, agregado=agregado)


    # traz a log das últimas 24 horas e registra entrada manual de log, se for o caso.
    else:

        if user_id == '%':
            log = db.session.query(Log_Auto.id,
                                Log_Auto.data_hora,
                                Log_Auto.demanda_id,
                                Log_Auto.tipo_registro,
                                Log_Auto.atividade,
                                Log_Desc.desc_registro,
                                User.username,
                                Demanda.programa,
                                label('ativ_sigla',Plano_Trabalho.atividade_sigla),
                                Log_Auto.duracao)\
                            .outerjoin(Log_Desc, Log_Auto.tipo_registro == Log_Desc.tipo_registro)\
                            .join(User, Log_Auto.user_id == User.id)\
                            .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
                            .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
                            .filter(Log_Auto.data_hora >= (datetime.now()-timedelta(days=1)))\
                            .order_by(Log_Auto.id.desc())\
                            .subquery()
        else:
            log = db.session.query(Log_Auto.id,
                                Log_Auto.data_hora,
                                Log_Auto.demanda_id,
                                Log_Auto.tipo_registro,
                                Log_Auto.atividade,
                                Log_Desc.desc_registro,
                                User.username,
                                Demanda.programa,
                                label('ativ_sigla',Plano_Trabalho.atividade_sigla),
                                Log_Auto.duracao)\
                            .outerjoin(Log_Desc, Log_Auto.tipo_registro == Log_Desc.tipo_registro)\
                            .join(User, Log_Auto.user_id == User.id)\
                            .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
                            .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
                            .filter(Log_Auto.user_id == user_id,
                                    Log_Auto.data_hora >= (datetime.now()-timedelta(days=1)))\
                            .order_by(Log_Auto.id.desc())\
                            .subquery()


        atividades = db.session.query(log,
                                      Plano_Trabalho.atividade_sigla)\
                               .outerjoin(Plano_Trabalho, Plano_Trabalho.id == log.c.programa)\
                               .order_by(log.c.id.desc())\
                               .all()

        # cria lista com ocorrências de tipo de registro

        l_log = [entrada.desc_registro for entrada in atividades]

        # conta entradas no log por tipo de registro, gerando um dicionário classificado

        agregado = {k: v for k, v in sorted(Counter(l_log).items(), key=lambda item: item[1])}


        return render_template('user_log.html', log=log, atividades=atividades, name=current_user.username,
                           form=form, form2=form2, usu=usu, agregado=agregado)

#
# registro de observações do usuário no log

@users.route("/user_obs", methods=['GET','POST'])
@login_required
def user_obs():
    """+--------------------------------------------------------------------------------------+
       |Permite o registro de observação do usário no log.                                    |
       |                                                                                      |
       +--------------------------------------------------------------------------------------+
    """

    form = LogFormMan()

    if form.validate_on_submit():

        if form.entrada_log.data != '':

            # registra_log_auto(current_user.id,None,'man: '+form.entrada_log.data)
            reg_log = Log_Auto(data_hora     = datetime.now(),
                               user_id       = current_user.id,
                               demanda_id    = None,
                               tipo_registro = 'man: '+form.entrada_log.data,
                               atividade     = form.atividade.data,
                               duracao       = form.duracao.data)
            db.session.add(reg_log)
            db.session.commit()

            form.entrada_log.data = ''

        return redirect(url_for('users.user_log',usu='*'))

    form.duracao.data = 5

    return render_template('user_obs.html', form=form)

## exibe as últimas mensagens relevantes recebidas pelo usuário

@users.route("/user_msgs_recebidas")
@login_required
def user_msgs_recebidas():
    """+--------------------------------------------------------------------------------------+
       |Monstra as mensagens relevantes e mais recentes recebidas pelo usuário.               |
       +--------------------------------------------------------------------------------------+
    """

    hoje = date.today()

    deleta_msgs = db.session.query(Msgs_Recebidas).filter(Msgs_Recebidas.data_hora < (hoje - timedelta(days=30))).delete()
    db.session.commit()

    msgs = db.session.query(Msgs_Recebidas).filter(Msgs_Recebidas.user_id == current_user.id).order_by(Msgs_Recebidas.data_hora.desc()).all()


    return render_template('user_msgs_recebidas.html', msgs = msgs)


#
# gerar relatório de atividades

@users.route("/user_rel", methods=['GET','POST'])
@login_required
def user_rel():
    """+--------------------------------------------------------------------------------------+
       |Permite gerar html do relatório de atividades no período informado.                   |
       |                                                                                      |
       +--------------------------------------------------------------------------------------+
    """

    form = RelForm()

    if form.validate_on_submit():

        # levanta dados do plano de Trabalho

        atividades_1 = db.session.query(Plano_Trabalho.id,
                                        Plano_Trabalho.atividade_sigla,
                                        Plano_Trabalho.atividade_desc,
                                        Plano_Trabalho.natureza,
                                        Plano_Trabalho.meta)\
                                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                        .filter(Ativ_Usu.user_id == current_user.id, Ativ_Usu.nivel == 'Titular')\
                                        .order_by(Plano_Trabalho.natureza,Plano_Trabalho.atividade_sigla).all()

        quantidade_1 = len(atividades_1)

        carga_1 = db.session.query(label('total',func.sum(Plano_Trabalho.meta)))\
                            .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                            .filter(Ativ_Usu.user_id == current_user.id, Ativ_Usu.nivel == 'Titular').all()

        atividades_2 = db.session.query(Plano_Trabalho.id,
                                        Plano_Trabalho.atividade_sigla,
                                        Plano_Trabalho.atividade_desc,
                                        Plano_Trabalho.natureza,
                                        Plano_Trabalho.meta)\
                                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                        .filter(Ativ_Usu.user_id == current_user.id, Ativ_Usu.nivel == 'Suplente')\
                                        .order_by(Plano_Trabalho.natureza,Plano_Trabalho.atividade_sigla).all()

        quantidade_2 = len(atividades_2)

        carga_2 = db.session.query(label('total',func.sum(Plano_Trabalho.meta)))\
                            .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                            .filter(Ativ_Usu.user_id == current_user.id, Ativ_Usu.nivel == 'Suplente').all()


        # levanta dados de ações executadas

        coordenador = db.session.query(User.username,
                                       User.cargo_func,
                                       User.email)\
                                .filter(User.cargo_func == 'Coordenador(a)', User.ativo == 1, User.coord == current_user.coord).first()

        coordenador_geral = db.session.query(User.username,
                                             User.cargo_func,
                                             User.email)\
                                       .filter(User.cargo_func == 'Coordenador(a)-Geral').first()

        data_ini = form.data_ini.data
        data_fim = form.data_fim.data

        log = db.session.query(Log_Auto.id,
                               Log_Auto.data_hora,
                               Log_Auto.demanda_id,
                               Log_Auto.tipo_registro,
                               Log_Auto.atividade,
                               Log_Desc.desc_registro,
                               User.username,
                               Demanda.programa,
                               Demanda.sei,
                               Demanda.conclu,
                               label('ativ_sigla',Plano_Trabalho.atividade_sigla),
                               Log_Auto.duracao)\
                        .outerjoin(Log_Desc, Log_Desc.tipo_registro == Log_Auto.tipo_registro)\
                        .join(User, User.id == Log_Auto.user_id)\
                        .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
                        .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
                        .filter(Log_Auto.user_id == current_user.id,
                                Log_Auto.data_hora >= datetime.combine(data_ini,time.min),
                                Log_Auto.data_hora <= datetime.combine(data_fim,time.max))\
                        .subquery()

        atividades = db.session.query(log,
                                      Plano_Trabalho.atividade_sigla)\
                               .outerjoin(Plano_Trabalho, Plano_Trabalho.id == log.c.programa)\
                               .all()

        registra_log_auto(current_user.id,None,'rel')

        return render_template('form_atividades.html', log=log, atividades = atividades,
                                atividades_1=atividades_1, atividades_2=atividades_2,
                                quantidade_1=quantidade_1, quantidade_2=quantidade_2,
                                carga_1=carga_1[0][0], carga_2=carga_2[0][0],
                                data_ini=data_ini.strftime('%x'), data_fim=data_fim.strftime('%x'),
                                coordenador=coordenador, coordenador_geral=coordenador_geral)

    return render_template('user_inf_datas.html', form=form)

#
## lista usuários para atribuir atividades

@users.route('/coord_view_users')
@login_required

def coord_view_users():
    """+--------------------------------------------------------------------------------------+
       |Mostra lista dos usuários cadastrados para o coord atribuir atividades.               |
       |Visto somente por coord.                                                              |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.despacha == 1 or current_user.despacha0 == 1 or current_user.role[0:5] == "admin":

        users = User.query.order_by(User.id).filter(User.coord == current_user.coord, User.ativo == 1).all()
        return render_template('coord_view_users.html', users=users)

    else:
        abort(403)

    return redirect(url_for('core.inicio'))

#


## registro de atividades para um usuário

@users.route("/<int:user_id>/ativ_usu", methods=['GET', 'POST'])
@login_required
def ativ_usu(user_id):
    """
    +----------------------------------------------------------------------------------------------+
    |Permite ao chefe registrar atividades para um user.                                           |
    |                                                                                              |
    |Recebe o id do user como parâmetro.                                                           |
    +----------------------------------------------------------------------------------------------+
    """
    if current_user.despacha == 1 or current_user.despacha0 == 1 or current_user.role[0:5] == "admin":

        user = User.query.get_or_404(user_id)

        ativ_usu = db.session.query(Ativ_Usu.atividade_id, Ativ_Usu.nivel, Ativ_Usu.id)\
                             .filter(Ativ_Usu.user_id == user.id)\
                             .order_by(Ativ_Usu.nivel.desc()).all()

        l_ativ_usu = [a[0] for a in ativ_usu]

        atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                          .order_by(Plano_Trabalho.atividade_sigla).all()
        lista_atividades = [(str(a[1]),a[0]) for a in atividades]
        lista_atividades.insert(0,('',''))

        form = AtivUsu()

        form.atividade.choices = lista_atividades

        if form.validate_on_submit():

            if int(form.atividade.data) in l_ativ_usu:
                flash('Usuário já tem esta atividade!','erro')
            else:
                ativ_para_user = Ativ_Usu(atividade_id = form.atividade.data,
                                          user_id      = user.id,
                                          nivel        = form.nivel_resp.data)
                db.session.add(ativ_para_user)

                db.session.commit()

                registra_log_auto(current_user.id,None,'aus')

                flash('Atividade atribuída ao usuário com sucesso!','sucesso')


            return redirect(url_for('users.ativ_usu', user_id=user.id))

        # traz as atividades atuais do usuário
        elif request.method == 'GET':

            l_ativ_usu = []
            for ativ in ativ_usu:
                atividade_usu = db.session.query(Plano_Trabalho.atividade_sigla)\
                                  .filter(Plano_Trabalho.id == ativ.atividade_id).first()
                l_ativ_usu.append([atividade_usu.atividade_sigla, ativ.nivel, ativ.id])

        return render_template('coord_update_user.html', user_id=user.id, name=user.username, atividades_usu=l_ativ_usu, form=form)

    else:
        abort(403)
#
#removendo uma atividade de um usuário

@users.route('/<int:id>/<int:user_id>/delete_atividade_usu', methods=['GET','POST'])
@login_required
def delete_atividade_usu(id,user_id):
    """+----------------------------------------------------------------------+
       |Permite que o chefe remova uma atividade atribuida a um usuário.      |
       |                                                                      |
       |Recebe o ID da atividade como parâmetro.                              |
       +----------------------------------------------------------------------+

    """
    if current_user.ativo == 0 or (current_user.despacha0 == 0 and current_user.despacha == 0 and current_user.despacha2 == 0):
        abort(403)

    atividade = Ativ_Usu.query.get_or_404(id)

    db.session.delete(atividade)
    db.session.commit()

    registra_log_auto(current_user.id,None,'xus')

    flash ('Atividade excluída da lista do usuário!','sucesso')

    return redirect(url_for('users.ativ_usu', user_id=user_id))




# Lista tipos de log (sem menu)

@users.route('/admin_tipos_log')
@login_required

def admin_tipos_log():
    """+--------------------------------------------------------------------------------------+
       |Mostra lista dos tipos de de log.                                                     |
       |Visto somente por admin.                                                              |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)

    tipos_log = db.session.query(Log_Desc).order_by(Log_Desc.tipo_registro).all()

    return render_template('admin_tipos_log.html', tipos_log=tipos_log)

## inserção de novo tipo de log pelo admin

@users.route("/admin_insere_tipo_log", methods=['GET', 'POST'])
@login_required
def admin_insere_tipo_log():
    """
    +----------------------------------------------------------------------------------------------+
    |Permite ao admin inserir novo tipo de log no sitema.                                          |
    |                                                                                              |
    +----------------------------------------------------------------------------------------------+
    """

    if current_user.role[0:5] != 'admin':

        abort(403)

    form = TipoLogForm()

    if form.validate_on_submit():

        novo_tipo = Log_Desc(tipo_registro = form.tipo.data,
                             desc_registro = form.desc.data)
        db.session.add(novo_tipo)
        db.session.commit()

        flash('Tipo '+form.tipo.data+' inserido no sistema!','sucesso')

        return redirect(url_for('users.admin_tipos_log'))

    return render_template('admin_insere_tipo_log.html', form=form)


