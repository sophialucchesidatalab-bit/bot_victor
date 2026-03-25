"""
mensagens.py — Textos do bot Victor Afonso Nutricionista
Tom baseado nas conversas reais do consultório.
"""
from config import LINK_MARINADAS, LINK_QUESTIONARIO, LINK_ORIENTACOES_IMG

# ════════════════════════════════════════════════════════════
# BLOCOS — IDs para controle anti-repetição
# Salvo na coluna "ultima_msg" da planilha Google Sheets
# O bot.py só envia um bloco se ultima_msg != esse ID
# ════════════════════════════════════════════════════════════
BLOCO_MENU          = "MENU"
BLOCO_SUBMENU       = "SUBMENU"
BLOCO_INFO_CONSULTA = "INFO_CONSULTA"
BLOCO_TURNO         = "TURNO"
BLOCO_HORARIOS      = "HORARIOS"
BLOCO_CONFIRMADO    = "CONFIRMADO"
BLOCO_MARINADAS     = "MARINADAS"
BLOCO_DESCRICAO     = "DESCRICAO"
BLOCO_ATENDENTE     = "ATENDENTE"


# ════════════════════════════════════════════════════════════
# MENU PRINCIPAL
# ════════════════════════════════════════════════════════════
MENU_PRINCIPAL = (
    "Consultório Nutricionista Victor Afonso, que bom te ver por aqui 🙏\n\n"
    "Para te ajudar melhor, escolha uma das opções abaixo:\n\n"
    "1️⃣ Informações sobre o acompanhamento nutricional\n"
    "2️⃣ Informações sobre as Marinadas do Nutri\n"
    "3️⃣ Outros assuntos\n\n"
    "É só responder com *1*, *2* ou *3* 💚"
)

# ════════════════════════════════════════════════════════════
# SUBMENU CONSULTA
# ════════════════════════════════════════════════════════════
SUBMENU_CONSULTA = (
    "Ótimo! Pode me confirmar:\n\n"
    "1️⃣ Primeira consulta\n"
    "2️⃣ Agendar retorno\n"
    "3️⃣ Outras informações"
)

# ════════════════════════════════════════════════════════════
# INFO DA CONSULTA — 2 partes, como Victor faz na conversa
# Parte 1: o que inclui + acompanhamento 3 meses
# Parte 2: locais, valor, pagamento + pergunta do local
# ════════════════════════════════════════════════════════════
INFO_CONSULTA_PARTE1 = (
    "Fico feliz que tenha nos encontrado! 😊\n\n"
    "Vou te explicar como funciona o acompanhamento com o Nutri Victor:\n\n"
    "• Anamnese completa, observando os principais pontos que possam estar "
    "prejudicando sua performance e/ou saúde\n"
    "• Avaliação física (Bioimpedância, Dobras cutâneas e circunferências)\n"
    "• Caso necessário, solicitação de exames bioquímicos de acordo com suas "
    "queixas clínicas\n"
    "• Elaboração de um programa alimentar totalmente personalizado para VOCÊ, "
    "com receitas e suplementação\n"
    "• *Acompanhamento de 3 meses* com suporte via WhatsApp — você pode ajustar "
    "a dieta quantas vezes forem necessárias para alcançar seu objetivo!"
)

INFO_CONSULTA_PARTE2 = (
    "O atendimento pode ser feito de 2 formas:\n\n"
    "📍 *Presencial:* Max Fit (Méier) ou Integra Saúde (Copacabana)\n"
    "💻 *Online:* Google Meet ou WhatsApp Vídeo (até 1h30)\n\n"
    "➡️ Valor: *R$300,00*\n"
    "💳 Presencial: débito, crédito à vista ou Pix\n"
    "📱 Online: Pix, transferência ou PagSeguro\n\n"
    "Você gostaria de agendar em *Copa*, *Méier* ou *Online*? 😊"
)

# Só a pergunta de local, usada no fluxo de retorno
PERGUNTA_LOCAL_RETORNO = (
    "Qual local prefere para o retorno?\n\n"
    "📍 Copacabana\n"
    "📍 Méier\n"
    "💻 Online"
)

# ════════════════════════════════════════════════════════════
# TURNO
# ════════════════════════════════════════════════════════════
PERGUNTA_TURNO = (
    "Você teria algum turno ou dia da semana de preferência? 📅\n\n"
    "🌅 Manhã\n"
    "☀️ Tarde\n"
    "🌙 Noite"
)

# Instrução de resposta enviada junto com os horários disponíveis
INSTRUCAO_HORARIO = (
    "Qual horário você prefere? 😊\n"
    "_(Responda com data e horário, ex: *27/03 às 11:00*)_"
)

# ════════════════════════════════════════════════════════════
# MARINADAS
# ════════════════════════════════════════════════════════════
MARINADAS = (
    f"Que ótima escolha! 🥩🔥\n\n"
    f"As *Marinadas do Nutri* são temperos naturais desenvolvidos pelo próprio "
    f"Nutri Victor, pensados para deixar sua alimentação mais saborosa e saudável "
    f"ao mesmo tempo.\n\n"
    f"Clica no link abaixo para conhecer e garantir o seu:\n"
    f"👉 {LINK_MARINADAS}\n\n"
    f"Qualquer dúvida é só chamar! 💚"
)

# ════════════════════════════════════════════════════════════
# OUTROS ASSUNTOS
# ════════════════════════════════════════════════════════════
PEDIR_DESCRICAO = (
    "Claro! Me conta um pouco mais sobre o que você precisa 😊\n\n"
    "Pode descrever à vontade que nossa atendente irá te responder em breve! 💚"
)

CONFIRMACAO_RECEBIMENTO = (
    "Recebemos sua mensagem! 📩\n\n"
    "Nossa atendente irá te responder em breve. Obrigado pelo contato! 💚"
)

AGUARDA_ATENDENTE = (
    "Certo! Nossa atendente vai te responder em breve com todas as informações 💚"
)

# ════════════════════════════════════════════════════════════
# PÓS-AGENDAMENTO — 3 mensagens separadas (padrão Victor)
# bot.py envia: msg1 → msg2 → imagem bioimpedância → msg3
# ════════════════════════════════════════════════════════════
def pos_agendamento(nome: str, local: str, horario: str) -> tuple:
    msg1 = (
        f"Combinado {nome}, marcado! 🎉\n\n"
        f"📍 *Local:* {local}\n"
        f"🕐 *Horário:* {horario}\n\n"
        f"Estamos à disposição! 💚"
    )
    msg2 = (
        f"Peço, por gentileza, que responda esse questionário pré-consulta "
        f"com algumas perguntas importantes:\n"
        f"👉 {LINK_QUESTIONARIO}"
    )
    msg3 = (
        "Por fim, seguem as orientações para uma avaliação mais assertiva 👆"
    )
    return msg1, msg2, msg3

# ════════════════════════════════════════════════════════════
# ENDEREÇOS (enviados quando paciente perguntar)
# ════════════════════════════════════════════════════════════
ENDERECO_COPA = (
    "📍 *Integra Saúde — Copacabana*\n"
    "Praça Serzedelo Corrêa, 15 — sala 703\n"
    "Próximo à estação de metrô Siqueira Campos 🚇"
)

ENDERECO_MEIER = (
    "📍 *Academia Max Fit — Méier*\n"
    "R. Mario Piragibe, 26 — Méier 🏋️"
)

IA_NAO_SABE = (
    "Aguarde um momento, vou chamar a assistente para te ajudar! 💚"
)

# ════════════════════════════════════════════════════════════
# ERROS / FALLBACKS
# ════════════════════════════════════════════════════════════
ERRO_OPCAO_INVALIDA = (
    "Não entendi sua resposta 😅\n\n"
    "Por favor responda com o número da opção desejada:"
)

ERRO_LOCAL_INVALIDO = (
    "Não entendi o local 😅\n\n"
    "Por favor informe: 📍 *Copa*, *Méier* ou 💻 *Online*"
)

# ════════════════════════════════════════════════════════════
# NOTIFICAÇÕES PARA VICTOR
# ════════════════════════════════════════════════════════════
def notif_interesse(nome: str, phone: str, local: str, turno: str) -> str:
    return (
        f"📅 *Nova solicitação de consulta!*\n\n"
        f"*Paciente:* {nome}\n"
        f"*Telefone:* {phone}\n"
        f"*Local:* {local}\n"
        f"*Turno preferido:* {turno}\n\n"
        f"Horários foram enviados ao paciente. Aguardando escolha 💚"
    )

def notif_agendado(nome: str, phone: str, local: str,
                   horario: str, turno: str, sucesso_agenda: bool) -> str:
    aviso = "✅ Evento criado no Google Agenda" if sucesso_agenda else "⚠️ Criar evento manualmente na agenda"
    return (
        f"🎉 *Consulta Agendada!*\n\n"
        f"*Paciente:* {nome}\n"
        f"*WhatsApp:* {phone}\n"
        f"*Local:* {local}\n"
        f"*Horário:* {horario}\n"
        f"*Turno preferido:* {turno}\n\n"
        f"{aviso}\n\n"
        f"Questionário e orientações já foram enviados ao paciente 💚"
    )

def notif_outro(nome: str, phone: str, assunto: str) -> str:
    return (
        f"📬 *Nova mensagem recebida!*\n\n"
        f"*De:* {nome} — {phone}\n"
        f"*Assunto:* {assunto}\n\n"
        f"Responda diretamente pelo WhatsApp 💚"
    )

def notif_marinadas(nome: str, phone: str) -> str:
    return (
        f"🥩 *Interesse nas Marinadas!*\n\n"
        f"*Paciente:* {nome}\n"
        f"*Telefone:* {phone}\n\n"
        f"O link foi enviado automaticamente 💚"
    )


# ════════════════════════════════════════════════════════════
# ENCERRAMENTO DO BOT (após turno coletado)
# ════════════════════════════════════════════════════════════
BLOCO_ENCERRAMENTO = "ENCERRAMENTO"

ENCERRAMENTO_BOT = (
    "Perfeito! 😊✅\n\n"
    "Já anotei tudo:\n\n"
    "Nossa atendente entrará em contato em breve para confirmar "
    "a data e o horário disponíveis para você! 💚\n\n"
    "Qualquer dúvida, estamos por aqui."
)


def notif_triagem(nome: str, phone: str, local: str, turno: str) -> str:
    """
    Notificação enviada para Victor ao final da triagem do bot.
    Contém tudo que foi coletado para a atendente dar sequência.
    """
    return (
        f"📋 *Nova triagem concluída!*\n\n"
        f"*Paciente:* {nome}\n"
        f"*WhatsApp:* {phone}\n"
        f"*Local preferido:* {local}\n"
        f"*Turno preferido:* {turno}\n\n"
        f"O bot encerrou. Por favor, entre em contato para confirmar "
        f"a data e o horário! 💚"
    )
