"""Planes privados serializados por el bloqueo M2.1; snapshots inmutables."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import uuid

from pydantic import BaseModel, ConfigDict

from ..cv_contracts import CvMetadata, CvSource, TailoringPlan
from .cv_store import CvError, CvStore, TOKEN
from .cv_parser import parse
from .job_analysis import analyze, fingerprint
from .tailoring_engine import make_plan, output_bytes, preview


class StoredPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = 1
    plan: TailoringPlan
    job: dict[str,str]
    job_fingerprint: str
    cv: CvMetadata


def now():
    return datetime.now(timezone.utc).isoformat()


class TailoringStore:
    def __init__(self, settings, db):
        self.cv = CvStore(settings)
        self.db = db

    def job(self, job_id):
        row = self.db.execute('SELECT id,title,company,description FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row is None:
            raise CvError(404,'Oferta no encontrada.')
        return {k:v or '' for k,v in dict(row).items()}

    @contextmanager
    def locked(self):
        # Reuse the master store's cross-thread/process lock and secure root fd.
        with self.cv.locked() as (root,index):
            try:
                os.mkdir('tailoring',mode=0o700,dir_fd=root)
            except FileExistsError:
                pass
            fd = os.open('tailoring',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=root)
            try:
                os.fchmod(fd,0o700)
                yield fd,root,index
            finally:
                os.close(fd)

    def _new(self,fd,name,content):
        # Atomic publication with no overwrite, using a same-directory hard link.
        stage = uuid.uuid4().hex+'.stage'
        try:
            self.cv._atomic(fd,stage,content)
            os.link(stage,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
        finally:
            try:
                os.unlink(stage,dir_fd=fd)
            except FileNotFoundError:
                pass

    def _save(self,fd,state):
        content=state.model_dump_json().encode()
        if len(content)>20_000_000:
            raise CvError(413,'El plan supera el límite privado de almacenamiento.')
        self.cv._atomic(fd,state.plan.id+'.json',content)

    def create(self,job_id,cv_id,expected,lang):
        job=self.job(job_id)
        with self.locked() as (fd,root,index):
            row=self.cv.find(index,cv_id,expected)
            content=self.cv._verified_content(root,row)
            cv=self.cv.public(row)
            parsed=parse(content.decode('utf-8-sig'),CvSource(id=cv.id,lang=cv.lang,path='',sha256=cv.sha256,imported_at=cv.imported_at))
            plan=make_plan(parsed,analyze(job),lang)
            plan.id=uuid.uuid4().hex; plan.created_at=plan.updated_at=now(); plan.cv_name=cv.name
            state=StoredPlan(plan=plan,job=job,job_fingerprint=fingerprint(job),cv=cv)
            self._new(fd,plan.id+'.source',content)
            try:
                self._save(fd,state)
            except Exception:
                os.unlink(plan.id+'.source',dir_fd=fd)
                raise
            return plan

    def _load(self,fd,plan_id,index):
        if not TOKEN.fullmatch(plan_id):
            raise CvError(422,'Identificador de plan inválido.')
        try:
            raw=self.cv._read(fd,plan_id+'.json',20_000_000)
        except FileNotFoundError:
            raise CvError(404,'Plan no encontrado.') from None
        try:
            state=StoredPlan.model_validate_json(raw)
        except ValueError:
            raise CvError(409,'El plan privado no supera la validación de integridad.') from None
        p=state.plan
        if (state.version!=1 or p.id!=plan_id or p.cv_id!=state.cv.id or p.cv_sha256!=state.cv.sha256 or
            p.job_id!=state.job.get('id') or state.job_fingerprint!=fingerprint(state.job)):
            raise CvError(409,'La identidad o revisión del plan no es válida.')
        try:
            content=self.cv._read(fd,plan_id+'.source',max(self.cv.limit,state.cv.size_bytes))
        except FileNotFoundError:
            raise CvError(409,'No está disponible la instantánea privada del plan.') from None
        if hashlib.sha256(content).hexdigest()!=p.cv_sha256:
            raise CvError(409,'La instantánea privada no supera la verificación SHA-256.')
        cv=parse(content.decode('utf-8-sig'),CvSource(id=state.cv.id,lang=state.cv.lang,path='',sha256=state.cv.sha256,imported_at=state.cv.imported_at))
        canonical=make_plan(cv,analyze(state.job),p.lang)
        fields={'analysis','matches','coverage','blockers','cv_partial'}
        if canonical.model_dump(include=fields)!=p.model_dump(include=fields) or [s.model_dump(exclude={'status'}) for s in canonical.suggestions]!=[s.model_dump(exclude={'status'}) for s in p.suggestions]:
            raise CvError(409,'Las propuestas o evidencias del plan no corresponden a sus fuentes.')
        master=next((r for r in index.records if r.id==p.cv_id),None)
        p.cv_changed=master is None or master.sha256!=p.cv_sha256
        try:
            p.job_changed=fingerprint(self.job(p.job_id))!=state.job_fingerprint
        except CvError as exc:
            if exc.status!=404: raise
            p.job_changed=True
        return state,cv,content

    @staticmethod
    def _revision(p,expected,mutate=False):
        if p.revision!=expected:
            raise CvError(409,'El plan cambió. Recarga y revisa las decisiones actuales.')
        if mutate and p.job_changed:
            raise CvError(409,'La oferta cambió. Crea un nuevo plan para la versión actual.')

    def get(self,plan_id):
        with self.locked() as (fd,_,index):
            return self._load(fd,plan_id,index)[0].plan

    def decide(self,plan_id,suggestion_id,status,expected):
        with self.locked() as (fd,_,index):
            state,_,_=self._load(fd,plan_id,index); p=state.plan
            self._revision(p,expected,True)
            s=next((s for s in p.suggestions if s.id==suggestion_id),None)
            if s is None: raise CvError(404,'Propuesta no encontrada.')
            s.status=status; p.revision+=1; p.updated_at=now(); p.state='review'
            p.artifact=p.artifact_sha256=None
            self._save(fd,state)
            return p

    @staticmethod
    def _preview(state,cv,content):
        pv=preview(cv,state.plan,content)
        if state.plan.job_changed:
            pv.blockers.append('La oferta cambió; crea un plan nuevo antes de generar.')
        return pv

    def preview(self,plan_id,expected):
        with self.locked() as (fd,_,index):
            state,cv,content=self._load(fd,plan_id,index)
            self._revision(state.plan,expected)
            return self._preview(state,cv,content)

    def generate(self,plan_id,expected,preview_sha256):
        with self.locked() as (fd,_,index):
            state,cv,content=self._load(fd,plan_id,index); p=state.plan
            self._revision(p,expected,True)
            pv=self._preview(state,cv,content)
            if pv.blockers:
                raise CvError(409,'La generación está bloqueada. Revisa las limitaciones y conflictos en la vista previa.')
            if pv.sha256!=preview_sha256:
                raise CvError(409,'La vista previa cambió. Revisa las diferencias antes de generar.')
            artifact=uuid.uuid4().hex
            p.artifact=artifact; p.artifact_sha256=pv.sha256; p.state='generated'
            p.revision+=1; p.updated_at=now()
            # Commit plan last: failed writes cannot publish a partial artifact.
            written=[]
            try:
                for name,data in ((artifact+'.tex',output_bytes(cv,pv.result,content)),
                                  (artifact+'.audit',state.model_dump_json().encode())):
                    self._new(fd,name,data); written.append(name)
                self._save(fd,state)
            except Exception:
                for name in written:
                    os.unlink(name,dir_fd=fd)
                raise
            return p

    def download(self,plan_id):
        with self.locked() as (fd,_,index):
            state,cv,source=self._load(fd,plan_id,index); p=state.plan
            if p.state!='generated' or not p.artifact or not TOKEN.fullmatch(p.artifact):
                raise CvError(409,'Genera una copia después de revisar sus diferencias.')
            content=self.cv._read(fd,p.artifact+'.tex',self.cv.limit*4+1000)
            # Regenerate to prove downloaded bytes correspond to approved changes.
            pv=preview(cv,p,source)
            if (pv.blockers or hashlib.sha256(content).hexdigest()!=p.artifact_sha256 or
                content!=output_bytes(cv,pv.result,source)):
                raise CvError(409,'El documento adaptado no supera la verificación de integridad.')
            return content
