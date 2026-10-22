"""M2.3: solo documentos sintéticos; nunca ejecutar TeX en estas pruebas."""
import hashlib
import json

import pytest

from tests.backend.test_tailoring_api import setup_plan, view, generate, decide


def generated(client, settings, lang='es'):
    from tests.backend.test_tailoring_engine import TEX
    tex = TEX if lang == 'es' else TEX.replace('Proyectos', 'Projects').replace('Educación', 'Education')
    _, _, p = setup_plan(client, settings, tex, lang)
    p = decide(client, p, next(s for s in p['suggestions'] if s['action'] == 'emphasize')).json()
    return generate(client, p, view(client, p).json()['sha256']).json()


def request_pdf(client, p, **extra):
    return client.post(f"/api/tailoring/plans/{p['id']}/pdf", json={
        'expected_revision': p['revision'], 'expected_tex_sha256': p['artifact_sha256'], **extra})


def test_capabilities_never_claim_tools_are_a_sandbox(client):
    r = client.get('/api/tailoring/pdf/capabilities')
    assert r.status_code == 200
    assert r.json()['available'] is False
    assert r.json()['code'] == 'sandbox_unverified'
    assert r.json()['reasons']
    assert r.headers['cache-control'] == 'no-store'
    assert r.headers['x-content-type-options'] == 'nosniff'
    assert '/usr/' not in r.text


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_verified_documents_blocked_and_traceable(client, settings, lang):
    p = generated(client, settings, lang)
    root = settings.data_dir / 'cv' / 'tailoring'
    original = (root / (p['artifact'] + '.tex')).read_bytes()
    r = request_pdf(client, p)
    assert r.status_code == 503, r.text
    state = client.get(f"/api/tailoring/plans/{p['id']}/pdf", params={'expected_revision':p['revision']})
    assert state.status_code == 200
    meta = state.json()
    assert meta['status'] == 'blocked' and meta['code'] == 'sandbox_unverified'
    assert meta['plan_id'] == p['id'] and meta['revision'] == p['revision']
    assert meta['tex_sha256'] == hashlib.sha256(original).hexdigest()
    assert meta['pdf_sha256'] is None and meta['pages'] is None
    assert meta['compiler'] is None and meta['created_at'] and meta['attempt_id']
    assert (root / (p['artifact'] + '.tex')).read_bytes() == original
    assert not list(root.glob('*.pdf'))
    assert meta['attempt_id'] not in client.get('/api/backup/export').text
    assert all(f.stat().st_mode & 0o077 == 0 for f in root.iterdir())
    download = client.get(f"/api/tailoring/plans/{p['id']}/pdf/download", params={'expected_revision':p['revision']})
    assert download.status_code == 409
    assert download.headers['cache-control'] == 'no-store'


def test_no_arbitrary_tex_or_paths_and_strict_revision(client, settings):
    p = generated(client, settings)
    for extra in ({'tex':'private'}, {'path':'/etc/passwd'}, {'expected_revision':True}, {'expected_revision':'2'}):
        assert request_pdf(client, p, **extra).status_code == 422
    assert request_pdf(client, p, expected_tex_sha256='0'*64).status_code == 409
    assert request_pdf(client, p, expected_revision=p['revision']-1).status_code == 409
    absent = {**p, 'id':'0'*32}
    assert request_pdf(client, absent).status_code == 404


@pytest.mark.parametrize('target', ['source', 'artifact', 'decisions'])
def test_tampering_rejected_before_environment(client, settings, target):
    p = generated(client, settings)
    root = settings.data_dir / 'cv' / 'tailoring'
    if target == 'decisions':
        path = root / (p['id'] + '.json'); obj = json.loads(path.read_text())
        next(s for s in obj['plan']['suggestions'] if s['status']=='accepted')['status']='rejected'
        path.write_text(json.dumps(obj))
    else:
        name = p['id'] + '.source' if target == 'source' else p['artifact'] + '.tex'
        (root / name).write_bytes(b'changed')
    assert request_pdf(client, p).status_code == 409
    assert not list(root.glob('*.pdf-audit'))


def test_no_generated_artifact_and_changed_decisions(client, settings):
    _, _, p = setup_plan(client, settings)
    assert request_pdf(client, {**p,'artifact_sha256':'0'*64}).status_code == 409
    p = generated(client, settings); assert request_pdf(client, p).status_code == 503
    newer = decide(client, p, p['suggestions'][-1], 'rejected').json()
    assert request_pdf(client, p).status_code == 409
    assert client.get(f"/api/tailoring/plans/{p['id']}/pdf", params={'expected_revision':newer['revision']}).json()['status'] == 'not_generated'


def test_attempt_history_and_plan_isolation(client, settings):
    a = generated(client, settings); b = generated(client, settings)
    assert request_pdf(client, a).status_code == 503
    state = lambda p: client.get(f"/api/tailoring/plans/{p['id']}/pdf", params={'expected_revision':p['revision']}).json()
    first = state(a)
    assert state(b)['status'] == 'not_generated'
    assert request_pdf(client, a).status_code == 503
    assert state(a)['attempt_id'] != first['attempt_id']
    assert len(list((settings.data_dir/'cv'/'tailoring').glob('*.pdf-audit'))) == 2


def test_private_write_failure_and_recovery(client, settings, monkeypatch):
    from backend.services.cv_store import CvStore
    p = generated(client, settings)
    original = CvStore._atomic
    def fail(self, fd, name, content):
        if name.endswith('.pdf-status'):
            raise OSError('/private/secret')
        return original(self, fd, name, content)
    with monkeypatch.context() as m:
        m.setattr(CvStore, '_atomic', fail)
        r = request_pdf(client, p)
        assert r.status_code == 500 and '/private/secret' not in r.text
    assert not list((settings.data_dir/'cv'/'tailoring').glob('*.pdf-audit'))
    assert request_pdf(client, p).status_code == 503


def test_validation_errors_do_not_echo_submitted_private_document(client, settings):
    p = generated(client, settings)
    r = request_pdf(client, p, tex='SECRET-SYNTHETIC-DOCUMENT', path='/private/synthetic-location')
    assert r.status_code == 422
    assert 'SECRET-SYNTHETIC-DOCUMENT' not in r.text
    assert '/private/synthetic-location' not in r.text


@pytest.mark.parametrize('kind', ['symlink', 'hardlink', 'directory'])
def test_artifact_file_type_protections(client, settings, tmp_path, kind):
    import os
    p = generated(client, settings)
    artifact = settings.data_dir/'cv'/'tailoring'/(p['artifact']+'.tex')
    saved = artifact.read_bytes()
    outside = tmp_path/'synthetic-outside'; outside.write_bytes(saved)
    artifact.unlink()
    if kind == 'symlink': artifact.symlink_to(outside)
    elif kind == 'hardlink': os.link(outside, artifact)
    else: artifact.mkdir()
    assert request_pdf(client, p).status_code == 500
    assert outside.read_bytes() == saved


def test_concurrent_blocked_requests_have_separate_history(client, settings):
    from concurrent.futures import ThreadPoolExecutor
    p = generated(client, settings)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(request_pdf, client, p) for _ in range(2)]
        assert [f.result().status_code for f in futures] == [503, 503]
    root = settings.data_dir/'cv'/'tailoring'
    assert len(list(root.glob('*.pdf-audit'))) == 2
    assert client.get(f"/api/tailoring/plans/{p['id']}/pdf",params={'expected_revision':p['revision']}).status_code == 200


def test_capabilities_do_not_execute_detected_engines(monkeypatch):
    import subprocess
    from backend.services.pdf_environment import capabilities
    monkeypatch.setattr('backend.services.pdf_environment.shutil.which', lambda name: '/fake/'+name)
    def forbidden(*args, **kwargs): raise AssertionError('No process may execute')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert capabilities().available is False
    assert 'pdflatex' in capabilities().detected_tools


@pytest.mark.parametrize('change, expected', [
    (r'\documentclass{moderncv}', 'Clase no soportada'),
    (r'\usepackage{unknown}', 'Paquete no permitido'),
    (r'\custom{synthetic}', 'Macro desconocida'),
    (r'\begin{table}x\end{table}', 'Entorno no admitido'),
    (r'\input{/synthetic/host}', 'Archivo externo'),
    (r'\write18{curl example.invalid}', 'Macro desconocida'),
    (r'\openout1=/synthetic/out', 'Macro desconocida'),
])
def test_template_diagnostics_never_expand_tex(change, expected):
    from backend.cv_contracts import CvSource
    from backend.services.cv_parser import parse
    from backend.services.pdf_diagnostics import diagnostics
    from tests.backend.test_tailoring_engine import TEX
    content = TEX.replace(r'\documentclass{article}', change) if change.startswith(r'\documentclass') else TEX.replace(r'\begin{document}', change+'\n'+r'\begin{document}')
    cv = parse(content, CvSource(id='a'*32,lang='es',path='',sha256='a'*64,imported_at=''))
    messages = diagnostics(cv)
    assert any(expected in m for m in messages)
    assert not any('/synthetic/' in m or 'curl' in m for m in messages)


@pytest.mark.parametrize('target', ['missing_audit', 'corrupt_audit', 'corrupt_status', 'other_plan'])
def test_private_pdf_trace_corruption_rejected(client, settings, target):
    p = generated(client, settings); assert request_pdf(client, p).status_code == 503
    root = settings.data_dir/'cv'/'tailoring'
    status_file = root/(p['id']+'.pdf-status')
    meta = json.loads(status_file.read_text())
    audit = root/(meta['attempt_id']+'.pdf-audit')
    if target == 'missing_audit': audit.unlink()
    elif target == 'corrupt_audit': audit.write_bytes(b'corrupt')
    elif target == 'corrupt_status': status_file.write_bytes(b'corrupt')
    else:
        meta['plan_id'] = '0'*32
        status_file.write_text(json.dumps(meta))
    r = client.get(f"/api/tailoring/plans/{p['id']}/pdf", params={'expected_revision':p['revision']})
    assert r.status_code == 409
    assert r.headers['cache-control'] == 'no-store'
