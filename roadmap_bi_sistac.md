# Roadmap de Evolução do SISTAC — BI e Painel Executivo

Proposta funcional/produto, sem código e sem arquitetura técnica detalhada.
Foco: demonstrar valor institucional e viabilidade para homologação e produção.

**Premissa central:** as telas analíticas que já existem (Resumo por Programa,
Quadro UF × Programa, Mapa — em Convênios e Acordos) não são descartadas — são a
**primeira geração do BI**. As 4 etapas abaixo evoluem essa base, não a substituem
do zero.

---

## Visão geral das 4 etapas

| Etapa | Objetivo | Complexidade |
|---|---|---|
| 1 — BI Convênios | Evoluir as telas analíticas já existentes | **Baixa** |
| 2 — BI Acordos | Evoluir as telas + trazer a cadeia processo mãe→filho→chamada→bolsista | **Média** |
| 3 — Módulo TED completo | Trazer TED pra dentro do SISTAC (gestão + BI) | **Alta** |
| 4 — Painel Executivo | Visão consolidada por Programa CNPq, pra alta gestão | **Alta** |

---

## ETAPA 1 — BI Convênios

### Objetivo
Dar à gestão uma visão consolidada e acionável da carteira de convênios — hoje
dispersa em telas separadas (resumo, quadro UF×programa, mapa) — cruzando
dinheiro, geografia, programa e tempo numa experiência só.

### Público-alvo
Coordenação-Geral (COPES), coordenadores de área, chefias que acompanham
captação e execução de convênios.

### Indicadores
- Valor total em carteira (repasse + contrapartida), com quebra por situação
- Taxa de desembolso (desembolso ÷ repasse) — indicador de execução real
- Quantidade de convênios por situação (em execução, encerrado, inadimplente, etc.)
- Distribuição geográfica por UF
- Distribuição por Programa CNPq e por Programa Estratégico
- Evolução temporal (novos convênios e valores, por ano)
- Convênios com vigência a vencer nos próximos 3/6/12 meses
- Ranking de parceiros (FAPs) por volume de recursos

### Gráficos sugeridos
- Mapa do Brasil (coroplético) — valor por UF
- Barras horizontais — top Programas CNPq por valor
- Linha temporal — evolução anual de novos convênios e valores
- Rosca/pizza — distribuição por situação
- Tabela-ranking — parceiros (FAPs) por volume

### Filtros sugeridos
Programa CNPq, Programa Estratégico, UF, parceiro/FAP, situação, ano/período de
vigência

### Benefícios para a gestão
- Visão consolidada sem precisar abrir convênio por convênio
- Identificação de risco (baixa execução, vigência vencendo) antes que vire problema
- Base concreta para decisões de renovação ou novo aporte

### Complexidade: **Baixa**
Os dados já existem e já são usados nas 3 telas atuais — é evolução de UI/
agregação, não integração nova.

---

## ETAPA 2 — BI Acordos

### Objetivo
Mesma lógica da Etapa 1, mas cobrindo a cadeia mais longa dos Acordos: processo
mãe → processo filho → chamada → bolsista → pagamento — hoje só visível
navegando por cada nível separadamente.

### Público-alvo
Mesmo público da Etapa 1, mais quem acompanha chamadas e processos vinculados a
acordos especificamente.

### Indicadores
- Valor total de acordos (recursos CNPq + recursos das FAPs), separados
- Quantidade de processos mãe e processos filho por acordo
- Quantidade de chamadas vinculadas por acordo/programa
- Quantidade de bolsistas ativos, por acordo e por programa
- Situação de pagamentos (em dia / pendente / atrasado)
- Distribuição por Programa CNPq e Programa Estratégico
- Evolução temporal (novos acordos e valores, por ano)

### Gráficos sugeridos
- Mesmos tipos da Etapa 1 (mapa, barras, linha temporal, rosca)
- **Gráfico de funil** (novo, específico de Acordos): Acordo → Processos mãe →
  Processos filho → Chamadas → Bolsistas — mostra visualmente onde a execução
  "afunila" ou trava

### Filtros sugeridos
Programa CNPq, Programa Estratégico, situação, ano — UF quando aplicável ao
acordo/processo

### Benefícios para a gestão
- Visão da cadeia de execução completa, não só do valor "no papel" do acordo
- Identifica gargalos (ex: muitos processos mãe sem processo filho associado,
  chamadas sem bolsistas)

### Complexidade: **Média**
Mais entidades relacionadas que precisam ser agregadas corretamente (processos
mãe/filho, chamadas, bolsistas, pagamentos), mas ainda sem integração externa —
os dados já estão no SISTAC.

---

## ETAPA 3 — Módulo TED completo

### Objetivo
Trazer o TED pra dentro do SISTAC como instrumento de gestão de verdade — hoje
não existe nem tela de gestão nem BI, é acompanhado fora do sistema. Só depois
da tela de gestão existir é que um BI de TED faz sentido.

### Público-alvo
Quem hoje acompanha TED manualmente, fora do SISTAC.

### Visão funcional (sem entrar em implementação)
- **Gestão**: listagem de TEDs do CNPq (carregados da fonte de dados aberta),
  com detalhe de valor, situação, vigência, órgão de origem
- **Vínculo a Programa CNPq**: como já mapeado na investigação anterior, esse
  vínculo é majoritariamente manual — a tela de gestão precisa ter uma ação de
  "associar a um Programa CNPq", não depender de automação completa
- **BI**: só depois da gestão estar populada, replicar o padrão das Etapas 1 e 2
  (valor por órgão de origem no lugar de valor por UF, já que TED não tem
  necessariamente uma UF associada; situação; evolução temporal)

### Indicadores (visão de alto nível)
- Valor total captado, por órgão de origem (MCTI, FNDCT, MMA, MS, etc.)
- Quantidade de TEDs por situação (aprovado, em elaboração, em análise)
- Percentual de TEDs já vinculados a um Programa CNPq (indicador de progresso
  da curadoria, não um dado 100% preenchido desde o início)
- Evolução temporal (por ano)

### Gráficos sugeridos
- Barras — valor por órgão de origem
- Rosca/pizza — distribuição por situação
- Linha temporal — evolução anual
- Indicador simples (gauge/percentual) — progresso da curadoria de vínculo a
  Programa CNPq

### Filtros sugeridos
Órgão descentralizador, situação, ano, Programa CNPq vinculado (quando disponível)

### Benefícios para a gestão
Primeira vez que o CNPq teria visão sistemática e centralizada dos TEDs
recebidos — hoje essa informação está dispersa e não é acompanhada dentro de
um sistema de gestão único.

### Complexidade: **Alta**
Depende de carga de dados de fonte externa, de um módulo de gestão inteiro
construído do zero, e de um processo de curadoria manual contínuo (não é um
trabalho que "termina" — TEDs novos vão continuar precisando de vínculo manual).

---

## ETAPA 4 — Painel Executivo

### Objetivo
Visão consolidada, para quem decide no nível mais alto, organizada pelo
**Programa CNPq** — não pelo instrumento. Responde à pergunta "como está indo
o Conhecimento Brasil (ou o INCT, ou a Pró-Amazônia) no total?", somando
Convênio + Acordo + TED do mesmo programa numa vista só.

### Público-alvo
Presidência, Diretoria, Coordenações-Gerais.

### Indicadores
- Valor total captado/gerido por Programa CNPq (somando os 3 instrumentos)
- Valor total por Programa Estratégico (agrupando vários Programas CNPq quando
  fizer sentido, ex: várias edições de "Conhecimento Brasil")
- Cobertura geográfica consolidada (UF), quando aplicável
- Evolução temporal consolidada, por programa
- Ranking de programas por volume total de recursos
- Comparativo entre instrumentos (quanto vem de Convênio vs. Acordo vs. TED, por programa)

### Gráficos sugeridos
- Cards de KPI no topo (valor total, quantidade de programas ativos, etc.)
- Mapa consolidado do Brasil
- Ranking (barras horizontais) de Programas CNPq por volume total
- Gráfico de composição (barras empilhadas) — quanto de cada programa vem de
  cada instrumento

### Filtros sugeridos
Programa CNPq, Programa Estratégico, período

### Benefícios para a gestão
Decisão estratégica de alto nível sem precisar entrar em cada módulo
separadamente — a pergunta "quanto o CNPq está investindo nisso, no total?"
finalmente tem uma resposta direta.

### Importante
**O Painel Executivo não substitui os BIs de Convênios e Acordos** (nem o
futuro BI de TED) — ele **consome** as informações já consolidadas por eles.
Se um número parecer errado no Painel Executivo, a explicação está sempre
rastreável até o BI do instrumento específico.

### Complexidade: **Alta**
Depende que as Etapas 1–3 já estejam prontas e alimentando dados — é a camada
de consumo final, não de produção de dado. Não faz sentido antecipar essa
etapa.

---

## Proposta de navegação do SISTAC

```
Home
Convênios
  ├── Gestão   (telas operacionais já existentes)
  └── BI       (Etapa 1)
Acordos
  ├── Gestão   (telas operacionais já existentes)
  └── BI       (Etapa 2)
TEDs
  ├── Gestão   (novo — Etapa 3)
  └── BI       (novo — Etapa 3)
Painel Executivo   (Etapa 4 — acesso restrito a Presidência/Diretoria/Coord.-Gerais)
```

Cada módulo (Convênios, Acordos, TEDs) passa a ter a mesma estrutura de duas
abas — Gestão (operação do dia a dia) e BI (visão gerencial) — dando
consistência visual e de navegação em todo o sistema.
