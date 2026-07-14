"""
.. topic:: Users (services) — Autenticação, registro e senha

    Camada de regra de negócio do grupo de autenticação do módulo de
    usuários: registro, confirmação de e-mail, login, logout e troca
    de senha. Sem dependência de objetos de request/response do Flask
    (redirect, flash) — as rotas (views.py) decidem o que fazer com o
    resultado retornado por estas funções.

    Cada função de fluxo (registrar_usuario, confirmar_email, etc.)
    retorna um status textual em vez de manipular a resposta HTTP
    diretamente, permitindo que a view decida a mensagem exibida ao
    usuário e para onde redirecionar.
"""

from threading import Thread
from datetime import datetime, date, timedelta, time
from calendar import monthrange
from collections import Counter

from itsdangerous import URLSafeTimedSerializer
from flask import url_for, render_template
from flask_mail import Message
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from sqlalchemy.sql import label

from project import db, mail, app, sched
from project.models import User, Coords, Sistema, Demanda, Providencia, Despacho, Log_Auto, Plano_Trabalho, Ativ_Usu, RefSICONV, Log_Desc, Msgs_Recebidas
from project.demandas.views import registra_log_auto
from project.core.views import cargaSICONV, chamadas_DW


# --- envio de e-mail ---

def send_async_email(msg):
    """Executa o envio de e-mails de forma assíncrona."""
    with app.app_context():
        mail.send(msg)


def send_email(subject, recipients, text_body, html_body):
    """Envia e-mails em uma thread separada."""
    msg = Message(subject, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    thr = Thread(target=send_async_email, args=[msg])
    thr.start()


def send_confirmation_email(user_email):
    """Prepara e envia o e-mail de confirmação de registro."""
    confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    confirm_url = url_for(
        'users.confirm_email',
        token=confirm_serializer.dumps(user_email, salt='email-confirmation-salt'),
        _external=True)

    html = render_template('email_confirmation.html', confirm_url=confirm_url)

    send_email('Confirme seu endereço de e-mail', [user_email], '', html)


def send_password_reset_email(user_email):
    """Prepara e envia o e-mail com token de troca de senha."""
    password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

    password_reset_url = url_for(
        'users.reset_with_token',
        token=password_reset_serializer.dumps(user_email, salt='password-reset-salt'),
        _external=True)

    html = render_template('email_senha_atualiza.html', password_reset_url=password_reset_url)

    send_email('Atualização de senha solicitada', [user_email], '', html)


# --- registro ---

def registrar_usuario(email, username, password, coord, despacha0, despacha, despacha2):
    """
    Cria um novo usuário, definindo seu papel (admin, se for o primeiro
    usuário do sistema), garante o registro da coordenação informada e
    dispara o e-mail de confirmação. Retorna o usuário criado.
    """
    qtd_users = db.session.query(func.count(User.id)).first()

    if qtd_users[0] != 0:
        version = db.session.query(User.sversion).first()
        role_user = 'user'
    else:
        version = [1]
        role_user = 'admin'

    trab_conv = db.session.query(Sistema.funcionalidade_conv).first()
    trab_acordo = db.session.query(Sistema.funcionalidade_acordo).first()
    trab_instru = db.session.query(Sistema.funcionalidade_instru).first()

    user = User(
        email=email,
        username=username,
        plaintext_password=password,
        despacha0=1 if despacha0 else 0,
        despacha=1 if despacha else 0,
        despacha2=1 if despacha2 else 0,
        coord=coord,
        role=role_user,
        email_confirmation_sent_on=datetime.now(),
        ativo=0,
        sversion=version[0],
        cargo_func='a definir',
        trab_conv=trab_conv[0],
        trab_acordo=trab_acordo[0],
        trab_instru=trab_instru[0],
    )

    db.session.add(user)
    db.session.commit()

    last_id = db.session.query(User.id).order_by(User.id.desc()).first()
    registra_log_auto(last_id[0], None, 'usu')

    coords = db.session.query(Coords.sigla).all()
    if (coord,) not in coords:
        nova_coord = Coords(sigla=coord, pai='')
        db.session.add(nova_coord)
        db.session.commit()

    send_confirmation_email(user.email)

    return user


def confirmar_email(token):
    """
    Valida o token de confirmação de e-mail e marca o usuário como
    confirmado.

    Retorna uma tupla (status, user), onde status é um dos:
    'invalido', 'ja_confirmado', 'confirmado'.
    """
    try:
        confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = confirm_serializer.loads(token, salt='email-confirmation-salt', max_age=3600)
    except Exception:
        return 'invalido', None

    user = User.query.filter_by(email=email).first()

    if user.email_confirmed == 1:
        return 'ja_confirmado', user

    user.email_confirmed = 1
    user.email_confirmed_on = datetime.now()
    db.session.commit()

    return 'confirmado', user


# --- troca de senha ---

def solicitar_reset_senha(email):
    """
    Envia o e-mail de troca de senha, se o e-mail existir e estiver
    confirmado.

    Retorna um dos status: 'nao_encontrado', 'nao_confirmado', 'enviado'.
    """
    user = User.query.filter_by(email=email).first()

    if user is None:
        return 'nao_encontrado'

    if user.email_confirmed != 1:
        return 'nao_confirmado'

    send_password_reset_email(user.email)
    return 'enviado'


def redefinir_senha_com_token(token, nova_senha):
    """
    Valida o token de troca de senha e define a nova senha.

    Retorna uma tupla (status, user), onde status é um dos:
    'token_invalido', 'usuario_invalido', 'atualizada'.
    """
    try:
        password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = password_reset_serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        return 'token_invalido', None

    user = User.query.filter_by(email=email).first()
    if user is None:
        return 'usuario_invalido', None

    user.password_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
    db.session.commit()

    registra_log_auto(user.id, None, 'sen')

    return 'atualizada', user


def trocar_senha(usuario, senha_atual, nova_senha):
    """
    Troca a senha do usuário logado, validando a senha atual.

    Retorna um dos status: 'inativo', 'senha_incorreta', 'trocada'.
    """
    if usuario.ativo != 1:
        return 'inativo'

    if not usuario.check_password(senha_atual):
        return 'senha_incorreta'

    usuario.password_hash = generate_password_hash(nova_senha, method='pbkdf2:sha256')
    db.session.commit()

    registra_log_auto(usuario.id, None, 'sen')

    return 'trocada'


# --- login ---

def autenticar(email, senha):
    """
    Verifica as credenciais de login e, se corretas, atualiza os
    campos de último acesso.

    Retorna uma tupla (status, user), onde status é um dos:
    'nao_encontrado', 'senha_incorreta', 'nao_confirmado', 'autenticado'.
    """
    user = User.query.filter_by(email=email).first()

    if user is None:
        return 'nao_encontrado', None

    if not user.check_password(senha):
        return 'senha_incorreta', None

    if user.email_confirmed != 1:
        return 'nao_confirmado', None

    user.last_logged_in = user.current_logged_in
    user.current_logged_in = datetime.now()
    db.session.commit()

    return 'autenticado', user


# =============================================================================
# Perfil / conta
# =============================================================================

def atualizar_perfil(usuario, username, email):
    """Atualiza nome de usuário e e-mail do próprio usuário logado."""
    usuario.username = username
    usuario.email = email

    db.session.commit()

    registra_log_auto(usuario.id, None, 'usu')


def calcular_estatisticas_conta(user_id, hoje):
    """
    Calcula as estatísticas exibidas na tela de conta do usuário:
    quantidade de demandas, taxa de conclusão, tempo médio de vida das
    demandas, prazo médio de despacho, e médias mensais/semanais de
    dedicação. Retorna um dicionário pronto para popular o template.
    """
    user_demandas = db.session.query(Demanda.user_id, func.count(Demanda.user_id))\
                              .filter(Demanda.user_id == user_id)\
                              .group_by(Demanda.user_id).first()

    qtd_demandas = user_demandas[1] if user_demandas else 0

    user_demandas_conclu = db.session.query(Demanda.user_id, func.count(Demanda.user_id))\
                                     .filter(Demanda.user_id == user_id, Demanda.conclu == '1')\
                                     .group_by(Demanda.user_id).first()

    qtd_demandas_conclu = user_demandas_conclu[1] if user_demandas_conclu else 0

    if qtd_demandas != 0:
        percent_conclu = round((qtd_demandas_conclu / qtd_demandas) * 100)
    else:
        percent_conclu = 0

    demandas_datas = db.session.query(Demanda.data, Demanda.data_conclu)\
                                .filter(Demanda.conclu == '1', Demanda.data_conclu != None, Demanda.user_id == user_id)

    vida = 0
    for dia in demandas_datas:
        vida += (dia.data_conclu - dia.data).days

    if len(list(demandas_datas)) > 0:
        vida_m = round(vida / len(list(demandas_datas)))
    else:
        vida_m = 0

    despachos = db.session.query(label('c_data', Despacho.data), Despacho.demanda_id, Demanda.id, label('i_data', Demanda.data))\
                          .outerjoin(Demanda, Despacho.demanda_id == Demanda.id)\
                          .filter(Demanda.user_id == user_id)\
                          .all()

    desp = 0
    for despacho in despachos:
        desp += (despacho.c_data - despacho.i_data).days

    if len(list(despachos)) > 0:
        desp_m = round(desp / len(list(despachos)))
    else:
        desp_m = 0

    meses = []
    for i in range(12):
        m = hoje.month - i - 1
        y = hoje.year
        if m < 1:
            m += 12
            y -= 1
        if m >= 0 and m < 10:
            m = '0' + str(m)
        meses.append((str(m), str(y)))

    demandas_12meses = [Demanda.query.filter(Demanda.data >= mes[1] + '-' + mes[0] + '-01',
                                             Demanda.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Demanda.user_id == user_id).count()
                                             for mes in meses]

    med_dm = round(sum(demandas_12meses) / len(demandas_12meses))
    max_dm = max(demandas_12meses)
    mes_max_dm = meses[demandas_12meses.index(max_dm)]
    min_dm = min(demandas_12meses)
    mes_min_dm = meses[demandas_12meses.index(min_dm)]

    providencias_12meses = [Providencia.query.filter(Providencia.data >= mes[1] + '-' + mes[0] + '-01',
                                             Providencia.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Providencia.user_id == user_id).count()
                                             for mes in meses]

    med_pr = round(sum(providencias_12meses) / len(providencias_12meses))
    max_pr = max(providencias_12meses)
    mes_max_pr = meses[providencias_12meses.index(max_pr)]
    min_pr = min(providencias_12meses)
    mes_min_pr = meses[providencias_12meses.index(min_pr)]

    minutos_dedicados_12meses = [db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= mes[1] + '-' + mes[0] + '-01',
                                             Providencia.data <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Providencia.user_id == user_id).all()
                                             for mes in meses]

    minutos_log_man_12meses = [db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= mes[1] + '-' + mes[0] + '-01',
                                             Log_Auto.data_hora <= mes[1] + '-' + mes[0] + '-' + str(monthrange(int(mes[1]), int(mes[0]))[1]),
                                             Log_Auto.user_id == user_id).all()
                                             for mes in meses]

    hd_p = [minu[0][0] if minu[0][0] is not None else 0 for minu in minutos_dedicados_12meses]
    hd_l = [minu[0][0] if minu[0][0] is not None else 0 for minu in minutos_log_man_12meses]
    hd_z = zip(hd_p, hd_l)
    hd = [x + y for (x, y) in hd_z]

    med_hd = round((sum(hd) / len(hd)) / 60)
    max_hd = round(max(hd) / 60)
    mes_max_hd = meses[hd.index(max(hd))]
    min_hd = round(min(hd) / 60)
    mes_min_hd = meses[hd.index(min(hd))]

    start = hoje - timedelta(days=hoje.weekday())
    end = start + timedelta(days=6)

    minutos_dedicados_semana_p = db.session.query(func.sum(Providencia.duracao)).filter(Providencia.data >= start,
                                             Providencia.data <= end,
                                             Providencia.user_id == user_id).all()

    minutos_dedicados_semana_l = db.session.query(func.sum(Log_Auto.duracao)).filter(Log_Auto.data_hora >= start,
                                          Log_Auto.data_hora <= end,
                                          Log_Auto.user_id == user_id).all()

    md_p = minutos_dedicados_semana_p[0][0]
    md_l = minutos_dedicados_semana_l[0][0]

    if md_p is None:
        md_p = 0

    if md_l is None:
        md_l = 0

    horas_dedicadas_semana = round((md_p + md_l) / 60)

    return {
        'qtd_demandas': qtd_demandas,
        'qtd_demandas_conclu': qtd_demandas_conclu,
        'percent_conclu': percent_conclu,
        'vida_m': vida_m,
        'desp_m': desp_m,
        'med_dm': med_dm,
        'max_dm': max_dm,
        'mes_max_dm': mes_max_dm,
        'min_dm': min_dm,
        'mes_min_dm': mes_min_dm,
        'med_pr': med_pr,
        'max_pr': max_pr,
        'mes_max_pr': mes_max_pr,
        'min_pr': min_pr,
        'mes_min_pr': mes_min_pr,
        'med_hd': med_hd,
        'max_hd': max_hd,
        'mes_max_hd': mes_max_hd,
        'min_hd': min_hd,
        'mes_min_hd': mes_min_hd,
        'horas': horas_dedicadas_semana,
    }


_CAMPOS_DEMANDA_BASE = [
    Demanda.id, Demanda.programa, Demanda.sei, Demanda.convênio,
    Demanda.ano_convênio, Demanda.tipo, Demanda.data, Demanda.user_id,
    Demanda.titulo, Demanda.desc, Demanda.necessita_despacho, Demanda.conclu,
    Demanda.data_conclu, Demanda.necessita_despacho_cg, Demanda.urgencia,
    Demanda.data_env_despacho, Demanda.nota, Plano_Trabalho.atividade_sigla,
]


def listar_demandas_usuario(username, filtro):
    """
    Retorna as demandas de um usuário (ou de todos, se username='todos'),
    filtradas por: 'nc...' (não concluídas), 'conclu' (concluídas), ou
    qualquer outro valor (todas). Retorna um dicionário pronto para o
    template user_demandas.html.
    """
    com_despacho_novo = []
    com_despacho_novo_data = {}
    para_despacho = []
    com_usu = []

    if username == 'todos':
        user_id = '%'
        user = None
    else:
        user = User.query.filter_by(username=username).first_or_404()
        user_id = user.id

    if filtro[0:2] == 'nc':
        campos = _CAMPOS_DEMANDA_BASE + [Demanda.data_verific]
        query = db.session.query(*campos).outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)

        if user_id == '%':
            demandas = query.filter(Demanda.conclu == '0')\
                            .order_by(Demanda.urgencia, Demanda.data.desc()).all()
        else:
            demandas = query.filter(Demanda.user_id == user_id, Demanda.conclu == '0')\
                            .order_by(Demanda.urgencia, Demanda.data.desc()).all()

        for demanda in demandas:
            providencias = db.session.query(Providencia.data, label('tipo', 'PROV - ' + Providencia.texto))\
                                            .filter(Providencia.demanda_id == demanda.id)\
                                            .order_by(Providencia.data.desc()).all()

            despachos = db.session.query(Despacho.data, label('tipo', 'DESP - ' + Despacho.texto))\
                                        .filter_by(demanda_id=demanda.id)\
                                        .order_by(Despacho.data.desc()).all()

            pro_des = providencias + despachos
            pro_des.sort(key=lambda ordem: ordem.data, reverse=True)

            if pro_des != []:
                if pro_des[0].tipo[0:6] == 'DESP -':
                    com_despacho_novo.append(demanda.id)
                    com_despacho_novo_data[demanda.id] = pro_des[0].data

            if demanda.necessita_despacho == 1 or demanda.necessita_despacho_cg == 1:
                para_despacho.append(demanda.id)

            if demanda.id not in com_despacho_novo and demanda.necessita_despacho == 0 and demanda.necessita_despacho_cg == 0:
                com_usu.append(demanda.id)

    elif filtro == 'conclu':
        query = db.session.query(*_CAMPOS_DEMANDA_BASE).outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)

        if user_id == '%':
            demandas = query.filter(Demanda.conclu != '0').order_by(Demanda.data_conclu.desc()).all()
        else:
            demandas = query.filter(Demanda.user_id == user_id, Demanda.conclu != '0')\
                            .order_by(Demanda.data_conclu.desc()).all()

    else:
        query = db.session.query(*_CAMPOS_DEMANDA_BASE).outerjoin(Plano_Trabalho, Plano_Trabalho.id == Demanda.programa)

        if user_id == '%':
            demandas = query.order_by(Demanda.urgencia, Demanda.data.desc()).all()
        else:
            demandas = query.filter(Demanda.user_id == user_id)\
                            .order_by(Demanda.urgencia, Demanda.data.desc()).all()

    return {
        'demandas': demandas,
        'user': user,
        'filtro': filtro,
        'qtd': len(demandas),
        'com_despacho_novo': com_despacho_novo,
        'qtd_cdn': len(com_despacho_novo),
        'qtd_pdes': len(para_despacho),
        'qtd_com_usu': len(com_usu),
        'com_despacho_novo_data': com_despacho_novo_data,
    }


def plano_trabalho_usuario(user_id):
    """
    Retorna as atividades do plano de trabalho de um usuário, separadas
    entre Titular e Suplente, com a carga horária total de cada grupo.
    """
    user = User.query.get_or_404(user_id)

    atividades_1 = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla,
                                    Plano_Trabalho.atividade_desc, Plano_Trabalho.natureza,
                                    Plano_Trabalho.meta)\
                                    .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                    .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Titular')\
                                    .order_by(Plano_Trabalho.natureza, Plano_Trabalho.atividade_sigla).all()

    carga_1 = db.session.query(label('total', func.sum(Plano_Trabalho.meta)))\
                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                        .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Titular').all()

    carga_1_total = 0 if (carga_1[0][0] == 0 or carga_1[0][0] is None) else carga_1[0][0]

    atividades_2 = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla,
                                    Plano_Trabalho.atividade_desc, Plano_Trabalho.natureza,
                                    Plano_Trabalho.meta)\
                                    .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                    .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Suplente')\
                                    .order_by(Plano_Trabalho.natureza, Plano_Trabalho.atividade_sigla).all()

    carga_2 = db.session.query(label('total', func.sum(Plano_Trabalho.meta)))\
                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                        .filter(Ativ_Usu.user_id == user_id, Ativ_Usu.nivel == 'Suplente').all()

    carga_2_total = 0 if (carga_2[0][0] == 0 or carga_2[0][0] is None) else carga_2[0][0]

    return {
        'user': user,
        'atividades_1': atividades_1,
        'atividades_2': atividades_2,
        'quantidade_1': len(atividades_1),
        'quantidade_2': len(atividades_2),
        'carga_1': carga_1_total,
        'carga_2': carga_2_total,
    }


# =============================================================================
# Administração
# =============================================================================

def listar_usuarios():
    """Lista todos os usuários cadastrados, ordenados por ID."""
    return User.query.order_by(User.id).all()


def dados_config_sistema():
    """Retorna os dados atuais de configuração geral do sistema."""
    users = listar_usuarios()
    sistema = Sistema.query.first()
    inst = RefSICONV.query.first()
    return users, sistema, inst


def atualizar_config_sistema(ver, nome_sistema, descritivo, funcionalidade_conv,
                              funcionalidade_acordo, funcionalidade_instru,
                              cod_inst, carga_auto, usuario_id):
    """
    Atualiza a versão do sistema para todos os usuários, os dados gerais
    do Sistema, o código da instituição no SICONV, e agenda/cancela as
    cargas automáticas (SICONV e DW) conforme o parâmetro carga_auto.
    """
    users = listar_usuarios()
    sistema = Sistema.query.first()
    inst = RefSICONV.query.first()

    for user in users:
        user.sversion = ver
        if not funcionalidade_conv:
            user.trab_conv = 0
        if not funcionalidade_acordo:
            user.trab_acordo = 0
        if not funcionalidade_instru:
            user.trab_instru = 0

    db.session.commit()

    sistema.nome_sistema = nome_sistema
    sistema.descritivo = descritivo
    sistema.funcionalidade_conv = '1' if funcionalidade_conv else '0'
    sistema.funcionalidade_acordo = '1' if funcionalidade_acordo else '0'
    sistema.funcionalidade_instru = '1' if funcionalidade_instru else '0'
    inst.cod_inst = cod_inst

    id_1 = 'carga_siconv'
    id_2 = 'carga_chamadas_DW'

    if carga_auto:
        sistema.carga_auto = '1'

        # VERIFICA E, SE FOR O CASO, AGENDA CARGA SICONV
        try:
            job_existente = sched.get_job(id_1)
            executa = not job_existente
        except Exception:
            executa = True

        if executa:
            dia_semana = 'mon-fri'
            hora = 8
            minuto = 13
            msg = ('*** Agendamento acionado ' + id_1 + ', rodando ' + dia_semana + ', às ' + str(hora) + ':' + str(minuto) + ' ***')
            print(msg)
            try:
                sched.add_job(trigger='cron', id=id_1, func=cargaSICONV, day_of_week=dia_semana, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
                sched.start()
            except Exception:
                sched.reschedule_job(id_1, trigger='cron', day_of_week=dia_semana, hour=hora, minute=minuto)

            registra_log_auto(usuario_id, None, 'agc')

        # VERIFICA E, SE FOR O CASO, AGENDA CARGA DW
        try:
            job_existente = sched.get_job(id_2)
            executa = not job_existente
        except Exception:
            executa = True

        if executa:
            dia = '2nd tue'
            hora = 18
            minuto = 18
            msg = ('*** Agendamento inicial ' + id_2 + ', rodando ' + dia + ', às ' + str(hora) + ':' + str(minuto) + ' ***')
            print(msg)
            try:
                sched.add_job(trigger='cron', id=id_2, func=chamadas_DW, day=dia, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
                sched.start()
            except Exception:
                sched.reschedule_job(id_2, trigger='cron', day=dia, hour=hora, minute=minuto)

            registra_log_auto(usuario_id, None, 'agc')

    else:
        sistema.carga_auto = '0'
        print('*** Jobs de carga serão CANCELADOS. Não haverá cargas automáticas. ***')
        try:
            sched.remove_job(id_1)
        except Exception:
            print('*** Não há job ' + id_1 + ' para cancelar. ***')
        try:
            sched.remove_job(id_2)
        except Exception:
            print('*** Não há job ' + id_2 + ' para cancelar. ***')
        registra_log_auto(usuario_id, None, 'agx')

    registra_log_auto(usuario_id, None, 'ver')


def buscar_usuario(user_id):
    """Busca um usuário pelo ID, ou levanta 404 se não existir."""
    return User.query.get_or_404(user_id)


def coords_choices():
    """Retorna a lista de coordenações formatada para um SelectField."""
    coords = db.session.query(Coords.sigla).order_by(Coords.sigla).all()
    lista_coords = [(c[0], c[0]) for c in coords]
    lista_coords.insert(0, ('', ''))
    return lista_coords


def atualizar_usuario_admin(user_id, coord, despacha0, despacha, despacha2, ativo,
                             role, cargo_func, trab_conv, trab_acordo, trab_instru, usuario_id):
    """Atualiza os dados administrativos de um usuário (feito pelo admin)."""
    user = buscar_usuario(user_id)
    sistema = Sistema.query.first()

    user.coord = coord
    user.despacha0 = 1 if despacha0 else 0
    user.despacha = 1 if despacha else 0
    user.despacha2 = 1 if despacha2 else 0
    user.ativo = 1 if ativo else 0
    user.role = role
    user.cargo_func = cargo_func

    if sistema.funcionalidade_conv == 1:
        user.trab_conv = int(trab_conv)
    if sistema.funcionalidade_acordo == 1:
        user.trab_acordo = int(trab_acordo)
    if sistema.funcionalidade_instru == 1:
        user.trab_instru = int(trab_instru)

    db.session.commit()

    registra_log_auto(usuario_id, None, 'adm')

    return user


def listar_coords():
    """Lista todas as coordenações cadastradas."""
    return db.session.query(Coords).order_by(Coords.sigla).all()


def criar_coord(sigla, pai):
    """Registra uma nova coordenação."""
    nova_coord = Coords(sigla=sigla, pai=pai)
    db.session.add(nova_coord)
    db.session.commit()
    return nova_coord


def buscar_coord(coord_id):
    """Busca uma coordenação pelo ID, ou levanta 404 se não existir."""
    return Coords.query.get_or_404(coord_id)


def atualizar_coord(coord_id, sigla, pai):
    """Atualiza os dados de uma coordenação existente."""
    coord = buscar_coord(coord_id)
    coord.sigla = sigla
    coord.pai = pai
    db.session.commit()
    return coord


def listar_tipos_log():
    """Lista todos os tipos de log cadastrados."""
    return db.session.query(Log_Desc).order_by(Log_Desc.tipo_registro).all()


def criar_tipo_log(tipo, desc):
    """Registra um novo tipo de log."""
    novo_tipo = Log_Desc(tipo_registro=tipo, desc_registro=desc)
    db.session.add(novo_tipo)
    db.session.commit()
    return novo_tipo


# =============================================================================
# Atividade / log
# =============================================================================

def _is_integer(n):
    """Verifica se uma string representa um número inteiro."""
    try:
        float(n)
    except ValueError:
        return False
    else:
        return float(n).is_integer()


def resolver_usuario_alvo_log(usu, usuario_atual_id):
    """
    Resolve o filtro de usuário para a consulta de log: 'todos' vira '%'
    (sem filtro), um ID numérico é usado diretamente, e qualquer outro
    valor (ex: '*') aponta para o próprio usuário logado.
    """
    if usu == 'todos':
        return '%'
    elif _is_integer(usu):
        return usu
    return usuario_atual_id


def _query_log(user_id, data_ini, data_fim):
    """Monta a subquery de log filtrada por usuário e intervalo de datas."""
    filtros = [
        Log_Auto.data_hora >= datetime.combine(data_ini, time.min),
        Log_Auto.data_hora <= datetime.combine(data_fim, time.max),
    ]
    if user_id != '%':
        filtros.insert(0, Log_Auto.user_id == user_id)

    return db.session.query(
        Log_Auto.id, Log_Auto.data_hora, Log_Auto.demanda_id, Log_Auto.tipo_registro,
        Log_Auto.atividade, Log_Desc.desc_registro, User.username, Demanda.programa,
        label('ativ_sigla', Plano_Trabalho.atividade_sigla), Log_Auto.duracao
    ).outerjoin(Log_Desc, Log_Auto.tipo_registro == Log_Desc.tipo_registro)\
     .join(User, Log_Auto.user_id == User.id)\
     .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
     .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
     .filter(*filtros)\
     .order_by(Log_Auto.id.desc())\
     .subquery()


def _query_log_24h(user_id):
    """Monta a subquery de log das últimas 24 horas, filtrada por usuário."""
    filtros = [Log_Auto.data_hora >= (datetime.now() - timedelta(days=1))]
    if user_id != '%':
        filtros.insert(0, Log_Auto.user_id == user_id)

    return db.session.query(
        Log_Auto.id, Log_Auto.data_hora, Log_Auto.demanda_id, Log_Auto.tipo_registro,
        Log_Auto.atividade, Log_Desc.desc_registro, User.username, Demanda.programa,
        label('ativ_sigla', Plano_Trabalho.atividade_sigla), Log_Auto.duracao
    ).outerjoin(Log_Desc, Log_Auto.tipo_registro == Log_Desc.tipo_registro)\
     .join(User, Log_Auto.user_id == User.id)\
     .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
     .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
     .filter(*filtros)\
     .order_by(Log_Auto.id.desc())\
     .subquery()


def _atividades_e_agregado(log_subquery):
    """A partir de uma subquery de log, monta a lista de atividades e o agregado por tipo."""
    atividades = db.session.query(log_subquery, Plano_Trabalho.atividade_sigla)\
                           .outerjoin(Plano_Trabalho, Plano_Trabalho.id == log_subquery.c.programa)\
                           .order_by(log_subquery.c.id.desc())\
                           .all()

    l_log = [entrada.desc_registro for entrada in atividades]
    agregado = {k: v for k, v in sorted(Counter(l_log).items(), key=lambda item: item[1])}

    return atividades, agregado


def log_filtrado(user_id, data_ini, data_fim, log_part):
    """
    Retorna o log filtrado por período e tipo de registro (log_part é
    usado num LIKE sobre o tipo_registro).
    """
    log = _query_log(user_id, data_ini, data_fim)
    atividades, agregado = _atividades_e_agregado(log)
    return log, atividades, agregado


def log_ultimas_24h(user_id):
    """Retorna o log das últimas 24 horas."""
    log = _query_log_24h(user_id)
    atividades, agregado = _atividades_e_agregado(log)
    return log, atividades, agregado


def registrar_observacao_log(usuario_id, atividade_id, entrada_log, duracao):
    """Registra uma entrada manual de log ('observação') para o usuário."""
    if entrada_log == '':
        return

    reg_log = Log_Auto(
        data_hora=datetime.now(), user_id=usuario_id, demanda_id=None,
        tipo_registro='man: ' + entrada_log, atividade=atividade_id, duracao=duracao,
    )
    db.session.add(reg_log)
    db.session.commit()


def mensagens_recebidas(usuario_id):
    """
    Remove mensagens com mais de 30 dias e retorna as mensagens
    recebidas pelo usuário, mais recentes primeiro.
    """
    hoje = date.today()

    db.session.query(Msgs_Recebidas)\
             .filter(Msgs_Recebidas.data_hora < (hoje - timedelta(days=30)))\
             .delete()
    db.session.commit()

    return db.session.query(Msgs_Recebidas)\
                     .filter(Msgs_Recebidas.user_id == usuario_id)\
                     .order_by(Msgs_Recebidas.data_hora.desc()).all()


def gerar_relatorio_atividades(usuario, data_ini, data_fim):
    """
    Monta os dados do relatório de atividades de um usuário no período
    informado: plano de trabalho (Titular/Suplente) e log de ações
    executadas.
    """
    atividades_1 = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla,
                                    Plano_Trabalho.atividade_desc, Plano_Trabalho.natureza,
                                    Plano_Trabalho.meta)\
                                    .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                    .filter(Ativ_Usu.user_id == usuario.id, Ativ_Usu.nivel == 'Titular')\
                                    .order_by(Plano_Trabalho.natureza, Plano_Trabalho.atividade_sigla).all()

    quantidade_1 = len(atividades_1)

    carga_1 = db.session.query(label('total', func.sum(Plano_Trabalho.meta)))\
                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                        .filter(Ativ_Usu.user_id == usuario.id, Ativ_Usu.nivel == 'Titular').all()

    atividades_2 = db.session.query(Plano_Trabalho.id, Plano_Trabalho.atividade_sigla,
                                    Plano_Trabalho.atividade_desc, Plano_Trabalho.natureza,
                                    Plano_Trabalho.meta)\
                                    .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                                    .filter(Ativ_Usu.user_id == usuario.id, Ativ_Usu.nivel == 'Suplente')\
                                    .order_by(Plano_Trabalho.natureza, Plano_Trabalho.atividade_sigla).all()

    quantidade_2 = len(atividades_2)

    carga_2 = db.session.query(label('total', func.sum(Plano_Trabalho.meta)))\
                        .join(Ativ_Usu, Plano_Trabalho.id == Ativ_Usu.atividade_id)\
                        .filter(Ativ_Usu.user_id == usuario.id, Ativ_Usu.nivel == 'Suplente').all()

    coordenador = db.session.query(User.username, User.cargo_func, User.email)\
                            .filter(User.cargo_func == 'Coordenador(a)', User.ativo == 1,
                                    User.coord == usuario.coord).first()

    coordenador_geral = db.session.query(User.username, User.cargo_func, User.email)\
                                   .filter(User.cargo_func == 'Coordenador(a)-Geral').first()

    log = db.session.query(
        Log_Auto.id, Log_Auto.data_hora, Log_Auto.demanda_id, Log_Auto.tipo_registro,
        Log_Auto.atividade, Log_Desc.desc_registro, User.username, Demanda.programa,
        Demanda.sei, Demanda.conclu, label('ativ_sigla', Plano_Trabalho.atividade_sigla),
        Log_Auto.duracao
    ).outerjoin(Log_Desc, Log_Desc.tipo_registro == Log_Auto.tipo_registro)\
     .join(User, User.id == Log_Auto.user_id)\
     .outerjoin(Demanda, Demanda.id == Log_Auto.demanda_id)\
     .outerjoin(Plano_Trabalho, Plano_Trabalho.id == Log_Auto.atividade)\
     .filter(Log_Auto.user_id == usuario.id,
             Log_Auto.data_hora >= datetime.combine(data_ini, time.min),
             Log_Auto.data_hora <= datetime.combine(data_fim, time.max))\
     .subquery()

    atividades = db.session.query(log, Plano_Trabalho.atividade_sigla)\
                           .outerjoin(Plano_Trabalho, Plano_Trabalho.id == log.c.programa)\
                           .all()

    registra_log_auto(usuario.id, None, 'rel')

    return {
        'log': log,
        'atividades': atividades,
        'atividades_1': atividades_1,
        'atividades_2': atividades_2,
        'quantidade_1': quantidade_1,
        'quantidade_2': quantidade_2,
        'carga_1': carga_1[0][0],
        'carga_2': carga_2[0][0],
        'data_ini': data_ini.strftime('%x'),
        'data_fim': data_fim.strftime('%x'),
        'coordenador': coordenador,
        'coordenador_geral': coordenador_geral,
    }


def listar_usuarios_coordenacao(coord):
    """Lista os usuários ativos de uma coordenação, para atribuição de atividades."""
    return User.query.order_by(User.id).filter(User.coord == coord, User.ativo == 1).all()


def atividades_atuais_usuario(user_id):
    """Retorna as atividades atualmente atribuídas a um usuário."""
    return db.session.query(Ativ_Usu.atividade_id, Ativ_Usu.nivel, Ativ_Usu.id)\
                     .filter(Ativ_Usu.user_id == user_id)\
                     .order_by(Ativ_Usu.nivel.desc()).all()


def atividades_choices():
    """Retorna a lista de atividades do plano de trabalho formatada para um SelectField."""
    atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                           .order_by(Plano_Trabalho.atividade_sigla).all()
    lista_atividades = [(str(a[1]), a[0]) for a in atividades]
    lista_atividades.insert(0, ('', ''))
    return lista_atividades


def atribuir_atividade(user_id, atividade_id, nivel, usuario_id):
    """
    Atribui uma atividade do plano de trabalho a um usuário, se ele
    ainda não a tiver. Retorna um dos status: 'ja_possui', 'atribuida'.
    """
    ja_possui_ids = [a[0] for a in atividades_atuais_usuario(user_id)]

    if int(atividade_id) in ja_possui_ids:
        return 'ja_possui'

    ativ_para_user = Ativ_Usu(atividade_id=atividade_id, user_id=user_id, nivel=nivel)
    db.session.add(ativ_para_user)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'aus')

    return 'atribuida'


def atividades_atuais_formatadas(user_id):
    """Retorna as atividades atuais do usuário já formatadas para exibição no template."""
    ativ_usu = atividades_atuais_usuario(user_id)

    l_ativ_usu = []
    for ativ in ativ_usu:
        atividade_usu = db.session.query(Plano_Trabalho.atividade_sigla)\
                          .filter(Plano_Trabalho.id == ativ.atividade_id).first()
        l_ativ_usu.append([atividade_usu.atividade_sigla, ativ.nivel, ativ.id])

    return l_ativ_usu


def excluir_atividade_usuario(atividade_usu_id, usuario_id):
    """Remove uma atividade atribuída a um usuário."""
    atividade = Ativ_Usu.query.get_or_404(atividade_usu_id)

    db.session.delete(atividade)
    db.session.commit()

    registra_log_auto(usuario_id, None, 'xus')
