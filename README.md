# PC Agent AI

Assistente desktop per **Windows 10/11** con telemetria hardware in tempo reale, ottimizzazione rapida per il gaming e chatbot AI basato su **Google Gemini** con esecuzione sicura di strumenti locali.

## Funzionalità principali

- **Telemetria live (aggiornamento ogni 2s)**:
  - **CPU**: utilizzo `%`, temperatura `°C`, consumo `W` e ventole di sistema `RPM` *(tramite LibreHardwareMonitor)*.
  - **RAM**: utilizzo, tipo DDR, frequenza attiva `MHz`, modalità canale (`Dual Channel` / `Single Channel`) e dettaglio dei singoli banchi fisici.
  - **Dischi**: rilevamento automatico di tutte le unità montate, spazio libero, velocità `R/W MB/s` e avvisi colore per dischi quasi pieni.
  - **GPU NVIDIA**: utilizzo `%`, temperatura `°C`, VRAM, consumo `W`, ventole `%` e frequenza Core `MHz` *(tramite `nvidia-smi`)*.
  - **Rete**: interfaccia attiva, link speed, IP locale, traffico `↓ / ↑` live e `Ping` verso `1.1.1.1`.
  - **Footer di sistema**: versione di Windows e versione del driver grafico installato.
- **Azioni rapide locali**:
  - `Top Process`: mostra i Top 5 processi per CPU e i Top 5 per RAM.
  - `Storage`: riepilogo partizioni e analisi delle principali cache/cartelle pesanti su `C:`.
  - `Gaming Mode` / `Balance`: passa tra piano *Prestazioni eccellenti* (chiudendo app non essenziali e pulendo file temporanei) e *Bilanciato*, rilevando automaticamente il piano attivo all'avvio.
  - `Start App`: elenca le applicazioni all'avvio automatico di Windows.
  - `RAM Detail`: report completo su RAM fisica, paging e moduli installati.
- **Chatbot AI (Google Gemini)**:
  - Rileva automaticamente l'hardware del PC su cui viene eseguito.
  - Può interrogare tutti i sensori, analizzare dischi/processi, disabilitare app all'avvio e terminare processi bloccati in modo sicuro (chiedendo sempre conferma e bloccando processi di sistema/protetti).
  - Fallback automatico tra modelli Gemini in caso di sovraccarico dei server (`503`/`429`).

## Requisiti

- **Windows 10 / 11**
- **Python 3.10+** (con `Add Python to PATH` abilitato)
- **Chiave API Gemini** (gratuita su [Google AI Studio](https://aistudio.google.com/apikey)) — *opzionale: senza chiave la telemetria e i pulsanti locali funzionano comunque*
- *(Opzionale)* **[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor)** con Web Server attivo su `http://localhost:8085` per leggere temperatura CPU, Watt CPU e ventole scheda madre
- *(Opzionale)* GPU **NVIDIA** con driver installati per la telemetria GPU (`nvidia-smi`)

## Installazione rapida

1. Scarica o clona questo repository:
   ```bash
   git clone https://github.com/Elpool95/PC_Agent_AI.git
   cd PC_Agent_AI
   ```
2. Fai doppio clic su **`install.bat`**:
   - Crea un ambiente virtuale isolato (`.venv`)
   - Installa le dipendenze da `requirements.txt`
   - Crea il file `config/.env` da `config/.env.example`
   - Crea automaticamente l'icona di avvio **"PC Agent AI"** sul Desktop
3. Apri il file `config/.env` e inserisci la tua API Key:
   ```env
   GEMINI_API_KEY=la_tua_chiave_api
   ```
   *(In alternativa puoi impostare `GEMINI_API_KEY` come variabile d'ambiente di Windows).*
4. Avvia l'app con **`avvia_agent.bat`** (o dal collegamento sul Desktop).

## Personalizzazione

Puoi modificare soglie di allerta, modelli Gemini, app chiudibili in `Gaming Mode` e processi protetti in `config/settings.py`.

## Struttura del progetto

- `config/` — configurazioni, soglie e `pytest.ini` (`settings.py`, `.env.example`)
- `modules/` — moduli applicativi (`agent_win11.py`, `ai_agent.py`, `tools.py`)
- `tests/` — suite di test unitari, sicurezza e usabilità GUI
- `doc/` — documentazione tecnica completa (`architecture.md`, `security.md`, `testing-and-skills.md`, `licenses.md`, `changelog.md`)
- `reports/` — log runtime e report JUnit XML (`junit.xml`)
- `.agents/` — regole (`rules/`) e skill (`skills/`) per coding agent

## Autore & Licenza

- **Autore**: Elpool95
- **Licenza**: [MIT License](LICENSE) — per l'elenco completo delle licenze di terze parti (`psutil` BSD-3-Clause, `google-genai` Apache-2.0, `pytest` MIT, ecc.) vedi [doc/licenses.md](doc/licenses.md).
