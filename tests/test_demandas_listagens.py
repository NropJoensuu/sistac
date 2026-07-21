# test_demandas_listagens.py
#
# Testes de characterization do grupo Listagens/pesquisa do módulo
# demandas.

from project.models import Tipos_Demanda


def test_list_demandas_responde_200(client):
    resp = client.get("/demandas/demandas")
    assert resp.status_code == 200


def test_prioriza_responde_200(client):
    resp = client.get("/demandas/0.5/0.5/0.5/*/*/prioriza")
    assert resp.status_code == 200


def test_pesquisa_demanda_responde_200(client):
    resp = client.get("/demandas/pesquisa")
    assert resp.status_code == 200


def test_demandas_por_tipo_responde_200(client, app):
    with app.app_context():
        tipo = Tipos_Demanda.query.first()
        tipo_nome = tipo.tipo if tipo else 'Tipo Teste Nucleo'

    resp = client.get(f"/demandas/{tipo_nome}/demandas_por_tipo")
    assert resp.status_code == 200


def test_list_pesquisa_sem_filtros_responde_200(client):
    pesq = ';;Todos;Todos;Todos;;;;;;Todos'
    resp = client.get(f"/demandas/{pesq}/list_pesquisa")
    assert resp.status_code == 200
