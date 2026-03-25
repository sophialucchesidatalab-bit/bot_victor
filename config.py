import os

# === Z-API ===
ZAPI_INSTANCE     = os.getenv("ZAPI_INSTANCE", "3F08645D62A8F15B3B63CA0B4A3FCD13")  # ✅ Instance ID
ZAPI_TOKEN        = os.getenv("ZAPI_TOKEN",    "BB8428EE82CF8EB91C2A62F3")           # ✅ Token
ZAPI_BASE_URL     = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}"
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# === ANTHROPIC ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# === VICTOR (numero que recebe notificacoes) ===
VICTOR_PHONE = os.getenv("VICTOR_PHONE", "5521997501668")

# === GOOGLE SHEETS ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "14qcCx9nM6NWjg6O6SCdYX6N94kXwI64FQqMHejkb4ZI")
SHEET_NAME     = os.getenv("SHEET_NAME",     "Bot_estado")

# === LINKS ===
LINK_MARINADAS    = os.getenv("LINK_MARINADAS",    "https://nutrivictorafonso.hotmart.host/marinadas-do-nutri-victor-0fd4c29e-6213-49be-be5c-32bffa06db54")
LINK_QUESTIONARIO = os.getenv("LINK_QUESTIONARIO", "https://forms.gle/FfkdcGTq48fK6jjr7")
LINK_ORIENTACOES  = os.getenv("LINK_ORIENTACOES",  "https://ADICIONAR_LINK_ORIENTACOES_AQUI")

# === ESTADOS DA CONVERSA ===
ESTADO_NOVO                   = "NOVO"                    # legado — não usado ativamente
ESTADO_AGUARDA_OPCAO          = "AGUARDA_OPCAO"
ESTADO_AGUARDA_SUBMENU        = "AGUARDA_SUBMENU"
ESTADO_AGUARDA_LOCAL          = "AGUARDA_LOCAL"
ESTADO_AGUARDA_TURNO          = "AGUARDA_TURNO"
ESTADO_AGUARDA_DESCRICAO      = "AGUARDA_DESCRICAO"
ESTADO_AGUARDA_MARINADAS      = "AGUARDA_MARINADAS"
ESTADO_AGUARDANDO_CONFIRMACAO = "AGUARDANDO_CONFIRMACAO"  # legado — não usado ativamente
ESTADO_ATENDIMENTO_HUMANO     = "ATENDIMENTO_HUMANO"
