import logging
import os
from flask import Flask, request, jsonify
from bot import processar_mensagem
from sheets import buscar_estado, criar_registro, atualizar_estado
from config import ESTADO_ATENDIMENTO_HUMANO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Victor Afonso Nutricionista"}), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Endpoint que recebe as mensagens da Z-API.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "payload vazio"}), 400

        logger.info(f"Webhook recebido: {data}")

        # ── Ignora quando consultório inicia a conversa pelo celular ───────────
        # fromApi=False → mensagem veio do celular físico (Victor), não de um cliente
        # fromMe=True   → mensagem enviada pelo próprio número via API
        # Em ambos os casos: registra na planilha como ATENDIMENTO_HUMANO e silencia
        from_api = data.get("fromApi", True)
        from_me_raw = data.get("fromMe") or data.get("fromme") or data.get("from_me")
        from_me = str(from_me_raw).lower() in ("true", "1", "yes")

        if from_me or not from_api:
            phone_temp = data.get("phone", "").strip()
            nome_temp = (
                data.get("senderName", "")
                or data.get("chatName", "")
                or "Paciente"
            )
            if phone_temp:
                try:
                    registro_temp = buscar_estado(phone_temp)
                    if registro_temp is None:
                        criar_registro(
                            phone=phone_temp,
                            nome=nome_temp,
                            etapa=ESTADO_ATENDIMENTO_HUMANO
                        )
                        logger.info(f"Registro criado em ATENDIMENTO_HUMANO para {phone_temp}")
                    else:
                        atualizar_estado(
                            registro_temp.get("row_number"),
                            etapa=ESTADO_ATENDIMENTO_HUMANO
                        )
                        logger.info(f"Atualizado para ATENDIMENTO_HUMANO: {phone_temp}")
                except Exception as e:
                    logger.error(f"Erro ao registrar ATENDIMENTO_HUMANO: {e}")
            return jsonify({"status": "ignorado (consultorio_iniciou)"}), 200

        # ── Ignora mensagens de grupos ─────────────────────────────────────────
        if data.get("isGroup") or data.get("isgroup"):
            logger.info("Ignorado: mensagem de grupo")
            return jsonify({"status": "ignorado (grupo)"}), 200

        # ── Ignora tipos de mensagem que não são texto ─────────────────────────
        tipo = data.get("type", "")
        if tipo and tipo not in ("ReceivedCallback", ""):
            logger.info(f"Ignorado: tipo={tipo}")
            return jsonify({"status": f"ignorado (tipo={tipo})"}), 200

        # ── Ignora notificações de status de entrega ───────────────────────────
        if data.get("status") and not data.get("text") and not data.get("phone"):
            logger.info("Ignorado: notificação de status sem texto")
            return jsonify({"status": "ignorado (status delivery)"}), 200

        # ── Extrai campos principais ───────────────────────────────────────────
        phone = data.get("phone", "").strip()
        nome = (
            data.get("senderName", "")
            or data.get("chatName", "")
            or "Paciente"
        )

        # ── Extrai o texto da mensagem ─────────────────────────────────────────
        texto = ""
        campo_text = data.get("text")
        if isinstance(campo_text, dict):
            texto = campo_text.get("message", "").strip()
        elif isinstance(campo_text, str):
            texto = campo_text.strip()

        # ── Ignora se não tiver phone ou texto ─────────────────────────────────
        if not phone:
            logger.info("Ignorado: sem phone")
            return jsonify({"status": "ignorado (sem phone)"}), 200

        if not texto:
            logger.info(f"Ignorado: sem texto | phone={phone} | tipo={tipo}")
            return jsonify({"status": "ignorado (sem texto)"}), 200

        # ── Processa ───────────────────────────────────────────────────────────
        logger.info(f"Processando: phone={phone} nome={nome} texto='{texto}'")
        processar_mensagem(phone=phone, nome=nome, texto=texto)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Erro no webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
