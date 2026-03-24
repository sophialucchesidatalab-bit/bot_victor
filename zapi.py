import requests
import logging
from config import ZAPI_BASE_URL

logger = logging.getLogger(__name__)

def enviar_mensagem(phone: str, mensagem: str) -> bool:
    """Envia mensagem de texto via Z-API."""
    try:
        url = f"{ZAPI_BASE_URL}/send-text"
        payload = {"phone": phone, "message": mensagem}
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        logger.info(f"Mensagem enviada para {phone}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {phone}: {e}")
        return False

def enviar_documento(phone: str, url_doc: str, nome_arquivo: str, caption: str = "") -> bool:
    """Envia um documento/PDF via Z-API."""
    try:
        url = f"{ZAPI_BASE_URL}/send-document/document"
        payload = {
            "phone": phone,
            "document": url_doc,
            "fileName": nome_arquivo,
            "caption": caption
        }
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        logger.info(f"Documento enviado para {phone}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar documento para {phone}: {e}")
        return False
