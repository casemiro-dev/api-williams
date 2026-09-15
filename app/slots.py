"""Regras de grade, duração e diff livre x ocupado."""
from datetime import datetime
from zoneinfo import ZoneInfo
from . import config


def time_str_to_minutes(t: str) -> int:
    """'00:40:00' ou '00:40' -> 40."""
    parts = (t or "00:40:00").split(":")
    h = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return h * 60 + m


def minutes_to_time_str(total: int) -> str:
    return f"{total // 60:02d}:{total % 60:02d}:00"


def sum_time_required(services: list[dict]) -> str:
    """Soma time_required como o front faz (função ee)."""
    total = sum(time_str_to_minutes(s.get("time_required", "00:00:00")) for s in services)
    return minutes_to_time_str(total) if total else config.DEFAULT_TIME_REQUIRED


def now_sp() -> datetime:
    try:
        return datetime.now(ZoneInfo(config.TIMEZONE))
    except Exception:
        # Windows sem tzdata: America/Sao_Paulo = UTC-3 fixo
        from datetime import timedelta, timezone
        return datetime.now(timezone(timedelta(hours=-3)))


def weekday_to_bb_day(date_obj) -> int:
    """Python Mon=0..Sun=6 -> BestBarbers 1=Mon..7=Sun."""
    return date_obj.weekday() + 1


def get_opening_for_date(barbershop: dict, date_obj) -> dict | None:
    day = weekday_to_bb_day(date_obj)
    for o in barbershop.get("opening_hours", []) or []:
        if o.get("day") == day:
            return o
    return None


def hhmm_to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


def min_to_hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def build_grade(opening: dict, interval_min: int) -> list[str]:
    """Gera slots esperados ex: 09:00,09:40... a partir de start/close_hour."""
    if not opening or opening.get("is_closed"):
        return []
    try:
        start = hhmm_to_min(opening["start_hour"])
        end = hhmm_to_min(opening["close_hour"])
    except Exception:
        return []
    out, cur = [], start
    while cur < end:
        out.append(min_to_hhmm(cur))
        cur += interval_min
    return out


# Alias de chave de turno aceitos da API (o site usa morning/evening/night,
# mas aceitamos variantes como "afternoon" para nunca perder a grade).
TURNO_KEY_ALIASES = {
    "morning": ("morning", "manha", "morning_slots"),
    "evening": ("evening", "afternoon", "tarde"),
    "night": ("night", "noite"),
}

# Chaves de horário possíveis dentro de cada item retornado pela API.
TIME_KEYS = ("hour", "time", "time_str", "start_time", "start_hour",
             "value", "hora", "slot", "label")


def _item_hora(item) -> str | None:
    """Extrai o horário (HH:MM) de um item string ou dict, sem descartar."""
    if isinstance(item, str):
        return item[:5]
    if isinstance(item, dict):
        for k in TIME_KEYS:
            v = item.get(k)
            if v:
                return str(v)[:5]
        # nenhuma chave de tempo conhecida: preserva o valor bruto p/ não perder
        return str(item)[:5]
    return None


def normalize_slots(raw: dict, log=None) -> dict[str, list[dict]]:
    """Achata {morning, evening, night} em {turno: [{hora, barber_id}]}.

    Nunca descarta itens silenciosamente: chaves de turno desconhecidas e
    itens sem horário reconhecível são registrados (se um `log` for passado).
    """
    norm: dict[str, list[dict]] = {"morning": [], "evening": [], "night": []}
    if not raw:
        return norm
    seen = set()
    for turno, aliases in TURNO_KEY_ALIASES.items():
        for alias in aliases:
            if alias not in raw:
                continue
            for item in raw[alias] or []:
                hora = _item_hora(item)
                seen.add(item if isinstance(item, (int, str)) else repr(item))
                if hora:
                    norm[turno].append({
                        "hora": hora,
                        "barber_id": item.get("barber_id") if isinstance(item, dict) else None,
                    })
                elif log:
                    log.warning("[normalize] item sem horário preservado? turno=%s item=%r", turno, item)
    # chaves de turno que a API retornou mas não conhecemos (ex: outro nome)
    for key in raw:
        if key in {"_error"}:
            continue
        if key not in sum(TURNO_KEY_ALIASES.values(), ()):
            if log:
                log.warning("[normalize] chave de turno desconhecida ignorada: %r (n=%d)", key, len(raw[key] or []))
    return norm


def raw_counts(raw: dict) -> dict[str, int]:
    """Contagem bruta de itens por turno retornada pela API."""
    counts: dict[str, int] = {}
    if not raw:
        return counts
    for key, val in raw.items():
        if isinstance(val, (list, tuple)):
            counts[key] = len(val)
    return counts


TURNO_MAP = {
    "manha": "morning", "manhã": "morning", "morning": "morning",
    "tarde": "evening", "evening": "evening",
    "noite": "night", "night": "night",
}


def resolve_turno(turno: str | None) -> str | None:
    if not turno:
        return None
    return TURNO_MAP.get(turno.strip().lower())


def all_slots_flat(norm: dict[str, list[dict]], turno: str | None = None) -> list[dict]:
    key = resolve_turno(turno)
    turnos = [key] if key else ["morning", "evening", "night"]
    out = []
    for t in turnos:
        for s in norm.get(t, []):
            out.append({**s, "turno": t})
    return sorted(out, key=lambda x: x["hora"])


def diff_grade(grade: list[str], livres: list[str]) -> tuple[list[str], list[str]]:
    livres_set = set(livres)
    ocupados = [h for h in grade if h not in livres_set]
    return sorted(livres), ocupados


def barber_name_by_id(barbers: list[dict], bid) -> str | None:
    for b in barbers:
        if str(b.get("id")) == str(bid):
            return b.get("name")
    return None


def build_texto_ia(data: str, barbeiro_label: str, turno: str | None,
                   livres: list[dict], ocupados: list[str]) -> str:
    t = f" ({turno})" if turno else ""
    if not livres and not ocupados:
        return f"{barbeiro_label} dia {data}{t}: barbearia fechada ou sem grade."
    lv = ", ".join(
        f"{s['hora']}" + (f" com {s.get('barber_name')}" if s.get("barber_name") else "")
        for s in livres
    ) or "nenhum"
    oc = ", ".join(ocupados) or "nenhum"
    return (
        f"{barbeiro_label} dia {data}{t}: livres [{lv}]. "
        f"Ocupados/indisponíveis [{oc}]."
    )
