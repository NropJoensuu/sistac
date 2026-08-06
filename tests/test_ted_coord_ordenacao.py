# test_ted_coord_ordenacao.py
#
# Testes do prompt A7/A8/A9 + os dois pedidos novos de Igor sobre a
# Gestão de TED (ver prompt_a7_a8_a9_gestao.txt / proposta_melhorias.md):
#
# - A7: BI TED agrega por coordenação (`por_coord`), com os TEDs sem
#   nenhuma execução interna registrada caindo no balde "Não atribuído"
#   em vez de serem excluídos da contagem.
# - A8: BI TED agrega valor por órgão de origem usando a sigla
#   (sigla_ou_nome_orgao), não o nome completo.
# - A9: filtro "Ano" do BI TED mantido em aa_ano_plano_acao (Opção B —
#   ver decisão documentada em proposta_melhorias.md), com tooltip
#   explicativo no <label>.
# - Gestão de TED: sem `coord` explícito na URL, a listagem vem
#   pré-filtrada pela coordenação do usuário logado, excluindo os TEDs
#   não triados (sem execução interna); `coord=*` remove o filtro; um
#   aviso aparece quando há TEDs sem coordenação nenhuma no sistema.
# - Gestão de TED: ordem padrão (sem `sort` na URL) passa a ser por
#   vigência fim ascendente, com NULLS LAST (quem não tem data de fim
#   vai pro final, não pro topo).
#
# IDs na faixa 96xxx pra não colidir com os sintéticos dos demais
# arquivos de teste de TED.

from datetime import date, timedelta

from project import db
from project.ted import services
from project.models import User, TED_Programa, TED_PlanoAcao, TED_Execucao_Interna


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True


def _usuario(app, email, username, coord='DPI'):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is None:
            user = User(
                email=email, username=username,
                plaintext_password='senha123', coord=coord, role='user',
                ativo=1, sversion=1, cargo_func='teste',
                trab_conv=1, trab_acordo=1, trab_instru=1, trab_ted=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        else:
            if user.trab_ted != 1:
                user.trab_ted = 1
            if user.coord != coord:
                user.coord = coord
            db.session.commit()
        return user.id


def _programa(id_programa, unidade='MCTI', sigla=None):
    programa = TED_Programa.query.get(id_programa)
    if programa is None:
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa=f'COORDORD{id_programa}',
            nome='Programa Teste Coord/Ordenacao', unidade_descentralizadora=unidade,
            sigla_unidade_descentralizadora=sigla, ano='2026',
        ))
        db.session.commit()
    return TED_PlanoAcao.query.get(id_programa)


def _plano(id_plano, id_programa, numero_ted, valor=100000.0, vigencia_fim=None):
    plano = TED_PlanoAcao.query.get(id_plano)
    if plano is None:
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano='APROVADO',
            objeto='Objeto de teste coord/ordenacao', valor_beneficiario_especifico=valor,
            valor_chamamento_publico=0.0, vigencia_inicio=None, vigencia_fim=vigencia_fim,
            ano='2026',
        ))
        db.session.commit()
    else:
        plano.vigencia_fim = vigencia_fim
        db.session.commit()
    return TED_PlanoAcao.query.get(id_plano)


# ---------------------------------------------------------------- A7

def test_bi_ted_por_coord_agrega_nao_atribuido_para_sem_execucao(app):
    with app.app_context():
        _programa(96001, unidade='COORDBITESTE')
        _plano(96010, 96001, 'COORDBI001')  # sem execução interna

        dados = services.bi_ted({'orgao': 'COORDBITESTE'})
        por_coord = {c['coordenacao']: c for c in dados['coordenacoes']}

        assert 'Não atribuído' in por_coord
        assert por_coord['Não atribuído']['qtd'] >= 1


def test_bi_ted_por_coord_conta_execucao_registrada(app):
    with app.app_context():
        _programa(96002, unidade='COORDBITESTE2')
        id_plano = 96020
        _plano(id_plano, 96002, 'COORDBI002', valor=50000.0)

        TED_Execucao_Interna.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()
        services.registrar_execucao_interna(
            id_plano_acao=id_plano, coordenacao='COORDXPTO', sei_cnpq='00000.000010/2026-01',
            observacao='teste', usuario_id=1,
        )

        dados = services.bi_ted({'orgao': 'COORDBITESTE2'})
        por_coord = {c['coordenacao']: c for c in dados['coordenacoes']}

        assert por_coord['COORDXPTO']['qtd'] == 1
        assert por_coord['COORDXPTO']['valor'] == 50000.0


def test_bi_ted_filtro_select_coordenacao_no_form(client, app):
    resp = client.get('/ted/bi_ted')
    assert resp.status_code == 200
    assert 'name="coord"' in resp.get_data(as_text=True)


# ---------------------------------------------------------------- A8

def test_bi_ted_agrega_orgao_pela_sigla(app):
    with app.app_context():
        _programa(96003, unidade='Ministério Teste Sigla BI', sigla='MTSB')
        _plano(96030, 96003, 'SIGLABI001')

        dados = services.bi_ted({'orgao': 'Ministério Teste Sigla BI'})
        nomes_orgao = {o['orgao'] for o in dados['orgaos']}

        assert 'MTSB' in nomes_orgao
        assert 'Ministério Teste Sigla BI' not in nomes_orgao


def test_bi_ted_select_orgao_mostra_sigla_com_nome_no_title(client, app):
    with app.app_context():
        _programa(96004, unidade='Ministério Teste Sigla Select', sigla='MTSS')
        _plano(96040, 96004, 'SIGLABI002')

    resp = client.get('/ted/bi_ted')
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)
    assert 'value="Ministério Teste Sigla Select" title="Ministério Teste Sigla Select"' in texto
    assert '>MTSS</option>' in texto


# ---------------------------------------------------------------- A9

def test_bi_ted_tooltip_no_filtro_de_ano(client, app):
    """
    Decisão A9 (Opção B): 60 dos 363 TEDs reais (~16%) não têm
    vigencia_inicio -- fração grande demais pra trocar a base do filtro
    de Ano com segurança sem perder TEDs da contagem. Mantido
    aa_ano_plano_acao, com tooltip explicando o que o filtro representa.
    """
    resp = client.get('/ted/bi_ted')
    assert resp.status_code == 200
    assert 'aa_ano_plano_acao' in resp.get_data(as_text=True)


# ---------------------------------------------- Gestão: filtro por coordenação

def test_gestao_sem_coord_na_url_filtra_pela_coordenacao_do_usuario(client, app):
    with app.app_context():
        _programa(96005, unidade='COORDGESTAO1')
        _plano(96050, 96005, 'COORDGE001')
        _plano(96051, 96005, 'COORDGE002')

        TED_Execucao_Interna.query.filter_by(id_plano_acao=96050).delete()
        TED_Execucao_Interna.query.filter_by(id_plano_acao=96051).delete()
        db.session.commit()

        # 96050 é da coordenação do usuário de teste (DPI), 96051 é de outra
        services.registrar_execucao_interna(
            id_plano_acao=96050, coordenacao='DPI', sei_cnpq='00000.000020/2026-01',
            observacao='teste', usuario_id=1,
        )
        services.registrar_execucao_interna(
            id_plano_acao=96051, coordenacao='OUTRACOORD', sei_cnpq='00000.000021/2026-01',
            observacao='teste', usuario_id=1,
        )

    user_id = _usuario(app, 'teste.tedcoordpadrao@teste.com', 'usuariotedcoordpadrao', coord='DPI')
    _login(client, user_id)

    resp = client.get('/ted/gestao', query_string={'orgao': 'COORDGESTAO1'})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    assert 'COORDGE001' in texto
    assert 'COORDGE002' not in texto


def test_gestao_coord_asterisco_mostra_todos_inclusive_nao_triados(client, app):
    with app.app_context():
        _programa(96006, unidade='COORDGESTAO2')
        _plano(96060, 96006, 'COORDGE010')  # sem execução -- não triado
        _plano(96061, 96006, 'COORDGE011')

        TED_Execucao_Interna.query.filter_by(id_plano_acao=96061).delete()
        db.session.commit()
        services.registrar_execucao_interna(
            id_plano_acao=96061, coordenacao='OUTRACOORD2', sei_cnpq='00000.000022/2026-01',
            observacao='teste', usuario_id=1,
        )

    user_id = _usuario(app, 'teste.tedcoordtodos@teste.com', 'usuariotedcoordtodos', coord='DPI')
    _login(client, user_id)

    resp = client.get('/ted/gestao', query_string={'orgao': 'COORDGESTAO2', 'coord': '*'})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    assert 'COORDGE010' in texto
    assert 'COORDGE011' in texto


def test_gestao_select_coordenacao_aparece_com_opcoes_e_coordenacao_do_usuario_pre_selecionada(client, app):
    user_id = _usuario(app, 'teste.tedcoordselect@teste.com', 'usuariotedcoordselect', coord='DPI')
    _login(client, user_id)

    resp = client.get('/ted/gestao')
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    assert 'name="coord"' in texto
    # DPI (coordenação do usuário, filtro padrão sem 'coord' na URL) vem
    # pré-selecionada; COPES aparece na lista, mas não selecionada
    assert '<option value="DPI" selected>DPI</option>' in texto
    assert '<option value="COPES" >COPES</option>' in texto


def test_gestao_select_coordenacao_todos_reflete_o_mesmo_valor_do_link_do_aviso(client, app):
    user_id = _usuario(app, 'teste.tedcoordselecttodos@teste.com', 'usuariotedcoordselecttodos', coord='DPI')
    _login(client, user_id)

    resp = client.get('/ted/gestao', query_string={'coord': '*'})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    assert '<option value="*" selected>Todos</option>' in texto


def test_gestao_seleciona_coordenacao_diferente_da_propria_filtra_estritamente_por_ela(client, app):
    """
    Meio-termo entre "a minha" (padrão) e "todos" (link do aviso): o
    <select> deixa escolher qualquer coordenação específica, mesmo
    comportamento estrito do filtro padrão, só que pra ela.
    """
    with app.app_context():
        _programa(96011, unidade='COORDSELECTTESTE')
        _plano(96150, 96011, 'COORDSEL001')  # DPI
        _plano(96151, 96011, 'COORDSEL002')  # COPES

        TED_Execucao_Interna.query.filter_by(id_plano_acao=96150).delete()
        TED_Execucao_Interna.query.filter_by(id_plano_acao=96151).delete()
        db.session.commit()

        services.registrar_execucao_interna(
            id_plano_acao=96150, coordenacao='DPI', sei_cnpq='00000.000030/2026-01',
            observacao='teste', usuario_id=1,
        )
        services.registrar_execucao_interna(
            id_plano_acao=96151, coordenacao='COPES', sei_cnpq='00000.000031/2026-01',
            observacao='teste', usuario_id=1,
        )

    user_id = _usuario(app, 'teste.tedcoordoutra@teste.com', 'usuariotedcoordoutra', coord='DPI')
    _login(client, user_id)

    resp = client.get('/ted/gestao', query_string={'orgao': 'COORDSELECTTESTE', 'coord': 'COPES'})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    assert 'COORDSEL002' in texto
    assert 'COORDSEL001' not in texto
    assert '<option value="COPES" selected>COPES</option>' in texto


def test_listar_teds_filtro_coord_e_membership_nao_igualdade_de_lista(app):
    """services.listar_teds({'coord': sigla}) mantém um TED se QUALQUER
    uma das execuções internas bater com a sigla pedida (um TED pode ter
    mais de uma coordenação)."""
    with app.app_context():
        _programa(96007, unidade='COORDGESTAO3')
        _plano(96070, 96007, 'COORDGE020')

        TED_Execucao_Interna.query.filter_by(id_plano_acao=96070).delete()
        db.session.commit()
        services.registrar_execucao_interna(
            id_plano_acao=96070, coordenacao='DPI', sei_cnpq='00000.000023/2026-01',
            observacao='teste', usuario_id=1,
        )
        services.registrar_execucao_interna(
            id_plano_acao=96070, coordenacao='COPES', sei_cnpq='00000.000024/2026-01',
            observacao='teste', usuario_id=1,
        )

        com_dpi = services.listar_teds({'orgao': 'COORDGESTAO3', 'coord': 'DPI'})
        com_copes = services.listar_teds({'orgao': 'COORDGESTAO3', 'coord': 'COPES'})
        com_outra = services.listar_teds({'orgao': 'COORDGESTAO3', 'coord': 'ZZZNAOEXISTE'})

        assert any(i['plano'].id == 96070 for i in com_dpi)
        assert any(i['plano'].id == 96070 for i in com_copes)
        assert not any(i['plano'].id == 96070 for i in com_outra)


def test_gestao_mostra_aviso_quando_ha_ted_sem_coordenacao(client, app):
    with app.app_context():
        _programa(96008, unidade='COORDAVISO1')
        _plano(96080, 96008, 'COORDAV001')  # sem execução interna -- garante contagem > 0

    user_id = _usuario(app, 'teste.tedaviso@teste.com', 'usuariotedaviso', coord='DPI')
    _login(client, user_id)

    resp = client.get('/ted/gestao')
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)
    assert 'Há TED a ser alocado em coordenação' in texto


def test_total_teds_sem_coordenacao_conta_apenas_nao_triados(app):
    with app.app_context():
        _programa(96009, unidade='COORDCONTAGEM')
        _plano(96090, 96009, 'COORDCT001')  # sem execução
        _plano(96091, 96009, 'COORDCT002')

        TED_Execucao_Interna.query.filter_by(id_plano_acao=96091).delete()
        db.session.commit()
        services.registrar_execucao_interna(
            id_plano_acao=96091, coordenacao='DPI', sei_cnpq='00000.000025/2026-01',
            observacao='teste', usuario_id=1,
        )

        total = services.total_teds_sem_coordenacao()
        triados = {e.id_plano_acao for e in TED_Execucao_Interna.query.all()}

        assert 96090 not in triados
        assert 96091 in triados
        assert total >= 1


# --------------------------------------------- Gestão: ordenação padrão

def test_ordenacao_padrao_por_vigencia_fim_ascendente(app):
    hoje = date.today()
    with app.app_context():
        _programa(96100, unidade='ORDPADRAO1')
        _plano(96110, 96100, 'ORDPAD001', vigencia_fim=hoje + timedelta(days=90))
        _plano(96111, 96100, 'ORDPAD002', vigencia_fim=hoje + timedelta(days=10))
        _plano(96112, 96100, 'ORDPAD003', vigencia_fim=hoje + timedelta(days=45))

        resultado = services.listar_teds({'orgao': 'ORDPADRAO1'})
        ids_em_ordem = [i['plano'].id for i in resultado if i['plano'].id in (96110, 96111, 96112)]

        assert ids_em_ordem == [96111, 96112, 96110]


def test_ordenacao_padrao_manda_vigencia_fim_nula_para_o_final(app):
    hoje = date.today()
    with app.app_context():
        _programa(96101, unidade='ORDPADRAO2')
        _plano(96120, 96101, 'ORDPAD010', vigencia_fim=None)
        _plano(96121, 96101, 'ORDPAD011', vigencia_fim=hoje + timedelta(days=5))

        resultado = services.listar_teds({'orgao': 'ORDPADRAO2'})
        ids_em_ordem = [i['plano'].id for i in resultado if i['plano'].id in (96120, 96121)]

        # 96121 (com data) vem antes de 96120 (sem data, NULLS LAST)
        assert ids_em_ordem == [96121, 96120]


def test_ordenacao_padrao_nao_se_aplica_quando_ha_sort_explicito(app):
    with app.app_context():
        _programa(96102, unidade='ORDPADRAO3')
        _plano(96130, 96102, 'ZZZ_ORDPAD', vigencia_fim=None)
        _plano(96131, 96102, 'AAA_ORDPAD', vigencia_fim=None)

        resultado = services.listar_teds({'orgao': 'ORDPADRAO3'}, sort='ted', direcao='asc')
        ids_em_ordem = [i['plano'].id for i in resultado if i['plano'].id in (96130, 96131)]

        assert ids_em_ordem == [96131, 96130]
