import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import SPREADSHEET_ID, SHEET_NAME
import os
import json
import time

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON nao configurado")

    creds_dict = json.loads(creds_json)

    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=SCOPES
    )

    return build("sheets", "v4", credentials=creds)


def buscar_estado(phone: str) -> dict | None:

    try:
        service = _get_service()

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:G"
        ).execute()

        rows = result.get("values", [])

        for i, row in enumerate(rows[1:], start=2):

            if row and row[0] == phone:

                return {
                    "row_number": i,
                    "phone": row[0] if len(row) > 0 else "",
                    "etapa": row[1] if len(row) > 1 else "",
                    "local": row[2] if len(row) > 2 else "",
                    "data": row[3] if len(row) > 3 else "",
                    "hora": row[4] if len(row) > 4 else "",
                    "nome": row[5] if len(row) > 5 else "",
                }

        return None

    except Exception as e:

        logger.error(
            f"[ERRO buscar_estado] {phone}: {e}"
        )

        return None


def atualizar_estado(
    row_number: int,
    etapa: str = None,
    local: str = None,
    data: str = None,
    hora: str = None,
    nome: str = None
) -> bool:

    from datetime import datetime

    for tentativa in range(3):

        try:

            service = _get_service()

            agora = datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )

            atualizacoes = []

            if etapa is not None:
                atualizacoes.append({
                    "range": f"{SHEET_NAME}!B{row_number}",
                    "values": [[etapa]]
                })

            if local is not None:
                atualizacoes.append({
                    "range": f"{SHEET_NAME}!C{row_number}",
                    "values": [[local]]
                })

            if data is not None:
                atualizacoes.append({
                    "range": f"{SHEET_NAME}!D{row_number}",
                    "values": [[data]]
                })

            if hora is not None:
                atualizacoes.append({
                    "range": f"{SHEET_NAME}!E{row_number}",
                    "values": [[hora]]
                })

            if nome is not None:
                atualizacoes.append({
                    "range": f"{SHEET_NAME}!F{row_number}",
                    "values": [[nome]]
                })

            atualizacoes.append({
                "range": f"{SHEET_NAME}!G{row_number}",
                "values": [[agora]]
            })

            service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={
                    "valueInputOption": "USER_ENTERED",
                    "data": atualizacoes
                }
            ).execute()

            logger.info(
                f"[OK atualizar_estado] linha={row_number} etapa={etapa}"
            )

            return True

        except Exception as e:

            logger.error(
                f"[ERRO atualizar_estado tentativa {tentativa+1}] {e}"
            )

            time.sleep(1)

    return False
