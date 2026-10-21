"""Búsqueda manual y estado del programador."""
from __future__ import annotations
import math

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_db, get_profile
from ..schemas import ScanRun, SearchStatus
from ..services import search

router = APIRouter(tags=["búsqueda"])


@router.get("/search/status", response_model=SearchStatus)
def search_status(db=Depends(get_db), profile=Depends(get_profile)):
    return search.status(db, profile)


@router.post("/search", response_model=ScanRun)
def run_search(db=Depends(get_db), profile=Depends(get_profile)):
    """Consulta las fuentes habilitadas. Requiere internet; respeta la espera mínima."""
    try:
        return search.run_search(db, profile, trigger="manual")
    except search.SearchBusy as exc:
        raise HTTPException(409, str(exc)) from None
    except search.CooldownActive as exc:
        wait = max(1, math.ceil((exc.next_allowed - search.utcnow()).total_seconds()))
        raise HTTPException(429, {"message": str(exc), "next_allowed_at": exc.next_allowed.isoformat()},
                            headers={"Retry-After": str(wait)}) from None
