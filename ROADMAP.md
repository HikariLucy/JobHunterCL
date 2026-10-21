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
- [ ] Instalación desde cero con el BAT (bloqueada por disco lleno en la validación).
- [ ] Smoke test en Ubuntu y primera ejecución de CI en GitHub.
- [ ] Importar historial de estados desde respaldos.

## M1 · Búsqueda adaptada a Chile
- [ ] Perfil fiel verificado: experiencia, ubicación, modalidad, remuneración, inglés, seniority. *(campos disponibles en el panel; falta usarlos en el matching)*
- [ ] Obtener descripción completa por APIs públicas antes de puntuar.
- [ ] Mejorar ranking: habilidades obligatorias vs deseables, incompatibilidades duras y explicaciones.
- [ ] Conectores adicionales (solo endpoints permitidos), intervalos, backoff y robots/ToS por plataforma.
- [ ] Pruebas con fixtures reales anonimizados y análisis de duplicados entre fuentes.

## M2 · Preparación de postulaciones
- [ ] Importar CV **local** y extraer datos con revisión explícita. *(diseño: docs/CV_INTEGRACION.md)*
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
