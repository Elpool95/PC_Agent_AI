# Changelog — PC Agent AI

Riepilogo cronologico delle funzionalità, ottimizzazioni e hardening sviluppati.

## 1. Avvio & Portabilità
- Corretto `avvia_agent.bat` con percorsi relativi (`%~dp0`) e rilevamento automatico di `.venv\Scripts\pythonw.exe`, `pythonw` e `pyw`.
- Creato `install.bat` per installazione automatica (`.venv`, `requirements.txt`, `config/.env`, collegamento automatico sul Desktop con icona Windows).
- Rimossi tutti i riferimenti personali e hardware hardcoded: rilevamento dinamico di CPU, core, RAM, GPU, dischi e versione Windows.
- Aggiunto loader nativo per `.env` / `config/.env` in `config/settings.py`.

## 2. Telemetria Hardware & UI
- Aggiunto consumo CPU in Watt (`CPU Package`) e velocità ventole scheda madre (`RPM`) da LibreHardwareMonitor.
- Rilevamento dinamico di tutti i dischi montati, disposti su griglia 2 colonne con colore indipendente per singolo disco (`#ff5252` critico `>= 90%`, `#ffb74d` warning `>= 80%`, `#ce93d8` normale).
- Aggiunti dettagli completi dei banchi RAM fisici (slot, capacità, DDR, frequenza `MHz`, voltaggio, codice modello, modalità `Dual Channel`) e pulsante `RAM Detail`.
- Aggiunta riga live Rete (interfaccia attiva, link speed, IP locale, `↓ / ↑` e `Ping` verso `1.1.1.1`).
- Aggiunti `Fan %` e `Clock MHz` sulla riga GPU.
- Aggiunto footer inferiore con versione Windows 11 e versione driver grafico NVIDIA; ancorati `footer_frame` e `input_frame` in basso (`side=tk.BOTTOM`) con finestra iniziale `900x760`.
- Rilevamento automatico del piano energetico attivo all'avvio (`Gaming Mode ●` / `Balance ●`).
- Unificato `Top Process` (Top 5 CPU + Top 5 RAM), aggiunto `Clear` e uniformate le etichette pulsanti in inglese sintetico.

## 3. Agent AI (Google Gemini)
- Esposti a `GeminiAgent` tutti i nuovi tool di telemetria, analisi spazio `C:`, banchi RAM, rete/ping, versioni OS/driver, chiusura sicura processi e protezione porta LHM.
- Aggiunta inizializzazione resiliente in background (l'app funziona anche offline o senza API key).
- Implementato fallback automatico tra modelli Gemini (`gemini-3.8-flash` -> `3.7-flash` -> `3.5-flash-lite` -> `3.1-flash-lite`) su errori `503`/`504`/`429`/`404` preservando la cronologia.

## 4. Architettura, Sicurezza, Test & Skill
- Riorganizzato il repository in `config/`, `modules/`, `tests/`, `reports/`, `doc/` e `.agents/` (`rules/`, `skills/`).
- Eseguito audit SAST/DAST/Pentest/Hardening: eliminato ogni `shell=True`, aggiunti `timeout` espliciti, validazione stretta su `ping`/`disk`/`kill`, mascheramento `%USERPROFILE%`, conferma nativa HITL (`messagebox.askyesno`) sui 5 tool sensibili e pulsante **`Lock LHM`** per bloccare la porta `8085` dalla LAN via Windows Firewall.
- Creata suite `pytest` con report JUnit XML (`reports/junit.xml`) e soglia di copertura `>= 80%` (27 test, ~86% coverage).
- Create regole di progetto (`project.md`, `security.md`, `testing.md`) e skill validate al 100/100 (`test-suite`, `usability-test`, `skill-evaluator`).
