import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from . import config
from .routers import meta, availability

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL, logging.INFO),
                    format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

app = FastAPI(title="API Williams Barbearia", version="1.0.0",
              description="Horários livres/ocupados (BestBarbers) para N8N/IA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if config.API_KEY and not request.url.path.startswith(("/health", "/docs", "/openapi", "/redoc")):
        if request.headers.get("X-API-Key") != config.API_KEY:
            return JSONResponse({"detail": "X-API-Key inválida"}, status_code=401)
    return await call_next(request)


@app.get("/health")
async def health():
    return {"ok": True, "slug": config.SLUG, "barbershop_id": config.BARBERSHOP_ID}


app.include_router(meta.router)
app.include_router(availability.router)
