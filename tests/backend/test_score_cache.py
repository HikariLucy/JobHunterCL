from backend.services import jobs as svc
from jobhunter.config import DEFAULT_PROFILE
from jobhunter.matching import evaluate

JOB = {"id": "a" * 24, "title": "Soporte TI Junior", "location": "Santiago, Chile",
       "description": "Nivel: Junior · Jornada: Full time · Categoría: Soporte Técnico Linux y redes."}


def test_cache_matches_evaluate_and_avoids_recomputing(monkeypatch):
    profile = {**DEFAULT_PROFILE, "skills": ["linux", "redes"]}
    expected = evaluate(JOB, profile)
    assert (svc.score(JOB, profile)["score"], svc.score(JOB, profile)["reasons"]) == (expected[0], expected[1])
    calls = []
    monkeypatch.setattr(svc, "evaluate", lambda j, p: calls.append(1) or evaluate(j, p))
    svc.score(JOB, profile)
    assert calls == []


def test_cache_invalidates_on_profile_or_content_change(monkeypatch):
    profile = {**DEFAULT_PROFILE, "skills": ["linux"]}
    svc.score(JOB, profile)
    calls = []
    monkeypatch.setattr(svc, "evaluate", lambda j, p: calls.append(1) or evaluate(j, p))
    changed_profile = {**profile, "skills": ["linux", "redes"]}
    assert any("redes" in r for r in svc.score(JOB, changed_profile)["reasons"])
    changed_job = {**JOB, "description": JOB["description"] + " Python."}
    svc.score(changed_job, changed_profile)
    assert len(calls) == 2


def test_cached_lists_are_not_shared():
    a = svc.score(JOB, DEFAULT_PROFILE)
    a["reasons"].append("mutado")
    assert "mutado" not in svc.score(JOB, DEFAULT_PROFILE)["reasons"]
