# JOBHUNTER CL — M2.3

**Resultado: infraestructura segura bloqueada; M2.3 NO está completamente finalizado.**
No existe un PDF real generado en aislamiento demostrado. No se ha habilitado
compilación, sustituido maquetación ni ejecutado documentos con permisos del usuario.
Fecha de auditoría: 22 de octubre de 2026 (UTC).

## 1. Auditoría inicial

- Repositorio HikariLucy/JobHunterCL, rama `feat/local-first-fastapi-react`.
- HEAD inicial y remoto consultado en lectura: `f7f425a92e73b04010986645cf095b3ba8b79588`.
  Árbol inicial limpio. No se modificó main, no hubo push ni merge.
- Revisados `M22_INFORME.md`, `CV_INTEGRACION.md`, contratos `TailoringPlan` y
  `TailoringPreview`, `tailoring_engine.py`, `tailoring_store.py`, `cv_store.py`,
  parser, router, `TailoringPage.tsx`, pruebas y `.github/workflows/tests.yml`.
- CI disponible: Python 3.12/pytest y Node 22/Vitest/build, timeout 15 minutos.
  No se disparó un workflow remoto; los resultados de este informe son locales.
- La revisión del plan aumenta al decidir y al generar `.tex`. Su hash de preview
  incluye bytes UTF-8/BOM/CRLF conservados. La descarga reconstruye las decisiones
  y compara bytes; se extrajo esa verificación para compartirla con PDF.
- No se abrieron/importaron los CV personales ES/EN. Todas las fixtures y capturas
  son sintéticas; no se usó la carpeta de datos real para Chromium.

## 2. Evaluación del entorno, antes de implementar

Entorno observado: Linux x86_64, base Ubuntu 24.04, usuario UID 1000 no root.

| Capacidad | Observación |
|---|---|
| pdflatex, xelatex, lualatex, tectonic | Ausentes en PATH |
| bubblewrap | `/usr/bin/bwrap`, versión 0.9.0 |
| unshare, prlimit | Presentes |
| Docker | CLI presente; la sonda dentro de Codex no accede al socket. No se presume disponibilidad fuera de Codex ni rootless |
| podman, firejail | Ausentes |
| pdfinfo | Presente; NO ejecutado sobre PDF no confiable |
| user namespaces | sysctl permite creación; AppArmor restrict_unprivileged_userns=0 |
| paquetes/fuentes TeX cerrados y cuotas | No preparados ni verificados |

Sonda **sin documentos**:

```
bwrap --unshare-all --die-with-parent --new-session \
  --ro-bind /usr /usr --symlink usr/bin /bin \
  --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
  --proc /proc --dev /dev --tmpfs /tmp -- /bin/true
```

Dentro de las restricciones de Codex falló la creación de socket NETLINK_ROUTE.
Fuera, mediante ejecución autorizada de la sonda mínima, terminó con **exit 0**.
Una sonda inicial sin rutas del cargador falló con `execvp: No such file or directory`;
al incluir `/lib` y `/lib64` se pudo ejecutar `true`. Estos resultados solo prueban
esa sonda: **NO prueban aislamiento de compilación**, cuotas, seccomp, paquetes,
lecturas del host, sockets o resistencia a escape. No se probó ningún escape.

No se instaló ninguna dependencia del sistema/global ni se descargaron paquetes
TeX/imágenes. Context7 CLI consultó documentación oficial actual de FastAPI para
respuestas y errores; no recibió secretos ni documentos.

## 3. Modelo de amenazas y frontera

Se considera todo TeX no confiable: lectura de HOME/SSH/browser/SQLite, inclusiones,
escritura arbitraria, shell escape, red/DNS/sockets, fork bombs y agotamiento de
CPU/RAM/disco, PDFs corruptos y filtraciones en logs. M2.2 limita transformaciones,
pero su gramática no constituye un sandbox.

Alternativas evaluadas:

- **Bubblewrap**: puede crear namespaces, pero faltan runner auditado, raíz mínima
  de paquetes offline, límites agregados de recursos y cuota de escritura. La sonda
  montó `/usr` solo para ejecutar `true`; no es un perfil propuesto para compilar.
- **Contenedor rootless**: CLI Docker no acredita daemon rootless, imagen cerrada,
  ausencia de red, límites ni mounts seguros. Podman está ausente.
- **Ejecución directa con timeout/no-shell-escape**: descartada por insuficiente.

La frontera efectiva de esta entrega es **no iniciar procesos documentales**.
`pdf_environment` inventaría nombres; ni binarios presentes, variables de entorno,
PATH ni un booleano del cliente habilitan compilación. Los contratos usan literal
`available:false`. No hay worker, proceso hijo, cola ni temporal de compilación que
cancelar. Esto evita ejecución insegura; no prueba un sandbox operativo.

No protege frente a otro proceso que ya controle la misma cuenta, alteración
coordinada de todos los archivos de trazabilidad, fallos físicos o borrado forense.
SHA-256 prueba correspondencia, no autenticidad frente al propietario de la cuenta.

## 4. Arquitectura y API

- `pdf_contracts.py`: cuerpos y respuestas estrictos, sin fuente ni paths.
- `pdf_environment.py`: capacidades siempre bloqueadas, razones concretas.
- `pdf_diagnostics.py`: diagnósticos sin expandir ni repetir contenido del CV.
- `TailoringStore._verified_artifact`: verificación compartida y gramática M2.2.
- `pdf_service.py`: comprobación atómica de origen, registro de bloqueo, estado y
  rechazo de descarga. No contiene un backend simulado ni subprocess oculto.
- `pdf_validation.py`: inspección preliminar de envoltura y hash, sin publicación.
- `PdfPanel.tsx`: carga, error/reintento, bloqueo, metadatos de intento y `.tex`
  conservado. No ofrece enlaces/visor PDF ficticios.

| Método | Ruta `/api/tailoring` | Contrato/comportamiento |
|---|---|---|
| GET | `/pdf/capabilities` | motivos, inventario sin rutas, `available:false` |
| POST | `/plans/{id}/pdf` | `expected_revision`, `expected_tex_sha256`; valida y registra, devuelve 503 |
| GET | `/plans/{id}/pdf?expected_revision=N` | `not_generated` o `blocked`, plan/revisión/hash/fecha/ID |
| GET | `/plans/{id}/pdf/download?expected_revision=N` | 409: no existe un PDF verificado |

404 plan ausente; 409 revisión/hash/integridad/estado; 422 solicitud inválida;
500 almacenamiento/POSIX; 503 sandbox no verificado. Timeout, recursos, proceso
fallido y PDF inválido todavía no tienen ruta de ejecución real. No se fingen esos
estados en un servicio que jamás inicia compilación.

Middleware conserva `Cache-Control:no-store` y `X-Content-Type-Options:nosniff`.
Se reprodujo y corrigió la reflexión de campos extra en 422: las rutas CV/tailoring
ahora responden un mensaje fijo sin serializar body/input/errores documentales.
Otros endpoints mantienen su manejo habitual.

## 5. Integridad y persistencia

La solicitud se resuelve bajo RLock/flock compartidos: carga y valida plan,
identidad, snapshot SHA-256, propuestas canónicas, revisión actual y oferta;
exige artefacto generado, compara hash solicitado y real, reconstruye exactamente
los bytes aprobados y vuelve a aplicar gramática conservadora al adaptado.
No vuelve a generar contenido libre ni cambia decisiones rechazadas.

`JOBHUNTER_DATA_DIR/cv/tailoring/` conserva:

- `<attempt_uuid>.pdf-audit`: intento bloqueado inmutable, publicación exclusiva.
- `<plan_uuid>.pdf-status`: último estado mediante sustitución atómica.

Se reutilizan descriptores relativos, O_NOFOLLOW, archivos regulares sin hardlinks,
0700/0600, fsync y publicación existente M2.2. Se comprueba correspondencia de estado
con historial. Ausencia/corrupción del historial o JSON inválido bloquea con 409;
fallos del SO y enlaces se ocultan con error privado. Fallo de commit retira el
intento nuevo y conserva el estado anterior. No se promete durabilidad física.

Cada intento incluye plan, revisión, hash `.tex`, UUID, fecha UTC y estado. Como no
hay ejecución, hash PDF/compilador/versión/páginas son null. Decisiones nuevas o
nueva generación invalidan su presentación como actual. Se conserva el historial
sin borrado automático; no hay UI de retención. Interrupción abrupta puede dejar
un registro huérfano privado; no se publica como actual. El registro no contiene
fuente, rutas personales, stdout/stderr ni secretos. No pasa por SQLite o backups
JSON; `.pdf`, `.pdf-audit`, `.pdf-status` y datos privados están ignorados por Git.

## 6. Generación y validación PDF: límites explícitos

**No se eligió/habilitó un motor real.** Para la gramática actual article,
pdfLaTeX offline es un candidato más acotado que instalar árboles de XeLaTeX/LuaLaTeX;
su compatibilidad efectiva debe probarse con paquetes y fuentes fijados. Tectonic
requeriría impedir descargas y fijar bundle/cache. Ninguna elección vuelve seguro TeX.
No se usó HTML u otro render para reemplazar silenciosamente la fuente aprobada.

`inspect_envelope` rechaza vacío, cabecera/EOF no reconocibles y exceso de tamaño
(defecto 10 MB), calcula SHA-256. Devuelve `structurally_verified:false` y páginas
null incluso ante una envoltura reconocible. **No valida un PDF completo** ni lo
publica. No se cuenta `/Page` con regex como si fuera un conteo confiable.

Pendientes: ejecución controlada, límites CPU/RAM/procesos/espacio/tiempo, cierre
con terminación de hijos, salida única esperada, parser PDF aislado, 1..20 páginas,
comprobación de archivos inesperados, persistencia exitosa, hash PDF, versión y
configuración fija del compilador, comparación de páginas y revisión visual privada.
No se afirma equivalencia visual. No existen PDF publicados que retirar o conservar.

## 7. Resultados reales de sandbox

- Sonda bwrap + true: exit 0 fuera de Codex; no se usó TeX.
- PDF sintético real en sandbox: **OMITIDO/BLOQUEADO**.
- Pruebas de lectura del host, escritura externa, red/DNS/sockets y límites de
  recursos en sandbox: **OMITIDAS**, porque no hay frontera documental verificada.
- No se ejecutó ningún ataque fuera de aislamiento ni un compilador falso para
  declarar funcionamiento real. M2.3 continúa incompleto.

## 8. Verificación ejecutada

| Verificación | Resultado local final |
|---|---|
| `.venv/bin/python -m pytest -q` | **289 PASS**, 1 warning de deprecación Starlette/httpx preexistente |
| `cd frontend && npm test` | **47 PASS**, 8 archivos |
| `npm run typecheck` | exit 0 |
| `npm run build` | exit 0; Vite 8.3.5, 40 módulos |
| `git diff --check` | exit 0 |
| Chromium 153.0.8010.52 | flujo sintético backend real, escritorio y móvil oscuro |
| cierre servidor sintético | application shutdown complete, exit 0 y limpieza temporal |
| revisión independiente | sin hallazgos críticos/importantes; inconsistencia menor de 500/409 reproducida y corregida con regresión |

Las primeras ejecuciones TestClient dentro de Codex quedaron esperando; se cerraron
solo esos procesos propios y se repitió fuera con timeout. No se alteró la aplicación
que el usuario ya tenía abierta. Las suites externas finalizaron en segundos.
Hubo fallos intencionales al añadir UI/validador, reproducción de 422 que reflejaba
input y auditoría ausente/estado corrupto que daban 500; se corrigieron. La ejecución
inicial de las pruebas API no produjo evidencia RED al bloquearse TestClient; no se
presenta como una secuencia TDD completa. No quedan pruebas fallidas conocidas en
las suites finales. No se instalaron dependencias para eliminar el warning.

### Matriz de los 20 requisitos de prueba

| N | Requisito | Evidencia/estado |
|---|---|---|
| 1–2 | `.tex` ES y EN | PASS validación de origen y bloqueo, sin PDF real |
| 3 | generación con sandbox | OMITIDA; no runner seguro/motor |
| 4 | bloqueo sin sandbox | PASS, incluso con todos los nombres de motores simulados presentes |
| 5–6 | fuente alterada/revisión obsoleta | PASS 409 antes del entorno |
| 7 | sin artefacto/aprobaciones válidas | PASS rechazo sin artefacto y decisiones alteradas; M2.2 conserva copia sin cambios aprobados según su contrato |
| 8 | macros peligrosas/inclusiones | PASS diagnósticos y regresión M2.2, sin ejecución |
| 9–11 | lectura host/escritura/red | PASS rechazo estático de macros sintéticas; escape real OMITIDO |
| 12–13 | timeout/memoria/espacio | OMITIDOS en compilación; no proceso que limitar |
| 14 | PDF vacío/corrupto/grande | PASS rechazo preliminar de envoltura; validación estructural real OMITIDA |
| 15 | hashes origen/resultado | PASS hash origen/envoltura sintética; hash de PDF real OMITIDO |
| 16 | aislamiento entre planes | PASS estados/revisiones y registros separados; procesos de compilación OMITIDOS |
| 17 | fallos de proceso | PASS fallo de publicación e historial corrupto/ausente; muerte de compilador OMITIDA |
| 18 | concurrencia/cancelación/cierre | PASS solicitudes bloqueadas concurrentes y cierre de servidor; cancelación de hijos OMITIDA |
| 19 | regresión M2.1/M2.2 | PASS suite completa |
| 20 | navegación/escritorio/móvil | PASS Chromium + pruebas navegación Vitest |

Pruebas nuevas en `test_pdf_api.py` y `test_pdf_validation.py`; fixtures TeX en
`test_tailoring_engine.py`. Ningún PASS parcial se interpreta como compilación real.

## 9. Evidencia visual sintética

Servidor reproducible: `.venv/bin/python scripts/smoke_m23.py`, puerto 8873,
SQLite y CV sintéticos en TemporaryDirectory, acceso log desactivado, sin datos reales.
Requiere frontend compilado y las dependencias de desarrollo ya existentes.

- [Escritorio 1440×1100](evidencias/m23/escritorio.png).
- [Móvil oscuro 390×844](evidencias/m23/movil-oscuro.png).

Chromium comprobó PDF deshabilitado, razones visibles, revisión 3 y hash `.tex`,
descarga `.tex` 200 con no-store y término aprobado, POST PDF 503, navegación
Adaptar → Mis CV sin reactivar onboarding. En móvil `scrollWidth=390`, `innerWidth=390`.
El onboarding inicial sin perfil apareció correctamente; se descartó solo en la
sesión sintética para continuar la prueba. No se capturó ningún documento personal.

## 10. Compatibilidad

No se amplió la gramática M2.2: article, paquetes explícitos, lista de comandos y
entornos document/itemize; sin inclusiones, definiciones, tablas o macros libres.
Diagnósticos diferenciados: clase, paquete, macro, entorno, archivo externo,
estructura y motor ausente. No garantizan que una plantilla aceptada compile.
Los maestros personales ES/EN siguen sin evaluar y requieren elección del usuario.
Windows mantiene bloqueo POSIX del gestor; el resto de JobHunter continúa disponible.

## 11. Commits locales

1. `4d287ac` — contratos, verificación de procedencia, bloqueo, registros privados,
   errores sin contenido, diagnósticos, inspección preliminar y pruebas backend.
2. `c1a195f` — `feat(cv): show safe PDF availability and synthetic review evidence`
   — tarjeta React, pruebas, script y capturas sintéticas (hash en `git log`).
3. Commit documental `docs(m23): record blocked compilation and verified local results`
   — este informe, README, ROADMAP y manual. Su propio hash se obtiene con
   `git log --oneline f7f425a..HEAD`.

Todos locales en la rama indicada; sin push/merge.

## 12. Habilitación posterior y pendientes M3

Solicitar aprobación explícita antes de instalar motor/paquetes o herramientas de
sistema. Primero preparar raíz offline mínima y runner sin privilegios con montajes
cerrados, entrada solo lectura, salida privada con cuota, red/DNS/sockets bloqueados,
capabilities mínimas y recursos agregados acotados. Verificar esos controles con
pruebas sintéticas **dentro** de esa frontera y comprobar cierre/cancelación.
Después ejecutar PDF sintético ES/EN real, validar estructura/páginas en aislamiento,
persistir hashes y configuración atómicamente y habilitar descarga/visor por API
privada. Publicar evidencia real antes de marcar M2.3 terminado.

Para M3: asociación de documentos verificados con postulaciones y política/UI de
retención; siguen fuera de alcance envío, automatización de portales y cuentas.
No trasladar la ejecución insegura a M3 como si este bloqueo estuviera resuelto.
