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
