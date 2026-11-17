"""pipeline/haushalt_wuppertal.py: Zeilen der Ergebnispläne und der bezirksbezogenen Ansätze lesen, Prüfsummen mit
Rundung, und die ausgelesenen Dateien in data/haushalt (Haushaltsplan 2026/2027, Band 1). Ohne Netz; die Parser-Tests
mit erfundenen Zeilen."""
import csv
import hashlib
import json

from pipeline import config
from pipeline import haushalt_wuppertal as h

ZIEL = config.ROOT / "data" / "haushalt"


def test_ergebniszeilen_mit_umbruch_und_vorzeichen():
    text = """      10     =   Ordentliche Erträge   1.000   2.000   3.000   4.000   5.000   6.000   7.000   8.000
                 Testaufwendungen für Sach- und
      13     -                                   -100   -200   -300   -400   -500   -600   -700   -800
                 Dienstleistungen
      18   =  Ordentliches Ergebnis (= Zeilen 10 und     900   1.800   2.700   3.600   4.500   5.400   6.300   7.200"""
    z = h.ergebniszeilen(text)
    assert z["10"] == ("Ordentliche Erträge", [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000])
    assert z["13"][1] == [-100, -200, -300, -400, -500, -600, -700, -800]
    assert z["18"][1][0] == 900


def test_bezirkszeilen_fallgruppe_und_bezirk_ueber_zeilen():
    text = """     1.    Bezirksvertretung Testbezirk
      1)    Unterhaltung des Infrastrukturver.       2_Bezirksvertretung Testbezirk      -1.000    -1.000    -1.000    -1.000    -1.000
            Verfügungsmittel Bezirksvertretungen     2_Bezirksvertretung Testbezirk        -500      -500      -500      -500      -500
      3)    Tiefbaumaßnahmen                         Probestraße                                0   -20.000         0         0         0
            ungelesene Zeile mit Betrag 1.234"""
    zeilen, bezirk, fg, ungelesen = h.bezirkszeilen(text)
    assert bezirk == "Testbezirk" and fg == "3"
    assert [(z["fallgruppe"], z["erlaeuterung"]) for z in zeilen] == [
        ("1", "2_Bezirksvertretung Testbezirk"), ("1", "2_Bezirksvertretung Testbezirk"), ("3", "Probestraße")]
    assert zeilen[2]["betraege"] == [0, -20000, 0, 0, 0]
    assert ungelesen == []   # eine Zahl allein ist keine Tabellenzeile
    # Fortsetzung auf der nächsten Seite: Bezirk und Fallgruppe gelten weiter
    z2, *_ = h.bezirkszeilen("   Tiefbaumaßnahmen    Testweg    -1   -2   -3   -4   -5", bezirk, fg)
    assert z2[0]["bezirk"] == "Testbezirk" and z2[0]["fallgruppe"] == "3"


def _pb(werte10, werte17, werte18):
    zeilen = {str(i): ("x", [0] * 8, 1) for i in range(1, 19)}
    zeilen["1"] = ("x", werte10, 1)
    zeilen["10"] = ("x", werte10, 1)
    zeilen["11"] = ("x", werte17, 1)
    zeilen["17"] = ("x", werte17, 1)
    zeilen["18"] = ("x", werte18, 1)
    return {"name": "Test", "zeilen": zeilen}


def test_pruefen_rundung_und_abweichung():
    pb = {"11": _pb([100] * 8, [-60] * 8, [40] * 8), "12": _pb([50] * 8, [-20] * 8, [31] * 8)}   # 30 + 1 Rundung
    gesamt = {"10": ("x", [150] * 8, 1), "17": ("x", [-80] * 8, 1), "18": ("x", [72] * 8, 1)}   # 71 + 1
    assert h.pruefen(gesamt, pb) == []
    pb["12"]["zeilen"]["18"] = ("x", [40] * 8, 1)    # 10 Euro daneben
    fehler = h.pruefen(gesamt, pb)
    assert any("PB 12: 10 + 17 = 18" in f[0] for f in fehler)
    assert any("Gesamtergebnisplan, Zeile 18" in f[0] for f in fehler)


def _tsv(name):
    return list(csv.DictReader(open(ZIEL / name, encoding="utf-8"), delimiter="\t"))


def test_ausgelesene_dateien():
    stand = json.loads((ZIEL / "STAND.json").read_text(encoding="utf-8"))
    assert stand["produktbereiche"] == 17 and stand["bezirksvertretungen"] == 10 and stand["bezirkszeilen"] == 292
    pdf = config.ROOT / stand["quelle"]
    if pdf.exists():
        assert hashlib.sha256(pdf.read_bytes()).hexdigest() == stand["sha256"]
    pb = _tsv("produktbereiche.tsv")
    assert len({r["produktbereich"] for r in pb}) == 18           # 17 Produktbereiche und Gesamt
    wert = {(r["produktbereich"], r["zeile"], r["spalte"]): int(r["betrag_eur"]) for r in pb}
    for sp in h.SPALTEN:                                             # Summe der Produktbereiche = Gesamt (Rundung)
        for z in ("10", "17", "18"):
            s = sum(v for (k, zz, s_), v in wert.items() if k != "Gesamt" and zz == z and s_ == sp)
            assert abs(s - wert[("Gesamt", z, sp)]) <= h.RUNDUNG, (z, sp)
    assert wert[("Gesamt", "18", "Ansatz 2026")] == -90780578          # Band 1, S. 96
    bz = _tsv("bezirke.tsv")
    assert len(bz) == 292 * 5 and len({r["bezirksvertretung"] for r in bz}) == 10
    assert {r["fallgruppe"] for r in bz} == {"1", "2", "3"}
    # keine Personennamen: Spalten nur Bezirk, Fallgruppe, Art, Erläuterung, Spalte, Betrag, Fundstelle
    assert list(bz[0]) == ["bezirksvertretung", "fallgruppe", "art", "erlaeuterung", "spalte", "betrag_eur", "datei",
                           "seite"]
