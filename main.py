import logging
import os
from flask import Flask, request, jsonify
from bot import processar_mensagem

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
    A Z-API envia um POST com o JSON da mensagem recebida.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "payload vazio"}), 400

        logger.info(f"Webhook recebido: {data}")

        # Ignora mensagens enviadas pelo proprio bot
        if data.get("fromMe"):
            return jsonify({"status": "ignorado (fromMe)"}), 200

        # Ignora mensagens de grupos
        if data.get("isGroup"):
            return jsonify({"status": "ignorado (grupo)"}), 200

        # Extrai campos principais
        phone = data.get("phone", "")
        nome  = data.get("senderName", "") or data.get("chatName", "") or "Paciente"

        # Extrai o texto da mensagem
        texto = ""
        if isinstance(data.get("text"), dict):
            texto = data["text"].get("message", "")
        elif isinstance(data.get("text"), str):
            texto = data["text"]

        if not phone or not texto:
            return jsonify({"status": "ignorado (sem phone ou texto)"}), 200

        # Processa a mensagem
        processar_mensagem(phone=phone, nome=nome, texto=texto)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error(f"Erro no webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
