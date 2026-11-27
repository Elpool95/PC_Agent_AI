# Security & Verification Rules (SAST, DAST, Pentest, Hardening)

Ogni volta che viene scritto o modificato codice in questo repository, applicare sistematicamente le verifiche seguenti prima di considerare il task completato.

## 1. SAST (Static Application Security Testing)
- **Command Injection**: evitare `subprocess` con `shell=True` quando esistono input variabili; preferire sempre liste di argomenti `[exe, arg1, arg2]` e `creationflags=NO_WINDOW`. Validare rigorosamente ogni parametro passato a comandi di sistema (`ping`, `powercfg`, `nvidia-smi`, PowerShell).
- **Segreti & Credenziali**: mai inserire API key, token, password o percorsi personali nel codice; usare solo variabili d'ambiente / `config/.env` (escluso in `.gitignore`).
- **Funzioni pericolose**: vietato usare `eval()`, `exec()`, `pickle` su dati non fidati o deserializzazioni insicure.
- **Rete & Timeout**: ogni chiamata HTTP/rete (`urllib`, client Gemini) deve avere un `timeout` esplicito e puntare solo a endpoint attesi (es. `http://localhost:8085/data.json` per LHM).
- **Controllo statico**: eseguire sempre `python -m py_compile` sui file modificati (e `bandit -r modules config` se `bandit` è installato nell'ambiente).

## 2. DAST (Dynamic Application Security Testing)
- **Test con input anomali**: testare i tool esposti all'AI con input malformati o limite (es. stringhe vuote, PID inesistenti, metacaratteri shell `foo & calc`, path traversal `..\..`, processi protetti/di sistema) verificando che restituiscano errori controllati senza crash.
- **Test di resilienza**: verificare che GUI e telemetria restino operative anche in assenza di rete, API key, LibreHardwareMonitor o `nvidia-smi`.

## 3. Pentest (Abuse Case & Prompt Injection)
- **Difesa in profondità lato codice**: i controlli di sicurezza (`PROTECTED_PROCESSES`, `_PROCESSI_SISTEMA_PROTETTI`, restrizione delle cartelle eliminabili in `pulisci_file_temporanei`) devono essere imposti nel codice Python, mai delegati solo al prompt di sistema dell'LLM.
- **Azioni distruttive**: ogni operazione che modifica stato di sistema (terminare processi, rimuovere app all'avvio, modificare piani energetici o file) deve avere allowlist/denylist esplicite e conferma utente quando invocata via chat AI.
- **Nessuna esecuzione arbitraria**: non esporre mai a Gemini tool generici di esecuzione shell/PowerShell o accesso libero al filesystem.

## 4. Hardening (Irrobustimento)
- **Minimo privilegio**: l'app deve funzionare da utente standard gestendo `PermissionError` / `AccessDenied` senza crashare.
- **Logging sicuro**: non scrivere mai chiavi API, token o dati sensibili in console o in `reports/*.log`.
- **Supply chain & isolamento**: mantenere dipendenze essenziali in `requirements.txt`, usare l'ambiente virtuale isolato `.venv` e verificare le CVE delle dipendenze con `pip-audit` (e `.github/dependabot.yml` su GitHub).
- **Superficie di attacco ridotta**: esporre a `GeminiAgent` solo i tool strettamente necessari, con type hints chiari e output minimi.
