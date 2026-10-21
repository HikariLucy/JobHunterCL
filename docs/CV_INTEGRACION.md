# Integración de CV LaTeX (M2) — diseño

> Estado: **solo contratos** (`backend/cv_contracts.py` + pruebas). No hay implementación.

## Objetivo

Usar los dos CV maestros del usuario (español e inglés, en LaTeX) para proponer una versión adaptada a cada oferta **sin inventar conocimientos, títulos ni experiencia**.

## Privacidad

- Los `.tex` se leen desde una ruta local elegida por el usuario y se copian a `data/cv/` (ignorado por git, igual que `*.tex` en todo el repo).
- Los CV **no** se incluyen en el respaldo JSON por defecto.
- Ningún texto del CV sale del equipo salvo que el usuario apruebe explícitamente un proveedor de IA (por defecto: reglas locales deterministas).

## Flujo

```
.tex (es/en) ──import──► CvSource + ParsedCv (secciones con offsets en el .tex)
oferta ──analyze──► JobAnalysis (idioma → CV a usar, requisitos obligatorios/deseables)
ParsedCv + JobAnalysis ──Tailor.plan──► TailoringPlan (sugerencias atómicas con evidencia)
usuario acepta/rechaza cada sugerencia
aceptadas ──render──► .tex adaptado en data/cv/out/ (+ PDF si hay LaTeX instalado)
```

## Reglas anti-invención (validate_suggestion)

1. Toda sugerencia (salvo `gap`) cita evidencia **literal** del CV maestro.
2. `gap` = requisito sin evidencia: se informa al usuario y **nunca** se escribe en el CV.
3. Acciones permitidas: reordenar, enfatizar, reformular con las mismas afirmaciones, quitar. Nunca añadir habilidades, cargos, fechas o títulos.
4. El `.tex` adaptado conserva el preámbulo/plantilla; solo se sustituyen los `tex_span` aceptados.

## Selección de idioma

`JobAnalysis.lang` se decide por el idioma predominante de la oferta; el usuario puede forzarlo. Ofertas remotas internacionales → CV en inglés por defecto.

## Fases propuestas

1. Importar y parsear `.tex` (secciones `\section`, entornos `itemize`), con vista previa.
2. Análisis de requisitos por reglas (reutilizando `matching.norm`/`contains`).
3. Plan de adaptación determinista (reordenar habilidades/experiencias por relevancia).
4. Opcional y con aprobación: LLM para reformulación, siempre pasando por `validate_suggestion`.

API prevista: `POST /api/cv/import`, `GET /api/cv`, `POST /api/jobs/{id}/tailor`, `PATCH /api/tailor/{plan}/suggestions/{id}`, `POST /api/tailor/{plan}/render`.
