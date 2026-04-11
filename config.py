import os

# === Z-API ===
ZAPI_INSTANCE     = os.getenv("ZAPI_INSTANCE",     "3F08645D62A8F15B3B63CA0B4A3FCD13")
ZAPI_TOKEN        = os.getenv("ZAPI_TOKEN",        "BB8428EE82CF8EB91C2A62F3")
ZAPI_BASE_URL     = f"https://api.z-api.io/instances/{os.getenv('ZAPI_INSTANCE', '3F08645D62A8F15B3B63CA0B4A3FCD13')}/token/{os.getenv('ZAPI_TOKEN', 'BB8428EE82CF8EB91C2A62F3')}"
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# === ANTHROPIC ===
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# === VICTOR ===
VICTOR_PHONE = os.getenv("VICTOR_PHONE", "5521997501668")

# === GOOGLE SHEETS — Bot estado ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "14qcCx9nM6NWjg6O6SCdYX6N94kXwI64FQqMHejkb4ZI")
SHEET_NAME     = os.getenv("SHEET_NAME",     "Bot_estado")

# === GOOGLE SHEETS — Agenda (horários disponíveis) ===
AGENDA_SPREADSHEET_ID = os.getenv(
    "AGENDA_SPREADSHEET_ID",
    "1-5d-Rt2m8aaHR6uXtuEYfy__CxdS3IJBzOMsNUePIlU"
)

# === LINKS ===
LINK_MARINADAS    = os.getenv("LINK_MARINADAS",    "https://hotmart.com/en/club/victor-da-cruz-afonso/products/6881968/content/y4bpWblP7R")
LINK_QUESTIONARIO = os.getenv("LINK_QUESTIONARIO", "https://forms.gle/FfkdcGTq48fK6jjr7")

# === IMAGENS ===
IMG_BIOIMPEDANCIA = os.getenv(
    "IMG_BIOIMPEDANCIA",
    "https://raw.githubusercontent.com/sophialucchesidatalab-bit/bot_victor/main/bioimpedancia.jpg"
)

# === DURAÇÃO DAS CONSULTAS (minutos) ===
DURACAO_CONSULTA = {
    "Méier":      90,
    "Copacabana": 120,
    "Online":     90,
}

# === ENDEREÇOS ===
ENDERECO = {
    "Méier":      "R. Mario Piragibe, 26 - Méier",
    "Copacabana": "Edifício Tibagi - Praça Serzedelo Corrêa, 15 - salas 702 e 703 - Copacabana",
    "Online":     None,
}

# === ESTADOS DA CONVERSA ===
ESTADO_NOVO                      = "NOVO"
ESTADO_AGUARDA_OPCAO             = "AGUARDA_OPCAO"
ESTADO_AGUARDA_SUBMENU           = "AGUARDA_SUBMENU"
ESTADO_AGUARDA_LOCAL             = "AGUARDA_LOCAL"
ESTADO_AGUARDA_TURNO             = "AGUARDA_TURNO"
ESTADO_AGUARDA_HORARIO           = "AGUARDA_HORARIO"
ESTADO_AGUARDA_CONFIRMACAO       = "AGUARDA_CONFIRMACAO"
ESTADO_AGUARDA_DESCRICAO         = "AGUARDA_DESCRICAO"
ESTADO_AGUARDA_MARINADAS         = "AGUARDA_MARINADAS"
ESTADO_ATENDIMENTO_HUMANO        = "ATENDIMENTO_HUMANO"
ESTADO_AGUARDA_NOME_FAMILIAR     = "AGUARDA_NOME_FAMILIAR"
ESTADO_AGUARDA_CONFIRMACAO_VALOR = "AGUARDA_CONFIRMACAO_VALOR"
