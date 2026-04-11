"""
sheets_agenda.py
Acesso à planilha de horários disponíveis (Agenda Nutri Victor).
Separado do sheets.py (Bot_estado) para não misturar responsabilidades.

Planilha: Agenda Nutri Victor
ID: 1-5d-Rt2m8aaHR6uXtuEYfy__CxdS3IJBzOMsNUePIlU
Aba de leitura:  Horarios_Disponiveis
Colunas: Data | Dia | Local | Hora Início | Hora Fim
"""

import logging
import os
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

AGENDA_SPREADSHEET_ID = os.getenv(
    "AGENDA_SPREADSHEET_ID",
    "1-5d-Rt2m8aaHR6uXtuEYfy__CxdS3IJBzOMsNUePIlU"
)
ABA_HORARIOS = "Horarios_Disponiveis"

# Turnos por faixa de horário de início
TURNO_MANHA = range(0,   12 * 60)       # até 11:59
TURNO_TARDE = range(12 * 60, 18 * 60)   # 12:00 – 17:59
TURNO_NOITE = range(18 * 60, 24 * 60)   # 18:00 – 23:59

# Mapeamento local do bot → nome na planilha
LOCAL_MAP = {
    "Copacabana": "Copa",
    "Méier":      "Méier",
    "Online":     "Online",
}


def _get_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON nao configurado")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _hora_para_min(hora_str: str) -> int:
    """Converte 'HH:MM' em minutos desde meia-noite."""
    try:
        h, m = hora_str.strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def _turno_do_horario(hora_str: str) -> str:
    """Retorna 'Manhã', 'Tarde' ou 'Noite' dado um horário 'HH:MM'."""
    minutos = _hora_para_min(hora_str)
    if minutos in TURNO_MANHA:
        return "Manhã"
    if minutos in TURNO_TARDE:
        return "Tarde"
    return "Noite"


def _calcular_janela_datas() -> tuple[set, set]:
    """
    Calcula quais datas exibir ao lead: sempre 2 semanas com slots.

    Semana Victor = Qua–Sáb.

    Retorna (datas_semana1, datas_semana2) como conjuntos de strings "DD/MM/AAAA".
    A semana1 é a atual se ainda tiver dias futuros (Qua–Sáb >= hoje),
    caso contrário é a próxima. Semana2 é sempre a seguinte à semana1.
    """
    from datetime import date, timedelta

    hoje = date.today()
    dia_semana = hoje.weekday()  # 0=seg … 6=dom

    # Mapeia weekday Python para os dias Victor (Qua=2, Qui=3, Sex=4, Sáb=5)
    DIAS_VICTOR = {2, 3, 4, 5}

    # Encontra a próxima Quarta-feira (ou hoje se for Qua)
    dias_ate_qua = (2 - dia_semana) % 7  # 2 = Wednesday
    qua_atual = hoje + timedelta(days=dias_ate_qua)

    # Se já passou do Sábado desta semana, começa na próxima Quarta
    sab_atual = qua_atual + timedelta(days=3)
    if hoje > sab_atual:
        qua_atual += timedelta(weeks=1)
        sab_atual = qua_atual + timedelta(days=3)

    # Semana 1: Qua–Sáb da semana atual (só dias APÓS hoje — nunca inclui hoje)
    semana1 = set()
    for i in range(4):  # Qua, Qui, Sex, Sáb
        d = qua_atual + timedelta(days=i)
        if d > hoje:
            semana1.add(d.strftime("%d/%m/%Y"))

    # Semana 2: Qua–Sáb da semana seguinte
    qua_prox = qua_atual + timedelta(weeks=1)
    semana2 = set()
    for i in range(4):
        d = qua_prox + timedelta(days=i)
        semana2.add(d.strftime("%d/%m/%Y"))

    return semana1, semana2


def buscar_horarios(local_bot: str, turno: str) -> list[dict]:
    """
    Retorna slots disponíveis para o local e turno pedidos,
    limitados às 2 próximas semanas (Qua–Sáb):

    - Semana atual: se ainda tiver dias com slots >= hoje
    - Semana seguinte: sempre incluída
    - Se semana atual não tiver slots: avança para semana seguinte + a outra

    Parâmetros:
        local_bot: "Copacabana", "Méier" ou "Online"
        turno:     "Manhã", "Tarde" ou "Noite"
    """
    from datetime import timedelta
    local_planilha = LOCAL_MAP.get(local_bot, local_bot)

    try:
        service = _get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=AGENDA_SPREADSHEET_ID,
            range=f"{ABA_HORARIOS}!A:E"
        ).execute()
        rows = result.get("values", [])

        semana1_datas, semana2_datas = _calcular_janela_datas()
        datas_validas = semana1_datas | semana2_datas

        # Filtra todos os slots dentro da janela
        slots_semana1 = []
        slots_semana2 = []

        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue
            data, dia, local_linha, hora_ini, hora_fim = (
                row[0].strip(), row[1].strip(), row[2].strip(),
                row[3].strip(), row[4].strip()
            )

            if local_linha != local_planilha:
                continue
            if data not in datas_validas:
                continue
            if _turno_do_horario(hora_ini) != turno:
                continue

            slot = {
                "data":        data,
                "dia":         dia,
                "local":       local_linha,
                "hora_inicio": hora_ini,
                "hora_fim":    hora_fim,
                "row_index":   i,
            }

            if data in semana1_datas:
                slots_semana1.append(slot)
            else:
                slots_semana2.append(slot)

        # Se semana1 não tem nada → avança: semana2 vira semana1, calcula nova semana2
        if not slots_semana1 and slots_semana2:
            logger.info("buscar_horarios: semana atual sem slots — avançando janela")

            # Recalcula: a "nova semana2" é a semana após semana2
            from datetime import date, timedelta
            # Pega qualquer data da semana2 para calcular a próxima
            data_ref_str = list(semana2_datas)[0]
            d, m, a = data_ref_str.split("/")
            data_ref = date(int(a), int(m), int(d))
            # Próxima quarta após semana2
            dias_ate_qua = (2 - data_ref.weekday()) % 7
            if dias_ate_qua == 0:
                dias_ate_qua = 7
            qua_nova = data_ref + timedelta(days=dias_ate_qua)

            nova_semana2_datas = set()
            for i in range(4):
                d_nova = qua_nova + timedelta(days=i)
                nova_semana2_datas.add(d_nova.strftime("%d/%m/%Y"))

            # Busca slots da nova semana2 na planilha
            slots_nova_semana2 = []
            for i, row in enumerate(rows[1:], start=2):
                if len(row) < 5:
                    continue
                data, dia, local_linha, hora_ini, hora_fim = (
                    row[0].strip(), row[1].strip(), row[2].strip(),
                    row[3].strip(), row[4].strip()
                )
                if local_linha != local_planilha:
                    continue
                if data not in nova_semana2_datas:
                    continue
                if _turno_do_horario(hora_ini) != turno:
                    continue
                slots_nova_semana2.append({
                    "data": data, "dia": dia, "local": local_linha,
                    "hora_inicio": hora_ini, "hora_fim": hora_fim, "row_index": i,
                })

            slots_final = slots_semana2 + slots_nova_semana2
        else:
            slots_final = slots_semana1 + slots_semana2

        logger.info(f"buscar_horarios: {len(slots_final)} slots para {local_bot} / {turno}")
        return slots_final

    except Exception as e:
        logger.error(f"Erro ao buscar horários: {e}")
        return []


def remover_horario_confirmado(
    local_bot: str,
    data_confirmada: str,
    hora_confirmada: str,
    duracao_min: int
) -> int:
    """
    Remove da aba Horarios_Disponiveis após confirmação de agendamento.

    Regras aplicadas no mesmo dia:
    - Méier agendado  → remove Méier e Online que conflitam + 5h de brecha antes/depois
    - Copa agendado   → remove Copa que conflita + remove Méier dentro de 4h + Online dentro de 3h
    - Online agendado → remove Online que conflita + remove Méier e Copa dentro de 4h e 3h respectivamente

    Brechas:
    - Méier ↔ Online: 5h (300 min)  — após agendamento confirmado
    - Méier ↔ Copa:   4h (240 min)
    - Copa  ↔ Online: 3h (180 min)
    """
    BRECHA_MEIER_ONLINE = 300  # 5h
    BRECHA_MEIER_COPA   = 240  # 4h
    BRECHA_COPA_ONLINE  = 180  # 3h

    local_planilha = LOCAL_MAP.get(local_bot, local_bot)
    ini_ocupado = _hora_para_min(hora_confirmada)
    fim_ocupado = ini_ocupado + duracao_min
    data_limpa  = data_confirmada.strip()

    try:
        service = _get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=AGENDA_SPREADSHEET_ID,
            range=f"{ABA_HORARIOS}!A:E"
        ).execute()
        rows = result.get("values", [])

        linhas_remover = []

        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue
            data_linha  = row[0].strip()
            local_linha = row[2].strip()
            hora_ini    = row[3].strip()
            hora_fim    = row[4].strip()

            # Só processa slots do mesmo dia
            if data_linha != data_limpa:
                continue

            ini_slot = _hora_para_min(hora_ini)
            fim_slot = _hora_para_min(hora_fim)

            deve_remover = False

            # ── Conflito direto com o local agendado ─────────────────────────
            if local_linha == local_planilha:
                if ini_slot < fim_ocupado and fim_slot > ini_ocupado:
                    deve_remover = True

            # ── Brechas por combinação de locais ─────────────────────────────
            if local_bot == "Méier":
                # Méier agendado → brecha 5h para Online
                if local_linha == "Online":
                    if not (fim_slot + BRECHA_MEIER_ONLINE <= ini_ocupado or
                            fim_ocupado + BRECHA_MEIER_ONLINE <= ini_slot):
                        deve_remover = True

            elif local_bot == "Copacabana":
                # Copa agendado → brecha 4h para Méier
                if local_linha == "Méier":
                    if not (fim_slot + BRECHA_MEIER_COPA <= ini_ocupado or
                            fim_ocupado + BRECHA_MEIER_COPA <= ini_slot):
                        deve_remover = True
                # Copa agendado → brecha 3h para Online
                if local_linha == "Online":
                    if not (fim_slot + BRECHA_COPA_ONLINE <= ini_ocupado or
                            fim_ocupado + BRECHA_COPA_ONLINE <= ini_slot):
                        deve_remover = True

            elif local_bot == "Online":
                # Online agendado → brecha 5h para Méier
                if local_linha == "Méier":
                    if not (fim_slot + BRECHA_MEIER_ONLINE <= ini_ocupado or
                            fim_ocupado + BRECHA_MEIER_ONLINE <= ini_slot):
                        deve_remover = True
                # Online agendado → brecha 3h para Copa
                if local_linha == "Copa":
                    if not (fim_slot + BRECHA_COPA_ONLINE <= ini_ocupado or
                            fim_ocupado + BRECHA_COPA_ONLINE <= ini_slot):
                        deve_remover = True

            if deve_remover:
                linhas_remover.append(i)

        if not linhas_remover:
            logger.info("remover_horario_confirmado: nenhuma linha para remover")
            return 0

        # Remove de baixo para cima para não deslocar índices
        linhas_remover = sorted(set(linhas_remover), reverse=True)
        sheet_id = _get_sheet_id(service, AGENDA_SPREADSHEET_ID, ABA_HORARIOS)

        requests = []
        for linha in linhas_remover:
            requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId":    sheet_id,
                        "dimension":  "ROWS",
                        "startIndex": linha - 1,
                        "endIndex":   linha,
                    }
                }
            })

        service.spreadsheets().batchUpdate(
            spreadsheetId=AGENDA_SPREADSHEET_ID,
            body={"requests": requests}
        ).execute()

        logger.info(f"remover_horario_confirmado: {len(linhas_remover)} linhas removidas "
                    f"(local={local_bot}, data={data_confirmada}, hora={hora_confirmada})")
        return len(linhas_remover)

    except Exception as e:
        logger.error(f"Erro ao remover horário confirmado: {e}")
        return 0


def _get_sheet_id(service, spreadsheet_id: str, sheet_name: str) -> int:
    """Retorna o sheetId numérico de uma aba pelo nome."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            return props.get("sheetId", 0)
    raise ValueError(f"Aba '{sheet_name}' não encontrada na planilha")


def buscar_todos_slots_sabado(local_bot: str) -> list[dict]:
    """
    Busca todos os slots de sábado disponíveis para o local,
    sem restrição de turno e sem limite de 2 semanas.
    Usado quando o lead pergunta "tem sábado?" e não há sábado
    nas próximas 2 semanas — mostra o sábado mais próximo disponível.
    Retorna lista ordenada por data.
    """
    local_planilha = LOCAL_MAP.get(local_bot, local_bot)

    try:
        service = _get_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=AGENDA_SPREADSHEET_ID,
            range=f"{ABA_HORARIOS}!A:E"
        ).execute()
        rows = result.get("values", [])

        from datetime import date
        hoje = date.today()

        slots_sab = []
        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 5:
                continue
            data_str  = row[0].strip()
            dia_str   = row[1].strip()
            local_str = row[2].strip()
            hora_ini  = row[3].strip()
            hora_fim  = row[4].strip()

            if local_str != local_planilha:
                continue
            if dia_str != "Sáb":
                continue

            # Só datas futuras
            try:
                d, m, a = data_str.split("/")
                data_slot = date(int(a), int(m), int(d))
                if data_slot <= hoje:
                    continue
            except Exception:
                continue

            slots_sab.append({
                "data":        data_str,
                "dia":         dia_str,
                "local":       local_str,
                "hora_inicio": hora_ini,
                "hora_fim":    hora_fim,
                "row_index":   i,
            })

        # Ordena por data
        slots_sab.sort(key=lambda s: (
            int(s["data"].split("/")[2]),
            int(s["data"].split("/")[1]),
            int(s["data"].split("/")[0])
        ))

        logger.info(f"buscar_todos_slots_sabado: {len(slots_sab)} slots para {local_bot}")
        return slots_sab

    except Exception as e:
        logger.error(f"Erro ao buscar slots sábado: {e}")
        return []
