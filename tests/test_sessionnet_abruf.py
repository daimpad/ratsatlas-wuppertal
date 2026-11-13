"""SessionNet-Adapter, Wuppertaler Abruf nach dem Plan für Phase 2 (CLAUDE.md 9, 13.11.2026), gegen den lokalen
Testserver (tests/oparl_testserver.py, erfundene Daten, keine Anfrage an die Stadt):
- modified_since URL-kodiert, auch in Folgeadressen; Abbruch, wenn der Filter nicht wirkt (Stufe 2)
- Zeitfilter des Vollabrufs: Grenzseite nach `created` plus Sicherheitsabstand, Filter nach `date` (Stufe 3)
- Sitzungen: erste Seiten der Liste plus verwiesene Sitzungen einzeln, nicht die ganze Liste (Stufe 4)
- Schätzung des Vollabrufs ohne Netz
Gegenproben (im Bericht zu dieser Änderung): unkodiert gesendet, ohne Sicherheitsabstand und mit der ganzen
Sitzungsliste schlagen die jeweiligen Tests fehl."""
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pipeline import abruf, config, sessionnet

ROOT = Path(__file__).resolve().parent.parent


def _jsonl(path):
    return [json.loads(z) for z in path.read_text(encoding="utf-8").splitlines() if z.strip()]


def _tsv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _statistik(liste):
    return [z for z in _tsv(config.ABRUFSTATISTIK) if z["liste"] == liste]


def _seiten(oparl, pfad="/papers"):
    """Abgerufene Seiten einer Liste (Parameter page; erste Seite None)."""
    return [q.get("page") for p, q, _ in oparl.anfragen if p == pfad]


def _vorlage(oparl, i, created, datum, sitzung=1, modified="2026-10-01T10:00:00+02:00"):
    p = oparl.paper(i, modified=modified)
    p["created"], p["date"] = created, datum
    p["consultation"][0]["meeting"] = sitzung if isinstance(sitzung, str) else f"{oparl.b}/meetings/{sitzung}"
    return p


def _zustand():
    return json.loads(config.ZUSTAND.read_text(encoding="utf-8"))


def _stand():
    return json.loads(config.STAND.read_text(encoding="utf-8"))


# --- (1) modified_since URL-kodiert ---------------------------------------------------------------------------------

def test_filter_in_folgeadresse():
    seit = "2026-11-04T08:45:43+00:00"
    kodiert = "modified_since=2026-11-04T08%3A45%3A43%2B00%3A00"
    b = "http://127.0.0.1/papers"
    assert sessionnet._filter_in_folgeadresse(f"{b}?{kodiert}&page=2", seit) == (f"{b}?{kodiert}&page=2", False)
    assert sessionnet._filter_in_folgeadresse(f"{b}?modified_since={seit}&page=2", seit) == (
        f"{b}?{kodiert}&page=2", True)
    assert sessionnet._filter_in_folgeadresse(f"{b}?page=2", seit) == (f"{b}?page=2&{kodiert}", True)
    assert sessionnet._filter_in_folgeadresse(f"{b}?page=2", None) == (f"{b}?page=2", False)
    assert sessionnet._filter_in_folgeadresse(None, seit) == (None, False)
    assert sessionnet._mit_parametern(b, modified_since=seit, limit="") == f"{b}?{kodiert}"


@pytest.mark.parametrize("folgeadresse", ["kodiert", "roh", "ohne"])
def test_folgeadresse_wird_kodiert_gefiltert(oparl, folgeadresse):
    """Wie links.next den Filter weitergibt, ist für Wuppertal nicht gemessen: roh (mit „+“, der Server läse ein
    Leerzeichen und filterte nicht) und ohne Parameter werden berichtigt; alle Seiten kommen gefiltert."""
    sessionnet.fetch_all()
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    alt = [oparl.paper(i) for i in (6, 7, 8)]                      # ungeändert: dürfen nicht kommen
    oparl.papers = alt + [oparl.paper(i, modified=jetzt) for i in range(1, 6)]
    oparl.folgeadresse = folgeadresse
    oparl.anfragen.clear()
    oparl.roh.clear()
    sessionnet.fetch_all()
    assert _seiten(oparl) == [None, "2", "3"]
    assert all("%2B00%3A00" in r for r in oparl.roh if r.startswith("/papers"))
    z = _statistik("papers")[-1]
    assert (z["modus"], z["filter_wirksam"], z["ergebnis"]) == ("inkrementell", "ja", "ok")
    zeilen = [r for r in _tsv(config.ABRUFSTATISTIK_SEITEN) if r["modus"] == "inkrementell"]
    angepasst = [r["folgeadresse_angepasst"] for r in zeilen]
    assert angepasst == (["", "", ""] if folgeadresse == "kodiert" else ["", "ja", "ja"])
    assert not {f"{oparl.b}/papers/{i}" for i in (6, 7, 8)} & {p["id"] for p in _jsonl(config.PAPERS)}


def test_unwirksamer_filter_bricht_den_inkrementellen_lauf_ab(oparl, monkeypatch):
    """Übergeht der Server modified_since, bricht der Lauf nach der ersten Seite ab (Art `filter`), statt die ganze
    Liste zu laden; der letzte gültige Stand bleibt, kein Sperrverdacht."""
    sessionnet.fetch_all()
    vorher = config.PAPERS.read_bytes()
    original = oparl.liste
    monkeypatch.setattr(oparl, "liste", lambda objekte, pfad, q, groesse=None: original(
        objekte, pfad, {k: v for k, v in q.items() if k != "modified_since"}, groesse))
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert _seiten(oparl) == [None]                                 # nur die erste Seite
    assert not [p for p, _, _ in oparl.anfragen if p.startswith("/meetings")]
    assert config.PAPERS.read_bytes() == vorher
    z = _statistik("papers")[-1]
    assert z["modus"] == "inkrementell" and z["ergebnis"].startswith("abbruch: modified_since unwirksam")
    zustand = _zustand()
    assert zustand["letzter_abbruch"]["art"] == "filter"
    assert not {"sperre_verdacht", "listenfehler", "papers_fortsetzung"} & set(zustand)
    stand = _stand()
    assert "modified_since unwirksam" in stand["abruf_fehler"]["meldung"]
    assert "modified_since wirkt nicht" in stand["abruf_hinweis"]["meldung"]


# --- (2) Zeitfilter des Vollabrufs ----------------------------------------------------------------------------------

# Seiten zu je 2 Vorlagen, neueste zuerst nach created: (created, date) je Vorlage. Grenzseite 3 (alle created 2019),
# Treffer (date ab 2020) auf den Seiten 3 und 5; mit Sicherheitsabstand 3 endet der Abruf nach Seite 8
SEITEN = [
    [("2021-03-01", "2021-03-10"), ("2021-02-01", "2021-02-05")],     # 1
    [("2020-01-10", "2020-01-20"), ("2020-01-02", "2020-01-03")],     # 2
    [("2019-12-20", "2020-02-01"), ("2019-12-10", "2019-12-15")],     # 3 Grenzseite, ein Treffer
    [("2019-11-20", "2019-11-25"), ("2019-11-10", "2019-11-12")],     # 4 Abstand 1
    [("2019-10-20", "2021-05-01"), ("2019-10-10", "2019-10-11")],     # 5 Treffer: Zählung zurück auf 0
    [("2019-09-20", "2019-09-25"), ("2019-09-10", "2019-09-12")],     # 6 Abstand 1
    [("2019-08-20", "2019-08-25"), ("2019-08-10", "2019-08-12")],     # 7 Abstand 2
    [("2019-07-20", "2019-07-25"), ("2019-07-10", "2019-07-12")],     # 8 Abstand 3: Ende
    [("2019-06-20", "2020-06-25"), ("2019-06-10", "2019-06-12")],     # 9 nicht gelesen
    [("2019-05-20", "2019-05-25"), ("2019-05-10", "2019-05-12")],     # 10 nicht gelesen
]
IM_ZEITRAUM = {(1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (5, 0)}      # (Seite, Platz) mit date ab 2020, gelesen


def _zeitfilter_liste(oparl, seiten=SEITEN):
    """Vorlagen in Kölner bzw. Wuppertaler Form (neueste zuerst nach created); Kennung = 100 × Seite + Platz."""
    oparl.form = "koeln"
    neueste = [(_vorlage(oparl, 100 * s + i, f"{c}T10:00:00+01:00", d), (s, i))
               for s, seite in enumerate(seiten, 1) for i, (c, d) in enumerate(seite)]
    oparl.papers = [p for p, _ in reversed(neueste)]                  # zuletzt angefügt kommt zuerst
    return {f"{oparl.b}/papers/{100 * s + i}" for _, (s, i) in neueste if (s, i) in IM_ZEITRAUM}


def test_zeitfilter_grenzseite_und_sicherheitsabstand(oparl, monkeypatch):
    monkeypatch.setattr(config, "ABRUF_SICHERHEITSABSTAND", 3)
    erwartet = _zeitfilter_liste(oparl)
    sessionnet.fetch_all()
    assert _seiten(oparl) == [None, "2", "3", "4", "5", "6", "7", "8"]   # Seite 9 nie angefragt
    assert {p["id"] for p in _jsonl(config.PAPERS)} == erwartet          # auch die Treffer auf Seite 3 und 5
    z = _statistik("papers")[-1]
    assert (z["modus"], z["seiten"], z["objekte"], z["ergebnis"]) == ("voll", "8", "6", "ok")
    assert (z["grenzseite"], z["ende"], z["ausserhalb_zeitraum"]) == ("3", "Zeitfilter", "10")
    zeilen = _tsv(config.ABRUFSTATISTIK_SEITEN)
    assert [r["seite"] for r in zeilen] == [str(i) for i in range(1, 9)]
    status = [r["zeitfilter"] for r in zeilen]
    assert status[:2] == ["vor der Grenzseite"] * 2 and status[2].startswith("Grenzseite")
    assert status[3:] == ["Sicherheitsabstand 1/3", status[4], "Sicherheitsabstand 1/3", "Sicherheitsabstand 2/3",
                          "Sicherheitsabstand 3/3"] and "zurückgesetzt" in status[4]
    r3 = zeilen[2]
    assert (r3["objekte"], r3["im_zeitraum"], r3["date_ab"], r3["created_ab"], r3["created_vor"]) == (
        "2", "1", "1", "0", "2")
    assert (r3["created_min"], r3["created_max"], r3["date_min"], r3["date_max"]) == (
        "2019-12-10", "2019-12-20", "2019-12-15", "2020-02-01")
    # nur Zahlen und Kalendertage im Seitenprotokoll, keine Titel
    text = config.ABRUFSTATISTIK_SEITEN.read_text(encoding="utf-8")
    assert "Vorlage" not in text and oparl.TITEL_ORT not in text


def test_zeitfilter_endet_am_listenende(oparl, monkeypatch):
    """Endet die Liste vor dem Sicherheitsabstand, endet der Abruf dort: keine gebildeten Seitenadressen."""
    monkeypatch.setattr(config, "ABRUF_SICHERHEITSABSTAND", 3)
    _zeitfilter_liste(oparl, SEITEN[:4])
    sessionnet.fetch_all()
    assert _seiten(oparl) == [None, "2", "3", "4"]
    z = _statistik("papers")[-1]
    assert (z["grenzseite"], z["ende"], z["ergebnis"]) == ("3", "Listenende", "ok")


def test_zeitfilter_401_im_sicherheitsabstand_und_fortsetzung(oparl, monkeypatch):
    """HTTP 401 auf Seite 6: Abbruch dort (mögliche Sperre), keine weitere Seite; die Fortsetzung beginnt mit Seite 5
    und dem Zustand des Zeitfilters vor Seite 5 und endet wie ein Abruf ohne Unterbrechung."""
    monkeypatch.setattr(config, "ABRUF_SICHERHEITSABSTAND", 3)
    erwartet = _zeitfilter_liste(oparl)
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: 401 if pfad == "/papers" and q.get("page") == "6" else False)
    sessionnet.fetch_all()
    assert _seiten(oparl) == [None, "2", "3", "4", "5", "6"]
    zustand = _zustand()
    assert zustand["sperre_verdacht"]["naechte"] == 1
    fort = zustand["papers_fortsetzung"]
    assert fort["naechste"].endswith("page=5") and fort["zeitfilter"] == {"grenzseite": 3, "ohne_treffer": 1}
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: False)
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert _seiten(oparl) == ["5", "6", "7", "8"]
    assert {p["id"] for p in _jsonl(config.PAPERS)} == erwartet
    z = _statistik("papers")[-1]
    assert (z["modus"], z["grenzseite"], z["ende"], z["ergebnis"]) == ("voll, fortgesetzt", "3", "Zeitfilter", "ok")


def test_unlesbarer_zeitfilter_verwirft_die_fortsetzung(oparl, capsys):
    config.RAW.mkdir(parents=True, exist_ok=True)
    (config.RAW / "papers.teil.jsonl").write_text(json.dumps(oparl.papers[0]) + "\n", encoding="utf-8")
    config.ZUSTAND.write_text(json.dumps({"papers_fortsetzung": {
        "naechste": f"{oparl.b}/papers?page=2", "seiten": 1, "start": "2026-11-08T22:10:00+00:00",
        "zeitfilter": {"grenzseite": "drei", "ohne_treffer": 0}}}), encoding="utf-8")
    sessionnet.fetch_all()
    assert "Zustand des Zeitfilters unlesbar" in capsys.readouterr().err
    assert _statistik("papers")[-1]["modus"] == "voll, Fortsetzung verworfen"


def test_sicherheitsabstand_mindestens_eine_seite(oparl, monkeypatch):
    monkeypatch.setattr(config, "ABRUF_SICHERHEITSABSTAND", 0)
    with pytest.raises(ValueError, match="RATSATLAS_SICHERHEITSABSTAND"):
        sessionnet.fetch_all()
    assert oparl.anfragen == []


def test_im_zeitraum():
    s = sessionnet.im_zeitraum
    assert s({"date": "2020-01-01"}) and not s({"date": "2019-12-31"})
    assert s({"date": "2020-03-01", "created": "2017-12-21T09:21:46+01:00"})          # date ist maßgeblich
    assert not s({"date": "2013-05-01", "created": "2020-02-01T09:00:00+01:00"})
    assert s({"created": "2019-12-31T23:30:00+00:00"})        # ohne date: created, Kalendertag in Berlin (01.01.)
    assert not s({"date": "kaputt", "created": "2019-12-31T22:30:00+00:00"})
    assert s({}) and s({"date": None, "created": "kaputt"})   # nicht entscheidbar: behalten


def test_inkrementell_nur_vorlagen_im_zeitraum(oparl):
    """Auch inkrementell gilt der Zeitraum: geänderte ältere Vorlagen werden verworfen, eine Vorlage, deren date vor
    2020 rückt, verlässt den Stand (zehn Vorlagen, damit die Mengenprüfung der Beratungen, 90 %, nicht greift)."""
    oparl.papers = [oparl.paper(i) for i in range(1, 11)]
    sessionnet.fetch_all()
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    oparl.papers.append(_vorlage(oparl, 11, "2015-03-01T10:00:00+01:00", "2015-03-10", modified=jetzt))
    oparl.papers[1] = _vorlage(oparl, 2, oparl.papers[1]["created"], "2019-06-01", modified=jetzt)
    sessionnet.fetch_all()
    ids = {p["id"] for p in _jsonl(config.PAPERS)}
    assert f"{oparl.b}/papers/11" not in ids and f"{oparl.b}/papers/2" not in ids and len(ids) == 9
    z = _statistik("papers")[-1]
    assert (z["modus"], z["ausserhalb_zeitraum"], z["ergebnis"]) == ("inkrementell", "2", "ok")
    assert "abruf_fehler" not in _stand()


# --- (3) Sitzungen --------------------------------------------------------------------------------------------------

def _sitzung(oparl, n, start):
    return {"id": f"{oparl.b}/meetings/{n}", "type": "https://schema.oparl.org/1.1/Meeting", "name": f"Sitzung {n}",
            "start": start, "organization": [f"{oparl.b}/organizations/rat"], "modified": "2026-10-02T08:00:00+02:00",
            "agendaItem": []}


def _sitzungen_einrichten(oparl, monkeypatch, verweise=None):
    """Sieben Sitzungen, neueste zuerst (Seiten 7, 6 | 5, 4 | 3, 2 | 1). Vorlagen ab 2020 verweisen auf 1 (zweimal), 2
    und 6; eine Vorlage von 2015 auf 3. Sitzung 1 liegt lange zurück, Sitzung 2 in der Zukunft."""
    monkeypatch.setattr(config, "ABRUF_SITZUNGSSEITEN", 2)
    oparl.form = "koeln"
    zukunft = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(timespec="seconds")
    starts = {1: "2020-05-04T17:00:00+02:00", 2: zukunft, 3: "2015-05-04T17:00:00+02:00"}
    oparl.meetings = [_sitzung(oparl, n, starts.get(n, "2027-03-01T17:00:00+01:00")) for n in range(1, 8)]
    oparl.meetings[0]["agendaItem"] = [{"id": f"{oparl.b}/agendaitems/1", "number": "3", "name": "TOP",
                                        "result": "ungeändert beschlossen", "public": True}]
    verweise = verweise or {1: 1, 2: 1, 3: 2, 4: 6}
    oparl.papers = [_vorlage(oparl, 5, "2015-03-01T10:00:00+01:00", "2015-03-10", sitzung=3)] + [
        _vorlage(oparl, i, f"2026-09-0{i}T10:00:00+02:00", "2026-09-20", sitzung=verweise[i]) for i in sorted(verweise)]


def _einzeln(oparl):
    return [p for p, _, _ in oparl.anfragen if p.startswith("/meetings/")]


def test_sitzungen_erste_seiten_und_verwiesene_einzeln(oparl, monkeypatch):
    _sitzungen_einrichten(oparl, monkeypatch)
    sessionnet.fetch_all()
    assert _seiten(oparl, "/meetings") == [None, "2"]                     # nicht die ganze Liste (4 Seiten)
    assert sorted(_einzeln(oparl)) == ["/meetings/1", "/meetings/2"]      # 6 aus der Liste, 3 nur von 2015, 1 einmal
    ids = {m["id"].rsplit("/", 1)[1] for m in json.loads(config.MEETINGS.read_text(encoding="utf-8"))}
    assert ids == {"7", "6", "5", "4", "1", "2"}
    beratungen = {b["uri"]: b for b in _jsonl(config.BERATUNGEN)}
    b1 = beratungen[f"{oparl.b}/consultations/1"]
    assert b1["meeting"]["uri"] == f"{oparl.b}/meetings/1" and b1["agendaItem"]["result"] == "ungeändert beschlossen"
    z = _statistik("meetings")[-1]
    assert (z["seiten"], z["einzeln"], z["objekte"], z["ende"], z["ergebnis"]) == ("2", "2", "6", "Seitenzahl", "ok")
    # nächster Lauf: aus dem Cache, nur die künftige Sitzung 2 erneut (Sitzung 1 liegt mehr als 60 Tage zurück)
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert _seiten(oparl, "/meetings") == [None, "2"] and _einzeln(oparl) == ["/meetings/2"]
    assert "abruf_fehler" not in _stand()


def test_sitzung_404_und_fremder_host(oparl, monkeypatch):
    _sitzungen_einrichten(oparl, monkeypatch, {1: 9, 2: "http://example.invalid/meetings/5", 3: 1})
    sessionnet.fetch_all()
    assert sorted(_einzeln(oparl)) == ["/meetings/1", "/meetings/9"]
    z = _statistik("meetings")[-1]
    assert z["ergebnis"] == "ok; 1 Sitzung mit HTTP 404/410 übersprungen; 1 Verweis auf einen anderen Host nicht angefragt"
    assert list(_zustand()["sitzungen_fehlend"]) == [f"{oparl.b}/meetings/9"]
    assert "abruf_fehler" not in _stand() and "abruf_ok" in _stand()
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert "/meetings/9" not in _einzeln(oparl)                          # erst nach SITZUNG_FEHLT_TAGE erneut


def test_sitzungen_abbruch_und_fortsetzung_aus_dem_cache(oparl, monkeypatch):
    """HTTP 401 bei zwei Sitzungen in Folge: Abbruch (mögliche Sperre), Geholtes bleibt im Cache; der nächste Lauf holt
    nur, was fehlt (Sitzung 1 insgesamt einmal), und die beiden abgewiesenen erneut (am Ende)."""
    _sitzungen_einrichten(oparl, monkeypatch, {1: 1, 2: 1, 3: 2, 4: 3})
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: 401 if pfad in ("/meetings/2", "/meetings/3") else False)
    sessionnet.fetch_all()
    assert _einzeln(oparl) == ["/meetings/3", "/meetings/2"]   # neueste Vorlage zuerst; Sitzung 1 nicht mehr
    assert _zustand()["sperre_verdacht"]["naechte"] == 1 and "abruf_fehler" in _stand()
    roh = {m["id"] for m in _jsonl(config.RAW / "meetings_roh.jsonl")}
    assert {f"{oparl.b}/meetings/{n}" for n in (7, 6, 5, 4)} <= roh
    assert _statistik("meetings")[-1]["ergebnis"].startswith("abbruch: 2 Sitzungen in Folge abgewiesen")
    assert all(v["serie"] for v in _zustand()["sitzungen_verweigert"].values())
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: False)
    sessionnet.fetch_all()
    einzeln = _einzeln(oparl)
    assert einzeln.count("/meetings/1") == 1 and einzeln.count("/meetings/2") == 2 and einzeln.count("/meetings/3") == 2
    assert "abruf_fehler" not in _stand() and "sitzungen_verweigert" not in _zustand()
    assert {m["id"].rsplit("/", 1)[1] for m in json.loads(config.MEETINGS.read_text(encoding="utf-8"))} == {
        "7", "6", "5", "4", "1", "2", "3"}


@pytest.mark.parametrize("code", [401, 403])
def test_einzelne_sitzung_abgewiesen_kein_stillstand(oparl, monkeypatch, code):
    """Eine einzelne Sitzung antwortet dauerhaft mit 401/403 (etwa nicht öffentlich): vermerkt, der Lauf endet
    vollständig (meetings.json, Beratungen), kein Sperrverdacht; erneut erst nach der Frist."""
    _sitzungen_einrichten(oparl, monkeypatch)
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: code if pfad == "/meetings/1" else False)
    sessionnet.fetch_all()
    assert sorted(_einzeln(oparl)) == ["/meetings/1", "/meetings/2"]
    z = _zustand()
    assert "sperre_verdacht" not in z and list(z["sitzungen_verweigert"]) == [f"{oparl.b}/meetings/1"]
    assert "abruf_fehler" not in _stand() and config.MEETINGS.exists() and config.BERATUNGEN.exists()
    assert "1 Sitzung mit HTTP 401/403 übersprungen" in _statistik("meetings")[-1]["ergebnis"]
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert "/meetings/1" not in _einzeln(oparl)
    spaeter = datetime.now(timezone.utc) + timedelta(days=config.SITZUNG_FEHLT_TAGE, hours=1)
    monkeypatch.setattr(abruf, "uhr", lambda: spaeter)
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert _einzeln(oparl)[-1] == "/meetings/1" and "sperre_verdacht" not in _zustand()


def test_zwei_dauerhaft_abgewiesene_sitzungen_kein_dauerhafter_stillstand(oparl, monkeypatch):
    """Zwei benachbarte Sitzungen antworten dauerhaft mit 401: Der erste Lauf bricht ab (mögliche Sperre), der nächste
    fragt sie erneut am Ende an; weisen sie wieder ab, zählt das nicht als neue Serie: Der Lauf endet vollständig."""
    _sitzungen_einrichten(oparl, monkeypatch, {1: 1, 2: 1, 3: 2, 4: 3})
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: 401 if pfad in ("/meetings/2", "/meetings/3") else False)
    sessionnet.fetch_all()
    assert _zustand()["sperre_verdacht"]["naechte"] == 1 and "abruf_fehler" in _stand()
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert _einzeln(oparl) == ["/meetings/1", "/meetings/3", "/meetings/2"]   # die abgewiesenen am Ende
    z = _zustand()
    assert "abruf_fehler" not in _stand() and "sperre_verdacht" not in z and config.MEETINGS.exists()
    assert not any(v["serie"] for v in z["sitzungen_verweigert"].values())


def test_sitzungen_404_in_folge_abbruch(oparl, monkeypatch):
    """Antworten mehrere Einzelabrufe in Folge mit 404 (Einzeladresse womöglich falsch), endet der Lauf nach
    config.SITZUNG_FEHLT_IN_FOLGE Anfragen statt alle Verweise anzufragen; kein Sperrverdacht."""
    monkeypatch.setattr(config, "SITZUNG_FEHLT_IN_FOLGE", 2)
    _sitzungen_einrichten(oparl, monkeypatch, {1: 11, 2: 12, 3: 13, 4: 14})
    sessionnet.fetch_all()
    assert _einzeln(oparl) == ["/meetings/14", "/meetings/13"]
    z = _zustand()
    assert "sperre_verdacht" not in z and "abruf_fehler" in _stand()
    assert "Einzeladresse der Sitzungen prüfen" in _statistik("meetings")[-1]["ergebnis"]


def test_kuenftige_sitzung_aus_der_liste_wird_erneuert(oparl, monkeypatch):
    """Eine künftige Sitzung nur aus der Liste (keine Vorlage verweist auf sie) rutscht von den ersten Seiten; wird sie
    abgesagt, holt der nächste Lauf sie einzeln, statt den alten Stand weiterzugeben."""
    _sitzungen_einrichten(oparl, monkeypatch)
    sessionnet.fetch_all()
    sieben = next(m for m in oparl.meetings if m["id"].endswith("/meetings/7"))
    sieben["cancelled"] = True
    oparl.meetings += [_sitzung(oparl, n, "2027-04-01T17:00:00+02:00") for n in (8, 9, 10, 11)]   # vorn
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert "/meetings/7" in _einzeln(oparl)
    m7 = next(m for m in json.loads(config.MEETINGS.read_text(encoding="utf-8")) if m["id"].endswith("/meetings/7"))
    assert m7["cancelled"] is True
    assert "künftige Sitzung" in _statistik("meetings")[-1]["ergebnis"]
    # Obergrenze je Lauf
    monkeypatch.setattr(config, "SITZUNG_KUENFTIGE_HOECHSTENS", 0)
    oparl.meetings += [_sitzung(oparl, n, "2027-05-01T17:00:00+02:00") for n in (12, 13, 14, 15)]
    oparl.anfragen.clear()
    sessionnet.fetch_all()
    assert sorted(_einzeln(oparl)) == ["/meetings/2", "/meetings/6"]   # nur verwiesene, keine aus der Liste


def test_zeitfilter_vorlagen_ohne_datum_setzen_die_zaehlung_nicht_zurueck():
    """Vorlagen ohne lesbares date und created werden behalten, verlängern den Sicherheitsabstand aber nicht."""
    from datetime import date
    zf = sessionnet.Zeitfilter(stichtag=date(2020, 1, 1), abstand=2, grenzseite=3)
    alt = {"date": "2019-05-01", "created": "2019-04-20T10:00:00+02:00"}
    ohne = {"date": "kaputt"}
    assert sessionnet.im_zeitraum(ohne)
    assert not zf.seite([alt, ohne], 4) and zf.ohne_treffer == 1
    assert zf.seite([alt, ohne], 5) and zf.ohne_treffer == 2
    zf = sessionnet.Zeitfilter(stichtag=date(2020, 1, 1), abstand=2, grenzseite=3)
    assert not zf.seite([alt, {"date": "2020-02-01"}], 4) and zf.ohne_treffer == 0


def test_sitzungsverweise():
    papers = [{"consultation": [{"meeting": "m/1"}, {"meeting": "m/2"}, {"meeting": ["m/9"]}, "kaputt"]},
              {"consultation": [{"meeting": "m/1"}, {}]}, {"deleted": True, "consultation": [{"meeting": "m/3"}]},
              {"consultation": None}]
    assert sessionnet.sitzungsverweise(papers) == ["m/1", "m/2"]


# --- (4) Schätzung ohne Netz ----------------------------------------------------------------------------------------

def test_schaetzung_aus_den_messwerten(monkeypatch, capsys):
    monkeypatch.setattr(abruf, "get_json", lambda *a, **k: pytest.fail("Schätzung ohne Netz"))
    monkeypatch.setattr(config, "ABRUF_SICHERHEITSABSTAND", 5)
    monkeypatch.setattr(config, "ABRUF_SITZUNGSSEITEN", 2)
    monkeypatch.setattr(config, "ABRUF_ABSTAND", 2.0)
    monkeypatch.setattr(config, "ABRUF_ZEITFENSTER", "23-1")
    s = sessionnet.schaetzung()
    assert [p["anfragen"] for p in s["posten"]] == [1, 3, 92, 2] and s["anfragen"] == 98
    # 1 × (2 + 0,52) + 3 × (2 + 1,83) + 92 × (2 + 4,61) + 2 × (2 + 1,95) Sekunden
    assert s["sekunden"] == round(2.52 + 3 * 3.83 + 92 * 6.61 + 2 * 3.95) == 630
    assert (s["fenster_sekunden"], s["naechte"]) == (7200, 1)
    t = sessionnet.schaetzung(2000)
    assert t["anfragen"] == 2098 and t["sekunden"] == round(630.03 + 2000 * 3.95) and t["naechte"] == 2
    assert any("offen" in a for a in s["annahmen"]) and any("gesetzt: 2000" in a for a in t["annahmen"])
    monkeypatch.delenv("RATSATLAS_SITZUNGEN", raising=False)
    sessionnet.schaetzung_ausgeben()
    aus = capsys.readouterr().out
    assert "98 Anfragen" in aus and "keine Messwerte" in aus and "grenzseite = 87" in aus


def test_schritt_schaetzung(tmp_path):
    """`python -m pipeline schaetzung` ohne Freigabe und ohne Netz."""
    umgebung = {k: v for k, v in __import__("os").environ.items() if not k.startswith("RATSATLAS_")
                or k == "RATSATLAS_SPERRE"}
    r = subprocess.run([sys.executable, "-m", "pipeline", "schaetzung"], cwd=ROOT, capture_output=True, text=True,
                       timeout=120, env={**umgebung, "RATSATLAS_SITZUNGEN": "1500"})
    assert r.returncode == 0, r.stderr
    assert "1500 Anfragen" in r.stdout and "1598 Anfragen" in r.stdout
