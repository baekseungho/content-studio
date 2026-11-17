@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0app.py"
) else (
  python "%~dp0app.py"
)
pause
