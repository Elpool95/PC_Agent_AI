# PC Agent AI — Guida di Progetto per Agent

Progetto desktop Python/Tkinter per Windows 10/11: telemetria hardware live + ottimizzazione rapida gaming + chatbot Google Gemini con tool locali.

## Mappa dei file

- `config/settings.py`: definisce `BASE_DIR`, `REPORTS_DIR`, carica `.env` (da root o `config/.env`), definisce `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `GEMINI_TIMEOUT_MS`, soglie allerta (`CPU_*`, `GPU_TEMP_*`, `RAM_CRIT`, `DISK_*`), `SAFE_TO_CLOSE`, `PROTECTED_PROCESSES` e `NO_WINDOW`.
- `modules/tools.py`: funzioni di sistema e tool esposti a Gemini — CPU/RAM/top processi (`analizza_sistema`), temperatura/W/ventole CPU via LibreHardwareMonitor `localhost:8085` (`leggi_sensori_cpu`), GPU via `nvidia-smi` (`monitora_gpu`), dischi dinamici e analisi cache (`elenca_lettere_dischi`, `mappa_dischi_fisici`, `monitora_archiviazione`, `analizza_spazio_disco`), banchi RAM via WMI (`info_banchi_ram`), rete e ping (`info_rete_attiva`, `misura_ping`), versioni OS/driver (`info_versioni_sistema`, `info_cpu_nome`), piano energetico (`piano_energetico_attivo`, `attiva_modalita_prestazioni`, `ripristina_modalita_bilanciata`), avvio automatico (`elenca_app_avvio`, `disabilita_app_avvio`), pulizia temp (`pulisci_file_temporanei`) e chiusura sicura (`termina_processo`).
- `modules/ai_agent.py`: classe `GeminiAgent` con prompt di sistema generato dinamicamente dall'hardware rilevato, registrazione tool e fallback automatico tra modelli Gemini su errori `503`/`504`/`429`/`404`.
- `modules/agent_win11.py`: GUI Tkinter (`PCAgentGUI`) avviata come `pythonw -m modules.agent_win11`, con barra telemetria live (CPU+ventole, RAM+banchi, griglia dischi con colore per singolo disco, GPU, Rete+ping), pulsanti rapidi, console chat e footer OS/driver.
- `.agents/rules/` e `.agents/skills/`: regole e skill personalizzate per Antigravity.
- `doc/`: documentazione tecnica completa (`architecture.md`, `security.md`, `testing-and-skills.md`, `changelog.md`).
- `reports/`: cartella dedicata ai file di log runtime e report JUnit XML (`*.log`, `*.xml` ignorati da Git).
- `install.bat` / `avvia_agent.bat`: installer automatico (`.venv`, `requirements.txt`, `config/.env`, icona Desktop) e launcher portabile senza console (`pythonw -m modules.agent_win11`).
- `config/.env.example` / `requirements.txt` / `README.md`: template API key, dipendenze e documentazione.

## Vincoli di progetto e architettura

- **Portabilità assoluta**: mai hardcodare percorsi utente (`C:\Users\...`), nomi di CPU/GPU/RAM o lettere di disco fisse; tutto deve essere rilevato dinamicamente a runtime.
- **Zero finestre console fantasma**: ogni chiamata `subprocess` verso PowerShell, `nvidia-smi`, `ping` o `powercfg` deve passare `creationflags=NO_WINDOW`.
- **UI non bloccante e resiliente**: inizializzazione di `GeminiAgent`, query WMI e azioni rapide girano su thread daemon; l'app deve aprirsi e mostrare la telemetria anche offline o senza `GEMINI_API_KEY`.
- **Layout Tkinter**: `footer_frame` e `input_frame` restano ancorati con `side=tk.BOTTOM` prima dell'area chat (`expand=True`) così non vengono mai spinti fuori schermo.
- **Lingua**: etichette pulsanti in inglese breve (`Top Process`, `Storage`, `Gaming Mode`, `Balance`, `Start App`, `RAM Detail`, `Clear`, `Send`); messaggi di sistema, chat e commenti in italiano.

## Vincoli di sicurezza

- Mai terminare né disabilitare processi in `PROTECTED_PROCESSES` (Riot Vanguard, Riot Client, Discord, Steam) o in `_PROCESSI_SISTEMA_PROTETTI` (`tools.py`).
- L'agent AI deve chiedere sempre conferma esplicita prima di disabilitare un'app all'avvio o terminare un processo.
- Mai committare `.env`, `.venv/`, `errore.log` o chiavi API.

## Convenzioni di verifica e Git

- Dopo modifiche Python, verificare sempre con:
  `python -m py_compile config/settings.py modules/tools.py modules/ai_agent.py modules/agent_win11.py`
- Messaggi di commit in stile Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
