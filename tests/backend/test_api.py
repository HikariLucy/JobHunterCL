import json

from fastapi.testclient import TestClient

from backend.main import create_app
from jobhunter.storage import job_id

from .conftest import JOBS

ID1 = job_id(JOBS[0]["url"])


def test_health_reports_schema(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["schema_version"] == 1
    assert "Postulada" in body["statuses"]


def test_rejects_foreign_host_header(settings):
    with TestClient(create_app(settings), base_url="http://evil.example") as c:
        assert c.get("/api/health").status_code == 400


def test_jobs_are_scored_and_sorted(seeded):
    page = seeded.get("/api/jobs").json()
    assert page["total"] == 2 and page["stored"] == 2
    first, second = page["items"]
    assert first["id"] == ID1 and first["score"] > second["score"]
    assert any("Cargo objetivo" in r for r in first["reasons"])
    assert any("residencia" in w for w in second["warnings"])


def test_jobs_filters(seeded):
    assert seeded.get("/api/jobs", params={"min_score": 50}).json()["total"] == 1
    assert seeded.get("/api/jobs", params={"q": "globex"}).json()["total"] == 1
    assert seeded.get("/api/jobs", params={"status": ["Postulada"]}).json()["total"] == 0
    assert seeded.get("/api/jobs", params={"status": ["Inventado"]}).status_code == 422


def test_update_status_records_history(seeded):
    r = seeded.patch(f"/api/jobs/{ID1}", json={"status": "Postulada", "notes": "Enviado por portal"})
    assert r.status_code == 200
    assert r.json()["status"] == "Postulada" and r.json()["notes"] == "Enviado por portal"
    seeded.patch(f"/api/jobs/{ID1}", json={"status": "Postulada"})  # sin cambio: no duplica historial
    hist = seeded.get(f"/api/jobs/{ID1}/history").json()
    assert [(h["old_status"], h["new_status"]) for h in hist] == [("Nueva", "Postulada")]
    tracking = seeded.get("/api/tracking").json()
    assert tracking["counts"]["Postulada"] == 1
    assert tracking["items"][0]["id"] == ID1


def test_update_invalid_or_missing(seeded):
    assert seeded.patch(f"/api/jobs/{ID1}", json={"status": "Contratada"}).status_code == 422
    assert seeded.patch("/api/jobs/noexiste", json={"status": "Revisar"}).status_code == 404
    assert seeded.get("/api/jobs/noexiste").status_code == 404


def test_dashboard(seeded):
    body = seeded.get("/api/dashboard").json()
    assert body["total"] == 2
    assert body["new_matches_count"] == 1
    assert body["top_matches"][0]["id"] == ID1
    assert body["search"]["running"] is False


def test_profile_roundtrip_preserves_new_and_legacy_fields(client, settings):
    settings.profile_path.parent.mkdir(parents=True, exist_ok=True)
    settings.profile_path.write_text(json.dumps({"titles": ["soporte ti"], "custom_legacy": 1}), encoding="utf-8")
    p = client.get("/api/profile").json()
    assert p["titles"] == ["soporte ti"] and p["custom_legacy"] == 1
    p["languages"] = [{"name": "Inglés", "level": "B2"}]
    p["skills"] = ["Python", "python", "  SQL "]
    saved = client.put("/api/profile", json=p).json()
    assert saved["skills"] == ["Python", "SQL"]
    on_disk = json.loads(settings.profile_path.read_text(encoding="utf-8"))
    assert on_disk["languages"][0]["level"] == "B2" and on_disk["custom_legacy"] == 1


def test_profile_rejects_bad_source_tokens(client):
    p = client.get("/api/profile").json()
    p["sources"]["greenhouse_boards"] = ["../../etc"]
    assert client.put("/api/profile", json=p).status_code == 422


def test_config_interval_and_min_interval(client):
    cfg = client.get("/api/config").json()
    assert cfg["scan_interval_minutes"] == 0 and cfg["min_interval_minutes"] == 30
    cfg = client.put("/api/config", json={"scan_interval_minutes": 120,
                                         "sources": {"getonbrd": True, "remotive": True}}).json()
    assert cfg["scan_interval_minutes"] == 120 and cfg["min_interval_minutes"] == 390
    assert client.get("/api/profile").json()["sources"]["remotive"] is True


def test_backup_export_import_roundtrip(seeded, settings, tmp_path):
    seeded.patch(f"/api/jobs/{ID1}", json={"status": "Preparada"})
    exported = seeded.get("/api/backup/export")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["format"] == "jobhuntercl-backup-v1" and payload["status_history"]

    other = settings.__class__(data_dir=tmp_path / "otro", frontend_dist=settings.frontend_dist,
                               allowed_hosts=settings.allowed_hosts, scheduler_enabled=False)
    with TestClient(create_app(other)) as c2:
        r = c2.post("/api/backup/import", content=exported.content, headers={"Content-Type": "application/json"})
        assert r.status_code == 200, r.text
        assert r.json()["imported"] == 2 and r.json()["profile_restored"] is True
        assert r.json()["safety_copy"].startswith("jobs-pre-import-")
        assert c2.get(f"/api/jobs/{ID1}").json()["status"] == "Preparada"


def test_backup_import_rejects_garbage(client):
    assert client.post("/api/backup/import", content=b"no-json").status_code == 422
    assert client.post("/api/backup/import", content=b'{"jobs": []}').status_code == 422


def test_root_without_frontend_build_explains(client):
    assert "npm run build" in client.get("/").json()["message"]


def test_serves_spa_when_built(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    s = settings.__class__(data_dir=settings.data_dir, frontend_dist=dist,
                           allowed_hosts=settings.allowed_hosts, scheduler_enabled=False)
    with TestClient(create_app(s)) as c:
        assert "root" in c.get("/seguimiento").text
        assert c.get("/assets/app.js").status_code == 200
        assert c.get("/api/inexistente").status_code == 404
        assert "root" in c.get("/../../secret").text
