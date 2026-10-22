"""Explicaciones conservadoras de preferencias; no certifican datos del usuario.

El texto libre solo se clasifica con marcadores explícitos. Sin evidencia suficiente
se solicita revisión, sin filtros duros ni conversiones monetarias implícitas.
"""
from __future__ import annotations
import re

from .matching import contains, has_skill, norm

_MODALITIES = {'remoto': ('remoto', 'remote', 'fully remote', 'teletrabajo'),
               'hibrido': ('hibrido', 'hybrid'), 'presencial': ('presencial', 'onsite', 'on-site')}
_GEO_MODES = {'fully_remote':'remoto', 'remote_local':'remoto', 'hybrid':'hibrido', 'onsite':'presencial', 'no_remote':'presencial'}
_LANGUAGE = re.compile(r'\b(ingles|english|espanol|spanish|portugues|portuguese|frances|french)\s*[:\-]?\s*(a[12]|b[12]|c[12]|basico|intermedio|avanzado|fluido|nativo|basic|intermediate|advanced|fluent|native)\b|\b(fluent|native|advanced)\s+(english|spanish|portuguese|french)\b')
_LANG_NAMES = {'ingles':'en','english':'en','espanol':'es','spanish':'es','portugues':'pt','portuguese':'pt','frances':'fr','french':'fr'}
# Descriptores libres no equivalen a certificados CEFR; solo se compara CEFR con CEFR.
_CEFR = {'a1':1,'a2':2,'b1':3,'b2':4,'c1':5,'c2':6}
_SALARY = re.compile(r'\b(?:renta|salary|salario|remuneracion):\s*(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?)\s*)?(CLP|USD|EUR)/(mes|month|ano|year)\b', re.I)
_CLAUSE = re.compile(r'(obligatori[oa]s?|requerid[oa]s?|required|must have|deseables?|nice to have|optional)\s*:\s*([^\n.;]+)', re.I)


def _modality(text: str) -> set[str]:
    value = norm(text)
    if re.search(r'\b(no|not|sin|without|temporalmente|temporarily|temporary)\b', value):
        return set()
    return {key for key, words in _MODALITIES.items() if any(contains(text, word) for word in words)}


def preference_effects(job: dict, profile: dict, affinity: bool) -> tuple[int, list[str], list[str]]:
    positive, warnings = [], []
    delta = 0
    prefs = profile.get('preferences') or {}
    raw = str(job.get('description') or '')
    body = norm(raw)
    wanted = set().union(*(_modality(str(m)) for m in prefs.get('modalities') or []))
    geo_mode = (job.get('geo') or {}).get('modality')
    mode = ({_GEO_MODES[geo_mode]} if geo_mode in _GEO_MODES else set()) if geo_mode else _modality(str(job.get('location') or ''))
    # Evitar inferir «remoto» de una descripción de la empresa. Solo un marcador de modalidad.
    if not mode and not geo_mode:
        explicit = re.search(r'\b(?:modalidad|work mode)\s*:\s*([^.;\n]+)', body)
        if explicit:
            mode = _modality(explicit.group(1))
    if wanted:
        if not mode or len(mode) != 1:
            warnings.append('Modalidad por confirmar: no hay una modalidad única informada')
        elif wanted & mode:
            if affinity:
                delta += 6
                positive.append('Modalidad compatible: ' + next(iter(mode)))
        else:
            delta -= 8
            warnings.append('Modalidad distinta de la deseada: ' + next(iter(mode)))
    for match in _LANGUAGE.finditer(body):
        name, required = (match.group(1), match.group(2)) if match.group(1) else (match.group(4), match.group(3))
        # «deseable», negaciones y frases ambiguas se revisan; nunca se prometen como cumplidas.
        left = max((body.rfind(sep, 0, match.start()) for sep in ('.', ';', '\n', '·')), default=-1) + 1
        right = min((pos for sep in ('.', ';', '\n', '·') if (pos := body.find(sep, match.end())) >= 0), default=len(body))
        context = body[left:right]
        optional = any(contains(context, word) for word in ('deseable', 'optional', 'nice to have', 'no requiere', 'not required', 'no es obligatorio'))
        required_marker = any(contains(context, word) for word in ('required', 'requirement', 'requisito', 'requisitos', 'obligatorio', 'obligatoria', 'se requiere', 'necesario', 'must', 'essential', 'excluyente'))
        if not optional and not required_marker:
            warnings.append(f'Idioma mencionado por confirmar: {name} {required}; no se clasifica como requisito')
            continue
        label = 'Idioma deseable' if optional else 'Idioma requerido'
        language = next((item for item in profile.get('languages') or [] if _LANG_NAMES.get(norm(item.get('name', ''))) == _LANG_NAMES[name]), None)
        if not language:
            warnings.append(f'{label}: {name} {required}; sin declaración, por confirmar')
            continue
        declared = norm(language.get('level', ''))
        if declared in _CEFR and required in _CEFR:
            if _CEFR[declared] < _CEFR[required]:
                warnings.append(f'{label}: {name} {required}; nivel declarado {declared} inferior')
            else:
                positive.append(f'Idioma declarado: {name} {declared} frente a {required}; requiere revisión')
        else:
            warnings.append(f'{label}: {name} {required}; comparar manualmente con {declared or "nivel por confirmar"}')
        if not str(language.get('evidence') or '').strip():
            warnings.append(f'{name}: nivel declarado sin evidencia aportada; no acredita certificación')
        else:
            warnings.append(f'{name}: evidencia aportada por el usuario, pendiente de verificar')
    minimum = prefs.get('salary_min')
    if minimum is not None:
        salary = _SALARY.search(body)
        if not salary:
            warnings.append('Remuneración por confirmar: falta rango con moneda y periodicidad explícitas')
        else:
            lo, hi = float(salary.group(1)), float(salary.group(2) or salary.group(1))
            currency = salary.group(3).upper()
            period = 'mensual' if salary.group(4).lower() in ('mes', 'month') else 'anual'
            if lo > hi or currency != str(prefs.get('salary_currency', 'CLP')).upper() or period != prefs.get('salary_period', 'mensual'):
                warnings.append('Remuneración: rangos, monedas o periodicidades incomparables; revisar sin conversión')
            elif hi < minimum:
                warnings.append('Remuneración publicada inferior al mínimo esperado; revisar condiciones brutas/netas')
            elif lo < minimum:
                warnings.append('Remuneración: el rango se superpone con el mínimo esperado; confirmar monto y condiciones')
            else:
                positive.append('Remuneración publicada alcanza el mínimo declarado; confirmar condiciones brutas/netas')
    skills = profile.get('skills') or []
    learning = profile.get('learning_skills') or []
    evidence = {norm(x.get('skill', '')): x.get('evidence') for x in profile.get('skill_evidence') or [] if str(x.get('evidence') or '').strip()}
    for skill in skills:
        if has_skill(body, skill) and norm(skill) in evidence:
            positive.append(f'Evidencia aportada para {skill}: {evidence[norm(skill)][:160]} (sin verificación externa)')
    for skill in learning:
        if has_skill(body, skill):
            warnings.append(f'{skill}: en aprendizaje; no se considera dominio demostrado')
    for clause in _CLAUSE.finditer(raw):
        kind = norm(clause.group(1))
        label = 'Deseable' if kind.startswith(('deseable', 'nice', 'optional')) else 'Obligatorio'
        fragment = clause.group(2).strip()[:240]
        declared = [s for s in skills if has_skill(norm(fragment), s)]
        warnings.append(f'{label} por revisar: {fragment}' + (f' · coincidencias declaradas: {", ".join(declared)}; confirmar alcance y evidencia' if declared else ' · sin coincidencia declarada; brecha por confirmar'))
    return delta, positive, list(dict.fromkeys(warnings))
