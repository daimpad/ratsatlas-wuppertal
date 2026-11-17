"""Leiste nach Bonn (ratsatlas-bonn #219, #221, #222), Wuppertaler Fassung (Entscheidung 17.11.2026): nur die Menüs
„Mitmachen“ und „Über“; keine Menüs „Themen“ und „Wer entscheidet“, keine alten Menüs und Schalter, keine Bonner
Verweise; Kennzahlen und Verfahrenswege von der Liste aus."""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "site" / "index.html").read_text(encoding="utf-8")


def test_zwei_menues():
    assert re.findall(r'class="menu-btn" data-mega="([^"]+)"', HTML) == ["mega-mitmachen", "mega-ueber"]
    for alt in ("mega-themen", "mega-entscheiden", "mega-auswertung", "mega-daten", "mega-verstehen",
                'data-panel="panel-detail"', 'data-panel="panel-prozesse"'):
        assert alt not in HTML, alt


def test_keine_bonner_verweise_in_leiste_und_menues():
    kopf = re.sub(r"<!--.*?-->", "", HTML[HTML.index("<header>"):HTML.index("</header>")], flags=re.S)   # ohne Kommentare
    assert "Bonn" not in kopf and "bonn.de" not in kopf and "ratsatlas-bonn/" not in kopf
    assert "teilen/" not in kopf                                   # „Bilder zum Teilen“ gibt es in Wuppertal nicht
    assert 'href="data/export/wuppertal/vorlagen.geojson"' in kopf
    assert "Aktuell in Wuppertal" in kopf


def test_kennzahlen_und_verfahrenswege_von_der_liste():
    liste = HTML[HTML.index('id="panel-list"'):HTML.index('id="papers"')]
    assert 'data-open-tab="stats"' in liste


def test_zusatzthemen_in_menues_geschaltet():
    for funktion in ("einfache_sprache", "technik", "mitmachen", "chat"):
        assert f'data-funktion="{funktion}" hidden' in HTML, funktion
