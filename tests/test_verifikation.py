"""Verifikation (pipeline/verifikation.py, Phase 6, 23.11.2026): Stichprobe gegen die OParl-API nur gegen den lokalen
Testserver (synthetische Daten), eine Anfrage je Vorlage, Befunde je Feld, Abbruch und Sperrvermerk, Prüfliste."""
import csv
import json

from pipeline import build, config, sessionnet, verifikation


def _tsv(name):
    with open(config.EXPORT / name, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _vorbereiten(oparl):
    sessionnet.fetch_all()
    build.build()
    oparl.anfragen.clear()


def test_alles_gleich_eine_anfrage_je_vorlage(oparl):
    _vorbereiten(oparl)
    meta = verifikation.verifizieren(n=5, seed=1)
    assert meta["stichprobe"] == meta["geprueft"] == meta["uebereinstimmend"] == 5 and meta["ende"] == "vollständig"
    pfade = [p for p, _, _ in oparl.anfragen]
    assert len(pfade) == 5 and all(p.startswith("/papers/") for p in pfade)
    zeilen = _tsv(verifikation.TSV)
    assert {z["feld"] for z in zeilen} == {"reference", "name", "date", "paper_type", "under_direction_of",
                                           "beratungen", "anlagen"}
    assert all(z["ergebnis"] == "ok" for z in zeilen)
    assert json.loads((config.EXPORT / verifikation.JSON).read_text())["seed"] == 1
    pruef = _tsv(verifikation.PRUEF_TSV)
    assert len(pruef) == 5 and pruef[0]["nr"] == "1" and all(z["beratungsfolge"] for z in pruef)


def test_abweichung_und_aenderung_seit_dem_abruf(oparl):
    _vorbereiten(oparl)
    # Titel ohne neues `modified`: abweichend; Titel mit neuerem `modified`: seit dem Abruf geändert
    oparl.papers[0] = oparl.paper(1, name="Anderer Titel")
    oparl.papers[1] = oparl.paper(2, name="Neu gefasst", modified="2026-11-01T10:00:00+01:00")
    meta = verifikation.verifizieren(n=5, seed=1)
    assert (meta["uebereinstimmend"], meta["abweichend"], meta["geaendert"]) == (3, 1, 1)
    namen = {z["drucksache"]: z["ergebnis"] for z in _tsv(verifikation.TSV) if z["feld"] == "name"}
    assert namen["1001/2026"] == "abweichend" and namen["AN/102/2026"] == "seit dem Abruf geändert"


def test_404_ist_befund_anderer_abbruch_beendet_und_vermerkt(oparl, monkeypatch):
    _vorbereiten(oparl)
    ids = [f"{oparl.b}/papers/{i}" for i in (1, 2, 3)]
    monkeypatch.setattr(verifikation, "_stichprobe", lambda db, n, seed: ids)
    status = {"/papers/1": 404, "/papers/2": 403}
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: status.get(pfad, False))
    meta = verifikation.verifizieren(seed=1)
    assert meta["geprueft"] == 1 and meta["fehler"] == 1 and meta["ende"] == "abgebrochen (http)"
    assert [p for p, _, _ in oparl.anfragen] == ["/papers/1", "/papers/2"]   # nach dem Abbruch keine Anfrage mehr
    zustand = json.loads(config.ZUSTAND.read_text())
    assert zustand["sperre_verdacht"]["naechte"] == 1 and "Verifikation" in zustand["letzter_abbruch"]["meldung"]


def test_ohne_gepruefte_vorlage_bleiben_fruehere_ergebnisse(oparl, monkeypatch):
    _vorbereiten(oparl)
    (config.EXPORT).mkdir(parents=True, exist_ok=True)
    (config.EXPORT / verifikation.TSV).write_text("frueher\n", encoding="utf-8")
    monkeypatch.setattr(oparl, "stoerung", lambda pfad, q: 403 if pfad.startswith("/papers/") else False)
    assert verifikation.verifizieren(n=2, seed=1) is None
    assert (config.EXPORT / verifikation.TSV).read_text() == "frueher\n"


def test_ohne_vollstaendigen_abruf_keine_anfrage(oparl):
    _vorbereiten(oparl)
    stand = json.loads(config.STAND.read_text())
    config.STAND.write_text(json.dumps({**stand, "abruf_hinweis": {"meldung": "Zeitfenster"}}))
    assert verifikation.verifizieren(n=2, seed=1) is None and not oparl.anfragen


def test_wiederholte_beratungskennung_bleibt_je_sitzung_erhalten(oparl):
    # Wuppertal: dieselbe Beratungskennung erneut in einer späteren Sitzung (Verifikation 23./24.11.2026: 3 von 50
    # Vorlagen mit weniger Beratungen als die Quelle, weil die spätere Sitzung die frühere überschrieb)
    b = oparl.b
    oparl.meetings.append({"id": f"{b}/meetings/2", "name": "Rat", "start": "2026-11-05T16:00:00+01:00",
                           "organization": [f"{b}/organizations/rat"], "modified": "2026-11-06T08:00:00+01:00",
                           "agendaItem": [{"id": f"{b}/agendaitems/21", "number": "3", "name": "TOP 3",
                                           "result": "vertagt", "public": True}]})
    erste = dict(oparl.papers[0]["consultation"][0])
    oparl.papers[0]["consultation"].append({**erste, "meeting": f"{b}/meetings/2", "agendaItem": f"{b}/agendaitems/21"})
    _vorbereiten(oparl)
    import sqlite3
    db = sqlite3.connect(config.DB)
    zeilen = db.execute("SELECT id, meeting_id, agenda_item_id FROM consultation WHERE paper_id = ? ORDER BY position",
                        (f"{b}/papers/1",)).fetchall()
    db.close()
    assert zeilen == [(erste["id"], f"{b}/meetings/1", f"{b}/agendaitems/1"),
                      (erste["id"] + "#2", f"{b}/meetings/2", f"{b}/agendaitems/21")]
    meta = verifikation.verifizieren(n=5, seed=1)
    assert meta["uebereinstimmend"] == 5


def test_beratung_schluessel():
    from pipeline.sessionnet import beratung_schluessel
    assert beratung_schluessel([{"id": "a"}, {"id": "b"}, {"id": "a"}, {}, "x", {"id": "a"}]) == \
        ["a", "b", "a#2", None, None, "a#3"]
    assert beratung_schluessel(None) == []
