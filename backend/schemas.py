"""Contratos de la API (Pydantic v2)."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, Field
from jobhunter.storage import STATUSES

Status = Literal["Nueva", "Revisar", "Preparada", "Postulada", "Descartada"]
assert set(Status.__args__) == set(STATUSES)

# Reexportados para conservar imports de clientes internos y versiones previas.
from jobhunter.profile_schema import (  # noqa: F401
    Profile, Sources, Preferences, ExperienceItem, EducationItem, SkillEvidence,
    LanguageItem, ExperienceKind, EducationStatus, ShortText,
)


class ProfileStatus(BaseModel):
    """Estado de data/profile.json para decidir si mostrar el asistente inicial."""
    exists: bool
    readable: bool
    error: str | None
    backup_available: bool
    new_profile: Profile  # plantilla para el asistente cuando no hay perfil guardado


class Eligibility(BaseModel):
    """Elegibilidad geográfica para las zonas del perfil (matching.eligibility)."""
    status: Literal["compatible", "desconocida", "incompatible"]
    evidence: str
    basis: str


class Job(BaseModel):
    id: str
    source: str
    title: str
    company: str
    location: str | None = ""
    url: str
    description: str | None = ""
    posted_at: str | None = ""
    first_seen: str
    last_seen: str
    status: Status
    notes: str = ""
    score: int
    reasons: list[str]
    warnings: list[str]
    eligibility: Eligibility


class JobPage(BaseModel):
    items: list[Job]
    total: int
    stored: int


class JobUpdate(BaseModel):
    status: Status | None = None
    notes: str | None = Field(default=None, max_length=5000)


class HistoryEntry(BaseModel):
    id: int
    job_id: str
    old_status: str | None
    new_status: str
    changed_at: str
    origin: str


class ScanRun(BaseModel):
    id: int
    started_at: str
    finished_at: str | None
    trigger: str
    status: str
    fetched: int
    added: int
    errors: list[str]


class SearchStatus(BaseModel):
    running: bool
    last_scan: str | None
    next_allowed_at: str | None
    min_interval_minutes: int
    scan_interval_minutes: int
    next_scheduled_at: str | None
    recent_runs: list[ScanRun]


class AppConfig(BaseModel):
    sources: Sources
    scan_interval_minutes: int = Field(ge=0, le=7 * 24 * 60)
    min_interval_minutes: int = 0


class AppConfigUpdate(BaseModel):
    sources: Sources | None = None
    scan_interval_minutes: int | None = Field(default=None, ge=0, le=7 * 24 * 60)
