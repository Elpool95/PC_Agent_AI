---
name: dependency-upgrade
description: >-
  Verifica nuove versioni e CVE per requirements.txt e requirements-dev.txt,
  valuta l'impatto SemVer (patch/minor/major) ed esegue upgrade sicuri con
  Quality Gate completo (pytest, coverage >=80%, Bandit SAST, pip-audit).
  Usare durante lo sviluppo, prima di una release o quando l'utente chiede di
  controllare o aggiornare le dipendenze.
---

> **PC Agent AI — Workspace Skill** | **Categoria:** DevOps & Dependencies | **Versione:** 1.0.0 | **Autore:** Elpool95

---

# Dependency Audit & Upgrade Skill (Solution Architect / Senior DevOps)

Procedura standard per verificare nuove versioni delle librerie in `requirements.txt` e `requirements-dev.txt` ed eseguire upgrade controllati senza introdurre regressioni o vulnerabilità.

## Prerequisiti
Ambiente virtuale `.venv` attivo con dipendenze di sviluppo installate:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

## Procedura di esecuzione
1. **Controllo versioni disponibili e CVE**:
   ```powershell
   .\.venv\Scripts\python.exe -m pip list --outdated --format=columns
   .\.venv\Scripts\python.exe -m pip_audit --progress-spinner off
   ```
2. **Valutazione architetturale (SemVer)**:
   - **Patch / Minor**: procedere con l'upgrade nel `.venv` e aggiornare i vincoli minimi in `requirements.txt` / `requirements-dev.txt` se necessario (es. per fissare una versione che risolve una CVE).
   - **Major**: verificare le breaking changes prima di aggiornare e informare l'utente se richiede modifiche al codice applicativo (`modules/tools.py`, `modules/ai_agent.py`, `modules/agent_win11.py`).
3. **Esecuzione upgrade controllato**:
   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade <pacchetto>
   ```
4. **Quality Gate post-upgrade obbligatorio**:
   ```powershell
   .\.venv\Scripts\python.exe -m pip check
   python -m py_compile config/settings.py modules/tools.py modules/ai_agent.py modules/agent_win11.py
   python -m pytest -c config/pytest.ini --rootdir=.
   .\.venv\Scripts\python.exe -m bandit -r config modules -ll
   .\.venv\Scripts\python.exe -m pip_audit --progress-spinner off
   ```
5. **Validazione e documentazione**:
   - Verificare `0` test falliti, coverage totale `>= 80%`, `0` issue Bandit High/Medium e `0` CVE.
   - Se un controllo fallisce, fare rollback immediato del pacchetto alla versione precedente.
   - Aggiornare `reports/quality-security-report.md` (sezione SCA/CVE) e, in caso di release, incrementare `APP_VERSION` in `config/settings.py`.

---

*PC Agent AI Skill v1.0.0 — Autore: Elpool95 | Licenza: MIT | Validata con `skill-evaluator` | Documentazione: `doc/testing-and-skills.md`*
