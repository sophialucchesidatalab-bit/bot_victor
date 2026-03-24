from config import LINK_MARINADAS, LINK_QUESTIONARIO, LINK_ORIENTACOES

MENU_PRINCIPAL = """Consultório Nutricionista Victor Afonso, que bom te ver por aí 🙏

Para te ajudar melhor, escolha uma das opções abaixo, por favor.

1️⃣ Informações sobre o acompanhamento nutricional
2️⃣ Informações sobre as Marinadas do Nutri
3️⃣ Outros assuntos

E só me responder com 1, 2 ou 3 💚

Em breve nossa atendente irá lhe responder!"""

SUBMENU_CONSULTA = """Por favor confirmar: 😊

1️⃣ Primeira consulta
2️⃣ Agendar retorno
3️⃣ Outras informações"""

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

Gostaria de agendar em *Copa, Méier ou Online*? 😊"""

PERGUNTA_LOCAL_RETORNO = """Por favor confirmar o local de atendimento para o retorno:

📍 Copacabana
📍 Méier
💻 Online"""

PERGUNTA_TURNO = """Você teria algum turno ou dia da semana de preferência? 📅

🌅 Manhã
☀️ Tarde  
🌙 Noite"""

MARINADAS = f"""Que ótima escolha! 🥩🔥

As *Marinadas do Nutri* são temperos naturais desenvolvidos pelo próprio Nutri Victor, pensados para deixar sua alimentação mais saborosa e saudável ao mesmo tempo.

Clica no link abaixo para conhecer e garantir o seu:
👉 {LINK_MARINADAS}

Qualquer dúvida é só chamar, nossa atendente está por aqui! 💚"""

PEDIR_DESCRICAO = """Olá! Fico feliz em te ajudar 😊

Por favor, me conta um pouco mais sobre o que você precisa. Pode descrever o assunto à vontade que nossa atendente irá te responder em breve! 💚"""

CONFIRMACAO_RECEBIMENTO = """Recebemos sua mensagem! 📩

Nossa atendente irá te responder em breve. Obrigado pelo contato! 💚"""

CONFIRMACAO_SOLICITACAO = """Perfeito! 😊✅

Sua solicitação foi recebida. Nossa atendente entrará em contato em breve para confirmar os detalhes da sua consulta! 💚"""

def notificacao_victor(paciente_nome: str, paciente_phone: str,
                        local: str = "", turno: str = "",
                        assunto: str = "", tipo: str = "agendamento") -> str:
    if tipo == "agendamento":
        return (
            f"📅 *Nova solicitação de consulta!*\n\n"
            f"*Paciente:* {paciente_nome}\n"
            f"*Telefone:* {paciente_phone}\n"
            f"*Local:* {local}\n"
            f"*Turno preferido:* {turno}\n\n"
            f"Por favor confirme o agendamento diretamente com o paciente 💚"
        )
    elif tipo == "outro":
        return (
            f"📬 *Nova mensagem recebida!*\n\n"
            f"*De:* {paciente_nome} — {paciente_phone}\n"
            f"*Assunto:* {assunto}\n\n"
            f"Responda diretamente pelo WhatsApp 💚"
        )
    elif tipo == "marinadas":
        return (
            f"🥩 *Interesse nas Marinadas!*\n\n"
            f"*Paciente:* {paciente_nome}\n"
            f"*Telefone:* {paciente_phone}\n\n"
            f"O link foi enviado automaticamente 💚"
        )
    return ""

def pos_agendamento_confirmado(nome: str) -> str:
    return f"""Perfeito, {nome}! Consulta agendada! 🎉

Abaixo segue um questionário pré-consulta com algumas perguntas importantes para você ter o melhor proveito com o Nutri Victor:
👉 {LINK_QUESTIONARIO}

Além disso, seguem abaixo as orientações para uma avaliação mais assertiva:
👉 {LINK_ORIENTACOES}

Qualquer dúvida é só chamar! 💚"""

ERRO_OPCAO_INVALIDA = """Não entendi sua resposta 😅

Por favor responda com o número da opção desejada:"""

AGUARDA_ATENDENTE = """Certo! Nossa atendente vai te responder em breve com todas as informações 💚"""
