"""Impressum und Datenschutzerklärung (CLAUDE.md 9, 11.11.2026, Auswahl des Auftraggebers):

- Impressum: sichtbarer Link auf https://nozilla.de/impressum/ in der Fußzeile jeder ausgelieferten Seite, ohne und mit
  Daten (Karte, Datenschutz, 404, Begriffe, Feeds, Gebiets- und Vorgangsseiten). Auf der Karte ist die Quellenzeile
  von Leaflet die Fußzeile: app.js setzt den Link dort vorn ins Präfix (die Browser-Prüfung sieht nach, dass er
  sichtbar ist, tests/browser/seiten.test.mjs); alle anderen Seiten haben ein <footer> mit dem Link.
- Datenschutzerklärung, Abschnitt „Beim Aufruf der Seite“: keine unbelegte Liste von Protokollfeldern, keine Frist und
  keine Zusicherung für die Anbieter; was belegt ist (netcup GmbH in Karlsruhe laut Impressum von netcup, GitHub Pages
  mit EU-US Data Privacy Framework, Angemessenheitsbeschluss für das Vereinigte Königreich), Rechtsgrundlagen und der
  Satz zur bzw. zum Datenschutzbeauftragten bleiben.

Jede Prüffunktion hat eine Gegenprobe mit der Fassung vor der Änderung. Keine Anfragen an Server."""
import importlib.util
import re

import pytest

from pipeline import config

ROOT = config.ROOT
IMPRESSUM = "https://nozilla.de/impressum/"
FUSS = re.compile(r"<footer\b[^>]*>(.*?)</footer>", re.S)
LINK = re.compile(r'<a\s[^>]*href="https://nozilla\.de/impressum/"[^>]*>\s*Impressum\b')
PRAEFIX = re.compile(r"map\.attributionControl\.setPrefix\((.*?)\);\n", re.S)


def _modul(name, pfad):
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def fuss_mit_impressum(html):
    """Wahr, wenn ein <footer> der Seite den Link auf das Impressum mit dem Wort „Impressum“ enthält."""
    return any(LINK.search(f) for f in FUSS.findall(html))


def karte_mit_impressum(app_js):
    """Wahr, wenn app.js den Impressum-Link vorn ins Präfix der Quellenzeile setzt, auf Telefon und breitem Bildschirm."""
    konst = re.search(r"const IMPRESSUM_LINK = '([^']*)';", app_js)
    aufruf = PRAEFIX.search(app_js)
    if not konst or not LINK.search(konst.group(1)) or not aufruf:
        return False
    zweige = aufruf.group(1).split(" : ", 1)
    return len(zweige) == 2 and all("${IMPRESSUM_LINK}" in z for z in zweige)


def _bauen(tmp_path, monkeypatch, export):
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)
    monkeypatch.setattr(config, "EXPORT", export)
    monkeypatch.setattr(config, "SITE_URL", "https://wuppertal.ratsatlas.de/")
    ziel = tmp_path / "_site"
    _modul("seite_bauen", ROOT / "tools" / "seite_bauen.py").main(ziel)
    return ziel


@pytest.fixture(scope="module")
def testexport(tmp_path_factory):
    """Gesamtexport aus erfundenen Daten (tests/browser/testseite.py, lokaler Testserver): mit Vorgangs- und
    Gebietsseiten."""
    ordner = tmp_path_factory.mktemp("testseite")
    voll, _ = _modul("testseite", ROOT / "tests" / "browser" / "testseite.py").erzeugen(ordner, "http://127.0.0.1:8798/")
    return voll / "data" / "export"


OHNE_DATEN = {"index.html", "datenschutz.html", "404.html", "begriffe/index.html", "rss/index.html"}
MIT_DATEN = OHNE_DATEN | {"gebiete/index.html", "vorgang/1001-2026/index.html", "ortsteil/testquartier-a/index.html",
                          "stadtbezirk/testbezirk-1/index.html"}


@pytest.mark.parametrize("daten", [False, True])
def test_impressum_in_der_fusszeile_jeder_gebauten_seite(tmp_path, monkeypatch, testexport, daten):
    ziel = _bauen(tmp_path, monkeypatch, testexport if daten else tmp_path / "leer")
    seiten = {p.relative_to(ziel).as_posix(): p for p in ziel.rglob("*.html")}
    assert (MIT_DATEN if daten else OHNE_DATEN) <= set(seiten), sorted(seiten)
    ohne = [name for name, p in sorted(seiten.items())
            if name != "index.html" and not fuss_mit_impressum(p.read_text(encoding="utf-8"))]
    assert ohne == []
    # Karte: Fußzeile ist die Quellenzeile, gesetzt von app.js; ohne Skript zeigt der noscript-Block den Link
    assert karte_mit_impressum((ziel / "app.js").read_text(encoding="utf-8"))
    noscript = re.search(r"<noscript>(.*?)</noscript>", seiten["index.html"].read_text(encoding="utf-8"), re.S).group(1)
    assert LINK.search(noscript)


def test_gegenprobe_impressum_pruefung():
    # 404-Seite vor der Änderung: Link im Text der Karte, aber in keinem <footer>
    alt_404 = ('<main><h1>Diese Seite gibt es nicht</h1><p><small><a href="https://nozilla.de/impressum/">Impressum</a> · '
               '<a href="datenschutz.html">Datenschutz</a></small></p></main>')
    assert not fuss_mit_impressum(alt_404)
    assert not fuss_mit_impressum('<footer class="page-foot"><a href="datenschutz.html">Datenschutz</a></footer>')
    assert not fuss_mit_impressum('<footer><a href="https://nozilla.de/">Impressum</a></footer>')
    assert fuss_mit_impressum(alt_404.replace("<p><small>", "<footer><small>").replace("</small></p>", "</small></footer>"))
    # app.js vor der Änderung: Präfix ohne Impressum (nur ⓘ bzw. Leaflet)
    alt_js = ("""  const IMPRESSUM_LINK = '<a href="https://nozilla.de/impressum/">Impressum</a>';\n"""
              """    map.attributionControl.setPrefix(mobil ? '<a href="#sources" class="attr-info">ⓘ</a>'\n"""
              """      : L.Control.Attribution.prototype.options.prefix);\n""")
    assert not karte_mit_impressum(alt_js)
    nur_breit = alt_js.replace("L.Control.Attribution", "`${IMPRESSUM_LINK}` + L.Control.Attribution")
    assert not karte_mit_impressum(nur_breit)
    assert karte_mit_impressum((ROOT / "site" / "app.js").read_text(encoding="utf-8"))


# Abschnitt „Beim Aufruf der Seite“: Wörter der früheren, unbelegten Feldliste, Fristen, Zusicherung für die Anbieter
FELDLISTE = ("Browsertyp", "Betriebssystem", "verweisende Seite", "übertragene Datenmenge", "Meldung über den Erfolg",
             "Datum und Uhrzeit", "abgerufene Adresse")
FRIST = re.compile(r"\b\d+\s*(?:Stunden|Tage|Tagen|Wochen|Monate|Monaten|Jahre|Jahren)\b|eingestellten Frist")
ZUSICHERUNG = re.compile(r"Die Protokolle werden nicht")


def aufruf_abschnitt(html):
    m = re.search(r"<h2>Beim Aufruf der Seite</h2>(.*?)<h2>", html, re.S)
    return m.group(1) if m else ""


def unbelegt(html):
    """Unbelegte Angaben im Abschnitt zum Aufruf der Seite: Protokollfelder, Fristen, Zusicherung für die Anbieter."""
    teil = aufruf_abschnitt(html)
    funde = [w for w in FELDLISTE if w in teil]
    funde += [m.group(0) for m in FRIST.finditer(teil)]
    funde += ["Wie jeder Webserver"] if "Wie jeder Webserver" in teil else []
    funde += [m.group(0) for m in ZUSICHERUNG.finditer(teil)]
    return funde


def test_datenschutz_ohne_unbelegte_feldliste_und_frist():
    html = (ROOT / "site" / "datenschutz.html").read_text(encoding="utf-8")
    teil = aufruf_abschnitt(html)
    assert teil and unbelegt(html) == []
    # Belegtes bleibt (Recherche 11.11.2026: Impressum von netcup, DPF-Verzeichnis, GitHub Docs, EU-Kommission)
    for satz in ("netcup GmbH (Karlsruhe)", "GitHub Pages", "darunter Ihre IP-Adresse",
                 "GitHub ist nach dem EU-US Data Privacy Framework zertifiziert (Art. 45 DSGVO)",
                 "Art. 6 Abs. 1 lit. f DSGVO", "Ich führe diese Daten nicht mit anderen Daten zusammen"):
        assert satz in teil, satz
    assert ("Für das Vereinigte Königreich besteht ein Angemessenheitsbeschluss der EU-Kommission (Art. 45 DSGVO)."
            in html)
    assert "Eine Datenschutzbeauftragte oder einen Datenschutzbeauftragten gibt es nicht" in html
    # keine weitere E-Mail-Adresse als der Kontakt des Projekts, keine Straßenanschrift von netcup
    assert set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", html)) == {"contact@nozilla.de"}
    assert "Emmy-Noether" not in html and "76131" not in html
    assert re.search(r'<p class="meta">Stand: \d{1,2}\. \w+ \d{4}</p>', html)


def test_gegenprobe_unbelegte_angaben():
    alt = ("<h2>Beim Aufruf der Seite</h2><p>Wie jeder Webserver führen beide ein Zugriffsprotokoll: abgerufene Adresse, "
           "Datum und Uhrzeit, übertragene Datenmenge, Meldung über den Erfolg des Abrufs, verweisende Seite, Browsertyp "
           "und Betriebssystem sowie die IP-Adresse.</p><p>Die Protokolle werden nicht mit anderen Daten zusammengeführt "
           "und nicht ausgewertet, um Personen wiederzuerkennen; sie werden nach der beim jeweiligen Anbieter "
           "eingestellten Frist gelöscht.</p><h2>Kartenkacheln</h2>")
    funde = unbelegt(alt)
    for erwartet in ("Browsertyp", "verweisende Seite", "eingestellten Frist", "Wie jeder Webserver",
                     "Die Protokolle werden nicht"):
        assert erwartet in funde, (erwartet, funde)
    assert unbelegt(alt.replace("eingestellten Frist gelöscht", "nach 14 Tagen gelöscht"))
    assert "14 Tagen" in unbelegt("<h2>Beim Aufruf der Seite</h2><p>gelöscht nach 14 Tagen</p><h2>")
    # Fristen und Feldwörter außerhalb des Abschnitts zählen nicht (z. B. Kartenkacheln: „Angaben zu Browser“)
    assert unbelegt("<h2>Kartenkacheln</h2><p>Browsertyp, 7 Tage</p><h2>") == []
