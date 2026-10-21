@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JobHunter CL

echo ====================================================
echo   JOBHUNTER CL - Panel local (FastAPI + React)
echo ====================================================
echo Carpeta: %CD%
echo.

if not exist "start.py" (
  echo [ERROR] No se encontro start.py. Ejecuta este archivo desde la carpeta del proyecto.
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
    goto :fail
  )
)

".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Se requiere Python 3.11 o posterior en .venv.
  goto :fail
)

".venv\Scripts\python.exe" -c "import fastapi, uvicorn, requests, bs4" >nul 2>nul
if errorlevel 1 (
  echo [2/3] Instalando dependencias de Python. Puede tardar unos minutos...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias. Revisa internet, proxy o politicas del PC.
    goto :fail
  )
) else (
  echo [2/3] Dependencias de Python encontradas.
)

echo [3/3] Iniciando JobHunter CL...
echo Deja esta ventana abierta. Para cerrar: Ctrl+C o cierra la ventana.
echo.
".venv\Scripts\python.exe" start.py %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo No se completo el inicio. Copia el error de esta ventana para diagnosticarlo.
echo (No pegues contrasenas ni tokens.)
pause
exit /b 1
