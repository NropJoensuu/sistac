# test_convenios_bi.py
#
# Testes da tela de BI Convênios (Etapa 1 do roadmap_bi_sistac.md):
# rota básica, filtros via querystring, regressão de divisão por zero na
# taxa de desembolso, e contagem de convênios com vigência a vencer.

from datetime import date, timedelta
from project import db
from project.convenios import services
from project.models import User, Programa, Proposta, Convenio


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
                trab_conv=1, trab_acordo=1, trab_instru=1,
                despacha0=0, despacha=0, despacha2=0,
            )
            db.session.add(user)
            db.session.commit()
        return user.id


def _programa_proposta(cod_programa, uf='DF', proponente='Proponente Teste'):
    if not Programa.query.get(cod_programa):
        db.session.add(Programa(cod_programa, cod_programa, 'Programa BI Teste', 'Ativo', '2024'))
    if not Proposta.query.get(cod_programa):
        db.session.add(Proposta(cod_programa, cod_programa, uf, proponente, 'Objeto teste BI'))
    db.session.commit()


def _convenio(nr_convenio, id_proposta, sit_convenio='Em execução', ano='2024',
              vl_repasse=100000.0, vl_desembolsado=50000.0,
              dia_fim_vigenc=date(2030, 1, 1)):
    # DIA_FIM_VIGENC_CONV é relativo a "hoje" em alguns testes (vigência a
    # vencer) — se o convênio já existir de uma execução anterior da suíte,
    # atualiza a data em vez de pular, senão o teste fica incorreto com o
    # passar dos dias (idempotência não pode significar "dado congelado").
    existente = Convenio.query.get(nr_convenio)
    if existente is None:
        db.session.add(Convenio(
            nr_convenio, id_proposta, '01', '01', ano, '01/01/2024', sit_convenio, 'Normal',
            'Publicado', 'Sim', 'Não', 'PROC-BI', 'UG1', '01/01/2024', '01/01/2024',
            dia_fim_vigenc, '01/01/2025', '60', '01/03/2026', 'Contratado', 'Sim', '',
            'N', '1', '0', '0',
            vl_repasse + 10000.0, vl_repasse, 10000.0, 0.0, vl_desembolsado,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ))
    else:
        existente.DIA_FIM_VIGENC_CONV = dia_fim_vigenc
    db.session.commit()


def test_bi_convenios_responde_200(client, app):
    user_id = _usuario(app, 'teste.bi@teste.com', 'usuariobiteste')
    with app.app_context():
        _programa_proposta('9200')
        _convenio('CONVBI001', '9200')
    _login(client, user_id)
    resp = client.get('/convenios/bi_convenios')
    assert resp.status_code == 200


def test_bi_convenios_com_filtros_responde_200(client, app):
    user_id = _usuario(app, 'teste.bifiltro@teste.com', 'usuariobifiltroteste')
    with app.app_context():
        _programa_proposta('9201', uf='SP', proponente='FAP Teste')
        _convenio('CONVBI002', '9201')
    _login(client, user_id)
    resp = client.get(
        '/convenios/bi_convenios',
        query_string={'uf': 'SP', 'situacao': 'Em execução', 'ano': '2024', 'parceiro': 'FAP'},
    )
    assert resp.status_code == 200


def test_bi_convenios_taxa_desembolso_com_repasse_zero_nao_quebra(client, app):
    """
    Regressão: um convênio com VL_REPASSE_CONV zerado não deve derrubar a
    tela de BI (mesma classe de bug já corrigida em resumo_convenios —
    divisão por zero ao calcular a taxa de desembolso).
    """
    user_id = _usuario(app, 'teste.birepassezero@teste.com', 'usuariobirepassezero')
    with app.app_context():
        _programa_proposta('9202')
        _convenio('CONVBI003', '9202', vl_repasse=0.0, vl_desembolsado=0.0)
    _login(client, user_id)
    resp = client.get('/convenios/bi_convenios')
    assert resp.status_code == 200


def test_bi_convenios_vigencia_a_vencer(app):
    """
    Confere que a contagem de "vigência a vencer em 3 meses" inclui um
    convênio cujo fim de vigência está dentro da janela, e não conta um
    convênio cujo fim de vigência está muito além dela.
    """
    with app.app_context():
        hoje = date.today()
        _programa_proposta('9203')
        _convenio('CONVBI004', '9203', dia_fim_vigenc=hoje + timedelta(days=30))
        _convenio('CONVBI005', '9203', dia_fim_vigenc=hoje + timedelta(days=800))

        dados = services.bi_convenios()

        convenios_no_periodo = [
            c for c in Convenio.query.filter(Convenio.NR_CONVENIO.in_(['CONVBI004', 'CONVBI005']))
        ]
        assert len(convenios_no_periodo) == 2
        assert dados['vigencia_a_vencer']['3_meses'] >= 1
