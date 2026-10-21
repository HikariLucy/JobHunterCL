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

## Verificación — ronda 1 (implementación)

- `pytest` 47 y `vitest` 19 aprobadas; `tsc` y `vite build` sin errores.
- Windows 10: `start.py` arranca, sirve API y SPA, rechaza `Host` ajeno (400), escucha solo en `127.0.0.1` y cierra con código 0.

## Validación — ronda 2 (2026-10-21, sin funcionalidades nuevas)

Todas las pruebas se hicieron con carpetas de datos **temporales** (`JOBHUNTER_DATA_DIR`). La base personal `data/jobs.sqlite3` no se abrió en escritura (sigue en esquema 0).

| Prueba | Método | Resultado |
|---|---|---|
| BAT real, primera instalación | Clon limpio de la rama + `cmd /c INICIAR-JOBHUNTER.bat` | Crea `.venv` e inicia `pip install`; **falló por disco lleno** (`Errno 28`, C: con 0,06 GB libres). El BAT mostró el error, el mensaje de ayuda y `pause` correctamente. Instalación completa **no verificada**. |
| BAT real, uso normal | `cmd /c INICIAR-JOBHUNTER.bat` en el repo con `.venv` existente | Detecta dependencias, recompila el panel desactualizado, responde en 8–11 s, cierre por Ctrl+Pausa con código 0 y puerto liberado. |
| Búsqueda real Get on Board | Botón del panel (Chrome headless) | Primero devolvió **0 ofertas**: el feed ya no es RSS (bug corregido). Tras la corrección: 326 leídas, 326 nuevas, URLs únicas, 11 coincidencias ≥ 30. Segunda pulsación bloqueada por la espera mínima sin consultar la fuente. |
| E2E de las 5 secciones | Chrome 1366×900 vía DevTools Protocol: clics, formularios y capturas | 30/31. Única falla: la consola registra el 429 **intencional** de la API en la segunda búsqueda; sin excepciones JS. |
| Responsive | Chrome 390×844 | **Bug**: 4 de 5 secciones desbordaban (hasta 526 px). Corregido; las cinco miden 390 px. |
| Respaldo JSON | Exportar de un servidor e importar en otro vacío | 19/19: campos idénticos, estado y nota, perfil, sin duplicados al reimportar, copia previa, rechazo de respaldos corruptos sin cambios, compatible con el importador Streamlit. |
| Copia SQLite | Migración de una base v0 | Copia previa íntegra (`integrity_check` ok, mismos datos, esquema 0); restaurar = copiar el archivo. |
| Privacidad | `git ls-files`, `git log -p`, `git check-ignore` | Sin bases, CV, `.env`, cookies ni tokens versionados. Faltaba ignorar `jobhunter_respaldo*.json` (corregido). |
| CI | Revisión estática + YAML válido | Ahora se ejecuta en `feat/**`, `fix/**`, `chore/**`, PR y manual. **No ejecutado en GitHub** (sin push). |

### Problemas corregidos en esta ronda

1. `collect`: feed de Get on Board en formato `<source><job>` → 0 ofertas siempre (también afectaba al MVP Streamlit).
2. `search`: una respuesta sin ofertas (o un 429/5xx) no iniciaba la espera mínima → consultas repetidas a la fuente.
3. CSS: desborde horizontal en móvil.
4. `.gitignore`: respaldos exportados.
5. CI sin disparadores para ramas de trabajo; requisito de Node mal documentado (20+ → 22.12+).
6. BAT: aviso sobre la pregunta «¿Desea terminar el trabajo por lotes?» de cmd.

## No verificado

- Instalación desde cero mediante el BAT (bloqueada por falta de espacio en disco).
- Doble clic manual en el BAT y apertura real del navegador predeterminado (se ejecutó con `cmd /c` y `--no-browser`).
- Aviso de «servidor detenido» del panel (cubierto solo por el código; no por prueba E2E).
- Ubuntu y GitHub Actions.
- Remotive, Greenhouse y Lever con red real.

## Pendientes

1. Liberar espacio en C: y repetir la instalación desde cero con el BAT.
2. El usuario valida la paridad con datos reales → decidir retiro de Streamlit (`app.py`, `launch.py`, `INICIAR-WINDOWS.bat`). El MVP Streamlit mantiene su política anterior de espera (solo con resultados).
3. Push de la rama y primera ejecución de CI.
4. Smoke test en Ubuntu.
5. Importar historial de estados desde respaldos (hoy solo se exporta).
6. M1 según ROADMAP.
