"""Copias privadas exactas e índice atómico. Sin SQLite, compiladores ni logs.

POSIX: operaciones relativas al descriptor privado + O_NOFOLLOW; flock serializa
procesos. Los .deleted se recuperan según el índice tras una interrupción.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import stat
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from ..cv_contracts import CvMetadata, CvSource
from ..settings import ROOT
from . import cv_parser

_LOCK = threading.RLock()
TOKEN = re.compile(r'^[a-f0-9]{32}$')
BLOB = re.compile(r'^[a-f0-9]{32}\.tex$')


class CvError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message
        super().__init__(message)


class Record(CvMetadata):
    blob: str = Field(pattern=r'^[a-f0-9]{32}\.tex$')


class Index(BaseModel):
    version: int = 1
    records: list[Record] = Field(default_factory=list)


def validate(content: bytes, filename: str, limit: int) -> str:
    if len(content) > limit:
        raise CvError(413, 'El CV supera el límite de tamaño configurado.')
    if not filename.lower().endswith('.tex') or any(c in filename for c in '/\\\x00') or len(filename) > 255:
        raise CvError(422, 'Selecciona un archivo .tex con nombre válido, sin rutas.')
    try:
        tex = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise CvError(422, 'El archivo debe estar codificado en UTF-8 (BOM opcional).') from None
    if not tex.strip() or any(ord(c) < 32 and c not in '\n\r\t' for c in tex):
        raise CvError(422, 'El archivo contiene texto vacío o caracteres de control no admitidos.')
    masked = cv_parser._mask_comments(tex)
    if not re.search(r'\\(?:documentclass|begin\s*\{document\}|section|cvsection|name)\b', masked):
        raise CvError(422, 'No se reconoce contenido LaTeX de un currículum.')
    return tex


class CvStore:
    def __init__(self, settings):
        self.root = settings.data_dir / 'cv'
        # Nunca servir documentos desde public/dist ni ponerlos junto al código.
        target = self.root.parent.resolve() / 'cv'
        if ROOT in target.parents and ROOT / 'data' not in target.parents:
            raise CvError(500, 'La carpeta de CV debe ser privada y estar separada del código y archivos públicos.')
        self.limit = settings.cv_max_bytes

    @contextmanager
    def locked(self):
        # Linux Mint es la plataforma verificada. En sistemas sin estas primitivas
        # se falla cerrado; no se degrada la protección contra enlaces simbólicos.
        if not hasattr(os, 'O_NOFOLLOW') or os.open not in os.supports_dir_fd:
            raise CvError(500, 'La gestión segura de CV requiere soporte POSIX; esta plataforma está pendiente de validación.')
        import fcntl
        with _LOCK:
            self.root.parent.mkdir(parents=True, exist_ok=True)
            self.root.mkdir(mode=0o700, exist_ok=True)
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fchmod(fd, 0o700)
                lock = os.open('.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    index = self._index(fd)
                    self._recover(fd, index)
                    yield fd, index
                finally:
                    os.close(lock)
            finally:
                os.close(fd)

    def _read(self, fd: int, name: str, limit: int) -> bytes:
        f = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(f)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                raise CvError(500, 'Archivo privado inválido; no se modificó.')
            os.fchmod(f, 0o600)
            with os.fdopen(f, 'rb', closefd=False) as stream:
                content = stream.read(limit + 1)
            if len(content) > limit:
                raise CvError(500, 'Archivo privado fuera de los límites; no se modificó.')
            return content
        finally:
            os.close(f)

    def _index(self, fd: int) -> Index:
        try:
            raw = self._read(fd, 'index.json', 10_000_000)
        except FileNotFoundError:
            return Index()
        try:
            index = Index.model_validate_json(raw)
            ids = [r.id for r in index.records]
            primary = [r.lang for r in index.records if r.is_primary]
            if index.version != 1 or len(set(ids)) != len(ids) or len(set(primary)) != len(primary):
                raise ValueError('index')
            if any(not TOKEN.fullmatch(r.id) or not re.fullmatch('[a-f0-9]{64}', r.sha256) for r in index.records):
                raise ValueError('record')
            return index
        except ValueError:
            raise CvError(500, 'El índice de CV está dañado; se conservó para recuperación manual.') from None

    def _atomic(self, fd: int, name: str, content: bytes):
        temp = uuid.uuid4().hex + '.tmp'
        f = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            with os.fdopen(f, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
        finally:
            try:
                os.unlink(temp, dir_fd=fd)
            except FileNotFoundError:
                pass

    def _save(self, fd, index):
        content = index.model_dump_json().encode()
        if len(content) > 10_000_000:
            raise CvError(413, 'El índice de CV alcanzó su límite de tamaño.')
        self._atomic(fd, 'index.json', content)

    def _recover(self, fd, index):
        live = {r.blob for r in index.records}
        # Solo nombres internos, nunca recorrer carpetas ni seguir enlaces.
        for name in os.listdir(fd):
            if name.endswith('.deleted') and BLOB.fullmatch(name[:-8]):
                original = name[:-8]
                if original in live:
                    os.replace(name, original, src_dir_fd=fd, dst_dir_fd=fd)
                else:
                    os.unlink(name, dir_fd=fd)
            elif (BLOB.fullmatch(name) and name not in live) or re.fullmatch(r'[a-f0-9]{32}\.tmp', name):
                os.unlink(name, dir_fd=fd)

    @staticmethod
    def find(index, cv_id, expected=None):
        row = next((r for r in index.records if r.id == cv_id), None)
        if row is None:
            raise CvError(404, 'CV no encontrado.')
        if expected is not None and expected != row.sha256:
            raise CvError(409, 'El CV cambió. Actualiza la lista y revisa la versión antes de confirmar.')
        return row

    @staticmethod
    def public(row):
        return CvMetadata.model_validate(row.model_dump())

    def list(self):
        with self.locked() as (_, index):
            return [self.public(r) for r in index.records]

    def get(self, cv_id):
        with self.locked() as (_, index):
            return self.public(self.find(index, cv_id))

    def _verified_content(self, fd, row):
        content = self._read(fd, row.blob, max(row.size_bytes, self.limit))
        if hashlib.sha256(content).hexdigest() != row.sha256:
            raise CvError(409, 'La copia privada cambió fuera de JobHunter; se conservó para revisar su integridad.')
        return content

    def preview(self, cv_id):
        with self.locked() as (fd, index):
            row = self.find(index, cv_id)
            content = self._verified_content(fd, row)
            source = CvSource(id=row.id, lang=row.lang, path=row.blob, sha256=row.sha256, imported_at=row.imported_at)
            return cv_parser.parse(content.decode('utf-8-sig'), source)

    def import_cv(self, content, filename, name, lang):
        validate(content, filename, self.limit)
        if not name.strip() or len(name) > 120 or any(ord(c) < 32 for c in name):
            raise CvError(422, 'El nombre descriptivo debe tener entre 1 y 120 caracteres sin controles.')
        with self.locked() as (fd, index):
            stamp = datetime.now(timezone.utc).isoformat()
            row = Record(id=uuid.uuid4().hex, blob=uuid.uuid4().hex+'.tex', name=name.strip(), lang=lang,
                         sha256=hashlib.sha256(content).hexdigest(), imported_at=stamp, updated_at=stamp,
                         size_bytes=len(content))
            self._atomic(fd, row.blob, content)
            index.records.append(row)
            try:
                self._save(fd, index)
            except Exception:
                os.unlink(row.blob, dir_fd=fd)
                raise
            return self.public(row)

    def primary(self, cv_id):
        with self.locked() as (fd, index):
            row = self.find(index, cv_id)
            for other in index.records:
                if other.lang == row.lang:
                    other.is_primary = other.id == cv_id
            self._save(fd, index)
            return self.public(row)

    def replace(self, cv_id, content, filename, expected):
        validate(content, filename, self.limit)
        with self.locked() as (fd, index):
            row = self.find(index, cv_id, expected)
            self._verified_content(fd, row)
            old = row.blob
            row.blob = uuid.uuid4().hex+'.tex'
            row.sha256 = hashlib.sha256(content).hexdigest()
            row.size_bytes = len(content)
            row.updated_at = datetime.now(timezone.utc).isoformat()
            self._atomic(fd, row.blob, content)
            try:
                self._save(fd, index)
            except Exception:
                os.unlink(row.blob, dir_fd=fd)
                raise
            # El índice ya comprometido es la autoridad. Si se interrumpe aquí,
            # la próxima operación elimina únicamente la revisión no referenciada.
            os.unlink(old, dir_fd=fd)
            return self.public(row)

    def delete(self, cv_id, expected):
        with self.locked() as (fd, index):
            row = self.find(index, cv_id, expected)
            self._verified_content(fd, row)
            tombstone = row.blob+'.deleted'
            os.replace(row.blob, tombstone, src_dir_fd=fd, dst_dir_fd=fd)
            index.records.remove(row)
            try:
                self._save(fd, index)
            except Exception:
                os.replace(tombstone, row.blob, src_dir_fd=fd, dst_dir_fd=fd)
                raise
            os.unlink(tombstone, dir_fd=fd)
            return {'deleted': True}
