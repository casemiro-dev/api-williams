import os

# --- Configurações principais (sobrescreva via env no Easypanel) ---
SLUG = os.getenv("SLUG", "williamsbarbearia")
BARBERSHOP_ID = int(os.getenv("BARBERSHOP_ID", "12611"))
API_BASE = os.getenv("BESTBARBERS_API", "https://api.bestbarbers.app")
TIMEZONE = os.getenv("TZ", "America/Sao_Paulo")

# Serviço padrão quando o N8N não informa service_ids (Corte de cabelo 40min)
DEFAULT_SERVICE_IDS = os.getenv("DEFAULT_SERVICE_IDS", "40451")
DEFAULT_TIME_REQUIRED = os.getenv("DEFAULT_TIME_REQUIRED", "00:40:00")

# Cache TTL em segundos
CACHE_TTL_BARBERSHOP = int(os.getenv("CACHE_TTL_BARBERSHOP", "3600"))
CACHE_TTL_SERVICES = int(os.getenv("CACHE_TTL_SERVICES", "86400"))
CACHE_TTL_AVAIL = int(os.getenv("CACHE_TTL_AVAIL", "60"))

# Auth opcional: se API_KEY setada, exige header X-API-Key (exceto /health e /docs)
API_KEY = os.getenv("API_KEY", "")

# Intervalo padrão da grade (min). O valor real vem da API (agenda_time_interval).
FALLBACK_INTERVAL_MIN = int(os.getenv("AGENDA_INTERVAL", "40"))
MAX_RANGE_DAYS = int(os.getenv("MAX_RANGE_DAYS", "14"))

# Mapa de barbeiros conhecidos (fallback se API falhar).
# IDs reais validados em 09/09/2026 via /barbershop-data/12611.
KNOWN_BARBERS = [
    {"id": 16464, "name": "William Albuquerque"},
    {"id": 37151, "name": "Moises Queiroz"},
    {"id": 16696, "name": "Fabio Azevedo"},
]
