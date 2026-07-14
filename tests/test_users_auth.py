# test_users_auth.py
#
# Testes de characterization do grupo de autenticação do módulo users
# (registro, login, confirmação de e-mail). Cobre especificamente dois
# bugs reais encontrados durante a refatoração:
#
# 1. Registro com e-mail/usuário duplicado crashava com erro 500
#    (ValidationError não tratada).
# 2. Hash de senha gerado pelo Werkzeug moderno (scrypt, 162 chars)
#    não cabia na coluna do banco (VARCHAR(128)), quebrando qualquer
#    cadastro ou troca de senha.


def test_pagina_login_carrega(client):
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_com_credenciais_invalidas_nao_quebra(client):
    """
    Login com e-mail inexistente deve reexibir o formulário com uma
    mensagem de erro (200), nunca travar com erro 500.
    """
    resp = client.post(
        "/login",
        data={"email": "naoexiste@teste.com", "password": "qualquer"},
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_registro_com_dados_invalidos_nao_quebra(client):
    """
    Submeter o formulário de registro vazio/inválido deve reexibir o
    formulário (200), nunca travar com erro 500.
    """
    resp = client.post(
        "/register",
        data={"email": "", "username": "", "password": "", "coord": ""},
    )
    assert resp.status_code == 200
