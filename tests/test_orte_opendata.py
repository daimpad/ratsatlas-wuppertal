"""Open-Data-Orte für die Ortsliste (explore/orte_opendata.py, Freigabe 16.11.2026). Nur erfundene Geodaten; ohne Netz."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "explore"))
import orte_opendata as od  # noqa: E402
from pipeline import orte_kuratiert as ok  # noqa: E402


def _quadrat(x0, y0, x1, y1):
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


def _fc(features):
    return {"type": "FeatureCollection", "features": features}


def _f(geom, **props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def _pt(x, y):
    return {"type": "Point", "coordinates": [x, y]}


@pytest.fixture
def daten(tmp_path):
    d = tmp_path / "opendata"
    d.mkdir()
    dateien = {
        "quartiere": _fc([_f(_quadrat(0, 0, 1, 1), NAME="Quartier West"), _f(_quadrat(1, 0, 2, 1), NAME="Quartier Ost")]),
        "stadtbezirke": _fc([_f(_quadrat(0, 0, 2, 1), NAME="Bezirk Mitte")]),
        "schwebebahn": _fc([_f(_pt(0.5, 0.5), NAME="Testbrücke")]),
        "zugaenge_punkte": _fc([_f(_pt(0.2, 0.2), NAME="Probestraße", TYP="Treppe", TRASSE="Testtrasse"),
                                _f(_pt(1.5, 0.5), NAME="Musterweg", TYP="Fußweg", TRASSE="Testtrasse")]),
        "zugaenge_wege": _fc([_f({"type": "LineString", "coordinates": [[0.1, 0.1], [0.3, 0.3]]}, NAME="Probeweg",
                                 TRASSE="Testtrasse")]),
        "schulen": _fc([_f(_pt(0.5, 0.5), Name="Gemeinschaftsgrundschule Probestraße", Telefon="0000", Mail="x@y.z"),
                        _f(_pt(1.5, 0.5), Name="Grundschule"),
                        _f(_pt(1.4, 0.4), Name="Max-Muster-Gesamtschule Ostviertel")]),
        "spielplaetze": _fc([_f(_quadrat(1.2, 0.2, 1.4, 0.4), name="Musterplatz (KSP)", flaeche=1)]),
        "veranstaltung": _fc([_f(_pt(0.6, 0.6), HAUPTNAME="Testhalle / Probebühne Mitte", TELEFON="0000"),
                              _f(_pt(0.6, 0.6), HAUPTNAME="ort")]),
    }
    for k, inhalt in dateien.items():
        (d / od.DATEIEN[k]).write_text(json.dumps(inhalt), encoding="utf-8")
    sq = tmp_path / "strasse_quartier.tsv"
    sq.write_text("strassenname\tstrassenschluessel\tquartier\tadresspunkte\nDöppersberg\t1\tQuartier Ost\t3\n",
                  encoding="utf-8")
    return d, sq


def _nach_name(zeilen):
    return {z["name"]: z for z in zeilen}


def test_ableitung_regeln_und_quartiere(daten):
    d, sq = daten
    zeilen, zaehl = od.ableiten(d, sq)
    z = _nach_name(zeilen)
    st = z["Schwebebahnstation Testbrücke"]
    assert st["quartiere"] == "Quartier West" and "Station Testbrücke" in st["varianten"].split("|")
    assert "Testbrücke" not in st["varianten"].split("|")                      # Name allein trifft nicht
    tr = z["Testtrasse"]
    assert tr["verortung"] == "linie" and set(tr["quartiere"].split("|")) == {"Quartier West", "Quartier Ost"}
    assert tr["stadtbezirke"] == "Bezirk Mitte|Bezirk Mitte"
    assert "Probestraße" not in z and "Musterweg" not in z                    # Zugangsnamen sind Straßen
    assert z["Döppersberg"]["quartiere"] == "Quartier Ost"
    sch = z["Gemeinschaftsgrundschule Probestraße"]
    assert {"Grundschule Probestraße", "Grundschule Probestr."} <= set(sch["varianten"].split("|"))
    assert "Grundschule" not in z                                             # nur Schulform
    assert "Max-Muster-Gesamtschule" in z["Max-Muster-Gesamtschule Ostviertel"]["varianten"].split("|")
    sp = z["Spielplatz Musterplatz"]
    assert sp["quartiere"] == "Quartier Ost" and "Kinderspielplatzes Musterplatz" in sp["varianten"]
    v = z["Testhalle / Probebühne Mitte"]
    assert {"Testhalle", "Probebühne Mitte"} <= set(v["varianten"].split("|")) and "ort" not in z
    assert zaehl["veranstaltung_ausgeschlossen"] == 1 and zaehl["schulen_ohne_namen"] == 1


def test_keine_koordinaten_und_keine_kontaktfelder(daten, tmp_path):
    d, sq = daten
    zeilen, _ = od.ableiten(d, sq)
    aus = tmp_path / "orte.tsv"
    od.schreibe_tsv(aus, zeilen, od.SPALTEN)
    text = aus.read_text(encoding="utf-8")
    assert "0000" not in text and "x@y.z" not in text and "0.5" not in text
    assert all(z["beleg"] and "CC BY 4.0" in z["beleg"] for z in zeilen)


def test_ortsliste_mit_regeln(daten, tmp_path):
    d, sq = daten
    zeilen, _ = od.ableiten(d, sq)
    aus = tmp_path / "orte.tsv"
    od.schreibe_tsv(aus, zeilen, od.SPALTEN)
    liste = ok.Ortsliste(ok.laden(aus))
    assert [o.name for o, *_ in liste.treffer("Radabstellanlage Testbrücke")] == []
    assert [o.name for o, *_ in liste.treffer("Aufzug an der Schwebebahnstation Testbrücke")] == \
        ["Schwebebahnstation Testbrücke"]
    assert [o.name for o, *_ in liste.treffer("Sanierung des Kinderspielplatzes Musterplatz")] == \
        ["Spielplatz Musterplatz"]
    zeilen_v, _ = liste.verorte("Neubau der Grundschule Probestr. und Ausbau der Testtrasse")
    assert [(r["name"], r["ortsteil"], r["confidence"]) for r in zeilen_v] == [
        ("Gemeinschaftsgrundschule Probestraße", "Quartier West", "mittel"),
        ("Testtrasse", "Quartier West", "niedrig"), ("Testtrasse", "Quartier Ost", "niedrig")]


def test_zusammenfuehren_fuellt_nur_offene_quartiere():
    kur = [ok.Ort("Trasse", verortung="linie", beleg="kuratiert"),
           ok.Ort("Platz", verortung="punkt", quartiere=("A",), stadtbezirke=("X",), beleg="kuratiert")]
    abg = [ok.Ort("Trasse", verortung="linie", quartiere=("B", "C"), stadtbezirke=("Y", "Y"), beleg="opendata"),
           ok.Ort("Platz", verortung="punkt", quartiere=("Z",), beleg="opendata"),
           ok.Ort("Neu", verortung="punkt", quartiere=("D",), beleg="opendata")]
    out = {o.name: o for o in ok.zusammenfuehren(kur, abg)}
    assert out["Trasse"].quartiere == ("B", "C") and out["Trasse"].beleg == "kuratiert; Quartiere: opendata"
    assert out["Platz"].quartiere == ("A",) and out["Platz"].beleg == "kuratiert"
    assert list(out) == ["Trasse", "Platz", "Neu"]


def test_versionierte_tabelle_passt_zum_format():
    pfad = ROOT / "pipeline" / "orte_opendata.tsv"
    with open(pfad, encoding="utf-8") as f:
        zeilen = list(csv.DictReader(f, delimiter="\t"))
    assert list(zeilen[0]) == od.SPALTEN
    assert all(z["beleg"] and z["quartiere"] not in ("", ok.OFFEN) for z in zeilen)
    orte = ok.laden(pfad)                                   # Ort prüft Verortung und Beleg
    assert len(orte) == len(zeilen)
    assert not any("@" in z["beleg"] or "@" in z["varianten"] for z in zeilen)
