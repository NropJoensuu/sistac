# test_acordos_chamadas.py
#
# Testes de characterization do grupo Chamadas do acordo do módulo
# acordos. Cobre dois bugs reais encontrados durante a refatoração:
# 1. consulta_acordo_proc_mae quebrava (AttributeError, depois
#    BuildError) quando o processo-mãe não tinha nenhum acordo
#    associado.
# 2. processos_chamada quebrava (AttributeError) quando o ID de
#    chamada do DW não correspondia a nenhuma chamada cadastrada.

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
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-88').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste', sei='00000.000000/2024-88', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def test_consulta_acordo_proc_mae_sem_associacao_nao_quebra(client, app):
    """Regressão: processo-mãe sem acordo associado deve redirecionar, não quebrar."""
    user_id = _usuario(app, 'teste.consultaacordoprocmae@teste.com', 'usuarioconsultaacordoprocmaeteste')
    _login(client, user_id)
    resp = client.get("/acordos/999999/consulta_acordo_proc_mae")
    assert resp.status_code == 302


def test_processos_chamada_inexistente_retorna_404(client):
    """Regressão: ID de chamada do DW inexistente deve retornar 404, não quebrar."""
    resp = client.get("/acordos/999999/processos_chamada")
    assert resp.status_code == 404


def test_chamadas_acordo_responde_200(client, app):
    user_id = _usuario(app, 'teste.chamadasacordo@teste.com', 'usuariochamadasacordoteste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/{acordo_id}/chamadas_acordo")
    assert resp.status_code == 200


def test_programa_acordo_responde_200(client, app):
    user_id = _usuario(app, 'teste.programaacordo@teste.com', 'usuarioprogramaacordoteste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/programa_acordo/{acordo_id}")
    assert resp.status_code == 200


def test_associa_chamada_responde_200(client, app):
    user_id = _usuario(app, 'teste.associachamadaacordo@teste.com', 'usuarioassociachamadaacordoteste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/associa_chamada/{acordo_id}")
    assert resp.status_code == 200
