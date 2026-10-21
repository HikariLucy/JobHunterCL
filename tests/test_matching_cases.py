"""Casos de puntuación derivados del análisis de 326 ofertas reales (2026-10-21).

Los textos son sintéticos: reproducen el patrón observado sin copiar ofertas
ni nombres de empresas. Perfil: `DEFAULT_PROFILE` (no es el perfil del usuario).

- Las pruebas con docstring «Antes: …» eran los 7 defectos documentados como
  xfail estrictos; M1 los corrigió. Medición antes/después: scripts/eval_matching.py
  y docs/ANALISIS_PUNTAJES.md.
"""
import pytest

from jobhunter.config import DEFAULT_PROFILE
from jobhunter.matching import evaluate, norm, required_years

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
    s, _, warns = score(job("Senior Backend Engineer", "Python, SQL, Docker, Git.", level="Semi Senior"))
    assert s < THRESHOLD and SENIOR in warns  # el título manda aunque la fuente diga Semi Senior


def test_unrelated_commercial_role_stays_low():
    s, _, _ = score(job("Appointment Setter", "Agendar reuniones con clientes.", level="Junior",
                        category="Comercial y Ventas"))
    assert s < THRESHOLD


def test_explicit_five_years_is_flagged():
    _, _, warns = score(job("Backend Developer", "Requisitos: 5+ years of experience con Python."))
    assert YEARS in warns


def test_senior_level_field_is_penalized():
    """Antes: 92/207 ofertas Senior/Expert sin «senior» en el título no se penalizaban."""
    s, _, warns = score(job("DevOps & AI Infrastructure Engineer",
                            "Python, PostgreSQL, Linux, Git y Docker.", level="Senior"))
    assert "La fuente indica nivel senior" in warns and s < THRESHOLD


def test_junior_level_field_counts_as_entry_level():
    """Antes: 10/16 ofertas Junior sin «junior» en el título no recibían la bonificación."""
    _, pos, _ = score(job("Desarrollador .NET Web Forms + SQL Server", "C#, SQL Server.", level="Junior"))
    assert ENTRY in pos


def test_semi_senior_is_softly_penalized_for_entry_profiles():
    s_mid, _, warns = score(job("Programador Back-end", "Python.", level="Semi Senior"))
    s_jr, _, _ = score(job("Programador Back-end", "Python.", level="Junior"))
    assert s_mid < s_jr and any("Semi Senior" in w for w in warns)


def test_seniority_preference_changes_level_scoring():
    mid_profile = {**DEFAULT_PROFILE, "preferences": {"seniority": ["Semi Senior"]}}
    _, pos, warns = evaluate(job("Programador Back-end", "Python.", level="Semi Senior"), mid_profile)
    assert "Nivel buscado: semi senior" in pos and not any("Semi Senior" in w for w in warns)
    senior_profile = {**DEFAULT_PROFILE, "preferences": {"seniority": ["senior"]}}
    _, _, warns = evaluate(job("Backend Engineer", "Python.", level="Senior"), senior_profile)
    assert not any("senior" in w.lower() for w in warns)


def test_year_range_with_en_dash_is_not_five_plus():
    """Antes: norm() eliminaba el guion largo y «1–3 years» se leía «13 years»."""
    _, _, warns = score(job("Backend Developer", "1–3 years of experience con Python.", level="Junior"))
    assert YEARS not in warns


def test_minimum_age_is_not_experience():
    """Antes: cualquier «N años» contaba como experiencia exigida, incluida la edad."""
    _, _, warns = score(job("Chat Support Agent", "Requisito: ser mayor de 18 años.", level="Sin experiencia requerida"))
    assert YEARS not in warns


@pytest.mark.parametrize("text, years", [
    ("1–3 years of experience", 1),
    ("ser mayor de 18 años", None),
    ("18 years old", None),
    ("con más de 12 años creciendo en el mercado", None),
    ("empresa con más de 50 años de experiencia en el continente", None),
    ("Mínimo 5 años en desarrollo", 5),
    ("+5 años en ciberseguridad", 5),
    ("5+ years of professional experience", 5),
    ("5 o más años de experiencia", 5),
    ("3 a 5 años de experiencia", 3),
    ("at least 4 years", 4),
    ("2 años de experiencia en Python 3", 2),
])
def test_required_years(text, years):
    assert required_years(norm(text)) == years


def test_three_or_four_years_warn_entry_profiles_only():
    _, _, warns = score(job("QA Engineer", "3+ años de experiencia en QA.", level="Junior"))
    assert "Pide 3 años de experiencia" in warns
    mid = {**DEFAULT_PROFILE, "preferences": {"seniority": ["semi senior"]}}
    _, _, warns = evaluate(job("QA Engineer", "3+ años de experiencia en QA."), mid)
    assert not any("años" in w for w in warns)


def test_networking_and_it_support_still_match():
    _, pos, _ = score(job("Técnico de Soporte", "Soporte técnico a usuarios y redes LAN. Redes sociales: no.",
                          level="Junior", category="Soporte Técnico"))
    assert any("redes" in p and "soporte" in p for p in pos)


def test_compatible_or_negated_residency_is_not_restricted():
    for text in ("Candidates must be based in Latin America.", "No tienes que vivir en CDMX.",
                 "Solo residentes en Chile."):
        _, pos, warns = score(job("Backend Developer", text))
        assert any("Ubicación" in p for p in pos), text
        assert not any("restricción" in w for w in warns), text


def test_country_list_without_profile_zone_is_flagged():
    """44/326 ofertas listan países elegibles sin Chile y no tenían advertencia."""
    s_out, _, warns = score(job("Backend Developer", "Python.", location="Argentina, Colombia, Uruguay", level="Junior"))
    s_in, _, _ = score(job("Backend Developer", "Python.", location="Perú, Colombia, Chile", level="Junior"))
    assert s_out < s_in and any("fuera de tus zonas" in w for w in warns)
    _, _, warns = score(job("Backend Developer", "Python.", location="No indicada (verificar en oferta)"))
    assert not any("fuera de tus zonas" in w for w in warns)


def test_social_media_is_not_networking():
    """Antes: la habilidad «redes» coincidía con «redes sociales»."""
    _, pos, _ = score(job("Community Manager", "Gestión de redes sociales y contenido.", category="Marketing"))
    assert not any("redes" in p for p in pos)


def test_customer_service_is_not_it_support():
    """Antes: la habilidad «soporte» coincidía con «soporte al cliente» no técnico."""
    _, pos, _ = score(job("Ejecutivo de Atención", "Soporte al cliente por chat y correo.",
                          category="Soporte al cliente"))
    assert not any("soporte" in p for p in pos)


def test_remote_bonus_respects_residency_restriction():
    """Antes: «Remoto» sumaba ubicación aunque la oferta exigiera residir en otro país."""
    _, pos, _ = score(job("Backend Developer", "Python. Remoto solo para residentes en Argentina."))
    assert not any("Ubicación" in p for p in pos)
