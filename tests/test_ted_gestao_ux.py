# test_ted_gestao_ux.py
#
# Testes das melhorias de UX pedidas por Igor na revisão visual da tela
# de Gestão de TED (nota_feedback_visual_ted.txt, item 2): paginação,
# ordenação por coluna, download de CSV, coluna de Coordenação do CNPq
# agregada a partir das execuções internas, timestamp de última carga,
# e o botão de atualização manual movido para o menu Carga (some da
# própria tela de Gestão) com a carga automática diária agendada.

import os
from datetime import date
from unittest.mock import patch, MagicMock

from project import app as flask_app, db, sched
from project.ted import services
from project.models import User, TED_Programa, TED_PlanoAcao, TED_Execucao_Interna, TED_Carga_Status


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
                trab_conv=1, trab_acordo=1, trab_instru=1, trab_ted=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        elif user.trab_ted != 1:
            user.trab_ted = 1
            db.session.commit()
        return user.id


def _programa_teste(id_programa, unidade='MCTI'):
    if not TED_Programa.query.get(id_programa):
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa=f'TESTE{id_programa}', nome='Programa Teste TED UX',
            unidade_descentralizadora=unidade, ano='2026',
        ))
        db.session.commit()


def _plano(id_plano, id_programa, numero_ted, situacao='APROVADO', valor=100000.0):
    if not TED_PlanoAcao.query.get(id_plano):
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano=situacao,
            objeto='Objeto de teste UX', valor_beneficiario_especifico=valor,
            valor_chamamento_publico=0.0, vigencia_inicio=None, vigencia_fim=None,
            ano='2026',
        ))
        db.session.commit()


def test_paginacao_segunda_pagina_traz_o_restante(client, app):
    user_id = _usuario(app, 'teste.tedpaginacao@teste.com', 'usuariotedpaginacao')
    with app.app_context():
        _programa_teste(92000, unidade='PAGINACAOTESTE')
        for i in range(30):
            _plano(92000 + i, 92000, f'PAG{i:03d}')

    _login(client, user_id)

    # coord='*' -- os TEDs sintéticos deste teste não têm execução interna
    # registrada, então ficariam de fora do filtro padrão por coordenação
    # (pedido novo de Igor); coord='*' os traz de volta pra não interferir
    # no que este teste cobre de fato (paginação)
    resp1 = client.get('/ted/gestao', query_string={'orgao': 'PAGINACAOTESTE', 'page': 1, 'coord': '*'})
    assert resp1.status_code == 200
    texto1 = resp1.get_data(as_text=True)

    resp2 = client.get('/ted/gestao', query_string={'orgao': 'PAGINACAOTESTE', 'page': 2, 'coord': '*'})
    assert resp2.status_code == 200
    texto2 = resp2.get_data(as_text=True)

    # a pagina 1 tem 25 (per_page) dos 30, a pagina 2 tem os 5 restantes —
    # nao pode haver TED repetido nas duas paginas
    assert 'PAG000' in texto1
    assert 'PAG029' not in texto1
    assert 'PAG029' in texto2


def test_ordenacao_por_situacao(client, app):
    user_id = _usuario(app, 'teste.tedordenacao@teste.com', 'usuariotedordenacao')
    with app.app_context():
        _programa_teste(92100, unidade='ORDENATESTE')
        _plano(92101, 92100, 'ORD001', situacao='ZZZ_ULTIMA')
        _plano(92102, 92100, 'ORD002', situacao='AAA_PRIMEIRA')

    _login(client, user_id)

    with app.app_context():
        pagina_asc, _ = services.listar_teds({'orgao': 'ORDENATESTE'}, page=1, sort='situacao', direcao='asc')
        pagina_desc, _ = services.listar_teds({'orgao': 'ORDENATESTE'}, page=1, sort='situacao', direcao='desc')

    assert pagina_asc[0]['plano'].situacao_plano == 'AAA_PRIMEIRA'
    assert pagina_desc[0]['plano'].situacao_plano == 'ZZZ_ULTIMA'


def test_coordenacao_agregada_a_partir_das_execucoes(app):
    with app.app_context():
        _programa_teste(92200)
        _plano(92201, 92200, 'COORD001')

        TED_Execucao_Interna.query.filter_by(id_plano_acao=92201).delete()
        db.session.commit()

        services.registrar_execucao_interna(
            id_plano_acao=92201, coordenacao='DPI', sei_cnpq='00000.000002/2026-01',
            observacao='teste', usuario_id=1,
        )
        services.registrar_execucao_interna(
            id_plano_acao=92201, coordenacao='COPES', sei_cnpq='00000.000003/2026-01',
            observacao='teste', usuario_id=1,
        )

        item = [i for i in services.listar_teds() if i['plano'].id == 92201][0]
        assert item['coordenacoes'] == ['COPES', 'DPI']


def test_exportar_teds_csv_gera_arquivo_com_cabecalho_esperado(app):
    with app.app_context():
        _programa_teste(92300)
        _plano(92301, 92300, 'CSV001')

        caminho = services.exportar_teds_csv({'busca': 'CSV001'})

        assert os.path.exists(caminho)
        with open(caminho, encoding='UTF8') as f:
            cabecalho = f.readline().strip()
        assert cabecalho.split(';')[0] == 'TED'
        assert 'Coordenação do CNPq' in cabecalho


def test_rota_exporta_csv_redireciona_para_estatico(client, app):
    user_id = _usuario(app, 'teste.tedcsv@teste.com', 'usuariotedcsv')
    _login(client, user_id)
    resp = client.get('/ted/exporta_csv')
    assert resp.status_code == 302
    assert 'ted.csv' in resp.headers['Location']


def test_data_ultima_carga_gravada_e_exibida(client, app, preserva_tabelas_ted):
    """
    cargaTED() faz delete-and-reload real nas 3 tabelas-espelho de TED
    -- aqui recarrega com listas vazias, que sem preserva_tabelas_ted
    (conftest.py) apagaria os TEDs reais a cada rodada da suíte (ver
    proposta_melhorias.md, item 8).
    """
    user_id = _usuario(app, 'teste.tedultimacarga@teste.com', 'usuariotedultimacarga')

    fake_get_result = {'plano_acao': [], 'programa': [], 'termo_execucao': []}

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        for chave, valor in fake_get_result.items():
            if url.endswith(f'/{chave}'):
                resp.json.return_value = valor
        return resp

    with app.app_context():
        with patch('project.ted.services.requests.get', side_effect=fake_get):
            services.cargaTED()

        assert services.dados_ultima_carga_ted() is not None

    _login(client, user_id)
    resp = client.get('/ted/gestao')
    assert resp.status_code == 200
    assert 'Dados atualizados em' in resp.get_data(as_text=True)


def test_botao_atualizar_da_api_sumiu_da_tela_de_gestao(client, app):
    user_id = _usuario(app, 'teste.tedsemboto@teste.com', 'usuariotedsemboto')
    _login(client, user_id)
    resp = client.get('/ted/gestao')
    assert 'Atualizar da API' not in resp.get_data(as_text=True)


def test_link_atualizar_ted_aparece_no_menu_carga_para_quem_tem_trab_ted(client, app):
    user_id = _usuario(app, 'teste.tedmenucarga@teste.com', 'usuariotedmenucarga')
    _login(client, user_id)
    resp = client.get('/')
    assert 'Atualizar TED' in resp.get_data(as_text=True)


def test_agendar_carga_ted_diaria_e_idempotente(app):
    with app.app_context():
        try:
            sched.remove_job('carga_ted_diaria')
        except Exception:
            pass

        services.agendar_carga_ted_diaria()
        assert sched.get_job('carga_ted_diaria') is not None

        # chamar de novo não deve levantar erro nem duplicar o job
        services.agendar_carga_ted_diaria()
        assert sched.get_job('carga_ted_diaria') is not None
