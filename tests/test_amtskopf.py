"""Federführendes Amt aus dem Kopf der Vorlagendokumente (pipeline/amtskopf.py, Schritt `amtskopf`; CLAUDE.md 5.3 und 9,
Entscheidungen vom 13.11. und 15.11.2026) mit erfundenen Texten, Vorlagen und Organisationen; keine Daten der Stadt,
keine Anfrage ans Netz.

- Fälle: Stelle eindeutig, Stelle mehrdeutig (keine Zuordnung), Nummer nur außerhalb des Kopfes, keine Nummer, leerer
  Text, Seite 2 bei leerer Seite 1, noch nicht geladen, Datei nach Name gewählt
- actors.responsibilities: method „pdf_kopf“, derived 1, evidence nur die Fundstelle; robust ohne Ergebnisdatei
- Audit-Tabelle und Konsolenausgabe ohne Textauszüge, Dateinamen, Namen, Telefonnummern oder E-Mail-Adressen
- Gleichheit der übernommenen Textfunktionen mit explore/oparl_messung.py und explore/auswertung.py (Stufe 6)"""
import csv
import gzip
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from oparl_testserver import pdf_erzeugen, pfade_umlenken
from pipeline import actors, amtskopf, config, dokumente

EXPLORE = Path(__file__).resolve().parents[1] / "explore"
BASIS = "http://127.0.0.1:9/oparl/bodies/0001"
ORG = f"{BASIS}/organizations"

# erfundene Organisationen mit Präfix at (Nummern frei gewählt; 403 zweimal für „Stelle mehrdeutig“)
ORGS = [
    {"id": f"{ORG}/at/1", "name": "Ressort 402 - Testressort", "shortName": ""},
    {"id": f"{ORG}/at/2", "name": "Ressort 403 - Musterfinanzen"},
    {"id": f"{ORG}/at/3", "name": "Ressort 403 - Beispielkasse"},
    {"id": f"{ORG}/gr/7", "name": "Ausschuss für Probeangelegenheiten"},
]
# erfundene Merkmale, die nie in Audit-Tabelle, Ergebnis oder Konsole stehen dürfen
GEHEIM = ("Erika Musterfrau", "Musterfrau", "0202 987654", "erika.musterfrau@example.invalid", "example.invalid",
          "Zebrafink", "Kopfmarke", "Testressort", "Probetext", "Dateiname-Marke")
KOPF = ("Stadt Musterhausen\nDer Oberbürgermeister\nRessort 402 Testressort\nSachbearbeitung: Erika Musterfrau\n"
        "Telefon 0202 987654\nE-Mail erika.musterfrau@example.invalid\nBeschlussvorschlag\nZebrafink Kopfmarke Probetext\f"
        "Seite zwei ohne Nummer\f")


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    pfade_umlenken(tmp_path, BASIS, monkeypatch.setattr)

    def gesperrt(*a, **k):
        raise AssertionError("amtskopf darf keine Verbindung öffnen")
    monkeypatch.setattr(socket.socket, "connect", gesperrt)
    monkeypatch.setattr(socket, "create_connection", gesperrt)
    config.RAW.mkdir(parents=True, exist_ok=True)
    config.ORGANIZATIONS.write_text(json.dumps(ORGS, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def _vorlage(nr, art="Beschlussvorlage", leitung=None, dateien=None, datum="2024-03-01"):
    p = {"id": f"{BASIS}/papers/{nr}", "reference": f"VO/{nr:04d}/24", "paperType": art, "date": datum,
         "name": f"Erfundene Vorlage {nr}",
         "auxiliaryFile": dateien if dateien is not None else [_datei(nr, 1, "Vorlage")]}
    if leitung:
        p["underDirectionOf"] = [leitung]
    return p


def _datei(nr, i, name, datei_name=None):
    return {"id": f"{BASIS}/files/{nr}-{i}", "name": name, "fileName": datei_name or f"{name}.pdf",
            "mimeType": "application/pdf", "accessUrl": f"{BASIS}/downloadfiles/a/{nr}-{i}.pdf"}


def _schreiben(papers, texte):
    """papers.jsonl, Texte (gz, wie dokumente._text_schreiben) und Zustand des Dokumentabrufs (je Text „geladen“ bzw.
    „ohne_text“, wenn der Text keine Buchstaben hat)."""
    config.PAPERS.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in papers), encoding="utf-8")
    config.TEXTE_ORDNER.mkdir(parents=True, exist_ok=True)
    zustand = {"version": 1, "dateien": {}}
    for kennung, (vorlage, text) in texte.items():
        s = dokumente.schluessel(kennung)
        with gzip.open(dokumente.textpfad(s), "wt", encoding="utf-8") as f:
            f.write(text)
        status = "geladen" if any(c.isalnum() for c in text) else "ohne_text"
        zustand["dateien"][kennung] = {"status": status, "vorlage": vorlage, "schluessel": s}
    config.DOKUMENTE_ZUSTAND.write_text(json.dumps(zustand), encoding="utf-8")


def _audit():
    with open(config.AMTSKOPF_AUDIT, encoding="utf-8") as f:
        return {z["id"]: z for z in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)}


def _datei_id(nr, i=1):
    return f"{BASIS}/files/{nr}-{i}"


FAELLE = {
    1: KOPF,                                                                            # eindeutig
    2: "Stadt Musterhausen\nRessort 403\nBegründung\nProbetext\f",                      # mehrdeutig
    3: "Stadt Musterhausen\nOhne Nummer im Kopf\nBegründung\nDas Ressort 402 Probetext\f",   # nur außerhalb
    4: "Stadt Musterhausen\nRessort Probewesen\nSachverhalt\nProbetext ohne Nummer\f",    # keine Nummer
    5: "\f\f",                                                                          # leerer Text
    6: "\f\nAmt 402\nBeschlussvorschlag\nProbetext\f",                                  # Seite 1 leer, Seite 2
}


@pytest.fixture
def lauf(umgebung, capsys):
    papers = [_vorlage(nr) for nr in FAELLE]
    papers += [_vorlage(7),                                                   # noch nicht geladen
               _vorlage(8, leitung=f"{ORG}/at/1"),                            # mit underDirectionOf
               _vorlage(9, art="Antrag CDU"),                                 # keine Verwaltungsvorlage
               _vorlage(10, datum="2019-06-30", dateien=[_datei(10, 1, "Vorlage")]),   # vor 2020
               _vorlage(11, dateien=[_datei(11, 1, "Anlage 1", "Dateiname-Marke Erika Musterfrau.pdf"),
                                     _datei(11, 2, "Beschlussvorlage")])]     # Datei nach Name gewählt
    texte = {_datei_id(nr): (f"{BASIS}/papers/{nr}", t) for nr, t in FAELLE.items()}
    texte[_datei_id(8)] = (f"{BASIS}/papers/8", KOPF)
    texte[_datei_id(11, 1)] = (f"{BASIS}/papers/11", "Ressort 403\nBegründung\f")
    texte[_datei_id(11, 2)] = (f"{BASIS}/papers/11", "Kopf\nRessort 402.\nSachverhalt\f")
    _schreiben(papers, texte)
    amtskopf.auswerten()
    return {"papers": {p["id"]: p for p in papers}, "audit": _audit(), "ausgabe": capsys.readouterr().out,
            "ergebnis": json.loads(config.AMTSKOPF.read_text(encoding="utf-8"))}


def _p(nr):
    return f"{BASIS}/papers/{nr}"


def test_eindeutige_stelle(lauf):
    z = lauf["audit"][_p(1)]
    assert (z["treffer"], z["stelle"], z["abgleich"]) == ("kennung", amtskopf.STELLE_EINDEUTIG, f"{ORG}/at/1")
    assert (z["fundstelle"], z["zeile"], z["abschnitt_zeile"], z["kennung"]) == ("Seite 1", "3", "7", "Ressort 402")
    assert (z["seiten"], z["seitengrenzen"], z["lage"], z["datei"]) == ("2", "ja", "ein Kandidat", _datei_id(1))
    assert lauf["ergebnis"]["vorlagen"][_p(1)] == {"organization_id": f"{ORG}/at/1", "datei": _datei_id(1),
                                                    "fundstelle": "Seite 1, Kopf, Zeile 3"}


def test_mehrdeutige_stelle_ohne_zuordnung(lauf):
    z = lauf["audit"][_p(2)]
    assert (z["treffer"], z["stelle"], z["abgleich"]) == ("kennung", amtskopf.STELLE_MEHRDEUTIG, "mehrdeutig (2)")
    assert z["stellen"] == f"{ORG}/at/2; {ORG}/at/3"
    assert _p(2) not in lauf["ergebnis"]["vorlagen"]
    assert actors.responsibilities(lauf["papers"][_p(2)], {}, {}) == []


def test_nummer_nur_ausserhalb_des_kopfes(lauf):
    z = lauf["audit"][_p(3)]
    assert (z["treffer"], z["stelle"]) == ("nur außerhalb des Kopfes", amtskopf.NICHT_IM_KOPF)
    assert z["kandidaten"] == "Ressort 402 Z4 außerhalb" and z["kennung"] == "" and z["abschnitt_zeile"] == "3"
    assert _p(3) not in lauf["ergebnis"]["vorlagen"]


def test_keine_nummer(lauf):
    z = lauf["audit"][_p(4)]
    assert (z["treffer"], z["stelle"], z["kandidaten_n"], z["lage"]) == ("nein", amtskopf.NICHT_IM_KOPF, "0", "keiner")


def test_leerer_text(lauf):
    z = lauf["audit"][_p(5)]
    assert (z["treffer"], z["stelle"], z["fundstelle"]) == ("kein_text", amtskopf.OHNE_TEXTEBENE, "Seite 1 und 2")
    assert z["status_dokument"] == "ohne_text"


def test_seite_zwei_bei_leerer_seite_eins(lauf):
    z = lauf["audit"][_p(6)]
    assert (z["fundstelle"], z["zeile"], z["kennung"], z["stelle"]) == (
        "Seite 2", "1", "Amt 402", amtskopf.STELLE_EINDEUTIG)
    assert lauf["ergebnis"]["vorlagen"][_p(6)]["fundstelle"] == "Seite 2, Kopf, Zeile 1"


def test_auswahl_der_vorlagen_und_der_datei(lauf):
    audit = lauf["audit"]
    assert audit[_p(7)]["treffer"] == amtskopf.NICHT_ABGERUFEN and audit[_p(7)]["stelle"] == amtskopf.NICHT_GELESEN
    assert audit[_p(7)]["status_dokument"] == "nicht im Zustand"
    assert not {_p(8), _p(9), _p(10)} & set(audit)        # mit underDirectionOf, Antrag, vor 2020
    z = audit[_p(11)]                                       # die Anlage steht zuerst, gelesen wird die Vorlage
    assert (z["datei"], z["datei_platz"], z["auswahl"]) == (
        _datei_id(11, 2), "auxiliaryFile 2 von 2", "Name nennt die Vorlage (Annahme)")
    assert (z["kennung"], z["stelle"]) == ("Ressort 402", amtskopf.STELLE_EINDEUTIG)


def test_responsibilities_aus_dem_kopf(lauf):
    rows = actors.responsibilities(lauf["papers"][_p(1)], {}, {})
    assert rows == [dict(organization_id=f"{ORG}/at/1", kind="federfuehrend", method="pdf_kopf",
                         evidence="Seite 1, Kopf, Zeile 3", derived=1)]
    # underDirectionOf hat Vorrang, auch wenn der Kopf etwas anderes nennt
    rows = actors.responsibilities({**lauf["papers"][_p(1)], "underDirectionOf": [f"{ORG}/at/2"]}, {}, {})
    assert [(r["organization_id"], r["method"], r["derived"]) for r in rows] == [(f"{ORG}/at/2", "underDirectionOf", 0)]
    # Datei nicht mehr in auxiliaryFile: veraltet, keine Zuordnung
    assert actors.responsibilities({**lauf["papers"][_p(1)], "auxiliaryFile": [_datei(1, 9, "Vorlage")]}, {}, {}) == []


def test_responsibilities_ohne_oder_mit_defekter_ergebnisdatei(umgebung):
    p = _vorlage(1)
    assert not config.AMTSKOPF.exists() and actors.responsibilities(p, {}, {}) == []
    config.AMTSKOPF.write_text("{kein json", encoding="utf-8")
    assert actors.responsibilities(p, {}, {}) == []
    # Einträge ohne at-Kennung oder mit freiem Text als Fundstelle werden nicht übernommen
    for eintrag in ({"organization_id": f"{ORG}/gr/7", "datei": _datei_id(1), "fundstelle": "Seite 1, Kopf, Zeile 3"},
                    {"organization_id": f"{ORG}/at/1", "datei": _datei_id(1), "fundstelle": "Ressort 402 Testressort"}):
        config.AMTSKOPF.write_text(json.dumps({"vorlagen": {p["id"]: eintrag}}), encoding="utf-8")
        assert actors.responsibilities(p, {}, {}) == []


def test_ohne_rohdaten_nichts_geschrieben(umgebung, capsys):
    amtskopf.auswerten()
    assert "fehlt" in capsys.readouterr().out
    assert not config.AMTSKOPF.exists() and not config.AMTSKOPF_AUDIT.exists()


def test_ohne_texte_alle_nicht_abgerufen(umgebung, capsys):
    _schreiben([_vorlage(1), _vorlage(2)], {})
    amtskopf.auswerten()
    audit = _audit()
    assert {z["treffer"] for z in audit.values()} == {amtskopf.NICHT_ABGERUFEN}
    assert json.loads(config.AMTSKOPF.read_text(encoding="utf-8"))["vorlagen"] == {}
    assert "abgerufen (Nenner wie Stufe 6) 0" in capsys.readouterr().out


def test_audit_ergebnis_und_konsole_ohne_textauszuege(lauf):
    tsv = config.AMTSKOPF_AUDIT.read_text(encoding="utf-8")
    erg = config.AMTSKOPF.read_text(encoding="utf-8")
    for text in (tsv, erg, lauf["ausgabe"]):
        for merkmal in GEHEIM + ("Oberbürgermeister", "Sachbearbeitung", "Telefon", "E-Mail", "Erfundene Vorlage"):
            assert merkmal not in text, merkmal
        assert "@" not in text
    # nur feste Spalten; die Kandidaten nennen nur Bezeichnung, Nummer, Zeile und Lage
    assert tsv.splitlines()[0].split("\t") == list(amtskopf.SPALTEN)
    for z in lauf["audit"].values():
        for teil in filter(None, z["kandidaten"].split("; ")):
            bezeichnung, nummer, zeile, lage = teil.split(" ")
            assert bezeichnung in amtskopf.BEZEICHNUNG_BELEGT + amtskopf.BEZEICHNUNG_ANNAHME
            assert nummer.replace(".", "").isdigit() and zeile[0] == "Z" and lage in ("Kopf", "außerhalb")


def test_zusammenfassung_mit_quoten_je_jahr(lauf):
    aus = lauf["ausgabe"]
    assert "Ämterliste: 3 Organisationen mit Präfix at aus organizations.json (Vollabruf)" in aus
    # abgerufen: 1–6 und 11 (7 nicht geladen); Nummer erkannt bei 1, 2, 6, 11; eindeutig bei 1, 6, 11
    assert "Nummer im Kopf erkannt (je abgerufene Datei): 4 von 7 (57 %); Stelle eindeutig 3 von 7 (43 %)" in aus
    assert "  2024: 8 / 7 / 4 / 3" in aus
    assert "Nach Bestand je Jahr gewichtet, Stelle eindeutig: 43 %" in aus
    # Vorlagen ab 2020: 1–9 und 11 (10 vor 2020); underDirectionOf 1 (Vorlage 8), PDF-Kopf eindeutig 3
    assert "Federführung ab 2020: underDirectionOf 1 + PDF-Kopf (Stelle eindeutig) 3 = 4 von 10 (40 %)" in aus


def test_gewichtung_nach_bestand_je_jahr():
    def z(jahr, treffer):
        return {"jahr": jahr, "treffer": treffer, "stelle": ""}
    # 2025: 1 von 2 abgerufen (Treffer), Bestand 2; 2021: 1 von 1 ohne Treffer, Bestand 6 (5 noch nicht geladen)
    zeilen = [z("2025", "kennung"), z("2025", amtskopf.NICHT_ABGERUFEN), z("2021", "nein")] + [
        z("2021", amtskopf.NICHT_ABGERUFEN)] * 5
    q, ohne = amtskopf.gewichtet(zeilen, lambda x: x["treffer"] == "kennung")
    assert q == pytest.approx(2 / 8 * 1 + 6 / 8 * 0) and ohne == []
    q, ohne = amtskopf.gewichtet(zeilen + [z("2020", amtskopf.NICHT_ABGERUFEN)], lambda x: x["treffer"] == "kennung")
    assert ohne == ["2020"] and q == pytest.approx(2 / 9 + 1 / 9 * 0.5)
    assert amtskopf.gewichtet([z("2020", amtskopf.NICHT_ABGERUFEN)], lambda x: True) is None


def test_schritt_im_aufruf_der_pipeline(umgebung):
    main = (Path(__file__).resolve().parents[1] / "pipeline" / "__main__.py").read_text(encoding="utf-8")
    assert '"amtskopf": amtskopf.auswerten,' in main and "|amtskopf|" in main


# --- Gleichheit mit Stufe 6 (explore/oparl_messung.py, explore/auswertung.py) --------------------------------------

@pytest.fixture(scope="module")
def stufe6():
    sys.path.insert(0, str(EXPLORE))
    import auswertung
    import oparl_messung
    return oparl_messung, auswertung


def test_regeln_gleich_wie_stufe_6(stufe6):
    m, a = stufe6
    for name in ("RE_VO", "RE_PRAEFIX", "RE_AMT", "RE_ABSCHNITT", "RE_VORLAGE_NAME", "RE_ANLAGE"):
        assert getattr(amtskopf, name).pattern == getattr(m, name).pattern, name
        assert getattr(amtskopf, name).flags == getattr(m, name).flags, name
    for name in ("KOPF_ZEILEN", "BEZEICHNUNG_BELEGT", "BEZEICHNUNG_ANNAHME", "_ZEICHEN", "VOR", "NACH", "GELESEN"):
        assert getattr(amtskopf, name) == getattr(m, name), name
    assert amtskopf.STELLEN == a.STELLEN and amtskopf.GELESEN == a.GELESEN


TEXTE = [
    KOPF.split("\f")[0],
    "Kopf\nGeschäfts-\nbereich 2.1\nStadt-\nbetrieb 105.3 und Amt 402.\nBegründung\nRessort 403",
    "Ressort\n102 Vermessung und Eigenbetrieb–Test­\nRessort 4021 Ressort 40.12\nSachverhalt",
    "Zeile\n" * 35 + "Amt 402",
    "Eigenbetrieb 50 und Ressort 403\n​Beschlussvorschlag",
    "",
    "Amt 402\nAmt 402\nAmt 105",
]
AEMTER = [(o["id"], f"{o['name']} {o.get('shortName') or ''}") for o in ORGS if "/at/" in o["id"]]


@pytest.mark.parametrize("text", TEXTE)
def test_textfunktionen_gleich_wie_stufe_6(stufe6, text):
    m, a = stufe6
    zeilen = amtskopf.text_normalisieren(text)
    assert zeilen == m.text_normalisieren(text)
    assert amtskopf.kopf_kandidaten(zeilen) == m.kopf_kandidaten(zeilen)
    kandidaten = amtskopf.kopf_kandidaten(zeilen)[0]
    assert amtskopf.federfuehrend(kandidaten) == m.federfuehrend(kandidaten)
    for k in kandidaten:
        for aemter in (AEMTER, [], None):
            assert amtskopf.amt_abgleichen(k["nummer"], aemter) == m.amt_abgleichen(k["nummer"], aemter)
            assert amtskopf.amt_kandidaten(k["nummer"], aemter) == m.amt_kandidaten(k["nummer"], aemter)


@pytest.mark.parametrize("p", [
    {"reference": "VO/0042/26", "paperType": "Bericht", "dateiliste": [
        {"name": "Anlage 1", "fileName": "VO_0042_26_Anlage.pdf", "url": "u1"},
        {"name": "Plan", "fileName": "42_2026.pdf", "mimeType": "application/pdf", "url": "u2"}]},
    {"reference": "VO/0001/24", "paperType": "Beschlussvorlage", "dateiliste": [
        {"name": "Anhang", "url": "u1"}, {"name": "Beschlussvorlage", "mimeType": "application/msword", "url": "u2"},
        {"name": "Text der Beschlussvorlage", "url": "u3"}]},
    {"reference": "X", "paperType": "", "dateiliste": [{"name": "Plan", "url": ""}, {"name": "Karte", "url": "u2"}]},
    {"reference": "VO/0001/24", "datei": "u9", "dateien": 3},
    {"reference": "VO/0001/24"},
    {"date": "2021-05-01"}, {},
])
def test_dateiwahl_und_jahr_gleich_wie_stufe_6(stufe6, p):
    m, _ = stufe6
    assert amtskopf.datei_waehlen(p) == m.datei_waehlen(p)
    assert amtskopf.jahr_der_vorlage(p) == m.jahr_der_vorlage(p)


@pytest.mark.parametrize("z", [
    {"treffer": "kennung", "abgleich": f"{ORG}/at/1"}, {"treffer": "kennung", "abgleich": "mehrdeutig (2)"},
    {"treffer": "kennung", "abgleich": "kein Treffer in organizations/at"},
    {"treffer": "kennung", "abgleich": "Ämterliste fehlt (zuerst organisationen)"}, {"treffer": "kennung"},
    {"treffer": "nein"}, {"treffer": "nur außerhalb des Kopfes"}, {"treffer": "kein_text"}, {"treffer": "zu groß"},
    {"treffer": amtskopf.NICHT_ABGERUFEN}, {},
])
def test_kategorie_gleich_wie_stufe_6(stufe6, z):
    assert amtskopf.stelle_kategorie(z) == stufe6[1].stelle_kategorie(z)


@pytest.mark.parametrize("werkzeug", ["pypdf", "pdftotext"])
@pytest.mark.parametrize("seiten", [["Ressort 402 Testressort", "Amt 105"], ["", "Ressort 403 Musterfinanzen"], [""]])
def test_texte_des_dokumentabrufs_wie_pdf_in_stufe_6(stufe6, tmp_path, werkzeug, seiten):
    """Seitengrenzen: Der Dokumentabruf trennt Seiten mit \\f; Seite 1, sonst Seite 2 ergibt dieselbe Fundstelle,
    Kennung, Zeile und denselben Abgleich wie die Auswertung der PDF-Datei in Stufe 6."""
    if werkzeug == "pypdf":
        pytest.importorskip("pypdf")
    elif subprocess.run(["which", "pdftotext"], capture_output=True).returncode:
        pytest.skip("pdftotext fehlt")
    m, _ = stufe6
    inhalt = pdf_erzeugen(seiten)
    pdf, txt = tmp_path / "probe.pdf", tmp_path / "probe.txt"
    pdf.write_bytes(inhalt)
    assert dokumente.extrahieren(pdf, txt, werkzeug) == len(seiten)
    text = txt.read_text(encoding="utf-8")
    assert text.count("\f") == len(seiten)
    neu, alt = amtskopf.text_auswerten(text, AEMTER), m.pdf_auswerten(inhalt, AEMTER)
    for spalte in ("treffer", "fundstelle", "kennung", "zeile", "abgleich", "stellen", "lage", "kandidaten",
                   "abschnitt_zeile", "seiten"):
        assert neu.get(spalte, "") == alt.get(spalte, ""), spalte
