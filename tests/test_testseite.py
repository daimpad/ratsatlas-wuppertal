"""Erzeuger der Testseite für die Browser-Prüfung (tests/browser/testseite.py): läuft ohne Netz gegen den lokalen
OParl-Testserver, schreibt die Fassungen voll (mit Gesamtexport und Seiten) und leer (ohne data/), enthält nur erfundene
Testnamen und keine Namen aus Bonn oder Köln; die umgelenkten Pfade der Pipeline sind danach wiederhergestellt."""
import importlib.util
import json
import re
from pathlib import Path

from pipeline import abruf, config, net

ROOT = Path(__file__).resolve().parent.parent
FREMD = re.compile(r"Bonn|Köln|Koeln|Ehrenfeld|Venloer")


def _testseite():
    spec = importlib.util.spec_from_file_location("testseite", ROOT / "tests" / "browser" / "testseite.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_testseite_aus_erfundenen_daten(tmp_path):
    vorher = (config.EXPORT, config.OPARL_BODY, config.ORTSTEILE, abruf._OEFFNER, net._OEFFNER)
    voll, leer = _testseite().erzeugen(tmp_path, "http://127.0.0.1:8799/")
    assert (config.EXPORT, config.OPARL_BODY, config.ORTSTEILE, abruf._OEFFNER, net._OEFFNER) == vorher

    index = json.loads((voll / "data" / "export" / config.STADT / "index.json").read_text(encoding="utf-8"))
    assert sorted(o["name"] for o in index["ortsteile"]) == ["Testquartier A", "Testquartier B"]
    assert [b["name"] for b in index["bezirke"]] == ["Testbezirk 1"]
    for pfad in ("vorgang/1001-2026/index.html", "begriffe/index.html", "gebiete/index.html", "rss/index.html",
                 "ortsteil/testquartier-a/index.html", "stadtbezirk/testbezirk-1/index.html", "sitemap-vorgaenge.xml"):
        assert (voll / pfad).is_file(), pfad
    assert "http://127.0.0.1:8799/vorgang/1001-2026/" in (voll / "sitemap-vorgaenge.xml").read_text(encoding="utf-8")
    # nur erfundene Namen in allem, was die Pipeline erzeugt hat (site/ selbst nennt Bonn in Kommentaren)
    erzeugt = [p for p in voll.rglob("*") if p.is_file() and p.suffix in (".json", ".html", ".xml", ".geojson", ".tsv")
               and not (ROOT / "site" / p.relative_to(voll)).exists()]
    assert len(erzeugt) > 20
    assert [p.relative_to(voll).as_posix() for p in erzeugt if FREMD.search(p.read_text(encoding="utf-8"))] == []
    # leer: nur site/, ohne Gesamtexport
    assert (leer / "index.html").is_file() and not (leer / "data").exists()
