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

# Dias em que Victor ATENDE
DIAS_VALIDOS    = {"Qua", "Qui", "Sex", "Sáb"}
# Dias em que Victor NÃO atende
DIAS_BLOQUEADOS = {"Seg", "Ter", "Dom"}


# ─────────────────────────────────────────────
# EXTRAÇÃO DE INTENÇÃO DO MENU PRINCIPAL
# ─────────────────────────────────────────────

def extrair_opcao_menu(texto: str) -> str | None:
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
    resultado = extrair_local_e_turno(texto)
    return resultado.get("local")


# ─────────────────────────────────────────────
# EXTRAÇÃO SÓ DE TURNO
# ─────────────────────────────────────────────

def extrair_turno(texto: str) -> str | None:
    """Extrai apenas o PRIMEIRO turno mencionado."""
    resultado = extrair_local_e_turno(texto)
    return resultado.get("turno")


# ─────────────────────────────────────────────
# EXTRAÇÃO DE MÚLTIPLOS TURNOS
# ─────────────────────────────────────────────

def extrair_multiplos_turnos(texto: str) -> list[str]:
    """
    Extrai TODOS os turnos mencionados pelo lead.
    Ex: "De preferência manhã ou à noite" → ["Manhã", "Noite"]
    Retorna lista ordenada (Manhã → Tarde → Noite).
    """
    prompt = f"""{CONTEXTO_VICTOR}

O lead enviou a seguinte mensagem sobre preferência de horário:
"{texto}"

Identifique TODOS os turnos mencionados ou implícitos.

Turnos válidos: "Manhã", "Tarde", "Noite"
- Manhã = manhã, manha, de manhã, cedo, matutino, antes do meio-dia, de manhãzinha, pela manhã
- Tarde = tarde, de tarde, pela tarde, após o almoço, depois do almoço
- Noite = noite, de noite, pela noite, à noite, a noite, após as 18h, depois das 18h

Casos especiais:
- "qualquer horário" / "qualquer" / "tanto faz" / "não tenho preferência" → todos os três turnos
- "manhã ou noite" → ["Manhã", "Noite"]
- "tarde e noite" → ["Tarde", "Noite"]

Responda APENAS com JSON:
{{"turnos": ["Manhã", "Noite"]}}

Se nenhum turno identificado:
{{"turnos": []}}

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if resultado and isinstance(resultado.get("turnos"), list):
        ORDEM = {"Manhã": 0, "Tarde": 1, "Noite": 2}
        turnos = [t for t in resultado["turnos"] if t in ORDEM]
        return sorted(turnos, key=lambda t: ORDEM[t])

    # Fallback regex
    import unicodedata
    def norm(s):
        s = s.lower()
        s = unicodedata.normalize("NFD", s)
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    t = norm(texto)
    turnos = []
    if any(x in t for x in ["manha", "cedo", "matutino"]):
        turnos.append("Manhã")
    if any(x in t for x in ["tarde", "almoco"]):
        turnos.append("Tarde")
    if any(x in t for x in ["noite", "18h", "depois das 18"]):
        turnos.append("Noite")
    if any(x in t for x in ["qualquer", "tanto faz", "nao tenho preferencia"]):
        return ["Manhã", "Tarde", "Noite"]
    return turnos


# ─────────────────────────────────────────────
# EXTRAÇÃO DE DIAS DA SEMANA  ← NOVO
# ─────────────────────────────────────────────

def extrair_dias_semana(texto: str) -> dict:
    """
    Extrai todos os dias da semana mencionados e classifica em válidos/bloqueados.

    Retorna:
    {
        "validos":    ["Qui", "Sex"],  # dias que Victor atende (Qua-Sáb)
        "bloqueados": ["Ter"],         # dias que Victor NÃO atende (Seg/Ter/Dom)
        "todos":      ["Ter", "Qui", "Sex"]
    }
    Lista vazia = nenhum dia daquele tipo foi mencionado.
    """
    prompt = f"""{CONTEXTO_VICTOR}

O lead enviou a seguinte mensagem:
"{texto}"

Identifique TODOS os dias da semana mencionados explícita ou implicitamente.

Abreviações a usar na resposta:
Segunda-feira = Seg | Terça-feira = Ter | Quarta-feira = Qua
Quinta-feira  = Qui | Sexta-feira = Sex | Sábado = Sáb | Domingo = Dom

Dias que o Nutri Victor ATENDE: Qua, Qui, Sex, Sáb
Dias que o Nutri Victor NÃO atende: Seg, Ter, Dom

Exemplos:
- "quero marcar na terça ou na quinta" → validos=["Qui"], bloqueados=["Ter"]
- "só terça" → validos=[], bloqueados=["Ter"]
- "sexta ou sábado" → validos=["Sex","Sáb"], bloqueados=[]
- "de quarta em diante" → validos=["Qua","Qui","Sex","Sáb"], bloqueados=[]
- "de quinta em diante" → validos=["Qui","Sex","Sáb"], bloqueados=[]
- "qualquer dia" → validos=["Qua","Qui","Sex","Sáb"], bloqueados=[]
- "segunda a sexta" → validos=["Qua","Qui","Sex"], bloqueados=["Seg","Ter"]
- mensagem sem nenhum dia → validos=[], bloqueados=[]

Responda APENAS com JSON:
{{"validos": ["Qui"], "bloqueados": ["Ter"]}}

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)

    ORDEM = {"Seg": 0, "Ter": 1, "Qua": 2, "Qui": 3, "Sex": 4, "Sáb": 5, "Dom": 6}

    if resultado and isinstance(resultado.get("validos"), list):
        validos    = [d for d in resultado.get("validos", [])    if d in ORDEM]
        bloqueados = [d for d in resultado.get("bloqueados", []) if d in ORDEM]
        validos    = sorted(validos,    key=lambda d: ORDEM[d])
        bloqueados = sorted(bloqueados, key=lambda d: ORDEM[d])
        todos      = sorted(validos + bloqueados, key=lambda d: ORDEM[d])
        return {"validos": validos, "bloqueados": bloqueados, "todos": todos}

    # Fallback regex
    import unicodedata, re
    def norm(s):
        s = s.lower()
        s = unicodedata.normalize("NFD", s)
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    t = norm(texto)
    encontrados = set()

    MAPA = {
        "segunda": "Seg", "terca": "Ter", "quarta": "Qua",
        "quinta":  "Qui", "sexta": "Sex", "sabado": "Sáb", "domingo": "Dom",
    }
    for palavra, abrev in MAPA.items():
        if re.search(rf"\b{palavra}\b", t):
            encontrados.add(abrev)

    if re.search(r"quarta\s*(em\s*diante|para\s*frente|adiante)", t):
        encontrados.update(["Qua", "Qui", "Sex", "Sáb"])
    if re.search(r"quinta\s*(em\s*diante|para\s*frente|adiante)", t):
        encontrados.update(["Qui", "Sex", "Sáb"])
    if re.search(r"qualquer\s*dia|tanto\s*faz", t):
        encontrados.update(["Qua", "Qui", "Sex", "Sáb"])

    validos    = sorted([d for d in encontrados if d in DIAS_VALIDOS],    key=lambda d: ORDEM[d])
    bloqueados = sorted([d for d in encontrados if d in DIAS_BLOQUEADOS], key=lambda d: ORDEM[d])
    todos      = sorted(list(encontrados), key=lambda d: ORDEM[d])
    return {"validos": validos, "bloqueados": bloqueados, "todos": todos}


# ─────────────────────────────────────────────
# EXTRAÇÃO DE HORÁRIO ESCOLHIDO
# ─────────────────────────────────────────────

def extrair_horario_escolhido(texto: str, slots_disponiveis: list[dict]) -> dict | None:
    """
    Identifica qual slot o lead escolheu dentre os disponíveis.
    Retorna o dict do slot, "PERGUNTA" se for pergunta, ou None.
    """
    if not slots_disponiveis:
        return None

    import re as _re
    texto = _re.sub(r"[*_~]", "", texto).strip()

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

Exemplos:
- "sexta as 9h" ou "sexta 9" → dia=Sex, hora=09:00
- "quarta às 10h30" → dia=Qua, hora=10:30
- "03/04 às 9:00" → data=03/04/2026, hora=09:00
- "9h" sozinho → procura 09:00 na lista

CONVERSÕES: "9h"=09:00 | "9h30"=09:30 | "10h"=10:00 | "11h30"=11:30

PERGUNTAS (retorne null):
- "tem às 13h?" / "tem sábado?" / "qual o primeiro horário?"

Se há dois dias iguais, escolha a data mais próxima.

Responda APENAS com JSON:
Se identificou: {{"dia": "Sex", "data": "03/04/2026", "hora_inicio": "09:00"}}
Se pergunta: {{"slot": null, "pergunta": true}}

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if not resultado:
        return None

    if resultado.get("pergunta") or resultado.get("slot") is None:
        if resultado.get("hora_inicio") is None and resultado.get("data") is None:
            return "PERGUNTA"

    hora_extraida = resultado.get("hora_inicio")
    data_extraida = resultado.get("data")
    dia_extraido  = resultado.get("dia")

    if not hora_extraida:
        return None

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

    return None


# ─────────────────────────────────────────────
# CHAMADA À API CLAUDE
# ─────────────────────────────────────────────

def _chamar_claude(prompt: str) -> dict | None:
    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        texto = response.content[0].text.strip()

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
# RESPOSTAS LIVRES
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
