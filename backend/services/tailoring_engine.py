"""Transformaciones cerradas sobre viñetas planas. Nunca genera afirmaciones."""
from __future__ import annotations
import difflib
import hashlib
import re

from jobhunter.matching import contains, norm
from ..cv_contracts import (Evidence, EvidenceMatch, Suggestion, TailoringPlan, TailoringPreview,
                            validate_suggestion)
from . import cv_parser

NEGATIVE = re.compile(r'\b(no|not|never|sin|without|learning|aprendiendo|aprender|aprendizaje|pendiente|basico|basic|familiar|interes|interest|deseo|wish|want|curso|course)\b')
# Restrict the whole document, not just the spans we will edit. TeX definitions,
# catcodes, math, includes and unknown environments make local reasoning unsafe.
ALLOWED = {'documentclass','usepackage','begin','end','section','item',
           'textbf','textit','emph','name','email','phone','address','title','author','date','url','href','maketitle'}


def structure_blockers(cv):
    masked = cv_parser._mask_comments(cv.source_text)
    reason = 'Generación bloqueada: estructura LaTeX no soportada; revisa y edita una copia manualmente.'
    if cv.partial or cv.uninterpreted:
        return [reason]
    if any(m[1] not in ALLOWED for m in cv_parser.COMMAND.finditer(masked)):
        return [reason]
    if re.search(r'(?<!\\)[$&#^_~]', masked):
        return [reason]
    stack = []
    depth = 0
    for token in re.finditer(r'\\(?:begin|end)\{[^{}]*\}|\\section\*?\s*\{[^{}]*\}|\\.|[{}]', masked):
        value = token[0]
        if value.startswith(('\\begin{','\\end{')):
            if depth:
                return [reason]
            env = value[value.index('{')+1:-1]
            if value.startswith('\\begin'):
                if (env == 'document' and stack) or (env == 'itemize' and stack != ['document']) or env not in {'document','itemize'}:
                    return [reason]
                stack.append(env)
            elif not stack or stack.pop() != env:
                return [reason]
        elif value.startswith('\\section'):
            if stack != ['document'] or depth:
                return [reason]
        elif value == '{':
            depth += 1
        elif value == '}':
            depth -= 1
            if depth < 0:
                return [reason]
    if depth or stack or masked.count('\\begin{document}') != 1 or masked.count('\\end{document}') != 1:
        return [reason]
    # Prevent a document boundary embedded into ignored/trailing content.
    tail = masked.split('\\end{document}',1)[1]
    if tail.strip():
        return [reason]
    return []


def _lists(cv):
    for sec in cv.sections:
        if sec.kind not in {'projects','experience','skills'}:
            continue
        start, end = sec.tex_span
        for match in re.finditer(r'\\begin\{itemize\}(.*?)\\end\{itemize\}', cv.source_text[start:end], re.S):
            body = match[1]
            base = start + match.start(1)
            markers = list(re.finditer(r'\\item\b', body))
            if not markers or body[:markers[0].start()].strip():
                continue
            items = []
            for i,m in enumerate(markers):
                a = base + m.start()
                b = base + (markers[i+1].start() if i+1 < len(markers) else len(body))
                raw = cv.source_text[a:b]
                text = raw[len('\\item'):].strip()
                # Simple standalone prose only. No comments, links, braces,
                # optional labels, macros or contact information can be edited.
                if not text or len(text)>500 or re.search(r'[\\{}%$&#^_~\[\]@]', text) or re.search(r'https?://|\b\d{6,}\b',text):
                    items = []; break
                items.append((a,b,raw,text))
            if items:
                yield sec, items


def _matches(cv, analysis):
    out = []
    for idx,req in enumerate(analysis.requirements):
        if not req.skill:
            continue
        for sec in cv.sections:
            if sec.kind not in {'projects','experience','skills'}:
                continue
            for line in sec.text.splitlines():
                if len(line)>500 or not contains(line,req.skill) or NEGATIVE.search(norm(line)):
                    continue
                # Only use a quote that exists BOTH in extracted text and in the
                # exact source span. Formatting can make this impossible: skip it.
                quote = line.removeprefix('• ').strip()
                if not quote or len(quote)>500:
                    continue
                pos = sec.raw_tex.find(quote)
                if pos < 0:
                    continue
                a = sec.tex_span[0]+pos
                out.append(EvidenceMatch(requirement_index=idx,
                    evidence=Evidence(section_key=sec.key,quote=quote,tex_span=(a,a+len(quote))),
                    rationale='Mención literal documentada. No certifica dominio, años, empleo formal ni cumplimiento de condiciones compuestas.'))
    return out


def make_plan(cv, analysis, lang):
    matches = _matches(cv,analysis)
    suggestions = []
    def add(action, sec, before, after, span, evidence, indices, rationale):
        suggestions.append(Suggestion(id=f's{len(suggestions)+1}',action=action,section_key=sec,
            before=before,after=after,tex_span=span,evidence=evidence,
            requirement_indices=sorted(set(indices)),rationale=rationale))
    matched = {m.requirement_index for m in matches}
    for i,req in enumerate(analysis.requirements):
        if i not in matched:
            add('gap','', '',None,None,[],[i],f'Sin evidencia suficiente: {req.text}. No se añadirá al CV.')
    blockers = structure_blockers(cv)
    if not blockers:
        for sec, items in _lists(cv):
            related = []
            for a,b,raw,text in items:
                hits = [m for m in matches if m.evidence.section_key==sec.key and
                        a <= m.evidence.tex_span[0] < m.evidence.tex_span[1] <= b]
                related.append(hits)
                if not hits:
                    add('remove',sec.key,raw,'',(a,b),[Evidence(section_key=sec.key,quote=text,tex_span=(a+raw.index(text),a+raw.index(text)+len(text)))],[],
                        'Omisión opcional de una viñeta sin coincidencias con el catálogo detectado; puede seguir siendo relevante. El maestro se conserva.')
                else:
                    for skill in dict.fromkeys(analysis.requirements[h.requirement_index].skill for h in hits):
                        # Restrict to one unformatted exact token. No normalization
                        # is used to create edits; offsets are Python characters.
                        token = re.search(r'(?<!\w)'+re.escape(skill)+r'(?!\w)', text, re.I)
                        if token:
                            x = a+raw.index(text)+token.start(); y = x+len(token[0])
                            add('emphasize',sec.key,token[0],r'\textbf{'+token[0]+'}',(x,y),[h.evidence for h in hits],
                                [h.requirement_index for h in hits], 'Destacar un término ya escrito, sin añadir ni reformular afirmaciones.')
            # Stable permutation of complete items, preserving every byte in each.
            order = sorted(range(len(items)),key=lambda i:-len({h.requirement_index for h in related[i]}))
            if order != list(range(len(items))):
                a,b = items[0][0],items[-1][1]
                add('reorder',sec.key,cv.source_text[a:b],''.join(items[i][2] for i in order),(a,b),
                    [h.evidence for hs in related for h in hs], [h.requirement_index for hs in related for h in hs],
                    'Priorizar viñetas completas dentro de la misma lista. Orden estable según menciones documentadas; conserva texto, contexto de sección y fechas.')
    # Coverage is only of bare skill requirements with documented mentions;
    # composite years/languages/degrees are deliberately never counted as met.
    required = [i for i,r in enumerate(analysis.requirements) if r.kind=='required']
    return TailoringPlan(job_id=analysis.job_id,cv_id=cv.source.id,cv_sha256=cv.source.sha256,
                         lang=lang, coverage=len(set(required)&matched)/len(required) if required else 0,
                         suggestions=suggestions,analysis=analysis,matches=matches,blockers=blockers,cv_partial=cv.partial)


def output_bytes(cv, result, original_bytes=None):
    bom = b'\xef\xbb\xbf' if original_bytes and original_bytes.startswith(b'\xef\xbb\xbf') else b''
    return bom+result.encode('utf-8')


def preview(cv, plan, original_bytes=None):
    blockers = list(plan.blockers)
    canonical = make_plan(cv,plan.analysis,plan.lang)
    # Client never sends edits. Still fail closed if a caller or private file
    # changed a quote, span, action or replacement after planning.
    if ([s.model_dump(exclude={'status'}) for s in canonical.suggestions] !=
        [s.model_dump(exclude={'status'}) for s in plan.suggestions]):
        blockers.append('Las propuestas no corresponden a la fuente verificada.')
    edits = []
    for s in plan.suggestions:
        if s.status != 'accepted' or s.action=='gap':
            continue
        blockers.extend(validate_suggestion(s,cv))
        for ev in s.evidence:
            if not ev.tex_span or cv.source_text[slice(*ev.tex_span)] != ev.quote:
                blockers.append('Cita o ubicación de evidencia inválida.')
        if not s.tex_span or cv.source_text[slice(*s.tex_span)] != s.before:
            blockers.append('El fragmento original no corresponde a su ubicación.')
        else:
            edits.append(s)
    edits.sort(key=lambda s:s.tex_span)
    if any(a.tex_span[1]>b.tex_span[0] for a,b in zip(edits,edits[1:])):
        blockers.append('Conflicto: cambios superpuestos. Rechaza una alternativa (por ejemplo reordenar o destacar esa lista).')
    result = cv.source_text
    if not blockers:
        for s in reversed(edits):
            a,b = s.tex_span
            result = result[:a]+s.after+result[b:]
    return TailoringPreview(revision=plan.revision, original=cv.source_text,result=result,
        diff=''.join(difflib.unified_diff(cv.source_text.splitlines(keepends=True),result.splitlines(keepends=True),fromfile='original.tex',tofile='adaptado.tex')),
        sha256=hashlib.sha256(output_bytes(cv,result,original_bytes)).hexdigest(),blockers=list(dict.fromkeys(blockers)),
        applied=[] if blockers else [s.id for s in edits])
