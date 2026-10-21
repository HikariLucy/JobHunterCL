# JobHunter CL — Especificación completa M1.4

**Fase:** perfil profesional, onboarding y validación local
**Repositorio privado:** `HikariLucy/jobhunter`
**Rama de trabajo:** `feat/local-first-fastapi-react`
**Estado de referencia:** último push conocido `5d85c7c` (verificar HEAD real antes de comenzar)
**Alcance de esta ejecución:** implementación local, pruebas y documentación. **Sin push ni merge.**

> Esta especificación reemplaza el mensaje anterior que llegó truncado. Lee las secciones 1–11 completas antes de implementar. Si algún apartado entra en conflicto con el código real, informa la discrepancia, preserva datos y aplica la solución compatible más pequeña. No deduzcas requisitos invisibles.

## 1. Contexto y objetivos

JobHunter CL es una aplicación **local-first** para encontrar empleos, evaluar compatibilidad profesional y llevar seguimiento de postulaciones en Chile y empleos remotos. Cuenta con backend FastAPI, frontend React + TypeScript + Vite, SQLite local, búsqueda mediante feed/API pública de Get on Board y otros conectores opcionales, matching explicable, elegibilidad geográfica, historial, respaldos y CI. El panel actual fue revisado visualmente por el usuario y **su diseño general está aprobado**.

**Objetivo específico M1.4:** pasar de un perfil genérico a un perfil profesional configurable y fiable, con primera configuración (onboarding), persistencia segura y un matching que utilice las preferencias de forma verificable. Preparar la integración futura de CV en LaTeX sin desarrollar todavía la generación ni el envío.

**Visión final del producto (no implementar en M1.4):** búsqueda automática mientras la app esté abierta, selección de ofertas, adaptación fiel del CV LaTeX y postulaciones manuales, asistidas o automáticas **solo donde la plataforma lo permita**, con consentimiento inicial explícito, reglas del usuario, límites por día, registros y capacidad de detener la automatización. No se implementan envíos, Playwright ni conexión a cuentas de empleo en esta fase.

## 2. Auditoría previa obligatoria

1. Verifica `git status`, rama y HEAD reales; no asumas que el SHA de referencia sigue siendo HEAD.
2. Revisa `README.md`, `ROADMAP.md`, `docs/ARQUITECTURA.md`, `docs/MIGRACION.md`, `docs/CV_INTEGRACION.md`, `backend/schemas.py`, `jobhunter/config.py`, `jobhunter/matching.py`, `frontend/src/pages/ProfilePage.tsx`, API y pruebas.
3. Documenta el contrato actual del perfil, cómo se guardan las preferencias, cómo se invalidan las puntuaciones y qué rutas consume el frontend.
4. No reescribas características existentes ni elimines Streamlit. Mantén compatibilidad con versiones anteriores de perfiles y respaldos.

## 3. Persistencia segura del perfil (primera implementación)

El `save_profile` existente escribe directamente `data/profile.json`: antes del onboarding, corrige este riesgo.

- Escritura atómica y compatible con Windows/Ubuntu: serializar y validar antes de escribir, guardar en archivo temporal **en el mismo directorio**, vaciar/sincronizar cuando resulte apropiado y sustituir atómicamente el destino (`os.replace` o equivalente).
- Conservar una copia `.bak` de la última versión válida **sin destruir la única copia buena** en un error intermedio.
- Si falla validación, escritura o reemplazo, preservar el último perfil íntegro; emitir un error útil y no un éxito falso.
- Manejar cargas corruptas de forma segura; no sobrescribir automáticamente el archivo dañado. Documenta recuperación desde respaldo.
- Preservar claves desconocidas de configuraciones anteriores cuando sea necesario para retrocompatibilidad, sin permitir campos arbitrarios inseguros.
- Mantener `data/`, backups y perfiles ignorados por Git. No copiar datos reales a fixtures.
- Añadir pruebas de escritura correcta, archivo corrupto, fallo simulado, backup y compatibilidad con perfil antiguo.

No crear migración SQLite si todos los datos nuevos pueden vivir en el perfil existente.

## 4. Onboarding de primera ejecución

Diseñar un asistente breve y progresivo usando los componentes actuales, **sin rediseño general**. Mostrarlo si no existe un perfil guardado o si el usuario lo invoca explícitamente; no forzar el wizard a perfiles existentes. El usuario puede omitir campos y terminar después.

Orden sugerido, ajustable según la UX real:

1. **Objetivos profesionales:** cargos que busca y áreas de interés.
2. **Experiencia y formación:** cargos, empresa o proyecto, período, principales responsabilidades; educación obtenida o *en curso*, sin presentarla como título completado.
3. **Habilidades:** distinguir las que domina de las que está aprendiendo; permitir registrar evidencia opcional de experiencia/proyecto.
4. **Idiomas:** idioma, nivel declarado y evidencia opcional (sin inferir certificaciones).
5. **Preferencias:** junior/entry-level/intermedio si corresponde; modalidad presencial, híbrida o remota; ubicaciones permitidas y restricciones de residencia; disposición a relocalización; remuneración mínima y moneda **opcionales**.
6. **Fuentes y límites:** Get on Board feed y API, Remotive y fuentes por empresa. API de Get on Board activa por defecto **solo en perfiles nuevos**, respetando configuraciones previas; no disparar consultas externas durante el onboarding ni al iniciar la aplicación.
7. **Resumen y confirmación:** revisar/editar, guardar o cancelar sin pérdida de un perfil anterior.

Añadir señales de validación no intrusivas y estado claro de guardado. No pedir ni exigir CV, RUT, claves de portales, dirección particular ni otros datos sensibles. El asistente debe funcionar con teclado y en móvil. El perfil debe seguir siendo editable en «Mi perfil».

## 5. Veracidad, niveles y evidencias

- Separar **habilidad declarada**, **habilidad demostrada por experiencia/proyecto** y **habilidad en aprendizaje**, sin fingir acreditaciones.
- Diferenciar experiencia laboral formal, prácticas y proyectos personales/educativos; un proyecto no equivale automáticamente a años de experiencia contractual.
- No inventar empleos, estudios, certificaciones, títulos, fechas ni idiomas.
- Si la información es incompleta, indicar «por confirmar» en vez de completar automáticamente.
- El usuario puede revisar y modificar todo. No utilizar el CV personal real sin selección explícita del usuario.

## 6. Matching basado en preferencias y explicaciones

Audita `evaluate`, `source_meta`, la clasificación geográfica y las cachés antes de cambiar reglas.

Implementa mejoras incrementales y trazables:

- **Modalidad:** diferenciar modalidad deseada de elegibilidad geográfica. «Remoto» no es un país; no sumar compatibilidad por modalidad cuando no está confirmada.
- **Nivel de experiencia:** usar primero metadatos estructurados, luego información textual; nunca descartar automáticamente vacantes sin seniority declarado, como soporte N1/N2 o analista TI.
- **Idiomas:** contrastar requisitos explícitos contra idiomas/niveles declarados, con advertencia si faltan evidencias. No inferir inglés por palabras técnicas de una descripción ni prometer cumplimiento de un nivel no acreditado.
- **Remuneración:** tratar como advertencia/revisión cuando la oferta no da rango o las monedas/periodicidades son incomparables; no inventar conversión de divisas ni descartar sin evidencia firme.
- **Requisitos obligatorios vs deseables:** clasificar únicamente cuando la descripción lo permita; explicar coincidencias y brechas, sin declarar que un requisito está cumplido sin respaldo.
- **Geografía:** mantener «compatible», «desconocida» e «incompatible»; ofertas desconocidas continúan visibles sin bonificación de ubicación. Restricciones explícitas prevalecen sobre «totalmente remoto».
- Evitar dobles penalizaciones del mismo requisito; preservar score 0–100 y umbral configurable salvo necesidad justificada/documentada.
- Invalidar correctamente cachés al cambiar perfil/oferta, sin perder el rendimiento del dashboard.

Validar antes/después con **perfiles sintéticos diversos**, no únicamente un perfil por defecto o un snapshot de un día. Añadir pruebas unitarias, integración de API y React para mensajes/explicaciones. No realizar llamadas reales a portales salvo necesidad justificada, respetando esperas.

## 7. Fuentes y ejecución local

- Mantener las fuentes existentes y su deduplicación. No implementar Himalayas todavía: diseño ya está documentado en `docs/HIMALAYAS.md`.
- Continuar solo en `127.0.0.1` por defecto; sin Docker obligatorio, servicios en segundo plano, nube, suscripciones ni base remota.
- El programador solo funciona cuando JobHunter está abierto y respeta mínimos por fuente; un error 429 no causa reintentos agresivos.
- No añadir scraping de LinkedIn, Indeed u otros portales que lo restrinjan. La importación de alertas laborales recibidas voluntariamente por correo es una **idea futura**, no parte de esta fase.
- No introducir dependencias pesadas sin necesidad; el PC Windows ha tenido poco espacio de almacenamiento.

## 8. CV LaTeX: preparar, no ejecutar envíos

Revisar `docs/CV_INTEGRACION.md` y `backend/cv_contracts.py`. Identificar contratos y UI faltantes para un flujo futuro:

`.tex` maestro ES/EN elegido por el usuario → extracción/revisión → requisitos de una oferta → propuesta de cambios con evidencia literal del CV → aprobación → copia `.tex` adaptada → PDF opcional si LaTeX está instalado.

En M1.4 puedes implementar **solo** importación local y vista previa si resulta acotada, segura y comprobable, usando fixtures sintéticos. No modificar los CV originales, no usar servicios de IA pagos ni incorporar envío de CV o de postulaciones. Los CV quedan fuera de Git y del respaldo JSON por defecto. Las lagunas de experiencia se muestran como tales, nunca se inventan.

## 9. Validación de Windows/Ubuntu y calidad

- En el sistema operativo disponible, ejecutar pruebas completas con `JOBHUNTER_DATA_DIR` apuntando a una carpeta temporal.
- Verificar iniciador correspondiente, API restringida a loopback, frontend y rutas profundas, flujo de onboarding, guardar/recargar perfil, manejo de errores, cierre limpio y lectura offline de ofertas guardadas.
- Si el agente está en **Windows 10**, **no** reportar Ubuntu real como aprobado. Mantener el smoke test `iniciar-jobhunter.sh` pendiente para el PC doméstico.
- Si el agente trabaja realmente en Ubuntu, probar el lanzador Linux con permisos/dependencias normales y evidencia reproducible.
- Ejecutar pytest, Vitest, TypeScript (`tsc`) y build; registrar resultados exactos y limitaciones. Probar que los cambios no alteren perfil/base personal.
- Validar interfaz en escritorio y ancho móvil representativo; no cambiar el estilo visual aprobado sin motivo.

## 10. Preparación para eventual comercialización — solo documento

Crear o actualizar `docs/PRODUCTO.md` como **propuesta no vinculante**, distinguiendo hechos y suposiciones:

- **Público potencial:** personas que buscan empleo tecnológico inicial en Chile/LATAM y después otras áreas; validar demanda antes de asumirla.
- **Oferta de valor:** agregación autorizada de oportunidades, ranking transparente, seguimiento privado y futura adaptación de CV/postulación automatizada permitida.
- **Modelo de negocio a evaluar:** app local gratuita + posible licencia Pro; comparar pago único vs suscripción, sin fijar precios como hechos ni implementar cobros.
- **Distribución futura:** instaladores Windows/Ubuntu, actualizaciones y soporte; modularidad para un eventual backend alojado, sin despliegue en este hito.
- **Seguridad y privacidad:** datos locales, consentimiento, borrado/exportación, respaldo, minimización de datos.
- **Cumplimiento:** licencias de dependencias, derechos sobre marcas, términos de APIs, atribución, condiciones para usos comerciales y protección de datos según territorios. No asumir que una API pública autoriza comercialización sin revisar términos.
- **Automatización final:** modos manual, asistido y automático *opt-in* únicamente en plataformas que lo permitan, con controles por volumen, prevención de duplicados, supervisión de errores y registro. **No implementar en M1.4.**
- **Validación de mercado:** beta privada y métricas de utilidad antes de inversiones o publicidad.

No agregar pagos, cuentas de usuario obligatorias, publicidad, telemetría, DRM, nube ni integraciones no autorizadas.

## 11. Metodología, entregables y condiciones de parada

### Método

1. Audita la rama/HEAD antes de escribir y presenta brevemente el plan y los riesgos.
2. Prioriza seguridad de `profile.json`, luego onboarding y persistencia, luego matching y pruebas.
3. Implementa cambios pequeños, reversibles y documentados; commits locales descriptivos.
4. Mantén el diseño aprobado y el MVP Streamlit hasta que el usuario confirme paridad.
5. **No hagas push ni merge a `main` sin autorización explícita.**
6. **No toques datos reales, CV reales ni credenciales.** Usa solo directorios de prueba temporales.
7. No ejecutes postulaciones ni envíos automáticos. No instales servicios ni publiques una web.
8. No marques como PASS nada que no hayas ejecutado. Ante un bloqueo, entrega avance parcial verificable y limita el alcance.

### Informe final requerido

1. Resumen de implementación y archivos modificados.
2. Evidencia del onboarding, persistencia atómica y recuperación ante fallos.
3. Evidencia de cambios de matching y comparación antes/después en distintos perfiles.
4. Resultados concretos de pytest, Vitest, TypeScript y build.
5. Estado verdadero del smoke test Ubuntu y Windows.
6. Estado del diseño de integración LaTeX.
7. `docs/PRODUCTO.md` y supuestos de comercialización.
8. Commits locales, rama, estado de árbol y confirmación de **no push/no merge**.
9. Pendientes, riesgos y siguiente paso sugerido.

**Empieza leyendo este documento completo. No pidas de nuevo las secciones 1–10: están aquí. Procede con la auditoría y los primeros cambios locales seguros.**
