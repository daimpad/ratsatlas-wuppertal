"""Veröffentlichung ohne Abruf (CLAUDE.md 9, 10.11.2026): tools/seite_bauen.py baut die fertige Seite (nur
auslieferbare Dateien, ohne Daten noindex, Canonical auf SITE_URL, .htaccess), .github/workflows/pages.yml schreibt sie
ohne Abruf und ohne Zeitplan in den Branch deploy (ohne Historie) und auf GitHub Pages. Keine Anfragen an Server."""
import importlib.util
import json
import re
import shutil
import subprocess

import pytest

from pipeline import config

ROOT = config.ROOT
WF = ROOT / ".github" / "workflows" / "pages.yml"
ENDUNGEN = {".html", ".js", ".css", ".png", ".ico", ".svg", ".webmanifest", ".woff2", ".txt", ".xml", ".md"}
NAMEN = {".htaccess", "robots.txt", "LICENSE", "vorschaubild.jpg"}
VERBOTEN = ("pipeline/", "explore/", "tests/", ".github", "data/raw", "inventur/", "tools/", "chat/", "CLAUDE.md",
            "og-image.jpg", "package.json", "haushalt.js", "thema.js", "technik.js", "prozesse.js", "beteiligung.js")
# Wurzelabsolute Pfade ("/…", nicht "//…") brechen auf der Ausweichadresse /ratsatlas-wuppertal/
WURZELPFAD = re.compile(r"""(?:\b(?:href|src|action)\s*=\s*|\bfetch\(\s*|\bimport\(\s*|url\(\s*)["'`]?/(?![/*])""")


def _bauskript():
    spec = importlib.util.spec_from_file_location("seite_bauen", ROOT / "tools" / "seite_bauen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _bauen(tmp_path, monkeypatch, export, site_url="https://wuppertal.ratsatlas.de/", geo=None, gebietskarte=None):
    """Seite bauen; ohne `geo` zeigen die Pfade der Flächen ins Leere (Stand ohne Geodaten, unabhängig von data/geo),
    mit `geo` (Name → Pfad, z. B. aus testseite.testgebiete) auf diese Dateien. Gebietskarte freigegeben, wenn `geo`
    angegeben ist (sonst wie im Workflow aus der Umgebung), außer `gebietskarte` sagt es ausdrücklich."""
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)
    monkeypatch.setattr(config, "EXPORT", export)
    monkeypatch.setattr(config, "SITE_URL", site_url)
    for name in ("ORTSTEILE", "STADTBEZIRKE", "BPLAN"):
        monkeypatch.setattr(config, name, (geo or {}).get(name, tmp_path / f"fehlt-{name.lower()}.geojson"))
    monkeypatch.delenv("RATSATLAS_GEBIETSKARTE", raising=False)
    ziel = tmp_path / "_site"
    _bauskript().main(ziel, gebietskarte=(geo is not None) if gebietskarte is None else gebietskarte)
    return ziel


def _dateien(ziel):
    return sorted(p.relative_to(ziel).as_posix() for p in ziel.rglob("*") if p.is_file())


def test_ohne_daten_nur_seite_und_noindex(tmp_path, monkeypatch):
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer")
    dateien = _dateien(ziel)
    for d in dateien:
        name = d.rsplit("/", 1)[-1]
        assert name in NAMEN or "." + name.rsplit(".", 1)[-1] in ENDUNGEN, d
        assert not d.endswith((".py", ".yml", ".jsonl", ".sqlite", ".json", ".jpg")) or d == "vorschaubild.jpg", d
        assert not any(v in d for v in VERBOTEN), d
    assert "index.html" in dateien and "data/LICENSE-DATA.md" in dateien
    assert not (ziel / "data" / "export").exists() and not list(ziel.glob("sitemap*.xml"))
    htaccess = (ziel / ".htaccess").read_text(encoding="utf-8")
    assert 'Header always set X-Robots-Tag "noindex"' in htaccess and "bonn" not in htaccess.lower()
    seiten = list(ziel.rglob("*.html"))
    assert len(seiten) >= 5
    for seite in seiten:
        html = seite.read_text(encoding="utf-8")
        assert html.count('<meta name="robots" content="noindex">') == 1, seite
        assert "index, follow" not in html, seite
    robots = (ziel / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap" not in robots and "Disallow: /" not in robots
    index = (ziel / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://wuppertal.ratsatlas.de/">' in index
    assert "daimpad.github.io/ratsatlas-wuppertal/" not in index


def test_ohne_daten_ohne_ratsassistent_und_relative_pfade(tmp_path, monkeypatch):
    """Abgeschalteter Ratsassistent: CSP ohne fremde Hosts außer den OSM-Kacheln, Datenschutzerklärung ohne ihn; alle
    Pfade relativ, damit die Seite auch unter /ratsatlas-wuppertal/ (GitHub Pages) funktioniert."""
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer")
    index = (ziel / "index.html").read_text(encoding="utf-8")
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', index).group(1)
    assert "connect-src 'self';" in csp
    assert set(re.findall(r"https?://[^\s;]+", csp)) == {"https://tile.openstreetmap.org"}
    datenschutz = (ziel / "datenschutz.html").read_text(encoding="utf-8")
    for wort in ("Ratsassistent", "Anthropic", "OpenRouter", "Mistral", "ris-assistent"):
        assert wort not in datenschutz, wort
    assert "<h2>Kartenkacheln</h2>" in datenschutz and "<h2>Was im Browser gespeichert wird</h2>" in datenschutz
    assert "tile.openstreetmap.org" in datenschutz
    for f in sorted(ziel.rglob("*")):
        if f.suffix in (".html", ".js", ".css") and f.name != "404.html":
            treffer = WURZELPFAD.findall(f.read_text(encoding="utf-8"))
            assert not treffer, (f.relative_to(ziel).as_posix(), treffer[:3])
    assert WURZELPFAD.search('<a href="/datenschutz.html">') and WURZELPFAD.search('fetch("/data/x.json")')
    assert not WURZELPFAD.search('<a href="//example.org/">') and not WURZELPFAD.search('href="data/x"')


def _mit_daten(tmp_path):
    export = tmp_path / "export"
    (export / config.STADT).mkdir(parents=True)
    (export / config.STADT / "index.json").write_text('{"ortsteile": [], "bezirke": [], "ohne_ortsbezug": []}',
                                                      encoding="utf-8")
    return export


@pytest.mark.parametrize("daten", [False, True])
def test_namensnennung_auf_jeder_gebauten_seite(tmp_path, monkeypatch, daten):
    """CLAUDE.md 3.2 und data/LICENSE-DATA.md: Namensnennung der Stadt (CC BY 4.0, Bebauungspläne CC BY-ND 4.0) auf
    jeder Seite, auch auf Datenschutzerklärung und Fehlerseite."""
    ziel = _bauen(tmp_path, monkeypatch, _mit_daten(tmp_path) if daten else tmp_path / "leer")
    seiten = sorted(ziel.rglob("*.html"))
    assert {"datenschutz.html", "404.html", "index.html"} <= {s.name for s in seiten}
    for seite in seiten:
        html = seite.read_text(encoding="utf-8")
        assert config.NAMENSNENNUNG in html and config.NAMENSNENNUNG_BPLAN in html, seite


def test_datenschutz_ohne_bonner_reste_und_mit_hinweis_ohne_daten(tmp_path, monkeypatch):
    """Datenschutzerklärung: § 24 GO NRW statt Bonner „Bürgeranträge“, keine Amtsträger (keine Personennamen aus
    Personenlisten oder Dokumenten, CLAUDE.md 2); ohne Daten der Hinweis, dass noch keine Ratsdaten gezeigt werden, und
    im noscript-Block keine Links auf Dateien, die erst mit Daten entstehen."""
    ohne = _bauen(tmp_path / "a", monkeypatch, tmp_path / "leer")
    mit = _bauen(tmp_path / "b", monkeypatch, _mit_daten(tmp_path))
    hinweis = "Derzeit zeigt die Seite noch keine Ratsdaten"
    for ziel, hat_daten in ((ohne, False), (mit, True)):
        ds = (ziel / "datenschutz.html").read_text(encoding="utf-8")
        assert "§ 24 GO NRW" in ds and "Bürgerantr" not in ds and "Amtsträger" not in ds
        assert "keine eigene Vorgangsseite" in ds and "Konto bei GitHub" in ds
        assert (hinweis in ds) is not hat_daten
        noscript = re.search(r"<noscript>(.*?)</noscript>", (ziel / "index.html").read_text(encoding="utf-8"), re.S).group(1)
        assert ("export.zip" in noscript and "gebiete/" in noscript) is hat_daten
    rss = (ohne / "rss" / "index.html").read_text(encoding="utf-8")
    # kein Versprechen eines täglichen Laufs, solange pages.yml ohne Zeitplan läuft; kein Bonner Beispiel für die Kennung
    assert "frühmorgens" not in rss and "papers/2022978" not in rss and "keinen regelmäßigen Lauf" in rss
    assert "einmal am Tag (" not in rss


def test_version_txt_mit_commit_von_main(tmp_path, monkeypatch):
    """version.txt für die Live-Prüfung (tools/live_pruefen.py): GITHUB_SHA, sonst git rev-parse HEAD, sonst „lokal“."""
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef0123456789abcdef01234567")
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer")
    assert (ziel / "version.txt").read_text(encoding="utf-8") == "0123456789abcdef0123456789abcdef01234567\n"
    bau = _bauskript()
    monkeypatch.setenv("GITHUB_SHA", "kein-commit")

    def ohne_git(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(bau.subprocess, "run", ohne_git)
    assert bau.stand() == "lokal"
    monkeypatch.undo()
    if shutil.which("git"):
        kopf = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
        if kopf.returncode == 0:
            monkeypatch.delenv("GITHUB_SHA", raising=False)
            assert bau.stand() == kopf.stdout.strip()


def test_unvollstaendige_seite_bricht_ab(tmp_path):
    bau = _bauskript()
    with pytest.raises(SystemExit, match="unvollständig"):
        bau.pruefen(tmp_path)
    with pytest.raises(ValueError, match="nicht genau einmal"):
        bau.ersetzen("ohne Stelle", "connect-src", "", "index.html")


def test_abweichende_site_url_im_canonical(tmp_path, monkeypatch):
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer", "https://beispiel.invalid/")
    for name in ("index.html", "datenschutz.html", "begriffe/index.html", "rss/index.html"):
        assert 'rel="canonical" href="https://beispiel.invalid/' in (ziel / name).read_text(encoding="utf-8"), name


def test_reproduzierbar(tmp_path, monkeypatch):
    a = _bauen(tmp_path / "a", monkeypatch, tmp_path / "leer")
    b = _bauen(tmp_path / "b", monkeypatch, tmp_path / "leer")
    assert _dateien(a) == _dateien(b)
    for d in _dateien(a):
        assert (a / d).read_bytes() == (b / d).read_bytes(), d


def test_mit_daten_ohne_noindex(tmp_path, monkeypatch):
    export = tmp_path / "export"
    (export / config.STADT).mkdir(parents=True)
    (export / config.STADT / "index.json").write_text('{"ortsteile": [], "bezirke": [], "ohne_ortsbezug": []}',
                                                      encoding="utf-8")
    ziel = _bauen(tmp_path, monkeypatch, export)
    assert (ziel / "data" / "export" / config.STADT / "index.json").is_file()
    assert "Header always set X-Robots-Tag" not in (ziel / ".htaccess").read_text(encoding="utf-8")
    assert "Sitemap: https://wuppertal.ratsatlas.de/sitemap.xml" in (ziel / "robots.txt").read_text(encoding="utf-8")
    assert (ziel / "sitemap.xml").is_file()
    assert '<meta name="robots" content="index, follow">' in (ziel / "index.html").read_text(encoding="utf-8")
    for seite in ziel.rglob("*.html"):
        if seite.name != "404.html":
            assert 'content="noindex"' not in seite.read_text(encoding="utf-8"), seite


def test_rss_seite_feeds_erst_mit_daten_und_cors(tmp_path, monkeypatch):
    """rss/ verspricht Feeds: ohne Daten ein Hinweis, dass es sie noch nicht gibt; mit Daten kein Hinweis. Der Satz zu
    CORS stimmt mit deploy/htaccess überein (Hauptadresse gibt Feeds und JSON frei), nicht mehr „noch nicht
    eingerichtet“."""
    ohne = (_bauen(tmp_path / "a", monkeypatch, tmp_path / "leer") / "rss" / "index.html").read_text(encoding="utf-8")
    assert ohne.count('id="rss-ohne-daten"') == 1 and "Noch keine Feeds:" in ohne
    export = tmp_path / "export"
    (export / config.STADT).mkdir(parents=True)
    (export / config.STADT / "index.json").write_text('{"ortsteile": [], "bezirke": [], "ohne_ortsbezug": []}',
                                                      encoding="utf-8")
    mit = (_bauen(tmp_path / "b", monkeypatch, export) / "rss" / "index.html").read_text(encoding="utf-8")
    assert "rss-ohne-daten" not in mit and "Noch keine Feeds" not in mit
    htaccess = (ROOT / "deploy" / "htaccess").read_text(encoding="utf-8")
    cors = re.search(r'<FilesMatch "([^"]*)">\s*Header set Access-Control-Allow-Origin "\*"', htaccess)
    assert cors and all(re.search(cors.group(1), f"feed.{e}") for e in ("xml", "json"))
    for html in (ohne, mit):
        assert "noch nicht eingerichtet" not in html
        assert ("<code>Access-Control-Allow-Origin: *</code> ausgeliefert, auf der Hauptadresse wie auf dem Spiegel "
                "<code>https://daimpad.github.io/ratsatlas-wuppertal/</code>") in html


def test_htaccess_cache_dauer_fuer_alle_bilder():
    """Jede Bildart, die die fertige Seite ausliefert (ENDUNGEN und NAMEN, darunter vorschaubild.jpg), hat in
    deploy/htaccess eine Expires-Zeile von einer Woche (Pflege 10.11.2026: JPEG fehlte)."""
    htaccess = (ROOT / "deploy" / "htaccess").read_text(encoding="utf-8")
    typen = {".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon"}
    endungen = ENDUNGEN | {"." + n.rsplit(".", 1)[1] for n in NAMEN if "." in n.lstrip(".")}
    bilder = {e for e in endungen if e in typen}
    assert bilder == set(typen), bilder
    for e in bilder:
        assert re.search(rf'^\s*ExpiresByType {re.escape(typen[e])} "access plus 1 week"$', htaccess, re.M), e
    # Gegenprobe: ohne die JPEG-Zeile schlägt die Prüfung an
    ohne = htaccess.replace('ExpiresByType image/jpeg "access plus 1 week"', "")
    assert not re.search(r'^\s*ExpiresByType image/jpeg "access plus 1 week"$', ohne, re.M)


# --- Gebietskarte ohne Ratsdaten (CLAUDE.md 9, 13.11.2026; erfundene Flächen aus tests/browser/testseite.py) ---------

def _testseite():
    spec = importlib.util.spec_from_file_location("testseite", ROOT / "tests" / "browser" / "testseite.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _flaechen(ziel):
    return ziel / "data" / "export" / config.STADT / "flaechen"


def test_gebietskarte_flaechen_namensnennung_und_noindex(tmp_path, monkeypatch, capsys):
    """Mit Flächen der Stadtbezirke und Quartiere, ohne Ratsdaten: flaechen/ wie im Gesamtexport (Quartiere und
    Stadtbezirke vereinfacht und so gekennzeichnet, Bebauungspläne unverändert mit CC BY-ND 4.0), kein index.json,
    weiter noindex; Datenschutzerklärung und noscript-Block mit „Ratsdaten folgen“ statt „Daten nicht verfügbar“."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer", geo=geo)
    assert "Gebietskarte: ortsteile" in capsys.readouterr().out
    fl = _flaechen(ziel)
    assert sorted(p.name for p in fl.iterdir()) == ["bebauungsplaene.json", "bezirke.json", "ortsteile.json"]
    assert not (ziel / "data" / "export" / config.STADT / "index.json").exists() and not (ziel / "data" / "geo").exists()
    quelle = json.loads(geo["BPLAN"].read_text(encoding="utf-8"))
    plaene = json.loads((fl / "bebauungsplaene.json").read_text(encoding="utf-8"))
    assert plaene["features"] == quelle["features"]               # CC BY-ND 4.0: Zahlen und Reihenfolge unverändert
    fliege = next(f for f in plaene["features"] if f["properties"]["name"] == "Testplan 4")
    assert fliege["geometry"]["coordinates"] == _testseite().TESTPLAN_FLIEGE
    assert plaene["meta"]["attribution"] == config.NAMENSNENNUNG_BPLAN and plaene["meta"]["geometrie"].startswith("unverändert")
    for name, anzahl in (("ortsteile.json", 3), ("bezirke.json", 2)):
        daten = json.loads((fl / name).read_text(encoding="utf-8"))
        assert len(daten["features"]) == anzahl and daten["meta"]["attribution"] == config.NAMENSNENNUNG
        assert daten["meta"]["geometrie"].startswith("vereinfacht") and daten["meta"]["retrieved_at"]
    assert {f["properties"]["ortsteil_bez"] for f in json.loads((fl / "ortsteile.json").read_text())["features"]} == {
        "Testquartier A", "Testquartier B", "Testquartier C"}
    for seite in ziel.rglob("*.html"):
        assert seite.read_text(encoding="utf-8").count('<meta name="robots" content="noindex">') == 1, seite
    assert 'Header always set X-Robots-Tag "noindex"' in (ziel / ".htaccess").read_text(encoding="utf-8")
    assert not list(ziel.glob("sitemap*.xml"))
    ds = (ziel / "datenschutz.html").read_text(encoding="utf-8")
    assert "Derzeit zeigt die Seite noch keine Ratsdaten (Hinweis „Ratsdaten folgen“)" in ds
    assert "Daten nicht verfügbar" not in ds
    noscript = re.search(r"<noscript>(.*?)</noscript>", (ziel / "index.html").read_text(encoding="utf-8"), re.S).group(1)
    assert "Noch liegen keine Ratsdaten vor; die Karte zeigt bisher nur die Gebiete der Stadt." in noscript
    assert "export.zip" not in noscript and "gebiete/" not in noscript


def test_gebietskarte_gegenprobe_bearbeitete_plaene_fallen_auf(tmp_path, monkeypatch):
    """Gegenprobe zur Prüfung „unverändert“: Würde flaechen.write die Bebauungspläne wie die Quartiere vereinfachen,
    wären Rundung (zehn Nachkommastellen) und Reparatur der sich schneidenden Fläche sichtbar."""
    from pipeline import flaechen
    monkeypatch.setattr(flaechen, "UNVERAENDERT", set())
    monkeypatch.setitem(flaechen.QUELLEN, "bebauungsplaene", lambda: config.QUELLE_BPLAN)
    geo = _testseite().testgebiete(tmp_path / "geo")
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer", geo=geo)
    plaene = json.loads((_flaechen(ziel) / "bebauungsplaene.json").read_text(encoding="utf-8"))
    quelle = json.loads(geo["BPLAN"].read_text(encoding="utf-8"))
    fliege = next(f for f in plaene["features"] if f["properties"]["name"] == "Testplan 4")
    assert plaene["features"] != quelle["features"]
    assert fliege["geometry"]["coordinates"] != _testseite().TESTPLAN_FLIEGE


def test_gebietskarte_ohne_beide_flaechen_wie_ohne_daten(tmp_path, monkeypatch):
    """Ohne Geodaten bleibt die Seite Byte für Byte wie ohne Daten (Live-Seite unverändert); ebenso, wenn nur die
    Quartiere oder nur die Stadtbezirke vorliegen. Gegenprobe: mit beiden Dateien unterscheidet sie sich."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    leer = _bauen(tmp_path / "leer", monkeypatch, tmp_path / "x")
    for teil in ("ORTSTEILE", "STADTBEZIRKE"):
        ziel = _bauen(tmp_path / teil, monkeypatch, tmp_path / "x", geo={teil: geo[teil], "BPLAN": geo["BPLAN"]})
        assert _dateien(ziel) == _dateien(leer), teil
        for d in _dateien(leer):
            assert (ziel / d).read_bytes() == (leer / d).read_bytes(), (teil, d)
    voll = _bauen(tmp_path / "beide", monkeypatch, tmp_path / "x", geo=geo)
    assert set(_dateien(voll)) - set(_dateien(leer)) == {
        f"data/export/{config.STADT}/flaechen/{n}" for n in ("bebauungsplaene.json", "bezirke.json", "ortsteile.json")}
    assert (voll / "datenschutz.html").read_bytes() != (leer / "datenschutz.html").read_bytes()


def test_gebietskarte_nur_mit_freigabe(tmp_path, monkeypatch, capsys):
    """Flächen allein veröffentlichen nichts: ohne RATSATLAS_GEBIETSKARTE=ja (Vorgabe im Workflow) bleibt die Seite
    Byte für Byte wie ohne Daten, mit Hinweis im Protokoll. Gegenprobe: mit der Umgebungsvariable entsteht die Karte."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    leer = _bauen(tmp_path / "leer", monkeypatch, tmp_path / "x")
    aus = _bauen(tmp_path / "aus", monkeypatch, tmp_path / "x", geo=geo, gebietskarte=False)
    assert "Gebietskarte nicht freigegeben" in capsys.readouterr().out
    assert _dateien(aus) == _dateien(leer)
    for d in _dateien(leer):
        assert (aus / d).read_bytes() == (leer / d).read_bytes(), d
    bau = _bauskript()
    for wert, erwartet in (("ja", True), ("ja\n", True), ("", False), ("nein", False), ("1", False), ("JA", False)):
        monkeypatch.setenv("RATSATLAS_GEBIETSKARTE", wert)
        assert bau.gebietskarte_freigegeben() is erwartet, wert
    monkeypatch.setattr(config, "EXPORT", tmp_path / "x")
    for name, pfad in geo.items():
        monkeypatch.setattr(config, name, pfad)
    monkeypatch.setenv("RATSATLAS_GEBIETSKARTE", "ja")
    bau.main(tmp_path / "an")
    assert (_flaechen(tmp_path / "an") / "ortsteile.json").is_file()


def test_gebietskarte_freigegeben_ohne_flaechen_meldet_es(tmp_path, monkeypatch, capsys):
    """Schalter gesetzt, aber Flächen fehlen (z. B. data/geo nicht im Checkout des Workflows): Seite wie ohne Daten,
    mit Hinweis im Protokoll, welche Datei fehlt. Gegenprobe: ohne Schalter kein solcher Hinweis."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    leer = _bauen(tmp_path / "leer", monkeypatch, tmp_path / "x")
    assert "Flächen fehlen" not in capsys.readouterr().out
    ziel = _bauen(tmp_path / "an", monkeypatch, tmp_path / "x", geo={"ORTSTEILE": geo["ORTSTEILE"]}, gebietskarte=True)
    aus = capsys.readouterr().out
    assert "Gebietskarte freigegeben, aber Flächen fehlen (" in aus and "fehlt-stadtbezirke.geojson" in aus
    assert "quartiere" not in aus.split("Flächen fehlen", 1)[1].split(")", 1)[0]
    assert "(ohne Daten: noindex)" in aus
    assert _dateien(ziel) == _dateien(leer)
    for d in _dateien(leer):
        assert (ziel / d).read_bytes() == (leer / d).read_bytes(), d


def test_gebietskarte_groessen_in_bytes(tmp_path, monkeypatch, capsys):
    """Die Größen im Protokoll sind Bytes der geschriebenen Dateien, nicht Zeichen (flaechen.write zählt Zeichen).
    Gegenprobe an einer Datei mit Umlauten und Gedankenstrich: Bytes und Zeichen unterscheiden sich."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "x", geo=geo)
    aus = capsys.readouterr().out
    fl = _flaechen(ziel)
    for n in ("ortsteile", "bezirke", "bebauungsplaene"):
        assert f"{n} {(fl / f'{n}.json').stat().st_size / 1024:.1f} KiB" in aus, n
    assert aus.index("Gebietskarte: ortsteile") < aus.index("bezirke") < aus.index("bebauungsplaene")
    probe = tmp_path / "probe"
    probe.mkdir()
    text = '{"name":"Überfeld – Süd"}'
    (probe / "a.json").write_text(text, encoding="utf-8")
    groessen = _bauskript().dateigroessen(probe, ["a"])
    assert groessen == {"a": len(text.encode("utf-8"))} and groessen["a"] != len(text)


def test_gebietskarte_entfaellt_mit_ratsdaten(tmp_path, monkeypatch):
    """Mit Ratsdaten (index.json) gilt der Gesamtexport: keine eigenen Flächen aus seite_bauen, kein noindex."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    ziel = _bauen(tmp_path, monkeypatch, _mit_daten(tmp_path), geo=geo)
    assert (ziel / "data" / "export" / config.STADT / "index.json").is_file() and not _flaechen(ziel).exists()
    assert 'content="noindex"' not in (ziel / "index.html").read_text(encoding="utf-8")


def test_gebietskarte_ohne_bebauungsplaene_und_reproduzierbar(tmp_path, monkeypatch):
    geo = _testseite().testgebiete(tmp_path / "geo")
    ohne = {k: v for k, v in geo.items() if k != "BPLAN"}
    a = _bauen(tmp_path / "a", monkeypatch, tmp_path / "x", geo=ohne)
    assert sorted(p.name for p in _flaechen(a).iterdir()) == ["bezirke.json", "ortsteile.json"]
    b = _bauen(tmp_path / "b", monkeypatch, tmp_path / "x", geo=ohne)
    assert _dateien(a) == _dateien(b)
    for d in _dateien(a):
        assert (a / d).read_bytes() == (b / d).read_bytes(), d


@pytest.mark.parametrize("name, feld", [("ORTSTEILE", "ortsteil_bez"), ("ORTSTEILE", "bezirk_bez"),
                                        ("STADTBEZIRKE", "bezirk_bez"), ("BPLAN", "name")])
def test_gebietskarte_ohne_feldnamen_bricht_ab(tmp_path, monkeypatch, name, feld):
    """Flächen mit den Feldnamen der Quelle statt des Bonner Modells (Zuordnung erst nach Messstufe G): Abbruch vor dem
    Bau, statt namenlose Flächen auszuliefern; eine vorhandene Seite bleibt unberührt."""
    geo = _testseite().testgebiete(tmp_path / "geo")
    daten = json.loads(geo[name].read_text(encoding="utf-8"))
    daten["features"][-1]["properties"]["QUELLFELD"] = daten["features"][-1]["properties"].pop(feld)
    geo[name].write_text(json.dumps(daten), encoding="utf-8")
    (tmp_path / "_site").mkdir()
    (tmp_path / "_site" / "alt.txt").write_text("alt", encoding="utf-8")
    with pytest.raises(SystemExit, match=rf"Fläche {len(daten['features'])} ohne {feld} "):
        _bauen(tmp_path, monkeypatch, tmp_path / "x", geo=geo)
    assert (tmp_path / "_site" / "alt.txt").is_file()


def test_testseite_gebietskarte_stellt_pfade_wieder_her(tmp_path):
    vorher = (config.ORTSTEILE, config.STADTBEZIRKE, config.BPLAN, config.EXPORT)
    ziel = _testseite().gebietskarte(tmp_path, "http://127.0.0.1:8799/")
    assert (config.ORTSTEILE, config.STADTBEZIRKE, config.BPLAN, config.EXPORT) == vorher
    assert (_flaechen(ziel) / "ortsteile.json").is_file() and (ziel / "index.html").is_file()
    assert 'href="http://127.0.0.1:8799/"' in (ziel / "index.html").read_text(encoding="utf-8")
    text = " ".join(p.read_text(encoding="utf-8") for p in _flaechen(ziel).iterdir())
    assert not re.search(r"Bonn|Köln|Wuppertal-|Barmen|Elberfeld", text.replace("Stadt Wuppertal", ""))


# --- .github/workflows/pages.yml (statisch) -------------------------------------------------------------------------

def _wf():
    return WF.read_text(encoding="utf-8")


def _job(name):
    """Text eines Jobs (zwei Leerzeichen eingerückt) bis zum nächsten Job."""
    m = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z][\w-]*:\n|\Z)", _wf().split("\njobs:\n", 1)[1], re.M | re.S)
    assert m, name
    return m.group(1)


def test_pages_yml_ausloeser_ohne_abruf_und_zeitplan():
    wf = _wf()
    kopf = wf.split("\njobs:\n")[0]
    code = "\n".join(z for z in wf.splitlines() if not z.lstrip().startswith("#"))
    assert re.search(r'^on:\n  push:\n    branches: \["main"\]\n  workflow_dispatch:\n\n', kopf, re.M)
    for wort in ("schedule", "cron", "pull_request", "workflow_run"):
        assert wort not in code, wort
    for wort in ("pipeline fetch", "python -m pipeline", "RATSATLAS_STADT_INFORMIERT", "RATSATLAS_MESSUNG"):
        assert wort not in code, wort
    assert not (ROOT / ".github" / "workflows" / "static.yml").exists()


def test_pages_yml_gepinnt_und_rechte_je_job():
    wf = _wf()
    uses = re.findall(r"uses:\s*(\S+)(.*)$", wf, re.M)
    assert uses
    for aktion, rest in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", aktion) and re.match(r"\s+# v\d", rest), aktion
    kopf = wf.split("\njobs:\n")[0]
    assert re.search(r"^permissions:\n  contents: read\n", kopf, re.M)
    bauen, deploy, pages = _job("bauen"), _job("deploy"), _job("pages")
    # nur main: workflow_dispatch lässt sich auf jedem Branch starten, deploy liefert sofort über Plesk aus
    for job in (bauen, deploy, pages):
        assert "    if: github.ref == 'refs/heads/main'\n" in job
    assert "contents: read" in bauen and "write" not in bauen
    assert "contents: write" in deploy and "pages: write" not in deploy and "id-token" not in deploy
    assert "pages: write" in pages and "id-token: write" in pages and "contents: write" not in pages
    assert "contents: write" not in kopf
    # deploy und pages hängen nur vom Bau ab, nicht voneinander (ein nicht eingerichtetes Pages verhindert deploy nicht)
    assert re.findall(r"^    needs: (.*)$", deploy, re.M) == ["bauen"] == re.findall(r"^    needs: (.*)$", pages, re.M)
    assert "needs:" not in bauen
    # Der Job mit Schreibrecht führt weder pip noch Code des Repositorys aus und checkt nichts aus
    for wort in ("pip", "python", "actions/checkout", "setup-python", "seite_bauen", "npm"):
        assert wort not in deploy, wort
    assert "actions/download-artifact@" in deploy and "name: seite" in deploy and "path: _site" in deploy
    # Checkout nie mit gespeicherter Anmeldung
    assert wf.count("actions/checkout@") == wf.count("persist-credentials: false") == 1
    assert "SITE_URL: ${{ vars.SITE_URL || 'https://wuppertal.ratsatlas.de/' }}" in bauen
    assert "python tools/seite_bauen.py _site" in bauen and "seite_bauen" not in pages
    assert "actions/upload-artifact@" in bauen and "include-hidden-files: true" in bauen and "path: _site" in bauen
    assert 'path: "_pages"' in bauen and "rm -f _pages/.htaccess" in bauen
    assert "environment:" in pages and "name: github-pages" in pages and "actions/deploy-pages@" in pages


def _deploy_schritt():
    m = re.search(r"- name: Fertige Seite in den Branch deploy schreiben \(ohne Historie\)\n.*?run: \|\n(.*?)(?=\n\n|\Z)",
                  _job("deploy"), re.S)
    assert m
    return "\n".join(z[10:] for z in m.group(1).splitlines())


def test_pages_yml_deploy_ohne_historie():
    schritt = _deploy_schritt()
    assert "git init -q -b deploy" in schritt and "--force" in schritt and "HEAD:deploy" in schritt
    assert "git clone" not in schritt and "--branch deploy" not in schritt
    assert "cp -r _site/. _deploy/" in schritt and "test -f _deploy/.htaccess" in schritt


@pytest.mark.skipif(not shutil.which("git") or not shutil.which("bash"), reason="git und bash nötig")
def test_deploy_schritt_lokal_genau_ein_commit(tmp_path, monkeypatch):
    """Den Shell-Schritt mit einem lokalen bare-Repository statt GitHub ausführen: nach zwei Läufen mit geänderter
    Seite hat deploy genau einen Commit, der Baum enthält nur die Seite; ein dritter Lauf ohne Änderung pusht nicht."""
    schritt = _deploy_schritt()
    assert schritt.startswith('url="https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"\n')
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    skript = f'url="{remote.as_uri()}"\n' + schritt.split("\n", 1)[1]
    arbeit = tmp_path / "arbeit"
    ziel = _bauen(arbeit, monkeypatch, tmp_path / "leer")
    assert ziel == arbeit / "_site"
    umgebung = {"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path), "GITHUB_SHA": "0123456789abcdef",
                "GIT_CONFIG_NOSYSTEM": "1"}

    def lauf():
        return subprocess.run(["bash", "-e", "-c", skript], cwd=arbeit, env=umgebung, capture_output=True, text=True,
                              check=True).stdout

    def git(*args):
        return subprocess.run(["git", "--git-dir", str(remote), *args], capture_output=True, text=True,
                              check=True).stdout.strip()

    lauf()
    erster = git("rev-parse", "deploy")
    (ziel / "robots.txt").write_text("User-agent: *\nAllow: /\n# geändert\n", encoding="utf-8")
    lauf()
    assert git("rev-parse", "deploy") != erster
    assert git("rev-list", "--count", "deploy") == "1"
    baum = git("ls-tree", "-r", "--name-only", "deploy").splitlines()
    assert sorted(baum) == _dateien(ziel)
    assert ".htaccess" in baum and "index.html" in baum
    zweiter = git("rev-parse", "deploy")
    assert "Seite unverändert" in lauf()
    assert git("rev-parse", "deploy") == zweiter
    # Nur version.txt neu (anderer Commit von main, Seite gleich): kein Push, deploy behält seine version.txt
    alt = git("show", "deploy:version.txt")
    (ziel / "version.txt").write_text("fedcba9876543210fedcba9876543210fedcba98\n", encoding="utf-8")
    assert "Seite unverändert" in lauf()
    assert git("rev-parse", "deploy") == zweiter and git("show", "deploy:version.txt") == alt
    # deploy ohne version.txt (Stand vor der Live-Prüfung): wird neu geschrieben, obwohl die Seite gleich ist
    (ziel / "version.txt").unlink()
    (ziel / "robots.txt").write_text("User-agent: *\nAllow: /\n# ohne version.txt\n", encoding="utf-8")
    lauf()
    ohne = git("rev-parse", "deploy")
    assert ohne != zweiter and "version.txt" not in git("ls-tree", "-r", "--name-only", "deploy").splitlines()
    (ziel / "version.txt").write_text(alt + "\n", encoding="utf-8")
    assert "Seite unverändert" not in lauf()
    assert git("rev-parse", "deploy") != ohne and git("show", "deploy:version.txt") == alt
