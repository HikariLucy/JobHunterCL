import hashlib
import json
import os

import pytest

from backend.services.cv_store import CvStore
from jobhunter.storage import connection, upsert_jobs
from tests.backend.test_cv_manager import upload
from tests.backend.test_tailoring_engine import TEX, ES


def setup_plan(client, settings, content=None, lang='es'):
    db = connection(settings.db_path)
    upsert_jobs(db,[{**ES,'source':'Synthetic','url':'https://example.invalid/synthetic','location':'Chile'}]); db.close()
    job = client.get('/api/jobs').json()['items'][0]
    cv = upload(client, content or TEX,lang=lang).json()
    r = client.post('/api/tailoring/plans',json={'job_id':job['id'],'cv_id':cv['id'],'expected_cv_sha256':cv['sha256'],'lang':'en'})
    assert r.status_code==201,r.text
    return job,cv,r.json()


def decide(client,p,s,status='accepted',**extra):
    return client.patch(f"/api/tailoring/plans/{p['id']}/suggestions/{s['id']}",json={'expected_revision':p['revision'],'status':status,**extra})


def view(client,p):
    return client.get(f"/api/tailoring/plans/{p['id']}/preview",params={'expected_revision':p['revision']})


def generate(client,p,sha):
    return client.post(f"/api/tailoring/plans/{p['id']}/generate",json={'expected_revision':p['revision'],'preview_sha256':sha})


def test_full_flow_snapshot_bom_crlf_and_download(client,settings):
    content=b'\xef\xbb\xbf'+TEX.replace('\n','\r\n').encode()
    job,cv,p=setup_plan(client,settings,content)
    assert p['lang']=='en' and p['cv_sha256']==cv['sha256']
    assert p['state']=='review' and all(s['status']=='pending' for s in p['suggestions'])
    assert client.get(f"/api/tailoring/jobs/{job['id']}/analysis").status_code==200
    preview=view(client,p)
    assert preview.status_code==200 and preview.headers['cache-control']=='no-store'
    assert preview.json()['sha256']==cv['sha256']
    s=next(s for s in p['suggestions'] if s['action']=='emphasize')
    p=decide(client,p,s).json()
    assert p['revision']==2
    rejected=next(s for s in p['suggestions'] if s['action']=='remove')
    p=decide(client,p,rejected,'rejected').json()
    preview=view(client,p).json()
    assert '\\textbf{' in preview['result'] and preview['diff']
    r=generate(client,p,preview['sha256']); assert r.status_code==200,r.text
    done=r.json(); assert done['state']=='generated' and done['artifact_sha256']==preview['sha256']
    download=client.get(f"/api/tailoring/plans/{p['id']}/download")
    assert download.status_code==200 and download.content.startswith(b'\xef\xbb\xbf')
    assert hashlib.sha256(download.content).hexdigest()==done['artifact_sha256']
    assert b'\r\n' in download.content and download.headers['cache-control']=='no-store'
    assert '.tex' in download.headers['content-disposition']
    assert CvStore(settings).preview(cv['id']).source.sha256==hashlib.sha256(content).hexdigest()
    assert 'demo@example.invalid' not in client.get('/api/backup/export').text
    for path in (settings.data_dir/'cv'/'tailoring').iterdir():
        assert path.stat().st_mode & 0o077 == 0


def test_concurrent_decisions_tampered_payload_and_preview(client,settings):
    _,_,p=setup_plan(client,settings); s=p['suggestions'][-1]
    assert decide(client,p,s,after='inventado').status_code==422
    assert decide(client,p,s,tex_span=[0,5]).status_code==422
    assert decide(client,p,s,cv_sha256='0'*64).status_code==422
    newer=decide(client,p,s).json()
    assert decide(client,p,s,'rejected').status_code==409
    assert view(client,p).status_code==409
    assert generate(client,newer,'0'*64).status_code==409
    assert client.get(f"/api/tailoring/plans/{p['id']}/download").status_code==409


def test_replaced_and_deleted_master_preserves_snapshot(client,settings):
    _,cv,p=setup_plan(client,settings)
    url=f"/api/cv/{cv['id']}"; args={'confirm':True,'expected_sha256':cv['sha256']}
    new=client.put(url,params=args,headers={'X-CV-Filename':'new.tex'},content=(TEX+'% nueva').encode()).json()
    assert client.get(f"/api/tailoring/plans/{p['id']}").json()['cv_changed']
    assert client.delete(url,params={**args,'expected_sha256':new['sha256']}).status_code==200
    pv=view(client,p).json(); assert pv['original']==TEX
    assert generate(client,p,pv['sha256']).status_code==200


def test_changed_offer_blocks_mutation_and_generation(client,settings):
    job,_,p=setup_plan(client,settings)
    db=connection(settings.db_path); db.execute('UPDATE jobs SET description=? WHERE id=?',('Nueva oferta sintética',job['id'])); db.commit(); db.close()
    assert client.get(f"/api/tailoring/plans/{p['id']}").json()['job_changed']
    assert decide(client,p,p['suggestions'][-1]).status_code==409
    pv=view(client,p).json(); assert pv['blockers']
    assert generate(client,p,pv['sha256']).status_code==409


@pytest.mark.parametrize('target',['snapshot','plan','artifact'])
def test_corruption_fails_closed(client,settings,target):
    _,_,p=setup_plan(client,settings); root=settings.data_dir/'cv'/'tailoring'
    if target=='snapshot':
        (root/(p['id']+'.source')).write_bytes(b'changed')
    elif target=='plan':
        file=root/(p['id']+'.json'); obj=json.loads(file.read_text()); obj['plan']['suggestions'][-1]['after']='Invented Kubernetes'; file.write_text(json.dumps(obj))
    else:
        pv=view(client,p).json(); done=generate(client,p,pv['sha256']).json()
        (root/(done['artifact']+'.tex')).write_bytes(b'changed')
    route='/download' if target=='artifact' else ''
    assert client.get(f"/api/tailoring/plans/{p['id']}"+route).status_code==409


def test_write_failure_and_symlinks(client,settings,monkeypatch,tmp_path):
    _,cv,p=setup_plan(client,settings)
    root=settings.data_dir/'cv'/'tailoring'
    original=CvStore._atomic
    def fail(self,fd,name,content):
        if name==p['id']+'.json': raise OSError('private path must not leak')
        return original(self,fd,name,content)
    with monkeypatch.context() as m:
        m.setattr(CvStore,'_atomic',fail)
        r=decide(client,p,p['suggestions'][-1]); assert r.status_code==500
        assert 'private path' not in r.text and r.headers['cache-control']=='no-store'
    assert client.get(f"/api/tailoring/plans/{p['id']}").json()['revision']==p['revision']
    source=root/(p['id']+'.source'); source.unlink(); outside=tmp_path/'outside'; outside.write_text('private')
    source.symlink_to(outside)
    assert client.get(f"/api/tailoring/plans/{p['id']}").status_code==500
    assert outside.read_text()=='private'
    assert client.get('/api/tailoring/plans/not-a-uuid').status_code==422
    assert client.post('/api/tailoring/plans',json={'job_id':'x','cv_id':cv['id'],'expected_cv_sha256':cv['sha256'],'lang':'es','path':'/tmp/escape'}).status_code==422


def test_conflicting_approvals_block_generation(client,settings):
    _,_,p=setup_plan(client,settings)
    ids=[s['id'] for s in p['suggestions'] if s['action'] in {'reorder','emphasize'}]
    for sid in ids:
        p=decide(client,p,{'id':sid}).json()
    pv=view(client,p).json(); assert pv['blockers']
    assert generate(client,p,pv['sha256']).status_code==409
    reorder=next(s for s in p['suggestions'] if s['action']=='reorder')
    p=decide(client,p,reorder,'rejected').json()
    pv=view(client,p).json(); assert not pv['blockers']
    assert generate(client,p,pv['sha256']).status_code==200


def test_actual_concurrent_decisions_serialize(client,settings):
    from concurrent.futures import ThreadPoolExecutor
    _,_,p=setup_plan(client,settings); s=p['suggestions'][-1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(decide,client,p,s,'accepted'); b=pool.submit(decide,client,p,s,'rejected')
        assert sorted([a.result().status_code,b.result().status_code])==[200,409]


def test_generation_write_failure_never_publishes_or_overwrites(client,settings,monkeypatch):
    _,_,p=setup_plan(client,settings)
    pv=view(client,p).json(); done=generate(client,p,pv['sha256']).json()
    root=settings.data_dir/'cv'/'tailoring'; before={p.name:p.read_bytes() for p in root.iterdir()}
    original=CvStore._atomic
    def fail(self,fd,name,content):
        if name==p['id']+'.json': raise OSError('synthetic commit failure')
        return original(self,fd,name,content)
    with monkeypatch.context() as m:
        m.setattr(CvStore,'_atomic',fail)
        assert generate(client,done,pv['sha256']).status_code==500
    assert {p.name:p.read_bytes() for p in root.iterdir()}==before
    assert client.get(f"/api/tailoring/plans/{p['id']}/download").status_code==200


def test_snapshot_fsync_failure_and_directory_escape(client,settings,monkeypatch,tmp_path):
    _,cv,p=setup_plan(client,settings); root=settings.data_dir/'cv'/'tailoring'
    before=set(os.listdir(root))
    with monkeypatch.context() as m:
        m.setattr(os,'fsync',lambda _: (_ for _ in ()).throw(OSError('synthetic fsync')))
        assert client.post('/api/tailoring/plans',json={'job_id':p['job_id'],'cv_id':cv['id'],'expected_cv_sha256':cv['sha256'],'lang':'es'}).status_code==500
    assert set(os.listdir(root))==before
    root.rename(root.with_name('saved-tailoring')); outside=tmp_path/'outside-dir'; outside.mkdir(); root.symlink_to(outside,target_is_directory=True)
    assert client.get(f"/api/tailoring/plans/{p['id']}").status_code==500
    assert list(outside.iterdir())==[]


def test_old_cv_hash_hardlink_and_unsupported_platform(client,settings,monkeypatch,tmp_path):
    _,cv,p=setup_plan(client,settings)
    assert client.post('/api/tailoring/plans',json={'job_id':p['job_id'],'cv_id':cv['id'],'expected_cv_sha256':'0'*64,'lang':'es'}).status_code==409
    root=settings.data_dir/'cv'/'tailoring'; source=root/(p['id']+'.source')
    os.link(source,tmp_path/'second-link')
    assert client.get(f"/api/tailoring/plans/{p['id']}").status_code==500
    with monkeypatch.context() as m:
        m.setattr(os,'supports_dir_fd',set())
        assert client.get(f"/api/tailoring/plans/{p['id']}").status_code==500
        assert client.get('/api/health').status_code==200


def test_english_job_and_english_document(client,settings):
    from tests.backend.test_tailoring_engine import EN
    tex=TEX.replace('Proyectos','Projects').replace('Educación','Education').replace('Proyecto académico de dibujo con SVG.','Academic drawing project using SVG.').replace('Desarrollé servicios con Python y FastAPI.','Built services with Python and FastAPI.').replace('Gestioné datos con PostgreSQL.','Managed data using PostgreSQL.').replace('Ingeniería en curso desde 2022.','Engineering degree in progress since 2022.')
    db=connection(settings.db_path);upsert_jobs(db,[{**EN,'source':'Synthetic EN','url':'https://example.invalid/en','location':'Chile'}]);db.close()
    job=client.get('/api/jobs').json()['items'][0];cv=upload(client,tex,lang='en').json()
    r=client.post('/api/tailoring/plans',json={'job_id':job['id'],'cv_id':cv['id'],'expected_cv_sha256':cv['sha256'],'lang':'en'})
    assert r.status_code==201
    p=r.json();assert p['analysis']['lang']=='en'
    s=next(s for s in p['suggestions'] if s['action']=='emphasize')
    p=decide(client,p,s).json();pv=view(client,p).json();assert not pv['blockers']
    assert generate(client,p,pv['sha256']).status_code==200
    result=client.get(f"/api/tailoring/plans/{p['id']}/download").text
    assert 'Engineering degree in progress since 2022.' in result
    assert 'Academic drawing project using SVG.' in result
