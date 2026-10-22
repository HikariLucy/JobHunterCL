# Integración local de currículums LaTeX

M2.1 implementa gestión y extracción textual. La adaptación, PDF y envío son futuros.

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

## Contratos M2.2

Se conservan `JobAnalysis`, `Requirement`, `Evidence`, `Suggestion`, `TailoringPlan`,
`Tailor` y `validate_suggestion`; `TailoringPlan.cv_sha256` permite fijar una revisión
para la siguiente fase. M2.2 deberá exigirlo al generar planes y preservar un
snapshot fuente por cada plan antes de permitir sustituir/eliminar documentos.
No hay endpoints activos de adaptación o render.

Flujo futuro: oferta → requisitos obligatorios/deseables/desconocidos → selección
ES/EN revisable → comparar evidencia → propuestas trazables → copia `.tex` distinta
→ PDF en aislamiento con controles específicos → documento asociado a postulación.
Toda modificación citará el CV original o confirmación expresa del usuario. Un
requisito sin respaldo será brecha, nunca habilidad inventada. El validador actual
solo comprueba citas literales en texto extraído y gaps sin salida: no demuestra
equivalencia semántica ni autoriza aplicar sugerencias. Deben validarse también
hashes, spans y correspondencia fuente al implementar generación.

La modalidad remota por sí sola no decide el idioma. Una futura compilación requiere
sandbox propio, límites de recursos/tiempo y acceso a archivos/red restringido,
sin shell escape; detectar un compilador instalado no basta para habilitarla.

Evidencias y verificación: [M21_INFORME.md](M21_INFORME.md).
