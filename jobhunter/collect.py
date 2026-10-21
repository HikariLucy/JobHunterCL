"""Conectores de lectura para publicaciones públicas (sin inicio de sesión)."""
from __future__ import annotations
import re
import time
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import quote
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

UA = "JobHunterCL/0.1 (buscador personal, acceso puntual a feeds publicos)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "application/json, application/xml, text/xml, */*"})


def plain(s: str) -> str:
    return " ".join(BeautifulSoup(s or "", "html.parser").get_text(" ", strip=True).split())


def valid_token(token: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{2,70}", token))


def _field(item, *names) -> str:
    """Primer hijo cuyo nombre (sin namespace) coincide; tolera CDATA con espacios."""
    for el in item:
        name = el.tag.split("}")[-1].lower()
        if name in names and el.text and el.text.strip():
            return el.text.strip()
    return ""


def parse_getonbrd_rss(content: bytes) -> list[dict]:
    """Lee el feed público de Get on Board.

    Formato actual (verificado 2026-10): XML tipo Indeed `<source><job>…</job></source>`.
    Se mantiene compatibilidad con RSS 2.0 (`<item>`) por si el portal vuelve a ese formato.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError("Respuesta del feed ilegible") from exc

    results = []
    for item in root.iter():
        if item.tag.split("}")[-1].lower() not in ("item", "job"):
            continue
        url = _field(item, "url", "link")
        title = plain(_field(item, "title"))
        if not (url.startswith("https://") and title):
            continue
        place = ", ".join(x for x in (plain(_field(item, "city")), plain(_field(item, "region")),
                                      plain(_field(item, "country", "location"))) if x)
        meta = " · ".join(f"{label}: {plain(value)}" for label, value in (
            ("Nivel", _field(item, "experience")), ("Jornada", _field(item, "jobtype")),
            ("Categoría", _field(item, "category")), ("Renta", _field(item, "salary"))) if value)
        body = " ".join(x for x in (meta, plain(_field(item, "description", "encoded", "summary")),
                                    plain(_field(item, "content"))) if x)
        company = plain(_field(item, "company", "author", "creator")) or "No indicada"
        results.append({"source": "Get on Board", "title": title, "company": company,
                        "location": place or "No indicada (verificar en oferta)",
                        "url": url, "description": body[:10000],
                        "posted_at": _field(item, "date", "pubdate", "published")})
    if not results and root.tag.split("}")[-1].lower() not in ("rss", "source", "feed"):
        raise ValueError(f"Formato de feed no reconocido: <{root.tag}>")
    return results


def getonbrd() -> list[dict]:
    r = SESSION.get("https://www.getonbrd.com/jobs/feed", timeout=(6, 30))
    r.raise_for_status()
    return parse_getonbrd_rss(r.content)


def remotive() -> list[dict]:
    r = SESSION.get("https://remotive.com/api/remote-jobs", params={"limit": 100}, timeout=(6, 30))
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    return [{"source": "Remotive", "title": plain(j.get("title", "")),
             "company": plain(j.get("company_name", "")) or "No indicada",
             "location": plain(j.get("candidate_required_location", "")) or "Remoto (revisar países elegibles)",
             "url": j.get("url", ""), "description": plain(j.get("description", ""))[:10000],
             "posted_at": j.get("publication_date", "")} for j in jobs if str(j.get("url", "")).startswith("https://")]


def greenhouse(board: str) -> list[dict]:
    if not valid_token(board):
        raise ValueError("Identificador de empresa inválido (Greenhouse)")
    r = SESSION.get(f"https://boards-api.greenhouse.io/v1/boards/{quote(board)}/jobs",
                    params={"content": "true"}, timeout=(6, 30))
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    return [{"source": f"Greenhouse/{board}", "title": plain(j.get("title", "")),
             "company": board, "location": (j.get("location") or {}).get("name", ""),
             "url": j.get("absolute_url", ""), "description": plain(j.get("content", ""))[:10000],
             "posted_at": j.get("updated_at", "")} for j in jobs if str(j.get("absolute_url", "")).startswith("https://")]


def lever(site: str) -> list[dict]:
    if not valid_token(site):
        raise ValueError("Identificador de empresa inválido (Lever)")
    r = SESSION.get(f"https://api.lever.co/v0/postings/{quote(site)}",
                    params={"mode": "json", "limit": 100}, timeout=(6, 30))
    r.raise_for_status()
    jobs = r.json()
    return [{"source": f"Lever/{site}", "title": plain(j.get("text", "")),
             "company": site, "location": (j.get("categories") or {}).get("location", ""),
             "url": j.get("hostedUrl", ""),
             "description": plain(j.get("descriptionPlain", "") or j.get("description", ""))[:10000],
             "posted_at": ""} for j in jobs if str(j.get("hostedUrl", "")).startswith("https://")]


class PartialFetch(Exception):
    """Una fuente paginada falló a mitad: `jobs` conserva lo obtenido hasta entonces."""

    def __init__(self, jobs: list[dict], cause: Exception):
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.jobs, self.cause = jobs, cause


# API pública de Get on Board (contrato y evidencia: docs/GETONBRD_API.md).
GOB_API = "https://www.getonbrd.com/api/v0"
GOB_TECH_CATEGORIES = {  # slug de la API -> nombre que usa el feed (lo lee matching.source_meta)
    "programacion": "Programación", "sysadmin-devops-qa": "SysAdmin / DevOps / QA",
    "data-science-analytics": "Data Science / Analytics", "machine-learning-ai": "Machine Learning / AI",
    "desarrollo-mobile": "Desarrollo Mobile", "cybersecurity": "Ciberseguridad",
    "technical-support": "Soporte Técnico",
}
GOB_SENIORITY = {1: "Sin experiencia requerida", 2: "Junior", 3: "Semi Senior", 4: "Senior", 5: "Expert"}
GOB_MODALITY = {1: "Full time", 2: "Part time", 3: "Freelance", 4: "Práctica/Internship"}
GOB_REMOTE = {"hybrid": "híbrido", "no_remote": "presencial"}
GOB_MAX_PAGES = 5
GOB_PAUSE = 1.0
GOB_EXPAND = '["company"]'
_GOB_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,200}")


def _rel_id(attrs: dict, key: str):
    data = (attrs.get(key) or {}).get("data") or {}
    try:
        return int(data.get("id"))
    except (TypeError, ValueError):
        return None


def normalize_getonbrd_api(item: dict, category_slug: str, country: str = "Chile") -> dict | None:
    """Oferta de la API en el formato del feed (mismo id interno y misma cabecera)."""
    job_id, attrs = str(item.get("id") or ""), item.get("attributes") or {}
    title = plain(attrs.get("title", ""))
    if not (_GOB_ID.fullmatch(job_id) and title and category_slug in GOB_TECH_CATEGORIES):
        return None
    company = ((attrs.get("company") or {}).get("data") or {}).get("attributes") or {}
    modality = attrs.get("remote_modality")
    if modality == "fully_remote":
        location = "Remoto"
    elif modality == "remote_local":
        location = f"Remoto (incluye {country})"
    else:
        places = ", ".join(plain(c) for c in attrs.get("countries") or [] if c) or country
        location = f"{places} ({GOB_REMOTE[modality]})" if modality in GOB_REMOTE else places
    lo, hi = attrs.get("min_salary"), attrs.get("max_salary")
    salary = f"{lo} - {hi} USD/mes" if lo and hi and lo != hi else (f"{lo or hi} USD/mes" if lo or hi else "")
    meta = " · ".join(f"{label}: {value}" for label, value in (
        ("Nivel", GOB_SENIORITY.get(_rel_id(attrs, "seniority"), "")),
        ("Jornada", GOB_MODALITY.get(_rel_id(attrs, "modality"), "")),
        ("Categoría", GOB_TECH_CATEGORIES[category_slug]), ("Renta", salary)) if value)
    body = " ".join(f"{label}: {text}" for label, text in (
        ("Requisitos", plain(attrs.get("description", ""))), ("Funciones", plain(attrs.get("functions", ""))),
        ("Deseable", plain(attrs.get("desirable", "")))) if text)
    published = attrs.get("published_at")
    posted = (datetime.fromtimestamp(published, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
              if isinstance(published, (int, float)) else "")
    return {"source": "Get on Board", "title": title, "company": plain(company.get("name", "")) or "No indicada",
            "location": location, "url": f"https://www.getonbrd.com/jobs/{category_slug}/{job_id}",
            "description": f"{meta} {body}".strip()[:10000], "posted_at": posted}


def getonbrd_api(session=None, sleep=time.sleep, country_code: str = "cl", country: str = "Chile",
                 categories=tuple(GOB_TECH_CATEGORIES), max_pages: int = GOB_MAX_PAGES,
                 stats: dict | None = None) -> list[dict]:
    """Ofertas técnicas elegibles desde el país: por categoría con `country_code` (presencial,
    híbrido o remoto restringido que lo incluye) + totalmente remotas (`search/jobs?remote=true`).

    El nivel no se filtra aquí (la API no ofrece ese filtro); lo pondera el matching.
    Un 429 detiene la fuente sin reintentar. Si una página falla tras otras correctas se
    lanza PartialFetch con lo ya obtenido, para no repetir toda la pasada.
    """
    session = session or SESSION
    stats = stats if stats is not None else {}
    stats.setdefault("requests", 0)
    by_name = {v: k for k, v in GOB_TECH_CATEGORIES.items()}
    found: dict[str, dict] = {}

    def pages(path: str, params: dict):
        for page in range(1, max_pages + 1):
            if stats["requests"]:
                sleep(GOB_PAUSE)
            stats["requests"] += 1
            r = session.get(f"{GOB_API}{path}", params={**params, "per_page": 120, "page": page,
                                                         "lang": "es", "expand": GOB_EXPAND}, timeout=(6, 30))
            r.raise_for_status()
            payload = r.json()
            data = payload.get("data") or []
            yield data
            if not data or page >= int((payload.get("meta") or {}).get("total_pages") or 1):
                return
        stats["truncated"] = stats.get("truncated", 0) + 1

    def add(item: dict, slug: str):
        job = normalize_getonbrd_api(item, slug, country)
        if job:
            found.setdefault(job["url"], job)

    try:
        for slug in categories:
            for data in pages(f"/categories/{quote(slug)}/jobs", {"country_code": country_code}):
                for item in data:
                    add(item, slug)
        for data in pages("/search/jobs", {"remote": "true"}):
            for item in data:
                attrs = item.get("attributes") or {}
                slug = by_name.get(_category_es(attrs.get("category_name", "")))
                if slug is None:
                    stats["unmapped_categories"] = stats.get("unmapped_categories", 0) + 1
                if slug in categories and attrs.get("remote_modality") == "fully_remote":
                    add(item, slug)
    except (requests.RequestException, ValueError) as exc:
        if found:
            raise PartialFetch(list(found.values()), exc) from exc
        raise
    return list(found.values())


# Nombres de categoría que devuelve la API con lang=es -> nombre del feed.
_GOB_API_CATEGORY_NAMES = {
    "programación": "Programación", "programming": "Programación",
    "sysadmin / devops / qa": "SysAdmin / DevOps / QA",
    "data / analytics": "Data Science / Analytics", "data science / analytics": "Data Science / Analytics",
    "machine learning & ai": "Machine Learning / AI", "desarrollo mobile": "Desarrollo Mobile",
    "mobile development": "Desarrollo Mobile", "cybersecurity": "Ciberseguridad", "ciberseguridad": "Ciberseguridad",
    "technical support": "Soporte Técnico", "soporte técnico": "Soporte Técnico",
}


def _category_es(name: str) -> str:
    return _GOB_API_CATEGORY_NAMES.get(str(name).strip().lower(), "")


def build_sources(sources: dict) -> list[tuple[str, Callable[[], list[dict]]]]:
    """Lista (nombre, función) de las fuentes habilitadas en el perfil."""
    jobsources = []
    if sources.get("getonbrd", True):
        jobsources.append(("Get on Board", getonbrd))
    if sources.get("getonbrd_api", False):
        jobsources.append(("Get on Board API", getonbrd_api))
    if sources.get("remotive", False):
        jobsources.append(("Remotive", remotive))
    for board in sources.get("greenhouse_boards", []):
        jobsources.append(("Greenhouse/" + board, lambda board=board: greenhouse(board)))
    for site in sources.get("lever_sites", []):
        jobsources.append(("Lever/" + site, lambda site=site: lever(site)))
    return jobsources


def fetch_all(sources: dict) -> tuple[list[dict], list[str]]:
    results, errors = [], []
    for name, fn in build_sources(sources):
        try:
            results.extend(fn())
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{name}: {str(exc)[:180]}")
    return results, errors
