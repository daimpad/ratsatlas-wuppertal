"""Messstufen der Wuppertaler OParl-API (explore/STUFEN.md) gegen den lokalen Testserver explore/testserver.py
(Wuppertaler Antwortform laut CLAUDE.md 3.1, erfundene Daten); abgeleitet aus ratsatlas-koeln @d609111:
Anzahl der Anfragen je Kommando, Obergrenze RATSATLAS_MAX_ANFRAGEN (Abbruch statt Überschreitung), Cache-Treffer
zählen nicht, Folgeseiten ohne URL-Kodierung, Seitengrenzen, Abbruchkriterien (auch Mindestabstand innerhalb eines
Prozesses und zwischen zwei Prozessen, Antworten eines lokalen Schein-Proxys auf CONNECT, abgeschnittene oder
unlesbare Antworten, Sperre gegen gleichzeitige Prozesse, keine Anfrage nach einem Abbruch), Abruf von http-IDs über
https, Umfang per Bisektion, Stichprobe über verteilte Seiten, Zerlegung von paperType, PDF-Köpfe aus auxiliaryFile,
Probelauf und Auswertung; explore/geodaten.py ohne Netz (Mindestwerte, Obergrenze, Kontakt, Freigabe, Zeitfenster,
Ende nach möglicher Sperre; Ableitungen aus dem Cache).
Läuft offline: Anfragen gehen nur an 127.0.0.1 und 127.0.0.2 (gilt nicht als lokal und steht in Tests für die Stadt);
Adressen der Stadt werden nie aufgerufen (fremde Adressen nur unter example.invalid, über einen lokalen Schein-Proxy)."""
import argparse
import collections
import contextlib
import csv
import datetime as dt
import importlib
import io
import json
import os
import re
import shutil
import signal
import socketserver
import ssl
import statistics
import subprocess
import sys
import threading
import time
import types
import urllib.error
import urllib.parse
import warnings
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

EXPLORE = Path(__file__).resolve().parents[1] / "explore"
sys.path.insert(0, str(EXPLORE))
probelauf = importlib.import_module("probelauf")
testserver = importlib.import_module("testserver")


@pytest.fixture
def server():
    with testserver.Testserver() as s:
        yield s


def lauf(server, tmp_path, kommando, *parameter, obergrenze=0, cache="cache", **zusatz):
    return probelauf.messung(server, tmp_path / cache, tmp_path / "ergebnisse", kommando, parameter, obergrenze,
                             **zusatz)


def tsv(datei):
    with open(datei, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def protokoll(tmp_path, cache="cache"):
    return tsv(tmp_path / cache / "abrufe.tsv")


def test_test_stellt_genau_drei_anfragen(server, tmp_path):
    m = lauf(server, tmp_path, "test", obergrenze=3)
    assert m["rc"] == 0, m["stderr"]
    assert m["server"] == 3 and [p for p, *_ in server.anfragen] == [
        "/oparl/system", "/oparl/bodies/0001", "/oparl/bodies/0001/papers"]
    assert all(ua.startswith("ratsatlas-wuppertal-explore/0.1 (+https://github.com/daimpad/ratsatlas-wuppertal")
               for _, _, ua, _ in server.anfragen)
    assert [z["quelle"] for z in protokoll(tmp_path)] == ["netz"] * 3
    assert (m["lauf"]["netz"], m["lauf"]["cache"], m["lauf"]["ergebnis"]) == ("3", "0", "ok")
    werte = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_test.tsv")}
    assert werte[("paper", "pagination.elementsPerPage")] == "100" and werte[("paper", "objekte_erste_seite")] == "100"
    assert werte[("paper", "links.next")].endswith("/papers?page=2") and werte[("paper", "links.next_schema")] == "http"
    # Testdaten wie in Wuppertal (Stufe 1, 10.11.2026): nach created, nicht nach date sortiert; Erwartung aus den Daten
    daten = [server.daten.datum(k) for k in range(100)]
    v = sum(1 for a, b in zip(daten, daten[1:]) if b > a)
    assert v > 0 and werte[("paper", "id_schema")] == "http"
    assert werte[("paper", "date_absteigend_erste_seite")] == f"nein ({v} Verletzungen) (n = 100)"
    assert werte[("body", "name")] == "[Testdaten] Instance 0001"


def test_test_unveraendert_bei_sortierten_daten(tmp_path):
    """Stufe 1 bleibt gleich: Mit date = Tag von created (Testdaten ohne Versatz) urteilt test() wie vor der Umstellung
    der Testdaten „ja (n = 100)“, mit denselben drei Anfragen."""
    with testserver.Testserver(date_versatz=False) as s:
        m = lauf(s, tmp_path, "test", obergrenze=3)
        assert m["rc"] == 0 and m["server"] == 3, m["stderr"]
        assert [p for p, *_ in s.anfragen] == ["/oparl/system", "/oparl/bodies/0001", "/oparl/bodies/0001/papers"]
    werte = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_test.tsv")}
    assert werte[("paper", "date_absteigend_erste_seite")] == "ja (n = 100)"


def test_cache_treffer_zaehlen_nicht(server, tmp_path):
    assert lauf(server, tmp_path, "test", obergrenze=3)["rc"] == 0
    zweiter = lauf(server, tmp_path, "test", obergrenze=1)        # alles aus dem Cache
    assert zweiter["rc"] == 0 and zweiter["server"] == 0
    assert (zweiter["lauf"]["netz"], zweiter["lauf"]["cache"]) == ("0", "3")
    # kennzahlen braucht 8 Anfragen, davon 3 aus dem Cache von test: Obergrenze 5 reicht
    k = lauf(server, tmp_path, "kennzahlen", obergrenze=5)
    assert k["rc"] == 0, k["stderr"]
    assert k["server"] == 5 and (k["lauf"]["netz"], k["lauf"]["cache"]) == ("5", "3")


def test_kennzahlen_stellt_acht_anfragen(server, tmp_path):
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8)
    assert m["rc"] == 0, m["stderr"]
    assert m["server"] == 8
    assert [p.rsplit("/", 1)[1] for p, *_ in server.anfragen] == ["system", "0001", "papers", "meetings",
                                                                     "organizations", "people", "papers", "papers"]
    status = [s for *_, s in server.anfragen]
    assert status.count(404) == 1 and status.count(200) == 7          # nur der URL-kodierte Vergleich
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv")
             if z["objekt"] == "paper"}
    assert werte["test modified_since URL-kodiert"] == "Parameter abgelehnt (HTTP 404)"
    seit = next(f for f in werte if f.startswith("test modified_since=") and "+00:00" in f)
    assert "filter_wirksam=ja" in werte[seit]
    assert not any("created_since" in f or "limit" in f for f in werte)   # gegenüber Köln entfallen
    assert werte["pagination.totalElements"] == "fehlt" and werte["pagination.elementsPerPage"] == "100"
    # System-Objekt: Kontaktfelder nur als „vorhanden“/„leer“, nie die (hier erfundenen) Werte (CLAUDE.md 2 und 3.1)
    system = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv")
              if z["objekt"] == "system"}
    assert server.daten.system()["contactEmail"] and server.daten.system()["contactName"]
    assert (system["contactEmail"], system["contactName"]) == ("vorhanden (Domain example.invalid)", "vorhanden")
    for datei in (tmp_path / "ergebnisse").iterdir():
        text = datei.read_text(encoding="utf-8")
        assert "testperson" not in text and "Kontaktperson" not in text, datei.name


@pytest.mark.parametrize("kommando, obergrenze", [("kennzahlen", 5), ("test", 2)])
def test_obergrenze_bricht_ab_statt_zu_ueberschreiten(server, tmp_path, kommando, obergrenze):
    m = lauf(server, tmp_path, kommando, obergrenze=obergrenze)
    assert m["rc"] == 2 and "RATSATLAS_MAX_ANFRAGEN" in m["stderr"]
    assert m["server"] == obergrenze and m["lauf"]["netz"] == str(obergrenze)
    assert m["lauf"]["ergebnis"] == "abbruch (obergrenze)"
    datei = "oparl_kennzahlen.tsv" if kommando == "kennzahlen" else "oparl_test.tsv"
    teil = tsv(tmp_path / "ergebnisse" / datei)                       # Teilergebnis mit Abbruchvermerk
    assert teil[-1]["feld"] == "abbruch" and "Obergrenze" in teil[-1]["wert"]


def test_folgeseiten_ueber_links_next_ohne_url_kodierung(server, tmp_path):
    m = lauf(server, tmp_path, "sitzungen", "--seiten", "3", obergrenze=4)
    assert m["rc"] == 0, m["stderr"]
    assert m["server"] == 4                                            # Body + 3 Seiten
    seiten = [q for p, q, _, s in server.anfragen if p.endswith("/meetings")]
    assert seiten == ["", "page=2", "page=3"]
    werte = {z["result"]: z["anzahl"] for z in tsv(tmp_path / "ergebnisse" / "oparl_top_ergebnisse.tsv")}
    assert werte["Sitzungen insgesamt"] == "300" and int(werte["TOPs mit result"]) < int(werte["TOPs insgesamt"])
    # Zeitraum je Seite, künftige Sitzungen, Sortierung nach start, result getrennt nach vergangen/künftig
    sitz = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_sitzungen.tsv")}
    assert sitz["start frühestes"] == "2020-01-06T17:00:00+01:00" and sitz["Sitzungen insgesamt"] == "300"
    assert sitz["Sortierung nach start"].startswith("aufsteigend nach start (3 Seiten geprüft")
    assert int(sitz["Sitzungen vergangen"]) + int(sitz["Sitzungen künftig"]) == 300
    assert sitz["TOPs mit result (vergangen)"] == werte["TOPs mit result"] or sitz["Sitzungen künftig"] != "0"
    seiten = tsv(tmp_path / "ergebnisse" / "oparl_sitzungen_seiten.tsv")
    assert [z["seite"] for z in seiten] == ["1", "2", "3"] and all(z["reihenfolge"] == "aufsteigend" for z in seiten)
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "Sitzungen (sitzungen): 300 erfasst, start 2020-01-06T17:00:00+01:00 bis " in aus
    assert "Sortierung: aufsteigend nach start" in aus


def test_organisationen_haben_eine_seitengrenze(server, tmp_path):
    m = lauf(server, tmp_path, "organisationen", obergrenze=10)
    assert m["rc"] == 0 and m["server"] == 6                           # Body + Vorgabe 5 Seiten
    liste = tsv(tmp_path / "ergebnisse" / "oparl_listen.tsv")[-1]
    assert (liste["seiten"], liste["objekte"], liste["ende"]) == ("5", "500", "Seitengrenze 5")
    # ausdrücklich ohne Grenze: bis zum Ende von links.next; die ersten Seiten kommen aus dem Cache
    m = lauf(server, tmp_path, "organisationen", "--seiten", "0", obergrenze=10)
    assert m["rc"] == 0 and m["server"] == 2 and m["lauf"]["cache"] == "6"
    liste = tsv(tmp_path / "ergebnisse" / "oparl_listen.tsv")[-1]
    assert (liste["seiten"], liste["objekte"], liste["ende"]) == ("7", "650", "Ende der Liste (kein links.next)")


def test_organisationen_nach_praefix_und_typ(server, tmp_path):
    """Präfixe der Kennungen (organizations/gr/<n>, organizations/at/<n>, weitere) und organizationType je Präfix;
    Kennungen unverändert (http://)."""
    m = lauf(server, tmp_path, "organisationen", "--seiten", "0", obergrenze=8)
    assert m["rc"] == 0, m["stderr"]
    orgs = tsv(tmp_path / "ergebnisse" / "oparl_organisationen.tsv")
    assert {z["praefix"] for z in orgs} == {"gr", "at", "zz"} and all(z["id"].startswith("http://") for z in orgs)
    typen = {(z["praefix"], z["organizationType"]): int(z["anzahl"])
             for z in tsv(tmp_path / "ergebnisse" / "oparl_organisationstypen.tsv")}
    assert typen[("at", "[Testdaten] Verwaltung")] == 60 and typen[("zz", "(leer)")] == 10
    assert typen[("gr", "[Testdaten] Gremium")] + typen[("gr", "(leer)")] == 580
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "Organisationen: 650 erfasst; je Präfix: gr 580, at 60, zz 10" in aus
    om = importlib.import_module("oparl_messung")
    assert om._praefix("http://oparl.wuppertal.de/oparl/bodies/0001/organizations/at/12") == "at"
    assert om._praefix("http://x/organizations/12") == "(ohne Präfix)"


def test_429_stoppt_ohne_wiederholung(server, tmp_path):
    server.stoerung = lambda pfad, abfrage: 429 if pfad.endswith("/meetings") else None
    m = lauf(server, tmp_path, "sitzungen", obergrenze=3)
    assert m["rc"] == 2 and m["server"] == 2 and m["lauf"]["ergebnis"] == "abbruch (server)"
    assert [z["status"] for z in protokoll(tmp_path)] == ["200", "429"]


def test_langsame_antwort_stoppt(server, tmp_path):
    server.verzoegerung = 0.3
    m = lauf(server, tmp_path, "test", obergrenze=3, RATSATLAS_MAX_DAUER="0.1")
    assert m["rc"] == 2 and m["server"] == 1 and m["lauf"]["ergebnis"] == "abbruch (langsam)"


def test_html_statt_json_stoppt(server, tmp_path):
    server.stoerung = lambda pfad, abfrage: 200 if pfad.endswith("/bodies/0001") else None
    m = lauf(server, tmp_path, "test", obergrenze=3)
    assert m["rc"] == 1 and m["server"] == 2 and m["lauf"]["ergebnis"].startswith("fehler (JSONDecodeError")


def test_ohne_information_der_stadt_keine_anfrage(server, tmp_path):
    fremd = {"RATSATLAS_OPARL_SYSTEM": "http://example.invalid/oparl/system",
             "RATSATLAS_OPARL_BODY": "http://example.invalid/oparl/bodies/x"}
    m = lauf(server, tmp_path, "test", obergrenze=3, **fremd)
    assert m["rc"] == 1 and "nicht freigegeben" in m["stderr"]
    # freigegeben, aber außerhalb des Zeitfensters
    h = dt.datetime.now(ZoneInfo("Europe/Berlin")).hour
    m = lauf(server, tmp_path, "test", obergrenze=3, RATSATLAS_MESSUNG_FREIGEGEBEN="ja",
             RATSATLAS_ZEITFENSTER=f"{(h + 2) % 24}-{(h + 3) % 24}", **fremd)
    assert m["rc"] == 1 and "Zeitfenster" in m["stderr"]
    assert server.anfragen == [] and not (tmp_path / "cache" / "abrufe.tsv").exists()


def test_schleifenschutz_in_links_next(monkeypatch):
    om = importlib.import_module("oparl_messung")
    monkeypatch.setattr(om, "_LISTEN", [])
    seiten = {"http://127.0.0.1/l": {"data": [{"id": "a"}], "links": {"next": "http://127.0.0.1/l?page=2"}},
              "http://127.0.0.1/l?page=2": {"data": [{"id": "a"}], "links": {"next": "http://127.0.0.1/l?page=3"}}}
    monkeypatch.setattr(om, "_hole", lambda url, endung=".json", max_bytes=None: json.dumps(seiten[url]).encode())
    assert [nr for nr, _ in om._seiten("http://127.0.0.1/l", name="x")] == [1]
    assert om._LISTEN[-1]["ende"] == "Seite ohne neue Kennungen"
    seiten["http://127.0.0.1/l"]["links"]["next"] = "http://127.0.0.1/l"
    assert [nr for nr, _ in om._seiten("http://127.0.0.1/l", name="y")] == [1]
    assert om._LISTEN[-1]["ende"] == "links.next wiederholt"


def test_weiterleitung_wird_nicht_verfolgt(server, tmp_path):
    fremd = "http://example.invalid/oparl/bodies/x"
    server.weiterleitungen["/oparl/bodies/0001"] = (301, fremd)
    m = lauf(server, tmp_path, "test", obergrenze=3)
    assert m["rc"] == 2 and m["lauf"]["ergebnis"] == "abbruch (weiterleitung)" and fremd in m["lauf"]["meldung"]
    assert m["server"] == 2 and m["lauf"]["netz"] == "2"               # die Weiterleitung zählt als eine Anfrage
    z = protokoll(tmp_path)[-1]
    assert (z["status"], z["ziel"], z["quelle"]) == ("301", fremd, "netz")
    # auch ein Ziel auf demselben Server wird nicht abgerufen
    server.weiterleitungen = {"/oparl/system": (302, "/oparl/bodies/0001")}
    m = lauf(server, tmp_path, "test", obergrenze=3, cache="cache2")
    assert m["rc"] == 2 and m["server"] == 1
    assert [p for p, *_ in server.anfragen][-1] == "/oparl/system"
    assert protokoll(tmp_path, "cache2")[-1]["ziel"].endswith("/oparl/bodies/0001")
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache2", tmp_path / "ergebnisse")
    assert "Status 302 × 1 (Weiterleitung nach http://127.0.0.1:" in aus


def test_abstand_nach_ende_der_antwort_und_zeit_mit_zone(server, tmp_path):
    server.verzoegerung = 0.25
    m = lauf(server, tmp_path, "test", obergrenze=3, RATSATLAS_ABSTAND="0.3")
    assert m["rc"] == 0, m["stderr"]
    abstaende = [b - a for a, b in zip(server.eingang, server.eingang[1:])]
    assert len(abstaende) == 2 and min(abstaende) >= 0.5               # Antwortzeit 0,25 s + Abstand 0,3 s
    assert all(re.search(r"T\d\d:\d\d:\d\d[+-]\d\d:\d\d$", z["zeit"]) for z in protokoll(tmp_path))


def test_altes_protokoll_bekommt_neuen_kopf(server, tmp_path):
    (tmp_path / "cache").mkdir()
    alt = "zeit\turl\tstatus\tbytes\tdauer_s\tquelle\n2026-11-04T10:46:34\thttps://example.invalid/a\t200\t1\t0.10\tnetz\n"
    (tmp_path / "cache" / "abrufe.tsv").write_text(alt, encoding="utf-8")
    assert lauf(server, tmp_path, "test", obergrenze=3)["rc"] == 0
    zeilen = protokoll(tmp_path)
    assert list(zeilen[0]) == ["zeit", "url", "status", "bytes", "dauer_s", "quelle", "ziel"]
    assert zeilen[0]["url"] == "https://example.invalid/a" and len(zeilen) == 4


def test_strenge_vorgaben_fuer_anfragen_an_die_stadt(server, tmp_path, monkeypatch):
    om = importlib.import_module("oparl_messung")
    werte, fehler = om.sichere_vorgaben({"RATSATLAS_MAX_ANFRAGEN": "3", "RATSATLAS_KONTAKT": "kontakt@example.invalid"})
    assert fehler == [] and werte == {"wiederholungen": 0, "max_dauer": 5.0, "max_anfragen": 3, "abstand": 2.0}
    _, fehler = om.sichere_vorgaben({})
    assert any("RATSATLAS_MAX_ANFRAGEN" in f for f in fehler) and any("RATSATLAS_KONTAKT" in f for f in fehler)
    for zusatz, name in (({"RATSATLAS_WIEDERHOLUNGEN": "4"}, "WIEDERHOLUNGEN"), ({"RATSATLAS_MAX_DAUER": "0"}, "MAX_DAUER"),
                         ({"RATSATLAS_MAX_DAUER": "30"}, "MAX_DAUER"),
                         ({"RATSATLAS_KONTAKT": "<Kontaktadresse des Auftraggebers>"}, "KONTAKT")):
        env = {"RATSATLAS_MAX_ANFRAGEN": "3", "RATSATLAS_KONTAKT": "kontakt@example.invalid", **zusatz}
        assert any(name in f for f in om.sichere_vorgaben(env)[1]), zusatz
    # als Prozess: freigegeben und im Zeitfenster, aber Platzhalter im Kontakt und Wiederholungen → keine Anfrage
    fremd = {"RATSATLAS_OPARL_SYSTEM": "http://example.invalid/oparl/system",
             "RATSATLAS_OPARL_BODY": "http://example.invalid/oparl/bodies/x", "RATSATLAS_MESSUNG_FREIGEGEBEN": "ja",
             "RATSATLAS_KONTAKT": "<Kontaktadresse des Auftraggebers>", "RATSATLAS_WIEDERHOLUNGEN": "4"}
    m = lauf(server, tmp_path, "test", obergrenze=3, **fremd)
    assert m["rc"] == 1 and "RATSATLAS_KONTAKT" in m["stderr"] and "RATSATLAS_WIEDERHOLUNGEN" in m["stderr"]
    assert server.anfragen == [] and not (tmp_path / "cache" / "abrufe.tsv").exists()
    # vor jeder Anfrage an die Stadt: ohne strenge Werte kein Abruf
    monkeypatch.setenv("RATSATLAS_MESSUNG_FREIGEGEBEN", "ja")
    monkeypatch.setenv("RATSATLAS_ZEITFENSTER", "")
    monkeypatch.setattr(om.abruf, "WIEDERHOLUNGEN", 4)
    monkeypatch.setattr(om, "hole", lambda *a, **k: pytest.fail("darf nicht abrufen"))
    with pytest.raises(om.Abbruch, match="Zeitfenster"):      # leerer Wert gilt für die Stadt als außerhalb
        om._hole("https://oparl.wuppertal.de/oparl/system")
    monkeypatch.setattr(om, "im_zeitfenster", lambda jetzt=None, url=None: True)
    with pytest.raises(om.Abbruch, match="strenge Vorgaben"):
        om._hole("https://oparl.wuppertal.de/oparl/system")


def test_abrufadresse_http_der_stadt_ueber_https():
    """http:// auf Hosts der Stadt wird vor dem Abruf zu https:// (Kennungen der Wuppertaler API beginnen mit http://,
    CLAUDE.md 3.1); Pfad und Abfrage bleiben unverändert, alle übrigen Adressen auch. Cache: ein Eintrag für beide."""
    abruf = importlib.import_module("abruf")
    for alt, neu in (
            ("http://oparl.wuppertal.de/oparl/bodies/0001/papers?page=2",
             "https://oparl.wuppertal.de/oparl/bodies/0001/papers?page=2"),
            ("http://oparl.wuppertal.de/oparl/bodies/0001/papers?modified_since=2026-11-01T00:00:00+00:00",
             "https://oparl.wuppertal.de/oparl/bodies/0001/papers?modified_since=2026-11-01T00:00:00+00:00"),
            ("http://ris.wuppertal.de/x", "https://ris.wuppertal.de/x"),
            ("http://daten.wuppertal.de/a.json", "https://daten.wuppertal.de/a.json"),
            ("http://offenedaten-wuppertal.de/dataset/x", "https://offenedaten-wuppertal.de/dataset/x"),
            ("http://OPARL.Wuppertal.de:80/oparl/system", "https://OPARL.Wuppertal.de/oparl/system")):
        assert abruf.abrufadresse(alt) == neu, alt
    for gleich in ("https://oparl.wuppertal.de/oparl/system", "http://127.0.0.1:8765/oparl/system",
                   "http://example.invalid/x", "http://evilwuppertal.de/x", "http://wuppertal.de.example.invalid/x",
                   "http://oparl.wuppertal.de:8080/x"):
        assert abruf.abrufadresse(gleich) == gleich, gleich
    assert abruf._cachepfad("http://oparl.wuppertal.de/a", ".json") == abruf._cachepfad("https://oparl.wuppertal.de/a",
                                                                                          ".json")
    # führende und folgende Leerzeichen: gleiche Adresse ohne sie (früher entstand ein anderer Host, z. B. …wuppertal.dee)
    for alt in (" http://oparl.wuppertal.de/oparl/bodies/0001/papers?page=2",
                "   http://oparl.wuppertal.de/oparl/bodies/0001/papers?page=2", "\thttp://oparl.wuppertal.de/oparl/"
                "bodies/0001/papers?page=2 "):
        neu = abruf.abrufadresse(alt)
        assert neu == "https://oparl.wuppertal.de/oparl/bodies/0001/papers?page=2", (alt, neu)
        assert urllib.parse.urlsplit(neu).hostname == "oparl.wuppertal.de"
    # Leer- oder Steuerzeichen im Inneren (Tab im Host, Leerzeichen im Pfad): nicht umgeschrieben, nie gesendet
    for innen in ("http://a\t\t\t.wuppertal.de/x", "http://oparl.wuppertal.de/a b", "https://oparl.wuppertal.de/x\ny"):
        assert abruf.abrufadresse(innen) == innen
        with pytest.raises(abruf.Abbruch) as e:
            abruf.hole(innen, ".json")
        assert e.value.art == "adresse"


def _wie_die_stadt_im_prozess(om, monkeypatch, tmp_path):
    """oparl_messung im Testprozess mit Adressen der Stadt: Freigabe gesetzt, Zeitfenster offen, strenge Werte in
    abruf; `hole` wird ersetzt (kein Netz)."""
    monkeypatch.setenv("RATSATLAS_MESSUNG_FREIGEGEBEN", "ja")
    monkeypatch.delenv("RATSATLAS_ZEITFENSTER", raising=False)
    monkeypatch.setattr(om, "im_zeitfenster", lambda jetzt=None, url=None: True)   # Adressen der Stadt: nur so offen
    monkeypatch.delenv("RATSATLAS_PDF_FREIGEGEBEN", raising=False)
    for name, wert in (("WIEDERHOLUNGEN", 0), ("MAX_DAUER", 5.0), ("MAX_ANFRAGEN", 3), ("ABSTAND", 2.0),
                       ("KONTAKT", "kontakt@example.invalid"), ("PROTOKOLL", tmp_path / "cache" / "abrufe.tsv")):
        monkeypatch.setattr(om.abruf, name, wert)
    monkeypatch.setattr(om, "ERG", tmp_path / "erg")
    monkeypatch.setattr(om, "_LISTEN", [])
    monkeypatch.setattr(om, "_sperrfrist_geprueft", False)


def test_http_ids_werden_ueber_https_abgerufen(tmp_path, monkeypatch):
    """Body, Liste und links.next mit http://oparl.wuppertal.de: abgerufen wird über https://, in den Ergebnissen
    stehen die Kennungen unverändert (http://). PDFs ohne Freigabe nicht, auch nicht über https."""
    import argparse
    om = importlib.import_module("oparl_messung")
    _wie_die_stadt_im_prozess(om, monkeypatch, tmp_path)
    body = "http://oparl.wuppertal.de/oparl/bodies/0001"
    liste = f"{body}/organizations"
    seiten = {body: {"id": body, "organization": liste},
              liste: {"data": [{"id": f"{liste}/at/1", "name": "[Testdaten] A"}], "links": {"next": f"{liste}?page=2"}},
              f"{liste}?page=2": {"data": [{"id": f"{liste}/gr/1", "name": "[Testdaten] B"}], "links": {}}}
    geholt = []

    def hole(url, endung="", max_bytes=None):
        geholt.append(url)
        return json.dumps(seiten[url.replace("https://", "http://", 1)]).encode()
    monkeypatch.setattr(om, "hole", hole)
    monkeypatch.setattr(om, "BODY", body)
    om.organisationen(argparse.Namespace(seiten=5))
    assert geholt == ["https://oparl.wuppertal.de/oparl/bodies/0001",
                      "https://oparl.wuppertal.de/oparl/bodies/0001/organizations",
                      "https://oparl.wuppertal.de/oparl/bodies/0001/organizations?page=2"]
    assert [z["id"] for z in tsv(tmp_path / "erg" / "oparl_organisationen.tsv")] == [f"{liste}/at/1", f"{liste}/gr/1"]
    assert (om._LISTEN[-1]["url"], om._LISTEN[-1]["erstes_next"]) == (liste, f"{liste}?page=2")
    with pytest.raises(om.Abbruch, match="PDF-Abruf nicht freigegeben") as e:
        om._hole("http://oparl.wuppertal.de/x/downloadfiles/1.pdf", ".pdf")
    assert "https://oparl.wuppertal.de/x/downloadfiles/1.pdf" in str(e.value) and len(geholt) == 3


def test_seitenform_verteilung_und_bisektion():
    om = importlib.import_module("oparl_messung")
    liste = "http://oparl.wuppertal.de/oparl/bodies/0001/papers"
    form = om.seitenform(liste, {"links": {"next": f"{liste}?page=2"}})
    assert form(1) == liste and form(150) == f"{liste}?page=150"
    assert om.seitenform(liste, {"links": {}}) is None and om.seitenform(liste, {}) is None
    for nxt in (f"{liste}?page=2&limit=100", f"{liste}?seite=2", "http://example.invalid/papers?page=2", f"{liste}/2",
                f"{liste}?page=3"):
        with pytest.raises(om.Abbruch) as e:
            om.seitenform(liste, {"links": {"next": nxt}})
        assert e.value.art == "form", nxt
    assert om.verteilte_seiten(71, 8) == [1, 11, 21, 31, 41, 51, 61, 71]
    assert om.verteilte_seiten(3, 8) == [1, 2, 3] and om.verteilte_seiten(0, 8) == [] and om.verteilte_seiten(9, 1) == [1]
    geholt = []
    assert om._bisektion(lambda n: geholt.append(n) or n, 50, 150, lambda n: n >= 72) == (71, 72)
    assert len(geholt) <= 7 and om.hoechstzahl_umfang() == 17 and om.hoechstzahl_umfang((1, 2), (1, 2)) == 2 + 2 + 2


def test_umfang_bisektion_gesamtzahl_grenze_sortierung(server, tmp_path):
    """umfang: Grenze 01.01.2020 nach created und letzte Seite per Bisektion über ?page=N (Bereiche aus CLAUDE.md
    3.1), Sortierung nach created (maßgeblich) und date (informativ), Abstand date − created, Ende von links.next; ein
    zweiter Lauf kommt ohne Anfrage aus. Die Testdaten sind wie in Wuppertal nach created, nicht nach date sortiert."""
    m = lauf(server, tmp_path, "umfang", obergrenze=17)
    assert m["rc"] == 0, m["stderr"]
    assert m["server"] == 16 and m["lauf"]["netz"] == "16"
    seiten = [q for pf, q, _, _ in server.anfragen if pf.endswith("/papers")]
    assert seiten[0] == "" and all(re.fullmatch(r"page=\d+", q) for q in seiten[1:])
    assert seiten[1:5] == ["page=50", "page=150", "page=100", "page=75"] and "page=240" in seiten and "page=250" in seiten
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_umfang.tsv")}
    d = server.daten
    k0 = next(k for k in range(d.anzahl) if d.erstellt_tag(k) < dt.date(2020, 1, 1))   # erste mit created vor 2020
    assert w[("grenze", "grenzseite")] == str(d.grenzseite()) == "72"
    assert "Sortierung nach created" in w[("grenze", "vorlagen_ab_stichtag")]
    assert w[("grenze", "letzte_seite_ab_stichtag")] == "71" and w[("grenze", "vorlagen_ab_stichtag")].startswith(f"{k0} ")
    assert w[("ende", "letzte_seite")] == "246" and w[("ende", "vorlagen_gesamt")].startswith(f"{d.anzahl} ")
    assert w[("ende", "links_letzte_seite")] == "Schlüssel first,self; next fehlt oder leer"
    assert w[("ende", "links_leere_seite")] == "Seite 247: Objekte 0; Schlüssel first,self; next fehlt oder leer"
    assert w[("sortierung", "created_absteigend")].startswith("ja (") and w[("paper", "id_schema")] == "http"
    assert w[("sortierung", "date_absteigend")].startswith("nein (") and "informativ" in w[("sortierung", "date_absteigend")]
    assert w[("paper", "pagination.totalElements")] == "fehlt"
    infos = tsv(tmp_path / "ergebnisse" / "oparl_umfang_seiten.tsv")
    assert len(infos) == 15 and {z["created_absteigend"] for z in infos} == {"ja", "–"}   # leere Seite 247 ohne Urteil
    assert {z["date_absteigend"][:4] for z in infos} == {"nein", "–"}
    # Abstand date − created aus den abgerufenen Seiten, Erwartung aus den Testdaten
    seiten = sorted(int(z["seite"]) for z in infos)
    ks = [k for n in seiten for k in range((n - 1) * 100, min(n * 100, d.anzahl))]
    abst = [d.versatz(k) for k in ks]
    assert w[("abstand", "date_minus_created_tage")] == (f"min {min(abst)}, Median {format(statistics.median(abst), 'g').replace('.', ',')}, "
                                                         f"max {max(abst)} ({len(ks)} Vorlagen auf {sum(1 for z in infos if int(z['objekte']))} Seiten)")
    assert w[("abstand", "date_vor_created")] == f"{sum(1 for x in abst if x < 0)} von {len(ks)}"
    stichtag = dt.date(2020, 1, 1)
    ueber = [k for k in ks if k // 100 + 1 >= 72 and d.datum(k) >= stichtag > d.erstellt_tag(k)]
    assert ueber and w[("abstand", "date_ab_trotz_created_vor_ab_grenzseite")].startswith(f"{len(ueber)} (Untergrenze")
    assert w[("abstand", "seiten_mit_date_ab_trotz_created_vor")] == "72"
    assert w[("abstand", "groesste_differenz_date_ab_trotz_created_vor")] == f"{max(d.versatz(k) for k in ueber)} Tage"
    assert w[("abstand", "sicherheitsabstand")].startswith("offen (nur ausgewiesen")
    z1 = next(z for z in infos if z["seite"] == "1")
    assert z1["ab_stichtag_created"] == "100" and z1["ohne_created"] == "0" and z1["created_max"] == d.erstellt(0).isoformat()
    m = lauf(server, tmp_path, "umfang", obergrenze=1)                 # alles aus dem Cache
    assert (m["rc"], m["server"], m["lauf"]["netz"], m["lauf"]["cache"]) == (0, 0, "0", "16")
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "| grenze | grenzseite | 72 |" in aus and "| ende | letzte_seite | 246 |" in aus
    assert "Regel Stufe 3 (Grenzseite G als Zahl, Sortierung nach created ja, Lauf ok): erfüllt" in aus


def test_umfang_bereich_passt_nicht_und_unsortiert(tmp_path):
    """Liegt das Gesuchte nicht im Bereich, wird es vermerkt und ohne weitere Anfrage übersprungen; eine Seite, die
    nicht nach created absteigt, ergibt „nein“ (Regel Stufe 3 nicht erfüllt)."""
    with testserver.Testserver(vorlagen=5000) as kurz:                 # 50 Seiten
        m = lauf(kurz, tmp_path, "umfang", obergrenze=17)
        assert m["rc"] == 0 and m["server"] == 4, m["stderr"]           # Body, Seite 1, Seite 50, Seite 240
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_umfang.tsv")}
    assert w[("grenze", "grenzseite")] == "nicht im Bereich (Seite 50 ohne Vorlage mit created ab 2020-01-01)"
    assert w[("ende", "letzte_seite")] == "nicht im Bereich (Seite 240 leer)"
    with testserver.Testserver() as s:
        ordnung = list(range(s.daten.anzahl))
        ordnung[9900:10000] = reversed(ordnung[9900:10000])           # Seite 100 aufsteigend
        s.daten.ordnung = ordnung
        m = lauf(s, tmp_path, "umfang", obergrenze=17, cache="cache2")
    assert m["rc"] == 0, m["stderr"]
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_umfang.tsv")}
    assert w[("sortierung", "created_absteigend")].startswith("nein (1 Seiten innen nicht absteigend")
    regel = importlib.import_module("auswertung").regel_umfang(tsv(tmp_path / "ergebnisse" / "oparl_umfang.tsv"), [])
    assert regel.startswith("nicht erfüllt (Sortierung nach created nein (1 Seiten innen")


def test_stichprobe_streut_ueber_2020_bis_2026(server, tmp_path):
    """stichprobe nach umfang: 8 Seiten gleichmäßig über 1 … G − 1 (G nach created), Vorlagen mit date vor 2020
    verworfen und gezählt, jedes Jahr 2020–2026 vertreten; Sortierung nach created (Regel) und date (informativ),
    date ab 2020 trotz created davor; Abdeckung, Beratungsrollen, Referenzschema; Stichprobendatei ohne Dateiobjekte.
    Mengen aus den (erfundenen) Testdaten berechnet."""
    assert lauf(server, tmp_path, "umfang", obergrenze=17)["rc"] == 0
    vorher = len(server.anfragen)
    m = lauf(server, tmp_path, "stichprobe", obergrenze=9)
    assert m["rc"] == 0, m["stderr"]
    assert (m["server"], m["lauf"]["cache"]) == (6, "3")                # Body, Seite 1 und 71 aus dem Cache
    assert [q for _, q, _, _ in server.anfragen[vorher:]] == [f"page={n}" for n in (11, 21, 31, 41, 51, 61)]
    erg = tmp_path / "ergebnisse"
    bed = {z["feld"]: z["vorhanden"] for z in tsv(erg / "oparl_stichprobe_bedeckung.tsv")}
    d, stichtag = server.daten, dt.date(2020, 1, 1)
    ks = [k for n in (1, 11, 21, 31, 41, 51, 61, 71) for k in range((n - 1) * 100, n * 100)]
    im = [k for k in ks if stichtag <= d.datum(k) <= dt.date(2026, 12, 31)]
    n = str(len(im))
    assert len(im) >= 500 and len(ks) - len(im) == sum(1 for k in ks if d.datum(k) < stichtag) > 0
    assert bed["Vorlagen 2020-01-01 bis 2026-12-31"] == n
    assert bed["verworfen: date vor dem Stichtag"] == str(len(ks) - len(im))
    assert bed["doppelte Kennungen"] == bed["Seiten nicht absteigend nach created"] == bed["Jahre 2020–2026 ohne Vorlage"] == "0"
    assert bed["Seiten nicht absteigend nach date (informativ)"] == "8"
    trotz = sum(1 for k in im if d.erstellt_tag(k) < stichtag)
    assert trotz > 0 and bed["date ab Stichtag trotz created vor Stichtag (in der Stichprobe)"] == str(trotz)
    umf = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(erg / "oparl_umfang.tsv")}
    nicht = re.match(r"\d+", umf[("abstand", "date_ab_trotz_created_vor_ab_grenzseite")]).group()
    assert bed["nicht erfasst: date ab Stichtag auf Seiten ab G (aus Stufe 3, Untergrenze)"] == nicht != "0"
    assert bed["mainFile"] == bed["location"] == "0" and bed["auxiliaryFile"] == n
    assert bed["underDirectionOf → organizations/at"] == bed["underDirectionOf"] != "0"
    assert int(bed["keyword"]) < len(im) and bed["consultation.meeting"] == bed["consultation.agendaItem"] == bed["consultation"]
    assert [z["jahr"] for z in tsv(erg / "oparl_stichprobe_jahre.tsv")] == [str(j) for j in range(2020, 2027)]
    assert {z["role"] for z in tsv(erg / "oparl_beratungsrollen.tsv")} == {"Entgegennahme o. B.", "[Testdaten] Rolle B"}
    assert tsv(erg / "oparl_referenzschema.tsv") == [{"schema": "VO/NNNN/JJ", "anzahl": n}]
    zeilen = [json.loads(z) for z in (tmp_path / "cache" / "stichprobe_vorlagen.jsonl").open(encoding="utf-8")]
    assert len(zeilen) == len(im) and all(set(z) == {"id", "name", "reference", "paperType", "date", "underDirectionOf",
                                                  "datei", "dateien", "dateiliste"} for z in zeilen)
    # je Datei nur Name, Dateiname, mimeType und Adresse (für die Wahl der Datei in Stufe 6), nur im Cache
    assert all(len(z["dateiliste"]) == z["dateien"] and z["dateiliste"][0]["url"] == z["datei"]
               and all(set(d) == {"name", "fileName", "mimeType", "url"} for d in z["dateiliste"]) for z in zeilen)
    assert all(z["name"].startswith("[Testdaten] Vorlage ") for z in zeilen)    # Titel nur im Cache
    assert all(re.search(r"/downloadfiles/\d+\.pdf$", z["datei"]) for z in zeilen)   # downloadUrl vor accessUrl
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", erg)
    assert ("Regel Stufe 5 (mindestens 500 Vorlagen 2020–2026, jedes Jahr vertreten, keine Doppelungen, Sortierung "
            "nach created): erfüllt") in aus
    assert "Abdeckung (Vorlagen): zerlegt " in aus and "| Antrag FDP / WfW Rat AU |" in aus


def _seitenfolge(monkeypatch, tmp_path, seiten_daten):
    """oparl_messung im Prozess mit erfundenen Seiten der Vorlagenliste (ohne Netz); liefert Modul und abgerufene
    Adressen."""
    om = importlib.import_module("oparl_messung")
    monkeypatch.setattr(om, "_LISTEN", [])
    monkeypatch.setattr(om, "ERG", tmp_path / "erg")
    monkeypatch.setattr(om, "STICHPROBE", tmp_path / "cache" / "stichprobe_vorlagen.jsonl")
    monkeypatch.setattr(om, "BODY", "http://127.0.0.1/body")
    liste, seiten = "http://127.0.0.1/papers", {}
    for i, daten in enumerate(seiten_daten):
        url = liste if i == 0 else f"{liste}?page={i + 1}"
        seiten[url] = {"data": daten, "links": {"next": f"{liste}?page={i + 2}"} if i + 1 < len(seiten_daten) else {}}
    seiten[om.BODY] = {"paper": liste}
    abgerufen = []

    def hole(url, endung=".json"):
        abgerufen.append(url)
        return json.dumps(seiten[url]).encode()
    monkeypatch.setattr(om, "_hole", hole)
    return om, abgerufen


def _vorlage(nr, datum, created=None):
    p = {"id": f"p{nr}", "reference": f"VO/{nr:04d}/{datum[2:4]}", "paperType": "Beschlussvorlage", "date": datum}
    if created:
        p["created"] = created
    return {**p, "auxiliaryFile": [{"downloadUrl": f"http://127.0.0.1/f/{nr}.pdf", "accessUrl": f"http://127.0.0.1/f/a/{nr}.pdf",
                               "fileName": "[Testdaten] Name", "text": "Volltext"}]}


def test_doppelungen_verworfene_und_stichprobe_ohne_dateiobjekte(monkeypatch, tmp_path):
    import argparse
    a = argparse.Namespace(seiten=3, grenzseite=4, stichtag="2020-01-01", bis=2026)
    # Seite 2 wiederholt p2 (Seiten verschoben), Seite 3 endet mit einer Vorlage von 2019
    om, abgerufen = _seitenfolge(monkeypatch, tmp_path, [[_vorlage(1, "2026-03-01"), _vorlage(2, "2025-03-01")],
                                                        [_vorlage(2, "2025-03-01"), _vorlage(3, "2024-03-01")],
                                                        [_vorlage(4, "2020-02-01"), _vorlage(5, "2019-12-31")]])
    om.stichprobe(a)
    assert abgerufen == ["http://127.0.0.1/body", "http://127.0.0.1/papers", "http://127.0.0.1/papers?page=2",
                         "http://127.0.0.1/papers?page=3"]
    bed = {z["feld"]: z["vorhanden"] for z in tsv(tmp_path / "erg" / "oparl_stichprobe_bedeckung.tsv")}
    assert (bed["doppelte Kennungen"], bed["verworfen: date vor dem Stichtag"], bed["Vorlagen 2020-01-01 bis 2026-12-31"]
            ) == ("1", "1", "4")
    assert bed["Jahre 2020–2026 ohne Vorlage"] == "3"                    # 2021, 2022, 2023
    zeilen = [json.loads(z) for z in (tmp_path / "cache" / "stichprobe_vorlagen.jsonl").open(encoding="utf-8")]
    assert len(zeilen) == 4 and zeilen[0] == {"id": "p1", "name": None, "reference": "VO/0001/26",
                                              "paperType": "Beschlussvorlage",
                                              "date": "2026-03-01", "underDirectionOf": False,
                                              "datei": "http://127.0.0.1/f/1.pdf", "dateien": 1,
                                              "dateiliste": [{"name": None, "fileName": "[Testdaten] Name",
                                                              "mimeType": None, "url": "http://127.0.0.1/f/1.pdf"}]}
    assert "Volltext" not in json.dumps(zeilen) and not list((tmp_path / "erg").glob("*.jsonl"))
    # unsortierte Seite (created aufsteigend): gezählt, Regel nicht erfüllt
    om, _ = _seitenfolge(monkeypatch, tmp_path / "b", [[_vorlage(1, "2024-01-01", "2023-12-20T10:00:00+01:00"),
                                                        _vorlage(2, "2025-01-01", "2024-12-20T10:00:00+01:00")]])
    om.stichprobe(argparse.Namespace(seiten=8, grenzseite=2, stichtag="2020-01-01", bis=2026))
    bed = tsv(tmp_path / "b" / "erg" / "oparl_stichprobe_bedeckung.tsv")
    werte = {z["feld"]: z["vorhanden"] for z in bed}
    assert werte["Seiten nicht absteigend nach created"] == werte["Seiten nicht absteigend nach date (informativ)"] == "1"
    regel = importlib.import_module("auswertung").regel_stichprobe(bed, [])
    assert regel.startswith("nicht erfüllt (nur 2 Vorlagen") and "Seiten nicht absteigend nach created 1" in regel
    # nach created sortiert, nach date nicht: Regel nur nach created; date vor 2020 trotz created ab 2020 wird verworfen,
    # date ab 2020 mit created davor gezählt; ohne oparl_umfang.tsv ist „nicht erfasst“ offen
    om, _ = _seitenfolge(monkeypatch, tmp_path / "d", [[_vorlage(1, "2024-01-09", "2024-01-05T10:00:00+01:00"),
                                                        _vorlage(2, "2024-01-20", "2024-01-03T10:00:00+01:00"),
                                                        _vorlage(3, "2020-01-03", "2019-12-30T10:00:00+01:00")]])
    om.stichprobe(argparse.Namespace(seiten=8, grenzseite=2, stichtag="2020-01-01", bis=2026))
    werte = {z["feld"]: (z["vorhanden"], z["von"]) for z in tsv(tmp_path / "d" / "erg" / "oparl_stichprobe_bedeckung.tsv")}
    assert werte["Seiten nicht absteigend nach created"] == ("0", "1")
    assert werte["Seiten nicht absteigend nach date (informativ)"] == ("1", "1")
    assert werte["date ab Stichtag trotz created vor Stichtag (in der Stichprobe)"] == ("1", "3")
    assert werte["nicht erfasst: date ab Stichtag auf Seiten ab G (aus Stufe 3, Untergrenze)"] == ("offen", "–")
    assert werte["Vorlagen 2020-01-01 bis 2026-12-31"] == ("3", "3")
    # Vorlagen ohne created: Sortierung nach created nicht prüfbar, zählt für die Regel als nicht sortiert (Annahme)
    om, _ = _seitenfolge(monkeypatch, tmp_path / "e", [[_vorlage(1, "2024-01-09", "2024-01-05T10:00:00+01:00"),
                                                        _vorlage(2, "2024-01-08")]])
    om.stichprobe(argparse.Namespace(seiten=8, grenzseite=2, stichtag="2020-01-01", bis=2026))
    assert tsv(tmp_path / "e" / "erg" / "oparl_stichprobe_seiten.tsv")[0]["created_absteigend"] == "nicht prüfbar (1 ohne created)"
    werte = {z["feld"]: z["vorhanden"] for z in tsv(tmp_path / "e" / "erg" / "oparl_stichprobe_bedeckung.tsv")}
    assert werte["Seiten nicht absteigend nach created"] == "1"
    # ohne Grenzseite: Abbruch vor der ersten Anfrage
    om, abgerufen = _seitenfolge(monkeypatch, tmp_path / "c", [[_vorlage(1, "2024-01-01")]])
    with pytest.raises(om.Abbruch) as e:
        om.stichprobe(argparse.Namespace(seiten=8, grenzseite=None, stichtag="2020-01-01", bis=2026))
    assert e.value.art == "voraussetzung" and "zuerst: umfang" in str(e.value) and abgerufen == []


def _mit_created(nr, tag_offset, versatz, stichtag=dt.date(2020, 1, 1)):
    """Erfundene Vorlage: created = Stichtag + tag_offset (10 Uhr, +01:00), date = Tag von created + versatz."""
    c = stichtag + dt.timedelta(days=tag_offset)
    return _vorlage(nr, (c + dt.timedelta(days=versatz)).isoformat(), f"{c.isoformat()}T10:00:00+01:00")


def _umfang_args(grenze, ende):
    return argparse.Namespace(liste="paper", grenze_seiten=list(grenze), ende_seiten=list(ende), stichtag="2020-01-01")


def test_umfang_bisektion_nach_created_bei_unsortiertem_date(monkeypatch, tmp_path):
    """Grenzseite nach created, wenn date sie verschieben würde: Seiten 6 und 7 enthalten je eine Vorlage mit created vor
    2020 und date ab 2020 (eine Bisektion nach date ergäbe G = 8). Gleiche Bisektion, gleiche Startseiten, Anfragen
    höchstens hoechstzahl_umfang; Abstand date − created und Vorlagen über die Grenze auf den Seiten ab G."""
    seiten = [[_mit_created(10 * i + j, (5 - i) * 10 + 5 - 3 * j, 20 if i in (6, 7) and j == 0 else 2)
               for j in range(2)] for i in range(1, 13)] + [[]]
    stichtag = dt.date(2020, 1, 1)
    nach_date = next(i for i, s in enumerate(seiten, 1) if s and all(dt.date.fromisoformat(p["date"]) < stichtag
                                                                       for p in s))
    nach_created = next(i for i, s in enumerate(seiten, 1) if s and all(p["created"] < "2020" for p in s))
    assert (nach_date, nach_created) == (8, 6)
    om, abgerufen = _seitenfolge(monkeypatch, tmp_path, seiten)
    om.umfang(_umfang_args((2, 9), (11, 13)))
    liste = "http://127.0.0.1/papers"
    assert abgerufen == ["http://127.0.0.1/body", liste] + [f"{liste}?page={n}" for n in (2, 9, 5, 7, 6, 11, 13, 12)]
    assert len(abgerufen) <= om.hoechstzahl_umfang((2, 9), (11, 13)) == 10
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "erg" / "oparl_umfang.tsv")}
    assert (w[("grenze", "grenzseite")], w[("grenze", "letzte_seite_ab_stichtag")]) == ("6", "5")
    assert w[("grenze", "vorlagen_ab_stichtag")].startswith("10 (")          # 4 Seiten × 2 + 2 auf Seite 5
    assert w[("ende", "letzte_seite")] == "12"
    assert w[("sortierung", "created_absteigend")].startswith("ja (")
    assert w[("sortierung", "date_absteigend")].startswith("nein (")         # informativ
    assert w[("abstand", "date_ab_trotz_created_vor_ab_grenzseite")].startswith(
        "2 (Untergrenze: date ab 2020-01-01, created vor 2020-01-01, auf den abgerufenen Seiten ab G = 6: "
        "6, 7, 9, 11, 12, 13)")
    assert w[("abstand", "seiten_mit_date_ab_trotz_created_vor")] == "6, 7"
    assert w[("abstand", "spaeteste_seite_mit_date_ab_trotz_created_vor")] == "7"
    assert w[("abstand", "groesste_differenz_date_ab_trotz_created_vor")] == "20 Tage"
    assert w[("abstand", "groesste_differenz_insgesamt")] == "20 Tage"
    assert w[("abstand", "date_minus_created_tage")] == "min 2, Median 2, max 20 (16 Vorlagen auf 8 Seiten)"
    assert (w[("abstand", "date_vor_created")], w[("abstand", "ohne_date_oder_created")]) == ("0 von 16", "0")
    assert w[("abstand", "sicherheitsabstand")] == ("offen (nur ausgewiesen; Seiten ab G nur stichprobenhaft abgerufen: "
                                                     "6, 7, 9, 11, 12, 13)")
    infos = {z["seite"]: z for z in tsv(tmp_path / "erg" / "oparl_umfang_seiten.tsv")}
    assert (infos["6"]["date_ab_trotz_created_vor"], infos["6"]["ab_stichtag"], infos["6"]["ab_stichtag_created"]) == (
        "1", "1", "0")
    assert (infos["6"]["abstand_min"], infos["6"]["abstand_median"], infos["6"]["abstand_max"]) == ("2", "11", "20")
    assert infos["13"]["created_absteigend"] == infos["13"]["abstand_median"] == "–"     # leere Seite


def test_umfang_ohne_created_nicht_neu_und_nicht_sortiert(monkeypatch, tmp_path):
    """Vorlagen ohne created zählen bei der Bisektion nicht als neu, werden je Seite gezählt und machen das Urteil zur
    Sortierung nach created zu „nein“ (Annahme, vorsichtig); die Regel Stufe 3 ist dann nicht erfüllt."""
    ohne = _vorlage(31, "2021-05-01")                                       # date ab 2020, created fehlt
    seiten = [[_mit_created(1, 40, 3), _mit_created(2, 30, 3)], [_mit_created(3, 20, 3), _mit_created(4, 10, 3)],
              [_mit_created(5, -5, 3), ohne], [_mit_created(6, -20, 3), _mit_created(7, -30, 3)],
              [_mit_created(8, -40, 3)], []]
    om, abgerufen = _seitenfolge(monkeypatch, tmp_path, seiten)
    om.umfang(_umfang_args((2, 4), (5, 6)))
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "erg" / "oparl_umfang.tsv")}
    assert w[("grenze", "grenzseite")] == "3"
    assert w[("sortierung", "created_absteigend")].startswith(
        "nein (0 Seiten innen nicht absteigend, 0 Seitenübergänge verletzt, 1 Seiten mit Vorlagen ohne created;")
    infos = {z["seite"]: z for z in tsv(tmp_path / "erg" / "oparl_umfang_seiten.tsv")}
    assert (infos["3"]["ohne_created"], infos["3"]["ab_stichtag_created"]) == ("1", "0")
    assert infos["3"]["created_absteigend"] == "nicht prüfbar (1 ohne created)"
    assert infos["3"]["ohne_date_oder_created"] == "1" and w[("abstand", "ohne_date_oder_created")] == "1"
    regel = importlib.import_module("auswertung").regel_umfang(tsv(tmp_path / "erg" / "oparl_umfang.tsv"), [])
    assert regel.startswith("nicht erfüllt (Sortierung nach created nein (")
    # ohne Grenzseite (Bereich passt nicht): Sicherheitsabstand nicht bestimmbar
    om, _ = _seitenfolge(monkeypatch, tmp_path / "b", seiten)
    om.umfang(_umfang_args((3, 4), (5, 6)))
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "b" / "erg" / "oparl_umfang.tsv")}
    assert w[("grenze", "grenzseite")] == "nicht im Bereich (Seite 3 ohne Vorlage mit created ab 2020-01-01)"
    assert w[("abstand", "sicherheitsabstand")] == w[("abstand", "date_ab_trotz_created_vor_ab_grenzseite")] == (
        "nicht bestimmbar (keine Grenzseite)")
    assert importlib.import_module("auswertung").regel_umfang(
        tsv(tmp_path / "b" / "erg" / "oparl_umfang.tsv"), []).startswith("nicht erfüllt (Grenzseite nicht im Bereich")


def test_created_randwerte_und_umfang_liste_ohne_created(monkeypatch, tmp_path):
    """created mit Randwerten, die nicht in Ortszeit darstellbar sind (OverflowError), zählt wie „ohne created“ statt
    den Lauf abzubrechen; `umfang --liste` (Stufe 4) wertet date/created gar nicht aus und gibt wie bisher nur Seite,
    Objekte und links aus."""
    om = importlib.import_module("oparl_messung")
    rand = ("0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-05:00")
    for wert in rand:
        assert om._erstellt({"created": wert}) is None, wert
    info = om._seiteninfo(1, {"data": [_vorlage(1, "2024-01-01", rand[1]), _vorlage(2, "2023-01-01", rand[0])]},
                          dt.date(2020, 1, 1))
    assert (info["ohne_created"], info["ab_stichtag_created"], info["ohne_date_oder_created"]) == (2, 0, 2)
    # umfang: Randwert auf Seite 3 zählt nicht als neu, die Bisektion läuft durch
    seiten = [[_mit_created(1, 40, 3), _mit_created(2, 30, 3)], [_mit_created(3, 20, 3), _mit_created(4, 10, 3)],
              [_mit_created(5, -5, 3), _vorlage(31, "2021-05-01", rand[0])],
              [_mit_created(6, -20, 3), _mit_created(7, -30, 3)], [_mit_created(8, -40, 3)], []]
    om, _ = _seitenfolge(monkeypatch, tmp_path, seiten)
    om.umfang(_umfang_args((2, 4), (5, 6)))
    w = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "erg" / "oparl_umfang.tsv")}
    assert w[("grenze", "grenzseite")] == "3" and w[("ende", "letzte_seite")] == "5"
    assert {z["seite"]: z for z in tsv(tmp_path / "erg" / "oparl_umfang_seiten.tsv")}["3"]["ohne_created"] == "1"
    # umfang --liste: Objekte mit Randwerten in created/date, Ausgabe nur seite, objekte, links
    objekte = [{"id": f"m{i}", "created": rand[i % 2], "date": "kaputt"} for i in range(3)]
    om, abgerufen = _seitenfolge(monkeypatch, tmp_path / "b", [objekte, objekte, []])
    om.umfang_liste(argparse.Namespace(liste="paper", ende_seiten=[2, 3], stichtag="2020-01-01"))
    zeilen = tsv(tmp_path / "b" / "erg" / "oparl_umfang_paper_seiten.tsv")
    assert [list(z) for z in zeilen] == [["seite", "objekte", "links_schluessel", "links_next"]] * 3
    assert [(z["seite"], z["objekte"]) for z in zeilen] == [("1", "3"), ("2", "3"), ("3", "0")]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "b" / "erg" / "oparl_umfang_paper.tsv")}
    assert werte["letzte_seite"] == "2" and len(abgerufen) <= om.hoechstzahl_umfang(None, (2, 3))


def test_nicht_erfasst_nur_bei_gleicher_grenzseite(monkeypatch, tmp_path):
    """„nicht erfasst … (aus Stufe 3, Untergrenze)“ wird nur übernommen, wenn die Grenzseite in oparl_umfang.tsv der in
    der Stichprobe verwendeten G entspricht (sonst „offen (…)“, z. B. bei --grenzseite von Hand)."""
    om = importlib.import_module("oparl_messung")
    datei = tmp_path / "oparl_umfang.tsv"
    datei.write_text("objekt\tfeld\twert\ngrenze\tgrenzseite\t5\n"
                     "abstand\tdate_ab_trotz_created_vor_ab_grenzseite\t3 (Untergrenze: …)\n", encoding="utf-8")
    assert om.nicht_erfasst_aus_umfang(datei) == om.nicht_erfasst_aus_umfang(datei, g=5) == 3
    assert om.nicht_erfasst_aus_umfang(datei, g=2) == "offen (G aus umfang 5 ≠ verwendete G 2)"
    assert om.nicht_erfasst_aus_umfang(tmp_path / "fehlt.tsv", g=2) == "offen"
    # in der Stichprobe: --grenzseite 2, oparl_umfang.tsv nennt G = 5
    om, _ = _seitenfolge(monkeypatch, tmp_path / "s", [[_vorlage(1, "2024-01-09", "2024-01-05T10:00:00+01:00")]])
    (tmp_path / "s" / "erg").mkdir(parents=True)
    (tmp_path / "s" / "erg" / "oparl_umfang.tsv").write_text(datei.read_text(encoding="utf-8"), encoding="utf-8")
    feld = "nicht erfasst: date ab Stichtag auf Seiten ab G (aus Stufe 3, Untergrenze)"
    om.stichprobe(argparse.Namespace(seiten=8, grenzseite=2, stichtag="2020-01-01", bis=2026))
    werte = {z["feld"]: z["vorhanden"] for z in tsv(tmp_path / "s" / "erg" / "oparl_stichprobe_bedeckung.tsv")}
    assert werte[feld] == "offen (G aus umfang 5 ≠ verwendete G 2)"


def test_auswertung_created_tag_in_ortszeit(tmp_path):
    """Anzeige von created in „Stichprobe – Seiten“ nach dem Tag in Ortszeit wie die Bisektion (_erstellt)."""
    aw = importlib.import_module("auswertung")
    assert aw.tag_ortszeit("2019-12-31T23:30:00Z") == "2020-01-01"
    assert aw.tag_ortszeit("2019-12-31T23:30:00+00:00") == "2020-01-01"
    assert aw.tag_ortszeit("2020-06-30T23:30:00+02:00") == "2020-06-30"
    assert aw.tag_ortszeit("2020-01-01T00:10:00") == "2020-01-01"
    assert aw.tag_ortszeit("kaputt") == "kaputt" and aw.tag_ortszeit("0001-01-01T00:00:00+01:00") == "0001-01-01"
    erg = tmp_path / "erg"
    erg.mkdir()
    (erg / "oparl_stichprobe_seiten.tsv").write_text(
        "seite\tobjekte\tab_stichtag\tdate_max\tdate_min\tcreated_max\tcreated_min\n"
        "3\t100\t1\t2020-01-03\t2019-12-30\t2020-01-01T10:00:00+01:00\t2019-12-31T23:30:00Z\n", encoding="utf-8")
    aus = aw.auswertung(tmp_path / "cache", erg)
    assert "created 2020-01-01 bis 2020-01-01 (Ortszeit)" in aus


def test_created_helfer_zeitzone_sommerzeit_und_abstand():
    om = importlib.import_module("oparl_messung")
    # Tag von created in Ortszeit Europe/Berlin
    assert om._erstellt({"created": "2019-12-31T23:30:00Z"}) == dt.date(2020, 1, 1)
    assert om._erstellt({"created": "2019-12-31T23:59:00+01:00"}) == dt.date(2019, 12, 31)
    assert om._erstellt({"created": "2020-06-30T22:30:00+00:00"}) == dt.date(2020, 7, 1)      # +02:00
    assert om._erstellt({"created": "2020-06-30T23:30:00+02:00"}) == dt.date(2020, 6, 30)
    assert om._erstellt({"created": "2020-01-01T00:10:00"}) == dt.date(2020, 1, 1)            # ohne Zone: Ortszeit
    for o in ({}, {"created": ""}, {"created": None}, {"created": "kaputt"}, {"created": 5}, "kein Objekt"):
        assert om._erstellt(o) is None, o
    # Umstellung auf Winterzeit: 02:10+01:00 (01:10 UTC) liegt nach 02:30+02:00 (00:30 UTC); als Text umgekehrt
    spaet, frueh = {"created": "2026-10-25T02:10:00+01:00"}, {"created": "2026-10-25T02:30:00+02:00"}
    assert om._absteigend_created([spaet, frueh]) == (0, 2) and om._absteigend_created([frueh, spaet]) == (1, 2)
    assert om._absteigend_created([spaet, {}, {"created": "kaputt"}, frueh, "x"]) == (0, 2)
    # Umstellung auf Sommerzeit
    assert om._absteigend_created([{"created": "2026-03-29T03:10:00+02:00"},
                                   {"created": "2026-03-29T01:50:00+01:00"}]) == (0, 2)
    # zwischen Seiten als Zeitpunkt, nicht als Text
    stichtag = dt.date(2020, 1, 1)
    infos = [om._seiteninfo(1, {"data": [{"created": "2026-10-25T03:00:00+01:00", "date": "2026-10-26"}, spaet]},
                            stichtag),
             om._seiteninfo(2, {"data": [frueh, {"created": "2026-10-24T09:00:00+02:00", "date": "2026-10-27"}]},
                            stichtag)]
    assert om._sortierung(infos, "created").startswith("ja (2 Seiten geprüft")
    assert om._sortierung(infos).startswith("nein (")                                   # date informativ
    assert om._sortierung([om._seiteninfo(1, {"data": []}, stichtag)], "created") == "nicht prüfbar (keine Seite mit created)"
    # Abstände und Kennwerte
    objekte = [{"date": "2024-01-05", "created": "2024-01-01T10:00:00+01:00"},       # 4
               {"date": "2024-01-02", "created": "2024-01-01T23:30:00Z"},           # created 02.01. Ortszeit: 0
               {"date": "2023-12-31", "created": "2024-01-01T10:00:00+01:00"},       # −1 (date vor created)
               {"date": "2024-01-08", "created": "2024-01-01T10:00:00+01:00"},       # 7
               {"date": "2024-01-08"}, {"created": "2024-01-01T10:00:00+01:00"},
               {"date": "kaputt", "created": "2024-01-01T10:00:00+01:00"}, "kein Objekt"]
    assert om._abstaende(objekte) == ([4, 0, -1, 7], 3)
    assert om._abstand_kennwerte([4, 0, -1, 7]) == {"min": "-1", "median": "2", "max": "7", "negativ": 1}
    assert om._abstand_kennwerte([1, 4]) == {"min": "1", "median": "2,5", "max": "4", "negativ": 0}
    assert om._abstand_kennwerte([]) == {"min": "–", "median": "–", "max": "–", "negativ": 0}
    info = om._seiteninfo(3, {"data": objekte[:6]}, stichtag)
    assert (info["abstand_min"], info["abstand_median"], info["abstand_max"], info["date_vor_created"],
            info["ohne_date_oder_created"], info["ohne_created"], info["ohne_date"]) == ("-1", "2", "7", 1, 2, 1, 1)
    assert info["created_absteigend"] == "nein (1)"            # Verletzung (Zeile 2 nach Zeile 1) vor „nicht prüfbar“
    leer = om._seiteninfo(4, {"data": []}, stichtag)
    assert (leer["abstand_min"], leer["abstand_median"], leer["created_absteigend"], leer["date_absteigend"],
            leer["created_max"]) == ("–", "–", "–", "–", "")


def test_abstand_zeilen_nur_ab_grenzseite():
    om = importlib.import_module("oparl_messung")
    stichtag = dt.date(2020, 1, 1)
    geholt = {1: {"data": [_mit_created(1, 400, 3)]},
              5: {"data": [_mit_created(2, -2, 9), _mit_created(3, -1, 0)]},       # vor G: nicht in der Zählung ab G
              6: {"data": [_mit_created(4, -3, 5), _mit_created(5, -4, 1), {"date": "2020-02-01"}]},
              9: {"data": [_mit_created(6, -30, 40), _mit_created(7, -40, 2)]},
              12: {"data": []}}
    w = {z["feld"]: z["wert"] for z in om._abstand_zeilen(geholt, 6, stichtag)}
    assert w["date_ab_trotz_created_vor_ab_grenzseite"].startswith(
        "2 (Untergrenze: date ab 2020-01-01, created vor 2020-01-01, auf den abgerufenen Seiten ab G = 6: 6, 9, 12)")
    assert w["seiten_mit_date_ab_trotz_created_vor"] == "6, 9" and w["spaeteste_seite_mit_date_ab_trotz_created_vor"] == 9
    assert w["groesste_differenz_date_ab_trotz_created_vor"] == "40 Tage" == w["groesste_differenz_insgesamt"]
    assert w["date_minus_created_tage"] == "min 0, Median 3, max 40 (7 Vorlagen auf 4 Seiten)"
    assert w["ohne_date_oder_created"] == 1 and w["date_vor_created"] == "0 von 7"
    assert w["sicherheitsabstand"] == "offen (nur ausgewiesen; Seiten ab G nur stichprobenhaft abgerufen: 6, 9, 12)"
    ohne_treffer = {z["feld"]: z["wert"] for z in om._abstand_zeilen({k: geholt[k] for k in (1, 5, 12)}, 6, stichtag)}
    assert ohne_treffer["date_ab_trotz_created_vor_ab_grenzseite"].startswith("0 (")
    assert ohne_treffer["seiten_mit_date_ab_trotz_created_vor"] == "keine"
    assert ohne_treffer["groesste_differenz_date_ab_trotz_created_vor"] == "–"
    ohne_g = {z["feld"]: z["wert"] for z in om._abstand_zeilen(geholt, None, stichtag)}
    assert ohne_g["sicherheitsabstand"] == ohne_g["date_ab_trotz_created_vor_ab_grenzseite"] == (
        "nicht bestimmbar (keine Grenzseite)")
    assert "seiten_mit_date_ab_trotz_created_vor" not in ohne_g
    assert {z["feld"]: z["wert"] for z in om._abstand_zeilen({}, None, stichtag)}["date_minus_created_tage"] == (
        "– (keine Vorlage mit date und created)")


def _ohne_jetzt(text):
    """modified_since-Grenze und Zeitstempel, die von „jetzt“ abhängen, maskiert."""
    return re.sub(r"\d{4}-\d\d-\d\dT\d\d(:|%3A)\d\d(:|%3A)\d\d(\.\d+)?(\+00:00|%2B00%3A00|Z)", "<zeit>", text)


@pytest.mark.parametrize("kommando, obergrenze, datei", [("test", 3, "oparl_test.tsv"),
                                                          ("kennzahlen", 8, "oparl_kennzahlen.tsv")])
def test_stufe_1_und_2_unabhaengig_vom_date_versatz(tmp_path, kommando, obergrenze, datei):
    """test und kennzahlen stellen gegen Testdaten mit und ohne Versatz von date dieselben Anfragen und schreiben
    dieselben Felder; bei test unterscheidet sich nur das (unveränderte) Urteil zur Sortierung der ersten Seite nach
    date, bei kennzahlen nichts (Zeiten, die von „jetzt“ abhängen, maskiert)."""
    ergebnisse = {}
    for versatz in (False, True):
        with testserver.Testserver(date_versatz=versatz) as s:
            m = lauf(s, tmp_path / str(versatz), kommando, obergrenze=obergrenze)
            assert m["rc"] == 0 and m["server"] == obergrenze, m["stderr"]
            anfragen = [(p, _ohne_jetzt(q).replace(s.basis, ""), st) for p, q, _, st in s.anfragen]
        zeilen = tsv(tmp_path / str(versatz) / "ergebnisse" / datei)
        ergebnisse[versatz] = (anfragen, [(z["objekt"], _ohne_jetzt(z["feld"]),
                                           _ohne_jetzt(z["wert"]).replace(s.basis, "<basis>"))
                                          for z in zeilen])
    (a0, z0), (a1, z1) = ergebnisse[False], ergebnisse[True]
    assert a0 == a1 and [z[:2] for z in z0] == [z[:2] for z in z1]
    unterschied = [(x, y) for x, y in zip(z0, z1) if x != y]
    if kommando == "test":
        assert [x[:2] for x, _ in unterschied] == [("paper", "date_absteigend_erste_seite")]
        assert unterschied[0][0][2] == "ja (n = 100)" and unterschied[0][1][2].startswith("nein (")
    else:
        assert unterschied == []


def test_papertyp_zerlegung_nach_regeltabelle():
    """Regeltabelle explore/paperType_regeln.tsv: Startregeln aus den Beispielen in CLAUDE.md 3.1; „Gemeinsamer Antrag“
    ohne Namen: Einreichende offen; Kürzel nach der Ebene („AU“) wörtlich und offen; unbekannte Arten nicht zerlegt."""
    aw = importlib.import_module("auswertung")
    regeln = aw.regeln_laden()
    assert regeln and all("CLAUDE.md 3.1" in r["beleg"] for r in regeln)
    erwartet = {"Antrag CDU": ("Antrag", "CDU", "offen", ""),
                "Antrag B90/Grüne BV": ("Antrag", "B90/Grüne", "BV", ""),
                "Gemeinsamer Antrag BV": ("Gemeinsamer Antrag", "offen", "BV", ""),
                "Gemeinsamer Antrag Rat": ("Gemeinsamer Antrag", "offen", "Rat", ""),
                "Große Anfrage die Linke": ("Große Anfrage", "die Linke", "offen", ""),
                "Antrag FDP / WfW Rat AU": ("Antrag", "FDP / WfW", "Rat", "AU"),
                "Bericht": ("Bericht", "–", "offen", ""), "Beschlussvorlage": ("Beschlussvorlage", "–", "offen", ""),
                "Antwort auf Anfragen": ("Antwort auf Anfragen", "–", "offen", "")}
    for pt, werte in erwartet.items():
        z = aw.zerlege(pt, regeln)
        assert (z["art"], z["einreichende"], z["ebene"], z["zusatz"]) == werte, (pt, z)
    assert aw.zerlege("Antrag FDP / WfW Rat AU", regeln)["status"] == "zerlegt (Kürzel „AU“ offen)"
    assert aw.zerlege("[Testdaten] Mitteilung", regeln) == {"regel": "", "art": "offen", "einreichende": "offen",
                                                          "ebene": "offen", "zusatz": "", "status": aw.NICHT_ZERLEGT}
    assert aw.ohne_einreichende("Bericht", regeln) and not aw.ohne_einreichende("Antrag CDU", regeln)
    assert not aw.ohne_einreichende("Gemeinsamer Antrag BV", regeln) and not aw.ohne_einreichende(None, regeln)
    zeilen, q = aw.papertyp_abdeckung([("Antrag CDU", "30"), ("Bericht", "60"), ("[Testdaten] X", "10"),
                                       ("Antrag FDP / WfW Rat AU", "0")], regeln)
    assert [z["regel"] for z in zeilen] == ["4", "1", "", "3"]
    assert (q["zerlegt"], q["einreichende"], q["ebene"], q["kuerzel_offen"]) == ((90, 100), (90, 100), (0, 100), (0, 100))


def _bis_stichprobe(server, tmp_path):
    """Stufen 3, 4 (organisationen bis zum Ende der Liste) und 5 gegen den lokalen Testserver: Grundlage für Stufe 6."""
    for kommando, *parameter in (("umfang",), ("organisationen", "--seiten", "0"), ("stichprobe",)):
        assert lauf(server, tmp_path, kommando, *parameter, obergrenze=20)["rc"] == 0


# erfundene Bearbeiterangaben aus testserver.BEARBEITUNG (Name, Telefon, E-Mail): dürfen nirgends erscheinen
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
BEARBEITER = ("Erika", "Erfunden", "Musterfrau", "Bearbeitung", "0202", "99 88 77 66", "pdf-test.invalid", "Telefon",
              "E-Mail")
# Kopftext der erfundenen PDFs (nur für Ausgaben von pdf-koepfe: Titel und Organisationsnamen aus der API tragen in
# anderen Ergebnisdateien ebenfalls „[Testdaten]“)
KOPFTEXT = ("Testdaten", "Beispiel", "beschliesst", "Anmeldung", "Kopfangabe", "Scanner", "Ghostscript", "Microsoft")


def _ohne_bearbeiter(*texte):
    """Keine erfundene Bearbeiterangabe (Name, Telefon, E-Mail) und keine E-Mail-Adresse."""
    for text in texte:
        assert not any(v in text for v in BEARBEITER), [v for v in BEARBEITER if v in text]
        assert not RE_EMAIL.search(text), RE_EMAIL.search(text).group()


def _ohne_pdf_inhalt(*texte):
    """Dazu kein Text aus den erfundenen PDFs (Kopftext, Metadaten)."""
    _ohne_bearbeiter(*texte)
    for text in texte:
        assert not any(v in text for v in KOPFTEXT), [v for v in KOPFTEXT if v in text]


def test_pdf_koepfe_aus_auxiliaryfile_mit_aemterabgleich(server, tmp_path):
    """pdf-koepfe nach umfang, organisationen und stichprobe: nur Verwaltungsvorlagen ohne underDirectionOf, eine Anfrage
    je Vorlage, Datei nach Name als Vorlage gewählt, alle Kandidaten mit Zeile und Lage, Regel für den federführenden
    Kandidaten, Abgleich mit organizations/at, Messwerte ohne Inhalt; keine Textauszüge, keine Bearbeiterangaben in
    Ergebnisdateien, stdout oder stderr; Auswertung mit Quoten, Hochrechnung und Regel Stufe 6."""
    pytest.importorskip("pypdf")
    _bis_stichprobe(server, tmp_path)
    vorher = len(server.anfragen)
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "100", obergrenze=100)
    assert m["rc"] == 0 and m["server"] == 100, m["stderr"]
    pfade = [pf for pf, *_ in server.anfragen[vorher:]]
    assert all(re.search(r"/downloadfiles/\d+\.pdf$", pf) for pf in pfade) and len(set(pfade)) == 100
    erg = tmp_path / "ergebnisse"
    zeilen = tsv(erg / "pdf_koepfe.tsv")
    assert list(zeilen[0]) == list(importlib.import_module("oparl_messung").PDF_SPALTEN)
    assert {z["paperType"] for z in zeilen} <= {"Beschlussvorlage", "Bericht", "Antwort auf Anfragen"}
    ohne = {p["id"] for p in map(server.daten.vorlage, range(8000)) if not p.get("underDirectionOf")}
    assert all(z["id"] in ohne for z in zeilen)
    # Wahl der Datei: die Vorlage (bei mehreren Dateien die zweite, zwischen den Anlagen), nie eine Anlage
    assert all(re.fullmatch(r"auxiliaryFile (1 von 1|2 von [23])", z["datei"]) for z in zeilen)
    assert {z["auswahl"] for z in zeilen} == {"Name nennt die Vorlage (Annahme)", "Name nennt die Referenz (Annahme)"}
    assert all(int(re.search(r"/(\d+)\.pdf$", pf).group(1)) % 3 in (0, 1) for pf in pfade)
    assert {z["treffer"] for z in zeilen} == {"kennung", "nur außerhalb des Kopfes", "nein", "kein_text"}
    assert {z["lage"] for z in zeilen if z["treffer"] == "kennung"} == {"ein Kandidat", "mehrere gleiche",
                                                                        "mehrere verschiedene"}
    assert {z["fundstelle"] for z in zeilen} == {"Seite 1", "Seite 2"}
    assert all(z["textebene"] == "ja (ab Seite 2)" for z in zeilen if z["fundstelle"] == "Seite 2")
    assert all(z["textebene"] == "nein (OCR nötig)" and z["kennung"] == "" for z in zeilen if z["treffer"] == "kein_text")
    # Regel: unter mehreren verschiedenen gilt der erste mit belegter Bezeichnung (Ressort vor Geschäftsbereich)
    verschieden = [z for z in zeilen if z["lage"] == "mehrere verschiedene"]
    assert verschieden and all(z["bezeichnung"] == "Ressort" and z["kandidaten"].startswith("Geschäftsbereich 99 Z1 Kopf")
                               and "belegter Bezeichnung" in z["regel"] for z in verschieden)
    ressort = [z for z in zeilen if z["kennung"].startswith(("Ressort ", "Amt "))]
    assert ressort and all(re.search(r"/organizations/at/\d+$", z["abgleich"]) for z in ressort)
    betrieb = [z for z in zeilen if z["kennung"] == "Stadtbetrieb 999"]   # über die Silbentrennung erkannt
    assert betrieb and all(z["abgleich"] == "kein Treffer in organizations/at" and z["bezeichnung_beleg"] == "Annahme"
                           for z in betrieb)
    assert all(z["bezeichnung_beleg"] == "belegt (CLAUDE.md 3.1/3.2)" for z in ressort)
    assert all(z["kandidaten_kopf"] == "0" and "außerhalb" in z["kandidaten"]
               for z in zeilen if z["treffer"] == "nur außerhalb des Kopfes")
    # Messwerte je Datei ohne Inhalt
    assert all(z["bytes"].isdigit() and z["seiten"] in ("1", "2") and z["pdf_kennung"] == "ja" and z["quelle"] == "netz"
               and float(z["antwort_s"]) >= 0 for z in zeilen)
    assert {z["erzeuger"] for z in zeilen} <= {"Office-Programm", "Scan/Texterkennung", "PDF-Bibliothek", "fehlt"}
    grundlage = {z["feld"]: z["wert"] for z in tsv(erg / "pdf_koepfe_grundlage.tsv")}
    stichprobe = (tmp_path / "cache" / "stichprobe_vorlagen.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(stichprobe) >= 500 and grundlage["stichprobe_vorlagen"] == str(len(stichprobe))
    assert grundlage["ausgewaehlt"] == "100"
    assert grundlage["pdf_max_bytes"] == str(10 * 1024 * 1024) and grundlage["aemterliste"] == "60"
    # keine Textauszüge, Bearbeiterangaben, Telefonnummern oder E-Mail-Adressen (auch nicht aus den Metadaten)
    _ohne_bearbeiter(m["stdout"], m["stderr"], *(d.read_text(encoding="utf-8") for d in erg.iterdir()))
    _ohne_pdf_inhalt(m["stdout"], m["stderr"], *(d.read_text(encoding="utf-8") for d in erg.glob("pdf_koepfe*.tsv")))
    assert any(z["lage"] == "mehrere gleiche" for z in zeilen)           # die Variante mit Bearbeiterangaben war dabei
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", erg)
    _ohne_pdf_inhalt(aus.split("## Kennwerte")[1].split("### Stufe 6")[1])
    assert "PDF-Köpfe (auxiliaryFile): 100 Verwaltungsvorlagen ohne underDirectionOf ausgewählt, 100 angefragt" in aus
    assert re.search(r"Erkennungsquote \(Kennung nach Regel im Kopf gefunden, Annahme, Zuordnung ungeprüft / "
                     r"abgerufen\): \d+ von 100 \(\d+ %; Wilson 95 % \d+ %–\d+ %\)", aus)
    # Hochrechnung nach Jahr gewichtet (Bestand je Jahr in der Grundlage), Richtigkeit der Zuordnung ungeprüft
    bestand = {f: w for f, w in grundlage.items() if f.startswith("verwaltung_ohne_underDirectionOf_mit_datei_")}
    assert bestand and sum(map(int, bestand.values())) == int(grundlage["verwaltung_ohne_underDirectionOf_mit_datei"])
    assert re.search(r"Kennung nach Regel gefunden, \d+ von 100 angefragten Dateien, nach Jahr gewichtet", aus)
    assert "Richtigkeit der Zuordnung (manuelle Kontrolle im lokalen Cache, nur richtig/falsch): nicht geprüft" in aus
    assert "ungeprüft: Jeder Treffer zählt als richtige Zuordnung (Obergrenze)" in aus
    assert re.search(r"Neue Dokumente im Monat \(Schätzung .*\): etwa \d+ \(", aus)
    assert "Hochrechnung der Federführung (Schätzung, Vorlagen ab 2020)" in aus and "bei rund " in aus
    assert re.search(r"je Bezeichnung \(federführend\): .*Stadtbetrieb \(Annahme\) \d+", aus)
    assert "Geschäftsbereich (Annahme)" in aus and "ohne Textebene (OCR nötig): " in aus
    assert re.search(r"Regel Stufe 6 \(.*\): erfüllt", aus)
    om = importlib.import_module("oparl_messung")
    assert om.amt_abgleichen("905", None) == "Ämterliste fehlt (zuerst organisationen)"
    assert om.amt_abgleichen("905", []).startswith("Ämterliste leer")
    assert om.amt_abgleichen("905", [("a", "Ressort 905"), ("b", "R 905")]) == "mehrdeutig (2)"
    assert om.amt_abgleichen("90", [("a", "Ressort 905"), ("b", "Amt 90.1")]) == "kein Treffer in organizations/at"
    m_ = om.RE_AMT.search("[Testdaten] Amt 402 Datenschutz")
    assert (m_.group(1), m_.group(2)) == ("Amt", "402")
    # ein zweiter Lauf kommt aus dem Cache (keine Anfrage)
    assert {z["content_type"] for z in zeilen} == {"application/pdf"}
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "100", obergrenze=1)
    zweiter = tsv(erg / "pdf_koepfe.tsv")
    assert (m["rc"], m["server"], m["lauf"]["cache"]) == (0, 0, "100") and {z["quelle"] for z in zweiter} == {"cache"}
    # Content-Type und Antwortzeit des Netzabrufs aus der Begleitdatei im Cache (nicht aus dem Abrufprotokoll)
    assert [(z["id"], z["content_type"], z["antwort_s"]) for z in zweiter] == [
        (z["id"], z["content_type"], z["antwort_s"]) for z in zeilen]


def test_pdf_kopf_erkennung_und_normalisierung():
    """Normalisierung (geschützte Leerzeichen, Bindestrich-Varianten, weiche Trennzeichen, Silbentrennung), alle
    Kandidaten mit Zeile und Lage zum ersten Abschnitt, Kopf ohne Abschnitt = erste 30 Zeilen, Regel für den
    federführenden Kandidaten (Annahme)."""
    om = importlib.import_module("oparl_messung")
    zeilen = om.text_normalisieren("[Testdaten] Kopf\r\n\r\nRessort 102\nStadt-\nbetrieb 12‑ x\n"
                                   "Ge­schäfts­bereich\n 3.1 \n Amt\n402\nBegründung:\nAmt 999\nElberfeld-\nWest")
    assert zeilen == ["[Testdaten] Kopf", "Ressort 102", "Stadtbetrieb 12- x", "Geschäftsbereich", "3.1", "Amt",
                      "402", "Begründung:", "Amt 999", "Elberfeld-", "West"]
    kandidaten, abschnitt = om.kopf_kandidaten(zeilen)
    assert abschnitt == 8
    assert [(k["kennung"], k["zeile"], k["kopf"]) for k in kandidaten] == [
        ("Ressort 102", 2, True), ("Stadtbetrieb 12", 3, True), ("Amt 402", 6, True), ("Amt 999", 9, False)]
    assert om.RE_AMT.search("Geschäftsbereich 3.1") is None                        # Nummer mit zwei oder drei Ziffern
    assert om.RE_AMT.search("Eigenbetrieb 01.2").group(0) == "Eigenbetrieb 01.2"
    assert om.RE_AMT.search("Ordnungsamt 402") is None and om.RE_AMT.search("Amt 4021") is None
    # Satzpunkt nach der Nummer: erkannt; Teilnummer mit Punkt und Ziffer: als Teil der Nummer
    for text, kennung in (("Zuständig: Amt 402.", "Amt 402"), ("Ressort 102. Weiter", "Ressort 102"),
                          ("Amt 402.13.", "Amt 402.13"), ("Amt 402.1x", "Amt 402.1")):
        assert om.RE_AMT.search(text).group(0) == kennung, text
    assert om.kopf_kandidaten(om.text_normalisieren("Zuständig: Ressort 102."))[0][0]["kennung"] == "Ressort 102"
    assert om.amt_abgleichen("402", [("a", "Amt 402."), ("b", "Amt 402.1")]) == "a"
    # Kandidat in der Zeile des Abschnitts selbst gehört nicht zum Kopf
    kandidaten, abschnitt = om.kopf_kandidaten(["[Testdaten] Kopf", "Begründung: Amt 402"])
    assert abschnitt == 2 and [(k["zeile"], k["kopf"]) for k in kandidaten] == [(2, False)]
    # ohne Abschnitt: Kopf = erste 30 Zeilen
    lang = [f"[Testdaten] Zeile {i}" for i in range(40)]
    lang[5], lang[35] = "Amt 402", "Ressort 102"
    kandidaten, abschnitt = om.kopf_kandidaten(lang)
    assert abschnitt is None and [(k["zeile"], k["kopf"]) for k in kandidaten] == [(6, True), (36, False)]
    # Regel: Lage und federführender Kandidat
    def k(kennung, zeile=1, kopf=True):
        return {"bezeichnung": kennung.split()[0], "nummer": kennung.split()[1], "kennung": kennung, "zeile": zeile,
                "kopf": kopf}
    assert om.federfuehrend([]) == (None, "keiner", "")
    assert om.federfuehrend([k("Amt 402", kopf=False)])[:2] == (None, "keiner")
    assert om.federfuehrend([k("Amt 402")])[1:] == ("ein Kandidat", "einzige Kennung im Kopf")
    assert om.federfuehrend([k("Amt 402"), k("Amt 402", 5)])[1] == "mehrere gleiche"
    feder, lage, regel = om.federfuehrend([k("Geschäftsbereich 11"), k("Ressort 102", 2), k("Amt 402", 3)])
    assert (feder["kennung"], lage) == ("Ressort 102", "mehrere verschiedene") and "(Annahme)" in regel
    feder, _, regel = om.federfuehrend([k("Stadtbetrieb 12"), k("Eigenbetrieb 13", 2)])
    assert feder["kennung"] == "Stadtbetrieb 12" and regel == "erster Kandidat im Kopf (Annahme)"
    # Klasse des Erzeugers: nur die Klasse, nie der Rohwert
    assert om.erzeuger_klasse({"/Producer": "Microsoft® Word für Microsoft 365", "/Creator": "x"}) == "Office-Programm"
    assert om.erzeuger_klasse({"/Producer": "[Testdaten] Erika Erfunden"}) == "andere"
    assert om.erzeuger_klasse({"/Creator": "Canon iR-ADV Scan"}) == "Scan/Texterkennung"
    assert om.erzeuger_klasse(None) == om.erzeuger_klasse({}) == "fehlt"
    # Größengrenze: RATSATLAS_PDF_MAX_BYTES darf nur senken
    assert om.pdf_grenze({}) == om.PDF_MAX_BYTES == 10 * 1024 * 1024
    assert om.pdf_grenze({"RATSATLAS_PDF_MAX_BYTES": "1000"}) == 1000
    for wert in ("0", "-5", "x", str(om.PDF_MAX_BYTES + 1)):
        assert om.pdf_grenze({"RATSATLAS_PDF_MAX_BYTES": wert}) == om.PDF_MAX_BYTES, wert


def test_pdf_datei_waehlen():
    """Wahl der Datei aus auxiliaryFile (Annahme): Name nennt die Referenz, dann die Vorlage oder den paperType, nie eine
    Anlage oder eine Datei mit anderem mimeType; sonst die erste; Stichprobe ohne Dateiliste: erste Datei."""
    om = importlib.import_module("oparl_messung")

    def d(name, url, mime="application/pdf", datei=None):
        return {"name": name, "fileName": datei, "mimeType": mime, "url": url}
    p = {"reference": "VO/0042/26", "paperType": "Bericht", "dateiliste": [
        d("[Testdaten] Anlage 1 zu VO/0042/26", "u1"), d("[Testdaten] Bericht", "u2"),
        d("[Testdaten] Text", "u3", datei="VO_42_2026.docx", mime="application/msword"), d("[Testdaten] Datei", "u4",
                                                                                          datei="42-26.pdf")]}
    assert om.datei_waehlen(p) == ("u4", 4, 4, "Name nennt die Referenz (Annahme)")
    p["dateiliste"].pop()
    assert om.datei_waehlen(p) == ("u2", 2, 3, "Name nennt die Vorlage (Annahme)")
    p["dateiliste"][1]["name"] = "[Testdaten] Stellungnahme"
    assert om.datei_waehlen(p) == ("u1", 1, 3, "erste Datei (kein Name als Vorlage erkannt)")
    assert om.datei_waehlen({"reference": "X", "dateiliste": [d("Drucksache", None), d("Anhang", "u9")]}) == (
        "u9", 2, 2, "erste Datei (kein Name als Vorlage erkannt)")
    assert om.datei_waehlen({"datei": "u", "dateien": 2}) == ("u", 1, 2, "erste Datei (Stichprobe ohne Dateiliste)")
    # Unterstrich und Ziffer als Trenner: „Anlage_1_…“ und „Anlage1.pdf“ sind Anlagen, „Vorlage_…“ ist die Vorlage
    p = {"reference": "VO/1380/26", "paperType": "Beschlussvorlage", "dateiliste": [
        d(None, "u1", datei="Anlage_1_VO_1380_26.pdf"), d(None, "u2", datei="Vorlage_VO_1380_26.pdf")]}
    assert om.datei_waehlen(p) == ("u2", 2, 2, "Name nennt die Referenz (Annahme)")
    p = {"reference": "X", "paperType": "Bericht", "dateiliste": [
        d(None, "u1", datei="Anlage1.pdf"), d(None, "u2", datei="Anlagen_2.pdf"), d(None, "u3", datei="Bericht_2026.pdf")]}
    assert om.datei_waehlen(p) == ("u3", 3, 3, "Name nennt die Vorlage (Annahme)")
    assert om.RE_ANLAGE.search("Planlage") is None and om.RE_VORLAGE_NAME.search("Vorlagenliste") is None
    assert om.datei_waehlen({"datei": None, "dateien": 0})[0] is None


def test_pdf_koepfe_fehlervarianten_und_groessengrenze(server, tmp_path):
    """404, defekte Datei, große Datei (über der Grenze: nicht gespeichert, Lauf geht weiter), andere Datei: je Datei
    vermerkt, eine Anfrage je Vorlage; keine Meldungen von pypdf; Regel Stufe 6 dann nicht erfüllt."""
    pytest.importorskip("pypdf")
    _bis_stichprobe(server, tmp_path)
    zuordnung = {}   # reihum in der Reihenfolge der Anfragen (Dateinummern der Auswahl folgen einem Muster)
    server.pdf_variante = lambda nr: zuordnung.setdefault(nr, ("404", "defekt", "gross", "anderes", None)[
        len(zuordnung) % 5])
    vorher = len(server.anfragen)
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "20", obergrenze=20, RATSATLAS_PDF_MAX_BYTES="200000")
    assert m["rc"] == 0 and m["server"] == 20 and m["lauf"]["ergebnis"] == "ok", m["stderr"]
    zeilen = tsv(tmp_path / "ergebnisse" / "pdf_koepfe.tsv")
    treffer = {z["treffer"] for z in zeilen}
    assert {"fehler: HTTP 404", "zu groß", "kein PDF"} <= treffer and any(t.startswith("fehler: Pdf") for t in treffer)
    gross = [z for z in zeilen if z["treffer"] == "zu groß"]
    assert all(z["bytes"] == "> 200000" and z["quelle"] == "netz" and z["antwort_s"] for z in gross)
    nummern = {int(re.search(r"/(\d+)\.pdf$", pf).group(1)) for pf, *_ in server.anfragen[vorher:]}
    gecacht = {p.name for p in (tmp_path / "cache" / "roh").glob("*.pdf")}
    om = importlib.import_module("oparl_messung")
    for nr in nummern:   # große Datei und 404 nicht im Cache, alle übrigen schon
        url = f"{server.body_url}/downloadfiles/{nr}.pdf"
        assert (om.abruf._cachepfad(url, ".pdf").name in gecacht) == (zuordnung[nr] not in ("404", "gross")), nr
    # große Dateien: Content-Length über der Grenze, Inhalt nicht gelesen (0 Bytes im Protokoll, Status 200)
    gross_urls = {om.abruf.abrufadresse(f"{server.body_url}/downloadfiles/{nr}.pdf") for nr in nummern
                  if zuordnung[nr] == "gross"}
    protokoll_gross = [z for z in protokoll(tmp_path) if z["quelle"] == "netz" and z["url"] in gross_urls]
    assert protokoll_gross and all((z["bytes"], z["status"]) == ("0", "200") for z in protokoll_gross)
    assert all(int(z["bytes"]) <= 200000 for z in protokoll(tmp_path) if z["quelle"] == "netz")
    # Content-Type je Datei aus dem Kopf der Antwort, auch bei 404 und zu großen Dateien (Testserver)
    typ = collections.defaultdict(set)
    for z in zeilen:
        typ[z["treffer"] if z["treffer"] in ("fehler: HTTP 404", "kein PDF", "zu groß") else "pdf"].add(z["content_type"])
    assert typ == {"fehler: HTTP 404": {"text/html"}, "kein PDF": {"application/octet-stream"},
                   "zu groß": {"application/pdf"}, "pdf": {"application/pdf"}}, typ
    assert "EOF marker" not in m["stderr"] and "Traceback" not in m["stderr"]
    _ohne_pdf_inhalt(m["stdout"], m["stderr"])
    aw = importlib.import_module("auswertung")
    aus = aw.auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert re.search(r"Regel Stufe 6 \(.*\): nicht erfüllt \(nur \d+ PDFs gelesen \(mindestens 50\); \d+ von 20 "
                     r"Dateien mit Fehler", aus)
    # Nenner der Quoten aus der bekannten Zuordnung: abgerufen = angefragt ohne 404, gelesen = nur gültige PDFs
    n_404 = sum(1 for z in zeilen if z["treffer"] == "fehler: HTTP 404")
    gelesen = [z for z in zeilen if z["treffer"] in aw.GELESEN]
    k = sum(1 for z in zeilen if z["treffer"] == "kennung")
    k_at = sum(1 for z in zeilen if z["treffer"] == "kennung" and "/organizations/at/" in z["abgleich"])
    assert n_404 == 4 and len(gelesen) == 4 and 0 < k < len(gelesen)
    assert f"Erkennungsquote (Kennung nach Regel im Kopf gefunden, Annahme, Zuordnung ungeprüft / abgerufen): {k} von " \
           f"{20 - n_404} (" in aus
    assert f"- bezogen auf gelesene PDFs: {k} von {len(gelesen)} (" in aus
    assert f"Abgleichquote (einer Organisation aus organizations/at zugeordnet / Kennung erkannt): {k_at} von {k}" in aus
    assert f"(Kennung nach Regel gefunden, {k} von 20 angefragten Dateien, " in aus
    assert f"(einer Organisation aus organizations/at zugeordnet, {k_at} von 20 angefragten Dateien, " in aus


def test_pdf_koepfe_html_statt_pdf_bricht_ab(server, tmp_path):
    """HTML statt PDF (mögliche Sperr- oder Fehlerseite): Abbruch der Art `inhalt` nach dieser Anfrage, Antwort aus dem
    Cache entfernt, Zeile vermerkt."""
    pytest.importorskip("pypdf")
    _bis_stichprobe(server, tmp_path)
    server.pdf_variante = lambda nr: "html"
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "5", obergrenze=5)
    assert m["rc"] == 2 and m["server"] == 1 and m["lauf"]["ergebnis"] == "abbruch (inhalt)", m["stderr"]
    assert "HTML statt PDF" in m["stderr"] and not list((tmp_path / "cache" / "roh").glob("*.pdf*"))
    zeilen = tsv(tmp_path / "ergebnisse" / "pdf_koepfe.tsv")
    assert [z["treffer"] for z in zeilen] == ["abbruch (inhalt)"]
    _ohne_pdf_inhalt(m["stdout"], m["stderr"], (tmp_path / "ergebnisse" / "pdf_koepfe.tsv").read_text(encoding="utf-8"))


@pytest.mark.parametrize("variante", ["gross", "html"])
def test_pdf_koepfe_langsame_antwort_bricht_ab(server, tmp_path, variante):
    """Antwort über RATSATLAS_MAX_DAUER: Abbruch auch bei einer Datei über der Größengrenze (abruf.py meldet dort
    `groesse` vor der Antwortzeit) und bei einer HTML-Seite (abruf.py speichert vor der Prüfung auf `langsam`; die Seite
    wird aus dem Cache entfernt, Art `inhalt`). Ein zweiter Lauf liest nichts aus dem Cache."""
    pytest.importorskip("pypdf")
    _bis_stichprobe(server, tmp_path)
    server.pdf_variante = lambda nr: variante
    server.verzoegerung = lambda pfad, abfrage: 0.5 if pfad.endswith(".pdf") else 0
    zusatz = {"RATSATLAS_MAX_DAUER": "0.2", "RATSATLAS_PDF_MAX_BYTES": "200000"}
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "5", obergrenze=5, **zusatz)
    art = "langsam" if variante == "gross" else "inhalt"
    assert m["rc"] == 2 and m["server"] == 1 and m["lauf"]["ergebnis"] == f"abbruch ({art})", m["stderr"]
    assert "Antwortzeit" in m["stderr"] and not list((tmp_path / "cache" / "roh").glob("*.pdf*"))
    assert [z["treffer"] for z in tsv(tmp_path / "ergebnisse" / "pdf_koepfe.tsv")] == [f"abbruch ({art})"]
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "5", obergrenze=5, **zusatz)
    assert m["lauf"]["cache"] == "0" and m["lauf"]["ergebnis"] == f"abbruch ({art})", m["stderr"]


def test_pdf_koepfe_im_prozess_grenze_je_aufruf_und_anzahl_geprueft(server, tmp_path, monkeypatch):
    """pdf-koepfe übergibt die Größengrenze je Anfrage als max_bytes und lässt abruf.MAX_BYTES unverändert (auch während
    des Kommandos und nach einem Abbruch); Meldungen von pypdf über warnings werden unterdrückt; --anzahl außerhalb
    1–100 endet vor der ersten Anfrage."""
    pytest.importorskip("pypdf")
    om = importlib.import_module("oparl_messung")
    monkeypatch.setattr(om, "STICHPROBE", tmp_path / "stichprobe_vorlagen.jsonl")
    monkeypatch.setattr(om, "ERG", tmp_path / "ergebnisse")
    om.ERG.mkdir()
    p = next(p for p in map(server.daten.vorlage, range(200)) if p["paperType"] == "Beschlussvorlage"
             and not p.get("underDirectionOf"))
    om.STICHPROBE.write_text(json.dumps({"id": p["id"], "reference": p["reference"], "paperType": p["paperType"],
                                         "date": p["date"], "underDirectionOf": False,
                                         "dateiliste": om._dateiliste(p)}) + "\n", encoding="utf-8")
    vorher = om.abruf.MAX_BYTES
    grenzen = []

    def hole(url, endung, max_bytes=None):
        grenzen.append(max_bytes)
        assert om.abruf.MAX_BYTES == vorher > om.PDF_MAX_BYTES
        raise om.Abbruch("[Testdaten] Sperre", "sperre")
    monkeypatch.setattr(om, "_hole", hole)
    with pytest.raises(om.Abbruch):
        om.pdf_koepfe(argparse.Namespace(anzahl=1))
    assert om.abruf.MAX_BYTES == vorher and grenzen == [om.PDF_MAX_BYTES]
    assert [z["treffer"] for z in tsv(om.ERG / "pdf_koepfe.tsv")] == ["abbruch (sperre)"]
    with warnings.catch_warnings(record=True) as gemeldet:
        warnings.simplefilter("always")
        with om._pypdf_still():
            warnings.warn("[Testdaten] Meldung aus pypdf", UserWarning)
        assert gemeldet == []
    for wert in ("0", "-1", "101"):
        m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", wert, obergrenze=5)
        assert m["rc"] == 2 and m["server"] == 0 and "--anzahl: 1 bis 100" in m["stderr"], wert


def test_stufe_6_ohne_pdf_freigabe_keine_anfrage(tmp_path):
    """Gegen einen Testserver, der nicht als lokal gilt (127.0.0.2, wie die Stadt): Mit RATSATLAS_MESSUNG_FREIGEGEBEN=ja,
    aber ohne RATSATLAS_PDF_FREIGEGEBEN=ja stellt pdf-koepfe keine Anfrage; mit beiden genau eine je Vorlage."""
    pytest.importorskip("pypdf")
    om = importlib.import_module("oparl_messung")
    with testserver.Testserver(host="127.0.0.2") as stadt:
        cache = tmp_path / "cache"
        cache.mkdir()
        vorlagen = [p for p in map(stadt.daten.vorlage, range(200)) if p["paperType"] == "Beschlussvorlage"
                    and not p.get("underDirectionOf")][:2]
        with (cache / "stichprobe_vorlagen.jsonl").open("w", encoding="utf-8") as f:
            for p in vorlagen:
                f.write(json.dumps({"id": p["id"], "name": p["name"], "reference": p["reference"],
                                    "paperType": p["paperType"], "date": p["date"], "underDirectionOf": False,
                                    "datei": om._erste_datei(p)[0], "dateien": len(p["auxiliaryFile"]),
                                    "dateiliste": om._dateiliste(p)}) + "\n")
        skript = str(EXPLORE / "oparl_messung.py")
        env = _wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="6", RATSATLAS_MAX_ANFRAGEN="2")
        ohne = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "2"], capture_output=True, text=True,
                              timeout=120, env=env)
        assert ohne.returncode == 1 and "RATSATLAS_PDF_FREIGEGEBEN" in ohne.stderr, ohne.stderr
        assert stadt.anfragen == [] and not (tmp_path / "ergebnisse" / "oparl_laeufe.tsv").exists()
        mit = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "2"], capture_output=True, text=True,
                             timeout=120, env={**env, "RATSATLAS_PDF_FREIGEGEBEN": "ja"})
    assert mit.returncode == 0, mit.stderr
    assert [pf for pf, *_ in stadt.anfragen] and all(re.search(r"/downloadfiles/\d+\.pdf$", pf)
                                                     for pf, *_ in stadt.anfragen) and len(stadt.anfragen) == 2
    assert tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]["ergebnis"] == "ok"


def test_wilson_hochrechnung_und_regel_stufe_6():
    aw = importlib.import_module("auswertung")
    assert aw.wilson(0, 0) is None and aw.wilson(0, 10)[0] == 0.0 and aw.wilson(10, 10)[1] == 1.0
    unten, oben = aw.wilson(50, 100)
    assert round(unten, 3) == 0.404 and round(oben, 3) == 0.596
    g = {"stichprobe_vorlagen": "800", "mit_underDirectionOf": "600", "verwaltung_ohne_underDirectionOf_mit_datei": "100",
         "aemterliste": "60"}
    h = aw.hochrechnung(g, 50, 100, gesamt=8000)
    assert (h["a"], h["v"], h["q"], h["anteil"]) == (0.75, 0.125, 0.5, 0.8125)
    assert h["unten"] < h["anteil"] < h["oben"] and h["n_anteil"] == 6500 and h["n_v"] == 1000
    assert aw.hochrechnung({}, 1, 2) is None and aw.hochrechnung(g, 0, 0) is None
    zeilen = [{"treffer": "kennung", "abgleich": "http://x/organizations/at/1"}] * 60 + [{"treffer": "nein"}] * 30 + [
        {"treffer": "fehler: HTTP 404"}] * 10
    zz = aw.pdf_zaehlung(zeilen)
    assert [len(zz[k]) for k in ("versucht", "abgerufen", "gelesen", "kennung", "abgeglichen", "fehler")] == [
        100, 90, 90, 60, 60, 10]
    ok = [{"kommando": "pdf-koepfe", "lauf": "7", "ergebnis": "ok"}]
    assert aw.regel_pdf(zz, ok, g) == "erfüllt"
    assert aw.regel_pdf(zz, [], g).startswith("nicht prüfbar")
    assert aw.regel_pdf(zz, [{"kommando": "pdf-koepfe", "lauf": "8", "ergebnis": "abbruch (langsam)"}], g).startswith(
        "nicht erfüllt (letzter pdf-koepfe-Lauf 8: abbruch (langsam))")
    assert "Ämterliste fehlt" in aw.regel_pdf(zz, ok, {**g, "aemterliste": "fehlt"})
    viele_fehler = aw.pdf_zaehlung(zeilen[:55] + [{"treffer": "zu groß"}] * 20)
    assert "20 von 75 Dateien mit Fehler" in aw.regel_pdf(viele_fehler, ok, g)


def test_hochrechnung_nach_jahr_gewichtet():
    """Die Auswahl nimmt gleich viele Vorlagen je Jahr; die Hochrechnung gewichtet die Quote mit dem Bestand je Jahr.
    Beispiel: Bestand 90 (2026) und 10 (2020), je 10 angefragt, Quote 90 % und 10 % → gewichtet 82 %, ungewichtet 50 %."""
    aw = importlib.import_module("auswertung")
    g = {"stichprobe_vorlagen": "100", "mit_underDirectionOf": "0", "verwaltung_ohne_underDirectionOf_mit_datei": "100",
         "verwaltung_ohne_underDirectionOf_mit_datei_2026": "90", "verwaltung_ohne_underDirectionOf_mit_datei_2020": "10"}
    je_jahr = {"2026": (9, 10), "2020": (1, 10)}
    h = aw.hochrechnung(g, 10, 20, je_jahr=je_jahr)
    assert h["gewichtet"] and round(h["anteil"], 6) == 0.82 and h["q_roh"] == 0.5
    assert h["unten"] < h["anteil"] < h["oben"] <= 1 and h["ohne_auswahl"] == []
    assert aw.hochrechnung(g, 10, 20)["anteil"] == 0.5 and not aw.hochrechnung(g, 10, 20)["gewichtet"]
    # Jahr ohne angefragte Datei: ungewichtete Quote, vermerkt
    h = aw.hochrechnung({**g, "verwaltung_ohne_underDirectionOf_mit_datei_2023": "0"}, 10, 20, je_jahr={"2026": (9, 10)})
    assert h["ohne_auswahl"] == ["2020", "2023"]
    zeilen = [{"jahr": "2026", "treffer": "kennung"}, {"jahr": "2026", "treffer": "nein"}, {"jahr": "2020"}]
    assert aw.je_jahr_zaehlen(zeilen, zeilen[:1]) == {"2026": (1, 2), "2020": (0, 1)}
    # Monate bis zur Zählung in Stufe 3 und manuelle Kontrolle
    assert round(aw.monate_bis([{"kommando": "umfang", "ergebnis": "ok", "start": "2026-11-09T23:05:00+01:00"}])) == 82
    assert aw.monate_bis([{"kommando": "umfang", "ergebnis": "abbruch (langsam)", "start": "2026-11-09T23:05:00+01:00"}]) \
        is None


def test_pdf_kontrolle_nur_urteile(tmp_path):
    aw = importlib.import_module("auswertung")
    assert aw.kontrolle_lesen(tmp_path, {"a"}) is None
    (tmp_path / "pdf_koepfe_kontrolle.tsv").write_text("id\turteil\na\trichtig\nb\tfalsch\nc\tunklar\nx\tfalsch\n",
                                                       encoding="utf-8")
    assert aw.kontrolle_lesen(tmp_path, {"a", "b", "c"}) == (1, 2)


def test_pdf_auswahl_gleichmaessig_ueber_die_jahre():
    om = importlib.import_module("oparl_messung")
    vorlagen = ([{"reference": f"VO/{i:04d}/24"} for i in range(10)] + [{"reference": f"VO/{i:04d}/25"} for i in range(2)]
                + [{"reference": f"VO/{i:04d}/26"} for i in range(10)])
    auswahl = om.auswahl_je_jahr(vorlagen, 9)
    zaehl = {j: sum(1 for p in auswahl if om.jahr_der_vorlage(p) == j) for j in ("2024", "2025", "2026")}
    assert zaehl == {"2024": 3, "2025": 2, "2026": 4}
    assert om.jahr_der_vorlage({"reference": "X/1", "date": "2021-05-01"}) == "2021" and om.jahr_der_vorlage({}) == "?"


def test_auswertung_ohne_protokoll_und_404_hinweis(tmp_path):
    auswertung = importlib.import_module("auswertung")
    zeilen = [{"quelle": "netz", "status": "404", "url": "http://x/papers?limit=100"},
              {"quelle": "netz", "status": "404", "url": "http://x/papers?modified_since=2026-11-01T00%3A00%3A00"},
              {"quelle": "netz", "status": "200", "url": "http://x/papers"}]
    assert auswertung.status_hinweise(zeilen, "kennzahlen") == {
        ("404", ""): 1, ("404", " (erwartet: Test mit URL-kodiertem Parameter)"): 1}
    erg = tmp_path / "ergebnisse"
    erg.mkdir()
    (erg / "oparl_laeufe.tsv").write_text(
        "lauf\tstufe\tkommando\tparameter\tstart\tende\tdauer_s\tnetz\tcache\tobergrenze\tprotokoll_von\t"
        "protokoll_bis\tergebnis\tmeldung\n1\t1\ttest\t\t2026-11-07T23:05:00+01:00\t2026-11-07T23:05:09+01:00\t9\t3\t0"
        "\t3\t0\t3\tok\t\n", encoding="utf-8")
    aus = auswertung.auswertung(tmp_path / "leer", erg)
    assert "Statuscodes und Antwortzeiten nicht prüfbar (Protokoll fehlt)" in aus and "- keine (" not in aus


# Befehl in STUFEN.md für die Neuauswertung von Stufe 6 ohne Netz (keine Stufe, keine Freigabe)
NUR_CACHE_BEFEHL = "RATSATLAS_NUR_CACHE=ja "


def test_stufenplan_befehle_sind_vollstaendig():
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    befehle = [z for z in text.splitlines() if "oparl_messung.py" in z and z.startswith("RATSATLAS_")
               and not z.startswith(NUR_CACHE_BEFEHL)]   # Neuauswertung ohne Netz: eigener Test
    assert len(befehle) == 10                                   # dazu zwei optionale: umfang --liste meeting|person
    assert all("ratsatlas-koeln" not in b and "stadt-koeln" not in b for b in befehle)
    for b in befehle:
        for teil in ("RATSATLAS_MESSUNG_FREIGEGEBEN=ja ", "RATSATLAS_KONTAKT=", "RATSATLAS_WIEDERHOLUNGEN=0 ",
                     "RATSATLAS_MAX_DAUER=5 ", "RATSATLAS_STUFE=", "RATSATLAS_MAX_ANFRAGEN="):
            assert teil in b, (teil, b)
    assert "export " not in text


def test_mehrere_befehle_einer_stufe_nur_nach_rueckgabewert_0():
    """Ein bash-Block mit mehreren Befehlen (Stufe 3) wird als Ganzes übernommen: Jeder Befehl außer dem letzten endet
    mit `&& \\`, damit nach einem Abbruch (Rückgabewert 2) keiner mehr läuft."""
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    bloecke = re.findall(r"```bash\n(.*?)```", text, re.S)
    mehrere = [b for b in bloecke if b.count("oparl_messung.py") > 1]
    assert mehrere, "Stufe 4 hat zwei Befehle"
    for block in mehrere:
        zeilen = [z for z in block.splitlines() if z.strip()]
        assert all(z.endswith(" && \\") for z in zeilen[:-1]) and not zeilen[-1].endswith("\\"), block
    # die Befehle bleiben einzeln vollständig (je Zeile ein Aufruf eines Skripts aus explore/ mit allen Variablen)
    assert all(len(re.findall(r"explore/(?:oparl_messung|geodaten|ortsnamen)\.py", b))
               == len([z for z in b.splitlines() if z.strip()]) for b in bloecke)


def test_probelauf_entspricht_stufenplan_und_auswertung(tmp_path):
    zeilen = probelauf.probelauf(tmp_path)
    assert all(z["ergebnis"] in ("ok", "übersprungen (pypdf fehlt)") for z in zeilen), zeilen
    gemessen = {(z["stufe"], z["kommando"]): (z.get("netz_folge"), z.get("netz_leer")) for z in zeilen
                if z["ergebnis"] == "ok"}
    erwartet = {("1", "test"): (3, 3), ("2", "kennzahlen"): (5, 8), ("3", "umfang"): (14, 16),
                ("4", "organisationen"): (4, 6), ("4", "sitzungen"): (1, 3), ("5", "stichprobe"): (6, 9)}
    if ("6", "pdf-koepfe") in gemessen:
        erwartet[("6", "pdf-koepfe")] = (100, 100)
    assert {k: v for k, v in gemessen.items() if k in erwartet} == erwartet
    om = importlib.import_module("oparl_messung")
    assert dict(((s, k), n) for s, k, _, n in probelauf.STUFEN)[("3", "umfang")] == om.hoechstzahl_umfang()
    # STUFEN.md nennt dieselben Befehle und Obergrenzen wie probelauf.STUFEN
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    befehle = re.findall(r"RATSATLAS_MAX_ANFRAGEN=(\d+)[^\n`]*?oparl_messung\.py ([a-z-]+)([^\n`&\\]*)", text)
    im_plan = {(k, " ".join(p.split()), int(n)) for n, k, p in befehle}
    assert {(k, " ".join(p), n) for _, k, p, n in probelauf.STUFEN} <= im_plan
    # Auswertung der Folge
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "folge" / "cache",
                                                            tmp_path / "folge" / "ergebnisse")
    assert "erfundenen Daten" in aus and "nicht aus Wuppertal" in aus and "| 1 | test | 3 | 0 | 200×3 |" in aus
    assert "| 2 | kennzahlen | 5 | 3 | 200×4, 404×1 |" in aus and "| 3 | umfang | 14 | 2 | 200×14 |" in aus
    assert "erwartet: Test mit URL-kodiertem Parameter" in aus
    assert "Parameter page; URL-kodiert nein" in aus
    with (tmp_path / "folge" / "cache" / probelauf.STICHPROBE).open(encoding="utf-8") as f:
        n = sum(1 for _ in f)   # Menge der Stichprobe aus den (erfundenen) Testdaten
    assert n >= 500 and f"| mainFile | 0 | {n} | 0 % |" in aus and f"| location | 0 | {n} | 0 % |" in aus
    assert "| grenze | grenzseite | 72 |" in aus and "Organisationen: 500 erfasst; je Präfix: gr 430, at 60, zz 10" in aus
    assert "jedes Jahr vertreten, keine Doppelungen, Sortierung nach created): erfüllt" in aus
    assert "Regel Stufe 3 (Grenzseite G als Zahl, Sortierung nach created ja, Lauf ok): erfüllt" in aus
    if ("6", "pdf-koepfe") in gemessen:   # gleichmäßig über 2020–2026
        assert "je Jahr: 2020 14, 2021 14, 2022 14, 2023 14, 2024 14, 2025 15, 2026 15" in aus
        assert "Regel Stufe 6 (mindestens 50 PDFs gelesen, höchstens 20 % Fehler, Ämterliste vorhanden, Lauf ok): " \
               "erfüllt" in aus and "Hochrechnung der Federführung (Schätzung" in aus


class ScheinProxy:
    """Lokaler Schein-Proxy: beantwortet jeden Tunnel (CONNECT) mit `connect` (Vorgabe 403) und unverschlüsselte
    Anfragen mit `get` (Vorgabe 407); er leitet nichts weiter. `anfragen`: (Methode, Ziel)."""

    def __init__(self, connect=403, get=407):
        self.anfragen = []
        proxy = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _ablehnen(self, code):
                proxy.anfragen.append((self.command, self.path))
                self.send_response(code)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_CONNECT(self):
                self._ablehnen(connect)

            def do_GET(self):
                self._ablehnen(get)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *a):
        self.server.shutdown()
        self.server.server_close()


def test_mindestabstand_fuer_anfragen_an_die_stadt(server, tmp_path, monkeypatch):
    om = importlib.import_module("oparl_messung")
    basis = {"RATSATLAS_MAX_ANFRAGEN": "3", "RATSATLAS_KONTAKT": "kontakt@example.invalid"}
    assert om.sichere_vorgaben({**basis, "RATSATLAS_ABSTAND": "3"}) == (
        {"wiederholungen": 0, "max_dauer": 5.0, "max_anfragen": 3, "abstand": 3.0}, [])
    for wert in ("1.9", "0", "-2", "nan", "inf"):
        assert any("RATSATLAS_ABSTAND" in f for f in om.sichere_vorgaben({**basis, "RATSATLAS_ABSTAND": wert})[1]), wert
    # als Prozess: alles übrige streng, aber RATSATLAS_ABSTAND=0 (aus probelauf.umgebung) → Abbruch vor der ersten Anfrage
    fremd = {"RATSATLAS_OPARL_SYSTEM": "http://example.invalid/oparl/system",
             "RATSATLAS_OPARL_BODY": "http://example.invalid/oparl/bodies/x", "RATSATLAS_MESSUNG_FREIGEGEBEN": "ja",
             "RATSATLAS_KONTAKT": "kontakt@example.invalid"}
    m = lauf(server, tmp_path, "test", obergrenze=3, **fremd)
    assert m["rc"] == 1 and "Abbruch vor der ersten Anfrage" in m["stderr"] and "RATSATLAS_ABSTAND" in m["stderr"]
    assert server.anfragen == [] and not (tmp_path / "cache" / "abrufe.tsv").exists()
    # vor jeder Anfrage an die Stadt: Abstand unter 2 s → kein Abruf; 2 s → Abruf
    monkeypatch.setenv("RATSATLAS_MESSUNG_FREIGEGEBEN", "ja")
    monkeypatch.setenv("RATSATLAS_ZEITFENSTER", "")              # Testadresse (.invalid): leerer Wert zulässig
    for name, wert in (("WIEDERHOLUNGEN", 0), ("MAX_DAUER", 5.0), ("MAX_ANFRAGEN", 3),
                       ("KONTAKT", "kontakt@example.invalid"), ("ABSTAND", 1.0),
                       ("PROTOKOLL", tmp_path / "cache" / "abrufe.tsv")):
        monkeypatch.setattr(om.abruf, name, wert)
    for name, wert in (("SYSTEM", "https://example.invalid/oparl/system"), ("BODY", "https://example.invalid/oparl/b"),
                       ("ERG", tmp_path / "erg"), ("_sperrfrist_geprueft", False)):
        monkeypatch.setattr(om, name, wert)
    monkeypatch.setattr(om, "hole", lambda *a, **k: b"geholt")   # kein Netz
    with pytest.raises(om.Abbruch, match="Abstand mindestens 2 s"):
        om._hole("https://example.invalid/oparl/system")
    monkeypatch.setattr(om.abruf, "ABSTAND", 2.0)
    assert om._hole("https://example.invalid/oparl/system") == b"geholt"


def test_proxy_ablehnung_erkennen():
    abruf = importlib.import_module("abruf")

    def tunnel(code, text):
        return urllib.error.URLError(OSError(f"Tunnel connection failed: {code} {text}"))
    for code, text in ((403, "Forbidden"), (405, "Method Not Allowed"), (407, "Proxy Authentication Required")):
        assert abruf.proxy_ablehnung(tunnel(code, text)) == code == abruf.tunnel_status(tunnel(code, text))
    assert abruf.proxy_ablehnung(urllib.error.HTTPError("http://x/", 407, "Proxy Authentication Required", {}, None)) == 407
    assert abruf.proxy_ablehnung(urllib.error.HTTPError("http://x/", 403, "Forbidden", {}, None)) is None
    # Proxy erreicht das Ziel nicht (502, 504) oder meldet Begrenzung/Überlastung (429, 503): keine Ablehnung
    for code, text in ((502, "Bad Gateway"), (504, "Gateway Timeout"), (503, "Service Unavailable"),
                       (429, "Too Many Requests")):
        assert abruf.proxy_ablehnung(tunnel(code, text)) is None and abruf.tunnel_status(tunnel(code, text)) == code
    for fehler in (urllib.error.URLError(ConnectionResetError("reset")), TimeoutError("timed out")):
        assert abruf.proxy_ablehnung(fehler) is None and abruf.tunnel_status(fehler) is None   # mögliche Sperre


def _fremd_ueber(proxy):
    """Umgebung für oparl_messung.py: Adressen der Stadt durch example.invalid ersetzt, alles über den Schein-Proxy."""
    return {"RATSATLAS_OPARL_SYSTEM": "https://example.invalid/oparl/system",
            "RATSATLAS_OPARL_BODY": "https://example.invalid/oparl/bodies/x", "RATSATLAS_MESSUNG_FREIGEGEBEN": "ja",
            "RATSATLAS_KONTAKT": "kontakt@example.invalid", "RATSATLAS_ABSTAND": "2",
            "HTTPS_PROXY": proxy.url, "https_proxy": proxy.url, "HTTP_PROXY": proxy.url, "http_proxy": proxy.url,
            "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}


@pytest.mark.parametrize("code", [403, 407])
def test_proxy_ablehnung_ist_keine_sperre(server, tmp_path, code):
    with ScheinProxy(connect=code) as proxy:
        m = lauf(server, tmp_path, "test", obergrenze=3, **_fremd_ueber(proxy))
    assert m["rc"] == 2 and m["lauf"]["ergebnis"] == "abbruch (proxy)", m["stderr"]
    assert proxy.anfragen == [("CONNECT", "example.invalid:443")]      # genau ein Versuch, keine Wiederholung
    assert m["server"] == 0 and m["lauf"]["netz"] == "1"
    assert "keine Anfrage hat die Stadt erreicht" in m["stderr"] and "example.invalid muss im Netz" in m["stderr"]
    z = protokoll(tmp_path)[-1]
    assert (z["status"], z["quelle"]) == (f"proxy {code}", "netz")
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "## Ablehnungen durch den Proxy der Arbeitsumgebung" in aus
    assert "Lauf 1 (test): 1 Anfrage(n) vom Proxy abgelehnt (Host example.invalid)" in aus
    assert f"Status proxy {code} × 1 (Ablehnung durch den Proxy der Arbeitsumgebung" in aus
    assert "mögliche Sperre" not in aus
    assert f"| – | test | 1 | 0 | proxy {code}×1 | – | – | 0 | abbruch (proxy) |" in aus   # keine Antwortzeit der Stadt


@pytest.mark.parametrize("code", [502, 504])
def test_proxy_erreicht_das_ziel_nicht_ist_moegliche_sperre(server, tmp_path, code):
    # 502/504 auf CONNECT: Der Proxy hat die Stadt angefragt, aber nicht erreicht – so zeigte sich die Sperre bei mandari
    with ScheinProxy(connect=code) as proxy:
        m = lauf(server, tmp_path, "test", obergrenze=3, **_fremd_ueber(proxy))
    assert m["rc"] == 2 and m["lauf"]["ergebnis"] == "abbruch (sperre)", m["stderr"]
    assert proxy.anfragen == [("CONNECT", "example.invalid:443")]      # genau ein Versuch, keine Wiederholung
    assert "mögliche Sperre" in m["lauf"]["meldung"] and "kein Hinweis auf eine Sperre" not in m["stderr"]
    z = protokoll(tmp_path)[-1]
    assert (z["status"], z["quelle"]) == (f"tunnel {code}", "netz")
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert f"Status tunnel {code} × 1 (beim Verbindungsaufbau über den Proxy: der Proxy erreicht den Server nicht; " \
           "mögliche Sperre: stoppen)" in aus
    assert "## Ablehnungen durch den Proxy der Arbeitsumgebung" not in aus


@pytest.mark.parametrize("code, art", [(403, "proxy"), (405, "proxy"), (407, "proxy"), (502, "sperre"),
                                       (504, "sperre"), (500, "sperre"), (429, "server"), (503, "server")])
def test_connect_antworten_des_proxys(tmp_path, monkeypatch, code, art):
    """Jede Antwort ≠ 200 auf CONNECT bricht ohne Wiederholung ab, auch wenn Wiederholungen nach 429/5xx erlaubt
    wären; nur 403/405/407 gelten als Ablehnung durch den Proxy (keine Sperre)."""
    abruf = importlib.import_module("abruf")
    with ScheinProxy(connect=code) as proxy:
        for name in ("HTTPS_PROXY", "https_proxy"):
            monkeypatch.setenv(name, proxy.url)
        for name in ("NO_PROXY", "no_proxy"):
            monkeypatch.setenv(name, "127.0.0.1,localhost")
        # Öffner neu bauen: der Proxy aus der Umgebung gilt ab dem Bau (sonst der Proxy der Arbeitsumgebung)
        monkeypatch.setattr(abruf, "_OEFFNER", urllib.request.build_opener(abruf._OhneWeiterleitung))
        for name, wert in (("CACHE", tmp_path), ("PROTOKOLL", tmp_path / "abrufe.tsv"), ("ABSTAND", 0.0),
                           ("WIEDERHOLUNGEN", 4), ("PAUSEN", [0.01] * 4), ("MAX_ANFRAGEN", 0),
                           ("_erste_netzanfrage", True), ("_sperre", None)):
            monkeypatch.setattr(abruf, name, wert)
        with pytest.raises(abruf.Abbruch) as e:
            abruf.hole("https://example.invalid/oparl/system", ".json")
    assert (e.value.art, e.value.code) == (art, code)
    assert proxy.anfragen == [("CONNECT", "example.invalid:443")]
    assert ("mögliche Sperre" in str(e.value)) == (art == "sperre")
    assert ("kein Hinweis auf eine Sperre" in str(e.value)) == (art == "proxy")
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert z["status"] == (f"proxy {code}" if art == "proxy" else f"tunnel {code}")


def test_mindestabstand_auch_zwischen_zwei_prozessen(server, tmp_path):
    """Zwei Prozesse nacheinander mit demselben Cache (wie Stufe 3): Auch die erste Anfrage des zweiten Prozesses folgt
    frühestens 2 s nach dem Ende der letzten Antwort des ersten, die erste des ersten frühestens 2 s nach dem Start."""
    env = probelauf.umgebung(server, tmp_path / "cache", tmp_path / "ergebnisse", 1)
    env["RATSATLAS_ABSTAND"] = "2"
    skript = "import sys; sys.path.insert(0, sys.argv[1]); import abruf; abruf.hole(sys.argv[2], '.json')"
    starts = []
    for url in (server.system_url, server.body_url):
        starts.append(time.monotonic())
        r = subprocess.run([sys.executable, "-c", skript, str(EXPLORE), url], env=env, capture_output=True, text=True,
                           timeout=60)
        assert r.returncode == 0, r.stderr
    assert len(server.eingang) == 2 and len(server.ausgang) == 2
    assert server.eingang[0] - starts[0] >= 2.0                       # erste Anfrage frühestens 2 s nach dem Start
    assert server.eingang[1] - server.ausgang[0] >= 2.0               # Prozessgrenze: Abstand ab Ende der Antwort
    assert [z["quelle"] for z in protokoll(tmp_path)] == ["netz", "netz"]


def test_erste_anfrage_wartet_auf_letzte_netzanfrage_im_protokoll(tmp_path, monkeypatch):
    abruf = importlib.import_module("abruf")
    jetzt = dt.datetime.now(ZoneInfo("Europe/Berlin")).replace(microsecond=0)
    kopf = "zeit\turl\tstatus\tbytes\tdauer_s\tquelle\tziel\n"
    pfad = tmp_path / "abrufe.tsv"
    pfad.write_text(kopf + f"{jetzt.isoformat()}\thttp://127.0.0.1:1/a\t200\t1\t0.10\tnetz\t\n"
                    "2099-01-01T00:00:00+01:00\thttp://127.0.0.1:1/b\tcache\t1\t0.00\tcache\t\n", encoding="utf-8")
    assert abruf.letzte_netzanfrage(pfad) == jetzt.timestamp()       # Zeilen aus dem Cache zählen nicht
    gewartet = []
    monkeypatch.setattr(abruf, "time", types.SimpleNamespace(monotonic=time.monotonic, time=time.time,
                                                              sleep=gewartet.append))
    for name, wert in (("PROTOKOLL", pfad), ("ABSTAND", 2.0), ("_letzte", time.monotonic() - 100),
                       ("_erste_netzanfrage", True)):
        monkeypatch.setattr(abruf, name, wert)
    abruf._warten()                    # Import lange her, aber die letzte Netzanfrage laut Protokoll gerade eben
    nach = time.time()
    assert len(gewartet) == 1 and gewartet[0] <= 3.0
    # Anfrage frühestens 2 s nach dem Ende der Antwort; das Ende liegt vor jetzt + 1 s (Zeit sekundengenau)
    assert nach + gewartet[0] >= jetzt.timestamp() + 3.0 - 1e-6
    abruf._warten()                    # danach gilt nur noch der Abstand innerhalb des Prozesses
    assert len(gewartet) == 1
    # ältere Netzanfrage (vor einer Stunde): kein Warten
    pfad.write_text(kopf + f"{(jetzt - dt.timedelta(hours=1)).isoformat()}\thttp://127.0.0.1:1/a\t200\t1\t0.10\tnetz\t\n",
                    encoding="utf-8")
    monkeypatch.setattr(abruf, "_erste_netzanfrage", True)
    abruf._warten()
    assert len(gewartet) == 1


GEO_FREIGABE = {"RATSATLAS_MAX_ANFRAGEN": "40", "RATSATLAS_KONTAKT": "test@example.invalid",
                "RATSATLAS_MESSUNG_FREIGEGEBEN": "ja"}


def test_geodaten_mindestwerte_und_ende_nach_sperre(tmp_path, monkeypatch):
    """explore/geodaten.py ohne Netz (hole ersetzt): Abstand ≥ 2 s, keine Wiederholung, Obergrenze, Kontakt,
    RATSATLAS_MESSUNG_FREIGEGEBEN=ja und Zeitfenster vor der ersten Anfrage erzwungen; nach sperre/server/proxy/
    obergrenze/langsam/parallel/tls/gesperrt/zeitfenster und HTTP 401/403/429 endet der ganze Lauf, nach einer
    Weiterleitung oder HTTP 404 nur dieser Katalog, nach einer zu großen Datei nur diese Datei. Nur Hosts der Stadt."""
    geodaten = importlib.import_module("geodaten")
    abruf = importlib.import_module("abruf")
    assert geodaten.vorgaben(GEO_FREIGABE) == ({"wiederholungen": 0, "abstand": 2.0, "max_anfragen": 40}, [])
    assert any("RATSATLAS_MAX_ANFRAGEN" in f for f in geodaten.vorgaben({})[1])     # Obergrenze ist Pflicht
    for env in ({"RATSATLAS_ABSTAND": "1.5"}, {"RATSATLAS_ABSTAND": "nan"}, {"RATSATLAS_WIEDERHOLUNGEN": "2"},
                {"RATSATLAS_ABSTAND": "x"}, {"RATSATLAS_MAX_ANFRAGEN": "0"}, {"RATSATLAS_MAX_ANFRAGEN": "x"},
                {"RATSATLAS_KONTAKT": ""}, {"RATSATLAS_KONTAKT": "<kontakt>"}, {"RATSATLAS_MESSUNG_FREIGEGEBEN": "nein"},
                {"RATSATLAS_MESSUNG_FREIGEGEBEN": ""}):
        assert geodaten.vorgaben({**GEO_FREIGABE, **env})[1], env
    for name in ("RATSATLAS_ABSTAND", "RATSATLAS_WIEDERHOLUNGEN", "RATSATLAS_MAX_ANFRAGEN", "RATSATLAS_KONTAKT",
                 "RATSATLAS_MESSUNG_FREIGEGEBEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RATSATLAS_ZEITFENSTER", "")      # Zeitfenster eigens unten
    monkeypatch.setattr(abruf, "ABSTAND", 0.0)
    monkeypatch.setattr(abruf, "WIEDERHOLUNGEN", 4)
    monkeypatch.setattr(abruf, "MAX_ANFRAGEN", 0)
    monkeypatch.setattr(abruf, "KONTAKT", "test@example.invalid")
    monkeypatch.setattr(abruf, "USER_AGENT", "ratsatlas-wuppertal-explore/0.1 (+test; test@example.invalid)")
    monkeypatch.setattr(abruf, "CACHE", tmp_path / "cache")   # main() schreibt _cache/geodaten_dateien.tsv
    monkeypatch.setattr(abruf, "PROTOKOLL", tmp_path / "cache" / "abrufe.tsv")   # Markerdatei daneben
    monkeypatch.delenv("RATSATLAS_NACH_ABBRUCH", raising=False)
    erg = tmp_path / "ergebnisse"
    monkeypatch.setattr(geodaten, "ERG", erg)
    aufrufe, grenzen = [], {}
    katalog = len([d for d in geodaten.DATENSAETZE if d.get("katalog")])
    direkt = len([d for d in geodaten.DATENSAETZE if d.get("datei")])
    assert (katalog, direkt) == (2, 4) and geodaten.geplante_anfragen() == 10

    def schein(fehler_bei):
        """hole ohne Netz: Katalogseite mit Verweis auf JSON-LD (DCAT), darin eine Datei; Direktdateien als
        GeoJSON bzw. Zip (erfundener Inhalt); Abbruch bei der Endung `fehler_bei`."""
        def hole(url, endung="", cache=True, max_bytes=None):
            aufrufe.append(url)
            grenzen[url] = max_bytes
            if endung in fehler_bei:
                raise fehler_bei[endung]
            if endung == ".html":
                return b'<a href="/dataset/beispiel/dcat.jsonld">DCAT</a>'
            if endung == ".jsonld":
                return json.dumps([{"@id": "d", "@type": [geodaten.DCAT + "Dataset"],
                                    geodaten.DCAT + "distribution": [{"@id": "v"}]},
                                   {"@id": "v", geodaten.DCAT + "downloadURL": [
                                       {"@id": "https://daten.wuppertal.de/test/beispiel.json"}]}]).encode()
            if endung == ".zip":
                b = io.BytesIO()
                with zipfile.ZipFile(b, "w") as z:
                    z.writestr("t.csv", "STRSCHL;STRNAME\n1;Teststr.\n")
                return b.getvalue()
            return json.dumps({"type": "FeatureCollection", "features": []}).encode()
        return hole

    monkeypatch.setattr(geodaten, "hole", schein({}))
    assert geodaten.main() == 1 and aufrufe == []                     # ohne Obergrenze, Kontakt, Freigabe
    for name, wert in GEO_FREIGABE.items():
        monkeypatch.setenv(name, wert)
    monkeypatch.setenv("RATSATLAS_ABSTAND", "0.5")
    assert geodaten.main() == 1 and aufrufe == []                     # zu kleiner Abstand
    monkeypatch.delenv("RATSATLAS_ABSTAND")
    monkeypatch.setenv("RATSATLAS_MESSUNG_FREIGEGEBEN", "nein")
    assert geodaten.main() == 1 and aufrufe == []                     # Messung nicht freigegeben
    monkeypatch.setenv("RATSATLAS_MESSUNG_FREIGEGEBEN", "ja")
    monkeypatch.setattr(geodaten, "im_zeitfenster", lambda jetzt=None: False)
    assert geodaten.main() == 1 and aufrufe == []                     # außerhalb des Zeitfensters
    monkeypatch.setattr(geodaten, "im_zeitfenster", lambda jetzt=None: True)
    monkeypatch.setattr(abruf, "KONTAKT", "")
    assert geodaten.main() == 1 and aufrufe == []                     # Kontakt fehlt im User-Agent
    monkeypatch.setattr(abruf, "KONTAKT", "test@example.invalid")
    # nach einem Abbruch sperrt das gemeinsame Laufprotokoll 12 Stunden (eigener Test unten); hier ausdrücklich frei
    monkeypatch.setenv("RATSATLAS_NACH_ABBRUCH", "ja")
    for art, code in (("sperre", None), ("server", 429), ("proxy", 403), ("obergrenze", None), ("langsam", None),
                      ("parallel", None), ("tls", None), ("gesperrt", None), ("zeitfenster", None), ("http", 401),
                      ("http", 403), ("http", 429)):
        for endung, n in ((".html", 1), (".jsonld", 2), (".json", 3)):   # Seite, Beschreibung, erste Datei
            aufrufe.clear()
            monkeypatch.setattr(geodaten, "hole", schein({endung: abruf.Abbruch(f"Test {art}", art, code)}))
            assert geodaten.main() == 2, (art, code, endung)
            assert len(aufrufe) == n, (art, endung)                   # keine weitere Anfrage
            assert not list(erg.glob("geodaten_*.tsv"))              # Ergebnisdateien unverändert, nur der Vermerk
            vermerk = tsv(erg / "oparl_laeufe.tsv")[-1]
            assert (vermerk["kommando"], vermerk["ergebnis"]) == ("geodaten", f"abbruch ({art})")
            assert not (tmp_path / "cache" / "lauf_offen.json").exists()   # Marker nach dem Vermerk entfernt
    assert (abruf.ABSTAND, abruf.WIEDERHOLUNGEN, abruf.MAX_ANFRAGEN) == (2.0, 0, 40)
    # Weiterleitung und HTTP 404 an der Katalogseite: nur dieser Katalog, die übrigen Datensätze laufen weiter
    weiter = abruf.Abbruch("Weiterleitung HTTP 301 nach https://example.invalid/neu nicht verfolgt", "weiterleitung",
                           301, "https://example.invalid/neu")
    for fehler, text in ((weiter, "example.invalid/neu"), (abruf.Abbruch("HTTP 404: x", "http", 404), "HTTP 404")):
        aufrufe.clear()
        monkeypatch.setattr(geodaten, "hole", schein({".html": fehler}))
        assert geodaten.main() == 0 and len(aufrufe) == katalog + direkt
        kat = tsv(erg / "geodaten_katalog.tsv")
        katalogzeilen = [z for z in kat if z["katalog_url"].startswith(geodaten.KATALOG_BASIS)]
        assert len(katalogzeilen) == katalog
        assert all(z["titel"] == f"nicht gefunden ({fehler})" and text in z["titel"] for z in katalogzeilen)
    # zu große Datei (Straßenverzeichnis): nur diese Datei, alle übrigen Anfragen laufen
    aufrufe.clear()
    monkeypatch.setattr(geodaten, "hole", schein({".zip": abruf.Abbruch("zu groß", "groesse")}))
    assert geodaten.main() == 0 and len(aufrufe) == geodaten.geplante_anfragen()
    # Größengrenze je Datei als max_bytes (max_mb), Katalogseiten und Beschreibungen ohne eigene Grenze; abruf.MAX_BYTES
    # bleibt unverändert
    for ds in geodaten.DATENSAETZE:
        if ds.get("datei"):
            assert grenzen[ds["datei"]] == ds["max_mb"] * geodaten.MB, ds["kennung"]
    assert all(g is None for u, g in grenzen.items() if u.startswith(geodaten.KATALOG_BASIS) or u.endswith(".jsonld"))
    assert abruf.MAX_BYTES == 250 * 1024 * 1024
    felder = tsv(erg / "geodaten_felder.tsv")
    assert any(z["datensatz"] == "strassenverzeichnis" and "zu groß" in z["ebene"] for z in felder)
    # nur Hosts der Stadt; Planungs-WMS und statistische Bezirke werden nicht abgefragt
    assert all(geodaten.stadt_host(u) for u in aufrufe)
    assert not any("maps.wuppertal.de" in u for u in aufrufe)
    with pytest.raises(abruf.Abbruch) as e:
        geodaten._hole("https://example.invalid/x.json", ".json")
    assert e.value.art == "adresse"


def test_geodaten_ableiten_ohne_netz(tmp_path, monkeypatch):
    """`ableiten` ohne Netz mit erfundenen Geometrien: Straße → Quartier per Point-in-Polygon (Mehrfachzuordnung,
    Grenzpunkt beim alphabetisch ersten Quartier), Zählprüfung, Feldnamen mit Regel bzw. Vorgabe, Muster der
    Hausnummern und B-Plan-Nummern; keine Einzeladressen in den Ergebnisdateien, B-Plan-Daten unverändert."""
    geodaten = importlib.import_module("geodaten")
    abruf = importlib.import_module("abruf")
    monkeypatch.setattr(abruf, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(geodaten, "hole", lambda *a, **k: pytest.fail("Netzanfrage in ableiten"))

    def quadrat(x0):
        return {"type": "Polygon", "coordinates": [[[x0, 51.0], [x0 + 0.1, 51.0], [x0 + 0.1, 51.1], [x0, 51.1],
                                                    [x0, 51.0]]]}
    quartiere = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"NR": i, "NAME": f"Testquartier {i}"}, "geometry": quadrat(7.0 + i / 10)}
        for i in range(2)]}
    punkte = [(7.05, "1", "Teststr.", "1"), (7.15, "1", "Teststr.", "12a"), (7.15, "2", "Erfundenweg", "3"),
              (7.1, "2", "Erfundenweg", "5"), (9.0, "3", "Außerhalbstr.", "7")]
    adressen = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"STRSCHL": s, "STRNAME": n, "HNR": h},
         "geometry": {"type": "Point", "coordinates": [x, 51.05]}} for x, s, n, h in punkte]}
    bplaene = {"spatialReference": {"wkid": 4326}, "features": [
        {"attributes": {"PLANNR": p}, "geometry": None} for p in ("1234", "1234V", "56/1")]}
    b_bytes = json.dumps(bplaene).encode()
    dateien = {"quartiere": ("https://daten.wuppertal.de/t/Q.json", json.dumps(quartiere).encode()),
               "adressen": ("https://daten.wuppertal.de/t/A.json", json.dumps(adressen).encode()),
               "bplaene_rechtsverbindlich": ("https://daten.wuppertal.de/t/B.json", b_bytes)}
    erg = tmp_path / "ergebnisse"
    geodaten.ableiten(dateien, erg)
    sq = tsv(erg / "strasse_quartier.tsv")
    assert list(sq[0]) == ["strassenname", "strassenschluessel", "quartier", "adresspunkte"]
    assert [(z["strassenname"], z["quartier"], z["adresspunkte"]) for z in sq] == [
        ("Erfundenweg", "Testquartier 0", "1"), ("Erfundenweg", "Testquartier 1", "1"),   # 7.1: Grenze → erstes
        ("Teststr.", "Testquartier 0", "1"), ("Teststr.", "Testquartier 1", "1")]
    abl = {(z["pruefung"], z["datensatz"]): z for z in tsv(erg / "geodaten_ableitungen.tsv")}
    assert abl[("anzahl", "quartiere")]["ergebnis"] == "abweichend"            # 2 statt 69
    assert abl[("anzahl", "stadtbezirke")]["ergebnis"] == "offen"              # nicht geladen
    assert abl[("feld strassenname", "adressen")]["wert"] == "STRNAME"
    assert abl[("feld name_quartier", "quartiere")]["wert"] == "NAME"           # NR ist Zahl, kein Name
    assert abl[("adresspunkte ohne quartier", "adressen")]["wert"] == "1"
    assert abl[("adresspunkte auf quartiersgrenze", "adressen")]["wert"] == "1"
    assert "99a ×1" in abl[("hausnummer muster", "adressen")]["anmerkung"]
    nummern = {z["muster"]: z["anzahl"] for z in tsv(erg / "geodaten_bplan_nummern.tsv")}
    assert nummern == {"9999": "1", "9999A": "1", "99/9": "1"}
    # keine Einzeladressen in den Ergebnisdateien
    for f in erg.iterdir():
        text = f.read_text(encoding="utf-8")
        assert "12a" not in text and "Außerhalbstr." not in text, f.name
    assert "ausgelassen" in geodaten.beschreibe("adressen", *dateien["adressen"])[0]["beispiel"]
    assert b_bytes == dateien["bplaene_rechtsverbindlich"][1]                    # B-Pläne unverändert
    # Vorgabe überschreibt die Erkennung; eine Vorgabe ohne passendes Feld lässt die Ableitung offen
    geodaten.ableiten(dateien, erg, {"quartiere.name_quartier": "FEHLT"})
    abl = {(z["pruefung"], z["datensatz"]): z for z in tsv(erg / "geodaten_ableitungen.tsv")}
    assert abl[("strasse_quartier", "adressen")]["ergebnis"] == "offen"
    # Kommando ableiten liest nur den Cache
    monkeypatch.setattr(geodaten, "ERG", erg)
    assert geodaten.main(["ableiten"]) == 1                                     # Cache leer
    for url, daten in dateien.values():
        p = abruf._cachepfad(url, ".json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(daten)
    geodaten._zuordnung_schreiben(dateien)
    assert geodaten.main(["ableiten"]) == 0 and len(tsv(erg / "strasse_quartier.tsv")) == 4
    assert geodaten.main(["ableiten", "--feld", "quartiere.name_quartier=NAME"]) == 0
    with pytest.raises(SystemExit):
        geodaten.main(["ableiten", "--feld", "ohne_gleichheitszeichen"])


def test_geodaten_hilfsfunktionen(monkeypatch):
    """Hosts der Stadt, http → https, Dateiauswahl, Zeitfenster 23–1 Uhr, Feldvorgaben und Muster (ohne Netz)."""
    geodaten = importlib.import_module("geodaten")
    for url, erwartet in (("https://daten.wuppertal.de/x.json", True), ("https://offenedaten-wuppertal.de/d", True),
                          ("https://maps.wuppertal.de/planung", True), ("https://wuppertal.de.example.invalid/", False),
                          ("https://nichtwuppertal.de/x", False), ("https://example.invalid/x", False)):
        assert geodaten.stadt_host(url) is erwartet, url
    assert geodaten._https("http://daten.wuppertal.de/a/b.json?x=1") == "https://daten.wuppertal.de/a/b.json?x=1"
    assert geodaten._https("http://example.invalid/a.json") == "http://example.invalid/a.json"
    zeilen = [{"download_url": "https://example.invalid/fremd.json; https://daten.wuppertal.de/t/b.csv; "
                               "https://daten.wuppertal.de/t/b.zip; https://daten.wuppertal.de/t/b.kml",
               "access_url": "http://daten.wuppertal.de/t/b_EPSG25832.json; "
                             "http://daten.wuppertal.de/t/b_EPSG4326.json"}]
    assert geodaten.waehle_dateien(zeilen) == ["https://daten.wuppertal.de/t/b_EPSG4326.json"]
    assert geodaten.waehle_dateien(zeilen, 3) == ["https://daten.wuppertal.de/t/b_EPSG4326.json",
                                                  "https://daten.wuppertal.de/t/b_EPSG25832.json",
                                                  "https://daten.wuppertal.de/t/b.zip"]
    monkeypatch.delenv("RATSATLAS_ZEITFENSTER", raising=False)
    berlin = ZoneInfo("Europe/Berlin")
    for stunde, erwartet in ((22, False), (23, True), (0, True), (1, False), (12, False)):
        assert geodaten.im_zeitfenster(dt.datetime(2026, 11, 9, stunde, 30, tzinfo=berlin)) is erwartet, stunde
    assert geodaten._feldvorgaben(["adressen.strassenname=STRNAME"]) == {"adressen.strassenname": "STRNAME"}
    assert geodaten.muster("1234V") == "9999A" and geodaten.muster(" 56/1a ") == "99/9a"
    assert geodaten.erkenne_feld(["A", "B"], [], "plannummer", "B") == ("B", "Vorgabe")
    assert geodaten.erkenne_feld(["A"], [], "plannummer", "C")[0] is None


def _laeufe(erg, *zeilen):
    kopf = ("lauf", "stufe", "kommando", "parameter", "start", "ende", "dauer_s", "netz", "cache", "obergrenze",
            "protokoll_von", "protokoll_bis", "ergebnis", "meldung")
    erg.mkdir(parents=True, exist_ok=True)
    (erg / "oparl_laeufe.tsv").write_text("\n".join("\t".join(map(str, z)) for z in (kopf, *zeilen)) + "\n",
                                          encoding="utf-8")


def test_auswertung_ordnet_protokollzeilen_nur_im_zeitraum_des_laufs_zu(tmp_path):
    auswertung = importlib.import_module("auswertung")
    cache, erg = tmp_path / "cache", tmp_path / "ergebnisse"
    cache.mkdir()
    zeilen = [("2026-11-07T23:05:01+01:00", "https://example.invalid/a"),   # Lauf 1
              ("2026-11-07T23:05:03+01:00", "https://example.invalid/b"),   # Lauf 1
              ("2026-11-08T23:05:01+01:00", "https://example.invalid/c"),   # vor dem Start von Lauf 2
              ("2026-11-09T23:05:01", "https://example.invalid/d")]         # ohne Zone (Lauf 3)
    (cache / "abrufe.tsv").write_text("zeit\turl\tstatus\tbytes\tdauer_s\tquelle\tziel\n" + "".join(
        f"{t}\t{u}\t200\t10\t0.50\tnetz\t\n" for t, u in zeilen), encoding="utf-8")
    _laeufe(erg, (1, 1, "test", "", "2026-11-07T23:05:00+01:00", "2026-11-07T23:05:09+01:00", 9, 2, 0, 3, 0, 2, "ok", ""),
            (2, 2, "kennzahlen", "", "2026-11-08T23:10:00+01:00", "2026-11-08T23:10:09+01:00", 9, 1, 0, 10, 2, 3, "ok", ""),
            (3, 3, "organisationen", "", "2026-11-09T23:05:00+01:00", "2026-11-09T23:05:09+01:00", 9, 1, 0, 5, 3, 4,
             "ok", ""),
            (4, 4, "sitzungen", "", "2026-11-10T23:05:00+01:00", "2026-11-10T23:05:09+01:00", 9, 2, 0, 3, 4, 6, "ok", ""))
    aus = auswertung.auswertung(cache, erg)
    assert "| 1 | test | 2 | 0 | 200×2 | 0.50 | 0.50 | 20 | ok |" in aus
    for nr, kommando in ((2, "kennzahlen"), (3, "organisationen"), (4, "sitzungen")):
        assert (f"Lauf {nr} ({kommando}): Statuscodes und Antwortzeiten nicht prüfbar (Protokollzeilen passen nicht "
                "zum Lauf)") in aus
    assert "| 2 | kennzahlen | 1 | 0 | nicht prüfbar (Protokollzeilen passen nicht zum Lauf) |" in aus
    assert "Weitere Zeilen im Abrufprotokoll ohne Lauf (z. B. Zeit außerhalb eines Laufs): 2" in aus
    # ohne Abrufprotokoll bleibt es bei „Protokoll fehlt“
    assert "Statuscodes und Antwortzeiten nicht prüfbar (Protokoll fehlt)" in auswertung.auswertung(tmp_path / "x", erg)


def test_regel_stufe_5_nur_nach_vollstaendigem_lauf(tmp_path):
    auswertung = importlib.import_module("auswertung")
    gut = [{"feld": "Vorlagen 2020-01-01 bis 2026-12-31", "vorhanden": "755", "von": "800"},
           {"feld": "doppelte Kennungen", "vorhanden": "0", "von": "800"},
           {"feld": "Seiten nicht absteigend nach created", "vorhanden": "0", "von": "8"},
           {"feld": "Jahre 2020–2026 ohne Vorlage", "vorhanden": "0", "von": "7"},
           {"feld": "Seiten nicht absteigend nach date (informativ)", "vorhanden": "8", "von": "8"},
           {"feld": "date ab Stichtag trotz created vor Stichtag (in der Stichprobe)", "vorhanden": "12", "von": "755"},
           {"feld": "nicht erfasst: date ab Stichtag auf Seiten ab G (aus Stufe 3, Untergrenze)", "vorhanden": "offen",
            "von": "–"}]
    ok = {"lauf": "4", "kommando": "stichprobe", "ergebnis": "ok"}
    abgebrochen = {"lauf": "5", "kommando": "stichprobe", "ergebnis": "abbruch (proxy)"}
    andere = {"lauf": "6", "kommando": "sitzungen", "ergebnis": "abbruch (server)"}
    assert auswertung.regel_stichprobe(gut, [ok, andere]) == "erfüllt"   # date-Sortierung nur informativ
    assert auswertung.regel_stichprobe(gut, [ok, abgebrochen]).startswith("nicht prüfbar (Lauf abgebrochen)")
    assert auswertung.regel_stichprobe(gut, []).startswith("nicht prüfbar")
    assert auswertung.regel_stichprobe([], [ok]) is None
    wenig = [dict(gut[0], vorhanden="499")] + gut[1:]
    assert auswertung.regel_stichprobe(wenig, [ok]).startswith("nicht erfüllt (nur 499 Vorlagen (mindestens 500))")
    for i, text in ((1, "doppelte Kennungen 2"), (2, "Seiten nicht absteigend nach created 2"),
                    (3, "Jahre 2020–2026 ohne Vorlage: 2")):
        falsch = [dict(z, vorhanden="2") if j == i else z for j, z in enumerate(gut)]
        assert text in auswertung.regel_stichprobe(falsch, [ok]), i
    # in der Auswertung: Zählungen in Ordnung, aber der letzte stichprobe-Lauf ist abgebrochen
    erg = tmp_path / "ergebnisse"
    _laeufe(erg, (4, 5, "stichprobe", "", "2026-11-09T23:05:00+01:00", "2026-11-09T23:05:30+01:00", 30, 9, 0, 9, 0, 0,
                  "ok", ""),
            (5, 5, "stichprobe", "", "2026-11-11T23:05:00+01:00", "2026-11-11T23:05:01+01:00", 1, 1, 0, 9, 0, 0,
             "abbruch (proxy)", "Ablehnung durch den Proxy"))
    (erg / "oparl_stichprobe_bedeckung.tsv").write_text("feld\tvorhanden\tvon\n" + "".join(
        f"{z['feld']}\t{z['vorhanden']}\t{z['von']}\n" for z in gut), encoding="utf-8")
    aus = auswertung.auswertung(tmp_path / "cache", erg)
    assert ("Regel Stufe 5 (mindestens 500 Vorlagen 2020–2026, jedes Jahr vertreten, keine Doppelungen, Sortierung nach "
            "created): nicht prüfbar (Lauf abgebrochen)") in aus
    assert "Sortierung nach created): erfüllt" not in aus


def test_stufenbefehle_mit_kontakt_und_strengen_vorgaben():
    om = importlib.import_module("oparl_messung")
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    assert "<Kontaktadresse" not in text
    befehle = [z for z in text.splitlines() if "oparl_messung.py" in z and z.startswith("RATSATLAS_")
               and not z.startswith(NUR_CACHE_BEFEHL)]
    assert len(befehle) == 10
    for b in befehle:
        env = {k: v.strip('"') for k, v in re.findall(r'(RATSATLAS_[A-Z_]+)=("[^"]*"|\S+)', b)}
        assert env["RATSATLAS_KONTAKT"] == "contact@nozilla.de", b
        if env["RATSATLAS_MAX_ANFRAGEN"].isdigit():   # Stufe 4 optional: Obergrenze erst nach Stufe 4
            werte, fehler = om.sichere_vorgaben(env)
            assert fehler == [] and werte["abstand"] >= 2, (b, fehler)


def _abruf_im_prozess(monkeypatch, cache, **zusatz):
    """explore/abruf.py im Testprozess: eigener Cache, Abstand 0, Wiederholungen erlaubt (um zu zeigen, dass trotzdem
    nicht wiederholt wird), Öffner ohne Proxy; die Sperrdatei des Prozesses wird nach dem Test freigegeben."""
    abruf = importlib.import_module("abruf")
    werte = {"CACHE": cache, "PROTOKOLL": cache / "abrufe.tsv", "ABSTAND": 0.0, "WIEDERHOLUNGEN": 4,
             "PAUSEN": [0.01] * 4, "MAX_ANFRAGEN": 0, "_erste_netzanfrage": True, "_sperre": None,
             "_OEFFNER": urllib.request.build_opener(abruf._OhneWeiterleitung, urllib.request.ProxyHandler({}))}
    for name, wert in {**werte, **zusatz}.items():
        monkeypatch.setattr(abruf, name, wert)
    return abruf


UNVOLLSTAENDIG = {   # (Antwort, Status im Protokoll, Bytes im Protokoll)
    "content-length": (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n"
                       b"{\"data\": [", "IncompleteRead", 10),
    "chunked": (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n"
                b"5\r\n{\"a\":\r\n", "IncompleteRead", 5),
    "statuszeile": (b"GARBAGE\r\n\r\n", "BadStatusLine", 0),
}


@pytest.mark.parametrize("fall", list(UNVOLLSTAENDIG))
def test_abgeschnittene_oder_unlesbare_antwort_ist_moegliche_sperre(tmp_path, monkeypatch, roher_server, fall):
    """Weniger Bytes als Content-Length (read(n) meldet das nicht), chunked ohne Abschluss, unlesbare Statuszeile:
    Art `sperre`, eine Anfrage, Protokollzeile, nichts im Cache."""
    antwort, status, n = UNVOLLSTAENDIG[fall]
    server = roher_server(antwort)
    abruf = _abruf_im_prozess(monkeypatch, tmp_path)
    url = f"{server.url}/oparl/system"
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(url, ".json")
    assert e.value.art == "sperre" and "mögliche Sperre" in str(e.value)
    assert server.anfragen == ["GET /oparl/system HTTP/1.1"]          # keine Wiederholung trotz WIEDERHOLUNGEN=4
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert (z["status"], z["bytes"], z["quelle"]) == (status, str(n), "netz")
    assert not abruf._cachepfad(url, ".json").exists()               # nichts im Cache


def test_unlesbare_connect_antwort_ist_moegliche_sperre(tmp_path, monkeypatch, roher_server):
    proxy = roher_server(b"GARBAGE\r\n\r\n")
    for name in ("HTTPS_PROXY", "https_proxy"):
        monkeypatch.setenv(name, proxy.url)
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(name, "127.0.0.1,localhost")
    abruf = importlib.import_module("abruf")
    abruf = _abruf_im_prozess(monkeypatch, tmp_path, _OEFFNER=urllib.request.build_opener(abruf._OhneWeiterleitung))
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole("https://example.invalid/oparl/system", ".json")
    assert e.value.art == "sperre" and "BadStatusLine" in str(e.value)
    assert proxy.anfragen == ["CONNECT example.invalid:443 HTTP/1.1"]
    assert tsv(tmp_path / "abrufe.tsv")[-1]["status"] == "BadStatusLine"


def test_abgeschnittene_antwort_beendet_den_lauf_als_moegliche_sperre(server, tmp_path):
    server.abschneiden = lambda pfad: pfad.endswith("/bodies/0001")
    m = lauf(server, tmp_path, "test", obergrenze=3)
    assert m["rc"] == 2 and m["lauf"]["ergebnis"] == "abbruch (sperre)", m["stderr"]
    assert m["server"] == 2 and "Mögliche Sperre" in m["stderr"]
    assert protokoll(tmp_path)[-1]["status"] == "IncompleteRead"
    assert len(list((tmp_path / "cache" / "roh").glob("*.json"))) == 1   # nur das System, nicht der Body
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "Status IncompleteRead × 1 (mögliche Sperre: stoppen)" in aus


@pytest.mark.parametrize("code", [502, 504])
def test_502_504_als_antwort_ist_moegliche_sperre(server, tmp_path, monkeypatch, code):
    """HTTP 502/504 als Antwort (auch im Tunnel des Proxys der Arbeitsumgebung): mögliche Sperre, keine Wiederholung;
    503 bleibt Art `server` (mit erlaubten Wiederholungen wiederholt)."""
    server.stoerung = lambda pfad, abfrage: code if pfad.endswith("/oparl/system") else None
    m = lauf(server, tmp_path, "test", obergrenze=3)
    assert m["rc"] == 2 and m["lauf"]["ergebnis"] == "abbruch (sperre)", m["stderr"]
    assert m["server"] == 1 and "Mögliche Sperre" in m["stderr"]
    assert protokoll(tmp_path)[-1]["status"] == str(code)
    abruf = _abruf_im_prozess(monkeypatch, tmp_path / "im_prozess")
    vorher = len(server.anfragen)
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(server.system_url, ".json")
    assert (e.value.art, e.value.code) == ("sperre", code) and len(server.anfragen) - vorher == 1
    server.stoerung = lambda pfad, abfrage: 503
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(server.system_url, ".json")
    assert (e.value.art, e.value.code) == ("server", 503) and len(server.anfragen) - vorher == 6


def test_zweiter_gleichzeitiger_prozess_bricht_vor_der_ersten_anfrage_ab(server, tmp_path):
    """Sperre abruf.lock (Ort RATSATLAS_SPERRE, hier tmp_path/sperre): Hält ein Prozess sie, bricht ein zweiter ohne
    Anfrage ab, auch mit anderem Cache (wie aus einer anderen Arbeitskopie)."""
    env = probelauf.umgebung(server, tmp_path / "cache", tmp_path / "ergebnisse", 3)
    assert env["RATSATLAS_SPERRE"] == str(tmp_path / "sperre")
    halter = ("import sys; sys.path.insert(0, sys.argv[1]); import abruf; abruf.sperre_halten(); "
              "print('bereit', flush=True); sys.stdin.read()")
    p = subprocess.Popen([sys.executable, "-c", halter, str(EXPLORE)], env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True)
    try:
        assert p.stdout.readline().strip() == "bereit"
        m = lauf(server, tmp_path, "test", obergrenze=3, cache="anderer_cache")   # gleiche Sperre, anderer Cache
        assert m["rc"] == 2 and m["lauf"]["ergebnis"] == "abbruch (parallel)", m["stderr"]
        assert server.anfragen == [] and m["lauf"]["netz"] == "0" and "anderer Abrufprozess" in m["stderr"]
        assert not (tmp_path / "cache" / "abrufe.tsv").exists() and (tmp_path / "sperre" / "abruf.lock").exists()
    finally:
        p.stdin.close()
        p.wait(timeout=30)
    m = lauf(server, tmp_path, "test", obergrenze=3, cache="anderer_cache")   # danach ist die Sperre frei
    assert m["rc"] == 0 and m["server"] == 3, m["stderr"]
    assert len(protokoll(tmp_path, "anderer_cache")) == 3


def test_unlesbare_antwort_wird_aus_dem_cache_entfernt(server, tmp_path, monkeypatch):
    """oparl_messung._json: Eine unlesbare Antwort (HTML mit Status 200) bleibt nicht im Cache; ein späterer Lauf liest
    sie nicht ohne Anfrage als gültig, sondern fragt erneut."""
    om = importlib.import_module("oparl_messung")
    abruf = _abruf_im_prozess(monkeypatch, tmp_path / "cache")
    monkeypatch.setattr(om, "SYSTEM", server.system_url)           # lokaler Probelauf: nur lokale Adressen erlaubt
    monkeypatch.setattr(om, "BODY", server.body_url)
    server.stoerung = lambda pfad, abfrage: 200 if pfad.endswith("/bodies/0001") else None
    pfad = abruf._cachepfad(server.body_url, ".json")
    with pytest.raises(ValueError):
        om._json(server.body_url)
    assert not pfad.exists() and len(server.anfragen) == 1
    server.stoerung = lambda pfad, abfrage: None
    assert om._json(server.body_url)["id"] == server.body_url                    # erneut gefragt, jetzt gültig
    assert len(server.anfragen) == 2 and pfad.exists()
    assert om._json(server.body_url)["id"] == server.body_url and len(server.anfragen) == 2   # aus dem Cache


def test_letzter_abbruch_innerhalb_von_12_stunden(tmp_path):
    om = importlib.import_module("oparl_messung")
    erg, jetzt = tmp_path / "erg", dt.datetime(2026, 11, 8, 0, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    datei = erg / "oparl_laeufe.tsv"
    assert om.letzter_abbruch(datei, jetzt) is None                       # noch kein Lauf

    def zeile(nr, ende, ergebnis):
        return (nr, 3, "organisationen", "--seiten 4", ende, ende, 1, 2, 0, 5, 0, 2, ergebnis, "Test")
    for ende, ergebnis, gesperrt in (
            ("2026-11-07T23:10:00+01:00", "abbruch (server)", True),
            ("2026-11-07T23:10:00+01:00", "abbruch (proxy)", True),
            ("2026-11-07T23:10:00+01:00", "fehler (JSONDecodeError)", True),
            ("2026-11-07T23:10:00", "abbruch (sperre)", True),            # ohne Zone: Ortszeit Europe/Berlin
            ("", "abbruch (sperre)", True),                               # ohne Ende: vorsichtshalber gesperrt
            ("2026-11-07T23:10:00+01:00", "ok", False),
            ("2026-11-07T23:10:00+01:00", "unterbrochen", True),          # Strg+C oder Signal (Runde 9)
            ("2026-11-07T23:10:00+01:00", "abbruch (tls)", True),         # Einstellung, aber Sperrfrist
            ("2026-11-07T12:29:00+01:00", "abbruch (server)", False)):    # vor mehr als 12 Stunden
        _laeufe(erg, zeile(1, "2026-11-06T23:10:00+01:00", "abbruch (sperre)"), zeile(2, ende, ergebnis))
        treffer = om.letzter_abbruch(datei, jetzt)
        assert (treffer is not None) == gesperrt, (ende, ergebnis)
        assert treffer is None or treffer["lauf"] == "2"                  # maßgeblich ist der letzte Lauf


def _wie_die_stadt(stadt, tmp_path, **zusatz):
    """Umgebung für oparl_messung.py gegen einen Testserver auf 127.0.0.2: gilt nicht als lokal, also gelten Freigabe,
    Zeitfenster (hier offen), strenge Vorgaben, Abstand ≥ 2 s und die Prüfung des letzten Laufs."""
    assert stadt.system_url.startswith("http://127.0.0.2:")
    keine = ",".join(x for x in (os.environ.get("NO_PROXY", ""), "127.0.0.1,127.0.0.2,localhost") if x)
    env = {k: v for k, v in os.environ.items() if not k.startswith("RATSATLAS_")}
    env.update({"RATSATLAS_OPARL_SYSTEM": stadt.system_url, "RATSATLAS_OPARL_BODY": stadt.body_url,
                "RATSATLAS_SPERRE": str(tmp_path / "sperre"),   # Sperrdatei nie in ~/.cache (echte Messung parallel)
                "RATSATLAS_MESSUNG_FREIGEGEBEN": "ja", "RATSATLAS_ZEITFENSTER": "",
                "RATSATLAS_KONTAKT": "kontakt@example.invalid", "RATSATLAS_WIEDERHOLUNGEN": "0",
                "RATSATLAS_MAX_DAUER": "5", "RATSATLAS_CACHE": str(tmp_path / "cache"),
                "RATSATLAS_ERGEBNISSE": str(tmp_path / "ergebnisse"), "NO_PROXY": keine, "no_proxy": keine, **zusatz})
    return env


def test_nach_abbruch_keine_weitere_anfrage_an_die_stadt(tmp_path):
    """Stufe 4 ohne `&&` ausgeführt: Der erste Prozess bricht mit 503 ab, der zweite schickt keine Anfrage (letzter Lauf
    in oparl_laeufe.tsv vor weniger als 12 Stunden abgebrochen)."""
    with testserver.Testserver(host="127.0.0.2") as stadt:
        stadt.stoerung = lambda pfad, abfrage: 503 if pfad.endswith("/organizations") else None
        skript = str(EXPLORE / "oparl_messung.py")
        erster = subprocess.run([sys.executable, skript, "organisationen", "--seiten", "5"], capture_output=True,
                                text=True, timeout=120,
                                env=_wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="4", RATSATLAS_MAX_ANFRAGEN="6"))
        assert erster.returncode == 2 and len(stadt.anfragen) == 2, erster.stderr     # Body, Liste mit 503
        zweiter = subprocess.run([sys.executable, skript, "sitzungen", "--seiten", "2"], capture_output=True, text=True,
                                 timeout=120,
                                 env=_wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="4", RATSATLAS_MAX_ANFRAGEN="3"))
    assert zweiter.returncode == 1 and "RATSATLAS_NACH_ABBRUCH" in zweiter.stderr, zweiter.stderr
    assert "abbruch (server)" in zweiter.stderr
    assert len(stadt.anfragen) == 2                                           # keine Anfrage des zweiten Prozesses
    assert [z["ergebnis"] for z in tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")] == ["abbruch (server)"]


def test_freigabe_nach_abbruch_nur_ausdruecklich(tmp_path, monkeypatch):
    """Nach einem Abbruch vor weniger als 12 Stunden: ohne RATSATLAS_NACH_ABBRUCH keine Anfrage (Rückgabewert 1), mit
    RATSATLAS_NACH_ABBRUCH=ja geht der Lauf weiter (hier ohne Netz: hole ersetzt)."""
    om = importlib.import_module("oparl_messung")
    erg = tmp_path / "erg"
    jetzt = dt.datetime.now(ZoneInfo("Europe/Berlin")).replace(microsecond=0).isoformat()
    _laeufe(erg, (1, 3, "organisationen", "--seiten 4", jetzt, jetzt, 1, 2, 0, 5, 0, 2, "abbruch (server)", "503"))
    for name, wert in (("ERG", erg), ("SYSTEM", "https://example.invalid/oparl/system"),
                       ("BODY", "https://example.invalid/oparl/bodies/x"), ("_LISTEN", [])):
        monkeypatch.setattr(om, name, wert)
    for name, wert in (("WIEDERHOLUNGEN", 4), ("MAX_DAUER", 0.0), ("ABSTAND", 0.0), ("MAX_ANFRAGEN", 3),
                       ("KONTAKT", "kontakt@example.invalid"), ("PROTOKOLL", tmp_path / "cache" / "abrufe.tsv")):
        monkeypatch.setattr(om.abruf, name, wert)                          # main() setzt sie; danach zurück
                                                                           # (Markerdatei neben dem Protokoll in tmp_path)
    for name in ("RATSATLAS_NACH_ABBRUCH", "RATSATLAS_ABSTAND", "RATSATLAS_WIEDERHOLUNGEN", "RATSATLAS_MAX_DAUER"):
        monkeypatch.delenv(name, raising=False)
    for name, wert in (("RATSATLAS_MESSUNG_FREIGEGEBEN", "ja"), ("RATSATLAS_ZEITFENSTER", ""),
                       ("RATSATLAS_MAX_ANFRAGEN", "3"), ("RATSATLAS_KONTAKT", "kontakt@example.invalid")):
        monkeypatch.setenv(name, wert)
    geholt = []

    def hole(url, endung="", max_bytes=None):
        geholt.append(url)
        raise om.Abbruch("Test: Zeitüberschreitung, mögliche Sperre", "sperre")
    monkeypatch.setattr(om, "hole", hole)
    with pytest.raises(SystemExit) as e:
        om.main(["test"])
    assert "RATSATLAS_NACH_ABBRUCH" in str(e.value.code) and geholt == []
    monkeypatch.setenv("RATSATLAS_NACH_ABBRUCH", "ja")
    assert om.main(["test"]) == 2 and geholt == ["https://example.invalid/oparl/system"]
    assert [z["ergebnis"] for z in tsv(erg / "oparl_laeufe.tsv")] == ["abbruch (server)", "abbruch (sperre)"]


# --- Runde 9 (Köln): Unterbrechung (Strg+C, SIGTERM, SIGHUP), Zertifikatsprüfung (Art `tls`), Antwortform (hier
# Wuppertal laut CLAUDE.md 3.1), Probelauf Stufe 2 ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("sig, rueckgabe", [(None, 130), (signal.SIGINT, 130), (signal.SIGTERM, 143)])
def test_unterbrochener_lauf_wird_vermerkt_und_sperrt_12_stunden(tmp_path, monkeypatch, sig, rueckgabe):
    """Strg+C (KeyboardInterrupt oder SIGINT) und SIGTERM (etwa Zeitlimit des aufrufenden Werkzeugs) enden gleich:
    Vermerk „unterbrochen“ in oparl_laeufe.tsv, danach gilt die 12-Stunden-Regel (SIGHUP als Prozess:
    test_sighup_wie_strg_c_ausser_mit_nohup). Die Signalbehandlung gilt nur während des Laufs (danach wieder die
    vorige). Eine Wache fängt SIGTERM, falls main() es nicht behandelt (sonst endete der Testprozess)."""
    om = importlib.import_module("oparl_messung")

    class Wache(Exception):
        pass

    def wache(nummer, _rahmen):
        raise Wache(nummer)
    alt = {s: signal.signal(s, wache) for s in (signal.SIGTERM, signal.SIGHUP)}
    try:
        def kommando(_a):
            if sig is None:
                raise KeyboardInterrupt
            os.kill(os.getpid(), sig)
            time.sleep(5)
        monkeypatch.setitem(om.KOMMANDOS, "test", kommando)
        for name, wert in (("ERG", tmp_path / "erg"), ("SYSTEM", "http://127.0.0.1:9/oparl/system"),
                           ("BODY", "http://127.0.0.1:9/oparl/bodies/x"), ("_LISTEN", [])):
            monkeypatch.setattr(om, name, wert)
        monkeypatch.setattr(om.abruf, "PROTOKOLL", tmp_path / "abrufe.tsv")
        assert om.main(["test"]) == rueckgabe
        assert all(signal.getsignal(s) is wache for s in alt)          # vorige Behandlung wiederhergestellt
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        for s, behandlung in alt.items():
            signal.signal(s, behandlung)
    datei = tmp_path / "erg" / "oparl_laeufe.tsv"
    zeile = tsv(datei)[-1]
    name = signal.Signals(sig).name if sig else "SIGINT"
    assert (zeile["ergebnis"], zeile["meldung"]) == ("unterbrochen", f"unterbrochen ({name})")
    assert om.letzter_abbruch(datei)["lauf"] == zeile["lauf"]           # Sperrfrist 12 Stunden


def test_sigterm_beendet_den_lauf_mit_vermerk_und_ohne_weitere_anfrage(tmp_path):
    """Als Prozess gegen einen Testserver, der wie die Stadt behandelt wird (127.0.0.2): SIGTERM nach der ersten Antwort
    (während des Abstands von 2 s) → Rückgabewert 143, Vermerk „unterbrochen (SIGTERM)“; ein zweiter Lauf schickt keine
    Anfrage (12-Stunden-Regel)."""
    with testserver.Testserver(host="127.0.0.2") as stadt:
        skript = str(EXPLORE / "oparl_messung.py")
        env = _wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="1", RATSATLAS_MAX_ANFRAGEN="3")
        p = subprocess.Popen([sys.executable, skript, "test"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
        frist, protokoll_datei = time.monotonic() + 30, tmp_path / "cache" / "abrufe.tsv"
        while time.monotonic() < frist and p.poll() is None and not (
                protokoll_datei.exists() and len(protokoll_datei.read_text(encoding="utf-8").splitlines()) >= 2):
            time.sleep(0.02)                                                # erste Antwort gelesen und vermerkt
        p.send_signal(signal.SIGTERM)
        _, fehler = p.communicate(timeout=30)
        n = len(stadt.anfragen)
        assert p.returncode == 143 and "Unterbrochen (SIGTERM)" in fehler, fehler
        zeile = tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]
        assert (zeile["ergebnis"], zeile["meldung"], zeile["netz"]) == ("unterbrochen", "unterbrochen (SIGTERM)", str(n))
        assert 1 <= n < 3
        zweiter = subprocess.run([sys.executable, skript, "test"], env=env, capture_output=True, text=True, timeout=60)
        assert zweiter.returncode == 1 and "RATSATLAS_NACH_ABBRUCH" in zweiter.stderr and "unterbrochen" in zweiter.stderr
        assert len(stadt.anfragen) == n                                   # keine Anfrage des zweiten Laufs


def test_zertifikatsfehler_erkennen():
    abruf = importlib.import_module("abruf")
    from pipeline import abruf as pabruf
    pruefung = ssl.SSLCertVerificationError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                                                "self-signed certificate (_ssl.c:1000)")
    ende = ssl.SSLEOFError(8, "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")
    for modul in (abruf, pabruf):
        assert modul.zertifikatsfehler(pruefung) and modul.zertifikatsfehler(urllib.error.URLError(pruefung))
        assert modul.zertifikatsfehler(urllib.error.URLError(ssl.SSLError(1, "[SSL: CERTIFICATE_VERIFY_FAILED] x")))
        for anderer in (ende, urllib.error.URLError(ende), urllib.error.URLError(ConnectionResetError(104, "reset")),
                        urllib.error.URLError(OSError("Tunnel connection failed: 502 Bad Gateway")), TimeoutError(),
                        urllib.error.HTTPError("https://x/", 403, "CERTIFICATE_VERIFY_FAILED", {}, None)):
            assert not modul.zertifikatsfehler(anderer), anderer


def test_zertifikatsfehler_ist_keine_moegliche_sperre(tmp_path, monkeypatch, tls_server):
    """Lokaler TLS-Server mit selbst signiertem Zertifikat, dem der Client nicht vertraut: Art `tls`, keine HTTP-Anfrage
    beim Server, Status `tls` im Protokoll, nichts im Cache, keine Wiederholung. Gegenversuch: Mit vertrautem
    Zertifikat antwortet derselbe Server."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path)
    url = f"{tls_server.url}/oparl/system"
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(url, ".json")
    assert e.value.art == "tls" and "CERTIFICATE_VERIFY_FAILED" in str(e.value)
    assert "mögliche Sperre" not in str(e.value) and "vermutlich eine Einstellung der Arbeitsumgebung" in str(e.value)
    assert "Sperrseite nicht ausgeschlossen" in str(e.value) and "Berichten, nicht wiederholen" in str(e.value)
    assert tls_server.anfragen == []                                     # keine HTTP-Anfrage gesendet
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert (z["status"], z["quelle"]) == ("tls", "netz") and not abruf._cachepfad(url, ".json").exists()
    kontext = ssl.create_default_context(cafile=str(tls_server.zertifikat))
    oeffner = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=kontext))
    assert oeffner.open(url, timeout=10).read() == b"{}" and tls_server.anfragen == ["/oparl/system"]


@pytest.mark.parametrize("reset", [False, True])
def test_andere_tls_fehler_bleiben_moegliche_sperre(tmp_path, monkeypatch, abbrechender_server, reset):
    server = abbrechender_server(reset)
    abruf = _abruf_im_prozess(monkeypatch, tmp_path)
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(f"{server.url}/oparl/system", ".json")
    assert e.value.art == "sperre" and "mögliche Sperre" in str(e.value)
    assert len(server.verbindungen) == 1                                 # keine Wiederholung trotz WIEDERHOLUNGEN=4


def test_zertifikatsfehler_im_lauf_mit_12_stunden_regel_und_auswertung(tmp_path, tls_server):
    """Als Prozess (Adresse gilt nicht als lokal: strenge Vorgaben, Abstand 2 s): Abbruch der Art `tls`, Hinweis auf die
    Einstellung der Arbeitsumgebung, keine mögliche Sperre; der nächste Lauf schickt keine Anfrage (12-Stunden-Regel).
    Die Auswertung nennt den Status `tls` ohne „mögliche Sperre“ und ohne Antwortzeit."""
    keine = ",".join(x for x in (os.environ.get("NO_PROXY", ""), "127.0.0.1,localhost") if x)
    env = {k: v for k, v in os.environ.items() if not k.startswith("RATSATLAS_")}
    env.update({"RATSATLAS_OPARL_SYSTEM": f"{tls_server.url}/oparl/system",
                "RATSATLAS_OPARL_BODY": f"{tls_server.url}/oparl/bodies/x", "RATSATLAS_MESSUNG_FREIGEGEBEN": "ja",
                "RATSATLAS_ZEITFENSTER": "", "RATSATLAS_KONTAKT": "kontakt@example.invalid",
                "RATSATLAS_MAX_ANFRAGEN": "3", "RATSATLAS_STUFE": "1", "RATSATLAS_SPERRE": str(tmp_path / "sperre"),
                "RATSATLAS_CACHE": str(tmp_path / "cache"), "RATSATLAS_ERGEBNISSE": str(tmp_path / "ergebnisse"),
                "NO_PROXY": keine, "no_proxy": keine})
    skript = str(EXPLORE / "oparl_messung.py")
    r = subprocess.run([sys.executable, skript, "test"], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "Zertifikatsprüfung ist gescheitert" in r.stderr, r.stderr
    assert "Mögliche Sperre" not in r.stderr and tls_server.anfragen == []
    zeile = tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]
    assert (zeile["ergebnis"], zeile["netz"]) == ("abbruch (tls)", "1")
    zweiter = subprocess.run([sys.executable, skript, "test"], env=env, capture_output=True, text=True, timeout=60)
    assert zweiter.returncode == 1 and "RATSATLAS_NACH_ABBRUCH" in zweiter.stderr
    assert len(tsv(tmp_path / "cache" / "abrufe.tsv")) == 1               # keine weitere Anfrage
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert ("Status tls × 1 (Zertifikatsprüfung fehlgeschlagen: vermutlich Einstellung der Arbeitsumgebung (CA des "
            "Proxys); Zertifikat der Gegenseite oder Sperrseite nicht ausgeschlossen – berichten, nicht wiederholen)") in aus
    assert "mögliche Sperre" not in aus and "| 1 | test | 1 | 0 | tls×1 | – | – | 0 | abbruch (tls) |" in aus


def test_wuppertaler_form_wie_claude_md(server):
    """Antwortform des Testservers laut CLAUDE.md 3.1 (Stichprobe vom 09.11.2026), Daten erfunden."""
    seite = json.loads(server.antwort("/oparl/bodies/0001/papers", "")[2])
    assert seite["pagination"] == {"elementsPerPage": 100, "currentPage": 1} and len(seite["data"]) == 100
    assert sorted(seite["links"]) == ["first", "next", "self"] and seite["links"]["next"].endswith("/papers?page=2")
    vorlagen = seite["data"]
    assert all(p["id"].startswith("http://") and re.fullmatch(r"VO/\d{4}/\d{2}", p["reference"]) for p in vorlagen)
    assert not any("mainFile" in p or "location" in p for p in vorlagen)
    # wie in Wuppertal (Stufe 1, 10.11.2026): absteigend nach created, nicht nach date; date einige Tage nach created
    erstellt = [dt.datetime.fromisoformat(p["created"]) for p in vorlagen]
    assert erstellt == sorted(erstellt, reverse=True)
    daten = [p["date"] for p in vorlagen]
    assert daten != sorted(daten, reverse=True)
    abstand = {k: (dt.date.fromisoformat(p["date"]) - erstellt[k].date()).days for k, p in enumerate(vorlagen)}
    assert {k for k, x in abstand.items() if x < 0} == {k for k in range(100) if k % 97 == 0} == {0, 97}
    assert all(0 <= x <= 30 for k, x in abstand.items() if k % 97) and abstand[7] == abstand[57] == 30
    # einige Vorlagen mit created vor 2020 und date ab 2020 (an der Grenze, Seiten 71 und 72)
    d = server.daten
    ueber = [k for k in range(d.anzahl) if d.erstellt_tag(k) < dt.date(2020, 1, 1) <= d.datum(k)]
    assert ueber and {k // 100 + 1 for k in ueber} == {71, 72}
    # created um 10 Uhr Ortszeit: Offset +01:00 im Winter, +02:00 im Sommer; als Zeitpunkt absteigend über die Liste
    zeiten = [dt.datetime.fromisoformat(d.vorlage(k)["created"]) for k in range(0, d.anzahl, 50)]
    assert {t.strftime("%z") for t in zeiten} == {"+0100", "+0200"} and zeiten == sorted(zeiten, reverse=True)
    assert all(t.hour == 10 for t in zeiten)
    dateien = [f for p in vorlagen for f in p["auxiliaryFile"]]
    assert dateien and all(re.search(r"/downloadfiles/a/\d+\.pdf$", f["accessUrl"])
                           and re.search(r"/downloadfiles/\d+\.pdf$", f["downloadUrl"]) for f in dateien)
    assert all("/organizations/at/" in u for p in vorlagen for u in p.get("underDirectionOf", []))
    assert all({"meeting", "agendaItem", "role"} <= set(c) for p in vorlagen for c in p.get("consultation", []))
    assert {"Antrag CDU", "Antrag FDP / WfW Rat AU", "Gemeinsamer Antrag BV", "Beschlussvorlage"} <= {
        p["paperType"] for p in vorlagen}
    assert 0 < sum(1 for p in vorlagen if p.get("keyword")) < 100
    assert json.loads(server.antwort("/oparl/bodies/0001/papers", "page=246")[2])["data"]
    leer = json.loads(server.antwort("/oparl/bodies/0001/papers", "page=247")[2])
    assert leer["data"] == [] and "next" not in leer["links"]
    body = server.daten.body()
    assert body["license"] == "" and "legislativeTerm" not in body and "location" not in body
    assert body["person"].endswith("/people") and body["name"] == "[Testdaten] Instance 0001"
    assert server.antwort("/oparl/bodies/0001/papers", "modified_since=2026-01-01T00%3A00%3A00%2B00%3A00")[0] == 404
    orgs = {o["id"].rsplit("/", 2)[1] for o in server.daten.organisationen}
    assert orgs == {"gr", "at", "zz"}


def test_kennzahlen_und_auswertung_ohne_gesamtzahlen(server, tmp_path):
    """kennzahlen ohne Gesamtzahlen: „fehlt“ statt None, keine Ausnahme; auswertung.py --stufe 2; mit Gesamtzahlen
    (Testserver `gesamtzahlen`) stehen sie in der Tabelle."""
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8, stufe="2")
    assert m["rc"] == 0 and m["server"] == 8, m["stderr"]
    werte = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv")}
    for liste in ("paper", "meeting", "organization", "person"):
        assert werte[(liste, "pagination.totalElements")] == werte[(liste, "pagination.totalPages")] == "fehlt"
        assert werte[(liste, "links.schluessel")] == "first,next,self"
    assert werte[("person", "url")].endswith("/people") and werte[("body", "license")] == ""
    assert werte[("body", "legislativeTerm")] == werte[("body", "location")] == "null"
    assert not any("None" in w for w in werte.values())
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse", "2")
    assert "| 2 | kennzahlen | 8 | 0 | 200×7, 404×1 |" in aus
    assert "| paper | fehlt | 100 | fehlt | 100 | first,next,self | gleicher Pfad; Parameter page; URL-kodiert nein |" in aus
    assert "| modified_since URL-kodiert | Parameter abgelehnt (HTTP 404) |" in aus and "None" not in aus
    with testserver.Testserver(gesamtzahlen=True) as gesamt:
        assert lauf(gesamt, tmp_path, "kennzahlen", obergrenze=8, cache="cache2")["rc"] == 0
    werte = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv")}
    assert (werte[("paper", "pagination.totalElements")], werte[("paper", "pagination.totalPages")]) == ("24550", "246")


@pytest.mark.parametrize("code, ergebnis, anfragen", [
    (400, "ok", 8), (401, "ok", 8), (404, "ok", 8),
    (403, "abbruch (http)", 8), (429, "abbruch (server)", 8), (500, "abbruch (server)", 8),
    (502, "abbruch (sperre)", 8)])
def test_parametertests_abgelehnt_oder_abbruch(server, tmp_path, code, ergebnis, anfragen):
    """Parametertest `modified_since` URL-kodiert (8., letzte Anfrage) mit Fehlantwort: 400, 401 und 404 gelten als
    „Parameter abgelehnt“, die Messung endet regulär; jede andere Fehlantwort bricht nach dieser Anfrage ab (keine
    Wiederholung)."""
    server.stoerung = lambda pfad, abfrage: code if "%" in abfrage else None
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8)
    assert m["lauf"]["ergebnis"] == ergebnis and m["server"] == anfragen == int(m["lauf"]["netz"]), m["stderr"]
    assert [s for _, q, _, s in server.anfragen if "%" in q] == [code]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv") if z["objekt"] == "paper"}
    if ergebnis == "ok":
        assert m["rc"] == 0 and werte["test modified_since URL-kodiert"] == f"Parameter abgelehnt (HTTP {code})"
    else:
        assert m["rc"] == 2 and "%" in server.anfragen[-1][1]


def _stufe_2_befehl():
    """Umgebung und Argumente des Befehls aus STUFEN.md, Stufe 2."""
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    zeile = next(z for z in text.splitlines() if z.startswith("RATSATLAS_") and "RATSATLAS_STUFE=2 " in z)
    werte = {k: v.strip('"') for k, v in re.findall(r'(RATSATLAS_[A-Z_]+)=("[^"]*"|\S+)', zeile)}
    return werte, zeile.split("explore/oparl_messung.py", 1)[1].split()


def _scheinzeit(ordner, uhrzeit):
    """PYTHONTZPATH für Teilprozesse: eine per zic erzeugte Zone Europe/Berlin mit festem Abstand zu UTC, so dass es
    jetzt `uhrzeit` (hh:mm:00) Ortszeit ist (keine Änderung der Systemzeit). Ohne zic: Test übersprungen."""
    zic = shutil.which("zic")
    if not zic:
        pytest.skip("zic fehlt")
    jetzt = dt.datetime.now(dt.timezone.utc)
    h, m = (int(x) for x in uhrzeit.split(":"))
    ab = (h * 3600 + m * 60 - (jetzt.hour * 3600 + jetzt.minute * 60 + jetzt.second)) % 86400
    ab = ab - 86400 if ab > 43200 else ab
    zeichen, ab = ("-", -ab) if ab < 0 else ("", ab)
    ordner.mkdir(parents=True)
    (ordner / "quelle").write_text(f"Zone\tEurope/Berlin\t{zeichen}{ab // 3600}:{ab % 3600 // 60:02d}:{ab % 60:02d}"
                                   "\t-\tSCHEIN\n", encoding="utf-8")
    subprocess.run([zic, "-d", str(ordner / "tz"), str(ordner / "quelle")], check=True, capture_output=True, timeout=60)
    return str(ordner / "tz")


def _stufe_2_wie_im_plan(stadt, ordner, uhrzeit):
    """Startet die Zeile aus STUFEN.md, Stufe 2, unverändert in bash im Wurzelverzeichnis des Repositorys; von außen
    gesetzt sind nur die Adressen des Testservers (wie die Stadt behandelt), Cache, Ergebnisse, Sperre und HOME in
    `ordner` sowie die Scheinzeit (PYTHONTZPATH). `python3` ist der Interpreter der Tests."""
    zeile = next(z for z in (EXPLORE / "STUFEN.md").read_text(encoding="utf-8").splitlines()
                 if z.startswith("RATSATLAS_") and "RATSATLAS_STUFE=2 " in z)
    (ordner / "bin").mkdir(parents=True, exist_ok=True)
    if not (ordner / "bin" / "python3").exists():
        (ordner / "bin" / "python3").symlink_to(sys.executable)
    keine = ",".join(x for x in (os.environ.get("NO_PROXY", ""), "127.0.0.1,127.0.0.2,localhost") if x)
    env = {k: v for k, v in os.environ.items() if not k.startswith("RATSATLAS_")}
    env.update({"RATSATLAS_OPARL_SYSTEM": stadt.system_url, "RATSATLAS_OPARL_BODY": stadt.body_url,
                "RATSATLAS_CACHE": str(ordner / "cache"), "RATSATLAS_ERGEBNISSE": str(ordner / "ergebnisse"),
                "RATSATLAS_SPERRE": str(ordner / "sperre"), "HOME": str(ordner / "home"),
                "PYTHONTZPATH": _scheinzeit(ordner / "zone", uhrzeit),
                "PATH": f"{ordner / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}", "NO_PROXY": keine, "no_proxy": keine})
    return subprocess.Popen(["bash", "-c", zeile], cwd=str(EXPLORE.parent), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)


def test_probelauf_stufe_2_wie_die_stadt_mit_scheinzeit(tmp_path, monkeypatch):
    """Genau die Zeile aus STUFEN.md, Stufe 2, gegen Testserver auf 127.0.0.2 (gilt nicht als lokal: Freigabe, strenge
    Vorgaben, Abstand 2 s, Zeitfenster 23–1 Uhr ohne RATSATLAS_ZEITFENSTER) mit Scheinzeit 23:05 Uhr: (i) mit einem
    Cache wie nach Stufe 1 (System, Body, erste Vorlagenseite) 5 Anfragen ans Netz, (ii) ohne Cache 8, in der Reihenfolge
    des Plans; Abstände mindestens 2 s, keine Wiederholung. Filterurteil modified_since: Server wendet an → „ja“ (mit und
    ohne Cache), übergeht → „nein (…; frühestes modified … vor der Grenze)“, übergeht, nachdem alle Vorlagen seit dem
    Cache geändert wurden → „nicht unterscheidbar (gleiche Kennungen wie ohne Filter)“. Um 22:59 und 01:00 Uhr keine
    Anfrage."""
    werte, argumente = _stufe_2_befehl()
    assert argumente == ["kennzahlen"] and werte["RATSATLAS_MAX_ANFRAGEN"] == "8"
    assert "RATSATLAS_ABSTAND" not in werte and "RATSATLAS_ZEITFENSTER" not in werte
    laeufe = {}
    # Name → (Cache wie nach Stufe 1, modified_since übergangen, alle Vorlagen nach dem Cache geändert, Urteil)
    faelle = {"mit": (True, False, False, "ja"), "ohne": (False, False, False, "ja"),
              "uebergeht": (True, True, False, "nein ("),
              "geaendert": (True, True, True, "nicht unterscheidbar (gleiche Kennungen wie ohne Filter)")}
    with contextlib.ExitStack() as stapel:
        for name, (mit_cache, uebergeht, aendern, _) in faelle.items():
            server = stapel.enter_context(testserver.Testserver(host="127.0.0.2"))
            if mit_cache:   # Cache wie nach Stufe 1: System, Body, erste Seite der Vorlagen
                _cache_wie_nach_stufe_1(monkeypatch, server, tmp_path / name / "cache")
            if aendern:
                _alle_vorlagen_aendern(server)
            server.ohne_modified_filter = uebergeht
            laeufe[name] = (server, time.monotonic(), _stufe_2_wie_im_plan(server, tmp_path / name, "23:05"))
        for name, (server, start, p) in laeufe.items():
            _, fehler = p.communicate(timeout=120)
            assert p.returncode == 0, fehler
            zeile = tsv(tmp_path / name / "ergebnisse" / "oparl_laeufe.tsv")[-1]
            netz, cache = (5, 3) if faelle[name][0] else (8, 0)
            assert (len(server.anfragen), zeile["netz"], zeile["cache"], zeile["stufe"]) == (netz, str(netz), str(cache),
                                                                                         "2"), name
            assert "T23:0" in zeile["start"] and zeile["ergebnis"] == "ok"                  # Scheinzeit
            reihenfolge = [pf.rsplit("/", 1)[1] + (f"?{q.split('=')[0]}" if q else "") for pf, q, *_ in server.anfragen]
            erwartet = ["meetings", "organizations", "people", "papers?modified_since", "papers?modified_since"]
            assert reihenfolge == (erwartet if faelle[name][0] else ["system", "0001", "papers"] + erwartet)
            kodiert = [q for pf, q, *_ in server.anfragen if "%" in q]
            assert len(kodiert) == 1 and [s for pf, q, _, s in server.anfragen if q == kodiert[0]] == [404]
            assert sorted(s for *_, s in server.anfragen) == [200] * (netz - 1) + [404]
            assert len({(pf, q) for pf, q, *_ in server.anfragen}) == netz    # keine Wiederholung
            assert server.eingang[0] - start >= 2.0
            # `ausgang` vermerkt der Server unmittelbar vor dem letzten Byte, also nie nach dem Ende der Antwort im
            # Client (abruf._letzte); daher ohne Spielraum wie in Köln
            assert min(b - a for a, b in zip(server.ausgang, server.eingang[1:])) >= 2.0, name
            werte_tsv = {(z["objekt"], z["feld"]): z["wert"]
                         for z in tsv(tmp_path / name / "ergebnisse" / "oparl_kennzahlen.tsv")}
            assert werte_tsv[("paper", "test modified_since URL-kodiert")] == "Parameter abgelehnt (HTTP 404)"
            assert werte_tsv[("paper", "pagination.totalElements")] == "fehlt"
            grenze = werte_tsv[("paper", "grenze modified_since")].split(" ")[0]
            assert urllib.parse.unquote(kodiert[0]) == f"modified_since={grenze}"     # dieselbe Grenze
            urteil = werte_tsv[("paper", f"test modified_since={grenze}")].split("filter_wirksam=", 1)[1]
            assert urteil.startswith(faelle[name][3]) and ("frühestes modified" in urteil) == (name == "uebergeht"), (
                name, urteil)
    # außerhalb des Zeitfensters: keine Anfrage, kein Protokoll
    with testserver.Testserver(host="127.0.0.2") as stadt:
        for uhrzeit in ("22:59", "01:00"):
            ordner = tmp_path / f"um_{uhrzeit.replace(':', '')}"
            _, fehler = (p := _stufe_2_wie_im_plan(stadt, ordner, uhrzeit)).communicate(timeout=60)
            assert p.returncode == 1 and "außerhalb des Zeitfensters 23-1 Uhr" in fehler, (uhrzeit, fehler)
            assert stadt.anfragen == [] and not (ordner / "cache" / "abrufe.tsv").exists()


# --- Runde 10 (Köln): Zeitfilter ohne weitere Anfrage beurteilt, Reihenfolge (kodierter Test zuletzt), zwei 401, Antworten ohne JSON,
# Tropf-Antwort und Unterbrechung während einer Anfrage, Signale ----------------------------------------------------------

@pytest.mark.parametrize("uebergeht, urteil", [(False, "ja"), (True, "nein")])
def test_zeitfilter_angewandt_oder_uebergangen(server, tmp_path, uebergeht, urteil):
    """Neueste zuerst, jüngste Vorlagen kürzlich geändert: Ein Server, der modified_since anwendet, ergibt „ja“, einer,
    der ihn übergeht, „nein“ (mit fester Grenze vor 7 Tagen hieße es fälschlich „ja“). Die Grenze kommt aus der
    ungefilterten ersten Seite (100 Vorlagen, Median der ersten 50)."""
    server.ohne_modified_filter = uebergeht
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8)
    assert m["rc"] == 0 and m["server"] == 8, m["stderr"]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv") if z["objekt"] == "paper"}
    grenze, herkunft = werte["grenze modified_since"].split(" ", 1)
    assert grenze.endswith("+00:00") and "Median von modified der ersten 50 Vorlagen" in herkunft
    assert f"filter_wirksam={urteil}" in werte[f"test modified_since={grenze}"]
    abfragen = [q for pf, q, *_ in server.anfragen if pf.endswith("/papers") and q]
    assert [q.split("=")[0] for q in abfragen] == ["modified_since", "modified_since"] and "%" in abfragen[1]
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert f"filter_wirksam={urteil}" in aus and f"Grenze modified_since: {grenze}" in aus


def test_filter_urteil_ohne_weitere_anfrage():
    om = importlib.import_module("oparl_messung")
    t0 = dt.datetime(2026, 11, 6, 12, tzinfo=dt.timezone.utc)

    def vorlage(kennung, erstellt, geaendert):
        return {"id": kennung, "created": erstellt.isoformat(), "modified": geaendert.isoformat()}
    basis = [vorlage(f"p{n}", t0 - dt.timedelta(days=n), t0 - dt.timedelta(hours=n)) for n in range(10)]
    seit, _ = om._grenze_modified(basis)                                 # Median der ersten fünf: p2
    grenze = om._zeitpunkt(seit)
    assert seit == "2026-11-06T10:00:00+00:00"
    urteil = lambda antwort: om._filter_urteil(basis, antwort, "modified", von=grenze)["von"]   # noqa: E731
    assert urteil(basis).startswith("nein (7 von 10 vor der Grenze")    # alle Änderungen jünger als 7 Tage
    assert urteil(basis[:3]) == "ja"
    # acht neue Vorlagen seit der ungefilterten Seite: Ein Server ohne Filter zeigte sie und p0, p1 → nicht unterscheidbar
    neue = [vorlage(f"n{n}", t0 + dt.timedelta(hours=n + 1), t0 + dt.timedelta(hours=n + 1)) for n in range(8)]
    assert urteil(neue + basis[:2]).startswith("nicht unterscheidbar (8 Kennungen nicht auf der ungefilterten Seite")
    # ältere, kürzlich geänderte Vorlagen verdrängen nichts von der ersten Seite → ja
    alt = [vorlage(f"a{n}", t0 - dt.timedelta(days=100 + n), t0) for n in range(8)]
    assert urteil(basis[:3] + alt) == "ja"
    assert urteil([]) == "keine Objekte"
    # alle modified gleich: nicht unterscheidbar, mit Vergleich der Kennungen
    gleich = [dict(o, modified=t0.isoformat()) for o in basis]
    seit, _ = om._grenze_modified(gleich)
    assert om._filter_urteil(gleich, gleich, "modified", von=om._zeitpunkt(seit))["von"] == (
        "nicht unterscheidbar (gleiche Kennungen wie ohne Filter)")
    # created_since/created_until bei neueste zuerst
    jahr = {"von": om._zeitpunkt("2025-01-01T00:00:00+01:00"), "bis": om._zeitpunkt("2025-12-31T23:59:59+01:00")}
    j2025 = [vorlage(f"j{n}", dt.datetime(2025, 12, 20 - n, tzinfo=dt.timezone.utc), t0) for n in range(5)]
    u = om._filter_urteil(basis, j2025, "created", **jahr)
    assert u["bis"] == "ja" and u["von"].startswith("nicht unterscheidbar (5 Kennungen")
    assert "neueste zuerst: die erste Seite zeigt nur die jüngsten Vorlagen" in u["von"]
    u = om._filter_urteil(basis, basis, "created", **jahr)              # Filter übergangen
    assert u["bis"].startswith("nein (10 von 10 nach der Grenze") and u["von"].startswith("nicht unterscheidbar")
    j2024 = [vorlage("x", dt.datetime(2024, 5, 1, tzinfo=dt.timezone.utc), t0)]
    assert om._filter_urteil(basis, j2025 + j2024, "created", **jahr)["von"].startswith("nein (1 von 6 vor der Grenze")


@pytest.mark.parametrize("stoerung, ergebnis, n401", [
    (lambda q: q.startswith("modified_since"), "abbruch (http)", 2),                 # 7. und 8. Anfrage: zwei in Folge
    (lambda q: q.startswith("modified_since") and "%" not in q, "ok", 1)])           # nur die 7.; die 8. ergibt 404
def test_zwei_401_in_folge_brechen_ab(server, tmp_path, stoerung, ergebnis, n401):
    server.stoerung = lambda pfad, abfrage: 401 if stoerung(abfrage) else None
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8)
    assert (m["lauf"]["ergebnis"], m["server"]) == (ergebnis, 8), m["stderr"]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv") if z["objekt"] == "paper"}
    assert sum(w == "Parameter abgelehnt (HTTP 401)" for w in werte.values()) == 1
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert f"Status 401 × {n401} (abgelehnt oder Sperre?)" in aus
    assert "Parameter abgelehnt (HTTP 401) – abgelehnt oder Sperre?" in aus
    if ergebnis != "ok":
        assert m["rc"] == 2 and "zweimal HTTP 401 in Folge (abgelehnt oder Sperre?)" in m["lauf"]["meldung"]


def test_antwort_ohne_json_bleibt_nicht_im_cache(server, tmp_path, monkeypatch):
    """Parametertest und Folgeseite einer Liste mit HTML statt JSON (Status 200): Fehler, die Antwort wird aus dem Cache
    entfernt (ein späterer Lauf fragt erneut), gültige Antworten bleiben."""
    server.stoerung = lambda pfad, abfrage: 200 if "%" in abfrage else None
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8)
    assert m["rc"] == 1 and m["lauf"]["ergebnis"].startswith("fehler (JSONDecodeError"), m["stderr"]
    abruf = importlib.import_module("abruf")
    monkeypatch.setattr(abruf, "CACHE", tmp_path / "cache")
    kodiert = next(q for _, q, *_ in server.anfragen if "%" in q)
    assert not abruf._cachepfad(f"{server.body_url}/papers?{kodiert}", ".json").exists()
    assert abruf._cachepfad(f"{server.body_url}/papers", ".json").exists()
    om = importlib.import_module("oparl_messung")
    abruf = _abruf_im_prozess(monkeypatch, tmp_path / "liste")
    monkeypatch.setattr(om, "_LISTEN", [])
    monkeypatch.setattr(om, "SYSTEM", server.system_url)           # lokaler Probelauf: nur lokale Adressen erlaubt
    monkeypatch.setattr(om, "BODY", server.body_url)
    server.stoerung = lambda pfad, abfrage: 200 if abfrage == "page=2" else None
    url = f"{server.body_url}/organizations"
    with pytest.raises(ValueError):
        list(om._seiten(url, 3, name="organization"))
    assert abruf._cachepfad(url, ".json").exists() and not abruf._cachepfad(f"{url}?page=2", ".json").exists()


def test_letzter_parametertest_langsam_nach_allen_messungen(server, tmp_path):
    """Der URL-kodierte Test ist die letzte Anfrage: Wirkt er (Server dekodiert wie Köln) und ist die Antwort zu
    langsam, bricht der Lauf ab („langsam“), wenn alle übrigen Messungen vorliegen; die Zahl der Objekte steht aus dem
    Inhalt am Abbruch im Ergebnis (abruf.py speichert die langsame Antwort nicht)."""
    server.kodierte_parameter = "dekodieren"
    server.verzoegerung = lambda pfad, abfrage: 0.6 if "%" in abfrage else 0
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8, RATSATLAS_MAX_DAUER="0.4")
    assert (m["rc"], m["lauf"]["ergebnis"], m["server"]) == (2, "abbruch (langsam)", 8), m["stderr"]
    assert "%" in server.anfragen[-1][1]
    werte = {(z["objekt"], z["feld"]): z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv")}
    wert = werte[("paper", "test modified_since URL-kodiert")]
    assert re.match(r"objekte=\d+; ", wert) and "Antwortzeit" in wert and not wert.startswith("objekte=100;")
    # die langsame Antwort (URL-kodierter Test) liegt nicht im Cache
    assert not any("%" in json.loads(k.read_text(encoding="utf-8"))["url"]
                   for k in (tmp_path / "cache" / "roh").glob("*.kopf"))
    assert ("person", "links.next") in werte and any(f.startswith("test modified_since=") for _, f in werte)


@pytest.fixture
def tropf_server():
    """Fabrik für lokale HTTP-Server auf 127.0.0.1: Kopf mit Content-Length, dann der Inhalt in `teile` mit `pause`
    Sekunden vor jedem Teil (verzögerte oder tropfende Antwort)."""
    gestartet = []

    def starten(teile, pause):
        inhalt = b"".join(teile)

        class H(socketserver.BaseRequestHandler):
            def handle(self):
                daten = b""
                while b"\r\n\r\n" not in daten:
                    teil = self.request.recv(4096)
                    if not teil:
                        return
                    daten += teil
                self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n"
                                     b"Connection: close\r\n\r\n" % len(inhalt))
                for teil in teile:
                    time.sleep(pause)
                    try:
                        self.request.sendall(teil)
                    except OSError:
                        return

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        server.daemon_threads, server.url = True, f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        gestartet.append(server)
        return server

    yield starten
    for server in gestartet:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("teile, art, status", [(3, "langsam", "200"), (12, "sperre", "Gesamtfrist")])
def test_verzoegerte_und_tropfende_antwort(tmp_path, monkeypatch, tropf_server, teile, art, status):
    """Inhalt in Blöcken gelesen: vollständig, aber über RATSATLAS_MAX_DAUER → „langsam“ (nicht im Cache, Inhalt nur am
    Abbruch); länger als die Gesamtfrist (hier 1 s statt 60 s) → Art `sperre`, Status `Gesamtfrist`, nichts im Cache,
    Abbruch ohne das Ende abzuwarten."""
    server = tropf_server([b'{"a": 1'] + [b" "] * (teile - 2) + [b"}"], 0.2)
    abruf = _abruf_im_prozess(monkeypatch, tmp_path, GESAMTFRIST=1.0, MAX_DAUER=0.3)
    url = f"{server.url}/oparl/system"
    start = time.monotonic()
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(url, ".json")
    assert e.value.art == art and ("Tropf-Antwort" in str(e.value)) == (art == "sperre")
    assert time.monotonic() - start < 2.0                                # nicht bis zum Ende der Tropf-Antwort
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert (z["status"], z["quelle"]) == (status, "netz")
    assert not abruf._cachepfad(url, ".json").exists() and not list(tmp_path.glob("roh/*"))
    assert e.value.daten == (b'{"a": 1' + b" " * (teile - 2) + b"}" if art == "langsam" else None)


def test_sigterm_waehrend_einer_anfrage_ist_moegliche_sperre(tmp_path):
    """SIGTERM, während die Antwort aussteht (etwa Zeitlimit des aufrufenden Werkzeugs bei hängender Anfrage): Die
    Anfrage steht mit Status `unterbrochen` im Protokoll (Auswertung: Netz 1, mögliche Sperre), der Lauf mit
    „unterbrochen während einer Anfrage“."""
    with testserver.Testserver(host="127.0.0.2") as stadt:
        stadt.verzoegerung = 3.0
        env = _wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="1", RATSATLAS_MAX_ANFRAGEN="3")
        p = subprocess.Popen([sys.executable, str(EXPLORE / "oparl_messung.py"), "test"], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        frist = time.monotonic() + 30
        while not stadt.eingang and time.monotonic() < frist and p.poll() is None:
            time.sleep(0.02)
        time.sleep(0.3)                                                    # die Antwort steht noch aus
        p.send_signal(signal.SIGTERM)
        _, fehler = p.communicate(timeout=30)
    assert p.returncode == 143 and "Unterbrochen (SIGTERM) während einer Anfrage: mögliche Sperre" in fehler, fehler
    zeile = tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]
    assert (zeile["ergebnis"], zeile["netz"]) == ("unterbrochen", "1")
    assert zeile["meldung"].startswith("unterbrochen während einer Anfrage (SIGTERM): mögliche Sperre, stoppen")
    z = protokoll(tmp_path)[-1]
    assert (z["status"], z["quelle"]) == ("unterbrochen", "netz") and z["url"] == stadt.system_url
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "| 1 | test | 1 | 0 | unterbrochen×1 |" in aus
    assert "Status unterbrochen × 1 (Lauf während dieser Anfrage unterbrochen" in aus and "mögliche Sperre" in aus


SIGHUP_SKRIPT = """
import os, signal, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
signal.signal(signal.SIGHUP, signal.SIG_IGN if sys.argv[3] == "ignoriert" else signal.SIG_DFL)
import oparl_messung as om
om.ERG, om.SYSTEM, om.BODY = Path(sys.argv[2]), "http://127.0.0.1:9/oparl/system", "http://127.0.0.1:9/oparl/bodies/x"
def kommando(_a):
    os.kill(os.getpid(), signal.SIGHUP)
    time.sleep(2)
om.KOMMANDOS["test"] = kommando
sys.exit(om.main(["test"]))
"""


@pytest.mark.parametrize("vorher, rueckgabe, ergebnis", [("vorgabe", 129, "unterbrochen"), ("ignoriert", 0, "ok")])
def test_sighup_wie_strg_c_ausser_mit_nohup(tmp_path, vorher, rueckgabe, ergebnis):
    """SIGHUP endet wie Strg+C (Vermerk, 12-Stunden-Regel), außer es ist ignoriert wie mit nohup: dann bleibt es
    ignoriert und der Lauf geht weiter (als eigener Prozess, damit ein nicht behandeltes SIGHUP nicht die Tests
    beendet)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("RATSATLAS_")}
    env.update({"RATSATLAS_CACHE": str(tmp_path / "cache"), "RATSATLAS_SPERRE": str(tmp_path / "sperre")})
    r = subprocess.run([sys.executable, "-c", SIGHUP_SKRIPT, str(EXPLORE), str(tmp_path / "erg"), vorher], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == rueckgabe, r.stderr
    zeile = tsv(tmp_path / "erg" / "oparl_laeufe.tsv")[-1]
    assert zeile["ergebnis"] == ergebnis and (zeile["meldung"] == "unterbrochen (SIGHUP)") == (ergebnis != "ok")


def _main_mit_wache(om, monkeypatch, tmp_path, kommando):
    """om.main(["test"]) mit Ersatzkommando und einer Wache für SIGTERM (falls main() es nicht behandelt); ein Signal
    oder KeyboardInterrupt, das main() verlässt, lässt den Test scheitern (statt die Testsitzung zu beenden)."""
    class Wache(Exception):
        pass

    def wache(nummer, _rahmen):
        raise Wache(nummer)
    if signal.getsignal(signal.SIGINT) is not signal.default_int_handler:
        pytest.skip("SIGINT ist in dieser Testumgebung nicht die Vorgabe von Python")
    alt = signal.signal(signal.SIGTERM, wache)
    try:
        monkeypatch.setitem(om.KOMMANDOS, "test", kommando)
        for name, wert in (("ERG", tmp_path / "erg"), ("SYSTEM", "http://127.0.0.1:9/oparl/system"),
                           ("BODY", "http://127.0.0.1:9/oparl/bodies/x"), ("_LISTEN", [])):
            monkeypatch.setattr(om, name, wert)
        monkeypatch.setattr(om.abruf, "PROTOKOLL", tmp_path / "abrufe.tsv")
        try:
            return om.main(["test"])
        except (KeyboardInterrupt, Wache) as e:
            pytest.fail(f"Signal hat main() verlassen: {e!r}")
    finally:
        signal.signal(signal.SIGTERM, alt)
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def test_zwei_signale_kurz_nacheinander(tmp_path, monkeypatch):
    """Zwei Signale gleichzeitig ausstehend (SIGINT und SIGTERM): Das erste beendet den Lauf wie Strg+C, das zweite wird
    ignoriert und unterbricht den Vermerk nicht."""
    om = importlib.import_module("oparl_messung")
    # Die Signale gehen gezielt an den Hauptthread (pthread_kill), nicht an den Prozess (os.kill): Ein an den Prozess
    # gerichtetes Signal stellt der Kernel einem anderen laufenden Thread zu, wenn der Hauptthread es blockiert; Python
    # behandelt es dann schon vor dem zweiten Signal (in CI so aufgetreten, Rückgabewert 143). Der rechnende Nebenthread
    # stellt genau diese Lage her; an den Hauptthread gerichtete Signale bleiben dort ausstehend und werden nach der
    # Freigabe in aufsteigender Nummer behandelt (SIGINT vor SIGTERM).
    halt = threading.Event()

    def rechnen():
        while not halt.is_set():
            sum(range(1000))
    neben = threading.Thread(target=rechnen, daemon=True)
    neben.start()

    def kommando(_a):
        beide = {signal.SIGINT, signal.SIGTERM}
        haupt = threading.get_ident()
        signal.pthread_sigmask(signal.SIG_BLOCK, beide)
        signal.pthread_kill(haupt, signal.SIGTERM)
        signal.pthread_kill(haupt, signal.SIGINT)
        signal.pthread_sigmask(signal.SIG_UNBLOCK, beide)                 # beide zugleich zugestellt
        time.sleep(5)
    try:
        assert _main_mit_wache(om, monkeypatch, tmp_path, kommando) == 130
    finally:
        halt.set()
        neben.join(5)
    zeilen = tsv(tmp_path / "erg" / "oparl_laeufe.tsv")
    assert len(zeilen) == 1 and (zeilen[0]["ergebnis"], zeilen[0]["meldung"]) == ("unterbrochen", "unterbrochen (SIGINT)")


def test_signal_waehrend_des_vermerks_wird_ignoriert(tmp_path, monkeypatch):
    """Ein Signal, während main() den Vermerk schreibt (finally), wird ignoriert: Der Vermerk steht vollständig."""
    om = importlib.import_module("oparl_messung")
    echt = om._anhaengen

    def anhaengen(*a, **k):
        os.kill(os.getpid(), signal.SIGTERM)
        return echt(*a, **k)
    monkeypatch.setattr(om, "_anhaengen", anhaengen)
    assert _main_mit_wache(om, monkeypatch, tmp_path, lambda _a: None) == 0
    assert tsv(tmp_path / "erg" / "oparl_laeufe.tsv")[-1]["ergebnis"] == "ok"


def test_lauf_ohne_regulaeres_ende_gilt_als_unterbrochen(tmp_path, monkeypatch):
    """Schlechter Fall zuerst: Endet ein Lauf durch eine Ausnahme, die main() nicht behandelt (hier SystemExit im
    Kommando), steht „unterbrochen“ im Vermerk (12-Stunden-Regel), nicht „ok“."""
    om = importlib.import_module("oparl_messung")
    with pytest.raises(SystemExit):
        _main_mit_wache(om, monkeypatch, tmp_path, lambda _a: sys.exit("Test"))
    datei = tmp_path / "erg" / "oparl_laeufe.tsv"
    assert (tsv(datei)[-1]["ergebnis"], tsv(datei)[-1]["meldung"]) == ("unterbrochen", "nicht regulär beendet")
    assert om.letzter_abbruch(datei) is not None


# --- Runde 11: „ja“ nur, wenn eine Vorlage unter der Grenze fehlt; Abstand bei „nein“; Gesamtfrist nach dem Lesen und
# Wächter; Markerdatei gegen harte Beendigung -----------------------------------------------------------------------------

def test_filter_urteil_nach_aenderung_aller_vorlagen_und_abstand_bei_nein():
    """modified kann sich seit der ungefilterten Seite geändert haben: Sind alle Vorlagen seither geändert, liefert ein
    Server, der modified_since übergeht, dieselben Kennungen mit jüngerem modified → „nicht unterscheidbar“ (vorher
    fälschlich „ja“); ebenso ein Server, der ihn anwendet. „ja“ nur, wenn eine Vorlage fehlt, die laut ungefilterter Seite
    unter der Grenze lag. Bei „nein“ steht, wie weit die äußerste Vorlage jenseits der Grenze liegt."""
    om = importlib.import_module("oparl_messung")
    t0 = dt.datetime(2026, 11, 6, 12, tzinfo=dt.timezone.utc)

    def vorlage(kennung, erstellt, geaendert):
        return {"id": kennung, "created": erstellt.isoformat(), "modified": geaendert.isoformat()}
    basis = [vorlage(f"p{n}", t0 - dt.timedelta(days=n), t0 - dt.timedelta(hours=n)) for n in range(10)]
    grenze = om._zeitpunkt(om._grenze_modified(basis)[0])                  # t0 − 2 h
    urteil = lambda antwort: om._filter_urteil(basis, antwort, "modified", von=grenze)["von"]   # noqa: E731
    geaendert = [dict(o, modified=(t0 + dt.timedelta(hours=1)).isoformat()) for o in basis]
    assert urteil(geaendert) == "nicht unterscheidbar (gleiche Kennungen wie ohne Filter)"   # übergangen
    assert urteil(geaendert[:3] + geaendert[5:]) == "ja"                   # p3, p4 lagen unter der Grenze und fehlen
    assert urteil(basis[:3]) == "ja"                                       # angewandt, nichts geändert
    # übergangen: frühestes modified 7 h vor der Grenze; Versatz von 1 h (etwa „+“ als Leerzeichen: Ortszeit)
    assert urteil(basis) == "nein (7 von 10 vor der Grenze; frühestes modified 7 h vor der Grenze)"
    versatz = basis[:3] + [dict(basis[3], modified=(grenze - dt.timedelta(minutes=59)).isoformat())]
    assert urteil(versatz) == "nein (1 von 4 vor der Grenze; frühestes modified 59 min vor der Grenze)"
    jahr = {"von": om._zeitpunkt("2025-01-01T00:00:00+01:00"), "bis": om._zeitpunkt("2025-12-31T23:59:59+01:00")}
    u = om._filter_urteil(basis, basis, "created", **jahr)
    assert u["bis"] == "nein (10 von 10 nach der Grenze; spätestes created 309,5 Tage nach der Grenze)"
    for sekunden, text in ((30, "30 s"), (300, "5 min"), (3600, "1 h"), (5400, "1 h 30 min"), (86340, "23 h 59 min"),
                           (2 * 86400, "2,0 Tage"), (-3600, "1 h")):
        assert om._dauer_text(dt.timedelta(seconds=sekunden)) == text


def _cache_wie_nach_stufe_1(monkeypatch, server, cache):
    """Cache wie nach Stufe 1: System, Body und erste Vorlagenseite des Servers in `cache`."""
    abruf = importlib.import_module("abruf")
    monkeypatch.setattr(abruf, "CACHE", cache)
    for url in (server.system_url, server.body_url, f"{server.body_url}/papers"):
        pfad = abruf._cachepfad(url, ".json")
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(server.antwort(url[len(server.basis):], "")[2])


def _alle_vorlagen_aendern(server):
    """Alle Vorlagen des Testservers jetzt geändert (nach dem Cache von Stufe 1)."""
    server.daten.alle_geaendert = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


@pytest.mark.parametrize("uebergeht", [True, False])
def test_modified_since_nach_aenderung_aller_vorlagen_nicht_unterscheidbar(server, tmp_path, monkeypatch, uebergeht):
    """kennzahlen mit dem Cache aus Stufe 1 (5 Anfragen), danach alle Vorlagen geändert: Ob der Server modified_since
    übergeht oder anwendet, ist nicht unterscheidbar (gleiche Kennungen); kein „ja“, auf das sich der inkrementelle Abruf
    stützen würde."""
    _cache_wie_nach_stufe_1(monkeypatch, server, tmp_path / "cache")
    _alle_vorlagen_aendern(server)
    server.ohne_modified_filter = uebergeht
    m = lauf(server, tmp_path, "kennzahlen", obergrenze=8)
    assert m["rc"] == 0 and m["server"] == 5, m["stderr"]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_kennzahlen.tsv") if z["objekt"] == "paper"}
    grenze = werte["grenze modified_since"].split(" ")[0]
    assert werte[f"test modified_since={grenze}"].endswith(
        "filter_wirksam=nicht unterscheidbar (gleiche Kennungen wie ohne Filter)")
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "etwa weil alle seither geändert wurden" in aus


@pytest.fixture
def kopf_server():
    """Fabrik für lokale HTTP-Server auf 127.0.0.1: `kopf` Sekunden vor dem Kopf warten, dann ein leerer Inhalt
    (Content-Length 0) oder, mit `ende`, eine chunked-Antwort, deren Abschluss erst nach `ende` Sekunden kommt."""
    gestartet = []

    def starten(kopf, ende=None):
        class H(socketserver.BaseRequestHandler):
            def handle(self):
                daten = b""
                while b"\r\n\r\n" not in daten:
                    teil = self.request.recv(4096)
                    if not teil:
                        return
                    daten += teil
                try:
                    time.sleep(kopf)
                    if ende is None:
                        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 0"
                                             b"\r\nConnection: close\r\n\r\n")
                        return
                    self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nTransfer-Encoding: "
                                         b"chunked\r\nConnection: close\r\n\r\n2\r\n{}\r\n")
                    time.sleep(ende)
                    self.request.sendall(b"0\r\n\r\n")
                except OSError:
                    return

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        server.daemon_threads, server.url = True, f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        gestartet.append(server)
        return server

    yield starten
    for server in gestartet:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("kopf, ende", [(1.3, None), (0, 1.3)])
def test_gesamtfrist_nach_dem_lesen_ohne_waechter(tmp_path, monkeypatch, kopf_server, kopf, ende):
    """Ohne Wächter (etwa außerhalb des Hauptthreads): leerer Inhalt nach langsamem Kopf bzw. später Abschluss einer
    chunked-Antwort, insgesamt über der Gesamtfrist (hier 1 s) → Art `sperre`, Status `Gesamtfrist`, nichts im Cache."""
    server = kopf_server(kopf, ende)
    abruf = _abruf_im_prozess(monkeypatch, tmp_path, GESAMTFRIST=1.0)
    monkeypatch.setattr(abruf, "_waechter_an", lambda: False)
    url = f"{server.url}/oparl/system"
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(url, ".json")
    assert e.value.art == "sperre" and "Gesamtfrist 1 s" in str(e.value)
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert (z["status"], z["quelle"]) == ("Gesamtfrist", "netz") and not abruf._cachepfad(url, ".json").exists()


def test_waechter_beendet_haengenden_kopf(tmp_path, monkeypatch, kopf_server):
    """Wächter (SIGALRM, Hauptthread): Der Kopf kommt erst nach 3 s, die Gesamtfrist (hier 1 s) beendet das Warten nach
    etwa 1 s → Art `sperre`, Status `Gesamtfrist`, nichts im Cache; danach ist kein Zeitgeber mehr gesetzt. Eine schnelle
    Antwort danach bleibt unberührt."""
    server = kopf_server(3.0)
    abruf = _abruf_im_prozess(monkeypatch, tmp_path, GESAMTFRIST=1.0)
    url = f"{server.url}/oparl/system"
    start = time.monotonic()
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(url, ".json")
    assert time.monotonic() - start < 2.0 and e.value.art == "sperre" and "hängender Verbindungsaufbau" in str(e.value)
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert (z["status"], z["quelle"]) == ("Gesamtfrist", "netz") and not abruf._cachepfad(url, ".json").exists()
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0) and not abruf._frist_aktiv
    schnell = kopf_server(0, 0.1)
    assert abruf.hole(f"{schnell.url}/a", ".json") == b"{}" and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def _marker(om, ordner, **werte):
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / om.MARKER
    pfad.write_text(json.dumps({"lauf": 2, "stufe": "2", "kommando": "kennzahlen", "parameter": "", "pid": 1, **werte}),
                    encoding="utf-8")
    return pfad


def test_markerdatei_ohne_vermerk_sperrt_12_stunden(tmp_path, capsys):
    """letzter_abbruch mit Markerdatei: jünger als 12 Stunden ohne Vermerk (hart beendet) oder unlesbar → „nicht regulär
    beendet“; älter → gemeldet und entfernt; ist der Lauf vermerkt, gilt der Vermerk (Marker entfernt)."""
    om = importlib.import_module("oparl_messung")
    erg, jetzt = tmp_path / "erg", dt.datetime(2026, 11, 8, 23, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    datei = erg / "oparl_laeufe.tsv"
    _laeufe(erg, (1, 1, "test", "", "2026-11-07T23:05:00+01:00", "2026-11-07T23:05:09+01:00", 9, 3, 0, 3, 0, 3, "ok", ""))
    pfad = _marker(om, tmp_path / "cache", start="2026-11-08T23:05:00+01:00")
    assert om.letzter_abbruch(datei, jetzt) is None                       # ohne `marker`: nur oparl_laeufe.tsv
    treffer = om.letzter_abbruch(datei, jetzt, pfad)
    assert (treffer["ergebnis"], treffer["lauf"], treffer["kommando"], treffer["marker"]) == (
        "nicht regulär beendet", 2, "kennzahlen", str(pfad)) and pfad.exists()
    pfad.write_text("{kaputt", encoding="utf-8")                           # unlesbar: vorsichtshalber gesperrt
    assert om.letzter_abbruch(datei, jetzt, pfad)["ergebnis"] == "nicht regulär beendet"
    pfad = _marker(om, tmp_path / "cache", start="2026-11-08T11:00:00+01:00")   # älter als 12 Stunden
    assert om.letzter_abbruch(datei, jetzt, pfad) is None and not pfad.exists()
    assert "Lauf 2 (kennzahlen, Stufe 2) vom 2026-11-08T11:00:00+01:00 wurde nicht regulär beendet" in capsys.readouterr().err
    # Lauf 2 ist vermerkt („ok“), der Marker blieb (Ende zwischen Vermerk und Entfernen): der Vermerk gilt
    _laeufe(erg, (1, 1, "test", "", "2026-11-07T23:05:00+01:00", "2026-11-07T23:05:09+01:00", 9, 3, 0, 3, 0, 3, "ok", ""),
            (2, 2, "kennzahlen", "", "2026-11-08T23:05:00+01:00", "2026-11-08T23:05:30+01:00", 30, 7, 3, 10, 3, 13, "ok",
             ""))
    pfad = _marker(om, tmp_path / "cache", start="2026-11-08T23:05:00+01:00")
    assert om.letzter_abbruch(datei, jetzt, pfad) is None and not pfad.exists()


def test_hart_beendeter_lauf_sperrt_den_naechsten(tmp_path):
    """Als Prozess gegen einen Testserver, der wie die Stadt behandelt wird (127.0.0.2): SIGKILL während der ersten
    Anfrage → kein Vermerk, die Markerdatei bleibt; der nächste Lauf schickt keine Anfrage (Rückgabewert 1, „nicht
    regulär beendet“). Mit RATSATLAS_NACH_ABBRUCH=ja läuft er und entfernt den Marker am Ende."""
    with testserver.Testserver(host="127.0.0.2") as stadt:
        stadt.verzoegerung = 3.0
        skript = str(EXPLORE / "oparl_messung.py")
        env = _wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="1", RATSATLAS_MAX_ANFRAGEN="3")
        marker = tmp_path / "cache" / "lauf_offen.json"
        p = subprocess.Popen([sys.executable, skript, "test"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True)
        frist = time.monotonic() + 30
        while not stadt.eingang and time.monotonic() < frist and p.poll() is None:
            time.sleep(0.02)
        inhalt = json.loads(marker.read_text(encoding="utf-8"))
        assert (inhalt["kommando"], inhalt["stufe"], inhalt["pid"]) == ("test", "1", p.pid)
        p.kill()                                                           # SIGKILL: kein Vermerk möglich
        p.communicate(timeout=30)
        assert p.returncode == -signal.SIGKILL and marker.exists()
        assert not (tmp_path / "ergebnisse" / "oparl_laeufe.tsv").exists()
        n = len(stadt.anfragen)
        zweiter = subprocess.run([sys.executable, skript, "test"], env=env, capture_output=True, text=True, timeout=60)
        assert zweiter.returncode == 1 and "nicht regulär beendet" in zweiter.stderr, zweiter.stderr
        assert "RATSATLAS_NACH_ABBRUCH" in zweiter.stderr and len(stadt.anfragen) == n and marker.exists()
        stadt.verzoegerung = 0.0
        dritter = subprocess.run([sys.executable, skript, "test"], env={**env, "RATSATLAS_NACH_ABBRUCH": "ja"},
                                 capture_output=True, text=True, timeout=120)
        assert dritter.returncode == 0, dritter.stderr
        assert not marker.exists() and tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]["ergebnis"] == "ok"


# --- Runde 12 (Wuppertal, Prüfung nach Phase-1-Übernahme): Abrufadresse, Kontaktfelder, gemeinsame 12-Stunden-Regel mit
# geodaten.py, Ortsnamen in Titeln, Gesamtzahl von meeting/person, Zeitfenster, erlaubte Hosts, Stand der Geodaten ------

def test_geodaten_und_oparl_messung_sperren_sich_gegenseitig(tmp_path, monkeypatch):
    """Gemeinsames Laufprotokoll ergebnisse/oparl_laeufe.tsv: Ein Abbruch der OParl-Messung sperrt geodaten.py (keine
    Anfrage), ein Abbruch von geodaten.py sperrt oparl_messung.py, eine Markerdatei ohne Vermerk sperrt beide; mit
    RATSATLAS_NACH_ABBRUCH=ja läuft geodaten.py weiter."""
    geodaten = importlib.import_module("geodaten")
    om = importlib.import_module("oparl_messung")
    abruf = importlib.import_module("abruf")
    for name, wert in GEO_FREIGABE.items():
        monkeypatch.setenv(name, wert)
    for name in ("RATSATLAS_NACH_ABBRUCH", "RATSATLAS_ABSTAND", "RATSATLAS_WIEDERHOLUNGEN", "RATSATLAS_MAX_DAUER"):
        monkeypatch.delenv(name, raising=False)
    for name, wert in (("CACHE", tmp_path / "cache"), ("PROTOKOLL", tmp_path / "cache" / "abrufe.tsv"),
                       ("KONTAKT", "test@example.invalid"), ("ABSTAND", 0.0), ("WIEDERHOLUNGEN", 0),
                       ("MAX_ANFRAGEN", 0),
                       ("USER_AGENT", "ratsatlas-wuppertal-explore/0.1 (+test; test@example.invalid)")):
        monkeypatch.setattr(abruf, name, wert)
    monkeypatch.setattr(geodaten, "im_zeitfenster", lambda jetzt=None: True)
    aufrufe = []

    def hole_sperre(url, endung="", cache=True, max_bytes=None):
        aufrufe.append(url)
        raise abruf.Abbruch("Test: Verbindungsabbruch, mögliche Sperre", "sperre")
    monkeypatch.setattr(geodaten, "hole", hole_sperre)
    # (1) Abbruch der OParl-Messung vor weniger als 12 Stunden → geodaten.py fragt nichts
    erg = tmp_path / "erg"
    jetzt = dt.datetime.now(ZoneInfo("Europe/Berlin")).replace(microsecond=0).isoformat()
    _laeufe(erg, (1, 3, "umfang", "", jetzt, jetzt, 1, 2, 0, 17, 0, 2, "abbruch (sperre)", "Test"))
    monkeypatch.setattr(geodaten, "ERG", erg)
    assert geodaten.main() == 1 and aufrufe == []
    assert len(tsv(erg / "oparl_laeufe.tsv")) == 1                         # kein Vermerk ohne Lauf
    # (2) geodaten.py bricht ab (mögliche Sperre) → Vermerk mit Kommando geodaten → oparl_messung.py sperrt
    erg2 = tmp_path / "erg2"
    monkeypatch.setattr(geodaten, "ERG", erg2)
    assert geodaten.main() == 2 and len(aufrufe) == 1
    vorher = om.letzter_abbruch(erg2 / "oparl_laeufe.tsv")
    assert (vorher["kommando"], vorher["ergebnis"], vorher["stufe"]) == ("geodaten", "abbruch (sperre)", "")
    assert not (tmp_path / "cache" / "lauf_offen.json").exists()
    for name, wert in (("ERG", erg2), ("SYSTEM", "https://example.invalid/oparl/system"),
                       ("BODY", "https://example.invalid/oparl/bodies/x"), ("_LISTEN", [])):
        monkeypatch.setattr(om, name, wert)
    monkeypatch.setenv("RATSATLAS_ZEITFENSTER", "")                         # Testadresse (.invalid)
    monkeypatch.setattr(om, "hole", lambda *a, **k: pytest.fail("darf nicht abrufen"))
    with pytest.raises(SystemExit) as e:
        om.main(["test"])
    assert "RATSATLAS_NACH_ABBRUCH" in str(e.value.code) and "(geodaten)" in str(e.value.code)
    # (3) Markerdatei eines hart beendeten Laufs (ohne Vermerk) sperrt geodaten.py ebenso
    erg3 = tmp_path / "erg3"
    monkeypatch.setattr(geodaten, "ERG", erg3)
    marker = om._marker_setzen({"lauf": 1, "stufe": "3", "kommando": "umfang", "parameter": "", "start": jetzt})
    assert geodaten.main() == 1 and len(aufrufe) == 1
    om._marker_entfernen(marker)
    # (4) freigegeben nach Rücksprache: geodaten.py läuft (hier ohne Netz: Abbruch beim ersten Abruf, vermerkt)
    monkeypatch.setattr(geodaten, "ERG", erg)
    monkeypatch.setenv("RATSATLAS_NACH_ABBRUCH", "ja")
    assert geodaten.main() == 2 and len(aufrufe) == 2
    assert [z["kommando"] for z in tsv(erg / "oparl_laeufe.tsv")] == ["umfang", "geodaten"]


def test_zeitfenster_fuer_die_stadt_nur_23_bis_1(tmp_path, monkeypatch):
    """RATSATLAS_ZEITFENSTER darf für Server der Stadt nur enger als 23–1 Uhr sein: leer oder weiter gilt als außerhalb
    (auch in geodaten.py). Nur Testadressen (Loopback, .invalid) dürfen das Fenster abschalten oder weiten."""
    om = importlib.import_module("oparl_messung")
    geodaten = importlib.import_module("geodaten")
    berlin = ZoneInfo("Europe/Berlin")

    def um(h):
        return dt.datetime(2026, 11, 9, h, 30, tzinfo=berlin)
    stadt = "https://oparl.wuppertal.de/oparl/system"
    for wert in ("", "0-24", "1-1", "8-20", "22-1", "23-2", "0-0"):
        monkeypatch.setenv("RATSATLAS_ZEITFENSTER", wert)
        assert not any(om.im_zeitfenster(um(h), stadt) for h in range(24)), wert
        assert not any(geodaten.im_zeitfenster(um(h)) for h in range(24)), wert
    for wert, offen in (("23-1", {23, 0}), ("23-24", {23}), ("0-1", {0})):
        monkeypatch.setenv("RATSATLAS_ZEITFENSTER", wert)
        assert {h for h in range(24) if om.im_zeitfenster(um(h), stadt)} == offen, wert
    monkeypatch.setenv("RATSATLAS_ZEITFENSTER", "")
    for url in ("http://127.0.0.2:8000/x", "https://example.invalid/x", "http://localhost/x", "http://[::1]:80/x"):
        assert om.testadresse(url) and om.im_zeitfenster(um(12), url), url
    for url in (stadt, "https://daten.wuppertal.de/x", "https://invalid.example.org/x", "https://example.org/x", None):
        assert not om.testadresse(url), url
    # als Lauf gegen die Stadt: leerer Wert → Abbruch vor der ersten Anfrage
    for name, wert in (("ERG", tmp_path / "erg"), ("SYSTEM", stadt),
                       ("BODY", "https://oparl.wuppertal.de/oparl/bodies/0001")):
        monkeypatch.setattr(om, name, wert)
    monkeypatch.setenv("RATSATLAS_MESSUNG_FREIGEGEBEN", "ja")
    monkeypatch.setattr(om, "hole", lambda *a, **k: pytest.fail("darf nicht abrufen"))
    with pytest.raises(SystemExit) as e:
        om.main(["test"])
    assert "Zeitfenster" in str(e.value.code)


def test_nur_hosts_der_stadt_und_von_system_und_body(tmp_path, monkeypatch):
    """_hole sendet nur an Hosts der Stadt und an die Hosts von SYSTEM/BODY; ein lokaler Probelauf nur an lokale
    Adressen, ein Lauf gegen die Stadt nie an lokale. Die 12-Stunden-Regel gilt auch ohne main()."""
    om = importlib.import_module("oparl_messung")
    _wie_die_stadt_im_prozess(om, monkeypatch, tmp_path)
    geholt = []
    monkeypatch.setattr(om, "hole", lambda url, endung="", max_bytes=None: geholt.append(url) or b"{}")
    monkeypatch.setattr(om, "SYSTEM", "https://oparl.wuppertal.de/oparl/system")
    monkeypatch.setattr(om, "BODY", "https://oparl.wuppertal.de/oparl/bodies/0001")
    for fremd in ("https://example.org/oparl/x", "http://127.0.0.1:8765/oparl/system",
                  "https://oparl.wuppertal.de.example.org/x", "http://evilwuppertal.de/x"):
        with pytest.raises(om.Abbruch) as e:
            om._hole(fremd)
        assert e.value.art == "adresse", fremd
    assert geholt == []
    om._hole("http://ris.wuppertal.de/x")
    assert geholt == ["https://ris.wuppertal.de/x"]
    # lokaler Probelauf: keine Adresse der Stadt (auch nicht aus links.next oder auxiliaryFile)
    monkeypatch.setattr(om, "SYSTEM", "http://127.0.0.1:9/oparl/system")
    monkeypatch.setattr(om, "BODY", "http://127.0.0.1:9/oparl/bodies/0001")
    for fremd in ("http://oparl.wuppertal.de/oparl/bodies/0001/papers?page=2", "https://example.invalid/x"):
        with pytest.raises(om.Abbruch) as e:
            om._hole(fremd)
        assert e.value.art == "adresse", fremd
    om._hole("http://127.0.0.1:9/oparl/bodies/0001/papers?page=2")
    assert len(geholt) == 2
    # 12-Stunden-Regel ohne main(): ein Abbruch im Laufprotokoll sperrt die erste Anfrage an die Stadt
    monkeypatch.setattr(om, "SYSTEM", "https://oparl.wuppertal.de/oparl/system")
    monkeypatch.setattr(om, "BODY", "https://oparl.wuppertal.de/oparl/bodies/0001")
    monkeypatch.setattr(om, "_sperrfrist_geprueft", False)
    jetzt = dt.datetime.now(ZoneInfo("Europe/Berlin")).replace(microsecond=0).isoformat()
    _laeufe(tmp_path / "erg", (1, "G", "geodaten", "laden", jetzt, jetzt, 1, 1, 0, 10, 0, 1, "abbruch (sperre)", "x"))
    with pytest.raises(om.Abbruch, match="RATSATLAS_NACH_ABBRUCH") as e:
        om._hole("https://oparl.wuppertal.de/oparl/system")
    assert e.value.art == "gesperrt" and len(geholt) == 2


def test_umfang_liste_person_und_meeting(server, tmp_path):
    """`umfang --liste person|meeting`: ohne totalElements das Listenende per Bisektion im Bereich --ende-seiten (Pflicht),
    höchstens hoechstzahl_umfang(None, Bereich) Anfragen; Personen nur gezählt (keine Namen); mit totalElements ohne
    weitere Anfrage; Auswertung nennt die Gesamtzahl bzw. „Gesamtzahl offen“."""
    om = importlib.import_module("oparl_messung")
    assert om.hoechstzahl_umfang(None, (2, 8)) == 7 and om.hoechstzahl_umfang() == 17
    m = lauf(server, tmp_path, "umfang", "--liste", "person", obergrenze=7)
    assert m["rc"] == 2 and "--ende-seiten" in m["stderr"] and m["server"] == 0     # Bereich ist Pflicht
    m = lauf(server, tmp_path, "umfang", "--liste", "person", "--ende-seiten", "2", "8", obergrenze=7)
    assert m["rc"] == 0 and m["server"] <= 7, m["stderr"]
    assert m["lauf"]["parameter"] == "--liste person --ende-seiten 2 8"
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_umfang_person.tsv")}
    assert (werte["letzte_seite"], werte["person_gesamt"]) == ("3", "300 (bei 100 je Seite)")
    for datei in (tmp_path / "ergebnisse").glob("oparl_umfang_person*.tsv"):
        assert "[Testdaten] Person" not in datei.read_text(encoding="utf-8")       # keine Namen
    m = lauf(server, tmp_path, "umfang", "--liste", "meeting", "--ende-seiten", "2", "4", obergrenze=6)
    assert m["rc"] == 0, m["stderr"]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_umfang_meeting.tsv")}
    assert werte["letzte_seite"] == "nicht im Bereich (Seite 4 gefüllt)" and "meeting_gesamt" not in werte
    # Auswertung: person gemessen, meeting außerhalb des Bereichs (offen); ohne Messung ausdrücklich offen
    assert lauf(server, tmp_path, "kennzahlen", obergrenze=8)["rc"] == 0
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "- person: Gesamtzahl 300 (bei 100 je Seite) (umfang --liste person)" in aus
    assert ("- meeting: Gesamtzahl offen (umfang --liste meeting: letzte Seite nicht im Bereich (Seite 4 gefüllt))"
            in aus)
    (tmp_path / "ergebnisse" / "oparl_umfang_meeting.tsv").unlink()
    aus = importlib.import_module("auswertung").auswertung(tmp_path / "cache", tmp_path / "ergebnisse")
    assert "- meeting: Gesamtzahl offen (pagination.totalElements fehlt; umfang --liste meeting nicht ausgeführt)" in aus
    # mit Gesamtzahlen: keine Anfrage über Body und erste Seite hinaus
    with testserver.Testserver(gesamtzahlen=True) as gesamt:
        m = lauf(gesamt, tmp_path, "umfang", "--liste", "meeting", "--ende-seiten", "2", "8", obergrenze=7,
                 cache="cache2")
        assert m["rc"] == 0 and m["server"] == 2, m["stderr"]
    werte = {z["feld"]: z["wert"] for z in tsv(tmp_path / "ergebnisse" / "oparl_umfang_meeting.tsv")}
    assert werte["meeting_gesamt"] == "600 (pagination.totalElements, ohne weitere Anfrage)"


def test_papertyp_ebenen_wort_ist_keine_einreichende():
    """Ein Ebenen-Wort ohne Fraktion davor („Antrag BV“, „Antrag Rat“) gilt nicht als Einreichende; die Quote
    „Einreichende genannt“ zählt das „–“ der Verwaltungsvorlagen nicht und bezieht sich auf politische Vorlagen."""
    aw = importlib.import_module("auswertung")
    regeln = aw.regeln_laden()
    for pt in ("Antrag BV", "Antrag Rat", "Antrag CDU Rat AU XY", "Große Anfrage BV Rat"):
        assert aw.zerlege(pt, regeln)["status"] == aw.NICHT_ZERLEGT, pt
    assert aw.zerlege("Antrag CDU Rat", regeln)["einreichende"] == "CDU"
    _, q = aw.papertyp_abdeckung([("Antrag CDU", "30"), ("Bericht", "60"), ("Gemeinsamer Antrag BV", "10"),
                                  ("Antrag BV", "5")], regeln)
    assert q["einreichende"] == (90, 105) and q["einreichende_genannt"] == (30, 40)


def test_ortsnamen_in_erfundenen_titeln(tmp_path):
    """explore/ortsnamen.py ohne Netz: längster Treffer zuerst mit Wortgrenzen, Doppelnamen in Teilen, Ausschlussliste
    (BV, Rathaus, Barmer), Auswahl gleichmäßig über die Jahre mit fester Saat; Ergebnisse ohne Titeltexte."""
    on = importlib.import_module("ortsnamen")
    titel = {"p0": "[Testdaten] Spielplatz in Oberbarmen", "p1": "[Testdaten] Antrag der BV Barmen zu Barmen",
             "p2": "[Testdaten] Sitzung im Rathaus Barmen", "p3": "[Testdaten] Barmer Ersatzkasse",
             "p4": "[Testdaten] Radweg Elberfeld-West", "p5": "[Testdaten] Schule in Beyenburg",
             "p6": "[Testdaten] Elberfelder Markt", "p7": None, "p8": "[Testdaten] Bezirksvertretung Elberfeld tagt"}
    stichprobe = tmp_path / "s.jsonl"
    stichprobe.write_text("".join(json.dumps({"id": k, "name": t, "reference": f"VO/000{i}/2{i % 7}",
                                              "date": f"202{i % 7}-03-01"}) + "\n"
                                  for i, (k, t) in enumerate(titel.items())), encoding="utf-8")
    gebiete = tmp_path / "geodaten_gebiete.tsv"
    gebiete.write_text("datensatz\tnamensfeld\tname\tobjekte\n" + "".join(
        f"{d}\tNAME\t{n}\t1\n" for d, n in (("stadtbezirke", "Barmen"), ("stadtbezirke", "Oberbarmen"),
                                             ("stadtbezirke", "Elberfeld"), ("stadtbezirke", "Elberfeld-West"),
                                             ("stadtbezirke", "Langerfeld-Beyenburg"), ("quartiere", "Barmen"))),
        encoding="utf-8")
    verz = on.verzeichnis(tsv(gebiete))
    assert {"Langerfeld", "Beyenburg"} <= set(verz) and "West" not in verz      # Teile, ohne Himmelsrichtung
    assert verz["Barmen"]["ebenen"] == {"stadtbezirk", "quartier"}
    erg = tmp_path / "erg"
    assert on.main(["--stichprobe", str(stichprobe), "--gebiete", str(gebiete), "--ergebnisse", str(erg)]) == 0
    zeilen = {z["id"]: z for z in tsv(erg / "ortsnamen_titel.tsv")}
    assert len(zeilen) == 9
    assert zeilen["p0"]["treffer"] == "Oberbarmen"                               # nicht zusätzlich Barmen
    assert zeilen["p4"]["treffer"] == "Elberfeld-West"                           # nicht zusätzlich Elberfeld
    assert zeilen["p5"]["treffer"] == "Beyenburg" and "teil von Langerfeld-Beyenburg" in zeilen["p5"]["ebenen"]
    assert (zeilen["p1"]["treffer"], zeilen["p1"]["ausgeschlossen"]) == ("Barmen", "Barmen (Regel 1)")
    assert (zeilen["p2"]["treffer"], zeilen["p2"]["ausgeschlossen"]) == ("", "Barmen (Regel 3)")
    assert (zeilen["p8"]["treffer"], zeilen["p8"]["ausgeschlossen"]) == ("", "Elberfeld (Regel 2)")
    assert zeilen["p3"]["treffer"] == "" and zeilen["p3"]["regeln"] == "4"       # Barmer: Eigenname, kein Treffer
    assert zeilen["p6"]["treffer"] == "" and zeilen["p7"]["treffer"] == on.OHNE_TITEL
    zaehl = {z["kennzahl"]: z for z in tsv(erg / "ortsnamen_zaehlung.tsv")}
    assert zaehl["titel mit treffer"]["wert"] == "4" and zaehl["schätzung stufe b (gebietsnamen)"]["wert"] == "4 von 9"
    assert "Untergrenze" in zaehl["schätzung stufe b (gebietsnamen)"]["anmerkung"]
    for datei in erg.iterdir():                                                 # keine Titeltexte
        text = datei.read_text(encoding="utf-8")
        assert "Testdaten" not in text and "Spielplatz" not in text, datei.name
    # Auswahl: gleichmäßig über die Jahre, wiederholbar mit derselben Saat
    vorlagen = [{"id": f"x{i}", "name": "t", "reference": f"VO/{i:04d}/{20 + i % 7}"} for i in range(700)]
    a, b = on.auswahl(vorlagen, 300, 7), on.auswahl(vorlagen, 300, 7)
    assert [p["id"] for p in a] == [p["id"] for p in b] and len(a) == 300
    je = collections.Counter(p["reference"][-2:] for p in a)
    assert sorted(je.values()) == [42] + [43] * 6 and je["20"] == 42                  # neuere Jahre zuerst
    assert on.auswahl(vorlagen, 300, 8) != a                                    # andere Saat, andere Auswahl
    # Eingaben fehlen bzw. Stichprobe ohne Titel: Rückgabewert 1
    assert on.main(["--stichprobe", str(tmp_path / "fehlt.jsonl"), "--gebiete", str(gebiete)]) == 1
    alt = tmp_path / "alt.jsonl"
    alt.write_text(json.dumps({"id": "p", "reference": "VO/0001/24"}) + "\n", encoding="utf-8")
    assert on.main(["--stichprobe", str(alt), "--gebiete", str(gebiete), "--ergebnisse", str(erg)]) == 1


def test_kopfangaben_und_stand_der_geodaten(tmp_path, monkeypatch, server):
    """abruf.py legt zu jeder gespeicherten Antwort Last-Modified und ETag (soweit geliefert) in eine Begleitdatei;
    geodaten.py übernimmt daraus den Stand und bei Zip die Zeitstempel der Einträge, Vergleich mit dem Auftrag."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path / "cache")
    daten = abruf.hole(server.system_url, ".json")
    kopf = abruf.kopfangaben(server.system_url, ".json")
    assert kopf["url"] == server.system_url and "Last-Modified" not in kopf and daten  # Testserver: ohne Last-Modified
    assert abruf.kopfangaben("http://127.0.0.1:1/fehlt", ".json") == {}
    geodaten = importlib.import_module("geodaten")
    url_zip = "https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Strassenverzeichnis_CSV.zip"
    url_b = "https://daten.wuppertal.de/Gesetze_Justiz/rvbBebauungsplanverfahren_EPSG4326_JSON.json"
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(zipfile.ZipInfo("t.csv", date_time=(2021, 9, 6, 8, 0, 0)), "STRSCHL;STRNAME\n1;Teststr.\n")
        z.writestr(zipfile.ZipInfo("u.csv", date_time=(2021, 8, 1, 8, 0, 0)), "X\n1\n")
    for url, endung, inhalt, kopf in ((url_zip, ".zip", b.getvalue(), {}),
                                      (url_b, ".json", b'{"features": []}',
                                       {"Last-Modified": "Mon, 01 Jun 2026 10:00:00 GMT", "ETag": "\"x1\""})):
        pfad = abruf._cachepfad(url, endung)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(inhalt)
        abruf._kopf_schreiben(pfad, url, kopf)
    stand = geodaten.stand_der_datei(url_zip, b.getvalue())
    assert stand == {"stand_http": "offen", "etag": "offen", "stand_zip": "2021-08-01 bis 2021-09-06 (2 Einträge)"}
    assert geodaten.stand_der_datei(url_b, b"{}")["stand_http"] == "Mon, 01 Jun 2026 10:00:00 GMT"
    monkeypatch.setattr(geodaten, "hole", lambda *a, **k: pytest.fail("Netzanfrage in ableiten"))
    geodaten.ableiten({"strassenverzeichnis": (url_zip, b.getvalue()), "bplaene_rechtsverbindlich": (url_b, b'{}')},
                      tmp_path / "erg")
    abl = {(z["pruefung"], z["datensatz"]): z for z in tsv(tmp_path / "erg" / "geodaten_ableitungen.tsv")}
    sv, bp = abl[("stand", "strassenverzeichnis")], abl[("stand", "bplaene_rechtsverbindlich")]
    assert (sv["wert"], sv["ergebnis"]) == ("09/2021", "gleicher Monat (Zip-Einträge)") and "09/2021" in sv["auftrag"]
    assert (bp["wert"], bp["ergebnis"]) == ("06/2026", "gleicher Monat (Last-Modified)") and "x1" in bp["anmerkung"]



def test_stufe_g_geodaten_befehl_vollstaendig():
    """STUFEN.md, Stufe G: genau ein vollständiger Befehl für geodaten.py mit Freigabe, Kontakt, ohne Wiederholung und
    mit der Obergrenze geplante_anfragen() (ohne Reserve); die Vorgaben von geodaten.py sind damit erfüllt."""
    geodaten = importlib.import_module("geodaten")
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    befehle = [z for z in text.splitlines() if "explore/geodaten.py" in z and z.startswith("RATSATLAS_")]
    assert len(befehle) == 1 and befehle[0].endswith("python3 explore/geodaten.py laden")
    env = {k: v.strip('"') for k, v in re.findall(r'(RATSATLAS_[A-Z_]+)=("[^"]*"|\S+)', befehle[0])}
    assert env["RATSATLAS_KONTAKT"] == "contact@nozilla.de" and env["RATSATLAS_STUFE"] == "G"
    werte, fehler = geodaten.vorgaben(env)
    assert fehler == [] and werte["max_anfragen"] == geodaten.geplante_anfragen() == 10
    assert "RATSATLAS_ZEITFENSTER" not in env and "RATSATLAS_ABSTAND" not in env


# --- Nachträge an explore/abruf.py nach Messstufe 1 (Branch nachtrag-abruf) ---------------------------------------------

def test_nachtrag_1_antwortzeit_vor_groesse_und_langsame_antwort_nicht_im_cache(tmp_path, monkeypatch, server):
    """Nachtrag 1: Eine langsame Antwort bleibt nicht im Cache (Inhalt nur am Abbruch); der nächste Aufruf fragt erneut.
    Eine Antwort, die zu langsam und zugleich zu groß ist, ist Art `langsam` (Antwortzeit vor der Größe)."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path, MAX_DAUER=0.2)
    server.verzoegerung = 0.4
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(server.system_url, ".json")
    assert e.value.art == "langsam" and "nicht im Cache" in str(e.value)
    assert json.loads(e.value.daten)["id"] and not abruf._cachepfad(server.system_url, ".json").exists()
    assert not abruf._begleitpfad(abruf._cachepfad(server.system_url, ".json")).exists()
    # zu langsam und zu groß (Content-Length über max_bytes): Art `langsam`, nicht `groesse`; nichts im Cache
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(server.body_url, ".json", max_bytes=10)
    assert e.value.art == "langsam" and not abruf._cachepfad(server.body_url, ".json").exists()
    # danach schnell: erneute Anfrage (nicht aus dem Cache), jetzt gespeichert
    server.verzoegerung = 0
    vorher = len(server.anfragen)
    assert abruf.hole(server.system_url, ".json") and len(server.anfragen) == vorher + 1
    assert abruf._cachepfad(server.system_url, ".json").exists()


def test_nachtrag_2_groessengrenze_je_aufruf(tmp_path, monkeypatch, roher_server):
    """Nachtrag 2: max_bytes senkt MAX_BYTES nur für diesen Aufruf (höher geht nicht, MAX_BYTES bleibt); Content-Length
    über der Grenze: Abbruch nach dem Kopf, Inhalt nicht gelesen (0 Bytes); ohne Content-Length (chunked) höchstens
    Grenze + 1 Byte gelesen; ungültige Grenze: ValueError ohne Anfrage."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path, MAX_BYTES=1000)
    mit_laenge = roher_server(b"HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: 2000\r\n\r\n"
                              + b"x" * 2000)
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(f"{mit_laenge.url}/a.pdf", ".pdf", max_bytes=1500)
    assert e.value.art == "groesse" and "laut Content-Length" in str(e.value)
    assert (e.value.abruf["bytes"], e.value.abruf["max_bytes"], e.value.abruf["status"]) == (0, 1000, "200")
    z = tsv(tmp_path / "abrufe.tsv")[-1]
    assert (z["status"], z["bytes"], z["quelle"]) == ("200", "0", "netz")
    assert abruf.MAX_BYTES == 1000 and not list(tmp_path.glob("roh/*"))
    # unter der Grenze laut Content-Length, aber kleiner als MAX_BYTES: gespeichert
    klein = roher_server(b"HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nContent-Length: 20\r\n\r\n" + b"y" * 20)
    assert abruf.hole(f"{klein.url}/b.pdf", ".pdf", max_bytes=20) == b"y" * 20
    # chunked ohne Content-Length: höchstens Grenze + 1 Byte gelesen
    chunked = roher_server(b"HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\nTransfer-Encoding: chunked\r\n\r\n"
                           b"32\r\n" + b"z" * 50 + b"\r\n0\r\n\r\n")
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(f"{chunked.url}/c.pdf", ".pdf", max_bytes=10)
    assert e.value.art == "groesse" and e.value.abruf["bytes"] == 11
    assert tsv(tmp_path / "abrufe.tsv")[-1]["bytes"] == "11"
    # ungültige Grenze: keine Anfrage, keine Protokollzeile
    zeilen = len(tsv(tmp_path / "abrufe.tsv"))
    for wert in (0, -1, 1.5, "10", True):
        with pytest.raises(ValueError):
            abruf.hole(f"{klein.url}/d.pdf", ".pdf", max_bytes=wert)
    assert len(klein.anfragen) == 1 and len(tsv(tmp_path / "abrufe.tsv")) == zeilen


def test_nachtrag_3_content_type_und_laenge_in_der_begleitdatei(tmp_path, monkeypatch, server):
    """Nachtrag 3: Begleitdatei im Cache mit Status, Antwortzeit, Content-Type und Content-Length; kopfangaben liefert
    sie ohne Anfrage. STUFEN.md nennt jede Spalte von pdf_koepfe.tsv (auch content_type)."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path)
    daten = abruf.hole(server.system_url, ".json")
    kopf = abruf.kopfangaben(server.system_url, ".json")
    assert (kopf["Content-Type"], kopf["Content-Length"], kopf["status"]) == ("application/json", str(len(daten)), "200")
    assert float(kopf["dauer_s"]) >= 0 and set(abruf.KOPFANGABEN) >= {"Content-Type", "Content-Length"}
    assert abruf._kopfwert("text/html;\tcharset=x\r\n" + "a" * 300) == "text/html; charset=x " + "a" * 179
    assert abruf._kopfwert("application/pdf\x1b[2J\x00\x07X\x7f\x85Y") == "application/pdf [2J X Y"
    om = importlib.import_module("oparl_messung")
    stufe_6 = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8").split("## Stufe 6")[1].split("## Stufe G")[0]
    assert "content_type" in om.PDF_SPALTEN and all(f"`{s}`" in stufe_6 for s in om.PDF_SPALTEN), [
        s for s in om.PDF_SPALTEN if f"`{s}`" not in stufe_6]


def test_nachtrag_4_angaben_zum_aufruf_ohne_abrufprotokoll(tmp_path, monkeypatch, server):
    """Nachtrag 4: Quelle, Status und Antwortzeit eines Aufrufs über letzter_abruf() bzw. Abbruch.abruf; hole() liefert
    weiter bytes; ohne Anfrage keine Angaben. oparl_messung liest dafür nicht mehr _cache/abrufe.tsv (hier /dev/null)."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path)
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(f"{server.system_url} x", ".json")
    assert e.value.art == "adresse" and e.value.abruf is None and abruf.letzter_abruf() is None
    daten = abruf.hole(server.system_url, ".json")
    netz = abruf.letzter_abruf()
    assert isinstance(daten, bytes) and (netz["quelle"], netz["status"], netz["bytes"]) == ("netz", "200", len(daten))
    assert netz["antwortzeit_s"] == netz["dauer_s"] >= 0 and netz["content_type"] == "application/json"
    assert netz["url"] == server.system_url and netz["max_bytes"] == abruf.MAX_BYTES
    assert abruf.hole(server.system_url, ".json") == daten
    cache = abruf.letzter_abruf()
    assert (cache["quelle"], cache["status"], cache["dauer_s"]) == ("cache", "cache", 0)
    assert f"{cache['antwortzeit_s']:.2f}" == f"{netz['antwortzeit_s']:.2f}" and cache["content_type"] == "application/json"
    assert cache["content_length"] == netz["content_length"] == str(len(daten))
    with pytest.raises(abruf.Abbruch) as e:
        abruf.hole(f"{server.body_url}/gibt-es-nicht", ".json")
    assert e.value.art == "http" and (e.value.abruf["status"], e.value.abruf["quelle"]) == ("404", "netz")
    # _pdf_holen: Messwerte aus letzter_abruf(), auch wenn das Abrufprotokoll nicht lesbar ist
    om = importlib.import_module("oparl_messung")
    assert not hasattr(om, "_protokollzeile")
    monkeypatch.setattr(abruf, "PROTOKOLL", Path(os.devnull))
    monkeypatch.setattr(abruf, "_kopf_geprueft", True)
    monkeypatch.setattr(om, "SYSTEM", server.system_url)
    monkeypatch.setattr(om, "BODY", server.body_url)
    p = next(p for p in map(server.daten.vorlage, range(200)) if p["paperType"] == "Beschlussvorlage")
    url = om.datei_waehlen({"reference": p["reference"], "paperType": p["paperType"],
                            "dateiliste": om._dateiliste(p)})[0]
    z = dict.fromkeys(om.PDF_SPALTEN, "")
    assert om._pdf_holen(url, z, 10 * 1024 * 1024).startswith(b"%PDF-")
    assert (z["quelle"], z["content_type"]) == ("netz", "application/pdf") and float(z["antwort_s"]) >= 0
    z = dict.fromkeys(om.PDF_SPALTEN, "")
    om._pdf_holen(url, z, 10 * 1024 * 1024)
    assert (z["quelle"], z["content_type"]) == ("cache", "application/pdf") and float(z["antwort_s"]) >= 0


def test_nachtrag_5_nur_cache_ohne_netzanfrage(tmp_path, monkeypatch, server):
    """Nachtrag 5: Im reinen Cache-Modus keine Netzanfrage, auch nicht für fehlende Einträge oder mit cache=False
    (Abbruch der Art `cache` vor Sperre und Obergrenze, keine Protokollzeile); vorhandene Einträge kommen aus dem Cache.
    RATSATLAS_NUR_CACHE: „ja“ und jeder andere nicht leere Wert außer „nein“ schalten den Modus ein."""
    abruf = _abruf_im_prozess(monkeypatch, tmp_path)
    daten = abruf.hole(server.system_url, ".json")
    vorher, zeilen = len(server.anfragen), len(tsv(tmp_path / "abrufe.tsv"))
    monkeypatch.setattr(abruf, "NUR_CACHE", True)
    monkeypatch.setattr(abruf, "_sperre", None)
    monkeypatch.setattr(abruf, "MAX_ANFRAGEN", 1)
    netz = abruf.zaehler()["netz"]
    for url, cache in ((server.body_url, True), (server.system_url, False)):
        with pytest.raises(abruf.Abbruch) as e:
            abruf.hole(url, ".json", cache=cache)
        assert e.value.art == "cache" and e.value.abruf is None
    assert len(server.anfragen) == vorher and len(tsv(tmp_path / "abrufe.tsv")) == zeilen
    assert abruf._sperre is None and abruf.zaehler()["netz"] == netz
    assert abruf.hole(server.system_url, ".json") == daten and abruf.letzter_abruf()["quelle"] == "cache"
    assert len(server.anfragen) == vorher
    for wert, erwartet in (("ja", True), ("", False), ("nein", False), ("1", True), (" JA ", True)):
        r = subprocess.run([sys.executable, "-c", "import abruf; print(abruf.NUR_CACHE)"], cwd=EXPLORE,
                           capture_output=True, text=True, timeout=60,
                           env={**os.environ, "RATSATLAS_NUR_CACHE": wert, "RATSATLAS_SPERRE": str(tmp_path / "s")})
        assert r.stdout.strip() == str(erwartet), (wert, r.stderr)


def test_nachtrag_5_nur_cache_laeufe_zaehlen_nicht_fuer_die_12_stunden_regel(tmp_path):
    """Ein Lauf im reinen Cache-Modus (Vermerk in `parameter`) verdeckt keinen früheren Abbruch."""
    om = importlib.import_module("oparl_messung")
    jetzt = dt.datetime(2026, 11, 10, 0, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    datei = tmp_path / "oparl_laeufe.tsv"
    _laeufe_schreiben = [
        {"lauf": "1", "kommando": "pdf-koepfe", "parameter": "--anzahl 100", "ende": "2026-11-09T23:30:00+01:00",
         "ergebnis": "abbruch (sperre)"},
        {"lauf": "2", "kommando": "pdf-koepfe", "parameter": f"--anzahl 100; {om.NUR_CACHE_VERMERK}",
         "ende": "2026-11-10T00:10:00+01:00", "ergebnis": "ok"}]
    with datei.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, om.LAEUFE_SPALTEN, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(_laeufe_schreiben)
    vorher = om.letzter_abbruch(datei, jetzt)
    assert vorher and vorher["lauf"] == "1" and vorher["ergebnis"] == "abbruch (sperre)"


def test_nachtrag_5_stufe_6_neu_auswerten_ohne_netz(tmp_path):
    """Stufe 6 nach einem Lauf wie bei der Stadt (127.0.0.2) im reinen Cache-Modus wiederholen: ohne Freigabe, außerhalb
    des Zeitfensters, ohne Obergrenze und Kontakt keine Anfrage; Zeilen der Dateien im Cache neu ausgewertet, Dateien
    mit HTTP 404 oder „zu groß“ aus der früheren Zeile übernommen; Vermerk „nur Cache“, keine Markerdatei."""
    pytest.importorskip("pypdf")
    om = importlib.import_module("oparl_messung")
    with testserver.Testserver(host="127.0.0.2") as stadt:
        cache = tmp_path / "cache"
        cache.mkdir()
        vorlagen = [p for p in map(stadt.daten.vorlage, range(400)) if p["paperType"] == "Beschlussvorlage"
                    and not p.get("underDirectionOf")][:4]
        with (cache / "stichprobe_vorlagen.jsonl").open("w", encoding="utf-8") as f:
            for p in vorlagen:
                f.write(json.dumps({"id": p["id"], "name": p["name"], "reference": p["reference"],
                                    "paperType": p["paperType"], "date": p["date"], "underDirectionOf": False,
                                    "datei": om._erste_datei(p)[0], "dateien": len(p["auxiliaryFile"]),
                                    "dateiliste": om._dateiliste(p)}) + "\n")
        varianten = iter(("404", "gross", None, None))
        zuordnung = {}
        stadt.pdf_variante = lambda nr: zuordnung.setdefault(nr, next(varianten))
        skript = str(EXPLORE / "oparl_messung.py")
        env = _wie_die_stadt(stadt, tmp_path, RATSATLAS_STUFE="6", RATSATLAS_MAX_ANFRAGEN="4",
                             RATSATLAS_PDF_FREIGEGEBEN="ja", RATSATLAS_PDF_MAX_BYTES="200000")
        erst = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "4"], capture_output=True, text=True,
                              timeout=120, env=env)
        assert erst.returncode == 0 and len(stadt.anfragen) == 4, erst.stderr
        vorher = tsv(tmp_path / "ergebnisse" / "pdf_koepfe.tsv")
        assert {z["treffer"] for z in vorher} >= {"fehler: HTTP 404", "zu groß"}
        ohne_netz = {k: v for k, v in env.items() if k not in (
            "RATSATLAS_MESSUNG_FREIGEGEBEN", "RATSATLAS_PDF_FREIGEGEBEN", "RATSATLAS_MAX_ANFRAGEN", "RATSATLAS_KONTAKT")}
        ohne_netz.update(RATSATLAS_NUR_CACHE="ja", RATSATLAS_ZEITFENSTER="23-23", RATSATLAS_STUFE="6")
        stadt.pdf_variante = lambda nr: pytest.fail("Anfrage im reinen Cache-Modus")
        neu = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "4"], capture_output=True,
                             text=True, timeout=120, env=ohne_netz)
        assert neu.returncode == 0, neu.stderr
        assert len(stadt.anfragen) == 4   # keine weitere Anfrage
    nachher = tsv(tmp_path / "ergebnisse" / "pdf_koepfe.tsv")
    assert [(z["id"], z["treffer"], z["bytes"], z["content_type"]) for z in nachher] == [
        (z["id"], z["treffer"], z["bytes"], z["content_type"]) for z in vorher]
    for alt, z in zip(vorher, nachher):
        if alt["treffer"] in ("fehler: HTTP 404", "zu groß"):
            assert z["quelle"] == om.FRUEHER and z["antwort_s"] == alt["antwort_s"]
        else:
            assert (z["quelle"], z["antwort_s"]) == ("cache", alt["antwort_s"]) and z["kennung"] == alt["kennung"]
    lauf = tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]
    assert (lauf["ergebnis"], lauf["netz"]) == ("ok", "0") and om.NUR_CACHE_VERMERK in lauf["parameter"]
    assert not (cache / "lauf_offen.json").exists()
    ergebnis = tmp_path / "ergebnisse" / "pdf_koepfe.tsv"
    # Abbruch im Cache-Modus (erste Datei fehlt kurz im Cache): pdf_koepfe.tsv bleibt unverändert, auch die Zeilen mit
    # HTTP 404 und „zu groß“; mit der Datei wieder im Cache gelingt die Neuauswertung wie zuvor
    stand = ergebnis.read_bytes()
    erste = next(p for z in nachher if z["quelle"] == "cache" for p in vorlagen if p["id"] == z["id"])
    pfad = om.abruf._cachepfad(om.datei_waehlen({**erste, "dateiliste": om._dateiliste(erste)})[0],
                               ".pdf").relative_to(om.abruf.CACHE)
    pdf = cache / pfad
    beiseite = pdf.with_name("beiseite")
    pdf.rename(beiseite)
    r = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "4"], capture_output=True, text=True,
                       timeout=120, env=ohne_netz)
    assert r.returncode == 2 and tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]["ergebnis"] == "abbruch (cache)"
    assert ergebnis.read_bytes() == stand and "bleibt unverändert" in r.stderr
    beiseite.rename(pdf)
    r = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "4"], capture_output=True, text=True,
                       timeout=120, env=ohne_netz)
    assert r.returncode == 0, r.stderr
    assert [(z["treffer"], z["bytes"]) for z in tsv(ergebnis)] == [(z["treffer"], z["bytes"]) for z in vorher]
    # frühere Zeile mit anderer Datei (`datei`): keine Übernahme, Abbruch der Art `cache`
    with ergebnis.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, om.PDF_SPALTEN, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows({**z, "datei": "auxiliaryFile 9 von 9"} if z["treffer"] in ("fehler: HTTP 404", "zu groß") else z
                    for z in vorher)
    r = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "4"], capture_output=True, text=True,
                       timeout=120, env=ohne_netz)
    assert r.returncode == 2 and tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]["ergebnis"] == "abbruch (cache)"
    assert len(stadt.anfragen) == 4
    # fehlt ein Eintrag ohne passende frühere Zeile: Abbruch der Art `cache`, keine Anfrage
    for pfad in (cache / "roh").glob("*.pdf"):
        pfad.unlink()
    (tmp_path / "ergebnisse" / "pdf_koepfe.tsv").unlink()
    r = subprocess.run([sys.executable, skript, "pdf-koepfe", "--anzahl", "4"], capture_output=True, text=True,
                       timeout=120, env=ohne_netz)
    assert r.returncode == 2 and "abbruch (cache)" == tsv(tmp_path / "ergebnisse" / "oparl_laeufe.tsv")[-1]["ergebnis"]
    assert "keine Anfrage" in r.stderr


def test_nachtrag_5_nur_cache_nur_fuer_pdf_koepfe(tmp_path):
    """Der reine Cache-Modus gilt nur für pdf-koepfe: jedes andere Kommando endet vor dem Lauf (kein Eintrag in
    oparl_laeufe.tsv), sonst machte ein Lauf ohne Freigabe aus einem abgebrochenen Lauf der Stufe 5 „Regel erfüllt“."""
    om = importlib.import_module("oparl_messung")
    env = {**os.environ, "RATSATLAS_NUR_CACHE": "ja", "RATSATLAS_CACHE": str(tmp_path / "cache"),
           "RATSATLAS_ERGEBNISSE": str(tmp_path / "ergebnisse"), "RATSATLAS_SPERRE": str(tmp_path / "sperre")}
    for kommando in om.KOMMANDOS:
        if kommando == "pdf-koepfe":
            continue
        r = subprocess.run([sys.executable, str(EXPLORE / "oparl_messung.py"), kommando], capture_output=True,
                           text=True, timeout=60, env=env)
        assert r.returncode == 2 and "nur für pdf-koepfe" in r.stderr, (kommando, r.stderr)
    assert not (tmp_path / "ergebnisse" / "oparl_laeufe.tsv").exists() and not (tmp_path / "cache").exists()


def test_nachtrag_5_befehl_zur_neuauswertung_in_stufen_md():
    """STUFEN.md und README.md: genau ein Befehl „Stufe 6 neu auswerten ohne Netz“, mit RATSATLAS_NUR_CACHE=ja und ohne
    Freigaben (er stellt keine Anfrage); die Anfragezahlen der Stufen bleiben unverändert."""
    text = (EXPLORE / "STUFEN.md").read_text(encoding="utf-8")
    befehle = [z for z in text.splitlines() if z.startswith(NUR_CACHE_BEFEHL)]
    assert befehle == ["RATSATLAS_NUR_CACHE=ja RATSATLAS_STUFE=6 python3 explore/oparl_messung.py pdf-koepfe --anzahl 100"]
    assert "Stufe 6 neu auswerten ohne Netz" in text
    assert "RATSATLAS_NUR_CACHE" in (EXPLORE / "README.md").read_text(encoding="utf-8")
    for verboten in ("FREIGEGEBEN", "MAX_ANFRAGEN", "NACH_ABBRUCH", "ZEITFENSTER"):
        assert verboten not in befehle[0]


# --- Stufe 6: Nummer erkannt, Stelle mehrdeutig (CLAUDE.md 9, 13.11.2026); erfundene Kennungen und Namen ---
AT = "http://oparl.example.invalid/oparl/bodies/0001/organizations/at"
AEMTER_MEHRDEUTIG = [(f"{AT}/1", "[Testdaten] Ressort 903 - Erste Stelle "), (f"{AT}/2", "[Testdaten] Ressort 903 - "
                     "Zweite Stelle "), (f"{AT}/3", "[Testdaten] Ressort 904 - Einzige Stelle "),
                     (f"{AT}/4", "[Testdaten] Ressort 903.1 - Teilstelle "),
                     (f"{AT}/5", "[Testdaten] Ressort 905 R 905")]


def _pdf_tsv(pfad, zeilen, spalten):
    with open(pfad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, spalten, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(zeilen)


def test_pdf_stelle_mehrdeutig_ohne_wahl():
    """Abgleich: Eine Nummer, die zu mehreren at-Organisationen passt, ergibt „mehrdeutig (n)“, `stellen` nennt alle
    passenden Kennungen in der Reihenfolge der Ämterliste, keine wird gewählt; Teilnummern (903.1) zählen nicht.
    Gegenprobe: eine Nummer mit genau einer Organisation (auch über Name und Kurzname derselben) ist eindeutig."""
    pytest.importorskip("pypdf")
    om = importlib.import_module("oparl_messung")
    aw = importlib.import_module("auswertung")
    assert om.amt_kandidaten("903", AEMTER_MEHRDEUTIG) == [f"{AT}/1", f"{AT}/2"]
    assert om.amt_kandidaten("903", None) == om.amt_kandidaten("903", []) == []
    assert om.amt_abgleichen("903", AEMTER_MEHRDEUTIG) == "mehrdeutig (2)"
    assert om.amt_abgleichen("904", AEMTER_MEHRDEUTIG) == f"{AT}/3"           # Gegenprobe: eindeutig
    assert om.amt_abgleichen("905", AEMTER_MEHRDEUTIG) == f"{AT}/5"           # Name und Kurzname derselben Stelle
    assert om.amt_abgleichen("906", AEMTER_MEHRDEUTIG) == "kein Treffer in organizations/at"
    kopf = ["[Testdaten] Stadt Beispiel", "Ressort {}", "Beschlussvorschlag", "[Testdaten] Text"]
    mehr = om.pdf_auswerten(testserver.pdf([[z.format(903) for z in kopf]]), AEMTER_MEHRDEUTIG)
    assert (mehr["treffer"], mehr["kennung"], mehr["abgleich"]) == ("kennung", "Ressort 903", "mehrdeutig (2)")
    assert mehr["stellen"] == f"{AT}/1; {AT}/2" and aw.stelle_kategorie(mehr) == aw.STELLE_MEHRDEUTIG
    eins = om.pdf_auswerten(testserver.pdf([[z.format(904) for z in kopf]]), AEMTER_MEHRDEUTIG)
    assert (eins["abgleich"], eins.get("stellen", "")) == (f"{AT}/3", "")
    assert aw.stelle_kategorie(eins) == aw.STELLE_EINDEUTIG
    # ohne Ämterliste: Nummer erkannt, aber kein Abgleich (keine Stelle, keine Wahl)
    ohne = om.pdf_auswerten(testserver.pdf([[z.format(903) for z in kopf]]), None)
    assert ohne.get("stellen", "") == "" and aw.stelle_kategorie(ohne) == aw.STELLE_LISTE_FEHLT
    _ohne_pdf_inhalt(*(str(v) for v in (*mehr.values(), *eins.values())))


def test_pdf_stelle_kategorien_aus_treffer_und_abgleich():
    """Jede Zeile aus pdf_koepfe.tsv erhält genau eine Kategorie, auch ohne Spalte `stelle` (ältere Tabelle)."""
    aw = importlib.import_module("auswertung")
    faelle = [({"treffer": "kennung", "abgleich": f"{AT}/3"}, aw.STELLE_EINDEUTIG),
              ({"treffer": "kennung", "abgleich": "mehrdeutig (3)"}, aw.STELLE_MEHRDEUTIG),
              ({"treffer": "kennung", "abgleich": "kein Treffer in organizations/at"}, aw.STELLE_OHNE),
              ({"treffer": "kennung", "abgleich": "Ämterliste fehlt (zuerst organisationen)"}, aw.STELLE_LISTE_FEHLT),
              ({"treffer": "kennung", "abgleich": "Ämterliste leer (keine Organisation mit Präfix at erfasst)"},
               aw.STELLE_LISTE_FEHLT),
              ({"treffer": "kennung"}, aw.STELLE_UNBEKANNT),
              ({"treffer": "nein"}, aw.NICHT_IM_KOPF), ({"treffer": "nur außerhalb des Kopfes"}, aw.NICHT_IM_KOPF),
              ({"treffer": "kein_text"}, aw.OHNE_TEXTEBENE)]
    faelle += [({"treffer": t}, aw.NICHT_GELESEN) for t in (
        "fehler: HTTP 404", "fehler: HTTP 410", "zu groß", "kein PDF", "verschlüsselt", "fehler: PdfReadError",
        "abbruch (langsam)", "nicht abgerufen", "")]
    for zeile, kategorie in faelle:
        assert aw.stelle_kategorie(zeile) == kategorie, zeile
    assert {k for _, k in faelle} == set(aw.STELLEN) and len(aw.STELLEN) == len(set(aw.STELLEN))
    # Gegenprobe: „mehrdeutig“ ohne Kennung im Kopf ist keine Stelle (nur Zeilen mit Treffer `kennung` zählen)
    assert aw.stelle_kategorie({"treffer": "nein", "abgleich": "mehrdeutig (2)"}) == aw.NICHT_IM_KOPF


def test_pdf_auswertung_eindeutig_und_mehrdeutig_getrennt(tmp_path):
    """Zählung und Abschnitt Stufe 6 mit erfundenen Zeilen: 40 eindeutig, 12 mehrdeutig (903 zu 2, 901 zu 3
    Organisationen), 5 ohne Stelle, 33 ohne Nummer im Kopf, 10 HTTP 404. Die drei Teile ergeben zusammen die
    Erkennung (57); mehrdeutige zählen nicht als zugeordnet. Gegenprobe ohne mehrdeutige Zeilen."""
    aw = importlib.import_module("auswertung")
    om = importlib.import_module("oparl_messung")
    zeilen = ([{"treffer": "kennung", "kennung": "Ressort 904", "abgleich": f"{AT}/3", "jahr": "2026"}] * 40
              + [{"treffer": "kennung", "kennung": "Ressort 903", "abgleich": "mehrdeutig (2)", "jahr": "2025",
                  "stellen": f"{AT}/1; {AT}/2"}] * 9
              + [{"treffer": "kennung", "kennung": "Amt 901", "abgleich": "mehrdeutig (3)", "jahr": "2024"}] * 3
              + [{"treffer": "kennung", "kennung": "Stadtbetrieb 999", "abgleich": "kein Treffer in organizations/at",
                  "jahr": "2023"}] * 5
              + [{"treffer": "nein", "jahr": "2022"}] * 33 + [{"treffer": "fehler: HTTP 404", "jahr": "2021"}] * 10)
    zz = aw.pdf_zaehlung(zeilen)
    assert [len(zz[k]) for k in ("versucht", "abgerufen", "kennung", "abgeglichen", "mehrdeutig", "ohne_stelle")] == [
        100, 90, 57, 40, 12, 5]
    assert len(zz["abgeglichen"]) + len(zz["mehrdeutig"]) + len(zz["ohne_stelle"]) == len(zz["kennung"])
    assert not any("/organizations/at/" in z["abgleich"] for z in zz["mehrdeutig"])   # keine Stelle gewählt
    erg = tmp_path / "ergebnisse"
    erg.mkdir()
    _pdf_tsv(erg / "pdf_koepfe.tsv", zeilen, om.PDF_SPALTEN)
    _pdf_tsv(erg / "pdf_koepfe_grundlage.tsv", [
        {"feld": f, "wert": w} for f, w in (("stichprobe_vorlagen", "800"), ("mit_underDirectionOf", "600"),
                                            ("verwaltung_ohne_underDirectionOf_mit_datei", "100"),
                                            ("aemterliste", "5"))], ["feld", "wert"])
    aus = "\n".join(aw.pdf_abschnitt(erg, []))
    assert ("Erkennungsquote getrennt nach Stelle (/ abgerufen; Stelle mehrdeutig: Nummer passt zu mehreren "
            "Organisationen aus organizations/at, keine wird gewählt): Stelle eindeutig 40 von 90 (44 %; Wilson 95 % "
            in aus)
    assert "; Stelle mehrdeutig 12 von 90 (13 %; " in aus
    assert "; keine Stelle in organizations/at 5 von 90 (6 %; " in aus
    assert (f"Ergebnis je Datei (Spalte stelle, alle ausgewählten): {aw.STELLE_EINDEUTIG} 40, "
            f"{aw.STELLE_MEHRDEUTIG} 12, "
            f"{aw.STELLE_OHNE} 5, {aw.NICHT_IM_KOPF} 33, {aw.NICHT_GELESEN} 10") in aus
    assert ("Nummern mit mehrdeutiger Stelle (Nummer: Dateien, Organisationen mit dieser Nummer laut Abgleich): "
            "901: 3 Dateien, 3 Organisationen, 903: 9 Dateien, 2 Organisationen") in aus
    # bestehende Quoten unverändert: Erkennung 57, zugeordnet nur die eindeutigen 40
    assert "abgerufen): 57 von 90 (" in aus and "/ Kennung erkannt): 40 von 57 (" in aus
    assert "(einer Organisation aus organizations/at zugeordnet, 40 von 100 angefragten Dateien, " in aus
    assert "- Nummer erkannt, Stelle mehrdeutig: 12 von 100 (12 %; " in aus and "keine automatische Wahl" in aus
    # Gegenprobe: ohne mehrdeutige Zeilen 0 und „–“; die ältere Tabelle ohne Spalten stelle/stellen genügt
    ohne = [z for z in zeilen if z.get("abgleich", "").startswith("mehrdeutig") is False]
    _pdf_tsv(erg / "pdf_koepfe.tsv", ohne, [s for s in om.PDF_SPALTEN if s not in ("stelle", "stellen")])
    aus = "\n".join(aw.pdf_abschnitt(erg, []))
    assert "; Stelle mehrdeutig 0 von 78" in aus and "Stelle eindeutig 40 von 78 (" in aus
    assert "Organisationen mit dieser Nummer laut Abgleich): –" in aus and aw.STELLE_MEHRDEUTIG not in aus.split(
        "Ergebnis je Datei")[1].split("\n")[0]


def test_pdf_koepfe_stelle_mehrdeutig_ohne_weitere_anfrage(server, tmp_path):
    """pdf-koepfe gegen den lokalen Testserver: Spalte `stelle` je Zeile, mit eindeutiger Ämterliste keine mehrdeutige
    Stelle (Gegenprobe). Danach eine erfundene zweite Organisation mit derselben Nummer in der Ämterliste: Neuauswertung
    aus dem Cache ohne Anfrage, betroffene Zeilen als „Nummer erkannt, Stelle mehrdeutig“ mit beiden Kennungen in
    `stellen`, alle übrigen Spalten der Erkennung unverändert; Zahl der Anfragen bleibt 100."""
    pytest.importorskip("pypdf")
    aw = importlib.import_module("auswertung")
    _bis_stichprobe(server, tmp_path)
    vorher = len(server.anfragen)
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "100", obergrenze=100)
    assert m["rc"] == 0 and m["server"] == 100 and len(server.anfragen) - vorher == 100, m["stderr"]
    erg = tmp_path / "ergebnisse"
    erste = tsv(erg / "pdf_koepfe.tsv")
    assert all(z["stelle"] == aw.stelle_kategorie(z) for z in erste)
    assert aw.STELLE_MEHRDEUTIG not in {z["stelle"] for z in erste} and {z["stellen"] for z in erste} == {""}
    assert {aw.STELLE_EINDEUTIG, aw.STELLE_OHNE, aw.NICHT_IM_KOPF, aw.OHNE_TEXTEBENE} <= {z["stelle"] for z in erste}
    assert "Stelle: {" in m["stdout"]
    # erfundene zweite Organisation mit der häufigsten Nummer unter den eindeutig zugeordneten Kennungen
    nummer = collections.Counter(z["kennung"].split()[-1] for z in erste
                                 if z["stelle"] == aw.STELLE_EINDEUTIG).most_common(1)[0][0]
    orgs = tsv(erg / "oparl_organisationen.tsv")
    original = [o for o in orgs if o["praefix"] == "at" and re.search(rf"\b{nummer}\b", o["name"])]
    assert len(original) == 1
    zweite = {**original[0], "id": f"{server.body_url}/organizations/at/9999",
              "name": f"[Testdaten] Ressort {nummer} Zweite Stelle", "kurz": ""}
    _pdf_tsv(erg / "oparl_organisationen.tsv", orgs + [zweite], list(orgs[0]))
    vorher = len(server.anfragen)
    m = lauf(server, tmp_path, "pdf-koepfe", "--anzahl", "100", obergrenze=1)
    assert (m["rc"], m["server"], m["lauf"]["cache"], len(server.anfragen) - vorher) == (0, 0, "100", 0), m["stderr"]
    zweiter = tsv(erg / "pdf_koepfe.tsv")
    betroffen = [z for z in zweiter if z["treffer"] == "kennung" and z["kennung"].split()[-1] == nummer]
    assert betroffen and all(z["stelle"] == aw.STELLE_MEHRDEUTIG and z["abgleich"] == "mehrdeutig (2)"
                             and z["stellen"] == f"{original[0]['id']}; {zweite['id']}" for z in betroffen)
    erkennung = ("id", "treffer", "kennung", "lage", "regel", "fundstelle")
    assert [tuple(z[s] for s in erkennung) for z in zweiter] == [tuple(z[s] for s in erkennung) for z in erste]
    ids = {z["id"] for z in betroffen}
    # nicht betroffene Zeilen: alle Spalten gleich bis auf Quelle und Antwortzeit (erster Lauf netz, zweiter cache)
    ohne_abruf = [s for s in erste[0] if s not in ("quelle", "antwort_s")]
    paare = [(z, e) for z, e in zip(zweiter, erste) if z["id"] not in ids]
    assert len(zweiter) == len(erste) and paare
    assert {z["quelle"] for z, _ in paare} == {"cache"} and {e["quelle"] for _, e in paare} == {"netz"}
    assert all({s: z[s] for s in ohne_abruf} == {s: e[s] for s in ohne_abruf} for z, e in paare)
    aus = aw.auswertung(tmp_path / "cache", erg)
    k = len(betroffen)
    assert f"; Stelle mehrdeutig {k} von 100 (" in aus and f"{nummer}: {k} Dateien, 2 Organisationen" in aus
    _ohne_pdf_inhalt(m["stdout"], m["stderr"], (erg / "pdf_koepfe.tsv").read_text(encoding="utf-8"))
