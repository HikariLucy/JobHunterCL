"""Respaldo JSON compatible con el MVP (`jobhuntercl-backup-v1`).

El formato se mantiene: el MVP ignora la clave adicional `status_history`, y
los respaldos sin ella (exportados por el MVP o por versiones anteriores) se
siguen importando igual. Antes de importar se guarda una copia de la base en
`data/backups/`.
"""
from __future__ import annotations
import json
import re
from datetime import datetime

from jobhunter.config import save_profile
from jobhunter.storage import STATUSES, export_backup, get_backup_profile, import_backup

from .. import db as dbmod
from ..schemas import Profile
from ..settings import AppSettings

MAX_HISTORY = 100_000
_JOB_ID = re.compile(r"^[0-9a-f]{24}$")
_ORIGIN = re.compile(r"^[a-z0-9_-]{1,32}$")


def export(db, profile: dict) -> bytes:
    payload = json.loads(export_backup(db, profile))
    payload["status_history"] = [dict(r) for r in db.execute("SELECT * FROM status_history ORDER BY id")]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _valid_entry(entry) -> tuple | None:
    """Normaliza una entrada del historial o devuelve None si no es válida."""
    if not isinstance(entry, dict):
        return None
    job_id, old, new = entry.get("job_id"), entry.get("old_status"), entry.get("new_status")
    changed_at, origin = entry.get("changed_at"), entry.get("origin", "import")
    if not isinstance(job_id, str) or not _JOB_ID.match(job_id):
        return None
    if new not in STATUSES or (old is not None and old not in STATUSES):
        return None
    if not isinstance(changed_at, str) or len(changed_at) > 64:
        return None
    try:
        datetime.fromisoformat(changed_at)
    except ValueError:
        return None
    if not isinstance(origin, str) or not _ORIGIN.match(origin):
        origin = "import"
    return job_id, old, new, changed_at, origin


def parse_history(content: bytes) -> tuple[list[tuple], int]:
    """Valida `status_history` sin escribir. Devuelve (entradas válidas, omitidas).

    Ausente o nulo = respaldo antiguo: lista vacía. Si existe y no es una lista,
    se rechaza el respaldo completo.
    """
    history = json.loads(content).get("status_history")
    if history is None:
        return [], 0
    if not isinstance(history, list):
        raise ValueError("Historial de estados inválido")
    if len(history) > MAX_HISTORY:
        raise ValueError("Historial de estados demasiado grande")
    valid = [e for e in map(_valid_entry, history) if e is not None]
    return valid, len(history) - len(valid)


def _import_history(db, entries: list[tuple]) -> tuple[int, int]:
    """Inserta entradas de ofertas existentes, sin duplicar. Devuelve (nuevas, omitidas)."""
    known = {r[0] for r in db.execute("SELECT id FROM jobs")}
    seen = {tuple(r) for r in db.execute(
        "SELECT job_id, old_status, new_status, changed_at FROM status_history")}
    added = skipped = 0
    for job_id, old, new, changed_at, origin in entries:
        key = (job_id, old, new, changed_at)
        if job_id not in known:
            skipped += 1
            continue
        if key in seen:
            continue
        db.execute("INSERT INTO status_history(job_id, old_status, new_status, changed_at, origin) VALUES (?,?,?,?,?)",
                   (job_id, old, new, changed_at, origin))
        seen.add(key)
        added += 1
    db.commit()
    return added, skipped


def restore(db, settings: AppSettings, content: bytes) -> dict:
    """Valida todo antes de escribir. Devuelve un resumen."""
    try:
        backup_profile = get_backup_profile(content)
    except json.JSONDecodeError as exc:
        raise ValueError("El archivo no es JSON válido") from exc
    if backup_profile is not None:
        Profile.model_validate(backup_profile)  # lanza ValidationError (subclase de ValueError)
    history, invalid = parse_history(content)
    safety = dbmod.snapshot(settings.db_path, settings.backups_dir, "pre-import")
    count = import_backup(db, content)
    history_added, orphans = _import_history(db, history)
    if backup_profile is not None:
        save_profile(backup_profile, settings.profile_path)
    return {"imported": count, "profile_restored": backup_profile is not None,
            "safety_copy": safety.name if safety else None,
            "history_imported": history_added, "history_skipped": invalid + orphans}
