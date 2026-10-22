# JobHunter CL

**Buscador y gestor local de oportunidades laborales en Chile y empleos remotos.** Recopila publicaciones desde fuentes públicas, evalúa su afinidad con un perfil editable y permite organizar el seguimiento de postulaciones sin depender de un servicio en la nube.

**Estado de `main`: MVP funcional con Python, Streamlit y SQLite.** Incluye fuentes configurables (Get on Board, Remotive, Greenhouse y Lever), deduplicación, puntuación explicable, notas y estados de seguimiento, además de exportación e importación de respaldos JSON. **No envía postulaciones ni completa formularios automáticamente.** Las integraciones externas requieren una conexión y deben validarse en el entorno de ejecución.

**Evolución en curso:** el panel local **FastAPI + React** se desarrolla en [`feat/local-first-fastapi-react`](https://github.com/HikariLucy/JobHunterCL/tree/feat/local-first-fastapi-react). Sus funciones no deben confundirse con las de `main`. Consulta el README de esa rama para conocer los requisitos y avances del nuevo panel.

## Windows (PowerShell)

Requiere **Python 3.11+**, conexión a internet para nuevas búsquedas y permiso para instalar dependencias. Clona este repositorio público y usa el iniciador incluido:

```powershell
git clone https://github.com/HikariLucy/JobHunterCL.git
cd JobHunterCL
.\INICIAR-WINDOWS.bat
```

También puedes descargar el ZIP del repositorio y ejecutar `INICIAR-WINDOWS.bat` desde la carpeta extraída. El BAT crea/reutiliza `.venv`, instala dependencias si hace falta y abre Streamlit. Deja su ventana abierta mientras utilizas la aplicación. El panel estará normalmente en `http://127.0.0.1:8501` (o en otro puerto libre).

Ejecución manual, desde la raíz del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launch.py
```

Si no está disponible `py`, utiliza `python` para crear el entorno virtual.

## Ubuntu / Linux

```bash
git clone https://github.com/HikariLucy/JobHunterCL.git ~/proyectos/JobHunterCL
cd ~/proyectos/JobHunterCL
bash iniciar-linux.sh
```

Como alternativa manual:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launch.py
```

La interfaz abre normalmente en `http://127.0.0.1:8501`. En **Perfil y fuentes** ajusta los cargos y habilidades; después utiliza **Buscar nuevas ofertas**. Get on Board es la fuente inicial; Remotive y empresas Greenhouse/Lever son opcionales. Las búsquedas ocurren bajo demanda y aplican esperas para limitar consultas.

## Datos y continuidad entre equipos

El proyecto guarda el perfil, las ofertas, las notas y los estados **localmente**. El código se puede clonar desde este repositorio público; el seguimiento no se sincroniza por GitHub.

1. No subas `data/`, CV, contraseñas, respaldos personales ni `.venv/` al repositorio.
2. En el segundo equipo, clona `https://github.com/HikariLucy/JobHunterCL.git`, crea un entorno virtual e instala `requirements.txt`.
3. Usa **Seguimiento → Descargar respaldo JSON** y **Importar respaldo** para trasladar tus ofertas y estados. El JSON puede contener información privada: consérvalo y transfiérelo de forma segura.

El MVP Streamlit de `main` no debe ejecutarse a la vez que otra versión que modifique su misma base de datos.

### Si Windows no abre el panel

1. Abre CMD en la carpeta descomprimida: escribe `cmd` en la barra de direcciones del Explorador y pulsa Enter.
2. Ejecuta `INICIAR-WINDOWS.bat`. La consola **no debería cerrarse sola**: si hay un error, quedará visible al final.
3. Cuando se muestre «Panel listo», copia la dirección `http://127.0.0.1:8501` al navegador. El puerto puede ser 8502, 8503, etc., si ya hay otra app ocupando el primero.
4. Si ves un error durante instalación (por ejemplo proxy, red restringida o `pip`), envía el texto o una captura de CMD. No pegues tokens, contraseñas ni variables de entorno.
5. Si `.venv` quedó incompleto, cambia su nombre por `.venv-anterior` y vuelve a lanzar el BAT; no es necesario eliminar tus archivos de `data/`.

En el PC del trabajo, instala dependencias solo si está autorizado por las políticas de la empresa.

## Fuentes y límites

- **Get on Board:** feed público `https://www.getonbrd.com/jobs/feed` (centrado en empleo tecnológico Chile/LatAm). No requiere inicio de sesión.
- **Remotive:** API pública `https://remotive.com/api/remote-jobs`, solo si se activa. Su documentación aconseja consultar como máximo 4 veces por día, atribuir el origen y enlazar la oferta original; la app aplica una espera de 6 horas cuando está habilitada.
- **Greenhouse / Lever:** API de publicaciones abiertas para empresas que selecciones. Introduce el *board token* o *site name* público, no credenciales.
- No se salta CAPTCHA, no se extraen datos protegidos por inicio de sesión, no se hacen envíos masivos y no se inventa experiencia ni respuestas. Antes de implementar cada portal adicional hay que comprobar sus condiciones y permiso de automatización.

**Privacidad y seguridad:** uso local; `data/` contiene el perfil y el seguimiento. No ejecutes el panel en una red compartida ni en un servidor accesible públicamente. En un PC corporativo utiliza la aplicación solo si las políticas internas lo permiten.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Desarrollo y próximos hitos

Consulta [ROADMAP.md](ROADMAP.md) y [PROMPT_CODEX_CLAUDE.md](PROMPT_CODEX_CLAUDE.md). Las fases futuras contemplan mejorar el ranking y preparar postulaciones asistidas; cualquier interacción automatizada con portales dependerá de sus condiciones y de la revisión del usuario. Los cambios del panel FastAPI + React aún no forman parte de la versión documentada en este README.
