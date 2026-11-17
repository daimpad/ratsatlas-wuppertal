"""Ablage der aus Volltexten abgeleiteten Orte (Entscheidung 17.11.2026): ohne Text, ohne Hauskoordinaten, sortiert;
Rundlauf speichern → lesen. Erfundene Werte."""
import json

from pipeline import volltext


def zeile(name, level="strasse", **k):
    return {"name": name, "level": level, "ortsteil": "Testquartier A", "bezirk": "Testbezirk 1", "lon": 0.001,
            "lat": 0.002, "source": "test", "method": "volltext_strasse", "confidence": "mittel",
            "evidence": f"im Hauptteil des Hauptdokuments genannt: {name}", "teil": "Hauptteil", "nennungen": 2,
            "text": "darf nicht gespeichert werden", **k}


def test_rundlauf_ohne_text_und_ohne_hauskoordinaten(tmp_path):
    pfad = tmp_path / "orte.json"
    volltext.orte_speichern({"b": {"befund": "verortet", "teil": "Hauptteil", "zeilen": [zeile("Teststraße")]},
                             "a": {"befund": "verortet", "teil": "Hauptteil", "zeilen": [zeile("Testweg 1", "adresse")]}},
                            7, pfad)
    roh = pfad.read_text(encoding="utf-8")
    assert "darf nicht gespeichert" not in roh
    daten = json.loads(roh)
    assert daten["meta"]["vorlagen_mit_text"] == 7 and daten["meta"]["vorlagen_verortet"] == 1
    g = volltext.gespeicherte_orte(pfad)
    assert list(g) == ["b"] and g["b"]["zeilen"][0]["name"] == "Teststraße"
    assert set(g["b"]["zeilen"][0]) == set(volltext.ABLAGE_FELDER)


def test_ohne_datei_leer(tmp_path):
    assert volltext.gespeicherte_orte(tmp_path / "fehlt.json") == {}
