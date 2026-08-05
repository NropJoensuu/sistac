# test_ted_gestao.py
#
# Testes do módulo TED (Etapa 3 do roadmap de BI, tela de gestão):
# rota básica, curadoria manual (execução interna e vínculo a Programa
# CNPq), e cargaTED() com a chamada HTTP mockada (não bate na API real
# do TransfereGov durante o pytest).

from unittest.mock import patch, MagicMock

from project import db
from project.ted import services
from project.models import (
    User, Programa_CNPq, TED_Programa, TED_PlanoAcao, TED_TermoExecucao,
    TED_Execucao_Interna, TED_Vinculo_ProgramaCNPq,
)


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
            # usuário criado em execução anterior da suíte, antes de
            # trab_ted existir (banco de dev persistente) — sem isso,
            # o guard novo em /ted/gestao devolveria 403.
            user.trab_ted = 1
            db.session.commit()
        return user.id


def _plano_teste(id_plano=90001, id_programa=90001, numero_ted='900001'):
    if not TED_Programa.query.get(id_programa):
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa='TESTE001', nome='Programa Teste TED',
            unidade_descentralizadora='MCTI', ano='2026',
        ))
        db.session.commit()
    existente = TED_PlanoAcao.query.get(id_plano)
    if existente is None:
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano='APROVADO',
            objeto='Objeto de teste do TED', valor_beneficiario_especifico=100000.0,
            valor_chamamento_publico=0.0, vigencia_inicio=None, vigencia_fim=None,
            ano='2026',
        ))
        db.session.commit()
    return id_plano


def test_gestao_sem_login_redireciona(client):
    resp = client.get('/ted/gestao')
    assert resp.status_code == 302


def test_gestao_logado_responde_200(client, app):
    user_id = _usuario(app, 'teste.tedgestao@teste.com', 'usuariotedgestao')
    with app.app_context():
        _plano_teste()
    _login(client, user_id)
    resp = client.get('/ted/gestao')
    assert resp.status_code == 200


def test_gestao_com_filtros_responde_200(client, app):
    user_id = _usuario(app, 'teste.tedfiltro@teste.com', 'usuariotedfiltro')
    with app.app_context():
        _plano_teste(id_plano=90002, id_programa=90002, numero_ted='900002')
    _login(client, user_id)
    resp = client.get('/ted/gestao', query_string={'orgao': 'MCTI', 'ano': '2026'})
    assert resp.status_code == 200


def test_registra_execucao_interna_aparece_na_listagem(app):
    with app.app_context():
        id_plano = _plano_teste(id_plano=90003, id_programa=90003, numero_ted='900003')

        # limpa execuções de rodadas anteriores da suíte (banco de dev
        # persistente) — registrar_execucao_interna acumula por design
        # (um TED pode ter mais de uma execução), então o teste precisa
        # começar de um estado conhecido, não assumir "nenhuma ainda".
        TED_Execucao_Interna.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()

        services.registrar_execucao_interna(
            id_plano_acao=id_plano, coordenacao='DPI', sei_cnpq='00000.000001/2026-01',
            observacao='teste', usuario_id=1,
        )

        item = [i for i in services.listar_teds() if i['plano'].id == id_plano][0]
        assert len(item['execucoes']) == 1
        assert item['execucoes'][0].sei_cnpq == '00000.000001/2026-01'


def test_vincular_programa_cnpq_atualiza_estado(app):
    with app.app_context():
        id_plano = _plano_teste(id_plano=90004, id_programa=90004, numero_ted='900004')

        if not Programa_CNPq.query.filter_by(COD_PROGRAMA='TEDTESTE01').first():
            programa_cnpq = Programa_CNPq('TEDTESTE01', 'Programa CNPq Teste TED', 'PCTT', 'DPI')
            db.session.add(programa_cnpq)
            db.session.commit()
        programa_cnpq = Programa_CNPq.query.filter_by(COD_PROGRAMA='TEDTESTE01').first()

        # idem: limpa vínculo de rodadas anteriores antes de checar o
        # estado "antes" (banco de dev persistente, não recriado a cada run)
        TED_Vinculo_ProgramaCNPq.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()

        antes = [i for i in services.listar_teds() if i['plano'].id == id_plano][0]
        assert antes['programa_cnpq_nome'] is None

        services.vincular_programa_cnpq(
            id_plano_acao=id_plano, id_programa_cnpq=programa_cnpq.ID_PROGRAMA,
            tipo_evidencia='nome_literal', usuario_id=1,
        )

        depois = [i for i in services.listar_teds() if i['plano'].id == id_plano][0]
        assert depois['programa_cnpq_nome'] == 'PCTT'


def test_carga_ted_mockada_popula_tabelas_espelho(app, preserva_tabelas_ted):
    """
    cargaTED() não bate na API real durante o teste — a chamada HTTP é
    mockada. Cobre o caso de plano_acao ainda 'EM_ELABORACAO', sem
    sq_instrumento (número do TED só existe depois de aprovado).

    A função em si faz delete-and-reload real nas 3 tabelas-espelho de
    TED — preserva_tabelas_ted (conftest.py) restaura os TEDs reais
    depois do teste (ver proposta_melhorias.md, item 8).
    """
    fake_planos = [
        {
            'id_plano_acao': 91001, 'id_programa': 91001,
            'sigla_unidade_descentralizada': 'CNPq', 'unidade_descentralizada': 'CNPq',
            'sq_instrumento': '999999', 'tx_situacao_plano_acao': 'APROVADO',
            'tx_objeto_plano_acao': 'Objeto de carga de teste',
            'vl_beneficiario_especifico': 500000.0, 'vl_chamamento_publico': 0.0,
            'dt_inicio_vigencia': '2026-01-01', 'dt_fim_vigencia': '2028-01-01',
            'aa_ano_plano_acao': 2026,
        },
        {
            'id_plano_acao': 91002, 'id_programa': 91001,
            'sigla_unidade_descentralizada': 'CNPq', 'unidade_descentralizada': 'CNPq',
            'sq_instrumento': None, 'tx_situacao_plano_acao': 'EM_ELABORACAO',
            'tx_objeto_plano_acao': None,
            'vl_beneficiario_especifico': 0.0, 'vl_chamamento_publico': 0.0,
            'dt_inicio_vigencia': None, 'dt_fim_vigencia': None,
            'aa_ano_plano_acao': 2026,
        },
    ]
    fake_programas = [
        {'id_programa': 91001, 'tx_codigo_programa': '99999999', 'aa_ano_programa': 2026,
         'tx_nome_programa': 'Programa de carga de teste', 'unidade_descentralizadora': 'MCTI'},
    ]
    fake_termos = [
        {'id_termo': 91501, 'id_plano_acao': 91001, 'tx_situacao_termo': 'EM_EXECUCAO',
         'dt_assinatura_termo': '2026-02-01', 'tx_numero_ns_termo': '2026NS000001',
         'tx_num_processo_sei': None},
    ]

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith('/plano_acao'):
            resp.json.return_value = fake_planos
        elif url.endswith('/programa'):
            resp.json.return_value = fake_programas
        elif url.endswith('/termo_execucao'):
            resp.json.return_value = fake_termos
        return resp

    with app.app_context():
        with patch('project.ted.services.requests.get', side_effect=fake_get):
            resultado = services.cargaTED()

        assert resultado == {'programas': 1, 'planos': 2, 'termos': 1}

        aprovado = TED_PlanoAcao.query.get(91001)
        assert aprovado.numero_ted == '999999'
        em_elaboracao = TED_PlanoAcao.query.get(91002)
        assert em_elaboracao.numero_ted is None

        programa = TED_Programa.query.get(91001)
        assert programa.nome == 'Programa de carga de teste'

        termo = TED_TermoExecucao.query.get(91501)
        assert termo.referencia_externa is None
