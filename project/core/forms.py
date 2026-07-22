"""

.. topic:: Core (formulários)

   Formulários exclusivos do papel admin_master, usados para configurar as
   funcionalidades do sistema e editar o texto da página Sobre.

"""

# forms.py dentro de core

from flask_wtf import FlaskForm
from wtforms import TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired


class EditaSobreForm(FlaskForm):

    descritivo = TextAreaField('Texto introdutório da página Sobre:', validators=[DataRequired(message="O texto não pode ficar vazio!")])
    submit     = SubmitField('Salvar')


class ConfigSistemaForm(FlaskForm):

    funcionalidade_conv   = BooleanField('Funcionalidade de Convênios habilitada?')
    funcionalidade_acordo = BooleanField('Funcionalidade de Acordos habilitada?')
    funcionalidade_instru = BooleanField('Funcionalidade de Instrumentos habilitada?')
    carga_auto            = BooleanField('Carga automática (SICONV/DW) habilitada?')
    submit                = SubmitField('Salvar')
