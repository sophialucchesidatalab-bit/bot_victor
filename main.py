import logging
import os
from flask import Flask, request, jsonify
from bot import processar_mensagem
from sheets import buscar_estado, criar_registro, atualizar_estado
from config import ESTADO_ATENDIMENTO_HUMANO

# Números que nunca recebem bot — Victor atende manualmente
NUMEROS_SEM_BOT = {
    "5521991640431",
}

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
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "payload vazio"}), 400

        logger.info(f"Webhook recebido: {data}")

        phone = data.get("phone", "").strip()

        # ── Ignora notificações de status ──────────────────────────────────────
        if data.get("type") == "MessageStatusCallback":
            return jsonify({"status": "ignorado (status callback)"}), 200

        # 🚫 Números VIP — bot não entra, Victor atende direto
        if phone in NUMEROS_SEM_BOT:
            logger.info(f"[BLOQUEIO] Número {phone} na lista sem bot — ignorando.")
            return jsonify({"status": "ignored_vip_number"}), 200

        # ── Detecta se foi o Victor enviando do celular físico ─────────────────
        from_me_raw = data.get("fromMe") or data.get("fromme") or data.get("from_me")
        from_me = str(from_me_raw).lower() in ("true", "1", "yes")

        if from_me:
            nome_temp = (
                data.get("senderName", "")
                or data.get("chatName", "")
                or "Paciente"
            )
            if phone:
                try:
                    registro_temp = buscar_estado(phone)
                    if registro_temp is None:
                        criar_registro(
                            phone=phone,
                            nome=nome_temp,
                            etapa=ESTADO_ATENDIMENTO_HUMANO
                        )
                        logger.info(f"Registro criado em ATENDIMENTO_HUMANO para {phone}")
                    else:
                        atualizar_estado(
                            registro_temp.get("row_number"),
                            etapa=ESTADO_ATENDIMENTO_HUMANO
                        )
                        logger.info(f"Atualizado para ATENDIMENTO_HUMANO: {phone}")
                except Exception as e:
                    logger.error(f"Erro ao registrar ATENDIMENTO_HUMANO: {e}")
            return jsonify({"status": "ignorado (victor_enviou)"}), 200

        # ── Ignora mensagens de grupos ─────────────────────────────────────────
        if data.get("isGroup") or data.get("isgroup"):
            logger.info("Ignorado: mensagem de grupo")
            return jsonify({"status": "ignorado (grupo)"}), 200

        # ── Ignora tipos que não são texto recebido ────────────────────────────
        tipo = data.get("type", "")
        if tipo and tipo not in ("ReceivedCallback", ""):
            logger.info(f"Ignorado: tipo={tipo}")
            return jsonify({"status": f"ignorado (tipo={tipo})"}), 200

        # ── Extrai campos principais ───────────────────────────────────────────
        nome = (
            data.get("senderName", "")
            or data.get("chatName", "")
            or "Paciente"
        )

        # ── Extrai o texto ─────────────────────────────────────────────────────
        texto = ""
        campo_text = data.get("text")
        if isinstance(campo_text, dict):
            texto = campo_text.get("message", "").strip()
        elif isinstance(campo_text, str):
            texto = campo_text.strip()

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
