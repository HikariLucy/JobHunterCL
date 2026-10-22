"""Reglas locales sobre la descripción ya guardada. No acredita cumplimiento."""
from __future__ import annotations
import hashlib
import re

from jobhunter.matching import contains, has_skill, norm, required_years
from jobhunter.preferences import requirement_kind
from ..cv_contracts import JobAnalysis, Requirement

TECHNOLOGIES = ('Python', 'FastAPI', 'PostgreSQL', 'Docker', 'React', 'APIs REST', 'REST APIs',
                'TypeScript', 'JavaScript', 'SQL', 'Linux', 'Git', 'Java', 'Kubernetes', 'AWS',
                'Django', 'Flask', 'Node.js', 'C++', 'C#', '.NET', 'MongoDB', 'Redis')


def fingerprint(job: dict) -> str:
    # Metadata is pinned too; a title/company change invalidates the analysis.
    import json
    return hashlib.sha256(json.dumps({k: job.get(k) or '' for k in ('id','title','company','description')},
                                     ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def analyze(job: dict) -> JobAnalysis:
    description = job.get('description') or ''
    text = norm(description)
    es = sum(contains(text, w) for w in ('buscamos','requisitos','experiencia','equipo','desarrollador','obligatorio','modalidad','ingles'))
    en = sum(contains(text, w) for w in ('we','requirements','experience','team','developer','required','work','english'))
    lang = 'en' if en > es else 'es'
    requirements = []
    context = 'unknown'
    # Keep original substrings as evidence, including accents. Headings scope only
    # following lines, neutral sentences reset that scope.
    for chunk in re.split(r'\n|(?<=[.!?])\s+', description):
        quote = chunk.strip()
        if not quote:
            continue
        n = norm(quote)
        kind = requirement_kind(quote, context)
        if kind == 'unknown':
            context = 'unknown'
        if quote.endswith(':'):
            context = kind
        skills = [t for t in TECHNOLOGIES if has_skill(quote, t)]
        # SQL inside PostgreSQL is excluded by word boundaries in matching.contains.
        for skill in skills:
            requirements.append(Requirement(text=quote, kind=kind, skill=skill, category='technology'))
        category = None
        if required_years(n) is not None:
            category = 'experience'
        elif any(contains(n,w) for w in ('junior','senior','trainee','semi senior','mid level')):
            category = 'level'
        elif any(contains(n,w) for w in ('ingles','english','espanol','spanish','frances','french')):
            category = 'language'
        elif any(contains(n,w) for w in ('remoto','remote','hibrido','hibrida','hybrid','presencial','contrato','salary','renta','jornada')):
            category = 'condition'
        if category or (not skills and kind != 'unknown' and not quote.endswith(':')):
            requirements.append(Requirement(text=quote, kind=kind, category=category or 'other'))
    partial = len(description.strip()) < 80 or not requirements or description.rstrip().endswith(('…','...'))
    return JobAnalysis(job_id=job['id'], lang=lang, title=job.get('title') or '', company=job.get('company') or '',
                       description=description, description_sha256=hashlib.sha256(description.encode()).hexdigest(),
                       requirements=requirements, partial=partial,
                       warnings=['Análisis parcial: revisa manualmente el texto disponible y la oferta original.'] if partial else [])
