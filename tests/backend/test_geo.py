"""Metadatos geográficos: persistencia, combinación de evidencia y respuesta de la API."""
from backend.services import geo, search
from jobhunter.collect import normalize_getonbrd_api
from jobhunter.storage import job_id

from ..test_getonbrd_api import item

PROFILE = {"titles": ["desarrollador junior"], "skills": ["python"], "locations": ["santiago", "chile", "remoto", "latam"],
           "min_score": 0, "sources": {"getonbrd": True, "getonbrd_api": True}}


def feed_version(slug, location):
    return {"source": "Get on Board", "title": f"Oferta {slug}", "company": "Acme", "location": location,
            "url": f"https://www.getonbrd.com/jobs/programacion/{slug}", "description": "Texto del feed"}


def api_version(slug, remote):
    return normalize_getonbrd_api(item(slug, remote=remote, countries=("Remote",)), "programacion")


def test_merge_keeps_feed_country_list_as_evidence():
    merged = geo.merge_evidence(feed_version("a-1", "Perú, Colombia, Argentina , Chile"), api_version("a-1", "remote_local"))
    assert merged["geo"]["countries"] == ["Perú", "Colombia", "Argentina", "Chile"]
    assert merged["location"] == "Remoto (Perú, Colombia, Argentina, Chile)" and "feed" in merged["geo"]["evidence"]
    # Sin lista explícita en el feed, la incertidumbre se mantiene.
    same = geo.merge_evidence(feed_version("b-2", "Remoto"), api_version("b-2", "remote_local"))
    assert same["geo"]["countries"] == [] and "por confirmar" in same["location"]


def test_search_persists_geo_and_api_reports_eligibility(client, settings):
    from backend import db as dbmod
    db = dbmod.connect(settings.db_path)
    feed = [feed_version("a-1", "Perú, Chile"), feed_version("b-2", "Remoto")]
    api = [api_version("a-1", "remote_local"), api_version("b-2", "remote_local"), api_version("c-3", "fully_remote")]
    search.run_search(db, PROFILE, source_factory=lambda s: [("Get on Board", lambda: feed), ("Get on Board API", lambda: api)])
    stored = geo.load_all(db)
    assert len(stored) == 3 and stored[job_id(api[0]["url"])]["countries"] == ["Perú", "Chile"]
    db.close()
    client.put("/api/profile", json=PROFILE)
    items = {j["url"].rsplit("/", 1)[1]: j for j in client.get("/api/jobs", params={"limit": 50}).json()["items"]}
    assert items["a-1"]["eligibility"]["status"] == "compatible"
    assert items["b-2"]["eligibility"]["status"] == "desconocida"   # visible, no descartada
    assert items["c-3"]["eligibility"]["status"] == "compatible" and items["c-3"]["eligibility"]["basis"] == "metadatos"
    assert "geo" not in items["a-1"]
    pending = client.get("/api/jobs", params={"eligibility": "desconocida"}).json()
    assert [j["url"].rsplit("/", 1)[1] for j in pending["items"]] == ["b-2"]
    assert client.get("/api/jobs", params={"eligibility": "otra"}).status_code == 422
    assert client.get(f"/api/jobs/{job_id(api[1]['url'])}").json()["eligibility"]["status"] == "desconocida"


def test_backup_roundtrip_keeps_geo_and_rejects_malformed(client, settings, tmp_path):
    import json as _json
    from fastapi.testclient import TestClient
    from backend import db as dbmod
    from backend.main import create_app
    db = dbmod.connect(settings.db_path)
    api = [api_version("c-3", "fully_remote"), api_version("b-2", "remote_local")]
    search.run_search(db, PROFILE, source_factory=lambda s: [("Get on Board API", lambda: api)])
    db.close()
    payload = client.get("/api/backup/export").json()
    assert {r["modality"] for r in payload["job_geo"]} == {"fully_remote", "remote_local"}
    other = settings.__class__(data_dir=tmp_path / "otro", frontend_dist=settings.frontend_dist,
                               allowed_hosts=settings.allowed_hosts, scheduler_enabled=False)
    with TestClient(create_app(other)) as c2:
        assert c2.post("/api/backup/import", content=_json.dumps(payload).encode()).status_code == 200
        c2.put("/api/profile", json=PROFILE)
        statuses = {j["url"].rsplit("/", 1)[1]: j["eligibility"]["status"] for j in c2.get("/api/jobs").json()["items"]}
        assert statuses == {"c-3": "compatible", "b-2": "desconocida"}
        bad = {**payload, "job_geo": {"no": "lista"}}
        assert c2.post("/api/backup/import", content=_json.dumps(bad).encode()).status_code == 422
        legacy = {k: v for k, v in payload.items() if k != "job_geo"}  # respaldos anteriores
        assert c2.post("/api/backup/import", content=_json.dumps(legacy).encode()).status_code == 200
