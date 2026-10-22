# M2.3 — plan incremental y decisiones

## Alcance autorizado

Implementar el flujo PDF desde copias aprobadas M2.2. La especificación del usuario
es el diseño de referencia. En ausencia de aislamiento demostrable, entregar
infraestructura bloqueada, sin compilación real ni fallback. Trabajar en la rama
indicada y crear commits locales, sin instalar herramientas del sistema.

## Auditoría previa

HEAD inicial f7f425a, rama feat/local-first-fastapi-react, árbol limpio.
Revisados M22_INFORME, CV_INTEGRACION, contratos, parser, motor, almacenes y router.
CI tests.yml ejecuta pytest y Vitest/build. M2.2 preserva snapshot y reconstruye
las decisiones; genera una revisión nueva incluso para una copia sin cambios.

Capacidades observadas: bwrap 0.9.0, unshare, docker, prlimit y pdfinfo presentes;
pdflatex/xelatex/lualatex/tectonic/podman/firejail ausentes. Sonda bwrap con true:
dentro de Codex falla NETLINK_ROUTE; fuera, con cargador /lib y /lib64, exit 0.
Esto no prueba un sandbox para documentos. No hay compilador ni perfil auditado,
árbol cerrado de paquetes, cuotas de escritura o pruebas de escape. No se instala.

## Diseño

- pdf_contracts: contratos estrictos de capacidades, solicitud y estado trazable.
- pdf_environment: inventario pasivo sin ejecutar herramientas, siempre bloqueado;
  no confundir ejecutables presentes con garantías ni permitir habilitación por env.
- tailoring_store: verificación atómica de snapshot, revisión, artefacto y decisiones;
  misma primitiva compartida por descarga y solicitudes PDF.
- pdf_service: validación previa, diagnóstico conservador, registro privado atómico
  de intentos bloqueados e historial; estado y descarga fallan cerrado.
- pdf_validation: comprobación preliminar de bytes, límite y hash; no es un parser
  ni autoriza publicar. Validación estructural/páginas queda pendiente de aislamiento.
- API: GET /pdf/capabilities; POST y GET /plans/{id}/pdf; GET /plans/{id}/pdf/download.
  Identificadores y revisiones, nunca fuente o rutas arbitrarias. 503 sin aislamiento,
  404 ausente, 409 revisión/hash/estado, 422 cuerpo inválido, 500 almacenamiento privado.
- React: tarjeta junto al .tex, disponibilidad, estado bloqueado, revisión/hash y
  explicación; botón deshabilitado sin capacidad. El contrato reserva metadatos
  de PDF futuro; no ofrecer revisión/descarga funcional sin PDF verificado.

## Pasos y verificación

1. Escribir pruebas de rechazo y contratos, observar fallo por endpoints ausentes.
2. Implementar validación compartida, capacidades y registro privado; pruebas backend.
3. Escribir prueba UI de bloqueo y conservación .tex; implementar tarjeta y verificar.
4. Ejecutar pytest completo, Vitest, typecheck, build, diff --check; Chromium sintético
   en escritorio/390px/oscuro. No smoke TeX sin frontera verificada.
5. Actualizar manuales e informe con resultados y omisiones; commits auditables.

## Riesgos que revisar

Revisión cambiada entre comprobaciones, artefacto cambiado aunque hash solicitado
coincida, mezcla de planes, enlaces simbólicos/duros, fallo de publicación, errores
que revelen rutas, estado viejo mostrado como actual, respaldo JSON que exporte CV.
No probar escapes host/red/escritura sin aislamiento. Un falso no certifica compilación.
