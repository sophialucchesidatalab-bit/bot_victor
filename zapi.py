"""
zapi.py
Funções de envio via Z-API (WhatsApp).
"""

import logging
import requests
from config import ZAPI_BASE_URL, ZAPI_CLIENT_TOKEN

logger = logging.getLogger(__name__)

HEADERS = {"Content-Type": "application/json"}
if ZAPI_CLIENT_TOKEN:
    HEADERS["Client-Token"] = ZAPI_CLIENT_TOKEN


def enviar_mensagem(phone: str, texto: str) -> bool:
    """Envia mensagem de texto simples."""
    url = f"{ZAPI_BASE_URL}/send-text"
    payload = {"phone": phone, "message": texto}
    try:
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)
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
        resp = requests.post(url, json=payload, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        logger.info(f"Imagem enviada para {phone}: {url_imagem}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar imagem para {phone}: {e}")
        return False
