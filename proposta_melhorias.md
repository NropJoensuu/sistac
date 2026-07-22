# Proposta de Melhorias — sistac

Documento de planejamento, sem código ainda. Organizado por área, com o `users`
priorizado conforme combinado. Cada item indica o que já sabemos do código hoje e
qual decisão de produto precisa ser tomada antes de implementar.

---

## 1. Usuários (prioridade atual)

### 1.1 Painel de "Funcionalidades do sistema" — **novo**
Hoje as flags `funcionalidade_conv` / `funcionalidade_acordo` / `funcionalidade_instru`
(que acabamos de habilitar manualmente no banco) só são alteráveis direto no banco de
dados — não existe nenhuma tela no sistema para isso. Elas controlam se as permissões
"trabalha com convênios/acordos/instrumentos" podem ser atribuídas a um usuário.

**Decisão pendente:** quem deveria poder alterar isso?
- Opção A: um novo papel "super admin", acima do `admin` atual
- Opção B: o próprio `admin` atual, numa tela nova (ex: `/admin_config_sistema`)

Sugestão minha: começar pela Opção B (mais simples, sem criar hierarquia de papéis
nova) e só evoluir para super-admin se, na prática, times diferentes precisarem de
níveis diferentes de acesso.

### 1.2 Autogestão de conta pelo próprio usuário — **novo**
Anotação sua de uma sessão anterior: usuário deveria conseguir, sem depender do admin:
- Alterar o próprio e-mail cadastrado
- Autoexcluir a própria conta/dados

Hoje isso só é possível via admin (e a exclusão via admin, que já implementamos, é
restrita a cadastros não confirmados — por segurança). Precisamos decidir: um usuário
ativo e confirmado pode se autoexcluir livremente, ou deveria haver alguma restrição
(ex: não pode se autoexcluir se tiver demandas em aberto)?

### 1.3 Gestão de cadastros pendentes pelo admin — **concluído nesta sessão**
Confirmar e-mail manualmente, reenviar confirmação, excluir cadastro não confirmado.
Já implementado, testado e publicado.

### 1.4 Fluxo "esqueci minha senha" — **verificar se já existe**
Ainda não conferimos se esse fluxo existe e funciona bem. Vale checar antes de decidir
se entra na lista de melhorias.

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

## 6. Infraestrutura / Ambiente (fora do controle do código da aplicação)

Itens que não se resolvem só editando `sistac` — dependem de configuração de servidor
ou de decisões de infraestrutura do CNPq:

- **Logo do CNPq não aparecendo**: ainda pendente de diagnóstico (precisa confirmar se
  `/static/coop_nac.png` carrega direto pela URL).
- **Mapa de Convênios "Access blocked"**: política de uso de tiles do OpenStreetMap
  bloqueando por falta de `Referer` correto — comum em ambientes de preview/proxy como
  o do Codespace. Pode não se reproduzir em produção.
- **Integração Oracle DW ("Pega Programas/Chamadas/Financeiro DW")**: já documentado
  como dívida técnica em `core/services.py` — falta a biblioteca cliente do Oracle no
  ambiente, e há SQL montado por concatenação que merece hardening dedicado (ver seção
  "Security/Technical Debt" no código).

---

## Como sugiro seguirmos

1. Fechar as decisões pendentes de papéis/permissão (itens 1.1 e 4.1 dependem da mesma
   decisão — vale resolver isso primeiro, já que trava dois itens).
2. Implementar 1.2 (autogestão de conta) e 1.4 (checar esqueci-senha) — ainda dentro
   de `users`, como você pediu.
3. Depois, os itens 2.x e 3.x (edição/exclusão em Bolsas e Programas CNPq) — mais
   simples, sem decisão de produto pendente, só a implementação em si.
4. Por último, 5.1 (revisão de CSV) e os itens de infraestrutura, que dependem de
   confirmação externa ou de outra equipe.

Faz sentido essa ordem, ou prefere atacar em outra sequência?
