@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.11 with Python Launcher enabled.
  exit /b 1
)
py -3.11 --version || exit /b 1
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv || exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip || exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt || exit /b 1
echo.
echo TBA ready. Start: .venv\Scripts\python.exe app.py
echo Then open: http://127.0.0.1:5000
echo Optional Piper/Parler offline voice models are not installed.
