# Bot WhatsApp — Consultório Victor Afonso

Bot inteligente para agendamento e atendimento inicial via WhatsApp,
integrado com Z-API, Claude Haiku (IA), Google Sheets (memória) e Google Agenda.

---

## Como funciona

```
Paciente → Z-API → Railway (este código) → Claude Haiku (IA)
                                         → Google Sheets (memória)
                                         → Google Agenda (horários)
                                         → Z-API (resposta)
```

---

## Passo a passo para subir no Railway

### 1. Criar conta no Railway
- Acesse https://railway.app
- Crie conta com seu e-mail ou GitHub
- Plano gratuito tem 500h/mês (suficiente para começar)

### 2. Criar conta na Anthropic (Claude)
- Acesse https://console.anthropic.com
- Crie conta e adicione crédito (mínimo $5)
- Vá em **Settings → API Keys → Create Key**
- Copie a chave (começa com `sk-ant-`)

### 3. Criar conta de serviço no Google Cloud
*(necessário para Google Sheets + Google Agenda)*

1. Acesse https://console.cloud.google.com
2. Crie um projeto novo (ex: "bot-victor")
3. Ative as APIs:
   - Google Sheets API
   - Google Calendar API
4. Vá em **IAM & Admin → Service Accounts → Create**
5. Dê um nome (ex: "bot-victor-service")
6. Clique em **Create and Continue → Done**
7. Clique na conta criada → **Keys → Add Key → JSON**
8. Faça download do arquivo JSON
9. Abra o arquivo e copie TODO o conteúdo em UMA linha

### 4. Compartilhar planilha com a conta de serviço
1. Abra o JSON baixado e copie o campo `client_email`
   (parece com `bot-victor@seu-projeto.iam.gserviceaccount.com`)
2. Abra a planilha: https://docs.google.com/spreadsheets/d/14qcCx9nM6NWjg6O6SCdYX6N94kXwI64FQqMHejkb4ZI
3. Clique em **Compartilhar**
4. Cole o `client_email` e dê permissão de **Editor**

### 5. Compartilhar Google Agenda com a conta de serviço
1. Abra o Google Agenda do Victor
2. Para cada agenda (Copacabana, MaxFit Méier):
   - Clique nos 3 pontos → **Configurações e compartilhamento**
   - Role até **Compartilhar com pessoas específicas**
   - Adicione o `client_email` com permissão **Ver todos os detalhes**
   - Copie o **ID do calendário** (campo "ID do agendário")
   - Cole no `.env.example` nos campos CALENDAR_COPA e CALENDAR_MEIER

### 6. Subir o código no Railway

**Opção A — via GitHub (recomendado):**
1. Crie um repositório no GitHub e faça upload desta pasta
2. No Railway, clique em **New Project → Deploy from GitHub**
3. Selecione o repositório

**Opção B — via Railway CLI:**
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

### 7. Configurar as variáveis de ambiente no Railway
1. No Railway, clique no seu projeto → **Variables**
2. Adicione cada variável do `.env.example` com os valores corretos
3. Para o `GOOGLE_CREDENTIALS_JSON`, cole o conteúdo do JSON em UMA linha

### 8. Pegar a URL do servidor
1. No Railway → **Settings → Domains → Generate Domain**
2. Copie a URL (ex: `https://bot-victor.up.railway.app`)

### 9. Configurar o webhook na Z-API
1. Acesse app.z-api.io → Instâncias → Victor Afonso
2. No campo **"Ao receber"**, cole:
   `https://bot-victor.up.railway.app/webhook`
3. Salva

### 10. Testar
- Mande "oi" para o WhatsApp do consultório
- O bot deve responder com o menu principal

---

## Estrutura do projeto

```
bot_victor/
├── main.py              # Servidor Flask — recebe webhook da Z-API
├── bot.py               # Lógica principal — estados e fluxos
├── mensagens.py         # Textos de todas as mensagens do bot
├── sheets.py            # Integração Google Sheets (memória)
├── calendar_service.py  # Integração Google Agenda (horários)
├── claude_ai.py         # Integração Claude Haiku (IA)
├── zapi.py              # Envio de mensagens via Z-API
├── config.py            # Variáveis de ambiente
├── requirements.txt     # Dependências Python
├── Procfile             # Configuração Railway/Gunicorn
└── .env.example         # Modelo de variáveis (não commitar o .env real)
```

---

## Estados da conversa (memória)

| Estado | Significado |
|--------|-------------|
| AGUARDA_OPCAO | Aguardando 1, 2 ou 3 do menu |
| AGUARDA_SUBMENU | Aguardando 1ª consulta / retorno / outras infos |
| AGUARDA_LOCAL | Aguardando Copa / Méier / Online |
| AGUARDA_TURNO | Aguardando manhã / tarde / noite |
| AGUARDA_DESCRICAO | Aguardando descrição do assunto |
| AGUARDA_MARINADAS | Aguardando dúvida sobre marinadas |
| AGUARDANDO_CONFIRMACAO | Aguardando paciente escolher horário |
| ATENDIMENTO_HUMANO | Passou para atendente humana |

---

## Variáveis importantes para preencher depois

- `LINK_MARINADAS` — link da loja das Marinadas do Nutri
- `LINK_ORIENTACOES` — link das orientações de bioimpedância
- `CALENDAR_COPA` — ID da agenda das salas de Copacabana
- `CALENDAR_MEIER` — ID da agenda da Max Fit Méier

---

## Suporte

Projeto desenvolvido por Sophia Lucchesi — Março 2026
