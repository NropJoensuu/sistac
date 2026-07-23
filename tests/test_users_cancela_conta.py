# test_users_cancela_conta.py
#
# Testes da autoexclusão de conta: o usuário cancela a própria conta
# (desativa e anonimiza e-mail/nome, liberando o e-mail original para
# um novo cadastro no futuro). O histórico (demandas, log) permanece
# intacto, ainda vinculado ao mesmo ID.

from project import db
from project.models import User
from project.users import services


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def test_cancelar_propria_conta_anonimiza_e_desativa(app):
    with app.app_context():
        user_id = _usuario(app, 'teste.cancelaservico@teste.com', 'usuariocancelaservicoteste')
        user = User.query.get(user_id)

        services.cancelar_propria_conta(user)

        user_atualizado = User.query.get(user_id)
        assert user_atualizado.ativo == 0
        assert user_atualizado.email == 'cancelado_' + str(user_id) + '@sistac.local'
        assert user_atualizado.username == 'cancelado_' + str(user_id)


def test_email_original_fica_livre_apos_cancelamento(app):
    with app.app_context():
        email_original = 'teste.emailliberado@teste.com'
        user_id = _usuario(app, email_original, 'usuarioemailliberadoteste')
        user = User.query.get(user_id)

        services.cancelar_propria_conta(user)

        assert User.query.filter_by(email=email_original).first() is None


def test_cancela_conta_via_rota_desloga_o_usuario(client, app):
    user_id = _usuario(app, 'teste.cancelarota@teste.com', 'usuariocancelarotateste')
    _login(client, user_id)

    resp = client.post("/cancela_conta", follow_redirects=False)
    assert resp.status_code == 302

    # sessão encerrada: acessar uma rota protegida deve redirecionar para o login
    resp2 = client.get("/account", follow_redirects=False)
    assert resp2.status_code == 302


def test_cancela_conta_exige_login(client):
    resp = client.post("/cancela_conta", follow_redirects=False)
    assert resp.status_code == 302
