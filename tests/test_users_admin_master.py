# test_users_admin_master.py
#
# Testes da funcionalidade Admin Master: um papel acima do admin
# comum, que só pode ser atribuído (ou removido) por outro admin
# master, e somente a usuários da coordenação COPES. Admin master tem
# acesso exclusivo à tela "Dados gerais do sistema" (admin_reg_ver),
# que reúne configuração de versão, texto da página Sobre, e as
# funcionalidades do sistema (Convênios/Acordos/Instrumentos).

from project import db
from project.models import User
from project.users import services


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username, coord='COPES', role='admin'):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord=coord, role=role,
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        else:
            user.coord = coord
            user.role = role
            db.session.commit()
        return user.id


def test_admin_comum_nao_pode_promover_a_admin_master(app):
    """Regressão de segurança: só um admin master promove outro admin master."""
    with app.app_context():
        admin_comum_id = _usuario(app, 'teste.admincomum@teste.com', 'usuarioadmincomumteste', role='admin')
        alvo_id = _usuario(app, 'teste.alvopromocao@teste.com', 'usuarioalvopromocaoteste', role='admin')

        admin_comum = User.query.get(admin_comum_id)

        user, erro = services.atualizar_usuario_admin(
            user_id=alvo_id, coord='COPES', despacha0=0, despacha=0, despacha2=0, ativo=1,
            role='admin_master', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
            admin_atual=admin_comum,
        )

        assert erro is not None
        assert User.query.get(alvo_id).role == 'admin'


def test_admin_master_pode_promover_usuario_de_copes(app):
    with app.app_context():
        master_id = _usuario(app, 'teste.adminmaster@teste.com', 'usuarioadminmasterteste', coord='COPES', role='admin_master')
        alvo_id = _usuario(app, 'teste.alvocopes@teste.com', 'usuarioalvocopesteste', coord='COPES', role='admin')

        master = User.query.get(master_id)

        user, erro = services.atualizar_usuario_admin(
            user_id=alvo_id, coord='COPES', despacha0=0, despacha=0, despacha2=0, ativo=1,
            role='admin_master', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
            admin_atual=master,
        )

        assert erro is None
        assert User.query.get(alvo_id).role == 'admin_master'


def test_admin_master_nao_pode_promover_usuario_fora_de_copes(app):
    with app.app_context():
        master_id = _usuario(app, 'teste.adminmaster2@teste.com', 'usuarioadminmaster2teste', coord='COPES', role='admin_master')
        alvo_id = _usuario(app, 'teste.alvoforacopes@teste.com', 'usuarioalvoforacopesteste', coord='DPI', role='admin')

        master = User.query.get(master_id)

        user, erro = services.atualizar_usuario_admin(
            user_id=alvo_id, coord='DPI', despacha0=0, despacha=0, despacha2=0, ativo=1,
            role='admin_master', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
            admin_atual=master,
        )

        assert erro is not None
        assert User.query.get(alvo_id).role == 'admin'


def test_admin_reg_ver_bloqueado_para_admin_comum(client, app):
    """
    Regressão da consolidação: admin_reg_ver ('Dados gerais do
    sistema') passou a ser exclusivo do admin master — antes era
    aberto a qualquer admin.
    """
    user_id = _usuario(app, 'teste.regveradmincomum@teste.com', 'usuarioregveradmincomumteste', role='admin')
    _login(client, user_id)
    resp = client.get("/admin_reg_ver")
    assert resp.status_code == 403


def test_admin_reg_ver_permitido_para_admin_master(client, app):
    user_id = _usuario(app, 'teste.regvermaster@teste.com', 'usuarioregvermasterteste', role='admin_master')
    _login(client, user_id)
    resp = client.get("/admin_reg_ver")
    assert resp.status_code == 200


def test_admin_comum_nao_promove_ninguem_a_admin(app):
    """Regressão: conceder papel 'admin' também passou a ser exclusivo do admin master."""
    with app.app_context():
        admin_comum_id = _usuario(app, 'teste.admincomum2@teste.com', 'usuarioadmincomum2teste', role='admin')
        alvo_id = _usuario(app, 'teste.alvopromocaoadmin@teste.com', 'usuarioalvopromocaoadminteste', role='user')

        admin_comum = User.query.get(admin_comum_id)

        user, erro = services.atualizar_usuario_admin(
            user_id=alvo_id, coord='DPI', despacha0=0, despacha=0, despacha2=0, ativo=1,
            role='admin', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
            admin_atual=admin_comum,
        )

        assert erro is not None
        assert User.query.get(alvo_id).role == 'user'


def test_admin_master_promove_usuario_a_admin(app):
    with app.app_context():
        master_id = _usuario(app, 'teste.masterpromoveadmin@teste.com', 'usuariomasterpromoveadminteste', coord='COPES', role='admin_master')
        alvo_id = _usuario(app, 'teste.alvopromovido@teste.com', 'usuarioalvopromovidoteste', coord='DPI', role='user')

        master = User.query.get(master_id)

        user, erro = services.atualizar_usuario_admin(
            user_id=alvo_id, coord='DPI', despacha0=0, despacha=0, despacha2=0, ativo=1,
            role='admin', cargo_func='teste', trab_conv=1, trab_acordo=1, trab_instru=1,
            admin_atual=master,
        )

        assert erro is None
        assert User.query.get(alvo_id).role == 'admin'
