@echo off
setlocal
cd /d "%~dp0"
if not defined SLT_PYTHON set SLT_PYTHON=python
if not defined SLT_DATA_DIR set SLT_DATA_DIR=%~dp0..\local_data
if not exist "%SLT_DATA_DIR%\config.yaml" (
  echo Missing local config. Run python ..\desktop\init_local_data.py first for mock data.
  pause
  exit /b 1
)
"%SLT_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
