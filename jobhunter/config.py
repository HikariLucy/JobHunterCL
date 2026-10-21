"""Configuración local, editable desde el panel."""
from __future__ import annotations
import json
from pathlib import Path

PROFILE_PATH = Path("data/profile.json")
DEFAULT_PROFILE = {
    "titles": ["desarrollador junior", "developer junior", "backend junior", "soporte ti", "soporte tecnico", "mesa de ayuda", "analista junior", "devops junior", "practica informatica"],
    "skills": ["python", "sql", "postgresql", "linux", "git", "docker", "fastapi", "redes", "soporte"],
    "locations": ["santiago", "chile", "remote", "remoto", "latam"],
    "min_score": 30,
    "sources": {"getonbrd": True, "remotive": False, "greenhouse_boards": [], "lever_sites": []},
}


def load_profile(path=PROFILE_PATH):
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_PROFILE))
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Perfil local inválido")
    return {**json.loads(json.dumps(DEFAULT_PROFILE)), **value}


def save_profile(profile, path=PROFILE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
