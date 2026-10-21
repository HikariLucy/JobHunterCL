"""Ofertas y seguimiento."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from jobhunter.storage import STATUSES

from ..deps import get_db, get_profile
from ..schemas import HistoryEntry, Job, JobPage, JobUpdate
from ..services import jobs as svc
from ..services import search

router = APIRouter(tags=["ofertas"])


@router.get("/jobs", response_model=JobPage)
def list_jobs(status: list[str] = Query(default=[]), min_score: int = Query(0, ge=0, le=100),
              q: str = Query("", max_length=200), source: str = Query("", max_length=200),
              sort: str = Query("score", pattern="^(score|recent)$"),
              eligibility: str = Query("", pattern="^(|compatible|desconocida|incompatible)$"),
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
              db=Depends(get_db), profile=Depends(get_profile)):
    bad = [s for s in status if s not in STATUSES]
    if bad:
        raise HTTPException(422, f"Estado desconocido: {bad[0]}")
    return svc.query(db, profile, statuses=status, min_score=min_score, q=q, source=source,
                     sort=sort, limit=limit, offset=offset, eligibility=eligibility)


@router.get("/jobs/sources", response_model=list[str])
def job_sources(db=Depends(get_db)):
    return [r[0] for r in db.execute("SELECT DISTINCT source FROM jobs ORDER BY source")]


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, db=Depends(get_db), profile=Depends(get_profile)):
    try:
        return svc.get(db, profile, job_id)
    except svc.JobNotFound:
        raise HTTPException(404, "Oferta no encontrada") from None


@router.patch("/jobs/{job_id}", response_model=Job)
def update_job(job_id: str, body: JobUpdate, db=Depends(get_db), profile=Depends(get_profile)):
    try:
        return svc.update(db, profile, job_id, body.status, body.notes)
    except svc.JobNotFound:
        raise HTTPException(404, "Oferta no encontrada") from None


@router.get("/jobs/{job_id}/history", response_model=list[HistoryEntry])
def job_history(job_id: str, db=Depends(get_db)):
    return svc.history(db, job_id)


@router.get("/tracking")
def tracking(db=Depends(get_db), profile=Depends(get_profile)):
    rows = svc.all_scored(db, profile)
    active = [j for j in rows if j["status"] != "Nueva"]
    active.sort(key=lambda j: (STATUSES.index(j["status"]), -j["score"]))
    return {"statuses": list(STATUSES), "counts": svc.status_counts(db),
            "items": active, "recent_changes": svc.recent_history(db)}


@router.get("/dashboard")
def dashboard(db=Depends(get_db), profile=Depends(get_profile)):
    rows = svc.all_scored(db, profile)
    min_score = int(profile.get("min_score", 30))
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    new_matches = sorted((j for j in rows if j["status"] == "Nueva" and j["score"] >= min_score),
                         key=lambda j: (-j["score"], j["title"]))
    return {
        "total": len(rows),
        "counts": svc.status_counts(db),
        "min_score": min_score,
        "new_matches_count": len(new_matches),
        "top_matches": new_matches[:6],
        "seen_last_7_days": sum(1 for j in rows if j["first_seen"] >= week_ago),
        "search": search.status(db, profile),
        "recent_changes": svc.recent_history(db, limit=8),
    }
