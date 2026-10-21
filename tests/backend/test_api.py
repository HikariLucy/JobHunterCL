import json

from fastapi.testclient import TestClient

from backend.main import create_app
from jobhunter.storage import connection, job_id

from .conftest import JOBS

ID1 = job_id(JOBS[0]["url"])


def test_health_reports_schema(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["schema_version"] == 2
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


def test_config_getonbrd_api_toggle(client):
    assert client.get("/api/config").json()["sources"]["getonbrd_api"] is False
    cfg = client.put("/api/config", json={"scan_interval_minutes": 0,
                                         "sources": {"getonbrd": True, "getonbrd_api": True}}).json()
    assert cfg["sources"]["getonbrd_api"] is True and cfg["min_interval_minutes"] == 60
    assert client.get("/api/profile").json()["sources"]["getonbrd"] is True


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


def _other_client(settings, tmp_path, name="otro"):
    other = settings.__class__(data_dir=tmp_path / name, frontend_dist=settings.frontend_dist,
                               allowed_hosts=settings.allowed_hosts, scheduler_enabled=False)
    return TestClient(create_app(other))


def _post_backup(c, payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return c.post("/api/backup/import", content=body, headers={"Content-Type": "application/json"})


def test_backup_restores_status_history_idempotently(seeded, settings, tmp_path):
    seeded.patch(f"/api/jobs/{ID1}", json={"status": "Revisar"})
    seeded.patch(f"/api/jobs/{ID1}", json={"status": "Postulada"})
    original = seeded.get(f"/api/jobs/{ID1}/history").json()
    exported = seeded.get("/api/backup/export").content

    with _other_client(settings, tmp_path) as c2:
        first = _post_backup(c2, exported).json()
        assert first["history_imported"] == 2 and first["history_skipped"] == 0
        restored = c2.get(f"/api/jobs/{ID1}/history").json()
        strip = lambda rows: [{k: r[k] for k in ("job_id", "old_status", "new_status", "changed_at", "origin")} for r in rows]
        assert strip(restored) == strip(original)
        again = _post_backup(c2, exported).json()
        assert again["history_imported"] == 0 and again["history_skipped"] == 0
        assert len(c2.get(f"/api/jobs/{ID1}/history").json()) == 2


def test_backup_without_history_still_imports(seeded, settings, tmp_path):
    """Respaldos del MVP Streamlit o de versiones anteriores: sin `status_history`."""
    payload = seeded.get("/api/backup/export").json()
    del payload["status_history"]
    with _other_client(settings, tmp_path) as c2:
        r = _post_backup(c2, payload)
        assert r.status_code == 200, r.text
        assert r.json()["imported"] == 2 and r.json()["history_imported"] == 0
        payload["status_history"] = None
        assert _post_backup(c2, payload).status_code == 200


def test_backup_history_skips_invalid_and_orphan_entries(seeded, settings, tmp_path):
    payload = seeded.get("/api/backup/export").json()
    good = {"job_id": ID1, "old_status": "Nueva", "new_status": "Revisar",
            "changed_at": "2026-10-01T12:00:00+00:00", "origin": "api"}
    payload["status_history"] = [
        good,
        {**good, "changed_at": "2026-10-02T12:00:00+00:00", "origin": "<script>"},  # origen saneado
        {**good, "new_status": "Contratado"},       # estado desconocido
        {**good, "changed_at": "ayer"},             # fecha inválida
        {**good, "job_id": "../../etc"},            # identificador inválido
        {**good, "job_id": "f" * 24},               # oferta inexistente
        "texto",
    ]
    with _other_client(settings, tmp_path) as c2:
        r = _post_backup(c2, payload).json()
        assert r["history_imported"] == 2 and r["history_skipped"] == 5
        origins = {h["origin"] for h in c2.get(f"/api/jobs/{ID1}/history").json()}
        assert origins == {"api", "import"}


def test_backup_with_malformed_history_is_rejected_without_changes(seeded, settings, tmp_path):
    payload = seeded.get("/api/backup/export").json()
    payload["status_history"] = {"no": "es una lista"}
    with _other_client(settings, tmp_path) as c2:
        assert _post_backup(c2, payload).status_code == 422
        assert c2.get("/api/jobs").json()["total"] == 0
        assert not (tmp_path / "otro" / "backups").exists()


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


def test_search_cooldown_returns_429_with_real_retry_after(client, settings):
    from backend.services import search
    from jobhunter.storage import set_setting
    db = connection(settings.db_path)
    set_setting(db, search.LAST_SCAN, search.utcnow().isoformat())
    db.close()
    r = client.post("/api/search")
    assert r.status_code == 429
    assert r.json()["detail"]["next_allowed_at"]
    assert 25 * 60 < int(r.headers["Retry-After"]) <= 30 * 60  # espera mínima por defecto: 30 min
