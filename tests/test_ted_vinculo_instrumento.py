# test_ted_vinculo_instrumento.py
#
# Testes do vínculo N:N entre TED e Acordo/Convênio (itens A6/B14/C6 do
# backlog pós-BI, tratados como um bloco único — as três pontas do mesmo
# relacionamento). TED_Vinculo_Instrumento já suportava N:N no modelo,
# mas a lógica que o usava assumia 1:1 em dois lugares:
#
# 1. vincular_instrumento() buscava um vínculo existente por
#    id_plano_acao e sobrescrevia — um TED podia financiar só 1
#    Acordo/Convênio, quando na prática pode financiar até 27 (Igor).
# 2. listar_teds() guardava instrumentos_vinculados como um dict
#    {id_plano_acao: vinculo}, descartando silenciosamente qualquer
#    vínculo além do primeiro.
#
# Também cobre a decisão de Igor de vincular só a partir da tela de
# Acordo/Convênio, nunca da tela de TED (a antiga rota
# /ted/<id>/vincula_instrumento foi removida por virar código morto).

from datetime import date

from project import db
from project.ted import services
from project.models import (
    User, Acordo, Convenio, Programa, Proposta,
    TED_Programa, TED_PlanoAcao, TED_Vinculo_Instrumento,
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
            # usuário criado em execução anterior da suíte, antes de trab_ted
            # existir (banco de dev persistente) — sem isso a rota de TED
            # devolveria 403.
            user.trab_ted = 1
            db.session.commit()
        return user.id


def _programa_ted(id_programa=95000):
    if not TED_Programa.query.get(id_programa):
        db.session.add(TED_Programa(
            id=id_programa, codigo_programa='TESTEVIN', nome='Programa Teste Vinculo',
            unidade_descentralizadora='MCTI', ano='2026',
        ))
        db.session.commit()


def _plano_ted(id_plano, numero_ted, id_programa=95000):
    _programa_ted(id_programa)
    if not TED_PlanoAcao.query.get(id_plano):
        db.session.add(TED_PlanoAcao(
            id=id_plano, numero_ted=numero_ted, id_programa=id_programa,
            unidade_descentralizada='CNPq', situacao_plano='APROVADO',
            objeto='Objeto de teste de vínculo TED', valor_beneficiario_especifico=100000.0,
            valor_chamamento_publico=0.0, vigencia_inicio=None, vigencia_fim=None,
            ano='2026',
        ))
        db.session.commit()
    return id_plano


def _acordo_teste(sei, nome):
    acordo = Acordo.query.filter_by(sei=sei).first()
    if acordo is None:
        acordo = Acordo(
            nome=nome, desc='teste', sei=sei, epe='EPE Teste', uf='DF',
            data_inicio=date(2024, 1, 1), data_fim=date(2026, 12, 31),
            valor_cnpq=100000.0, valor_epe=0.0, unidade_cnpq='DPI', situ='Assinado',
            capital=0.0, custeio=0.0, bolsas=100000.0, siafi='000',
        )
        db.session.add(acordo)
        db.session.commit()
    return acordo.id


def _convenio_teste(nr_convenio, id_programa='9500'):
    if not Programa.query.get(id_programa):
        db.session.add(Programa(id_programa, id_programa, 'Programa Teste Vinculo TED', 'Ativo', '2024'))
    if not Proposta.query.get(id_programa):
        db.session.add(Proposta(id_programa, id_programa, 'DF', 'Proponente Teste Vinculo TED', 'Objeto teste'))
    db.session.commit()

    if not Convenio.query.get(nr_convenio):
        db.session.add(Convenio(
            nr_convenio, id_programa, '01', '01', '2024', '01/01/2024', 'Em execução', 'Normal',
            'Publicado', 'Sim', 'Não', 'PROC001', 'UG1', '01/01/2024', '01/01/2024',
            date(2025, 12, 31), '01/01/2025', '60', '01/03/2026', 'Contratado', 'Sim', '',
            'N', '1', '0', '0',
            100000.0, 90000.0, 10000.0, 50000.0, 20000.0, 0.0, 0.0, 500.0, 0.0, 0.0, 90000.0,
        ))
        db.session.commit()
    return nr_convenio


def test_vincular_instrumento_duas_vezes_cria_duas_linhas_nao_sobrescreve(app):
    """Regressão do bug real: a versão antiga sobrescrevia o vínculo por id_plano_acao."""
    with app.app_context():
        user_id = _usuario(app, 'teste.vincinstr@teste.com', 'usuariovincinstrteste')
        id_plano = _plano_ted(95101, '950101')
        acordo_1 = _acordo_teste('00000.000000/2025-01', 'Acordo Teste Vinculo 1')
        acordo_2 = _acordo_teste('00000.000000/2025-02', 'Acordo Teste Vinculo 2')

        TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()

        services.vincular_instrumento(id_plano, 'acordo', None, acordo_1, user_id)
        services.vincular_instrumento(id_plano, 'acordo', None, acordo_2, user_id)

        vinculos = TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).all()
        assert len(vinculos) == 2
        assert {v.id_acordo for v in vinculos} == {acordo_1, acordo_2}


def test_listar_teds_com_ted_vinculado_a_dois_acordos_retorna_os_dois(app):
    """Regressão do bug real: listar_teds() guardava só 1 vínculo por TED (dict), descartando os demais."""
    with app.app_context():
        user_id = _usuario(app, 'teste.listavinc@teste.com', 'usuariolistavincteste')
        id_plano = _plano_ted(95102, '950102')
        acordo_1 = _acordo_teste('00000.000000/2025-03', 'Acordo Teste Vinculo 3')
        acordo_2 = _acordo_teste('00000.000000/2025-04', 'Acordo Teste Vinculo 4')

        TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()

        services.vincular_instrumento(id_plano, 'acordo', None, acordo_1, user_id)
        services.vincular_instrumento(id_plano, 'acordo', None, acordo_2, user_id)

        item = [i for i in services.listar_teds() if i['plano'].id == id_plano][0]
        assert len(item['instrumentos']) == 2
        assert any('00000.000000/2025-03' in r for r in item['instrumentos'])
        assert any('00000.000000/2025-04' in r for r in item['instrumentos'])


def test_desvincular_instrumento_remove_so_o_vinculo_indicado(app):
    with app.app_context():
        user_id = _usuario(app, 'teste.desvinc@teste.com', 'usuariodesvincteste')
        id_plano = _plano_ted(95103, '950103')
        acordo_1 = _acordo_teste('00000.000000/2025-05', 'Acordo Teste Vinculo 5')
        acordo_2 = _acordo_teste('00000.000000/2025-06', 'Acordo Teste Vinculo 6')

        TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()

        services.vincular_instrumento(id_plano, 'acordo', None, acordo_1, user_id)
        services.vincular_instrumento(id_plano, 'acordo', None, acordo_2, user_id)

        vinculos = TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).all()
        assert len(vinculos) == 2
        alvo = [v for v in vinculos if v.id_acordo == acordo_1][0]

        services.desvincular_instrumento(alvo.id, user_id)

        restantes = TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).all()
        assert len(restantes) == 1
        assert restantes[0].id_acordo == acordo_2


def test_tela_acordo_vincula_ted_aparece_e_desvincula_some(client, app):
    """Fluxo completo pela tela de Acordo (item C6) — vincular só é feito a partir daqui, nunca do TED."""
    with app.app_context():
        user_id = _usuario(app, 'teste.telaacordovinc@teste.com', 'usuariotelaacordovincteste')
        id_plano = _plano_ted(95104, '950104')
        acordo_id = _acordo_teste('00000.000000/2025-07', 'Acordo Teste Vinculo Tela')

        TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano, id_acordo=acordo_id).delete()
        db.session.commit()

    _login(client, user_id)

    resp = client.post(f'/acordos/{acordo_id}/vincula_ted', data={'id_plano_acao': id_plano}, follow_redirects=True)
    assert resp.status_code == 200
    assert 'TED 950104'.encode() in resp.data

    with app.app_context():
        vinculo = TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano, id_acordo=acordo_id).first()
        assert vinculo is not None
        id_vinculo = vinculo.id

    resp = client.post(f'/acordos/{acordo_id}/{id_vinculo}/desvincula_ted', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert TED_Vinculo_Instrumento.query.get(id_vinculo) is None


def test_tela_convenio_vincula_ted_aparece_e_desvincula_some(client, app):
    """Mesmo fluxo, agora pela tela de Convênio (item B14)."""
    with app.app_context():
        user_id = _usuario(app, 'teste.telaconvvinc@teste.com', 'usuariotelaconvvincteste')
        id_plano = _plano_ted(95105, '950105')
        nr_convenio = _convenio_teste('CONVTESTEVINC01')

        TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano, nr_convenio=nr_convenio).delete()
        db.session.commit()

    _login(client, user_id)

    resp = client.post(f'/convenios/{nr_convenio}/vincula_ted', data={'id_plano_acao': id_plano}, follow_redirects=True)
    assert resp.status_code == 200
    assert 'TED 950105'.encode() in resp.data

    with app.app_context():
        vinculo = TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano, nr_convenio=nr_convenio).first()
        assert vinculo is not None
        id_vinculo = vinculo.id

    resp = client.post(f'/convenios/{nr_convenio}/{id_vinculo}/desvincula_ted', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert TED_Vinculo_Instrumento.query.get(id_vinculo) is None


def test_gestao_ted_sem_link_de_vincular_e_com_badges_multiplos(client, app):
    """
    Decisão de Igor: a tela de Gestão de TED não oferece mais o caminho de
    vincular (só leitura, badges) — e múltiplos instrumentos aparecem
    todos, não só o primeiro (bug real corrigido em listar_teds()).
    """
    with app.app_context():
        user_id = _usuario(app, 'teste.gestaobadges@teste.com', 'usuariogestaobadgesteste')
        id_plano = _plano_ted(95106, '950106')
        acordo_1 = _acordo_teste('00000.000000/2025-08', 'Acordo Teste Badge 1')
        acordo_2 = _acordo_teste('00000.000000/2025-09', 'Acordo Teste Badge 2')

        TED_Vinculo_Instrumento.query.filter_by(id_plano_acao=id_plano).delete()
        db.session.commit()

        services.vincular_instrumento(id_plano, 'acordo', None, acordo_1, user_id)
        services.vincular_instrumento(id_plano, 'acordo', None, acordo_2, user_id)

    _login(client, user_id)
    resp = client.get('/ted/gestao', query_string={'busca': '950106'})
    assert resp.status_code == 200
    assert b'vincula_instrumento' not in resp.data
    assert b'00000.000000/2025-08' in resp.data
    assert b'00000.000000/2025-09' in resp.data
