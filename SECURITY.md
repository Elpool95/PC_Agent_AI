# Security Policy — Elpool Agent PC (PC Agent AI)

## Versioni supportate

Le correzioni di sicurezza vengono rilasciate sulla versione stabile corrente:

| Versione | Supportata |
| :--- | :---: |
| `1.0.x` | Sì |
| `< 1.0.0` | No |

---

## Come segnalare una vulnerabilità

Se individui una vulnerabilità di sicurezza in **Elpool Agent PC**, **non aprire una Issue pubblica**.

Segnalala in modo privato e responsabile tramite **GitHub Security Advisories**:
- Apri una segnalazione privata su: **[Report a vulnerability](https://github.com/Elpool95/PC_Agent_AI/security/advisories/new)**

### Cosa includere nella segnalazione
Per aiutarci a riprodurre e risolvere rapidamente il problema, indica:
1. **Descrizione della vulnerabilità** e componente coinvolto (es. `modules/tools.py`, `modules/ai_agent.py`, `modules/agent_win11.py`, `install.bat`).
2. **Passaggi esatti per riprodurla** (o Proof of Concept minimale).
3. **Impatto stimato** (es. command injection, bypass conferme UAC/HITL, esposizione rete/privacy, terminazione processi protetti).
4. **Ambiente**: versione di Windows, versione Python e versione di `APP_VERSION`.

### Tempi di gestione
- **Presa in carico**: entro **3 giorni lavorativi** dalla segnalazione.
- **Valutazione e fix**: rilascio prioritario di una patch (`1.0.x`) una volta confermato il problema, con divulgazione coordinata dopo la pubblicazione della correzione.

---

## Modello di sicurezza e misure già adottate

**Elpool Agent PC** applica il principio del minimo privilegio e difese stratificate:
- **Zero `shell=True`** e validazione stretta di tutti gli input passati a comandi di sistema (`ping`, `powercfg`, `netsh`, `nvidia-smi`, PowerShell) con `timeout` obbligatori.
- **Human-in-the-Loop (HITL) lato codice**: ogni tool distruttivo o con elevazione UAC esposto a Google Gemini richiede conferma esplicita tramite popup nativo Tkinter.
- **Processi protetti lato codice**: processi di sistema Windows e anti-cheat/client di gioco (`PROTECTED_PROCESSES`) non possono mai essere terminati o modificati.
- **Privacy & Rete**: mascheramento automatico di `%USERPROFILE%` nei percorsi e protezione della porta `8085` di LibreHardwareMonitor dalla LAN tramite Windows Firewall (`Lock LHM`).

Per i dettagli tecnici completi su SAST, DAST e hardening consulta [doc/security.md](doc/security.md).
