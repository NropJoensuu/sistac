"""

.. topic:: Convênios (formulários)

   O formulário do módulo *Convenios* recebe dados informados pelo usuário para o registro
   de dados SEI de um convênio e é o mesmo utilizado quando da atualização de dados já existente.

   * SEIForm: utilizado registrar ou atualizar dados SEI de um convênio.
   * ProgPrefForm: para registrar ou atualizar programas preferenciais, ou seja, aqueles a partir dos quais será feira extração no SICONV.
   * ChamadaForm: para registrar ou atualizar dados de chamadas públicas cujos resultados foram homologados pelo CNPq.
   * NDForm: para registrar naturezas de despesas em empenhos

**Campos definidos no formulário (todos são obrigatórios, exceto o "obs" do ChamadaForm):**

"""

# forms.py dentro de convenios

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField, SelectField, SelectMultipleField
from wtforms.validators import DataRequired, Regexp
from sqlalchemy import distinct

from project import db
from project.models import Programa_Interesse, User

class SEIForm(FlaskForm):

    nr_convenio = IntegerField('SICONV:', render_kw={'readonly': True})
    sei         = StringField('SEI:',validators=[DataRequired(message="Informe o Processo!")]) # incluir regex para sei... um dia....
    epe         = StringField('EP (sigla):',validators=[DataRequired(message="Informe a instituição!")])
    fiscal      = SelectField('Fiscal:')
    submit      = SubmitField('Atualizar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pessoal = db.session.query(User.username)\
                            .filter(User.ativo == 1)\
                            .order_by(User.username).all()
        lista_pessoal = [(p[0],p[0]) for p in pessoal]
        lista_pessoal.insert(0,('',''))
        self.fiscal.choices = lista_pessoal

class ChamadaConvForm(FlaskForm):

    chamada = SelectMultipleField('Chamada:')

    submit  = SubmitField('Associar')      

# form para inserir/atualizar programa preferencial
class ProgPrefForm(FlaskForm):

    #coords = db.session.query(Coords.sigla)\
    #                  .order_by(Coords.sigla).all()
    #lista_coords = [(c[0],c[0]) for c in coords]
    #lista_coords.insert(0,('',''))

    cod_programa = IntegerField('Código do Programa:', render_kw={'readonly': True})
    desc         = StringField('Descrição:', render_kw={'readonly': True})
    sigla        = StringField('Sigla:',validators=[DataRequired(message="Informe a Sigla do Programa!")])
    coord        = StringField('Coordenação:',validators=[DataRequired(message="Informa a Coordenação!")])
    #coord        = SelectField('Coordenação:',choices= lista_coords, validators=[DataRequired(message="Escolha uma Coordenção!")])
    submit       = SubmitField('Registrar')

#
## form para inserir dados de chamada homologadas
class ChamadaForm(FlaskForm):

    sei               = StringField('SEI:') 
    chamada           = StringField('Chamada:',validators=[DataRequired(message="Informe o nome da Chamada!")])
    qtd_projetos      = StringField('Quantidade de projetos:',validators=[DataRequired(message="Informe a quantidade de projetos!")])
    vl_total_chamada  = StringField('Valor total homologado:',validators=[DataRequired(message="Informe o valor!")])
    doc_sei           = StringField('Doc. SEI com a lista de projetos:')
    obs               = StringField('Observações:')
    submit      = SubmitField('Registrar')

#
## form para inserir dados de natureza de despesa em empenho
class NDForm(FlaskForm):

    nd      = StringField('Código da Natureza de Despesa:',validators=[DataRequired(message="Informe a ND!")])
    submit  = SubmitField('Registrar')
#
# form para escolher a coordenação na lista de convênios
class ListaForm(FlaskForm):

    coord        = SelectField('Coordenação:')
    submit       = SubmitField('Filtrar coordenação')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        coords = db.session.query(distinct(Programa_Interesse.coord))\
                          .order_by(Programa_Interesse.coord).all()
        lista_coords = [(c[0],c[0]) for c in coords]
        lista_coords.insert(0,('inst','Instituição'))
        lista_coords.insert(0,('',''))
        self.coord.choices = lista_coords
