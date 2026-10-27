@echo off
setlocal
cd /d "%~dp0.."
echo [1/4] Checking Python 3.12 64-bit...
py -3.12 -c "import sys, struct; print(sys.version); sys.exit(0 if struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto python_missing
echo [2/4] Preparing isolated PC environment...
py -3.12 -m venv .venv-pc
if errorlevel 1 goto failed
.venv-pc\Scripts\python.exe -c "import sys, struct; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto wrong_environment
echo [3/4] Installing PC dependencies (no C compiler required)...
.venv-pc\Scripts\python.exe -m pip install --only-binary=:all: .
if errorlevel 1 goto failed
echo [4/4] Installing Chromium...
.venv-pc\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto failed
echo Installation complete. Run pc\02-login.bat next.
pause
exit /b 0
:python_missing
echo Python 3.12 64-bit and the Python launcher are required.
echo Download: https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
echo Install Python 3.12 alongside any existing Python, then run this file again.
pause
exit /b 1
:wrong_environment
echo The existing .venv-pc uses an incompatible Python.
echo Rename .venv-pc and run this installer again. Keep .naver-session.json unchanged.
pause
exit /b 1
:failed
echo Installation failed. Send a screenshot showing the step number and error above.
pause
exit /b 1
