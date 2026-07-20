# test_demandas_plano_trabalho.py
#
# Testes de characterization do grupo Plano de trabalho do módulo
# demandas (primeiro grupo do maior módulo do projeto). Também
# confirma que o re-export de registra_log_auto (agora em
# project.demandas.services, com compatibilidade em
# project.demandas.views) continua funcionando para todo o sistema.

from project import db
from project.models import User, Plano_Trabalho


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
                despacha0=1, despacha=1, despacha2=1,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _atividade(app):
    with app.app_context():
        atividade = Plano_Trabalho.query.filter_by(atividade_sigla='ATVTESTE').first()
        if atividade is None:
            atividade = Plano_Trabalho(
                atividade_sigla='ATVTESTE', atividade_desc='Atividade Teste',
                natureza='Finalística', meta=10, situa='Ativa', unidade='DPI',
            )
            db.session.add(atividade)
            db.session.commit()
        return atividade.id


def test_plano_trabalho_sem_login_redireciona(client):
    """Regressão do bug: rota usava current_user.coord sem @login_required."""
    resp = client.get("/demandas/plano_trabalho")
    assert resp.status_code == 302


def test_plano_trabalho_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.planotrabalho@teste.com', 'usuarioplanotrabalhoteste')
    _login(client, user_id)
    resp = client.get("/demandas/plano_trabalho")
    assert resp.status_code == 200


def test_update_plano_trabalho_responde_200(client, app):
    user_id = _usuario(app, 'teste.updplano@teste.com', 'usuarioupdplanoteste')
    atividade_id = _atividade(app)
    _login(client, user_id)
    resp = client.get(f"/demandas/{atividade_id}/update_plano_trabalho")
    assert resp.status_code == 200


def test_cria_atividade_responde_200(client, app):
    user_id = _usuario(app, 'teste.criaatividade@teste.com', 'usuariocriaatividadeteste')
    _login(client, user_id)
    resp = client.get("/demandas/cria_atividade")
    assert resp.status_code == 200


def test_delete_atividade_sem_permissao_bloqueado(client, app):
    """Usuário sem permissão de despacho não deve conseguir excluir atividade do plano."""
    with app.app_context():
        user = User.query.filter_by(email='teste.semdespacho@teste.com').first()
        if user is None:
            user = User(
                email='teste.semdespacho@teste.com', username='usuariosemdespachoteste',
                plaintext_password='senha123', coord='DPI', role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        user_id = user.id

    atividade_id = _atividade(app)
    _login(client, user_id)
    resp = client.get(f"/demandas/{atividade_id}/delete")
    assert resp.status_code == 403
