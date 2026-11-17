"""tools/geodaten_uebernehmen.py (erfundene Flächen) und die versionierten Geodaten in data/geo (Stand 16.11.2026).

Erfundene Testdaten mit den Feldnamen der Wuppertaler Quelle (config.GEO_FELDER); keine Anfrage an Server der Stadt.
"""
import importlib.util
import json
from pathlib import Path

import pytest

from pipeline import config, plans

ROOT = Path(__file__).resolve().parents[1]


def _werkzeug():
    spec = importlib.util.spec_from_file_location("geodaten_uebernehmen", ROOT / "tools" / "geodaten_uebernehmen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _rechteck(w, s, o, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [o, s], [o, n], [w, n], [w, s]]]}


def _fc(feats):
    return {"type": "FeatureCollection", "name": "Test", "features": feats}


BEZIRKE = _fc([{"type": "Feature", "properties": {"BEZIRK": "1", "NAME": "Testbezirk Eins", "FLAECHE": 1},
                "geometry": _rechteck(0, 0, 0.01, 0.01)},
               {"type": "Feature", "properties": {"BEZIRK": "2", "NAME": "Testbezirk Zwei", "FLAECHE": 1},
                "geometry": _rechteck(0.01, 0, 0.02, 0.01)}])
QUARTIERE = _fc([{"type": "Feature", "properties": {"QUARTIER": "10", "NAME": "Testquartier A", "FLAECHE": 1},
                  "geometry": _rechteck(0, 0, 0.01, 0.01)},
                 {"type": "Feature", "properties": {"QUARTIER": "21", "NAME": "Testquartier B", "FLAECHE": 1},
                  "geometry": _rechteck(0.012, 0, 0.018, 0.01)}])
PLAN = {"type": "Feature", "properties": {"ID": 1, "VERFAHREN": "T1", "Dat_Recht": "02.03.2004", "VSTAND": "rechtskräftig",
                                          "Plan1": "https://example.invalid/T1.pdf", "Plan2": " "},
        "geometry": {"type": "MultiPolygon", "coordinates": [[[[0.0011234567891, 0.001], [0.003, 0.001],
                                                               [0.003, 0.003], [0.0011234567891, 0.001]]]]}}


def _dateien(tmp_path, quartiere=QUARTIERE):
    pfade = {}
    for name, daten in (("bez", BEZIRKE), ("qua", quartiere), ("rvb", _fc([PLAN])), ("lfd", _fc([
            {**PLAN, "properties": {**PLAN["properties"], "VERFAHREN": "T2", "Dat_Recht": None,
                                    "VSTAND": "Aufstellungsbeschluss"}}]))):
        pfade[name] = tmp_path / f"{name}.json"
        pfade[name].write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return pfade


def _aufruf(pfade, ziel):
    return ["--stadtbezirke", str(pfade["bez"]), "--quartiere", str(pfade["qua"]), "--bplan", str(pfade["rvb"]),
            "--bplan-laufend", str(pfade["lfd"]), "--abruf", "2026-11-16", "--ziel", str(ziel)]


def test_uebernahme_bonner_modell_und_plaene_unveraendert(tmp_path):
    pfade = _dateien(tmp_path)
    _werkzeug().main(_aufruf(pfade, tmp_path / "geo"))
    geo = tmp_path / "geo"
    bez = json.loads((geo / config.STADTBEZIRKE.name).read_text(encoding="utf-8"))
    assert [f["properties"] for f in bez["features"]] == [{"bezirk": "1", "bezirk_bez": "Testbezirk Eins"},
                                                          {"bezirk": "2", "bezirk_bez": "Testbezirk Zwei"}]
    assert [f["geometry"] for f in bez["features"]] == [f["geometry"] for f in BEZIRKE["features"]]
    qua = json.loads((geo / config.ORTSTEILE.name).read_text(encoding="utf-8"))
    assert [f["properties"] for f in qua["features"]] == [
        {"ortsteil": "10", "ortsteil_bez": "Testquartier A", "bezirk": "1", "bezirk_bez": "Testbezirk Eins"},
        {"ortsteil": "21", "ortsteil_bez": "Testquartier B", "bezirk": "2", "bezirk_bez": "Testbezirk Zwei"}]
    for d, quelle in ((bez, config.QUELLE_STADTBEZIRKE), (qua, config.QUELLE_GEO)):
        assert d["meta"]["source"] == config.SOURCES[quelle]["url"] and d["meta"]["attribution"] == config.NAMENSNENNUNG
        assert d["meta"]["retrieved_at"] == "2026-11-16" and d["meta"]["aenderung"].startswith("Geometrien unverändert")
    assert "abgeleitet" in qua["meta"]["aenderung"]
    # Bebauungspläne: Features wertgleich (CC BY-ND 4.0), Zahlen auch als Text, nur „meta“ ergänzt
    for name, quelle, datei in ((config.BPLAN.name, config.QUELLE_BPLAN, "rvb"),
                                (config.BPLAN_LAUFEND.name, config.QUELLE_BPLAN_LAUFEND, "lfd")):
        text = (geo / name).read_text(encoding="utf-8")
        d = json.loads(text)
        assert d["features"] == json.loads(pfade[datei].read_text(encoding="utf-8"))["features"]
        assert "0.0011234567891" in text and d["meta"]["source"] == config.SOURCES[quelle]["url"]
        assert d["meta"]["attribution"] == config.NAMENSNENNUNG_BPLAN


def test_stadtbezirk_des_quartiers_muss_zur_nummer_passen(tmp_path):
    falsch = json.loads(json.dumps(QUARTIERE))
    falsch["features"][1]["properties"]["QUARTIER"] = "11"     # liegt in Testbezirk Zwei
    with pytest.raises(SystemExit, match="Quartier 11 Testquartier B: Stadtbezirk nicht eindeutig"):
        _werkzeug().main(_aufruf(_dateien(tmp_path, falsch), tmp_path / "geo"))
    assert not (tmp_path / "geo" / config.ORTSTEILE.name).exists()


def test_plan_ohne_nummer_bricht_ab(tmp_path):
    pfade = _dateien(tmp_path)
    ohne = _fc([{**PLAN, "properties": {**PLAN["properties"], "VERFAHREN": " "}}])
    pfade["rvb"].write_text(json.dumps(ohne), encoding="utf-8")
    with pytest.raises(SystemExit, match="ohne Geometrie oder VERFAHREN"):
        _werkzeug().main(_aufruf(pfade, tmp_path / "geo"))


def test_planfelder_der_quelle_und_bonner_modell():
    p = PLAN["properties"]
    assert plans.plan_name(p) == "T1" and plans.inkraft(p) == "2004-03-02" and plans.plan_pdf(p).endswith("T1.pdf")
    assert plans.plan_pdf({"Plan1": "208_DBA"}) is None and plans.inkraft({"Dat_Recht": None}) is None
    assert plans.plan_name({"name": "6322-2", "VERFAHREN": "x"}) == "6322-2"
    assert plans.inkraft({"inkraft_seit": "2020-01-01"}) == "2020-01-01"


# --- versionierte Geodaten (data/geo, Browser-Download des Auftraggebers vom 16.11.2026) ---------------------------

def _laden(pfad):
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_versionierte_geodaten_vollstaendig():
    bez, qua = _laden(config.STADTBEZIRKE), _laden(config.ORTSTEILE)
    assert len(bez["features"]) == 10 and len(qua["features"]) == 69     # CLAUDE.md 2
    namen = {f["properties"]["bezirk_bez"] for f in bez["features"]}
    assert {"Elberfeld", "Langerfeld-Beyenburg", "Uellendahl-Katernberg", "Ronsdorf"} <= namen
    assert {f["properties"]["bezirk_bez"] for f in qua["features"]} == namen
    assert all(f["properties"]["ortsteil"][0] == f["properties"]["bezirk"] for f in qua["features"])
    for d in (bez, qua):
        assert d["meta"]["attribution"] == config.NAMENSNENNUNG and d["meta"]["retrieved_at"] == "2026-11-16"
    rvb, lfd = _laden(config.BPLAN), _laden(config.BPLAN_LAUFEND)
    assert len(rvb["features"]) == 692 and len(lfd["features"]) == 99
    for d in (rvb, lfd):
        assert d["meta"]["attribution"] == config.NAMENSNENNUNG_BPLAN and "CC BY-ND 4.0" in d["meta"]["license"]
        assert all(plans.plan_name(f["properties"]) for f in d["features"])
    # keine Adressen, kein Straßenverzeichnis in data/geo (nur für die Verortung, nicht für die Seite)
    assert sorted(p.name for p in config.GEO.iterdir()) == sorted(
        p.name for p in (config.STADTBEZIRKE, config.ORTSTEILE, config.BPLAN, config.BPLAN_LAUFEND))


def test_stadt_bbox_umschliesst_die_stadtbezirke():
    s, w, n, e = config.STADT_BBOX
    xs, ys = [], []

    def lauf(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                lauf(x)
    for f in _laden(config.STADTBEZIRKE)["features"]:
        lauf(f["geometry"]["coordinates"])
    assert s <= min(ys) and w <= min(xs) and n >= max(ys) and e >= max(xs)
    assert min(ys) - s < 0.001 and max(xs) - e > -0.001
