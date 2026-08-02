@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Creation de l'environnement Python...
  python -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
  echo Installation des dependances...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)

".venv\Scripts\python.exe" server.py %*
goto :eof

:error
echo.
echo Echec de l'installation. Verifie que Python 3.10+ est installe et dans le PATH.
pause
