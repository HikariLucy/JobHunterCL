# JobHunter CL — MVP local

Buscador y organizador personal de ofertas laborales para Chile y trabajos remotos. Incluye lectura de fuentes públicas, matching configurable, deduplicación, SQLite, estados y respaldo transferible entre computadores.

**Estado:** MVP de búsqueda y seguimiento. **No postula automáticamente**. Los formularios se abren en el portal de origen para revisión humana. No se han validado en vivo las integraciones en la red de tu equipo.

## Windows (PowerShell)

Necesitas **Python 3.11 o superior**, internet y permiso para instalar programas en el PC de trabajo. **Opción fácil:** descomprime **todo** el ZIP, entra en `JobHunter-CL` y haz doble clic en `INICIAR-WINDOWS.bat`. El iniciador comprueba Python 3.11+, crea o reutiliza `.venv`, instala paquetes si faltan, espera a que Streamlit responda y abre el navegador. **Deja la ventana CMD abierta** mientras utilices la aplicación. Si el navegador no aparece, la propia consola imprime la URL `http://127.0.0.1:8501` (u otro puerto libre). Si prefieres la terminal, usa estos comandos:

```powershell
cd "$HOME\Documents"
# Descomprime el ZIP completo en Documentos antes de ejecutar:
cd .\JobHunter-CL
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launch.py
```

Si `py` no existe pero `python` sí, cambia `py -m venv .venv` por `python -m venv .venv`.

## Ubuntu / Linux

La opción rápida es `bash iniciar-linux.sh`; verifica las dependencias y abre el navegador al levantar el servidor. También puedes ejecutar los comandos manualmente:

```bash
cd ~/proyectos/JobHunter-CL
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python launch.py
```

La interfaz se abre normalmente en http://127.0.0.1:8501 (o el siguiente puerto libre). En la pestaña **Perfil y fuentes** adapta los cargos y habilidades a tu caso. Luego pulsa **Buscar nuevas ofertas**. Get on Board es la fuente inicial; Remotive y compañías de Greenhouse/Lever son opcionales. No se consulta de manera continua: debes hacer clic y existe una espera para evitar solicitudes excesivas.

## Continuar desde casa

1. No subas `data/`, CV, secretos ni `.venv/` a GitHub; el proyecto los ignora.
2. Tras crear tu repositorio **privado** de GitHub, envía el código con Git. En casa ejecuta `git clone URL_DEL_REPO` y crea otro entorno virtual.
3. Si quieres mantener las ofertas y sus estados, usa **Seguimiento → Descargar respaldo JSON** y luego **Importar respaldo** en casa por un canal personal seguro. El respaldo incluye el perfil y puede contener notas privadas; transfiérelo por un canal personal seguro.

### Repositorio existente: HikariLucy/jobhunter

Ya existe el repositorio privado [HikariLucy/jobhunter](https://github.com/HikariLucy/jobhunter). **No vuelvas a crearlo.** Puedes clonar el proyecto en otro equipo así:

```powershell
git clone https://github.com/HikariLucy/jobhunter.git
cd jobhunter
.\INICIAR-WINDOWS.bat
```

Desde Ubuntu:

```bash
git clone https://github.com/HikariLucy/jobhunter.git ~/proyectos/jobhunter
cd ~/proyectos/jobhunter
bash iniciar-linux.sh
```

GitHub solo guarda el código. El archivo `data/profile.json`, la base de datos y los CV personales **no** se suben. Si necesitas recuperar tus postulaciones, utiliza el respaldo JSON dentro de la pestaña «Seguimiento» y guárdalo de forma privada.

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

## Próximos hitos

Revisar `ROADMAP.md` y `PROMPT_CODEX_CLAUDE.md`. La fase de automatizar formularios es asistida, permitida según cada sitio y con confirmación antes del envío.
