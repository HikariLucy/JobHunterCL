"""Inventario pasivo. Detectar un binario nunca autoriza ejecutar documentos.

No se ejecutan compiladores, docker, pdfinfo ni sondas desde una petición HTTP.
No hay un flag de configuración que eluda la ausencia de un runner auditado.
"""
import os
import shutil
from ..pdf_contracts import PdfCapabilities
from .pdf_sandbox import document_readiness

TOOLS = ('pdflatex', 'xelatex', 'lualatex', 'tectonic', 'bwrap', 'unshare',
         'podman', 'docker', 'prlimit', 'pdfinfo')
ENGINES = frozenset(TOOLS[:4])


def capabilities() -> PdfCapabilities:
    # Passive internal contract only: no report file/boolean can authorize TeX.
    readiness = document_readiness()
    if readiness.document_verified:
        raise RuntimeError('El adaptador documental M2.3C aún no está implementado.')
    detected = [name for name in TOOLS if shutil.which(name)]
    reasons = ['Compilación PDF deshabilitada: no existe un perfil de aislamiento verificado para documentos LaTeX.']
    if not ENGINES.intersection(detected):
        reasons.append('Herramienta de compilación ausente: no se detectó un motor LaTeX.')
    if os.name != 'posix':
        reasons.append('Esta plataforma no dispone de las garantías POSIX verificadas para CV.')
    reasons.append('Habilitar requiere aprobación explícita de dependencias y pruebas reales de aislamiento, paquetes cerrados y límites de recursos.')
    return PdfCapabilities(reasons=reasons, detected_tools=detected)
