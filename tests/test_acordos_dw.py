# test_acordos_dw.py
#
# Testes de characterization do grupo Integração DW do módulo
# acordos (último grupo mapeado, fecha esta parte da refatoração).
#
# Não é possível testar programas_por_unidade_DW, chamadas_por_programa_DW
# e dados_financeiros_acordos_DW de ponta a ponta neste ambiente, pois
# dependem de acesso real a um Oracle DW (infraestrutura de produção).
# Os testes abaixo cobrem o que É possível validar sem essa dependência
# externa: um bug real de acesso a resultado None, e as rotas que não
# dependem do Oracle.

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
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-55').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste DW', sei='00000.000000/2024-55', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def test_espera_carga_responde_200(client, app):
    user_id = _usuario(app, 'teste.esperacarga@teste.com', 'usuarioesperacargateste')
    _login(client, user_id)
    resp = client.get("/acordos/teste123/espera_carga")
    assert resp.status_code == 200


def test_lista_dados_financeiros_acordo_inexistente_retorna_404(client, app):
    """Regressão: acordo inexistente deve retornar 404, não quebrar."""
    user_id = _usuario(app, 'teste.listadadosfin@teste.com', 'usuariolistadadosfinteste')
    _login(client, user_id)
    resp = client.get("/acordos/999999/lista_dados_financeiros_acordo")
    assert resp.status_code == 404


def test_lista_dados_financeiros_acordo_existente_responde_200(client, app):
    user_id = _usuario(app, 'teste.listadadosfin2@teste.com', 'usuariolistadadosfin2teste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/{acordo_id}/lista_dados_financeiros_acordo")
    assert resp.status_code == 200


def test_carregaidrel_responde_redirect(client, app):
    user_id = _usuario(app, 'teste.carregaidrel@teste.com', 'usuariocarregaidrelteste')
    _login(client, user_id)
    resp = client.get("/acordos/carregaidrel")
    assert resp.status_code == 302
