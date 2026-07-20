# test_demandas_tipos.py
#
# Testes de characterization do grupo Tipos de demanda/passos do
# módulo demandas. Cobre dois bugs reais: lista_tipos usava
# current_user.coord sem @login_required, e a geração do PDF de
# procedimentos usava a API antiga do fpdf2 (pdf.output(caminho, 'F'))
# além de um caminho absoluto do Docker.

from project import db
from project.models import User, Tipos_Demanda


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


def _tipo(app):
    with app.app_context():
        tipo = Tipos_Demanda.query.filter_by(tipo='Tipo Teste Grupo B').first()
        if tipo is None:
            tipo = Tipos_Demanda(tipo='Tipo Teste Grupo B', relevancia=1, unidade='DPI')
            db.session.add(tipo)
            db.session.commit()
        return tipo.id


def test_lista_tipos_sem_login_redireciona(client):
    """Regressão do bug: rota usava current_user.coord sem @login_required."""
    resp = client.get("/demandas/lista_tipos")
    assert resp.status_code == 302


def test_lista_tipos_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.listatipos@teste.com', 'usuariolistatiposteste')
    _login(client, user_id)
    resp = client.get("/demandas/lista_tipos")
    assert resp.status_code == 200


def test_geracao_pdf_procedimentos_nao_quebra(client, app):
    """
    Regressão: a geração do PDF de procedimentos usava a API antiga do
    fpdf2 (pdf.output(caminho, 'F')) e um caminho absoluto do Docker
    ('/app/project/static/...'), ambos incompatíveis fora do container.
    """
    user_id = _usuario(app, 'teste.pdfprocedimentos@teste.com', 'usuariopdfprocedimentosteste')
    _tipo(app)
    _login(client, user_id)
    resp = client.post("/demandas/lista_tipos", data={"gerar": "y"})
    assert resp.status_code == 302


def test_cria_tipo_demanda_responde_200(client, app):
    user_id = _usuario(app, 'teste.criatipodemanda@teste.com', 'usuariocriatipodemandateste')
    _login(client, user_id)
    resp = client.get("/demandas/cria_tipo_demanda")
    assert resp.status_code == 200


def test_cria_passo_tipo_responde_200(client, app):
    user_id = _usuario(app, 'teste.criapassotipo@teste.com', 'usuariocriapassotipoteste')
    tipo_id = _tipo(app)
    _login(client, user_id)
    resp = client.get(f"/demandas/{tipo_id}/cria_passo_tipo")
    assert resp.status_code == 200


def test_lista_passos_tipos_responde_200(client, app):
    tipo_id = _tipo(app)
    resp = client.get(f"/demandas/{tipo_id}/lista_passos_tipos")
    assert resp.status_code == 200
