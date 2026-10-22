"""Perfiles y ofertas sintéticos: sin datos personales ni red."""
import pytest
from jobhunter.matching import evaluate

BASE = {'titles':['soporte ti'], 'skills':['linux'], 'locations':['chile'],
        'preferences': {'modalities':['remoto'], 'seniority':['junior']}}
JOB = {'title':'Soporte TI', 'description':'Linux', 'location':'Chile'}


def run(body='', **patch):
    return evaluate({**JOB, 'description':body, **patch}, BASE)


def test_modality_requires_confirmation_and_differs_from_geography():
    unknown = run('Linux')
    remote = run('Linux', geo={'modality':'fully_remote'})
    onsite = run('Linux', location='Chile (presencial)')
    assert remote[0] == unknown[0] + 6
    assert onsite[0] < unknown[0]
    assert any('Modalidad por confirmar' in w for w in unknown[2])
    assert not any('Modalidad compatible' in r for r in unknown[1])


def test_structured_level_precedes_title_and_unknown_n1_stays_visible():
    score, _, warns = run('Nivel: Junior · Linux', title='Senior Soporte TI')
    assert score > 50 and not any('parece senior' in w for w in warns)
    assert run('Linux', title='Soporte TI N1/N2')[0] >= 38


def test_no_double_seniority_penalty():
    senior = run('Nivel: Senior · Linux')[0]
    years = run('Nivel: Senior · Linux. Obligatorio: 5 años de experiencia.')[0]
    assert years == senior


@pytest.mark.parametrize('requirement', ['Inglés C1 obligatorio', 'English B2 required', 'Fluent English required'])
def test_explicit_language_compared_to_declared_level(requirement):
    job = {**JOB, 'description': 'Linux. ' + requirement}
    _, _, missing = evaluate(job, BASE)
    _, _, lower = evaluate(job, {**BASE, 'languages':[{'name':'inglés', 'level':'A2'}]})
    _, pos, no_evidence = evaluate(job, {**BASE, 'languages':[{'name':'English', 'level':'C2'}]})
    assert any('Idioma requerido' in w for w in missing)
    assert any(('comparar manualmente' if requirement.startswith('Fluent') else 'inferior') in w for w in lower)
    assert any('sin evidencia' in w for w in no_evidence)
    assert not any('acreditado' in r for r in pos)


def test_technical_english_does_not_infer_language_and_learning_is_not_mastery():
    _, pos, warns = evaluate({**JOB, 'description':'Linux and Rust API cloud services'},
                            {**BASE, 'learning_skills':['rust']})
    assert not any('Idioma requerido' in w for w in warns)
    assert not any('rust' in r.lower() for r in pos)


@pytest.mark.parametrize('salary, phrase', [
    ('', 'Remuneración por confirmar'), ('Renta: 1000 - 1500 USD/mes', 'incomparables'),
    ('Renta: 10000000 - 20000000 CLP/año', 'incomparables'),
    ('Renta: 500000 - 700000 CLP/mes', 'inferior'),
    ('Renta: 700000 - 1000000 CLP/mes', 'se superpone')])
def test_salary_is_conservative(salary, phrase):
    _, _, warns = evaluate({**JOB, 'description':'Linux. ' + salary},
                          {**BASE, 'preferences':{'salary_min':800000, 'salary_currency':'CLP', 'salary_period':'mensual'}})
    assert any(phrase in w for w in warns)


def test_required_desirable_and_evidence_do_not_promise_fulfilment():
    profile = {**BASE, 'learning_skills':['rust'], 'skill_evidence':[{'skill':'linux','evidence':'Laboratorio'}]}
    _, pos, warns = evaluate({**JOB,'description':'Obligatorio: Linux y Rust. Deseable: SQL.'}, profile)
    assert any('Evidencia aportada' in r for r in pos)
    assert any('Obligatorio' in w and 'Rust' in w for w in warns)
    assert any('Deseable' in w and 'SQL' in w for w in warns)
    assert any('aprendizaje' in w for w in warns)


@pytest.mark.parametrize('job', [
    {**JOB, 'location':'Chile (Temporalmente remoto)', 'geo':{'modality':'temporarily_remote'}},
    {**JOB, 'description':'Linux. Modalidad: no remoto'},
    {**JOB, 'description':'Linux. Modalidad: remoto no confirmado'},
])
def test_ambiguous_or_negated_mode_has_no_bonus(job):
    _, pos, warns = evaluate(job, BASE)
    assert not any('Modalidad compatible' in r for r in pos)
    assert any('Modalidad por confirmar' in w for w in warns)


def test_language_markers_do_not_cross_clauses_or_invent_requirements():
    _, _, warns = run('Linux. English C1 required. French B2 optional.')
    assert any('Idioma requerido: english' in w for w in warns)
    assert any('Idioma deseable: french' in w for w in warns)
    _, _, benefit = run('Linux. Ofrecemos curso de inglés B2 gratuito.')
    assert not any('Idioma requerido' in w or 'Idioma deseable' in w for w in benefit)
