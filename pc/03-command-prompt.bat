@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\activate.bat goto missing
echo Read PC_START.md for post and comment commands.
echo Commands start with navercafe. Type exit to close this window.
cmd /k .venv\Scripts\activate.bat
exit /b 0
:missing
echo Run pc\01-install.bat first.
pause
exit /b 1
