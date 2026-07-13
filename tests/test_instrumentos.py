# test_instrumentos.py
#
# Testes de characterization específicos do módulo instrumentos,
# cobrindo o piloto de refatoração (views.py + services.py).


def test_lista_instrumentos_responde_200(client):
    """A listagem pública de instrumentos deve carregar sem erro."""
    resp = client.get("/instrumentos/todos/*/lista_instrumentos")
    assert resp.status_code == 200


def test_delete_instrumento_sem_login_redireciona(client):
    """Excluir um instrumento sem estar logado deve redirecionar para o login."""
    resp = client.get("/instrumentos/1/delete")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
