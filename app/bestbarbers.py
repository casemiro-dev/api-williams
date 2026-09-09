"""Cliente HTTP para a API oficial (reversa) da BestBarbers."""
import httpx
from . import config

TIMEOUT = 15.0


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=config.API_BASE, timeout=TIMEOUT)


async def get_barbershop_by_slug(slug: str | None = None) -> dict:
    async with _client() as c:
        r = await c.get(
            "/v3/client/barbershop-by-slug",
            params={"slug": slug or config.SLUG, "client_id": "undefined"},
        )
        r.raise_for_status()
        return r.json()


async def get_barbershop_data(barbershop_id: int | None = None) -> dict:
    """Retorna barbershop completo: barbers, products, opening_hours, agenda_time_interval."""
    bid = barbershop_id or config.BARBERSHOP_ID
    async with _client() as c:
        r = await c.get(
            f"/v3/client/barbershop-data/{bid}",
            params={"latitude": "-3.6773173", "longitude": "-40.3584663", "client_id": "undefined"},
        )
        r.raise_for_status()
        return r.json()


async def get_services(barbershop_id: int | None = None) -> list[dict]:
    bid = barbershop_id or config.BARBERSHOP_ID
    async with _client() as c:
        r = await c.get(f"/v3/barbershop/services/{bid}", params={"all_services": "false"})
        r.raise_for_status()
        return r.json()


async def post_available_times(payload: dict) -> dict:
    """POST /v3/appointment/available-times?type=client.

    payload = {date, currentHour, currentDate, barber_id, barbershop_id, time_required, services}
    Retorna {morning: [...], evening: [...], night: [...]} onde cada item pode ser
    string "09:40" ou dict {hour, barber_id, ...}.
    """
    async with _client() as c:
        r = await c.post(
            "/v3/appointment/available-times",
            params={"type": "client"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else {}
