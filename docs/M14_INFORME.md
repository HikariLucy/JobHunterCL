# Informe verificable M1.4 — 2026-10-21

## Alcance y estado real

Continuación desde `614e394` en `feat/local-first-fastapi-react`, árbol inicialmente limpio. Implementación local de onboarding, persistencia, reglas conservadoras de matching, pruebas y documentos. No se considera validada en Windows esta revisión ni se presume aceptación visual del usuario. No se hizo push ni merge. Streamlit y el CSS aprobado permanecen intactos. No se leyeron ni modificaron perfiles, bases, CV o credenciales personales: todos los arranques usaron `/tmp` y todas las pruebas de almacenamiento usan fixtures/directorios temporales. Se comprobó que `data/profile.json`, `data/jobs.sqlite3` y `cv/*.tex` continúan ignorados por Git.

## Auditoría de los tres commits de referencia

| Commit | Lo que aporta | Hallazgos al continuar |
|---|---|---|
| `24e08f6` | Temporal en mismo directorio, fsync, replace, .bak, detección de JSON corrupto y pruebas de fallos | Validaba objeto JSON, pero no el contrato anidado; un objeto inválido podía rotar a .bak. Refería docs/PERFIL.md todavía inexistente. |
| `8040cb5` | GET /api/profile/status y campos veraces opcionales del backend | Sin wizard ni tipos/campos React correspondientes; claves heredadas omitidas podían perderse. Configuración tenía el mismo problema para fuentes. |
| `614e394` | Especificación completa M1.4 | Solo documento: no demuestra implementación del hito. |

Se leyeron completos la especificación y README, ROADMAP, ARQUITECTURA, MIGRACION, CV_INTEGRACION, contratos, perfil, matching, API y sus pruebas. El plan/registro está en `docs/superpowers/plans/2026-10-21-m14.md`.

## Contrato, persistencia y recuperación

`jobhunter/profile_schema.py` es ahora el contrato único de perfil, reexportado por `backend/schemas.py`. El perfil permanece en JSON sin migración SQLite. Campos añadidos anteriormente y ahora editables: áreas, tipo de experiencia, formación con estado, habilidades en aprendizaje, evidencia por habilidad/idioma y periodicidad de remuneración; son opcionales y aceptan perfiles anteriores.

GET /api/profile/status informa existencia/legibilidad/error/copia y plantilla nueva; GET/PUT /api/profile lee/guarda; GET/PUT /api/config sigue administrando fuentes/frecuencia. El frontend ya consume status y el perfil, sin consultar portales durante el asistente. API Get on Board activa solo en la plantilla de perfil nuevo; no se alteran las fuentes de perfiles anteriores.

La validación/serialización precede cualquier escritura. Temporales en el mismo directorio, flush/fsync y os.replace conservan integridad del destino. .bak conserva la versión válida anterior; no rota sobre ella un perfil con tipos o estados anidados inválidos. Un fallo de fsync/reemplazo no devuelve éxito. La carga corrupta no escribe ni abre el asistente; la recuperación es manual y se explica en `docs/PERFIL.md`. Un guardado explícito conserva aparte la copia corrupta.

Las claves heredadas superiores y de fuentes se conservan desde el servidor aunque el cliente las omita; PUT de perfil/configuración no agrega claves desconocidas nuevas. Pruebas específicas: `test_failed_replace_preserves_profile_and_cleans_temp`, `test_failed_temp_write_preserves_profile_and_backup`, `test_nested_corruption_cannot_replace_good_backup`, `test_omitted_legacy_fields_survive_save`, `test_config_preserves_legacy_sources_without_adding_arbitrary_fields` y compatibilidad del MVP/BOM Windows. No se garantiza recuperación ante fallos físicos de disco.

## Onboarding e interfaz

Siete pasos opcionales en las tarjetas existentes: objetivos, experiencia/formación, habilidades, idiomas, preferencias, fuentes/límites y resumen editable. Primera ejecución abre Mi perfil; los perfiles existentes no son forzados. «Abrir asistente» reutiliza el perfil guardado. Cancelar no escribe. Anterior/Siguiente conserva el borrador en memoria. Un error de API conserva datos y muestra error sin éxito falso. Tras guardar, se puede continuar editando; recargar usa el perfil persistido. Salir de la página antes de guardar descarta el borrador.

Formación en curso y proyectos conservan su tipo; no se inventan títulos ni años laborales. Evidencia es texto aportado por el usuario, sin certificación implícita. Las notas de residencia se conservan para revisión manual; no se interpretan como permiso migratorio. No se exige CV ni información sensible.

Pruebas React cubren pasos/omisión/resumen, retroceso, cancelación de perfil existente, guardado, error con borrador retenido, perfil corrupto, campos veraces y mensajes de matching. El CSS general, navegación y resto de páginas se conservan.

Chromium real mediante DevTools, con contexto aislado y datos `/tmp/jobhunter-m14-browser`: apertura desde `/` redirigió al asistente; entrada de cargo con Enter; recorrido de los siete pasos; foco en encabezado de cada paso; guardado por Enter y recarga con el cargo sintético persistido, sin wizard forzado. Escritorio 1440×1000 y viewport móvil emulado 390×844: los siete pasos tuvieron `scrollWidth == innerWidth == 390`, sin controles fuera del ancho; revisión visual de capturas. Esto no sustituye aceptación del usuario ni prueba con dispositivo físico o lector de pantalla.

Capturas sintéticas de esta sesión (no datos privados): `/tmp/jobhunter-m14-desktop.png`, `/tmp/jobhunter-m14-mobile-summary.png`, `/tmp/jobhunter-m14-mobile-final.png`. No se versionan binarios regenerables.

## Matching y caché

Modalidad confirmada +6 si hay afinidad, distinta −8, desconocida sin bonificación; no confunde país y remoto. Remoto temporal/negado/no confirmado no suma. La elegibilidad conserva compatible/desconocida/incompatible y prioridad de restricciones explícitas. Nivel estructurado precede al título; N1/N2 sin seniority permanece visible. Se aplica la mayor penalización de nivel/años para evitar duplicarla, manteniendo score 0–100 y umbral.

Idiomas reconocidos con nivel y requisito explícito se comparan por cláusula; CEFR solo contra CEFR. Otros descriptores requieren revisión, sin equivalencias inventadas. Cursos/beneficios no se clasifican como requisitos. Salarios se comparan solo con moneda/periodicidad explícitas y comparables; no se convierte divisa ni se descarta una oferta por dato ausente. Requisitos obligatorios/deseables se clasifican solo con marcadores explícitos, conservando fragmento, coincidencias declaradas y brechas pendientes. Aprendizaje no suma como habilidad dominada y evidencia no acredita cumplimiento.

La caché existente incluye el perfil completo y título/descripción/ubicación/geo de la oferta; pruebas unitarias y API confirman invalidación por perfil y contenido sin recalcular cada dashboard. No se cambió su arquitectura ni se persistieron scores.

Comparación reproducible contra `614e394`: `.venv/bin/python scripts/eval_m14.py`. Casos sintéticos diferentes, sin ofertas ni perfiles reales:

| Caso | Antes | Después | Interpretación |
|---|---:|---:|---|
| Inicial soporte N1/N2, modalidad desconocida | 53 | 53 | Sigue visible; avisa sin bonificar modalidad |
| Intermedio, remoto confirmado | 63 | 69 | Modalidad confirmada afín +6 |
| Senior con 5+ años, perfil inicial | 0 | 5 | Evita sumar penalizaciones del mismo nivel |
| Fuente Junior, título Senior | 23 | 71 | Prevalece metadato estructurado |
| Idioma inferior y renta incomparable | 53 | 53 | Explicaciones de brechas sin inventar cumplimiento o cambio de moneda |
| Proyecto y aprendizaje sin dominio declarado | 38 | 38 | Aprendizaje no suma; Rust obligatorio y SQL deseable por revisar |

Estas cifras prueban casos concretos, no precisión/recall general del mercado. El algoritmo deliberadamente conserva incertidumbre y no es un analizador semántico completo.

## Pruebas ejecutadas

Sistema real: Linux Mint 22.3 Zena, `ID_LIKE=ubuntu debian`, base Ubuntu noble (24.04), kernel `7.0.0-31-generic`. Python 3.12.3, Node 24.21.0. Dependencias Python instaladas en `.venv` desde requirements.txt; frontend mediante npm ci y lockfile. Sin sudo, Docker ni servicios instalados.

| Comando | Resultado final |
|---|---|
| `JOBHUNTER_DATA_DIR=$(mktemp -d /tmp/jobhunter-verified-XXXXXX) .venv/bin/python -m pytest -q` | **188 passed**, 1 warning, 2.40 s |
| `cd frontend && npm test` | **33 passed**, 5 archivos, 2.57 s |
| `cd frontend && npm run typecheck` | **PASS**, tsc -b, salida 0 |
| `cd frontend && npm run build` | **PASS**, 37 módulos, build Vite 331 ms |
| `.venv/bin/python scripts/smoke_m14.py` | **PASS** en Linux real, dos arranques y cierres |
| `.venv/bin/python scripts/eval_m14.py` | **PASS**, tabla sintética reproducible anterior |
| `git diff --check` | **PASS** |

Warning Python: Starlette depreca el uso de httpx en TestClient a favor de httpx2. Las pruebas pasan con las dependencias declaradas; no se añadió una dependencia nueva por ese aviso. Los primeros intentos de TestClient se bloquearon dentro del aislamiento de herramientas: se terminaron esos dos procesos y se ejecutaron las suites fuera del aislamiento con los mismos fixtures temporales. Los resultados finales anteriores son de ejecuciones completas, no de los intentos interrumpidos.

Logs locales de evidencia: `/tmp/jobhunter-pytest-final.txt`, `/tmp/jobhunter-frontend-final.txt`, `/tmp/jobhunter-smoke-final.txt`; son regenerables mediante los comandos anteriores. Se observó RED antes de GREEN para persistencia, onboarding, matching, las diez regresiones de revisión, configuración y separación de idiomas por salto de línea.

## Smoke real de iniciar-jobhunter.sh

`scripts/smoke_m14.py` ejecuta **bash iniciar-jobhunter.sh**, con TemporaryDirectory, puerto disponible y programador habilitado pero sin frecuencia configurada. No usa datos de `data/` ni lanza búsquedas de fuentes. El script verifica:

- Listener real en `/proc/net/tcp{,6}` exclusivamente `127.0.0.1`; Host externo devuelve 400.
- Frontend compilado y rutas profundas `/perfil`, `/ofertas`, `/seguimiento`, `/configuracion`.
- Perfil ausente y plantilla nueva; PUT, GET, segundo guardado, .bak con versión anterior; 422 sin modificar archivo.
- Sin ejecuciones de búsqueda al arrancar/configurar. No se desconectó la red del sistema ni se hizo búsqueda real a portales.
- SIGINT: salida 0, mensaje de cierre y puerto cerrado; reinicio conserva perfil y consulta una oferta sintética guardada sin usar portales; segundo cierre limpio.
- Limpieza automática de sus datos temporales. El proceso adicional usado por Chromium también se cerró con SIGINT.

**Linux real aprobado en Mint/base Ubuntu. Ubuntu de distribución pura no se ejecutó. Windows de esta revisión está pendiente**; las verificaciones Windows anteriores de M0.5 son históricas. El entorno se preparó antes del smoke: no se presenta como prueba completa del primer arranque sin dependencias instaladas, ni de apertura automática de navegador (se usó --no-browser).

## CV y propuesta de producto

`docs/CV_INTEGRACION.md` revisa contratos existentes y enumera selector ES/EN, extracción/preview, offsets/hash, revisión literal, aprobación por sugerencia, copia .tex y PDF opcional faltantes. La importación era opcional en M1.4 y se mantiene para M2. No hay lectura de CV real, generación ni envío. El validador actual de sugerencias no acredita equivalencia semántica de una reformulación.

`docs/PRODUCTO.md` separa hechos de hipótesis: público Chile/LATAM inicial, app gratuita y licencia Pro por evaluar, pago único/suscripción sin precios, instaladores/soporte futuros, privacidad/consentimiento/borrado local, revisión de licencias/ToS/atribución/territorios y beta privada antes de invertir. No declara permisos comerciales ni cumplimiento legal sin revisar. Automatización opt-in permitida es futura; no se añadieron cobros, cuentas, telemetría ni nube.

## Revisión y decisiones

Revisión independiente, solo lectura, de `614e394..34e0029`: tres hallazgos importantes (validación anidada de respaldos, modalidad temporal/negada, clasificación de idiomas entre cláusulas). Se corrigieron con diez regresiones RED→GREEN y suite completa; después se comprobó el caso de saltos de línea y la misma conservación de fuentes desde Configuración. No hubo hallazgos concretos menores diferidos.

La revisión dejó fuera visual/teclado, smoke, documentos, Windows y respuestas de portales. Visual/teclado/smoke se ejecutaron después; documentos revisados por el implementador; Windows y portales reales permanecen fuera del PASS. Decisiones: usar la rama solicitada sin crear otra, mantener CV solo como diseño M2 y preferir advertencias al inferir requisitos inciertos. Coste de estas decisiones: importación CV y reconocimiento semántico más amplio siguen pendientes, sin presentar capacidades inexistentes.

## Commits y pendientes

Commits locales desde la referencia (más el commit documental que contiene este informe):

- `98b1b8c` validar perfil y conservar claves heredadas.
- `ea50030` onboarding opcional y campos veraces editables.
- `34e0029` reglas explicables de matching y comparación sintética.
- `e797e1f` contrato compartido, respaldos y correcciones de revisión.
- `5212d26` conservación de fuentes heredadas en Configuración.
- `50e0cfb` separación de idiomas por salto de línea.
- `293a7e2` smoke reproducible del iniciador Linux.
- El commit documental que contiene este informe se identifica con `git log --oneline 614e394..HEAD`.

La entrega conserva la rama `feat/local-first-fastapi-react`, sin push ni merge; el estado final se comprueba con `git status --short` y `git log --oneline 614e394..HEAD`.

Pendientes: smoke real Windows actualizado; prueba Ubuntu sin derivados si se requiere distinguir esa distribución; aceptación del diseño/paridad por el usuario antes de retirar Streamlit; ampliar idiomas/descriptores y formatos de salario/requisitos con fuentes autorizadas; mantener compatibilidad de dependencias ante la deprecación de TestClient; implementar importación/revisión CV en M2. Siguiente paso sugerido: validar manualmente este hito en Windows con una carpeta temporal y recoger feedback del asistente, antes de cualquier publicación o merge.
