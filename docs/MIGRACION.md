# Migración Streamlit → FastAPI + React

Rama: `feat/local-first-fastapi-react` (desde `main` c50dd8b). Fecha: 2026-10-21.

## Auditoría inicial (estado real de `main`)

- 13 pruebas pasando (Python 3.12.10, Windows 10).
- `data/jobs.sqlite3` con tablas `jobs` y `settings`, 0 filas, `user_version = 0`.
- **Bug encontrado y corregido:** Greenhouse/Lever con `location`/`categories` nulos lanzaban `AttributeError`, no capturado por `fetch_all`, y abortaban la búsqueda completa.
- Rutas `data/...` relativas al directorio de trabajo (la API usa rutas absolutas).
- Sin historial de estados; la espera mínima vivía dentro de `app.py`.
- README hablaba de un ZIP «JobHunter-CL»; el repo real es `jobhunter`.

## Fases

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Auditoría, rama, plan | ✅ |
| F1 | Backend FastAPI, migración aditiva, servicios, 24 pruebas | ✅ |
| F2 | Frontend React (5 secciones), 19 pruebas Vitest | ✅ |
| F3 | Lanzador único Windows/Ubuntu, smoke test real en Windows | ✅ (Ubuntu sin probar) |
| F4 | Programador en proceso, reintentos, registro de ejecuciones | ✅ (básico) |
| F5 | Contratos de CV | ✅ solo diseño |
| F6 | Validación de paridad por el usuario → retirar Streamlit | ⏳ |
| F7 | Playwright (postulación asistida, con confirmación) | ⏳ futuro |

## Matriz de paridad

| Función del MVP Streamlit | Nueva interfaz | Notas |
|---|---|---|
| Buscar ofertas con espera mínima | ✅ Botón en Dashboard/Explorar | Misma clave `last_scan`, misma política |
| Listar con puntaje, motivos y advertencias | ✅ Explorar | |
| Filtrar por estado, puntaje mínimo, texto | ✅ | + fuente, orden, paginación |
| Abrir oferta original | ✅ | `rel="noopener noreferrer"` |
| Cambiar estado y guardar nota | ✅ | + historial |
| Métricas por estado | ✅ Dashboard/Seguimiento | |
| Tabla de seguimiento | ✅ Seguimiento | Tarjetas filtrables por estado |
| Exportar / importar respaldo JSON | ✅ Configuración | Formato v1 compatible en ambos sentidos; copia previa al importar |
| Editar cargos, habilidades, ubicaciones | ✅ Mi perfil | + experiencia, idiomas, preferencias |
| Fuentes (Get on Board, Remotive, Greenhouse, Lever) | ✅ Configuración | Valida identificadores |
| — | ✅ Búsqueda programada | Nuevo |

## Compatibilidad y respaldo de datos

- La migración solo **añade** tablas; Streamlit sigue funcionando sobre la misma base (probado en `test_migration_is_additive_and_backs_up_first`).
- Antes de migrar una base existente se crea `data/backups/jobs-pre-v1-<fecha>.sqlite3`; antes de importar un respaldo, `jobs-pre-import-<fecha>.sqlite3`.
- Si la base tiene un esquema más nuevo que el código, la API se niega a arrancar en lugar de tocarla.
- `profile.json` conserva claves desconocidas; los campos nuevos son opcionales.
- Ambas interfaces pueden usarse, pero **no a la vez** de forma intensiva: los cambios de estado hechos en Streamlit no generan historial.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Node.js ausente en algún equipo | `start.py` sirve la API igualmente y explica cómo compilar; se puede copiar `frontend/dist`. |
| Cambios de formato en las fuentes | Errores por fuente aislados y registrados en `scan_runs`; fixtures de prueba. |
| Bloqueo de SQLite con dos interfaces abiertas | `busy_timeout` 5 s; uso recomendado de una sola interfaz. |
| Aviso `httpx`→`httpx2` de Starlette 1.9 en pruebas | Solo afecta al cliente de pruebas; revisar al actualizar dependencias. |

## Verificación realizada

- `pytest`: **47 pasan** (13 originales + 2 de conectores + 24 API/migración/búsqueda + 5 lanzador + 3 contratos CV).
- `vitest`: **19 pasan**. `tsc` y `vite build` sin errores.
- Windows 10, smoke test real con `start.py`: endpoints 200, SPA servida en rutas profundas, `Host: evil.example` → 400, escucha solo en `127.0.0.1`, cierre por Ctrl+Pausa con código 0.

## No verificado

- Revisión visual en navegador (la extensión de Chrome no estaba conectada); el comportamiento de la UI está cubierto con pruebas de componentes en jsdom.
- Ubuntu (lanzador `.sh` sin ejecutar).
- Búsqueda real contra las fuentes con internet desde la nueva interfaz.
- Doble clic en `INICIAR-JOBHUNTER.bat` (se probó `start.py` directamente).

## Pendientes

1. El usuario valida la paridad con datos reales → decidir retiro de Streamlit (`app.py`, `launch.py`, `INICIAR-WINDOWS.bat`).
2. Smoke test en Ubuntu y búsqueda real con red.
3. Importar historial desde respaldos (hoy solo se exporta).
4. M1: requisitos obligatorios vs deseables, descripción completa por API, fixtures reales anonimizados.
5. M2: implementar CV según `docs/CV_INTEGRACION.md`.
6. CI: job de frontend añadido; confirmar que pasa en GitHub tras el push (pendiente de autorización).
