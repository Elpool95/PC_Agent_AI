# Architettura — PC Agent AI

## Panoramica
**PC Agent AI** è un'applicazione desktop Python/Tkinter portabile per Windows 10/11 che combina:
1. **Telemetria hardware live** (aggiornamento ogni 2 secondi su thread daemon separati).
2. **Azioni rapide locali** (a 0 token) per analisi processi, dischi, RAM, avvio automatico, piani energetici e sicurezza LHM.
3. **Chatbot AI (Google Gemini)** con rilevamento dinamico dell'hardware del PC, esecuzione sicura di tool locali e fallback automatico tra modelli.

## Struttura del repository

```text
PC_Agent_AI/
├── .agents/
│   ├── rules/                  # Regole sempre attive (project.md, security.md, testing.md)
│   └── skills/                 # Skill on-demand (test-suite, usability-test, skill-evaluator)
├── config/
│   ├── __init__.py
│   ├── .env.example            # Template API key Gemini
│   ├── pytest.ini              # Configurazione pytest (JUnit XML + coverage >= 80%)
│   └── settings.py             # Soglie allerta, modelli Gemini, processi protetti, loader .env
├── doc/                        # Documentazione tecnica di progetto
│   ├── architecture.md
│   ├── changelog.md
│   ├── security.md
│   └── testing-and-skills.md
├── modules/
│   ├── __init__.py
│   ├── agent_win11.py          # GUI Tkinter (PCAgentGUI)
│   ├── ai_agent.py             # Client Google Gemini + HITL + fallback modelli
│   └── tools.py                # Sensori hardware, dischi, rete, powercfg, processi, firewall
├── reports/                    # Report JUnit XML e log runtime (ignorati da Git)
├── tests/                      # Suite di test unitari, sicurezza e GUI
│   ├── test_ai_agent.py
│   ├── test_gui.py
│   └── test_tools.py
├── avvia_agent.bat             # Launcher portabile senza console (pythonw -m modules.agent_win11)
├── install.bat                 # Installer automatico (.venv, dipendenze, config/.env, icona Desktop)
├── README.md
├── requirements.txt
└── requirements-dev.txt
```

## Componenti chiave

### 1. Configurazione (`config/settings.py`)
- Carica automaticamente `GEMINI_API_KEY` da `.env` o `config/.env` senza dipendenze esterne.
- Definisce `GEMINI_MODEL` (`gemini-3.8-flash`), la catena `GEMINI_FALLBACK_MODELS` (`gemini-3.7-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`) e `GEMINI_TIMEOUT_MS`.
- Centralizza le soglie di allerta (`CPU_WARN`, `CPU_CRIT`, `GPU_TEMP_WARN`, `GPU_TEMP_CRIT`, `RAM_CRIT`, `DISK_WARN`, `DISK_CRIT`), `SAFE_TO_CLOSE`, `PROTECTED_PROCESSES` e `NO_WINDOW`.

### 2. Telemetria & Strumenti (`modules/tools.py`)
- **CPU & Ventole**: utilizzo via `psutil`; temperatura, consumo `W` e ventole scheda madre (`RPM`) via LibreHardwareMonitor (`http://localhost:8085/data.json`).
- **RAM**: utilizzo e paging via `psutil`; dettaglio banchi fisici, frequenza `MHz`, voltaggio, tipo DDR e modalità canale (`Dual Channel` / `Single Channel`) via WMI (`Win32_PhysicalMemory`).
- **Dischi**: rilevamento dinamico di tutte le unità montate, mappatura `PhysicalDriveX`, velocità `R/W MB/s` e analisi cache principali su `C:`.
- **GPU NVIDIA**: utilizzo `%`, temperatura `°C`, VRAM, Watt, Fan `%` e Core Clock `MHz` via `nvidia-smi`.
- **Rete**: interfaccia attiva, link speed, IP locale, traffico `↓ / ↑` e latenza `Ping` verso `1.1.1.1`.
- **Sistema & Controllo**: rilevamento versione Windows 11 e driver GPU, piano energetico attivo (`powercfg`), gestione app all'avvio (`HKCU\Run`), pulizia `TEMP`, chiusura sicura processi e protezione porta `8085` via Windows Firewall.

### 3. Agent AI (`modules/ai_agent.py`)
- Costruisce il prompt di sistema dinamicamente rilevando CPU, core, RAM, GPU e versione Windows a runtime.
- Gestisce il fallback automatico su errori `503`, `504`, `429` e `404` preservando la cronologia chat.
- Applica conferma obbligatoria lato codice (Human-in-the-Loop) su tutti i tool che modificano lo stato del sistema.

### 4. Interfaccia Grafica (`modules/agent_win11.py`)
- Finestra `900x760` (minima `820x620`) con `footer_frame` e `input_frame` ancorati in basso (`side=tk.BOTTOM`) così da restare sempre visibili.
- Griglia dinamica per i dischi con colore indipendente per singola partizione (`#ff5252` critico, `#ffb74d` warning, `#ce93d8` normale).
- Inizializzazione non bloccante di `GeminiAgent` in background: l'app resta pienamente usabile anche offline.
