"""Contratos de la futura integración de CV LaTeX (M2). AÚN SIN IMPLEMENTAR.

Ver docs/CV_INTEGRACION.md. Este módulo solo fija tipos para que backend,
frontend y pruebas evolucionen sobre una interfaz estable.

Principios no negociables:
- Los .tex viven fuera del repositorio (por defecto `data/cv/`, ignorado por git).
- Toda propuesta de cambio cita su evidencia: un fragmento del CV original.
  Lo que no tenga evidencia se marca como `gap` (brecha) y NUNCA se inserta.
- Ninguna versión adaptada se genera sin aprobación explícita de cada cambio.
"""
from __future__ import annotations
from typing import Literal, Protocol

from pydantic import BaseModel, Field

Lang = Literal["es", "en"]


class CvSource(BaseModel):
    """CV maestro importado desde un .tex local."""
    id: str
    lang: Lang
    path: str                      # ruta local absoluta; nunca se sube ni se exporta en respaldos
    sha256: str                    # detecta cambios del archivo original
    imported_at: str


class CvSection(BaseModel):
    """Bloque del CV con su ubicación exacta en el .tex (para reescribir sin romper el formato)."""
    key: str                       # p. ej. "experience[0]", "skills"
    kind: Literal["header", "summary", "experience", "education", "skills", "languages", "projects", "other"]
    text: str                      # texto plano extraído
    tex_span: tuple[int, int]      # offsets de inicio/fin en el .tex


class ParsedCv(BaseModel):
    source: CvSource
    sections: list[CvSection]
    skills: list[str]


class Requirement(BaseModel):
    text: str
    kind: Literal["required", "nice_to_have", "unknown"]
    skill: str | None = None


class JobAnalysis(BaseModel):
    job_id: str
    lang: Lang                     # idioma detectado de la oferta → CV a usar
    requirements: list[Requirement]


class Evidence(BaseModel):
    section_key: str
    quote: str = Field(max_length=500)  # cita literal del CV maestro


class Suggestion(BaseModel):
    """Una propuesta atómica que el usuario acepta o rechaza."""
    id: str
    action: Literal["reorder", "emphasize", "rephrase", "remove", "gap"]
    section_key: str
    before: str
    after: str | None              # None para `gap`: solo se informa, no se escribe
    rationale: str
    evidence: list[Evidence]       # obligatorio salvo en `gap`
    status: Literal["pending", "accepted", "rejected"] = "pending"


class TailoringPlan(BaseModel):
    job_id: str
    cv_id: str
    lang: Lang
    coverage: float = Field(ge=0, le=1)   # proporción de requisitos obligatorios con evidencia
    suggestions: list[Suggestion]


class CvParser(Protocol):
    def parse(self, tex: str, source: CvSource) -> ParsedCv: ...


class Tailor(Protocol):
    """Implementaciones posibles: reglas deterministas (primero) y, con aprobación, un LLM local o de pago."""
    def plan(self, cv: ParsedCv, job: JobAnalysis) -> TailoringPlan: ...


def validate_suggestion(s: Suggestion, cv: ParsedCv) -> list[str]:
    """Regla anti-invención: toda evidencia debe aparecer literalmente en el CV maestro."""
    problems = []
    if s.action != "gap" and not s.evidence:
        problems.append(f"{s.id}: cambio sin evidencia")
    corpus = {sec.key: sec.text for sec in cv.sections}
    for ev in s.evidence:
        if ev.quote not in corpus.get(ev.section_key, ""):
            problems.append(f"{s.id}: la cita no existe en {ev.section_key}")
    if s.action == "gap" and s.after is not None:
        problems.append(f"{s.id}: una brecha no puede proponer texto")
    return problems
