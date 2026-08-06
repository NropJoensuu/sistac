# Proposta de Melhorias — sistac

Documento de planejamento e acompanhamento. Reescrito em 05/08/2026 pra
incorporar o backlog detalhado de refinamento pós-BI.

---

## ✅ Concluído (resumo — não precisa mais de atenção)

- **Usuários**: Admin Master, hierarquia por coordenação, autogestão de conta
  (autoexclusão), gestão de cadastros pendentes, fluxo "esqueci minha senha"
  conferido, correção do bug grave de despacho no registro, re-registro sobre
  e-mail não confirmado.
- **Roadmap de BI, as 4 etapas**: BI Convênios, BI Acordos, módulo TED
  completo (Gestão + BI), Painel Executivo (Captado × Executado, sem soma
  indevida entre TED e Acordo/Convênio).
- **Infraestrutura**: `static_folder` corrigido (resolveu também o logo do
  CNPq), URL do SICONV migrada pro novo endereço do Transferegov, proteção
  automática de dados persistentes/singleton nos testes (item 8 antigo).
- **Dados**: carga real de bolsistas (53.817 pagamentos, via `cargaPDCTR`
  migrado pra `.xlsx`).

---

## 🔴 1. Homologação — prioridade combinada

- Gerar/enviar a imagem Docker pro Harbor (versão a definir — ver nota de
  versionamento no final deste documento)
- Enviar o pedido formal pra infraestrutura (`pedido_ambiente_testes.txt`,
  já pronto — reapresentar)
- Troca de domínio `sicopesii.cnpq.br` → `sistac.cnpq.br` (parte do mesmo
  pedido)

---

## 🟡 2. Refinamento pós-BI — backlog detalhado (Igor, 05/08/2026)

Ordem sugerida por Igor: TED → Convênios → Acordos. Mantida abaixo. Ao
final desta seção, uma sugestão minha de sequenciamento dentro disso.

### Nota importante — dois mecanismos de curadoria diferentes, não confundir

- **Acordo ↔ Programa CNPq**: mecanismo **manual, antigo**, já existia antes
  de qualquer trabalho de BI (tela "Associar Programa(s) ao Acordo/TED").
  Nunca foi automatizado. O Painel Executivo usa esse vínculo manual
  (`grupo_programa_cnpq`) pra agregar por Programa CNPq.
- **Processo-Mãe (pagamento de bolsista) ↔ Acordo**: mecanismo **novo**,
  parcialmente automatizado (78% nos 139 processos-mãe testados, o resto
  numa fila de revisão manual dentro do próprio sistema). Serve pra outra
  coisa — rastrear a qual Acordo um lote de pagamentos pertence — não tem
  relação com o Painel Executivo.

### A. TED

| # | Item |
|---|---|
| A1 | Programa CNPq: hoje cadastrado manualmente — avaliar carregar automaticamente a partir dos dados do DW |
| A2 | ✅ Gestão TED: texto da coluna em branco (cor branca sobre fundo branco) — corrigido pra `text-dark`, mesmo padrão (ausência de classe de cor especial, texto escuro padrão do Bootstrap) usado nos cabeçalhos de tabela de Convênios/Acordos |
| A3 | ✅ Gestão TED: separar coluna "Vigência" em duas — início e fim. Feito: duas colunas independentes ("Início" e "Fim"), cada uma ordenável pelo clique no cabeçalho — a chave `'vigencia'` de `_CHAVES_ORDENACAO` virou `'vigencia_inicio'` e `'vigencia_fim'` |
| A4 | ✅ Gestão TED: colorir "Vigência fim" com o mesmo padrão de Convênios/Acordos (cinza a 90 dias do fim, amarelo a 60, vermelho a 30). Feito: `listar_teds()` passou a devolver `prazo` (dias até o fim da vigência, `None` quando não há data — 54 dos 363 TEDs reais estão nessa situação), e o template aplica as mesmas 3 classes de Convênios, com o mesmo tooltip explicativo no cabeçalho. Conferido com dado real: 5 vermelhos, 4 laranjas, 4 cinzas |
| A5 | ✅ Gestão TED: instituições devem aparecer pela sigla, não nome completo. Feito: a sigla **não existia no banco** — a API do TransfereGov já mandava `sigla_unidade_descentralizadora`, mas a carga descartava. Coluna nova em `TED_Programa` + migração à mão + `cargaTED()` passou a capturar; recarga real populou os 278 programas (100%). Exibição: sigla como texto do badge, nome completo no `title` (tooltip), com fallback pro nome completo se a sigla vier vazia. Confirmado que a recarga **não afetou** as tabelas de curadoria manual (`TED_Vinculo_ProgramaCNPq` 7, `TED_Vinculo_Instrumento` 8, `TED_Execucao_Interna` 4 — idênticas antes e depois) |
| A6 | ✅ Gestão TED: vínculo de Acordo/Convênio só permitia 1 por vez (bug real: `vincular_instrumento` sobrescrevia por `id_plano_acao`, e `listar_teds()` guardava só 1 vínculo por TED num dict — os demais eram descartados silenciosamente), mas um TED pode ter até 27, segundo Igor. Corrigido: `vincular_instrumento` sempre cria uma linha nova (mesmo padrão de `registrar_execucao_interna`); `listar_teds()` retorna uma lista `instrumentos` por TED. **Decisão de Igor aplicada**: não é mais possível vincular Acordo/Convênio pela tela de TED — a antiga rota `/ted/<id>/vincula_instrumento` (formulário que pedia o id cru) foi removida por virar código morto; a coluna de instrumentos na Gestão de TED agora é só leitura (badges com SEI/nº do Convênio, uma por vínculo). O caminho passou a ser o inverso — ver itens B14 e C6 |
| A7 | ✅ BI TED: filtro por coordenação + quadro por coordenação. `bi_ted()` ganhou `por_coord`/`coordenacoes` (mesmo padrão de `por_orgao`/`por_situacao`/`por_ano`), reaproveitando `item['coordenacoes']` que `listar_teds()` já calculava a partir de `TED_Execucao_Interna`. TEDs sem nenhuma execução interna registrada caem no balde **"Não atribuído"** em vez de serem excluídos da contagem (mesmo espírito de honestidade sobre cobertura incompleta do resto do BI); um TED com mais de uma coordenação soma em cada uma (a soma de `qtd` por coordenação pode passar do total de TEDs, de propósito). `<select>` de coordenação adicionado ao formulário do BI, mesmo padrão dos outros selects |
| A8 | ✅ BI TED: filtro "órgão de origem" — usar siglas, não nome completo. Chave de agregação de `por_orgao` trocada de `unidade_descentralizadora` pra `sigla_ou_nome_orgao()`; `<select>` de órgão no BI passou a listar a sigla como rótulo (nome completo no `title`, mesmo padrão de A5), mantendo o nome completo como valor submetido (é o que a query de `listar_teds()` filtra) |
| A9 | ✅ BI TED: filtro "Ano". **Decisão: Opção B (manter + tooltip)** — conferido com dado real: 60 dos 363 TEDs (~16%) não têm `vigencia_inicio` preenchido; fração grande demais pra trocar a base do filtro com segurança sem perder TEDs da contagem quando o filtro de ano for aplicado. Mantido `aa_ano_plano_acao`, com tooltip no `<label>` explicando que é o ano de registro do plano de ação, não o início de vigência |
| A10 | ✅ Pedido novo (Igor) — Gestão TED: sem `coord` explícito na URL, a listagem vem pré-filtrada, estritamente, pela coordenação do usuário logado (`current_user.coord`) — TEDs não triados (sem nenhuma execução interna) ficam de fora do padrão. Adaptação do valor mágico `'usu'`/`'*'` já usado em Convênios/Acordos (`_filtro_coord_padrao()` em `project/ted/views.py`), mas sem a hierarquia de coordenações filhas dessas duas telas — aqui é sigla exata (`current_user.coord`), já que `TED_Execucao_Interna.coordenacao` é curadoria manual avulsa por TED, sem cadeia de `Programa_Interesse`. **Decisão de Igor aplicada**: em vez de afrouxar o filtro padrão, um aviso (`alert alert-warning`, mesmo padrão visual do projeto) aparece na tela quando há TEDs sem coordenação nenhuma no sistema todo (`total_teds_sem_coordenacao()`, contagem global, não só da vigência filtrada), com link direto pro filtro `coord=*`. **Complemento** (correção pontual, mesma leva): faltava o meio-termo entre "a minha" (padrão) e "todos" (link do aviso) — `<select>` de coordenação adicionado na barra de filtros (mesmo padrão visual dos demais), com todas as `Coords.sigla` (`coordenacoes_choices()`, reaproveitada) mais a opção "Todos" (`value="*"`, mesmo valor mágico do link do aviso — não `value=""`, que nesse filtro já significa "cair no padrão da minha coordenação"), pré-selecionado conforme o filtro efetivo (a coordenação do usuário quando é o padrão, ou o que estiver explícito na URL) |
| A11 | ✅ Pedido novo (Igor) — Gestão TED: ordem padrão da listagem (sem `sort` na URL) passou a ser por `vigencia_fim` ascendente — quem vence primeiro no topo —, com `NULLS LAST` explícito (`TED_PlanoAcao.vigencia_fim.asc().nullslast()`) pra quem não tem data de fim ir pro final, não pro topo |

### B. Convênios

| # | Item |
|---|---|
| B1 | Renomear título "Lista dos Programas de Convênio (Transferegov)" → "Cadastrar Programa de Convênio no SISTAC" |
| B2 | Tela de inserir/alterar Programa: campo "Sigla*" → "Sigla do Convênio ou Programa no CNPq" |
| B3 | Renomear menu "Programas" → "Programas do Transferegov" (mesma tela do B1, título duplicado no pedido original — considerar como um único ajuste) |
| B4 | Remover "Lista em execução" do menu |
| B5 | Remover "Em execução por UF e Programa" do menu + comentar a execução (mesmo padrão já feito em Acordos) |
| B6 | Remover "Histórico por Programa" do menu + comentar a execução (idem) |
| B7 | Remover "Mapa" do menu + comentar a execução (idem) |
| B8 | Criar item de menu "Gestão", com "Programas do Transferegov" como submenu |
| B9 | Convênio → Programa CNPq: tabela existe, nada grava nela ainda (cobertura 0% no Painel Executivo). **Confirmar**: o sistema já busca os Programas CNPq via DW? Se sim, avaliar se dá pra popular esse vínculo a partir de lá também (mesma ideia do item A1) |
| B10 | BI Convênios: filtro por coordenação + quadro por coordenação |
| B11 | BI Convênios: filtro "órgão de origem" — siglas, não nome completo |
| B12 | BI Convênios: filtro "Ano" — ano de início de vigência, ou tooltip |
| B13 | Gestão → Lista de Convênios: filtros no mesmo padrão da Gestão de TED |
| B14 | ✅ Gestão → Lista de Convênios → Convênio: seção "TEDs Vinculados" (modal) na tela de detalhes do Convênio (`convenio_detalhes.html`) — lista os TEDs já vinculados (com opção de desvincular) e um campo de busca (texto + `<datalist>` nativo do HTML5, sem lib nova) mostrando "TED nº — início do objeto" em vez do id cru, pra vincular um novo. Chama `ted.services.vincular_instrumento`/`desvincular_instrumento` diretamente (mesmo padrão já usado em `acordos/views.py` importando `core.services`) |

### C. Acordos

| # | Item |
|---|---|
| C1 | Gestão → Todos: filtros no mesmo padrão da Gestão de TED |
| C2 | **A coluna "#" não é um ID estável** (varia conforme ordenação/filtro) — não serve pra relacionamento. Usar o número SEI (`nnnnnn/aaaa-dd`, já obrigatório no cadastro) como identificador real |
| C3 | Renomear "Lista de Acordos/TEDs" → "Lista de Acordos" |
| C4 | Renomear "Inserir detalhes de um Acordo/TED" → "Inserir detalhes de um Acordo" |
| C5 | ✅ **Bug de dado**: campos Capital/Custeio/Bolsas em Acordo pertencem só ao CNPq — a fórmula comparava contra Valor CNPq + Valor EP indevidamente. Corrigido em `criar_acordo`/`atualizar_acordo` (`project/acordos/services.py`) pra comparar só contra Valor CNPq; tooltip adicionado em `add_acordo.html`. **Exceção documentada**: 6 acordos reais legados com "TED" no nome (ex: "ProfixJD-2022 - TED", "Centelha 2021 - TED", "PPP, PRONEM e PRONEX - TED") usavam `valor_epe` como forma alternativa de registrar recursos de TED antes de existir o módulo TED — `bolsas` nesses acordos guarda `valor_cnpq + valor_epe` de propósito, dado correto pra época (confirmado por Igor). Esses 6 registros **não foram alterados**; o alerta `alerta_nds` é isento pra qualquer acordo com "TED" no nome (checagem `'TED' in nome.upper()`), isenção temporária a ser removida quando esses acordos legados forem descontinuados/migrados pro módulo TED de verdade |
| C6 | ✅ Inserir campo pra vincular número de TED — mesmo padrão do item B14 (seção "TEDs Vinculados" em modal, dentro de `add_acordo.html`, com busca por `<datalist>` em vez de id cru) |
| C7 | BI Acordos: filtro por coordenação + quadro por coordenação |
| C8 | BI Acordos: filtro "órgão de origem" — siglas |
| C9 | BI Acordos: filtro "Ano" — ano de início de vigência, ou tooltip |

---

## Itens removidos do escopo

- **Programa Estratégico** (agrupar edições do mesmo Programa CNPq, ex:
  "Conhecimento Brasil 2024" + "2026"): confirmado por Igor que não é mais
  necessário. Removido do roadmap do Painel Executivo.

---

## 🟢 3. Itens pequenos, sem decisão ainda

- **3.1** — Não dá pra excluir modalidade de bolsa depois de cadastrada
- **3.2** — Separar sigla/nome completo da modalidade de bolsa
- **3.3** — Não dá pra editar/excluir Programa CNPq depois de cadastrado
- **3.4** — Comportamento do CSV mudou (revisão pendente, nunca foi
  conferida de fato)
- **3.5** — Upload de `.xlsx` pela tela do `cargaPDCTR` (hoje só funciona
  via terminal, decisão deliberada de adiar)

---

## 4. Módulo Demandas

Deixado de lado desde o início da frente de BI, a pedido de Igor — maior
módulo do sistema (~3.371 linhas), ainda com pendências da fase de
refatoração original (grupos E, F, G).

---

## 5. Itens futuros, sem prazo

- **E-mails** — tela de configuração de textos de e-mail pelo admin master
  (ainda nem começou)
- **Integração de verdade TED ↔ Acordo/Convênio** — rastrear qual TED
  financiou qual Acordo/Convênio especificamente (hoje o Painel Executivo
  evita isso mostrando Captado/Executado separados, mas a reconciliação
  exata não existe)
- **TED → Gestão**: clicar no número do TED deveria abrir o detalhamento
  completo, mesmo padrão de Convênios/Acordos
- **Mapas** — OpenStreetMap bloqueado no preview do Codespace (pode não se
  repetir em produção)
- **Integração Oracle DW** — ainda sem biblioteca cliente no ambiente de
  desenvolvimento

---

## Nota sobre versionamento

Não existe uma regra formal de versionamento no projeto — o padrão seguido
até agora (`5.0.13` → `5.0.14`) foi só incrementar o último número, por
precedente histórico, sem lógica definida. Sugestão (não decidida):
incrementar o número do **meio** pra levas grandes de funcionalidade nova
(essa leva de BI seria `5.1.0`), reservando o último número pra correções
pontuais dali em diante. Fica a critério de Igor.

---

## Sugestão de sequenciamento (Claude)

A ordem por módulo (TED → Convênios → Acordos) faz sentido e mantenho.
Duas sugestões de ajuste **dentro** dessa ordem:

1. ✅ **Adiantar os dois itens que são bugs de verdade, não só polimento**:
   A2 (texto branco ilegível) e C5 (Capital/Custeio/Bolsas somando EP
   indevidamente). Feito.
2. ✅ **Fazer A6/B14/C6 como um bloco só**, já que são as três pontas do
   mesmo relacionamento (vincular TED a partir de Convênio/Acordo, não o
   inverso). Feito — `vincular_instrumento`/`desvincular_instrumento`/
   `teds_vinculados`/`teds_choices` em `project/ted/services.py`, telas
   novas em `add_acordo.html` e `convenio_detalhes.html`, rota antiga
   `/ted/<id>/vincula_instrumento` removida. Achado lateral corrigido de
   quebra: a ordenação padrão de `listar_teds()` (só por `ano`, sem
   tiebreaker) deixava a paginação instável quando havia empate — um
   teste (`test_paginacao_segunda_pagina_traz_o_restante`) capturou isso
   depois que outro teste da suíte reescreveu a tabela de TED numa ordem
   diferente; corrigido com um tiebreaker por `id`.

Fora isso, a ordem proposta está boa — trato como confirmada, a menos que
você quera ajustar.
