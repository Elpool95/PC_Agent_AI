---
name: test-suite
description: >-
  Esegue la suite di test unitari, sicurezza (SAST/DAST) e code coverage (>=80%)
  generando il report JUnit XML in reports/junit.xml. Usare quando si sviluppano
  nuove funzioni, prima di un commit/release o quando l'utente chiede di testare il codice.
---

# Test Suite & JUnit Coverage Skill

Procedura standard per verificare il funzionamento, la sicurezza e la copertura del codice di `PC_Agent_AI`.

## Prerequisiti
Assicurarsi che le dipendenze di sviluppo siano installate:
```bash
pip install -r requirements-dev.txt
```

## Procedura di esecuzione
1. **Controllo statico (SAST rapido)**:
   ```bash
   python -m py_compile config/settings.py modules/tools.py modules/ai_agent.py modules/agent_win11.py
   ```
   Verificare che non siano presenti `shell=True`, `eval(`, `exec(`, `pickle` o segreti hardcoded.

2. **Esecuzione test con report JUnit XML e coverage (>= 80%)**:
   ```bash
   python -m pytest -c config/pytest.ini --rootdir=.
   ```
   Grazie a `config/pytest.ini`, il comando esegue automaticamente:
   - Tutti i test in `tests/` (unitari, mock hardware/WMI/LHM/Gemini, sicurezza/DAST e GUI headless)
   - Generazione del report standard JUnit in `reports/junit.xml`
   - Verifica della soglia minima di copertura **`>= 80%`** su `config` e `modules`

3. **Analisi del risultato**:
   - Se la coverage scende sotto l'80%, individuare le righe scoperte nella colonna `Missing` e aggiungere i test mancanti in `tests/`.
   - Verificare che `reports/junit.xml` riporti `failures="0"` e `errors="0"`.
