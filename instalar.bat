@echo off
cd /d "%~dp0"
echo Creando el entorno de Python en la carpeta "venv"...
python -m venv venv
if errorlevel 1 (
  echo.
  echo No se encontro Python. Instala Python 3.12 desde https://www.python.org/downloads/
  echo y marca la casilla "Add python.exe to PATH" durante la instalacion.
  pause
  exit /b 1
)
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Hubo un error instalando las dependencias.
  pause
  exit /b 1
)
echo.
echo Instalacion terminada. Ahora abre iniciar.bat
pause
