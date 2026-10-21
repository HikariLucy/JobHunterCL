# Contrato del conector «Get on Board — API pública» (M1.2)

Fecha de verificación: 2026-10-21. Fuente: especificación OpenAPI oficial que carga `getonbrd.com/api-doc.html` (`/doc/openapi.yaml?v=2026-05-08-agent-docs`, OpenAPI 3.0.3, API v0.1.0), más peticiones reales de comprobación (unas 22 en total, con 1 s de pausa).

## Lo que dice la documentación oficial

- **API pública**: abierta, sin autenticación; categorías, empresas, ofertas publicadas y búsqueda. Base `https://www.getonbrd.com/api/v0/`. Hay un sandbox (`sandbox.getonbrd.dev`) con datos falsos.
- **Paginación**: `page` (desde 1) y `per_page` (por defecto y como máximo 120); la respuesta trae `meta.page`, `meta.per_page` y `meta.total_pages`.
- **Idioma**: `lang=en|es|pt`.
- **`expand`**: mecanismo general («Many endpoints support»); los valores dependen del endpoint.
- **Límites de consulta y condiciones**: **la especificación no documenta límites, 429 ni condiciones específicas de uso** (`robots.txt` no restringe nada). El conector aplica sus propios límites (ver más abajo).

### Endpoints públicos de ofertas y sus filtros documentados

| Endpoint | Filtros documentados |
|---|---|
| `GET /categories` | `page`, `per_page` |
| `GET /categories/{category_id}/jobs` | `category_id` (slug), `country_code`, `page`, `per_page` |
| `GET /search/jobs` | `query`, `companies`, `country_code`, `remote`, `featured`, `board_host`, `expand`, `lang`, `page`, `per_page`. **Exige al menos uno** de `query`/`companies`/`featured`/`remote`/`country_code`/`board_host` (si no, 422). |
| `GET /seniorities`, `/modalities`, `/countries`, `/cities` | Datos de referencia |

**No existe un filtro documentado por nivel** («Sin experiencia», «Junior») en ningún endpoint de ofertas. El nivel llega en cada oferta como `seniority.data.id`; se filtra **en local**.

## Comportamiento comprobado (no documentado)

| Comprobación | Resultado |
|---|---|
| Ids de nivel (`/seniorities`) | 1 Sin experiencia, 2 Junior, 3 Semi Senior, 4 Senior, 5 Expert |
| Ids de jornada (`/modalities`) | 1 Full time, 2 Part time, 3 Freelance, 4 Práctica/Internship |
| `country_code=cl` en `categories/programacion/jobs` | 202 de 310: presenciales o híbridas en Chile y remotas restringidas a países que incluyen Chile. **Excluye las 70 totalmente remotas.** No es un filtro de «elegible desde Chile». |
| `search/jobs?remote=true` | Solo `remote_modality = fully_remote`; todas las categorías; 2 páginas. |
| `location_tenants` | Ids numéricos de países **sin endpoint público** (`/countries` usa slugs). No se usan. |
| URL | `links.public_url = /jobs/{id}`; el feed usa `/jobs/{categoría}/{id}`. En las 216 ofertas comunes, `{categoría}` del feed = slug de categoría de la API e `{id}` del feed = `id` de la API. |
| `expand=["company"]` en `categories/{id}/jobs` | Funciona; sin él, la empresa es solo un id. |
| Cabeceras de límite (`RateLimit-*`, `Retry-After`) | Ninguna observada. |

## Diseño del conector

**Qué consulta (elegibilidad desde Chile):**
1. `GET /categories/{slug}/jobs?country_code=cl&expand=["company"]&per_page=120&page=N` para cada categoría técnica: `programacion`, `sysadmin-devops-qa`, `data-science-analytics`, `machine-learning-ai`, `desarrollo-mobile`, `cybersecurity`, `technical-support`.
2. `GET /search/jobs?remote=true&expand=["company"]&per_page=120&page=N`, quedándose en local con las categorías técnicas.

Así no se descargan las ofertas presenciales o restringidas a otros países, que no son elegibles desde Chile. Medido: ~11 peticiones por pasada (feed: 1).

**Protecciones:**
- Máximo 5 páginas por consulta.
- 1 s entre peticiones.
- Espera mínima propia de 60 min con el conector activo (feed: 30 min).
- `User-Agent` identificable.
- 429: se detiene sin reintentar y respeta `Retry-After`.
- Si falla una página después de otras correctas, se guardan las ya obtenidas y se registra el error, en lugar de repetir toda la pasada.
- Deduplicación en memoria entre categorías, entre las dos consultas y con el feed (gana la versión de la API, más completa).

**Normalización (mismo vocabulario que el feed, para que el matching trate igual ambas fuentes):**

| Campo | Regla |
|---|---|
| `url` | `https://www.getonbrd.com/jobs/{slug de categoría}/{id}`: **mismo id interno que el feed**, sin cambiar `canonical()` ni los ids ya guardados. |
| `source` | `Get on Board` (igual que el feed). |
| `company` | `company.data.attributes.name`; si falta, `No indicada`. |
| `location` | `fully_remote` → `Remoto`. `remote_local` → `Remoto (elegibilidad para Chile por confirmar)` (la API no informa sus países). `hybrid`/`no_remote` → `countries` unidos y modalidad, p. ej. `Chile (híbrido)`; sin `countries`, `País no informado` (nunca se supone Chile). *Hasta M1.2 se mostraba «Remoto (incluye Chile)» sin evidencia.* |
| `geo` | Metadatos estructurados (`modality`, `countries` informados), guardados en `job_geo` y usados por `matching.eligibility()`. |
| Cabecera de la descripción | `Nivel: … · Jornada: … · Categoría: … · Renta: … USD/mes`, con los nombres del feed («Sin experiencia requerida», «Data Science / Analytics», «Ciberseguridad», «Soporte Técnico»…), que es lo que lee `source_meta()`. |
| Cuerpo | `Requisitos:` (description) + `Funciones:` (functions) + `Deseable:` (desirable), en texto plano. Sin beneficios. |
| `posted_at` | `published_at` (epoch) → `YYYY-MM-DD HH:MM:SS UTC`, como el feed. |

**Activación:** `sources.getonbrd_api` en el perfil/configuración (desactivado por defecto); el feed (`sources.getonbrd`) sigue siendo independiente.

## Evaluación M1.2 (2026-10-21, datos temporales, perfil por defecto)

> **Snapshot anterior a dos correcciones.** (1) Es previo a `3ef344b`: le faltan 5 de 116 ofertas remotas técnicas («Machine Learning / AI») que el conector corregido sí obtiene. (2) Es previo a M1.3: la ubicación `remote_local` figuraba como «Remoto (incluye Chile)» y contaba como elegible. Las cifras de esta sección son las de M1.2; las de M1.3 están en «Elegibilidad geográfica».

Reproducible: `python scripts/compare_sources.py --fetch DIR` (1 consulta al feed + 1 pasada del conector) y luego `python scripts/compare_sources.py DIR --details`. Etiquetas:
- **Inicial:** nivel declarado Junior o Sin experiencia.
- **Compatible:** técnica, elegible desde las zonas del perfil, no exige más de 2 años y nivel inicial o sin declarar. Una «Junior» que pide 3+ años no cuenta.
- **Dudosa:** Semi Senior técnica, elegible y sin exigir más de 2 años.

| | Feed | API | Solo API | Solo feed | Unión |
|---|---|---|---|---|---|
| Ofertas | 327 | 574 | 395 | 148 | 722 |
| Técnicas | 216 | 574 | 395 | 37 | 611 |
| Nivel inicial | 6 | 40 | 34 | 0 | 40 |
| Compatibles (por requisitos) | 6 | 38 | 32 | 0 | 38 |
| Dudosas | 35 | 177 | 142 | 0 | 177 |
| Iniciales que piden 3+ años | 0 | 2 | 2 | 0 | 2 |
| No elegibles desde las zonas del perfil | 44 | 0 | 0 | 44 | 44 |
| Exigen 5+ / 3–4 / 1–2 años / sin exigencia | 87 / 74 / 27 / 139 | 121 / 130 / 61 / 262 | | | 151 / 170 / 79 / 322 |
| Sobre el umbral (30) | 5 | 38 | 33 | 0 | 38 |
| Precisión (compatible) | 1,0 | 0,816 | 0,788 | — | 0,816 |
| Precisión (compatible o dudosa) | 1,0 | 0,974 | 0,970 | — | 0,974 |
| Recall (compatible) | 0,833 | 0,816 | 0,812 | — | 0,816 |

- **Solapamiento:** 179 ofertas comunes. La URL es idéntica en todas, así que se guardan una sola vez.
- **Peticiones:** feed 1 (1,8 s); API **10** (16,3 s con 1 s de pausa). Todas 200; ninguna cabecera de límite.
- **Lo que aporta la API:** 395 ofertas técnicas que el feed no tenía, todas elegibles desde Chile. Las vacantes compatibles pasan de 6 a 38.
- **Lo que aporta el feed con la API activa:** nada compatible en esta muestra. Sus 148 exclusivas son 111 no técnicas y 37 técnicas no elegibles desde Chile. Se mantiene (1 sola petición) por si cambia el perfil o la cobertura de la API.
- **Las 7 coincidencias de la API que no son «compatibles»** son Semi Senior de soporte N1/N2 y mesa de ayuda («dudosas»), que coinciden con cargos del perfil.
- **Compatibles bajo el umbral (7):** Salesforce, Azure, QA, WordPress… Puntúan 0 porque el perfil de prueba no tiene esas habilidades; es un límite del perfil, no del conector.
- **De punta a punta, sin red** (snapshot cargado por `run_search` con feed + API): 722 filas únicas; la segunda pasada añade 0; el dashboard tarda 1,18 s la primera vez y ~0,05 s después.

### Limitaciones comprobadas

- La primera pasada real tenía un fallo de categorías: con `lang=es`, la búsqueda remota devuelve «Machine Learning / AI». Se perdieron 5 de 116 remotas técnicas. Está corregido (`3ef344b`) con una prueba, pero el snapshot de la tabla es anterior: le faltan esas 5. No se repitió la pasada para respetar la espera mínima de 60 min.
- Un solo día y una sola fuente. La etiqueta usa el nivel y la categoría que publica la propia fuente.
- `country_code=cl` excluye las totalmente remotas (se cubren con `remote=true`). Los países de `remote_local` (`location_tenants`) no tienen endpoint público: desde M1.3 la ubicación se muestra como «Remoto (elegibilidad para Chile por confirmar)» y no cuenta como elegible confirmada.
- La API no documenta límites de consulta: la espera mínima de 60 min es una decisión propia, no un requisito publicado.

## Elegibilidad geográfica (M1.3)

**Problema (auditoría):**
- «remote/remoto» del perfil se trataba como lugar, así que **toda oferta remota sumaba +8** de ubicación.
- `remote_local` se mostraba como «Remoto (incluye Chile)» sin que la API informara los países.
- Una híbrida sin `countries` se etiquetaba «Chile» por haber consultado con `country_code=cl`.
- «(híbrido)» impedía detectar ubicaciones fuera de zona.
- Todo se decidía por el texto visible.

**Clasificación** (`matching.eligibility`, con evidencia y origen):

| Estado | Cuándo | Efecto |
|---|---|---|
| `compatible` | Países informados que incluyen una zona del perfil (API, o lista explícita del feed); `fully_remote` (los metadatos no admiten restricción de país); restricción de residencia compatible en el texto; lista de lugares con una zona. | +8 (si hay afinidad); insignia «Elegible». |
| `desconocida` | `remote_local` sin países; «Remoto» solo por texto; ubicación no indicada; híbrida sin país; perfil sin zonas geográficas. | Sin bonificación ni penalización; aviso «Elegibilidad geográfica por confirmar»; **sigue visible** (filtro «Por confirmar»). |
| `incompatible` | Países o lugares fuera de las zonas; residencia exigida en otro lugar; «US only». | −20 (−40 en «US only»); insignia «Fuera de tus zonas». |

**Orden de prioridad:**
1. Restricción explícita en el texto.
2. Metadatos estructurados (`job_geo`).
3. Texto de ubicación.

«remote/remoto» en el perfil es una **modalidad deseada, no una zona**. Si el feed lista los países de una oferta que la API marca `remote_local`, esa lista se conserva como evidencia (`API + feed (lista de países)`).

**Medición antes/después, sobre el mismo snapshot almacenado** (sin consultas nuevas). Para el «después», `compare_sources.legacy_geo` reconstruye `geo` desde las etiquetas que escribía el conector:
- «Remoto» = `fully_remote`.
- «Remoto (incluye …)» = `remote_local` sin países.
- «X (híbrido/presencial)» = países X. En la descarga cruda las 670 ofertas traían `countries`, así que ninguna «Chile» era supuesta.

| Unión feed + API (722) | Antes (M1.2) | Después (M1.3) |
|---|---|---|
| Elegibilidad compatible / desconocida / incompatible | (no existía: 678 «elegibles» / 44 no) | 534 / 144 / 44 |
| `remote_local` de la API (128) | 128 «incluye Chile» | 67 confirmadas por la lista del feed / 61 por confirmar |
| Compatibles confirmadas (por requisitos) | 38 | 36 |
| Pendientes de verificar | — | 2 |
| Sobre el umbral | 38 | 38 (37 elegibilidad confirmada + 1 por confirmar) |
| Precisión (compatible confirmada) | 0,816 | 0,789 |
| Precisión (confirmada o pendiente) | — | 0,816 |
| Recall (compatible confirmada) | 0,816 | 0,833 |

**Las 38 oportunidades anteriores:** ninguna sale ni entra en la lista sobre el umbral.
- **37 conservan elegibilidad confirmada:** 32 por los países que informa la API, 4 por la modalidad `fully_remote` y 1 por la lista explícita de países del feed (antes «Remoto (incluye Chile)» sin evidencia).
- **1 pasa a revisión:** `remote_local` sin países en ninguna fuente. Baja de 40 a 32 puntos al perder la bonificación y sigue visible.

De punta a punta, sin red (snapshot cargado con `run_search`): 574 filas en `job_geo`, 61 ubicaciones «por confirmar», 0 «incluye Chile»; los filtros `?eligibility=` devuelven 534 / 144 / 44.

**Decisión a revisar:** `fully_remote` cuenta como compatible porque los metadatos de Get on Board no admiten restricción de país para esa modalidad. Si una oferta así exige residencia en el texto, la restricción explícita prevalece. Si se prefiere más prudencia, bastaría con pasarla a «desconocida» en `eligibility()`: afectaría a 4 de las 38.
