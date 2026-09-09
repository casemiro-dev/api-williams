import asyncio
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from .. import bestbarbers, config, slots
from ..store import cache_get, cache_set, resolve_barbeiro

router = APIRouter(tags=["availability"])


async def _ctx():
    """Carrega barbershop + services com cache."""
    key = f"bb:data:{config.BARBERSHOP_ID}"
    data = cache_get(key)
    if not data:
        data = await bestbarbers.get_barbershop_data()
        cache_set(key, data, config.CACHE_TTL_BARBERSHOP)
    bb = data.get("barbershop", {})
    barbers = [b for b in (bb.get("barbers") or []) if b.get("visible_for_clients", True)]
    if not barbers:
        barbers = [{"id": b["id"], "name": b["name"], "visible_for_clients": True}
                   for b in config.KNOWN_BARBERS]
    products = bb.get("products") or []
    return bb, barbers, products


def _parse_date(s: str) -> date:
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Use date=YYYY-MM-DD")
    today = slots.now_sp().date()
    if d < today:
        raise HTTPException(400, "Data no passado. Use hoje em diante.")
    if (d - today).days > 30:
        raise HTTPException(400, "Limite de 30 dias à frente.")
    return d


def _service_filter(products: list[dict], ids: list[int]) -> tuple[list[dict], str]:
    if not ids:
        ids = [int(x) for x in str(config.DEFAULT_SERVICE_IDS).split(",") if x.strip().isdigit()]
    sel = [p for p in products if p.get("id") in ids]
    # se ID não está no barbershop-data (ex: produto novo), busca no endpoint services
    missing = [i for i in ids if i not in {p.get("id") for p in sel}]
    total = slots.minutes_to_time_str(
        sum(slots.time_str_to_minutes(p.get("time_required", "00:40:00")) for p in sel)
        or slots.time_str_to_minutes(config.DEFAULT_TIME_REQUIRED)
    )
    return sel, total, missing


async def _fetch_one(d: date, barber_id, time_required: str, service_ids: list[int],
                     bb_id: int) -> dict:
    now = slots.now_sp()
    payload = {
        "date": d.isoformat(),
        "currentHour": now.strftime("%H:%M"),
        "currentDate": now.strftime("%Y-%m-%d"),
        "barber_id": barber_id,
        "barbershop_id": bb_id,
        "time_required": time_required,
        "services": service_ids,
    }
    try:
        return await bestbarbers.post_available_times(payload)
    except Exception as e:
        return {"_error": str(e), "morning": [], "evening": [], "night": []}


def _enrich(chunk: list[dict], barbers: list[dict]) -> list[dict]:
    out = []
    for s in chunk:
        bid = s.get("barber_id")
        out.append({
            "hora": s["hora"],
            "turno": s.get("turno"),
            "barber_id": bid,
            "barber_name": slots.barber_name_by_id(barbers, bid) if bid else None,
        })
    return out


async def _availability_core(date_s: str, barbeiro: str | None,
                             service_ids: list[int], turno: str | None) -> dict:
    bb, barbers, products = await _ctx()
    d = _parse_date(date_s)
    bid, label = resolve_barbeiro(barbeiro, barbers)
    sel, time_required, _ = _service_filter(products, service_ids)
    interval = int(bb.get("agenda_time_interval") or config.FALLBACK_INTERVAL_MIN)
    opening = slots.get_opening_for_date(bb, d)
    grade = slots.build_grade(opening or {}, interval)

    # turno filtra a grade por faixa de hora (manhã 00-12, tarde 12-18, noite 18-24)
    # além das chaves morning/evening/night da API.
    tkey = slots.resolve_turno(turno)
    grade_f = grade
    if tkey == "morning":
        grade_f = [h for h in grade if h < "12:00"]
    elif tkey == "evening":
        grade_f = [h for h in grade if "12:00" <= h < "18:00"]
    elif tkey == "night":
        grade_f = [h for h in grade if h >= "18:00"]

    cache_key = f"av:{d}:{bid}:{time_required}:{turno}:{config.BARBERSHOP_ID}"
    hit = cache_get(cache_key)
    if hit:
        return hit

    raw = await _fetch_one(d, bid, time_required, service_ids or
                           [int(x) for x in str(config.DEFAULT_SERVICE_IDS).split(",") if x.strip().isdigit()],
                           bb.get("id", config.BARBERSHOP_ID))

    # Fallback sem-preferência: se barber_id=general vazio/erro, fan-out nos 3
    if bid == "general":
        flat_try = slots.all_slots_flat(slots.normalize_slots(raw), turno)
        if not flat_try and not raw.get("_error"):
            results = await asyncio.gather(*[
                _fetch_one(d, b["id"], time_required,
                           service_ids or [int(x) for x in str(config.DEFAULT_SERVICE_IDS).split(",") if x.strip().isdigit()],
                           bb.get("id", config.BARBERSHOP_ID))
                for b in barbers if str(b.get("id")).isdigit()
            ])
            merged: dict[str, dict] = {}
            for b, r in zip(barbers, results):
                for s in slots.all_slots_flat(slots.normalize_slots(r), turno):
                    merged.setdefault(s["hora"], {"hora": s["hora"], "turno": s.get("turno"),
                                                  "barber_id": b["id"], "barber_name": b.get("name")})
            livres = sorted(merged.values(), key=lambda x: x["hora"])
            livres_h = [x["hora"] for x in livres]
            _, ocup = slots.diff_grade(grade_f, livres_h)
            resp = {"data": d.isoformat(), "barbeiro": label, "barber_id": "general",
                    "turno": turno, "time_required": time_required,
                    "services": [{"id": p.get("id"), "name": p.get("name")} for p in sel],
                    "disponiveis": livres, "indisponiveis": ocup,
                    "total_livre": len(livres), "total_ocupado": len(ocup),
                    "texto_ia": slots.build_texto_ia(d.isoformat(), label, turno, livres, ocup)}
            cache_set(cache_key, resp, config.CACHE_TTL_AVAIL)
            return resp

    norm = slots.normalize_slots(raw)
    flat = slots.all_slots_flat(norm, turno)
    livres = _enrich(flat, barbers)
    # completa nome quando consulta é de barbeiro específico
    if bid != "general":
        for s in livres:
            s["barber_id"] = bid if s.get("barber_id") is None else s["barber_id"]
            s["barber_name"] = s.get("barber_name") or label
    livres_h = [x["hora"] for x in livres]
    _, ocup = slots.diff_grade(grade_f, livres_h)
    resp = {"data": d.isoformat(), "barbeiro": label, "barber_id": bid,
            "turno": turno, "time_required": time_required,
            "services": [{"id": p.get("id"), "name": p.get("name")} for p in sel],
            "disponiveis": livres, "indisponiveis": ocup,
            "total_livre": len(livres), "total_ocupado": len(ocup),
            "texto_ia": slots.build_texto_ia(d.isoformat(), label, turno, livres, ocup)}
    cache_set(cache_key, resp, config.CACHE_TTL_AVAIL)
    return resp


def _parse_ids(s: str | None) -> list[int]:
    if not s:
        return []
    return [int(x) for x in s.split(",") if x.strip().isdigit()]


@router.get("/availability")
async def availability(
    date: str = Query(..., description="YYYY-MM-DD"),
    barbeiro: str = Query("sem_preferencia", description="nome, id ou sem_preferencia"),
    service_ids: str = Query("", description="IDs separados por vírgula, ex 40451,41271"),
    turno: str | None = Query(None, description="manha|tarde|noite"),
):
    return await _availability_core(date, barbeiro, _parse_ids(service_ids), turno)


@router.get("/availability/all")
async def availability_all(
    date: str = Query(..., description="YYYY-MM-DD"),
    service_ids: str = Query("", description="IDs separados por vírgula"),
    turno: str | None = Query(None, description="manha|tarde|noite"),
):
    """Os 3 barbeiros + sem preferência de uma vez (ideal p/ IA comparar)."""
    bb, barbers, _ = await _ctx()
    ids = _parse_ids(service_ids)
    targets = [str(b["id"]) for b in barbers if str(b.get("id")).isdigit()] + ["general"]
    out = {}
    for t in targets:
        try:
            out[t] = await _availability_core(date, t, ids, turno)
        except HTTPException as e:
            out[t] = {"error": e.detail}
    # atalho sem_preferencia
    out["sem_preferencia"] = out.pop("general", {})
    return {"data": date, "turno": turno, "resultado": out}


@router.get("/availability/range")
async def availability_range(
    start: str = Query(..., description="YYYY-MM-DD inicial"),
    days: int = Query(7, ge=1, le=14, description="1-14 dias"),
    barbeiro: str = Query("sem_preferencia"),
    service_ids: str = Query(""),
    turno: str | None = Query(None),
):
    d0 = _parse_date(start)
    ids = _parse_ids(service_ids)
    dias = []
    for i in range(days):
        di = (d0 + timedelta(days=i)).isoformat()
        try:
            r = await _availability_core(di, barbeiro, ids, turno)
        except HTTPException as e:
            r = {"data": di, "error": e.detail}
        dias.append(r)
    return {"barbeiro": barbeiro, "turno": turno, "dias": dias}


@router.get("/ai/context")
async def ai_context(
    date: str = Query(..., description="YYYY-MM-DD"),
    service_ids: str = Query(""),
    turno: str | None = Query(None),
):
    """Texto pronto para o agente IA do N8N responder no WhatsApp."""
    data = await availability_all(date=date, service_ids=service_ids, turno=turno)
    blocos = []
    for k, v in data["resultado"].items():
        if isinstance(v, dict) and "texto_ia" in v:
            blocos.append(v["texto_ia"])
    return {"data": date, "turno": turno, "texto": "\n".join(blocos), "detalhe": data["resultado"]}
