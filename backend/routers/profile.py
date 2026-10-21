"""Perfil, configuración y respaldos."""
from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import ValidationError

from jobhunter.config import save_profile

from .. import db as dbmod
from ..deps import get_db, get_profile, get_settings
from ..schemas import AppConfig, AppConfigUpdate, Profile
from ..services import backup, search

router = APIRouter(tags=["perfil y configuración"])
MAX_BACKUP_BYTES = 15_000_000


def _reject_invalid_tokens(p: Profile) -> None:
    bad = p.sources.invalid_tokens()
    if bad:
        raise HTTPException(422, "Identificadores de empresa inválidos: " + ", ".join(bad[:5]))


@router.get("/profile", response_model=Profile)
def read_profile(profile=Depends(get_profile)):
    return Profile.model_validate(profile)


@router.put("/profile", response_model=Profile)
def write_profile(body: Profile, settings=Depends(get_settings)):
    _reject_invalid_tokens(body)
    save_profile(body.model_dump(mode="json"), settings.profile_path)
    return body


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
        save_profile(p.model_dump(mode="json"), settings.profile_path)
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
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, f"Respaldo inválido: {exc}") from None
    finally:
        db.close()
