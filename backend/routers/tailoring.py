"""API de adaptación: los cuerpos nunca aceptan citas, spans ni reemplazos."""
from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from ..cv_contracts import JobAnalysis, TailoringPlan, TailoringPreview
from ..pdf_contracts import PdfCapabilities, PdfRequest, PdfStatus
from ..services.pdf_environment import capabilities
from ..services.pdf_service import PdfService
from ..deps import get_db, get_settings
from ..services.cv_store import CvError
from ..services.job_analysis import analyze
from ..services.tailoring_store import TailoringStore

router=APIRouter(prefix='/tailoring',tags=['adaptación CV'])


class StrictBody(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)


class CreatePlan(StrictBody):
    job_id: str = Field(min_length=1,max_length=200)
    cv_id: str = Field(pattern='^[a-f0-9]{32}$')
    expected_cv_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    lang: Literal['es','en']


class Decision(StrictBody):
    expected_revision: int = Field(ge=1)
    status: Literal['accepted','rejected','pending']


class Generate(StrictBody):
    expected_revision: int = Field(ge=1)
    preview_sha256: str = Field(pattern='^[a-f0-9]{64}$')


@contextmanager
def service(settings,db):
    try:
        yield TailoringStore(settings,db)
    except CvError as exc:
        raise HTTPException(exc.status,exc.message) from None
    except (OSError,UnicodeError,ValueError):
        raise HTTPException(500,'No se pudo completar la operación en el almacenamiento privado de adaptación.') from None


@router.get('/jobs/{job_id}/analysis',response_model=JobAnalysis)
def analysis(job_id: str, settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return analyze(svc.job(job_id))


@router.post('/plans',response_model=TailoringPlan,status_code=201)
def create(body: CreatePlan,settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return svc.create(body.job_id,body.cv_id,body.expected_cv_sha256,body.lang)


@router.get('/plans/{plan_id}',response_model=TailoringPlan)
def get(plan_id: str,settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return svc.get(plan_id)


@router.patch('/plans/{plan_id}/suggestions/{suggestion_id}',response_model=TailoringPlan)
def decide(plan_id: str,suggestion_id: str,body: Decision,settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return svc.decide(plan_id,suggestion_id,body.status,body.expected_revision)


@router.get('/plans/{plan_id}/preview',response_model=TailoringPreview)
def preview(plan_id: str,expected_revision: int=Query(ge=1),settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return svc.preview(plan_id,expected_revision)


@router.post('/plans/{plan_id}/generate',response_model=TailoringPlan)
def generate(plan_id: str,body: Generate,settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return svc.generate(plan_id,body.expected_revision,body.preview_sha256)


@router.get('/plans/{plan_id}/download')
def download(plan_id: str,settings=Depends(get_settings),db=Depends(get_db)):
    with service(settings,db) as svc:
        return Response(svc.download(plan_id),media_type='application/x-tex',headers={
            'Content-Disposition':'attachment; filename="cv-adaptado.tex"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


# M2.3: no se acepta contenido TeX ni se ejecuta ningún compilador.


@router.get('/pdf/capabilities', response_model=PdfCapabilities)
def pdf_capabilities():
    return capabilities()


@router.post('/plans/{plan_id}/pdf', response_model=PdfStatus)
def generate_pdf(plan_id: str, body: PdfRequest, settings=Depends(get_settings), db=Depends(get_db)):
    with service(settings, db) as svc:
        return PdfService(svc).generate(plan_id, body.expected_revision, body.expected_tex_sha256)


@router.get('/plans/{plan_id}/pdf', response_model=PdfStatus)
def pdf_status(plan_id: str, expected_revision: int=Query(ge=1), settings=Depends(get_settings), db=Depends(get_db)):
    with service(settings, db) as svc:
        return PdfService(svc).status(plan_id, expected_revision)


@router.get('/plans/{plan_id}/pdf/download')
def download_pdf(plan_id: str, expected_revision: int=Query(ge=1), settings=Depends(get_settings), db=Depends(get_db)):
    with service(settings, db) as svc:
        return PdfService(svc).download(plan_id, expected_revision)
