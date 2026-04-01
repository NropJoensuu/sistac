# SISTAC — Sistema de Gestão de Acordos

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

## Como contribuir
1. Faça um fork do repositório
2. Crie um branch para sua funcionalidade (`git checkout -b feat/minha-funcionalidade`)
3. Faça suas alterações e commit (`git commit -m "feat: descrição da mudança"`)
4. Envie para o GitHub (`git push origin feat/minha-funcionalidade`)
5. Abra um Pull Request