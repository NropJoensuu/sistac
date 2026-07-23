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

from flask import render_template, url_for, flash, redirect, request, Blueprint, abort
from flask_login import login_user, current_user, logout_user, login_required
from wtforms import ValidationError
from datetime import date

from project.users.forms import RegistrationForm, LoginForm, UpdateUserForm, EmailForm, PasswordForm, AdminForm,\
                                LogForm, LogFormMan, VerForm, RelForm, AtivUsu, TrocaPasswordForm, CoordForm, TipoLogForm
from project.users import services
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

        services.atualizar_perfil(current_user, form.username.data, form.email.data)

        flash('Usuário atualizado!','sucesso')
        return redirect (url_for('users.account'))

    elif request.method == "GET":

        form.username.data = current_user.username
        form.email.data = current_user.email

        stats = services.calcular_estatisticas_conta(current_user.id, hoje)

    return render_template('account.html', form=form, **stats)

# lista das demandas de um usuário

@users.route('/user_posts/<filtro>/<username>')
def user_posts (username,filtro):
    """+--------------------------------------------------------------------------------------+
       |Mostra as demandas de um usuário quando seu nome é selecionado em uma tela de         |
       |consulta de demandas.                                                                 |
       |Recebe o nome do usuário como parâmetro e o tipo de consulta (filtro)                 |
       +--------------------------------------------------------------------------------------+
    """

    dados = services.listar_demandas_usuario(username, filtro)

    return render_template('user_demandas.html', **dados)

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

    dados = services.plano_trabalho_usuario(user_id)

    return render_template('user_pt.html', **dados)

# admim registra nova versão do sistema no banco de dadosSEI e outras condições

@users.route('/admin_reg_ver', methods=['GET', 'POST'])
@login_required

def admin_reg_ver():
    """+--------------------------------------------------------------------------------------+
       |O admin master atualiza no banco de dados a versão do sistema após uma               |
       |atualização e outros parâmetros do sistema.                                           |
       +--------------------------------------------------------------------------------------+
    """
    if current_user.role != 'admin_master':
        abort(403)
    else:
        users, sistema, inst = services.dados_config_sistema()

        form = VerForm()

        if form.validate_on_submit():

            services.atualizar_config_sistema(
                ver=form.ver.data,
                nome_sistema=form.nome_sistema.data,
                descritivo=form.descritivo.data,
                funcionalidade_conv=form.funcionalidade_conv.data,
                funcionalidade_acordo=form.funcionalidade_acordo.data,
                funcionalidade_instru=form.funcionalidade_instru.data,
                cod_inst=form.cod_inst.data,
                carga_auto=form.carga_auto.data,
                usuario_id=current_user.id,
            )

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
        users = services.listar_usuarios()
        return render_template('admin_view_users.html', users=users)

#
## confirma manualmente o e-mail de um usuário (ex: link de confirmação expirado)

@users.route('/<int:user_id>/admin_confirma_email', methods=['GET', 'POST'])
@login_required
def admin_confirma_email(user_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o admin confirme manualmente o e-mail de um usuário.                        |
    |Útil quando o link de confirmação expirou e a pessoa não consegue se cadastrar de novo   |
    |(o e-mail já está em uso por um cadastro pendente).                                      |
    |                                                                                        |
    |Recebe o ID do usuário como parâmetro.                                                  |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)

    services.confirmar_email_manualmente(user_id, current_user.id)

    flash('E-mail confirmado manualmente! O usuário já pode fazer login.', 'sucesso')

    return redirect(url_for('users.admin_view_users'))

## reenvia o e-mail de confirmação de cadastro

@users.route('/<int:user_id>/admin_reenvia_confirmacao', methods=['GET', 'POST'])
@login_required
def admin_reenvia_confirmacao(user_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o admin dispare novamente o e-mail de confirmação de cadastro de um usuário.|
    |                                                                                        |
    |Recebe o ID do usuário como parâmetro.                                                  |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)

    services.reenviar_confirmacao_email(user_id, current_user.id)

    flash('E-mail de confirmação reenviado!', 'sucesso')

    return redirect(url_for('users.admin_view_users'))

## exclui o cadastro de um usuário (restrito a cadastros ainda não confirmados)

@users.route('/<int:user_id>/admin_exclui_usuario', methods=['GET', 'POST'])
@login_required
def admin_exclui_usuario(user_id):
    """
    +---------------------------------------------------------------------------------------+
    |Permite que o admin exclua o cadastro de um usuário — restrito a cadastros com e-mail   |
    |ainda não confirmado, para não apagar contas ativas com dados/histórico já vinculados.  |
    |                                                                                        |
    |Recebe o ID do usuário como parâmetro.                                                  |
    +---------------------------------------------------------------------------------------+
    """
    if current_user.role[0:5] != 'admin':
        abort(403)

    if user_id == current_user.id:
        flash('Você não pode excluir seu próprio cadastro por aqui.', 'erro')
        return redirect(url_for('users.admin_view_users'))

    status = services.excluir_usuario_admin(user_id, current_user.id)

    if status == 'excluido':
        flash('Cadastro excluído!', 'sucesso')
    else:
        flash('Só é possível excluir cadastros com e-mail ainda não confirmado.', 'erro')

    return redirect(url_for('users.admin_view_users'))

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

        user = services.buscar_usuario(user_id)

        form = AdminForm()

        form.coord.choices = services.coords_choices()

        if current_user.role == 'admin_master':
            form.role.choices = [('user','user'), ('admin','admin'), ('admin_master','admin master')]
        else:
            # admin comum não concede nem remove papel de admin — o campo
            # fica travado no papel atual do usuário
            form.role.choices = [(user.role, user.role)]

        if form.validate_on_submit():

            usuario_atualizado, erro = services.atualizar_usuario_admin(
                user_id=user_id,
                coord=form.coord.data,
                despacha0=form.despacha0.data,
                despacha=form.despacha.data,
                despacha2=form.despacha2.data,
                ativo=form.ativo.data,
                role=form.role.data,
                cargo_func=form.cargo_func.data,
                trab_conv=form.trab_conv.data,
                trab_acordo=form.trab_acordo.data,
                trab_instru=form.trab_instru.data,
                admin_atual=current_user,
            )

            if erro:
                flash(erro, 'erro')
                return redirect(url_for('users.admin_update_user', user_id=user_id))

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
                               form=form, sistema=services.dados_sistema())



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
        coords = services.listar_coords()
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

            services.criar_coord(form.coord.data, form.pai.data)

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

        coord = services.buscar_coord(id)

        form = CoordForm()

        if form.validate_on_submit():

            services.atualizar_coord(id, form.coord.data, form.pai.data)

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

    user_id = services.resolver_usuario_alvo_log(usu, current_user.id)

    form = LogForm()
    form2 = LogFormMan()

    if form.validate_on_submit():

        log, atividades, agregado = services.log_filtrado(
            user_id, form.data_ini.data, form.data_fim.data, form.log_part.data)

        return render_template('user_log.html', log=log, atividades = atividades, name=current_user.username,
                               form=form, usu=usu, agregado=agregado)

    # traz a log das últimas 24 horas e registra entrada manual de log, se for o caso.
    else:

        log, atividades, agregado = services.log_ultimas_24h(user_id)

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

        services.registrar_observacao_log(
            current_user.id, form.atividade.data, form.entrada_log.data, form.duracao.data)

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

    msgs = services.mensagens_recebidas(current_user.id)

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

        dados = services.gerar_relatorio_atividades(current_user, form.data_ini.data, form.data_fim.data)

        return render_template('form_atividades.html', **dados)

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

        users = services.listar_usuarios_coordenacao(current_user.coord)
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

        user = services.buscar_usuario(user_id)

        l_ativ_usu = [a[0] for a in services.atividades_atuais_usuario(user.id)]

        form = AtivUsu()
        form.atividade.choices = services.atividades_choices()

        if form.validate_on_submit():

            status = services.atribuir_atividade(user.id, form.atividade.data, form.nivel_resp.data, current_user.id)

            if status == 'ja_possui':
                flash('Usuário já tem esta atividade!','erro')
            else:
                flash('Atividade atribuída ao usuário com sucesso!','sucesso')

            return redirect(url_for('users.ativ_usu', user_id=user.id))

        # traz as atividades atuais do usuário
        elif request.method == 'GET':
            l_ativ_usu = services.atividades_atuais_formatadas(user.id)

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

    services.excluir_atividade_usuario(id, current_user.id)

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

    tipos_log = services.listar_tipos_log()

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

        services.criar_tipo_log(form.tipo.data, form.desc.data)

        flash('Tipo '+form.tipo.data+' inserido no sistema!','sucesso')

        return redirect(url_for('users.admin_tipos_log'))

    return render_template('admin_insere_tipo_log.html', form=form)