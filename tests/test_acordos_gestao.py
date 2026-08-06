# test_acordos_gestao.py
#
# Testes da Gestão de Acordos (lista_acordos): paginação, ordenação por
# clique no cabeçalho, filtros (situação/EP UF/busca) e o bug real
# corrigido de rota sem @login_required usando current_user.id (item
# C1/C2 do backlog — mesmo padrão já coberto em Convênios/TED).

from datetime import date
from project import db
from project.acordos import services
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


def _acordo(sei, situ='Vigente-Z', uf='DF', nome='Acordo Teste Gestao'):
    existente = Acordo.query.filter_by(sei=sei).first()
    if existente is None:
        db.session.add(Acordo(
            nome=nome, sei=sei, epe='EPE Teste', uf=uf,
            data_inicio=date(2024, 1, 1), data_fim=date(2030, 1, 1),
            valor_cnpq=100000.0, valor_epe=50000.0, unidade_cnpq='DPI',
            situ=situ, desc='teste', capital=0.0, custeio=0.0,
            bolsas=100000.0, siafi='123',
        ))
        db.session.commit()


def test_lista_acordos_sem_login_redireciona(client):
    """
    Regressão do bug real corrigido: a rota não tinha @login_required,
    mas usava current_user.id incondicionalmente — acesso anônimo
    derrubava a página com AttributeError em vez de redirecionar pro
    login (mesmo padrão de bug já corrigido em Convênios/B13).
    """
    resp = client.get("/acordos/todos/*/lista_acordos")
    assert resp.status_code in (301, 302)


def test_lista_acordos_filtro_situacao_restringe_resultado(client, app):
    user_id = _usuario(app, 'teste.gestaoacordos1@teste.com', 'usuariogestaoacordos1')
    with app.app_context():
        _acordo('00000.000000/2024-61', situ='Vigente-Z')
        _acordo('00000.000000/2024-62', situ='Não executado')
    _login(client, user_id)

    resp = client.get(
        "/acordos/todos/*/lista_acordos",
        query_string={'situacao': 'Não executado'},
    )
    assert resp.status_code == 200
    assert b'00000.000000/2024-62' in resp.data
    assert b'00000.000000/2024-61' not in resp.data


def test_lista_acordos_ordenacao_e_paginacao_respondem_200(client, app):
    user_id = _usuario(app, 'teste.gestaoacordos2@teste.com', 'usuariogestaoacordos2')
    with app.app_context():
        _acordo('00000.000000/2024-63')
    _login(client, user_id)

    resp = client.get(
        "/acordos/todos/*/lista_acordos",
        query_string={'sort': 'nome', 'dir': 'desc', 'page': 1},
    )
    assert resp.status_code == 200


def test_buscar_acordos_pagina_e_filtra_por_busca():
    """
    services.buscar_acordos: filtro `busca` (nome/sei) e paginação —
    item C1 do backlog, mesma estrutura de listar_teds()/
    listar_convenios_siconv().
    """
    from project import app as flask_app
    with flask_app.app_context():
        _acordo('00000.000000/2024-64', nome='Acordo Busca Especial Gestao')

        pagina, paginacao, _, _, _ = services.buscar_acordos(
            'todos', '*', 'DPI', filtros={'busca': 'Busca Especial'}, page=1)

        assert paginacao['total'] >= 1
        assert all('Busca Especial' in a[2] for a in pagina)
