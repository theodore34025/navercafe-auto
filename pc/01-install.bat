@echo off
setlocal
cd /d "%~dp0.."
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto python_missing
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install .
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto failed
echo Installation complete. Run pc\02-login.bat next.
pause
exit /b 0
:python_missing
echo Install Python 3.12 from python.org, including the Python launcher.
pause
exit /b 1
:failed
echo Installation failed. Read the error above. Do not continue until fixed.
pause
exit /b 1
