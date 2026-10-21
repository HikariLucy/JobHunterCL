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
| `location` | `fully_remote` → `Remoto`. `remote_local` → `Remoto (incluye Chile)`. `hybrid`/`no_remote` → `countries` unidos y modalidad, p. ej. `Chile (híbrido)`. |
| Cabecera de la descripción | `Nivel: … · Jornada: … · Categoría: … · Renta: … USD/mes`, con los nombres del feed («Sin experiencia requerida», «Data Science / Analytics», «Ciberseguridad», «Soporte Técnico»…), que es lo que lee `source_meta()`. |
| Cuerpo | `Requisitos:` (description) + `Funciones:` (functions) + `Deseable:` (desirable), en texto plano. Sin beneficios. |
| `posted_at` | `published_at` (epoch) → `YYYY-MM-DD HH:MM:SS UTC`, como el feed. |

**Activación:** `sources.getonbrd_api` en el perfil/configuración (desactivado por defecto); el feed (`sources.getonbrd`) sigue siendo independiente.
