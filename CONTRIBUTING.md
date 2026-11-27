# Contribuire a Elpool Agent PC (PC Agent AI)

Grazie per l'interesse nel contribuire a **Elpool Agent PC**! Questo progetto nasce per offrire una telemetria hardware leggera e una **Gaming Mode** efficace e sicura su Windows 10/11, con particolare attenzione ai PC con componenti datati o configurazioni CPU-bound.

---

## 1. Setup dell'ambiente di sviluppo

1. Fai il fork del repository e clonalo in locale:
   ```bash
   git clone https://github.com/Elpool95/PC_Agent_AI.git
   cd PC_Agent_AI
   ```
2. Crea e attiva un ambiente virtuale Python 3.10+:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Installa le dipendenze di runtime e sviluppo:
   ```powershell
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. *(Opzionale)* Copia `config/.env.example` in `config/.env` e inserisci una `GEMINI_API_KEY` per testare il chatbot AI. L'app e tutti i test funzionano comunque anche senza API key.

---

## 2. Vincoli di architettura e qualità del codice

Ogni contributo deve rispettare i seguenti principi:

- **Portabilità assoluta**: non hardcodare mai percorsi utente (`C:\Users\...`), nomi di CPU/GPU/RAM, risoluzioni monitor o lettere di disco fisse. Tutto va rilevato dinamicamente a runtime.
- **Zero finestre console fantasma**: ogni chiamata `subprocess` verso PowerShell, `nvidia-smi`, `ping`, `powercfg` o `netsh` deve usare `creationflags=NO_WINDOW` e liste di argomenti esplicite (**mai `shell=True`**).
- **UI non bloccante e resiliente**: query WMI, chiamate AI e azioni locali devono girare su thread daemon; la finestra deve aprirsi e mostrare la telemetria anche offline.
- **Layout Tkinter**: `footer_frame` e `input_frame` restano ancorati con `side=tk.BOTTOM` prima dell'area chat (`expand=True`).
- **Sicurezza & reversibilità**:
  - Mai terminare o disabilitare processi in `PROTECTED_PROCESSES` o `_PROCESSI_SISTEMA_PROTETTI`.
  - Ogni modifica della Gaming Mode (piano energetico, registro HKCU, limite FPS NVIDIA, servizi) deve essere salvata in `reports/gaming_state.json` e completamente reversibile tramite **`Balance`**.
  - Ogni tool distruttivo o UAC esposto a Gemini deve richiedere conferma esplicita lato codice (`confirm_callback`).
- **Lingua**: etichette pulsanti in inglese breve (`Top Process`, `Storage`, `Gaming Mode`, `Balance`, `Start App`, `RAM Detail`, `Lock LHM`, `Clear`, `Send`); messaggi di sistema, chat e commenti in italiano.

---

## 3. Test e Quality Gate obbligatorio

Prima di aprire una Pull Request:

1. **Nuove funzionalità / Bugfix**:
   - Aggiungi test unitari dedicati in `tests/` (`test_tools.py`, `test_ai_agent.py` o `test_gui.py`) coprendo caso nominale e casi limite/errore.
   - Per bugfix, includi un test di regressione.
   - Per modifiche a comandi OS o tool AI, includi almeno un test negativo/DAST (input malformati, path traversal, metacaratteri o processi protetti).
2. **Verifica sintassi**:
   ```powershell
   python -m py_compile config/settings.py modules/tools.py modules/ai_agent.py modules/agent_win11.py
   ```
3. **Suite completa e coverage (`>= 80%`)**:
   ```powershell
   python -m pytest -c config/pytest.ini --rootdir=.
   ```
   Tutti i test devono passare (`0 failed`, `0 errors`) con copertura totale **`>= 80%`** su `config` e `modules`.

---

## 4. Commit, Versioning e Pull Request

- Usa messaggi di commit in stile **Conventional Commits**:
  - `feat:` nuove funzionalità
  - `fix:` correzione bug
  - `docs:` documentazione
  - `refactor:` ristrutturazione senza cambi funzionali
  - `test:` aggiunta o aggiornamento test
  - `chore:` manutenzione e configurazioni
- **Semantic Versioning (`MAJOR.MINOR.PATCH`)**: a ogni release `patch`, `minor` o `major`, aggiorna sempre insieme:
  1. `APP_VERSION` in `config/settings.py`
  2. La versione corrente in `README.md`
  3. Le note di rilascio in `doc/changelog.md`
- Non committare mai `.env`, `config/.env`, `.venv/`, `reports/*.log` o chiavi API.
- Apri la Pull Request descrivendo chiaramente cosa risolve o migliora, come testarla ed eventuali screenshot se riguarda la GUI.
