"""Ranking transparente, sin inventar competencias ni condiciones de elegibilidad."""
from __future__ import annotations
import re
import unicodedata
from functools import lru_cache


# Guiones tipográficos -> "-" antes de quitar lo no ASCII: si no, «1–3 años» se leía «13 años».
_DASHES = str.maketrans(dict.fromkeys("‐‑‒–—―−", "-"))


@lru_cache(maxsize=512)  # contains() vuelve a normalizar el mismo texto por cada término
def norm(s: str) -> str:
    text = str(s).lower().translate(_DASHES)
    return " ".join(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().split())


# «N años», «N+ years», «+N años», «N-M años», «N a M años», «N o más años».
# Se exige contexto de experiencia para no confundir la edad («mayor de 18 años»)
# ni la antigüedad de la empresa («más de 12 años creciendo»).
_YEARS = re.compile(r"(\+\s*)?\b(\d{1,2})(?:\s*(?:-|a|to)\s*(\d{1,2}))?\s*(\+|o mas)?\s*(?:anos|years?|yrs)\b")
_YEARS_BEFORE = re.compile(r"(?:minimo|al menos|at least|requisito|requirement|over|more than)\W*(?:de\W*)?$")
_YEARS_AFTER = re.compile(r"^\W*(?:\w+\W+){0,6}?(?:experiencia|experience|exp)\b")
_AGE = re.compile(r"(?:mayor(?:es)? de|edad|age[sd]?)\W*$")
_AGE_AFTER = re.compile(r"^\W*(?:de edad|old|of age)\b")


def required_years(text: str) -> int | None:
    """Años de experiencia exigidos en un texto normalizado: el menor de cada rango y
    el mayor entre menciones. None si no hay una exigencia clara."""
    found = []
    for m in _YEARS.finditer(text):
        before, after = text[max(0, m.start() - 25):m.start()], text[m.end():m.end() + 60]
        if _AGE.search(before) or _AGE_AFTER.search(after):
            continue
        years = int(m.group(2))
        if years > 15:  # «más de 50 años de experiencia» describe a la empresa, no al cargo
            continue
        if m.group(1) or m.group(4) or _YEARS_BEFORE.search(before) or _YEARS_AFTER.search(after):
            found.append(years)
    return max(found) if found else None


@lru_cache(maxsize=1024)
def _phrase_re(phrase: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)")


def contains(text: str, phrase: str) -> bool:
    phrase = norm(phrase)
    if not phrase:
        return False
    text = norm(text)
    # Descarte por subcadena (rápido) antes de comprobar límites de palabra.
    return phrase in text and _phrase_re(phrase).search(text) is not None


# Habilidades cuyo término aparece en expresiones de otro oficio («redes sociales» no
# son redes de datos; «soporte al cliente» no es soporte TI). Se ignoran esos usos.
SKILL_FALSE_FRIENDS = {
    "redes": ("redes sociales", "redes neuronales"),
    "soporte": ("soporte al cliente", "soporte a clientes", "soporte a campanas", "soporte comercial"),
}


@lru_cache(maxsize=256)
def _without_false_friends(text: str, key: str) -> str:
    for phrase in SKILL_FALSE_FRIENDS[key]:
        text = _phrase_re(phrase).sub(" ", text)
    return text


def has_skill(text: str, skill: str) -> bool:
    """Como contains(), pero sin contar los usos de SKILL_FALSE_FRIENDS."""
    key = norm(skill)
    if key in SKILL_FALSE_FRIENDS:
        text = _without_false_friends(norm(text), key)
    return contains(text, key)


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


LOCATION_SYNONYMS = {
    "latam": ("latin america", "latinoamerica", "america latina", "latam"),
    "remote": ("remote", "remoto", "anywhere"),
    "remoto": ("remoto", "remote", "anywhere"),
}
REMOTE_WORDS = ("remoto", "remote", "anywhere", "teletrabajo", "hibrido", "hybrid")
_UNKNOWN_LOCATION = ("no indicada", "verificar en oferta")
# Restricción explícita y estrecha («solo residentes en X», «must be based in X»);
# no se usa «based in» suelto porque suele describir a la empresa.
_RESTRICTION = re.compile(
    r"(?<!no )(?:(?:solo|solamente|unicamente|exclusivamente|only)\s+(?:para\s+)?"
    r"(?:residentes|residents|candidatos|candidates|personas|applicants)\s+(?:que\s+(?:residan|vivan)\s+)?"
    r"(?:en|in|de|of|from|based in|located in)"
    r"|(?:must|debes?|deberas|es necesario)\s+(?:be\s+)?(?:based|located|reside|live|residir|vivir|estar ubicad[oa])\s+(?:in|en))"
    r"\s+([a-z][a-z ,]{2,60})")


def location_terms(profile: dict) -> list[str]:
    terms = []
    for raw in profile.get("locations", []):
        key = norm(raw)
        if key:
            terms.extend(LOCATION_SYNONYMS.get(key, (key,)))
    return list(dict.fromkeys(terms))


# Solo indican trabajo a distancia, no un lugar. «Híbrido»/«presencial» sí van con lugares.
REMOTE_ONLY_WORDS = ("remoto", "remote", "anywhere", "teletrabajo")
_MODALITY_SUFFIX = re.compile(r"\((?:hibrido|hybrid|presencial|on-site|onsite)\)")


def place_terms(profile: dict) -> list[str]:
    """Zonas geográficas del perfil; «remote/remoto» es una modalidad deseada, no un lugar."""
    return [t for t in location_terms(profile) if t not in REMOTE_ONLY_WORDS]


def is_place_list(location: str) -> bool:
    """Ubicación con lugares concretos (no remota ni desconocida); admite «(híbrido)»."""
    location = _MODALITY_SUFFIX.sub(" ", norm(location))
    return bool(location.strip()) and not any(contains(location, w) for w in REMOTE_ONLY_WORDS + _UNKNOWN_LOCATION)


def residency_mentions(text: str) -> list[str]:
    """Lugares de residencia exigidos explícitamente en el texto («solo residentes en X»…)."""
    return [m.group(1).split(" para ")[0].strip(" ,")[:60] for m in _RESTRICTION.finditer(text)]


def residency_restriction(text: str, loc_terms: list[str]) -> str | None:
    """Lugar exigido para residir si es ajeno a las zonas del perfil; None si no hay o es compatible."""
    for place in residency_mentions(text):
        if not any(contains(place, x) for x in loc_terms):
            return place
    return None


COMPATIBLE, UNKNOWN, INCOMPATIBLE = "compatible", "desconocida", "incompatible"
_US_ONLY = ("united states only", "us only", "usa only", "canada only")


def eligibility(job: dict, profile: dict) -> dict:
    """Elegibilidad geográfica de la oferta para las zonas del perfil.

    Devuelve {"status": compatible|desconocida|incompatible, "evidence": texto, "basis": origen}.
    Prioridad: restricción explícita en el texto > metadatos estructurados de la fuente
    (`job["geo"]`: modality, countries) > texto de ubicación. Sin evidencia suficiente el
    resultado es «desconocida»: la oferta sigue visible para revisarla a mano.
    """
    zones = place_terms(profile)
    if not zones:
        return {"status": UNKNOWN, "evidence": "el perfil no define zonas geográficas", "basis": "perfil"}
    location = norm(job.get("location", ""))
    body = norm(job.get("description", ""))
    shown = str(job.get("location", ""))[:80]
    if any(contains(location, x) for x in _US_ONLY):
        return {"status": INCOMPATIBLE, "evidence": f"ubicación: {shown}", "basis": "texto"}
    mentions = residency_mentions(body)
    if any(not any(contains(p, z) for z in zones) for p in mentions):
        place = next(p for p in mentions if not any(contains(p, z) for z in zones))
        return {"status": INCOMPATIBLE, "evidence": f"exige residir en {place}", "basis": "texto"}
    geo = job.get("geo") or {}
    countries = [str(c) for c in geo.get("countries") or [] if str(c).strip()]
    if countries:
        listed = ", ".join(countries)[:80]
        ok = any(contains(norm(c), z) for c in countries for z in zones)
        return {"status": COMPATIBLE if ok else INCOMPATIBLE, "evidence": f"países informados: {listed}",
                "basis": geo.get("evidence") or "metadatos"}
    if geo.get("modality") == "fully_remote":
        return {"status": COMPATIBLE, "evidence": "remoto sin restricción de país", "basis": "metadatos"}
    if geo.get("modality"):
        return {"status": UNKNOWN, "evidence": "remoto restringido a países que la fuente no informa"
                if geo["modality"] == "remote_local" else "la fuente no informa el país", "basis": "metadatos"}
    if mentions:  # todas las menciones son compatibles (p. ej. «must be based in Latin America»)
        return {"status": COMPATIBLE, "evidence": f"exige residir en {mentions[0]}", "basis": "texto"}
    if is_place_list(location):
        ok = any(contains(location, z) for z in zones)
        return {"status": COMPATIBLE if ok else INCOMPATIBLE, "evidence": f"ubicación: {shown}", "basis": "texto"}
    return {"status": UNKNOWN, "evidence": "ubicación no indicada" if not location.strip()
            or any(contains(location, w) for w in _UNKNOWN_LOCATION)
            else f"«{shown}» sin países informados", "basis": "texto"}


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
    present = [s for s in skills if has_skill(all_text, s)]
    if present:
        score += min(42, len(present) * 7)
        positive.append("Coincidencias técnicas: " + ", ".join(present[:8]))
    # Nivel y ubicación solo suman si la oferta tiene algo del perfil (cargo o habilidad):
    # si no, un puesto junior de ventas «remoto» acumulaba 26 puntos sin afinidad alguna.
    affinity = bool(positive)
    wanted = wanted_levels(profile)
    level = source_meta(job.get("description", "")).get("level")
    offer = LEVEL_CLASS.get(level)
    if any(contains(title, k) for k in ("junior", "jr", "trainee", "practica", "entry level", "sin experiencia")):
        offer = offer or "inicial"
    senior_title = any(contains(title, k) for k in ("senior", "sr", "staff", "principal", "lead", "jefe", "gerente", "manager", "architect"))
    if offer in wanted and affinity:
        score += LEVEL_BONUS[offer]
        positive.append("Nivel inicial indicado" if offer == "inicial" else f"Nivel buscado: {level or offer}")
    level_penalty = 0
    if "senior" not in wanted and (offer == "senior" or (offer is None and senior_title)):
        level_penalty = 48
        warnings.append(f"La fuente indica nivel {level}" if offer == "senior" else "El cargo parece senior/de liderazgo")
    elif offer == "intermedio" and offer not in wanted:
        level_penalty = 15
        warnings.append("Nivel intermedio (Semi Senior): suele pedir experiencia previa")
    years_penalty = 0
    years = required_years(all_text)
    if years is not None and years >= 5 and "senior" not in wanted:
        years_penalty = 24
        warnings.append("Puede exigir 5 o más años de experiencia")
    elif years is not None and years >= 3 and wanted == {"inicial"}:
        years_penalty = 12
        warnings.append(f"Pide {years} años de experiencia")
    score -= max(level_penalty, years_penalty)
    # Ubicación: solo la elegibilidad confirmada suma; la desconocida avisa sin penalizar.
    elig = eligibility(job, profile)
    if elig["status"] == COMPATIBLE:
        if affinity:
            score += 8
            positive.append("Ubicación compatible: " + elig["evidence"])
    elif elig["status"] == INCOMPATIBLE:
        us_only = any(contains(location, x) for x in _US_ONLY)
        score -= 40 if us_only else 20
        warnings.append(("Posible restricción de residencia: " if us_only or elig["evidence"].startswith("exige")
                         else "Ubicación fuera de tus zonas de interés: ") + elig["evidence"])
    elif place_terms(profile):
        warnings.append("Elegibilidad geográfica por confirmar: " + elig["evidence"])
    if not location:
        warnings.append("Ubicación sin confirmar")
    if not positive:
        warnings.append("No se detectaron coincidencias claras con el perfil")
    from .preferences import preference_effects
    delta, pref_positive, pref_warnings = preference_effects(job, profile, affinity)
    score += delta
    positive.extend(pref_positive)
    warnings.extend(pref_warnings)
    return max(0, min(100, score)), positive, warnings
