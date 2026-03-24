import requests
import logging
from config import ZAPI_BASE_URL, ZAPI_CLIENT_TOKEN

logger = logging.getLogger(__name__)

def enviar_mensagem(phone: str, mensagem: str) -> bool:
    """Envia mensagem de texto via Z-API."""
    url = f"{ZAPI_BASE_URL}/send-text"
    payload = {
        "phone": str(phone).strip(),
        "message": (mensagem or "").strip()
    }
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_CLIENT_TOKEN
    }

    try:
        if not payload["message"]:
            logger.error(f"Mensagem vazia para {phone}. Payload não enviado.")
            return False

        response = requests.post(url, json=payload, headers=headers, timeout=15)

        logger.info(f"Z-API status={response.status_code}")
        logger.info(f"Z-API resposta={response.text}")

        response.raise_for_status()
        logger.info(f"Mensagem enviada para {phone}")
        return True

    except requests.RequestException as e:
        body = getattr(response, "text", "sem corpo de resposta") if "response" in locals() else "sem resposta"
        logger.error(f"Erro ao enviar mensagem para {phone}: {e} | body={body} | payload={payload}")
        return False
