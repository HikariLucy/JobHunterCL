# Prompts para agentes de código

## Codex — auditoría y pruebas de M0

> Estás trabajando en el repositorio JobHunter-CL. Empieza inspeccionando README.md, ROADMAP.md, app.py y jobhunter/. El proyecto debe permanecer local y privado. Revisa ejecución en Windows 11 con Python 3.11+, valida y corrige adaptadores de Get on Board RSS y Remotive con fixtures reales no sensibles, agrega pruebas de errores y no modifiques ni agregues datos en data/. No postules a ningún trabajo. No agregues mecanismos de evasión de CAPTCHA o de restricciones de sitios. Trabaja en rama feature/m0-hardening; ejecuta pytest y documenta evidencia antes de hacer commit. No hagas push sin que te lo pida.

## Claude Code — diseño M1 / M2

> Lee ROADMAP.md, README.md y toda la suite de pruebas de JobHunter-CL. Sin crear nuevos scraping no autorizados ni tocar data/ o el CV personal, prepara una propuesta M1 para mejorar matching de ofertas chilenas (junior, soporte, backend, DevOps, infraestructura), separar requisitos obligatorios y deseables y evaluar ubicación/eligibilidad. Implementa pruebas unitarias reproducibles, y un diseño de M2 de preparación de postulaciones sin envío. Haz cambios pequeños, reversibles y auditables en una rama separada. No inventes experiencia ni datos del postulante.
