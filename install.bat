@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   PC Agent AI - Installazione Automatica
echo ============================================
echo.

set "PY_CMD="
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [ERRORE] Python 3.10+ non trovato nel sistema.
    echo Scaricalo da https://www.python.org/downloads/ selezionando "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/4] Creazione ambiente virtuale (.venv)...
if not exist ".venv\Scripts\python.exe" (
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERRORE] Impossibile creare l'ambiente virtuale .venv.
        pause
        exit /b 1
    )
)

echo [2/4] Installazione dipendenze da requirements.txt...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\pip.exe" install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERRORE] Errore durante l'installazione delle dipendenze.
    pause
    exit /b 1
)

echo [3/4] Configurazione file config\.env...
if not exist "config\.env" if not exist ".env" (
    if exist "config\.env.example" (
        copy /Y "config\.env.example" "config\.env" >nul
        echo File config\.env creato da config\.env.example. Ricordati di inserire la tua GEMINI_API_KEY!
    )
)

echo [4/4] Creazione collegamento sul Desktop...
powershell -NoProfile -Command "$s = New-Object -ComObject WScript.Shell; $lnk = $s.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\PC Agent AI.lnk'); $lnk.TargetPath = '%~dp0avvia_agent.bat'; $lnk.WorkingDirectory = '%~dp0'; $lnk.WindowStyle = 7; $lnk.Description = 'PC Agent AI - Monitor & Optimizer'; if (Test-Path '%~dp0icon.ico') { $lnk.IconLocation = '%~dp0icon.ico' } else { $lnk.IconLocation = $env:SystemRoot + '\System32\imageres.dll,109' }; $lnk.Save()"
if %errorlevel%==0 (
    echo Collegamento "PC Agent AI" creato sul Desktop!
) else (
    echo [AVVISO] Impossibile creare automaticamente il collegamento sul Desktop.
)

echo.
echo Installazione completata!
echo - Inserisci la tua GEMINI_API_KEY nel file config\.env (o nelle variabili d'ambiente Windows).
echo - Avvia l'app con avvia_agent.bat o dal collegamento sul Desktop.
echo.
pause
