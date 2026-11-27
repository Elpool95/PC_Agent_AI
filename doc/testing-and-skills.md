# Testing, Quality Gate & Skill — PC Agent AI

## 1. Suite di Test & JUnit XML
La suite di test usa `pytest` + `pytest-cov` configurati in `config/pytest.ini`.

### Comandi principali
```bash
# Installazione dipendenze di sviluppo
pip install -r requirements-dev.txt

# Esecuzione suite completa (JUnit XML + coverage >= 80%)
python -m pytest -c config/pytest.ini --rootdir=.

# Solo test di usabilità GUI
python -m pytest -c config/pytest.ini --rootdir=. tests/test_gui.py -v --no-cov

# Valutazione automatica delle skill
python .agents/skills/skill-evaluator/scripts/evaluate_skills.py
```

### Struttura dei test (`tests/`)
- `tests/test_tools.py`: test unitari su sensori CPU/ventole/GPU/RAM/dischi/rete, piani energetici, avvio, pulizia temp, mascheramento percorsi, sicurezza LHM e test DAST/Pentest su input malevoli.
- `tests/test_ai_agent.py`: prompt dinamico hardware, fallback automatico su `503`/`404`, gestione offline e blocco/consenso HITL su tutti i 5 tool sensibili.
- `tests/test_gui.py`: test di usabilità e layout Tkinter offscreen (etichette pulsanti, ancoraggio inferiore, colori indipendenti per singolo disco, toggle modalità, `Lock LHM`, `Clear`, azioni locali e loop telemetria).

### Output
- Report standard JUnit XML generato automaticamente in `reports/junit.xml`.
- Soglia obbligatoria di copertura: **`>= 80%`** su `config` e `modules` (attualmente **~86%** con 27 test).

## 2. Regole di Workspace (`.agents/rules/`)
- `project.md`: mappa dei file, vincoli di portabilità, architettura e convenzioni Git.
- `security.md`: checklist obbligatoria SAST, DAST, Pentest e Hardening.
- `testing.md`: obbligo di creare test per ogni nuovo task/fix, rispettare il Quality Gate `>= 80%` e validare ogni skill creata o modificata.

## 3. Skill di Workspace (`.agents/skills/`)
Tutte le skill includono frontmatter YAML standard, header, criteri di verifica e footer, e vengono validate automaticamente da `skill-evaluator`:
- **`test-suite`**: esecuzione SAST, `pytest`, JUnit XML e verifica coverage `>= 80%`.
- **`usability-test`**: verifica automatizzata e checklist UX della GUI Tkinter.
- **`skill-evaluator`**: rubric (0–100) e script Python (`scripts/evaluate_skills.py`) per valutare frontmatter, triggerability, header/footer, coerenza dei percorsi, budget token e sicurezza di tutte le skill.
