"""
.. topic:: **Demandas (formulários)**

    Os formulários do módulo *Demandas* recebem dados informados pelo usuário para
    registro, atualização, procura e deleção de demandas.

    Uma demanda, após criada, só pode ser alterda e removida pelo seu autor.

    Para o tratamento de demandas, foram definidos 4 formulários:

    * Plano_TrabalhoForm: iserir ou alterar atividade no plano de trabalho.
    * Tipos_DemandaForm: criação ou atualização de tipos de demanda.
    * Passos_Tipos_Form: criação de passos para tipos de demanda.
    * Admin_Altera_Demanda_Form: admin altera data de conclusão de uma demanda.
    * DemandaForm1: triagem antes da criação de uma demanda.
    * DemandaForm: criação ou atualização de uma demanda.
    * Demanda_ATU_Form: atualizar demanda.
    * TransferDemandaForm: passar demanda para outra pessoa.
    * DespachoForm: criação de um despacho relativo a uma demanda existente.
    * ProvidenciaForm: criação de uma providência relativa a uma demanda existente.
    * PesquisaForm: localizar demandas conforme os campos informados.
    * PesosForm: atribuição de pesos para os critérios de priorização de demandas.
    * Afere_Demanda_Form: atribuir nota a uma demanda
    * Pdf_Demanda_Form: para gerar pdf da demanda em tela
    * CoordForm: escolher uma coordeação específica


**Campos definidos em cada formulário de *Demandas*:**

"""

# forms.py na pasta demandas

import datetime
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SelectField, BooleanField, DecimalField,\
                    DateTimeField, TextAreaField, SubmitField, RadioField
from wtforms.fields import DateField                    
from wtforms.validators import DataRequired, Regexp, Optional
from project import db
from project.models import Tipos_Demanda, Coords, User, Plano_Trabalho


class Plano_TrabalhoForm(FlaskForm):

    # pessoas = db.session.query(User.username, User.id)\
    #                   .order_by(User.username).all()
    # lista_pessoas = [(str(p[1]),p[0]) for p in pessoas]
    # lista_pessoas.insert(0,('',''))
    # lista_pessoas.insert(1,('*','DESATIVADO'))

    atividade_sigla = StringField('Sigla:',validators=[DataRequired(message="Informe a sigla!")])
    atividade_desc  = TextAreaField('Descrição:',validators=[DataRequired(message="Informe a descrição!")])
    natureza        = StringField('Natureza:',validators=[DataRequired(message="Informe a natureza!")])
    horas_semana    = DecimalField('Meta (h/sem):',validators=[DataRequired(message="Informe a meta!")], places=1)
    situa           = SelectField('Status:',choices= [('Ativa','Ativa'),('Desativada','Desativada')])
    unidade         = SelectField('Unidade:',validators=[DataRequired(message="Informe a unidade organizacional!")])

    submit     = SubmitField('Registrar')

class Tipos_DemandaForm(FlaskForm):

    tipo       = StringField('Tipo de Demanda')
    relevancia = SelectField('Relevância:',choices=[('3','Baixa'),('2','Média'),('1','Alta')],
                              validators=[DataRequired(message="Defina a Relevância!")])
    # unidade    = StringField('Unidade:',validators=[DataRequired(message="Informe a unidade organizacional!")])                          

    submit     = SubmitField('Registrar')

class Passos_Tipos_Form(FlaskForm):

    ordem = IntegerField('Ordem do passo:', validators=[DataRequired(message="Defina a ordem do passo!")])
    passo = StringField('Passo:', validators=[DataRequired(message="Identifique o passo!")])
    desc  = TextAreaField('Descrição:', validators=[DataRequired(message="Descreva o passo!")])

    submit = SubmitField('Registrar')

class Admin_Altera_Demanda_Form(FlaskForm):

    data_conclu = DateField('Data de conclusão da demanda:',format='%Y-%m-%d',validators=[DataRequired(message="Informe data da conclusão!")])

    submit      = SubmitField('Registrar')

class DemandaForm1(FlaskForm):
    # choices do campo tipo são definido na view
    sei                 = StringField('SEI:',validators=[DataRequired(message="Informe o Processo!")]) # incluir regex para sei, talvez ?!?!
    tipo                = SelectField('Tipo:', validators=[DataRequired(message="Escolha um Tipo!")])
    submit              = SubmitField('Verificar')


class DemandaForm(FlaskForm):

    # programa            = StringField('Programa:',validators=[DataRequired(message="Escolha um Programa!")])
    atividade             = SelectField('Atividade:', validators=[DataRequired(message="Escolha uma atividade do plano de trabalho!")])
    convênio              = IntegerField('Convênio:', validators=[Optional()])
    titulo                = StringField('Título:', validators=[DataRequired(message="Defina um Título!")])
    desc                  = TextAreaField('Descrição:',validators=[DataRequired(message="Descreva a Demanda!")])
    necessita_despacho    = BooleanField('Necessita despacho?')
    necessita_despacho_cg = BooleanField('Necessita despacho superior?')
    conclu                = SelectField('Concluída?',choices=[('0','Não'),('1','Sim, com sucesso'),('2','Sim, com insucesso')])
    urgencia              = SelectField('Urgência:',choices=[('3','Baixa'),('2','Média'),('1','Alta')],
                                       validators=[DataRequired(message="Defina a urgência!")])
    submit                = SubmitField('Registrar')

#
class Demanda_ATU_Form(FlaskForm):

    # programa            = StringField('Programa:',validators=[DataRequired(message="Escolha um Programa!")])
    atividade     = SelectField('Atividade:', validators=[DataRequired(message="Escolha uma atividade do plano de trabalho!")])
    sei           = StringField('SEI:')
    tipo          = SelectField('Tipo:')
    convênio      = IntegerField('Convênio:', validators=[Optional()])
    ano_convênio  = IntegerField('Ano do Convênio:', validators=[Optional()])
    titulo        = StringField('Título:', validators=[DataRequired(message="Defina um Título!")])
    desc          = TextAreaField('Descrição:',validators=[DataRequired(message="Descreva a Demanda!")])
    tipo_despacho = RadioField('Necessita despacho?',choices=[('0','Nenhum'),('1','1º nível'),('2','Superior')])
    conclu        = SelectField('Concluída?',choices=[('0','Não'),('1','Sim, com sucesso'),('2','Sim, com insucesso')])
    urgencia      = SelectField('Urgência:',choices=[('3','Baixa'),('2','Média'),('1','Alta')],
                                       validators=[DataRequired(message="Defina a urgência!")])
    submit              = SubmitField('Registrar')

class TransferDemandaForm(FlaskForm):

    pessoa = SelectField('Novo responsável:', validators=[DataRequired(message="Escolha alguém!")])
    submit = SubmitField('Transferir')

class DespachoForm(FlaskForm):

    texto                  = TextAreaField('Descrição:',validators=[DataRequired(message="Descreva o Despacho!")])
    necessita_despacho_cg  = BooleanField('Necessita despacho superior?')
    conclu                 = SelectField('Demanda concluída?',choices=[('0','Não'),('1','Sim, com sucesso'),('2','Sim, com insucesso')])
    passo                  = SelectField('Passo:')
    submit                 = SubmitField('Registrar')

class ProvidenciaForm(FlaskForm):

    data_hora           = DateTimeField('Momento:',format='%d/%m/%Y %H:%M:%S',validators=[DataRequired(message="O momento deve ser informado!")])
    duracao             = IntegerField('Tempo (min.):')
    agenda              = BooleanField("Marcar na agenda")
    texto               = TextAreaField('Descrição:',validators=[DataRequired(message="Insira uma descrição!")])
    necessita_despacho  = BooleanField('Necessita despacho?')
    conclu              = SelectField('Demanda concluída?',choices=[('0','Não'),('1','Sim, com sucesso'),('2','Sim, com insucesso')], validators=[Optional()])
    passo               = SelectField('Passo:')
    submit              = SubmitField('Registrar')

class PesquisaForm(FlaskForm):

    coord               = SelectField('Coordenação:')
    sei                 = StringField('SEI:')
    convênio            = StringField('Convênio:')
    tipo                = SelectField()
    titulo              = StringField('Título:')
    ## os valore nos dois campos a seguir vão ao contrário, pois na view a condição de pesquisa usa o !=
    necessita_despacho  = SelectField('Aguarda Despacho',choices=[('Todos','Todos'),
                                               ('Sim','Não'),
                                               ('Não','Sim')])
    necessita_despacho_cg  = SelectField('Aguarda Despacho superior',choices=[('Todos','Todos'),
                                              ('Sim','Não'),
                                              ('Não','Sim')])
    # conclu              = SelectField('Concluído',choices=[('Todos','Todos'),
    #                                             ('Sim','Não'),
    #                                             ('Não','Sim')])
    conclu              = SelectField('Concluída?',choices=[('Todos','Todos'),('0','Não'),('1','Sim, com sucesso'),('2','Sim, com insucesso')])

    autor               = SelectField('Responsável:')

    demanda_id          = StringField('Número da demanda:')

    atividade           = SelectField('Atividade:')

    submit              = SubmitField('Pesquisar')

# form para definir o peso de cada componente RDU
class PesosForm(FlaskForm):

    peso_R = SelectField('Relevância:',choices= [('0.5','Importante'),('1','Normal'),('1.5','Sem importância')],default='1')
    peso_D = SelectField('Momento:',choices= [('0.5','Importante'),('1','Normal'),('1.5','Sem importância')],default='1')
    peso_U = SelectField('Urgência:',choices= [('0.5','Importante'),('1','Normal'),('1.5','Sem importância')],default='1')
    coord  = SelectField('Coordenação:')
    pessoa = SelectField('Responsável:')
    submit = SubmitField('Aplicar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coords = db.session.query(Coords.sigla)\
                          .order_by(Coords.sigla).all()
        lista_coords = [(c[0],c[0]) for c in coords]
        lista_coords.insert(0,('',''))
        self.coord.choices = lista_coords

        pessoas = db.session.query(User.username, User.id)\
                          .order_by(User.username).all()
        lista_pessoas = [(str(p[1]),p[0]) for p in pessoas]
        lista_pessoas.insert(0,('',''))
        self.pessoa.choices = lista_pessoas

# form para aferir demanda
class Afere_Demanda_Form(FlaskForm):

    nota = RadioField('Nota:',choices=[('0','0'),('1','1'),('2','2'),('3','3'),('4','4'),('5','5'),('6','6'),('7','7'),('8','8'),('9','9'),('10','10')],
                              validators=[DataRequired(message="Escolha a nota!")])

    submit      = SubmitField('Registrar')

# form com botão para gerar relatório pdf
class Pdf_Form(FlaskForm):

    submit      = SubmitField('Gerar pdf')

# form para escolher coordenação
class CoordForm(FlaskForm):

    coord  = SelectField('Coordenação:')
    submit = SubmitField('Aplicar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coords = db.session.query(Coords.sigla)\
                          .order_by(Coords.sigla).all()
        lista_coords = [(c[0],c[0]) for c in coords]
        lista_coords.insert(0,('',''))
        self.coord.choices = lista_coords
