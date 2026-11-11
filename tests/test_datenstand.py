"""Ausgefallener Abruf (CLAUDE.md 5.1): Die Pipeline liefert den letzten gültigen Datenstand aus und meldet ihn der Seite
(index.json meta: `abruf_fehler`, `abruf_ok`); site/app.js zeigt daraus den Hinweis (tests/browser/vorgang.test.mjs).
Gegen den lokalen OParl-Testserver, ohne Anfragen an Server der Stadt."""
import json
from datetime import datetime, timedelta

import pytest

from pipeline import aenderungen, build, config, export, sessionnet


def _index():
    return json.loads((config.EXPORT / config.STADT / "index.json").read_text(encoding="utf-8"))


def _vorlagen():
    """Drucksachen in den Gebietsdateien (Quartiere, Stadtbezirke, ohne Ortsbezug)."""
    refs = set()
    for ordner in ("ortsteile", "bezirke", "ohne-ortsbezug"):
        for datei in (config.EXPORT / config.STADT / ordner).glob("*.json"):
            refs |= {p["reference"] for p in json.loads(datei.read_text(encoding="utf-8"))["papers"]}
    return refs


def _spaeter(zeit):
    return (datetime.fromisoformat(zeit) + timedelta(hours=1)).isoformat(timespec="seconds")


def _lauf():
    """Wie `python3 -m pipeline all` und danach export (täglicher Lauf, Phase 5)."""
    sessionnet.fetch_all()
    aenderungen.protokollieren()
    build.build()
    export.export()


def test_ausgefallener_abruf_liefert_letzten_stand_und_meldet_ihn(oparl, monkeypatch):
    _lauf()
    meta = _index()["meta"]
    ok = meta["abruf_ok"]
    assert ok and meta["abruf_fehler"] is None
    vorlagen, rohdaten = _vorlagen(), config.PAPERS.read_bytes()
    assert len(vorlagen) == 5

    # Abruf fällt aus (HTTP 404 auf der Vorlagenliste): letzter gültiger Stand bleibt und wird als solcher gemeldet.
    # Fehler eine Stunde nach dem letzten vollständigen Abruf (im Test sonst in derselben Sekunde; export zeigt nur
    # Fehler, die nach abruf_ok liegen)
    with monkeypatch.context() as m:
        m.setattr(oparl, "stoerung", lambda pfad, q: pfad == "/papers")
        m.setattr(sessionnet, "_now", lambda: _spaeter(ok))
        _lauf()
    assert config.PAPERS.read_bytes() == rohdaten
    meta = _index()["meta"]
    assert meta["abruf_ok"] == ok
    assert "HTTP 404" in meta["abruf_fehler"]["meldung"]
    assert datetime.fromisoformat(meta["abruf_fehler"]["zeit"]) >= datetime.fromisoformat(ok)
    assert _vorlagen() == vorlagen
    assert aenderungen.unterlagen_geaendert() == {}      # ein ausgefallener Lauf erzeugt keine Änderung

    # nächster vollständiger Abruf: Hinweis entfällt, neuer Zeitpunkt
    _lauf()
    meta = _index()["meta"]
    assert meta["abruf_fehler"] is None and meta["abruf_ok"] >= ok
    assert "abruf_fehler" not in json.loads(config.STAND.read_text())


def test_abbruch_nach_den_vorlagen_meldet_teilstand(oparl, monkeypatch):
    """Abruf bricht erst bei den Sitzungen ab: papers.jsonl ist dann schon neu (Kölner Ablauf in sessionnet.fetch_all),
    die neue Vorlage steht ohne ihre Beratungen im Export. index.json meldet das als Teilstand (`abruf_teilweise`),
    damit die Seite nicht „letzter gültiger Datenstand vom …“ behauptet; ein Fehler auf /papers ist kein Teilstand."""
    _lauf()
    ok = _index()["meta"]["abruf_ok"]
    assert _index()["meta"]["abruf_teilweise"] is False
    zeit = json.loads(config.ZUSTAND.read_text(encoding="utf-8"))["papers"]
    oparl.papers.append(oparl.paper(6, name="Neu im abgebrochenen Lauf", modified=zeit))
    with monkeypatch.context() as m:
        m.setattr(oparl, "stoerung", lambda pfad, q: pfad == "/meetings")
        m.setattr(sessionnet, "_now", lambda: _spaeter(ok))
        _lauf()
    meta = _index()["meta"]
    assert meta["abruf_ok"] == ok and "HTTP 404" in meta["abruf_fehler"]["meldung"]
    assert meta["abruf_teilweise"] is True
    assert "AN/106/2026" in _vorlagen()     # neu geholte Vorlage im Export, ohne Beratungen
    assert "consultations/6" not in config.BERATUNGEN.read_text(encoding="utf-8")
    # nächster vollständiger Lauf (nächste Nacht): kein Fehler, kein Teilstand
    zustand = json.loads(config.ZUSTAND.read_text(encoding="utf-8"))
    zustand.pop("letzter_abbruch", None)
    config.ZUSTAND.write_text(json.dumps(zustand), encoding="utf-8")
    _lauf()
    meta = _index()["meta"]
    assert meta["abruf_fehler"] is None and meta["abruf_teilweise"] is False
    assert "consultations/6" in config.BERATUNGEN.read_text(encoding="utf-8")


def test_abruf_teilweise_regeln():
    f = {"zeit": "2026-11-12T23:30:00+00:00", "meldung": "x"}
    ok = "2026-11-10T23:10:00+00:00"
    spaeter = "2026-11-12T23:20:00+00:00"
    assert export._abruf_teilweise({"abruf_fehler": f, "abruf_ok": ok, "papers": spaeter}) is True
    assert export._abruf_teilweise({"abruf_fehler": f, "abruf_ok": ok, "meetings": spaeter}) is True
    # nur die Gremienliste neu, Vorlagen vom letzten vollständigen Abruf: kein Teilstand
    assert export._abruf_teilweise({"abruf_fehler": f, "abruf_ok": ok, "organizations": spaeter, "papers": ok}) is False
    # ohne gezeigten Fehler (älter als abruf_ok) nie
    assert export._abruf_teilweise({"abruf_fehler": {"zeit": "2026-11-01T00:00:00+00:00"}, "abruf_ok": ok,
                                    "papers": spaeter}) is False
    # ohne abruf_ok: jede geschriebene Liste; unlesbarer Zeitpunkt: Teilstand
    assert export._abruf_teilweise({"abruf_fehler": f, "papers": spaeter}) is True
    assert export._abruf_teilweise({"abruf_fehler": f, "abruf_ok": ok, "papers": "kaputt"}) is True
    assert export._abruf_teilweise({"abruf_fehler": f}) is False


def test_programmfehler_vermerkt_und_export_behaelt_daten(oparl, monkeypatch):
    """Programmfehler im Abruf: laut (Ausnahme, Workflow rot) und in STAND.json; ein danach gebauter Export behält die
    Vorlagen und meldet den Fehler. Ohne neuen Export bleibt die alte Seite online; den Hinweis zeigt dann nur die
    Prüfung des Alters im Browser (app.js, STAND_VERALTET_TAGE)."""
    _lauf()
    vorlagen = _vorlagen()

    def kaputt(*a, **k):
        raise KeyError("unerwartete Form")
    monkeypatch.setattr(sessionnet, "beratungen", kaputt)
    monkeypatch.setattr(sessionnet, "_now", lambda: _spaeter(_index()["meta"]["abruf_ok"]))
    with pytest.raises(KeyError):
        sessionnet.fetch_all()
    assert "Programmfehler" in json.loads(config.STAND.read_text())["abruf_fehler"]["meldung"]
    aenderungen.protokollieren()
    build.build()
    export.export()
    assert _vorlagen() == vorlagen
    assert "Programmfehler" in _index()["meta"]["abruf_fehler"]["meldung"]


def test_uebersprungener_abruf_ohne_fehler(oparl, monkeypatch):
    """Gesperrter oder übersprungener Abruf ist kein Ausfall: kein abruf_fehler, abruf_ok bleibt (die Seite meldet erst
    nach STAND_VERALTET_TAGE Tagen „nicht aktualisiert“)."""
    _lauf()
    ok = _index()["meta"]["abruf_ok"]
    monkeypatch.setattr(sessionnet.abruf, "freigegeben", lambda url: False)
    _lauf()
    meta = _index()["meta"]
    assert meta["abruf_fehler"] is None and meta["abruf_ok"] == ok
    assert "nicht informiert" in json.loads(config.STAND.read_text())["abruf_uebersprungen"]["grund"]


def test_app_js_zeigt_datenstand_als_hinweis():
    """Hinweis außerhalb der eingeklappten Quellen (Los geht's, Vorgang) und in #stand; Berliner Tag (zeitTag nach
    ratsatlas-koeln origin/main @90928bc); Schwelle für veraltete Daten."""
    from pathlib import Path
    app = (Path(__file__).resolve().parents[1] / "site" / "app.js").read_text(encoding="utf-8")
    assert "index.meta.abruf_ok" in app or "im.abruf_ok" in app
    assert "const STAND_VERALTET_TAGE = 3;" in app
    assert "ist fehlgeschlagen; gezeigt wird der letzte gültige Datenstand" in app
    assert "seit dem ${zeitDatum(ok)} nicht aktualisiert" in app
    assert "im.abruf_teilweise" in app and "teilweise aktualisierter Datenstand" in app
