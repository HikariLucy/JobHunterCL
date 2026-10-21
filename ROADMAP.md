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

## M1 · Búsqueda adaptada a Chile
- [ ] Perfil fiel verificado: experiencia, ubicación, modalidad, remuneración, inglés, seniority.
- [ ] Obtener descripción completa por APIs públicas antes de puntuar.
- [ ] Mejorar ranking: habilidades obligatorias vs deseables, incompatibilidades duras y explicaciones.
- [ ] Conectores adicionales (solo endpoints permitidos), intervalos, backoff y robots/ToS por plataforma.
- [ ] Pruebas con fixtures reales anonimizados y análisis de duplicados entre fuentes.

## M2 · Preparación de postulaciones
- [ ] Importar CV **local** y extraer datos con revisión explícita.
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
- [ ] Planificador de búsqueda con límites y posibilidad de detenerse.
- [ ] Alertas por ofertas relevantes, deduplicadas.
- [ ] Sincronizar estado de forma cifrada entre computadores (GitHub solamente para código).
- [ ] Panel de tasas de respuesta, entrevistas y mejoras del CV.
