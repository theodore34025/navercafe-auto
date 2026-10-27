@echo off
setlocal
cd /d "%~dp0.."
if not exist .venv\Scripts\navercafe.exe goto missing
.venv\Scripts\navercafe.exe login
set "task_exit=%errorlevel%"
pause
exit /b %task_exit%
:missing
echo Run pc\01-install.bat first.
pause
exit /b 1
