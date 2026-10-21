"""Persistencia local SQLite. No publica CV ni credenciales en GitHub."""
from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

DB_PATH = Path("data/jobs.sqlite3")
STATUSES = ("Nueva", "Revisar", "Preparada", "Postulada", "Descartada")


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(url: str) -> str:
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(q), ""))


def connection(path: Path = DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, source TEXT NOT NULL, title TEXT NOT NULL,
        company TEXT NOT NULL, location TEXT, url TEXT NOT NULL, description TEXT,
        posted_at TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Nueva', notes TEXT NOT NULL DEFAULT '')""")
    db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.commit()
    return db


def job_id(url: str) -> str:
    return hashlib.sha256(canonical(url).encode("utf-8")).hexdigest()[:24]


def upsert_jobs(db, jobs: list[dict]) -> int:
    added = 0
    for job in jobs:
        url = job.get("url", "")
        if not url.startswith("https://") or not job.get("title"):
            continue
        uid = job_id(url)
        existed = db.execute("SELECT 1 FROM jobs WHERE id=?", (uid,)).fetchone()
        db.execute("""INSERT INTO jobs (id,source,title,company,location,url,description,posted_at,first_seen,last_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            source=excluded.source,title=excluded.title,company=excluded.company,
            location=excluded.location,url=excluded.url,description=excluded.description,
            posted_at=excluded.posted_at,last_seen=excluded.last_seen""",
            (uid, job.get("source", ""), job["title"], job.get("company", ""),
             job.get("location", ""), url, job.get("description", ""), job.get("posted_at", ""), now(), now()))
        added += int(not existed)
    db.commit()
    return added


def list_jobs(db):
    return [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY first_seen DESC")]


def set_status(db, uid, status):
    if status not in STATUSES:
        raise ValueError("Estado inválido")
    db.execute("UPDATE jobs SET status=? WHERE id=?", (status, uid))
    db.commit()


def set_notes(db, uid, notes):
    db.execute("UPDATE jobs SET notes=? WHERE id=?", (notes[:5000], uid))
    db.commit()


def get_setting(db, key, default=""):
    row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_setting(db, key, value):
    db.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    db.commit()


def export_backup(db, profile: dict | None = None) -> bytes:
    rows = list_jobs(db)
    return json.dumps({"format": "jobhuntercl-backup-v1", "jobs": rows, "profile": profile}, ensure_ascii=False, indent=2).encode("utf8")


def import_backup(db, content: bytes) -> int:
    if len(content) > 15_000_000:
        raise ValueError("Respaldo demasiado grande")
    payload = json.loads(content)
    if not isinstance(payload, dict) or payload.get("format") != "jobhuntercl-backup-v1" or not isinstance(payload.get("jobs"), list):
        raise ValueError("Formato de respaldo no válido")
    items = payload["jobs"]
    if len(items) > 10_000:
        raise ValueError("Demasiados registros")
    count = 0
    for job in items:
        if not isinstance(job, dict) or not str(job.get("url", "")).startswith("https://") or not job.get("title"):
            continue
        uid = job_id(job["url"])
        db.execute("""INSERT INTO jobs(id,source,title,company,location,url,description,posted_at,first_seen,last_seen,status,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,notes=excluded.notes""",
                   (uid, str(job.get("source", "")), str(job["title"]), str(job.get("company", "")),
                    str(job.get("location", "")), str(job["url"]), str(job.get("description", ""))[:10000],
                    str(job.get("posted_at", "")), str(job.get("first_seen", now())),
                    str(job.get("last_seen", now())),
                    job.get("status", "Nueva") if job.get("status") in STATUSES else "Nueva",
                    str(job.get("notes", ""))[:5000]))
        count += 1
    db.commit()
    return count


def get_backup_profile(content: bytes) -> dict | None:
    """Extrae perfil validado de un respaldo; no acepta estructuras arbitrarias."""
    payload = json.loads(content)
    if not isinstance(payload, dict) or payload.get("format") != "jobhuntercl-backup-v1":
        raise ValueError("Formato de respaldo no válido")
    profile = payload.get("profile")
    if profile is None:
        return None
    if not isinstance(profile, dict):
        raise ValueError("Perfil inválido")
    for key in ("titles", "skills", "locations"):
        values = profile.get(key, [])
        if not isinstance(values, list) or len(values) > 100 or not all(isinstance(v, str) and len(v) < 200 for v in values):
            raise ValueError("Campo de perfil inválido")
    sources = profile.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("Fuentes inválidas")
    return profile
