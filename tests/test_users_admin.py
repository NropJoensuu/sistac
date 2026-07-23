# test_users_admin.py
#
# Testes de characterization do grupo Administração do módulo users.
# Cobre um bug real encontrado durante a refatoração: o campo
# 'funcionalidade_acordo' do Sistema nunca podia ser desativado pelo
# admin (erro de copiar-colar fazia o "else" gravar '1' em vez de '0').

import pytest
from datetime import date
from project import db
from project.models import User, Sistema, RefSICONV


@pytest.fixture()
def usuario_admin(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.admin@teste.com').first()
        if user is None:
            user = User(
                email='teste.admin@teste.com', username='usuarioadminteste',
                plaintext_password='senha123', coord='TESTE', role='admin',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()

        if not RefSICONV.query.first():
            db.session.add(RefSICONV(data_ref=date.today(), cod_inst='000', data_cha_dw=date.today()))
            db.session.commit()

        return user.id


@pytest.fixture()
def usuario_comum_para_admin(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.naoadmin@teste.com').first()
        if user is None:
            user = User(
                email='teste.naoadmin@teste.com', username='usuarionaoadminteste',
                plaintext_password='senha123', coord='TESTE', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


@pytest.fixture()
def usuario_admin_master(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.adminmaster@teste.com').first()
        if user is None:
            user = User(
                email='teste.adminmaster@teste.com', username='usuarioadminmasterfixtureteste',
                plaintext_password='senha123', coord='COPES', role='admin_master',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()

        if not RefSICONV.query.first():
            db.session.add(RefSICONV(data_ref=date.today(), cod_inst='000', data_cha_dw=date.today()))
            db.session.commit()

        return user.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def test_admin_view_users_acessivel_por_admin(client, usuario_admin):
    _login(client, usuario_admin)
    resp = client.get("/admin_view_users")
    assert resp.status_code == 200


def test_admin_view_users_bloqueado_para_usuario_comum(client, usuario_comum_para_admin):
    _login(client, usuario_comum_para_admin)
    resp = client.get("/admin_view_users")
    assert resp.status_code == 403


def test_admin_reg_ver_bloqueado_para_admin_comum(client, usuario_admin):
    """Regressão da consolidação: admin_reg_ver passou a ser exclusivo do admin master."""
    _login(client, usuario_admin)
    resp = client.get("/admin_reg_ver")
    assert resp.status_code == 403


def test_funcionalidade_acordo_pode_ser_desativada(client, app, usuario_admin_master):
    """
    Regressão do bug: desmarcar 'funcionalidade_acordo' no formulário
    admin_reg_ver deve gravar '0', não '1'.
    """
    with app.app_context():
        sistema = Sistema.query.first()
        sistema.funcionalidade_acordo = '1'
        db.session.commit()

    _login(client, usuario_admin_master)
    resp = client.post("/admin_reg_ver", data={
        "ver": "5", "nome_sistema": "SISTAC", "descritivo": "teste", "cod_inst": "123",
    })
    assert resp.status_code == 302

    with app.app_context():
        sistema = Sistema.query.first()
        assert sistema.funcionalidade_acordo == 0
