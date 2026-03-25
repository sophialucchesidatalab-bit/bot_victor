"""
bot.py — Máquina de estados do bot Victor Afonso Nutricionista

REGRA ANTI-REPETIÇÃO:
    Cada etapa grava um ID de bloco em "ultima_msg" na planilha.
    Antes de enviar, o bot verifica: se ultima_msg == bloco_desta_etapa,
    a mensagem JÁ FOI enviada e é ignorada.
    Isso evita reenvios quando o Render reinicia ou a mensagem chega duplicada.
"""
import logging
import re
from config import (
    VICTOR_PHONE,
    ESTADO_AGUARDA_OPCAO, ESTADO_AGUARDA_SUBMENU,
    ESTADO_AGUARDA_LOCAL, ESTADO_AGUARDA_TURNO,
    ESTADO_AGUARDA_DESCRICAO, ESTADO_AGUARDA_MARINADAS,
    ESTADO_AGUARDANDO_CONFIRMACAO, ESTADO_ATENDIMENTO_HUMANO,
    LINK_ORIENTACOES_IMG,
)
from sheets import buscar_estado, criar_registro, atualizar_estado
from zapi import enviar_mensagem, enviar_imagem
from claude_ai import processar_mensagem_livre
from calendar_service import buscar_horarios_disponiveis
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
    if any(x in t for x in ["manha"]):
        return "manhã"
    if "tarde" in t:
        return "tarde"
    if "noite" in t:
        return "noite"
    return None


def detectar_endereco(texto: str) -> str | None:
    """Detecta se o paciente está pedindo endereço."""
    t = normalizar(texto)
    if any(x in t for x in ["endereco", "endereço", "onde fica", "localizacao",
                              "como chegar", "onde e", "onde é", "maps"]):
        return t
    return None


def ja_enviou(registro: dict, bloco: str) -> bool:
    """
    Verifica se esse bloco de mensagem já foi enviado ao paciente.
    Retorna True se sim → bot NÃO reenvia.
    """
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

    # ── ATALHO: paciente pedindo endereço em qualquer etapa ─
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
            # Texto livre → IA responde + reapresenta menu UMA vez
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
                # 2 mensagens separadas, como Victor faz
                enviar_mensagem(phone, msg.INFO_CONSULTA_PARTE1)
                enviar_mensagem(phone, msg.INFO_CONSULTA_PARTE2)

        elif texto_norm in ["2", "2️⃣"]:
            if not ja_enviou(registro, msg.BLOCO_INFO_CONSULTA):
                atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL,
                                 ultima_msg=msg.BLOCO_INFO_CONSULTA)
                enviar_mensagem(phone, msg.PERGUNTA_LOCAL_RETORNO)

        elif texto_norm in ["3", "3️⃣"]:
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             ultima_msg=msg.BLOCO_ATENDENTE)
            enviar_mensagem(phone, msg.AGUARDA_ATENDENTE)

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
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDA_TURNO:
        turno = detectar_turno(texto) or "sem preferência"

        try:
            horarios_texto = buscar_horarios_disponiveis(local, turno)
        except Exception as e:
            logger.error(f"Erro ao buscar agenda: {e}")
            horarios_texto = (
                "Vou verificar os horários disponíveis e nossa atendente "
                "entrará em contato em breve! 💚"
            )

        if not ja_enviou(registro, msg.BLOCO_HORARIOS):
            atualizar_estado(row, etapa=ESTADO_AGUARDANDO_CONFIRMACAO,
                             hora=turno, ultima_msg=msg.BLOCO_HORARIOS)
            enviar_mensagem(phone, horarios_texto)
            enviar_mensagem(phone, msg.INSTRUCAO_HORARIO)
            # Notifica Victor sobre interesse (sem confirmar ainda)
            enviar_mensagem(VICTOR_PHONE,
                msg.notif_interesse(nome_salvo, phone, local, turno))

    # ════════════════════════════════════════════════════════
    # ETAPA 5 — PACIENTE ESCOLHE O HORÁRIO
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_AGUARDANDO_CONFIRMACAO:
        from calendar_service import criar_evento_agenda, NOMES_LOCAL, _normalizar_local

        padrao = re.search(
            r"\d{1,2}/\d{1,2}(?:/\d{2,4})?\s*(?:às|as|@|a)?\s*\d{1,2}[h:]\d{0,2}",
            texto, re.IGNORECASE
        )

        if padrao and not ja_enviou(registro, msg.BLOCO_CONFIRMADO):
            horario_escolhido = padrao.group(0).strip()
            nome_local = NOMES_LOCAL.get(_normalizar_local(local), local)
            turno_salvo = registro.get("hora", "")

            # 1. Confirmação + questionário + imagem de bioimpedância
            m1, m2, m3 = msg.pos_agendamento(nome_salvo, nome_local, horario_escolhido)
            enviar_mensagem(phone, m1)
            enviar_mensagem(phone, m2)
            enviar_imagem(phone, LINK_ORIENTACOES_IMG)   # imagem bioimpedância
            enviar_mensagem(phone, m3)

            # 2. Cria evento no Google Agenda
            sucesso = criar_evento_agenda(
                local=local,
                paciente_nome=nome_salvo,
                paciente_phone=phone,
                data_hora_str=horario_escolhido
            )

            # 3. Notifica Victor
            enviar_mensagem(VICTOR_PHONE,
                msg.notif_agendado(nome_salvo, phone, nome_local,
                                   horario_escolhido, turno_salvo, sucesso))

            # 4. Atualiza estado
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             data=horario_escolhido,
                             ultima_msg=msg.BLOCO_CONFIRMADO)

        elif not padrao:
            # Sem data/hora → IA orienta
            resposta_ia = processar_mensagem_livre(
                texto,
                contexto=(
                    f"O paciente {nome_salvo} está escolhendo um horário para consulta "
                    f"em {local}. Oriente-o a responder com data e horário, "
                    "ex: '27/03 às 11:00'."
                )
            )
            enviar_mensagem(phone, resposta_ia)

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
    # ETAPA: ATENDIMENTO HUMANO
    # ════════════════════════════════════════════════════════
    elif etapa == ESTADO_ATENDIMENTO_HUMANO:
        # IA tenta responder; se não souber, chama a assistente
        resposta_ia = processar_mensagem_livre(
            texto,
            contexto=(
                "O paciente está com uma dúvida. Responda se souber com certeza. "
                "Se não tiver certeza ou a pergunta fugir do escopo nutricional/agendamento, "
                "responda EXATAMENTE com a palavra: NAO_SEI"
            )
        )

        if "NAO_SEI" in (resposta_ia or "").upper():
            enviar_mensagem(phone, msg.IA_NAO_SABE)
            enviar_mensagem(VICTOR_PHONE,
                f"⚠️ *Paciente precisa de atendimento!*\n\n"
                f"*Paciente:* {nome_salvo}\n"
                f"*WhatsApp:* {phone}\n"
                f"*Pergunta:* {texto}\n\n"
                f"A IA não soube responder. Por favor entre em contato! 💚"
            )
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO,
                             ultima_msg="CHAMOU_ASSISTENTE")
        else:
            enviar_mensagem(phone, resposta_ia)

    # ════════════════════════════════════════════════════════
    # ESTADO DESCONHECIDO → REINICIA
    # ════════════════════════════════════════════════════════
    else:
        logger.warning(f"[{phone}] Estado desconhecido '{etapa}' — reiniciando")
        atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO,
                         ultima_msg=msg.BLOCO_MENU)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
