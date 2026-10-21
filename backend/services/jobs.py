"""Consulta, puntuación y seguimiento de ofertas (reutiliza jobhunter.matching)."""
from __future__ import annotations
import sqlite3

from jobhunter.matching import evaluate, norm
from jobhunter.storage import STATUSES, list_jobs, now, set_notes, set_status


class JobNotFound(LookupError):
    pass


def score(job: dict, profile: dict) -> dict:
    s, reasons, warnings = evaluate(job, profile)
    return {**job, "score": s, "reasons": reasons, "warnings": warnings}


def all_scored(db: sqlite3.Connection, profile: dict) -> list[dict]:
    return [score(j, profile) for j in list_jobs(db)]


def query(db, profile, *, statuses=None, min_score=0, q="", source="", sort="score",
          limit=50, offset=0) -> dict:
    rows = all_scored(db, profile)
    stored = len(rows)
    needle = norm(q)
    out = []
    for j in rows:
        if statuses and j["status"] not in statuses:
            continue
        if j["score"] < min_score:
            continue
        if source and j["source"] != source:
            continue
        if needle and needle not in norm(f"{j['title']} {j['company']} {j['location'] or ''}"):
            continue
        out.append(j)
    if sort == "recent":
        out.sort(key=lambda j: j["first_seen"], reverse=True)
    else:
        out.sort(key=lambda j: (-j["score"], j["title"]))
    return {"items": out[offset:offset + limit], "total": len(out), "stored": stored}


def get(db, profile, job_id: str) -> dict:
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise JobNotFound(job_id)
    return score(dict(row), profile)


def update(db, profile, job_id: str, status: str | None, notes: str | None) -> dict:
    current = get(db, profile, job_id)
    if status is not None and status != current["status"]:
        if status not in STATUSES:
            raise ValueError("Estado inválido")
        set_status(db, job_id, status)
        db.execute("INSERT INTO status_history(job_id, old_status, new_status, changed_at, origin) VALUES (?,?,?,?,?)",
                   (job_id, current["status"], status, now(), "api"))
        db.commit()
    if notes is not None:
        set_notes(db, job_id, notes)
    return get(db, profile, job_id)


def history(db, job_id: str) -> list[dict]:
    return [dict(r) for r in db.execute(
        "SELECT * FROM status_history WHERE job_id=? ORDER BY changed_at DESC, id DESC", (job_id,))]


def recent_history(db, limit=20) -> list[dict]:
    return [dict(r) for r in db.execute(
        """SELECT h.*, j.title, j.company FROM status_history h LEFT JOIN jobs j ON j.id = h.job_id
           ORDER BY h.changed_at DESC, h.id DESC LIMIT ?""", (limit,))]


def status_counts(db) -> dict[str, int]:
    counts = {s: 0 for s in STATUSES}
    for status, n in db.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status"):
        counts[status] = counts.get(status, 0) + n
    return counts
