import os
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
GAMING_STATE_FILE = os.path.join(REPORTS_DIR, "gaming_state.json")

# Carica eventuali variabili da un file .env locale (root o config/.env) senza dipendenze esterne
for _env_path in (
    os.path.join(BASE_DIR, ".env"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
):
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

# Intervalli di aggiornamento telemetria live (secondi)
TELEMETRY_INTERVAL_NORMAL = 1
TELEMETRY_INTERVAL_GAMING = 2.5

# Limite FPS NVIDIA automatico in Gaming Mode (refresh_hz - margine, minimo 30 FPS)
FPS_CAP_MARGIN_HZ = 3
FPS_CAP_MIN = 30

# Processi sicuri da chiudere in Modalità Gaming
SAFE_TO_CLOSE = [
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe",
    "onedrive.exe", "googledrivesync.exe", "dropbox.exe",
    "spotify.exe", "teams.exe", "ms-teams.exe", "slack.exe",
    "widgets.exe", "widgetservice.exe", "phoneexperiencehost.exe", "yourphone.exe",
    "ccxprocess.exe", "adobe desktop service.exe",
]

# Processi PROTETTI che non verranno MAI chiusi
PROTECTED_PROCESSES = {
    "vgtray.exe", "vgc.exe",
    "riotclientservices.exe", "riotclientux.exe", "riotclientuxrender.exe",
    "discord.exe",
    "steam.exe", "steamwebhelper.exe", "steamservice.exe"
}

# Servizi Windows non essenziali mettibili temporaneamente in pausa in Gaming Mode (allowlist fissa)
GAMING_PAUSABLE_SERVICES = ("WSearch", "SysMain", "DiagTrack")

# Processi background tenuti aperti in Gaming Mode ma impostati a priorità CPU ridotta (mai anti-cheat, Riot o sistema)
GAMING_THROTTLE_PROCESSES = {
    "steamwebhelper.exe",
    "discord.exe",
    "epicwebhelper.exe",
}

NO_WINDOW = subprocess.CREATE_NO_WINDOW