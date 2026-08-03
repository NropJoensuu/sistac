# test_ted_bi.py
#
# Testes da tela de BI TED (Etapa 3 do roadmap_bi_sistac.md, parte
# final): rota pública sem login, filtros via querystring, cálculo do
# percentual de curadoria (vínculo a Programa CNPq) e agregação de
# valor por órgão de origem. Segue o padrão de test_convenios_bi.py/
# test_acordos_bi.py.

from project import db
from project.ted import services
from project.models import User, Sistema, TED_Programa, TED_PlanoAcao, Programa_CNPq


def _programa(id_programa, unidade='MCTI'):
    if not TED_Programa.query.get(id_programa):
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa=f'BITESTE{id_programa}', nome='Programa Teste BI TED',
            unidade_descentralizadora=unidade, ano='2026',
        ))
        db.session.commit()


def _plano(id_plano, id_programa, numero_ted, situacao='APROVADO', valor=100000.0, ano='2026'):
    if not TED_PlanoAcao.query.get(id_plano):
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano=situacao,
            objeto='Objeto de teste BI TED', valor_beneficiario_especifico=valor,
            valor_chamamento_publico=0.0, vigencia_inicio=None, vigencia_fim=None,
            ano=ano,
        ))
        db.session.commit()


def test_bi_ted_sem_login_responde_200(client):
    """BI TED é rota pública — não exige login, só depende de Sistema.bi_ted."""
    resp = client.get('/ted/bi_ted')
    assert resp.status_code == 200


def test_bi_ted_com_filtros_responde_200(client, app):
    with app.app_context():
        _programa(93100, unidade='FILTROBITESTE')
        _plano(93101, 93100, 'BIFILTRO001')
    resp = client.get('/ted/bi_ted', query_string={'orgao': 'FILTROBITESTE', 'ano': '2026'})
    assert resp.status_code == 200


def test_bi_ted_indisponivel_sem_login_quando_desabilitado(app):
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_ted
        sistema.bi_ted = 0
        db.session.commit()
    try:
        with app.test_client() as client_sem_sessao:
            resp = client_sem_sessao.get('/ted/bi_ted')
            assert resp.status_code == 200
            assert 'indispon' in resp.get_data(as_text=True).lower()
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_ted = original
            db.session.commit()


def test_percentual_curadoria_calculado_corretamente(app):
    with app.app_context():
        _programa(93200, unidade='CURATESTE')
        _plano(93201, 93200, 'BICURA001')
        _plano(93202, 93200, 'BICURA002')

        if not Programa_CNPq.query.filter_by(COD_PROGRAMA='BITEDTESTE01').first():
            db.session.add(Programa_CNPq('BITEDTESTE01', 'Programa CNPq Teste BI TED', 'PCBT', 'DPI'))
            db.session.commit()
        programa_cnpq = Programa_CNPq.query.filter_by(COD_PROGRAMA='BITEDTESTE01').first()

        services.vincular_programa_cnpq(
            id_plano_acao=93201, id_programa_cnpq=programa_cnpq.ID_PROGRAMA,
            tipo_evidencia='nome_literal', usuario_id=1,
        )

        dados = services.bi_ted({'orgao': 'CURATESTE'})
        assert dados['quantidade_total'] == 2
        assert dados['vinculados'] == 1
        assert dados['percentual_curadoria'] == 50


def test_valor_por_orgao_agregado_corretamente(app):
    with app.app_context():
        _programa(93300, unidade='ORGAOA_BITESTE')
        _programa(93301, unidade='ORGAOB_BITESTE')
        _plano(93302, 93300, 'BIORGAO001', valor=100000.0)
        _plano(93303, 93300, 'BIORGAO002', valor=50000.0)
        _plano(93304, 93301, 'BIORGAO003', valor=200000.0)

        dados = services.bi_ted()
        por_orgao = {o['orgao']: o for o in dados['orgaos']}

        assert por_orgao['ORGAOA_BITESTE']['qtd'] == 2
        assert por_orgao['ORGAOA_BITESTE']['valor'] == 150000.0
        assert por_orgao['ORGAOB_BITESTE']['qtd'] == 1
        assert por_orgao['ORGAOB_BITESTE']['valor'] == 200000.0


def test_link_bi_ted_aparece_no_menu_sem_login_quando_habilitado(client, app):
    # Sistema é linha única persistente (banco de dev) — força o estado em
    # vez de assumir, e restaura ao final (mesmo cuidado já aplicado em
    # tests/test_users_config_sistema.py).
    with app.app_context():
        sistema = Sistema.query.first()
        original = sistema.bi_ted
        sistema.bi_ted = 1
        db.session.commit()
    try:
        resp = client.get('/')
        assert 'BI TED' in resp.get_data(as_text=True)
    finally:
        with app.app_context():
            sistema = Sistema.query.first()
            sistema.bi_ted = original
            db.session.commit()
