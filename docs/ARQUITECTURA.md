# Arquitectura — JobHunter CL (local-first)

## Principios

1. **Local y bajo demanda.** Un solo proceso que el usuario abre y cierra. Sin servicios de Windows, demonios, Docker, WSL ni nube.
2. **Solo `127.0.0.1`.** Además, `TrustedHostMiddleware` rechaza peticiones con `Host` distinto de `127.0.0.1`/`localhost` (defensa contra DNS rebinding desde páginas web).
3. **Offline para lo guardado.** Dashboard, ofertas, seguimiento, perfil y respaldos funcionan sin internet. Solo «Buscar» necesita red.
4. **Datos fuera del repositorio.** `data/` (SQLite, perfil, respaldos, futuros CV) está en `.gitignore`. Se puede mover con `JOBHUNTER_DATA_DIR`.
5. **Reutilizar antes que reescribir.** El paquete `jobhunter/` (conectores, matching, almacenamiento) es el núcleo que comparten el MVP Streamlit y la API.

## Vista general

```
 Navegador ──HTTP 127.0.0.1:8765──► uvicorn (start.py, un proceso)
                                     ├─ /api/*      FastAPI (backend/)
                                     │    ├─ routers/   jobs · search · profile
                                     │    ├─ services/  jobs · search · scheduler · backup
                                     │    └─ db.py      migraciones aditivas + copias
                                     ├─ /assets, /*  frontend/dist (React compilado, fallback SPA)
                                     └─ tarea asyncio: programador (solo mientras corre)
                                               │
                         jobhunter/ (núcleo compartido con Streamlit)
                         ├─ collect.py   Get on Board · Remotive · Greenhouse · Lever
                         ├─ matching.py  puntaje 0–100 + motivos + advertencias
                         ├─ storage.py   SQLite jobs/settings, respaldo JSON v1
                         └─ config.py    data/profile.json
```

## Backend (`backend/`)

| Módulo | Responsabilidad |
|---|---|
| `settings.py` | Rutas absolutas desde la raíz del repo; variables `JOBHUNTER_*`. |
| `db.py` | `connect()` reutiliza `storage.connection`; `migrate()` aplica migraciones **solo aditivas** controladas por `PRAGMA user_version`, con copia previa en `data/backups/`. Rechaza esquemas más nuevos que el código. |
| `schemas.py` | Contratos Pydantic. `Profile` admite claves extra para no perder datos del MVP. |
| `services/jobs.py` | Puntuar (reutiliza `matching.evaluate`), filtrar, actualizar estado/nota e historial. |
| `services/search.py` | Búsqueda con candado, espera mínima por fuente, reintentos con backoff y registro en `scan_runs`. |
| `services/scheduler.py` | Bucle asyncio cada 60 s; ejecuta si vence el intervalo configurado (nunca menor que el mínimo de las fuentes). |
| `services/backup.py` | Exportar/importar `jobhuntercl-backup-v1` (+ `status_history`, validado antes de escribir, sin duplicados ni entradas huérfanas), copia de seguridad antes de importar. |
| `cv_contracts.py` | Contratos de la futura integración de CV (sin implementación). |

### Endpoints

| Método | Ruta | Uso |
|---|---|---|
| GET | `/api/health` | Estado, versión, esquema |
| GET | `/api/dashboard` | Totales, nuevas coincidencias, embudo, estado de búsqueda |
| GET | `/api/jobs?status=&min_score=&q=&source=&sort=&limit=&offset=` | Ofertas puntuadas con motivos |
| GET | `/api/jobs/sources` | Fuentes presentes en la base |
| GET/PATCH | `/api/jobs/{id}` | Detalle / cambiar estado o nota |
| GET | `/api/jobs/{id}/history` | Historial de estados |
| GET | `/api/tracking` | Postulaciones en curso + cambios recientes |
| GET | `/api/search/status` | Última búsqueda, próxima permitida/programada, ejecuciones |
| POST | `/api/search` | Búsqueda manual (409 si hay otra en curso; 429 con `Retry-After` en segundos si está en espera — el panel la anticipa con `/api/search/status`) |
| GET/PUT | `/api/profile` | Perfil |
| GET/PUT | `/api/config` | Fuentes + intervalo de búsqueda |
| GET | `/api/backup/export` | Descarga JSON |
| POST | `/api/backup/import` | Restaura JSON (cuerpo = contenido del archivo) |

Documentación interactiva: `http://127.0.0.1:8765/api/docs`.

### Base de datos

Tablas del MVP (no se modifican): `jobs`, `settings`.
Tablas añadidas en el esquema 1: `status_history`, `scan_runs`.
`settings.last_scan` se comparte con Streamlit, así ambas interfaces respetan la misma espera mínima.

Política de migraciones: nunca `DROP`/`RENAME`/`ALTER ... DROP`; cada versión nueva añade un elemento a `MIGRATIONS` y una prueba con una base «heredada».

### Búsquedas y límites

- Espera mínima: 30 min; 6 h 30 min si Remotive está activo (su API pide ≤ 4 consultas/día).
- Reintentos: solo errores de red/timeout/HTTP 5xx (2 s, 6 s). HTTP 429 no se reintenta.
- Cualquier respuesta de una fuente (también 0 resultados, 429 o 5xx) inicia la espera. Solo un fallo de red sin respuesta permite reintentar de inmediato. Todo queda en `scan_runs`.
- Ejecuciones que quedaron `running` por un cierre abrupto se marcan `interrupted` al arrancar.

## Frontend (`frontend/`)

React 19 + TypeScript + Vite, sin librerías de UI (CSS propio con variables y modo oscuro).

```
src/
  api/        client.ts (fetch tipado, ApiError), types.ts (espejo de schemas.py)
  hooks/      useAsync (carga/errores/recarga, descarta respuestas obsoletas)
  components/ ui.tsx (Card, StatCard, badges, Loading, ErrorBox, AsyncView…),
              JobCard, ListEditor, SearchButton, Layout
  pages/      Dashboard, Explore, Tracking, ProfilePage, Settings
```

En desarrollo Vite (5173) reenvía `/api` al backend (8765). En uso normal el backend sirve `frontend/dist`.

## Camino a Ubuntu Server (futuro, sin rediseño)

- El backend ya es una app ASGI estándar (`backend.main:app`) configurada por variables de entorno.
- Para un servidor bastaría: unidad systemd o contenedor, reverse proxy con TLS y **autenticación** (hoy no existe porque solo escucha en loopback), y añadir el dominio a `allowed_hosts`.
- SQLite basta para un usuario; migrar a PostgreSQL implicaría sustituir `storage`/`db` detrás de los mismos servicios.
