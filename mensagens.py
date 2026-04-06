"""
mensagens.py
Todas as mensagens enviadas pelo bot.
Strings estáticas + funções para mensagens dinâmicas.
"""

from config import LINK_QUESTIONARIO, IMG_BIOIMPEDANCIA, ENDERECO

# ─────────────────────────────────────────────
# MENSAGENS ESTÁTICAS
# ─────────────────────────────────────────────

MENU_PRINCIPAL = """Olá! 👋 Bem-vindo ao consultório do *Nutri Victor Afonso*!

Como posso te ajudar hoje?

1️⃣ Consulta / Acompanhamento Nutricional
2️⃣ Marinadas do Nutri
3️⃣ Outros assuntos

_Responda com o número da opção desejada._"""

SUBMENU_CONSULTA = """Ótimo! Sobre a consulta, você é:

1️⃣ Paciente novo (primeira consulta)
2️⃣ Retorno / Acompanhamento
3️⃣ Tenho outra dúvida

_Responda com o número._"""

INFO_PRIMEIRA_CONSULTA = """O que está incluso na consulta:
• Anamnese completa, observando os principais pontos que possam estar prejudicando sua performance e/ou saúde
• Avaliação física (Bioimpedância, Dobras cutâneas e circunferências)
• Caso necessário, solicitação de exames bioquímicos de acordo com suas queixas clínicas
• Elaboração de um programa alimentar totalmente personalizado para VOCÊ com receitas e suplementação

O atendimento pode ser feito de 2 formas:
📍 *Presencial:* Max Fit (Méier) ou Integra Saúde (Copacabana)
💻 *Online:* Google Meet ou WhatsApp Vídeo (até 1h)

➡️ Valor: *R$300,00*
💳 Pagamento presencial: cartão ou à vista
📱 Pagamento online: Pix, transferência ou PagSeguro

Gostaria de agendar em *Copa*, *Méier* ou *Online*? 😊"""

# ── Pergunta de local para retorno (sem info da consulta)
PERGUNTA_LOCAL = """Gostaria de agendar em *Copa*, *Méier* ou *Online*? 😊"""

PERGUNTA_TURNO = """Qual turno você prefere para a consulta?

🌅 Manhã
☀️ Tarde
🌙 Noite

_Responda com o nome do turno._"""

MARINADAS = """🧡 Que ótimo! As *Marinadas do Nutri Victor* são incríveis!

Acesse pelo link abaixo para conhecer e adquirir:
""" + LINK_QUESTIONARIO  # substitua pelo link de marinadas se necessário

PEDIR_DESCRICAO = """Claro! Me conta um pouco mais sobre o que você precisa e em breve o Nutri Victor entrará em contato. 😊"""

CONFIRMACAO_RECEBIMENTO = """Recebi! ✅ Em breve o Nutri Victor entrará em contato com você. 😊"""

ENCERRAMENTO_BOT = """Entendido! Em breve o *Nutri Victor* entrará em contato para confirmar seu agendamento. 😊"""

ERRO_OPCAO_INVALIDA = """Desculpa, não entendi sua resposta. 😅"""

ENCAMINHAR_HUMANO = """Obrigada pelas informações, vou encaminhar para o atendimento humano! 😊"""

# ── Mensagens contextuais de "não entendi" ────────────────────────────────────

def erro_nao_entendi(etapa: str) -> str:
    """Retorna mensagem de erro contextual repetindo a última pergunta."""
    PERGUNTAS = {
        "AGUARDA_OPCAO": (
            "Desculpe, não entendi o que você quis dizer. 😅\n\n"
            "Como posso te ajudar?\n\n"
            "1️⃣ Consulta / Acompanhamento Nutricional\n"
            "2️⃣ Marinadas do Nutri\n"
            "3️⃣ Outros assuntos"
        ),
        "AGUARDA_SUBMENU": (
            "Desculpe, não entendi o que você quis dizer. 😅\n\n"
            "Você é:\n\n"
            "1️⃣ Paciente novo (primeira consulta)\n"
            "2️⃣ Retorno / Acompanhamento\n"
            "3️⃣ Tenho outra dúvida"
        ),
        "AGUARDA_LOCAL": (
            "Desculpe, não entendi o que você quis dizer. 😅\n\n"
            "Gostaria de agendar em *Copa*, *Méier* ou *Online*?"
        ),
        "AGUARDA_TURNO": (
            "Desculpe, não entendi o que você quis dizer. 😅\n\n"
            "Qual turno você prefere?\n\n"
            "🌅 Manhã\n"
            "☀️ Tarde\n"
            "🌙 Noite"
        ),
        "AGUARDA_HORARIO": (
            "Desculpe, não entendi o que você quis dizer. 😅\n\n"
            "Me informe o *dia e horário* de sua preferência.\n"
            "_Exemplo: Sexta 09:00 ou 04/04 às 10:30_"
        ),
        "AGUARDA_CONFIRMACAO": (
            "Desculpe, não entendi o que você quis dizer. 😅\n\n"
            "Por favor, responda *SIM* para confirmar ou *NÃO* para escolher outro horário."
        ),
    }
    return PERGUNTAS.get(etapa, "Desculpe, não entendi o que você quis dizer. 😅\nPode repetir?")


ERRO_DIA_BLOQUEADO = """O Nutri atende somente de *quarta-feira a sábado*. 😊

Por favor, escolha um dia disponível na lista acima."""

ERRO_LOCAL_INVALIDO = """Desculpa, não reconheci o local. Por favor, escolha entre:

1️⃣ Copacabana
2️⃣ Méier
3️⃣ Online"""

ERRO_TURNO_INVALIDO = """Desculpa, não reconheci o turno. Por favor, escolha entre:

🌅 Manhã
☀️ Tarde
🌙 Noite"""

ERRO_HORARIO_NAO_IDENTIFICADO = """Desculpa, não consegui identificar o horário escolhido. 😅

Por favor, me informe o *dia e horário* no formato:
_Sexta 09:00_ ou _02/04 às 14:30_"""

ERRO_CONFIRMACAO_INVALIDA = """Por favor, responda *SIM* para confirmar ou *NÃO* para escolher outro horário."""

ERRO_SLOTS_EXPIRADOS = """Ops! Os horários precisam ser atualizados. Me informe novamente o turno de preferência:

🌅 Manhã
☀️ Tarde
🌙 Noite"""

REAGENDAMENTO = """Sem problema! Vamos escolher outro horário. 😊"""

SEM_HORARIOS_DISPONIVEIS = """No momento não há horários disponíveis nesse turno para o local escolhido. 😕

O *Nutri Victor* entrará em contato em breve para verificar outras opções!"""

FORMULARIO_PRE_CONSULTA = f"""📋 Para nos preparar melhor para a sua consulta, por favor preencha o formulário pré-consulta:

{LINK_QUESTIONARIO}"""

ORIENTACOES_BIO_TEXTO = """Por fim, seguem as orientações para uma avaliação mais assertiva: 👇"""

ORIENTACOES_BIO_IMAGEM = IMG_BIOIMPEDANCIA

ENDERECO_COPA = f"""📍 *Copacabana (Clínica Integra):*
{ENDERECO['Copacabana']}"""

ENDERECO_MEIER = f"""📍 *Méier (MaxFit):*
{ENDERECO['Méier']}"""

# ─────────────────────────────────────────────
# MENSAGENS DINÂMICAS
# ─────────────────────────────────────────────

def endereco_para_local(local: str) -> str:
    """Retorna a mensagem de endereço para o local confirmado."""
    if local == "Copacabana":
        return f"📍 {ENDERECO['Copacabana']}"
    if local == "Méier":
        return f"📍 {ENDERECO['Méier']}"
    return "📱 O Nutri Victor entrará em contato com as instruções para a consulta online."


def confirmacao_agendamento(nome: str, local: str, data: str, dia: str, hora: str) -> str:
    """Resumo do agendamento pedindo confirmação do lead."""
    DIAS_PT = {
        "Seg": "Segunda-feira",
        "Ter": "Terça-feira",
        "Qua": "Quarta-feira",
        "Qui": "Quinta-feira",
        "Sex": "Sexta-feira",
        "Sáb": "Sábado",
        "Dom": "Domingo",
    }
    nome_dia = DIAS_PT.get(dia, dia)
    local_fmt = {
        "Copacabana": "Copacabana",
        "Méier":      "Méier",
        "Online":     "Online",
    }.get(local, local)

    return (
        f"Perfeito, *{nome}*! ✅\n\n"
        f"Confirmo o seguinte agendamento:\n\n"
        f"📅 *Data:* {nome_dia}, {data}\n"
        f"⏰ *Horário:* {hora}\n"
        f"📍 *Local:* {local_fmt}\n\n"
        f"Está correto? Responda *SIM* para confirmar ou *NÃO* para escolher outro horário."
    )


def confirmacao_final(nome: str, data: str, dia: str, hora: str, endereco: str) -> str:
    """Mensagem final enviada ao lead após confirmação."""
    DIAS_PT = {
        "Seg": "Segunda-feira",
        "Ter": "Terça-feira",
        "Qua": "Quarta-feira",
        "Qui": "Quinta-feira",
        "Sex": "Sexta-feira",
        "Sáb": "Sábado",
        "Dom": "Domingo",
    }
    nome_dia = DIAS_PT.get(dia, dia)

    return (
        f"Certo, *{nome}*! 🎉\n\n"
        f"Sua consulta está confirmada:\n\n"
        f"📅 *{nome_dia}, {data}*\n"
        f"⏰ *{hora}*\n"
        f"{endereco}\n\n"
        f"Qualquer dúvida, estamos à disposição! 😊"
    )


def notif_consulta_marcada(nome: str, phone: str, local: str, data: str, hora: str) -> str:
    """Notificação enviada ao Victor quando uma consulta é confirmada."""
    return (
        f"📌 *Consulta marcada!*\n\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Telefone:* {phone}\n"
        f"📍 *Local:* {local}\n"
        f"📅 *Data:* {data}\n"
        f"⏰ *Horário:* {hora}"
    )


def notif_triagem(nome: str, phone: str, local: str, turno: str) -> str:
    return (
        f"📋 *Nova triagem recebida!*\n\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Telefone:* {phone}\n"
        f"📍 *Local:* {local}\n"
        f"🕐 *Turno:* {turno}\n\n"
        f"_Sem horários disponíveis no turno pedido — verificar manualmente._"
    )


def notif_marinadas(nome: str, phone: str) -> str:
    return (
        f"🛒 *Interesse em Marinadas!*\n\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Telefone:* {phone}"
    )


def notif_outro(nome: str, phone: str, descricao: str) -> str:
    return (
        f"💬 *Nova mensagem recebida!*\n\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Telefone:* {phone}\n"
        f"📝 *Mensagem:* {descricao}"
    )


def notif_nao_entendeu(nome: str, phone: str, texto: str) -> str:
    """Notifica Victor quando o bot não entendeu a mensagem do lead."""
    return (
        f"⚠️ *Bot não entendeu a mensagem*\n\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Telefone:* {phone}\n"
        f"💬 *Mensagem:* {texto}\n\n"
        f"_Lead encaminhado para atendimento humano._"
    )


# Mensagem quando lead diz "depois confirmo"
AGUARDA_CONFIRMACAO_DEPOIS = (
    "Sem problema! 😊 Quando quiser confirmar é só me chamar aqui. "
    "O *Nutri Victor* também pode entrar em contato para verificar a disponibilidade."
)

def notif_decide_depois(nome: str, phone: str, local: str) -> str:
    """Notifica Victor que o lead quer decidir o horário depois."""
    return (
        f"⏳ *Lead quer confirmar depois*\n\n"
        f"👤 *Nome:* {nome}\n"
        f"📞 *Telefone:* {phone}\n"
        f"📍 *Local:* {local}\n\n"
        f"_Horários foram apresentados mas o lead não confirmou ainda._"
    )
