# test_core_cascata_funcionalidades.py
#
# Testes da mudança de regra de negócio confirmada explicitamente por
# Igor: ao desabilitar uma funcionalidade do sistema (Convênios,
# Acordos, Instrumentos), a permissão "trabalha com X" correspondente
# deve ser removida em cascata de todos os usuários que a tinham, e o
# campo correspondente some da tela de edição de usuário enquanto a
# funcionalidade estiver desabilitada.

from project import db
from project.models import User, Sistema
from project.core import services as core_services


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _admin_master(app):
    with app.app_context():
        user = User.query.filter_by(email='teste.cascatamaster@teste.com').first()
        if user is None:
            user = User(
                email='teste.cascatamaster@teste.com', username='usuariocascatamasterteste',
                plaintext_password='senha123', coord='COPES', role='admin_master',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=1, despacha=1, despacha2=1,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _usuario_com_trab_acordo(app, email, username):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=0, trab_acordo=1, trab_instru=0,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        else:
            user.trab_acordo = 1
            db.session.commit()
        return user.id


def _restaurar_funcionalidades(app):
    with app.app_context():
        s = Sistema.query.first()
        s.funcionalidade_conv = 1
        s.funcionalidade_acordo = 1
        s.funcionalidade_instru = 1
        db.session.commit()


def test_desabilitar_funcionalidade_remove_permissao_em_cascata(app):
    admin_id = _admin_master(app)
    user_id = _usuario_com_trab_acordo(app, 'teste.cascatausuario@teste.com', 'usuariocascatausuarioteste')

    try:
        with app.app_context():
            # garante o ponto de partida (habilitado), para testar de fato a
            # transição habilitado -> desabilitado, que é quando a cascata roda
            s = Sistema.query.first()
            s.funcionalidade_acordo = 1
            db.session.commit()

            assert User.query.get(user_id).trab_acordo == 1

            core_services.atualizar_config_funcionalidades(
                funcionalidade_conv=True, funcionalidade_acordo=False, funcionalidade_instru=True,
                carga_auto=False, usuario_id=admin_id,
            )

            assert User.query.get(user_id).trab_acordo == 0
    finally:
        _restaurar_funcionalidades(app)


def test_campo_some_da_tela_quando_funcionalidade_desabilitada(client, app):
    admin_id = _admin_master(app)

    try:
        with app.app_context():
            core_services.atualizar_config_funcionalidades(
                funcionalidade_conv=True, funcionalidade_acordo=False, funcionalidade_instru=True,
                carga_auto=False, usuario_id=admin_id,
            )

        _login(client, admin_id)
        resp = client.get(f"/{admin_id}/admin_update_user")

        assert 'trabalha com acordos'.encode() not in resp.data.lower()
        assert 'trabalha com conv'.encode() in resp.data.lower()
    finally:
        _restaurar_funcionalidades(app)
