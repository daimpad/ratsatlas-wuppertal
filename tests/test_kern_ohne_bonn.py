"""Phase 2, Teil 6 (Bonner feste Angaben ersetzen, Rest nach PR #6): Kerndateien ohne Bonner Orts-, Gremien- und
Fraktionsnamen und ohne den Gebietsschlüssel „bonn“.

Geprüft werden nur Kerndateien (CLAUDE.md 5.4); die abgeschalteten Zusatzthema-Module (chat, kontext, anliegen,
baustellen, soll, beteiligung.js …) behalten bis zu ihrer Freigabe den Bonner Stand und werden hier nicht geprüft.
Kommentare und Docstrings dürfen Herkunftsvermerke („aus Bonn“, „Allianz für Bonn entfernt“) enthalten; geprüft wird
der wirksame Code (Zeichenketten, Schlüssel) bzw. der sichtbare Text. Jede Prüfung hat eine Gegenprobe, damit sie nicht
ins Leere läuft. Ohne Netz."""
import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import actors, begriffsseite, config, gebietsseiten, gebietszahlen, glossar

ROOT = Path(__file__).resolve().parents[1]

# Bonner Orts-, Gremien- und Fraktionsnamen, Bonner Beispielnummern und Schlüssel mit „bonn“ (aus der Fundstellenkarte
# zu PR #6). Nicht „Bonn“ allein: Herkunftsangaben (CLAUDE.md 2) und „abonnieren“ bleiben erlaubt.
BONNER_NAMEN = (
    "Bad Godesberg", "Beuel", "Hardtberg", "Bezirksvertretung Bonn", "BV Bonn", "Stadt Bonn", "Bonn hat",
    "bonn-zentrum", "Bonn-Zentrum", "Endenich", "Endenicher Straße", "Venusberg", "Röttgen", "Beethoven", "beethoven",
    "Allianz für Bonn", "AfB", "Rhein.Grün", "BBB", "Bürger Bund Bonn", "SBI", "BIG",
    "Betriebsausschuss SGB", "Ausschuss für Mobilität und Verkehr", "Ausschuss für Wohnen, Planung und Bauen",
    "themen_bonn", "anteil_bonn", "audit_geokodierung_bonn", "export_pilot",
    "261856", "261798", "261088", "50.6327", "7.0225",
    "OParl-Lite", "machdenstaat",   # Volltextdienst nur in Bonn (CLAUDE.md 3.2)
)
# Gebietsschlüssel „bonn“ in Code und Markup: "bonn", 'bonn', `bonn`, bonn:alle, data-scope="bonn", value="bonn"
SCHLUESSEL = re.compile(r"""["'`]bonn["'`:]|\bbonn:(?:alle|ganz)\b|\?suche=bonn\b|gebiet=bonn:""")

JS = ["site/app.js", "site/tour.js", "site/timeline.js"]
HTML = ["site/index.html"]
PY = ["pipeline/glossar.py", "pipeline/actors.py", "pipeline/topics.py", "pipeline/gebietszahlen.py",
      "pipeline/export.py", "pipeline/process.py", "pipeline/build.py", "pipeline/plans.py", "pipeline/begriffsseite.py",
      "pipeline/gebietsseiten.py", "pipeline/vorgangsseiten.py", "pipeline/publish.py", "pipeline/rssseite.py",
      "pipeline/seo.py", "pipeline/check.py"]
# Zeilen in app.js, die nur bei Freigabe eines Zusatzthemas laufen (FN.baustellen) und bis dahin Bonner Stand bleiben
ZUSATZTHEMA_ZEILEN = ("<li>Baustellen: Stadt Bonn",)
# Herkunftsangaben in index.html (wie tests/test_bplan_und_angaben.py HERKUNFT)
HERKUNFT = ("Code des Ratsatlas Bonn (daimpad/allris-test)", "auf Grundlage des Ratsatlas Bonn und des Abrufs")


def _js_code(text):
    """JavaScript ohne Kommentarzeilen, Zeilenend-Kommentare („ // …“) und Zeilen gesperrter Zusatzthemen."""
    zeilen = []
    for z in text.splitlines():
        if z.lstrip().startswith(("//", "/*", "*")) or any(k in z for k in ZUSATZTHEMA_ZEILEN):
            continue
        zeilen.append(re.sub(r"\s//\s.*$", "", z))
    return "\n".join(zeilen)


def _html_text(text):
    for h in HERKUNFT:
        text = text.replace(h, "")
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _py_strings(text):
    """Alle wirksamen Zeichenketten und Namen eines Moduls, ohne Kommentare und Docstrings."""
    baum = ast.parse(text)
    docs = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            k = knoten.body[0] if knoten.body else None
            if isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
                docs.add(id(k.value))
    teile = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str) and id(knoten) not in docs:
            teile.append(knoten.value)
        elif isinstance(knoten, ast.Name):
            teile.append(knoten.id)
        elif isinstance(knoten, ast.Attribute):
            teile.append(knoten.attr)
        elif isinstance(knoten, (ast.FunctionDef, ast.ClassDef)):
            teile.append(knoten.name)
    return "\n".join(teile)


def _funde(text):
    namen = [n for n in BONNER_NAMEN if re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", text)]
    return namen + SCHLUESSEL.findall(text)


@pytest.mark.parametrize("datei", JS)
def test_js_kern_ohne_bonner_namen_und_schluessel(datei):
    gefunden = _funde(_js_code((ROOT / datei).read_text(encoding="utf-8")))
    assert not gefunden, gefunden


@pytest.mark.parametrize("datei", HTML)
def test_html_kern_ohne_bonner_namen_und_schluessel(datei):
    gefunden = _funde(_html_text((ROOT / datei).read_text(encoding="utf-8")))
    assert not gefunden, gefunden


@pytest.mark.parametrize("datei", PY)
def test_pipeline_kern_ohne_bonner_namen(datei):
    gefunden = _funde(_py_strings((ROOT / datei).read_text(encoding="utf-8")))
    assert not gefunden, gefunden


def test_gegenprobe_pruefung_findet_bonner_angaben():
    """Die Prüfung schlägt an, wo sie soll, und nicht bei Herkunftsvermerken oder „abonnieren“."""
    js = ('const DEFAULT_AREA = "bonn:alle";\nif (area.kind === "bonn") x();\n'
          'fetch(`${BONN}ortsteile/bonn-zentrum.json`);\nconst G = ["Bezirksvertretung Bonn"];\n'
          '// Kommentar: Bezirksvertretung Bonn, "bonn" aus Bonn\nconst a = 1; // aus „bonn:alle“\n'
          'const t = "Diesen Vorgang abonnieren";')
    gefunden = _funde(_js_code(js))
    assert {"bonn-zentrum", "Bezirksvertretung Bonn", "BV Bonn"} & set(gefunden) == {"bonn-zentrum",
                                                                                      "Bezirksvertretung Bonn"}
    assert '"bonn:' in gefunden and '"bonn"' in gefunden
    assert len([f for f in gefunden if f.startswith(('"', "'", "`"))]) == 2
    assert not _funde(_js_code('// "bonn" Bezirksvertretung Bonn\nconst t = "abonnieren";'))
    html = '<button data-scope="bonn">x</button><!-- Bad Godesberg --><p>Code des Ratsatlas Bonn (daimpad/allris-test)</p>'
    assert _funde(_html_text(html)) == ['"bonn"']
    py = ('"""Docstring: Allianz für Bonn entfernt."""\n# Kommentar: Stadt Bonn\n'
          'PARTIES = [("Allianz für Bonn", r"AfB", r"x")]\nDATENFELD = "Ratsinformationssystem der Stadt Bonn"\n'
          'def f():\n    """Bad Godesberg im Docstring."""\n    return {"themen_bonn": 1}\n')
    assert set(_funde(_py_strings(py))) == {"Allianz für Bonn", "AfB", "Stadt Bonn", "themen_bonn"}
    # die echte Bonner Fassung von app.js (Gebietsschlüssel) hätte angeschlagen
    assert _funde(_js_code('  const DEFAULT_AREA = "bonn:alle";')) == ['"bonn:']


def test_gebietsschluessel_wie_koeln():
    """Gebietsart „ganze Stadt“ über const STADT (wie ratsatlas-koeln @d609111); Wert wie config.STADT, im Markup
    dieselben Werte (setScope vergleicht dataset.scope, syncUrl schreibt ?suche=…)."""
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    m = re.search(r'const STADT = "([a-z]+)", STADT_NAME = "([^"]+)";', app)
    assert m and m.groups() == (config.STADT, config.STADT_NAME) == ("wuppertal", "Wuppertal")
    assert "const DEFAULT_AREA = `${STADT}:alle`;" in app
    assert 'data-scope="wuppertal"' in html and '<input type="radio" name="scope" value="wuppertal">' in html
    # alte Links mit „bonn:…“ fallen über parseArea auf die Startansicht (DEFAULT_AREA)
    assert "return parseArea(DEFAULT_AREA);" in app
    # keine Bonner Kartengrenzen und keine erfundene Wuppertaler Box: Ausschnitt aus index.json bzw. den Flächen
    assert "BONN_BOUNDS =" not in app and config.STADT_BBOX is None
    assert "function stadtBounds(idx)" in app and "L.geoJSON(geo.bezirk).getBounds()" in app
    # Volltextsuche über OParl-Lite entfällt (CLAUDE.md 3.2)
    assert "const LITE = null;" in app


def test_tour_ohne_festes_beispielgebiet():
    """Kein fest eingetragenes Quartier für die Tour (Namen erst nach Messstufe G): das Beispielgebiet kommt zur
    Laufzeit aus index.json (beispielGebiet, Verhalten in test_app_funktionen_in_node); das Detailfenster öffnet nur,
    wenn ein Beispiel geladen wurde."""
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    tour = (ROOT / "site" / "tour.js").read_text(encoding="utf-8")
    assert not re.search(r"""loadArea\(["'`]ortsteil:[^$]""", app)
    assert not re.search(r"""ortsteile/[\w-]+\.json""", _js_code(app))
    assert "await loadArea(`ortsteil:${o.slug}`, true);" in app
    assert 'if (await ui.example()) ui.panel("panel-detail", true);' in tour
    assert "VO/1380/26" in tour and "261856" not in tour
    # abgeschaltete Zusatzthemen beschreibt die Tour nur bei Freigabe
    for thema in ("kontext", "baustellen", "mitmachen", "einfache_sprache", "haushalt", "soll", "chat"):
        assert f'an("{thema}")' in tour, thema
    assert "funktion(name) { return Boolean(FN[name]); }," in app


def test_zeitleiste_ohne_bonner_gremien():
    """Bahnen für Sitzungen leer bis Messstufe 3/4; das Zeichnen teilt nicht durch null und überspringt Sitzungen."""
    tl = (ROOT / "site" / "timeline.js").read_text(encoding="utf-8")
    assert "const PILOT_GREMIEN = [];" in tl and "const GREMIUM_ALIAS = {};" in tl
    assert "/ Math.max(1, rows)" in tl
    assert "for (const m of compact || !rows ? [] : data.meetings || [])" in tl
    assert "const i = bahn(m.gremium);" in tl


def test_glossar_ohne_bonn():
    """glossar.json und die Seite begriffe/ (Kern, immer erzeugt) nennen Bonn nicht mehr; Haushalt und Bonner Kürzel
    sind entfernt; Zahl der Stadtbezirke und Quartiere aus CLAUDE.md 2, ohne Namen."""
    g = glossar.glossar()
    text = json.dumps(g, ensure_ascii=False)
    assert "Bonn" not in text and "261798" not in text
    assert "haushalt" not in g["gruppen"] and g["kuerzel"] == {}
    begriffe = {b["begriff"]: b for b in g["begriffe"]}
    assert "Drucksachennummer" not in begriffe and "VO/1380/26" in begriffe["Vorlagennummer"]["erklaerung"]
    assert begriffe["Vorlagennummer"]["fundstelle"].startswith("Ratsinformationssystem der Stadt Wuppertal")
    assert "zehn Bezirksvertretungen" in begriffe["Bezirksvertretung"]["erklaerung"]
    assert "69 Quartiere" in begriffe["Quartier"]["erklaerung"]
    for b in ("ST", "AA", "DA", "Produktbereich", "Informationsbrief", "Bürgerbrief", "Beschlussvorlage: Einleitung"):
        assert b not in begriffe, b
    # jede Art verweist auf einen vorhandenen Begriff
    anker = {b["anker"] for b in g["begriffe"]}
    assert set(g["arten"].values()) <= anker


def test_begriffsseite_ohne_bonn(tmp_path):
    pfade = begriffsseite.write(tmp_path, "https://wuppertal.ratsatlas.de/", gebietsseiten._page)
    assert pfade
    html = (tmp_path / "begriffe" / "index.html").read_text(encoding="utf-8")
    assert "Bonn" not in html and "Wuppertal" in html


def test_einreichende_ohne_bonner_fraktionen():
    """Nur die in CLAUDE.md 3.1/5.3 genannten Einreichenden; Bonner Gruppen ergeben keinen Treffer mehr."""
    assert [p[0] for p in actors.PARTIES] == ["CDU", "SPD", "Grüne", "FDP", "Die Linke", "AfD"]
    rows = actors.originators({"paperType": "Antrag", "date": "2024-01-01",
                               "name": "Antrag der Allianz für Bonn: Radweg"}, [])
    assert not any("Bonn" in r["actor"] for r in rows)
    rows = actors.originators({"paperType": "Antrag", "date": "2024-01-01", "name": "Antrag der CDU: Radweg"}, [])
    assert [r["actor"] for r in rows] == ["CDU"]


def test_gebietszahlen_neutrale_schluessel():
    papers = {i: {"date": "2026-01-01", "themes": [{"theme": "verkehr" if i < 8 else "bauen"}]} for i in range(30)}
    index = {"ortsteile": [{"slug": "a", "stadtbezirk": "X"}], "bezirke": [{"slug": "x", "name": "X"}]}
    areas = {"ortsteil:a": list(range(8)), "bezirk:x": list(range(8, 30))}
    gebietszahlen.annotate(index, areas, papers, "2026-06-01")
    assert "themen_stadt" in index["zahlen"] and "themen_bonn" not in index["zahlen"]
    a = index["ortsteile"][0]["auffaellig"]
    assert a and a["thema"] == "verkehr" and "anteil_stadt" in a and "anteil_bonn" not in a
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    assert "themen_stadt" in app and "anteil_stadt" in app


def test_kein_bonner_pilotexport():
    from pipeline import export
    assert not hasattr(export, "export_pilot") and not hasattr(export, "_sample")


# --- Verhalten einzelner Funktionen aus site/app.js in node (ohne Browser; Karte, Tour und Zeitleiste im Ganzen erst
# mit Browser-Tests in Phase 4) ------------------------------------------------------------------------------------------
def _js_teil(src, kopf):
    """Quelltext einer Funktion bzw. const-Anweisung aus app.js ab `kopf` bis zur schließenden Klammer bzw. zum `;`."""
    start = src.index(kopf)
    tiefe, gesehen = 0, False
    for i in range(start, len(src)):
        c = src[i]
        if c in "([{":
            tiefe += 1
            gesehen = gesehen or c == "{"
        elif c in ")]}":
            tiefe -= 1
            if kopf.startswith("function") and gesehen and tiefe == 0 and c == "}":
                return src[start:i + 1]
        elif c == ";" and tiefe == 0 and not kopf.startswith("function"):
            return src[start:i + 1]
    raise AssertionError(f"{kopf} nicht gefunden")


def test_app_funktionen_in_node():
    """parseArea, stadtBounds, startBounds und beispielGebiet aus dem echten app.js mit einem erfundenen index
    (Flächen „Quartier A/B/C“, keine Wuppertaler Werte): alte Bonner Links fallen auf die Startansicht, die Box der
    Stadt ist die Vereinigung der Stadtbezirks-bbox, das Tour-Beispiel ist das Quartier mit den meisten Vorlagen."""
    node = shutil.which("node")
    assert node, "node fehlt (auf ubuntu-latest vorhanden)"
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    teile = [_js_teil(app, k) for k in ("const STADT =", "const BONN =", "const DEFAULT_AREA =", "function parseArea(",
                                         "const bboxBounds =", "function stadtBounds(", "function startBounds(",
                                         "const beispielGebiet =")]
    probe = """
let index = null;
%s
const r = {};
r.ohneIndex = parseArea("bonn:ganz");
r.ohneIndexBeispiel = beispielGebiet();
r.ohneIndexStart = startBounds(null, "wuppertal:alle");
index = {
  ortsteile: [{ name: "Quartier B", slug: "quartier-b", stadtbezirk: "Bezirk 1", count: 7, bbox: [1, 1, 2, 2] },
              { name: "Quartier A", slug: "quartier-a", stadtbezirk: "Bezirk 1", count: 7, bbox: [0, 0, 1, 1] },
              { name: "Quartier C", slug: "quartier-c", stadtbezirk: "Bezirk 2", count: 3, bbox: [5, 5, 6, 6] }],
  bezirke: [{ name: "Bezirk 1", slug: "bezirk-1", count: 14, bbox: [0, 0, 2, 2] },
            { name: "Bezirk 2", slug: "bezirk-2", count: 3, bbox: [5, -1, 6, 6] }],
  ohne_ortsbezug: [{ jahr: "2024", count: 1 }],
};
r.bonnGanz = parseArea("bonn:ganz");
r.bonnZentrum = parseArea("ortsteil:bonn-zentrum");
r.ganz = parseArea("wuppertal:ganz");
r.ortsteil = parseArea("ortsteil:quartier-c");
r.ohne = parseArea("ohne:2024");
r.stadt = stadtBounds(index);
r.startOrtsteil = startBounds(index, "ortsteil:quartier-c");
r.startFremd = startBounds(index, "ortsteil:bonn-zentrum");
r.beispiel = beispielGebiet();
index.ortsteile.forEach((o) => { o.count = 0; });
r.beispielLeer = beispielGebiet();
console.log(JSON.stringify(r));
""" % "\n".join(teile)
    aus = subprocess.run([node, "-e", probe], capture_output=True, text=True, timeout=60)
    assert aus.returncode == 0, aus.stderr
    r = json.loads(aus.stdout)
    stadt = {"kind": "wuppertal", "key": "alle", "name": "ganz Wuppertal", "file": None}
    assert r["ohneIndex"] == stadt and r["ohneIndexBeispiel"] is None and r["ohneIndexStart"] is None
    assert r["bonnGanz"] == stadt and r["bonnZentrum"] == stadt and r["ganz"] == stadt
    assert r["ortsteil"] == {"kind": "ortsteil", "key": "quartier-c", "name": "Quartier C",
                             "file": "data/export/wuppertal/ortsteile/quartier-c.json"}
    assert r["ohne"]["file"] == "data/export/wuppertal/ohne-ortsbezug/2024.json"
    assert r["stadt"] == [[0, -1], [6, 6]]
    assert r["startOrtsteil"] == [[5, 5], [6, 6]] and r["startFremd"] == r["stadt"]
    # Gleichstand 7:7 → alphabetisch „Quartier A“; ohne Vorlagen kein Beispiel
    assert r["beispiel"]["slug"] == "quartier-a" and r["beispielLeer"] is None
