"""Ämterliste aus den Organisationen mit Präfix at (explore/aemter.py; CLAUDE.md 5.3 und 9 vom 13.11.2026).

Ohne Netz. Gelesen wird nur die versionierte Ergebnisdatei explore/ergebnisse/oparl_organisationen.tsv (Stufe 4);
Namen in den Einzeltests sind erfunden („Testamt“, „Musterbetrieb“ …) und prüfen nur die Muster.
"""
import csv
import re
import socket
import sys
from pathlib import Path

import pytest

EXPLORE = Path(__file__).resolve().parents[1] / "explore"
sys.path.insert(0, str(EXPLORE))
import aemter  # noqa: E402

ERG = EXPLORE / "ergebnisse"


def _lies(pfad):
    with open(pfad, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


@pytest.fixture(scope="module")
def quelle():
    return _lies(ERG / "oparl_organisationen.tsv")


@pytest.fixture(scope="module")
def tabelle():
    return _lies(ERG / "aemter.tsv")


@pytest.fixture
def ohne_netz(monkeypatch):
    def gesperrt(*a, **k):
        raise AssertionError("aemter.py darf keine Verbindung öffnen")
    monkeypatch.setattr(socket.socket, "connect", gesperrt)
    monkeypatch.setattr(socket, "create_connection", gesperrt)


def test_versionierte_tabelle_entsteht_deterministisch_aus_der_quelle(tmp_path, ohne_netz, capsys):
    """Zwei Läufe ohne Netz ergeben byteweise dieselbe Datei, und sie ist gleich der versionierten aemter.tsv."""
    for lauf in ("a", "b"):
        assert aemter.main(["--ergebnisse", str(tmp_path / lauf)]) == 0
    a = (tmp_path / "a" / "aemter.tsv").read_bytes()
    assert a == (tmp_path / "b" / "aemter.tsv").read_bytes()
    assert a == (ERG / "aemter.tsv").read_bytes()
    assert "Klassen: amt 76, beteiligung 2, politisch 2, offen 15" in capsys.readouterr().out


def test_jede_at_organisation_genau_einmal_und_klassifiziert(quelle, tabelle):
    at = [o for o in quelle if o["praefix"] == "at"]
    assert len(at) == 95 and len(tabelle) == 95
    assert sorted(z["id"] for z in tabelle) == sorted(o["id"] for o in at)
    assert len({z["id"] for z in tabelle}) == 95
    namen = {o["id"]: o["name"] for o in at}
    regeln = {nr for nr, *_ in aemter.REGELN} | {aemter.OHNE_REGEL[0]}
    for z in tabelle:
        assert list(z) == aemter.SPALTEN
        assert z["name"] == namen[z["id"]]                           # Name unverändert aus der Quelle
        assert z["klasse"] in aemter.KLASSEN and z["regel"] in regeln and z["merkmal"]
        assert (z["klasse"] == "offen") == bool(z["frage"]), z       # Frage genau bei offenen Fällen
        assert "None" not in (z["startDate"], z["endDate"])


def test_regel_der_zeile_ist_die_erste_passende(tabelle):
    """Die Regelspalte stimmt mit der Funktion überein, und keine frühere Regel passt auf den Namen."""
    for z in tabelle:
        nr, kl, *_ = aemter.klasse(z["name"])
        assert (nr, kl) == (z["regel"], z["klasse"])
        nummern = [r for r, *_ in aemter.REGELN]
        bis = nummern.index(nr) if nr in nummern else len(nummern)
        for _, _, muster, *_ in aemter.REGELN[:bis]:
            assert not re.search(muster, aemter.norm(z["name"])), (z["name"], muster)


@pytest.mark.parametrize("name", [
    "Gesamtpersonalrat", "Gleichstellungsstelle für Frau und Mann", "Regionalbüro", "Jobcenter Wuppertal",
    "Eigenbetrieb WAW (Wasser und Abwasser Wuppertal)", "Eigenbetrieb ESW (Eigenbetrieb Straßenreinigung Wuppertal)",
    "Eigenbetrieb GMW (Gebäudemanagement Wuppertal)", "Eigenbetrieb APH (Alten-u. Altenpflegeheime)",
    "Eigenbetrieb KIJU (Kinder-und Jugendwohngruppen)", "UWG", "BEG", "AWG", "DIE GRAUEN - Graue Panther-"])
def test_grenzfaelle_sind_offen_mit_frage(tabelle, name):
    """Grenzfälle aus dem Auftrag (CLAUDE.md 9, 13.11.2026: „Grenzfälle als Frage“) werden nicht geraten."""
    z = next(z for z in tabelle if z["name"] == name)
    assert z["klasse"] == "offen" and z["regel"].startswith("G") and z["frage"].endswith("?")


def test_zahlen_im_stufenplan_stimmen_mit_der_tabelle(tabelle):
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    abschnitt = text.split("### Auswertung Ämterliste")[1].split("\n## ")[0]
    je_klasse, je_regel = aemter.zaehlung(tabelle)
    m = re.search(r"Klassen: amt (\d+), beteiligung (\d+), politisch (\d+), offen (\d+) \(zusammen (\d+)\)", abschnitt)
    assert m, "Zeile mit den Klassen fehlt"
    assert [int(x) for x in m.groups()] == [je_klasse[k] for k in aemter.KLASSEN] + [len(tabelle)]
    im_plan = {r: int(n) for r, n in re.findall(r"^\| ([A-Z]\d) \| [a-z]+ \| .*? \| (\d+) \|$", abschnitt, re.M)}
    assert im_plan == dict(je_regel)
    for wort in ("mit endDate", "spätester Beginn", "früherer Beginn", "einzige"):
        n = sum(z["startfolge"] == wort for z in tabelle)
        assert re.search(rf"{wort} {n}\b(?!\.\d)", abschnitt), (wort, n)
    assert "Fassungen:" not in abschnitt and "keine belegten Fassungen oder Nachfolger" in abschnitt
    # Zahlen der Gegenprobe nach date und created (CLAUDE.md 2: Zeitumfang nach date)
    assert "587 Verweise nach `date`" in abschnitt and "566 nach `created`" in abschnitt
    assert "200 Vorlagen tragen `created` 2017-12-21" in abschnitt
    # der Abschnitt steht unter Stufe 4, vor Stufe 5, und enthält keinen bash-Block (die Stufenblöcke prüft
    # test_messstufen.py)
    assert text.index("## Stufe 4") < text.index("### Auswertung Ämterliste") < text.index("## Stufe 5")
    assert "```" not in abschnitt


@pytest.mark.parametrize("name, erwartet", [
    ("123 Testamt", ("A1", "amt", "123", "dienststelle")),
    ("123.4 Musterstelle", ("A1", "amt", "123.4", "dienststelle")),
    ("Ressort 987 - Proben", ("A2", "amt", "987", "dienststelle")),
    ("Stadtbetrieb 987 - Proben", ("A2", "amt", "987", "dienststelle")),
    ("Geschäftsbereich 9.9 - Proben", ("A3", "amt", "9.9", "geschaeftsbereich")),
    ("GB9 Proben", ("A3", "amt", "9", "geschaeftsbereich")),
    ("Geschäftsbereichsbüro 987", ("A4", "amt", "987", "dienststelle")),
    ("Probenamt", ("A5", "amt", "", "")),
    ("Ratsgruppe Test", ("P1", "politisch", "", "")),
    ("Testfraktion", ("R0", "offen", "", "")),             # Wortgrenze: „Fraktion“ als eigenes Wort
    ("Muster Fraktion", ("P1", "politisch", "", "")),
    ("Musterbetrieb GmbH", ("B1", "beteiligung", "", "")),
    ("Probe AG", ("B1", "beteiligung", "", "")),
    ("Probe AGB", ("R0", "offen", "", "")),                   # „AG“ nur als eigenes Wort
    ("Eigenbetrieb Muster GmbH", ("G1", "offen", "", "")),   # Grenzfall geht vor Rechtsform
    ("XYZ", ("G2", "offen", "", "")),
    ("Musterstelle", ("R0", "offen", "", "")),
])
def test_muster_mit_erfundenen_namen(name, erwartet):
    nr, kl, *_ = aemter.klasse(name)
    assert (nr, kl) + aemter.nummer(name) == erwartet


def test_gleiche_nummer_und_hinweise_mit_erfundenen_daten():
    org = [
        {"id": "http://test.invalid/organizations/at/1", "praefix": "at", "name": "Ressort 987 - Alt",
         "startDate": "1999-10-01", "endDate": "2006-10-15"},
        {"id": "http://test.invalid/organizations/at/2", "praefix": "at", "name": "Ressort 987 - Mittel",
         "startDate": "2006-07-01", "endDate": "None"},
        {"id": "http://test.invalid/organizations/at/3", "praefix": "at", "name": "987 Neu",
         "startDate": "2016-09-15", "endDate": "None"},
        {"id": "http://test.invalid/organizations/at/4", "praefix": "at", "name": "XYZ",
         "startDate": "2005-01-07", "endDate": "2025-10-31"},
        {"id": "http://test.invalid/organizations/at/5", "praefix": "at", "name": "Probenamt",
         "startDate": "2006-10-16", "endDate": "None"},
        {"id": "http://test.invalid/organizations/gr/1", "praefix": "gr", "name": "Rat",
         "startDate": "", "endDate": ""},
    ]
    z = {r["id"][-4:]: r for r in aemter.tabelle(org)}
    assert list(z) == ["at/1", "at/2", "at/3", "at/4", "at/5"]           # gr nicht in der Ämterliste
    assert [z[k]["startfolge"] for k in ("at/1", "at/2", "at/3")] == ["mit endDate", "früherer Beginn",
                                                                       "spätester Beginn"]
    assert z["at/3"]["gleiche_nummer"] == "at/1, at/2" and z["at/4"]["startfolge"] == "einzige"
    assert z["at/2"]["endDate"] == "" and "ohne Nummer" in z["at/5"]["bemerkung"]
    assert "zeitlich anschließend beginnt at/5 (2006-10-16)" in z["at/1"]["bemerkung"]
    assert "47 Tage nach der Kommunalwahl am 14.09.2025" in z["at/4"]["bemerkung"]
    assert "Kommunalwahl" not in z["at/1"]["bemerkung"]                  # Wahlhinweis nur außerhalb von amt


def test_gleiche_nummer_ist_keine_nachfolge_echte_daten(tabelle):
    """Unter 403 bestehen laut Quelle drei verschieden benannte Organisationen ohne endDate, zwei davon mit gleichem
    startDate; die Tabelle darf keine davon als „neueste Fassung“ ausweisen (Befund der Prüfung vom 13.11.2026)."""
    gruppe = [z for z in tabelle if z["nummer"] == "403" and z["nummernart"] == "dienststelle"]
    assert len(gruppe) == 3 and all(not z["endDate"] for z in gruppe)
    assert len({z["name"] for z in gruppe}) == 3
    assert {z["startfolge"] for z in tabelle} <= {"einzige", "mit endDate", "früherer Beginn", "spätester Beginn"}
    gleich = [z for z in gruppe if "gleiches startDate wie" in z["bemerkung"]]
    assert len(gleich) == 2 and gleich[0]["startDate"] == gleich[1]["startDate"]
    assert "fassung" not in aemter.SPALTEN


def test_gleichzeitig_verwendet_und_nach_end_date_mit_erfundenen_daten(tmp_path, ohne_netz):
    import json
    cache = tmp_path / "roh"
    cache.mkdir()
    b = "http://test.invalid/organizations/at/"
    typ = "https://schema.oparl.org/1.1/Paper"
    seite = {"data": [
        {"id": "p1", "type": typ, "created": "2017-12-21", "date": "2013-02-01", "underDirectionOf": [b + "1"]},
        {"id": "p2", "type": typ, "created": "2022-01-01", "date": "2022-01-05", "underDirectionOf": [b + "1"]},
        {"id": "p3", "type": typ, "created": "2020-01-01", "date": "2020-02-01", "underDirectionOf": [b + "2"]},
        {"id": "p4", "type": typ, "created": "2019-12-20", "date": "2020-01-10", "underDirectionOf": [b + "3"]},
        {"id": "p5", "type": typ, "created": "2003-01-01", "date": "2003-01-02", "underDirectionOf": [b + "4"]}]}
    (cache / "a.json").write_text(json.dumps(seite), encoding="utf-8")
    zeilen = aemter.tabelle([
        {"id": b + "1", "praefix": "at", "name": "Ressort 987 - Eins", "startDate": "1999-10-01", "endDate": ""},
        {"id": b + "2", "praefix": "at", "name": "Ressort 987 - Zwei", "startDate": "2003-02-05", "endDate": ""},
        {"id": b + "3", "praefix": "at", "name": "Ressort 986 - Drei", "startDate": "1999-10-01",
         "endDate": "2019-12-31"},
        {"id": b + "4", "praefix": "at", "name": "Ressort 986 - Vier", "startDate": "2020-01-01", "endDate": ""}])
    g = aemter.gegenprobe_verweise(cache, zeilen)
    assert (g["ab_2020_date"], g["ab_2020_created"]) == (3, 2)        # p4: date 2020, created 2019
    assert g["jahre_created"]["2017"] == 1 and g["jahre_date"]["2013"] == 1
    # 987: Zeiträume 2013–2022 und 2020 überschneiden sich; 986: 2020 und 2003 nicht
    assert aemter.gleichzeitig_verwendet(zeilen, g["zeitraum"]) == {("dienststelle", "987"): [b + "1", b + "2"]}
    assert aemter.nach_end_date(zeilen, g["zeitraum"]) == {b + "3": ("2019-12-31", "2020-01-10")}


def test_eingabe_fehlt_oder_ohne_at(tmp_path, ohne_netz):
    assert aemter.main(["--organisationen", str(tmp_path / "fehlt.tsv"), "--ergebnisse", str(tmp_path)]) == 1
    leer = tmp_path / "nur_gr.tsv"
    leer.write_text("id\tpraefix\tname\tkurz\torganizationType\tclassification\tstartDate\tendDate\n"
                    "http://test.invalid/organizations/gr/1\tgr\tRat\t\tNone\tNone\tNone\tNone\n", encoding="utf-8")
    assert aemter.main(["--organisationen", str(leer), "--ergebnisse", str(tmp_path)]) == 1
    assert not (tmp_path / "aemter.tsv").exists()


def test_gegenprobe_cache_nur_lesend_mit_erfundenen_seiten(tmp_path, ohne_netz):
    import json
    cache = tmp_path / "roh"
    cache.mkdir()
    b = "http://test.invalid/organizations/at/"
    typ = "https://schema.oparl.org/1.1/"
    seite = {"data": [
        {"id": "p1", "type": typ + "Paper", "created": "2021-01-01", "underDirectionOf": [b + "1"]},
        {"id": "p2", "type": typ + "Paper", "created": "2019-01-01", "underDirectionOf": [b + "4"]},
        {"id": "p3", "type": typ + "Paper", "created": "2021-01-01"},
        {"id": "m1", "type": typ + "Meeting", "underDirectionOf": [b + "1"]}]}
    (cache / "a.json").write_text(json.dumps(seite), encoding="utf-8")
    (cache / "b.json").write_text(json.dumps(seite), encoding="utf-8")       # doppelte Vorlagen zählen einmal
    (cache / "c.json").write_text("kein json", encoding="utf-8")
    vorher = {p.name: p.read_bytes() for p in cache.iterdir()}
    zeilen = aemter.tabelle([{"id": b + "1", "praefix": "at", "name": "123 Testamt"},
                             {"id": b + "4", "praefix": "at", "name": "XYZ"}])
    g = aemter.gegenprobe_verweise(cache, zeilen)
    assert (g["vorlagen"], g["mit_verweis"], dict(g["je_klasse"]), g["ab_2020_created"]) == (
        3, 2, {"amt": 1, "offen": 1}, 1)
    assert {p.name: p.read_bytes() for p in cache.iterdir()} == vorher


def test_skript_importiert_abruf_nicht_selbst():
    """aemter.py importiert kein Abrufmodul direkt; abruf.py wird nur über oparl_messung mitgeladen (Abgleich für
    Stufe 6). Dass dabei nichts abgerufen wird, prüft test_main_ruft_hole_nicht_auf."""
    text = (EXPLORE / "aemter.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*import (abruf|urllib|requests|http)\b", text, re.M)
    assert "import abruf" not in text and "urlopen" not in text


def test_main_ruft_hole_nicht_auf(tmp_path, ohne_netz, monkeypatch, capsys):
    """main() lädt über oparl_messung auch abruf.py; hole() darf dabei nie aufgerufen werden, auch nicht mit --cache."""
    import abruf
    import oparl_messung

    def verboten(*a, **k):
        raise AssertionError("aemter.py darf abruf.hole nicht aufrufen")
    monkeypatch.setattr(abruf, "hole", verboten)
    monkeypatch.setattr(oparl_messung, "hole", verboten)
    (tmp_path / "roh").mkdir()
    assert aemter.main(["--ergebnisse", str(tmp_path), "--cache", str(tmp_path / "roh")]) == 0
    assert "Abgleich Stufe 6 nicht eindeutig: 8 Nummern" in capsys.readouterr().out
