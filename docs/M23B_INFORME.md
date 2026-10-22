# JobHunter CL — M2.3B: preparación y auditoría del sandbox

**Resultado: perfil de sondas sintéticas preparado y probado en este host.
Frontera documental incompleta; PDF continúa `available:false`.**

Auditoría: 22 de octubre de 2026 UTC y horario de Chile.
No se ejecutó ningún motor LaTeX, no se generó PDF, no se abrieron CV personales,
no se instalaron paquetes del sistema ni se solicitaron privilegios de administrador.

## 1. Estado inicial y alcance

- Rama: `feat/local-first-fastapi-react`.
- HEAD inicial exacto: `e7c9c999c65ada85c843eb425782ede436eea6d9`; árbol limpio.
- Revisados `M23_INFORME.md`, `M23_PLAN.md`, `pdf_environment.py`, `pdf_service.py`,
  `pdf_validation.py`, `tailoring_store.py`, contratos PDF, diagnósticos y sus
  pruebas; también fixtures M2.2 y configuración de CI/frontend.
- Se mantiene la rama solicitada. No se modifica `main`, no hay push ni merge.
- La especificación M2.3B autoriza implementación y commits locales. `.git` es
  de solo lectura dentro de Codex; los commits se hacen fuera de esa restricción,
  con el mismo usuario, sin elevación administrativa.
- La primera ejecución completa de pytest dentro de Codex quedó esperando bajo
  sus restricciones; se detuvo exclusivamente ese proceso y se repitió fuera.
  Los resultados finales de pytest corresponden al host, sin omisiones.

## 2. Capacidades reales

Linux Mint **22.3 Zena**, base noble, x86_64, kernel `7.0.0-31-generic`, UID 1000.
Inventario mediante `command -v`, `dpkg-query`, `ldd`, `readelf`, sysctl y cgroups;
solo metadatos de herramientas/sistema, sin leer directorios personales.

| Herramienta/control | Resultado observado |
|---|---|
| Bubblewrap | `/usr/bin/bwrap`, 0.9.0, paquete `0.9.0-1ubuntu0.1`; sin setuid ni file capabilities observados |
| prlimit / unshare | Disponibles; util-linux `2.39.3-9ubuntu6.6` |
| cc / libc estática / readelf | GCC 13.3.0, libc6-dev `2.39-0ubuntu8.9`, binutils `2.42-4ubuntu2.10`; fixture compilada estáticamente y comprobada sin INTERP/DYNAMIC |
| systemd-run de usuario | Disponible, systemd `255.4-1ubuntu8.17`; gestor de usuario accesible fuera de Codex |
| cgroup v2 | Controladores cpu/memory/pids delegados en el gestor del usuario |
| user namespaces | `unprivileged_userns_clone=1`, AppArmor `restrict_unprivileged_userns=0`; seis namespaces distintos verificados dentro de la sonda |
| libseccomp | Runtime `libseccomp2` 2.5.5 presente; `libseccomp-dev` ausente; sin filtro seccomp propio implementado |
| pdfinfo | Presente, poppler-utils `24.02.0-1ubuntu9.9`; solo inspección de dependencias, nunca ejecutado sobre documentos |
| Docker | CLI presente; no se usa daemon ni socket, no se presume rootless |
| pdflatex / xelatex / lualatex / tectonic | Ausentes en PATH |
| podman / firejail | Ausentes en PATH |
| paquetes/fuentes TeX propuestos | texlive-latex-base/recommended/extra, lang-spanish, fonts-lmodern y cm-super-minimal ausentes |

Dependencias de lanzamiento observadas: bwrap carga libc, libcap, libselinux y
pcre2; prlimit carga libc y libsmartcols. Permanecen fuera de la raíz de la sonda:
solo se monta el binario de fixture estático. `pdfinfo` carga una superficie mucho
mayor: Poppler, fontconfig, FreeType, codecs y libcurl con dependencias transitivas
de red/SSH/TLS. Su disponibilidad **no acredita** un validador documental aislado.

Sonda separada de systemd, realmente ejecutada con éxito:

```sh
systemd-run --user --wait --pipe --collect \
  -p MemoryMax=64M -p TasksMax=8 -p CPUQuota=50% /usr/bin/true
```

Terminó exit 0, unidad transitoria recolectada, pico de memoria informado 1.2 MiB.
Esto demuestra aceptación de configuración por el gestor del usuario. **No se
probó agotamiento/enforcement** de esos límites ni se integró systemd con el
harness. No requiere instalar paquetes ni cambiar configuración global en este
host; sí implementar y probar el control por trabajo. No se cambiaron sysctls,
perfiles AppArmor, límites de la sesión ni unidades persistentes.

## 3. Perfil fijo y superficie de ejecución

`backend/services/pdf_sandbox.py` define un perfil inmutable
`m23b-synthetic-v1`. `scripts/audit_sandbox.py` solo acepta ocho escenarios Enum;
su CLI no acepta argumentos, rutas, texto, ejecutables ni documentos. No existe
endpoint que importe o ejecute el harness.

La preparación compila únicamente `scripts/fixtures/sandbox_probe.c`, código
sintético confiable del repositorio. El compilador corre con permisos normales
solo sobre esa fixture, nunca sobre TeX o código aportado por el usuario. Cada
ejecutable de herramienta tiene ruta absoluta fija; no se busca un runner en PATH.

Configuración efectiva por sonda:

- `prlimit`: CPU soft/hard 2 s, AS soft/hard 128 MiB, NOFILE 64, NPROC 4096,
  FSIZE 2 MiB, CORE 0. Timeout externo 3 s, más hasta 2 s para verificar drenaje.
- Namespaces **obligatorios**, sin variantes `try`: user, pid, net, ipc, uts,
  cgroup; mount namespace propio de Bubblewrap.
- `--disable-userns --assert-userns-disabled --cap-drop ALL`, sesión nueva y
  `--die-with-parent`; sin privilegios efectivos/permitidos/bounding y con
  `NoNewPrivs=1`, comprobados dentro de la sonda.
- Raíz tmpfs remountada de solo lectura; montajes únicos de fixture `/probe` y
  `/input` de solo lectura, `/proc` propio remountado de solo lectura, `/out`
  tmpfs de **1 MiB**. Directorio de trabajo `/out`; no se monta `/dev` ni `/tmp`.
- Sin `/usr`, `/etc`, HOME, SSH, navegador, SQLite, proyecto ni sockets del host.
  El proceso no hereda directorio de trabajo del host: se cambia a `/out`.
- Entorno vaciado; solo variables de fixtures descartables (puerto, nombres de
  sockets/archivo oculto e identidades de namespace), sin secretos ni HOME.
- stdin `/dev/null`; stdout/stderr pipes de diagnóstico de tamaño finito en la
  fixture fija. Descriptores restantes cerrados, sin terminal ni sockets heredados.
  Estos canales estándar son una excepción explícita a los montajes: no publican
  archivos ni aceptan salida de un compilador arbitrario.
- No shell, `preexec_fn`, descargas ni gestores de paquetes durante las sondas.
  El tmpfs se destruye al salir del namespace; TemporaryDirectory y ExitStack
  eliminan fixture, binario y sockets de prueba incluso ante falta de capacidad.

El hash de perfil numérico/configuración es
`12d7240ca6e3815e77af7e4255e505e8a13c1d0cfa87d842c6820823cf47dcd3`.
No basta ese hash aislado: cada evidencia registra además hashes de harness,
fuente C, binario resultante y herramientas. Cambiar mounts/código exige repetir
la auditoría y revisar todos esos identificadores.

## 4. Resultados reproducibles

Evidencia real: [host Mint](evidencias/m23b/mint-host.json) y
[entorno restringido de Codex](evidencias/m23b/codex-restricted.json).
Ambos reportes mantienen `document_verified:false`. Son registros para revisión
humana; la aplicación no los carga ni confía en ellos como certificados.

| Caso | Resultado en host | Qué prueba y su límite |
|---|---|---|
| basic | exit 0 | Ejecuta binario estático, seis namespaces diferentes al host, capacidades cero, NNP, sin HOME ni fd extra; nuevos userns rechazados |
| filesystem | exit 0 | Lee `/input`; no lee fixture existente no montada; `/`, input y binario tienen ST_RDONLY; rechaza escritura fuera de `/out`, permite resultado dentro |
| network | exit 0 | Namespace net distinto, sin rutas IPv4; no conecta al listener TCP loopback sintético ni sockets UNIX de ruta/abstracto del host |
| limits | exit 0 | Rlimits soft/hard exactos; malloc de 192 MiB rechazado sin tocar memoria; apertura acotada de fd termina EMFILE |
| quota | exit 0 | statvfs indica <=1 MiB; escritura en varios archivos acotada a 2 MiB termina ENOSPC con total <=1 MiB; prueba cuota agregada de bytes, no solo FSIZE |
| cpu | código 137, ~2.01 s | RLIMIT_CPU termina bucle de una sola tarea antes del timeout externo; bwrap propaga SIGKILL como 128+9 |
| timeout | SIGKILL, ~3.00 s | Supervisor mata grupo de bwrap al alcanzar duración; recoge proceso y drena pipes |
| descendant | SIGKILL, ~3.00 s | Un único hijo crea otra sesión, confirma arranque y conserva stdout abierto; tras matar monitor se recibe EOF dentro del plazo y no espera los 30 s del hijo |
| falta de herramienta / frontera fallida | pruebas unitarias pasan | No inicia procesos si falta herramienta; fallo básico impide todas las sondas posteriores; nunca fallback al host |
| temporales | eliminado | Se comprueba desaparición de directorio tras éxito y rechazo de socket de fixture |

En Codex, crear el primer socket de fixture falla EPERM. El harness declara
`blocked / fixture_socket_unavailable`, no ejecuta sondas y registra limpieza.
Esa ejecución restringida no acredita ninguna propiedad del sandbox; se incluye
para demostrar cierre controlado. Las ocho sondas sí se ejecutaron fuera de
Codex con el mismo usuario, sin sudo ni cambios de sistema.

Diagnósticos corregidos durante desarrollo, sin ocultarlos como éxitos:

- NPROC=512 impidió crear namespaces: había 1539 hilos del UID en el host.
  Una sonda `true` sin ese límite funcionó y con él falló EAGAIN. Se fija 4096;
  es un techo compartido del usuario, **no protección agregada por trabajo**.
- El rechazo de nuevo userns fue ENOSPC, además del EPERM previsto. Ambos indican
  rechazo; se conserva la comprobación obligatoria `assert-userns-disabled`.
- Escribir el ejecutable activo devolvió ETXTBSY. Se comprueban además flags
  ST_RDONLY para evitar confundir ese error con un montaje de solo lectura.
- Se corrigió la interpretación de señal de Bubblewrap (137 frente a -9).
- Revisión independiente encontró omisiones demasiado amplias por stderr
  `bwrap:`. Ahora solo falta de herramientas/sockets o un EPERM de namespace
  exacto permite skip; errores desconocidos, montaje, opciones y compilación
  fallan las pruebas. Regresiones específicas cubren esa distinción.

## 5. Integración y contrato de autorización

`pdf_environment.capabilities()` consulta pasivamente `document_readiness()`;
el contrato interno enumera lo que impide auditar documentos y liga el perfil a
su SHA-256. La disponibilidad HTTP sigue siendo el literal falso original,
con el mismo código, razones y esquema. `PdfService` conserva validación bajo
lock de revisión, snapshot, decisiones y bytes M2.2 antes de registrar bloqueo.

No hay runner documental, worker ni importación del harness desde HTTP. Ningún
JSON de auditoría, booleano, variable de entorno, herramienta detectada o entrada
del cliente puede habilitar PDF. Se prueba explícitamente con variables de
habilitación ficticias. No se alteran API, interfaz React ni descargas M2.2.

Cuando exista un adaptador documental, deberá recibir exclusivamente bytes de
`TailoringStore._verified_artifact` bajo lock, con plan/revisión/hash, y copiar
esos bytes a staging privado inmutable antes de liberar el lock. Nunca recibirá
rutas, argv ni fuente del cliente. La acreditación documental debe comprobar el
perfil realmente aplicado, versiones/hashes del runtime y árbol TeX, controles
agregados por ejecución, validador y evidencia M2.3C vigente. **No se implementa
un cargador de attestations sin autenticación ni un estado `verified=true` vacío.**

## 6. Dependencias propuestas, sin instalar

Candidato inicial: **pdfLaTeX de TeX Live** para el subconjunto `article` y texto
latino ES/EN admitido por M2.2. Es una decisión propuesta para M2.3C, no una prueba
de compatibilidad. Unicode arbitrario/emoji no queda resuelto: las fixtures M2.2
incluyen emoji. No se deben perder glifos silenciosamente ni sustituir maquetación;
M2.3C deberá bloquear incompatibilidad con diagnóstico o justificar otro motor.
LuaLaTeX añade soporte Unicode/fuentes, pero también runtime Lua, cachés y mayor
superficie; no se propone como fallback automático. No se usa Tectonic con
descarga de bundles durante ejecución.

Árbol mínimo lógico a cerrar: motor y cargador/bibliotecas exactas; formato
pdflatex precompilado; `article`, núcleo LaTeX, inputenc/fontenc, babel inglés y
español, geometry, xcolor, hyperref, enumitem y sus dependencias transitivas;
TFM/encodings/mapas y fuentes Type 1 (Computer Modern/CM Super para T1 o selección
Latin Modern explícitamente aprobada). Los formatos/mapas se preparan de antemano,
sin mktexpk/mktextfm/mktexfmt, tlmgr, apt ni font discovery del HOME al compilar.
No existe todavía manifiesto mínimo por archivo: exige inspeccionar paquetes
aprobados y probar documentos sintéticos con ese árbol, sin montar `/usr` entero.

Metadatos apt locales: familias TeX propuestas candidatas
`2023.20240207-1`; fonts-lmodern `2.005-1`; cm-super-minimal `0.3.4-17`.
No se refrescó índice ni se descargaron paquetes. Comandos **propuestos, no
ejecutados**, sujetos a autorización futura:

```sh
# Revisar primero resolución, tamaño y cambios, sin instalar.
apt-get --simulate --no-install-recommends install \
  texlive-latex-base texlive-latex-recommended texlive-latex-extra \
  texlive-lang-spanish fonts-lmodern cm-super-minimal

# Solo después de aprobación explícita y fuera de esta fase:
apt-get --no-install-recommends install \
  texlive-latex-base texlive-latex-recommended texlive-latex-extra \
  texlive-lang-spanish fonts-lmodern cm-super-minimal

# Solo si se aprueba generar filtros seccomp con libseccomp:
apt-get --simulate --no-install-recommends install libseccomp-dev
apt-get --no-install-recommends install libseccomp-dev
```

La instalación real requiere intervención administrativa posterior; no se pide
ahora. TeX instala herramientas globales y ejecuta mantenimiento de formatos/mapas.
`latex-extra`, por enumitem, arrastra más que el mínimo lógico: paquetes Java,
PDFBox, preview y texlive-pictures según apt-cache. `--no-install-recommends`
reduce recomendaciones, no elimina esas dependencias obligatorias. Debe aprobarse
ese coste o preparar un bundle reducido, con versiones/hashes/licencias. Instalar
no autoriza montar toda la distribución ni ejecutar un documento.

Fuentes consultadas con Context7 CLI fuera de Codex y contrastadas con `bwrap
--help` 0.9.0 y metadatos locales: [Bubblewrap, namespaces y montajes](https://github.com/containers/bubblewrap/blob/main/_autodocs/api-reference/bwrap.md),
[código Bubblewrap](https://github.com/containers/bubblewrap/blob/main/bubblewrap.c),
[Kpathsea, restricciones de nombres](https://tug.org/texlive/Contents/live/texmf-dist/doc/kpathsea/kpathsea),
[Web2C, shell escapes](https://tug.org/texlive/devsrc/Master/texmf-dist/doc/web2c/web2c).
En M2.3C se deberán fijar `--no-shell-escape`, `shell_escape=f`,
`openin_any=p` y `openout_any=p` como defensas adicionales verificadas contra la
versión instalada; estas opciones de TeX no sustituyen los controles del kernel.

## 7. Riesgos y propiedades pendientes

No se acredita una frontera completa por haber pasado namespaces y sondas:

- **Recursos agregados:** AS y CPU son por proceso; NPROC comparte UID. Falta
  integrar cgroup MemoryMax/MemorySwapMax/TasksMax/CPUQuota y comprobar límites,
  fallos del gestor, cancelación y limpieza de la unidad. No se ejecutan fork
  bombs, agotamiento global de RAM ni pruebas destructivas del host.
- **Escritura:** tmpfs limita bytes de la sonda; no se ha diseñado una cuota
  explícita de inodos/metadatos/memfd/SHM ni salida/log documental. Se requiere
  memoria agregada y política de archivos/contenido/tamaño antes de exportar.
- **Syscalls/kernel:** no hay filtro seccomp propio. procfs de solo lectura aún
  expone interfaces/información del kernel. No se prueban exploits, ptrace contra
  el host, dispositivos, eBPF ni otros mecanismos de escape. No declarar seguros.
- **Red:** se prueban fixtures locales IPv4 y UNIX de ruta/abstracto. No se
  contacta internet/DNS ni servicios preexistentes; no se ha probado una matriz
  completa IPv6, familias socket y syscalls. Namespace aislado y falta de rutas
  son evidencia acotada, no prueba exhaustiva de ausencia de canales laterales.
- **Descendientes:** se prueba un hijo setsid que conserva stdout tras timeout.
  No demuestra todas las formas de daemonización, éxito normal con hijos,
  cancelación HTTP ni muerte inesperada del supervisor. Esas pruebas y cgroup
  kill/reap por trabajo siguen requeridas antes de TeX.
- **Confianza:** se confía en kernel y herramientas instaladas y en la cuenta
  local. Los hashes no autentican frente a otro proceso que controle esa cuenta.
  Una modificación de perfil/binarios/kernel/configuración invalida la evidencia.
- **Documentos:** faltan runtime offline cerrado, runner de entrada M2.2/M2.3,
  extracción segura de salida, validador PDF aislado y publicación atómica.
  pdf_validation sigue siendo inspección de envoltura, sin validez estructural.

## 8. Verificación final y criterio M2.3C

Resultados locales reales sobre el código final:

| Comando | Resultado |
|---|---|
| `.venv/bin/python -m pytest -q` fuera de Codex | **307 passed**, 15.58 s; sin skips; una advertencia preexistente Starlette/httpx |
| `npm test` en frontend | **47 passed**, 8 archivos |
| `npm run typecheck` | exit 0 |
| `npm run build` | exit 0, 40 módulos |
| `git diff --check` | exit 0 |
| `.venv/bin/python -m scripts.audit_sandbox` en host | exit 0, ocho sondas pasan, temporales eliminados |
| mismo comando dentro de Codex | exit 1 controlado, sockets de fixture no disponibles, cero sondas ejecutadas, temporales eliminados |

Las regresiones existentes M2.1/M2.2/M2.3 pasan. No se repite smoke visual porque
la UI no cambió. No se hizo smoke TeX, inspección de PDF ni instalación.

M2.3C requiere: aprobar dependencias y fijar el bundle; implementar y demostrar
controles agregados y política de syscalls; extender pruebas de procesos y salidas;
crear runner/validador documentales con entrada exclusivamente verificada;
generar y revisar documentos sintéticos ES/EN (incluidos glifos incompatibles);
documentar evidencia del conjunto completo. Hasta cumplir y revisar esas etapas,
**PDF permanece deshabilitado**. M2.3B prepara el perfil y prueba solo las
propiedades enumeradas; no convierte ese perfil parcial en un sandbox documental.
