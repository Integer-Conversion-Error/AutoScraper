@echo off
setlocal

set "VENV_PY=%~dp0venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  set "PYTHON=%VENV_PY%"
) else (
  set "PYTHON=python"
)

echo Using Python: %PYTHON%
echo Starting Celery Worker...
start "Celery Worker" cmd /c "\"%PYTHON%\" -m celery -A autoscraper_py.tasks:celery_app worker --loglevel=info -P solo"

echo Starting Flask App with Waitress...
start "Flask App" cmd /c "\"%PYTHON%\" -m waitress --host=127.0.0.1 --port=5000 autoscraper_py.wsgi:app & pause"
