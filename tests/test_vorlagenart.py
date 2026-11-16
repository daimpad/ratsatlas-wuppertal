"""Zerlegung der Wuppertaler Vorlagenart (pipeline/vorlagenart.py) und Einreichende daraus (pipeline/actors.py).
Grundlage sind die in Messstufe 5 gemessenen Werte (explore/ergebnisse/oparl_papertypen.tsv); keine Anfrage."""
import csv
from pathlib import Path

from pipeline import actors, process, vorlagenart

ROOT = Path(__file__).resolve().parent.parent


def _gemessen():
    with open(ROOT / "explore" / "ergebnisse" / "oparl_papertypen.tsv", encoding="utf-8") as f:
        return [z["paperType"] for z in csv.DictReader(f, delimiter="\t")]


def test_alle_gemessenen_vorlagenarten_zerlegt():
    arten = _gemessen()
    assert len(arten) == 33
    offen = [a for a in arten if vorlagenart.zerlege(a) is None]
    assert offen == []


def test_regeln_1_bis_4_wie_regeltabelle_aus_phase_1():
    with open(ROOT / "explore" / "paperType_regeln.tsv", encoding="utf-8") as f:
        tabelle = {int(z["nr"]): z["muster"] for z in csv.DictReader(f, delimiter="\t")}
    assert {nr: m for nr, m, *_ in vorlagenart.REGELN if nr <= 4} == tabelle


def test_beispiele():
    z = vorlagenart.zerlege
    fdp = z("Antrag FDP / WfW Rat AU")
    assert (fdp["art"], fdp["einreichende"], fdp["ebene"], fdp["zusatz"], fdp["regel"]) == \
        ("Antrag", "FDP / WfW", "Rat", "AU", 3)
    assert (z("Antrag B90/Grüne BV")["einreichende"], z("Antrag B90/Grüne BV")["ebene"]) == ("B90/Grüne", "BV")
    assert (z("Große Anfrage die Linke")["art"], z("Große Anfrage die Linke")["einreichende"]) == \
        ("Große Anfrage", "die Linke")
    assert z("Gemeinsamer Antrag Rat")["einreichende"] == ""            # offen (CLAUDE.md 5.3)
    assert z("Beschlussvorlage BV")["kategorie"] == "verwaltung" and z("Beschlussvorlage BV")["ebene"] == "BV"
    assert z("Satzungsbeschluss")["kategorie"] == "verwaltung"
    assert (z("Anfrage SPD BV")["art"], z("Anfrage SPD BV")["einreichende"]) == ("Anfrage", "SPD")
    assert z("Antrag DIE LINKE. Rat OB")["zusatz"] == "OB"
    assert z("") is None and z("Unbekannte Art") is None


def test_einreichende_aus_vorlagenart_gekennzeichnet():
    rows = actors.originators({"paperType": "Antrag CDU", "date": "2024-01-01", "name": "Radweg"}, [])
    assert [(r["actor"], r["actor_type"], r["method"], r["evidence"]) for r in rows] == \
        [("CDU", "Fraktion/Gruppe", "paper_type", "Antrag CDU")]
    rows = actors.originators({"paperType": "Antrag B90/Grüne BV", "date": "2024-01-01", "name": "x"}, [], {"Barmen"})
    assert [(r["actor"], r["actor_type"]) for r in rows] == [("Grüne-Bezirksfraktion Barmen", "Bezirksfraktion")]
    rows = actors.originators({"paperType": "Große Anfrage gewähltes Mitglied", "date": "2024-01-01", "name": "x"}, [])
    assert [(r["actor"], r["actor_type"]) for r in rows] == [("gewähltes Mitglied", "Einzelmandat")]
    rows = actors.originators({"paperType": "Antrag FDP / WfW Rat AU", "date": "2024-01-01", "name": "x"}, [])
    assert [r["actor"] for r in rows] == ["FDP / WfW"]                  # wörtlich, nicht aufgelöst


def test_gemeinsamer_antrag_ohne_namen_bleibt_offen():
    rows = actors.originators({"paperType": "Gemeinsamer Antrag BV", "date": "2024-01-01", "name": "Spielplatz"}, [])
    assert rows == []


def test_verwaltung_und_kategorien():
    rows = actors.originators({"paperType": "Bericht", "date": "2024-01-01", "name": "x",
                               "underDirectionOf": ["http://o/at/3"]}, [])
    assert [(r["actor"], r["organization_id"]) for r in rows] == [("Verwaltung", "http://o/at/3")]
    assert process.initiation_kind("Große Anfrage CDU") == "anfrage"
    assert process.initiation_kind("Gemeinsame große Anfrage") == "anfrage"
    assert process.initiation_kind("Antrag SPD Rat AU") == "antrag"
    assert process.initiation_kind("Grundsatzbeschluss") == "verwaltung"
    assert process.initiation_kind("Unbekannt") == "sonstige"


def test_federfuehrung_mit_klasse_aus_der_aemterliste(tmp_path, monkeypatch):
    datei = tmp_path / "aemter.tsv"
    datei.write_text("id\tname\tklasse\nhttp://o/at/3\tRessort 102 - Vermessung\tamt\n"
                     "http://o/at/9\tBeteiligung (erfunden)\tbeteiligung\n", encoding="utf-8")
    monkeypatch.setattr(actors, "AEMTERLISTE", datei)
    rows = actors.responsibilities({"underDirectionOf": ["http://o/at/3"]}, {}, {})
    assert rows[0]["evidence"] == "Ämterliste: amt" and rows[0]["method"] == "underDirectionOf"
    rows = actors.responsibilities({"underDirectionOf": ["http://o/at/77"]}, {}, {})
    assert rows[0]["evidence"] is None                                    # nicht in der Liste: ohne Klasse


def test_echte_aemterliste_lesbar():
    klassen = set(actors.aemterliste().values())
    assert klassen <= {"amt", "beteiligung", "politisch", "sonstig", "offen"} and "amt" in klassen
