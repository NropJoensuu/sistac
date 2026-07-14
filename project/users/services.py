"""
.. topic:: Users (services) — Autenticação, registro e senha

    Camada de regra de negócio do grupo de autenticação do módulo de
    usuários: registro, confirmação de e-mail, login, logout e troca
    de senha. Sem dependência de objetos de request/response do Flask
    (redirect, flash) — as rotas (views.py) decidem o que fazer com o
    resultado retornado por estas funções.

    Cada função de fluxo (registrar_usuario, confirmar_email, etc.)
    retorna um status textual em vez de manipular a resposta HTTP
    diretamente, permitindo que a view decida a mensagem exibida ao
    usuário e para onde redirecionar.
"""

from threading import Thread
from datetime import datetime

from itsdangerous import URLSafeTimedSerializer
from flask import url_for, render_template
from flask_mail import Message
from werkzeug.security import generate_password_hash
from sqlalchemy import func

from project import db, mail, app
from project.models import User, Coords, Sistema
from project.demandas.views import registra_log_auto


# --- envio de e-mail ---

def send_async_email(msg):
    """Executa o envio de e-mails de forma assíncrona."""
    with app.app_context():
        mail.send(msg)


def send_email(subject, recipients, text_body, html_body):
    """Envia e-mails em uma thread separada."""
    msg = Message(subject, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    thr = Thread(target=send_async_email, args=[msg])
    thr.start()


def send_confirmation_email(user_email):
    """Prepara e envia o e-mail de confirmação de registro."""
    confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    confirm_url = url_for(
        'users.confirm_email',
        token=confirm_serializer.dumps(user_email, salt='email-confirmation-salt'),
        _external=True)

    html = render_template('email_confirmation.html', confirm_url=confirm_url)

    send_email('Confirme seu endereço de e-mail', [user_email], '', html)


def send_password_reset_email(user_email):
    """Prepara e envia o e-mail com token de troca de senha."""
    password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    password_reset_url = url_for(
        'users.reset_with_token',
        token=password_reset_serializer.dumps(user_email, salt='password-reset-salt'),
        _external=True)

    html = render_template('email_senha_atualiza.html', password_reset_url=password_reset_url)

    send_email('Atualização de senha solicitada', [user_email], '', html)


# --- registro ---

def registrar_usuario(email, username, password, coord, despacha0, despacha, despacha2):
    """
    Cria um novo usuário, definindo seu papel (admin, se for o primeiro
    usuário do sistema), garante o registro da coordenação informada e
    dispara o e-mail de confirmação. Retorna o usuário criado.
    """
    qtd_users = db.session.query(func.count(User.id)).first()

    if qtd_users[0] != 0:
        version = db.session.query(User.sversion).first()
        role_user = 'user'
    else:
        version = [1]
        role_user = 'admin'

    trab_conv = db.session.query(Sistema.funcionalidade_conv).first()
    trab_acordo = db.session.query(Sistema.funcionalidade_acordo).first()
    trab_instru = db.session.query(Sistema.funcionalidade_instru).first()

    user = User(
        email=email,
        username=username,
        plaintext_password=password,
        despacha0=1 if despacha0 else 0,
        despacha=1 if despacha else 0,
        despacha2=1 if despacha2 else 0,
        coord=coord,
        role=role_user,
        email_confirmation_sent_on=datetime.now(),
        ativo=0,
        sversion=version[0],
        cargo_func='a definir',
        trab_conv=trab_conv[0],
        trab_acordo=trab_acordo[0],
        trab_instru=trab_instru[0],
    )

    db.session.add(user)
    db.session.commit()

    last_id = db.session.query(User.id).order_by(User.id.desc()).first()
    registra_log_auto(last_id[0], None, 'usu')

    coords = db.session.query(Coords.sigla).all()
    if (coord,) not in coords:
        nova_coord = Coords(sigla=coord)
        db.session.add(nova_coord)
        db.session.commit()

    send_confirmation_email(user.email)

    return user


def confirmar_email(token):
    """
    Valida o token de confirmação de e-mail e marca o usuário como
    confirmado.

    Retorna uma tupla (status, user), onde status é um dos:
    'invalido', 'ja_confirmado', 'confirmado'.
    """
    try:
        confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = confirm_serializer.loads(token, salt='email-confirmation-salt', max_age=3600)
    except Exception:
        return 'invalido', None

    user = User.query.filter_by(email=email).first()

    if user.email_confirmed == 1:
        return 'ja_confirmado', user

    user.email_confirmed = 1
    user.email_confirmed_on = datetime.now()
    db.session.commit()

    return 'confirmado', user


# --- troca de senha ---

def solicitar_reset_senha(email):
    """
    Envia o e-mail de troca de senha, se o e-mail existir e estiver
    confirmado.

    Retorna um dos status: 'nao_encontrado', 'nao_confirmado', 'enviado'.
    """
    user = User.query.filter_by(email=email).first()

    if user is None:
        return 'nao_encontrado'

    if user.email_confirmed != 1:
        return 'nao_confirmado'

    send_password_reset_email(user.email)
    return 'enviado'


def redefinir_senha_com_token(token, nova_senha):
    """
    Valida o token de troca de senha e define a nova senha.

    Retorna uma tupla (status, user), onde status é um dos:
    'token_invalido', 'usuario_invalido', 'atualizada'.
    """
    try:
        password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = password_reset_serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        return 'token_invalido', None

    user = User.query.filter_by(email=email).first()
    if user is None:
        return 'usuario_invalido', None

    user.password_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
    db.session.commit()

    registra_log_auto(user.id, None, 'sen')

    return 'atualizada', user


def trocar_senha(usuario, senha_atual, nova_senha):
    """
    Troca a senha do usuário logado, validando a senha atual.

    Retorna um dos status: 'inativo', 'senha_incorreta', 'trocada'.
    """
    if usuario.ativo != 1:
        return 'inativo'

    if not usuario.check_password(senha_atual):
        return 'senha_incorreta'

    usuario.password_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
    db.session.commit()

    registra_log_auto(usuario.id, None, 'sen')

    return 'trocada'


# --- login ---

def autenticar(email, senha):
    """
    Verifica as credenciais de login e, se corretas, atualiza os
    campos de último acesso.

    Retorna uma tupla (status, user), onde status é um dos:
    'nao_encontrado', 'senha_incorreta', 'nao_confirmado', 'autenticado'.
    """
    user = User.query.filter_by(email=email).first()

    if user is None:
        return 'nao_encontrado', None

    if not user.check_password(senha):
        return 'senha_incorreta', None

    if user.email_confirmed != 1:
        return 'nao_confirmado', None

    user.last_logged_in = user.current_logged_in
    user.current_logged_in = datetime.now()
    db.session.commit()

    return 'autenticado', user
