"""Servidor de revisión M2.3 con datos exclusivamente sintéticos y efímeros.

.venv/bin/python scripts/smoke_m23.py
Abrir la URL impresa. Ctrl+C limpia la carpeta temporal. No usa datos personales.
"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from backend import db as dbmod
from backend.main import create_app
from backend.settings import AppSettings
from backend.services.cv_store import CvStore, CvError
from backend.services.tailoring_store import TailoringStore
from backend.services.pdf_service import PdfService
from jobhunter.storage import connection, upsert_jobs
from tests.backend.test_tailoring_engine import TEX, ES


def main():
    with TemporaryDirectory(prefix='jobhunter-m23-synthetic-') as directory:
        settings = AppSettings(data_dir=Path(directory), scheduler_enabled=False)
        dbmod.migrate(settings.db_path, settings.backups_dir)
        db = connection(settings.db_path)
        try:
            upsert_jobs(db, [{**ES, 'source':'Synthetic', 'url':'https://example.invalid/m23', 'location':'Chile'}])
            job = db.execute('SELECT id FROM jobs').fetchone()['id']
            cv = CvStore(settings).import_cv(TEX.encode(), 'synthetic.tex', 'CV sintético ES', 'es')
            store = TailoringStore(settings, db)
            plan = store.create(job, cv.id, cv.sha256, 'es')
            suggestion = next(s for s in plan.suggestions if s.action == 'emphasize')
            plan = store.decide(plan.id, suggestion.id, 'accepted', plan.revision)
            preview = store.preview(plan.id, plan.revision)
            plan = store.generate(plan.id, plan.revision, preview.sha256)
            try:
                PdfService(store).generate(plan.id, plan.revision, plan.artifact_sha256)
            except CvError as exc:
                if exc.status != 503:
                    raise
            print(f'REVISIÓN SINTÉTICA: http://127.0.0.1:8873/ofertas/{job}/adaptar?plan={plan.id}', flush=True)
        finally:
            db.close()
        uvicorn.run(create_app(settings), host='127.0.0.1', port=8873, access_log=False)


if __name__ == '__main__':
    main()
