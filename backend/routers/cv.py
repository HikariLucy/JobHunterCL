"""Gestión local de documentos no confiables. Nunca compila ni ejecuta LaTeX."""
from __future__ import annotations
from contextlib import contextmanager
from typing import Literal
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response

from ..cv_contracts import CvMetadata, ParsedCv
from ..deps import get_settings
from ..services.cv_store import CvError, CvStore

router = APIRouter(prefix='/cv', tags=['currículums'])


def private(response: Response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'


@contextmanager
def store(settings):
    try:
        yield CvStore(settings)
    except CvError as exc:
        raise HTTPException(exc.status, exc.message) from None
    except (OSError, UnicodeError):
        # No devolver nombres/rutas/fuente privado ni mensajes del SO al cliente.
        raise HTTPException(500, 'No se pudo completar la operación de CV. Revisa permisos y almacenamiento privado; vuelve a cargar la lista.') from None


async def bounded_body(request, limit):
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > limit:
            raise HTTPException(413, 'El CV supera el límite de tamaño configurado.')
        content.extend(chunk)
    return bytes(content)


@router.post('/import', response_model=CvMetadata, status_code=201)
async def import_cv(request: Request, response: Response, filename: str = Header(alias='X-CV-Filename', max_length=765),
                    name: str = Header(alias='X-CV-Name', min_length=1, max_length=1440), lang: Literal['es', 'en'] = Header(alias='X-CV-Lang'),
                    settings=Depends(get_settings)):
    private(response)
    content = await bounded_body(request, settings.cv_max_bytes)
    with store(settings) as svc:
        return svc.import_cv(content, unquote(filename), unquote(name), lang)


@router.get('', response_model=list[CvMetadata])
def list_cv(response: Response, settings=Depends(get_settings)):
    private(response)
    with store(settings) as svc:
        return svc.list()


@router.get('/{cv_id}', response_model=CvMetadata)
def metadata(cv_id: str, response: Response, settings=Depends(get_settings)):
    private(response)
    with store(settings) as svc:
        return svc.get(cv_id)


@router.get('/{cv_id}/preview', response_model=ParsedCv)
def preview(cv_id: str, response: Response, settings=Depends(get_settings)):
    private(response)
    with store(settings) as svc:
        return svc.preview(cv_id)


@router.put('/{cv_id}/primary', response_model=CvMetadata)
def primary(cv_id: str, response: Response, settings=Depends(get_settings)):
    private(response)
    with store(settings) as svc:
        return svc.primary(cv_id)


@router.put('/{cv_id}', response_model=CvMetadata)
async def replace_cv(cv_id: str, request: Request, response: Response, filename: str = Header(alias='X-CV-Filename', max_length=765),
                     confirm: bool = Query(), expected_sha256: str = Query(pattern='^[a-f0-9]{64}$'),
                     settings=Depends(get_settings)):
    private(response)
    if not confirm:
        raise HTTPException(422, 'Debes confirmar explícitamente la sustitución.')
    content = await bounded_body(request, settings.cv_max_bytes)
    with store(settings) as svc:
        return svc.replace(cv_id, content, unquote(filename), expected_sha256)


@router.delete('/{cv_id}')
def delete(cv_id: str, response: Response, confirm: bool = Query(),
           expected_sha256: str = Query(pattern='^[a-f0-9]{64}$'), settings=Depends(get_settings)):
    private(response)
    if not confirm:
        raise HTTPException(422, 'Debes confirmar explícitamente la eliminación.')
    with store(settings) as svc:
        return svc.delete(cv_id, expected_sha256)
