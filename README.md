# SISTAC

Sistema de gerenciamento de TEDs, acordos e convênios.

## Descrição

O SISTAC é uma aplicação web desenvolvida em Python/Flask para apoiar o
gerenciamento de Termos de Execução Descentralizada (TEDs), acordos e
convênios, com controle de bolsas, bolsistas, projetos e demandas.

## Funcionalidades

- Gestão de acordos e convênios
- Controle de bolsas e bolsistas
- Acompanhamento de projetos
- Gestão de demandas internas
- Integração com dados do SICONV e DW CNPq
- Geração de relatórios em PDF
- Visualização de acordos em mapa do Brasil

## Tecnologias

- Python 3 / Flask
- SQLAlchemy (PostgreSQL / Oracle)
- Docker / Gunicorn
- Google API

## Como executar
```bash
pip install -r requirements.txt
python app.py
```

## Versão atual

v5.0.13