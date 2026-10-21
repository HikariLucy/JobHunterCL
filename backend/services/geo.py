"""Metadatos geográficos estructurados por oferta (tabla `job_geo`, esquema v2).

Las fuentes que conocen la modalidad remota o los países elegibles (API de Get on
Board) los adjuntan como `job["geo"]`. Se guardan aparte para que
`matching.eligibility()` no dependa solo del texto visible de ubicación.
"""
from __future__ import annotations
import json

from jobhunter.matching import is_place_list
from jobhunter.storage import job_id, now


def merge_evidence(previous: dict, current: dict) -> dict:
    """Misma oferta desde dos fuentes: gana `current` (la más completa), pero si sus
    metadatos no informan países y `previous` lista países explícitos (el feed lo hace
    para las remotas restringidas), esa lista se conserva como evidencia."""
    geo = current.get("geo")
    if not geo or geo.get("countries") or not is_place_list(previous.get("location", "")):
        return current
    countries = [c.strip() for c in str(previous["location"]).split(",") if c.strip()]
    merged = {**geo, "countries": countries, "evidence": f"{geo.get('evidence', '')} + feed (lista de países)"}
    location = current.get("location", "")
    if geo.get("modality") == "remote_local":
        location = f"Remoto ({', '.join(countries)})"
    return {**current, "geo": merged, "location": location}


def save(db, jobs: list[dict]) -> int:
    rows = [(job_id(j["url"]), str(g.get("modality") or ""), json.dumps(list(g.get("countries") or []), ensure_ascii=False),
             str(g.get("evidence") or "")[:200], now())
            for j in jobs if (g := j.get("geo"))]
    db.executemany("""INSERT INTO job_geo(job_id, modality, countries, evidence, updated_at) VALUES (?,?,?,?,?)
                      ON CONFLICT(job_id) DO UPDATE SET modality=excluded.modality, countries=excluded.countries,
                      evidence=excluded.evidence, updated_at=excluded.updated_at""", rows)
    db.commit()
    return len(rows)


def _row(r) -> dict:
    try:
        countries = [str(c) for c in json.loads(r["countries"] or "[]")][:50]
    except (ValueError, TypeError):
        countries = []
    return {"modality": r["modality"], "countries": countries, "evidence": r["evidence"]}


def load_all(db) -> dict[str, dict]:
    return {r["job_id"]: _row(r) for r in db.execute("SELECT * FROM job_geo")}


def load(db, uid: str) -> dict | None:
    r = db.execute("SELECT * FROM job_geo WHERE job_id=?", (uid,)).fetchone()
    return _row(r) if r else None
