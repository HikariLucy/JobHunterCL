"""Configuración del backend: rutas absolutas y red local.

Todo se resuelve respecto a la raíz del repositorio (no del directorio de
trabajo), para que el backend funcione igual desde un lanzador, un IDE o
un servicio futuro en Ubuntu Server.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class AppSettings:
    data_dir: Path
    frontend_dist: Path = ROOT / "frontend" / "dist"
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    scheduler_enabled: bool = True
    extra: dict = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def profile_path(self) -> Path:
        return self.data_dir / "profile.json"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"


def load_settings() -> AppSettings:
    """Lee variables de entorno opcionales (ver .env.example)."""
    data_dir = Path(os.environ.get("JOBHUNTER_DATA_DIR") or ROOT / "data").expanduser().resolve()
    scheduler = os.environ.get("JOBHUNTER_SCHEDULER", "1") not in {"0", "false", "no"}
    return AppSettings(data_dir=data_dir, scheduler_enabled=scheduler)
