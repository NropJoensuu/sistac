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
- **Bug — `TypeError` na edição de Acordo/Convênio com valor monetário
  `None`** (reportado por Igor, 06/08/2026): `/acordos/{id}/{lista}/update`
  quebrava com `TypeError: bad operand type for abs(): 'NoneType'` ao
  chamar `locale.currency(None, ...)` para Acordos com `valor_cnpq`,
  `valor_epe`, `capital`, `custeio` ou `bolsas` nulos no banco — dado
  legado, padrão existe desde o commit inicial do projeto (19/08/2022).
  257 dos 303 Acordos hoje têm `capital`/`custeio` `None` (os outros 3
  campos nunca são `None` na base atual). Corrigido tratando `None` como
  zero (`campo or 0`) em `project/acordos/views.py` (`update()`) e
  `project/acordos/services.py` (`_formata_lista_acordos`, mesmo padrão,
  mesmos campos). Mesmo padrão também encontrado e corrigido em
  `project/convenios/services.py` (`detalhes_convenio()`, campos
  `VL_*_CONV` e `VALOR_PARCELA_CRONO_DESEMBOLSO`) — dado importado do
  SICONV/Transferegov, mesmo risco de nulo. TED já tratava `None`
  corretamente (`or 0` já presente). Não corrigido o dado em si, só o
  comportamento da tela. Teste de regressão em
  `tests/test_acordos_nucleo.py::test_update_acordo_com_capital_none_nao_quebra`.

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
| B1 | ✅ Título "Lista dos Programas de Convênio" → "Cadastrar Programa de Convênio no SISTAC" (`lista_programas_pref.html`) |
| B2 | ✅ Tela de inserir/alterar Programa: label do campo "Sigla:" → "Sigla do Convênio ou Programa no CNPq:" (`ProgPrefForm.sigla`, `project/convenios/forms.py`) |
| B3 | ✅ Rótulo do menu "Programas" → "Programas do Transferegov" (mesma tela do B1, tratado como ajuste único) |
| B4 | ✅ Removido "Lista em execução" do menu (`base.html`) — a rota (`lista_convenios_SICONV` com `lista='em execução'`) continua ativa, só não tem mais link direto, pois é a mesma rota usada por "Lista todos" |
| B5 | ✅ Removido "Em execução por UF e Programa" do menu; view `quadro_convenios` comentada em `project/convenios/views.py` (não apagada), mesmo padrão já usado em Acordos (`quadro_acordos`) |
| B6 | ✅ Removido "Histórico por Programa" do menu; view `resumo_convenios` comentada (idem) |
| B7 | ✅ Removido "Mapa" do menu; view `brasil_convenios` comentada (idem). `tests/test_convenios_dashboards.py` (as 3 rotas acima) removido — não havia mais rota ativa pra testar |
| B8 | ✅ Item de menu "Gestão" criado no dropdown de Convênios (mesmo padrão de Acordos: `<h6 class="dropdown-header">`), com "Lista todos", "Programas do Transferegov" e "Mensagens SICONV" dentro; "BI Convênios" segue fora, após um divisor, controlado por `Sistema.bi_conv` |
| B9 | Convênio → Programa CNPq: tabela existe, nada grava nela ainda (cobertura 0% no Painel Executivo). **Deixado de fora desta rodada de propósito** — precisa de um mecanismo de curadoria novo (maior que os demais itens B1-B13), fica pra outra rodada. **Confirmar**, quando entrar em pauta: o sistema já busca os Programas CNPq via DW? Se sim, avaliar se dá pra popular esse vínculo a partir de lá também (mesma ideia do item A1) |
| B10 | ✅ BI Convênios: filtro por coordenação + quadro por coordenação. `bi_convenios()` ganhou `por_coord`/`opcoes_coord` (mesmo padrão de `por_orgao` em `bi_ted()`), usando `Programa_Interesse.coord` — dado estrutural nativo, sem curadoria manual, então (ao contrário de TED) não há convênio com mais de uma coordenação |
| B11 | ✅ **Redefinido por Igor**: não é "órgão de origem" (esse conceito não existe em Convênio, diferente de TED) — é filtro por **Região**. Criado mapa UF→Região padrão IBGE (27 UFs, `_REGIAO_POR_UF` em `project/convenios/services.py`, função `regiao_da_uf()`), usado pra agregar `por_regiao`/`opcoes_regiao` (5 regiões) em `bi_convenios()`, a partir de `Proposta.UF_PROPONENTE` (já usada no filtro `uf` existente) |
| B12 | ✅ **Decisão: Opção A (trocar a base do filtro)** — conferido com dado real: dos 361 convênios reais na base de dev (excluindo dados de teste), **100% têm `DIA_INIC_VIGENC_CONV` preenchido** (0% de nulos), bem mais completo que o equivalente em TED (~16% de nulos, item A9). `Convenio.ANO` também nem sempre bate com o ano de início de vigência (93% de concordância nos dados reais — parece ser o ano de registro/numeração do convênio, não de vigência). Com dado de vigência tão mais completo, o filtro/evolução "Ano" do BI passou a usar o ano extraído de `DIA_INIC_VIGENC_CONV` diretamente (`_ano_inicio_vigencia()`), no lugar de `Convenio.ANO` — ao contrário de TED, aqui não foi preciso manter tooltip como meio-termo |
| B13 | ✅ Gestão → Lista de Convênios (`lista_convenios_SICONV`/`list_convenios.html`): paginação, ordenação por clique no cabeçalho e filtros adicionais (situação, UF, programa, busca) no mesmo padrão de `listar_teds()`/`gestao.html` (TED) — `_CHAVES_ORDENACAO_CONV`, `page`/`sort`/`dir` como querystring. Exportação CSV (`/static/convenios.csv`) já existia e continua respeitando o filtro ativo (regravado a cada carregamento da lista, com o conjunto completo filtrado, sem paginar — mesmo espírito de `exportar_teds_csv`). O filtro por coordenação (`ListaForm`, com os valores especiais `'usu'`/`'*'`/`'inst'`/sigla parcial já existentes em `_subquery_programa()`) foi mantido como estava, sem migrar pra querystring. **Achado lateral corrigido**: a rota não tinha `@login_required` mas usava `current_user.id` incondicionalmente — acesso anônimo derrubava a página com `AttributeError` em vez de redirecionar pro login; corrigido |
| B14 | ✅ Gestão → Lista de Convênios → Convênio: seção "TEDs Vinculados" (modal) na tela de detalhes do Convênio (`convenio_detalhes.html`) — lista os TEDs já vinculados (com opção de desvincular) e um campo de busca (texto + `<datalist>` nativo do HTML5, sem lib nova) mostrando "TED nº — início do objeto" em vez do id cru, pra vincular um novo. Chama `ted.services.vincular_instrumento`/`desvincular_instrumento` diretamente (mesmo padrão já usado em `acordos/views.py` importando `core.services`) |

### C. Acordos

| # | Item |
|---|---|
| C1 | ✅ Gestão → Todos (`lista_acordos`/`lista_acordos.html`): paginação, ordenação por clique no cabeçalho e filtros adicionais (situação, EP UF, busca por nome/SEI) no mesmo padrão de `listar_teds()`/`listar_convenios_siconv()` (B13) — `_CHAVES_ORDENACAO_ACORDO`, `page`/`sort`/`dir` como querystring. Como `_formata_lista_acordos()` retorna uma lista de listas indexada por posição (não por nome de coluna) e a situação exibida pode ser corrigida por regra de negócio em tempo de leitura, o filtro/ordenação/paginação são aplicados em Python sobre a lista já formatada, não na query SQL. A exportação CSV (`/static/acordos.csv`) já existia e passa a respeitar o filtro ativo (conjunto completo filtrado, sem paginar). O filtro por coordenação (`ListaForm`) foi mantido como estava, sem migrar pra querystring — mesma decisão do B13. **Achados laterais corrigidos**: (1) a rota não tinha `@login_required` mas usava `current_user.id` incondicionalmente — acesso anônimo derrubava a página com `AttributeError` em vez de redirecionar pro login (mesmo padrão de bug já corrigido em Convênios/B13); (2) o texto "(UF: ...)" da listagem por UF indexava `acordos[0][5]`, que quebrava com `IndexError` quando o filtro não retornava nenhum acordo pra UF selecionada — trocado por `lista[2:4]` (a UF já vem embutida no próprio parâmetro de rota) |
| C2 | ✅ Coluna "#" trocada de posição-na-lista pro número SEI do acordo (`acordo[3]`, já obrigatório e único) — `lista_acordos.html`. Confirmado antes: todos os links de ação já usavam o ID real do banco (`acordo[0]`), então a correção é só de exibição, sem risco de quebrar navegação |
| C3 | ✅ Título "Lista de Acordos/TEDs" → "Lista de Acordos" (`lista_acordos.html`) |
| C4 | ✅ Título "Inserir detalhes de um Acordo/TED" → "Inserir detalhes de um Acordo" (`add_acordo.html`); o título irmão da mesma tela em modo edição ("Visualizar/Alterar detalhes do Acordo/TED") também teve o "/TED" removido, por consistência — mesmo padrão de rótulo, mesma tela. As demais ~10 ocorrências de "Acordo/TED" espalhadas por outras telas do módulo (chamadas, processos-mãe, financeiro etc.) **não foram tocadas**: o pedido era especificamente sobre esses dois títulos, e renomear terminologia em telas não mencionadas seria decisão de escopo maior, fora do que foi pedido |
| C5 | ✅ **Bug de dado**: campos Capital/Custeio/Bolsas em Acordo pertencem só ao CNPq — a fórmula comparava contra Valor CNPq + Valor EP indevidamente. Corrigido em `criar_acordo`/`atualizar_acordo` (`project/acordos/services.py`) pra comparar só contra Valor CNPq; tooltip adicionado em `add_acordo.html`. **Exceção documentada**: 6 acordos reais legados com "TED" no nome (ex: "ProfixJD-2022 - TED", "Centelha 2021 - TED", "PPP, PRONEM e PRONEX - TED") usavam `valor_epe` como forma alternativa de registrar recursos de TED antes de existir o módulo TED — `bolsas` nesses acordos guarda `valor_cnpq + valor_epe` de propósito, dado correto pra época (confirmado por Igor). Esses 6 registros **não foram alterados**; o alerta `alerta_nds` é isento pra qualquer acordo com "TED" no nome (checagem `'TED' in nome.upper()`), isenção temporária a ser removida quando esses acordos legados forem descontinuados/migrados pro módulo TED de verdade |
| C6 | ✅ Inserir campo pra vincular número de TED — mesmo padrão do item B14 (seção "TEDs Vinculados" em modal, dentro de `add_acordo.html`, com busca por `<datalist>` em vez de id cru) |
| C7 | ✅ BI Acordos: filtro por coordenação + quadro por coordenação. `bi_acordos()` ganhou `por_coord`/`opcoes_coord` (mesmo padrão de B10 em Convênios), usando `Acordo.unidade_cnpq` — dado estrutural nativo, já usado em `_base_query_acordos`/`_resolver_unidade`, sem curadoria manual |
| C8 | ✅ **Redefinido por Igor**: não é "órgão de origem" (esse conceito não existe em Acordo, mesma situação do B11 em Convênios) — é filtro por **Região**. Reaproveita o mapa UF → Região (padrão IBGE) já criado em `project/convenios/services.py` (`regiao_da_uf`/`REGIOES`, importado em `acordos/services.py` — não duplicado), agregando `por_regiao`/`opcoes_regiao` em `bi_acordos()` a partir de `Acordo.uf`. O filtro por região é aplicado em Python (após a query), já que região não é uma coluna própria |
| C9 | ✅ **Decisão: nenhuma mudança necessária.** Diferente de Convênio (`Convenio.ANO` vs. `DIA_INIC_VIGENC_CONV`, item B12) e de TED (item A9), Acordo nunca teve um campo "ANO" separado — o filtro/evolução "Ano" do BI já usava `Acordo.data_inicio.year` diretamente desde a Etapa 2, então não havia ambiguidade a resolver. Conferido com dado real, por precaução: dos 272 acordos reais na base de dev (excluindo nome contendo "teste"), apenas 4,0% têm `data_inicio` nulo — taxa baixa (bem melhor que os ~16% de TED), então manter o filtro direto (sem tooltip) é seguro. Decisão e o porquê documentados no docstring de `bi_acordos()` |

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

## Sugestão de sequenciamento

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

---

## Nota de correção — "257 de 303 Acordos com capital/custeio None" (06/08/2026)

Esse número foi medido no **banco de desenvolvimento**, não confirmado em
produção. Igor esclareceu: a população desses campos depende de curadoria/
carga de bolsas que só é feita manualmente com o tempo — o ambiente de dev
não passou por esse processo, então o número alto é característica do
banco de teste, não necessariamente do estado real de produção. A correção
do bug (`campo or 0` em vez de deixar quebrar) continua válida de qualquer
forma, como proteção defensiva — um campo `None` sempre pode voltar a
acontecer (import novo, edição incompleta), independente da causa raiz.

## Achado — comparação DW × planilha de bolsas (06/08/2026)

Investigado a pedido de Igor: os campos que a consulta DW (`consultaDW`,
tipo `'filhos_chamadas'`) busca **não são os mesmos** da planilha de
bolsas ("05-2026 - Bolsas.xlsx", carregada via `cargaPDCTR`). Há
sobreposição real (Processo, Nome, CPF, Situação, datas, Processo Mãe,
Nome da Chamada, Modalidade, Nível, Cod Programa), mas:

- **A planilha é por pagamento** (uma linha por mês pago); **o DW já vem
  agregado** (`SUM` por processo — `PAGO_BOLSAS`/`PAGO_CAPITAL`/
  `PAGO_CUSTEIO`).
- **Só a planilha tem**: contexto institucional/geográfico completo (Cod
  Inst, Nome da Instituição, Sigla, UF, Região, Cidade, País), hierarquia
  organizacional (Diretoria, Coordenação-Geral, Coordenação, Comitê),
  Sigla da Chamada, Demanda/Natureza da Demanda, descrição da modalidade
  (o DW só tem o código), nome do Programa (idem), Grande Área/Área de
  Conhecimento, dados do Coordenador, detalhamento de pagamento (data,
  tipo, moeda, taxa de bancada, prêmio, taxa escolar).
- **Só o DW tem** (consulta `filhos_chamadas`): `ESTADO_FOMENTO`,
  `QTD_BOLSAS` (soma de bolsas pagas *daquele processo-filho específico*,
  não contagem de filhos), `DTA_CARGA` (data de carga do próprio DW).
- **Atenção, não confundir dois campos parecidos de consultas diferentes**:
  `QTD_FILHOS` (consulta `processos_chamadas`, nível mãe) é quem de fato
  conta processos-filho distintos por processo-mãe
  (`COUNT(DISTINCT COD_PROC)` agrupado por `COD_PROC_MAE`). `QTD_BOLSAS`
  (consulta `filhos_chamadas`, nível filho) é outra coisa — soma de
  `FT_PAGAMENTO.QTD_BOLSAS` daquele filho, mais parecido com `mens_pagas`
  de `Processo_Filho`.

**Hipóteses de Igor sobre os campos do DW, com anotação**:
- `ESTADO_FOMENTO` ≈ situação do SIGEF: plausível conceitualmente (os dois
  tratam do "estado" do processo), mas **não confirmado** — não há como
  verificar sem comparar dado real do DW lado a lado com uma carga SIGEF
- `DTA_CARGA`: ao espelhar localmente, usar a data do commit/sincronização
  local (não a data de carga do DW em si) — combinado

**Conclusão**: as duas fontes não são substituíveis uma pela outra sem
perda de informação. A planilha tem mais contexto institucional/geográfico
(mais útil pro BI territorial); o DW vem oficial e agregado, sem depender
de exportação manual.

## Achado — carga de situações via SIGEF (06/08/2026) — ✅ resolvido

Existe integração com o SIGEF, mas — como o PDCTR — é **manual, via
upload de planilha**, não uma consulta em tempo real. Rota
`/acordos/carrega_sit_sigef`, função `cargaSit()`
(`project/acordos/services.py`): lê só 2 colunas da planilha ("Processo",
"Situação") e atualiza o campo `situ_filho` dos registros já existentes em
`Processo_Filho` e `PagamentosPDCTR` — não cria dado novo, só sincroniza
status.

**Bug confirmado e corrigido**: `cargaSit()` usava `xlrd.open_workbook()`
— a mesma biblioteca que só lê `.xls` antigo, não `.xlsx`, já corrigida no
`cargaPDCTR` mas não replicada aqui. Migrada pro mesmo padrão com
`openpyxl` (`load_workbook(..., read_only=True)` +
`iter_rows(values_only=True)`), mantendo a lógica de negócio idêntica.
`import xlrd` removido do módulo (não era mais usado em nenhum outro
lugar). Teste de regressão em
`tests/test_acordos_carga_sit.py::test_cargaSit_le_xlsx_e_atualiza_situacao`.

Ao revisar a rota, dois bugs reais adicionais encontrados e corrigidos:
- Faltava `@login_required` em `carrega_sit_sigef`, mas a rota usa
  `current_user.id` incondicionalmente (mesmo padrão de bug já visto em
  `lista_acordos`/Convênios-B13) — um acesso anônimo quebrava com
  `AttributeError` em vez de redirecionar pro login.
- A rota exigia `proc_mae`/`edic`/`epe`/`uf` na URL, mas `edic`/`epe`/`uf`
  nunca eram usados no corpo da função, e `cargaSit()` não é filtrada por
  um `proc_mae` — ela atualiza todos os processos-filho encontrados na
  planilha. `proc_mae` só servia pra escolher o destino do redirect final.
  Parâmetros removidos da rota (`/acordos/carrega_sit_sigef`, sem
  argumentos), redirect ajustado pra `core.inicio` (mesmo padrão do
  PDCTR) — não precisa mais de tela intermediária pedindo esses dados.

## Achado — PDCTR e SIGEF sem acesso pelo menu (06/08/2026) — ✅ resolvido

Confirmado: nem `/carregaPDCTR` nem `/carrega_sit_sigef` tinham link no
menu — só acessíveis digitando a URL direto, mesmo problema já visto
antes com o PDCTR sozinho. **Pedido de Igor**: as duas cargas devem ficar
acessíveis no contexto de usuários admin (menu Carga, mesmo padrão das
outras cargas do sistema — SICONV, DW, TED).

Adicionados os dois links no dropdown "Carga" (`project/templates/base.html`),
dentro do bloco `{% if current_user.trab_acordo == 1 %}` (mesma permissão
dos outros itens de carga do módulo Acordos: Pega Programas/Chamadas/
Financeiro DW), antes do divisor que separa do bloco de Convênios.

## Novo item de produto — menu "Instrumentos" vira "Ações" (06/08/2026)

Proposta de Igor, registrada para avaliação futura (não implementada
ainda): substituir o menu "Instrumentos" por "Ações", trazendo as
informações de Chamadas — permitindo ver ações que não envolvem Acordo,
Convênio nem TED. Precisa de desenho funcional antes de implementar (o
que exatamente aparece nessa tela, de onde vêm os dados de Chamadas sem
instrumento associado).
