import subprocess

# Modello Gemini e timeout (in millisecondi)
GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_TIMEOUT_MS = 60000

# Soglie di allerta per la telemetria live
CPU_WARN = 65
CPU_CRIT = 85
GPU_TEMP_WARN = 70
GPU_TEMP_CRIT = 80
RAM_CRIT = 85

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