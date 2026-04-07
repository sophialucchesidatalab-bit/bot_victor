import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import SPREADSHEET_ID, SHEET_NAME
import os, json

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON nao configurado")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _proxima_linha_vazia(service) -> int:
    """
    Encontra a próxima linha vazia olhando APENAS a coluna A.
    Isso evita o bug do append que considera colunas além de G
    e desvia os dados para colunas erradas.
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:A"
    ).execute()
    rows = result.get("values", [])
    return len(rows) + 1


def buscar_estado(phone: str) -> dict | None:
    """Busca o registro do paciente na planilha pelo telefone."""
    try:
        service = _get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A:G"
        ).execute()
        rows = result.get("values", [])
        for i, row in enumerate(rows[1:], start=2):  # pula cabeçalho
            if row and row[0] == phone:
                return {
                    "row_number": i,
                    "phone":      row[0] if len(row) > 0 else "",
                    "etapa":      row[1] if len(row) > 1 else "",
                    "local":      row[2] if len(row) > 2 else "",
                    "data":       row[3] if len(row) > 3 else "",
                    "hora":       row[4] if len(row) > 4 else "",
                    "nome":       row[5] if len(row) > 5 else "",
                    "atualizado": row[6] if len(row) > 6 else "",
                }
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar estado para {phone}: {e}")
        return None


def criar_registro(phone: str, nome: str, etapa: str,
                   local: str = "", hora: str = "") -> bool:
    """
    Cria novo registro para um paciente novo.
    Aceita local e hora opcionais para pré-preencher quando extraídos
    da primeira mensagem do paciente.
    USA UPDATE em linha exata em vez de APPEND para evitar
    deslocamento de colunas causado por dados em colunas além de G.
    """
    from datetime import datetime
    try:
        service = _get_service()
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        linha = _proxima_linha_vazia(service)

        # Colunas: A=phone, B=etapa, C=local, D=data, E=hora, F=nome, G=atualizado
        values = [[phone, etapa, local, "", hora, nome, agora]]

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A{linha}:G{linha}",
            valueInputOption="USER_ENTERED",
            body={"values": values}
        ).execute()

        logger.info(f"Registro criado para {phone} na linha {linha} (local={local})")
        return True
    except Exception as e:
        logger.error(f"Erro ao criar registro para {phone}: {e}")
        return False


def atualizar_estado(row_number: int, etapa: str = None, local: str = None,
                     data: str = None, hora: str = None, nome: str = None) -> bool:
    """Atualiza campos do registro do paciente."""
    from datetime import datetime
    try:
        service = _get_service()
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

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
        # Sempre atualiza timestamp
        atualizacoes.append({
            "range": f"{SHEET_NAME}!G{row_number}",
            "values": [[agora]]
        })

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"valueInputOption": "USER_ENTERED", "data": atualizacoes}
        ).execute()
        logger.info(f"Estado atualizado na linha {row_number}: etapa={etapa}")
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar estado na linha {row_number}: {e}")
        return False
