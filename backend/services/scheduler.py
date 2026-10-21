"""Programador en proceso: solo funciona mientras JobHunter está abierto.

No instala servicios del sistema. Al cerrar la aplicación, la tarea asyncio
se cancela junto con el ciclo de vida de FastAPI.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from jobhunter.config import load_profile

from .. import db as dbmod
from ..settings import AppSettings
from . import search

log = logging.getLogger("jobhunter.scheduler")
TICK_SECONDS = 60


def tick(settings: AppSettings, now: datetime | None = None, **search_kwargs) -> dict | None:
    """Ejecuta una búsqueda si corresponde. Devuelve el registro de la ejecución o None."""
    now = now or datetime.now(timezone.utc)
    db = dbmod.connect(settings.db_path)
    try:
        profile = load_profile(settings.profile_path)
        due = search.next_scheduled(db, profile.get("sources", {}), now)
        if due is None or now < due:
            return None
        try:
            return search.run_search(db, profile, trigger="scheduled", **search_kwargs)
        except (search.SearchBusy, search.CooldownActive) as exc:
            log.info("Búsqueda programada omitida: %s", exc)
            return None
    finally:
        db.close()


async def loop(settings: AppSettings) -> None:
    while True:
        try:
            run = await asyncio.to_thread(tick, settings)
            if run:
                log.info("Búsqueda programada: %s (%s nuevas)", run["status"], run["added"])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - el programador nunca debe tumbar la app
            log.exception("Fallo en el programador")
        await asyncio.sleep(TICK_SECONDS)
