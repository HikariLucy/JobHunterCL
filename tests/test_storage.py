import json
from jobhunter.storage import connection, job_id, canonical, upsert_jobs, list_jobs, set_status, export_backup, import_backup, get_backup_profile

J = {"source": "Prueba", "title": "Desarrollador Junior", "company": "Ejemplo",
     "location": "Santiago", "url": "https://example.org/jobs/123?utm_source=abc", "description": "Python"}


def test_tracking_not_lost_on_refresh(tmp_path):
    db = connection(tmp_path / "jobs.sqlite3")
    assert upsert_jobs(db, [J, J]) == 1
    uid = list_jobs(db)[0]["id"]
    set_status(db, uid, "Postulada")
    updated = dict(J, title="Desarrollador Python Junior", url="https://example.org/jobs/123?utm_source=other")
    assert upsert_jobs(db, [updated]) == 0
    row = list_jobs(db)[0]
    assert row["status"] == "Postulada"
    assert row["title"] == updated["title"]
    assert len(list_jobs(db)) == 1


def test_backup_roundtrip(tmp_path):
    a = connection(tmp_path / "a.db")
    b = connection(tmp_path / "b.db")
    upsert_jobs(a, [J])
    set_status(a, job_id(J["url"]), "Preparada")
    assert import_backup(b, export_backup(a)) == 1
    assert list_jobs(b)[0]["status"] == "Preparada"


def test_bad_backup_rejected(tmp_path):
    b = connection(tmp_path / "b.db")
    try:
        import_backup(b, b'{"jobs":[]}')
        assert False, "Expected error"
    except ValueError:
        pass


def test_backup_includes_profile(tmp_path):
    db = connection(tmp_path / "x.sqlite3")
    profile = {"titles": ["soporte TI"], "skills": ["Linux"], "locations": ["Chile"], "sources": {"getonbrd": True}}
    backup = export_backup(db, profile)
    assert get_backup_profile(backup)["titles"] == ["soporte TI"]
