"""Aufgaben 5 und 6 (messunabhängige Teile von Phase 2):

- Bebauungspläne (CC BY-ND 4.0, CLAUDE.md 3.2 und 6): Die Geometrien werden weder vereinfacht noch gerundet oder
  repariert; flaechen.write und bplan.speichern reichen sie wertgleich durch, mit Lizenzhinweis.
- Bonner feste Angaben ersetzt: Zeitraum ab 01.01.2020 als config.DATEN_AB (CLAUDE.md 2), Links auf
  daimpad/ratsatlas-wuppertal, SITE_URL, Seitenname, kein Bonner Vorschaubild (CLAUDE.md 9), technik/ ohne pages.yml.

Ohne Netz, mit erfundenen Daten (Koordinaten um 0°/0°) und dem lokalen Testserver aus conftest.oparl."""
import json
import re
import shutil
from pathlib import Path

import pytest

from pipeline import bplan, build, config, flaechen, gebietsseiten, publish, sessionnet, seo, technikseite

ROOT = Path(__file__).resolve().parents[1]

# erfundene Pläne: viele Nachkommastellen, Werte, die Rundung oder Vereinfachung verändern würden, eine sich selbst
# schneidende Fläche (Schleife), ein Punkt fast auf der Kante (Douglas-Peucker würde ihn entfernen)
SCHLEIFE = [[[0.001234567891, 0.001], [0.0031234567891, 0.0030000000001], [0.0031234567891, 0.001],
             [0.001234567891, 0.0030000000001], [0.001234567891, 0.001]]]
FAST_GERADE = [[[0.004, 0.004], [0.00500000001, 0.0040000000003], [0.006, 0.004], [0.006, 0.005],
                [0.004, 0.005], [0.004, 0.004]]]
PLAENE = {"type": "FeatureCollection", "features": [
    {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": SCHLEIFE},
     "properties": {"name": "Testplan 1", "frei": "erfunden"}},
    {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [FAST_GERADE]},
     "properties": {"name": "Testplan 2"}},
]}


def _koordinaten(o):
    """Alle Zahlen einer Geometrie als Text (repr), in Reihenfolge."""
    if isinstance(o, list):
        return [x for e in o for x in _koordinaten(e)]
    return [repr(o)]


# --- Bebauungspläne unverändert ----------------------------------------------------------------------------------

def test_flaechen_reicht_bplan_wertgleich_durch(tmp_path, monkeypatch):
    quelle = tmp_path / "bplan.geojson"
    quelle.write_text(json.dumps(PLAENE, ensure_ascii=False), encoding="utf-8")
    gebiete = tmp_path / "gebiete.geojson"
    gebiete.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"ortsteil_bez": "A"},
         "geometry": {"type": "Polygon", "coordinates": FAST_GERADE}}]}), encoding="utf-8")
    monkeypatch.setattr(config, "BPLAN", quelle)
    monkeypatch.setattr(config, "ORTSTEILE", gebiete)
    monkeypatch.setattr(config, "STADTBEZIRKE", tmp_path / "fehlt.geojson")
    sizes = flaechen.write(tmp_path / "out")
    assert set(sizes) == {"ortsteile", "bebauungsplaene"}
    out = json.loads((tmp_path / "out" / "flaechen" / "bebauungsplaene.json").read_text(encoding="utf-8"))
    # Features wertgleich (Geometrie, Eigenschaften, Reihenfolge), Koordinaten auch als Text gleich
    assert out["features"] == PLAENE["features"]
    for alt, neu in zip(PLAENE["features"], out["features"]):
        assert _koordinaten(neu["geometry"]["coordinates"]) == _koordinaten(alt["geometry"]["coordinates"])
    text = (tmp_path / "out" / "flaechen" / "bebauungsplaene.json").read_text(encoding="utf-8")
    assert "0.0031234567891" in text and "0.0030000000001" in text and "0.00500000001" in text
    # Lizenzhinweis
    assert "CC BY-ND 4.0" in out["meta"]["license"]
    assert out["meta"]["attribution"] == config.NAMENSNENNUNG_BPLAN
    assert "unverändert" in out["meta"]["geometrie"]
    # Quartiere werden weiterhin vereinfacht und gerundet (5 Stellen): der Punkt fast auf der Kante entfällt
    ot = json.loads((tmp_path / "out" / "flaechen" / "ortsteile.json").read_text(encoding="utf-8"))
    ring = ot["features"][0]["geometry"]["coordinates"][0]
    assert [0.00500000001, 0.0040000000003] not in ring and len(ring) < len(FAST_GERADE[0])
    assert all(len(repr(c).split(".")[1]) <= 5 for p in ring for c in p)


def test_flaechen_behaelt_vorhandenes_meta_der_quelle(tmp_path, monkeypatch):
    quelle = tmp_path / "bplan.geojson"
    quelle.write_text(json.dumps({**PLAENE, "meta": {"source": "x", "license": "Lizenz laut Quelle"}}), encoding="utf-8")
    monkeypatch.setattr(config, "BPLAN", quelle)
    monkeypatch.setattr(config, "ORTSTEILE", tmp_path / "fehlt1")
    monkeypatch.setattr(config, "STADTBEZIRKE", tmp_path / "fehlt2")
    flaechen.write(tmp_path)
    out = json.loads((tmp_path / "flaechen" / "bebauungsplaene.json").read_text(encoding="utf-8"))
    assert out["meta"]["source"] == "x" and out["meta"]["license"] == "Lizenz laut Quelle"
    assert out["features"] == PLAENE["features"]


def test_simplify_bleibt_fuer_kontext_unveraendert():
    """kontext.py ruft flaechen.simplify(sammlung, toleranz) auf; Signatur und Verhalten bleiben."""
    sammlung = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"x": 1}, "geometry": {"type": "Polygon", "coordinates": FAST_GERADE}}]}
    out = flaechen.simplify(sammlung, 0.0001)
    assert out["features"][0]["properties"] == {"x": 1}
    assert len(out["features"][0]["geometry"]["coordinates"][0]) < len(FAST_GERADE[0])


def test_bplan_speichern_ohne_bearbeitung(tmp_path):
    ziel = tmp_path / "geo" / "bebauungsplaene_wuppertal.geojson"
    ohne_geometrie = {"type": "Feature", "geometry": None, "properties": {"name": "ohne Fläche"}}
    n = bplan.speichern({**PLAENE, "features": [*PLAENE["features"], ohne_geometrie]}, ziel,
                        jetzt="2026-11-09T00:00:00+00:00")
    assert n == 2
    d = json.loads(ziel.read_text(encoding="utf-8"))
    assert d["features"] == PLAENE["features"]   # gleiche Werte, gleiche Reihenfolge, keine Sortierung
    assert d["meta"]["source"] == config.SOURCES[config.QUELLE_BPLAN]["url"]
    assert "CC BY-ND 4.0" in d["meta"]["license"] and d["meta"]["attribution"] == config.NAMENSNENNUNG_BPLAN
    assert d["meta"]["ohne_geometrie"] == 1 and d["meta"]["retrieved_at"] == "2026-11-09T00:00:00+00:00"
    assert "vereinfacht_m" not in d["meta"]
    assert "0.0031234567891" in ziel.read_text(encoding="utf-8")


def test_bplan_speichern_schutzregel(tmp_path):
    """Weniger als 90 % des bisherigen Bestands: Abbruch, der alte Stand bleibt (Regel aus Köln)."""
    ziel = tmp_path / "bplan.geojson"
    bplan.speichern({"type": "FeatureCollection", "features": PLAENE["features"] * 10}, ziel)
    vorher = ziel.read_bytes()
    with pytest.raises(RuntimeError, match="Stand bleibt"):
        bplan.speichern(PLAENE, ziel)
    assert ziel.read_bytes() == vorher
    assert bplan.config_min(100) == 90


def test_export_reicht_bplan_durch_und_zeitachse_ab_2020(oparl):
    """Ganzer Lauf (fetch, build, export) auf dem lokalen Testserver: B-Pläne wertgleich in flaechen/, Zeitachse und
    meta.daten_ab ab config.DATEN_AB, obwohl eine erfundene Vorlage von 2019 in den Daten steht."""
    from pipeline import export
    oparl.papers[0]["date"] = "2019-11-15"
    sessionnet.fetch_all()
    build.build()
    config.BPLAN.write_text(json.dumps(PLAENE), encoding="utf-8")
    export.export()
    out = config.EXPORT / config.STADT
    plaene = json.loads((out / "flaechen" / "bebauungsplaene.json").read_text(encoding="utf-8"))
    assert plaene["features"] == PLAENE["features"]
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert index["meta"]["daten_ab"] == config.DATEN_AB == "2020-01-01"
    zeit = json.loads((out / "zeit.json").read_text(encoding="utf-8"))
    assert zeit["months"][0] >= "2020-01"   # Bonner Grenze „2019“ hätte 2019-11 ergeben
    assert zeit["data_start"] == "2019-11-15"   # Daten selbst unverändert (Zeitfilter erst nach Messstufe 1/2)


# --- Zeitraum, Adressen, Seitenname ----------------------------------------------------------------------------

def test_leerer_feed_ohne_bonner_datum():
    xml = publish._atom("tag:x", "T", "U", "https://wuppertal.ratsatlas.de/a.xml", "https://wuppertal.ratsatlas.de/", [])
    assert "<updated>2020-01-01T00:00:00Z</updated>" in xml and "2019" not in xml


def test_konfiguration_wuppertal():
    # Vorgabe ohne Umgebungsvariable SITE_URL (CLAUDE.md 2)
    assert 'os.environ.get("SITE_URL", "https://wuppertal.ratsatlas.de/")' in (ROOT / "pipeline" / "config.py").read_text()
    assert config.SEITENNAME == "Ratsatlas Wuppertal" and config.DATEN_AB == "2020-01-01"
    assert seo.DEFAULT_URL == "https://daimpad.github.io/ratsatlas-wuppertal/"
    assert gebietsseiten.EIGENE == ("wuppertal.ratsatlas.de", "daimpad.github.io/ratsatlas-wuppertal")
    assert technikseite.REPO == "https://github.com/daimpad/ratsatlas-wuppertal"


BONNER_ANGABEN = ("ratsatlas-bonn", "bonn.ratsatlas.de", "ris-bonn.datenatlas.de", "Ratsatlas Bonn", "Oktober 2019",
                  "export/bonn/", "ganz-bonn.xml", "allris-bonn-export", "machdenstaat")
# erlaubt: Herkunftsangaben (CLAUDE.md 2) und der verborgene Block der abgeschalteten Volltextsuche über OParl-Lite
HERKUNFT = ("Code des Ratsatlas Bonn (daimpad/allris-test)", "auf Grundlage des Ratsatlas Bonn und des Abrufs")
VOLLTEXT = re.compile(r'<div class="doc-search" data-funktion="volltextsuche" hidden>.*?</div>', re.S)


def _bonner_angaben(text, js=False):
    for h in HERKUNFT:
        text = text.replace(h, "")
    text = VOLLTEXT.sub("", text)
    if js:   # Kommentare und die Volltextsuche (abgeschaltetes Zusatzthema, const LITE) in app.js
        text = "\n".join(z for z in text.splitlines() if not z.lstrip().startswith("//") and "const LITE" not in z)
    return [a for a in BONNER_ANGABEN if a in text]


@pytest.mark.parametrize("datei", ["site/index.html", "site/datenschutz.html", "site/404.html", "site/app.js",
                                   "site/tour.js", "site/timeline.js", "site/site.webmanifest",
                                   ".github/ISSUE_TEMPLATE/config.yml", ".github/ISSUE_TEMPLATE/fehler.yml",
                                   ".github/ISSUE_TEMPLATE/idee.yml", ".github/ISSUE_TEMPLATE/verortung.yml",
                                   "README.md", "CONTRIBUTING.md", "deploy/htaccess", "docs/PLESK.md",
                                   ".github/workflows/pages.yml", "tools/seite_bauen.py"])
def test_statische_dateien_ohne_bonner_adressen_und_zeitraum(datei):
    gefunden = _bonner_angaben((ROOT / datei).read_text(encoding="utf-8"), js=datei.endswith(".js"))
    assert not gefunden, gefunden


def test_kein_bonner_vorschaubild():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "og:image" not in html and "og-image" not in html
    assert '<meta name="twitter:card" content="summary">' in html
    assert '"image"' not in re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    # pages.yml lädt nur die mit tools/seite_bauen.py gebaute Seite hoch (ohne og-image.jpg, tests/test_seite_bauen.py),
    # nicht das ganze Repository wie früher static.yml
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert wf.index("python tools/seite_bauen.py _site") < wf.index("upload-pages-artifact")
    assert 'path: "_pages"' in wf and "cp -r _site _pages" in wf and "path: '.'" not in wf and 'path: "."' not in wf
    assert not (ROOT / ".github" / "workflows" / "static.yml").exists()


def test_seo_write_veroeffentlicht_ohne_bonner_angaben(tmp_path, monkeypatch):
    """Zusammengestellte Seite wie im künftigen Hauptlauf (site/ → _site, dann seo.write): kein og-image.jpg, keine
    Bonner Adressen, Platzhalter durch SITE_URL ersetzt, Seitenname Wuppertal. Ohne data/ (keine Gebiets- und
    Vorgangsseiten); Begriffe (glossar.py) prüft tests/test_kern_ohne_bonn.py."""
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)
    site = tmp_path / "_site"
    shutil.copytree(ROOT / "site", site)
    assert (site / "og-image.jpg").exists()
    seo.write(site, "https://wuppertal.ratsatlas.de/")
    assert not (site / "og-image.jpg").exists()
    for name in ("index.html", "datenschutz.html", "404.html"):
        html = (site / name).read_text(encoding="utf-8")
        assert "Ratsatlas Wuppertal" in html, name
        assert "https://wuppertal.ratsatlas.de/" in html and "daimpad.github.io/ratsatlas-wuppertal/" not in html, name
    assert '<link rel="canonical" href="https://wuppertal.ratsatlas.de/">' in (site / "index.html").read_text()
    for f in [*site.glob("*.html"), *site.glob("*.xml"), site / "robots.txt", site / "rss" / "index.html"]:
        gefunden = _bonner_angaben(f.read_text(encoding="utf-8"))
        assert not gefunden, (f.name, gefunden)
    rss = (site / "rss" / "index.html").read_text(encoding="utf-8")
    assert "data/export/wuppertal/feeds/ganz-wuppertal.xml" in rss and "Feed für ganz Wuppertal" in rss
    assert "CC0" not in rss and "OParl-Lite" not in rss


def test_technikseite_ohne_pages_yml_und_browsertests(tmp_path, monkeypatch):
    """technik/ ist bis Phase 5 abgeschaltet, write() bricht trotzdem nicht ab: ohne pages.yml (Kopie mit static.yml),
    tests/browser/package.json fehlt (Guard aus ratsatlas-koeln @d609111). Sinngemäß Kölns test_technikseite_ohne_bonn.
    Seit Phase 4 gibt es tests/browser/package.json; der Fall ohne sie läuft über eine Kopie der Wurzel ohne tests/
    (Verweise auf die übrigen Einträge), danach der Fall mit den Browser-Tests."""
    wf = tmp_path / "workflows"
    wf.mkdir()
    shutil.copy(ROOT / ".github" / "workflows-inaktiv" / "static.yml", wf / "static.yml")
    (wf / "neu.yml").write_text('name: Unbekannt\non:\n  workflow_dispatch:\njobs:\n  x:\n    runs-on: ubuntu-latest\n')
    monkeypatch.setattr(technikseite, "WORKFLOWS", wf)
    ohne = tmp_path / "wurzel_ohne_browsertests"
    ohne.mkdir()
    for eintrag in ROOT.iterdir():
        if eintrag.name != "tests":
            (ohne / eintrag.name).symlink_to(eintrag)
    (ohne / "tests").mkdir()
    monkeypatch.setattr(config, "ROOT", ohne)
    assert not (ohne / "tests" / "browser" / "package.json").exists()
    assert technikseite.versionen()["browser"] == {}
    assert technikseite.versionen()["browsertests"] == 0
    pfade = technikseite.write(tmp_path / "_site", "https://wuppertal.ratsatlas.de/", gebietsseiten._page)
    assert pfade == ["technik/"]
    text = (tmp_path / "_site" / "technik" / "index.html").read_text(encoding="utf-8")
    assert "Ratsatlas Wuppertal" in text and "github.com/daimpad/ratsatlas-wuppertal" in text
    for wort in ("Bonn", "Köln", "allris", "OParl-Lite"):
        assert wort not in text, wort
    # mit dem echten Ordner (pages.yml, tests.yml) und den Browser-Tests (Phase 4) ebenso
    monkeypatch.setattr(config, "ROOT", ROOT)
    monkeypatch.setattr(technikseite, "WORKFLOWS", ROOT / ".github" / "workflows")
    paket = json.loads((ROOT / "tests" / "browser" / "package.json").read_text(encoding="utf-8"))
    assert technikseite.versionen()["browser"] == paket["dependencies"]
    assert technikseite.versionen()["browsertests"] == len(list((ROOT / "tests" / "browser").glob("*.test.mjs"))) > 0
    technikseite.write(tmp_path / "_site2", "https://wuppertal.ratsatlas.de/", gebietsseiten._page)
    text = (tmp_path / "_site2" / "technik" / "index.html").read_text(encoding="utf-8")
    for wort in ("Bonn", "Köln", "allris", "OParl-Lite"):
        assert wort not in text, wort


# --- Nachprüfung: Quellenangaben ohne OParl-Lite, Namensnennung auf jeder Seite, Datenstand ----------------------------

def test_veroeffentlichte_seiten_mit_namensnennung_und_ohne_oparl_lite(oparl, tmp_path, monkeypatch):
    """Ganzer Lauf (fetch, build, export) auf dem lokalen Testserver, dann seo.write auf einer Kopie von site/ mit dem
    Export: Gebiets-, Vorgangs- und Begriffsseiten nennen kein OParl-Lite (gibt es in Wuppertal nicht, CLAUDE.md 3.2);
    Gebiets- und Vorgangsseiten tragen die Namensnennung der Geodaten (CLAUDE.md 3.2: auf jeder Seite). index.json
    nennt die Quellenkennung der Ratsdaten, aus der app.js den Datenstand liest."""
    from pipeline import export
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)
    sessionnet.fetch_all()
    build.build()
    export.export()
    index = json.loads((config.EXPORT / config.STADT / "index.json").read_text(encoding="utf-8"))
    assert index["meta"]["quelle_oparl"] == config.QUELLE_OPARL == "oparl-wuppertal"
    assert config.QUELLE_OPARL in {q["name"] for q in index["meta"]["sources"]}
    site = tmp_path / "_site"
    shutil.copytree(ROOT / "site", site)
    shutil.copytree(config.EXPORT / config.STADT, site / "data" / "export" / config.STADT)
    seo.write(site, "https://wuppertal.ratsatlas.de/")
    gebiete = [*(site / "ortsteil").rglob("index.html"), *(site / "stadtbezirk").rglob("index.html")]
    vorgaenge = list((site / "vorgang").rglob("index.html"))
    assert gebiete and vorgaenge, (gebiete, vorgaenge)
    for f in [*gebiete, *vorgaenge, site / "gebiete" / "index.html", site / "begriffe" / "index.html"]:
        html = f.read_text(encoding="utf-8")
        assert "OParl-Lite" not in html, f
        assert config.NAMENSNENNUNG in html and config.NAMENSNENNUNG_BPLAN in html, f


def test_app_js_ohne_bonner_quellenkennung_und_oparl_lite():
    """Datenstand und Prozesslinie: keine Bonner Quellenkennung, kein OParl-Lite in angezeigten Texten (Kommentare und
    die abgeschaltete Volltextsuche ausgenommen); Hinweis auf einen fehlgeschlagenen Abruf (CLAUDE.md 5.1)."""
    for f in ("app.js", "timeline.js", "tour.js"):
        text = (ROOT / "site" / f).read_text(encoding="utf-8")
        assert "oparl-bonn" not in text and "oparl-lite" not in text, f
        zeilen = [z for z in text.splitlines() if not z.lstrip().startswith("//") and "const LITE" not in z]
        assert not [z for z in zeilen if "OParl-Lite" in z], f
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    assert "index.meta.quelle_oparl" in app and "index.meta.abruf_fehler" in app
    assert "ist fehlgeschlagen; gezeigt wird der letzte gültige Datenstand" in app


def test_index_html_quellen_und_stand_ohne_vorgriff():
    """Über-Dialog trennt Ratsdaten (OParl-API, Lizenz ungeklärt) und Geodaten (Namensnennung); Quellenzeile nennt die
    Stadtbezirke; „Was ist neu?“ meldet Gebiete und Zeitraum nicht als fertig; Volltextsuche nur als data-funktion."""
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    ueber = re.search(r"<h3>Wer steckt dahinter\?</h3>(.*?)</p>", html, re.S).group(1)
    assert "OParl-API" in ueber and "Lizenz ungeklärt" in ueber and config.NAMENSNENNUNG in ueber
    assert "Stadtbezirke: Stadt Wuppertal – offenedaten-wuppertal.de (Lizenz noch zu prüfen)" in html
    neu = re.search(r'<dialog id="neu".*?</dialog>', html, re.S).group(0)
    assert "In Vorbereitung" in neu and "69 Quartieren" not in neu and "10 Stadtbezirken" not in neu
    ohne_volltext = VOLLTEXT.sub("", html)
    ohne_volltext = re.sub(r'<span data-funktion="volltextsuche" hidden>.*?</span>', "", ohne_volltext, flags=re.S)
    assert "OParl-Lite" not in ohne_volltext and "im Text der Dokumente suchen" not in ohne_volltext
    assert config.SOURCES[config.QUELLE_STADTBEZIRKE]["url"].startswith("https://")
