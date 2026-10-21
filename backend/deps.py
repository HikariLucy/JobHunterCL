"""Dependencias FastAPI compartidas por los routers."""
from __future__ import annotations
import json
from typing import Iterator

from fastapi import Depends, HTTPException, Request

from jobhunter.config import ProfileCorrupt, ProfileError, backup_path, load_profile

from . import db as dbmod
from .settings import AppSettings


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


def get_db(settings: AppSettings = Depends(get_settings)) -> Iterator:
    db = dbmod.connect(settings.db_path)
    try:
        yield db
    finally:
        db.close()


def get_profile(settings: AppSettings = Depends(get_settings)) -> dict:
    try:
        return load_profile(settings.profile_path)
    except ProfileCorrupt as exc:
        hint = (f" Hay una copia válida anterior en {backup_path(settings.profile_path).name}: ver docs/PERFIL.md."
                if backup_path(settings.profile_path).exists() else " Ver docs/PERFIL.md para recuperarlo.")
        raise HTTPException(500, f"El perfil local está dañado y no se modificó: {exc}.{hint}") from exc
    except (ProfileError, OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(500, f"No se pudo leer el perfil local: {exc}") from exc
