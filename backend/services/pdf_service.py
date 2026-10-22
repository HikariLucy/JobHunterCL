"""Frontera M2.3 cerrada: verificación y trazabilidad, sin ejecución de TeX.

Un runner futuro deberá separar preparación inmutable, aislamiento comprobado,
ejecución acotada, validación aislada y publicación. Ninguna de esas etapas puede
sustituirse por subprocess local, pdfinfo local o un compilador falso de producción.
"""
import os
import uuid

from ..pdf_contracts import PdfStatus
from .cv_store import CvError
from .pdf_diagnostics import diagnostics
from .pdf_environment import capabilities
from .tailoring_store import TailoringStore, now


class PdfService:
    def __init__(self, store: TailoringStore):
        self.store = store

    def generate(self, plan_id, expected_revision, expected_tex_sha256):
        store = self.store
        # One lock: no revision/decision race between checking and auditing.
        with store.locked() as (fd, _, index):
            state, cv, source = store._load(fd, plan_id, index)
            store._verified_artifact(fd, state, cv, source, expected_revision, expected_tex_sha256)
            environment = capabilities()
            # Literal False contract: no environment toggle or detected tool can
            # activate an unimplemented runner. No process, queue or temp dir.
            assert environment.available is False
            status = PdfStatus(plan_id=plan_id, revision=expected_revision,
                status='blocked', code=environment.code, tex_sha256=expected_tex_sha256,
                attempt_id=uuid.uuid4().hex, created_at=now(), diagnostics=diagnostics(cv))
            audit = status.attempt_id + '.pdf-audit'
            store._new(fd, audit, status.model_dump_json().encode())
            try:
                store.cv._atomic(fd, plan_id+'.pdf-status', status.model_dump_json().encode())
            except Exception:
                os.unlink(audit, dir_fd=fd)
                raise
        raise CvError(503, environment.reasons[0])

    def status(self, plan_id, expected_revision):
        store = self.store
        with store.locked() as (fd, _, index):
            state, cv, source = store._load(fd, plan_id, index)
            p = state.plan
            store._revision(p, expected_revision)
            empty = PdfStatus(plan_id=plan_id, revision=p.revision, diagnostics=diagnostics(cv))
            if p.state != 'generated':
                return empty
            store._verified_artifact(fd, state, cv, source)
            empty.tex_sha256 = p.artifact_sha256
            try:
                status = PdfStatus.model_validate_json(store.cv._read(fd, plan_id+'.pdf-status', 32_000))
            except FileNotFoundError:
                return empty
            except ValueError:
                raise CvError(409, 'El estado PDF privado no supera la verificación de integridad.') from None
            if status.plan_id != plan_id:
                raise CvError(409, 'El estado PDF privado no corresponde al plan.')
            if status.revision != p.revision or status.tex_sha256 != p.artifact_sha256:
                return empty
            if not status.attempt_id or status.status != 'blocked' or status.code != 'sandbox_unverified':
                raise CvError(409, 'El estado PDF privado no supera la verificación de integridad.')
            try:
                audit = store.cv._read(fd, status.attempt_id+'.pdf-audit', 32_000)
            except FileNotFoundError:
                raise CvError(409, 'No está disponible el historial privado del intento PDF.') from None
            if audit != status.model_dump_json().encode():
                raise CvError(409, 'El estado PDF privado no supera la verificación de integridad.')
            return status

    def download(self, plan_id, expected_revision):
        self.status(plan_id, expected_revision)
        raise CvError(409, 'No existe un PDF generado y verificado para esta revisión. La compilación segura está deshabilitada.')
