# Testing & Quality Gate Rules

Ogni volta che si sviluppa una nuova funzionalità, un task o un bugfix in questo repository, è obbligatorio rispettare questo workflow prima di considerare il lavoro concluso.

## 1. Creazione test obbligatoria
- **Nuova funzionalità / Task**: aggiungere test unitari dedicati in `tests/` (`test_tools.py`, `test_ai_agent.py` o `test_gui.py`) che coprano sia il caso nominale che i casi limite/errore.
- **Bugfix**: aggiungere sempre un test di regressione che riproduce lo scenario del bug e dimostra che la correzione funziona.
- **Modifiche GUI**: aggiornare o aggiungere test di usabilità/layout in `tests/test_gui.py` (etichette, ancoraggi, colori, flussi utente) seguendo `.agents/skills/usability-test/SKILL.md`.
- **Modifiche a tool AI o comandi OS**: aggiungere almeno un caso di test negativo/DAST (input malformati, path traversal, metacaratteri o processi protetti).

## 2. Quality Gate obbligatorio prima di chiudere
1. Eseguire la suite completa:
   ```bash
   python -m pytest -c config/pytest.ini --rootdir=.
   ```
2. Verificare che:
   - Tutti i test passino (`0 failed`, `0 errors`).
   - Il report JUnit XML sia rigenerato correttamente in `reports/junit.xml`.
   - La copertura totale resti **`>= 80%`** su `config` e `modules`.
3. Non dichiarare mai completato un task o un fix con test falliti o copertura sotto l'80%.

## 3. Quality Gate per le Skill (`.agents/skills/`)
- Ogni volta che si crea o modifica una skill in `.agents/skills/`, è obbligatorio:
  1. Eseguire lo script di valutazione automatica:
     ```bash
     python .agents/skills/skill-evaluator/scripts/evaluate_skills.py
     ```
  2. Verificare che la skill superi la soglia (0 errori/warning bloccanti) e rivederla per migliorarne chiarezza, triggerability della `description`, aderenza ai file reali del progetto e criteri di verifica.
