# sistac — Contexto do Projeto

## O que é

`sistac` é um fork pessoal de `cimei/sicopes`, um sistema Flask do CNPq para gestão
de acordos, convênios, instrumentos, bolsas e demandas (SICOPES). O projeto original
está em produção em `sicopesii.cnpq.br`, mantido por outra equipe (Cimei, que criou o
sistema, não está mais na equipe). Este fork é usado tanto para estudo (Python/Flask/
Git na prática) quanto, potencialmente, para propor melhorias que a infraestrutura do
CNPq poderá aplicar em produção no futuro — mas o deploy real não é controlado por
quem trabalha neste fork.

## Ambiente

- GitHub Codespaces, Python 3.12, venv em `/workspaces/sistac/venv/`
- Antes de rodar qualquer coisa:
  ```bash
  export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
  sudo service postgresql start
  ```
- Variáveis de ambiente necessárias (dev): `DB_USER`, `DB_PWD`, `DB_SERVER`, `DB_PORT`,
  `DB_DATABASE`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USER`, `MAIL_PWD`
- Blueprints são registrados **sem prefixo de URL** na maioria dos módulos (ex: rota
  `/admin_view_users`, não `/users/admin_view_users`) — confirmar em `project/__init__.py`
  antes de assumir prefixo.

## Arquitetura: o padrão que este projeto segue

Este projeto passou por uma refatoração completa (Fase 2) de monolito para o padrão:

- **`views.py`**: só rotas Flask finas — recebe request, chama `services.py`, decide
  redirect/render/flash. Sem lógica de negócio, sem queries diretas (com raras exceções
  documentadas inline).
- **`services.py`**: toda a lógica de negócio e queries SQLAlchemy. Sem `request`,
  `redirect`, `flash` (exceto onde documentado como exceção deliberada).

**Todos os 7 módulos já passaram por essa divisão**: `bolsas`, `instrumentos`, `users`,
`convenios`, `core`, `acordos`, `demandas`. Ao adicionar uma feature nova, siga o mesmo
padrão: lógica em `services.py`, rota fina em `views.py`.

### Dependência cruzada importante

`registra_log_auto` (usada por praticamente todo o sistema) vive em
`project/demandas/services.py`, mas `project/demandas/views.py` mantém um **re-export**
(`from project.demandas.services import registra_log_auto`) para que os 7+ módulos que
já fazem `from project.demandas.views import registra_log_auto` continuem funcionando
sem alteração. Não remova esse re-export sem atualizar todos os imports.

## Testes

- Suíte em `tests/`, roda com `pytest`.
- **Sempre rodar a suíte completa antes de commitar**:
  ```bash
  venv/bin/python -m pytest tests/ -v
  ```
- Padrão de nomenclatura: `test_<modulo>_<grupo>.py` (ex: `test_acordos_nucleo.py`).
- Toda função nova em `services.py` que corrige um bug real deve ganhar um teste de
  regressão citando o bug corrigido no docstring do teste.
- Testes usam um banco Postgres de dev persistente (não é recriado do zero a cada run)
  — funções de setup de teste devem checar `if not X.query.filter_by(...).first()`
  antes de criar dados, para serem idempotentes entre execuções repetidas.

## Convenções de commit

- Mensagens em português, formato: `refactor: extrai grupo X para services.py; corrige
  bug Y` ou `feat: <descrição>` para funcionalidades novas.
- Rodar a suíte de testes e confirmar `N passed` antes de qualquer commit.
- Arquivos gerados em tempo de execução (PDFs, CSVs de relatório) **nunca** devem ser
  commitados — checar `.gitignore`; se aparecer um novo, adicionar ao invés de commitar.

## Filosofia de correção de bugs

- Bugs reais (crashes, `AttributeError`/`IndexError` em resultado `None`/vazio,
  comparações erradas, valores sobrescritos por engano) são **corrigidos diretamente**,
  com comentário explicando o bug original e o porquê da correção.
- Mudanças de **regra de negócio** (ex: o que uma tela deveria fazer diferente) não são
  decididas sozinho — perguntar antes.
- Dívida técnica grande/arriscada (ex: SQL montado por concatenação no acesso ao Oracle
  DW, `oracledb.init_oracle_client()` chamado a cada consulta, fluxo OAuth do Google
  Calendar que usa `flow.run_console()` e por isso não funciona num servidor web) é
  **documentada em comentário/docstring**, não corrigida de forma isolada — normalmente
  precisa de mais contexto ou é fora do escopo do bug pontual.
- Padrões de bug já encontrados várias vezes neste projeto, então checar sempre que
  mexer em código correlato:
  - Rota sem `@login_required` mas usando `current_user.coord`/`current_user.id`.
  - Resultado de query com `.first()` usado sem checar `None`.
  - Resultado de query com `GROUP BY` usado sem checar lista vazia (`user[0][1]` quebra
    se não há nenhuma linha).
  - Coluna `Integer` recebendo string vazia `''` em vez de `None`.
  - Caminho absoluto tipo `/app/...` ou `/temp/...` (deveria ser `/tmp/...` ou usar
    `tempfile.gettempdir()`/`os.path.join(app.root_path, ...)`).
  - `db.session.delete()` chamado com uma lista (resultado de `.all()`) em vez de um
    objeto único — precisa iterar e deletar um por um.

## Ambiente de produção

`sicopesii.cnpq.br` roda um deploy que ninguém da equipe atual sabe explicar com
certeza (Cimei saiu da equipe). Mudanças feitas neste fork **não vão para produção
automaticamente** — a infraestrutura do CNPq precisa ser comunicada e atualizar o
sistema manualmente. Não assumir que uma correção aqui já resolve um problema relatado
em produção até isso ser confirmado.
