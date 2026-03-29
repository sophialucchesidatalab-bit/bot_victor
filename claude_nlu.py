"""
claude_nlu.py
Usa a Claude API para extrair intenções do lead em linguagem natural.
Substitui as funções de detecção por regex/palavras-chave do bot.py.
"""

import json
import logging
import os
import anthropic

logger = logging.getLogger(__name__)

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    return _client


# ─────────────────────────────────────────────
# PROMPT BASE DO VICTOR
# ─────────────────────────────────────────────

CONTEXTO_VICTOR = """Você é o assistente virtual do Nutricionista Victor Afonso.
O consultório atende em 3 locais: Méier (MaxFit), Copacabana (Integra) e Online.
Os atendimentos acontecem de quarta-feira a sábado.
Turnos disponíveis: Manhã (até 11h59), Tarde (12h-17h59), Noite (18h em diante).
"""


# ─────────────────────────────────────────────
# EXTRAÇÃO DE INTENÇÃO DO MENU PRINCIPAL
# ─────────────────────────────────────────────

def extrair_opcao_menu(texto: str) -> str | None:
    """
    Identifica qual opção do menu o lead escolheu.
    Retorna: "1" (consulta), "2" (marinadas), "3" (outro) ou None.
    """
    prompt = f"""{CONTEXTO_VICTOR}

O lead enviou a seguinte mensagem para o menu principal:
"{texto}"

O menu tem 3 opções:
1 = Consulta / Acompanhamento Nutricional
2 = Marinadas do Nutri
3 = Outros assuntos

Responda APENAS com um JSON no formato:
{{"opcao": "1"}}
ou {{"opcao": "2"}}
ou {{"opcao": "3"}}
ou {{"opcao": null}} se não for possível identificar.

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if resultado and resultado.get("opcao"):
        return resultado["opcao"]
    return None


# ─────────────────────────────────────────────
# EXTRAÇÃO DE LOCAL + TURNO JUNTOS
# ─────────────────────────────────────────────

def extrair_local_e_turno(texto: str) -> dict:
    """
    Extrai local e turno de uma mensagem em linguagem natural.

    Exemplos que deve entender:
    - "quero sexta à tarde no méier" → local=Méier, turno=Tarde
    - "prefiro de manhã em copa" → local=Copacabana, turno=Manhã
    - "online à noite" → local=Online, turno=Noite
    - "méier" → local=Méier, turno=None (só local)
    - "tarde" → local=None, turno=Tarde (só turno)

    Retorna dict com chaves: local, turno (cada um pode ser None)
    """
    prompt = f"""{CONTEXTO_VICTOR}

O lead enviou a seguinte mensagem:
"{texto}"

Extraia o local e o turno mencionados.

Locais válidos: "Méier", "Copacabana", "Online"
- Méier = méier, meier, max, maxfit, academia, na max, na academia, na maxfit
- Copacabana = copa, copacabana, em copa, integra, na copa
- Online = online, remoto, virtual, meet, videochamada, pelo meet

Turnos válidos: "Manhã", "Tarde", "Noite"
- Manhã = manhã, manha, de manhã, de manha, pela manhã, pela manha, cedo, matutino, antes do meio-dia, de manhãzinha
- Tarde = tarde, de tarde, pela tarde, após o almoço, depois do almoço, 12h-17h
- Noite = noite, de noite, pela noite, à noite, a noite, após as 18h, depois das 18h

Responda APENAS com JSON no formato:
{{"local": "Méier", "turno": "Tarde"}}

Use null para campos não mencionados:
{{"local": "Copacabana", "turno": null}}

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if resultado:
        return {
            "local": resultado.get("local"),
            "turno": resultado.get("turno"),
        }
    return {"local": None, "turno": None}


# ─────────────────────────────────────────────
# EXTRAÇÃO SÓ DE LOCAL
# ─────────────────────────────────────────────

def extrair_local(texto: str) -> str | None:
    """
    Extrai apenas o local de uma mensagem.
    Retorna: "Méier", "Copacabana", "Online" ou None.
    """
    resultado = extrair_local_e_turno(texto)
    return resultado.get("local")


# ─────────────────────────────────────────────
# EXTRAÇÃO SÓ DE TURNO
# ─────────────────────────────────────────────

def extrair_turno(texto: str) -> str | None:
    """
    Extrai apenas o turno de uma mensagem.
    Retorna: "Manhã", "Tarde", "Noite" ou None.
    """
    resultado = extrair_local_e_turno(texto)
    return resultado.get("turno")


# ─────────────────────────────────────────────
# EXTRAÇÃO DE HORÁRIO ESCOLHIDO
# ─────────────────────────────────────────────

def extrair_horario_escolhido(texto: str, slots_disponiveis: list[dict]) -> dict | None:
    """
    Identifica qual slot o lead escolheu dentre os disponíveis.

    Parâmetros:
        texto: mensagem do lead (ex: "sexta às 9", "quarta 14:30", "dia 4 de manhã")
        slots_disponiveis: lista de dicts com data, dia, hora_inicio

    Retorna o dict do slot escolhido, "PERGUNTA" se for uma pergunta, ou None.
    """
    if not slots_disponiveis:
        return None

    # Remove formatação do WhatsApp (*negrito*, _itálico_) antes de processar
    import re as _re
    texto = _re.sub(r"[*_~]", "", texto).strip()

    # Formata lista de slots para o prompt
    lista_slots = "\n".join([
        f"- {s['dia']} {s['data']} às {s['hora_inicio']}"
        for s in slots_disponiveis
    ])

    prompt = f"""{CONTEXTO_VICTOR}

O lead respondeu com a seguinte mensagem:
"{texto}"

Os horários disponíveis são:
{lista_slots}

TAREFA: Identifique qual horário o lead quer agendar.

Exemplos de como o lead pode escrever:
- "sexta as 9h" ou "sexta, as 9h" ou "sexta 9" → dia=Sex, hora=09:00
- "quarta 10:30" ou "quarta às 10h30" → dia=Qua, hora=10:30
- "03/04 às 9:00" ou "dia 3 de abril 9h" → data=03/04/2026, hora=09:00
- "9h" sozinho → procura 09:00 na lista
- "10 horas" ou "dez horas" → hora=10:00
- "9h30" ou "9:30" → hora=09:30

CONVERSÕES IMPORTANTES:
- "9h" = "09:00"
- "9h30" = "09:30"  
- "10h" = "10:00"
- "11h30" = "11:30"

PERGUNTAS ABERTAS — se o lead perguntou algo em vez de escolher, retorne null:
- "tem às 13h?" → está perguntando, não escolhendo → slot=null
- "tem sábado?" → está perguntando → slot=null
- "qual o primeiro horário?" → está perguntando → slot=null

Se há dois dias iguais disponíveis (ex: duas sextas) e o lead não especificou a data, escolha a mais próxima (menor data).

Responda APENAS com JSON:
Se identificou: {{"dia": "Sex", "data": "03/04/2026", "hora_inicio": "09:00"}}
Se pergunta ou não identificou: {{"slot": null, "pergunta": true}}

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if not resultado:
        return None

    # Lead fez uma pergunta em vez de escolher
    if resultado.get("pergunta") or resultado.get("slot") is None:
        if resultado.get("hora_inicio") is None and resultado.get("data") is None:
            return "PERGUNTA"

    # Casa com o slot real da lista
    hora_extraida = resultado.get("hora_inicio")
    data_extraida = resultado.get("data")
    dia_extraido  = resultado.get("dia")

    if not hora_extraida:
        return None

    # Normaliza hora para comparação: "9:00" → "09:00"
    def norm_hora(h):
        if not h:
            return h
        partes = h.strip().split(":")
        return f"{int(partes[0]):02d}:{partes[1] if len(partes) > 1 else '00'}"

    hora_norm = norm_hora(hora_extraida)

    for slot in slots_disponiveis:
        slot_hora_norm = norm_hora(slot["hora_inicio"])
        if data_extraida and slot["data"] == data_extraida and slot_hora_norm == hora_norm:
            return slot
        if dia_extraido and slot["dia"] == dia_extraido and slot_hora_norm == hora_norm:
            return slot

    # Encontrou hora mas não casou com nenhum slot disponível
    return None


# ─────────────────────────────────────────────
# CHAMADA À API CLAUDE
# ─────────────────────────────────────────────

def _chamar_claude(prompt: str) -> dict | None:
    """
    Chama a Claude API e retorna o JSON parseado.
    Em caso de erro, retorna None para o bot cair no fallback de regex.
    """
    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # modelo mais rápido e barato
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()

        # Remove possíveis blocos de código markdown
        if texto.startswith("```"):
            linhas = texto.split("\n")
            texto = "\n".join(linhas[1:-1])

        return json.loads(texto)

    except json.JSONDecodeError as e:
        logger.warning(f"Claude retornou JSON inválido: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro ao chamar Claude API: {e}")
        return None

# ─────────────────────────────────────────────
# CONFIRMAÇÃO DE AGENDAMENTO
# ─────────────────────────────────────────────

def extrair_confirmacao(texto: str) -> bool | None:
    """
    Identifica se o lead confirmou ou recusou o agendamento.
    Muito mais robusto que regex — entende qualquer variação informal.

    Retorna: True=confirmou, False=recusou, None=não identificado
    """
    prompt = f"""O lead está confirmando ou recusando um agendamento de consulta.

Mensagem do lead: "{texto}"

Exemplos de CONFIRMAÇÃO: sim, confirmo, confirmado, correto, certo, ok, pode,
pode ser, fechado, combinado, perfeito, exato, isso mesmo, show, beleza,
tá bom, tá ótimo, vai nessa, pode marcar, marca aí, isso, perfeito, ótimo,
quero esse, esse mesmo, esse horário, esse está ótimo.

Exemplos de RECUSA: não, nao, errado, incorreto, cancelar, quero mudar,
outro horário, não é esse, prefiro outro, muda, troca, diferente.

Responda APENAS com JSON:
{{"confirmado": true}} se confirmou
{{"confirmado": false}} se recusou
{{"confirmado": null}} se não foi possível identificar

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if resultado and resultado.get("confirmado") is not None:
        return resultado["confirmado"]
    return None


# ─────────────────────────────────────────────
# RESPOSTAS LIVRES (do claude_api.py original)
# ─────────────────────────────────────────────

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
- Atende de quarta-feira a sábado

REGRAS IMPORTANTES:
- Nunca invente informações sobre o consultório
- Se não souber responder, diga que o Nutri Victor irá ajudar em breve
- Nunca confirme agendamentos — apenas colete preferências
- Nunca forneça valores diferentes de R$300,00
- Sempre direcione dúvidas complexas para o atendimento humano
"""


def processar_mensagem_livre(mensagem: str, contexto: str = "") -> str:
    """
    Usa Claude para responder perguntas abertas que não se encaixam
    nos fluxos fixos — dúvidas sobre o consultório, perguntas gerais, etc.
    """
    try:
        client = _get_client()
        messages = []
        if contexto:
            messages.append({"role": "user", "content": contexto})
            messages.append({"role": "assistant", "content": "Entendido."})
        messages.append({"role": "user", "content": mensagem})

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        return response.content[0].text

    except Exception as e:
        logger.error(f"Erro ao processar mensagem livre: {e}")
        return (
            "Desculpe, tive um problema técnico. 😕\n\n"
            "O *Nutri Victor* irá te responder em breve! 💚"
        )


def classificar_intencao(mensagem: str) -> str:
    """
    Classifica a intenção da mensagem.
    Retorna: 'agendar', 'informacao', 'marinadas', 'saudacao' ou 'outro'
    """
    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system="Classifique a mensagem em UMA palavra: 'agendar', 'informacao', 'marinadas', 'saudacao' ou 'outro'. Responda APENAS a palavra.",
            messages=[{"role": "user", "content": mensagem}]
        )
        return response.content[0].text.strip().lower()

    except Exception as e:
        logger.error(f"Erro ao classificar intenção: {e}")
        return "outro"
