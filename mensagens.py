"""
mensagens.py — Textos do bot Victor Afonso Nutricionista
Padrão exato das mensagens reais do consultório.
"""
from config import LINK_MARINADAS

# ════════════════════════════════════════════════════════════
# IDs ANTI-REPETIÇÃO
# ════════════════════════════════════════════════════════════
BLOCO_MENU          = "MENU"
BLOCO_SUBMENU       = "SUBMENU"
BLOCO_INFO_CONSULTA = "INFO_CONSULTA"
BLOCO_TURNO         = "TURNO"
BLOCO_ENCERRAMENTO  = "ENCERRAMENTO"
BLOCO_MARINADAS     = "MARINADAS"
BLOCO_ATENDENTE     = "ATENDENTE"
BLOCO_DESCRICAO     = "DESCRICAO"

# ════════════════════════════════════════════════════════════
# MENU PRINCIPAL
# ════════════════════════════════════════════════════════════
MENU_PRINCIPAL = """Consultório Nutricionista Victor Afonso, que bom te ver por aí 🙏

Para te ajudar melhor, escolha uma das opções abaixo, por favor.

1️⃣ Informações sobre o acompanhamento nutricional
2️⃣ Informações sobre as Marinadas do Nutri
3️⃣ Outros assuntos

E só me responder com 1, 2 ou 3 💚

Em breve nossa atendente irá lhe responder!"""

# ════════════════════════════════════════════════════════════
# SUBMENU CONSULTA
# ════════════════════════════════════════════════════════════
SUBMENU_CONSULTA = """Por favor confirmar: 😊

1️⃣ Primeira consulta
2️⃣ Agendar retorno
3️⃣ Outras informações"""

# ════════════════════════════════════════════════════════════
# INFO PRIMEIRA CONSULTA
# (inclui pergunta do local no final, como o Victor faz)
# ════════════════════════════════════════════════════════════
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

# ════════════════════════════════════════════════════════════
# PERGUNTA LOCAL — só para retorno
# ════════════════════════════════════════════════════════════
PERGUNTA_LOCAL = """Gostaria de agendar em *Copa*, *Méier* ou *Online*? 😊"""

# ════════════════════════════════════════════════════════════
# PERGUNTA TURNO
# ════════════════════════════════════════════════════════════
PERGUNTA_TURNO = """Você teria algum turno ou dia da semana de preferência? 📅

🌅 Manhã
☀️ Tarde  
🌙 Noite"""

# ════════════════════════════════════════════════════════════
# ENCERRAMENTO — após receber o turno
# ════════════════════════════════════════════════════════════
ENCERRAMENTO_BOT = """Perfeito! 😊✅

Sua solicitação foi recebida. Nossa atendente entrará em contato em breve para confirmar os detalhes da sua consulta! 💚"""

# ════════════════════════════════════════════════════════════
# MARINADAS
# ════════════════════════════════════════════════════════════
MARINADAS = f"""Que ótima escolha! 🥩🔥

As *Marinadas do Nutri* são temperos naturais desenvolvidos pelo próprio Nutri Victor, pensados para deixar sua alimentação mais saborosa e saudável ao mesmo tempo.

Clica no link abaixo para conhecer e garantir o seu:
👉 {LINK_MARINADAS}

Qualquer dúvida é só chamar, nossa atendente está por aqui! 💚"""

# ════════════════════════════════════════════════════════════
# OUTROS ASSUNTOS / ATENDENTE
# ════════════════════════════════════════════════════════════
PEDIR_DESCRICAO = """Olá! Fico feliz em te ajudar 😊

Por favor, me conta um pouco mais sobre o que você precisa. Pode descrever o assunto à vontade que nossa atendente irá te responder em breve! 💚"""

AGUARDA_ATENDENTE = """Certo! Nossa atendente vai te responder em breve com todas as informações 💚"""

CONFIRMACAO_RECEBIMENTO = """Recebemos sua mensagem! 📩

Nossa atendente irá te responder em breve. Obrigado pelo contato! 💚"""

# ════════════════════════════════════════════════════════════
# ERROS
# ════════════════════════════════════════════════════════════
ERRO_OPCAO_INVALIDA = """Não entendi sua resposta 😅

Por favor responda com o número da opção desejada:"""

ERRO_LOCAL_INVALIDO = """Não entendi o local 😅

Por favor informe: 📍 *Copa*, *Méier* ou 💻 *Online*"""

# ════════════════════════════════════════════════════════════
# ENDEREÇOS
# ════════════════════════════════════════════════════════════
ENDERECO_COPA = """📍 *Integra Saúde — Copacabana*
Praça Serzedelo Corrêa, 15 — sala 703
Próximo à estação de metrô Siqueira Campos 🚇"""

ENDERECO_MEIER = """📍 *Academia Max Fit — Méier*
R. Mario Piragibe, 26 — Méier 🏋️"""

# ════════════════════════════════════════════════════════════
# NOTIFICAÇÕES PARA VICTOR
# ════════════════════════════════════════════════════════════
def notif_triagem(nome: str, phone: str, local: str, turno: str) -> str:
    return (
        f"📋 *Nova solicitação de consulta!*\n\n"
        f"*Nome:* {nome}\n"
        f"*Telefone:* {phone}\n"
        f"*Local:* {local}\n"
        f"*Horário de preferência:* {turno}\n\n"
        f"Entre em contato para confirmar os detalhes! 💚"
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
