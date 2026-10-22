# M1.4 — Hotfix de navegación

## Causa confirmada

`Layout` ejecutaba la consulta de estado en un efecto dependiente de `navigate`.
La aplicación usa `BrowserRouter` (modo declarativo), donde esa referencia puede
cambiar al navegar. Sin perfil y sin cancelación explícita, el efecto volvía a
consultar y redirigía otra vez a `/perfil`. El cleanup anterior cancelaba el
callback viejo, pero la navegación iniciaba otra consulta con permiso de redirigir.
Además, `ProfilePage` no consultaba la omisión almacenada al volver a entrar.

Referencia contrastada con Context7:
[React Router: useNavigate](https://github.com/remix-run/react-router/blob/main/docs/api/hooks/useNavigate.md).

## Corrección

- Una comprobación inicial por montaje de `Layout`, reutilizada en StrictMode.
- La comprobación queda consumida al responder o al cambiar de ubicación; volver
  atrás no la reactiva. También se detectan cambios de consulta o fragmento.
- El cleanup impide actuar sobre respuestas pendientes tras navegar o desmontar.
- Cancelar sigue sin guardar; al volver a Mi perfil se respeta la omisión de la
  sesión. El botón Abrir asistente permite iniciarlo voluntariamente.
- Los perfiles existentes conservan el formulario normal. Sin cambios visuales,
  de backend, de datos personales, del perfil real ni de CV.

## Verificación

Las nuevas pruebas usan App, MemoryRouter y StrictMode reales, con API simulada
y datos sintéticos. Antes del arreglo fallaron cuatro de cinco; después pasan
las cinco: recorrido de los cinco enlaces sin completar el asistente, cancelación
y reapertura voluntaria, perfil existente, respuesta demorada con historial y
cambio de consulta mientras hay una respuesta pendiente.

- `cd frontend && npm test`: **38 passed**, 6 archivos.
- `cd frontend && npm run typecheck`: correcto.
- `cd frontend && npm run build`: correcto.
- `JOBHUNTER_DATA_DIR=$(mktemp -d /tmp/jobhunter-nav-hotfix-XXXXXX) .venv/bin/python -m pytest -q -o faulthandler_timeout=30`:
  **188 passed**, 1 aviso de deprecación Starlette/httpx, 3.26 s.
- La primera ejecución Python dentro del sandbox quedó bloqueada y fue
  interrumpida; la ejecución completa anterior se realizó fuera del sandbox.
- Revisión independiente sin hallazgos; `git diff --check` correcto.

Validación automatizada; no se realizó una comprobación visual manual en navegador.
Entrega mediante commit local, sin push ni merge.
