@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

echo =====================================
echo Agent Auth System - Startup
echo =====================================
echo.

echo [1/4] Checking Python...
where py >nul 2>nul
if errorlevel 1 goto :python_failed
py -3 --version
if errorlevel 1 goto :python_failed

echo.
echo [2/4] Creating virtual environment and installing dependencies...
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto :venv_failed
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [3/4] Initializing database...
".venv\Scripts\python.exe" init_db.py
if errorlevel 1 goto :db_failed

echo.
echo [4/4] Starting web service...
echo User page: http://localhost:5000
echo Admin page: http://localhost:5000/admin/dashboard
echo Default login: admin / admin888
echo Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" app.py
exit /b %errorlevel%

:python_failed
echo ERROR: Python 3.8+ is required.
pause
exit /b 1
:venv_failed
echo ERROR: Could not create virtual environment.
pause
exit /b 1
:failed
echo ERROR: Dependency installation failed. Check network and retry.
pause
exit /b 1
:db_failed
echo ERROR: Database initialization failed.
pause
exit /b 1