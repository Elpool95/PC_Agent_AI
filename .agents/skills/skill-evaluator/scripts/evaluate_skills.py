"""Valutatore automatico delle skill in .agents/skills/."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = ROOT / ".agents" / "skills"
MIN_SCORE = 75


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    raw_fm, body = m.group(1), m.group(2)
    fm = {}
    current_key = None
    for line in raw_fm.splitlines():
        if re.match(r"^[a-zA-Z0-9_-]+\s*:", line):
            k, v = line.split(":", 1)
            current_key = k.strip()
            v = v.strip()
            fm[current_key] = "" if v in (">", ">-", "|", "|-") else v.strip("\"'")
        elif current_key and line.startswith((" ", "\t")):
            fm[current_key] = (fm[current_key] + " " + line.strip()).strip()
    return fm, body


def evaluate_skill(skill_file: Path) -> dict:
    folder_name = skill_file.parent.name
    content = skill_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    fm, body = parse_frontmatter(content)

    score = 0
    issues = []

    # 1. Frontmatter (25 pt)
    name = fm.get("name", "")
    desc = fm.get("description", "")
    if name and re.fullmatch(r"[a-z0-9-]+", name):
        score += 10
        if name == folder_name:
            score += 5
        else:
            issues.append(f"name '{name}' diverso dalla cartella '{folder_name}'")
    else:
        issues.append("Frontmatter 'name' mancante o non valido (usare lowercase e trattini)")

    if len(desc) >= 40:
        score += 6
        if any(k in desc.lower() for k in ("usare quando", "use when", "quando l'utente", "when the user", "attivare quando")):
            score += 4
        else:
            issues.append("Frontmatter 'description' dovrebbe indicare esplicitamente quando attivare la skill (es. 'Usare quando...')")
    else:
        issues.append("Frontmatter 'description' troppo breve (< 40 caratteri) o mancante")

    # 2. Struttura & Chiarezza (25 pt)
    if re.search(r"^#\s+\S+", body, re.MULTILINE):
        score += 8
    else:
        issues.append("Manca titolo principale H1")

    if re.search(r"^\s*1\.\s+", body, re.MULTILINE) or re.search(r"^##\s+", body, re.MULTILINE):
        score += 9
    else:
        issues.append("Mancano sezioni H2 o passi numerati")

    if any(k in body.lower() for k in ("verific", "controll", "soglia", "exit", "report", "pass")):
        score += 8
    else:
        issues.append("Mancano criteri espliciti di verifica/validazione")

    # 3. Coerenza col repository (20 pt)
    path_refs = re.findall(r"`([A-Za-z0-9_./-]+\.(?:py|ini|md|txt|bat))`", body)
    missing_refs = []
    for ref in set(path_refs):
        if ref.startswith(("http", "reports/")):
            continue
        candidate = ROOT / ref
        rel_candidate = skill_file.parent / ref
        if not candidate.exists() and not rel_candidate.exists():
            missing_refs.append(ref)
    if not missing_refs:
        score += 20
    else:
        score += max(0, 20 - 5 * len(missing_refs))
        issues.append(f"Percorsi citati non trovati: {', '.join(sorted(missing_refs))}")

    # 4. Token Budget & Progressive Disclosure (15 pt)
    if len(lines) <= 150 and len(content.encode("utf-8")) <= 6000:
        score += 15
    else:
        score += 7
        issues.append(f"SKILL.md troppo lungo ({len(lines)} righe, {len(content)} byte): spostare dettagli in references/")

    # 5. Sicurezza & Portabilità (15 pt)
    sec_patterns = [
        (r"C:\\Users\\", "Percorso personale C:\\Users\\ rilevato"),
        (r"AIza[0-9A-Za-z\-_]{20,}", "Possibile API key Google hardcoded"),
    ]
    sec_hits = [msg for pat, msg in sec_patterns if re.search(pat, content, re.IGNORECASE)]
    if not sec_hits:
        score += 15
    else:
        issues.extend(sec_hits)

    return {
        "skill": folder_name,
        "path": str(skill_file.relative_to(ROOT)),
        "score": score,
        "passed": score >= MIN_SCORE and not sec_hits,
        "issues": issues,
    }


def main() -> int:
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skill_files:
        print("Nessuna skill trovata in .agents/skills/")
        return 1

    all_ok = True
    print(f"=== Skill Evaluator ({len(skill_files)} skill trovate) ===")
    for sf in skill_files:
        res = evaluate_skill(sf)
        stato = "PASS" if res["passed"] else "FAIL"
        print(f"[{stato}] {res['skill']}: {res['score']}/100 ({res['path']})")
        for issue in res["issues"]:
            print(f"   - {issue}")
        if not res["passed"]:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
