import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services import search
from backend.settings import AppSettings
from jobhunter.storage import connection, upsert_jobs

JOBS = [
    {"source": "Prueba", "title": "Desarrollador Junior Python", "company": "Acme",
     "location": "Santiago, Chile", "url": "https://example.org/jobs/1", "description": "Python SQL Linux"},
    {"source": "Prueba", "title": "Senior Staff Architect", "company": "Globex",
     "location": "USA only", "url": "https://example.org/jobs/2", "description": "10 years Java"},
]


@pytest.fixture
def settings(tmp_path):
    return AppSettings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist",
                       allowed_hosts=("testserver", "127.0.0.1"), scheduler_enabled=False)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def seeded(settings, client):
    db = connection(settings.db_path)
    upsert_jobs(db, JOBS)
    db.close()
    return client


@pytest.fixture(autouse=True)
def _free_search_lock():
    yield
    if search._lock.locked():
        search._lock.release()
