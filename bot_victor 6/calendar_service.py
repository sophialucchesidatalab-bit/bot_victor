import logging
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import CALENDAR_COPA, CALENDAR_MEIER, CALENDAR_ONLINE
import os, json

logger = logging.getLogger(__name__)

SCOPES_CAL = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Duração por local (em minutos)
DURACAO_POR_LOCAL = {
    "copa":   120,  # 2 horas
    "meier":   90,  # 1h30
    "online":  90,  # 1h30
}

# Dias de atendimento: 2=Qua, 3=Qui, 4=Sex, 5=Sáb
DIAS_ATENDIMENTO = [2, 3, 4, 5]

# Horário de início e fim por dia
# Seg-Sex: 08:00 às 20:00 (slots gerados dinamicamente de acordo com duração)
# Sáb: 08:30 às 12:00
HORARIO_INICIO_SEMANA = (8, 0)    # 08:00
HORARIO_FIM_SEMANA    = (20, 0)   # 20:00
HORARIO_INICIO_SABADO = (8, 30)   # 08:30
HORARIO_FIM_SABADO    = (12, 0)   # 12:00 — última consulta deve TERMINAR até 12h

TURNOS = {
    "manha":  ("06:00", "12:00"),
    "tarde":  ("12:00", "18:00"),
    "noite":  ("18:00", "22:00"),
}

NOMES_LOCAL = {
    "copa":   "Copacabana (Integra Saúde)",
    "meier":  "Méier (Max Fit)",
    "online": "Online (Google Meet / WhatsApp Vídeo)",
}


def _get_calendar_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON nao configurado")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES_CAL)
    return build("calendar", "v3", credentials=creds)


def _normalizar_local(local: str) -> str:
    l = local.lower()
    if "copa" in l:                                  return "copa"
    if "meier" in l or "méier" in l or "meir" in l: return "meier"
    return "online"


def _get_calendar_ids(local_key: str) -> list:
    """
    Copa   → agenda Copacabana
    Méier  → agenda MaxFit
    Online → AMBAS as agendas físicas (Victor precisa estar livre nos dois)
    """
    if local_key == "copa":
        return [c for c in [CALENDAR_COPA] if c]
    elif local_key == "meier":
        return [c for c in [CALENDAR_MEIER] if c]
    else:
        return [c for c in [CALENDAR_COPA, CALENDAR_MEIER, CALENDAR_ONLINE] if c]


def _gerar_slots_dia(dia: datetime, local_key: str) -> list:
    """
    Gera todos os slots possíveis para um dia, respeitando:
    - Sábado: início 08:30, último slot deve TERMINAR até 12:00
    - Dias úteis: início 08:00, fim 20:00
    - Duração varia por local (Copa 2h, Méier/Online 1h30)
    Retorna lista de datetime (início de cada slot)
    """
    duracao = DURACAO_POR_LOCAL.get(local_key, 90)
    eh_sabado = dia.weekday() == 5

    if eh_sabado:
        h_ini, m_ini = HORARIO_INICIO_SABADO
        h_fim, m_fim = HORARIO_FIM_SABADO
    else:
        h_ini, m_ini = HORARIO_INICIO_SEMANA
        h_fim, m_fim = HORARIO_FIM_SEMANA

    inicio = dia.replace(hour=h_ini, minute=m_ini, second=0, microsecond=0)
    # Fim: o slot deve TERMINAR até o horário de fim
    limite_inicio = dia.replace(hour=h_fim, minute=m_fim, second=0, microsecond=0) - timedelta(minutes=duracao)

    slots = []
    cur = inicio
    while cur <= limite_inicio:
        slots.append(cur)
        cur += timedelta(minutes=duracao)

    return slots


def _eventos_ocupados_calendario(calendar_id: str,
                                  data_inicio: datetime,
                                  data_fim: datetime) -> list:
    """
    Retorna lista de tuplas (dt_inicio, dt_fim) dos eventos existentes.
    """
    if not calendar_id:
        return []
    try:
        service = _get_calendar_service()
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=data_inicio.isoformat() + "Z",
            timeMax=data_fim.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        resultado = []
        for event in events.get("items", []):
            start = event["start"].get("dateTime", event["start"].get("date"))
            end   = event["end"].get("dateTime",   event["end"].get("date"))
            if "T" in start and "T" in end:
                dt_s = datetime.fromisoformat(start.replace("Z", "+00:00")) - timedelta(hours=3)
                dt_e = datetime.fromisoformat(end.replace("Z",   "+00:00")) - timedelta(hours=3)
                resultado.append((dt_s, dt_e))
        return resultado
    except Exception as e:
        logger.error(f"Erro ao buscar eventos do calendário {calendar_id}: {e}")
        return []


def _slot_esta_livre(slot_inicio: datetime, slot_fim: datetime,
                      eventos: list) -> bool:
    """Verifica se um slot (inicio, fim) não conflita com nenhum evento."""
    for ev_ini, ev_fim in eventos:
        # Conflito se os intervalos se sobrepõem
        if slot_inicio < ev_fim and slot_fim > ev_ini:
            return False
    return True


def _dias_com_evento(eventos: list) -> set:
    """Retorna set de strings 'DD/MM' que têm pelo menos um evento."""
    return {ev_ini.strftime("%d/%m") for ev_ini, _ in eventos}


def buscar_horarios_disponiveis(local: str, turno: str, dias_frente: int = 21) -> str:
    """
    Busca horários livres respeitando:
    - Duração real por local (Copa 2h, Méier/Online 1h30)
    - Slots gerados dinamicamente — o próximo slot após um ocupado
      começa exatamente após o fim do anterior
    - Sábado inicia às 08:30, termina às 12:00
    - Qua a Sex: 08:00 às 20:00
    - Sem conflito entre consultórios no mesmo dia
    """
    local_key  = _normalizar_local(local)
    turno_norm = turno.lower().strip()
    duracao    = DURACAO_POR_LOCAL.get(local_key, 90)

    if "manh" in turno_norm:    turno_key = "manha"
    elif "tarde" in turno_norm: turno_key = "tarde"
    elif "noite" in turno_norm: turno_key = "noite"
    else:                        turno_key = None

    turno_ini, turno_fim = TURNOS.get(turno_key, ("06:00", "22:00")) if turno_key else ("06:00", "22:00")

    # Busca eventos de TODOS os calendários relevantes
    ids_principal = _get_calendar_ids(local_key)
    # Para anti-conflito entre consultórios
    ids_cruzado = []
    if local_key == "copa":
        ids_cruzado = [c for c in [CALENDAR_MEIER] if c]
    elif local_key == "meier":
        ids_cruzado = [c for c in [CALENDAR_COPA] if c]

    agora   = datetime.now()
    fim_per = agora + timedelta(days=dias_frente)

    # Coleta eventos do local principal
    eventos_principal = []
    for cal_id in ids_principal:
        eventos_principal += _eventos_ocupados_calendario(cal_id, agora, fim_per)

    # Coleta dias com evento no outro consultório (anti-conflito)
    eventos_cruzado = []
    for cal_id in ids_cruzado:
        eventos_cruzado += _eventos_ocupados_calendario(cal_id, agora, fim_per)
    dias_bloqueados_cruzado = _dias_com_evento(eventos_cruzado)

    # Gera slots disponíveis
    slots = []
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    dia = agora + timedelta(days=1)
    dia = dia.replace(hour=0, minute=0, second=0, microsecond=0)

    while len(slots) < 8 and dia.date() < fim_per.date():
        if dia.weekday() in DIAS_ATENDIMENTO:
            dia_str  = dia.strftime("%d/%m")
            dia_nome = dias_semana[dia.weekday()]

            # Bloqueia se há consulta em outro consultório no mesmo dia
            if dia_str in dias_bloqueados_cruzado:
                dia += timedelta(days=1)
                continue

            slots_dia = _gerar_slots_dia(dia, local_key)

            for slot_ini in slots_dia:
                slot_fim = slot_ini + timedelta(minutes=duracao)

                # Filtro de turno
                hora_str = slot_ini.strftime("%H:%M")
                if not (turno_ini <= hora_str <= turno_fim):
                    continue

                # Verifica se está no futuro
                if slot_ini <= agora:
                    continue

                # Verifica disponibilidade
                if _slot_esta_livre(slot_ini, slot_fim, eventos_principal):
                    slots.append(f"• {dia_str} ({dia_nome}) às {hora_str}")

                if len(slots) >= 8:
                    break

        dia += timedelta(days=1)

    nome_local  = NOMES_LOCAL.get(local_key, local)
    turno_disp  = {"manha": "manhã", "tarde": "tarde", "noite": "noite"}.get(turno_key, "")
    duracao_txt = "2 horas" if duracao == 120 else "1h30"

    if not slots:
        return (
            f"Poxa, não encontrei horários disponíveis em *{nome_local}* "
            f"nos próximos dias para esse turno. 😕\n\n"
            "Que tal tentar outro turno?\n🌅 Manhã   ☀️ Tarde   🌙 Noite"
        )

    texto = f"📅 *Horários disponíveis — {nome_local}*"
    if turno_disp:
        texto += f" ({turno_disp})"
    texto += f"\n_(duração: {duracao_txt} por consulta)_\n\n"
    texto += "\n".join(slots)
    texto += "\n\nQual horário você prefere? 😊\n_(Responda com data e horário, ex: 25/04 às 08:00)_"
    return texto


def criar_evento_agenda(local: str, paciente_nome: str, paciente_phone: str,
                         data_hora_str: str) -> bool:
    """
    Cria evento no Google Agenda com duração correta por local.
    Copa = 2h | Méier/Online = 1h30
    data_hora_str: 'DD/MM às HH:MM' ou 'DD/MM/AAAA às HH:MM'
    """
    local_key    = _normalizar_local(local)
    duracao      = DURACAO_POR_LOCAL.get(local_key, 90)
    calendar_ids = _get_calendar_ids(local_key)
    if not calendar_ids:
        logger.warning(f"Nenhum calendário configurado para {local_key}")
        return False

    calendar_id = calendar_ids[0]

    try:
        limpo  = data_hora_str.replace("às", "").replace("as", "")
        partes = [p for p in limpo.split() if p]
        data_s = partes[0]
        hora_s = partes[-1]

        p   = data_s.split("/")
        dia = int(p[0]); mes = int(p[1])
        ano = int(p[2]) if len(p) > 2 else datetime.now().year
        hora, minuto = map(int, hora_s.replace("h", ":").split(":"))

        # BRT (UTC-3) → UTC (+3)
        dt_inicio = datetime(ano, mes, dia, hora, minuto) + timedelta(hours=3)
        dt_fim    = dt_inicio + timedelta(minutes=duracao)

        service    = _get_calendar_service()
        nome_local = NOMES_LOCAL.get(local_key, local)
        duracao_txt = "2 horas" if duracao == 120 else "1h30"

        event = {
            "summary": f"Consulta — {paciente_nome}",
            "description": (
                f"Paciente: {paciente_nome}\n"
                f"WhatsApp: {paciente_phone}\n"
                f"Local: {nome_local}\n"
                f"Duração: {duracao_txt}\n"
                f"Agendado via bot WhatsApp"
            ),
            "start": {"dateTime": dt_inicio.isoformat() + "Z", "timeZone": "America/Sao_Paulo"},
            "end":   {"dateTime": dt_fim.isoformat()    + "Z", "timeZone": "America/Sao_Paulo"},
        }
        service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"Evento {duracao_txt} criado para {paciente_nome} em {data_hora_str} — {nome_local}")
        return True
    except Exception as e:
        logger.error(f"Erro ao criar evento: {e}")
        return False
