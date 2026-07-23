# test_users_hierarquia_admin.py
#
# Testes da restrição de hierarquia para admin comum: um admin só vê
# e edita usuários da própria coordenação (e suas unidades-filhas).
# Admin master continua sem restrição, vendo/editando qualquer
# usuário do sistema.

from project import db
from project.models import User, Coords
from project.users import services


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _unidades_teste(app):
    with app.app_context():
        for sigla in ['UNIDADEATESTE2', 'UNIDADEBTESTE2']:
            if not Coords.query.filter_by(sigla=sigla).first():
                db.session.add(Coords(sigla=sigla, pai=''))
        db.session.commit()


def _admin_master(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.hierarquiamaster@teste.com').first()
        if user is None:
            user = User(
                email='teste.hierarquiamaster@teste.com', username='usuariohierarquiamasterteste',
                plaintext_password='senha123', coord='COPES', role='admin_master',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _admin_unidade_a(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.adminunidadea@teste.com').first()
        if user is None:
            user = User(
                email='teste.adminunidadea@teste.com', username='usuarioadminunidadeateste',
                plaintext_password='senha123', coord='UNIDADEATESTE2', role='admin',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _usuario_unidade_b(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.usuariounidadeb@teste.com').first()
        if user is None:
            user = User(
                email='teste.usuariounidadeb@teste.com', username='usuariounidadebteste',
                plaintext_password='senha123', coord='UNIDADEBTESTE2', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def test_admin_comum_nao_ve_usuario_de_outra_unidade_na_listagem(client, app):
    _unidades_teste(app)
    admin_a_id = _admin_unidade_a(app)
    usuario_b_id = _usuario_unidade_b(app)

    _login(client, admin_a_id)
    resp = client.get("/admin_view_users")

    assert resp.status_code == 200
    assert 'teste.usuariounidadeb@teste.com'.encode() not in resp.data


def test_admin_comum_nao_edita_usuario_de_outra_unidade(client, app):
    _unidades_teste(app)
    admin_a_id = _admin_unidade_a(app)
    usuario_b_id = _usuario_unidade_b(app)

    _login(client, admin_a_id)
    resp = client.get(f"/{usuario_b_id}/admin_update_user")

    assert resp.status_code == 403


def test_admin_master_ve_e_edita_qualquer_usuario(client, app):
    """Regressão: admin master continua sem nenhuma restrição de hierarquia."""
    _unidades_teste(app)
    master_id = _admin_master(app)
    usuario_b_id = _usuario_unidade_b(app)

    _login(client, master_id)

    resp1 = client.get("/admin_view_users")
    assert 'teste.usuariounidadeb@teste.com'.encode() in resp1.data

    resp2 = client.get(f"/{usuario_b_id}/admin_update_user")
    assert resp2.status_code == 200


def test_usuario_visivel_para_considera_unidades_filhas(app):
    """A hierarquia deve incluir a própria coordenação do admin e suas unidades-filhas."""
    with app.app_context():
        if not Coords.query.filter_by(sigla='UNIDADEPAITESTE').first():
            db.session.add(Coords(sigla='UNIDADEPAITESTE', pai=''))
        if not Coords.query.filter_by(sigla='UNIDADEFILHATESTE').first():
            db.session.add(Coords(sigla='UNIDADEFILHATESTE', pai='UNIDADEPAITESTE'))
        db.session.commit()

        admin_pai = User.query.filter_by(email='teste.adminpai@teste.com').first()
        if admin_pai is None:
            admin_pai = User(
                email='teste.adminpai@teste.com', username='usuarioadminpaiteste',
                plaintext_password='senha123', coord='UNIDADEPAITESTE', role='admin',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(admin_pai)
            db.session.commit()

        usuario_filho = User.query.filter_by(email='teste.usuariofilho@teste.com').first()
        if usuario_filho is None:
            usuario_filho = User(
                email='teste.usuariofilho@teste.com', username='usuariofilhoteste',
                plaintext_password='senha123', coord='UNIDADEFILHATESTE', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(usuario_filho)
            db.session.commit()

        assert services.usuario_visivel_para(admin_pai, usuario_filho) is True
