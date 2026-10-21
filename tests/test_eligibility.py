"""Elegibilidad geográfica: compatible (con evidencia), desconocida e incompatible."""
import pytest

from jobhunter.config import DEFAULT_PROFILE
from jobhunter.matching import COMPATIBLE, INCOMPATIBLE, UNKNOWN, eligibility, evaluate

HEAD = "Nivel: Junior · Jornada: Full time · Categoría: Programación "


def job(location, description="Python.", geo=None, title="Desarrollador Backend"):
    j = {"title": title, "location": location, "description": HEAD + description}
    if geo is not None:
        j["geo"] = geo
    return j


def status(j, profile=DEFAULT_PROFILE):
    return eligibility(j, profile)["status"]


@pytest.mark.parametrize("location, expected", [
    ("Santiago, Chile", COMPATIBLE),
    ("Perú, Colombia, Argentina , Chile", COMPATIBLE),
    ("Chile (híbrido)", COMPATIBLE),
    ("Argentina, Colombia, Uruguay", INCOMPATIBLE),
    ("Buenos Aires, Argentina (híbrido)", INCOMPATIBLE),   # antes «híbrido» lo ocultaba
    ("USA only", INCOMPATIBLE),
    ("Remoto", UNKNOWN),                                    # sin países: no se confirma
    ("Remoto (elegibilidad para Chile por confirmar)", UNKNOWN),
    ("Remoto (incluye Chile)", UNKNOWN),                    # filas guardadas antes de M1.3
    ("No indicada (verificar en oferta)", UNKNOWN),
    ("", UNKNOWN),
])
def test_text_only_classification(location, expected):
    assert status(job(location)) == expected


def test_remote_preference_is_not_a_place():
    """«remote/remoto» en el perfil es una modalidad deseada; no confirma elegibilidad."""
    only_remote = {**DEFAULT_PROFILE, "locations": ["remoto", "remote"]}
    result = eligibility(job("Remoto"), only_remote)
    assert result["status"] == UNKNOWN and "no define zonas" in result["evidence"]


@pytest.mark.parametrize("geo, expected, evidence", [
    ({"modality": "fully_remote", "countries": []}, COMPATIBLE, "remoto sin restricción de país"),
    ({"modality": "remote_local", "countries": []}, UNKNOWN, "no informa"),
    ({"modality": "hybrid", "countries": ["Chile", "Mexico"]}, COMPATIBLE, "Chile, Mexico"),
    ({"modality": "hybrid", "countries": ["Mexico"]}, INCOMPATIBLE, "Mexico"),
    ({"modality": "hybrid", "countries": []}, UNKNOWN, "no informa el país"),
    ({"modality": "remote_local", "countries": ["Perú", "Chile"], "evidence": "API + feed"}, COMPATIBLE, "Perú, Chile"),
])
def test_structured_metadata(geo, expected, evidence):
    result = eligibility(job("Texto cualquiera", geo=geo), DEFAULT_PROFILE)
    assert result["status"] == expected and evidence in result["evidence"]
    assert result["basis"] != "texto"


def test_metadata_wins_over_visible_text():
    """El texto visible dice Chile, pero los metadatos no informan países: queda desconocida."""
    j = job("Remoto (incluye Chile)", geo={"modality": "remote_local", "countries": []})
    assert status(j) == UNKNOWN
    j = job("Remoto", geo={"modality": "hybrid", "countries": ["Argentina"]})
    assert status(j) == INCOMPATIBLE


def test_explicit_text_restriction_overrides_metadata():
    j = job("Remoto", "Python. Only candidates based in United States.", geo={"modality": "fully_remote", "countries": []})
    result = eligibility(j, DEFAULT_PROFILE)
    assert result["status"] == INCOMPATIBLE and "united states" in result["evidence"]
    j = job("Remoto", "Python. Candidates must be based in Latin America.")
    assert status(j) == COMPATIBLE


def test_scoring_by_eligibility():
    confirmed = evaluate(job("Santiago, Chile"), DEFAULT_PROFILE)
    unknown = evaluate(job("Remoto (elegibilidad para Chile por confirmar)"), DEFAULT_PROFILE)
    outside = evaluate(job("Argentina"), DEFAULT_PROFILE)
    assert confirmed[0] == unknown[0] + 8 and outside[0] < unknown[0]
    assert any(p.startswith("Ubicación compatible: ") for p in confirmed[1])
    assert not any("Ubicación" in p for p in unknown[1])
    assert any(w.startswith("Elegibilidad geográfica por confirmar") for w in unknown[2])
    assert any(w.startswith("Ubicación fuera de tus zonas de interés") for w in outside[2])


def test_unknown_is_not_penalized_and_stays_scorable():
    """Una oferta de elegibilidad desconocida conserva el resto de su puntaje (no se descarta)."""
    s, pos, _ = evaluate(job("Remoto", "Python, SQL, Linux, Docker.", title="Desarrollador Junior"), DEFAULT_PROFILE)
    assert s >= DEFAULT_PROFILE["min_score"] and any("Cargo objetivo" in p for p in pos)
