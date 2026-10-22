"""Configuración local, editable desde el panel.

`data/profile.json` es la única copia del perfil del usuario: se escribe de forma
atómica (archivo temporal en el mismo directorio + `os.replace`) y la versión
válida anterior se conserva en `profile.json.bak`. Un perfil ilegible nunca se
sobrescribe en silencio. Recuperación manual: docs/PERFIL.md.
"""
from __future__ import annotations
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

PROFILE_PATH = Path("data/profile.json")
MAX_PROFILE_BYTES = 1_000_000
DEFAULT_PROFILE = {
    "titles": ["desarrollador junior", "developer junior", "backend junior", "soporte ti", "soporte tecnico", "mesa de ayuda", "analista junior", "devops junior", "practica informatica"],
    "skills": ["python", "sql", "postgresql", "linux", "git", "docker", "fastapi", "redes", "soporte"],
    "locations": ["santiago", "chile", "remote", "remoto", "latam"],
    "min_score": 30,
    "sources": {"getonbrd": True, "getonbrd_api": False, "remotive": False, "greenhouse_boards": [], "lever_sites": []},
}
# Perfil que parte del asistente de primera ejecución: sin cargos ni habilidades
# supuestas (las elige el usuario) y con la API de Get on Board activa. Los perfiles
# ya guardados conservan sus fuentes.
NEW_PROFILE = {
    "titles": [], "skills": [], "locations": [], "min_score": 30,
    "sources": {"getonbrd": True, "getonbrd_api": True, "remotive": False, "greenhouse_boards": [], "lever_sites": []},
}


class ProfileError(Exception):
    """Base de los errores de perfil; el mensaje se puede mostrar al usuario."""


class ProfileCorrupt(ProfileError, ValueError):
    """El archivo existe pero no es un perfil legible. No se modifica."""


class ProfileWriteError(ProfileError, OSError):
    """No se pudo guardar; el perfil anterior sigue intacto."""


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def _copy(value):
    return json.loads(json.dumps(value))


def read_profile_file(path: Path) -> dict:
    """Lee y valida la forma básica de un perfil guardado; ProfileCorrupt si no sirve."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ProfileError(f"No se pudo leer {path.name}: {exc.strerror or exc}") from exc
    if len(raw) > MAX_PROFILE_BYTES:
        raise ProfileCorrupt(f"{path.name} supera {MAX_PROFILE_BYTES} bytes")
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileCorrupt(f"{path.name} no es JSON válido ({exc})") from exc
    if not isinstance(value, dict):
        raise ProfileCorrupt(f"{path.name} no contiene un objeto JSON")
    try:
        _validate_shape(value)
    except ValueError as exc:
        raise ProfileCorrupt(f"{path.name}: {exc}") from exc
    return value


def _validate_shape(value: dict) -> None:
    """Validación del núcleo compartido; no depende de FastAPI ni migra el archivo."""
    from pydantic import ValidationError
    from .profile_schema import Profile
    try:
        Profile.model_validate(value)
    except ValidationError as exc:
        error = exc.errors()[0]
        field = ".".join(str(k) for k in error["loc"])
        raise ValueError(f"{field}: {error['msg']}") from None


def load_profile(path=PROFILE_PATH):
    """Perfil guardado sobre los valores por defecto; ProfileCorrupt si el archivo está dañado."""
    path = Path(path)
    if not path.exists():
        return _copy(DEFAULT_PROFILE)
    return {**_copy(DEFAULT_PROFILE), **read_profile_file(path)}


def profile_status(path=PROFILE_PATH) -> dict:
    """Estado del archivo para el panel: existe, legible, error y si hay copia .bak."""
    path = Path(path)
    bak = backup_path(path)
    status = {"exists": path.exists(), "readable": True, "error": None, "backup_available": False}
    if bak.exists():
        try:
            read_profile_file(bak)
            status["backup_available"] = True
        except ProfileError:
            pass
    if status["exists"]:
        try:
            read_profile_file(path)
        except ProfileError as exc:
            status.update(readable=False, error=str(exc))
    return status


def _replace(src: Path, dst: Path, attempts: int = 5) -> None:
    """os.replace con reintentos breves: en Windows un antivirus o indexador puede
    bloquear el destino unos milisegundos (PermissionError)."""
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.05 * (i + 1))


def _write_temp(directory: Path, prefix: str, data: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=directory)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def save_profile(profile, path=PROFILE_PATH):
    """Guarda el perfil de forma atómica. Devuelve la ruta escrita.

    1. Serializa y valida antes de tocar el disco.
    2. Escribe un temporal en el mismo directorio y lo sincroniza.
    3. Si el destino actual es válido, lo copia a `.bak` (también vía temporal +
       replace, así la copia previa nunca queda a medias). Si está dañado, se aparta
       como `profile.json.corrupt-AAAAMMDD-HHMMSS` en lugar de perderlo.
    4. Sustituye el destino con `os.replace`.
    Ante cualquier fallo se lanza ProfileWriteError y el perfil anterior sigue intacto.
    """
    path = Path(path)
    if not isinstance(profile, dict):
        raise ProfileWriteError("El perfil debe ser un objeto JSON")
    try:
        _validate_shape(profile)
        data = (json.dumps(profile, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProfileWriteError(f"Perfil no serializable: {exc}") from exc
    if len(data) > MAX_PROFILE_BYTES:
        raise ProfileWriteError(f"Perfil demasiado grande (más de {MAX_PROFILE_BYTES} bytes)")
    tmp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = _write_temp(path.parent, f".{path.name}.", data)
        if path.exists():
            try:
                read_profile_file(path)
                current_ok = True
            except ProfileCorrupt:
                current_ok = False
            if current_ok:
                bak_tmp = _write_temp(path.parent, f".{path.name}.bak.", path.read_bytes())
                try:
                    _replace(bak_tmp, backup_path(path))
                except BaseException:
                    bak_tmp.unlink(missing_ok=True)
                    raise
            else:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                shutil.copy2(path, path.with_name(f"{path.name}.corrupt-{stamp}"))
        _replace(tmp, path)
        tmp = None
    except ProfileError:
        raise
    except OSError as exc:
        raise ProfileWriteError(
            f"No se pudo guardar el perfil ({exc.strerror or exc}); se conservó la versión anterior") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return path
