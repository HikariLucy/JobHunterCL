@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JobHunter CL - Inicio Windows

echo ====================================================
echo   JOBHUNTER CL - Inicio local en Windows
echo ====================================================
echo Carpeta: %CD%
echo.

if not exist "app.py" (
  echo [ERROR] No se encontro app.py.
  echo Extrae el ZIP completo y ejecuta este archivo desde su carpeta.
  goto :fail
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creando entorno virtual de Python...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo [ERROR] No se encontro Python. Necesitas Python 3.11 o posterior.
      goto :fail
    )
    python -m venv .venv
  )
  if errorlevel 1 (
    echo [ERROR] No se pudo crear el entorno virtual.
    echo Comprueba que Python este instalado y permita crear entornos venv.
    goto :fail
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] El entorno virtual esta incompleto.
  echo Cambia el nombre de .venv por .venv-anterior y vuelve a intentarlo.
  goto :fail
)

".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ requerido'"
if errorlevel 1 (
  echo [ERROR] Version de Python incompatible o entorno danado.
  echo Instala Python 3.11+ y vuelve a crear .venv.
  goto :fail
)

".venv\Scripts\python.exe" -c "import streamlit, requests, bs4" >nul 2>nul
if errorlevel 1 (
  echo [2/3] Instalando dependencias. Puede tardar unos minutos...
  ".venv\Scripts\python.exe" -m ensurepip --upgrade >nul 2>nul
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias.
    echo Revisa conexion a internet, proxy o politicas del PC.
    goto :fail
  )
) else (
  echo [2/3] Dependencias encontradas.
)

".venv\Scripts\python.exe" -c "import streamlit, requests, bs4"
if errorlevel 1 (
  echo [ERROR] Las dependencias no funcionan en este entorno.
  goto :fail
)

echo [3/3] Iniciando JobHunter CL...
echo La consola debe permanecer abierta mientras utilices la app.
echo.
".venv\Scripts\python.exe" launch.py
if errorlevel 1 goto :fail

echo.
echo JobHunter CL se ha cerrado.
pause
exit /b 0

:fail
echo.
echo No se ha completado el inicio. Copia el error de esta ventana
echo o envia una captura para poder diagnosticarlo.
pause
exit /b 1
