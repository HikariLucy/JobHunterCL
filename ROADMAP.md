# Roadmap — JobHunter CL

## M0 · Hoy · MVP ejecutable
- [x] Recopilar oportunidades desde feed público Get on Board.
- [x] Conectores opcionales Remotive, Greenhouse y Lever.
- [x] Normalizar y desduplicar ofertas en SQLite.
- [x] Comparar cargo y habilidades con un perfil editable.
- [x] Revisar ofertas y abrir URL original.
- [x] Estados Nueva / Revisar / Preparada / Postulada / Descartada.
- [x] Exportar/importar seguimiento JSON entre PCs.
- [x] No subir datos privados a GitHub.
- [ ] Ejecutar smoke test real con red en Windows del trabajo.
- [ ] Comprobar funcionamiento real en Ubuntu en casa.

## M0.5 · Arquitectura local-first (FastAPI + React) — rama `feat/local-first-fastapi-react`
- [x] Backend FastAPI modular sobre el SQLite existente, solo en 127.0.0.1 y con validación de Host.
- [x] Migración aditiva del esquema (historial de estados, registro de búsquedas) con copia previa.
- [x] Panel React: Dashboard, Explorar, Seguimiento, Mi perfil, Configuración.
- [x] Reutilización de conectores y matching; corrección de campos nulos en Greenhouse/Lever.
- [x] Búsqueda programada en proceso (solo con la app abierta), reintentos y registro de fallos.
- [x] Lanzador único Windows/Ubuntu con cierre limpio (verificado en Windows 10).
- [x] Contratos de integración de CV (sin implementación).
- [ ] Validación de paridad por el usuario con datos reales → retirar Streamlit.
- [x] Búsqueda real con red desde el panel nuevo (Get on Board, Windows 10, 2026-10-21).
- [x] Instalación desde cero con el BAT (Windows 10, 2026-10-21: 2 min 18 s, entorno de 53 MB).
- [x] CI en GitHub (pytest en Ubuntu + Vitest + build).
- [x] Smoke test real del lanzador Linux en Mint 22.3 / base Ubuntu 24.04 (2026-10-21): loopback, SPA, perfil, offline y cierre. Ver docs/M14_INFORME.md. Ubuntu sin derivados y Windows actualizado siguen pendientes.
- [x] Importar historial de estados desde respaldos.

## M1 · Búsqueda adaptada a Chile
- [ ] Perfil fiel verificado: experiencia, ubicación, modalidad, remuneración, inglés, seniority. *(M1.4 añade modalidad, remuneración e idiomas con revisión conservadora; falta validación de fidelidad por el usuario)*
- [ ] Obtener descripción completa por APIs públicas antes de puntuar.
- [x] Corregir los 7 defectos medidos del ranking (nivel de la fuente, años, falsos amigos, ubicación): precisión 0,36 → 1,0, recall 0,57 → 0,86 en 326 ofertas. *(docs/ANALISIS_PUNTAJES.md)*
- [ ] Mejorar ranking: habilidades obligatorias vs deseables, incompatibilidades duras y explicaciones.
- [x] Dashboard rápido: caché de puntajes (~0,34 s → ~0,02 s).
- [x] API pública de Get on Board (opcional, desde Configuración): ofertas técnicas elegibles desde Chile; compatibles 6 → 38 por pasada (10 peticiones). *(docs/GETONBRD_API.md)*
- [x] Elegibilidad geográfica explícita (compatible / por confirmar / incompatible) con metadatos de la fuente; sin bonificación para lo no confirmado. *(docs/GETONBRD_API.md)*
- [ ] Himalayas (remotos elegibles desde Chile): diseño listo en docs/HIMALAYAS.md, sin implementar.
- [ ] Otros conectores (solo endpoints permitidos), intervalos, backoff y robots/ToS por plataforma. *(docs/FUENTES.md)*
- [ ] Pruebas con fixtures reales anonimizados y análisis de duplicados entre fuentes.

## M2 · Preparación de postulaciones
- [x] M2.1: importar y gestionar CV LaTeX **locales**, vista textual revisable, ES/EN, principal, hash, sustitución y eliminación. *(docs/CV_INTEGRACION.md y docs/M21_INFORME.md)*
- [x] M2.2: análisis determinista de ofertas guardadas, menciones documentadas, brechas, propuestas conservadoras con aprobación individual y diff; instantánea privada fijada por hash y descarga de nueva copia `.tex`. Estructuras ambiguas bloqueadas. *(docs/M22_INFORME.md)*
- [ ] M2.3: infraestructura PDF, contratos, verificación del `.tex` y estado privado implementados; **compilación real bloqueada** por ausencia de motor y perfil de aislamiento demostrado. Pendientes runner, cuotas, validación estructural/páginas, PDF real y revisión visual. Véase docs/M23_INFORME.md. Asociación con postulaciones queda para M3.
- [ ] Adaptar CV y carta sin inventar experiencia.
- [ ] Detectar preguntas del formulario y preparar respuestas para aprobación.
- [ ] Definir protección de secretos y políticas de retención.

## M3 · Postulación asistida con navegador
- [ ] Adaptadores Playwright por portal **solo si sus reglas permiten automatización**.
- [ ] Rellenar formulario visible; subir CV elegido; esperar confirmación del usuario.
- [ ] NO enviar automáticamente en portales que lo prohíban ni eludir CAPTCHA/antibots.
- [ ] Evidencia de confirmación, reintentos seguros y protección antirrepostulación.
- [ ] Autoenvío opt-in solo para plataformas donde esté permitido y tras validar elegibilidad, CV y datos.

## M4 · Operación
- [x] Planificador de búsqueda con límites y posibilidad de detenerse (en proceso, M0.5).
- [ ] Alertas por ofertas relevantes, deduplicadas.
- [ ] Sincronizar estado de forma cifrada entre computadores (GitHub solamente para código).
- [ ] Panel de tasas de respuesta, entrevistas y mejoras del CV.

## M1.4 · Perfil, onboarding y validación local
- [x] Persistencia atómica, .bak, detección de corrupción anidada y compatibilidad de perfiles.
- [x] Asistente de siete pasos opcionales; edición posterior, evidencias y formación en curso.
- [x] Modalidad, idiomas explícitos, renta conservadora y requisitos con explicaciones; seniority sin penalización duplicada.
- [x] Pruebas sintéticas diversas y comparación reproducible; pytest, Vitest, tsc y build.
- [x] Smoke Linux real y navegador en escritorio/móvil con datos temporales.
- [x] Propuesta no vinculante de producto y contratos LaTeX revisados (solo diseño).
- [ ] Revalidar este cambio en Windows y validar paridad/diseño con el usuario antes de retirar Streamlit.
- [ ] Ampliar cobertura semántica de requisitos/idiomas y formatos de renta con fixtures autorizados; las reglas no acreditan cumplimiento.

## Modos de postulación previstos

- **Manual:** el usuario prepara y envía por su cuenta.
- **Asistido:** JobHunter prepara; el usuario revisa antes del envío.
- **Automático:** autorización previa y reglas configurables del usuario, únicamente
  donde las condiciones de la plataforma permitan automatización y después de
  validar elegibilidad, documentos y respuestas. No eludir CAPTCHA/antibots.

M2.1/M2.2 no implementan navegador de postulaciones, acceso a cuentas ni envío de formularios.
Pendiente: portar las garantías POSIX del gestor de CV a Windows sin degradar privacidad.
