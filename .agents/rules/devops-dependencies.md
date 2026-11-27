# Regole Solution Architect & Senior DevOps — Gestione Dipendenze

Quando l'Agent lavora su questo repository (sviluppo di nuove feature, bugfix o preparazione release), opera con mentalità da **Solution Architect e Senior DevOps** per mantenere `requirements.txt` e `requirements-dev.txt` aggiornati, sicuri e privi di CVE.

## 1. Verifica periodica durante lo sviluppo
- Prima di una release o quando si modifica l'ambiente/dipendenze, eseguire sempre:
  1. `.\.venv\Scripts\python.exe -m pip list --outdated` per individuare nuove versioni disponibili.
  2. `.\.venv\Scripts\python.exe -m pip_audit` per individuare eventuali CVE / GHSA.

## 2. Politica di Upgrade (SemVer)
- **Patch (`x.y.Z`) e Minor (`x.Y.0`)**:
  - Se l'aggiornamento risolve CVE o porta miglioramenti retrocompatibili, aggiornare il pacchetto nel `.venv` e aggiornare il vincolo minimo in `requirements.txt` / `requirements-dev.txt` quando opportuno.
- **Major (`X.0.0`)**:
  - Valutare prima l'impatto architetturale e le eventuali breaking change (es. cambio API `google-genai` o `psutil`), segnalare i rischi all'utente e procedere all'upgrade adattando codice e test.
- **Dipendenze minimali**: mantenere in `requirements.txt` solo pacchetti strettamente necessari al runtime; tutti gli strumenti di test, SAST e SCA (`pytest`, `pytest-cov`, `pip-audit`, `bandit`) vanno solo in `requirements-dev.txt`.

## 3. Verifica post-upgrade obbligatoria (Quality Gate)
Dopo ogni upgrade di dipendenze eseguire sempre e verificare `0` errori:
1. `.\.venv\Scripts\python.exe -m pip check` (`0` conflitti tra dipendenze transitive)
2. `python -m py_compile config/settings.py modules/tools.py modules/ai_agent.py modules/agent_win11.py`
3. `python -m pytest -c config/pytest.ini --rootdir=.` (tutti i test PASS e coverage `>= 80%`)
4. `.\.venv\Scripts\python.exe -m bandit -r config modules -ll` (`0` issue High/Medium)
5. `.\.venv\Scripts\python.exe -m pip_audit` (`0` CVE)

Se uno qualsiasi di questi controlli fallisce, eseguire il rollback della dipendenza alla versione stabile precedente e segnalare la causa.
