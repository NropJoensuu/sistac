# Etapa 4 — Painel Executivo: Proposta Funcional Detalhada

Continuação do esboço em `roadmap_bi_sistac.md`, agora com tudo que aprendemos
nas Etapas 1-3 (cobertura real de curadoria, estrutura real de dados). Ainda
sem código — proposta funcional/produto.

---

## 1. Acesso — corrigido: é público, como os outros BIs

O roadmap original sugeria acesso restrito, mas Igor confirmou: **o Painel
Executivo é aberto ao público, sem login** — mesmo padrão de Convênios/
Acordos/TED (respeitando o interruptor de sistema do admin master, se
existir um pro Painel Executivo, seguindo o mesmo modelo dos outros).

Isso elimina a necessidade de qualquer papel novo de "Diretoria"/
"Coordenação-Geral" — o painel é só mais uma tela pública de BI, só que
consolidando os outros três em vez de mostrar um instrumento isolado.

Segue o mesmo interruptor duplo (Gestão/BI) que já existe pros outros
módulos, se fizer sentido ter um `bi_painel_executivo` em `Sistema`
controlando a visibilidade, do mesmo jeito que `bi_conv`/`bi_acordo`/
`bi_ted` já funcionam hoje.

---

## 2. O problema central: a curadoria está incompleta, e o painel precisa ser honesto sobre isso

Hoje, cobertura real de vínculo a Programa CNPq:

| Instrumento | Cobertura | Como foi conseguida |
|---|---|---|
| Convênios | Alta (curada manualmente há tempos, já na planilha da COPES) | Curadoria manual histórica |
| Acordos | 108 de 139 processos-mãe (78%) | Curadoria automática + fila manual, recém-criada |
| TED | ~4% (13 de 301, na amostra testada) | Só nome/tema batendo por texto — a maioria precisa de curadoria manual que ainda não foi feita |

**O Painel Executivo não pode fingir que consolida 100% dos dados.** Se
somar só o que já está vinculado, sub-representa (principalmente TED). Se
tentar "advinhar" o resto, gera número errado pra decisão de Presidência —
o pior cenário possível.

**Proposta:** todo indicador consolidado do painel vem acompanhado de um
indicador de cobertura ("X% dos TEDs deste programa já têm vínculo
confirmado") — visível, não escondido. Isso é diferente do BI de cada
módulo (que já mostra o dado bruto do módulo, sem esse problema de
agregação cross-instrumento).

---

## 3. Indicadores (revisão do esboço original, com dado real)

### Nível 1 — Cards de resumo (topo da tela)
- Valor total consolidado (Convênio + Acordo + TED), com cobertura de curadoria ao lado
- Quantidade de Programas CNPq com pelo menos 1 instrumento vinculado
- Quantidade de Programas Estratégicos com dado consolidado disponível

### Nível 2 — Ranking por Programa CNPq
- Top N programas por valor total consolidado
- Composição por instrumento (barra empilhada: quanto vem de Convênio/Acordo/TED)
- Indicador de cobertura por programa (%  do valor do programa que já está
  curado vs. estimado/pendente)

### Nível 3 — Programas Estratégicos (agrupamento manual de Programas CNPq)
Exemplo já confirmado com dado real: "Conhecimento Brasil" — dois Programas
CNPq distintos (edições 2024 e 2026), já com TEDs de R$ 230 mi e R$ 822 mi
identificados. O painel precisa somar isso numa visão só, mesmo sendo
tecnicamente dois programas separados no cadastro.

**Isso exige uma tabela nova**: `ProgramaEstrategico` (nome, descrição) +
relação N:N com Programa CNPq — ainda não existe. Curadoria manual também
(não tem como inferir "Conhecimento Brasil 2024" e "Conhecimento Brasil
2026" são a mesma iniciativa estratégica só pelo nome, com segurança).

### Nível 4 — Evolução temporal
Série histórica consolidada (por ano), mesma limitação de cobertura do
Nível 1/2 — mostrar cobertura junto, não só o valor.

---

## 4. Gráficos sugeridos
- Cards de KPI (valor total, cobertura, qtd. programas)
- Ranking em barras horizontais (Top Programas CNPq)
- Barras empilhadas (composição por instrumento, por programa)
- Linha temporal (evolução consolidada)
- Indicador de cobertura (gauge ou barra de progresso) — visível em cada
  nível de agregação, não só uma vez na tela

## 5. Filtros sugeridos
Programa CNPq, Programa Estratégico (quando existir o cadastro), período,
instrumento (permitir isolar só Convênio, só Acordo, só TED, dentro da
visão consolidada)

---

## 6. O que precisa existir antes de programar a tela em si

1. Decisão de acesso (seção 1)
2. Tabela `ProgramaEstrategico` + vínculo N:N com Programa CNPq (curadoria
   manual, mesmo padrão já usado em TED/Acordo)
3. Aceitar que cobertura parcial é normal e vai aparecer na tela — não é
   bug, é reflexo do estado real da curadoria

## 7. Complexidade: Alta (confirmado do roadmap original)
Depende de tudo que já existe (Etapas 1-3, prontas) mais duas peças novas
(controle de acesso, cadastro de Programa Estratégico) — é a etapa mais
correta de deixar por último, e continua sendo.
