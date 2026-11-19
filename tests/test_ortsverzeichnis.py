"""pipeline/ortsverzeichnis.py (Phase 3): Dateien schreiben und lesen, Verortung über ortsnamen und die Ortsliste,
Hauskoordinate nur mit Erlaubnis, Gesellschaften der Ortsliste nicht verortet. Nur erfundene Daten, ohne Netz."""
import json

import pytest

from pipeline import build, config, ortsnamen, orte_kuratiert, ortsverzeichnis


def _rechteck(w, s, o, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [o, s], [o, n], [w, n], [w, s]]]}


@pytest.fixture
def geo(tmp_path, monkeypatch):
    q = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": _rechteck(0, 0, 0.01, 0.01),
         "properties": {"ortsteil": "11", "ortsteil_bez": "Testquartier A", "bezirk": "1", "bezirk_bez": "Testbezirk"}},
        {"type": "Feature", "geometry": _rechteck(0.01, 0, 0.02, 0.01),
         "properties": {"ortsteil": "12", "ortsteil_bez": "Testquartier B", "bezirk": "1", "bezirk_bez": "Testbezirk"}}]}
    b = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": _rechteck(0, 0, 0.02, 0.01), "properties": {"bezirk": "1", "bezirk_bez": "Testbezirk"}}]}
    for name, daten in (("ORTSTEILE", q), ("STADTBEZIRKE", b)):
        pfad = tmp_path / f"{name}.geojson"
        pfad.write_text(json.dumps(daten), encoding="utf-8")
        monkeypatch.setattr(config, name, pfad)
    monkeypatch.setattr(config, "STRASSEN", tmp_path / "strassen.json")
    monkeypatch.setattr(config, "HAUSNUMMERN", tmp_path / "hausnummern.json")
    adressen = [ortsnamen.Adresse("1", "Probestr.", str(n), None, 0.002 + n * 0.0005, 0.005, "Testbezirk")
                for n in range(1, 6)]
    flaechen = [ortsnamen.Flaeche(f["properties"]["ortsteil_bez"], "Testbezirk", f["geometry"]) for f in q["features"]]
    tabelle, index, befund = ortsnamen.strasse_quartier(adressen, flaechen)
    ortsverzeichnis.schreiben([ortsnamen.Strasse("Probestr.", "1", "Testbezirk")], tabelle, index, befund,
                              "2026-11-16")
    return tmp_path


def _ortsliste():
    return orte_kuratiert.Ortsliste([orte_kuratiert.Ort("Testhalle", (), "Veranstaltungsort", "flaeche",
                                                        ("Testquartier B",), ("Testbezirk",), "erfunden")])


def test_dateien_schreiben_und_lesen(geo):
    d = json.loads(config.STRASSEN.read_text(encoding="utf-8"))
    assert d["streets"] == ["Probestr."] and d["strassen"] == [["Probestr.", "1", "Testbezirk"]]
    assert d["meta"]["attribution"] == config.NAMENSNENNUNG and d["meta"]["retrieved_at"] == "2026-11-16"
    zeile = d["tabelle"]["s:1"][0]
    assert zeile[0] == "Testquartier A" and zeile[2] == 5
    h = json.loads(config.HAUSNUMMERN.read_text(encoding="utf-8"))
    assert len(h["adressen"]) == 5 and "Adressindex" in h["meta"]["hinweis"]


def test_strasse_quartier_und_hauskoordinate_nur_mit_erlaubnis(geo):
    w = ortsverzeichnis.Wuppertal(_ortsliste())
    assert w.streets and "Testbezirk" in w.bezirk_point and w.ot_by_name["Testquartier A"]["ortsteil"] == "11"
    ohne = w.locate("Parkplätze Probestraße 3", punkt_erlaubt=False)
    assert [(r["level"], r["ortsteil"], r["method"]) for r in ohne] == [("strasse", "Testquartier A", "strasse+hausnummer")]
    mit = w.locate("Parkplätze Probestraße 3", punkt_erlaubt=True)
    assert [(r["level"], r["method"], r["confidence"]) for r in mit] == [("adresse", "strasse+hausnummer_punkt", "hoch")]
    assert "3" not in mit[0]["evidence"]                      # Fundstelle ohne Hausnummer
    # eigener Ortsschlüssel je Hauspunkt, Name ohne Nummer
    orte = {}
    loc = build._add_location(mit[0], orte, w)
    assert loc.startswith("adresse:Probestr.|") and orte[loc][1] == "Probestr."


def test_ortsliste_und_gesellschaften(geo):
    w = ortsverzeichnis.Wuppertal(_ortsliste())
    rows = w.locate("Neue Stühle für die Testhalle")
    assert [(r["level"], r["name"], r["ortsteil"], r["method"]) for r in rows] == [
        ("objekt", "Testhalle", "Testquartier B", "ortsliste")]
    for titel in ("Jahresabschluss der Testhalle Wuppertal GmbH", "Aufsichtsrat Testhalle gGmbH",
                  "Trägerverein der Testhalle e.V.", "Testhalle Wuppertal Service GmbH"):
        assert w.locate(titel) == [], titel
    # ohne Straßen (Volltext mit street_re=False): Gebiete und Objekte bleiben
    assert [r["level"] for r in w.locate("Testquartier A und Probestraße 3", street_re=False)] == ["ortsteil"]


def test_ohne_dateien_leer(tmp_path, monkeypatch, geo):
    monkeypatch.setattr(config, "STRASSEN", tmp_path / "fehlt.json")
    monkeypatch.setattr(config, "HAUSNUMMERN", tmp_path / "fehlt2.json")
    w = ortsverzeichnis.Wuppertal(_ortsliste())
    assert w.streets == [] and w.locate("Probestraße 3") == []


def test_randquartiere_und_linienobjekte(geo):
    q = ortsnamen.StrasseQuartier
    tab = {"s:1": [q("A", "B", 40, 0.9, 0, 0), q("B", "B", 2, 0.05, 0, 0), q("C", "B", 3, 0.04, 0, 0),
                   q("D", "B", 5, 0.1, 0, 0)],
           "s:2": [q("A", "B", 1, 0.5, 0, 0), q("B", "B", 1, 0.5, 0, 0)]}
    aus = ortsverzeichnis.randquartiere_weg(tab)
    assert [z.quartier for z in aus["s:1"]] == ["A", "D"] and [z.quartier for z in aus["s:2"]] == ["A"]
    trasse = orte_kuratiert.Ort("Testtrasse", (), "Bahntrassenradweg", "linie", ("Testquartier A", "Testquartier B"),
                                ("Testbezirk", "Testbezirk"), "erfunden")
    w = ortsverzeichnis.Wuppertal(orte_kuratiert.Ortsliste([trasse]))
    assert {r["ortsteil"] for r in w.locate("Ausbau der Testtrasse")} == {"Testquartier A", "Testquartier B"}
    # mit genauerem Ort (Straße) im selben Titel: Abschnitt gemeint, die Trasse wird nicht verteilt
    rows = w.locate("Zugang zur Testtrasse an der Probestraße")
    assert [r["level"] for r in rows] == ["strasse"]


def test_regeln_der_handpruefung_19_11(geo):
    """Handprüfung 19.11.2026: Objektnamen verdecken Gebietsnamen, Straßen im Objektnamen bleiben im Quartier des
    Objekts, Kurzformen mit Ergänzungsstrich, „GS“ für Grundschulen."""
    halle = orte_kuratiert.Ort("Testhalle Testbezirk", (), "Veranstaltungsort", "punkt", ("Testquartier B",),
                               ("Testbezirk",), "erfunden")
    schule = orte_kuratiert.Ort("Grundschule Probestraße", (), "Schule", "punkt", ("Testquartier B",),
                                ("Testbezirk",), "erfunden")
    w = ortsverzeichnis.Wuppertal(orte_kuratiert.Ortsliste([halle, schule]))
    # „Testbezirk“ im Objektnamen ergibt keinen eigenen Stadtbezirk
    assert [(r["level"], r["name"]) for r in w.locate("Neukonzeption Testhalle Testbezirk")] == [
        ("objekt", "Testhalle Testbezirk")]
    # Die Probestraße liegt nur in Quartier A, die Schule laut Ortsliste in B: keine Straßenzeile, das Objekt bleibt;
    # „GS“ als Kurzform der Grundschule
    rows = w.locate("Zuschuss GS Probestr.")
    assert [(r["level"], r["ortsteil"]) for r in rows] == [("objekt", "Testquartier B")]
    # Kurzform mit Ergänzungsstrich
    assert [r["name"] for r in w.locate("Begleitmaßnahmen in der Probe- und Musterstraße")] == ["Probestr."]
