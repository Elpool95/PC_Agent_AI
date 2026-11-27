import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".agents" / "skills" / "skill-evaluator" / "scripts" / "evaluate_skills.py"


def _load_evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_skills", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_skill_template_semver_and_all_skills_pass():
    ev = _load_evaluator()
    tpl = ev.load_template_config()
    assert ev.SEMVER_RE.fullmatch(tpl["version"])
    assert tpl["author"]
    assert tpl["license"]
    assert "{categoria}" in tpl["header"]
    assert "{version}" in tpl["header"]
    assert "{author}" in tpl["header"]
    assert "{version}" in tpl["footer"]
    assert "{license}" in tpl["footer"]
    assert ev.main([]) == 0
