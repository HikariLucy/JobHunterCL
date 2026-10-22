"""Extracción textual acotada: no interpreta TeX, macros, archivos ni enlaces."""
from __future__ import annotations
import re
import unicodedata

from ..cv_contracts import CvSection, CvSource, ParsedCv, UninterpretedCv

SECTION = re.compile(r'\\(?:section|subsection|cvsection)\*?\s*\{([^{}]*)\}')
COMMAND = re.compile(r'\\([a-zA-Z@]+|[^a-zA-Z])(?:\*?)')
KINDS = {
    'summary': ('resumen', 'perfil', 'perfil profesional', 'resumen profesional', 'summary', 'profile', 'professional summary'),
    'experience': ('experiencia', 'experiencia profesional', 'experiencia laboral', 'experience', 'work experience', 'professional experience'),
    'education': ('educacion', 'formacion', 'formacion academica', 'education'),
    'skills': ('habilidades', 'competencias', 'habilidades tecnicas', 'skills', 'technical skills'),
    'projects': ('proyectos', 'projects'), 'languages': ('idiomas', 'languages'),
}
FORMAT = {'textbf', 'textit', 'texttt', 'emph', 'underline', 'textrm', 'textnormal', 'textsc', 'mbox'}
LAYOUT = {'documentclass', 'usepackage', 'begin', 'end', 'item', 'section', 'subsection', 'cvsection',
          'maketitle', 'par', 'smallskip', 'medskip', 'bigskip', 'noindent', 'hfill', 'newline'}
CONTACT = {'name', 'email', 'phone', 'address', 'title', 'author', 'date', 'url'}
KNOWN = FORMAT | LAYOUT | CONTACT | {'href', 'textbackslash', 'LaTeX', 'TeX'}
ENVIRONMENTS = {'document', 'itemize', 'enumerate', 'center', 'flushleft', 'flushright'}


def norm(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c)).strip()


def _mask_comments(tex: str) -> str:
    # Un % es comentario salvo que lo preceda una cantidad impar de barras.
    chars = list(tex)
    i = 0
    while i < len(tex):
        if tex[i] == '%':
            j = i - 1
            while j >= 0 and tex[j] == "\\":
                j -= 1
            if (i - 1 - j) % 2 == 0:
                end = tex.find('\n', i)
                if end < 0:
                    end = len(tex)
                chars[i:end] = ' ' * (end - i)
                i = end
                continue
        i += 1
    return ''.join(chars)



def _plain(raw: str) -> str:
    raw = _mask_comments(raw)
    raw = re.sub(r'\\(?:documentclass|usepackage)(?:\[[^\]]*\])?\{[^{}]*\}', '', raw)
    raw = re.sub(r'\\(?:begin|end)\{[^{}]*\}', '', raw)
    raw = re.sub(r'\\href\{[^{}]*\}\{([^{}]*)\}', r'\1', raw)
    raw = re.sub(r'\\(?:section|subsection|cvsection)\*?\s*\{([^{}]*)\}', r'\1\n', raw)
    raw = re.sub(r'\\item(?:\[[^\]]*\])?', '\n• ', raw)
    raw = re.sub(r'\\\\|\\(?:newline|par)\b', '\n', raw)
    raw = re.sub(r'\\([%&#_$])', r'\1', raw)
    raw = COMMAND.sub('', raw)
    raw = raw.replace('{', '').replace('}', '').replace('~', ' ')
    return '\n'.join(' '.join(line.split()) for line in raw.splitlines() if line.strip()).strip()


def parse(tex: str, source: CvSource) -> ParsedCv:
    masked = _mask_comments(tex)
    # Un entorno desconocido se conserva entero, incluido su cuerpo multilínea.
    ranges: list[tuple[int, int]] = []
    active: list[str] = []
    start = 0
    for token in re.finditer(r'\\(begin|end)\{([^{}]*)\}', masked):
        op, env = token[1], token[2]
        if not active:
            if op == 'begin' and env not in ENVIRONMENTS:
                active = [env]
                start = token.start()
        elif op == 'begin':
            active.append(env)
        elif env == active[-1]:
            active.pop()
            if not active:
                ranges.append((start, token.end()))
    if active:
        ranges.append((start, len(tex)))

    conditional = re.search(r'\\(?:if[a-zA-Z]*|else|fi)\b', masked)
    if conditional:
        ranges.append((conditional.start(), len(tex)))

    lines = masked.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    i = 0
    while i < len(lines):
        line = lines[i]
        bad = any(m[1] not in KNOWN and m[1][0].isalpha() for m in COMMAND.finditer(line))
        bad |= any(m[1] not in ENVIRONMENTS for m in re.finditer(r'\\(?:begin|end)\{([^{}]*)\}', line))
        if bad:
            first = i
            depth = 0
            while True:
                depth += sum(1 if m[0] == '{' else -1 for m in re.finditer(r'(?<!\\)[{}]', lines[i]))
                if i + 1 == len(lines) or depth <= 0:
                    break
                i += 1
            # Argumentos que comienzan en la siguiente línea también son opacos.
            while i + 1 < len(lines):
                following = i + 1
                while following < len(lines) and not lines[following].strip():
                    following += 1
                if following == len(lines) or not lines[following].lstrip().startswith('{'):
                    break
                i = following
                depth = 0
                while True:
                    depth += sum(1 if m[0] == '{' else -1 for m in re.finditer(r'(?<!\\)[{}]', lines[i]))
                    if i + 1 == len(lines) or depth <= 0:
                        break
                    i += 1
            ranges.append((offsets[first], offsets[i+1]))
        i += 1
    excluded: list[tuple[int, int]] = []
    for a, b in sorted(ranges):
        if excluded and a <= excluded[-1][1]:
            excluded[-1] = (excluded[-1][0], max(b, excluded[-1][1]))
        else:
            excluded.append((a, b))
    unknown = [UninterpretedCv(tex_span=(a, b), raw_tex=tex[a:b],
                reason='Macro o entorno no interpretado; revisar el fuente.') for a, b in excluded]
    extraction = list(masked)
    for a, b in excluded:
        extraction[a:b] = ['\n' if c == '\n' else ' ' for c in masked[a:b]]
    safe = ''.join(extraction)
    markers = list(SECTION.finditer(safe))
    starts = [(0, 'header', 'Encabezado')]
    for m in markers:
        title = m[1]
        kind = next((kind for kind, names in KINDS.items() if norm(title) in names), 'other')
        starts.append((m.start(), kind, title))
    sections = []
    for i, (a, kind, title) in enumerate(starts):
        b = starts[i+1][0] if i+1 < len(starts) else len(tex)
        text = _plain(safe[a:b])
        if text:
            sections.append(CvSection(key=f'{kind}[{i}]', kind=kind, title=title, text=text,
                                      tex_span=(a, b), raw_tex=tex[a:b]))
    warnings = []
    if unknown:
        warnings.append('Extracción parcial: hay macros o entornos sin interpretar. No se han ejecutado.')
    if any(s.kind == 'other' for s in sections):
        warnings.append('Hay secciones cuyo tipo no se reconoce; se conservan como otras secciones.')
    if not markers:
        warnings.append('No se reconocieron divisiones por sección; revisar el contenido como encabezado.')
    warnings.append('Vista textual orientativa: no reproduce el diseño LaTeX ni acredita experiencia.')
    return ParsedCv(source=source, source_text=tex, sections=sections, skills=[],
                    partial=bool(unknown or not markers or any(s.kind == 'other' for s in sections)),
                    warnings=warnings, uninterpreted=unknown)
