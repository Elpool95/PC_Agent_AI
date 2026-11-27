---
name: skill-evaluator
description: >-
  Valuta qualità, struttura, triggerability, sicurezza e token budget delle skill
  in .agents/skills/ tramite rubric e script automatico. Usare quando si crea o
  modifica una skill, o quando l'utente chiede un audit delle skill del progetto.
---

# Skill Evaluator

Procedura per valutare oggettivamente ogni skill presente in `.agents/skills/` secondo le best practice di Antigravity.

## Procedura di valutazione

1. **Eseguire lo script di valutazione automatica**:
   ```bash
   python .agents/skills/skill-evaluator/scripts/evaluate_skills.py
   ```
2. **Criteri valutati (punteggio 0–100)**:
   - **Frontmatter (25 pt)**: blocco YAML valido con `name` (lowercase/trattini, uguale al nome cartella) e `description` chiara (`>= 40` caratteri) che specifica cosa fa e quando attivarla.
   - **Struttura & Chiarezza (25 pt)**: titolo H1, passi numerati o sezioni operative, criteri di verifica espliciti.
   - **Coerenza col repository (20 pt)**: percorsi e comandi citati (`config/pytest.ini`, `tests/`, ecc.) realmente esistenti nel progetto.
   - **Token Budget & Progressive Disclosure (15 pt)**: `SKILL.md` conciso (`<= 150` righe / `<= 6 KB`) senza duplicazioni inutili.
   - **Sicurezza & Portabilità (15 pt)**: nessun percorso assoluto personale dell'utente, nessuna API key o segreto hardcoded.
3. **Soglia di qualità**:
   - Ogni skill deve ottenere almeno **`75/100`** (e 0 errori bloccanti) per essere considerata pronta.
   - Per ogni warning segnalato dallo script, proporre una correzione mirata alla skill interessata.
