# test_acordos_programas_cnpq.py
#
# Testes de characterization do grupo Programas CNPq do módulo
# acordos. Cobre um bug real: lista_programas_acordo quebrava com
# AttributeError quando o acordo informado não existia (o código
# original acessava `.nome` de um resultado que podia ser None).

from datetime import date
from project import db
from project.models import User, Acordo, Programa_CNPq


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
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-77').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste Programas', sei='00000.000000/2024-77', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def _programa_cnpq(app):
    with app.app_context():
        prog = Programa_CNPq.query.filter_by(COD_PROGRAMA='PRGTESTE001').first()
        if prog is None:
            prog = Programa_CNPq(
                COD_PROGRAMA='PRGTESTE001', NOME_PROGRAMA='Programa Teste',
                SIGLA_PROGRAMA='PT', COORD='DPI',
            )
            db.session.add(prog)
            db.session.commit()
        return prog.ID_PROGRAMA


def test_lista_programas_acordo_inexistente_retorna_404(client, app):
    """Regressão: acordo inexistente deve retornar 404, não quebrar com AttributeError."""
    user_id = _usuario(app, 'teste.listaprogacordo@teste.com', 'usuariolistaprogacordoteste')
    _login(client, user_id)
    resp = client.get("/acordos/999999/lista_programas_acordo")
    assert resp.status_code == 404


def test_lista_programas_acordo_existente_responde_200(client, app):
    user_id = _usuario(app, 'teste.listaprogacordo2@teste.com', 'usuariolistaprogacordo2teste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/{acordo_id}/lista_programas_acordo")
    assert resp.status_code == 200


def test_cria_programa_cnpq_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.criaprogcnpq@teste.com', 'usuariocriaprogcnpqteste')
    _login(client, user_id)
    resp = client.get("/acordos/cria_programa_cnpq")
    assert resp.status_code == 200


def test_lista_programa_cnpq_sem_login_redireciona(client):
    """Regressão do bug: rota usava current_user.coord sem @login_required, quebrando para visitante anônimo."""
    resp = client.get("/acordos/lista_programa_cnpq")
    assert resp.status_code == 302


def test_lista_programa_cnpq_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.listaprogcnpq@teste.com', 'usuariolistaprogcnpqteste')
    _login(client, user_id)
    resp = client.get("/acordos/lista_programa_cnpq")
    assert resp.status_code == 200


def test_atualiza_programa_cnpq_get_responde_200(client, app):
    user_id = _usuario(app, 'teste.atualizaprogcnpq@teste.com', 'usuarioatualizaprogcnpqteste')
    prog_id = _programa_cnpq(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/{prog_id}/atualiza_programa_cnpq")
    assert resp.status_code == 200


def test_edic_programa_responde_200(client):
    resp = client.get("/acordos/PRGTESTE001/PT/edic_programa")
    assert resp.status_code == 200
