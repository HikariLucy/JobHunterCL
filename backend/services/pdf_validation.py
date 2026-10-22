"""Inspección preliminar de bytes; NO acredita integridad estructural ni seguridad.

No invoca pdfinfo fuera de un aislamiento. No se usa para publicar un documento.
Un futuro validador aislado debe comprobar estructura, páginas (1..20), salida
única, exit code, archivos inesperados y metadatos sin contenido activo.
"""
import hashlib
import re
from .cv_store import CvError

MAX_PDF_BYTES = 10_000_000


def inspect_envelope(content: bytes, *, max_bytes: int = MAX_PDF_BYTES) -> dict:
    if not content or len(content) > max_bytes:
        raise CvError(422, 'PDF vacío o fuera del límite de tamaño.')
    if not re.match(rb'%PDF-(?:1\.[0-7]|2\.0)[\r\n]', content) or not content.rstrip().endswith(b'%%EOF'):
        raise CvError(422, 'No se reconoce una envoltura PDF completa.')
    return {'size_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
            'pages': None, 'structurally_verified': False}
