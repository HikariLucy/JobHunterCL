"""Ranking transparente, sin inventar competencias ni condiciones de elegibilidad."""
from __future__ import annotations
import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=512)  # contains() vuelve a normalizar el mismo texto por cada término
def norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", str(s).lower()).encode("ascii", "ignore").decode().split())


def contains(text: str, phrase: str) -> bool:
    phrase = norm(phrase)
    if not phrase:
        return False
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", norm(text)) is not None


# Categorías publicadas por Get on Board (normalizadas). Se usan como prefijo porque
# el feed no separa la categoría del cuerpo cuando la oferta no informa renta.
SOURCE_CATEGORIES = (
    "programacion", "sysadmin / devops / qa", "data science / analytics", "machine learning / ai",
    "desarrollo mobile", "diseno / ux", "ciberseguridad", "soporte tecnico", "soporte al cliente",
    "comercial y ventas", "marketing digital", "contenido, publicidad y medios", "operaciones / admin",
    "producto, innovacion y agilidad", "recursos humanos", "educacion y coaching",
)
_LEVEL = re.compile(r"^Nivel: ([^·]{1,40}?) ·")
_CATEGORY = re.compile(r"Categoría: ([^·]{1,80})")


def source_meta(description: str) -> dict:
    """Nivel y categoría que la fuente antepone a la descripción (Get on Board); None si faltan."""
    head = str(description or "")[:300]
    level = _LEVEL.match(head)
    cat = _CATEGORY.search(head)
    category = None
    if cat:
        text = norm(cat.group(1))
        category = next((c for c in SOURCE_CATEGORIES if text.startswith(c)), None)
    return {"level": norm(level.group(1)) if level else None, "category": category}


LEVEL_CLASS = {"sin experiencia requerida": "inicial", "junior": "inicial", "trainee": "inicial",
               "semi senior": "intermedio", "senior": "senior", "expert": "senior"}
LEVEL_BONUS = {"inicial": 18, "intermedio": 10, "senior": 10}
_WANTED_WORDS = (("inicial", ("junior", "jr", "trainee", "practica", "sin experiencia", "inicial", "entry")),
                 ("intermedio", ("semi", "intermedio", "mid")),
                 ("senior", ("senior", "expert", "lead")))


def wanted_levels(profile: dict) -> set[str]:
    """Niveles de «Nivel buscado» del perfil; sin preferencia se asume nivel inicial."""
    prefs = profile.get("preferences") or {}
    values = [norm(v) for v in (prefs.get("seniority") or []) if str(v).strip()]
    found = set()
    for value in values:
        # «semi senior» es intermedio, no senior
        if any(w in value for w in _WANTED_WORDS[1][1]):
            found.add("intermedio")
            continue
        for cls, words in (_WANTED_WORDS[0], _WANTED_WORDS[2]):
            if any(w in value for w in words):
                found.add(cls)
    return found or {"inicial"}


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
    wanted = wanted_levels(profile)
    level = source_meta(job.get("description", "")).get("level")
    offer = LEVEL_CLASS.get(level)
    if any(contains(title, k) for k in ("junior", "jr", "trainee", "practica", "entry level", "sin experiencia")):
        offer = offer or "inicial"
    senior_title = any(contains(title, k) for k in ("senior", "sr", "staff", "principal", "lead", "jefe", "gerente", "manager", "architect"))
    if offer in wanted:
        score += LEVEL_BONUS[offer]
        positive.append("Nivel inicial indicado" if offer == "inicial" else f"Nivel buscado: {level or offer}")
    if "senior" not in wanted and (offer == "senior" or senior_title):
        score -= 48
        warnings.append(f"La fuente indica nivel {level}" if offer == "senior" else "El cargo parece senior/de liderazgo")
    elif offer == "intermedio" and offer not in wanted:
        score -= 15
        warnings.append("Nivel intermedio (Semi Senior): suele pedir experiencia previa")
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
