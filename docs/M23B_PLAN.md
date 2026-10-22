# M2.3B — diseño y plan de ejecución

Especificación vinculante: solicitud M2.3B del usuario. Trabajo autorizado en
`feat/local-first-fastapi-react`, HEAD inicial `e7c9c99`, árbol limpio. Ejecución
local en esta rama por indicación expresa; sin worktree adicional, push ni merge.

Objetivo: preparar y medir un perfil de sondas; nunca ejecutar TeX ni habilitar PDF.
Se descarta montar `/usr` o el proyecto completo y se descarta ejecutar comandos
aportados por HTTP. Bubblewrap es el mecanismo elegido para la sonda mínima;
systemd de usuario se evalúa separadamente para futuros límites agregados.

## Perfil

Raíz tmpfs remountada de solo lectura. Montajes explícitos: ejecutable estático
de fixture, entrada sintética de solo lectura, procfs privado de solo lectura,
salida tmpfs de 1 MiB. Sin dev, HOME, sockets ni bibliotecas del anfitrión.
Namespaces obligatorios user/pid/net/ipc/uts/cgroup; capacidades eliminadas,
nuevos user namespaces deshabilitados, entorno vacío, sesión nueva y muerte con
el padre. prlimit fija CPU 2 s, AS 128 MiB, NOFILE 64, NPROC 4096, FSIZE 2 MiB,
CORE 0. Timeout externo 3 s. Estos rlimits son por proceso/UID y no sustituyen
controles agregados por trabajo. stdout/stderr son canales de diagnóstico de la
sonda fija, nunca salida documental; no se acepta código arbitrario.

## Pasos

- [x] Contrato interno inmutable: perfil, hash y requisitos documentales pendientes;
  integrarlo en `pdf_environment` sin cambiar contrato HTTP ni `available:false`.
  Pruebas de perfil y rechazo de habilitación por entorno antes de implementar.
- [x] Harness `scripts/audit_sandbox.py`, fixture C estática y pruebas reproducibles.
  Ejecutar primero sonda básica; si falla, detener las demás y declarar pendiente.
  Probar lectura/escritura, red contra listener local sintético, sockets UNIX de
  fixture, rlimits acotados, cuota tmpfs y un solo descendiente con setsid.
  No fork bombs, conexiones externas, TeX ni documentos personales.
- [x] Ejecutar la auditoría dentro y fuera de Codex, registrar resultados y hashes.
  Fallos de capacidad se informan como bloqueados, sin fallback al anfitrión.
- [x] pytest completo, Vitest, typecheck, build, diff --check; revisión de cambios,
  informe `M23B_INFORME.md`, commits locales pequeños.

## Revisión y límites

Revisar especialmente namespaces opcionales, descriptores heredados, montajes
amplios, timeout con descendientes en otra sesión, falta de herramientas y falsa
certificación por un archivo JSON. Ningún reporte o booleano autorizará PDF.
Faltan runner documental y validación aislada; paquetes/font tree cerrado;
controles agregados integrados y probados; política seccomp; pruebas M2.3C.

La especificación del usuario autoriza implementar lo justificable y documentar
lo restante; se continúa sin solicitar nuevamente aprobación del mismo alcance.

Decisión de auditoría: NPROC inicial 512 impedía crear namespaces porque el host
tenía 1539 hilos del mismo UID. Se cambia a 4096, verificable pero insuficiente
como límite por trabajo; cgroup pids.max sigue pendiente. Dentro de Codex la
creación de sockets de fixture falla EPERM; declarar capacidad ausente.

Verificación final: 307 pytest sin omisiones en host, 47 Vitest, typecheck/build y
diff --check correctos. Ocho sondas host pasan; dentro de Codex cero sondas por
capacidad ausente con limpieza demostrada. Revisión independiente corrigió skips
demasiado amplios mediante pruebas de errores desconocidos; informe y JSON en
`docs/M23B_INFORME.md` y `docs/evidencias/m23b/`. No se acredita seguridad documental.
