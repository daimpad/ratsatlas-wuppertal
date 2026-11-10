"""Phase 5 (Teil B): README, data/LICENSE-DATA.md, CONTRIBUTING und Issue-Vorlagen.

- Namensnennung wörtlich aus CLAUDE.md 3.2 (config.NAMENSNENNUNG, NAMENSNENNUNG_BPLAN) in README und LICENSE-DATA.
- data/LICENSE-DATA.md ist ein Entwurf (Lizenz der Ratsdaten ungeklärt, CLAUDE.md 8) und wird versioniert, obwohl
  data/raw, data/build und data/export ignoriert sind; die Seite verlinkt sie (site/index.html, pipeline/publish.py).
- Die Issue-Vorlage verortung.yml wird von site/app.js (reportLink) über ihre Feld-IDs vorausgefüllt.
- Nur belegte Kontaktadressen (CLAUDE.md 3.1 und 9).
Ohne Netz."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import config

ROOT = Path(__file__).resolve().parents[1]
LIZENZ_DATEN = ROOT / "data" / "LICENSE-DATA.md"
DOKUMENTE = ["README.md", "CONTRIBUTING.md", "NOTICE", "data/LICENSE-DATA.md"]


def _text(name):
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("datei", ["README.md", "data/LICENSE-DATA.md"])
def test_namensnennung_woertlich(datei):
    text = _text(datei)
    assert config.NAMENSNENNUNG == "Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0"
    assert config.NAMENSNENNUNG in text and config.NAMENSNENNUNG_BPLAN in text


def test_lizenz_daten_ist_entwurf_ohne_lizenzbehauptung_fuer_ratsdaten():
    text = LIZENZ_DATEN.read_text(encoding="utf-8")
    assert "Entwurf – Lizenz der Ratsdaten ungeklärt, siehe CLAUDE.md 8" in text.split("\n## ")[0]
    assert "ungeklärt" in text.split("## Ratsdaten")[1].split("\n## ")[0]
    assert "bis zur Lizenzklärung (CLAUDE.md 8) nicht festgelegt" in text
    assert "CC BY-ND 4.0" in text and "Andere geschlossene Lizenz" in text


def test_lizenz_daten_wird_versioniert():
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("kein Git-Checkout")
    r = subprocess.run(["git", "check-ignore", "-q", "data/LICENSE-DATA.md"], cwd=ROOT, capture_output=True)
    assert r.returncode == 1, "data/LICENSE-DATA.md darf nicht von .gitignore erfasst sein"


def test_verortung_vorlage_passt_zu_reportlink():
    app = _text("site/app.js")
    m = re.search(r'template: "verortung\.yml",(.*?)\}\);', app, re.S)
    assert m, "reportLink in site/app.js nicht gefunden"
    parameter = set(re.findall(r',\s*(\w+):', m.group(1))) - {"title"}
    ids = set(re.findall(r"^\s+id: (\w+)$", _text(".github/ISSUE_TEMPLATE/verortung.yml"), re.M))
    assert parameter == {"drucksache", "titel", "gebiet"} and parameter <= ids


@pytest.mark.parametrize("datei", DOKUMENTE + [".github/ISSUE_TEMPLATE/config.yml"])
def test_nur_belegte_kontaktadressen(datei):
    adressen = set(re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", _text(datei)))
    assert adressen <= {"contact@nozilla.de", "offenedaten@stadt.wuppertal.de"}, adressen
