from jobhunter.matching import contains, evaluate

PROFILE = {"titles": ["desarrollador junior", "soporte ti"], "skills": ["python", "linux", "sql"], "locations": ["santiago", "chile", "remoto"]}


def test_exact_title_and_skills():
    score, reasons, warnings = evaluate({"title": "Desarrollador Junior Python", "description": "SQL y Linux", "location": "Santiago, Chile"}, PROFILE)
    assert score >= 65
    assert any("Cargo objetivo" in r for r in reasons)


def test_senior_is_deprioritized():
    junior = {"title": "Soporte TI Junior", "description": "Python y Linux", "location": "Chile"}
    senior = {**junior, "title": "Senior Soporte TI Lead"}
    assert evaluate(junior, PROFILE)[0] > evaluate(senior, PROFILE)[0]


def test_do_not_match_substring():
    assert not contains("javascript", "java")


def test_no_claim_eligible_for_remote():
    score, _, warnings = evaluate({"title": "Soporte TI", "description": "", "location": "USA only"}, PROFILE)
    assert any("residencia" in w for w in warnings)
