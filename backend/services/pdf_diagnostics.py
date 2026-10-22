"""Diagnósticos acotados; nunca expandir macros ni devolver fragmentos privados."""
import re
from . import cv_parser
from .tailoring_engine import ALLOWED, structure_blockers


def diagnostics(cv) -> list[str]:
    masked = cv_parser._mask_comments(cv.source_text)
    result = []
    classes = re.findall(r'\\documentclass(?:\[[^\]]*\])?\{([^{}]*)\}', masked)
    if classes != ['article']:
        result.append('Clase no soportada: se requiere article.')
    packages = re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([^{}]*)\}', masked)
    supported = {'inputenc', 'fontenc', 'babel', 'geometry', 'xcolor', 'hyperref', 'enumitem'}
    if any(p.strip() not in supported for group in packages for p in group.split(',')):
        result.append('Paquete no permitido por la gramática M2.2.')
    commands = {m[1] for m in cv_parser.COMMAND.finditer(masked)}
    if commands & {'input', 'include', 'includegraphics', 'bibliography', 'openin', 'read'}:
        result.append('Archivo externo requerido o intento de lectura: no admitido.')
    if commands - ALLOWED:
        result.append('Macro desconocida o peligrosa: no admitida por M2.2.')
    if any(env not in {'document', 'itemize'} for env in re.findall(r'\\(?:begin|end)\{([^{}]*)\}', masked)):
        result.append('Entorno no admitido por M2.2.')
    if structure_blockers(cv):
        result.append('Estructura insegura o no soportada; revisar una copia manualmente.')
    return result
