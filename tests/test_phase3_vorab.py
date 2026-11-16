"""Phase 3 vorab (Freigabe 16.11.2026): kuratierte Ortsliste (pipeline/orte_kuratiert.py) und Datenschutzregel für
Hauskoordinaten (maske.hausnummer_punkt_erlaubt, maske.AMT_PRIVAT). Nur erfundene Texte; keine Anfrage."""
import pytest

from pipeline import maske, orte_kuratiert as ok


def test_echte_liste_lesbar_und_belegt():
    orte = ok.laden()
    namen = {o.name for o in orte}
    assert {"Schwebebahn", "Nordbahntrasse", "Döppersberg"} <= namen
    assert all(o.beleg for o in orte)
    assert all(not o.quartiere for o in orte)        # Geometrie bis nach Stufe G offen, nichts geschätzt


def test_abgleich_laengster_zuerst_und_zusammensetzungen():
    liste = ok.Ortsliste([ok.Ort("Schwebebahn", ("Wuppertaler Schwebebahn",), verortung="stadtweit", beleg="Test"),
                          ok.Ort("Testplatz", verortung="punkt", quartiere=("Quartier A",), stadtbezirke=("Bezirk 1",),
                                 beleg="Test")])
    t = liste.treffer("Sanierung der Wuppertaler Schwebebahn und der Schwebebahnstation am Testplatz")
    assert [(o.name, f) for o, f, *_ in t] == [("Schwebebahn", "Wuppertaler Schwebebahn"),
                                               ("Schwebebahn", "Schwebebahn"), ("Testplatz", "Testplatz")]
    assert liste.treffer("Unterschwebebahnen") == []    # kein Buchstabe vor dem Namen


def test_verortung_stadtweit_offen_und_linie():
    liste = ok.Ortsliste([
        ok.Ort("Schwebebahn", verortung="stadtweit", beleg="Test"),
        ok.Ort("Testtrasse", verortung="linie", quartiere=("A", "B"), stadtbezirke=("X", "Y"), beleg="Test"),
        ok.Ort("Testplatz", verortung="flaeche", beleg="Test")])
    zeilen, vermerke = liste.verorte("Schwebebahn, Testtrasse und Testplatz", source_object="http://o/p/1")
    assert [(z["ortsteil"], z["bezirk"], z["confidence"], z["method"], z["level"]) for z in zeilen] == \
        [("A", "X", "niedrig", "ortsliste", "objekt"), ("B", "Y", "niedrig", "ortsliste", "objekt")]
    assert all(z["source_object"] == "http://o/p/1" and z["lon"] is None for z in zeilen)
    assert vermerke == [("Schwebebahn", "stadtweit, nicht verortet"), ("Testplatz", "Geometrie offen (nach Messstufe G)")]


def test_eintrag_ohne_beleg_oder_mit_unbekannter_verortung_abgewiesen():
    with pytest.raises(ValueError):
        ok.Ort("X", beleg="")
    with pytest.raises(ValueError):
        ok.Ort("X", verortung="kreis", beleg="Test")


@pytest.mark.parametrize("name, erwartet", [
    ("Ressort 105 - Baurecht, Grundstücke und Wohnen", True), ("Ressort 105 - Bauen und Wohnen", True),
    ("Ressort 106 - Umweltschutz", True), ("105.1 Bauaufsicht (erfunden)", True),
    ("Ressort 103 - Umwelt, Grünflächen und Forsten", True), ("Ressort 104 - Straßen", False),
    ("Ressort 1050 (erfunden)", False), ("", False)])
def test_amt_privat_wuppertal(name, erwartet):
    assert bool(maske.AMT_PRIVAT.match(name)) is erwartet


def test_hausnummer_punkt_erlaubt():
    p = {"id": "http://o/p/1", "reference": "VO/0001/26", "paperType": "Beschlussvorlage", "name": "Teststraße 5"}
    assert maske.hausnummer_punkt_erlaubt(p)
    assert not maske.hausnummer_punkt_erlaubt(p, einwohner={"http://o/p/1"})                  # Kette § 24
    assert not maske.hausnummer_punkt_erlaubt(p, einwohner={"VO/0001/26"})
    assert not maske.hausnummer_punkt_erlaubt({**p, "name": "Bürgerantrag Teststraße 5"})     # Titel
    assert not maske.hausnummer_punkt_erlaubt({**p, "paperType": "Anregungen und Beschwerden"})
    assert not maske.hausnummer_punkt_erlaubt(p, amt_name="Ressort 105 - Bauen und Wohnen")  # privates Grundstück
    assert not maske.hausnummer_punkt_erlaubt(p, gremien=["Beirat Bürgerbeteiligung"])
    assert maske.hausnummer_punkt_erlaubt(p, amt_name="Ressort 104 - Straßen", gremien=["Rat der Stadt"])
