# test_ted_gestao_vigencia_sigla.py
#
# Testes dos itens A3, A4 e A5 do backlog (tela de Gestão de TED):
# - A3: coluna "Vigência" separada em duas ("Início" e "Fim"), cada uma
#   com ordenação própria (_CHAVES_ORDENACAO)
# - A4: coluna "Fim" colorida por proximidade do vencimento, mesmo
#   padrão de Convênios (vermelho <=30d, laranja 31-60d, cinza 61-90d),
#   a partir do campo `prazo` calculado em listar_teds()
# - A5: instituições exibidas pela sigla (TED_Programa.
#   sigla_unidade_descentralizadora, capturada da API pela cargaTED),
#   com fallback pro nome completo quando a sigla vier vazia
#
# Fixtures idempotentes (get-or-create), mesmo padrão dos demais testes
# de TED — ids na faixa 94xxx pra não colidir com os sintéticos dos
# outros arquivos.

from datetime import date, timedelta

from project import db
from project.ted import services
from project.models import User, TED_Programa, TED_PlanoAcao


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


def _programa(id_programa, unidade, sigla):
    programa = TED_Programa.query.get(id_programa)
    if programa is None:
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa=f'VIGSIG{id_programa}',
            nome='Programa Teste Vigencia/Sigla', unidade_descentralizadora=unidade,
            sigla_unidade_descentralizadora=sigla, ano='2026',
        ))
        db.session.commit()
    else:
        # fixture idempotente, mas o valor da sigla é justamente o que está
        # sob teste — garante o estado esperado mesmo se a linha já existir
        programa.unidade_descentralizadora = unidade
        programa.sigla_unidade_descentralizadora = sigla
        db.session.commit()
    return TED_Programa.query.get(id_programa)


def _plano(id_plano, id_programa, numero_ted, vigencia_inicio=None, vigencia_fim=None):
    plano = TED_PlanoAcao.query.get(id_plano)
    if plano is None:
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano='APROVADO',
            objeto='Objeto de teste vigencia/sigla', valor_beneficiario_especifico=100000.0,
            valor_chamamento_publico=0.0, vigencia_inicio=vigencia_inicio,
            vigencia_fim=vigencia_fim, ano='2026',
        ))
        db.session.commit()
    else:
        # datas são relativas a "hoje" nos testes de prazo — atualizar em vez
        # de pular, senão o teste passa a medir dado congelado de outra rodada
        plano.vigencia_inicio = vigencia_inicio
        plano.vigencia_fim = vigencia_fim
        db.session.commit()
    return TED_PlanoAcao.query.get(id_plano)


def _item_de(id_plano):
    return [i for i in services.listar_teds() if i['plano'].id == id_plano][0]


# ---------------------------------------------------------------- A3

def test_chaves_ordenacao_tem_inicio_e_fim_separados():
    """A3: a chave única 'vigencia' virou duas, uma por coluna."""
    assert 'vigencia_inicio' in services._CHAVES_ORDENACAO
    assert 'vigencia_fim' in services._CHAVES_ORDENACAO
    assert 'vigencia' not in services._CHAVES_ORDENACAO


def test_ordenacao_por_inicio_e_por_fim_sao_independentes(app):
    """
    A3: um TED que começa antes mas termina depois deve trocar de posição
    conforme a coluna escolhida — prova que as duas ordenações são
    realmente independentes, não a mesma chave renomeada.
    """
    with app.app_context():
        _programa(94001, 'Ministério da Ciência, Tecnologia e Inovações', 'MCTI')
        _plano(94010, 94001, 'VIGA001',
               vigencia_inicio=date(2020, 1, 1), vigencia_fim=date(2030, 1, 1))
        _plano(94011, 94001, 'VIGA002',
               vigencia_inicio=date(2021, 1, 1), vigencia_fim=date(2029, 1, 1))

        por_inicio = services.listar_teds({'orgao': 'Ministério da Ciência, Tecnologia e Inovações'},
                                          sort='vigencia_inicio', direcao='asc')
        ids_inicio = [i['plano'].id for i in por_inicio if i['plano'].id in (94010, 94011)]

        por_fim = services.listar_teds({'orgao': 'Ministério da Ciência, Tecnologia e Inovações'},
                                       sort='vigencia_fim', direcao='asc')
        ids_fim = [i['plano'].id for i in por_fim if i['plano'].id in (94010, 94011)]

        # começa antes (94010) vem primeiro por início; termina antes (94011)
        # vem primeiro por fim — ordens opostas
        assert ids_inicio == [94010, 94011]
        assert ids_fim == [94011, 94010]


def test_tela_mostra_duas_colunas_inicio_e_fim(client, app):
    """A3: cabeçalho tem 'Início' e 'Fim' como colunas próprias."""
    user_id = _usuario(app, 'teste.tedvigencia@teste.com', 'usuariotedvigencia')
    _login(client, user_id)
    resp = client.get('/ted/gestao')
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)
    assert 'sort=vigencia_inicio' in texto
    assert 'sort=vigencia_fim' in texto


# ---------------------------------------------------------------- A4

def test_prazo_calculado_para_as_tres_faixas_de_cor(app):
    """
    A4: `prazo` (dias até o fim da vigência) alimenta as 3 faixas de cor
    do template — vermelho (<=30), laranja (31-60), cinza (61-90).
    """
    hoje = date.today()
    with app.app_context():
        _programa(94002, 'Fundo Nacional de Desenvolvimento Científico e Tecnológico', 'FNDCT')
        _plano(94020, 94002, 'VIGB015', vigencia_fim=hoje + timedelta(days=15))
        _plano(94021, 94002, 'VIGB045', vigencia_fim=hoje + timedelta(days=45))
        _plano(94022, 94002, 'VIGB075', vigencia_fim=hoje + timedelta(days=75))

        assert _item_de(94020)['prazo'] == 15
        assert _item_de(94021)['prazo'] == 45
        assert _item_de(94022)['prazo'] == 75


def test_prazo_none_quando_nao_ha_data_de_fim(app):
    """A4: vários TEDs vêm da API sem vigência — não pode quebrar."""
    with app.app_context():
        _programa(94003, 'Ministério da Educação', 'MEC')
        _plano(94030, 94003, 'VIGC001', vigencia_fim=None)

        assert _item_de(94030)['prazo'] is None


def test_cores_das_tres_faixas_aparecem_na_tela(client, app):
    """A4: as classes de cor de Convênios são aplicadas na coluna Fim."""
    hoje = date.today()
    user_id = _usuario(app, 'teste.tedcores@teste.com', 'usuariotedcores')
    with app.app_context():
        _programa(94004, 'Ministério da Saúde', 'MS')
        _plano(94040, 94004, 'VIGD015', vigencia_fim=hoje + timedelta(days=15))
        _plano(94041, 94004, 'VIGD045', vigencia_fim=hoje + timedelta(days=45))
        _plano(94042, 94004, 'VIGD075', vigencia_fim=hoje + timedelta(days=75))

    _login(client, user_id)
    resp = client.get('/ted/gestao', query_string={'orgao': 'Ministério da Saúde'})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    assert 'bg-danger text-white font-weight-bold' in texto
    assert 'bg-warning text-dark font-weight-bold' in texto
    assert 'bg-secondary text-white font-weight-bold' in texto


def test_tooltip_explicativo_das_cores_no_cabecalho(client, app):
    """A4: mesmo tooltip que Convênios já tem, pra explicar as cores."""
    user_id = _usuario(app, 'teste.tedtooltip@teste.com', 'usuariotedtooltip')
    _login(client, user_id)
    resp = client.get('/ted/gestao')
    assert 'Vermelho: vence em menos de 30 dias' in resp.get_data(as_text=True)


# ---------------------------------------------------------------- A5

def test_carga_ted_captura_sigla_da_api(app, preserva_tabelas_ted):
    """
    A5: cargaTED() passa a gravar sigla_unidade_descentralizadora, campo
    que a API já mandava mas a carga descartava. HTTP mockado.
    """
    from unittest.mock import patch, MagicMock

    fake_planos = [{
        'id_plano_acao': 94100, 'id_programa': 94100,
        'sigla_unidade_descentralizada': 'CNPq', 'unidade_descentralizada': 'CNPq',
        'sq_instrumento': '940001', 'tx_situacao_plano_acao': 'APROVADO',
        'tx_objeto_plano_acao': 'Objeto carga sigla',
        'vl_beneficiario_especifico': 1000.0, 'vl_chamamento_publico': 0.0,
        'dt_inicio_vigencia': '2026-01-01', 'dt_fim_vigencia': '2028-01-01',
        'aa_ano_plano_acao': 2026,
    }]
    fake_programas = [{
        'id_programa': 94100, 'tx_codigo_programa': '94100000', 'aa_ano_programa': 2026,
        'tx_nome_programa': 'Programa carga sigla',
        'unidade_descentralizadora': 'Ministério da Ciência, Tecnologia e Inovações',
        'sigla_unidade_descentralizadora': 'MCTI',
    }]

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith('/plano_acao'):
            resp.json.return_value = fake_planos
        elif url.endswith('/programa'):
            resp.json.return_value = fake_programas
        elif url.endswith('/termo_execucao'):
            resp.json.return_value = []
        return resp

    with app.app_context():
        with patch('project.ted.services.requests.get', side_effect=fake_get):
            services.cargaTED()

        programa = TED_Programa.query.get(94100)
        assert programa.sigla_unidade_descentralizadora == 'MCTI'
        assert programa.unidade_descentralizadora == 'Ministério da Ciência, Tecnologia e Inovações'


def test_sigla_ou_nome_orgao_usa_sigla_e_cai_pro_nome(app):
    """A5: fallback pro nome completo quando a sigla vier vazia/nula."""
    with app.app_context():
        com_sigla = _programa(94005, 'Ministério da Ciência, Tecnologia e Inovações', 'MCTI')
        sem_sigla = _programa(94006, 'Órgão Sem Sigla Cadastrada', None)

        assert services.sigla_ou_nome_orgao(com_sigla) == 'MCTI'
        assert services.sigla_ou_nome_orgao(sem_sigla) == 'Órgão Sem Sigla Cadastrada'
        assert services.sigla_ou_nome_orgao(None) is None


def test_tela_mostra_sigla_no_lugar_do_nome_completo(client, app):
    """A5: badge do órgão traz a sigla, com o nome completo no tooltip."""
    user_id = _usuario(app, 'teste.tedsigla@teste.com', 'usuariotedsigla')
    with app.app_context():
        _programa(94007, 'Ministério da Ciência, Tecnologia e Inovações', 'MCTI')
        _plano(94070, 94007, 'VIGE001')

    _login(client, user_id)
    resp = client.get('/ted/gestao', query_string={'orgao': 'Ministério da Ciência, Tecnologia e Inovações'})
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True)

    # sigla como texto do badge, nome completo preservado no title
    assert '<span class="badge badge-secondary" title="Ministério da Ciência, Tecnologia e Inovações">MCTI</span>' in texto


def test_opcoes_filtro_traz_de_para_nome_sigla(app):
    """
    A5: o filtro continua usando o nome completo como valor (a query
    filtra por unidade_descentralizadora), mas ganha o de-para pra
    exibir a sigla. `orgaos` mantém o formato antigo de propósito — o
    BI de TED consome a mesma função.
    """
    with app.app_context():
        _programa(94008, 'Ministério da Ciência, Tecnologia e Inovações', 'MCTI')

        opcoes = services.opcoes_filtro()

        assert 'Ministério da Ciência, Tecnologia e Inovações' in opcoes['orgaos']
        assert opcoes['orgaos_siglas']['Ministério da Ciência, Tecnologia e Inovações'] == 'MCTI'
