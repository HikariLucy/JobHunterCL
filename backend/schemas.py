"""Contratos de la API (Pydantic v2)."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from jobhunter.collect import valid_token
from jobhunter.storage import STATUSES

Status = Literal["Nueva", "Revisar", "Preparada", "Postulada", "Descartada"]
assert set(Status.__args__) == set(STATUSES)

ShortText = Field(default="", max_length=2000)


def _clean_list(values: list[str]) -> list[str]:
    out, seen = [], set()
    for v in values:
        v = v.strip()
        if v and v.casefold() not in seen:
            seen.add(v.casefold())
            out.append(v[:199])
    return out[:100]


class Sources(BaseModel):
    model_config = ConfigDict(extra="allow")
    getonbrd: bool = True
    getonbrd_api: bool = False  # API pública: más ofertas técnicas elegibles desde Chile
    remotive: bool = False
    greenhouse_boards: list[str] = []
    lever_sites: list[str] = []

    @field_validator("greenhouse_boards", "lever_sites")
    @classmethod
    def _tokens(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

    def invalid_tokens(self) -> list[str]:
        """Se valida al guardar (no al leer) para no bloquear perfiles heredados del MVP."""
        return [v for v in self.greenhouse_boards + self.lever_sites if not valid_token(v)]


class ExperienceItem(BaseModel):
    role: str = Field(max_length=200)
    organization: str = Field(default="", max_length=200)
    period: str = Field(default="", max_length=100)
    summary: str = ShortText


class LanguageItem(BaseModel):
    name: str = Field(max_length=60)
    level: str = Field(default="", max_length=60)


class Preferences(BaseModel):
    modalities: list[str] = []
    seniority: list[str] = []
    salary_min: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="CLP", max_length=8)
    relocation: bool = False
    notes: str = ShortText


class Profile(BaseModel):
    """Perfil compatible con data/profile.json del MVP; los campos nuevos son opcionales."""
    model_config = ConfigDict(extra="allow")
    titles: list[str] = []
    skills: list[str] = []
    locations: list[str] = []
    min_score: int = Field(default=30, ge=0, le=100)
    sources: Sources = Sources()
    experience: list[ExperienceItem] = Field(default=[], max_length=50)
    languages: list[LanguageItem] = Field(default=[], max_length=20)
    preferences: Preferences = Preferences()

    @field_validator("titles", "skills", "locations")
    @classmethod
    def _lists(cls, values: list[str]) -> list[str]:
        return _clean_list(values)


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
