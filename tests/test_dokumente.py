"""Anlagen der Vorlagen (pipeline/dokumente.py, Entscheidung 13.11.2026 zum Download der Ratsdokumente) gegen den lokalen
Testserver (tests/oparl_testserver.py) mit erfundenen PDF-Dateien, die zur Laufzeit entstehen; keine Anfrage an die
Stadt, keine PDF-Datei im Repository.
- Text extrahiert und komprimiert gespeichert, PDF gelöscht; Fingerabdruck im Zustand, unveränderte Dateien ohne
  Anfrage übersprungen, geänderte neu geladen (Zusammenspiel mit pipeline/aenderungen.py)
- Fortsetzen nach Abbruch und Neustart, Aufräumen verwaister Texte und halber PDFs
- Rate tagsüber 5 s, nachts 2 s (Scheinuhr), Vorrang des OParl-Abrufs, Freigaben, 12-Stunden-Regel
- Abbruchfälle (401/403, 429/5xx, HTML statt PDF, abgeschnitten, Weiterleitung, 404 in Folge), Größenlimit,
  Obergrenzen je Lauf, Plattenplatz
- keine Dateinamen, Personennamen oder Texte in Protokollen und Ausgaben"""
import csv
import gzip
import json
import shutil
import subprocess
import types
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import threading

import pytest

from conftest import _Waechter
from oparl_testserver import Daten, _Handler, pdf_erzeugen, pfade_umlenken
from pipeline import abruf, aenderungen, config, dokumente, sessionnet

pytest.importorskip("pypdf")

# 12:00 Uhr Ortszeit (Europe/Berlin, MEZ): tagsüber, außerhalb des OParl-Zeitfensters 23–1 Uhr
MITTAG = datetime(2026, 11, 16, 11, 0, tzinfo=timezone.utc)
NACHTS = datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc)        # 03:00 Uhr Ortszeit
OPARL_FENSTER = datetime(2026, 11, 16, 22, 30, tzinfo=timezone.utc)   # 23:30 Uhr Ortszeit
MARKE = "Testinhalt Zebrafink 4711"            # erfundener Text im PDF; darf nur im Textordner stehen
NAME = "Anregung Erika Musterfrau"             # erfundener Personenname im Dateinamen; darf nirgends stehen


def _rohdaten(d):
    config.RAW.mkdir(parents=True, exist_ok=True)
    config.PAPERS.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in d.papers), encoding="utf-8")


def _tsv(pfad):
    with open(pfad, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def _protokoll():
    return _tsv(config.DOKUMENTE_PROTOKOLL) if config.DOKUMENTE_PROTOKOLL.exists() else []


def _statistik():
    return _tsv(config.DOKUMENTE_STATISTIK)


def _zustand():
    return json.loads(config.DOKUMENTE_ZUSTAND.read_text(encoding="utf-8"))


def _downloads(d):
    return [p for p, _, _ in d.anfragen if p.startswith("/downloadfiles/")]


def _anlagen(d, n=3):
    """n Vorlagen mit je einer Anlage (Datei i an Vorlage i), Text „Seite i“."""
    for i in range(1, n + 1):
        d.anlage(d.papers[i - 1], i, pdf_erzeugen([f"Vorlage {i} Seite eins", "Seite zwei"]))
    _rohdaten(d)


def _text(d, n):
    return dokumente.text(f"{d.b}/files/{n}")


# --- Grundablauf ------------------------------------------------------------------------------------------------------

def test_text_gespeichert_pdf_geloescht_fingerabdruck_im_zustand(oparl):
    _anlagen(oparl)
    dokumente.holen()
    assert sorted(_downloads(oparl)) == ["/downloadfiles/1.pdf", "/downloadfiles/2.pdf", "/downloadfiles/3.pdf"]
    assert _text(oparl, 1) == "Vorlage 1 Seite eins\fSeite zwei\f"
    dateien = sorted(p.name for p in config.TEXTE_ORDNER.rglob("*"))
    assert dateien == sorted(f"{dokumente.schluessel(f'{oparl.b}/files/{i}')}.txt.gz" for i in (1, 2, 3))
    assert not list(config.RAW.parent.rglob("*.pdf")), "PDF nicht gelöscht"
    with gzip.open(dokumente.textpfad(dokumente.schluessel(f"{oparl.b}/files/2")), "rt", encoding="utf-8") as f:
        assert "Vorlage 2" in f.read()
    e = _zustand()["dateien"][f"{oparl.b}/files/1"]
    assert e["status"] == "geladen" and e["seiten"] == 2 and e["groesse"] == oparl.papers[0]["auxiliaryFile"][0]["size"]
    assert len(e["sha256"]) == 64 and e["quelle"] == dokumente.quelle_fingerabdruck(oparl.papers[0]["auxiliaryFile"][0])
    assert e["vorlage"] == f"{oparl.b}/papers/1" and "modified" in e
    zeilen = _protokoll()
    assert [z["ergebnis"] for z in zeilen] == ["geladen"] * 3
    assert all(z["inhalt"] == "neu" and z["pruefung"] == "passt" and z["http"] == "200" for z in zeilen)
    s = _statistik()[-1]
    assert (s["ende"], s["dateien"], s["zu_laden"], s["geladen"], s["anfragen"]) == ("ok", "3", "3", "3", "3")
    assert [t[1] for t in dokumente.texte()] == sorted(f"{oparl.b}/files/{i}" for i in (1, 2, 3))


def test_pdf_sofort_nach_der_extraktion_geloescht(oparl, monkeypatch):
    """Wenn die Zeile einer Datei ins Protokoll geht, ist ihr PDF schon gelöscht (nicht erst am Ende des Laufs)."""
    _anlagen(oparl)
    gesehen = []
    alt = dokumente._protokoll

    def protokoll(zeile):
        gesehen.append(sorted(p.name for p in config.TEXTE_ORDNER.rglob("*.pdf")))
        alt(zeile)
    monkeypatch.setattr(dokumente, "_protokoll", protokoll)
    dokumente.holen()
    assert gesehen == [[], [], []]


def test_unveraenderte_dateien_ohne_anfrage(oparl):
    _anlagen(oparl)
    dokumente.holen()
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == []
    s = _statistik()[-1]
    assert (s["zu_laden"], s["unveraendert"], s["anfragen"]) == ("0", "3", "0")


def test_geaenderte_quelle_neu_geladen_umbenennung_nicht(oparl):
    """Zusammenspiel mit pipeline/aenderungen.py: dieselbe Änderung, die das Änderungsprotokoll als
    auxiliaryFile.angaben vermerkt (Größe, modified), lädt neu; eine bloße Umbenennung (dort nur als Namensänderung
    vermerkt) lädt nicht neu."""
    _anlagen(oparl)
    aenderungen.protokollieren()
    dokumente.holen()
    neu = pdf_erzeugen(["Vorlage 1 ersetzt", "Seite zwei"])
    f1, f2 = oparl.papers[0]["auxiliaryFile"][0], oparl.papers[1]["auxiliaryFile"][0]
    f1.update(size=len(neu), modified="2026-11-20T10:00:00+01:00")
    oparl.datei_setzen(1, neu)
    f2["name"] = f2["fileName"] = "umbenannt (erfunden)"
    _rohdaten(oparl)
    aenderungen.protokollieren()
    felder = {(z["quellobjekt"], z["feld"]) for z in _tsv(config.AENDERUNGEN)}
    assert (f"{oparl.b}/papers/1", "auxiliaryFile.angaben") in felder
    assert (f"{oparl.b}/papers/2", "auxiliaryFile.angaben") in felder   # Name geändert (nicht protokolliert)
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/1.pdf"]
    assert _text(oparl, 1).startswith("Vorlage 1 ersetzt")
    assert _protokoll()[-1]["inhalt"] == "geaendert"


def test_gleicher_inhalt_bei_geaenderten_angaben(oparl):
    _anlagen(oparl, 1)
    dokumente.holen()
    oparl.papers[0]["auxiliaryFile"][0]["modified"] = "2026-11-20T10:00:00+01:00"
    _rohdaten(oparl)
    dokumente.holen()
    assert _protokoll()[-1]["inhalt"] == "gleich"


def test_fehlender_text_wird_neu_geladen(oparl):
    _anlagen(oparl)
    dokumente.holen()
    dokumente.textpfad(dokumente.schluessel(f"{oparl.b}/files/2")).unlink()
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/2.pdf"]


def test_verwaiste_texte_entfernt_und_schutz_bei_unvollstaendigen_rohdaten(oparl):
    """30 Dateien; 3 fallen weg (90 % bleiben, fetch.MIN_ANTEIL): Text und Eintrag gelöscht. Fehlen danach 10 von 27,
    gelten die Rohdaten als unvollständig: nichts gelöscht."""
    verteilung = {0: 10, 1: 10, 2: 1, 3: 1, 4: 8}
    n = 0
    for i, anzahl in verteilung.items():
        for _ in range(anzahl):
            n += 1
            oparl.anlage(oparl.papers[i], n, pdf_erzeugen([f"Datei {n}"]))
    _rohdaten(oparl)
    dokumente.holen()
    assert len(_zustand()["dateien"]) == 30
    weg = [oparl.papers[4]["auxiliaryFile"].pop()["id"], oparl.papers[3]["auxiliaryFile"][0]["id"],
           oparl.papers[2]["auxiliaryFile"][0]["id"]]
    oparl.papers[3]["auxiliaryFile"][0]["deleted"] = True                       # Datei gelöscht
    oparl.papers[2]["date"], oparl.papers[2]["created"] = "2019-12-31", "2019-12-30T10:00:00+01:00"   # vor 2020
    _rohdaten(oparl)
    dokumente.holen()
    z = _zustand()["dateien"]
    assert len(z) == 27 and not set(weg) & set(z) and _statistik()[-1]["entfernt"] == "3"
    assert len(list(config.TEXTE_ORDNER.glob("*.txt.gz"))) == 27
    assert all(dokumente.text(k) is None for k in weg)
    oparl.papers[0]["auxiliaryFile"] = []   # 10 von 27 fehlen: Rohdaten unvollständig?
    _rohdaten(oparl)
    dokumente.holen()
    assert len(_zustand()["dateien"]) == 27 and len(list(config.TEXTE_ORDNER.glob("*.txt.gz"))) == 27


def test_halbes_pdf_und_temporaere_dateien_nach_neustart_entfernt(oparl):
    _anlagen(oparl, 1)
    dokumente.holen()
    arbeit = config.TEXTE_ORDNER / dokumente.ARBEIT
    arbeit.mkdir()
    (arbeit / "datei.pdf").write_bytes(b"%PDF-1.4 halb")
    (config.TEXTE_ORDNER / "x.txt.gz.tmp").write_bytes(b"halb")
    dokumente.holen()
    assert not arbeit.exists() and not list(config.TEXTE_ORDNER.glob("*.tmp"))


def test_fortsetzen_nach_abbruch(oparl, monkeypatch):
    monkeypatch.setattr(config, "ABRUF_PAUSEN", [0, 0])
    _anlagen(oparl)   # Reihenfolge: Vorlage 3, 2, 1 (neueste zuerst nach date, dann created)
    oparl.datei_setzen(2, (503, {"Content-Type": "text/plain"}, b""))
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/3.pdf"] + ["/downloadfiles/2.pdf"] * 3   # zwei Pausen
    assert _zustand()["letzter_abbruch"]["art"] == "aufgegeben" and _statistik()[-1]["ende"] == "aufgegeben"
    assert _text(oparl, 3) and not _text(oparl, 2)
    oparl.datei_setzen(2, pdf_erzeugen(["Vorlage 2 Seite eins"]))
    oparl.anfragen.clear()
    dokumente.holen()   # lokal: keine 12-Stunden-Regel
    assert _downloads(oparl) == ["/downloadfiles/2.pdf", "/downloadfiles/1.pdf"]
    assert "letzter_abbruch" not in _zustand()


def test_ohne_rohdaten_keine_anfrage(oparl):
    dokumente.holen()
    assert oparl.anfragen == [] and not config.DOKUMENTE_STATISTIK.exists()


# --- Dateiarten und Größen --------------------------------------------------------------------------------------------

def test_ohne_text_kein_pdf_und_unlesbares_pdf(oparl):
    p = oparl.papers
    oparl.anlage(p[0], 1, pdf_erzeugen([""]))
    oparl.anlage(p[1], 2, b"PK\x03\x04" + b"\0" * 2000)
    oparl.datei_setzen(2, (200, {"Content-Type": "application/zip"}, b"PK\x03\x04" + b"\0" * 2000))
    oparl.anlage(p[2], 3, b"%PDF-1.4\n" + b"kaputt " * 300)
    oparl.anlage(p[3], 4, pdf_erzeugen(["lesbar"]))
    _rohdaten(oparl)
    dokumente.holen()
    status = {k.rsplit("/", 1)[1]: e["status"] for k, e in _zustand()["dateien"].items()}
    assert status == {"1": "ohne_text", "2": "kein_pdf", "3": "extraktion_fehler", "4": "geladen"}
    assert not list(config.RAW.parent.rglob("*.pdf"))
    assert {z["ergebnis"]: z["meldung"] for z in _protokoll()}["kein_pdf"] == "application/zip"
    oparl.anfragen.clear()
    dokumente.holen()   # ohne geänderte Quelle kein neuer Versuch
    assert _downloads(oparl) == []


def test_groessenlimit(oparl, monkeypatch):
    monkeypatch.setattr(config, "DOKUMENTE_MAX_DATEI_BYTES", 2000)
    monkeypatch.setattr(config, "DOKUMENTE_MIN_FREI", 4000)
    gross = pdf_erzeugen(["x" * 3000])
    p = oparl.papers
    oparl.anlage(p[0], 1, gross)                                              # laut size: ohne Anfrage
    oparl.anlage(p[1], 2, gross, size=None)                                   # laut Content-Length: nur der Kopf
    oparl.anlage(p[2], 3, (200, {"Content-Type": "application/pdf", "Content-Length": None}, gross), size=None)
    oparl.anlage(p[3], 4, pdf_erzeugen(["klein"]))
    for f in (p[1], p[2]):
        f["auxiliaryFile"][0].pop("size")
    _rohdaten(oparl)
    dokumente.holen()
    assert sorted(_downloads(oparl)) == ["/downloadfiles/2.pdf", "/downloadfiles/3.pdf", "/downloadfiles/4.pdf"]
    zeilen = {z["datei"].rsplit("/", 1)[1]: z for z in _protokoll()}
    assert {k: z["ergebnis"] for k, z in zeilen.items()} == {"1": "zu_gross", "2": "zu_gross", "3": "zu_gross",
                                                             "4": "geladen"}
    assert zeilen["1"]["bytes"] == "0" and zeilen["2"]["bytes"] == "0"
    assert 2000 < int(zeilen["3"]["bytes"]) <= 2000 + dokumente.STUECK
    assert not list(config.RAW.parent.rglob("*.pdf"))
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == []   # gleiches Limit: kein neuer Versuch
    monkeypatch.setattr(config, "DOKUMENTE_MAX_DATEI_BYTES", 10 ** 6)
    monkeypatch.setattr(config, "DOKUMENTE_MIN_FREI", 2 * 10 ** 6)
    dokumente.holen()   # höheres Limit: alle drei neu
    assert sorted(_downloads(oparl)) == ["/downloadfiles/1.pdf", "/downloadfiles/2.pdf", "/downloadfiles/3.pdf"]
    assert all(e["status"] == "geladen" for e in _zustand()["dateien"].values())


def test_fremder_host_und_verweis_ohne_anfrage(oparl):
    oparl.anlage(oparl.papers[0], 1, pdf_erzeugen(["a"]), downloadUrl="https://example.org/1.pdf",
                 accessUrl="https://example.org/a/1.pdf")
    oparl.papers[1]["auxiliaryFile"] = [f"{oparl.b}/files/9"]   # nur ein Verweis, keine Adresse
    _rohdaten(oparl)
    dokumente.holen()   # die Wächter-Hülle ließe eine Anfrage an example.org den Test scheitern
    assert _downloads(oparl) == []
    s = _statistik()[-1]
    assert (s["fremder_host"], s["ohne_adresse"], s["zu_laden"]) == ("1", "1", "0")
    assert _zustand()["dateien"][f"{oparl.b}/files/1"]["status"] == "fremder_host"


def test_anregungen_und_beschwerden_mit_verbundenen_vorlagen_ausgenommen(oparl):
    """§ 24 GO NRW (CLAUDE.md 2 Datenschutz, Entscheidung 13.11.2026): keine Anlagen von Vorlagen aus der Einwohnerschaft
    und den mit ihnen verbundenen Vorlagen laden; die übrigen Vorlagen bleiben unberührt (Gegenprobe)."""
    _anlagen(oparl, 3)
    a, b, c = oparl.papers[:3]
    a["paperType"] = "Anregungen und Beschwerden"                # Art aus maske.EINWOHNER
    b["superordinatedPaper"] = [a["id"]]                         # Stellungnahme dazu, ohne Art und ohne Wort im Titel
    _rohdaten(oparl)
    kennungen = {x["vorlage"] for x in dokumente.aufgaben(oparl.papers)[0]}
    assert kennungen == {c["id"]}
    assert dokumente.AUSGESCHLOSSEN == {a["id"], b["id"]}
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/3.pdf"]
    assert _text(oparl, 3) and not _text(oparl, 1) and not _text(oparl, 2)


def test_ohne_vorlage_aus_der_einwohnerschaft_nichts_ausgenommen(oparl):
    _anlagen(oparl, 3)
    assert len(dokumente.aufgaben(oparl.papers)[0]) == 3
    assert dokumente.AUSGESCHLOSSEN == set()


def test_download_url_vor_access_url(oparl):
    f = oparl.anlage(oparl.papers[0], 1, pdf_erzeugen(["a"]))
    assert dokumente.aufgaben(oparl.papers)[0][0]["url"] == f["downloadUrl"]
    del f["downloadUrl"]
    assert dokumente.aufgaben(oparl.papers)[0][0]["url"] == f["accessUrl"]
    # Hosts der Stadt: http:// wird vor dem Senden zu https:// (abruf.abrufadresse, ohne Anfrage geprüft)
    assert abruf.abrufadresse("http://oparl.wuppertal.de/oparl/downloadfiles/1.pdf").startswith("https://")


# --- Abbruchfälle ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("antwort, art, sperre", [
    ((400, {}, b""), "http", False),
    ((429, {}, b""), "aufgegeben", True),
    ((500, {}, b""), "aufgegeben", True),
    ((200, {"Content-Type": "application/pdf", "Content-Length": "99999"}, b"%PDF-1.4 kurz"), "sperre", True),
    ((302, {"Location": "/downloadfiles/Name_einer_Person.pdf"}, b""), "weiterleitung", True),
])
def test_abbruchfaelle(oparl, monkeypatch, antwort, art, sperre):
    monkeypatch.setattr(config, "ABRUF_PAUSEN", [0, 0])
    _anlagen(oparl)
    oparl.datei_setzen(2, antwort)
    dokumente.holen()
    erwartet = ["/downloadfiles/3.pdf"] + ["/downloadfiles/2.pdf"] * (3 if art == "aufgegeben" else 1)
    assert _downloads(oparl) == erwartet, "nach dem Abbruch keine weitere Datei"
    z = _zustand()
    assert z["letzter_abbruch"]["art"] == art and _statistik()[-1]["ende"] == art
    assert z["dateien"][f"{oparl.b}/files/3"]["status"] == "geladen" and f"{oparl.b}/files/2" not in z["dateien"]
    assert _protokoll()[-1]["ergebnis"] == f"abbruch ({art})"
    assert not list(config.RAW.parent.rglob("*.pdf"))
    oparl_zustand = json.loads(config.ZUSTAND.read_text()) if config.ZUSTAND.exists() else {}
    assert bool(oparl_zustand.get("sperre_verdacht")) is sperre
    if sperre:   # derselbe Server: auch der OParl-Abruf pausiert
        assert oparl_zustand["letzter_abbruch"]["meldung"].startswith("Dokumente:")
    assert "Name_einer_Person" not in config.DOKUMENTE_PROTOKOLL.read_text(encoding="utf-8")
    assert "Name_einer_Person" not in config.DOKUMENTE_ZUSTAND.read_text(encoding="utf-8")


ABGEWIESEN = [
    ((401, {}, b""), "verweigert", "http"),
    ((403, {}, b""), "verweigert", "http"),
    ((200, {"Content-Type": "text/html"}, b"<html><body>Zugriff verweigert</body></html>"), "html", "sperrseite"),
    ((200, {"Content-Type": "application/pdf"}, b"<!DOCTYPE html><html>" + b" " * 2000), "html", "sperrseite"),
    ((200, {"Content-Type": "text/plain"}, b"Zu viele Anfragen"), "kein_pdf", "sperrseite"),
    ((200, {"Content-Type": "application/json"}, b'{"error": "rate limit"}'), "kein_pdf", "sperrseite"),
    ((200, {"Content-Type": "application/octet-stream"}, b""), "kein_pdf", "sperrseite"),
]


@pytest.mark.parametrize("antwort, status, art", ABGEWIESEN)
def test_einzeln_abgewiesen_vermerkt_kein_abbruch(oparl, antwort, status, art):
    """Eine einzelne abgewiesene Datei (etwa eine nicht öffentliche Anlage) wird vermerkt; der Lauf geht weiter, kein
    Sperrverdacht. Neuer Versuch erst nach der Frist, dann am Ende der Reihenfolge."""
    _anlagen(oparl)
    oparl.datei_setzen(2, antwort)
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/3.pdf", "/downloadfiles/2.pdf", "/downloadfiles/1.pdf"]
    z = _zustand()
    e = z["dateien"][f"{oparl.b}/files/2"]
    assert e["status"] == status and dokumente.abgewiesen(e) and "serie" not in e
    assert "letzter_abbruch" not in z and not config.ZUSTAND.exists() and _statistik()[-1]["ende"] == "ok"
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == []   # Frist
    e["geprueft"] = (datetime.now(timezone.utc) - timedelta(days=config.DOKUMENTE_ABGEWIESEN_TAGE, hours=1)).isoformat()
    config.DOKUMENTE_ZUSTAND.write_text(json.dumps(z), encoding="utf-8")
    oparl.datei_setzen(2, pdf_erzeugen(["wieder da"]))
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/2.pdf"] and _zustand()["dateien"][f"{oparl.b}/files/2"]["status"] == \
        "geladen"


@pytest.mark.parametrize("antwort, status, art", ABGEWIESEN)
def test_zwei_in_folge_abgewiesen_abbruch_mit_sperrverdacht(oparl, monkeypatch, antwort, status, art):
    """Zwei neu abgewiesene Dateien in Folge: Abbruch als mögliche Sperre (auch im Zustand des OParl-Abrufs). Die beiden
    werden im nächsten Lauf am Ende erneut angefragt; weisen sie dann wieder ab, während andere Dateien laden, zählen
    sie nicht als Serie (kein dauerhafter Stillstand an denselben Dateien)."""
    _anlagen(oparl, 4)
    oparl.datei_setzen(4, antwort)
    oparl.datei_setzen(3, antwort)
    dokumente.holen()
    assert _downloads(oparl) == ["/downloadfiles/4.pdf", "/downloadfiles/3.pdf"]
    z = _zustand()
    assert z["letzter_abbruch"]["art"] == art and _statistik()[-1]["ende"] == art
    assert all(z["dateien"][f"{oparl.b}/files/{i}"]["serie"] for i in (4, 3))
    oparl_zustand = json.loads(config.ZUSTAND.read_text())
    assert oparl_zustand["sperre_verdacht"]["naechte"] == 1
    oparl.anfragen.clear()
    dokumente.holen()   # lokal: keine 12-Stunden-Regel; neue Dateien zuerst, die Serie am Ende
    assert _downloads(oparl) == ["/downloadfiles/2.pdf", "/downloadfiles/1.pdf", "/downloadfiles/4.pdf",
                                 "/downloadfiles/3.pdf"]
    z = _zustand()
    assert _statistik()[-1]["ende"] == "ok" and "letzter_abbruch" not in z
    assert all(z["dateien"][f"{oparl.b}/files/{i}"]["status"] == status and "serie" not in
               z["dateien"][f"{oparl.b}/files/{i}"] for i in (4, 3))
    assert json.loads(config.ZUSTAND.read_text())["sperre_verdacht"]["naechte"] == 1   # nicht weiter gezählt
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == []   # Frist


def test_kein_pdf_in_folge_ohne_verdacht_endgueltig(oparl):
    """Andere Dateiarten (Word, Tabellen) sind keine Abweisung: kein Abbruch auch in Folge, kein neuer Versuch."""
    for i in range(1, 4):
        oparl.anlage(oparl.papers[i - 1], i, b"PK\x03\x04" + b"\0" * 2000)
        oparl.datei_setzen(i, (200, {"Content-Type": "application/vnd.openxmlformats-officedocument."
                                     "wordprocessingml.document"}, b"PK\x03\x04" + b"\0" * 2000))
    _rohdaten(oparl)
    dokumente.holen()
    assert len(_downloads(oparl)) == 3 and _statistik()[-1]["ende"] == "ok"
    assert {e["status"] for e in _zustand()["dateien"].values()} == {"kein_pdf"}
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == []


def test_medientyp_ohne_parameter_im_protokoll(oparl):
    """Parameter des Content-Type (name="…" mit Dateinamen) gelangen nicht ins Protokoll."""
    oparl.anlage(oparl.papers[0], 1, b"\xd0\xcf\x11\xe0" + b"\0" * 2000)
    oparl.datei_setzen(1, (200, {"Content-Type": f'application/msword; name="{NAME}.doc"'},
                           b"\xd0\xcf\x11\xe0" + b"\0" * 2000))
    _rohdaten(oparl)
    dokumente.holen()
    assert _protokoll()[-1]["meldung"] == "application/msword"
    for pfad in (config.DOKUMENTE_PROTOKOLL, config.DOKUMENTE_ZUSTAND, config.DOKUMENTE_STATISTIK):
        assert NAME not in pfad.read_text(encoding="utf-8")


def test_lokaler_dateifehler_ist_keine_sperre(oparl, monkeypatch, tmp_path):
    """Ein Fehler beim Schreiben des PDFs (fehlender Ordner, Platte voll) ist keine Antwort der Stadt: Art `lokal` bzw.
    `platz`, kein Sperrverdacht, kein lokaler Pfad in der Meldung."""
    _anlagen(oparl, 1)
    url = oparl.papers[0]["auxiliaryFile"][0]["downloadUrl"]
    with pytest.raises(abruf.Abbruch) as e:
        dokumente._hole(url, tmp_path / "fehlt" / "datei.pdf", 10 ** 6)
    assert e.value.art == "lokal" and not dokumente.moegliche_sperre(e.value) and str(tmp_path) not in str(e.value)

    echt = open

    class Voll:   # nur das PDF (Modus wb) trifft auf eine volle Platte
        def __init__(self, pfad, modus="r", *a, **k):
            self.f, self.modus = echt(pfad, modus, *a, **k), modus

        def write(self, b):
            if self.modus == "wb":
                raise OSError(28, "No space left on device")
            return self.f.write(b)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.f.close()

        def __getattr__(self, name):
            return getattr(self.f, name)
    with monkeypatch.context() as m:
        m.setattr(dokumente, "open", Voll, raising=False)
        dokumente.holen()
    z = _zustand()
    assert z["letzter_abbruch"]["art"] == "platz" and _statistik()[-1]["ende"] == "platz"
    assert not config.ZUSTAND.exists(), "kein Sperrverdacht im Zustand des OParl-Abrufs"
    assert not list(config.RAW.parent.rglob("*.pdf"))


def test_gesamtfrist_bei_tropf_antwort(tmp_path, monkeypatch):
    """Eine Antwort, die nur tröpfchenweise kommt, endet kurz nach der Gesamtfrist (read1: geprüft nach jedem Empfang),
    nicht erst nach einem vollen Stück von 64 KiB."""
    import time as zeit
    from http.server import BaseHTTPRequestHandler

    class Tropf(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", "200000")
            self.end_headers()
            try:
                self.wfile.write(b"%PDF-1.4\n" + b"x" * 1015)
                for _ in range(100):
                    self.wfile.flush()
                    zeit.sleep(0.05)
                    self.wfile.write(b"y" * 1024)
            except OSError:
                pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Tropf)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(config, "DOKUMENTE_GESAMTFRIST", 1)
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_TAG", 0.0)
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_NACHT", 0.0)
    start = zeit.monotonic()
    try:
        with pytest.raises(abruf.Abbruch) as e:
            dokumente._hole(f"http://127.0.0.1:{server.server_address[1]}/downloadfiles/1.pdf", tmp_path / "x.pdf",
                            10 ** 6)
    finally:
        server.shutdown()
    assert e.value.art == "sperre" and zeit.monotonic() - start < 2.5
    assert not (tmp_path / "x.pdf").exists()


def test_zustand_nicht_nach_jeder_datei(oparl, monkeypatch):
    """Der Zustand wird während des Laufs höchstens alle DOKUMENTE_ZUSTAND_SEKUNDEN geschrieben, am Ende immer."""
    _anlagen(oparl)
    aufrufe = []
    alt = dokumente._zustand_schreiben
    monkeypatch.setattr(dokumente, "_zustand_schreiben", lambda z: (aufrufe.append(1), alt(z)))
    monkeypatch.setattr(config, "DOKUMENTE_ZUSTAND_SEKUNDEN", 3600)
    dokumente.holen()
    assert len(aufrufe) == 2 and len(_zustand()["dateien"]) == 3   # vor dem Laden und am Ende
    aufrufe.clear()
    monkeypatch.setattr(config, "DOKUMENTE_ZUSTAND_SEKUNDEN", 0)
    dokumente.textpfad(dokumente.schluessel(f"{oparl.b}/files/1")).unlink()
    dokumente.textpfad(dokumente.schluessel(f"{oparl.b}/files/2")).unlink()
    dokumente.holen()
    assert len(aufrufe) == 4


def test_sigterm_raeumt_auf(oparl, monkeypatch):
    """SIGTERM während einer Datei (Ende eines Actions-Jobs): das PDF wird gelöscht, der Zustand geschrieben, die
    vorige Signalbehandlung wiederhergestellt."""
    import os
    import signal
    _anlagen(oparl)
    vorher = signal.getsignal(signal.SIGTERM)
    gesehen = []

    def extrahieren(pdf, txt, mit=None):
        gesehen.append(pdf.exists())
        os.kill(os.getpid(), signal.SIGTERM)
        for _ in range(1000):   # das Signal wird zwischen zwei Anweisungen behandelt
            pass
        raise AssertionError("SIGTERM nicht behandelt")
    monkeypatch.setattr(dokumente, "extrahieren", extrahieren)
    with pytest.raises(SystemExit):
        dokumente.holen()
    assert gesehen == [True]
    assert not list(config.RAW.parent.rglob("*.pdf")) and not (config.TEXTE_ORDNER / dokumente.ARBEIT).exists()
    assert _statistik()[-1]["ende"] == "beendet" and config.DOKUMENTE_ZUSTAND.exists()
    assert signal.getsignal(signal.SIGTERM) is vorher


def test_retry_after_ueber_die_pausen_hinaus(oparl, monkeypatch):
    monkeypatch.setattr(config, "ABRUF_PAUSEN", [0, 0])
    _anlagen(oparl, 1)
    oparl.datei_setzen(1, (429, {"Retry-After": "86400"}, b""))
    dokumente.holen()
    z = _zustand()
    assert z["letzter_abbruch"]["art"] == "aufgegeben" and z["nicht_vor"]
    assert json.loads(config.ZUSTAND.read_text())["nicht_vor"] == z["nicht_vor"]
    assert len(_downloads(oparl)) == 1


def test_404_einzeln_vermerkt_mehrere_in_folge_abbruch(oparl, monkeypatch):
    monkeypatch.setattr(config, "DOKUMENTE_FEHLT_IN_FOLGE", 2)
    _anlagen(oparl, 4)
    oparl.datei_setzen(4, (404, {}, b""))
    oparl.datei_setzen(2, (410, {}, b""))
    oparl.datei_setzen(1, (404, {}, b""))
    dokumente.holen()   # 4: fehlt, 3: geladen, 2: fehlt, 1: fehlt → zwei in Folge
    z = _zustand()
    assert {k.rsplit("/", 1)[1]: e["status"] for k, e in z["dateien"].items()} == {
        "4": "fehlt", "3": "geladen", "2": "fehlt", "1": "fehlt"}
    assert z["letzter_abbruch"]["art"] == "http" and not config.ZUSTAND.exists()   # kein Sperrverdacht
    # nach weniger als DOKUMENTE_FEHLT_TAGE kein neuer Versuch, danach schon
    oparl.anfragen.clear()
    dokumente.holen()
    assert _downloads(oparl) == []
    spaeter = datetime.now(timezone.utc) + timedelta(days=config.DOKUMENTE_FEHLT_TAGE, hours=1)
    monkeypatch.setattr(abruf, "uhr", lambda: spaeter)
    dokumente.holen()
    assert len(_downloads(oparl)) == 2   # 4, dann 2 und Abbruch (zwei in Folge)


# --- Obergrenzen, Platz, Einstellungen ----------------------------------------------------------------------------------

def test_obergrenzen_je_lauf(oparl, monkeypatch):
    _anlagen(oparl)
    monkeypatch.setattr(config, "DOKUMENTE_MAX_DATEIEN", 2)
    dokumente.holen()
    assert len(_downloads(oparl)) == 2 and _statistik()[-1]["ende"] == "grenze"
    assert "letzter_abbruch" not in _zustand() and _statistik()[-1]["offen"] == "1"
    monkeypatch.setattr(config, "DOKUMENTE_MAX_DATEIEN", 2000)
    monkeypatch.setattr(config, "DOKUMENTE_MAX_BYTES", 1)
    oparl.anfragen.clear()
    oparl.papers[0]["auxiliaryFile"][0]["modified"] = "2026-11-20T10:00:00+01:00"
    oparl.papers[1]["auxiliaryFile"][0]["modified"] = "2026-11-20T10:00:00+01:00"
    _rohdaten(oparl)
    dokumente.holen()
    assert len(_downloads(oparl)) == 1 and _statistik()[-1]["ende"] == "grenze"


def test_laufzeitgrenze(oparl, monkeypatch):
    _anlagen(oparl)
    uhr = {"t": 100.0}

    def schlafen(s):
        uhr["t"] += s
    monkeypatch.setattr(dokumente, "time", types.SimpleNamespace(monotonic=lambda: uhr["t"], sleep=schlafen))
    monkeypatch.setattr(dokumente, "_letzte", uhr["t"])
    monkeypatch.setattr(config, "DOKUMENTE_MAX_SEKUNDEN", 10)
    alt = dokumente._hole

    def hole(*a, **k):
        uhr["t"] += 6   # jede Datei dauert 6 s
        return alt(*a, **k)
    monkeypatch.setattr(dokumente, "_hole", hole)
    dokumente.holen()
    assert len(_downloads(oparl)) == 2 and _statistik()[-1]["ende"] == "grenze"


def test_plattenplatz(oparl, monkeypatch):
    _anlagen(oparl)
    monkeypatch.setattr(dokumente, "frei", lambda: 10)
    dokumente.holen()
    assert _downloads(oparl) == [] and _statistik()[-1]["ende"] == "platz"
    frei = iter([10 ** 12, 10 ** 12, 10 ** 12, 10])   # vor dem Lauf und vor Datei 1 genug, vor Datei 2 nicht
    monkeypatch.setattr(dokumente, "frei", lambda: next(frei, 10))
    dokumente.holen()
    assert len(_downloads(oparl)) == 1 and _statistik()[-1]["ende"] == "platz"


@pytest.mark.parametrize("name, wert", [("DOKUMENTE_MAX_DATEIEN", 0), ("DOKUMENTE_MAX_BYTES", -1),
                                        ("DOKUMENTE_MAX_DATEI_BYTES", True), ("DOKUMENTE_MIN_FREI", 1000),
                                        ("DOKUMENTE_MAX_SEKUNDEN", -5)])
def test_einstellungsfehler_vor_der_ersten_anfrage(oparl, monkeypatch, name, wert):
    _anlagen(oparl, 1)
    monkeypatch.setattr(config, name, wert)
    with pytest.raises(ValueError):
        dokumente.holen()
    assert oparl.anfragen == []


def test_ohne_werkzeug_keine_anfrage(oparl, monkeypatch):
    _anlagen(oparl, 1)
    monkeypatch.setattr(dokumente, "werkzeug", lambda: None)
    with pytest.raises(ValueError, match="pypdf"):
        dokumente.holen()
    assert oparl.anfragen == []


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext fehlt")
def test_pdftotext_als_ersatz(tmp_path):
    pdf, txt = tmp_path / "a.pdf", tmp_path / "a.txt"
    pdf.write_bytes(pdf_erzeugen(["eins", "zwei"]))
    assert dokumente.extrahieren(pdf, txt, "pdftotext") == 2
    assert [t.strip() for t in txt.read_text(encoding="utf-8").split("\f")[:2]] == ["eins", "zwei"]


def test_extraktion_mit_zeitgrenze(tmp_path, monkeypatch):
    pdf, txt = tmp_path / "a.pdf", tmp_path / "a.txt"
    pdf.write_bytes(pdf_erzeugen(["eins"]))
    monkeypatch.setattr(dokumente, "_PYPDF", "import time; time.sleep(30)")
    monkeypatch.setattr(config, "DOKUMENTE_EXTRAKTION_SEKUNDEN", 1)
    with pytest.raises(dokumente.ExtraktionFehler, match="Zeitgrenze"):
        dokumente.extrahieren(pdf, txt, "pypdf")


# --- Datenschutz und Repository ------------------------------------------------------------------------------------------

def test_keine_dateinamen_namen_oder_texte_in_protokollen_und_ausgaben(oparl, capsys):
    oparl.anlage(oparl.papers[0], 1, pdf_erzeugen([MARKE]), name=NAME)
    oparl.anlage(oparl.papers[1], 2, (200, {"Content-Type": "application/msword"}, MARKE.encode() * 100), name=NAME)
    _rohdaten(oparl)
    aenderungen.protokollieren()
    dokumente.holen()
    assert MARKE in _text(oparl, 1)
    ausgabe = capsys.readouterr()
    for teil in (ausgabe.out, ausgabe.err):
        assert MARKE not in teil and "Musterfrau" not in teil
    texte = config.TEXTE_ORDNER.resolve()
    for pfad in config.RAW.parent.rglob("*"):
        if pfad.is_file() and texte not in pfad.resolve().parents and pfad.resolve() != config.PAPERS.resolve():
            inhalt = pfad.read_bytes()
            assert MARKE.encode() not in inhalt and b"Musterfrau" not in inhalt, pfad


def test_texte_und_zustand_nicht_versioniert():
    if not shutil.which("git") or not (config.ROOT / ".git").exists():
        pytest.skip("kein Git-Checkout")
    for pfad in ("data/raw/texte/0123.txt.gz", "data/raw/texte/_arbeit/datei.pdf", "data/raw/zustand_dokumente.json",
                 "data/export/abruf_dokumente.tsv"):
        r = subprocess.run(["git", "check-ignore", "-q", pfad], cwd=config.ROOT, capture_output=True)
        assert r.returncode == 0, pfad
    assert config.TEXTE_ORDNER.is_relative_to(config.RAW) or config.TEXTE_ORDNER.name == "texte"


# --- Rate, Freigaben, Vorrang, 12-Stunden-Regel (Scheinuhr, Server auf 127.0.0.2: nicht lokal) ---------------------------

@pytest.mark.parametrize("utc, zeit", [
    (datetime(2026, 11, 16, 4, 59, tzinfo=timezone.utc), "nacht"),    # 05:59 Ortszeit
    (datetime(2026, 11, 16, 5, 0, tzinfo=timezone.utc), "tag"),       # 06:00
    (datetime(2026, 11, 16, 21, 59, tzinfo=timezone.utc), "tag"),     # 22:59
    (datetime(2026, 11, 16, 22, 0, tzinfo=timezone.utc), "nacht"),    # 23:00
    (datetime(2026, 7, 16, 4, 0, tzinfo=timezone.utc), "tag"),        # 06:00 Sommerzeit
])
def test_tageszeit_in_ortszeit(utc, zeit):
    assert dokumente.tageszeit(utc) == zeit


def test_mindestabstand_nicht_lokal(monkeypatch):
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_TAG", 0.0)
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_NACHT", float("nan"))
    assert dokumente.abstand_fuer(MITTAG) == 5.0 and dokumente.abstand_fuer(NACHTS) == 2.0
    assert dokumente.abstand_fuer(MITTAG, lokal=True) == 0.0
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_TAG", 8.0)
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_NACHT", 3.0)
    assert dokumente.abstand_fuer(MITTAG) == 8.0 and dokumente.abstand_fuer(NACHTS) == 3.0


@pytest.fixture
def fern(tmp_path, monkeypatch):
    """Testserver auf 127.0.0.2 (gilt nicht als lokal: Freigaben, Mindestabstand, Sperre und Vorrang wirken), ohne
    Proxy, mit Wächter; Scheinuhr (abruf.uhr) und Scheinzeit für Abstände (dokumente.time)."""
    server = ThreadingHTTPServer(("127.0.0.2", 0), _Handler)
    server.daten = Daten(f"http://127.0.0.2:{server.server_address[1]}")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    pfade_umlenken(tmp_path, server.daten.b, monkeypatch.setattr)
    monkeypatch.setattr(abruf, "_OEFFNER", _Waechter(abruf.oeffner({})))
    monkeypatch.setenv("RATSATLAS_STADT_INFORMIERT", "ja")
    monkeypatch.setenv("RATSATLAS_PDF_FREIGEGEBEN", "ja")
    monkeypatch.delenv("RATSATLAS_KONTAKT", raising=False)
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_TAG", 5.0)
    monkeypatch.setattr(config, "DOKUMENTE_ABSTAND_NACHT", 2.0)
    zeit = types.SimpleNamespace(t=1000.0, gewartet=[], jetzt=MITTAG, daten=server.daten)

    def schlafen(s):
        zeit.gewartet.append(round(s, 3))
        zeit.t += s
    monkeypatch.setattr(dokumente, "time", types.SimpleNamespace(monotonic=lambda: zeit.t, sleep=schlafen))
    monkeypatch.setattr(dokumente, "_letzte", 1000.0)
    monkeypatch.setattr(abruf, "uhr", lambda: zeit.jetzt)
    yield zeit
    server.shutdown()


@pytest.mark.parametrize("jetzt, abstand", [(MITTAG, 5.0), (NACHTS, 2.0)])
def test_rate_tagsueber_5_s_nachts_2_s(fern, jetzt, abstand):
    fern.jetzt = jetzt
    _anlagen(fern.daten)
    dokumente.holen()
    assert len(_downloads(fern.daten)) == 3
    assert fern.gewartet == [abstand] * 3   # vom Ende jeder Antwort (Scheinzeit steht) bis zur nächsten Anfrage
    assert {z["tageszeit"] for z in _protokoll()} == {"tag" if jetzt == MITTAG else "nacht"}
    assert {float(z["abstand"]) for z in _protokoll()} == {abstand}


def test_rate_wechselt_mit_der_uhrzeit(fern, monkeypatch):
    _anlagen(fern.daten)
    fern.jetzt = datetime(2026, 11, 17, 4, 59, 58, tzinfo=timezone.utc)   # 05:59:58 Ortszeit
    alt = dokumente._hole

    def hole(*a, **k):
        r = alt(*a, **k)
        fern.jetzt += timedelta(seconds=1)
        return r
    monkeypatch.setattr(dokumente, "_hole", hole)
    dokumente.holen()
    assert fern.gewartet == [2.0, 2.0, 5.0]


@pytest.mark.parametrize("umgebung", [{}, {"RATSATLAS_STADT_INFORMIERT": "ja"}, {"RATSATLAS_PDF_FREIGEGEBEN": "ja"}])
def test_ohne_beide_freigaben_keine_anfrage(fern, monkeypatch, umgebung):
    for k in ("RATSATLAS_STADT_INFORMIERT", "RATSATLAS_PDF_FREIGEGEBEN"):
        monkeypatch.delenv(k, raising=False)
    for k, v in umgebung.items():
        monkeypatch.setenv(k, v)
    _anlagen(fern.daten)
    dokumente.holen()
    assert fern.daten.anfragen == [] and _statistik()[-1]["ende"] == "uebersprungen"
    with pytest.raises(abruf.Abbruch) as e:
        dokumente._hole(fern.daten.papers[0]["auxiliaryFile"][0]["downloadUrl"], config.RAW / "x.pdf", 10 ** 6)
    assert e.value.art == "gesperrt" and fern.daten.anfragen == []


def test_vorrang_des_oparl_abrufs(fern, monkeypatch):
    _anlagen(fern.daten)
    fern.jetzt = OPARL_FENSTER
    dokumente.holen()
    assert fern.daten.anfragen == [] and _statistik()[-1]["ende"] == "uebersprungen"
    # kurz vor dem Zeitfenster (Vorlauf: Gesamtfrist, Extraktion, Abstand) beginnt ebenfalls keine Datei
    fern.jetzt = datetime(2026, 11, 16, 21, 50, tzinfo=timezone.utc)   # 22:50 Ortszeit
    dokumente.holen()
    assert fern.daten.anfragen == [] and _statistik()[-1]["ende"] == "uebersprungen"
    # während eines Laufs beginnt der Vorlauf: Ende ohne Fehler, keine 12-Stunden-Regel
    fern.jetzt = datetime(2026, 11, 16, 21, 46, 59, tzinfo=timezone.utc)   # 22:46:59 Ortszeit, Vorlauf ab 22:47
    alt = dokumente._hole

    def hole(*a, **k):
        r = alt(*a, **k)
        fern.jetzt += timedelta(seconds=1)
        return r
    monkeypatch.setattr(dokumente, "_hole", hole)
    dokumente.holen()
    assert len(_downloads(fern.daten)) == 1 and _statistik()[-1]["ende"] == "vorrang"
    assert "letzter_abbruch" not in _zustand() and not config.ZUSTAND.exists()
    # ohne Vorrang auch im Zeitfenster (2 s)
    monkeypatch.setattr(config, "DOKUMENTE_OPARL_VORRANG", False)
    dokumente.holen()
    assert len(_downloads(fern.daten)) == 3


def test_zwoelf_stunden_regel_und_pause_des_oparl_abrufs(fern):
    _anlagen(fern.daten)
    fern.daten.datei_setzen(3, (403, {}, b""))
    fern.daten.datei_setzen(2, (403, {}, b""))
    dokumente.holen()
    assert _downloads(fern.daten) == ["/downloadfiles/3.pdf", "/downloadfiles/2.pdf"]
    fern.daten.datei_setzen(3, pdf_erzeugen(["wieder da"]))
    fern.daten.datei_setzen(2, pdf_erzeugen(["wieder da"]))
    fern.daten.anfragen.clear()
    fern.jetzt = MITTAG + timedelta(hours=11)   # 23:00 Ortszeit wäre Vorrang; hier 22:00
    dokumente.holen()
    assert fern.daten.anfragen == [] and _statistik()[-1]["ende"] == "uebersprungen"
    # der Sperrverdacht steht auch im Zustand des OParl-Abrufs: dessen 12-Stunden-Regel greift ebenso
    assert sessionnet._pause_grund(sessionnet._zustand(), False)
    # eigene Regel abgelaufen, aber der OParl-Abruf meldet noch eine Pause (Retry-After): weiter keine Anfrage
    fern.jetzt = MITTAG + timedelta(hours=13)   # 02:00 Ortszeit am nächsten Tag
    sessionnet._zustand_aendern(nicht_vor=(fern.jetzt + timedelta(hours=1)).isoformat())
    dokumente.holen()
    assert fern.daten.anfragen == []
    sessionnet._zustand_aendern(nicht_vor=None)
    dokumente.holen()   # neue Datei zuerst, die abgewiesene Serie am Ende
    assert _downloads(fern.daten) == ["/downloadfiles/1.pdf", "/downloadfiles/3.pdf", "/downloadfiles/2.pdf"]
    assert "letzter_abbruch" not in _zustand()


def test_zwoelf_stunden_regel_ohne_sperrverdacht(fern):
    """Abbruch ohne mögliche Sperre (HTTP 400): nur die eigene 12-Stunden-Regel, der OParl-Abruf bleibt unberührt."""
    _anlagen(fern.daten, 1)
    fern.daten.datei_setzen(1, (400, {}, b""))
    dokumente.holen()
    assert _zustand()["letzter_abbruch"]["art"] == "http" and not config.ZUSTAND.exists()
    fern.daten.datei_setzen(1, pdf_erzeugen(["wieder da"]))
    fern.daten.anfragen.clear()
    fern.jetzt = MITTAG + timedelta(hours=10)
    dokumente.holen()
    assert fern.daten.anfragen == []
    fern.jetzt = MITTAG + timedelta(hours=14)   # 02:00 Ortszeit
    dokumente.holen()
    assert _downloads(fern.daten) == ["/downloadfiles/1.pdf"] and "letzter_abbruch" not in _zustand()


def test_paralleler_prozess_keine_anfrage(fern, monkeypatch):
    """Ein zweiter Lauf, während ein anderer Prozess die Sperre hält: keine Anfrage, und weder der Arbeitsordner (mit
    dem PDF des laufenden Prozesses) noch der Zustand werden angefasst."""
    _anlagen(fern.daten)
    dokumente.holen()
    fern.daten.anfragen.clear()
    dokumente.textpfad(dokumente.schluessel(f"{fern.daten.b}/files/1")).unlink()   # es gäbe etwas zu laden
    arbeit = config.TEXTE_ORDNER / dokumente.ARBEIT
    arbeit.mkdir()
    (arbeit / "datei.pdf").write_bytes(b"%PDF-1.4 laufender Prozess")
    zustand = config.DOKUMENTE_ZUSTAND.read_bytes()

    def belegt():
        raise abruf.Abbruch("Ein anderer Abrufprozess läuft noch", "parallel")
    monkeypatch.setattr(abruf, "sperre_halten", belegt)
    dokumente.holen()
    assert fern.daten.anfragen == [] and _statistik()[-1]["ende"] == "uebersprungen"
    assert (arbeit / "datei.pdf").exists() and config.DOKUMENTE_ZUSTAND.read_bytes() == zustand


def test_user_agent_mit_kontakt(fern):
    _anlagen(fern.daten, 1)
    dokumente.holen()
    assert {ua for p, _, ua in fern.daten.anfragen} == {config.USER_AGENT}
    assert config.KONTAKT in config.USER_AGENT


def test_dauerhaft_abgewiesene_datei_blockiert_nicht(fern):
    """Eine Datei antwortet dauerhaft mit 403 (nicht öffentlich): Sie wird vermerkt, die übrigen Dateien laden, und
    weder die 12-Stunden-Regel noch der Sperrverdacht des OParl-Abrufs greifen; drei Läufe im Abstand von 13 Stunden."""
    _anlagen(fern.daten)
    fern.daten.datei_setzen(3, (403, {}, b""))
    dokumente.holen()
    assert _downloads(fern.daten) == ["/downloadfiles/3.pdf", "/downloadfiles/2.pdf", "/downloadfiles/1.pdf"]
    for _ in range(2):
        fern.jetzt += timedelta(hours=13)
        fern.daten.anfragen.clear()
        dokumente.holen()
        assert fern.daten.anfragen == []
    assert "letzter_abbruch" not in _zustand() and not config.ZUSTAND.exists()
    assert _zustand()["dateien"][f"{fern.daten.b}/files/3"]["status"] == "verweigert"


def test_pause_reicht_nicht_in_das_zeitfenster_des_oparl_abrufs(fern, monkeypatch):
    """Nach 503 wachsende Pausen; eine Pause, die bis in das Zeitfenster (mit Vorlauf) reichte, wird nicht abgewartet:
    sofort `aufgegeben`, der Prozess gibt die Sperre frei (wie abruf.get_json)."""
    _anlagen(fern.daten, 1)
    fern.daten.datei_setzen(1, (503, {}, b""))
    fern.jetzt = datetime(2026, 11, 16, 20, 0, tzinfo=timezone.utc)   # 21:00 Ortszeit

    def schlafen(s):
        fern.gewartet.append(round(s, 3))
        fern.t += s
        fern.jetzt += timedelta(seconds=s)
    monkeypatch.setattr(dokumente, "time", types.SimpleNamespace(monotonic=lambda: fern.t, sleep=schlafen))
    dokumente.holen()
    pausen = [g for g in fern.gewartet if g >= 60]
    assert pausen == [60, 300, 1800, 3600]   # die nächste (3 h) reichte über 23 Uhr
    z = _zustand()
    assert z["letzter_abbruch"]["art"] == "aufgegeben" and "Zeitfenster des OParl-Abrufs" in z["letzter_abbruch"]["meldung"]
    assert abruf.im_zeitfenster(fern.jetzt) is False


def test_tagesgrenze_ueber_mehrere_laeufe(fern, monkeypatch):
    """Die Obergrenze je Kalendertag gilt über alle Läufe; am nächsten Tag geht es weiter."""
    monkeypatch.setattr(config, "DOKUMENTE_MAX_TAG", 2)
    _anlagen(fern.daten)
    dokumente.holen()
    assert len(_downloads(fern.daten)) == 2 and _statistik()[-1]["ende"] == "grenze"
    assert _zustand()["tag"] == {"datum": "2026-11-16", "anfragen": 2}
    fern.daten.anfragen.clear()
    fern.jetzt += timedelta(hours=1)
    dokumente.holen()
    assert fern.daten.anfragen == [] and _statistik()[-1]["ende"] == "uebersprungen"
    fern.jetzt += timedelta(days=1)
    dokumente.holen()
    assert _downloads(fern.daten) == ["/downloadfiles/1.pdf"]
    assert _zustand()["tag"] == {"datum": "2026-11-17", "anfragen": 1}
