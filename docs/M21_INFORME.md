# M2.1 — Integración de currículums LaTeX

Fecha local: 21 de octubre de 2026. Rama `feat/local-first-fastapi-react`.
Implementación local, sin push ni modificación/merge de `main`.

## Auditoría y alcance

- Inicio: árbol limpio, HEAD `4a810e4` (hotfix de navegación); rama correcta,
  sincronizada con su referencia remota local. No se modificó ningún commit previo.
- Leídos README, ROADMAP, ARQUITECTURA, CV_INTEGRACION, PERFIL y
  M14_HOTFIX_NAVEGACION; revisados contratos CV, rutas, modelos, persistencia,
  respaldos, cliente React, navegación y pruebas existentes.
- Reutilizados contratos `CvSource`, `CvSection`, `ParsedCv` y adaptación futura;
  componentes Card/Notice/AsyncView/ErrorBox/PageHeader, cliente tipado y useAsync.
- Sin rediseño del panel, cambios al matching, obligación de tener CV, eliminación
  de Streamlit, nuevas dependencias, nube, IA pagada ni servicios permanentes.

## Implementación y arquitectura

| Unidad | Responsabilidad |
|---|---|
| `backend/services/cv_store.py` | Copias privadas exactas, índice atómico, bloqueo, recuperación e integridad |
| `backend/services/cv_parser.py` | Extracción textual conservadora sin ejecución |
| `backend/routers/cv.py` | API, subida por chunks, validación y errores seguros |
| `backend/cv_contracts.py` | Metadatos públicos y fuente, secciones, bloques opacos y contratos M2.2 |
| `frontend/src/pages/CvPage.tsx` | Gestor y vista previa segura, integrado en `/cv` |

Persistencia: `<JOBHUNTER_DATA_DIR>/cv/`, índice JSON v1 y archivos UUID `.tex`.
Se eligió índice local para aislar metadatos y documentos de SQLite y sus snapshots;
no hubo migración SQLite ni motivo para crear un respaldo de migración. El índice
se valida antes de operar y se compromete mediante sustitución atómica.
Documentación de diseño/ejecución en
[plan M2.1](superpowers/plans/2026-10-21-m21-cv.md).

## Funcionamiento

Importar desde navegador, nombre descriptivo, idioma explícito ES/EN, múltiples
registros incluso con nombres iguales, fecha, tamaño y SHA-256 de bytes originales.
Principal explícito por idioma (sin selección automática). Sustituir conserva ID,
nombre/idioma, fecha inicial y principal; actualiza revisión/hash/fecha/tamaño.
Eliminar y sustituir requieren confirmación y hash revisado. El archivo original
del usuario permanece intacto. No se guarda su ruta ni nombre de archivo original.
La app sigue funcionando sin CV y con onboarding omitido o incompleto.

API implementada (contrato detallado en [CV_INTEGRACION](CV_INTEGRACION.md)):

- `POST /api/cv/import` → 201 `CvMetadata`.
- `GET /api/cv` y `GET /api/cv/{id}` → metadatos públicos.
- `GET /api/cv/{id}/preview` → `ParsedCv` sin path.
- `PUT /api/cv/{id}/primary` → principal por idioma.
- `PUT /api/cv/{id}` y `DELETE /api/cv/{id}` → operación confirmada y controlada por hash.

Subida de bytes crudos, cabeceras con nombre/idioma (sin nombres privados en query),
no dependencia multipart. Límite `JOBHUNTER_CV_MAX_BYTES` = 1 000 000 por defecto.
Errores FastAPI detail, HTTP 404/409/413/422/500 sin rutas internas ni fuente.

## Parser: evidencia y límites

Pruebas y capturas exclusivamente sintéticas, sin importar CV personales.
Se reconocieron encabezado/contacto como texto, resumen, experiencia, educación,
habilidades, proyectos e idiomas en ES/EN, además de una sección de comunidad
conservada como `other`. No se asumen años de empleo ni títulos completados.

Fuente completo, texto de cada sección, fragmento raw y offsets `[inicio,fin)`
permiten revisión y futura trazabilidad. Offsets en caracteres Unicode Python
sobre fuente sin BOM; SHA-256 en bytes exactos (incluidos BOM/CRLF).
Macros/entornos desconocidos y argumentos multilínea quedan opacos. Los condicionales
no se evalúan: desde el primero se excluye conservadoramente el resto. Los comentarios
respetan la paridad de barras escapadas. Sin secciones reconocidas se avisa parcial.

No es un motor TeX ni una extracción semántica completa: plantillas, redefiniciones,
comandos personalizados y estructuras no soportadas requieren revisar el fuente.
`skills` queda reservado/vacío; las habilidades visibles son el texto de su sección,
sin convertirlo en acreditación. `validate_suggestion` sigue siendo un control
literal limitado, no validación semántica ni autorización para generar documentos.

## Seguridad y privacidad

- Carpeta 0700 y archivos 0600; nombres internos UUID independientes de la entrada.
- Operaciones POSIX con descriptor de carpeta y `O_NOFOLLOW`; se rechazan rutas de
  entrada, enlaces simbólicos, enlaces duros al leer y ubicaciones bajo código/public.
- Escritura exclusiva temporal, flush/fsync del archivo y sustitución atómica.
  Índice corrupto falla cerrado. Recuperación de `.deleted` y huérfanos internos
  según índice tras interrupción; pruebas de fallo de escritura/fsync/reemplazo.
- Hash real comprobado en lectura, sustitución y eliminación dentro del bloqueo;
  un documento modificado externamente se conserva y devuelve conflicto 409.
- Fuente mostrado mediante texto React escapado; sin HTML arbitrario ejecutado,
  macros, subprocess, lectura de inputs LaTeX, shell escape o compilación.
- Sin texto de CV en logs nuevos, sin paths públicos, sin copias en public, fixtures
  personales o respaldos JSON. Respuestas CV con no-store y nosniff.
- Revisión independiente encontró tres defectos antes del cierre (cuerpos opacos,
  comentarios escapados e integridad antes de mutación). Se reprodujeron con cinco
  regresiones fallidas, se corrigieron y se revisaron de nuevo sin hallazgos
  importantes nuevos. No se presenta como auditoría de seguridad exhaustiva.

Límites: privacidad de usuario local, no defensa contra un proceso con control de
su misma cuenta, ni borrado forense ni garantías ante fallo físico/pérdida de energía.
El gestor seguro requiere POSIX: Linux probado; en Windows falla cerrado hasta
implementar garantías equivalentes. El resto de la app permanece disponible.

## Verificación ejecutada

| Comando / comprobación | Resultado final |
|---|---|
| `JOBHUNTER_DATA_DIR=/tmp/jobhunter-m21-final .venv/bin/python -m pytest -q -o faulthandler_timeout=30` | **217 passed**, 3.82 s |
| `cd frontend && npm test` | **41 passed**, 7 archivos |
| `cd frontend && npm run typecheck` | Correcto |
| `cd frontend && npm run build` | Correcto, 38 módulos Vite |
| `git diff --check` | Correcto |
| Chromium real, datos temporales, escritorio y móvil emulado | Correcto, detalles abajo |

Pytest ejecutado fuera del sandbox: TestClient se quedó bloqueado en la primera
invocación dentro de este, que se interrumpió y no se cuenta como aprobación.
Un aviso preexistente de deprecación Starlette/httpx; no errores de pruebas.
Vitest usa submit sintético en dos casos por la validación de FileList de jsdom;
el envío de formulario con required se verificó adicionalmente en Chromium real.

Cobertura CV: ES/EN, inválidos/extensión/control/binarios/vacíos, tamaño, Unicode/BOM,
macros/secciones/entornos/condicionales desconocidos, comentarios, comandos maliciosos
sin ejecución, paths y enlaces, duplicados, principal, reemplazo, eliminación,
confirmación ausente, conflictos de hash, corrupción del índice, fallos de escritura,
fsync y commit de índice, recuperación de interrupción, aislamiento de respaldos
y public. Navegación real React/StrictMode recorre las seis secciones sin perfil,
con perfil, cancelación/reapertura y respuestas demoradas; conserva la regresión
cubierta por `4a810e4`.

## Navegador y capturas

Chromium mediante DevTools, contextos aislados, servidores locales temporales
(8897 y 8898), scheduler desactivado, ningún conector consultado.

1. Entrada inicial abre el asistente; cancelar no guarda perfil. Recorrido por
   Dashboard, Explorar, Seguimiento, Mis CV, Configuración y Mi perfil sin redirección.
2. Estado vacío; formulario real con nombre Unicode y `.tex` sintético con BOM.
   Importación correcta, principal ES y preview parcial de macro y sección desconocida.
3. Importación EN, principales ES y EN simultáneos, cancelar sustitución/eliminación
   sin mutar, confirmar sustitución cambia hash manteniendo ID y confirmar eliminación
   deja intacto el registro ES.
4. Escritorio 1440×1000 y móvil oscuro emulado 390×844: `scrollWidth == innerWidth`,
   sin controles de main fuera del ancho. Capturas revisadas visualmente.
5. Segundo arranque con el código revisado: formulario válido, importación sintética,
   condicional desconocido conservado opaco y excluido del texto reconocido,
   no-store presente y `path` ausente de la respuesta.

Capturas con datos sintéticos (no dispositivo móvil físico ni aceptación visual del usuario):

- [Escritorio claro](evidencias/m21/escritorio.png).
- [Móvil oscuro](evidencias/m21/movil-oscuro.png).

Los servidores y pestañas temporales se cerraron al terminar; no quedan servicios
instalados ni se modificó el directorio real de datos.

## Git y entrega

Se preserva `4a810e4` como ancestro. Entrega dividida en commits locales auditables:
backend y pruebas, frontend y pruebas, documentación/evidencias. La lista exacta
de hashes se entrega junto al resultado; puede verificarse con
`git log --oneline 4a810e4..HEAD`. Sin push ni merge de main. Verificación final
con árbol limpio y rama original tras los commits.

## Pendientes para M2.2

- Analizar oferta con requisitos obligatorios, deseables y desconocidos; seleccionar
  CV ES/EN de forma explícita y revisable.
- Fijar revisión con `TailoringPlan.cv_sha256`, validar spans/citas contra fuente y
  mantener snapshot por plan antes de permitir cambios de su maestro asociado.
- Conectar propuestas con evidencia del CV o confirmación expresa del usuario;
  guardar brechas sin inventar habilidades. Aprobar individualmente las sugerencias.
- Generar otra copia `.tex`; PDF solo mediante aislamiento y controles propios,
  nunca habilitar compilación solo por detectar LaTeX instalado.
- Asociar PDF con postulación; mantener modos manual, asistido con revisión y
  automático mediante autorización previa/reglas, solo donde se permita y tras
  validar elegibilidad, documentos y respuestas. Sin implementación de envío en M2.1.
- Portabilidad segura Windows y expansión de plantillas solo con material sintético
  o autorizado; no inferir equivalencia semántica a partir de coincidencias literales.
