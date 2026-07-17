# test_acordos_processos.py
#
# Testes de characterization do grupo Processos mãe/filho/bolsistas do
# módulo acordos. Cobre 4 bugs reais encontrados durante a
# refatoração, todos do mesmo padrão: acesso a atributo de uma consulta
# que podia retornar None/vazia, sem checagem.

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
        acordo = Acordo.query.filter_by(sei='00000.000000/2024-66').first()
        if acordo is None:
            acordo = Acordo(
                nome='Acordo Teste Processos', sei='00000.000000/2024-66', epe='EPE Teste', uf='DF',
                data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31), valor_cnpq=100000.0,
                valor_epe=50000.0, unidade_cnpq='DPI', situ='Em execução', desc='teste',
                capital=0.0, custeio=0.0, bolsas=100000.0, siafi='123',
            )
            db.session.add(acordo)
            db.session.commit()
        return acordo.id


def test_lista_processos_mae_por_acordo_inexistente_retorna_404(client):
    """Regressão: acordo inexistente deve retornar 404, não quebrar."""
    resp = client.get("/acordos/999999/lista_processos_mae_por_acordo")
    assert resp.status_code == 404


def test_lista_processos_mae_por_acordo_existente_responde_200(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/lista_processos_mae_por_acordo")
    assert resp.status_code == 200


def test_altera_mae_processo_inexistente_retorna_404(client):
    """Regressão: processo-mãe inexistente deve retornar 404, não quebrar."""
    resp = client.get("/acordos/1/PROC_INEXISTENTE/altera_mae")
    assert resp.status_code == 404


def test_deleta_processo_mae_associacao_inexistente_nao_quebra(client, app):
    """Regressão: desfazer associação inexistente deve redirecionar com aviso, não quebrar."""
    user_id = _usuario(app, 'teste.deletaprocessomae@teste.com', 'usuariodeletaprocessomaeteste')
    _login(client, user_id)
    resp = client.get("/acordos/999999/1/deleta_processo_mae")
    assert resp.status_code == 302


def test_lista_processos_filho_sem_filhos_nao_quebra(client):
    """Regressão: processo-mãe sem nenhum filho deve carregar normalmente, não quebrar."""
    resp = client.get("/acordos/PROC_SEM_FILHOS_TESTE/lista_processos_filho")
    assert resp.status_code == 200


def test_processo_mae_acordo_responde_200(client, app):
    user_id = _usuario(app, 'teste.processomaeacordo@teste.com', 'usuarioprocessomaeacordoteste')
    acordo_id = _acordo(app)
    _login(client, user_id)
    resp = client.get(f"/acordos/{acordo_id}/processo_mae_acordo")
    assert resp.status_code == 200


def test_inclui_proc_mae_responde_200(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/inclui_proc_mae")
    assert resp.status_code == 200


def test_lista_processos_filho_por_acordo_responde_200(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/lista_processos_filho_por_acordo")
    assert resp.status_code == 200


def test_lista_bolsistas_acordo_responde_200(client, app):
    acordo_id = _acordo(app)
    resp = client.get(f"/acordos/{acordo_id}/lista_bolsistas")
    assert resp.status_code == 200
