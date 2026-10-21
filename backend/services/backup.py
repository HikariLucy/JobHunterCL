"""Respaldo JSON compatible con el MVP (`jobhuntercl-backup-v1`).

El formato se mantiene: el MVP ignora la clave adicional `status_history`.
Antes de importar se guarda una copia de la base en `data/backups/`.
"""
from __future__ import annotations
import json

from jobhunter.config import save_profile
from jobhunter.storage import export_backup, get_backup_profile, import_backup

from .. import db as dbmod
from ..schemas import Profile
from ..settings import AppSettings


def export(db, profile: dict) -> bytes:
    payload = json.loads(export_backup(db, profile))
    payload["status_history"] = [dict(r) for r in db.execute("SELECT * FROM status_history ORDER BY id")]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def restore(db, settings: AppSettings, content: bytes) -> dict:
    """Valida todo antes de escribir. Devuelve un resumen."""
    try:
        backup_profile = get_backup_profile(content)
    except json.JSONDecodeError as exc:
        raise ValueError("El archivo no es JSON válido") from exc
    if backup_profile is not None:
        Profile.model_validate(backup_profile)  # lanza ValidationError (subclase de ValueError)
    safety = dbmod.snapshot(settings.db_path, settings.backups_dir, "pre-import")
    count = import_backup(db, content)
    if backup_profile is not None:
        save_profile(backup_profile, settings.profile_path)
    return {"imported": count, "profile_restored": backup_profile is not None,
            "safety_copy": safety.name if safety else None}
