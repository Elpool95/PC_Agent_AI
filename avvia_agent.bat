@echo off
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0agent_win11.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0agent_win11.py"
    exit /b 0
)

where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "%~dp0agent_win11.py"
    exit /b 0
)

echo Python non trovato nel sistema. Esegui prima install.bat o installa Python 3.10+.
pause
