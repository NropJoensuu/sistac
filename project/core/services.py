"""
.. topic:: Core (services) — Home / Info

    Camada de regra de negócio do grupo "Home/Info" do módulo core:
    tela inicial, tela de informações, e o agendamento das cargas
    automáticas (SICONV e DW) feito na inicialização do sistema.

    Nota técnica: `agendar_cargas_iniciais` importa `cargaSICONV` e
    `chamadas_DW` de dentro da própria função (import local), e não no
    topo do arquivo, porque essas duas funções ainda vivem em
    `project/core/views.py` (serão movidas para este services.py só
    no grupo C — Integração SICONV/DW). Um import no topo do arquivo
    causaria import circular (views.py -> services.py -> views.py).
    Quando o grupo C for refatorado, este import interno deve ser
    atualizado para apontar para as funções já migradas.
"""

from project import db, sched
from project.models import Sistema, Log_Auto
from project.demandas.views import registra_log_auto


def dados_sistema():
    """Retorna o registro único de configuração geral do sistema."""
    return db.session.query(Sistema).first()


def agendar_cargas_iniciais():
    """
    Agenda os jobs de carga automática (SICONV e DW) na inicialização
    do sistema, se a carga automática estiver habilitada em Sistema.
    Não faz nada se `sistema.carga_auto != 1`.
    """
    # import local: ver nota técnica no topo do arquivo
    from project.core.views import cargaSICONV, chamadas_DW

    sistema = dados_sistema()

    if sistema.carga_auto != 1:
        return

    # pega último agendamento registrado, se houver
    log_agenda_ant_envio = db.session.query(Log_Auto.user_id, Log_Auto.id, Log_Auto.tipo_registro)\
                                     .filter(Log_Auto.tipo_registro == 'agc')\
                                     .order_by(Log_Auto.id.desc())\
                                     .first()

    # corrige bug real: o código original acessava .user_id direto,
    # sem checar se a query retornou None (acontece numa instalação
    # nova, antes de qualquer agendamento anterior existir).
    id_user = log_agenda_ant_envio.user_id if log_agenda_ant_envio else None

    # AGENDA CARGA SICONV NA INICIALIZAÇÃO DO SISTEMA
    id_1 = 'carga_siconv'

    try:
        job_existente = sched.get_job(id_1)
        executa = not job_existente
    except Exception:
        executa = True

    if executa:
        dia_semana = 'mon-fri'
        hora = 8
        minuto = 13

        print('*** Agendamento inicial ' + id_1 + ', rodando ' + dia_semana + ', às ' + str(hora) + ':' + str(minuto) + ' ***')
        try:
            sched.add_job(trigger='cron', id=id_1, func=cargaSICONV, day_of_week=dia_semana, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
            sched.start()
        except Exception:
            sched.reschedule_job(id_1, trigger='cron', day_of_week=dia_semana, hour=hora, minute=minuto)

        # só registra o log se houver um usuário válido para atribuir a ação
        # (numa instalação nova, sem nenhum agendamento anterior, não há)
        if id_user is not None:
            registra_log_auto(id_user, None, 'agi - agendamento cargaSICONV.')

    # AGENDA CARGA DW NA INICIALIZAÇÃO DO SISTEMA
    id_2 = 'carga_chamadas_DW'

    try:
        job_existente = sched.get_job(id_2)
        executa = not job_existente
    except Exception:
        executa = True

    if executa:
        dia = '2nd tue'
        hora = 18
        minuto = 18

        print('*** Agendamento inicial ' + id_2 + ', rodando ' + dia + ', às ' + str(hora) + ':' + str(minuto) + ' ***')
        try:
            sched.add_job(trigger='cron', id=id_2, func=chamadas_DW, day=dia, hour=hora, minute=minuto, misfire_grace_time=3600, coalesce=True)
            sched.start()
        except Exception:
            sched.reschedule_job(id_2, trigger='cron', day=dia, hour=hora, minute=minuto)

        if id_user is not None:
            registra_log_auto(id_user, None, 'agi - agendamento chamadas_DW.')
