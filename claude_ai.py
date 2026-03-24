import anthropic
import logging
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Você é o assistente virtual do Consultório Nutricionista Victor Afonso.
Seu nome é "Assistente do Nutri Victor".

Personalidade:
- Cordial, acolhedor e profissional
- Usa emojis com moderação (🙏💚✅😊)
- Escreve em português brasileiro
- Respostas curtas e objetivas — máximo 3 parágrafos

Sobre o consultório:
- Nutricionista: Victor Afonso
- Atendimento presencial: Max Fit (Méier) e Integra Saúde (Copacabana)
- Atendimento online: Google Meet ou WhatsApp Vídeo
- Valor da consulta: R$300,00
- Pagamento presencial: cartão ou à vista
- Pagamento online: Pix, transferência ou PagSeguro
- Horários Méier/Copa: Ter a Qui 8h, 9h30, 11h, 14h30, 16h, 17h30 | Sáb 8h30, 10h, 11h30
- Horários Online: mesmos + 18h, 19h30

REGRAS IMPORTANTES:
- Nunca invente informações sobre o consultório
- Se não souber responder, diga que a atendente irá ajudar
- Nunca confirme agendamentos sem a aprovação do Victor
- Nunca forneça valores diferentes de R$300,00
- Sempre direcione dúvidas complexas para a atendente humana
"""

def processar_mensagem_livre(mensagem: str, contexto: str = "") -> str:
    """
    Usa Claude Haiku para processar mensagens que não se encaixam
    nos fluxos fixos — dúvidas, perguntas abertas, etc.
    """
    try:
        messages = []
        if contexto:
            messages.append({"role": "user", "content": contexto})
            messages.append({"role": "assistant", "content": "Entendido."})
        messages.append({"role": "user", "content": mensagem})

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Erro ao chamar Claude API: {e}")
        return (
            "Desculpe, tive um problema técnico. 😕\n\n"
            "Nossa atendente irá te responder em breve! 💚"
        )

def classificar_intencao(mensagem: str) -> str:
    """
    Classifica a intenção da mensagem recebida.
    Retorna: 'agendar', 'informacao', 'marinadas', 'outro', 'saudacao'
    """
    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=10,
            system="Classifique a mensagem em UMA palavra: 'agendar', 'informacao', 'marinadas', 'saudacao' ou 'outro'. Responda APENAS a palavra.",
            messages=[{"role": "user", "content": mensagem}]
        )
        return response.content[0].text.strip().lower()
    except Exception as e:
        logger.error(f"Erro ao classificar intenção: {e}")
        return "outro"
