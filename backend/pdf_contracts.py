"""Contratos PDF estrictos: sin código fuente ni rutas en la API."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class PdfRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    expected_tex_sha256: str = Field(pattern='^[a-f0-9]{64}$')


class PdfCapabilities(StrictModel):
    available: Literal[False] = False
    code: Literal['sandbox_unverified'] = 'sandbox_unverified'
    reasons: list[str]
    detected_tools: list[str]


class PdfStatus(StrictModel):
    plan_id: str = Field(pattern='^[a-f0-9]{32}$')
    revision: int = Field(ge=1)
    status: Literal['not_generated', 'blocked'] = 'not_generated'
    code: Literal['not_generated', 'sandbox_unverified'] = 'not_generated'
    tex_sha256: str | None = Field(default=None, pattern='^[a-f0-9]{64}$')
    attempt_id: str | None = Field(default=None, pattern='^[a-f0-9]{32}$')
    created_at: str | None = None
    # Reservados: esta versión nunca afirma haber generado/validado un PDF.
    pdf_sha256: None = None
    compiler: None = None
    compiler_version: None = None
    pages: None = None
    diagnostics: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=lambda: [
        'El PDF requiere revisión visual; no se ha verificado equivalencia de maquetación.'])
