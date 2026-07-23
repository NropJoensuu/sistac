"""

.. topic:: **Usuários (formulários)**

   Os formulários do módulo *Users* recebem dados informados pelo usuário para seu registro
   inicial, para entrar no sistema (login), para atualização de registro, bem como os dados
   para atualização de senha.

   Para o tratamento de usuários, foram definidos 5 formulários:

   * LoginForm: utilizado para entrar (login) no sistema.
   * RegistrationForm: utilizado para o registro de um novo usuário.
   * UpdateUserForm: utilizado para que um usuário possa atualizar seus dados.
   * EmailForm: utilizado para um usuário informar seu e-mail quando precisar trocar sua senha.
   * PasswordForm: utilizado quando o usuário eferuar a troca de senha.
   * LogForm: para que o usuário informe o intervalo de datas para resgatar registros do log
   * VerForm: para o registro de atualização no sistema.
   * RelForm: datas para geração de relatório de atividades.
   * UserAtiv: relaciona atividades de um usuário


**Campos definidos em cada formulário de *Users*:**

"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField,\
                    TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo
from wtforms.fields import DateField
from wtforms import ValidationError
from flask_wtf.file import FileField, FileAllowed
from flask import flash

from flask_login import current_user
from project import db
from project.models import User, Coords, Plano_Trabalho

class LoginForm(FlaskForm):

    email    = StringField('E-mail: ', validators=[DataRequired(message="Informe seu e-mail registrado!"),Email()])
    password = PasswordField('Senha: ', validators=[DataRequired(message="Informe sua senha!")])
    submit   = SubmitField('Entrar')

class RegistrationForm(FlaskForm):

    email        = StringField('E-mail: ', validators=[DataRequired(message="Informe seu e-mail!"),Email()])
    username     = StringField('Nome do usuário: ', validators=[DataRequired(message="Informe um nome de usuário!")])
    password     = PasswordField('Senha: ', validators=[DataRequired(message="Informe uma senha!"),EqualTo('pass_confirm',message='Senhas devem ser iguais!')])
    pass_confirm = PasswordField('Confirmar Senha: ', validators=[DataRequired(message="Confirme a senha!")])
    # não é utilizada a lista de coordenações, pois o usuário pode se registrar antes de existirem coordenações no banco.
    coord        = StringField('Coordenação:',validators=[DataRequired(message="Informe a Coordenação!")])
    despacha     = BooleanField('Você é coordenador, ou o seu substituto?')
    despacha2    = BooleanField('Você é coordenador-geral, ou o seu substituto?')
    despacha0    = BooleanField('Você é chefe de serviço, ou o seu substituto?')
    submit       = SubmitField('Registrar-se')

    def check_email(self,field):
        if User.query.filter_by(email=field.data).first():
            flash('Este e-mail já foi registrado!','erro')
            raise ValidationError('Este e-mail já foi registrado!')

    def check_username(self,field):
        if User.query.filter_by(username=field.data).first():
            flash('Este nome de usuário já foi registrado! Por favor, escolha outro.','erro')
            raise ValidationError('Este nome de usuário já foi registrado!')


class UpdateUserForm(FlaskForm):

    email    = StringField('E-mail: ', validators=[DataRequired(message="Informe um e-mail!"),Email()])
    username = StringField('Usuário: ', validators=[DataRequired(message="Informe um nome de usuário!")])
    submit   = SubmitField('Atualizar')

    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first() and field.data != current_user.email:
            flash('Este e-mail já foi registrado!','erro')
            raise ValidationError('Este e-mail já foi registrado!')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first() and field.data != current_user.username:
            flash('Este nome de usuário já foi registrado! Por favor, escolha outro.','erro')
            raise ValidationError('Este nome de usuário já foi registrado!')

class EmailForm(FlaskForm):

    email    = StringField('E-mail: ', validators=[DataRequired(message="Informe seu e-mail!"),Email()])
    submit   = SubmitField('Enviar')

class PasswordForm(FlaskForm):

    password     = PasswordField('Senha: ', validators=[DataRequired(message="Forneça uma senha!"),EqualTo('pass_confirm',message='Senhas devem ser iguais!')])
    pass_confirm = PasswordField('Confirmar senha: ', validators=[DataRequired(message="Confirme a senha!")])
    submit       = SubmitField('Enviar')

class TrocaPasswordForm(FlaskForm):

    password_atual = PasswordField('Senha atual: ', validators=[DataRequired(message="Forneça uma senha!")])
    password_nova  = PasswordField('Senha nova: ', validators=[DataRequired(message="Forneça uma senha!"),EqualTo('pass_confirm',message='Senhas devem ser iguais!')])
    pass_confirm   = PasswordField('Confirmar senha: ', validators=[DataRequired(message="Confirme a senha!")])
    submit         = SubmitField('Enviar')    

class AdminForm(FlaskForm):

    coord        = SelectField('Coordenação:', validators=[DataRequired(message="Escolha uma Coordenção!")])
    despacha0    = BooleanField('É chefe de serviço, ou o seu substituto?')
    despacha     = BooleanField('É coordenador(a), ou substituto(a)?')
    despacha2    = BooleanField('É coordenador(a)-geral, ou substituto(a)?')
    role         = SelectField('Role: ',choices=[('user','user'),('admin','admin')] ,validators=[DataRequired(message="Informe o papel do usuário!")])
    cargo_func   = StringField('Cargo e Função: ')
    ativo        = BooleanField('Usuário está ativo?')
    trab_conv    = BooleanField('Usuário trabalha com convênios?')
    trab_acordo  = BooleanField('Usuário trabalha com acordos e encomendas?')
    trab_instru  = BooleanField('Usuário trabalha com instrumentos?')
    submit       = SubmitField('Atualizar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coords = db.session.query(Coords.sigla)\
                          .order_by(Coords.sigla).all()
        lista_coords = [(c[0],c[0]) for c in coords]
        lista_coords.insert(0,('',''))
        self.coord.choices = lista_coords

class CoordForm(FlaskForm):

    coord  = StringField('Coordenação:',validators=[DataRequired(message="Informe a sigla da Unidade!")])  
    pai    = StringField('Pai:')

    submit = SubmitField('Registrar') 


class TransferUnidadeForm(FlaskForm):

    origem  = SelectField('Unidade de origem (será removida):', validators=[DataRequired(message="Escolha a unidade de origem!")])
    destino = SelectField('Unidade de destino (recebe tudo da origem):', validators=[DataRequired(message="Escolha a unidade de destino!")])

    submit  = SubmitField('Transferir')

class LogForm(FlaskForm):

    data_ini = DateField('Data Inicial: ', format='%Y-%m-%d')
    data_fim = DateField('Data Final: ', format='%Y-%m-%d')
    log_part = StringField('Ação: ')
    submit   = SubmitField('Procurar')

class LogFormMan(FlaskForm):

    atividade   = SelectField('Atividade:')
    entrada_log = TextAreaField('Entrada no Diário: ')
    duracao     = IntegerField('Duração (min.): ')
    submit      = SubmitField('Registrar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                          .order_by(Plano_Trabalho.atividade_sigla).all()
        lista_atividades = [(str(a[1]),a[0]) for a in atividades]
        lista_atividades.insert(0,('',''))
        self.atividade.choices = lista_atividades

class VerForm(FlaskForm):

    ver                   = StringField('Versão: ')
    cod_inst              = StringField('Cód. da Instituição: ')
    nome_sistema          = StringField('Nome do sistema: ')
    descritivo            = TextAreaField('Descritivo: ')
    funcionalidade_conv   = BooleanField('Habilitar funcionalidade convênios?')
    funcionalidade_acordo = BooleanField('Habilitar funcionalidade acordos?')
    funcionalidade_instru = BooleanField('Habilitar funcionalidade instrumentos?')
    carga_auto            = BooleanField('Habilitar carga automática?')
    submit                = SubmitField('Registrar')

class RelForm(FlaskForm):

    data_ini = DateField('Data Inicial: ', format='%Y-%m-%d')
    data_fim = DateField('Data Final: ', format='%Y-%m-%d')
    submit   = SubmitField('Gerar Relatório')

#
class AtivUsu  (FlaskForm):

    atividade  = SelectField('Atividade:')
    nivel_resp = SelectField('Nível de responsabilidade: ',choices=[('',''),('Titular','Titular'),('Suplente','Suplente')],
                            validators=[DataRequired(message="Informe o nível de responsabilidade do usuário!")])
    submit    = SubmitField('Atribuir')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        atividades = db.session.query(Plano_Trabalho.atividade_sigla, Plano_Trabalho.id)\
                          .order_by(Plano_Trabalho.atividade_sigla).all()
        lista_atividades = [(str(a[1]),a[0]) for a in atividades]
        lista_atividades.insert(0,('',''))
        self.atividade.choices = lista_atividades

class TipoLogForm(FlaskForm):

    tipo = StringField('Tipo')
    desc = StringField('Descrição')
    submit   = SubmitField('Inserir')