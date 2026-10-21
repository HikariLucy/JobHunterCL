"""Conexión SQLite y migraciones aditivas.

Reglas de compatibilidad con el MVP Streamlit:
- Nunca se eliminan ni renombran tablas o columnas existentes (`jobs`, `settings`).
- Solo se agregan tablas nuevas; el MVP las ignora.
- `PRAGMA user_version` registra la versión del esquema.
- Antes de la primera migración de una base con datos se guarda una copia
  consistente en `data/backups/`.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from jobhunter import storage

SCHEMA_VERSION = 1

MIGRATIONS: dict[int, list[str]] = {
    1: [
        """CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            origin TEXT NOT NULL DEFAULT 'api')""",
        "CREATE INDEX IF NOT EXISTS idx_status_history_job ON status_history(job_id, changed_at)",
        """CREATE TABLE IF NOT EXISTS scan_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            trigger TEXT NOT NULL,
            status TEXT NOT NULL,
            fetched INTEGER NOT NULL DEFAULT 0,
            added INTEGER NOT NULL DEFAULT 0,
            errors TEXT NOT NULL DEFAULT '[]')""",
    ],
}


def connect(path: Path) -> sqlite3.Connection:
    """Reutiliza `storage.connection` (crea tablas base si faltan).

    FastAPI puede abrir la conexión en un hilo y usarla en otro dentro de la
    misma petición; cada conexión pertenece a una sola petición.
    """
    db = storage.connection(path, check_same_thread=False)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def schema_version(db: sqlite3.Connection) -> int:
    return db.execute("PRAGMA user_version").fetchone()[0]


def snapshot(db_path: Path, backups_dir: Path, label: str) -> Path | None:
    """Copia consistente de la base (API de backup de SQLite). None si no existe."""
    if not db_path.exists():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backups_dir / f"jobs-{label}-{stamp}.sqlite3"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def migrate(db_path: Path, backups_dir: Path) -> dict:
    """Aplica migraciones pendientes. Devuelve un resumen para registro."""
    existed = db_path.exists()
    db = connect(db_path)
    try:
        current = schema_version(db)
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"La base de datos usa el esquema {current}, más nuevo que esta versión ({SCHEMA_VERSION}).")
        if current == SCHEMA_VERSION:
            return {"from": current, "to": current, "backup": None}
    finally:
        db.close()
    backup = snapshot(db_path, backups_dir, f"pre-v{SCHEMA_VERSION}") if existed else None
    db = connect(db_path)
    try:
        for version in range(current + 1, SCHEMA_VERSION + 1):
            with db:
                for sql in MIGRATIONS[version]:
                    db.execute(sql)
                db.execute(f"PRAGMA user_version={version}")
    finally:
        db.close()
    return {"from": current, "to": SCHEMA_VERSION, "backup": str(backup) if backup else None}
