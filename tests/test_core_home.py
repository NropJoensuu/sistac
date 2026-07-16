# test_core_home.py
#
# Testes de characterization do grupo Home/Info do módulo core.
# Cobre um bug real: com carga_auto=1 e nenhum log 'agc' anterior
# (instalação nova), o código quebrava primeiro com AttributeError
# (acessava .user_id de um resultado None) e, depois de corrigido
# isso, com NotNullViolation ao tentar gravar user_id=NULL no log.

from project import db, sched
from project.models import Sistema


def test_pagina_inicial_responde_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_inicio_responde_200(client):
    resp = client.get("/inicio")
    assert resp.status_code == 200


def test_info_responde_200(client):
    resp = client.get("/info")
    assert resp.status_code == 200


def test_index_com_carga_auto_e_sem_log_anterior_nao_quebra(app, client):
    """
    Regressão do bug: habilitar carga_auto numa instalação sem nenhum
    log 'agc' anterior não deve derrubar a página inicial.
    """
    with app.app_context():
        for job_id in ['carga_siconv', 'carga_chamadas_DW']:
            try:
                sched.remove_job(job_id)
            except Exception:
                pass

        sistema = Sistema.query.first()
        original = sistema.carga_auto
        sistema.carga_auto = 1
        db.session.commit()

    try:
        resp = client.get("/")
        assert resp.status_code == 200
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.carga_auto = original
            db.session.commit()
