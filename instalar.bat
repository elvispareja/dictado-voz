@echo off
cd /d "%~dp0"
python --version >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python. Instalalo desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
  pause
  exit /b 1
)

rem uv descarga Python 3.12 solo para esta app, sea cual sea el Python instalado
rem (las librerias de voz aun no tienen version para Python 3.15).
echo Instalando uv...
python -m pip install --upgrade uv
if errorlevel 1 goto error

if exist venv (
  echo Borrando el entorno anterior...
  rmdir /s /q venv
)
echo Creando el entorno con Python 3.12, se descarga si no lo tienes...
python -m uv venv venv --python 3.12
if errorlevel 1 goto error

echo Instalando las librerias...
python -m uv pip install --python venv\Scripts\python.exe -r requirements.txt
if errorlevel 1 goto error

echo.
echo Instalacion terminada. Ahora abre iniciar.bat
pause
exit /b 0

:error
echo.
echo Hubo un error durante la instalacion.
pause
exit /b 1
