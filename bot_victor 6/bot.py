import logging
from config import (
    VICTOR_PHONE,
    ESTADO_NOVO, ESTADO_AGUARDA_OPCAO, ESTADO_AGUARDA_SUBMENU,
    ESTADO_AGUARDA_LOCAL, ESTADO_AGUARDA_TURNO, ESTADO_AGUARDA_DESCRICAO,
    ESTADO_AGUARDA_MARINADAS, ESTADO_AGUARDANDO_CONFIRMACAO, ESTADO_ATENDIMENTO_HUMANO
)
from sheets import buscar_estado, criar_registro, atualizar_estado
from zapi import enviar_mensagem
from claude_ai import processar_mensagem_livre
from calendar_service import buscar_horarios_disponiveis
import mensagens as msg

logger = logging.getLogger(__name__)


def normalizar(texto: str) -> str:
    """Normaliza texto para comparações."""
    import unicodedata
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def detectar_local(texto: str) -> str | None:
    t = normalizar(texto)
    if any(x in t for x in ["copa", "copacabana"]):
        return "Copacabana"
    if any(x in t for x in ["meier", "méier", "meir"]):
        return "Méier"
    if any(x in t for x in ["online", "remoto", "virtual", "meet"]):
        return "Online"
    return None


def detectar_turno(texto: str) -> str | None:
    t = normalizar(texto)
    if any(x in t for x in ["manha", "manhã", "manha"]):
        return "manhã"
    if "tarde" in t:
        return "tarde"
    if "noite" in t:
        return "noite"
    return None


def processar_mensagem(phone: str, nome: str, texto: str):
    """
    Função principal — recebe a mensagem do paciente
    e decide o que fazer com base no estado atual.
    """
    texto_norm = normalizar(texto)
    logger.info(f"Mensagem de {phone} ({nome}): '{texto}' | norm: '{texto_norm}'")

    # Busca estado atual do paciente
    registro = buscar_estado(phone)

    # --- PACIENTE NOVO ---
    if registro is None:
        criar_registro(phone, nome, ESTADO_AGUARDA_OPCAO)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
        return

    etapa  = registro.get("etapa", ESTADO_AGUARDA_OPCAO)
    local  = registro.get("local", "")
    row    = registro.get("row_number")
    nome_salvo = registro.get("nome", nome) or nome

    # --- AGUARDA_OPCAO: menu principal ---
    if etapa == ESTADO_AGUARDA_OPCAO:
        if texto_norm in ["1", "1️⃣"]:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_SUBMENU)
            enviar_mensagem(phone, msg.SUBMENU_CONSULTA)

        elif texto_norm in ["2", "2️⃣"]:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_MARINADAS)
            enviar_mensagem(phone, msg.MARINADAS)
            # Marinadas: apenas envia o link, sem notificar Victor

        elif texto_norm in ["3", "3️⃣"]:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_DESCRICAO)
            enviar_mensagem(phone, msg.PEDIR_DESCRICAO)

        else:
            # mensagem livre — usa IA para responder e reapresenta menu
            resposta_ia = processar_mensagem_livre(texto,
                contexto="O paciente está no menu principal e enviou uma mensagem fora do padrão.")
            enviar_mensagem(phone, resposta_ia)
            enviar_mensagem(phone, msg.MENU_PRINCIPAL)

    # --- AGUARDA_SUBMENU: 1a consulta / retorno / outras infos ---
    elif etapa == ESTADO_AGUARDA_SUBMENU:
        if texto_norm in ["1", "1️⃣"]:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL)
            enviar_mensagem(phone, msg.INFO_PRIMEIRA_CONSULTA)

        elif texto_norm in ["2", "2️⃣"]:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_LOCAL)
            enviar_mensagem(phone, msg.PERGUNTA_LOCAL_RETORNO)

        elif texto_norm in ["3", "3️⃣"]:
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
            enviar_mensagem(phone, msg.AGUARDA_ATENDENTE)

        else:
            enviar_mensagem(phone, msg.ERRO_OPCAO_INVALIDA + "\n\n" + msg.SUBMENU_CONSULTA)

    # --- AGUARDA_LOCAL: copa / meier / online ---
    elif etapa == ESTADO_AGUARDA_LOCAL:
        local_detectado = detectar_local(texto)
        if local_detectado:
            atualizar_estado(row, etapa=ESTADO_AGUARDA_TURNO, local=local_detectado)
            enviar_mensagem(phone, msg.PERGUNTA_TURNO)
        else:
            enviar_mensagem(phone,
                "Não entendi o local 😅\n\n"
                "Por favor informe:\n📍 *Copa*, *Méier* ou 💻 *Online*")

    # --- AGUARDA_TURNO: manha / tarde / noite ---
    elif etapa == ESTADO_AGUARDA_TURNO:
        turno_detectado = detectar_turno(texto)
        turno_final = turno_detectado or "sem preferência"

        atualizar_estado(row, etapa=ESTADO_AGUARDANDO_CONFIRMACAO, hora=turno_final)

        # Busca horários disponíveis no Google Agenda
        try:
            horarios_texto = buscar_horarios_disponiveis(local, turno_final)
        except Exception as e:
            logger.error(f"Erro ao buscar agenda: {e}")
            horarios_texto = (
                "Vou verificar os horários disponíveis e nossa atendente "
                "entrará em contato em breve! 💚"
            )

        enviar_mensagem(phone, horarios_texto)
        enviar_mensagem(phone, msg.CONFIRMACAO_SOLICITACAO)

        # Notifica Victor
        enviar_mensagem(VICTOR_PHONE,
            msg.notificacao_victor(
                nome_salvo, phone,
                local=local, turno=turno_final,
                tipo="agendamento"
            ))

    # --- AGUARDA_DESCRICAO: paciente descreve o assunto livre ---
    elif etapa == ESTADO_AGUARDA_DESCRICAO:
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        enviar_mensagem(phone, msg.CONFIRMACAO_RECEBIMENTO)
        enviar_mensagem(VICTOR_PHONE,
            msg.notificacao_victor(
                nome_salvo, phone,
                assunto=texto, tipo="outro"
            ))

    # --- AGUARDA_MARINADAS: dúvidas sobre marinadas ---
    elif etapa == ESTADO_AGUARDA_MARINADAS:
        atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO)
        resposta_ia = processar_mensagem_livre(texto,
            contexto="O paciente tem interesse nas Marinadas do Nutri Victor e enviou uma dúvida.")
        enviar_mensagem(phone, resposta_ia)
        enviar_mensagem(phone, "Nossa atendente estará disponível para te ajudar em breve! 💚")
        enviar_mensagem(VICTOR_PHONE,
            msg.notificacao_victor(nome_salvo, phone, assunto=texto, tipo="outro"))

    # --- AGUARDANDO_CONFIRMACAO: paciente escolhe horário ---
    elif etapa == ESTADO_AGUARDANDO_CONFIRMACAO:
        from calendar_service import criar_evento_agenda, NOMES_LOCAL, _normalizar_local
        import re

        # Detecta se a mensagem contém uma data/hora (ex: "25/04 às 09:30", "dia 25 às 9h")
        padrao_data = re.search(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+(?:às|as)?\s*\d{1,2}[h:]\d{0,2}", texto)

        if padrao_data:
            horario_escolhido = padrao_data.group(0).strip()
            local_key   = _normalizar_local(local)
            nome_local  = NOMES_LOCAL.get(local_key, local)

            # 1. Confirma para o paciente
            enviar_mensagem(phone, msg.pos_agendamento_confirmado(nome_salvo))

            # 2. Cria evento no Google Agenda
            sucesso_agenda = criar_evento_agenda(
                local=local,
                paciente_nome=nome_salvo,
                paciente_phone=phone,
                data_hora_str=horario_escolhido
            )

            # 3. Notifica Victor com todos os detalhes
            turno_salvo = registro.get("hora", "")
            aviso_agenda = "✅ Evento criado no Google Agenda" if sucesso_agenda else "⚠️ Criar evento manualmente na agenda"
            notif = (
                f"🎉 *Consulta Agendada!*\n\n"
                f"*Paciente:* {nome_salvo}\n"
                f"*WhatsApp:* {phone}\n"
                f"*Local:* {nome_local}\n"
                f"*Horário:* {horario_escolhido}\n"
                f"*Turno preferido:* {turno_salvo}\n\n"
                f"{aviso_agenda}\n\n"
                f"O pré-questionário e as orientações já foram enviados ao paciente 💚"
            )
            enviar_mensagem(VICTOR_PHONE, notif)

            # 4. Atualiza estado
            atualizar_estado(row, etapa=ESTADO_ATENDIMENTO_HUMANO, data=horario_escolhido)

        else:
            # Mensagem sem data/hora — usa IA para responder e repete a pergunta
            resposta_ia = processar_mensagem_livre(texto,
                contexto=(
                    f"O paciente {nome_salvo} está escolhendo um horário para consulta "
                    f"em {local}. Oriente-o a responder com a data e horário desejado, "
                    "ex: '25/04 às 09:30'."
                ))
            enviar_mensagem(phone, resposta_ia)

    # --- ATENDIMENTO_HUMANO: aguardando atendente ---
    elif etapa == ESTADO_ATENDIMENTO_HUMANO:
        # Usa IA para responder enquanto atendente não assume
        resposta_ia = processar_mensagem_livre(texto,
            contexto="O paciente está aguardando atendimento humano. Responda brevemente e reforce que a atendente responderá em breve.")
        enviar_mensagem(phone, resposta_ia)

    else:
        # Estado desconhecido — reinicia
        atualizar_estado(row, etapa=ESTADO_AGUARDA_OPCAO)
        enviar_mensagem(phone, msg.MENU_PRINCIPAL)
