import json as _json
import logging
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

# Nomes completos dos dias para uso nas mensagens
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
    import unicodedata
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def encaminhar_para_humano(phone, row, nome, texto):
    """Quando o bot não entende — encaminha para atendimento humano e notifica Victor."""
    atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
    enviar_mensagem(phone, msg.ENCAMINHAR_HUMANO)
    enviar_mensagem(VICTOR_PHONE, msg.notif_nao_entendeu(nome, phone, texto))


# ─────────────────────────────────────────────
# AVISO DE DIA BLOQUEADO
# ─────────────────────────────────────────────

def _montar_aviso_dia_bloqueado(bloqueados: list[str], local: str) -> str:
    """
    Monta mensagem avisando que o(s) dia(s) informado(s) não têm atendimento.
    Todos os locais atendem de Quarta a Sábado.
    """
    dias_bloq = ", ".join(NOMES_DIAS.get(d, d) for d in bloqueados)

    return (
        f"Infelizmente o Nutri Victor não atende às {dias_bloq}. 😕\n\n"
        f"O atendimento acontece de *Quarta a Sábado*.\n\n"
        f"Você consegue em algum desses dias? 😊"
    )


def _verificar_dias_e_avisar(phone, texto, local) -> bool:
    """
    Verifica se a mensagem menciona dias bloqueados.

    Regras:
    - Só dias bloqueados → envia aviso e retorna True (interrompe o fluxo)
    - Mix de válidos + bloqueados → ignora bloqueados silenciosamente, retorna False
    - Sem dias mencionados → retorna False

    Retorna True se o fluxo deve ser interrompido (aviso enviado).
    """
    try:
        dias = extrair_dias_semana(texto)
    except Exception:
        return False

    bloqueados = dias.get("bloqueados", [])
    validos    = dias.get("validos", [])

    # Só bloqueados, sem nenhum válido → avisa
    if bloqueados and not validos:
        aviso = _montar_aviso_dia_bloqueado(bloqueados, local or "nosso consultório")
        enviar_mensagem(phone, aviso)
        return True

    # Mix ou sem dias → segue normalmente
    return False


# ─────────────────────────────────────────────
# DETECÇÃO DE INTENÇÕES
# ─────────────────────────────────────────────

def detectar_opcao_menu(t, texto_original=""):
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
    if any(x in t for x in ["primeira","novo","nunca fui","primeira vez"]): return "1"
    if t in ["2", "2️⃣"] or t.startswith("2"): return "2"
    if any(x in t for x in ["retorno","voltar","ja fui","segunda"]): return "2"
    if t in ["3", "3️⃣"] or t.startswith("3"): return "3"
    if any(x in t for x in ["outro","outros","informacao","duvida"]): return "3"
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


def detectar_turnos(texto: str) -> list[str]:
    """Retorna LISTA de turnos mencionados (suporta múltiplos)."""
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
        "beleza", "otimo", "ta bom", "valeu", "vai nessa", "marca ai"
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

def buscar_slots_por_turnos(local: str, turnos: list[str]) -> list[dict]:
    """Busca slots de múltiplos turnos, mescla sem duplicatas e ordena cronologicamente."""
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


def _recuperar_turnos_pre(registro: dict) -> list[str]:
    """Lê o buffer de turnos pré-extraídos do campo 'hora'."""
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


def _enviar_slots_apos_submenu(phone, row, nome_salvo, local, turnos_pre):
    """
    Após definir tipo de consulta, envia slots (se há turnos salvos) ou pergunta turno.
    Limpa o buffer de turnos antes de agir.
    """
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
# HELPERS DE HORÁRIO
# ─────────────────────────────────────────────

def identificar_slot_escolhido(texto, slots):
    import re as _re
    texto = _re.sub(r"[*_~]", "", texto).strip()
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

    # ── NOVO CONTATO ──────────────────────────────────────────────────────────
    if registro is None:
        # Tenta extrair local e turnos da primeira mensagem
        local_extraido = None
        turnos_extraidos = []
        try:
            resultado_nlu = extrair_local_e_turno(texto)
            local_extraido = resultado_nlu.get("local")
        except Exception:
            pass

        if local_extraido:
            # Verifica dias bloqueados na primeira mensagem
            # Se mencionar só dias bloqueados → avisa imediatamente, sem criar registro ainda
            try:
                dias = extrair_dias_semana(texto)
                bloqueados = dias.get("bloqueados", [])
                validos    = dias.get("validos", [])
                if bloqueados and not validos:
                    aviso = _montar_aviso_dia_bloqueado(bloqueados, local_extraido)
                    # Cria registro em AGUARDA_SUBMENU mesmo assim para manter contexto
                    criar_registro(
                        phone=phone,
                        nome=nome,
                        etapa=ESTADO_AGUARDA_SUBMENU,
                        local=local_extraido,
                        hora="",
                    )
                    enviar_mensagem(phone, aviso)
                    return
            except Exception:
                pass

            try:
                turnos_extraidos = detectar_turnos(texto)
            except Exception:
                turnos_extraidos = []

        hora_buffer = (
            _json.dumps({"_turnos_pre": turnos_extraidos}, ensure_ascii=False)
            if turnos_extraidos else ""
        )

        criar_registro(
            phone=phone,
            nome=nome,
            etapa=ESTADO_AGUARDA_SUBMENU,
            local=local_extraido or "",
            hora=hora_buffer,
        )
        enviar_mensagem(phone, msg.SUBMENU_CONSULTA)
        return

    etapa      = registro.get("etapa", ESTADO_AGUARDA_OPCAO)
    local      = registro.get("local", "")
    row        = registro.get("row_number")
    nome_salvo = registro.get("nome", nome) or nome

    logger.info(f"[{phone}] etapa={etapa} local={local}")

    # Atalho: endereço
    if detectar_endereco(texto_norm) and local:
        if local == "Copacabana":
            enviar_mensagem(phone, msg.ENDERECO_COPA)
        elif local == "Méier":
            enviar_mensagem(phone, msg.ENDERECO_MEIER)
        return

    # ── MENU PRINCIPAL ────────────────────────────────────────────────────────
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
            encaminhar_para_humano(phone, row, nome_salvo, texto)

    # ── SUBMENU ───────────────────────────────────────────────────────────────
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

    # ── LOCAL ─────────────────────────────────────────────────────────────────
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

    # ── TURNO ─────────────────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_TURNO:
        # Verifica dias bloqueados antes de processar turnos
        # Se mencionar só dias bloqueados → avisa e aguarda nova resposta no mesmo estado
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

    # ── ESCOLHA DO HORÁRIO ────────────────────────────────────────────────────
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

    # ── CONFIRMAÇÃO ───────────────────────────────────────────────────────────
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

    # ── DESCRIÇÃO LIVRE ───────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_DESCRICAO:
        from claude_nlu import processar_mensagem_livre
        resposta_claude = processar_mensagem_livre(texto)
        enviar_mensagem(phone, resposta_claude)
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        enviar_mensagem(VICTOR_PHONE, msg.notif_outro(nome_salvo, phone, texto))

    # ── MARINADAS ─────────────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_MARINADAS:
        logger.info(f"[{phone}] AGUARDA_MARINADAS — ignorando")
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        return

    # ── ATENDIMENTO HUMANO ────────────────────────────────────────────────────
    elif etapa == ESTADO_ATENDIMENTO_HUMANO:
        logger.info(f"[{phone}] ATENDIMENTO_HUMANO — bot silencioso")
        return

    # ── ESTADO DESCONHECIDO ───────────────────────────────────────────────────
    else:
        logger.warning(f"[{phone}] Estado desconhecido '{etapa}' — reiniciando")
        atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
