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
    assert "Entwurf – Lizenz der Ratsdaten ungeklärt" in text.split("\n## ")[0]
    assert "ungeklärt" in text.split("## Ratsdaten")[1].split("\n## ")[0]
    assert "bis zur Lizenzklärung der Ratsdaten nicht festgelegt" in text
    # wird unter data/LICENSE-DATA.md und im Export ausgeliefert: keine Verweise auf interne Arbeitsdateien
    for intern in ("CLAUDE.md", "Messstufe", "explore/"):
        assert intern not in text, intern
    assert "flaechen/ortsteile.json" in text and "vereinfacht" in text
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


# --- TECHNIK.md (Phase 5, Freigabe 10.11.2026): Wuppertal statt Bonn; jede genannte Datei existiert ---------------

TECHNIK = ROOT / "TECHNIK.md"
# Bonner Orts-, Bezirks- und Dateinamen sowie Bonner Quellen aus der alten Fassung
BONNER_NAMEN = ["Endenich", "Beuel", "Bad Godesberg", "Hardtberg", "Lessenich", "Meßdorf", "_bonn", "allris-bonn",
                "bonn.ratsatlas.de", "OParl-Lite", "Bonn entscheidet", "Ortsteil", "Pilot"]


def _technik_inline():
    """Inline-Code (`…`) außerhalb von Codeblöcken."""
    ohne_bloecke = re.sub(r"```.*?```", "", TECHNIK.read_text(encoding="utf-8"), flags=re.S)
    return re.findall(r"`([^`\n]+)`", ohne_bloecke)


def _ignorierte_ordner():
    return [z.strip() for z in _text(".gitignore").splitlines()
            if z.strip().endswith("/") and not z.startswith("#")]


def test_technik_beschreibt_wuppertal_ohne_bonner_namen():
    text = TECHNIK.read_text(encoding="utf-8")
    assert text.startswith("# Ratsatlas Wuppertal – Technik\n")
    gefunden = [n for n in BONNER_NAMEN if n in text]
    assert not gefunden, gefunden
    # „Bonn“ nur als Herkunft: „Ratsatlas Bonn“, „aus Bonn“, „Bonner Format/Zusatzthemen/Kopie“
    for m in re.finditer(r"Bonn\w*", text):
        davor, wort, danach = text[max(0, m.start() - 10):m.start()], m.group(), text[m.end():m.end() + 14]
        assert (wort == "Bonn" and re.search(r"(Ratsatlas|aus) $", davor)) or \
            (wort == "Bonner" and re.match(r" (Format|Zusatzthemen|Kopie)", danach)), f"…{davor}{wort}{danach}…"


def test_technik_genannte_pfade_existieren():
    ignoriert = _ignorierte_ordner()
    pfade = [t for t in _technik_inline() if "/" in t and " " not in t and not t.startswith(("http", "daimpad/"))]
    assert len(pfade) > 40
    fehlend = [p for p in pfade if not (ROOT / p).exists() and not any(p.startswith(o) for o in ignoriert)]
    assert not fehlend, fehlend


def test_technik_umgebungsvariablen_gibt_es_im_code():
    code = "\n".join(p.read_text(encoding="utf-8") for ordner in ("pipeline", "explore", "tools")
                     for p in (ROOT / ordner).rglob("*.py"))
    namen = set(re.findall(r"\bRATSATLAS_[A-Z_]+", TECHNIK.read_text(encoding="utf-8")))
    assert {"RATSATLAS_STADT_INFORMIERT", "RATSATLAS_MESSUNG_FREIGEGEBEN", "RATSATLAS_PDF_FREIGEGEBEN"} <= namen
    fehlend = sorted(n for n in namen if f'"{n}"' not in code and f"'{n}'" not in code)
    assert not fehlend, fehlend


def test_technik_sperren_nennen_jedes_werkzeug_mit_abruf_bei_der_stadt():
    """Jede Datei in pipeline/, explore/ und tools/, die selbst Verbindungen öffnet und einen Host der Stadt nennt, steht
    in der Tabelle „Sperren und Freigaben“ (sonst liest sich die Tabelle wie eine vollständige Liste)."""
    text = TECHNIK.read_text(encoding="utf-8")
    tabelle = text[text.index("Sperren und Freigaben:"):]
    tabelle = tabelle[:tabelle.index("\n\n", tabelle.index("|"))]
    werkzeuge = []
    for ordner in ("pipeline", "explore", "tools"):
        for pfad in sorted((ROOT / ordner).rglob("*.py")):
            code = pfad.read_text(encoding="utf-8")
            if re.search(r"urlopen|http\.client", code) and re.search(r"[\"'][^\"'\s]*wuppertal\.de", code):
                werkzeuge.append(pfad.relative_to(ROOT).as_posix())
    assert "explore/strukturdaten/abruf_struktur.py" in werkzeuge and "pipeline/abruf.py" in werkzeuge
    fehlend = [w for w in werkzeuge if f"`{w}`" not in tabelle]
    assert not fehlend, fehlend
    assert "struktur-<host>.lock" in text and "`abruf.lock`" in text


def test_technik_nennt_alle_workflows_und_zusatzthemen():
    text = TECHNIK.read_text(encoding="utf-8")
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        assert f"`.github/workflows/{wf.name}`" in text, wf.name
    assert "`.github/dependabot.yml`" in text
    assert config.ZUSATZTHEMEN and not any(config.ZUSATZTHEMEN.values())
    fehlend = [k for k in config.ZUSATZTHEMEN if f"`{k}`" not in text]
    assert not fehlend, fehlend


def test_technik_schritte_der_pipeline_wie_im_code():
    """Aktive Schritte rufen Code auf, die als ersetzt genannten brechen in Wuppertal ab (pipeline/__main__.py)."""
    main = _text("pipeline/__main__.py")
    text = TECHNIK.read_text(encoding="utf-8")
    aktiv = re.search(r"Aktiv sind (.*?);", text).group(1)
    ersetzt = re.search(r"Abrufschritte \((.*?)\)", text).group(1)
    for schritt in re.findall(r"`([\w-]+)`", aktiv):
        assert re.search(rf'^    "{schritt}": (?!_ersetzt)', main, re.M), schritt
    for schritt in re.findall(r"`([\w-]+)`", ersetzt):
        assert re.search(rf'^    "{schritt}": _ersetzt\(', main, re.M), schritt
    assert 'for step in (["fetch", "build"] if argv[0] == "all"' in main


def test_readme_verweist_ohne_bonner_vorbehalt_auf_technik():
    readme = _text("README.md")
    assert "[TECHNIK.md](TECHNIK.md)" in readme and "noch Bonner Stand" not in readme
