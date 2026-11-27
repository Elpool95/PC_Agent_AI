import os
import subprocess

# Carica eventuali variabili da un file .env locale (es. GEMINI_API_KEY) senza dipendenze esterne
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    try:
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _k, _v = _line.split("=", 1)
                _k = _k.strip()
                _v = _v.strip().strip('"').strip("'")
                if _k and _v and _k not in os.environ:
                    os.environ[_k] = _v
    except Exception:
        pass

# Modello Gemini principale, fallback automatici e timeout (in millisecondi)
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_FALLBACK_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]
GEMINI_TIMEOUT_MS = 30000

# Soglie di allerta per la telemetria live
CPU_WARN = 65
CPU_CRIT = 85
GPU_TEMP_WARN = 70
GPU_TEMP_CRIT = 80
RAM_CRIT = 85
DISK_WARN = 80
DISK_CRIT = 90

# Processi sicuri da chiudere in Modalità Gaming
SAFE_TO_CLOSE = [
    "chrome.exe", "msedge.exe", "firefox.exe",
    "onedrive.exe", "spotify.exe", "teams.exe"
]

# Processi PROTETTI che non verranno MAI chiusi
PROTECTED_PROCESSES = {
    "vgtray.exe", "vgc.exe",
    "riotclientservices.exe", "riotclientux.exe", "riotclientuxrender.exe",
    "discord.exe",
    "steam.exe", "steamwebhelper.exe", "steamservice.exe"
}

NO_WINDOW = subprocess.CREATE_NO_WINDOW