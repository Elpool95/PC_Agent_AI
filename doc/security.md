# Sicurezza & Hardening — PC Agent AI

Questo documento riassume le misure di sicurezza implementate secondo le regole in `.agents/rules/security.md`.

## 1. SAST (Analisi Statica)
- **Zero `shell=True`**: tutte le chiamate `subprocess` (`powercfg`, `ping`, `nvidia-smi`, `netsh`, PowerShell) usano liste di argomenti esplicite e `creationflags=NO_WINDOW`.
- **Timeout obbligatori**: ogni chiamata esterna (`subprocess` e `urllib`) ha un `timeout` esplicito (`0.4s`–`10s`) per impedire blocchi indefiniti.
- **Nessuna funzione pericolosa**: vietati `eval()`, `exec()`, `pickle` non fidati.
- **Zero segreti nel repository**: `config/.env`, `.env`, `.venv/` e `reports/*.log` sono esclusi in `.gitignore`.

## 2. DAST & Validazione Input
- `misura_ping(host)`: accetta solo hostname/IP validi (`^[A-Za-z0-9.-]{1,253}$`) e blocca flag iniziali (`-`, `/`).
- `analizza_spazio_disco(unita)`: accetta solo lettere di unità valide (`^[A-Z]:$`) realmente esistenti, bloccando path traversal (`..\..\`).
- `termina_processo(target)`: rifiuta separatori di percorso e metacaratteri shell (`\ / ; & | ` `$` `\n` `\r`).

## 3. Pentest & Difesa contro Prompt Injection
- **Conferma obbligatoria Human-in-the-Loop (HITL) lato codice**: i 5 tool sensibili esposti a Gemini (`termina_processo`, `disabilita_app_avvio`, `attiva_modalita_prestazioni`, `pulisci_file_temporanei`, `blocca_lhm_da_lan`) sono incapsulati da un callback che apre un popup nativo Tkinter `messagebox.askyesno`. Nessun errore del modello o prompt injection può eseguire azioni distruttive senza clic esplicito dell'utente.
- **Processi protetti lato codice**: `PROTECTED_PROCESSES` (Riot Vanguard, Riot Client, Discord, Steam) e `_PROCESSI_SISTEMA_PROTETTI` (`explorer.exe`, `svchost.exe`, `lsass.exe`, `librehardwaremonitor.exe`, ecc.) più il PID corrente non possono mai essere terminati.
- **Nessuna esecuzione arbitraria**: Gemini non dispone di tool shell o accesso libero al filesystem.

## 4. Privacy & Hardening di Rete
- **Mascheramento percorsi utente**: `maschera_percorso_utente()` sostituisce la home utente (`C:\Users\<nome>`) con `%USERPROFILE%` nei dati restituiti da `analizza_spazio_disco()` ed `elenca_app_avvio()`.
- **Protezione porta LibreHardwareMonitor (`8085`)**:
  - `stato_sicurezza_lhm()` verifica all'avvio se la porta `8085` è esposta sulla LAN (`0.0.0.0` / `::`) senza protezione Firewall.
  - Il pulsante **`Lock LHM`** (o `blocca_lhm_da_lan()`) crea una regola permanente in Windows Defender Firewall (`PC_Agent_AI_Block_LHM_8085`) tramite elevazione UAC singola, bloccando l'accesso dalla LAN e mantenendo operativo `localhost:8085`.
- **Minimo privilegio**: l'app gira come utente standard e richiede UAC solo su richiesta esplicita per la regola Firewall.
