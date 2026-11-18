"""Block „Aktuell in Wuppertal“ im Startfenster (export._aktuell, aus allris-test @730d593, #221): Auswahl und Reihenfolge der
Sitzungen und Vorlagen. Erfundene Werte."""
from pipeline import export


def sitzung(datum, zeit="18:00", gremium="Rat", abgesagt=False):
    return {"date": datum, "time": zeit, "gremium": gremium, "web": "https://example.org/to", "cancelled": abgesagt,
            "source_object": f"m-{datum}-{gremium}"}


def test_sitzungen_ab_heute_ohne_abgesagte():
    ms = [sitzung("2026-11-10"), sitzung("2026-11-17", "18:00", "B"), sitzung("2026-11-17", "17:00", "A"),
          sitzung("2026-11-18", abgesagt=True), sitzung("2026-11-19")]
    a = export._aktuell({}, {}, {}, ms, "2026-11-17")
    assert [m["gremium"] for m in a["sitzungen"]] == ["A", "B", "Rat"]
    assert a["sitzungen"][0]["frist"] is None   # Bonner Antragsfrist (21 Tage) für Wuppertal nicht belegt


def test_vorlagen_nach_datum_mit_ort():
    cache = {1: {"reference": "VO/0001/26", "date": "2026-11-15", "paper_type": "Antrag", "name": "A"},
             2: {"reference": "VO/0003/26", "date": "2026-11-16", "paper_type": "Anfrage", "name": "B", "seite": True},
             3: {"reference": "VO/0004/26", "date": "2026-12-01", "paper_type": "Antrag", "name": "zukünftig"},
             4: {"reference": "VO/0002/26", "date": "2026-11-16", "paper_type": None, "name": "C"}}
    home = {1: "ortsteil:testquartier-a", 2: "ohne:2026", 4: "bezirk:testbezirk-1"}
    names = {"ortsteil:testquartier-a": "Testquartier A", "ohne:2026": "stadtweit / ohne Ortsbezug 2026",
             "bezirk:testbezirk-1": "Stadtbezirk Testbezirk 1, ohne genaueren Ort"}
    v = export._aktuell(cache, home, names, [], "2026-11-17")["vorlagen"]
    assert [x["reference"] for x in v] == ["VO/0003/26", "VO/0002/26", "VO/0001/26"]
    assert [x["ort"] for x in v] == ["stadtweit / ohne Ortsbezug", "Stadtbezirk Testbezirk 1", "Testquartier A"]
    assert v[0]["seite"] is True
