"""Ranking transparente, sin inventar competencias ni condiciones de elegibilidad."""
from __future__ import annotations
import re
import unicodedata


def norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode().split())


def contains(text: str, phrase: str) -> bool:
    phrase = norm(phrase)
    if not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", norm(text)) is not None


def evaluate(job: dict, profile: dict) -> tuple[int, list[str], list[str]]:
    """Devuelve score 0-100, motivos a favor y advertencias."""
    title = norm(job.get("title", ""))
    body = norm(job.get("description", ""))
    location = norm(job.get("location", ""))
    all_text = f"{title} {body}"
    positive, warnings = [], []
    score = 0
    role_terms = [x.strip() for x in profile.get("titles", []) if x.strip()]
    matched = [term for term in role_terms if contains(title, term)]
    if matched:
        score += 38
        positive.append("Cargo objetivo: " + matched[0])
    else:
        # Matches by constituent words when a title isn't an exact configured phrase
        overlaps = [term for term in role_terms if len(norm(term).split()) > 1 and
                    sum(contains(title, word) for word in norm(term).split()) >= 2]
        if overlaps:
            score += 22
            positive.append("Cargo similar: " + overlaps[0])
    skills = [s.strip() for s in profile.get("skills", []) if s.strip()]
    present = [s for s in skills if contains(all_text, s)]
    if present:
        score += min(42, len(present) * 7)
        positive.append("Coincidencias técnicas: " + ", ".join(present[:8]))
    if any(contains(title, k) for k in ("junior", "jr", "trainee", "practica", "entry level", "sin experiencia")):
        score += 18
        positive.append("Nivel inicial indicado")
    senior = any(contains(title, k) for k in ("senior", "sr", "staff", "principal", "lead", "jefe", "gerente", "manager", "architect"))
    if senior:
        score -= 48
        warnings.append("El cargo parece senior/de liderazgo")
    if re.search(r"\b(?:[5-9]|1\d)\s*(?:\+|o mas)?\s*(?:anos|years)\b", all_text):
        score -= 24
        warnings.append("Puede exigir 5 o más años de experiencia")
    if any(contains(all_text, k) for k in ("english c1", "ingles avanzado", "fluent english", "native english")):
        warnings.append("Revisar nivel de inglés exigido")
    loc_terms = [norm(x) for x in profile.get("locations", []) if x.strip()]
    if loc_terms and any(contains(location, x) for x in loc_terms):
        score += 8
        positive.append("Ubicación/modalidad de interés")
    if any(contains(location, x) for x in ("united states only", "us only", "usa only", "canada only")):
        score -= 40
        warnings.append("Posible restricción de residencia")
    if not location:
        warnings.append("Ubicación sin confirmar")
    if not positive:
        warnings.append("No se detectaron coincidencias claras con el perfil")
    return max(0, min(100, score)), positive, warnings
