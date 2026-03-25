import logging
from datetime import datetime

from config import (
    VICTOR_PHONE,
    ESTADO_AGUARDA_OPCAO,
    ESTADO_AGUARDA_SUBMENU,
    ESTADO_AGUARDA_LOCAL,
    ESTADO_AGUARDA_TURNO,
    ESTADO_AGUARDA_DESCRICAO,
    ESTADO_AGUARDA_MARINADAS,
    ESTADO_ATENDIMENTO_HUMANO,
)
from sheets import buscar_estado, criar_registro, atualizar_estado
from zapi import enviar_mensagem
import mensagens as msg

logger = logging.getLogger(__name__)


def normalizar_phone(phone: str) -> str:
    """
    Garante que o número sempre seja salvo e buscado no mesmo formato.
    Remove tudo que não for dígito, depois aplica formato padrão brasileiro.
    Exemplo: +55 21 99880-9680 → 5521998809680
    """
    digits = "".join(c for c in str(phone) if c.isdigit())
    # Remove código de país duplicado (ex: 5555...)
    if digits.startswith("55") and len(digits) > 13:
        digits = digits[2:]
    return digits


def normalizar(texto: str) -> str:
    import unicodedata
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def detectar_opcao_menu(texto_norm: str) -> str | None:
    """
    Detecta qual opção do menu o usuário escolheu.
    Aceita número, emoji numerado ou palavras-chave relacionadas.
    Retorna "1", "2", "3" ou None.
    """
    # Opção 1 — consulta / acompanhamento nutricional
    if texto_norm in ["1", "1️⃣"]:
        return "1"
    if texto_norm.startswith("1"):
        return "1"
    if any(x in texto_norm for x in [
        "consul", "acompanhamento", "nutricional", "nutri", "retorno",
        "agendar", "agendamento", "informacao", "informacoes", "primeira"
    ]):
        return "1"

    # Opção 2 — marinadas
    if texto_norm in ["2", "2️⃣"]:
        return "2"
    if texto_norm.startswith("2"):
        return "2"
    if any(x in texto_norm for x in ["marinada", "marinadas", "tempero", "produto"]):
        return "2"

    # Opção 3 — outros assuntos
    if texto_norm in ["3", "3️⃣"]:
        return "3"
    if texto_norm.startswith("3"):
        return "3"
    if any(x in texto_norm for x in ["outro", "outros", "assunto", "duvida", "pergunta"]):
        return "3"

    return None


def detectar_opcao_submenu(texto_norm: str) -> str | None:
    """
    Detecta opção do submenu de consulta.
    Retorna "1", "2", "3" ou None.
    """
    if texto_norm in ["1", "1️⃣"]:
        return "1"
    if texto_norm.startswith("1"):
        return "1"
    if any(x in texto_norm for x in ["primeira", "novo", "nunca fui", "primeira vez"]):
        return "1"

    if texto_norm in ["2", "2️⃣"]:
        return "2"
    if texto_norm.startswith("2"):
        return "2"
    if any(x in texto_norm for x in ["retorno", "voltar", "ja fui", "segunda"]):
        return "2"

    if texto_norm in ["3", "3️⃣"]:
        return "3"
    if texto_norm.startswith("3"):
        return "3"
    if any(x in texto_norm for x in ["outro", "outros", "informacao", "duvida"]):
        return "3"

    return None


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
        return "Manhã"
    if "tarde" in t:
        return "Tarde"
    if "noite" in t:
        return "Noite"
    return None


def detectar_endereco(texto: str) -> bool:
    t = normalizar(texto)
    return any(x in t for x in [
        "endereco", "endereço", "onde fica", "localizacao",
        "como chegar", "onde e", "onde é", "maps"
    ])


def data_hoje():
    return datetime.now().strftime("%d/%m/%Y")


def processar_mensagem(phone: str, nome: str, texto: str):
    # ── Normaliza o número antes de qualquer operação ──────────────────────────
    phone = normalizar_phone(phone)

    texto_norm = normalizar(texto)
    logger.info(f"[{phone}] msg='{texto}'")

    registro = buscar_estado(phone)

    # ── PACIENTE NOVO ──────────────────────────────────────────────────────────
    if registro is None:
        criar_registro(
            phone=phone,
            nome=nome,
            etapa=ESTADO_AGUARDA_OPCAO
        )
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
        return

    etapa      = registro.get("etapa", ESTADO_AGUARDA_OPCAO)
    local      = registro.get("local", "")
    row        = registro.get("row_number")
    nome_salvo = registro.get("nome", nome) or nome

    logger.info(f"[{phone}] etapa={etapa}")

    # ── ATALHO: paciente pede endereço ────────────────────────────────────────
    if detectar_endereco(texto_norm) and local:
        if local == "Copacabana":
            enviar_mensagem(phone, msg.ENDERECO_COPA)
        elif local == "Méier":
            enviar_mensagem(phone, msg.ENDERECO_MEIER)
        return

    # ── ETAPA 1 — MENU PRINCIPAL ──────────────────────────────────────────────
    if etapa == ESTADO_AGUARDA_OPCAO:
        opcao = detectar_opcao_menu(texto_norm)

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
            enviar_mensagem(phone, msg.ERRO_OPCAO_INVALIDA)
            enviar_mensagem(phone, msg.MENU_PRINCIPAL)

    # ── ETAPA 2 — SUBMENU ─────────────────────────────────────────────────────
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
            enviar_mensagem(phone, msg.ERRO_OPCAO_INVALIDA)
            enviar_mensagem(phone, msg.SUBMENU_CONSULTA)

    # ── ETAPA 3 — LOCAL ───────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_LOCAL:
        local_detectado = detectar_local(texto)
        if local_detectado:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO, local=local_detectado)
            enviar_mensagem(phone, msg.PERGUNTA_TURNO)
        else:
            enviar_mensagem(phone, msg.ERRO_LOCAL_INVALIDO)

    # ── ETAPA 4 — TURNO ───────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_TURNO:
        turno = detectar_turno(texto) or texto.strip().capitalize()

        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO, hora=turno)

        enviar_mensagem(phone, msg.ENCERRAMENTO_BOT)
        enviar_mensagem(
            VICTOR_PHONE,
            msg.notif_triagem(nome_salvo, phone, local, turno)
        )

    # ── ETAPA — DESCRIÇÃO LIVRE ───────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_DESCRICAO:
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        enviar_mensagem(phone, msg.CONFIRMACAO_RECEBIMENTO)
        enviar_mensagem(
            VICTOR_PHONE,
            msg.notif_outro(nome_salvo, phone, texto)
        )

    # ── ETAPA — MARINADAS ─────────────────────────────────────────────────────
    elif etapa == ESTADO_AGUARDA_MARINADAS:
        logger.info(f"[{phone}] Mensagem recebida em AGUARDA_MARINADAS — ignorando")
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        return

    # ── ATENDIMENTO HUMANO — BOT SILENCIOSO ───────────────────────────────────
    elif etapa == ESTADO_ATENDIMENTO_HUMANO:
        logger.info(f"[{phone}] Em ATENDIMENTO_HUMANO — bot silencioso")
        return

    # ── ESTADO DESCONHECIDO ───────────────────────────────────────────────────
    else:
        logger.warning(f"[{phone}] Estado desconhecido '{etapa}' — reiniciando")
        atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
