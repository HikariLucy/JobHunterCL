"""Aplicación FastAPI de JobHunter CL.

Uso local:  python start.py           (lanzador recomendado)
Desarrollo: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
"""
from __future__ import annotations
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jobhunter.storage import STATUSES

from . import __version__
from . import db as dbmod
from .routers import cv, jobs, profile, search
from .services import scheduler
from .services import search as search_svc
from .settings import AppSettings, load_settings

log = logging.getLogger("jobhunter")


def create_app(settings: AppSettings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        result = dbmod.migrate(settings.db_path, settings.backups_dir)
        if result["from"] != result["to"]:
            log.info("Esquema migrado %s -> %s (copia previa: %s)", result["from"], result["to"], result["backup"])
        conn = dbmod.connect(settings.db_path)
        try:
            search_svc.mark_interrupted(conn)
        finally:
            conn.close()
        app.state.migration = result
        task = asyncio.create_task(scheduler.loop(settings)) if settings.scheduler_enabled else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="JobHunter CL", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.settings = settings
    # Protección frente a DNS rebinding: solo se aceptan peticiones dirigidas a la máquina local.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CV-Filename", "X-CV-Name", "X-CV-Lang"])

    @app.get("/api/health", tags=["sistema"])
    def health():
        conn = dbmod.connect(settings.db_path)
        try:
            version = dbmod.schema_version(conn)
        finally:
            conn.close()
        return {"status": "ok", "version": __version__, "schema_version": version,
                "statuses": list(STATUSES), "scheduler": settings.scheduler_enabled}

    for module in (jobs, search, profile, cv):
        app.include_router(module.router, prefix="/api")

    _mount_frontend(app, settings)
    return app


def _mount_frontend(app: FastAPI, settings: AppSettings) -> None:
    """Sirve el frontend compilado (frontend/dist) con fallback SPA, si existe."""
    dist = settings.frontend_dist
    index = dist / "index.html"
    if not index.is_file():
        @app.get("/", include_in_schema=False)
        def no_frontend():
            return {"message": "Frontend no compilado. Ejecuta: cd frontend && npm install && npm run build",
                    "api_docs": "/api/docs"}
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Ruta de API no encontrada")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
