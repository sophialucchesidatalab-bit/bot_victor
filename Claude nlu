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
- Méier = méier, max, maxfit, academia, na max, na academia
- Copacabana = copa, copacabana, em copa, integra
- Online = online, remoto, virtual, meet, videochamada

Turnos válidos: "Manhã", "Tarde", "Noite"
- Manhã = manhã, manha, de manhã, pela manhã, cedo, matutino
- Tarde = tarde, de tarde, pela tarde
- Noite = noite, de noite, pela noite

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

    Retorna o dict do slot escolhido ou None.
    """
    if not slots_disponiveis:
        return None

    # Formata lista de slots para o prompt
    lista_slots = "\n".join([
        f"- {s['dia']} {s['data']} às {s['hora_inicio']}"
        for s in slots_disponiveis
    ])

    prompt = f"""{CONTEXTO_VICTOR}

O lead escolheu um horário com a mensagem:
"{texto}"

Os horários disponíveis são:
{lista_slots}

Identifique qual horário o lead quer. Considere variações como:
- "sexta" = dia da semana
- "9h", "9:00", "nove horas" = hora
- "dia 4" = data
- "amanhã", "semana que vem" = referências relativas

Responda APENAS com JSON no formato:
{{"dia": "Sex", "data": "04/04/2026", "hora_inicio": "09:00"}}

ou {{"slot": null}} se não conseguir identificar.

Nenhum texto além do JSON."""

    resultado = _chamar_claude(prompt)
    if not resultado or resultado.get("slot") is None and not resultado.get("hora_inicio"):
        return None

    # Casa com o slot real da lista
    hora_extraida = resultado.get("hora_inicio")
    data_extraida = resultado.get("data")
    dia_extraido  = resultado.get("dia")

    for slot in slots_disponiveis:
        if data_extraida and slot["data"] == data_extraida and slot["hora_inicio"] == hora_extraida:
            return slot
        if dia_extraido and slot["dia"] == dia_extraido and slot["hora_inicio"] == hora_extraida:
            return slot

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
