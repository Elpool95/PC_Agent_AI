"""Valutatore e sincronizzatore automatico delle skill in .agents/skills/."""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
SKILLS_DIR = ROOT / ".agents" / "skills"
TEMPLATE_PATH = ROOT / "config" / "skill_header_footer.json"
MIN_SCORE = 75
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def load_template_config() -> dict:
    """Carica header, footer, autore, licenza e versione semantica (X.Y.Z) da config/skill_header_footer.json."""
    data = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    version = str(data.get("version", "")).strip()
    author = str(data.get("author", "")).strip()
    lic = str(data.get("license", "")).strip()
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"Versione non SemVer (atteso X.Y.Z) in {TEMPLATE_PATH}: '{version}'")
    if not author:
        raise ValueError(f"Campo 'author' mancante in {TEMPLATE_PATH}")
    if not lic:
        raise ValueError(f"Campo 'license' mancante in {TEMPLATE_PATH}")
    return {
        "version": version,
        "author": author,
        "license": lic,
        "header": str(data["header"]),
        "footer": str(data["footer"]),
    }


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


def build_header_regex(header_tpl: str, tpl: dict) -> re.Pattern:
    escaped = re.escape(header_tpl)
    escaped = escaped.replace(re.escape("{categoria}"), r"[^|\n]+")
    escaped = escaped.replace(re.escape("{version}"), re.escape(tpl["version"]))
    escaped = escaped.replace(re.escape("{author}"), re.escape(tpl["author"]))
    escaped = escaped.replace(re.escape("{license}"), re.escape(tpl["license"]))
    return re.compile(r"^" + escaped + r"$", re.MULTILINE)


def sync_skill_header_footer(skill_file: Path, tpl: dict) -> bool:
    """Aggiorna header e footer della skill in base a config/skill_header_footer.json."""
    content = skill_file.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n.*?\n---\s*\n)(.*)$", content, re.DOTALL)
    if not m:
        return False
    fm_block, body = m.group(1), m.group(2)

    cat_match = re.search(r"\*\*Categoria:\*\*\s*([^|\n]+)", body)
    categoria = cat_match.group(1).strip() if cat_match else "General"
    ctx = {"categoria": categoria, "version": tpl["version"], "author": tpl["author"], "license": tpl["license"]}
    new_header = tpl["header"].format(**ctx)
    new_footer = tpl["footer"].format(**ctx)

    # Rimuovi vecchio header se presente
    body = re.sub(r"^\s*>\s*\*\*PC Agent AI — Workspace Skill\*\*[^\n]*\n+\s*---\s*\n+", "", body)
    # Rimuovi vecchio footer se presente
    body = re.sub(r"\n+---\s*\n+\*PC Agent AI Skill[^\n]*\*\s*$", "", body.rstrip())

    updated = f"{fm_block}\n{new_header}\n\n---\n\n{body.lstrip()}\n\n---\n\n{new_footer}\n"
    if updated != content:
        skill_file.write_text(updated, encoding="utf-8")
        return True
    return False


def evaluate_skill(skill_file: Path, tpl: dict | None = None) -> dict:
    if tpl is None:
        tpl = load_template_config()
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

    # 2. Struttura, Header & Footer da config/skill_header_footer.json (25 pt)
    header_re = build_header_regex(tpl["header"], tpl)
    expected_footer = tpl["footer"].format(
        categoria="", version=tpl["version"], author=tpl["author"], license=tpl["license"]
    )

    if header_re.search(body):
        score += 4
    else:
        issues.append(f"Header non conforme a config/skill_header_footer.json (versione attesa {tpl['version']})")

    if expected_footer in body:
        score += 4
    else:
        issues.append(f"Footer non conforme a config/skill_header_footer.json (versione attesa {tpl['version']})")

    if re.search(r"^#\s+\S+", body, re.MULTILINE):
        score += 5
    else:
        issues.append("Manca titolo principale H1")

    if re.search(r"^\s*1\.\s+", body, re.MULTILINE) or re.search(r"^##\s+", body, re.MULTILINE):
        score += 6
    else:
        issues.append("Mancano sezioni H2 o passi numerati")

    if any(k in body.lower() for k in ("verific", "controll", "soglia", "exit", "report", "pass")):
        score += 6
    else:
        issues.append("Mancano criteri espliciti di verifica/validazione")

    # 3. Coerenza col repository (20 pt)
    path_refs = re.findall(r"`([A-Za-z0-9_./-]+\.(?:py|ini|md|txt|bat|json))`", body)
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


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    tpl = load_template_config()
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skill_files:
        print("Nessuna skill trovata in .agents/skills/")
        return 1

    if "--sync" in args:
        aggiornate = sum(1 for sf in skill_files if sync_skill_header_footer(sf, tpl))
        print(f"Sincronizzati header/footer (v{tpl['version']}) su {aggiornate} skill.")

    all_ok = True
    print(f"=== Skill Evaluator v{tpl['version']} ({len(skill_files)} skill trovate) ===")
    for sf in skill_files:
        res = evaluate_skill(sf, tpl)
        stato = "PASS" if res["passed"] else "FAIL"
        print(f"[{stato}] {res['skill']}: {res['score']}/100 ({res['path']})")
        for issue in res["issues"]:
            print(f"   - {issue}")
        if not res["passed"]:
            all_ok = False
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
