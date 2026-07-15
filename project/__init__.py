# __init__.py dentro da pasta project

import sys
import os
import locale
import datetime
from flask import Flask,render_template,url_for,redirect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail

# from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from shutil import rmtree
import time
import glob

TOP_LEVEL_DIR = os.path.abspath(os.curdir)

app = Flask (__name__, static_url_path=None, instance_relative_config=True, static_folder='/app/project/static')

app.config.from_pyfile('flask.cfg')

app.static_url_path=app.config.get('STATIC_PATH')

db = SQLAlchemy(app)

migrate = Migrate(app, db)


# Filtro customizado do Jinja para formatar valores monetários em Real.
# Registrado aqui (não em app.py) para funcionar independente de como a
# aplicação é iniciada (python app.py, gunicorn, testes, etc.).
@app.template_filter('converte_para_real')
def converte_para_real(valor):
    if valor:
        return locale.currency(valor, symbol=False, grouping=True)
    return valor

mail = Mail(app)

locale.setlocale( locale.LC_ALL, '' )

# sched = APScheduler()
sched = BackgroundScheduler()

#################################
## log in - cofigurações

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = 'users.login'


############################################
## blueprints - registros

from project.core.views import core
from project.users.views import users
from project.demandas.views import demandas
from project.error_pages.handlers import error_pages

from project.bolsas.views import bolsas
from project.acordos.views import acordos

from project.convenios.views import convenios

from project.instrumentos.views import instrumentos

app.register_blueprint(core)
app.register_blueprint(users)
app.register_blueprint(demandas,url_prefix='/demandas')
app.register_blueprint(error_pages)

app.register_blueprint(bolsas,url_prefix='/bolsas')
app.register_blueprint(acordos,url_prefix='/acordos')

app.register_blueprint(convenios,url_prefix='/convenios')

app.register_blueprint(instrumentos,url_prefix='/instrumentos')