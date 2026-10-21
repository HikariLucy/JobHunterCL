"""Conectores de lectura para publicaciones públicas (sin inicio de sesión)."""
from __future__ import annotations
import re
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


def build_sources(sources: dict) -> list[tuple[str, Callable[[], list[dict]]]]:
    """Lista (nombre, función) de las fuentes habilitadas en el perfil."""
    jobsources = []
    if sources.get("getonbrd", True):
        jobsources.append(("Get on Board", getonbrd))
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
