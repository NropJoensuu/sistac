# test_users_admin_cadastro.py
#
# Testes da nova funcionalidade de gestão de cadastros pendentes pelo
# admin: confirmar e-mail manualmente, reenviar confirmação, e
# excluir cadastro (restrito a e-mails ainda não confirmados).
#
# Motivação real: um colega tentou se cadastrar em produção
# (sicopesii.cnpq.br), o link de confirmação expirou, e não havia
# como o admin resolver isso pela interface (nem confirmar, nem
# reenviar, nem excluir o cadastro para a pessoa tentar de novo).

from project import db
from project.models import User


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _admin(app):
    with app.app_context():
        admin = User.query.filter_by(email='admin@teste.com').first()
        if admin is None:
            admin = User(
                email='admin@teste.com', username='adminteste',
                plaintext_password='senha123', coord='DPI', role='admin',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=1, despacha=1, despacha2=1,
            )
            db.session.add(admin)
            db.session.commit()
        if admin.role != 'admin':
            admin.role = 'admin'
            db.session.commit()
        return admin.id


def _usuario_nao_confirmado(app, email, username):
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
            user.email_confirmed = 0
            db.session.add(user)
            db.session.commit()
        return user.id


def test_admin_confirma_email_libera_login(client, app):
    """O cenário real: e-mail expirado, admin confirma manualmente, usuário já pode logar."""
    admin_id = _admin(app)
    user_id = _usuario_nao_confirmado(app, 'teste.confirmaemailadmin@teste.com', 'usuarioconfirmaemailadminteste')
    _login(client, admin_id)

    resp = client.get(f"/{user_id}/admin_confirma_email")
    assert resp.status_code == 302

    with app.app_context():
        user = User.query.get(user_id)
        assert user.email_confirmed == 1


def test_admin_reenvia_confirmacao_responde_redirect(client, app):
    admin_id = _admin(app)
    user_id = _usuario_nao_confirmado(app, 'teste.reenviaconfadmin@teste.com', 'usuarioreenviaconfadminteste')
    _login(client, admin_id)

    resp = client.get(f"/{user_id}/admin_reenvia_confirmacao")
    assert resp.status_code == 302


def test_admin_nao_pode_excluir_a_si_mesmo(client, app):
    admin_id = _admin(app)
    _login(client, admin_id)

    resp = client.get(f"/{admin_id}/admin_exclui_usuario", follow_redirects=True)
    assert 'próprio cadastro'.encode() in resp.data


def test_admin_nao_pode_excluir_cadastro_confirmado(client, app):
    """Salvaguarda: exclusão só é permitida para cadastros com e-mail ainda não confirmado."""
    admin_id = _admin(app)
    user_id = _usuario_nao_confirmado(app, 'teste.jaconfirmado@teste.com', 'usuariojaconfirmadoteste')

    with app.app_context():
        user = User.query.get(user_id)
        user.email_confirmed = 1
        db.session.commit()

    _login(client, admin_id)
    resp = client.get(f"/{user_id}/admin_exclui_usuario", follow_redirects=True)

    assert 'ainda não confirmado'.encode() in resp.data
    with app.app_context():
        assert User.query.get(user_id) is not None


def test_admin_pode_excluir_cadastro_nao_confirmado(client, app):
    admin_id = _admin(app)
    user_id = _usuario_nao_confirmado(app, 'teste.excluinaoconf@teste.com', 'usuarioexcluinaoconfteste')
    _login(client, admin_id)

    resp = client.get(f"/{user_id}/admin_exclui_usuario", follow_redirects=True)

    assert 'Cadastro excluído'.encode() in resp.data
    with app.app_context():
        assert User.query.get(user_id) is None
