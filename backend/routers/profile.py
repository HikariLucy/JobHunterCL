"""Perfil, configuración y respaldos."""
from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError

from jobhunter.config import NEW_PROFILE, ProfileError, ProfileWriteError, profile_status, read_profile_file, save_profile

from .. import db as dbmod
from ..deps import get_db, get_profile, get_settings
from ..schemas import AppConfig, AppConfigUpdate, Profile, ProfileStatus
from ..services import backup, search

router = APIRouter(tags=["perfil y configuración"])
MAX_BACKUP_BYTES = 15_000_000


def _reject_invalid_tokens(p: Profile) -> None:
    bad = p.sources.invalid_tokens()
    if bad:
        raise HTTPException(422, "Identificadores de empresa inválidos: " + ", ".join(bad[:5]))


def _stored(settings) -> dict:
    """Perfil guardado tal cual (sin valores por defecto); vacío si no existe o está dañado."""
    try:
        return read_profile_file(settings.profile_path) if settings.profile_path.exists() else {}
    except ProfileError:
        return {}


def _keep_known_extras(body: Profile, stored: dict) -> dict:
    """Claves desconocidas: se conservan solo las que ya estaban en el archivo (perfiles
    del MVP o versiones anteriores). El panel no puede añadir campos arbitrarios."""
    data = body.model_dump(mode="json")
    for key in body.model_extra or {}:
        if key not in stored:
            data.pop(key, None)
    known_sources = stored.get("sources") if isinstance(stored.get("sources"), dict) else {}
    for key in body.sources.model_extra or {}:
        if key not in known_sources:
            data["sources"].pop(key, None)
    return data


def _save(data: dict, settings) -> None:
    try:
        save_profile(data, settings.profile_path)
    except ProfileWriteError as exc:
        raise HTTPException(500, str(exc)) from exc


@router.get("/profile", response_model=Profile)
def read_profile(profile=Depends(get_profile)):
    return Profile.model_validate(profile)


@router.get("/profile/status", response_model=ProfileStatus)
def read_profile_status(settings=Depends(get_settings)):
    """No lanza error con un perfil dañado: el panel lo informa sin abrir el asistente."""
    return {**profile_status(settings.profile_path), "new_profile": Profile.model_validate(NEW_PROFILE)}


@router.put("/profile", response_model=Profile)
def write_profile(body: Profile, settings=Depends(get_settings)):
    _reject_invalid_tokens(body)
    data = _keep_known_extras(body, _stored(settings))
    _save(data, settings)
    return Profile.model_validate(data)


@router.get("/config", response_model=AppConfig)
def read_config(db=Depends(get_db), profile=Depends(get_profile)):
    p = Profile.model_validate(profile)
    return {"sources": p.sources, "scan_interval_minutes": search.scan_interval(db),
            "min_interval_minutes": int(search.min_interval(p.sources.model_dump()).total_seconds() // 60)}


@router.put("/config", response_model=AppConfig)
def write_config(body: AppConfigUpdate, db=Depends(get_db), profile=Depends(get_profile),
                 settings=Depends(get_settings)):
    p = Profile.model_validate(profile)
    if body.sources is not None:
        p.sources = body.sources
        _reject_invalid_tokens(p)
        _save(p.model_dump(mode="json"), settings)
    if body.scan_interval_minutes is not None:
        search.set_scan_interval(db, body.scan_interval_minutes)
    return read_config(db, p.model_dump(mode="json"))


@router.get("/backup/export")
def export_backup(db=Depends(get_db), profile=Depends(get_profile)):
    name = f"jobhunter_respaldo_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    return Response(backup.export(db, profile), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/backup/import")
async def import_backup(request: Request, settings=Depends(get_settings)):
    content = await request.body()
    if len(content) > MAX_BACKUP_BYTES:
        raise HTTPException(413, "Respaldo demasiado grande")
    db = dbmod.connect(settings.db_path)
    try:
        return backup.restore(db, settings, content)
    except ValidationError as exc:
        raise HTTPException(422, f"Perfil del respaldo inválido: {exc.errors()[0]['msg']}") from None
    except ProfileWriteError as exc:
        raise HTTPException(500, f"Datos importados, pero el perfil no se guardó: {exc}") from None
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, f"Respaldo inválido: {exc}") from None
    finally:
        db.close()
