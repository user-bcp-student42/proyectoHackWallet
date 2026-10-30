"""API HTTP del MVP de registro y activación de wallet."""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from fastapi import Body, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app import analytics, seed
from app.domain import CANALES, PASOS, ErrorValidacion
from app.onboarding import Conflicto, NoEncontrado, OnboardingService, Reloj, reloj_utc
from app.store import JsonStore

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


class InicioOnboarding(BaseModel):
    canal_adquisicion: str | None = None


class GastoAdquisicion(BaseModel):
    mes: str = Field(description="Mes en formato AAAA-MM")
    canal: str
    monto_pen: float = Field(gt=0)

    @field_validator("mes")
    @classmethod
    def _mes(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", v):
            raise ValueError("Usa el formato AAAA-MM, por ejemplo 2026-09")
        return v

    @field_validator("canal")
    @classmethod
    def _canal(cls, v: str) -> str:
        if v not in CANALES:
            raise ValueError(f"Canal desconocido. Usa uno de: {', '.join(CANALES)}")
        return v


def _flag(nombre: str, defecto: bool) -> bool:
    return os.getenv(nombre, str(defecto)).strip().lower() in ("1", "true", "yes", "si", "sí")


def create_app(store: JsonStore | None = None, reloj: Reloj = reloj_utc,
               cargar_demo: bool | None = None) -> FastAPI:
    store = store or JsonStore(os.getenv("WALLET_DB_PATH", "data/db.json"))
    if cargar_demo is None:
        cargar_demo = _flag("DEMO_SEED", True)
    servicio = OnboardingService(store, reloj)

    app = FastAPI(
        title="Wallet Perú · Registro y activación (MVP)",
        version="1.0.0",
        description="Onboarding guiado de la wallet, eventos analíticos y reporte de MAU/CAC. "
                    "Integraciones de OTP y validación de identidad simuladas.",
    )
    app.state.store = store
    app.state.servicio = servicio

    if cargar_demo:
        seed.cargar(store, reloj().date())

    # ── Manejo de errores: siempre un mensaje accionable en español ──────

    @app.exception_handler(ErrorValidacion)
    async def _validacion(_: Request, exc: ErrorValidacion):
        return JSONResponse(status_code=422, content={
            "codigo": "DATOS_INVALIDOS",
            "mensaje": "Corrige los datos marcados para continuar.",
            "errores": exc.errores,
        })

    @app.exception_handler(Conflicto)
    async def _conflicto(_: Request, exc: Conflicto):
        status = 403 if exc.codigo == "WALLET_NO_ACTIVA" else 409
        return JSONResponse(status_code=status, content={"codigo": exc.codigo, "mensaje": exc.mensaje})

    @app.exception_handler(NoEncontrado)
    async def _no_encontrado(_: Request, exc: NoEncontrado):
        return JSONResponse(status_code=404, content={"codigo": "NO_ENCONTRADO", "mensaje": str(exc)})

    # ── Onboarding ───────────────────────────────────────────────────────

    @app.get("/api/salud", tags=["sistema"])
    def salud():
        return {"estado": "ok", "almacenamiento": "memoria" if store.in_memory else store.path}

    @app.get("/api/onboarding/pasos", tags=["onboarding"])
    def pasos():
        return [{"orden": i, "clave": p.clave, "titulo": p.titulo, "descripcion": p.descripcion}
                for i, p in enumerate(PASOS, start=1)]

    @app.post("/api/onboardings", status_code=201, tags=["onboarding"])
    def iniciar(datos: InicioOnboarding = Body(default_factory=InicioOnboarding)):
        return servicio.iniciar(datos.canal_adquisicion)

    @app.get("/api/onboardings/{onboarding_id}", tags=["onboarding"])
    def obtener(onboarding_id: str):
        return servicio.obtener(onboarding_id)

    @app.post("/api/onboardings/{onboarding_id}/pasos/{paso}", tags=["onboarding"])
    def enviar_paso(onboarding_id: str, paso: str, datos: dict = Body(default_factory=dict)):
        return servicio.enviar_paso(onboarding_id, paso, datos)

    @app.post("/api/onboardings/{onboarding_id}/abandonar", tags=["onboarding"])
    def abandonar(onboarding_id: str):
        return servicio.abandonar(onboarding_id)

    @app.get("/api/onboardings/{onboarding_id}/eventos", tags=["onboarding"])
    def eventos_onboarding(onboarding_id: str):
        return servicio.eventos(onboarding_id)

    @app.get("/api/wallets/{wallet_id}/pagos", tags=["pagos"])
    def punto_entrada_pagos(wallet_id: str):
        return servicio.punto_entrada_pagos(wallet_id)

    # ── Analítica ────────────────────────────────────────────────────────

    def _eventos_y_gastos(incluir_demo: bool):
        with store.read() as db:
            eventos, gastos = list(db["eventos"]), list(db["gasto_adquisicion"])
            if incluir_demo:
                eventos = store.demo["eventos"] + eventos
                gastos = store.demo["gasto_adquisicion"] + gastos
            return eventos, gastos

    @app.get("/api/analitica/onboarding", tags=["analitica"])
    def resumen(desde: date | None = Query(None), hasta: date | None = Query(None),
                incluir_demo: bool = True):
        eventos, _ = _eventos_y_gastos(incluir_demo)
        return analytics.resumen(eventos, desde, hasta)

    @app.get("/api/analitica/mensual", tags=["analitica"])
    def mensual(incluir_demo: bool = True):
        eventos, gastos = _eventos_y_gastos(incluir_demo)
        return {"metas": analytics.metas(), "meses": analytics.reporte_mensual(eventos, gastos)}

    @app.get("/api/analitica/eventos", tags=["analitica"])
    def ultimos_eventos(limite: int = Query(20, ge=1, le=200), incluir_demo: bool = False):
        eventos, _ = _eventos_y_gastos(incluir_demo)
        return list(reversed(eventos[-limite:]))

    @app.post("/api/analitica/gasto", status_code=201, tags=["analitica"])
    def registrar_gasto(gasto: GastoAdquisicion):
        registro = gasto.model_dump()
        with store.write() as db:
            db["gasto_adquisicion"].append(registro)
        return registro

    # ── Utilidades de demo ───────────────────────────────────────────────

    if _flag("DEMO_ENDPOINTS", True):
        @app.post("/api/demo/reiniciar", tags=["demo"])
        def reiniciar(con_datos_demo: bool = True):
            """Borra los registros reales y recarga (o quita) los datos ficticios."""
            store.reset()
            if con_datos_demo:
                return seed.cargar(store, reloj().date())
            store.demo = {"eventos": [], "gasto_adquisicion": []}
            return {"eventos_demo": 0, "registros_gasto_demo": 0}

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app
