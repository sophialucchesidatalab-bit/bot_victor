import json as _json
import logging
import re as _re
import unicodedata as _unicodedata
from datetime import datetime

from config import (
    VICTOR_PHONE,
    ESTADO_AGUARDA_OPCAO,
    ESTADO_AGUARDA_SUBMENU,
    ESTADO_AGUARDA_LOCAL,
    ESTADO_AGUARDA_TURNO,
    ESTADO_AGUARDA_HORARIO,
    ESTADO_AGUARDA_CONFIRMACAO,
    ESTADO_AGUARDA_DESCRICAO,
    ESTADO_AGUARDA_MARINADAS,
    ESTADO_ATENDIMENTO_HUMANO,
    ESTADO_AGUARDA_NOME_FAMILIAR,
    ESTADO_AGUARDA_CONFIRMACAO_VALOR,
    DURACAO_CONSULTA,
)
from sheets import buscar_estado, criar_registro, atualizar_estado
from sheets_agenda import buscar_horarios, remover_horario_confirmado
from zapi import enviar_mensagem, enviar_imagem
from claude_nlu import (
    extrair_opcao_menu,
    extrair_local_e_turno,
    extrair_local,
    extrair_turno,
    extrair_multiplos_turnos,
    extrair_dias_semana,
    extrair_horario_escolhido,
    extrair_confirmacao,
)
import mensagens as msg
from mensagens import erro_nao_entendi

logger = logging.getLogger(__name__)

NOMES_DIAS = {
    "Seg": "Segunda-feira", "Ter": "Terça-feira", "Qua": "Quarta-feira",
    "Qui": "Quinta-feira",  "Sex": "Sexta-feira",  "Sáb": "Sábado", "Dom": "Domingo",
}


# ─────────────────────────────────────────────
# HELPERS GERAIS
# ─────────────────────────────────────────────

def normalizar_phone(phone):
    digits = "".join(c for c in str(phone) if c.isdigit())
    if digits.startswith("55") and len(digits) > 13:
        digits = digits[2:]
    return digits


def normalizar(texto):
    texto = texto.lower().strip()
    texto = _unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if _unicodedata.category(c) != "Mn")


def encaminhar_para_humano(phone, row, nome, texto):
    atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
    enviar_mensagem(phone, msg.ENCAMINHAR_HUMANO)
    enviar_mensagem(VICTOR_PHONE, msg.notif_nao_entendeu(nome, phone, texto))


# ─────────────────────────────────────────────
# AVISO DE DIA BLOQUEADO
# ─────────────────────────────────────────────

def _montar_aviso_dia_bloqueado(bloqueados, local):
    dias_bloq = ", ".join(NOMES_DIAS.get(d, d) for d in bloqueados)
    return (
        f"Infelizmente o Nutri Victor não atende às {dias_bloq}. 😕\n\n"
        f"O atendimento acontece de *Quarta a Sábado*.\n\n"
        f"Você consegue em algum desses dias? 😊"
    )


def _verificar_dias_e_avisar(phone, texto, local):
    try:
        dias = extrair_dias_semana(texto)
    except Exception:
        return False
    bloqueados = dias.get("bloqueados", [])
    validos    = dias.get("validos", [])
    if bloqueados and not validos:
        aviso = _montar_aviso_dia_bloqueado(bloqueados, local or "nosso consultorio")
        enviar_mensagem(phone, aviso)
        return True
    return False


# ─────────────────────────────────────────────
# DETECCAO DE INTENCAO DE AGENDAMENTO
# ─────────────────────────────────────────────

_PADROES_AGENDAMENTO = _re.compile(
    r"\b("
    r"quero\s+agendar|quero\s+marcar|queria\s+marcar|gostaria\s+de\s+agendar|"
    r"quero\s+(?:uma\s+)?consulta|queria\s+(?:uma\s+)?consulta|"
    r"tem\s+vaga|tem\s+horario|tem\s+disponibilidade|"
    r"posso\s+marcar|queria\s+ver\s+(?:um\s+)?horario|"
    r"agenda\s+aberta|quero\s+atendimento|"
    r"marcar\s+consulta|agendar\s+consulta|"
    r"gostaria\s+de\s+marcar|posso\s+agendar|"
    r"como\s+(?:faco|faz[eo])\s+para\s+(?:marcar|agendar)|"
    r"quero\s+(?:me\s+)?consultar|gostaria\s+de\s+(?:me\s+)?consultar"
    r")\b"
)


def detectar_intencao_agendamento(texto):
    t = normalizar(texto)
    if _PADROES_AGENDAMENTO.search(t):
        return True
    try:
        from claude_nlu import classificar_intencao
        return classificar_intencao(texto) == "agendar"
    except Exception:
        return False


# ─────────────────────────────────────────────
# DETECCAO DE INTENCAO DE SABER MAIS
# ─────────────────────────────────────────────

_PADROES_INFO_CONSULTA = _re.compile(
    r"\b("
    r"quero\s+saber\s+mais|queria\s+saber\s+mais|gostaria\s+de\s+saber\s+mais|"
    r"quero\s+saber\s+mais\s+sobre|queria\s+saber\s+mais\s+sobre|"
    r"como\s+funciona|"
    r"como\s+e\s+(?:a\s+)?(?:consulta|o\s+atendimento|o\s+acompanhamento|feito|o\s+trabalho)|"
    r"queria\s+entender|pode\s+(?:me\s+)?explicar|me\s+explica|"
    r"explicar\s+(?:melhor|como\s+funciona)|"
    r"estou\s+(?:pensando|interessado|interessada)\s+em|"
    r"(?:quero|queria|vou)\s+(?:come[cc]ar|iniciar)\s+acompanhamento|"
    r"(?:quero|queria|vou)\s+(?:come[cc]ar|iniciar)\s+(?:a\s+)?consulta|"
    r"tenho\s+interesse|"
    r"quanto\s+tempo\s+dura"
    r")\b"
)


def detectar_intencao_info_consulta(texto):
    t = normalizar(texto)
    return bool(_PADROES_INFO_CONSULTA.search(t))


# ─────────────────────────────────────────────
# DETECCAO DE INTENCAO DE AGENDAR PARA FAMILIAR
# ─────────────────────────────────────────────

_PADROES_FAMILIAR = _re.compile(
    r"\b("
    r"para\s+(?:meu|minha)\s*(?:marido|esposa|esposo|mulher|namorado|namorada|"
    r"filho|filha|mae|pai|irma|irmao|amigo|amiga|familiar|parceiro|parceira)|"
    r"para\s+outra\s+pessoa|"
    r"para\s+ele\s+tambem|para\s+ela\s+tambem|"
    r"quero\s+(?:marcar|agendar)\s+duas\s+pessoas|"
    r"queria\s+dois\s+horarios|dois\s+horarios\s+seguidos|"
    r"para\s+mim\s+e\s+para|"
    r"no\s+mesmo\s+dia\s+(?:para|tambem)|"
    r"tambem\s+(?:quer|vai)\s+(?:marcar|agendar)|"
    r"seria\s+para\s+(?:meu|minha)"
    r")\b"
)


def detectar_intencao_familiar(texto):
    t = normalizar(texto)
    return bool(_PADROES_FAMILIAR.search(t))




# ─────────────────────────────────────────────
# DETECCAO DE PERGUNTA DE VALOR
# ─────────────────────────────────────────────

_PADROES_VALOR = _re.compile(
    r"\b("
    # quanto custa / quanto é / quanto sai / quanto fica
    r"quanto\s+(?:custa|e|que\s+e|fica|sai|ta|tah|esta|esta\s+custando|custando|preciso\s+investir)|"
    # qual o valor / qual o investimento / qual o custo
    r"qual\s+(?:o\s+)?(?:valor|investimento|custo|preco)|"
    # palavras soltas (fuzzy)
    r"\bvalor\b|\bpreco\b|\binvestimento\b|\bcusto\b|"
    # gostaria de saber / poderia me informar
    r"gostaria\s+de\s+saber\s+(?:o\s+)?(?:valor|quanto|preco)|"
    r"pode(?:ria)?\s+(?:me\s+)?(?:informar|dizer)\s+(?:o\s+)?(?:valor|quanto)|"
    # queria saber antes de marcar
    r"queria\s+saber\s+(?:o\s+)?(?:valor|quanto|preco)|"
    r"saber\s+quanto\s+custa\s+antes|saber\s+(?:o\s+)?valor\s+antes|"
    # quanto custa com você / passar com o nutri
    r"quanto\s+custa\s+(?:com|passar|se\s+consultar|atendimento)|"
    r"quanto\s+custa\s+passar|quanto\s+custa\s+com\s+(?:voce|o\s+nutri)|"
    # variações com erros de digitação comuns
    r"valro|vaor|preco\s+da\s+consul|quanto\s+custa\s+consult"
    r")\b"
)

# Estados em que NÃO interceptamos pergunta de valor
_ESTADOS_SEM_INTERCEPTACAO_VALOR = {
    ESTADO_ATENDIMENTO_HUMANO,
    ESTADO_AGUARDA_CONFIRMACAO_VALOR,
    ESTADO_AGUARDA_NOME_FAMILIAR,
}


def detectar_pergunta_valor(texto: str) -> bool:
    """Retorna True se o paciente está perguntando o valor/preço da consulta."""
    t = normalizar(texto)
    return bool(_PADROES_VALOR.search(t))


def _mensagem_retomada_fluxo(etapa_anterior: str, local: str) -> str:
    """Retorna a mensagem de retomada adequada para o estado anterior."""
    if etapa_anterior == ESTADO_AGUARDA_LOCAL:
        return msg.PERGUNTA_LOCAL
    if etapa_anterior in (ESTADO_AGUARDA_TURNO, ESTADO_AGUARDA_SUBMENU):
        return msg.PERGUNTA_TURNO
    if etapa_anterior == ESTADO_AGUARDA_OPCAO:
        return msg.MENU_PRINCIPAL
    # Para outros estados retorna string vazia (sem mensagem extra)
    return ""

# ─────────────────────────────────────────────
# DETECCAO DE INTENCOES
# ─────────────────────────────────────────────

# Saudações puras — retorna None imediatamente sem chamar o Claude NLU
# O bloco AGUARDA_OPCAO vai repetir o MENU_PRINCIPAL
_SAUDACOES = {
    "oi","ola","ola!","oi!","bom dia","boa tarde","boa noite",
    "bom dia!","boa tarde!","boa noite!","oi tudo bem","ola tudo bem",
    "hey","hello","hi","tudo bem","tudo bom","boa","salve","eai","e ai",
    "opa","oie","oii","oiii","oi boa tarde","oi boa noite","oi bom dia",
}

def detectar_opcao_menu(t, texto_original=""):
    # Saudacoes puras nao precisam chamar o Claude — retorna None direto
    if t.strip() in _SAUDACOES:
        return None

    try:
        opcao = extrair_opcao_menu(texto_original or t)
        if opcao:
            return opcao
    except Exception:
        pass
    if t in ["1", "1️⃣"] or t.startswith("1"): return "1"
    if any(x in t for x in ["consul","acompanhamento","nutricional","nutri","retorno","agendar","agendamento","informacao","informacoes","primeira"]): return "1"
    if t in ["2", "2️⃣"] or t.startswith("2"): return "2"
    if any(x in t for x in ["marinada","marinadas","tempero","produto"]): return "2"
    if t in ["3", "3️⃣"] or t.startswith("3"): return "3"
    if any(x in t for x in ["outro","outros","assunto","duvida","pergunta"]): return "3"
    return None


def detectar_opcao_submenu(t):
    if t in ["1", "1️⃣"] or t.startswith("1"): return "1"
    if any(x in t for x in [
        # diretas
        "primeira","novo","nunca fui","primeira vez","nunca consultei",
        "nunca fiz","nunca passei","primeira consulta","paciente novo",
        "novo paciente","nao tenho cadastro","nao sou cadastrado",
        "quero comecar","quero iniciar","primeira visita",
        # variações naturais
        "nunca fiz consulta","nunca consultei antes","nunca passei com",
        "nunca fui paciente","nao sou paciente ainda","nao sou paciente",
        "quero comecar com","quero comecar acompanhamento",
        "quero iniciar acompanhamento","queria comecar","queria iniciar",
        "queria saber como comecar","queria marcar minha primeira",
        "quero fazer minha primeira","quero marcar primeira",
        "quero agendar primeira",
        # com dúvida inicial sobre como funciona (primeira vez)
        "como faco para comecar","como faco para marcar primeira",
        "como funciona a primeira","como funciona consulta com",
        # curtas / informais
        "sou novo","novo aqui","quero comecar contigo",
        "quero iniciar contigo","iniciar acompanhamento",
        # com erro de digitação comum
        "nunca fiz consuta","primeira consuta","quero comecar consuta",
        "quero inicia acompanhamento",
    ]): return "1"
    if t in ["2", "2️⃣"] or t.startswith("2"): return "2"
    if any(x in t for x in [
        # diretas
        "retorno","voltar","ja fui","segunda","acompanhamento",
        "ja consultei","ja fiz consulta","ja passei","sou paciente",
        "ja sou paciente","quero retornar","continuacao","continuar",
        "dar continuidade","ja tenho cadastro","retornar",
        # variações naturais
        "ja consultei com","ja fiz consulta com","quero continuar acompanhamento",
        "quero continuar com","quero voltar","quero voltar a consultar",
        "quero voltar ao acompanhamento","quero retornar consulta",
        "quero remarcar retorno","preciso marcar retorno",
        "quero fazer retorno","quero agendar retorno",
        "quero continuar tratamento","quero continuar plano",
        "quero voltar consulta","reagendar retorno",
        # curtas
        "continuidade","voltar",
        # com erro de digitação
        "ja consutei","quero retorna","quero continua","retorno consulta",
    ]): return "2"
    if t in ["3", "3️⃣"] or t.startswith("3"): return "3"
    if any(x in t for x in [
        # diretas
        "outro","outros","informacao","duvida","outra coisa",
        "outra duvida","outra pergunta","nao e sobre consulta",
        "quero saber outra","tenho uma pergunta",
        # variações naturais
        "tenho uma duvida","queria tirar uma duvida","queria perguntar",
        "posso tirar uma duvida","posso fazer uma pergunta",
        "queria saber uma coisa","queria saber uma informacao",
        "tem como me explicar",
        # curtas
        "pergunta","queria saber",
        # com erro de digitação
        "tenho duvida","queria tira uma duvida",
    ]): return "3"
    return None


def detectar_local(texto):
    try:
        local = extrair_local(texto)
        if local:
            return local
    except Exception:
        pass
    t = normalizar(texto)
    if any(x in t for x in ["copa","copacabana","em copa"]):
        return "Copacabana"
    if any(x in t for x in ["meier","meir","mier","max","maxfit","academia","na max","na academia"]):
        return "Méier"
    if any(x in t for x in ["online","remoto","virtual","meet"]):
        return "Online"
    return None


def detectar_turno(texto):
    try:
        turno = extrair_turno(texto)
        if turno:
            return turno
    except Exception:
        pass
    t = normalizar(texto)
    if any(x in t for x in ["manha", "de manha", "pela manha", "cedo", "matutino"]):
        return "Manhã"
    if any(x in t for x in ["tarde", "de tarde", "pela tarde"]):
        return "Tarde"
    if any(x in t for x in ["noite", "de noite", "pela noite"]):
        return "Noite"
    return None


def detectar_turnos(texto):
    try:
        turnos = extrair_multiplos_turnos(texto)
        if turnos:
            return turnos
    except Exception:
        pass
    t = normalizar(texto)
    turnos = []
    if any(x in t for x in ["manha", "cedo", "matutino"]):
        turnos.append("Manhã")
    if any(x in t for x in ["tarde", "almoco"]):
        turnos.append("Tarde")
    if any(x in t for x in ["noite", "18h"]):
        turnos.append("Noite")
    if any(x in t for x in ["qualquer", "tanto faz"]):
        return ["Manhã", "Tarde", "Noite"]
    return turnos


def detectar_confirmacao(texto):
    try:
        resultado = extrair_confirmacao(texto)
        if resultado is not None:
            return resultado
    except Exception:
        pass
    t = normalizar(texto)
    if any(x in t for x in [
        "sim", "confirmo", "confirmar", "confirmado", "correto", "certo",
        "isso", "ok", "pode", "pode ser", "fechado", "combinado",
        "perfeito", "exato", "exatamente", "isso mesmo", "show",
        "beleza", "otimo", "ta bom", "valeu", "vai nessa", "marca ai", "podemos", "vamos"
    ]):
        return True
    if any(x in t for x in [
        "nao", "não", "errado", "incorreto", "cancelar",
        "mudar", "outro", "diferente", "trocar"
    ]):
        return False
    return None


def detectar_depois_confirmo(texto):
    t = normalizar(texto)
    return any(x in t for x in [
        "depois confirmo","depois eu confirmo","confirmo depois",
        "vou confirmar depois","te aviso","aviso depois",
        "pensar","vou ver","ver depois","depois eu falo",
        "falo depois","depois te falo",
    ])


def detectar_dia_bloqueado(texto):
    t = normalizar(texto)
    return any(x in t for x in ["segunda","seg","terca","ter","domingo","dom"])


def detectar_endereco(texto):
    t = normalizar(texto)
    return any(x in t for x in [
        "endereco","endereço","onde fica","localizacao",
        "como chegar","onde e","onde é","maps"
    ])


# ─────────────────────────────────────────────
# HELPERS DE SLOTS
# ─────────────────────────────────────────────

def buscar_slots_por_turnos(local, turnos):
    todos_slots = []
    slots_vistos = set()
    for turno in turnos:
        for slot in buscar_horarios(local, turno):
            chave = (slot["data"], slot["hora_inicio"])
            if chave not in slots_vistos:
                slots_vistos.add(chave)
                todos_slots.append(slot)

    def sort_slot(s):
        try:
            d, m, a = s["data"].split("/")
            return (int(a), int(m), int(d), s["hora_inicio"])
        except Exception:
            return (9999, 99, 99, s["hora_inicio"])

    todos_slots.sort(key=sort_slot)
    return todos_slots


def buscar_slots_seguidos(local, data, hora_confirmada):
    """
    Busca slots no mesmo local/data imediatamente apos o horario confirmado.
    Tolerancia de +-10min para variacoes de grade.
    """
    if not data or not hora_confirmada:
        return []

    duracao = DURACAO_CONSULTA.get(local, 90)
    todos   = buscar_slots_por_turnos(local, ["Manhã", "Tarde", "Noite"])
    do_dia  = [s for s in todos if s["data"] == data]

    if not do_dia:
        return []

    def hm_to_min(h):
        try:
            hh, mm = h.split(":")
            return int(hh) * 60 + int(mm)
        except Exception:
            return -1

    fim_confirmado = hm_to_min(hora_confirmada) + duracao
    return [s for s in do_dia if abs(hm_to_min(s["hora_inicio"]) - fim_confirmado) <= 10]


def formatar_horarios_para_mensagem(slots, local_bot):
    if not slots:
        return None
    DIAS_PT = {
        "Seg":"Segunda-feira","Ter":"Terça-feira","Qua":"Quarta-feira",
        "Qui":"Quinta-feira","Sex":"Sexta-feira","Sáb":"Sábado","Dom":"Domingo",
    }
    por_dia = {}
    for slot in slots:
        chave = (slot["dia"], slot["data"])
        if chave not in por_dia:
            por_dia[chave] = []
        por_dia[chave].append(slot["hora_inicio"])

    def sort_key(chave):
        _, data_str = chave
        try:
            d, m, a = data_str.split("/")
            return (int(a), int(m), int(d))
        except Exception:
            return (9999, 99, 99)

    linhas = []
    for (dia_abrev, data) in sorted(por_dia.keys(), key=sort_key):
        nome_dia = DIAS_PT.get(dia_abrev, dia_abrev)
        horarios = "; ".join(por_dia[(dia_abrev, data)])
        linhas.append(f"*{nome_dia} ({data}):* {horarios}")

    local_nome = {"Copacabana":"Copacabana","Méier":"no Méier","Online":"online"}.get(local_bot, local_bot)
    corpo = "\n".join(linhas)
    return (
        f"Em {local_nome}, tenho os seguintes horários disponíveis:\n\n"
        f"{corpo}\n\n"
        f"Me envie o dia e horário de sua preferência para confirmar sua consulta. "
        f"_(considere sempre o horário de início)_"
    )


def _recuperar_turnos_pre(registro):
    hora_raw = registro.get("hora", "")
    if not hora_raw:
        return []
    try:
        parsed = _json.loads(hora_raw)
        if isinstance(parsed, dict) and "_turnos_pre" in parsed:
            return parsed["_turnos_pre"] or []
    except Exception:
        pass
    return []


def _recuperar_hora_confirmada(registro):
    """Extrai hora_inicio do slot confirmado guardado no campo hora."""
    hora_raw = registro.get("hora", "")
    if not hora_raw:
        return ""
    try:
        parsed = _json.loads(hora_raw)
        if isinstance(parsed, dict) and "hora_inicio" in parsed:
            return parsed.get("hora_inicio", "")
    except Exception:
        pass
    import re
    if re.match(r"^\d{2}:\d{2}$", hora_raw.strip()):
        return hora_raw.strip()
    return ""


def _enviar_slots_apos_submenu(phone, row, nome_salvo, local, turnos_pre):
    atualizar_estado(row, hora="")
    if turnos_pre:
        slots = buscar_slots_por_turnos(local, turnos_pre)
        if slots:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_HORARIO,
                             hora=_json.dumps(slots, ensure_ascii=False))
            enviar_mensagem(phone, formatar_horarios_para_mensagem(slots, local))
        else:
            turno_label = " / ".join(turnos_pre)
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO, hora=turno_label)
            enviar_mensagem(phone, msg.SEM_HORARIOS_DISPONIVEIS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_triagem(nome_salvo, phone, local, turno_label))
    else:
        atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO)
        enviar_mensagem(phone, msg.PERGUNTA_TURNO)


# ─────────────────────────────────────────────
# HELPERS DE HORARIO
# ─────────────────────────────────────────────

def identificar_slot_escolhido(texto, slots):
    import re as _re2
    texto = _re2.sub(r"[*_~]", "", texto).strip()
    try:
        slot = extrair_horario_escolhido(texto, slots)
        if slot == "PERGUNTA":
            return "PERGUNTA"
        if slot:
            return slot
    except Exception:
        pass
    t = normalizar(texto)
    DIAS_NORM = {
        "quarta":"Qua","quinta":"Qui","sexta":"Sex",
        "sabado":"Sáb","segunda":"Seg","terca":"Ter","domingo":"Dom",
    }
    import re
    hora_match = re.search(r"(\d{1,2})[\s]*[hH:][\s]*(\d{2})?", t)
    hora_str = None
    if hora_match:
        h = int(hora_match.group(1))
        m = int(hora_match.group(2) or 0)
        hora_str = f"{h:02d}:{m:02d}"

    data_match = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", texto)
    data_str = None
    if data_match:
        d = int(data_match.group(1))
        m = int(data_match.group(2))
        a = data_match.group(3) or str(datetime.now().year)
        data_str = f"{d:02d}/{m:02d}/{a}"

    dia_abrev = None
    for nome, abrev in DIAS_NORM.items():
        if nome in t:
            dia_abrev = abrev
            break

    for slot in slots:
        match_hora = hora_str and slot["hora_inicio"] == hora_str
        match_data = data_str and slot["data"] == data_str
        match_dia  = dia_abrev and slot["dia"] == dia_abrev
        if match_data and match_hora: return slot
        if match_dia  and match_hora: return slot
    return None


def responder_pergunta_horario(texto, slots, local_bot):
    import re
    t = normalizar(texto)
    DIAS_NORM = {
        "quarta": "Qua", "quinta": "Qui", "sexta": "Sex",
        "sabado": "Sáb", "segunda": "Seg", "terca": "Ter",
    }
    hora_match = re.search(r"(\d{1,2})[\s]*[hH:][\s]*(\d{2})?", t)
    hora_str = None
    if hora_match:
        h = int(hora_match.group(1))
        m = int(hora_match.group(2) or 0)
        hora_str = f"{h:02d}:{m:02d}"

    dia_abrev = None
    for nome_dia, abrev in DIAS_NORM.items():
        if nome_dia in t:
            dia_abrev = abrev
            break

    slots_encontrados = []
    for slot in slots:
        match_hora = hora_str and slot["hora_inicio"] == hora_str
        match_dia  = dia_abrev and slot["dia"] == dia_abrev
        if hora_str and dia_abrev:
            if match_hora and match_dia:
                slots_encontrados.append(slot)
        elif hora_str:
            if match_hora:
                slots_encontrados.append(slot)
        elif dia_abrev:
            if match_dia:
                slots_encontrados.append(slot)

    if slots_encontrados:
        if len(slots_encontrados) == 1:
            s = slots_encontrados[0]
            return (
                f"Sim! Tenho disponível *{s['dia']} ({s['data']}) às {s['hora_inicio']}*. "
                f"Deseja confirmar esse horário?"
            )
        else:
            opcoes = "\n".join([f"• {s['dia']} ({s['data']}) às {s['hora_inicio']}" for s in slots_encontrados])
            return f"Sim! Tenho os seguintes horários disponíveis:\n\n{opcoes}\n\nQual prefere?"
    else:
        if dia_abrev == "Sáb":
            from sheets_agenda import buscar_todos_slots_sabado
            slots_sab = buscar_todos_slots_sabado(local_bot)
            if slots_sab:
                primeira_data_sab = slots_sab[0]["data"]
                slots_prox_sab = [s for s in slots_sab if s["data"] == primeira_data_sab]
                horarios = "; ".join([s["hora_inicio"] for s in slots_prox_sab])
                return (
                    f"O próximo sábado disponível é *Sáb ({primeira_data_sab})*:\n\n"
                    f"{horarios}\n\nDeseja um desses horários?"
                )
            else:
                mensagem_horarios = formatar_horarios_para_mensagem(slots, local_bot)
                return f"Não tenho horários de sábado disponíveis no momento. 😕\n\n{mensagem_horarios}"
        else:
            mensagem_horarios = formatar_horarios_para_mensagem(slots, local_bot)
            return f"Infelizmente não tenho esse horário disponível. 😕\n\n{mensagem_horarios}"


# ─────────────────────────────────────────────
# PROCESSAMENTO PRINCIPAL
# ─────────────────────────────────────────────

def processar_mensagem(phone, nome, texto):
    phone = normalizar_phone(phone)
    texto_norm = normalizar(texto)
    logger.info(f"[{phone}] msg='{texto}'")

    registro = buscar_estado(phone)

    # ── NOVO CONTATO
    if registro is None:
        local_extraido   = None
        turnos_extraidos = []
        try:
            resultado_nlu  = extrair_local_e_turno(texto)
            local_extraido = resultado_nlu.get("local")
        except Exception:
            pass

        if local_extraido:
            try:
                dias       = extrair_dias_semana(texto)
                bloqueados = dias.get("bloqueados", [])
                validos    = dias.get("validos", [])
                if bloqueados and not validos:
                    aviso   = _montar_aviso_dia_bloqueado(bloqueados, local_extraido)
                    sucesso = criar_registro(
                        phone=phone, nome=nome,
                        etapa=ESTADO_AGUARDA_SUBMENU,
                        local=local_extraido, hora="",
                    )
                    if not sucesso:
                        logger.error(f"[{phone}] Falha ao criar registro")
                        enviar_mensagem(VICTOR_PHONE,
                            f"⚠️ *Erro ao registrar novo contato!*\n\n"
                            f"👤 *Nome:* {nome}\n"
                            f"📞 *Telefone:* {phone}\n\n"
                            f"_Falha ao gravar na planilha. Verificar manualmente._"
                        )
                        return
                    enviar_mensagem(phone, aviso)
                    return
            except Exception:
                pass
            try:
                turnos_extraidos = detectar_turnos(texto)
            except Exception:
                turnos_extraidos = []

            # Local identificado na primeira mensagem → vai direto para SUBMENU
            hora_buffer_local = (
                _json.dumps({"_turnos_pre": turnos_extraidos}, ensure_ascii=False)
                if turnos_extraidos else ""
            )
            sucesso = criar_registro(
                phone=phone, nome=nome,
                etapa=ESTADO_AGUARDA_SUBMENU,
                local=local_extraido, hora=hora_buffer_local,
            )
            if not sucesso:
                logger.error(f"[{phone}] Falha ao criar registro")
                enviar_mensagem(VICTOR_PHONE,
                    f"⚠️ *Erro ao registrar novo contato!*\n\n"
                    f"👤 *Nome:* {nome}\n"
                    f"📞 *Telefone:* {phone}\n\n"
                    f"_Falha ao gravar na planilha. Verificar manualmente._"
                )
                return
            enviar_mensagem(phone, msg.SUBMENU_CONSULTA)
            return

        hora_buffer = (
            _json.dumps({"_turnos_pre": turnos_extraidos}, ensure_ascii=False)
            if turnos_extraidos else ""
        )

        # Pergunta de valor como primeira mensagem
        if not local_extraido and detectar_pergunta_valor(texto):
            logger.info(f"[{phone}] Pergunta de valor na primeira mensagem — INFO_PRIMEIRA_CONSULTA")
            sucesso = criar_registro(
                phone=phone, nome=nome,
                etapa=ESTADO_AGUARDA_LOCAL, local="", hora=hora_buffer,
            )
            if not sucesso:
                logger.error(f"[{phone}] Falha ao criar registro")
                enviar_mensagem(VICTOR_PHONE,
                    f"⚠️ *Erro ao registrar novo contato!*\n\n"
                    f"👤 *Nome:* {nome}\n"
                    f"📞 *Telefone:* {phone}\n\n"
                    f"_Falha ao gravar na planilha. Verificar manualmente._"
                )
                return
            enviar_mensagem(phone, msg.INFO_PRIMEIRA_CONSULTA)
            return

        # Intencao de agendar sem local
        if not local_extraido and detectar_intencao_agendamento(texto):
            logger.info(f"[{phone}] Intencao de agendamento — AGUARDA_LOCAL")
            sucesso = criar_registro(
                phone=phone, nome=nome,
                etapa=ESTADO_AGUARDA_LOCAL, local="", hora=hora_buffer,
            )
            if not sucesso:
                logger.error(f"[{phone}] Falha ao criar registro")
                enviar_mensagem(VICTOR_PHONE,
                    f"⚠️ *Erro ao registrar novo contato!*\n\n"
                    f"👤 *Nome:* {nome}\n"
                    f"📞 *Telefone:* {phone}\n\n"
                    f"_Falha ao gravar na planilha. Verificar manualmente._"
                )
                return
            enviar_mensagem(phone, msg.MENU_PRINCIPAL)
            return

        # Interesse em saber mais
        if not local_extraido and detectar_intencao_info_consulta(texto):
            logger.info(f"[{phone}] Interesse em info — INFO_PRIMEIRA_CONSULTA")
            sucesso = criar_registro(
                phone=phone, nome=nome,
                etapa=ESTADO_AGUARDA_LOCAL, local="", hora=hora_buffer,
            )
            if not sucesso:
                logger.error(f"[{phone}] Falha ao criar registro")
                enviar_mensagem(VICTOR_PHONE,
                    f"⚠️ *Erro ao registrar novo contato!*\n\n"
                    f"👤 *Nome:* {nome}\n"
                    f"📞 *Telefone:* {phone}\n\n"
                    f"_Falha ao gravar na planilha. Verificar manualmente._"
                )
                return
            enviar_mensagem(phone, msg.INFO_PRIMEIRA_CONSULTA)
            return

        # Fluxo padrao — saudacoes e mensagens nao identificadas
        # Vai para MENU_PRINCIPAL (opcao 1/2/3) e nao direto para o submenu
        sucesso = criar_registro(
            phone=phone, nome=nome,
            etapa=ESTADO_AGUARDA_OPCAO,
            local=local_extraido or "", hora=hora_buffer,
        )
        if not sucesso:
            logger.error(f"[{phone}] Falha ao criar registro")
            enviar_mensagem(VICTOR_PHONE,
                f"⚠️ *Erro ao registrar novo contato!*\n\n"
                f"👤 *Nome:* {nome}\n"
                f"📞 *Telefone:* {phone}\n\n"
                f"_Falha ao gravar na planilha. Verificar manualmente._"
            )
            return
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
        return

    etapa      = registro.get("etapa", ESTADO_AGUARDA_OPCAO)
    local      = registro.get("local", "")
    row        = registro.get("row_number")
    nome_salvo = registro.get("nome", nome) or nome

    logger.info(f"[{phone}] etapa={etapa} local={local}")

    # ── INTERCEPTACAO GLOBAL: familiar
    if (etapa not in (ESTADO_ATENDIMENTO_HUMANO, ESTADO_AGUARDA_NOME_FAMILIAR)
            and detectar_intencao_familiar(texto)):

        data_confirmada = registro.get("data", "")
        local_familiar  = local
        hora_confirmada = _recuperar_hora_confirmada(registro)

        if data_confirmada and local_familiar and hora_confirmada:
            slots_seguidos = buscar_slots_seguidos(local_familiar, data_confirmada, hora_confirmada)

            if slots_seguidos:
                buffer_familiar = _json.dumps({
                    "_familiar_slots": slots_seguidos,
                    "_familiar_data":  data_confirmada,
                    "_familiar_local": local_familiar,
                }, ensure_ascii=False)
                atualizar_estado(row, etapa=ESTADO_AGUARDA_NOME_FAMILIAR, hora=buffer_familiar)

                slot_s     = slots_seguidos[0]
                nome_dia_f = NOMES_DIAS.get(slot_s["dia"], slot_s["dia"])
                horas_str  = " / ".join(s["hora_inicio"] for s in slots_seguidos)

                enviar_mensagem(phone,
                    f"😊 Ótimo! Encontrei o seguinte horário disponível em sequência:\n\n"
                    f"📅 *{nome_dia_f} ({data_confirmada})*\n"
                    f"⏰ *{horas_str}*\n"
                    f"📍 *{local_familiar}*\n\n"
                    f"Qual é o nome completo do familiar?"
                )
            else:
                atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
                enviar_mensagem(phone,
                    f"Infelizmente não há horários disponíveis em sequência nesse dia. 😕\n\n"
                    f"O *Nutri Victor* entrará em contato para verificar outras opções!"
                )
                enviar_mensagem(VICTOR_PHONE,
                    f"👥 *Paciente quer agendar para familiar*\n\n"
                    f"👤 *Nome:* {nome_salvo}\n"
                    f"📞 *Telefone:* {phone}\n"
                    f"📍 *Local:* {local_familiar}\n"
                    f"📅 *Data solicitada:* {data_confirmada}\n\n"
                    f"_Sem horário seguido disponível — verificar manualmente._"
                )
        else:
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
            enviar_mensagem(phone,
                f"Para agendar para um familiar, primeiro precisamos confirmar o seu horário. 😊\n\n"
                f"O *Nutri Victor* entrará em contato para ajudar!"
            )
            enviar_mensagem(VICTOR_PHONE,
                f"👥 *Interesse em agendar para familiar (sem data confirmada)*\n\n"
                f"👤 *Nome:* {nome_salvo}\n"
                f"📞 *Telefone:* {phone}\n\n"
                f"_Lead não tem agendamento confirmado ainda._"
            )
        return

    # ── INTERCEPTACAO GLOBAL: pergunta de valor
    # Salva etapa atual em buffer, responde valor, muda para AGUARDA_CONFIRMACAO_VALOR.
    # Ao confirmar, restaura a etapa anterior e retoma o fluxo de onde parou.
    if (etapa not in _ESTADOS_SEM_INTERCEPTACAO_VALOR
            and detectar_pergunta_valor(texto)):

        # Se estiver em AGUARDA_SUBMENU, tenta extrair opcao do submenu da mesma mensagem
        # Ex: "retorno. quanto custa mesmo?" → opcao_submenu = "2"
        opcao_submenu_salva = None
        if etapa == ESTADO_AGUARDA_SUBMENU:
            opcao_submenu_salva = detectar_opcao_submenu(texto_norm)

        buffer_valor = _json.dumps({
            "_etapa_anterior": etapa,
            "_local_anterior": local,
            "_opcao_submenu": opcao_submenu_salva,
        }, ensure_ascii=False)
        atualizar_estado(row, etapa=ESTADO_AGUARDA_CONFIRMACAO_VALOR, hora=buffer_valor)

        enviar_mensagem(phone,
            "O valor do investimento é R$ 300,00 para o acompanhamento com o "
            "Nutri Victor por três meses. Podemos seguir com o agendamento?"
        )
        return

    # Atalho: endereco
    if detectar_endereco(texto_norm) and local:
        if local == "Copacabana":
            enviar_mensagem(phone, msg.ENDERECO_COPA)
        elif local == "Méier":
            enviar_mensagem(phone, msg.ENDERECO_MEIER)
        return

    # ── MENU PRINCIPAL
    if etapa == ESTADO_AGUARDA_OPCAO:
        opcao = detectar_opcao_menu(texto_norm, texto)
        if opcao == "1":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_SUBMENU)
            enviar_mensagem(phone, msg.SUBMENU_CONSULTA)
        elif opcao == "2":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO)
            enviar_mensagem(phone, msg.MARINADAS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_marinadas(nome_salvo, phone))
        elif opcao == "3":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_DESCRICAO)
            enviar_mensagem(phone, msg.PEDIR_DESCRICAO)
        else:
            # Nao reconheceu opcao — repete o menu (nao encaminha para humano)
            # Ex: saudacoes como "bom dia", "oi" chegam aqui quando ja ha registro
            enviar_mensagem(phone, msg.MENU_PRINCIPAL)

    # ── SUBMENU
    elif etapa == ESTADO_AGUARDA_SUBMENU:
        opcao = detectar_opcao_submenu(texto_norm)
        if opcao == "3":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_DESCRICAO)
            enviar_mensagem(phone, msg.PEDIR_DESCRICAO)
            return
        if opcao not in ("1", "2"):
            encaminhar_para_humano(phone, row, nome_salvo, texto)
            return
        turnos_pre = _recuperar_turnos_pre(registro)
        if opcao == "1":
            if local:
                enviar_mensagem(phone, msg.INFO_PRIMEIRA_CONSULTA)
                _enviar_slots_apos_submenu(phone, row, nome_salvo, local, turnos_pre)
            else:
                atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL)
                enviar_mensagem(phone, msg.INFO_PRIMEIRA_CONSULTA)
        elif opcao == "2":
            if local:
                _enviar_slots_apos_submenu(phone, row, nome_salvo, local, turnos_pre)
            else:
                atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL)
                enviar_mensagem(phone, msg.PERGUNTA_LOCAL)

    # ── LOCAL
    elif etapa == ESTADO_AGUARDA_LOCAL:
        if detectar_endereco(texto_norm):
            enviar_mensagem(phone, msg.ENDERECO_COPA)
            enviar_mensagem(phone, msg.ENDERECO_MEIER)
            enviar_mensagem(phone, msg.PERGUNTA_LOCAL)
            return
        local_detectado = detectar_local(texto)
        if local_detectado:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO, local=local_detectado)
            enviar_mensagem(phone, msg.PERGUNTA_TURNO)
        else:
            encaminhar_para_humano(phone, row, nome_salvo, texto)

    # ── TURNO
    elif etapa == ESTADO_AGUARDA_TURNO:
        if _verificar_dias_e_avisar(phone, texto, local):
            return
        turnos_detectados = detectar_turnos(texto)
        if not turnos_detectados:
            encaminhar_para_humano(phone, row, nome_salvo, texto)
            return
        slots = buscar_slots_por_turnos(local, turnos_detectados)
        if not slots:
            turno_label = " / ".join(turnos_detectados)
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO, hora=turno_label)
            enviar_mensagem(phone, msg.SEM_HORARIOS_DISPONIVEIS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_triagem(nome_salvo, phone, local, turno_label))
            return
        atualizar_estado(row, etapa=ESTADO_AGUARDA_HORARIO,
                         hora=_json.dumps(slots, ensure_ascii=False))
        enviar_mensagem(phone, formatar_horarios_para_mensagem(slots, local))

    # ── ESCOLHA DO HORARIO
    elif etapa == ESTADO_AGUARDA_HORARIO:
        if detectar_dia_bloqueado(texto):
            enviar_mensagem(phone, msg.ERRO_DIA_BLOQUEADO)
            return
        if detectar_depois_confirmo(texto):
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
            enviar_mensagem(phone, msg.AGUARDA_CONFIRMACAO_DEPOIS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_decide_depois(nome_salvo, phone, local))
            return
        try:
            slots = _json.loads(registro.get("hora", "[]"))
            if isinstance(slots, dict):
                slots = []
        except Exception:
            slots = []
        if not slots:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO)
            enviar_mensagem(phone, msg.ERRO_SLOTS_EXPIRADOS)
            return
        slot_escolhido = identificar_slot_escolhido(texto, slots)
        if slot_escolhido == "PERGUNTA":
            resposta = responder_pergunta_horario(texto, slots, local)
            enviar_mensagem(phone, resposta)
            return
        if not slot_escolhido:
            encaminhar_para_humano(phone, row, nome_salvo, texto)
            return
        atualizar_estado(
            row,
            etapa=ESTADO_AGUARDA_CONFIRMACAO,
            data=slot_escolhido["data"],
            hora=_json.dumps(slot_escolhido, ensure_ascii=False),
        )
        enviar_mensagem(phone, msg.confirmacao_agendamento(
            nome=nome_salvo, local=local,
            data=slot_escolhido["data"], dia=slot_escolhido["dia"],
            hora=slot_escolhido["hora_inicio"],
        ))

    # ── CONFIRMACAO
    elif etapa == ESTADO_AGUARDA_CONFIRMACAO:
        confirmado = detectar_confirmacao(texto)
        if confirmado is None:
            encaminhar_para_humano(phone, row, nome_salvo, texto)
            return
        try:
            slot = _json.loads(registro.get("hora", "{}"))
            if isinstance(slot, list):
                slot = {}
        except Exception:
            slot = {}
        if not slot:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO)
            enviar_mensagem(phone, msg.ERRO_SLOTS_EXPIRADOS)
            return
        if confirmado:
            remover_horario_confirmado(
                local_bot=local,
                data_confirmada=slot["data"],
                hora_confirmada=slot["hora_inicio"],
                duracao_min=DURACAO_CONSULTA.get(local, 90),
            )
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             data=slot["data"], hora=slot["hora_inicio"])
            enviar_mensagem(phone, msg.confirmacao_final(
                nome=nome_salvo, data=slot["data"], dia=slot["dia"],
                hora=slot["hora_inicio"], endereco=msg.endereco_para_local(local),
            ))
            enviar_mensagem(phone, msg.FORMULARIO_PRE_CONSULTA)
            enviar_mensagem(phone, msg.ORIENTACOES_BIO_TEXTO)
            enviar_imagem(phone, msg.ORIENTACOES_BIO_IMAGEM)
            enviar_mensagem(VICTOR_PHONE, msg.notif_consulta_marcada(
                nome=nome_salvo, phone=phone, local=local,
                data=slot["data"], hora=slot["hora_inicio"],
            ))
        else:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO)
            enviar_mensagem(phone, msg.REAGENDAMENTO)
            enviar_mensagem(phone, msg.PERGUNTA_TURNO)

    # ── NOME DO FAMILIAR
    elif etapa == ESTADO_AGUARDA_NOME_FAMILIAR:
        nome_familiar = texto.strip()
        if not nome_familiar or len(nome_familiar) < 2:
            enviar_mensagem(phone, "Por favor, me informe o nome completo do familiar. 😊")
            return
        try:
            buffer         = _json.loads(registro.get("hora", "{}"))
            slots_seguidos = buffer.get("_familiar_slots", [])
            data_familiar  = buffer.get("_familiar_data", "")
            local_familiar = buffer.get("_familiar_local", local)
        except Exception:
            slots_seguidos, data_familiar, local_familiar = [], "", local
        if not slots_seguidos or not data_familiar:
            encaminhar_para_humano(phone, row, nome_salvo, texto)
            return
        slot_f      = slots_seguidos[0]
        nome_dia_nf = NOMES_DIAS.get(slot_f["dia"], slot_f["dia"])
        remover_horario_confirmado(
            local_bot=local_familiar,
            data_confirmada=data_familiar,
            hora_confirmada=slot_f["hora_inicio"],
            duracao_min=DURACAO_CONSULTA.get(local_familiar, 90),
        )
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                         data=data_familiar, hora=slot_f["hora_inicio"])
        enviar_mensagem(phone,
            f"🎉 Perfeito! Consulta de *{nome_familiar}* confirmada:\n\n"
            f"📅 *{nome_dia_nf}, {data_familiar}*\n"
            f"⏰ *{slot_f['hora_inicio']}*\n"
            f"📍 *{local_familiar}*\n\n"
            f"{msg.endereco_para_local(local_familiar)}\n\n"
            f"Qualquer dúvida, é só chamar! 😊"
        )
        enviar_mensagem(VICTOR_PHONE,
            f"📌 *Consulta de familiar confirmada!*\n\n"
            f"👤 *Familiar:* {nome_familiar}\n"
            f"📞 *Telefone do responsável:* {phone} ({nome_salvo})\n"
            f"📍 *Local:* {local_familiar}\n"
            f"📅 *Data:* {data_familiar}\n"
            f"⏰ *Horário:* {slot_f['hora_inicio']}"
        )

    # ── CONFIRMACAO DE VALOR
    elif etapa == ESTADO_AGUARDA_CONFIRMACAO_VALOR:
        confirmado = detectar_confirmacao(texto)

        # Recupera contexto salvo
        try:
            buffer_v       = _json.loads(registro.get("hora", "{}"))
            etapa_anterior = buffer_v.get("_etapa_anterior", ESTADO_AGUARDA_LOCAL)
            local_anterior = buffer_v.get("_local_anterior", local) or local
        except Exception:
            etapa_anterior = ESTADO_AGUARDA_LOCAL
            local_anterior = local

        if confirmado is True:
            # Recupera opcao_submenu salva (se existir)
            opcao_sub = buffer_v.get("_opcao_submenu")

            # Caso especial: paciente estava em AGUARDA_SUBMENU, já tinha respondido
            # a opcao do submenu na mesma mensagem que perguntou o valor, e já tem local.
            # Ex: "retorno. quanto custa?" → ao confirmar, pula submenu e vai para turno.
            if (etapa_anterior == ESTADO_AGUARDA_SUBMENU
                    and opcao_sub in ("1", "2")
                    and local_anterior):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO, local=local_anterior, hora="")
                enviar_mensagem(phone, msg.PERGUNTA_TURNO)
            else:
                # Restaura estado anterior e manda mensagem correta
                atualizar_estado(row, etapa=etapa_anterior, local=local_anterior, hora="")
                msg_retomada = _mensagem_retomada_fluxo(etapa_anterior, local_anterior)
                if msg_retomada:
                    enviar_mensagem(phone, msg_retomada)
                else:
                    # Estado sem mensagem de retomada simples (ex: AGUARDA_HORARIO)
                    enviar_mensagem(phone,
                        "Ótimo! Pode continuar de onde estávamos. 😊"
                    )
        elif confirmado is False:
            encaminhar_para_humano(phone, row, nome_salvo, texto)
        else:
            # Nao entendeu — repete a pergunta
            enviar_mensagem(phone,
                "Desculpe, não entendi. Vamos seguir com o agendamento? "
                "Responda *SIM* para continuar ou *NÃO* para encerrar."
            )

    # ── DESCRICAO LIVRE
    elif etapa == ESTADO_AGUARDA_DESCRICAO:
        from claude_nlu import processar_mensagem_livre
        resposta_claude = processar_mensagem_livre(texto)
        enviar_mensagem(phone, resposta_claude)
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        enviar_mensagem(VICTOR_PHONE, msg.notif_outro(nome_salvo, phone, texto))

    # ── MARINADAS
    elif etapa == ESTADO_AGUARDA_MARINADAS:
        logger.info(f"[{phone}] AGUARDA_MARINADAS — ignorando")
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        return

    # ── ATENDIMENTO HUMANO
    elif etapa == ESTADO_ATENDIMENTO_HUMANO:
        logger.info(f"[{phone}] ATENDIMENTO_HUMANO — bot silencioso")
        return

    # ── ESTADO DESCONHECIDO
    else:
        logger.warning(f"[{phone}] Estado desconhecido '{etapa}' — reiniciando")
        atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
