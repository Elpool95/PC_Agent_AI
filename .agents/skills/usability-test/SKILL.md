---
name: usability-test
description: >-
  Esegue test di usabilità, layout, leggibilità e flussi utente sulla GUI Tkinter
  di PC Agent AI (PCAgentGUI). Usare quando si modifica l'interfaccia grafica,
  si aggiungono pulsanti/righe telemetria o l'utente chiede un audit UX/usabilità.
---



> **PC Agent AI — Workspace Skill** | **Categoria:** UX & Usability | **Versione:** 1.0.0 | **Autore:** Elpool95

---

# Usability Testing Skill (GUI Tkinter)

Checklist e verifica automatizzata/visuale per garantire che l'interfaccia di `PC_Agent_AI` sia chiara, reattiva e usabile su qualsiasi risoluzione Windows.

## 1. Verifica automatizzata GUI (headless/offscreen)
Eseguire i test GUI dedicati:
```bash
python -m pytest -c config/pytest.ini --rootdir=. tests/test_gui.py -v --no-cov
```
Controllano automaticamente:
- **Layout & Visibilità**: `footer_frame` e `input_frame` ancorati in basso (`side=bottom`), mai tagliati dalla finestra minima (`820x620`) né da quella predefinita (`900x760`).
- **Etichette pulsanti**: presenza e coerenza dei pulsanti (`Top Process`, `Storage`, `Gaming Mode`, `Balance`, `Start App`, `RAM Detail`, `Lock LHM`, `Clear`, `Send`).
- **Colori per singolo disco**: un disco critico (`>= 90%`) è rosso (`#ff5252`), uno in warning (`>= 80%`) arancione (`#ffb74d`), gli altri restano viola (`#ce93d8`).
- **Azioni utente & Sicurezza HITL**: `Clear` svuota la console, `Gaming Mode` / `Balance` aggiornano lo stato `●`, `Lock LHM` aggiorna lo stato `Lock LHM !` / `LHM Locked ●`, il popup di conferma nativo blocca azioni sensibili se rifiutate e l'invio di un messaggio vuoto non invia chiamate API.

## 2. Checklist UX manuale (dopo avvio con `avvia_agent.bat`)
1. **Avvio istantaneo**: la finestra si apre in < 1 secondo anche offline o con LibreHardwareMonitor spento.
2. **Nessun troncamento orizzontale**: tutte le righe (CPU+ventole, RAM+banchi, dischi, GPU, Rete+ping, footer OS/driver) sono leggibili senza tagli a `900x760`.
3. **Feedback chiaro**: durante l'invio a Gemini il pulsante `Send` si disabilita e appare `Elaborazione in corso...`; in caso di fallback modello appare l'avviso in console.
4. **Contrasto e leggibilità**: colori ad alto contrasto su sfondo scuro (`#141414` / `#1e1e1e` / `#252526`).
5. **Chiusura pulita**: nessun processo fantasma o finestra terminale residua alla chiusura.

---

*PC Agent AI Skill v1.0.0 — Autore: Elpool95 | Licenza: MIT | Validata con `skill-evaluator` | Documentazione: `doc/testing-and-skills.md`*
