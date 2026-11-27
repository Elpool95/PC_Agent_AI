---
name: skill-evaluator
description: >-
  Valuta qualità, struttura, triggerability, sicurezza e token budget delle skill
  in .agents/skills/ tramite rubric e script automatico. Usare quando si crea o
  modifica una skill, o quando l'utente chiede un audit delle skill del progetto.
---



> **PC Agent AI — Workspace Skill** | **Categoria:** Governance & Quality | **Versione:** 1.0.0 | **Autore:** Elpool95

---

# Skill Evaluator

Procedura per valutare oggettivamente ogni skill presente in `.agents/skills/` secondo le best practice di Antigravity.

## Procedura di valutazione

1. **Eseguire lo script di valutazione automatica** (opzionalmente con `--sync` per allineare header/footer e versione SemVer da `config/skill_header_footer.json`):
   ```bash
   python .agents/skills/skill-evaluator/scripts/evaluate_skills.py
   python .agents/skills/skill-evaluator/scripts/evaluate_skills.py --sync
   ```
2. **Criteri valutati (punteggio 0–100)**:
   - **Frontmatter (25 pt)**: blocco YAML valido con `name` (lowercase/trattini, uguale al nome cartella) e `description` chiara (`>= 40` caratteri) con condizione di attivazione esplicita.
   - **Struttura, Header & Footer (25 pt)**: header e footer conformi a `config/skill_header_footer.json` con versionamento semantico (`X.Y.Z`), titolo H1, passi numerati o sezioni operative e criteri di verifica espliciti.
   - **Coerenza col repository (20 pt)**: percorsi e comandi citati (`config/pytest.ini`, `tests/`, `doc/`, ecc.) realmente esistenti nel progetto.
   - **Token Budget & Progressive Disclosure (15 pt)**: `SKILL.md` conciso (`<= 150` righe / `<= 6 KB`) senza duplicazioni inutili.
   - **Sicurezza & Portabilità (15 pt)**: nessun percorso assoluto personale dell'utente, nessuna API key o segreto hardcoded.
3. **Soglia di qualità**:
   - Ogni skill deve ottenere almeno **`75/100`** (e 0 errori bloccanti) per essere considerata pronta.
   - Per ogni warning segnalato dallo script, proporre una correzione mirata alla skill interessata.

---

*PC Agent AI Skill v1.0.0 — Autore: Elpool95 | Licenza: MIT | Validata con `skill-evaluator` | Documentazione: `doc/testing-and-skills.md`*
