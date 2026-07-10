# test_rotas_publicas.py
#
# Testes de "characterization": confirmam o comportamento ATUAL da
# aplicação (não necessariamente o comportamento "correto" ou ideal).
# Servem de rede de segurança para detectar quebras acidentais durante
# refatorações futuras (Fase 2 em diante do projeto de melhoria).


def test_pagina_inicial_responde_200(client):
    """A rota '/' deve carregar sem erro para um visitante não autenticado."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_pagina_login_responde_200(client):
    """A página de login deve estar acessível sem autenticação."""
    resp = client.get("/login")
    assert resp.status_code == 200


def test_pagina_registro_responde_200(client):
    """A página de registro deve estar acessível sem autenticação."""
    resp = client.get("/register")
    assert resp.status_code == 200


def test_rota_protegida_redireciona_para_login(client):
    """
    Uma rota marcada com @login_required deve redirecionar (302) para
    o login quando acessada sem sessão autenticada — nunca retornar
    200 nem vazar dados para um visitante anônimo.
    """
    resp = client.get("/admin_view_users")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
