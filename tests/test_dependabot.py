"""Phase 5: .github/dependabot.yml für die fest auf Commits gesetzten GitHub-Actions (Freigabe 10.11.2026).

Gültiges YAML (mit PyYAML, falls installiert; tests.yml installiert es nicht, daher immer auch eine einfache
Strukturprüfung), Ökosystem github-actions, monatlich, eine Gruppe für alle Actions, Wartezeit 14 Tage, kein npm.
Ohne Netz."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATEI = ROOT / ".github" / "dependabot.yml"


def _zeilen():
    """Zeilen ohne Kommentare und Leerzeilen, mit Einrückung."""
    return [z.rstrip() for z in DATEI.read_text(encoding="utf-8").splitlines()
            if z.strip() and not z.lstrip().startswith("#")]


def test_struktur_ohne_pyyaml():
    zeilen = _zeilen()
    assert zeilen[0] == "version: 2" and zeilen[1] == "updates:"
    eintraege = [z for z in zeilen if z.startswith("  - ")]
    assert eintraege == ['  - package-ecosystem: "github-actions"'], "genau ein Eintrag, nur github-actions"
    text = "\n".join(zeilen)
    assert '\n    directory: "/"\n' in text
    assert re.search(r'\n    schedule:\n      interval: "monthly"\n', text)
    assert re.search(r"\n    groups:\n      actions:\n        patterns:\n          - \"\*\"\n", text)
    assert re.search(r"\n    cooldown:\n      default-days: 14\n", text)
    limit = int(re.search(r"\n    open-pull-requests-limit: (\d+)\n", text).group(1))
    assert 1 <= limit <= 3
    assert "\t" not in DATEI.read_text(encoding="utf-8"), "YAML erlaubt keine Tabulatoren zur Einrückung"


def test_gueltiges_yaml():
    yaml = pytest.importorskip("yaml")
    daten = yaml.safe_load(DATEI.read_text(encoding="utf-8"))
    assert daten["version"] == 2
    [eintrag] = daten["updates"]
    assert eintrag["package-ecosystem"] == "github-actions" and eintrag["directory"] == "/"
    assert eintrag["schedule"] == {"interval": "monthly"}
    assert eintrag["groups"] == {"actions": {"patterns": ["*"]}}
    assert eintrag["cooldown"] == {"default-days": 14}
    assert len(eintrag["commit-message"]["prefix"]) <= 50


def test_kein_npm_und_begruendung_im_kommentar():
    text = DATEI.read_text(encoding="utf-8")
    assert '"npm"' not in text
    assert "tests/browser/package-lock.json" in text and "workflows-inaktiv" in text
    assert "docs.github.com" in text


def test_workflows_setzen_actions_fest_auf_commits():
    """Sonst gäbe es für Dependabot nichts fest Gesetztes zu aktualisieren (und Tags wären veränderlich)."""
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for ref in re.findall(r"uses:\s*(\S+)", wf.read_text(encoding="utf-8")):
            assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", ref), f"{wf.name}: {ref}"


def test_contributing_nennt_dependabot():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Dependabot" in text and "sobald sie grün sind" in text
