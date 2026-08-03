# Proposta de Melhorias — sistac

Documento de planejamento, sem código ainda. Organizado por área, com o `users`
priorizado conforme combinado. Cada item indica o que já sabemos do código hoje e
qual decisão de produto precisa ser tomada antes de implementar.

---

## 1. Usuários (prioridade atual)

### 1.1 Painel de "Funcionalidades do sistema" — **concluído**
Virou o papel Admin Master: novo `role='admin_master'`, tela "Dados gerais do
sistema" exclusiva pra ele, com cascata de desativação de permissões e restrição de
hierarquia por coordenação para admin comum. Já implementado, testado e publicado.

### 1.2 Autogestão de conta pelo próprio usuário — **concluído**
- Alterar o próprio e-mail: já existia (`account()`), sem mudança.
- Autoexcluir a própria conta: implementado. Desativa (`ativo=0`) e anonimiza
  e-mail/nome de usuário (liberando o e-mail original para um novo cadastro no
  futuro), preservando o histórico (demandas, log) intacto, ainda vinculado ao
  mesmo ID. Confirmação via pop-up (JS) na tela "Suas informações"; e-mail de
  aviso enviado ao endereço atual, sem link de confirmação (ação já é imediata).

### 1.5 Tela de configuração de textos de e-mail (Admin Master) — **novo, futuro**
Hoje cada e-mail que o sistema envia (confirmação de cadastro, redefinir senha,
demanda concluída, pede despacho, despacho emitido, providência alheia,
transferência de demanda, conta cancelada...) é um arquivo HTML fixo no código.
Pra ficar editável pelo admin master, seria necessário mover o texto de cada um
pro banco de dados, e adaptar cada ponto do sistema que hoje monta o e-mail
direto do arquivo pra buscar do banco. Frente própria, ainda não iniciada.

### 1.3 Gestão de cadastros pendentes pelo admin — **concluído nesta sessão**
Confirmar e-mail manualmente, reenviar confirmação, excluir cadastro não confirmado.
Já implementado, testado e publicado.

### 1.4 Fluxo "esqueci minha senha" — **conferido, já está completo**
Testado de ponta a ponta: solicitação por e-mail (com tratamento de e-mail
inválido/não confirmado), token com expiração de 1h, troca de senha com hash
correto (`pbkdf2:sha256`), tratamento de token inválido/expirado, link visível
na tela de login. Nenhum bug encontrado, nenhuma ação necessária.

---

## 2. Acordos / Bolsas

### 2.1 Excluir modalidade de bolsa após inserida — **bug/lacuna**
Nota antiga: não é possível excluir uma modalidade depois de cadastrada.

### 2.2 Separar "nome completo da modalidade" da "sigla" — **melhoria de dados**
Sugestão sua: hoje o campo modalidade parece misturar sigla e nome completo. Seria
adicionar um campo novo (`nome_completo`) mantendo `modalidade` como a sigla.

## 3. Acordos / Programas CNPq

### 3.1 Editar/excluir programa após inserido — **lacuna**
Nota antiga: depois de cadastrado, um Programa CNPq não pode ser editado nem excluído
pela interface.

---

## 4. Página "Sobre"

### 4.1 Botão de edição para Admin master — **novo, precisa de decisão de papel**
Mesma decisão pendente do item 1.1: se criarmos um papel "admin master"/"super admin",
esse botão de edição da página Sobre seria uma das primeiras coisas a usar essa
permissão nova. Vale decidir a hierarquia de papéis (item 1.1) antes de implementar
isso, para não fazer duas vezes.

---

## 5. Relatórios / UX

### 5.1 Geração de CSV mudou de comportamento — **revisar**
Nota antiga: o botão de download sumiu e o CSV passou a ser gerado direto, sem pedir
confirmação. Precisa decidir se isso foi uma regressão da refatoração ou uma mudança
desejada — vou conferir o código específico quando chegarmos nesse item.

---

## 6. Convênios / TED / Acordos — reestruturação e BI (prioridade política atual)

Contexto: há uma janela política em aberto (possível saída do presidente do CNPq no
início do ano, por conta das eleições) para obter apoio à homologação/produção do
sistema. Por isso, esta frente foi priorizada à frente de `Demandas`, que fica para
outro momento.

| # | Item | Descrição | Observação |
|---|------|-----------|------------|
| 6.1 | Renomear menu "Acordos/TEDs" | Remove a palavra "TEDs" do rótulo, fica só "Acordos" | Rápido, cosmético |
| 6.2 | Criar aba própria de TED | Nova aba, nos moldes visuais do módulo Convênios | Estrutura de tela pode sair rápido; dado real depende do item 6.4 |
| 6.3 | Melhorar o sentido de "Instrumentos" | Ainda não detalhado — se é o nome, a descrição, ou os dados exibidos | Aguardando detalhamento de Igor |
| 6.4 | Integração de dados de TED (SICONV/transferegov) | TED hoje não existe como dado — é só um rótulo, misturado com Acordo. Precisa de fonte de dados nova (API/portal do transferegov a pesquisar) | Grande, não é rápido — não depende só de reorganizar tela |
| 6.5 | Substituir 3 dashboards por BI | Em Convênios: "Em execução por UF e Programa", "Histórico por Programa", "Mapa". Mesmo tratamento para Acordos e (futuramente) TED | **Priorizado agora** — é a demanda visual mais direta dos gestores, e o SISTAC já tem os dados |
| 6.6 | Integração futura TED + Acordos | Unificação de dados/fluxo entre os dois | Futuro, não priorizado agora |

**Próximo passo combinado**: avançar com o item 6.5 (BI), já que é a demanda mais
direta das chefias e o SISTAC já possui os dados necessários — só falta apresentá-los
bem. Igor vai fornecer massa de dados anonimizada para uso no desenvolvimento.

---

## 7. Infraestrutura / Ambiente (fora do controle do código da aplicação)

Itens que não se resolvem só editando `sistac` — dependem de configuração de servidor
ou de decisões de infraestrutura do CNPq:

- **Logo do CNPq não aparecendo**: ainda pendente de diagnóstico (precisa confirmar se
  `/static/coop_nac.png` carrega direto pela URL) — mas há uma pista forte, ver item
  abaixo (`static_folder` fixo em caminho de Docker): pode ser a mesma causa.
- **`static_folder` fixo em caminho de Docker — quebra downloads de CSV (e possivelmente
  o logo) fora do container**: `project/__init__.py` cria o Flask com
  `static_folder='/app/project/static'` (caminho fixo, assumindo o container Docker de
  produção). Nesse Codespace (onde o projeto vive em `/workspaces/sistac`), esse caminho
  não existe — então qualquer link `/static/arquivo` (`convenios.csv`,
  `programas_conv.csv`, e agora também `ted.csv`, adicionado na frente de melhorias da
  Gestão de TED) responde 404, mesmo que o arquivo tenha sido gerado corretamente em
  `project/static/` no disco real. Confirmado testando `convenios.csv` (já existia,
  mesmo problema) e `ted.csv` (novo). Provavelmente é a mesma causa do item do logo
  acima. Correção sugerida: usar um caminho relativo/portável (ex:
  `os.path.join(os.path.dirname(__file__), 'static')`, mesmo padrão já usado em
  `cria_csv` via `app.root_path`) em vez do caminho fixo do Docker — mas requer
  confirmar com o time de infra se a produção depende desse caminho fixo por algum
  outro motivo antes de mudar.
- **Mapa de Convênios "Access blocked"**: política de uso de tiles do OpenStreetMap
  bloqueando por falta de `Referer` correto — comum em ambientes de preview/proxy como
  o do Codespace. Pode não se reproduzir em produção.
- **Integração Oracle DW ("Pega Programas/Chamadas/Financeiro DW")**: já documentado
  como dívida técnica em `core/services.py` — falta a biblioteca cliente do Oracle no
  ambiente, e há SQL montado por concatenação que merece hardening dedicado (ver seção
  "Security/Technical Debt" no código).

---

## 8. Infraestrutura de testes — proteção contra efeito colateral em dado persistente/singleton (pendente)

Já ocorreram vários casos de testes que escrevem em dado **persistente e
compartilhado** entre execuções (a linha única de `Sistema`, contas de usuário
reais no banco de dev, e — achado novo durante o BI de TED — tabelas de
conteúdo inteiras) e não restauram o estado original ao terminar:

- A linha única de `Sistema` e contas reais (ex: `igorc@cnpq.br`) já tiveram
  Gestão/BI desligados e permissões zeradas por um teste de
  `admin_reg_ver` que fazia POST minimalista deixando todo `BooleanField`
  desmarcado — corrigido nesta sessão (o teste agora marca explicitamente os
  campos que não estão sob teste).
- Achado novo: `services.cargaTED()` faz *delete-and-reload* de verdade nas 3
  tabelas espelho de TED (`TED_PlanoAcao`, `TED_Programa`,
  `TED_TermoExecucao`) — comportamento correto da função, mas dois testes já
  escritos (`test_carga_ted_mockada_popula_tabelas_espelho` e um teste novo
  desta sessão, `test_data_ultima_carga_gravada_e_exibida`) chamam essa
  função de verdade (só a chamada HTTP é mockada) contra o banco de dev
  persistente. Resultado: toda vez que a suíte roda, os 301 TEDs reais
  (carregados da API do TransfereGov) são substituídos pelos dados de
  mock/vazios dos testes — precisei rodar `cargaTED()` de novo manualmente
  pra repovoar dado real antes de revisar o BI de TED.

Proposta (já cogitada antes): um fixture de teste que tira um "snapshot" do
estado de `Sistema` (e, se fizer sentido, de contas de usuário sensíveis e/ou
das tabelas de conteúdo que sofrem delete-and-reload, como as de TED) antes
de qualquer teste que mexa nesses dados, e restaura automaticamente depois —
independente do teste ter passado ou falhado. Alternativa mais simples só
para os dados de TED: um banco de teste isolado/efêmero em vez do banco de
desenvolvimento (mesma direção já apontada no comentário de
`tests/conftest.py`: "Fase 2+... banco de teste isolado/efêmero em vez do
banco de desenvolvimento").

Não é bloqueante para nenhum commit em andamento — é uma melhoria de
infraestrutura de teste, a ser tratada como tarefa própria quando houver
espaço.

---

## Como sugiro seguirmos

**Prioridade atual (janela política em aberto):** avançar com o item 6.5 (BI sobre
Convênios/Acordos/TED) — é a frente escolhida por atender diretamente à demanda das
chefias, usando dados que o sistema já possui.

Itens 1.x a 5.x seguem no backlog geral, concluídos ou pendentes conforme já registrado
em cada seção — retomamos assim que a frente de BI e homologação estiver encaminhada.
`Demandas` fica propositalmente de fora por enquanto, a pedido de Igor.
