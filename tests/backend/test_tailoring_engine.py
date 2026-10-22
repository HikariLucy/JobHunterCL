"""M2.2: documentos y ofertas exclusivamente sintéticos."""
import hashlib

import pytest

from backend.cv_contracts import CvSource
from backend.services.cv_parser import parse
from backend.services.job_analysis import analyze
from backend.services.tailoring_engine import make_plan, preview

TEX = r'''\documentclass{article}
\begin{document}
Persona Sintética 😀 — demo@example.invalid
\section{Proyectos}
\begin{itemize}
\item Proyecto académico de dibujo con SVG.
\item Desarrollé servicios con Python y FastAPI.
\item Gestioné datos con PostgreSQL.
\end{itemize}
\section{Educación}
Ingeniería en curso desde 2022.
\end{document}
'''
ES = {'id': 'synthetic', 'title': 'Backend Junior', 'company': 'Empresa ficticia',
      'description': 'Buscamos desarrollador para nuestro equipo.\nRequisitos obligatorios:\nPython y FastAPI.\nDeseable: PostgreSQL.\nUsamos Docker en otro equipo.\nSe requieren 3 años de experiencia laboral.\nInglés B2 obligatorio.\nModalidad híbrida en Chile.'}
EN = {**ES, 'description': 'We are looking for a developer to join our team.\nRequirements:\nPython and FastAPI.\nNice to have: PostgreSQL.\nOur other team uses Docker.\nMust have 3 years of professional experience.\nEnglish B2 required.\nRemote work.'}


def parsed(tex=TEX):
    return parse(tex, CvSource(id='a'*32, lang='es', path='private', sha256=hashlib.sha256(tex.encode()).hexdigest(), imported_at='2026-10-21'))


@pytest.mark.parametrize('job,lang', [(ES,'es'), (EN,'en')])
def test_analysis_evidence_and_gaps(job, lang):
    a = analyze(job)
    assert a.lang == lang and a.title == job['title'] and not a.partial
    assert next(r for r in a.requirements if r.skill == 'Python').kind == 'required'
    assert next(r for r in a.requirements if r.skill == 'PostgreSQL').kind == 'nice_to_have'
    assert next(r for r in a.requirements if r.skill == 'Docker').kind == 'unknown'
    assert all(r.text in job['description'] for r in a.requirements)
    p = make_plan(parsed(), a, 'en')
    assert p.lang == 'en' and all(s.status == 'pending' for s in p.suggestions)
    assert {m.requirement_index for m in p.matches}
    for m in p.matches:
        ev = m.evidence
        assert ev.quote in next(s.text for s in parsed().sections if s.key == ev.section_key)
        assert TEX[slice(*ev.tex_span)] == ev.quote
    gaps = [s for s in p.suggestions if s.action == 'gap']
    assert any('3 ' in s.rationale for s in gaps)
    assert any('Docker' in s.rationale for s in gaps)
    assert all(s.after is None for s in gaps)
    assert not any(s.action == 'rephrase' for s in p.suggestions)


def test_partial_and_remote_does_not_choose_english():
    a = analyze({**ES, 'description': 'Remoto'})
    assert a.partial and a.lang == 'es'
    assert analyze({**ES, 'description': ''}).partial


def test_transformations_preserve_claims_and_unicode():
    p = make_plan(parsed(), analyze(ES), 'es')
    for s in p.suggestions:
        if s.action != 'gap':
            assert TEX[slice(*s.tex_span)] == s.before
            # Each transformation on its own is applicable, pending has no effect.
            assert preview(parsed(), p).result == TEX
            s.status = 'accepted'
            result = preview(parsed(), p)
            assert not result.blockers
            out = result.result
            assert 'Persona Sintética 😀 — demo@example.invalid' in out
            assert 'Ingeniería en curso desde 2022.' in out
            assert out.startswith('\\documentclass{article}') and out.endswith('\\end{document}\n')
            if s.action == 'emphasize':
                assert out.replace('\\textbf{'+s.before+'}', s.before) == TEX
            elif s.action == 'reorder':
                assert sorted(s.before.splitlines()) == sorted(s.after.splitlines())
            elif s.action == 'remove':
                assert s.after == '' and out == TEX[:s.tex_span[0]] + TEX[s.tex_span[1]:]
            s.status = 'pending'
    assert {'reorder','emphasize','remove'} <= {s.action for s in p.suggestions}


@pytest.mark.parametrize('extra', [r'\mystery{Python}', r'\input{private.tex}', r'\iftrue Python\fi', r'\newcommand{\x}{Python}', r'\begin{custom}Python\end{custom}'])
def test_complex_tex_analysis_only(extra):
    cv = parsed(TEX.replace('\\section{Educación}', extra+'\n\\section{Educación}'))
    p = make_plan(cv, analyze(ES), 'es')
    assert p.blockers and preview(cv, p).blockers


@pytest.mark.parametrize('line', ['No tengo experiencia con Python.', 'Estoy aprendiendo Python.', 'Sin conocimientos de Python.', 'I have no experience with Python.', 'Learning Python.', 'Python pendiente de aprender.'])
def test_no_evidence_for_negation_or_learning(line):
    cv = parsed(TEX.replace('Desarrollé servicios con Python y FastAPI.', line))
    p = make_plan(cv, analyze(ES), 'es')
    py = next(i for i,r in enumerate(p.analysis.requirements) if r.skill == 'Python')
    assert not any(m.requirement_index == py for m in p.matches)


def test_overlap_and_tampering_are_blocked():
    cv = parsed(); p = make_plan(cv, analyze(ES), 'es')
    for s in p.suggestions:
        if s.action in {'reorder','emphasize'}:
            s.status = 'accepted'
    assert preview(cv,p).blockers
    p = make_plan(cv, analyze(ES), 'es')
    s = next(s for s in p.suggestions if s.action=='emphasize')
    s.status='accepted'; s.after='Invented Kubernetes expert'
    assert preview(cv,p).blockers
