# test_acordos_dashboards.py
#
# Testes de characterization do grupo Dashboards/mapas do módulo
# acordos. Cobre um bug real: resumo_acordos usava current_user.coord
# mas não tinha @login_required, quebrando com AttributeError para
# qualquer visitante não autenticado.

from datetime import date
from project import db
from project.models import User, Acordo


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


def _acordo(app):
    with app.app_context():
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-44').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste Dashboards', sei='00000.000000/2024-44', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def test_resumo_acordos_sem_login_redireciona(client):
    """Regressão do bug: rota usava current_user.coord sem @login_required."""
    resp = client.get("/acordos/resumo_acordos")
    assert resp.status_code == 302


def test_resumo_acordos_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.resumoacordos@teste.com', 'usuarioresumoacordosteste')
    _login(client, user_id)
    resp = client.get("/acordos/resumo_acordos")
    assert resp.status_code == 200


def test_brasil_acordos_responde_200(client):
    resp = client.get("/acordos/brasil_acordos")
    assert resp.status_code == 200


def test_quadro_acordos_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.quadroacordos@teste.com', 'usuarioquadroacordosteste')
    _login(client, user_id)
    resp = client.get("/acordos/quadro_acordos")
    assert resp.status_code == 200


def test_gasto_mes_sem_processos_mae_nao_quebra(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/2024/EPE/DF/gasto_mes")
    assert resp.status_code == 200
