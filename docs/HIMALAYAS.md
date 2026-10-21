# Diseño: conector Himalayas (remotos elegibles desde Chile) — sin implementar

Fecha: 2026-10-21. Requisito previo cumplido: el conector de la API de Get on Board está implementado y evaluado (ver [GETONBRD_API.md](GETONBRD_API.md)). Este documento es solo diseño; **ninguna petición a Himalayas se ha automatizado**.

## Política oficial (himalayas.app/api y himalayas.app/terms, sección API)

| Regla | Texto oficial (resumen fiel) | Consecuencia en JobHunter |
|---|---|---|
| Uso | Permitido en integraciones personales y comerciales. | Uso personal y local: permitido. |
| Atribución | Identificar claramente a Himalayas como fuente, con un enlace visible a la oferta en Himalayas o a himalayas.app. | Etiqueta «Himalayas» y enlace «Ver en Himalayas» en cada tarjeta. |
| Postulación | Todo botón de postular usa el `applicationLink` de la API **sin modificar**; no sustituirlo por el enlace directo del empleador o del ATS. | `url` = `applicationLink` tal cual (la canonicalización solo se usa para el id interno, nunca para mostrar). |
| Redistribución | Mostrar las ofertas solo en sitios o apps propios; no pasarlas a terceros (portales, agregadores, Google Jobs, LinkedIn), ni por feeds ni con datos estructurados `JobPosting`. | No exportarlas a otros servicios. El respaldo JSON es personal (entre los propios PC del usuario). Documentarlo en el panel. |
| Vencimiento | Retirar las ofertas al vencer. Pueden cerrarse antes de `expiryDate`; se recomienda releer a diario y comprobar la oferta antes de mostrarla. | Guardar `expiryDate` y ocultar las vencidas (ver más abajo). |
| Límites | Sin clave: un cupo público compartido, sin cifra publicada. Con clave gratuita: 60 por minuto y 10 000 al día. Las respuestas servidas desde su caché no cuentan. La clave solo debe usarse desde servidores propios. | Presupuesto conservador sin clave. Clave opcional del usuario en `.env` (`JOBHUNTER_HIMALAYAS_KEY`), nunca en el repositorio. |

## Consulta propuesta

`GET https://himalayas.app/jobs/api/search?country=CL&seniority=Entry-level&sort=recent&page=N`

- Con `country`, Himalayas incluye también las ofertas abiertas a todo el mundo (salvo `exclude_worldwide`); no hace falta una segunda consulta.
- Página de 20 como máximo; **tope de 5 páginas** (100 ofertas) por pasada.
- Opcional: una segunda consulta con `employment_type=Intern`, si la primera no las incluye. Comprobarlo con datos reales antes de añadirla.
- Espera mínima propia de **12 h** (lectura «diaria» sugerida por Himalayas), 1 s entre peticiones, 429 sin reintento y respetando `Retry-After`, `PartialFetch` para páginas parciales. Igual que en Get on Board.
- El nivel inicial **sí** se puede filtrar en origen (`seniority=Entry-level`), a diferencia de Get on Board. Aun así, el matching volverá a evaluar los requisitos («Entry-level» no implica compatible).

## Normalización (mismo contrato que el feed y la API de Get on Board)

| Campo | Regla |
|---|---|
| `source` | `Himalayas` |
| `url` | `applicationLink` sin modificar. Identidad = `job_id(applicationLink)`. |
| Atribución | Nueva tabla aditiva `job_attribution(job_id, source_name, source_url, expires_at)` con el enlace a la oferta en Himalayas (`guid` o `companies/{companySlug}/jobs/{slug}`; confirmar con una respuesta real). Respeta la regla de migraciones (solo tablas nuevas). |
| `company`, `title` | `companyName`, `title` en texto plano. |
| `location` | Sin `locationRestrictions` → `Remoto (mundial)`; si incluye Chile → `Remoto (incluye Chile)`; en otro caso, la lista de países, que el matching marcará como fuera de zona. |
| Huso horario | `timezoneRestrictions` lejos de UTC−3/−4 → advertencia en el texto (Chile). |
| Cabecera | `Nivel:` Entry-level → `Junior`; Mid-level → `Semi Senior`; Senior → `Senior`; Manager/Director/Executive → `Expert`. `Jornada:` según `employmentType` (Intern → `Práctica/Internship`). `Categoría:` solo si `parentCategories` se corresponde **sin ambigüedad** con una categoría técnica del feed (la tabla se arma con respuestas reales, no por suposición); si no, sin categoría. `Renta:` `minSalary`–`maxSalary` `currency`/`salaryPeriod`. |
| Cuerpo | `description` (HTML saneado) → texto plano; `excerpt` si falta la descripción. |
| `posted_at` | `pubDate` (epoch) → `YYYY-MM-DD HH:MM:SS UTC`. |

## Vencimiento y frescura

1. Cada pasada actualiza `expires_at` y `last_seen`.
2. El panel oculta las ofertas de Himalayas con `expires_at` vencido o no vistas en las 2 últimas pasadas, **salvo** las que el usuario ya movió de estado (Revisar, Preparada, Postulada). Esas se conservan con el aviso «vencida en Himalayas», por el historial.
3. Antes de abrir una oferta en estado «Nueva», opcionalmente: `GET /jobs/api/companies/:company/jobs/:slug` (200 abierta, 410 cerrada, 404 inexistente), cacheado 10 min. Se hace solo bajo demanda, nunca en bloque.

## Duplicados entre fuentes

Las URL de Himalayas y de Get on Board nunca coinciden. Una misma vacante publicada en ambas aparecería dos veces. Propuesta posterior: detectar candidatos por (empresa normalizada, título normalizado) y mostrarlos agrupados, sin fusionar datos automáticamente.

## Pruebas y evaluación previstas

- Sesión simulada como en `tests/test_getonbrd_api.py`: paginación de 20, tope de páginas, 429, `PartialFetch`, `applicationLink` intacto, atribución visible, ocultar vencidas, ubicación y huso horario.
- Extender `scripts/compare_sources.py`: ofertas nuevas, compatibles por requisitos, restricciones geográficas y de huso, y peticiones por pasada.

## Riesgos

- El cupo sin clave no está publicado: una pasada de 5 peticiones cada 12 h debería ser prudente, pero solo un 429 real lo confirmaría.
- La tabla de categorías depende de la taxonomía real de Himalayas: hay que observarla antes de fijarla.
- Los remotos «mundiales» compiten con candidatos de todo el mundo: para un perfil inicial, el volumen útil puede ser bajo. Medirlo antes de activarlo por defecto.
