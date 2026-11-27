# Report Quality Gate, SAST, DAST, Pentest & Hardening — v1.0.0

- **Progetto:** Elpool Agent PC (`PC_Agent_AI`)
- **Versione:** `v1.0.0` (`APP_VERSION` in `config/settings.py`)
- **Data verifica:** `2026-11-27`
- **Esito complessivo:** **PASS**

---

## 1. Quality Gate, Test Suite & Coverage

Comando eseguito:
```powershell
python -m py_compile config/settings.py modules/tools.py modules/ai_agent.py modules/agent_win11.py
python -m pytest -c config/pytest.ini --rootdir=.
python .agents/skills/skill-evaluator/scripts/evaluate_skills.py
```

| Verifica | Risultato | Dettaglio |
| :--- | :---: | :--- |
| Compilazione sintattica (`py_compile`) | **PASS** | 4/4 moduli (`settings.py`, `tools.py`, `ai_agent.py`, `agent_win11.py`) |
| Suite `pytest` (Unit, Security, GUI, Skills) | **PASS** | **42/42** test superati (`0 failed`, `0 errors`) |
| Report JUnit XML (`reports/junit.xml`) | **PASS** | Generato localmente (ignorato da Git) |
| Code Coverage totale (soglia `>= 80%`) | **PASS** | **`82.85%`** su `config` e `modules` |
| Skill Evaluator (`.agents/skills/`) | **PASS** | 3/3 skill a **`100/100`** (`skill-evaluator`, `test-suite`, `usability-test`) |

### Dettaglio Code Coverage per modulo

| Modulo | Statements | Miss | Coverage |
| :--- | :---: | :---: | :---: |
| `config/settings.py` | 44 | 3 | **93%** |
| `modules/ai_agent.py` | 98 | 8 | **92%** |
| `modules/agent_win11.py` | 411 | 39 | **91%** |
| `modules/tools.py` | 1208 | 252 | **79%** |
| **TOTALE** | **1761** | **302** | **82.85%** |

---

## 2. SAST (Static Application Security Testing — Bandit AST)

Analisi statica AST eseguita con **Bandit (`bandit>=1.7.0`)** su `config/` e `modules/` (`2.413` righe di codice) + verifica file tracciati su Git (`git ls-files`):
```powershell
.\.venv\Scripts\python.exe -m bandit -r config modules -ll
```

| Controllo SAST | Esito | Evidenza |
| :--- | :---: | :--- |
| **Bandit — Severità High** | **PASS (0 issue)** | Nessuna vulnerabilità critica/alta su 2.413 LoC |
| **Bandit — Severità Medium** | **PASS (0 reali)** | 2 falsi positivi verificati e documentati con `# nosec`: `B310` su URL locale fisso `http://localhost:8085/data.json` e `B104` su controllo difensivo di `0.0.0.0` in `stato_sicurezza_lhm()` |
| `subprocess` con `shell=True` | **PASS (0 hit)** | Tutte le chiamate usano liste di argomenti esplicite e `creationflags=NO_WINDOW` |
| Funzioni pericolose (`eval`, `exec`, `pickle`, `os.system`) | **PASS (0 hit)** | Nessuna occorrenza rilevata |
| Segreti / API Key / file sensibili in Git | **PASS (0 hit)** | `.env`, `config/.env`, `.venv/`, `reports/*.log`, `reports/gaming_state.json` esclusi in `.gitignore` |
| Timeout obbligatori su chiamate esterne | **PASS** | Timeout espliciti su `subprocess` (`3s–10s`), `urllib` LHM (`0.4s`) e client Gemini (`30s`) |

---

## 3. DAST (Dynamic Application Security Testing)

Test dinamici con input malevoli e scenari di fault injection eseguiti automaticamente in `tests/test_tools.py` e `tests/test_gui.py`:

| Vettore di attacco / Scenario | Funzione testata | Esito |
| :--- | :--- | :---: |
| Command & flag injection (`1.1.1.1 & calc.exe`, `-t`, `/?`, `host;whoami`) | `misura_ping()` | **BLOCCATO** (`Host non valido`) |
| Path traversal e unità inesistenti (`../../Windows`, `Z:`) | `analizza_spazio_disco()` | **BLOCCATO** (`errore` controllato) |
| Metacaratteri shell e input vuoti (`notepad.exe & calc`, `""`) | `termina_processo()` | **BLOCCATO** |
| GUID malformato con shell injection (`bad-guid & calc.exe`) | `_ottimizza_piano_gaming()` | **BLOCCATO** (`subprocess.run` mai invocato) |
| Servizi fuori allowlist / injection (`vgc`, `WSearch; calc.exe`) | `pausa_servizi_gaming()` | **BLOCCATO** (UAC mai invocato) |
| Resilienza offline (assenza API key, LHM, `nvidia-smi`, GPU non NVIDIA) | `GeminiAgent`, `PCAgentGUI`, `tools` | **PASS** (nessun crash, degrado controllato) |

---

## 4. Pentest (Abuse Case & Difesa contro Prompt Injection)

| Controllo di sicurezza | Implementazione | Esito |
| :--- | :--- | :---: |
| Conferma Human-in-the-Loop (HITL) lato codice | I 5 tool sensibili esposti a Gemini (`termina_processo`, `disabilita_app_avvio`, `attiva_modalita_prestazioni`, `pulisci_file_temporanei`, `blocca_lhm_da_lan`) sono protetti da `confirm_callback` (`messagebox.askyesno`) | **PASS** |
| Protezione processi anti-cheat e sistema | `PROTECTED_PROCESSES` (Riot Vanguard, Riot Client, Discord, Steam), `_PROCESSI_SISTEMA_PROTETTI` e PID corrente non terminabili né modificabili (verificato da test) | **PASS** |
| Assenza di esecuzione arbitraria via LLM | Nessun tool shell/PowerShell generico o scrittura arbitraria su filesystem esposto a `GeminiAgent` | **PASS** |

---

## 5. Hardening

| Misura di Hardening | Stato | Note |
| :--- | :---: | :--- |
| Minimo privilegio | **ATTIVO** | L'app gira da utente standard; UAC richiesto solo su azioni esplicite (pausa/riavvio servizi, HAGS, regola Firewall LHM) |
| Protezione porta `8085` LibreHardwareMonitor | **ATTIVO** | Controllo automatico esposizione LAN + pulsante `Lock LHM` (regola Windows Defender Firewall `PC_Agent_AI_Block_LHM_8085`) |
| Mascheramento privacy percorsi | **ATTIVO** | `maschera_percorso_utente()` sostituisce la home utente con `%USERPROFILE%` |
| Reversibilità completa Gaming Mode | **ATTIVO** | Snapshot persistente in `reports/gaming_state.json` (piano energetico, registro HKCU, limite FPS NVIDIA, servizi) ripristinato su `Balance` anche dopo riavvio |
| Dipendenze minimali | **ATTIVO** | Solo `psutil` e `google-genai` in `requirements.txt` (NVAPI DRS e monitor letti via `ctypes` nativo Windows) |

---

## 6. SCA / CVE Audit (Dipendenze Python)

Scansione eseguita sull'ambiente `.venv` contro il database ufficiale **OSV / PyPA Advisory Database (CVE & GHSA)**:
```powershell
.\.venv\Scripts\python.exe -m pip_audit
```

| Verifica SCA / CVE | Esito | Dettaglio |
| :--- | :---: | :--- |
| Scansione locale `pip-audit` (`.venv`) | **PASS (0 CVE)** | `No known vulnerabilities found` (verificati `psutil 7.2.2`, `google-genai 3.6.1`, `cryptography 50.0.2`, `requests 2.34.2`, `urllib3 2.8.0` e tutte le dipendenze transitive) |
| Dipendenza dev tracciata | **ATTIVO** | `pip-audit>=2.7.0` aggiunto in `requirements-dev.txt` |
| Monitoraggio CVE continuo su GitHub | **ATTIVO** | Configurato `.github/dependabot.yml` (controllo settimanale su `requirements.txt` e `requirements-dev.txt`) |
