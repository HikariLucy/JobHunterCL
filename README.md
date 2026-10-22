# JobHunter CL

Buscador y organizador personal de ofertas laborales para Chile y empleos remotos. Funciona **en tu PC, bajo demanda**: lo abres, consultas fuentes públicas, puntúa las ofertas con explicaciones y guarda tu seguimiento en SQLite local.

**Estado:** panel nuevo FastAPI + React en la rama `feat/local-first-fastapi-react`; el MVP Streamlit sigue disponible hasta validar la paridad ([docs/MIGRACION.md](docs/MIGRACION.md)). **No postula automáticamente.**

- Solo escucha en `127.0.0.1`. No instala servicios ni requiere Docker, WSL, nube ni servicios de pago.
- Las ofertas guardadas se consultan sin internet; las búsquedas nuevas requieren conexión.
- Las búsquedas programadas solo se ejecutan mientras JobHunter está abierto.
- Al cerrar la ventana (o Ctrl+C) todo se detiene.

## Requisitos

- **Python 3.11+**
- **Node.js 22 LTS o superior** (≥ 22.12 para compilar; las pruebas de frontend piden ≥ 22.22). Solo se usa para compilar el panel la primera vez y tras actualizar el código.

## Windows

```powershell
git clone https://github.com/HikariLucy/jobhunter.git
cd jobhunter
.\INICIAR-JOBHUNTER.bat
```

El BAT crea `.venv`, instala dependencias si faltan, compila el panel si hace falta y abre el navegador en `http://127.0.0.1:8765` (o el siguiente puerto libre). **Deja la ventana abierta** mientras lo uses; ciérrala o pulsa Ctrl+C para salir.

Manual:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
```

## Ubuntu

```bash
sudo apt install python3 python3-venv   # Node.js 22+: instálalo con nvm o NodeSource (el de apt suele ser antiguo)
git clone https://github.com/HikariLucy/jobhunter.git ~/proyectos/jobhunter
cd ~/proyectos/jobhunter
bash iniciar-jobhunter.sh
```

Manual: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python start.py`.

Opciones de `start.py`: `--no-browser`, `--port 8800`, `--build` (fuerza recompilar el panel).

## Configuración opcional

Copia `.env.example` a `.env`:

| Variable | Defecto | Uso |
|---|---|---|
| `JOBHUNTER_DATA_DIR` | `./data` | Carpeta de datos privados |
| `JOBHUNTER_PORT` | `8765` | Puerto inicial |
| `JOBHUNTER_SCHEDULER` | `1` | `0` desactiva el programador |

## Secciones

- **Dashboard:** nuevas coincidencias, embudo de postulaciones, estado de las búsquedas.
- **Explorar ofertas:** búsqueda, filtros, puntaje explicado, enlace al original, estado y notas. Cada oferta indica si es **elegible** desde tus zonas, si su elegibilidad está **por confirmar** (p. ej. remotas restringidas a países que la fuente no informa; siguen visibles y se filtran con «Elegibilidad → Por confirmar») o si está **fuera de tus zonas**. «Remoto» en tus ubicaciones es una modalidad deseada, no un lugar.
- **Seguimiento:** postulaciones por estado, notas e historial de cambios.
- **Mi perfil:** asistente opcional de primera ejecución, cargos/áreas, habilidades declaradas y en aprendizaje con evidencia, formación y tipo de experiencia, idiomas y preferencias. Todo puede omitirse y completarse después. «Nivel buscado» ajusta la puntuación (vacío = nivel inicial: penaliza Senior y, en menor medida, Semi Senior).
- **Configuración:** fuentes, frecuencia de búsqueda, registro de ejecuciones, respaldo/importación.

## Datos, respaldo y privacidad

- `data/` contiene la base SQLite, el perfil y las copias automáticas (`data/backups/`). **Nunca se sube a GitHub**; tampoco `.env`, CV (`*.tex`, `*.pdf`, `*.docx`), cookies ni sesiones.
- Antes de migrar el esquema o importar un respaldo se guarda una copia de la base.
- Para pasar el seguimiento a otro PC: **Configuración → Descargar respaldo** e **Importar** en el otro equipo. El JSON contiene datos privados; transfiérelo por un canal personal seguro. Incluye el historial de estados, que se restaura sin duplicarse si importas el mismo archivo dos veces. Es compatible con el respaldo del MVP Streamlit en ambos sentidos (los respaldos sin historial se importan igual).

## Fuentes y límites

- **Get on Board:** feed público XML y, opcionalmente, su API pública (Configuración → «Get on Board — API pública»): todas las ofertas técnicas elegibles desde Chile, ~10 consultas por búsqueda y espera mínima de 60 min. Ambas se combinan sin duplicar. **Remotive:** API pública (máx. 4 consultas/día → espera de 6 h 30 min). **Greenhouse / Lever:** APIs públicas de empresas concretas (identificador público, nunca credenciales).
- Espera mínima entre búsquedas: 30 min. Mientras dura, el botón «Buscar» queda deshabilitado e indica cuándo estará disponible. Reintentos solo ante fallos de red/servidor; un HTTP 429 no se reintenta.
- No se salta CAPTCHA, no se accede a contenido con inicio de sesión ni se envían postulaciones.

## Desarrollo

```bash
# Backend con recarga
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
# Frontend con recarga (otra terminal) → http://127.0.0.1:5173
cd frontend && npm install && npm run dev
```

Pruebas:

```bash
.venv/bin/python -m pytest -q          # Windows: .\.venv\Scripts\python.exe -m pytest -q
cd frontend && npm test && npm run build
```

Perfil y recuperación: [docs/PERFIL.md](docs/PERFIL.md) · Validación M1.4: [docs/M14_INFORME.md](docs/M14_INFORME.md) · Propuesta de producto: [docs/PRODUCTO.md](docs/PRODUCTO.md).

Arquitectura: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) · Integración futura de CV: [docs/CV_INTEGRACION.md](docs/CV_INTEGRACION.md) · Hitos: [ROADMAP.md](ROADMAP.md).

## MVP anterior (Streamlit)

Sigue disponible mientras se valida la paridad: `INICIAR-WINDOWS.bat` / `bash iniciar-linux.sh` (usa `launch.py`, puerto 8501). Comparte la misma base de datos; evita usar ambas interfaces a la vez. Sus dependencias están aparte, en `requirements-streamlit.txt` (~290 MB con pandas/pyarrow); esos lanzadores las instalan la primera vez. El panel nuevo no las necesita.

Smoke Linux con datos temporales y sin consultar portales: `.venv/bin/python scripts/smoke_m14.py`. Comparación de ranking sintético contra `614e394`: `.venv/bin/python scripts/eval_m14.py`.
