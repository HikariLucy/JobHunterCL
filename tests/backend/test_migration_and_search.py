import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
import requests

from backend import db as dbmod
from backend.services import scheduler, search
from jobhunter.storage import connection, get_setting, list_jobs, set_status, upsert_jobs

from .conftest import JOBS

T0 = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
PROFILE = {"titles": ["desarrollador junior"], "skills": ["python"], "locations": ["chile"],
           "sources": {"getonbrd": True, "remotive": False}}


def legacy_db(path):
    """Base creada exactamente como lo hace el MVP Streamlit."""
    db = connection(path)
    upsert_jobs(db, JOBS)
    set_status(db, list_jobs(db)[0]["id"], "Postulada")
    db.close()


def test_migration_is_additive_and_backs_up_first(tmp_path):
    path, backups = tmp_path / "jobs.sqlite3", tmp_path / "backups"
    legacy_db(path)
    result = dbmod.migrate(path, backups)
    assert (result["from"], result["to"]) == (0, 1)
    copy = sqlite3.connect(result["backup"])
    assert copy.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 2
    assert copy.execute("PRAGMA user_version").fetchone()[0] == 0
    copy.close()
    db = connection(path)  # el MVP sigue funcionando sobre la base migrada
    assert sorted(j["status"] for j in list_jobs(db)) == ["Nueva", "Postulada"]
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"jobs", "settings", "status_history", "scan_runs"} <= tables
    db.close()
    assert dbmod.migrate(path, backups)["backup"] is None  # idempotente, sin copias extra
    assert len(list(backups.iterdir())) == 1


def test_fresh_database_needs_no_backup(tmp_path):
    result = dbmod.migrate(tmp_path / "new.sqlite3", tmp_path / "backups")
    assert result["backup"] is None and not (tmp_path / "backups").exists()


def test_refuses_newer_schema(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    db = sqlite3.connect(path)
    db.execute("PRAGMA user_version=99")
    db.close()
    with pytest.raises(RuntimeError):
        dbmod.migrate(path, tmp_path / "b")


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    dbmod.migrate(path, tmp_path / "backups")
    conn = dbmod.connect(path)
    yield conn
    conn.close()


def http_error(code):
    resp = requests.Response()
    resp.status_code = code
    return requests.HTTPError(f"HTTP {code}", response=resp)


def test_search_retries_transient_errors_only(db):
    calls = {"flaky": 0, "limited": 0}

    def flaky():
        calls["flaky"] += 1
        if calls["flaky"] < 3:
            raise requests.ConnectionError("sin red")
        return [JOBS[0]]

    def limited():
        calls["limited"] += 1
        raise http_error(429)

    sleeps = []
    run = search.run_search(db, PROFILE, clock=lambda: T0, sleep=sleeps.append,
                            source_factory=lambda s: [("Flaky", flaky), ("Limitada", limited)])
    assert calls == {"flaky": 3, "limited": 1}
    assert sleeps == list(search.RETRY_DELAYS)
    assert run["status"] == "partial" and run["added"] == 1 and run["fetched"] == 1
    assert run["errors"][0].startswith("Limitada:")
    assert get_setting(db, search.LAST_SCAN) == T0.isoformat()


def test_search_cooldown_and_dedup(db):
    one = lambda s: [("Fuente", lambda: [JOBS[0], JOBS[0]])]  # noqa: E731
    assert search.run_search(db, PROFILE, clock=lambda: T0, source_factory=one)["added"] == 1
    with pytest.raises(search.CooldownActive) as exc:
        search.run_search(db, PROFILE, clock=lambda: T0 + timedelta(minutes=10), source_factory=one)
    assert exc.value.next_allowed == T0 + timedelta(minutes=30)
    run = search.run_search(db, PROFILE, clock=lambda: T0 + timedelta(minutes=31), source_factory=one)
    assert run["added"] == 0 and run["fetched"] == 2


def test_failed_search_does_not_start_cooldown(db):
    def down():
        raise requests.Timeout("timeout")
    run = search.run_search(db, PROFILE, clock=lambda: T0, sleep=lambda s: None,
                            source_factory=lambda s: [("Caída", down)])
    assert run["status"] == "error"
    assert search.next_allowed(db, PROFILE["sources"]) is None


def test_concurrent_search_is_rejected(db):
    search._lock.acquire()
    with pytest.raises(search.SearchBusy):
        search.run_search(db, PROFILE, source_factory=lambda s: [])


def test_interrupted_runs_are_closed(db):
    db.execute("INSERT INTO scan_runs(started_at, trigger, status) VALUES (?,?,?)", (T0.isoformat(), "manual", "running"))
    db.commit()
    assert search.mark_interrupted(db) == 1
    assert search.recent_runs(db)[0]["status"] == "interrupted"


def test_schedule_respects_source_limits(db):
    assert search.next_scheduled(db, PROFILE["sources"], T0) is None  # desactivado por defecto
    search.set_scan_interval(db, 10)  # menor que el mínimo de 30 min
    assert search.next_scheduled(db, PROFILE["sources"], T0) == T0  # nunca ejecutado: ahora
    search.run_search(db, PROFILE, clock=lambda: T0, source_factory=lambda s: [("F", lambda: [JOBS[0]])])
    assert search.next_scheduled(db, PROFILE["sources"], T0) == T0 + timedelta(minutes=30)
    remotive = {**PROFILE["sources"], "remotive": True}
    assert search.next_scheduled(db, remotive, T0) == T0 + timedelta(hours=6, minutes=30)


def test_scheduler_tick_runs_only_when_due(settings):
    settings.data_dir.mkdir(parents=True)
    dbmod.migrate(settings.db_path, settings.backups_dir)
    factory = lambda s: [("F", lambda: [JOBS[0]])]  # noqa: E731
    assert scheduler.tick(settings, T0, source_factory=factory) is None  # desactivado
    conn = dbmod.connect(settings.db_path)
    search.set_scan_interval(conn, 60)
    conn.close()
    now = datetime.now(timezone.utc)
    run = scheduler.tick(settings, now, source_factory=factory)
    assert run["trigger"] == "scheduled" and run["added"] == 1
    assert scheduler.tick(settings, now + timedelta(minutes=5), source_factory=factory) is None
