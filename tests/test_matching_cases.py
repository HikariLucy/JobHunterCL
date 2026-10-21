"""Casos de puntuación derivados del análisis de 326 ofertas reales (2026-10-21).

Los textos son sintéticos: reproducen el patrón observado sin copiar ofertas
ni nombres de empresas. Perfil: `DEFAULT_PROFILE` (no es el perfil del usuario).

- Las pruebas normales fijan el comportamiento correcto actual.
- Las marcadas `xfail(strict=True)` documentan defectos conocidos que M1 debe
  corregir. Al corregirlos pasarán, el xfail estricto fallará y habrá que
  quitar la marca. Ver docs/ANALISIS_PUNTAJES.md.
"""
import pytest

from jobhunter.config import DEFAULT_PROFILE
from jobhunter.matching import evaluate

THRESHOLD = DEFAULT_PROFILE["min_score"]


def job(title, description="", location="Remoto", level="Semi Senior", category="Programación"):
    # Get on Board antepone estos campos a la descripción del feed.
    head = f"Nivel: {level} · Jornada: Full time · Categoría: {category} "
    return {"title": title, "description": head + description, "location": location}


def score(j):
    return evaluate(j, DEFAULT_PROFILE)


SENIOR = "El cargo parece senior/de liderazgo"
YEARS = "Puede exigir 5 o más años de experiencia"
ENTRY = "Nivel inicial indicado"


# --- Comportamiento correcto actual -------------------------------------------------

def test_entry_level_it_roles_pass_threshold():
    for title, desc in [
        ("SRE / DevOps Engineer Junior", "Python, Linux y Docker en producción."),
        ("Soporte Operativo Junior", "Soporte a usuarios, Linux y redes LAN."),
        ("Junior IT Support Technician", "Soporte técnico de primer nivel."),
    ]:
        s, pos, _ = score(job(title, desc, level="Junior", category="SysAdmin / DevOps / QA"))
        assert s >= THRESHOLD, (title, s, pos)


def test_senior_in_title_is_penalized():
    s, _, warns = score(job("Senior Backend Engineer", "Python, SQL, Docker, Git.", level="Senior"))
    assert s < THRESHOLD and SENIOR in warns


def test_unrelated_commercial_role_stays_low():
    s, _, _ = score(job("Appointment Setter", "Agendar reuniones con clientes.", level="Junior",
                        category="Comercial y Ventas"))
    assert s < THRESHOLD


def test_explicit_five_years_is_flagged():
    _, _, warns = score(job("Backend Developer", "Requisitos: 5+ years of experience con Python."))
    assert YEARS in warns


# --- Defectos conocidos (M1) ---------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="El nivel se lee solo del título; 92/207 ofertas Senior/Expert sin advertencia")
def test_senior_level_field_is_penalized():
    s, _, warns = score(job("DevOps & AI Infrastructure Engineer",
                            "Python, PostgreSQL, Linux, Git y Docker.", level="Senior"))
    assert SENIOR in warns and s < THRESHOLD


@pytest.mark.xfail(strict=True, reason="El nivel se lee solo del título; 10/16 ofertas Junior sin bonificación")
def test_junior_level_field_counts_as_entry_level():
    _, pos, _ = score(job("Desarrollador .NET Web Forms + SQL Server", "C#, SQL Server.", level="Junior"))
    assert ENTRY in pos


@pytest.mark.xfail(strict=True, reason="norm() elimina el guion largo: '1–3 years' se lee como '13 years'")
def test_year_range_with_en_dash_is_not_five_plus():
    _, _, warns = score(job("Backend Developer", "1–3 years of experience con Python.", level="Junior"))
    assert YEARS not in warns


@pytest.mark.xfail(strict=True, reason="Cualquier 'N años' cuenta como experiencia exigida, incluida la edad")
def test_minimum_age_is_not_experience():
    _, _, warns = score(job("Chat Support Agent", "Requisito: ser mayor de 18 años.", level="Sin experiencia requerida"))
    assert YEARS not in warns


@pytest.mark.xfail(strict=True, reason="La habilidad 'redes' coincide con 'redes sociales'")
def test_social_media_is_not_networking():
    _, pos, _ = score(job("Community Manager", "Gestión de redes sociales y contenido.", category="Marketing"))
    assert not any("redes" in p for p in pos)


@pytest.mark.xfail(strict=True, reason="La habilidad 'soporte' coincide con 'soporte al cliente' no técnico")
def test_customer_service_is_not_it_support():
    _, pos, _ = score(job("Ejecutivo de Atención", "Soporte al cliente por chat y correo.",
                          category="Soporte al cliente"))
    assert not any("soporte" in p for p in pos)


@pytest.mark.xfail(strict=True, reason="'Remoto' suma ubicación de interés aunque exija residir en otro país (282/326)")
def test_remote_bonus_respects_residency_restriction():
    _, pos, _ = score(job("Backend Developer", "Python. Remoto solo para residentes en Argentina."))
    assert not any("Ubicación" in p for p in pos)
