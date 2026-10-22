"""Contrato de perfil compartido por API, persistencia y MVP; no importa backend."""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from jobhunter.collect import valid_token

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


# Tipo de experiencia: "" = por confirmar (perfiles anteriores a M1.4). Un proyecto
# o una práctica no equivalen a experiencia laboral formal.
ExperienceKind = Literal["", "empleo", "practica", "proyecto", "voluntariado"]
# Estado de un estudio: "" = por confirmar. «en_curso» nunca se presenta como título.
EducationStatus = Literal["", "completado", "en_curso", "incompleto"]


class ExperienceItem(BaseModel):
    role: str = Field(max_length=200)
    organization: str = Field(default="", max_length=200)
    period: str = Field(default="", max_length=100)
    summary: str = ShortText
    kind: ExperienceKind = ""


class EducationItem(BaseModel):
    title: str = Field(max_length=200)
    institution: str = Field(default="", max_length=200)
    period: str = Field(default="", max_length=100)
    status: EducationStatus = ""


class SkillEvidence(BaseModel):
    """Experiencia o proyecto que respalda una habilidad declarada (texto del usuario)."""
    skill: str = Field(max_length=199)
    evidence: str = Field(max_length=500)


class LanguageItem(BaseModel):
    name: str = Field(max_length=60)
    level: str = Field(default="", max_length=60)   # declarado por el usuario (A2, B2, nativo…)
    evidence: str = Field(default="", max_length=300)  # certificado, estudios, uso laboral; opcional


class Preferences(BaseModel):
    modalities: list[str] = []
    seniority: list[str] = []
    salary_min: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="CLP", max_length=8)
    salary_period: Literal["mensual", "anual"] = "mensual"
    relocation: bool = False
    notes: str = ShortText

    @field_validator("modalities", "seniority")
    @classmethod
    def _lists(cls, values: list[str]) -> list[str]:
        return _clean_list(values)[:20]


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
    # M1.4 (opcionales; perfiles anteriores siguen siendo válidos)
    areas: list[str] = []                 # áreas de interés (TI, datos, soporte…)
    learning_skills: list[str] = []       # en aprendizaje: no cuentan como dominadas
    skill_evidence: list[SkillEvidence] = Field(default=[], max_length=100)
    education: list[EducationItem] = Field(default=[], max_length=30)

    @field_validator("titles", "skills", "locations", "areas", "learning_skills")
    @classmethod
    def _lists(cls, values: list[str]) -> list[str]:
        return _clean_list(values)

