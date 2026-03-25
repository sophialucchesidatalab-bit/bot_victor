"""
bot.py — Máquina de estados do bot Victor Afonso Nutricionista

FLUXO SIMPLIFICADO:
    O bot coleta local e turno de preferência,
    avisa o paciente que a atendente entrará em contato
    e envia resumo completo para Victor.
    Todo o restante (horário, confirmação, calendário) é feito pelo humano.

REGRA ANTI-REPETIÇÃO:
    Cada etapa grava um ID de bloco em "ultima_msg" na planilha.
    Se ultima_msg == bloco_desta_etapa, a mensagem já foi enviada → ignora.
"""
import logging
from config import (
    VICTOR_PHONE,
    ESTADO_AGUARDA_OPCAO, ESTADO_AGUARDA_SUBMENU,
    ESTADO_AGUARDA_LOCAL, ESTADO_AGUARDA_TURNO,
    ESTADO_AGUARDA_DESCRICAO, ESTADO_AGUARDA_MARINADAS,
    ESTADO_ATENDIMENTO_HUMANO,
)
from sheets import buscar_estado, criar_registro, atualizar_estado
from zapi import enviar_mensagem
from claude_ai import processar_mensagem_livre
import mensagens as msg

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    import unicodedata
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def detectar_local(texto: str) -> str | None:
    t = normalizar(texto)
    if any(x in t for x in ["copa", "copacabana"]):
        return "Copacabana"
    if any(x in t for x in ["meier", "meir", "mier"]):
        return "Méier"
    if any(x in t for x in ["online", "remoto", "virtual", "meet"]):
        return "Online"
    return None


def detectar_turno(texto: str) -> str | None:
    t = normalizar(texto)
    if "manha" in t:
        return "manhã"
    if "tarde" in t:
        return "tarde"
    if "noite" in t:
        return "noite"
    return None


def detectar_endereco(texto: str) -> bool:
    t = normalizar(texto)
    return any(x in t for x in [
        "endereco", "endereço", "onde fica", "localizacao",
        "como chegar", "onde e", "onde é", "maps"
    ])


def ja_enviou(registro: dict, bloco: str) -> bool:
    """Retorna True se esse bloco já foi enviado — evita reenvio."""
    return registro.get("ultima_msg", "") == bloco


# ─────────────────────────────────────────────────────────
# PROCESSADOR PRINCIPAL
# ─────────────────────────────────────────────────────────

def processar_mensagem(phone: str, nome: str, texto: str):
    texto_norm = normalizar(texto)
    logger.info(f"[{phone}] msg='{texto}'")

    registro = buscar_estado(phone)

    # ── PACIENTE NOVO ──────────────────────────────────────
    if registro is None:
        criar_registro(phone, nome, ESTADO_AGUARDA_OPCAO,
                       ultima_msg=msg.BLOCO_MENU)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
        return

    etapa      = registro.get("etapa", ESTADO_AGUARDA_OPCAO)
    local      = registro.get("local", "")
    row        = registro.get("row_number")
    nome_salvo = registro.get("nome", nome) or nome

    logger.info(f"[{phone}] etapa={etapa} | ultima_msg={registro.get('ultima_msg')}")

    # ── ATALHO: endereço perguntado em qualquer etapa ──────
    if detectar_endereco(texto_norm) and local:
        if local == "Copacabana":
            enviar_mensagem(phone, msg.ENDERECO_COPA)
        elif local == "Méier":
            enviar_mensagem(phone, msg.ENDERECO_MEIER)
        return

    # ════════════════════════════════════════════════════════
    # ETAPA 1 — MENU PRINCIPAL
    # ════════════════════════════════════════════════════════
    if etapa == ESTADO_AGUARDA_OPCAO:
        if texto_norm in ["1", "1️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_SUBMENU):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_SUBMENU,
                                 ultima_msg=msg.BLOCO_SUBMENU)
                enviar_mensagem(phone, msg.SUBMENU_CONSULTA)

        elif texto_norm in ["2", "2️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_MARINADAS):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_MARINADAS,
                                 ultima_msg=msg.BLOCO_MARINADAS)
                enviar_mensagem(phone, msg.MARINADAS)
                enviar_mensagem(VICTOR_PHONE,
                    msg.notif_marinadas(nome_salvo, phone))

        elif texto_norm in ["3", "3️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_DESCRICAO):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_DESCRICAO,
                                 ultima_msg=msg.BLOCO_DESCRICAO)
                enviar_mensagem(phone, msg.PEDIR_DESCRICAO)

        else:
            if not ja_enviou(registro, msg.BLOCO_MENU):
                resposta_ia = processar_mensagem_livre(
                    texto,
                    contexto="O paciente está no menu principal e enviou mensagem fora do padrão."
                )
                enviar_mensagem(phone, resposta_ia)
                enviar_mensagem(phone, msg.MENU_PRINCIPAL)
                atualizar_estado(row, ultima_msg=msg.BLOCO_MENU)

    # ════════════════════════════════════════════════════════
    # ETAPA 2 — SUBMENU (1ª consulta / retorno / infos)
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDA_SUBMENU:
        if texto_norm in ["1", "1️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_INFO_CONSULTA):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL,
                                 ultima_msg=msg.BLOCO_INFO_CONSULTA)
                enviar_mensagem(phone, msg.INFO_CONSULTA_PARTE1)
                enviar_mensagem(phone, msg.INFO_CONSULTA_PARTE2)

        elif texto_norm in ["2", "2️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_INFO_CONSULTA):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL,
                                 ultima_msg=msg.BLOCO_INFO_CONSULTA)
                enviar_mensagem(phone, msg.PERGUNTA_LOCAL_RETORNO)

        elif texto_norm in ["3", "3️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_ATENDENTE):
                atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                                 ultima_msg=msg.BLOCO_ATENDENTE)
                enviar_mensagem(phone, msg.AGUARDA_ATENDENTE)
                enviar_mensagem(VICTOR_PHONE,
                    msg.notif_outro(nome_salvo, phone, "Paciente pediu outras informações"))

        else:
            enviar_mensagem(phone, msg.ERRO_OPCAO_INVALIDA)
            enviar_mensagem(phone, msg.SUBMENU_CONSULTA)

    # ════════════════════════════════════════════════════════
    # ETAPA 3 — ESCOLHA DO LOCAL
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDA_LOCAL:
        local_detectado = detectar_local(texto)
        if local_detectado:
            if not ja_enviou(registro, msg.BLOCO_TURNO):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO,
                                 local=local_detectado,
                                 ultima_msg=msg.BLOCO_TURNO)
                enviar_mensagem(phone, msg.PERGUNTA_TURNO)
        else:
            enviar_mensagem(phone, msg.ERRO_LOCAL_INVALIDO)

    # ════════════════════════════════════════════════════════
    # ETAPA 4 — TURNO DE PREFERÊNCIA
    # ✅ ÚLTIMO PASSO DO BOT — após isso, passa para humano
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDA_TURNO:
        turno = detectar_turno(texto) or "sem preferência"

        if not ja_enviou(registro, msg.BLOCO_ENCERRAMENTO):
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             hora=turno, ultima_msg=msg.BLOCO_ENCERRAMENTO)

            # 1. Avisa paciente que atendente confirmará o horário
            enviar_mensagem(phone, msg.ENCERRAMENTO_BOT)

            # 2. Envia resumo completo para Victor
            enviar_mensagem(VICTOR_PHONE,
                msg.notif_triagem(nome_salvo, phone, local, turno))

    # ════════════════════════════════════════════════════════
    # ETAPA: DESCRIÇÃO LIVRE (opção 3 do menu)
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDA_DESCRICAO:
        if not ja_enviou(registro, msg.BLOCO_ATENDENTE):
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             ultima_msg=msg.BLOCO_ATENDENTE)
            enviar_mensagem(phone, msg.CONFIRMACAO_RECEBIMENTO)
            enviar_mensagem(VICTOR_PHONE,
                msg.notif_outro(nome_salvo, phone, texto))

    # ════════════════════════════════════════════════════════
    # ETAPA: MARINADAS
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDA_MARINADAS:
        if not ja_enviou(registro, msg.BLOCO_ATENDENTE):
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             ultima_msg=msg.BLOCO_ATENDENTE)
            resposta_ia = processar_mensagem_livre(
                texto,
                contexto="O paciente tem interesse nas Marinadas do Nutri Victor e enviou uma dúvida."
            )
            enviar_mensagem(phone, resposta_ia)
            enviar_mensagem(phone,
                "Nossa atendente estará disponível para te ajudar em breve! 💚")
            enviar_mensagem(VICTOR_PHONE,
                msg.notif_outro(nome_salvo, phone, texto))

    # ════════════════════════════════════════════════════════
    # ETAPA: ATENDIMENTO HUMANO — bot silencioso
    # Qualquer mensagem nova é encaminhada para Victor
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_ATENDIMENTO_HUMANO:
        # Só repassa para Victor se for uma mensagem nova relevante
        # (não reenvia se já chamou a atendente)
        if registro.get("ultima_msg") != "ENCAMINHADO":
            pass  # silencioso — atendente humana assume a conversa
        # Se o paciente insistir com dúvida, encaminha para Victor
        enviar_mensagem(VICTOR_PHONE,
            f"💬 *Nova mensagem de paciente em atendimento:*\n\n"
            f"*Paciente:* {nome_salvo}\n"
            f"*WhatsApp:* {phone}\n"
            f"*Mensagem:* {texto}"
        )

    # ════════════════════════════════════════════════════════
    # ESTADO DESCONHECIDO → REINICIA
    # ════════════════════════════════════════════════════════
    else:
        logger.warning(f"[{phone}] Estado desconhecido '{etapa}' — reiniciando")
        atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO,
                         ultima_msg=msg.BLOCO_MENU)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
