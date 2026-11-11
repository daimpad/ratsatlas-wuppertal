"""Änderungsprotokoll der Vorlagen (CLAUDE.md 5.1, pipeline/aenderungen.py) gegen den lokalen OParl-Testserver: zwei
Läufe mit geänderten Testdaten, erster Lauf ohne Einträge, Datenschutz (keine Dateinamen), Anzeige „Unterlagen geändert
am …“ in Export und Vorgangsseite. Keine Anfrage an Server der Stadt; alle Werte erfunden."""
import csv
import itertools
import json
from datetime import datetime, timedelta

from pipeline import aenderungen, build, config, export, sessionnet, vorgangsseiten

NAME = "Stellungnahme Erika Mustermann"           # erfundener Personenname im Dateinamen (darf nirgends erscheinen)
DATEINAME = "Mustermann_Erika_Stellungnahme.pdf"


def _zeilen():
    with open(config.AENDERUNGEN, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, **aenderungen.TSV))


def _datei(oparl, n, **mehr):
    """Erfundene Anlage im Wuppertaler Muster (CLAUDE.md 3.1: nur auxiliaryFile, accessUrl …/downloadfiles/a/<n>.pdf)."""
    return {"id": f"{oparl.b}/files/{n}", "type": "https://schema.oparl.org/1.1/File", "name": NAME,
            "fileName": DATEINAME, "mimeType": "application/pdf", "size": 1000 + n,
            "accessUrl": f"{oparl.b}/downloadfiles/a/{n}.pdf", "downloadUrl": f"{oparl.b}/downloadfiles/{n}.pdf",
            "text": "Volltext, darf nicht erscheinen", **mehr}


_SEKUNDE = itertools.count(1)


def _jetzt():
    """Änderungszeitpunkt nach dem letzten Abruf (der inkrementelle Abruf holt ihn über modified_since), je Aufruf
    eine Sekunde später, damit jede Änderung ein neues modified trägt."""
    zeit = datetime.fromisoformat(json.loads(config.ZUSTAND.read_text())["papers"])
    return (zeit + timedelta(seconds=next(_SEKUNDE))).isoformat(timespec="seconds")


def _lauf(zeit=None):
    sessionnet.fetch_all()
    return aenderungen.protokollieren(zeit)


def _aendern(oparl, i, **felder):
    p = oparl.papers[i - 1]
    p.update(felder)
    p["modified"] = _jetzt()
    return p


def test_erster_lauf_ohne_eintraege_dann_unveraendert(oparl):
    assert _lauf() == 0
    assert config.VORSTAND.exists()
    assert config.AENDERUNGEN.read_text(encoding="utf-8") == "\t".join(aenderungen.SPALTEN) + "\n"
    assert aenderungen.unterlagen_geaendert() == {}
    # zweiter Lauf ohne Änderung in der Quelle und derselbe Schritt doppelt: keine Zeile
    assert _lauf() == 0
    assert aenderungen.protokollieren() == 0
    assert _zeilen() == []


def test_nachgereichte_datei_ohne_dateinamen_im_protokoll(oparl):
    _lauf()
    p = _aendern(oparl, 2, auxiliaryFile=[_datei(oparl, 7)])
    anfragen = len(oparl.anfragen)
    sessionnet.fetch_all()
    assert len(oparl.anfragen) > anfragen
    anfragen = len(oparl.anfragen)
    assert aenderungen.protokollieren() == 2
    assert len(oparl.anfragen) == anfragen          # der Schritt selbst sendet keine Anfrage
    zeilen = _zeilen()
    assert {z["quellobjekt"] for z in zeilen} == {p["id"]}    # keine Zeile für andere Vorlagen
    assert {z["vorlage"] for z in zeilen} == {p["reference"]}
    felder = {z["feld"]: z for z in zeilen}
    assert set(felder) == {"modified", "auxiliaryFile"}
    assert felder["modified"]["alt"] == "2026-10-01T10:00:00+02:00" and felder["modified"]["neu"] == p["modified"]
    assert felder["auxiliaryFile"]["alt"] == "0 Dateien"
    assert felder["auxiliaryFile"]["neu"] == f"1 Datei: {oparl.b}/files/7"
    assert len({z["zeitpunkt"] for z in zeilen}) == 1
    # Datenschutz (CLAUDE.md 2): weder Dateiname noch Volltext im Protokoll oder im Vorstand
    for datei in (config.AENDERUNGEN, config.VORSTAND):
        text = datei.read_text(encoding="utf-8")
        assert "Mustermann" not in text and "Erika" not in text and "Volltext" not in text, datei.name
    assert aenderungen.unterlagen_geaendert() == {p["id"]: aenderungen._tag(p["modified"])}


def test_gegenprobe_name_im_fingerabdruck_faellt_auf(oparl, monkeypatch):
    """Die Prüfung auf Namen greift: nimmt der Fingerabdruck den Dateinamen auf, steht er im Vorstand."""
    monkeypatch.setattr(aenderungen, "FINGERABDRUCK", aenderungen.FINGERABDRUCK + ("fileName",))
    _lauf()
    _aendern(oparl, 2, auxiliaryFile=[_datei(oparl, 7)])
    _lauf()
    assert "Mustermann" in config.VORSTAND.read_text(encoding="utf-8")


def test_ersetzt_umbenannt_entfernt(oparl):
    oparl.papers[1]["auxiliaryFile"] = [_datei(oparl, 7), _datei(oparl, 8)]
    _lauf()
    # ersetzt: gleiche Kennung, andere Größe und Adresse
    _aendern(oparl, 2, auxiliaryFile=[_datei(oparl, 7, size=5555, accessUrl=f"{oparl.b}/downloadfiles/a/99.pdf"),
                                      _datei(oparl, 8)])
    assert _lauf() == 2
    z = {x["feld"]: x for x in _zeilen()}["auxiliaryFile.angaben"]
    assert z["alt"] == f"{oparl.b}/files/7: accessUrl {oparl.b}/downloadfiles/a/7.pdf, size 1007"
    assert z["neu"] == f"{oparl.b}/files/7: accessUrl {oparl.b}/downloadfiles/a/99.pdf, size 5555"
    # nur umbenannt: Zeile ohne den Namen
    _aendern(oparl, 2, auxiliaryFile=[_datei(oparl, 7, size=5555, accessUrl=f"{oparl.b}/downloadfiles/a/99.pdf"),
                                      _datei(oparl, 8, name="Anlage Max Mustermann", fileName="Max.pdf")])
    assert _lauf() == 2
    z = {x["feld"]: x for x in _zeilen()[-2:]}["auxiliaryFile.angaben"]
    assert z["neu"] == f"{oparl.b}/files/8: Dateiname geändert (nicht protokolliert)"
    assert "Max" not in config.AENDERUNGEN.read_text(encoding="utf-8")
    # entfernt
    _aendern(oparl, 2, auxiliaryFile=[_datei(oparl, 8, name="Anlage Max Mustermann", fileName="Max.pdf")])
    assert _lauf() == 2
    z = {x["feld"]: x for x in _zeilen()[-2:]}["auxiliaryFile"]
    assert (z["alt"], z["neu"]) == (f"2 Dateien: {oparl.b}/files/7 | {oparl.b}/files/8", f"1 Datei: {oparl.b}/files/8")
    # Zeilen bleiben über die Läufe erhalten (Anhängen statt Überschreiben)
    assert len(_zeilen()) == 6


def test_beratungsfolge_und_nur_modified(oparl):
    _lauf()
    b = oparl.b
    c = oparl.papers[2]["consultation"][0]
    neu = {"id": f"{b}/consultations/30", "meeting": f"{b}/meetings/1", "agendaItem": f"{b}/agendaitems/3",
           "role": "Entgegennahme o. B.", "authoritative": False, "organization": [f"{b}/organizations/rat"]}
    _aendern(oparl, 3, consultation=[dict(c), neu])
    assert _lauf() == 2
    z = {x["feld"]: x for x in _zeilen()}["consultation"]
    assert z["alt"] == (f"1 Beratung: {b}/consultations/3 (Rolle Entscheidung; Sitzung {b}/meetings/1; "
                        f"TOP {b}/agendaitems/3; abschließend)")
    assert z["neu"].startswith("2 Beratungen: ") and f"{b}/consultations/30 (Rolle Entgegennahme o. B.; Gremium " \
        f"{b}/organizations/rat; Sitzung {b}/meetings/1; TOP {b}/agendaitems/3)" in z["neu"]
    # andere Rolle
    _aendern(oparl, 3, consultation=[dict(c, role="Vorberatung"), neu])
    assert _lauf() == 2 and _zeilen()[-1]["feld"] == "consultation"
    # anderes Ergebnis eines TOPs (steht in der Sitzung): keine Zeile
    oparl.meetings[0]["agendaItem"][2]["result"] = "vertagt"
    oparl.meetings[0]["modified"] = _jetzt()
    assert _lauf() == 0
    assert json.loads(config.BERATUNGEN.read_text().splitlines()[2])["agendaItem"]["result"] == "vertagt"
    # nur modified: Zeile, aber kein „Unterlagen geändert“
    _aendern(oparl, 4)
    assert _lauf() == 1 and _zeilen()[-1]["feld"] == "modified"
    assert aenderungen.unterlagen_geaendert() == {}
    # Gremium der Sitzung geändert: Das aus der Sitzung ergänzte Gremium (_organization_quelle) stammt nicht aus der
    # Vorlage und zählt nicht; Vorlage 5 wird dabei neu abgerufen und neu ergänzt
    oparl.meetings[0]["organization"] = [f"{b}/organizations/rat"]
    oparl.meetings[0]["modified"] = _jetzt()
    _aendern(oparl, 5)
    assert _lauf() == 1 and _zeilen()[-1]["feld"] == "modified"
    papers = [json.loads(z) for z in config.PAPERS.read_text().splitlines()]
    assert next(p for p in papers if p["id"].endswith("/papers/5"))["consultation"][0]["organization"] == [f"{b}/organizations/rat"]


def test_neue_vorlage_ohne_zeile(oparl):
    _lauf()
    oparl.papers.append(oparl.paper(6, modified=_jetzt()))
    assert _lauf() == 0
    assert f"{oparl.b}/papers/6" in json.loads(config.VORSTAND.read_text())["vorlagen"]


def _rohdaten(*papers):
    config.RAW.mkdir(parents=True, exist_ok=True)
    config.PAPERS.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in papers), encoding="utf-8")


def test_tag_in_berlin_und_aus_der_quelle(oparl):
    """Tag der Anzeige: Lauf um 23:30 UTC ist in Berlin der nächste Tag (Gegenprobe: UTC ergäbe den 12.); mit neuem
    modified der Vorlage im selben Lauf dessen Tag, außer es liegt nach dem Lauf."""
    p = oparl.paper(1)
    _rohdaten(p)
    aenderungen.protokollieren("2026-11-10T22:00:00+00:00")
    _rohdaten({**p, "auxiliaryFile": [_datei(oparl, 1)]})
    assert aenderungen.protokollieren("2026-11-12T23:30:00+00:00") == 1
    assert aenderungen.unterlagen_geaendert() == {p["id"]: "2026-11-13"}
    _rohdaten({**p, "auxiliaryFile": [_datei(oparl, 2)], "modified": "2026-11-14T08:00:00+01:00"})
    aenderungen.protokollieren("2026-11-14T22:30:00+00:00")
    assert aenderungen.unterlagen_geaendert() == {p["id"]: "2026-11-14"}
    # modified nach dem Lauf (Uhr der Quelle vorgestellt): Tag des Laufs
    _rohdaten({**p, "auxiliaryFile": [_datei(oparl, 3)], "modified": "2026-12-01T08:00:00+01:00"})
    aenderungen.protokollieren("2026-11-20T10:00:00+00:00")
    assert aenderungen.unterlagen_geaendert() == {p["id"]: "2026-11-20"}


def test_tabulator_und_zeilenumbruch_werden_ersetzt(oparl):
    p = oparl.paper(1)
    _rohdaten(p)
    aenderungen.protokollieren()
    c = dict(p["consultation"][0], role="Ent\tscheidung\nneu\r")
    _rohdaten({**p, "consultation": [c], "modified": "2026-11-01T\t10:00"})
    assert aenderungen.protokollieren() == 2
    zeilen = config.AENDERUNGEN.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3 and all(z.count("\t") == len(aenderungen.SPALTEN) - 1 for z in zeilen)
    assert "Rolle Ent scheidung neu " in zeilen[-1]


def test_alle_zeilenenden_ersetzt_und_ohne_anfuehrungszeichen(oparl):
    """Zeilenenden außer \\n und \\r (\\v, \\f, \\x1c–\\x1e, \\x85, U+2028, U+2029) teilen sonst in zeilenweisen Lesern
    (str.splitlines) den Datensatz; ASCII-Anführungszeichen erscheinen unverändert, ohne CSV-Maskierung (cut, awk)."""
    p = oparl.paper(1)
    _rohdaten(p)
    aenderungen.protokollieren()
    rolle = 'Ent\x0bschei\x0cdung\x1c\x1d\x1e\x85\u2028\u2029"q"'
    _rohdaten({**p, "consultation": [dict(p["consultation"][0], role=rolle)], "modified": '"2026-11-01"'})
    assert aenderungen.protokollieren() == 2
    zeilen = config.AENDERUNGEN.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3 and all(z.count("\t") == len(aenderungen.SPALTEN) - 1 for z in zeilen)
    assert "Rolle Ent schei dung" + " " * 6 + '"q";' in zeilen[-1]
    assert zeilen[-2].split("\t")[3] == '"2026-11-01"'       # Feld „neu“ wörtlich, nicht als „\"\"2026…\"\"“
    assert {z["feld"]: z["neu"] for z in _zeilen()}["modified"] == '"2026-11-01"'


def test_abbruch_bei_sitzungen_ohne_scheinaenderung(oparl, monkeypatch):
    """Abruf bricht nach den Vorlagen ab (Sitzungen gestört): Die neu geholte Vorlage steht ohne das aus der Sitzung
    ergänzte Gremium in papers.jsonl. Das darf keine Zeile „consultation“ erzeugen, weder in diesem noch im nächsten
    vollständigen Lauf; nur die echte Änderung (modified) erscheint, und zwar einmal."""
    b = oparl.b
    oparl.meetings[0]["organization"] = [f"{b}/organizations/rat"]   # Gremium nur in der Sitzung
    _lauf()
    roh = [json.loads(z) for z in config.PAPERS.read_text().splitlines()]
    assert next(p for p in roh if p["id"].endswith("/papers/2"))["consultation"][0]["_organization_quelle"] == "sitzung"
    _aendern(oparl, 2)
    with monkeypatch.context() as m:
        m.setattr(oparl, "stoerung", lambda pfad, q: pfad == "/meetings")
        sessionnet.fetch_all()
        stand = json.loads(config.STAND.read_text())
        assert "abruf_fehler" in stand
        roh = [json.loads(z) for z in config.PAPERS.read_text().splitlines()]
        assert "_organization_quelle" not in next(p for p in roh if p["id"].endswith("/papers/2"))["consultation"][0]
        assert aenderungen.protokollieren() == 1
    # nächste Nacht, vollständiger Lauf (der Abbruch sperrt sonst die Nacht, sessionnet.SPERRE_GLEICHE_NACHT)
    zustand = json.loads(config.ZUSTAND.read_text())
    zustand.pop("letzter_abbruch", None)
    config.ZUSTAND.write_text(json.dumps(zustand))
    assert _lauf() == 0
    assert [z["feld"] for z in _zeilen()] == ["modified"]


def test_ergaenztes_und_fehlendes_gremium_sind_gleich(oparl):
    """Gegenprobe ohne Abruf: Eintrag mit aus der Sitzung ergänztem Gremium gegen denselben ohne Ergänzung."""
    p = oparl.paper(1)
    c = p["consultation"][0]
    ergaenzt = {**p, "consultation": [dict(c, organization=[f"{oparl.b}/organizations/rat"],
                                           _organization_quelle="sitzung")]}
    roh = {**p, "consultation": [{k: v for k, v in c.items() if k != "organization"}]}
    assert aenderungen.vergleich(p["id"], aenderungen.eintrag(ergaenzt), aenderungen.eintrag(roh), "z") == []
    assert aenderungen.vergleich(p["id"], aenderungen.eintrag(roh), aenderungen.eintrag(ergaenzt), "z") == []


def test_unlesbarer_vorstand_wird_beiseitegelegt(oparl, capsys):
    _rohdaten(oparl.paper(1))
    config.VORSTAND.write_text("{kaputt", encoding="utf-8")
    assert aenderungen.protokollieren() == 0
    assert config.VORSTAND.with_name(config.VORSTAND.name + ".defekt").read_text() == "{kaputt"
    assert "unlesbar" in capsys.readouterr().err
    assert json.loads(config.VORSTAND.read_text())["vorlagen"]


def test_geloeschte_vorlage_ohne_zeile(oparl):
    p = oparl.paper(1)
    _rohdaten(p)
    aenderungen.protokollieren()
    _rohdaten({**p, "deleted": True, "modified": "2026-11-01T10:00:00+01:00", "auxiliaryFile": []})
    assert aenderungen.protokollieren() == 0
    assert json.loads(config.VORSTAND.read_text())["vorlagen"] == {}


def test_ohne_rohdaten_nichts(oparl):
    assert aenderungen.protokollieren() == 0
    assert not config.VORSTAND.exists() and not config.AENDERUNGEN.exists()


def test_anzeige_in_export_und_vorgangsseite(oparl):
    _lauf()
    p = _aendern(oparl, 2, auxiliaryFile=[_datei(oparl, 7)])
    _lauf()
    build.build()
    export.export()
    alle = {}
    for datei in (config.EXPORT / config.STADT).rglob("*.json"):
        for q in json.loads(datei.read_text(encoding="utf-8")).get("papers", []) if datei.parent.name in (
                "ortsteile", "bezirke", "ohne-ortsbezug") else []:
            alle[q["reference"]] = q
    assert alle, "keine Vorlagen im Export"
    tag = aenderungen._tag(p["modified"])
    assert {r: q["unterlagen_geaendert"] for r, q in alle.items() if "unterlagen_geaendert" in q} == {p["reference"]: tag}
    html = vorgangsseiten.body(alle[p["reference"]], "ohne:2026", set(), {})
    assert f"<dt>Unterlagen</dt><dd>geändert am {tag[8:10]}.{tag[5:7]}.{tag[:4]}" in html
    assert vorgangsseiten.UNTERLAGEN_TEXT in html
    andere = next(q for r, q in alle.items() if r != p["reference"])
    assert "<dt>Unterlagen</dt>" not in vorgangsseiten.body(andere, "ohne:2026", set(), {})
    assert vorgangsseiten.lastmod(alle[p["reference"]]) == max(tag, alle[p["reference"]]["date"])
    # Protokoll im Export (Datenpaket): ohne Dateinamen
    assert "Mustermann" not in config.AENDERUNGEN.read_text(encoding="utf-8")
