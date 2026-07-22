#!/bin/bash
# setup_ambiente.sh — deixa o Codespace pronto do zero para rodar o sistac
# Uso: bash setup_ambiente.sh

set -e  # para no primeiro erro

echo "1/7 — Locale..."
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

echo "2/7 — Iniciando PostgreSQL..."
sudo service postgresql start

echo "3/7 — Variáveis de ambiente..."
export DB_USER=postgres DB_PWD=postgres DB_SERVER=localhost DB_PORT=5432 DB_DATABASE=sistac_dev
export MAIL_SERVER=x MAIL_PORT=587 MAIL_USE_TLS=True MAIL_USER=x MAIL_PWD=x
export FLASK_APP=app.py

echo "4/7 — Garantindo que o banco e o schema existem..."
PGPASSWORD=postgres psql -U postgres -h localhost -tc "SELECT 1 FROM pg_database WHERE datname = 'sistac_dev'" | grep -q 1 \
  || PGPASSWORD=postgres psql -U postgres -h localhost -c "CREATE DATABASE sistac_dev;"
PGPASSWORD=postgres psql -U postgres -h localhost -d sistac_dev -c "CREATE SCHEMA IF NOT EXISTS dem;"

echo "5/7 — Rodando migrações..."
venv/bin/python -m flask db upgrade

echo "6/7 — Semeando tabela Sistema (se estiver vazia)..."
venv/bin/python -c "
from project import app, db
from project.models import Sistema

with app.app_context():
    if not Sistema.query.first():
        s = Sistema(nome_sistema='SISTAC', descritivo='', funcionalidade_conv=1,
                    funcionalidade_acordo=1, funcionalidade_instru=1, carga_auto=0)
        db.session.add(s)
        db.session.commit()
        print('Sistema semeado.')
    else:
        print('Sistema já existia, nada a fazer.')
"

echo "7/7 — Rodando a suíte de testes para confirmar que está tudo certo..."
venv/bin/python -m pytest tests/ -v

echo ""
echo "Ambiente pronto! Para subir o servidor:"
echo "  venv/bin/python app.py"
