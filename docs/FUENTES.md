# Fuentes de empleo de nivel inicial para Chile — propuesta M1

Fecha: 2026-10-21. **Estado (M1.2):** la API de Get on Board está implementada y evaluada ([GETONBRD_API.md](GETONBRD_API.md)); Himalayas, solo diseñada ([HIMALAYAS.md](HIMALAYAS.md)); el resto, sin implementar. Reglas del proyecto: solo APIs o feeds públicos y permitidos, un `User-Agent` identificable, esperas mínimas por fuente, sin scraping de sitios que lo restringen y sin postulaciones automáticas.

Cómo se verificó: documentación pública de cada servicio, `robots.txt` y, para Get on Board, dos peticiones mínimas a la API pública. Un `robots.txt` permisivo **no** equivale a autorización; mandan los términos de uso, que deben revisarse antes de implementar cada conector.

## A. APIs públicas sin autenticación — candidatas a conector

| Prioridad | Fuente | Qué aporta para nivel inicial | Evidencia | Condiciones / riesgos |
|---|---|---|---|---|
| 1 | **Get on Board API v0** (`/api/v0/...`) | Misma fuente que el feed actual, pero con datos estructurados: niveles «Sin experiencia» (id 1) y «Junior» (id 2), categorías y empresas. Permitiría pedir solo ofertas iniciales en lugar de las ~326 más recientes, de las que solo 16 eran de nivel inicial. | Su ayuda dice que la API pública no requiere configuración. `GET /api/v0/seniorities` respondió 200 sin autenticación. `robots.txt` sin restricciones. | Revisar en la referencia oficial (`getonbrd.com/api-doc.html`) los parámetros de búsqueda y filtro y los límites de uso. Mantener la espera mínima y la caché. |
| 2 | **Himalayas** (`himalayas.app/jobs/api/search`) | Remoto global con filtros `seniority=Entry-level` y `country`. | Página oficial de la API: gratuita y sin clave (con un cupo público compartido). | Términos: usar el enlace de postulación sin modificar, mostrar Himalayas como fuente, no redistribuir y retirar las ofertas vencidas. Encaja con un uso personal y local. |
| 3 | **ATS por empresa**: Ashby (`api.ashbyhq.com/posting-api/job-board/{org}`), Workable (widget público), SmartRecruiters (`/v1/companies/{id}/postings`) | Ofertas directas de empresas que el usuario elija; amplía lo que ya existe para Greenhouse y Lever. | Fuentes secundarias (directorios de APIs y artículos técnicos) los describen como públicos y sin clave. | **Falta confirmar la documentación oficial de cada uno.** SmartRecruiters solo los ofrece en algunos planes. Hay que conocer el identificador de la empresa; no existe forma de descubrirlas. |
| 4 | **Jobicy** (`jobicy.com/api/v2/remote-jobs`) | Remoto con filtros `geo`, `industry` y `tag`. | Repositorio oficial de la API. | Como máximo una sincronización por hora; conservar Jobicy como fuente y su URL canónica. Hay que comprobar si existe un filtro para LATAM (`?get=locations`). Poco contenido inicial esperado. |
| — | Remotive (ya existe) | Remoto. | — | Máximo 4 consultas al día (espera de 6 h 30 min ya aplicada). |

## B. Fuentes públicas sin API: requieren acuerdo o uso manual

| Fuente | Interés para nivel inicial | Estado | Propuesta |
|---|---|---|---|
| **Bolsa Nacional de Empleo** (bne.cl, SENCE / Ministerio del Trabajo) | Alta: es la mayor bolsa pública, con ofertas gestionadas por las OMIL. | No se encontró una API oficial; solo scrapers de terceros no oficiales. | No automatizar. Consultar a SENCE si existe API o datos abiertos (datos.gob.cl, solicitud de transparencia). Mientras tanto, añadir un enlace en el panel. |
| **Empleos Públicos** (Servicio Civil) | Media/alta: convocatorias del Estado. | `robots.txt` y el sitio devolvieron 403 a un cliente automatizado. Sin API pública encontrada. | Solo enlace manual; preguntar al Servicio Civil por un feed. |
| **Prácticas para Chile** (Servicio Civil) | Muy alta para estudiantes y egresados: prácticas en ministerios y servicios. | Sin API pública encontrada. | Enlace manual y recordatorio de los períodos de convocatoria. |

## C. Portales comerciales: no automatizar sin autorización expresa

| Portal | Señal observada | Decisión |
|---|---|---|
| LinkedIn, Indeed | `robots.txt` prohíbe las rutas de empleos y de búsqueda. Sus términos prohíben la extracción automatizada. | Excluidos. Como mucho, enlaces de búsqueda que el usuario abre a mano. |
| Computrabajo | 403 a un cliente automatizado. | Excluido. |
| ChileTrabajos | `robots.txt` con `Disallow: /`. | Excluido. |
| Laborum, Trabajando.com | Sin API pública encontrada; `robots.txt` parcial. | No automatizar sin un acuerdo. Revisar sus términos solo si ofrecen API de socios. |
| Portales de empleabilidad universitarios | Requieren inicio de sesión. | Uso manual. |

Una alternativa legítima para los portales C, a evaluar más adelante y con consentimiento explícito: importar las **alertas por correo** que el propio usuario recibe. Requiere acceso a su correo y una política de privacidad; queda fuera de M1.

## Orden recomendado

1. API v0 de Get on Board con filtro de nivel inicial y categorías técnicas, reutilizando `source_meta`, la espera mínima y el registro de búsquedas. Medir con `scripts/eval_matching.py` cuántas ofertas iniciales aporta frente al feed.
2. Himalayas (`Entry-level`, `country=CL`/LATAM), mostrando la atribución en la tarjeta.
3. Conectores Ashby y Workable por empresa, configurables como Greenhouse y Lever.
4. Enlaces manuales a BNE, Empleos Públicos y Prácticas para Chile en el panel.
