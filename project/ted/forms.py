"""
.. topic:: TED (formulários)

   Formulários de curadoria manual do módulo TED — nenhum deles cria ou
   edita o TED em si (que vem só da carga da API), só os registros de
   curadoria vinculados a ele.

   * ExecucaoInternaForm: registra coordenação/SEI de uma execução do TED pelo CNPq.
   * VinculoProgramaCNPqForm: associa o TED a um Programa CNPq.

   O vínculo a Convênio/Acordo (antiga VinculoInstrumentoForm, removida
   por virar código morto) agora é feito pelas telas de Convênio/Acordo,
   com um form HTML simples (sem WTForms dedicado — só um campo de busca
   + hidden, processados direto em request.form nas rotas vincula_ted).
"""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional


class ExecucaoInternaForm(FlaskForm):

    coordenacao = SelectField('Coordenação:', validators=[DataRequired(message="Escolha a coordenação!")])
    sei_cnpq    = StringField('Processo SEI do CNPq:', validators=[Optional()])
    observacao  = StringField('Observação:', validators=[Optional()])

    submit = SubmitField('Registrar')


class VinculoProgramaCNPqForm(FlaskForm):

    programa_cnpq  = SelectField('Programa CNPq:', validators=[DataRequired(message="Escolha o Programa CNPq!")])
    tipo_evidencia = SelectField('Como foi identificado:', choices=[
        ('nome_literal', 'Nome literal do programa'),
        ('tema_funcional', 'Tema/função (sem nome explícito)'),
        ('curadoria_manual', 'Curadoria manual, sem pista textual'),
    ])

    submit = SubmitField('Vincular')
