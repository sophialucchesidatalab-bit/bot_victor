"""
zapi.py
Funções de envio via Z-API (WhatsApp).
"""
import logging
import requests
from config import ZAPI_BASE_URL, ZAPI_CLIENT_TOKEN

logger = logging.getLogger(__name__)


def _get_headers() -> dict:
    """Monta headers a cada requisição para garantir que o Client-Token seja lido corretamente."""
    headers = {"Content-Type": "application/json"}
    token = ZAPI_CLIENT_TOKEN
    if token:
        headers["Client-Token"] = token
    return headers


def enviar_mensagem(phone: str, texto: str) -> bool:
    """Envia mensagem de texto simples."""
    url = f"{ZAPI_BASE_URL}/send-text"
    payload = {"phone": phone, "message": texto}
    try:
        resp = requests.post(url, json=payload, headers=_get_headers(), timeout=15)
        logger.info(f"Z-API send-text status={resp.status_code} body={resp.text[:200]}")
        resp.raise_for_status()
        logger.info(f"Mensagem enviada para {phone}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {phone}: {e}")
        return False


def enviar_imagem(phone: str, url_imagem: str, caption: str = "") -> bool:
    """
    Envia imagem via URL pública.
    A Z-API baixa a imagem do URL e envia para o WhatsApp.
    """
    url = f"{ZAPI_BASE_URL}/send-image"
    payload = {
        "phone":   phone,
        "image":   url_imagem,
        "caption": caption,
    }
    try:
        resp = requests.post(url, json=payload, headers=_get_headers(), timeout=30)
        logger.info(f"Z-API send-image status={resp.status_code} body={resp.text[:200]}")
        resp.raise_for_status()
        logger.info(f"Imagem enviada para {phone}: {url_imagem}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar imagem para {phone}: {e}")
        return False
