# Prompts para alterações no bot

Use estes modelos ao solicitar mudanças no bot para o Claude.

---

## Modelo 1 — Novo fluxo de conversa

```
Preciso adicionar um novo fluxo ao bot.

**O que deve acontecer:**
[Descreva o fluxo em linguagem simples — ex: "quando o paciente perguntar X, o bot deve fazer Y e depois Z"]

**Quando deve ser ativado:**
[ ] Primeira mensagem (novo contato)
[ ] Em qualquer momento da conversa (interceptação global)
[ ] Somente no estado: [nome do estado]

**Padrões de mensagem que ativam:**
- "exemplo 1"
- "exemplo 2"
- "exemplo 3"
(liste todos os exemplos que conseguir pensar)

**Resposta do bot:**
"[Texto exato que o bot deve enviar]"

**Após a resposta:**
- Se o paciente confirmar → [o que acontece]
- Se o paciente recusar → [o que acontece]
- Se não entender → [o que acontece]

**Novo estado necessário:** sim / não
[Se sim, nome sugerido: AGUARDA_XXXXX]
```

---

## Modelo 2 — Novos padrões de reconhecimento para fluxo existente

```
Preciso que o bot reconheça mais padrões de mensagem para um fluxo que já existe.

**Fluxo / estado afetado:**
[Ex: detecção de intenção de agendamento / AGUARDA_TURNO / interceptação de valor]

**Novos padrões a reconhecer:**
- "exemplo 1"
- "exemplo 2"
- "exemplo 3"

**Resposta esperada para esses padrões:**
[Igual à que já existe / ou diferente — descrever se diferente]

**Observação:**
[Qualquer detalhe relevante — ex: "só deve ativar se o paciente já tiver local definido"]
```

---

## Dicas para preencher bem

- **Liste o máximo de exemplos possível.** Quanto mais padrões você listar, mais preciso o regex fica e menos chamadas para o Claude Haiku são necessárias — economiza custo de API.
- **Se a resposta tiver variáveis dinâmicas**, indique com colchetes: `"Olá [nome], sua consulta é [data] às [hora]."`
- **Se o novo fluxo conflita com um existente** (ex: uma mensagem pode ativar dois padrões), mencione — isso evita bugs de ordem de prioridade.
- **Informe se é regex ou NLU.** Padrões exatos e previsíveis → regex (mais rápido, sem custo de API). Padrões ambíguos ou em linguagem muito livre → NLU via Claude Haiku.

---

## Estados atuais do bot (referência)

| Estado | Descrição |
|--------|-----------|
| `AGUARDA_OPCAO` | Menu principal |
| `AGUARDA_SUBMENU` | Tipo de consulta (primeira vez / retorno) |
| `AGUARDA_LOCAL` | Escolha de local |
| `AGUARDA_TURNO` | Preferência de turno |
| `AGUARDA_HORARIO` | Escolha do slot |
| `AGUARDA_CONFIRMACAO` | Confirmação do agendamento |
| `AGUARDA_NOME_FAMILIAR` | Nome do familiar (fluxo de horário seguido) |
| `AGUARDA_CONFIRMACAO_VALOR` | Confirmação após informar o valor |
| `AGUARDA_DESCRICAO` | Outros assuntos (resposta livre) |
| `AGUARDA_MARINADAS` | Legado — não usado ativamente |
| `ATENDIMENTO_HUMANO` | Bot silencioso — Victor assumiu |

## Interceptações globais ativas

| Interceptação | Ativa em | Comportamento |
|---------------|----------|---------------|
| Pergunta de valor | Qualquer estado (exceto humano e conf. valor) | Responde R$300 e salva estado anterior |
| Familiar | Qualquer estado (exceto humano e nome familiar) | Busca slot seguido ou encaminha Victor |
| Endereço | Qualquer estado com local definido | Envia endereço sem mudar estado |
