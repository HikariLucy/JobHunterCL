"""Conector de la API pública de Get on Board, sin red (sesión simulada)."""
import pytest
import requests

from backend import db as dbmod
from backend.services import search
from jobhunter.collect import PartialFetch, getonbrd_api, normalize_getonbrd_api, parse_getonbrd_rss
from jobhunter.matching import source_meta
from jobhunter.storage import job_id


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    dbmod.migrate(path, tmp_path / "backups")
    conn = dbmod.connect(path)
    yield conn
    conn.close()


def item(slug, *, seniority=2, modality=1, remote="hybrid", countries=("Chile",), category="Programación",
         company="Acme", salary=(None, None), published=1792605757):
    return {"id": slug, "type": "job", "links": {"public_url": f"https://www.getonbrd.com/jobs/{slug}"},
            "attributes": {
                "title": f"Oferta {slug}", "description": "<p>Python y <b>SQL</b></p>", "functions": "<p>Soporte</p>",
                "desirable": "", "remote_modality": remote, "countries": list(countries), "category_name": category,
                "seniority": {"data": {"id": seniority, "type": "seniority"}},
                "modality": {"data": {"id": modality, "type": "modality"}},
                "company": {"data": {"id": "acme", "type": "company", "attributes": {"name": company}}},
                "min_salary": salary[0], "max_salary": salary[1], "published_at": published}}


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    """routes: {(ruta, página): FakeResponse | Exception}; lo no definido devuelve una página vacía."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, timeout=None):
        path = url.split("/api/v0", 1)[1]
        self.calls.append((path, dict(params or {})))
        result = self.routes.get((path, params["page"]), FakeResponse(payload={"data": [], "meta": {"total_pages": 1}}))
        if isinstance(result, Exception):
            raise result
        return result


def page(items, total=1):
    return FakeResponse(payload={"data": items, "meta": {"total_pages": total}})


def run(routes, **kw):
    session, sleeps = FakeSession(routes), []
    jobs = getonbrd_api(session=session, sleep=sleeps.append, **kw)
    return jobs, session, sleeps


def test_normalization_matches_feed_format_and_id():
    job = normalize_getonbrd_api(item("soporte-ti-junior-acme-santiago", salary=(1000, 1500)), "programacion")
    feed_url = "https://www.getonbrd.com/jobs/programacion/soporte-ti-junior-acme-santiago"
    assert job["url"] == feed_url and job_id(job["url"]) == job_id(feed_url)
    assert job["description"].startswith(
        "Nivel: Junior · Jornada: Full time · Categoría: Programación · Renta: 1000 - 1500 USD/mes Requisitos: Python y SQL")
    assert "Funciones: Soporte" in job["description"] and "<" not in job["description"]
    assert job["company"] == "Acme" and job["location"] == "Chile (híbrido)" and job["source"] == "Get on Board"
    assert job["posted_at"].endswith(" UTC")
    assert source_meta(job["description"]) == {"level": "junior", "category": "programacion"}


@pytest.mark.parametrize("remote, countries, expected", [
    ("fully_remote", ("Remote",), "Remoto"),
    ("remote_local", ("Remote",), "Remoto (incluye Chile)"),
    ("no_remote", ("Chile",), "Chile (presencial)"),
    ("hybrid", (), "Chile (híbrido)"),
])
def test_location_by_remote_modality(remote, countries, expected):
    assert normalize_getonbrd_api(item("x-1", remote=remote, countries=countries), "programacion")["location"] == expected


def test_category_names_use_feed_vocabulary():
    for slug, name in (("data-science-analytics", "data science / analytics"), ("cybersecurity", "ciberseguridad"),
                       ("technical-support", "soporte tecnico"), ("machine-learning-ai", "machine learning / ai")):
        assert source_meta(normalize_getonbrd_api(item("x-1"), slug)["description"])["category"] == name


def test_rejects_unsafe_ids_and_non_tech_categories():
    assert normalize_getonbrd_api(item("../etc"), "programacion") is None
    assert normalize_getonbrd_api(item("ok-1"), "comercial-ventas") is None


def test_paginates_filters_remote_and_deduplicates():
    routes = {
        ("/categories/programacion/jobs", 1): page([item("a-1"), item("b-2")], total=2),
        ("/categories/programacion/jobs", 2): page([item("c-3")], total=2),
        ("/search/jobs", 1): page([
            item("r-1", remote="fully_remote", category="Programación"),
            item("a-1", remote="fully_remote", category="Programación"),       # duplicada
            item("v-1", remote="fully_remote", category="Comercial y Ventas"),  # no técnica
            item("l-1", remote="remote_local", category="Programación"),        # no es totalmente remota
        ]),
    }
    stats = {}
    jobs, session, sleeps = run(routes, categories=("programacion",), stats=stats)
    assert sorted(j["url"].rsplit("/", 1)[1] for j in jobs) == ["a-1", "b-2", "c-3", "r-1"]
    assert [c[0] for c in session.calls] == ["/categories/programacion/jobs"] * 2 + ["/search/jobs"]
    assert session.calls[0][1]["country_code"] == "cl" and session.calls[2][1]["remote"] == "true"
    assert all(c[1]["per_page"] == 120 and c[1]["lang"] == "es" for c in session.calls)
    assert stats["requests"] == 3 and len(sleeps) == 2  # pausa entre peticiones, no antes de la primera


def test_remote_search_accepts_feed_category_names_and_reports_unknown():
    """Con lang=es la búsqueda devuelve «Machine Learning / AI» (no «Machine Learning & AI»)."""
    routes = {("/search/jobs", 1): page([
        item("m-1", remote="fully_remote", category="Machine Learning / AI"),
        item("v-1", remote="fully_remote", category="Comercial y Ventas"),
        item("n-1", remote="fully_remote", category="Categoría Nueva"),
    ])}
    stats = {}
    jobs, _, _ = run(routes, categories=("machine-learning-ai",), stats=stats)
    assert [j["url"] for j in jobs] == ["https://www.getonbrd.com/jobs/machine-learning-ai/m-1"]
    assert stats["remote_non_tech"] == {"Comercial y Ventas": 1}
    assert stats["unknown_categories"] == {"Categoría Nueva": 1}


def test_page_limit_bounds_requests():
    routes = {("/categories/programacion/jobs", n): page([item(f"j-{n}")], total=50) for n in range(1, 51)}
    stats = {}
    jobs, session, _ = run(routes, categories=("programacion",), max_pages=3, stats=stats)
    assert len(jobs) == 3 and stats["truncated"] == 1 and stats["requests"] == 4  # 3 + búsqueda remota


def test_empty_responses():
    jobs, session, _ = run({}, categories=("programacion", "cybersecurity"))
    assert jobs == [] and len(session.calls) == 3


def test_rate_limit_stops_without_retrying():
    routes = {("/categories/programacion/jobs", 1): FakeResponse(429, headers={"Retry-After": "120"})}
    session = FakeSession(routes)
    with pytest.raises(requests.HTTPError):
        search.fetch_with_retries(lambda: getonbrd_api(session=session, sleep=lambda s: None,
                                                       categories=("programacion",)), sleep=lambda s: None)
    assert len(session.calls) == 1


def test_failure_after_some_pages_keeps_partial_results():
    routes = {
        ("/categories/programacion/jobs", 1): page([item("a-1")], total=2),
        ("/categories/programacion/jobs", 2): requests.ConnectionError("red caída"),
    }
    with pytest.raises(PartialFetch) as exc:
        run(routes, categories=("programacion",))
    assert [j["url"].rsplit("/", 1)[1] for j in exc.value.jobs] == ["a-1"]


def test_network_failure_on_first_request_is_plain_error():
    with pytest.raises(requests.ConnectionError):
        run({("/categories/programacion/jobs", 1): requests.ConnectionError("sin red")}, categories=("programacion",))


FEED = '''<?xml version="1.0" encoding="UTF-8"?><source><job>
<title><![CDATA[Oferta a-1]]></title><url><![CDATA[https://www.getonbrd.com/jobs/programacion/a-1]]></url>
<company><![CDATA[Acme]]></company><country><![CDATA[Chile]]></country>
<description><![CDATA[Texto breve del feed]]></description></job></source>'''.encode("utf-8")


def test_search_merges_feed_and_api_once_and_keeps_partial(db):
    feed = parse_getonbrd_rss(FEED)
    api = normalize_getonbrd_api(item("a-1"), "programacion")
    extra = normalize_getonbrd_api(item("z-9"), "programacion")

    def partial():
        raise PartialFetch([api, extra], requests.ConnectionError("corte"))

    profile = {"titles": [], "skills": ["python"], "locations": ["chile"],
               "sources": {"getonbrd": True, "getonbrd_api": True}}
    run_ = search.run_search(db, profile, source_factory=lambda s: [("Get on Board", lambda: feed),
                                                                     ("Get on Board API", partial)])
    assert run_["status"] == "partial" and run_["fetched"] == 2 and run_["added"] == 2
    assert "parcial (2 ofertas)" in run_["errors"][0]
    stored = {r["url"]: r for r in db.execute("SELECT url, description FROM jobs")}
    assert stored["https://www.getonbrd.com/jobs/programacion/a-1"]["description"].startswith("Nivel: Junior")


def test_api_raises_minimum_interval():
    assert search.min_interval({"getonbrd": True}).total_seconds() == 30 * 60
    assert search.min_interval({"getonbrd": True, "getonbrd_api": True}).total_seconds() == 60 * 60
    assert search.min_interval({"getonbrd_api": True, "remotive": True}).total_seconds() == 6.5 * 3600
