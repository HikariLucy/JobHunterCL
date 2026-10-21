"""Búsqueda bajo demanda o programada, con límites por fuente y reintentos.

- Comparte la clave `last_scan` de la tabla `settings` con el MVP Streamlit,
  así ambos respetan la misma espera mínima.
- Solo reintenta errores transitorios (red, timeout, HTTP 5xx). Un HTTP 429
  se registra y no se reintenta: se respeta el límite de la fuente.
- Un candado evita búsquedas simultáneas (manual + programada).
- La espera mínima empieza con cualquier respuesta de una fuente (también 0
  resultados, 429 o 5xx); solo los fallos de red sin respuesta permiten
  reintentar de inmediato.
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable

import requests

from jobhunter.collect import PartialFetch, build_sources
from jobhunter.storage import get_setting, job_id, set_setting, upsert_jobs

LAST_SCAN = "last_scan"
INTERVAL_KEY = "scan_interval_minutes"
RETRY_DELAYS = (2.0, 6.0)
_lock = threading.Lock()


class SearchBusy(RuntimeError):
    pass


class CooldownActive(RuntimeError):
    def __init__(self, next_allowed: datetime):
        super().__init__("Las fuentes se consultaron recientemente.")
        self.next_allowed = next_allowed


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def min_interval(sources: dict) -> timedelta:
    """Política del MVP: 30 min, más 6 h si Remotive está activo (máx. 4 consultas/día).
    La API de Get on Board hace ~11 peticiones por pasada: al menos 60 min."""
    if sources.get("remotive"):
        return timedelta(hours=6, minutes=30)
    return timedelta(minutes=60 if sources.get("getonbrd_api") else 30)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def next_allowed(db, sources: dict) -> datetime | None:
    last = parse_ts(get_setting(db, LAST_SCAN))
    return last + min_interval(sources) if last else None


def is_running() -> bool:
    return _lock.locked()


def _transient(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return False


def fetch_with_retries(fn: Callable[[], list[dict]], sleep=time.sleep,
                       delays=RETRY_DELAYS) -> list[dict]:
    for attempt in range(len(delays) + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - solo se reintentan los transitorios
            if attempt < len(delays) and _transient(exc):
                sleep(delays[attempt])
                continue
            raise
    raise AssertionError("inalcanzable")


def run_search(db: sqlite3.Connection, profile: dict, trigger: str = "manual", *,
               clock: Callable[[], datetime] = utcnow, sleep=time.sleep,
               source_factory=build_sources) -> dict:
    if not _lock.acquire(blocking=False):
        raise SearchBusy("Ya hay una búsqueda en curso.")
    try:
        sources = profile.get("sources", {})
        allowed = next_allowed(db, sources)
        if allowed and clock() < allowed:
            raise CooldownActive(allowed)
        cur = db.execute("INSERT INTO scan_runs(started_at, trigger, status) VALUES (?,?,?)",
                         (clock().isoformat(), trigger, "running"))
        run_id = cur.lastrowid
        db.commit()
        jobs, errors = [], []
        contacted = False  # alguna fuente recibió y respondió la petición
        for name, fn in source_factory(sources):
            try:
                jobs.extend(fetch_with_retries(fn, sleep=sleep))
                contacted = True
            except PartialFetch as exc:
                # Se conservan las páginas ya obtenidas; no se repite toda la pasada.
                jobs.extend(exc.jobs)
                errors.append(f"{name}: parcial ({len(exc.jobs)} ofertas); {str(exc)[:150]}")
                contacted = True
            except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
                errors.append(f"{name}: {str(exc)[:180]}")
                if not isinstance(exc, (requests.ConnectionError, requests.Timeout)):
                    contacted = True
        # La misma oferta puede llegar por varias fuentes (feed y API de Get on Board):
        # se guarda una vez y gana la última fuente, la más completa.
        jobs = list({job_id(j["url"]): j for j in jobs if str(j.get("url", "")).startswith("https://")}.values())
        added = upsert_jobs(db, jobs) if jobs else 0
        if contacted:
            # Toda consulta que llegó a la fuente cuenta para su límite, aunque no trajera ofertas.
            set_setting(db, LAST_SCAN, clock().isoformat())
        if jobs:
            status_ = "partial" if errors else "ok"
        else:
            status_ = "error" if errors else "empty"
        db.execute("UPDATE scan_runs SET finished_at=?, status=?, fetched=?, added=?, errors=? WHERE id=?",
                   (clock().isoformat(), status_, len(jobs), added, json.dumps(errors, ensure_ascii=False), run_id))
        db.commit()
        return run_row(db, run_id)
    finally:
        _lock.release()


def run_row(db, run_id: int) -> dict:
    r = dict(db.execute("SELECT * FROM scan_runs WHERE id=?", (run_id,)).fetchone())
    r["errors"] = json.loads(r["errors"] or "[]")
    return r


def recent_runs(db, limit=10) -> list[dict]:
    ids = [r[0] for r in db.execute("SELECT id FROM scan_runs ORDER BY id DESC LIMIT ?", (limit,))]
    return [run_row(db, i) for i in ids]


def mark_interrupted(db) -> int:
    """Al arrancar, cierra ejecuciones que quedaron 'running' por un cierre abrupto."""
    cur = db.execute("UPDATE scan_runs SET status='interrupted', finished_at=? WHERE status='running'",
                     (utcnow().isoformat(),))
    db.commit()
    return cur.rowcount


def last_attempt(db) -> datetime | None:
    row = db.execute("SELECT started_at FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()
    return parse_ts(row[0]) if row else None


def scan_interval(db) -> int:
    try:
        return max(0, int(get_setting(db, INTERVAL_KEY, "0")))
    except ValueError:
        return 0


def set_scan_interval(db, minutes: int) -> None:
    set_setting(db, INTERVAL_KEY, str(int(minutes)))


def effective_interval(db, sources: dict) -> timedelta | None:
    """Intervalo programado real: nunca menor que el límite de las fuentes. None = desactivado."""
    minutes = scan_interval(db)
    if minutes <= 0:
        return None
    return max(timedelta(minutes=minutes), min_interval(sources))


def next_scheduled(db, sources: dict, now: datetime | None = None) -> datetime | None:
    interval = effective_interval(db, sources)
    if interval is None:
        return None
    now = now or utcnow()
    anchors = [t for t in (last_attempt(db), parse_ts(get_setting(db, LAST_SCAN))) if t]
    if not anchors:
        return now
    return max(max(anchors) + interval, next_allowed(db, sources) or now)


def status(db, profile: dict) -> dict:
    sources = profile.get("sources", {})
    allowed = next_allowed(db, sources)
    scheduled = next_scheduled(db, sources)
    return {
        "running": is_running(),
        "last_scan": get_setting(db, LAST_SCAN) or None,
        "next_allowed_at": allowed.isoformat() if allowed else None,
        "min_interval_minutes": int(min_interval(sources).total_seconds() // 60),
        "scan_interval_minutes": scan_interval(db),
        "next_scheduled_at": scheduled.isoformat() if scheduled else None,
        "recent_runs": recent_runs(db),
    }
