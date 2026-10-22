# Integración local de currículums LaTeX

M2.1 implementa gestión y extracción textual; M2.2 añade análisis, revisión y copias `.tex` adaptadas locales. PDF corresponde a M2.3; envío queda para fases posteriores.

## Uso

En **Mis CV**, asignar nombre, seleccionar Español/English y elegir un `.tex` UTF-8
(con BOM opcional). Importar crea una copia privada; nunca abre rutas recibidas del
cliente ni modifica el archivo seleccionado. Pueden coexistir nombres iguales.
Seleccionar explícitamente un principal por idioma; no se elige automáticamente.
Ver contenido abre texto reconocido, contenido opaco y fuente completo escapado.
Sustituir pide otro archivo y confirmación; conserva ID, nombre, idioma, importación
e indicador principal, y actualiza hash, tamaño y fecha de versión. Eliminar pide
confirmación y borra únicamente la copia gestionada y sus metadatos. No promueve
otro principal silenciosamente. Ningún flujo de ofertas exige tener CV.

## Persistencia y privacidad

`<JOBHUNTER_DATA_DIR>/cv/` contiene `index.json` (versión 1), `.lock` y copias
`<uuid>.tex`. El índice referencia una revisión interna inmutable; el nombre original
del archivo no se conserva. Los bytes importados, incluido BOM/CRLF, se mantienen
exactos. SHA-256 corresponde a esos bytes. La vista textual decodifica UTF-8 sin BOM.

Se prefiere un índice local a añadir tablas SQLite: mantiene documentos y metadatos
fuera de respaldos JSON y snapshots de la base existente; no introduce migraciones
ni altera Streamlit. El índice tiene sustitución atómica, bloqueo de hilos y
`flock` entre procesos. No se migró SQLite, por lo que no corresponde crear un
respaldo de migración. Una futura migración del índice debe respaldarlo antes.

Permisos POSIX 0700 para carpeta y 0600 para archivos. Nombres UUID independientes
del cliente, operaciones relativas a descriptor de carpeta y `O_NOFOLLOW`.
Se rechazan enlaces simbólicos al abrir y archivos con enlaces duros o tipos no
regulares al leer. Se rechazan ubicaciones dentro del código/public/dist; dentro
del repositorio solo se permite su carpeta privada `data/`, ignorada por Git.
Un directorio externo elegido mediante configuración también es válido.

Temporales en la misma carpeta, creación exclusiva, flush/fsync del archivo y
`os.replace`. La revisión nueva se escribe antes de comprometer el índice; un fallo
previo conserva el documento anterior. La eliminación usa `.deleted` y revierte
el nombre si falla el índice. Tras interrupción, la siguiente operación restaura
el archivo si el índice aún lo referencia; en otro caso retira el temporal o la
revisión huérfana con nombre interno. No se recorren directorios externos.
Si falla la limpieza después de comprometer el índice, la API informa error y pide
recargar; la siguiente operación reintenta la limpieza. Esto no garantiza resistencia
a fallos físicos/pérdida de alimentación ni borrado forense de SSD/backups del SO.

Índice corrupto: falla cerrado y no sobrescribe. Cerrar JobHunter y conservar una
copia privada de toda la carpeta antes de recuperar manualmente. No editar archivos
mientras la app opera. Si falta/cambia una copia, vista previa y operaciones
destructivas fallan sin destruirla; volver a importar un original seleccionado
por el usuario es una opción tras conservar la copia dañada.

No se exportan paths, contenido en listas, CV en JSON de respaldo ni nuevos logs
con texto de CV. Las respuestas CV llevan `Cache-Control: no-store`. Metadatos de
subida viajan en cabeceras para no incluir nombres en URLs de acceso. No hay
servicios externos, IA pagada ni lectura automática de CV personales.

La protección segura del gestor está implementada para POSIX (Linux verificado).
En Windows, CV falla cerrado por falta de `dir_fd`/`O_NOFOLLOW`; el resto de la app
continúa disponible. Portar las garantías de almacenamiento a Windows es pendiente.

## API activa

| Método | Ruta | Respuesta |
|---|---|---|
| POST | `/api/cv/import` | 201, `CvMetadata` |
| GET | `/api/cv` | Lista de `CvMetadata` |
| GET | `/api/cv/{id}` | `CvMetadata` |
| GET | `/api/cv/{id}/preview` | `ParsedCv`, sin path interno |
| PUT | `/api/cv/{id}/primary` | `CvMetadata`, un principal por idioma |
| PUT | `/api/cv/{id}` | `CvMetadata` actualizado |
| DELETE | `/api/cv/{id}` | `{deleted: true}` |

Importación y sustitución reciben bytes crudos; el frontend envía
`Content-Type: application/x-tex`. Cabecera `X-CV-Filename` con nombre codificado
mediante percent encoding; importar también requiere `X-CV-Name` codificada e
`X-CV-Lang: es|en`. No se transmite una ruta del usuario. Los PUT/DELETE destructivos
requieren `confirm=true&expected_sha256=<hash revisado>`. Se compara también el
hash real de los bytes privados dentro del bloqueo.

Errores coherentes FastAPI `{detail: ...}`: 404 ausente, 409 conflicto de versión o
integridad, 413 tamaño, 422 validación/confirmación ausente o falsa, 500 fallo privado
de almacenamiento. No se incluyen rutas ni mensajes del sistema operativo.
Límite configurable `JOBHUNTER_CV_MAX_BYTES`, defecto 1 000 000 bytes; se verifica
por chunks antes de acumular más contenido y de nuevo antes de escribir.

## Parser conservador y límites

`cv_parser.parse` implementa el protocolo `CvParser` sin compilación ni expansión.
Identifica encabezado/contacto como texto, resumen, experiencia, educación,
habilidades, proyectos, idiomas y otras secciones. Reconoce divisiones literales
`section`, `subsection`, `cvsection` (también con estrella), títulos ES/EN y una
lista pequeña de comandos textuales, contactos y entornos. No depende de itemize:
acepta párrafos, enumeraciones y texto sencillo. Sin divisiones reconocidas conserva
un bloque y marca extracción parcial; no intenta adivinar cargos ni fechas.

Cada sección tiene clave, tipo, título, texto y `raw_tex` con `tex_span=[inicio,fin)`.
Offsets de caracteres Unicode Python en `source_text` sin BOM, no bytes ni unidades
UTF-16 de JavaScript. El fuente completo permanece disponible como texto. Los
bloques no interpretados incluyen raw/span/motivo. Comentarios respetan escapes
con paridad de barras; macros desconocidas con argumentos multilínea y entornos
desconocidos se conservan opacos. Desde un condicional desconocido se considera
opaco todo el resto, sin evaluar ramas. Se prioriza omitir frente a inventar.

Es una lectura orientativa, no un intérprete TeX ni un sanitizador para compilación.
No puede conocer la semántica de plantillas, redefiniciones, paquetes, archivos
incluidos, tablas arbitrarias, matemáticas o macros personalizadas. No acredita
habilidades, títulos completados ni años. `skills` queda reservado (vacío): el texto
de habilidades está en su sección, sin convertirlo en un catálogo acreditado.
`partial` avisa de estructuras no soportadas; aun sin aviso se debe revisar.
La vista React nunca usa HTML arbitrario, enlaces activos derivados del fuente ni
`dangerouslySetInnerHTML`. No hay procesos, `input` de archivos, macros ejecutadas,
`--shell-escape`, compilación automática, PDF ni integración con cuentas.

## Adaptación M2.2

Desde una oferta expandida: **Adaptar mi CV → elegir documento e idioma de trabajo
→ analizar y crear plan → revisar evidencia y decidir cada cambio → revisar
Diferencias propuestas → Generar CV adaptado → Descargar .tex adaptado**.
Sin CV se conserva el análisis y se ofrece Mis CV. No necesita perfil completo.
La URL con `?plan=<id>` permite reabrir el plan; no es un enlace público a su fuente.
El idioma recomendado es modificable y no depende de que el trabajo sea remoto.
Elegir otro idioma no traduce el CV: el texto se conserva en su idioma original.

### Contratos

Se extienden `JobAnalysis`, `Requirement`, `Evidence`, `Suggestion`, `TailoringPlan`
sin retirar sus campos originales. `JobAnalysis` guarda cargo, empresa, descripción
literal, SHA-256 de descripción, requisitos con categoría y aviso parcial.
`Requirement.text` es un fragmento literal, `kind` es required/nice_to_have/unknown.
Categorías: technology, experience, level, language, condition, other.

Cada `EvidenceMatch` apunta a un índice de requisito y `Evidence` contiene sección,
cita literal, span Python Unicode y certeza `literal_mention` con explicación.
Una coincidencia es una **mención documentada**, nunca una certificación de cumplir
el requisito. `coverage` es la proporción de entradas obligatorias con menciones,
no una probabilidad de contratación ni acreditación de nivel/experiencia.
La UI no presenta este cociente como cumplimiento.

Cada propuesta tiene ID, acción, sección, antes/después, span, índices de requisitos,
evidencias, razón y pending/accepted/rejected. Las brechas no tienen salida ni span.
Todas empiezan pending, incluidas brechas informativas, que nunca se aplican.
`validate_suggestion` comprueba las citas; el motor además regenera propuestas desde
fuente y oferta inmutables, verifica spans y bloquea conflictos. La comprobación
literal aislada **no demuestra equivalencia semántica**.

El plan fija `id`, `job_id`, `cv_id`, `cv_sha256`, `lang`, análisis con hash de
descripción, evidencia, propuestas/decisiones, estado review/generated, revisión
entera, fechas, nombre del CV, bloqueos y último artefacto/hash. La persistencia
privada agrega huella de ID/cargo/empresa/descripción y metadatos de la fuente.

### Endpoints activos

Todos bajo `/api/tailoring`, sin rutas arbitrarias ni documentos estáticos:

| Método | Ruta relativa | Contrato |
|---|---|---|
| GET | `/jobs/{job_id}/analysis` | `JobAnalysis` del texto guardado; no consulta conectores |
| POST | `/plans` | 201 `TailoringPlan`; cuerpo job_id, cv_id, expected_cv_sha256, lang |
| GET | `/plans/{id}` | `TailoringPlan` verificado; avisos cv_changed/job_changed |
| PATCH | `/plans/{id}/suggestions/{sid}` | expected_revision y status; devuelve nueva revisión |
| GET | `/plans/{id}/preview?expected_revision=N` | original, result, unified diff, SHA-256, blockers, applied y revisión |
| POST | `/plans/{id}/generate` | expected_revision y preview_sha256; crea artefacto y nueva revisión |
| GET | `/plans/{id}/download` | bytes `.tex` privados con Content-Disposition attachment |

Los cuerpos Pydantic son estrictos y rechazan campos extra. Nunca aceptan citas,
spans, hashes de fuente nuevos ni texto de reemplazo enviados por el navegador.
Crear exige el hash del CV revisado; decidir/generar exigen revisión actual dentro
del bloqueo. Generar exige además el hash exacto de la vista previa revisada.
Un hash de preview no es autenticación; ata los bytes generados al diff aprobado.

Errores: 404 recurso ausente, 409 revisión/integridad/conflicto/bloqueo, 413 tamaño,
422 contrato inválido, 500 almacenamiento/plataforma. No se devuelven mensajes del
SO, paths ni fuente en errores. Middleware aplica no-store y nosniff también a
respuestas de validación/error de CV y adaptación.

### Analizador y límites

`job_analysis` usa únicamente campos guardados de la oferta. Reutiliza `contains`,
`has_skill`, `norm` y `required_years` del matching y `requirement_kind` compartido
con preferencias. Un catálogo acotado reconoce tecnologías sin convertir su
aparición en obligación: solo marcadores explícitos o encabezados acotados la
clasifican; negación/conflicto queda unknown. Se conservan las citas originales.
Extrae también menciones de experiencia/nivel, idiomas y condiciones; su ausencia
no se rellena con suposiciones. No modifica el ranking ni acredita datos del perfil.

La detección ES/EN usa vocabulario del texto; empate/sin información recomienda ES.
Texto menor de 80 caracteres, sin requisitos detectados o con final truncado
explícito marca análisis parcial. Es una heurística: no demuestra que una descripción
larga sea completa. El texto guardado siempre queda disponible para revisión manual;
esta versión no implementa un editor de requisitos ni descarga descripciones externas.

El matching busca frases literales en secciones reconocidas de proyectos,
experiencia y habilidades. Exige cita presente tanto en texto extraído como en
fuente no comentado/no opaco. Una negación o aprendizaje en la sección excluye
conservadoramente **toda esa sección**, evitando acreditar listas bajo contexto
ambiguo. Esto produce falsos negativos intencionales. No suma años, no equipara
proyectos académicos con empleo y no interpreta educación como título terminado.
Idiomas, grados, condiciones y años quedan por revisar; no hay acreditación
semántica, equivalencias de herramientas ni inserciones desde el perfil.

### Transformaciones soportadas

- Reordenar viñetas completas mediante permutación estable, solo dentro de una lista.
- Destacar un término literal mediante `\textbf{...}` dentro de una viñeta plana.
- Omitir opcionalmente una viñeta completa sin coincidencias, previa aprobación.
- Informar brechas; no generan cambios. Reformulación automática deshabilitada.

Solo listas itemize planas de proyectos/experiencia/habilidades con texto sencillo.
No se editan encabezado/contactos, preámbulo, configuración, secciones educativas,
macros, inclusiones ni entornos opacos. Una lista con indicios de contacto, teléfono,
URL, etiquetas, formato interno, referencias contextuales o viñetas ambiguas no se
modifica. El documento completo debe superar validación estructural conservadora:
clase article; paquetes permitidos inputenc/fontenc/babel/geometry/xcolor/hyperref/
enumitem; comandos enumerados; documento único, llaves y entornos balanceados.
Clases/paquetes desconocidos, macros, condicionales, matemáticas y extracción parcial
bloquean generación. No es un intérprete TeX ni una garantía de compilación.

Todos los cambios empiezan pendientes. Pending/rejected conservan el fuente.
Reordenar una lista y destacar/omitir dentro de ella son alternativas superpuestas:
se debe rechazar una antes de generar. El diff se recalcula después de cada decisión.
Generar sin cambios aceptados crea una copia exacta del original (si es soportado).
Las brechas nunca se insertan. Los únicos bytes añadidos por una transformación
son la envoltura de formato explícita; no hay texto libre nuevo.

### Persistencia privada e integridad

`<JOBHUNTER_DATA_DIR>/cv/tailoring/`, carpeta 0700 y archivos 0600:

- `<plan_uuid>.source`: snapshot inmutable de **bytes exactos**, BOM/CRLF incluidos.
- `<plan_uuid>.json`: plan mutable con revisión y fuentes/metadatos fijados.
- `<artifact_uuid>.tex`: copia adaptada nueva y verificada.
- `<artifact_uuid>.audit`: procedencia, fechas, revisión y decisiones de generación.

Se reutilizan bloqueo RLock/flock y primitivas privadas de CvStore; M2.1 no cambia
su índice, esquema ni arquitectura. Directorio hijo abierto con O_NOFOLLOW y dir_fd;
lecturas rechazan symlinks/hardlinks/tipos no regulares. Publicación inmutable con
archivo temporal fsync y enlace exclusivo en el mismo directorio: no sobrescribe.
El plan mutable se sustituye atómicamente al final. Fallo antes de comprometerlo
retira nuevas copias; la revisión anterior sigue vigente. Las generaciones previas
se conservan privadas con su audit aunque cambien decisiones posteriores.

Toda lectura verifica SHA-256 del snapshot y reconstruye análisis/propuestas para
compararlos con el plan. Toda generación verifica de nuevo y descarga compara bytes
contra el resultado reconstruido. Cambios del maestro muestran aviso: se usa solo
la instantánea original, incluso después de sustituir/eliminar el maestro. Cambios
de cargo/empresa/descripción o eliminación de oferta bloquean decidir/generar; el
análisis conservado sigue consultable y una copia ya generada sigue descargable.

Cambiar decisiones invalida el enlace al último artefacto de ese plan y exige una
nueva generación revisada. Los documentos no pasan por SQLite, respaldo JSON,
public/dist, logs de contenido, compiladores, subprocess ni red. En Windows se
mantiene el fallo seguro POSIX de M2.1. No protege frente a otro proceso con control
de la misma cuenta, borrado forense o fallo físico. Una interrupción abrupta puede
dejar temporales/artefactos huérfanos privados: no se publican ni se borran planes
silenciosamente; conservar la carpeta para recuperación manual. No hay todavía
política/UI de retención o eliminación de planes.

Resultados y capturas sintéticas: [M22_INFORME.md](M22_INFORME.md).
