"""Solo documentos sintéticos; nunca leer CV del usuario."""
import hashlib
from urllib.parse import quote
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

TEX = r'''\documentclass{article}
\begin{document}
Ada Ejemplo — prueba@example.invalid
\section{Resumen}
Desarrollo de software sintético.
\section{Experiencia}
\begin{itemize}\item Proyecto ficticio con Python.\end{itemize}
\section{Educación}
Formación de ejemplo en curso.
\section{Habilidades}
Python, SQL
\section{Proyectos}
Aplicación de prueba.
\section{Idiomas}
Español
\end{document}
'''


def upload(client, tex=TEX, filename='cv.tex', lang='es', name='CV de prueba'):
    return client.post('/api/cv/import',
                       content=tex.encode('utf-8') if isinstance(tex, str) else tex,
                       headers={'Content-Type': 'application/x-tex', 'X-CV-Filename': quote(filename), 'X-CV-Name': quote(name), 'X-CV-Lang':lang})


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_import_preview_and_private_storage(client, settings, lang):
    data = b'\xef\xbb\xbf' + TEX.encode()
    r = upload(client, data, lang=lang)
    assert r.status_code == 201, r.text
    cv = r.json()
    assert cv['sha256'] == hashlib.sha256(data).hexdigest()
    assert cv['lang'] == lang and cv['imported_at'] and not cv['is_primary']
    assert 'path' not in cv and 'source_text' not in cv
    assert client.get('/api/cv').json() == [cv]
    assert client.get('/api/cv/' + cv['id']).json() == cv
    p = client.get(f"/api/cv/{cv['id']}/preview").json()
    assert p['source_text'] == TEX
    assert {'header', 'summary', 'experience', 'education', 'skills', 'projects', 'languages'} <= {s['kind'] for s in p['sections']}
    for s in p['sections']:
        a, b = s['tex_span']
        assert TEX[a:b] == s['raw_tex']
    files = list((settings.data_dir / 'cv').glob('*.tex'))
    assert len(files) == 1 and files[0].read_bytes() == data
    assert files[0].stat().st_mode & 0o077 == 0
    assert (settings.data_dir / 'cv').stat().st_mode & 0o077 == 0
    backup = client.get('/api/backup/export')
    assert 'prueba@example.invalid' not in backup.text and cv['sha256'] not in backup.text
    assert client.get('/cv/' + files[0].name).status_code == 404


@pytest.mark.parametrize('tex,filename', [('plain text', 'a.tex'), (TEX, 'a.pdf'), (b'\xff', 'a.tex'),
    (TEX+'\x00', 'a.tex'), (TEX, '../cv.tex'), (TEX, r'C:\cv.tex'), (TEX, '/cv.tex'), ('', 'a.tex')])
def test_invalid_files(client, tex, filename):
    assert upload(client, tex, filename).status_code == 422
    assert client.get('/api/cv').json() == []


def test_size_bound(settings):
    with TestClient(create_app(replace(settings, cv_max_bytes=50))) as c:
        assert upload(c).status_code == 413
        assert c.get('/api/cv').json() == []


def test_unknown_and_dangerous_tex_never_executed(client, tmp_path):
    marker = tmp_path / 'MUST_NOT_EXIST'
    tex = TEX.replace(r'\section{Resumen}', r'\mystery{Invisible}'+'\n'+r'\section{Otra sección}')
    tex += '\n'+r'\immediate\write18{touch '+str(marker)+r'}\input{/etc/passwd}\begin{custom}dato\end{custom}'
    r = upload(client, tex)
    assert r.status_code == 201
    p = client.get(f"/api/cv/{r.json()['id']}/preview").json()
    assert p['partial'] and p['uninterpreted'] and p['warnings']
    assert any(s['kind'] == 'other' for s in p['sections'])
    assert not marker.exists()
    assert 'root:x:' not in str(p)
    assert r'\mystery' in p['source_text']


def test_duplicate_primary_replace_delete(client, settings):
    a, b, en = upload(client).json(), upload(client).json(), upload(client, lang='en').json()
    assert a['id'] != b['id']
    for cv in [a, b, en]:
        assert client.put(f"/api/cv/{cv['id']}/primary").status_code == 200
    rows = client.get('/api/cv').json()
    assert {r['id'] for r in rows if r['is_primary']} == {b['id'], en['id']}
    url = f"/api/cv/{b['id']}"
    args = dict(expected_sha256=b['sha256'])
    assert client.put(url, params=args, headers={'X-CV-Filename':'new.tex'}, content=TEX.encode()).status_code == 422
    args['confirm'] = 'true'
    r = client.put(url, params=args, headers={'X-CV-Filename':'new.tex'}, content=(TEX+'% nueva versión').encode())
    assert r.status_code == 200, r.text
    assert r.json()['id'] == b['id'] and r.json()['is_primary']
    assert r.json()['sha256'] != b['sha256']
    assert client.delete(url, params={'confirm': True, 'expected_sha256': b['sha256']}).status_code == 409
    assert client.delete(url).status_code == 422
    assert client.delete(url, params={'confirm': True, 'expected_sha256': r.json()['sha256']}).status_code == 200
    assert client.get(url).status_code == 404
    assert len(list((settings.data_dir / 'cv').glob('*.tex'))) == 2


def test_write_failure_does_not_destroy_previous(client, settings, monkeypatch):
    from backend.services import cv_store
    old = upload(client).json()
    original = cv_store.os.replace
    def fail(src, dst, *args, **kwargs):
        if str(dst) == 'index.json':
            raise OSError('synthetic write failure')
        return original(src, dst, *args, **kwargs)
    with monkeypatch.context() as m:
        m.setattr(cv_store.os, 'replace', fail)
        assert upload(client).status_code == 500
        assert client.put(f"/api/cv/{old['id']}", headers={'X-CV-Filename':'cv.tex'}, params=dict(confirm=True,
            expected_sha256=old['sha256']), content=(TEX+'%changed').encode()).status_code == 500
        assert client.delete(f"/api/cv/{old['id']}", params=dict(confirm=True,
            expected_sha256=old['sha256'])).status_code == 500
    assert client.get('/api/cv').json() == [old]
    assert client.get(f"/api/cv/{old['id']}/preview").json()['source_text'] == TEX
    assert len(list((settings.data_dir / 'cv').glob('*.tex'))) == 1
    assert upload(client).status_code == 201


def test_symlinks_and_tampering_rejected(client, settings, tmp_path):
    cv = upload(client).json()
    blob = next((settings.data_dir / 'cv').glob('*.tex'))
    outside = tmp_path / 'outside'
    outside.write_text(TEX)
    blob.unlink()
    blob.symlink_to(outside)
    assert client.get(f"/api/cv/{cv['id']}/preview").status_code == 500
    assert outside.read_text() == TEX


def test_symlink_directory_rejected(client, settings, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (settings.data_dir / 'cv').symlink_to(outside, target_is_directory=True)
    assert upload(client).status_code == 500
    assert list(outside.iterdir()) == []


def test_corrupt_index_is_not_overwritten(client, settings):
    upload(client)
    index = settings.data_dir / 'cv' / 'index.json'
    index.write_text('broken')
    assert upload(client).status_code == 500
    assert index.read_text() == 'broken'


def test_recovery_from_interrupted_delete_and_orphan_write(client, settings):
    cv = upload(client).json()
    directory = settings.data_dir / 'cv'
    blob = next(directory.glob('*.tex'))
    tombstone = blob.with_name(blob.name+'.deleted')
    blob.rename(tombstone)  # Interrupción antes de comprometer el índice.
    orphan = directory / ('f'*32 + '.tex')
    orphan.write_text('orphan synthetic')
    assert client.get(f"/api/cv/{cv['id']}/preview").json()['source_text'] == TEX
    assert blob.exists() and not tombstone.exists() and not orphan.exists()


def test_unknown_multiline_is_not_evidence(client):
    tex = TEX + r'''
\newcommand{\claim}{
I am an invented expert
}
\begin{custom}
This is not recognized evidence
\end{custom}
'''
    cv = upload(client, tex).json()
    preview = client.get(f"/api/cv/{cv['id']}/preview").json()
    recognized = '\n'.join(s['text'] for s in preview['sections'])
    assert 'invented expert' not in recognized
    assert 'not recognized evidence' not in recognized
    assert preview['partial']


def test_english_sections_and_no_profile_dependency(client):
    tex = TEX.replace('Resumen','Summary').replace('Experiencia','Work Experience').replace('Educación','Education').replace('Habilidades','Skills').replace('Proyectos','Projects').replace('Idiomas','Languages')
    cv = upload(client, tex, lang='en').json()
    preview = client.get(f"/api/cv/{cv['id']}/preview").json()
    assert not preview['partial']
    assert not client.get('/api/profile/status').json()['exists']


def test_untrusted_index_path_and_hash_tampering(client, settings):
    import json
    cv = upload(client).json()
    directory = settings.data_dir / 'cv'
    blob = next(directory.glob('*.tex'))
    blob.write_text(TEX+'modified')
    assert client.get(f"/api/cv/{cv['id']}/preview").status_code == 409
    path = directory / 'index.json'
    index = json.loads(path.read_text())
    index['records'][0]['blob'] = '../../outside.tex'
    path.write_text(json.dumps(index))
    assert client.get('/api/cv').status_code == 500


def test_write_fsync_failure_rolls_back(client, settings, monkeypatch):
    from backend.services import cv_store
    cv = upload(client).json()
    def fail(_):
        raise OSError('synthetic disk failure')
    with monkeypatch.context() as m:
        m.setattr(cv_store.os, 'fsync', fail)
        assert upload(client).status_code == 500
    assert client.get('/api/cv').json() == [cv]
    assert len(list((settings.data_dir / 'cv').glob('*.tex'))) == 1


def test_private_dir_must_not_be_public(settings):
    from backend.services.cv_store import CvError, CvStore
    from backend.settings import ROOT
    with pytest.raises(CvError):
        CvStore(replace(settings, data_dir=ROOT / 'frontend' / 'public'))


@pytest.mark.parametrize('opaque', [r'\iffalse'+'\nInvented Expert\n'+r'\fi', r'\unknown'+'\n\n{Invented Expert}'])
def test_opaque_structures_are_not_recognized(client, opaque):
    cv = upload(client, TEX+'\n'+opaque).json()
    preview = client.get(f"/api/cv/{cv['id']}/preview").json()
    assert 'Invented Expert' not in '\n'.join(s['text'] for s in preview['sections'])
    assert preview['partial'] and 'Invented Expert' in str(preview['uninterpreted'])


def test_tex_comment_after_linebreak_is_not_evidence(client):
    tex = TEX + '\n'+r'Visible work \\% Invented Expert'+'\n'+r'Visible \% percent'
    cv = upload(client, tex).json()
    preview = client.get(f"/api/cv/{cv['id']}/preview").json()
    recognized = '\n'.join(s['text'] for s in preview['sections'])
    assert 'Invented Expert' not in recognized
    assert 'Visible % percent' in recognized


@pytest.mark.parametrize('operation', ['replace', 'delete'])
def test_destructive_operation_checks_actual_bytes(client, settings, operation):
    cv = upload(client).json()
    blob = next((settings.data_dir / 'cv').glob('*.tex'))
    modified = TEX+'modified outside'
    blob.write_text(modified)
    params = dict(confirm=True, expected_sha256=cv['sha256'])
    url = f"/api/cv/{cv['id']}"
    response = (client.delete(url, params=params) if operation == 'delete' else
                client.put(url, params=params, content=TEX.encode(), headers={'X-CV-Filename':'new.tex'}))
    assert response.status_code == 409
    assert blob.read_text() == modified
