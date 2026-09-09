"""Cache simples em memória com TTL + resolução de barbeiro."""
import time
from . import config

_cache: dict[str, tuple[float, object]] = {}


def cache_get(key: str):
    hit = _cache.get(key)
    if not hit:
        return None
    exp, val = hit
    if time.time() > exp:
        _cache.pop(key, None)
        return None
    return val


def cache_set(key: str, val: object, ttl: int):
    _cache[key] = (time.time() + ttl, val)


ALIASES = {
    "william": 16464, "william albuquerque": 16464,
    "moises": 37151, "moisés": 37151, "moises queiroz": 37151,
    "fabio": 16696, "fábio": 16696, "fabio azevedo": 16696,
    "sem_preferencia": "general", "sem preferencia": "general",
    "sem preferência": "general", "geral": "general", "general": "general",
    "qualquer": "general", "tanto faz": "general",
}


def resolve_barbeiro(value: str | int | None, barbers: list[dict]) -> tuple[str | int, str]:
    """Retorna (barber_id, label). Aceita ID, nome parcial ou 'sem_preferencia'."""
    if value is None or str(value).strip() == "":
        return "general", "Sem preferência"
    v = str(value).strip()
    # ID numérico direto
    if v.isdigit():
        for b in barbers:
            if str(b.get("id")) == v:
                return int(v), str(b.get("name"))
        return int(v), f"Barbeiro {v}"
    low = v.lower()
    if low in ALIASES:
        mapped = ALIASES[low]
        if mapped == "general":
            return "general", "Sem preferência"
        for b in barbers:
            if b.get("id") == mapped:
                return mapped, str(b.get("name"))
        return mapped, v
    # match parcial no nome vindo da API
    for b in barbers:
        if low in str(b.get("name", "")).lower():
            return b["id"], str(b["name"])
    # fallback: tenta IDs conhecidos
    for kb in config.KNOWN_BARBERS:
        if low in kb["name"].lower():
            return kb["id"], kb["name"]
    return "general", "Sem preferência"
