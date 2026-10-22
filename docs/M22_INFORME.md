# M2.2 — Adaptación local verificable de CV LaTeX

Fecha: 21 de octubre de 2026. Rama `feat/local-first-fastapi-react`.
El flujo produce otra copia `.tex`, con evidencia y aprobación individual.
No compila PDF ni envía postulaciones.

## 1. Auditoría inicial

HEAD real verificado: `ea7a111507fef730c24f73766e6eb75f9e9c862a`, árbol limpio,
rama solicitada. No se asumió el commit de referencia: se consultaron branch,
status, log y rev-parse. `git merge-base --is-ancestor 4a810e4 HEAD` confirmó
el hotfix. No se hizo fetch: esto verifica el checkout y las referencias locales,
no afirma conocer cambios remotos posteriores.

Revisados antes de implementar: CV_INTEGRACION, M21_INFORME, cv_contracts,
cv_store, cv_parser, routers CV/ofertas, servicios de ofertas, matching, CvPage,
JobCard, cliente API y ROADMAP. Se revisaron además navegación/onboarding,
preferencias, configuración, esquema, respaldos y pruebas existentes.

Baseline ejecutado: **217 pytest y 41 Vitest**, ambos sin fallos. Se mantuvieron
parser, índice y primitivas privadas M2.1. Sin migraciones SQLite ni cambios al
ranking; la clasificación de marcadores se comparte con preferencias. Se verificó
documentación pública de FastAPI y React mediante Context7; consultas genéricas,
sin documentos, datos del proyecto ni credenciales.

Todo el trabajo usa ofertas/CV/perfil sintéticos. No se abrieron CV personales,
la carpeta real de datos ni credenciales. El checkout permanece en la rama de
desarrollo. Sin modificaciones a main, push, merge o cambios de visibilidad.

## 2. Arquitectura

| Unidad | Responsabilidad |
|---|---|
| `backend/services/job_analysis.py` | Analizar exclusivamente la oferta guardada, citas y huellas |
| `jobhunter/preferences.py:requirement_kind` | Clasificación compartida de marcadores explícitos |
| `backend/services/tailoring_engine.py` | Evidencia, propuestas cerradas, validación estructural y diff |
| `backend/services/tailoring_store.py` | Snapshot, revisión concurrente, artefactos y trazabilidad privados |
| `backend/routers/tailoring.py` | Cuerpos estrictos, errores seguros y descarga de bytes verificados |
| `backend/cv_contracts.py` | Extensiones compatibles de contratos M2.1/M2.2 |
| `frontend/src/pages/TailoringPage.tsx` | Selección, revisión individual, evidencia, diferencias y descarga |

El almacén toma el bloqueo de CvStore para leer/verificar el maestro y conservar
sus bytes exactos antes de publicar un plan. El motor opera sobre la fuente
fijada; no acepta modificaciones documentales desde el cliente. Antes de cada
lectura/mutación reconstruye las propuestas y coteja sus campos. No se usan IA,
modelos externos, compiladores, procesos ni conexiones de red para adaptar.

## 3. Contratos y endpoints

Detalle completo y cuerpos: [CV_INTEGRACION.md](CV_INTEGRACION.md).

| Método | Ruta bajo `/api/tailoring` | Resultado |
|---|---|---|
| GET | `/jobs/{job_id}/analysis` | JobAnalysis con requisitos, citas, idioma recomendado y parcialidad |
| POST | `/plans` | 201, plan para job_id/cv_id/hash revisado/lang explícito |
| GET | `/plans/{id}` | Plan verificado, avisos de cambios del maestro/oferta |
| PATCH | `/plans/{id}/suggestions/{sid}` | Decisión accepted/rejected/pending con expected_revision |
| GET | `/plans/{id}/preview?expected_revision=N` | Fuente original, resultado, diff, bloqueos y hash de bytes |
| POST | `/plans/{id}/generate` | Nueva copia privada con expected_revision y preview_sha256 |
| GET | `/plans/{id}/download` | Attachment `.tex` verificado, sin ruta pública estática |

Plan: identidad de oferta/CV, SHA-256 de fuente, análisis con SHA-256 de descripción,
idioma de trabajo, requisitos, matches/evidencia, sugerencias/decisiones, estado,
revisión entera, fechas y artefacto/hash. El registro privado agrega metadatos del
CV y huella de ID/cargo/empresa/descripción de oferta. `Evidence` conserva cita,
sección y spans de caracteres Python Unicode. Nunca se aplican índices JS UTF-16.

Cuerpos estrictos rechazan campos extra, reemplazos, citas, spans o hashes de fuente
manipulados. Revisión anterior → 409; toda mutación se serializa entre hilos y
procesos. Generar verifica que los bytes corresponden a la vista previa revisada.
Pending y rejected conservan el original. Brechas nunca tienen texto de salida.
Respuestas de adaptación/CV, incluidos errores de validación, llevan no-store y
nosniff. Errores no contienen rutas ni mensajes del sistema operativo.

La URL `?plan=<id>` permite reabrir una revisión. Si la oferta ya fue eliminada,
el plan y su análisis guardado siguen visibles, pero no se generan nuevas copias.
No hay todavía índice visual de planes históricos ni editor manual de requisitos.

## 4. Identificación de requisitos

Catálogo acotado de tecnologías con límites de palabra: Python, FastAPI,
PostgreSQL, Docker, React, REST APIs/APIs REST y otras herramientas enumeradas.
Se reutilizan norm/contains/has_skill y required_years. Secciones con marcadores
explícitos permiten required/nice_to_have; menciones descriptivas quedan unknown.
Negaciones y mezcla de marcadores quedan por confirmar. No se presume obligación
por mencionar una herramienta. La evidencia de cada entrada es texto literal.

Experiencia solicitada, nivel, idiomas y condiciones se detectan si el fragmento
contiene vocabulario explícito. No se completan ausencias con suposiciones.
Descripción corta (<80 caracteres), sin entradas detectables o truncada con puntos
suspensivos se marca parcial. La heurística no puede probar que una descripción
larga esté completa; siempre se ofrece revisar el texto guardado. No se descargan
páginas ni se consultan conectores. El idioma ES/EN depende del vocabulario, con
recomendación ES ante empate; se puede cambiar. Remoto no decide inglés.

## 5. Límites del matching

Solo evidencia literal en secciones reconocidas de experiencia/proyectos/habilidades;
la cita debe existir tanto en texto extraído como en fuente no comentado/no opaco.
La certeza se llama `literal_mention`: no dice “requisito cumplido”. No hay similitud
semántica, traducción de herramientas, estimación de dominio, certificación,
reconocimiento de título finalizado ni cálculo de años acreditados.

Aprendizaje, negación o contexto incierto excluyen conservadoramente la sección
completa; puede omitir evidencia legítima y exige revisión humana. La educación no
se transforma. Proyectos académicos conservan su sección y texto. Idiomas, años,
grados y condiciones quedan como brechas por revisar, sin convertir menciones de
tecnologías en acreditación de esos requisitos compuestos. No se usa el perfil
para insertar datos en el CV.

## 6. Reglas anti-invención y transformaciones

1. Reordenar: permutación estable de viñetas completas dentro de **una misma lista**.
2. Destacar: insertar únicamente `\textbf{...}` alrededor de un término literal.
3. Omitir: retirar opcionalmente una viñeta completa sin coincidencia; puede seguir
   siendo relevante y requiere aprobación individual.
4. Reformular: deshabilitado. Una cita no demuestra que otro texto tenga igual sentido.
5. Brechas: solo informativas, ninguna salida documental.

Se valida el documento completo y se exige una gramática conservadora: clase article,
paquetes estándar enumerados, llaves/entornos balanceados y listas itemize planas
con viñetas textuales sencillas. Macros, clases/paquetes desconocidos, inclusiones,
condicionales, entornos opacos, matemáticas o extracción parcial bloquean generación.
Listas con contacto, teléfonos, links, etiquetas, contexto dependiente o formato
interno no se transforman. No se alteran configuración, preámbulo ni contactos.

No hay generador de prosa: en la gramática soportada, reordenar conserva los mismos
fragmentos; omitir produce un subconjunto; destacar conserva el texto y añade solo
formato. Las pruebas recorren todas las combinaciones aceptadas/rechazadas compatibles
de la fixture sintética y verifican que ninguna afirmación se duplica o aparece de
nuevo; el resto del documento queda idéntico. Esto no es una prueba general de la
semántica de TeX ni garantiza compilación de plantillas arbitrarias.

Aprobar reordenación y énfasis/omisión sobre la misma lista causa conflicto explícito.
La UI pide elegir una alternativa. No hace cambios automáticos ni resuelve conflictos
silenciosamente. Generar con cero aceptaciones crea otra copia exacta soportada.

## 7. Integridad, privacidad y persistencia

Solo `<JOBHUNTER_DATA_DIR>/cv/tailoring/`: snapshot `.source`, plan `.json`, copia
`.tex` y registro `.audit` por generación. Nombres UUID internos, directorio 0700,
archivos 0600. El snapshot mantiene BOM/CRLF y SHA-256 de bytes exactos.

Se reutilizan RLock/flock, descriptor de carpeta, O_NOFOLLOW, lectura regular sin
enlaces duros y escritura fsync de CvStore. Snapshot/artefactos se publican con
enlace exclusivo de un archivo temporal en el mismo directorio, sin sobrescribir.
El plan se sustituye atómicamente al final. Fallos simulados de fsync/commit no
publican copias parciales ni alteran la revisión comprometida. Descarga coteja el
artefacto con su hash y con los bytes reconstruidos desde decisiones verificadas.

Sustituir o eliminar maestro no destruye el snapshot: se muestra versión más reciente
o ausencia, y se trabaja únicamente sobre la fuente fijada. Oferta cambiada/eliminada
bloquea nuevas mutaciones/generación; una copia ya generada conserva su trazabilidad.
Cambiar decisiones invalida el artefacto actual y exige generar otra copia; las
anteriores siguen privadas con sus registros de decisiones.

Sin tablas/migraciones nuevas, respaldos JSON, public/dist, contenido documental en
logs o rutas de cliente. Windows mantiene el fallo seguro POSIX; el resto de la app
sigue disponible. Límites heredados: no protege frente a la misma cuenta del SO,
borrado forense o fallo físico. Una interrupción abrupta puede dejar huérfanos
privados sin publicar; retención/limpieza y recuperación de planes son manuales.
No se afirma resistencia completa a pérdida de alimentación.

## 8. Ejemplos sintéticos ES/EN

ES: “Requisitos obligatorios: Python y FastAPI”, “Deseable: PostgreSQL”, “Usamos
Docker en otro equipo”, “Se requieren 3 años de experiencia laboral”. CV:
“Desarrollé servicios con Python y FastAPI”, “Gestioné datos con PostgreSQL”,
proyecto académico SVG y “Ingeniería en curso desde 2022”. Resultado probado:
énfasis Python aceptado, otras propuestas rechazadas/pendientes, Docker y años
como brechas; maestro intacto. No convierte formación en curso en título terminado.

EN: “Requirements: Python and FastAPI”, “Nice to have: PostgreSQL”, “Our other team
uses Docker”, “Must have 3 years of professional experience”. CV: “Built services
using Python and FastAPI”, “Managed data using PostgreSQL”, “Academic drawing
project using SVG” y “Engineering degree in progress since 2022”. Resultado:
reordenación aceptada, omisión rechazada; copia descargada, formación y maestro
conservados. API prueba EN/EN; Chromium prueba además recomendación EN con idioma
de trabajo cambiado manualmente a ES, sin traducir ni cambiar afirmaciones.

Fixtures en `tests/backend/test_tailoring_engine.py`, `test_tailoring_api.py` y
`frontend/src/pages/tailoring.test.tsx`. Solo nombres ficticios y dominios `.invalid`.
No se versionan fuentes o artefactos `.tex` generados.

## 9. Chromium y capturas

Chromium real mediante DevTools, contexto aislado, servidor temporal loopback 8899,
scheduler desactivado y datos en `/tmp/jobhunter-m22-browser`. No se consultaron
portales. Se cerraron pestaña y servidor después de la prueba.

- Sin perfil: abandonar onboarding navegando, abrir oferta → Adaptar mi CV, revisar
  requisitos sin CV; importar sintéticos desde formularios reales de Mis CV.
- ES: selección, plan con todas las propuestas pending, aceptar énfasis, rechazar
  omisión/otras alternativas, diff actualizado y botón de generación; descarga real
  vía attachment y verificación de hash/maestro mediante fetch en el navegador.
- EN: importación con idioma English, recomendación EN, cambio manual a ES, revisión,
  reordenación aceptada/omisión rechazada, generación/descarga y conservación de
  “degree in progress”.
- Navegación por Dashboard, Explorar, Seguimiento, Mis CV, Configuración y Mi perfil
  con y sin perfil sintético; rutas y encabezados correctos. “Adaptar mi CV” mantiene
  el mismo document de React y no reactiva onboarding. `4a810e4` sigue ancestro y
  Layout no se modificó.
- Escritorio 1440×1000 claro y móvil oscuro 390×844. Se detectó y corrigió un
  desborde inicial del diff; medición final con emulación mobile/touch:
  innerWidth=390, scrollWidth=390, cero controles fuera del ancho. Sin errores ni
  advertencias de consola en la última navegación.

Capturas exclusivamente sintéticas, revisadas visualmente (emulación, no teléfono físico):

- [Escritorio, revisión completa](evidencias/m22/escritorio.png).
- [Móvil oscuro, oferta y revisión fijada](evidencias/m22/movil-oscuro.png).
- [Móvil oscuro, diff y descarga](evidencias/m22/movil-diferencias.png).

La herramienta rechazó escribir directamente en la ruta local; se guardaron los
bytes PNG devueltos por DevTools sin edición. No se incluyen capturas de datos reales.

## 10. Pruebas y revisión

| Comprobación ejecutada | Resultado |
|---|---|
| `JOBHUNTER_DATA_DIR=/tmp/jobhunter-m22-final .venv/bin/python -m pytest -q -o faulthandler_timeout=30` | **257 passed**, 5.51 s |
| `cd frontend && npm test` | **46 passed**, 8 archivos |
| `cd frontend && npm run typecheck` | Correcto |
| `cd frontend && npm run build` | Correcto, 39 módulos |
| Chromium funcional ES/EN, escritorio/móvil y navegación | Correcto, alcance descrito arriba |
| `git diff --check` | Correcto |

Pytest se ejecutó fuera del sandbox por el bloqueo conocido de TestClient dentro
de este entorno. Aviso preexistente de deprecación Starlette/httpx; sin errores.
No se ejecutó CI remoto ni se atribuye aprobación CI a estos commits locales.

Cobertura nueva: ES/ES y EN/EN, idioma manual, obligatoriedad/deseabilidad/unknown,
negación de obligación, menciones literales, brechas, formación en curso/proyectos
académicos, fuentes cambiadas/eliminadas, spans Unicode/comentarios/BOM/CRLF,
macros/clases/paquetes opacos, decisiones individuales, conflictos, conservación,
cuerpos manipulados, snapshot/plan/artefacto alterados, concurrencia con dos hilos,
fallos fsync/commit, directorios/symlinks/hardlinks, contratos de ruta, plataforma
sin primitivas POSIX, no-store y exclusión del respaldo JSON.

Revisión independiente de código (solo fixtures sintéticas) encontró aprendizaje
contextual, contactos con teléfono espaciado y ocultación de plan con oferta eliminada.
Los tres se reprodujeron en pruebas fallidas y se corrigieron. Revisión propia añadió
regresiones para negación de obligación, comentario con cita idéntica y clases/paquetes
no soportados. Las pruebas nuevas se observaron fallar antes de implementar/corregir.
El defecto responsive se detectó, corrigió y midió en Chromium. Esto no constituye
una auditoría de seguridad exhaustiva ni validación de todas las plantillas TeX.

## 11. Commits locales

1. `617df95` — analizador, contratos, motor y pruebas iniciales.
2. `e0a7b15` — snapshot, persistencia, API y pruebas.
3. `88dd852` — correcciones de evidencia/contexto/contactos y regresiones de integridad.
4. `c364005` — flujo React, diff, idioma, decisiones, descarga y navegación.
5. Commit documental `docs(m22): record tailoring contracts validation and synthetic evidence`:
   este informe, manual, README, ROADMAP, plan cerrado y capturas. Su hash se obtiene
   con `git log --oneline ea7a111..HEAD` después de guardar este mismo documento.

## 12. Pendientes y M2.3

- Compilación PDF aislada, sin shell escape y con límites de archivos/red/CPU/tiempo;
  detectar LaTeX instalado nunca habilita compilación automáticamente.
- Pruebas de plantillas/clases adicionales antes de ampliar la gramática; reformulación
  libre y equivalencia semántica no se habilitan con coincidencias literales.
- Portabilidad de almacenamiento privado a Windows con garantías equivalentes.
- Catálogo, idiomas y detección de contexto más amplios, editor manual de requisitos,
  listado/retención/eliminación de planes; no se presentan como implementados.
- Asociación documental con postulaciones queda posterior. No se implementó envío,
  automatización de formularios, IA externa o acceso a cuentas.
