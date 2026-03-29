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
    extrair_horario_escolhido,
)
import mensagens as msg
from mensagens import erro_nao_entendi

logger = logging.getLogger(__name__)


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


def detectar_opcao_menu(t, texto_original=""):
    # Tenta com Claude primeiro
    try:
        opcao = extrair_opcao_menu(texto_original or t)
        if opcao:
            return opcao
    except Exception:
        pass
    # Fallback: regex
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
    # Tenta com Claude primeiro
    try:
        local = extrair_local(texto)
        if local:
            return local
    except Exception:
        pass
    # Fallback: regex
    t = normalizar(texto)
    if any(x in t for x in ["copa","copacabana","em copa"]):
        return "Copacabana"
    if any(x in t for x in ["meier","meir","mier","max","maxfit","academia","na max","na academia"]):
        return "Méier"
    if any(x in t for x in ["online","remoto","virtual","meet"]):
        return "Online"
    return None


def detectar_turno(texto):
    # Tenta com Claude primeiro
    try:
        turno = extrair_turno(texto)
        if turno:
            return turno
    except Exception:
        pass
    # Fallback: regex
    t = normalizar(texto)
    if any(x in t for x in ["manha", "de manha", "pela manha", "cedo", "matutino"]):
        return "Manhã"
    if any(x in t for x in ["tarde", "de tarde", "pela tarde"]):
        return "Tarde"
    if any(x in t for x in ["noite", "de noite", "pela noite"]):
        return "Noite"
    return None


def detectar_confirmacao(texto):
    t = normalizar(texto)
    if any(x in t for x in ["sim","confirmo","confirmar","isso","correto","certo","ok"]):
        return True
    if any(x in t for x in ["nao","não","errado","incorreto","cancelar"]):
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
    """Retorna True se o lead mencionou um dia em que Victor não atende."""
    t = normalizar(texto)
    return any(x in t for x in ["segunda","seg","terca","ter","domingo","dom"])


def detectar_endereco(texto):
    t = normalizar(texto)
    return any(x in t for x in [
        "endereco","endereço","onde fica","localizacao",
        "como chegar","onde e","onde é","maps"
    ])


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


def identificar_slot_escolhido(texto, slots):
    # Remove formatação WhatsApp (*negrito*, _itálico_)
    import re as _re
    texto = _re.sub(r"[*_~]", "", texto).strip()

    # Tenta com Claude primeiro
    try:
        slot = extrair_horario_escolhido(texto, slots)
        if slot == "PERGUNTA":
            return "PERGUNTA"
        if slot:
            return slot
    except Exception:
        pass
    # Fallback: regex
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
    """
    Quando o lead faz uma pergunta sobre horários (ex: "tem às 13h?", "tem sábado?"),
    verifica na lista e responde de forma inteligente.
    """
    import re
    t = normalizar(texto)

    DIAS_NORM = {
        "quarta": "Qua", "quinta": "Qui", "sexta": "Sex",
        "sabado": "Sáb", "segunda": "Seg", "terca": "Ter",
    }

    # Extrai hora da pergunta
    hora_match = re.search(r"(\d{1,2})[\s]*[hH:][\s]*(\d{2})?", t)
    hora_str = None
    if hora_match:
        h = int(hora_match.group(1))
        m = int(hora_match.group(2) or 0)
        hora_str = f"{h:02d}:{m:02d}"

    # Extrai dia da pergunta
    dia_abrev = None
    for nome_dia, abrev in DIAS_NORM.items():
        if nome_dia in t:
            dia_abrev = abrev
            break

    # Filtra slots que batem com a pergunta
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
        # Não tem o horário pedido — verifica se perguntou sobre sábado
        if dia_abrev == "Sáb":
            # Busca o sábado mais próximo em TODOS os slots disponíveis na planilha
            from sheets_agenda import buscar_todos_slots_sabado
            slots_sab = buscar_todos_slots_sabado(local_bot)
            if slots_sab:
                # Pega o sábado mais próximo (primeiro da lista ordenada)
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
            # Não tem o horário pedido — mostra os disponíveis
            mensagem_horarios = formatar_horarios_para_mensagem(slots, local_bot)
            return f"Infelizmente não tenho esse horário disponível. 😕\n\n{mensagem_horarios}"


def processar_mensagem(phone, nome, texto):
    phone = normalizar_phone(phone)
    texto_norm = normalizar(texto)
    logger.info(f"[{phone}] msg='{texto}'")

    registro = buscar_estado(phone)

    if registro is None:
        criar_registro(phone=phone, nome=nome, etapa=ESTADO_AGUARDA_OPCAO)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
        return

    etapa      = registro.get("etapa", ESTADO_AGUARDA_OPCAO)
    local      = registro.get("local", "")
    row        = registro.get("row_number")
    nome_salvo = registro.get("nome", nome) or nome

    logger.info(f"[{phone}] etapa={etapa}")

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
            atualizar_estado(row, etapa=ESTADO_AGUARDA_MARINADAS)
            enviar_mensagem(phone, msg.MARINADAS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_marinadas(nome_salvo, phone))
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        elif opcao == "3":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_DESCRICAO)
            enviar_mensagem(phone, msg.PEDIR_DESCRICAO)
        else:
            enviar_mensagem(phone, erro_nao_entendi(etapa))

    # ── SUBMENU ───────────────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_SUBMENU:
        opcao = detectar_opcao_submenu(texto_norm)
        if opcao == "1":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL)
            enviar_mensagem(phone, msg.INFO_PRIMEIRA_CONSULTA)
        elif opcao == "2":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL)
            enviar_mensagem(phone, msg.PERGUNTA_LOCAL)
        elif opcao == "3":
            atualizar_estado(row, etapa=ESTADO_AGUARDA_DESCRICAO)
            enviar_mensagem(phone, msg.PEDIR_DESCRICAO)
        else:
            enviar_mensagem(phone, erro_nao_entendi(etapa))

    # ── LOCAL ─────────────────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_LOCAL:
        # Se perguntou endereço antes de escolher local → mostra os dois
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
            enviar_mensagem(phone, erro_nao_entendi(etapa))

    # ── TURNO ─────────────────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_TURNO:
        turno = detectar_turno(texto)
        if not turno:
            enviar_mensagem(phone, erro_nao_entendi(etapa))
            return

        slots = buscar_horarios(local, turno)

        if not slots:
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO, hora=turno)
            enviar_mensagem(phone, msg.SEM_HORARIOS_DISPONIVEIS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_triagem(nome_salvo, phone, local, turno))
            return

        import json as _json
        atualizar_estado(row, etapa=ESTADO_AGUARDA_HORARIO, hora=_json.dumps(slots, ensure_ascii=False))
        enviar_mensagem(phone, formatar_horarios_para_mensagem(slots, local))

    # ── ESCOLHA DO HORÁRIO ────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_HORARIO:
        import json as _json

        # Lead mencionou dia bloqueado
        if detectar_dia_bloqueado(texto):
            enviar_mensagem(phone, msg.ERRO_DIA_BLOQUEADO)
            return

        # Lead quer decidir depois
        if detectar_depois_confirmo(texto):
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
            enviar_mensagem(phone, msg.AGUARDA_CONFIRMACAO_DEPOIS)
            enviar_mensagem(VICTOR_PHONE, msg.notif_decide_depois(nome_salvo, phone, local))
            return

        try:
            slots = _json.loads(registro.get("hora", "[]"))
        except Exception:
            slots = []

        if not slots:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO)
            enviar_mensagem(phone, msg.ERRO_SLOTS_EXPIRADOS)
            return

        slot_escolhido = identificar_slot_escolhido(texto, slots)

        if slot_escolhido == "PERGUNTA":
            # Lead fez uma pergunta (ex: "tem às 13h?", "tem sábado?")
            # Verifica se o horário perguntado existe na lista
            resposta = responder_pergunta_horario(texto, slots, local)
            enviar_mensagem(phone, resposta)
            return

        if not slot_escolhido:
            enviar_mensagem(phone, erro_nao_entendi(etapa))
            enviar_mensagem(phone, formatar_horarios_para_mensagem(slots, local))
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
        import json as _json
        confirmado = detectar_confirmacao(texto)

        if confirmado is None:
            enviar_mensagem(phone, erro_nao_entendi(etapa))
            return

        try:
            slot = _json.loads(registro.get("hora", "{}"))
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
        # Lead enviou a explicação do "outro assunto" → encaminha ao Victor
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        enviar_mensagem(phone, msg.CONFIRMACAO_RECEBIMENTO)
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
