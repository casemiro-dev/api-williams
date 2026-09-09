from fastapi import APIRouter, Query
from .. import bestbarbers, config
from ..store import cache_get, cache_set

router = APIRouter(tags=["meta"])


async def _barbershop_data() -> dict:
    key = f"bb:data:{config.BARBERSHOP_ID}"
    hit = cache_get(key)
    if hit:
        return hit
    data = await bestbarbers.get_barbershop_data()
    cache_set(key, data, config.CACHE_TTL_BARBERSHOP)
    return data


@router.get("/info")
async def info():
    data = await _barbershop_data()
    bb = data.get("barbershop", {})
    return {
        "id": bb.get("id"),
        "name": bb.get("name"),
        "slug": bb.get("slug"),
        "phone": bb.get("phone"),
        "timezone": bb.get("timezone"),
        "agenda_time_interval": bb.get("agenda_time_interval"),
        "maximum_schedule_date": bb.get("maximum_schedule_date"),
        "opening_hours": bb.get("opening_hours"),
    }


@router.get("/barbers")
async def barbers():
    """3 barbeiros + aba Sem preferência (id=general), igual ao site."""
    data = await _barbershop_data()
    bb = data.get("barbershop", {})
    out = [
        {"id": b.get("id"), "name": b.get("name"),
         "profile_image_url": b.get("profile_image_url")}
        for b in (bb.get("barbers") or []) if b.get("visible_for_clients", True)
    ]
    if not out:  # fallback
        out = [{"id": b["id"], "name": b["name"], "profile_image_url": None}
               for b in config.KNOWN_BARBERS]
    out.append({"id": "general", "name": "Sem preferência",
                "profile_image_url": None, "without_preference": True})
    return {"barbershop_id": bb.get("id", config.BARBERSHOP_ID), "barbers": out}


@router.get("/services")
async def services(
    only_normal: bool = Query(True, description="Só type=normal (agendáveis no site)"),
):
    key = f"bb:services:{config.BARBERSHOP_ID}:{only_normal}"
    hit = cache_get(key)
    if hit:
        return hit
    data = await _barbershop_data()
    prods = (data.get("barbershop", {}).get("products") or [])
    if only_normal:
        prods = [p for p in prods if (p.get("type") or "normal") == "normal"]
    payload = {"barbershop_id": config.BARBERSHOP_ID, "services": [
        {"id": p.get("id"), "name": p.get("name"),
         "time_required": p.get("time_required"), "price": p.get("price")}
        for p in prods
    ]}
    cache_set(key, payload, config.CACHE_TTL_SERVICES)
    return payload
