# test_convenios_programas.py
#
# Testes de characterization do grupo "Programas de interesse" do
# módulo convenios. Cobre a correção de um bug real: o CSV de
# referência era gravado num caminho absoluto do Docker
# ('/app/project/static/...'), que não existe fora do container.


def test_lista_programas_pref_responde_200(client):
    resp = client.get("/convenios/lista_programas_pref")
    assert resp.status_code == 200
