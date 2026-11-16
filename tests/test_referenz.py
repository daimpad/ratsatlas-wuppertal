"""Vorlagennummern zerlegen und Folgevorlagen aus der Referenz ableiten (pipeline/referenz.py, CLAUDE.md 4.2).

Schreibweisen wie im Rohdaten-Cache (Messstufe 5, lokale Auswertung 16.11.2026), aber mit erfundenen Nummern, Titeln
und Vorlagen; ohne Netz (lokaler Testserver aus conftest.oparl), ohne Daten der Stadt."""
import json
import sqlite3

import pytest

from pipeline import build, config, export, process, publish, referenz, sessionnet, vorgangsseiten


# --- Zerlegen --------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ref, basis, zusatz, nummern, kuerzel", [
    ("VO/0123/24", "VO/0123/24", "", (), ()),
    ("VO/0123/24/1-A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24-A", "VO/0123/24", "A", (), ("A",)),
    ("VO/0123/24 - A", "VO/0123/24", "A", (), ("A",)),
    ("VO/0123/24-1-A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24 1-A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24\\1-A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24/1A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24-1A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24-1/A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24/A-1", "VO/0123/24", "A-1", (1,), ("A",)),
    ("VO/0123/24-A/1", "VO/0123/24", "A-1", (1,), ("A",)),
    ("VO/0123/24/I-A", "VO/0123/24", "1-A", (1,), ("A",)),
    ("VO/0123/24/2/A-1", "VO/0123/24", "2-A-1", (2, 1), ("A",)),
    ("VO/0123/241-A", "VO/0123/24", "1-A", (1,), ("A",)),         # fehlender Schrägstrich vor der Nummer
    ("VO/0123/24/1-Neuf.", "VO/0123/24", "1-Neuf.", (1,), ("Neuf.",)),
    ("VO/0123/24/Neuf.", "VO/0123/24", "Neuf.", (), ("Neuf.",)),
    ("VO/0123/24 Neuf.", "VO/0123/24", "Neuf.", (), ("Neuf.",)),
    ("VO/0123/24 - Neuf.", "VO/0123/24", "Neuf.", (), ("Neuf.",)),
    ("VO/0123/24/1. Neuf", "VO/0123/24", "1-Neuf.", (1,), ("Neuf.",)),
    ("VO/0123/24/1.Neuf.", "VO/0123/24", "1-Neuf.", (1,), ("Neuf.",)),
    ("VO/0123/24/1-A Neuf.", "VO/0123/24", "1-A-Neuf.", (1,), ("A", "Neuf.")),
    ("VO/0123/24/1-A-Neuf.", "VO/0123/24", "1-A-Neuf.", (1,), ("A", "Neuf.")),
    ("VO/0123/24/2-Erg.", "VO/0123/24", "2-Erg.", (2,), ("Erg.",)),
    ("VO/0123/24-Erg", "VO/0123/24", "Erg.", (), ("Erg.",)),
    ("VO/0123/24 - Erg.", "VO/0123/24", "Erg.", (), ("Erg.",)),
    (" vo / 123 / 24 /1-a", "VO/0123/24", "1-A", (1,), ("A",)),
])
def test_zerlegen(ref, basis, zusatz, nummern, kuerzel):
    r = referenz.zerlege(ref)
    assert (r.basis, r.zusatz, r.nummern, r.kuerzel, r.unbekannt) == (basis, zusatz, nummern, kuerzel, ())
    assert r.hat_zusatz == bool(zusatz)
    assert r.kanonisch == (f"{basis}/{zusatz}" if zusatz else basis)


@pytest.mark.parametrize("ref", ["", None, "1001/2026", "AN/101/2026", "VO/0123/2024", "VO/12345/24", "Vorlage"])
def test_andere_schemata_nicht_zerlegt(ref):
    assert referenz.zerlege(ref) is None


def test_unbekannter_zusatz_nicht_zuordenbar():
    r = referenz.zerlege("VO/0123/04 Öffentl.")
    assert r.unbekannt == ("Öffentl.",) and not r.zuordenbar
    assert not referenz.zerlege("VO/0123/04").zuordenbar


def test_bedeutung_nur_als_annahme():
    assert referenz.zusatz_text("1-A", ("A",)) == "Zusatz „1-A“ (A: vermutlich Antwort)"
    assert referenz.hinweis("VO/0123/24/1-A Neuf.") == ("aus der Referenz abgeleitet; Zusatz „1-A-Neuf.“ "
                                                         "(A: vermutlich Antwort; Neuf.: vermutlich Neufassung)")
    assert referenz.hinweis("VO/0123/24") == "aus der Referenz abgeleitet"
    assert all(v.startswith("vermutlich ") for v in referenz.KUERZEL.values())


# --- Zuordnung -------------------------------------------------------------------------------------------------------

def _v(i, ref):
    return {"id": f"http://oparl.invalid/papers/{i}", "reference": ref}


def test_zuordnung_nur_bei_eindeutiger_basis():
    vorlagen = [_v(1, "VO/0001/24"), _v(2, "VO/0001/24/1-A"),           # eindeutig
                _v(3, "VO/0002/24/1-A"),                                   # Basis fehlt
                _v(4, "VO/0003/24"), _v(5, "VO/0003/24 "), _v(6, "VO/0003/24/1-A"),   # Basis doppelt
                _v(7, "VO/0004/24"), _v(8, "VO/0004/24 Öffentl."),        # unbekannter Zusatz
                _v(9, "VO/0005/24"), _v(10, "VO/5/24 - Neuf."),            # Schreibvariante der Basis
                _v(11, "1001/2026"), _v(12, "")]
    z = referenz.zuordnung(vorlagen)
    assert {k: v["parent"] for k, v in z.items()} == {_v(2, "")["id"]: _v(1, "")["id"], _v(10, "")["id"]: _v(9, "")["id"]}
    assert z[_v(2, "")["id"]]["zusatz"] == "1-A" and z[_v(2, "")["id"]]["basis"] == "VO/0001/24"
    assert z[_v(2, "")["id"]]["evidence"] == ("aus der Referenz abgeleitet: VO/0001/24/1-A → VO/0001/24; "
                                              "Zusatz „1-A“ (A: vermutlich Antwort)")


def test_neufassung_einer_antwort_zuerst_zur_antwort():
    vorlagen = [_v(1, "VO/0007/24"), _v(2, "VO/0007/24/1-A"), _v(3, "VO/0007/24/1-A Neuf."),
                _v(4, "VO/0008/24"), _v(5, "VO/0008/24/1-A-Neuf.")]       # ohne Antwort: zur Basis
    z = referenz.zuordnung(vorlagen)
    assert z[_v(3, "")["id"]]["parent"] == _v(2, "")["id"] and z[_v(3, "")["id"]]["basis"] == "VO/0007/24/1-A"
    assert z[_v(2, "")["id"]]["parent"] == _v(1, "")["id"]
    assert z[_v(5, "")["id"]]["parent"] == _v(4, "")["id"]


def test_mehrere_zusaetze_zur_selben_basis():
    vorlagen = [_v(1, "VO/0009/24"), _v(2, "VO/0009/24/1-Erg."), _v(3, "VO/0009/24/2-Erg.")]
    z = referenz.zuordnung(vorlagen)
    assert {v["parent"] for v in z.values()} == {_v(1, "")["id"]} and len(z) == 2


# --- Einbindung: build, export, Prozesslinie, Vorgangsseite, Feeds ---------------------------------------------------

def _referenzen_setzen(oparl):
    """Erfundene Vorgänge: 1 Anfrage mit Antwort 2 (nur Referenz), 3 mit Neufassung 4 (zusätzlich in OParl verknüpft,
    wie in Wuppertal: Neufassung übergeordnet), 5 mit Zusatz ohne vorhandene Basis."""
    p = oparl.papers
    for q, ref, art in ((p[0], "VO/0101/26", "Große Anfrage (erfunden)"),
                        (p[1], "VO/0101/26/1-A", "Antwort auf Anfragen"),
                        (p[2], "VO/0102/26", "Beschlussvorlage"),
                        (p[3], "VO/0102/26/1-Neuf.", "Beschlussvorlage"),
                        (p[4], "VO/0199/26 - Erg.", "Bericht")):
        q["reference"], q["paperType"] = ref, art
    p[1]["date"] = "2026-09-25"
    p[3]["subordinatedPaper"] = [p[2]["id"]]
    p[2]["superordinatedPaper"] = [p[3]["id"]]


def _export_vorlagen():
    alle = {}
    for datei in (config.EXPORT / config.STADT).rglob("*.json"):
        if datei.parent.name not in ("ortsteile", "bezirke", "ohne-ortsbezug"):
            continue
        for q in json.loads(datei.read_text(encoding="utf-8")).get("papers", []):
            alle[q["reference"]] = q
    return alle


def test_abgeleitete_folgevorlage_im_export(oparl):
    _referenzen_setzen(oparl)
    sessionnet.fetch_all()
    build.build()
    db = sqlite3.connect(config.DB)
    rel = {(r[0].rsplit("/", 1)[1], r[1].rsplit("/", 1)[1]): r[2:] for r in db.execute(
        "SELECT parent_id, child_id, method, derived, evidence FROM paper_relation")}
    db.close()
    # 1 → 2 abgeleitet; 3/4 nur aus OParl (keine zweite, abgeleitete Verknüpfung); 5 ohne Basis
    assert rel == {("1", "2"): ("referenz", 1, "aus der Referenz abgeleitet: VO/0101/26/1-A → VO/0101/26; "
                                              "Zusatz „1-A“ (A: vermutlich Antwort)"),
                   ("4", "3"): ("oparl", 0, None)}
    export.export()
    alle = _export_vorlagen()
    anfrage, antwort = alle["VO/0101/26"], alle["VO/0101/26/1-A"]
    hinweis = "aus der Referenz abgeleitet; Zusatz „1-A“ (A: vermutlich Antwort)"
    assert anfrage["subordinated"] == [{"reference": "VO/0101/26/1-A", "paper_type": "Antwort auf Anfragen",
                                        "date": "2026-09-25", "name": antwort["name"], "derived": True,
                                        "method": "referenz", "hinweis": hinweis}]
    assert antwort["superordinated"][0]["derived"] is True and antwort["superordinated"][0]["hinweis"] == hinweis
    # OParl-Bezüge ohne Kennzeichnung
    assert alle["VO/0102/26"]["superordinated"] == [{"reference": "VO/0102/26/1-Neuf.", "paper_type": "Beschlussvorlage",
                                                      "date": "2026-09-20", "name": alle["VO/0102/26/1-Neuf."]["name"]}]
    assert not alle["VO/0199/26 - Erg."]["superordinated"]
    # Prozesslinie: Folgevorlage „abgeleitet“ mit Hinweis
    folge = [s for s in anfrage["steps"] if s["typ"] == "folgevorlage"]
    assert folge == [{"typ": "folgevorlage", "label": "Antwort auf Anfragen", "status": "abgeleitet",
                      "date": "2026-09-25", "source": config.QUELLE_OPARL, "reference": "VO/0101/26/1-A",
                      "title": antwort["name"], "method": "referenz", "hinweis": hinweis, "note": "referenz"}]
    assert "nicht dokumentiert" in process.NOTES["referenz"] and "Annahme" in process.NOTES["referenz"]
    oparl_folge = [s for s in alle["VO/0102/26/1-Neuf."]["steps"] if s["typ"] == "folgevorlage"]
    assert oparl_folge and oparl_folge[0]["status"] == "belegt" and "hinweis" not in oparl_folge[0]
    # Vorgangsseiten: beide Richtungen gekennzeichnet, OParl-Bezug nicht
    html = vorgangsseiten.body(anfrage, "ohne:2026", set(), {})
    assert "<h2>Folgevorlagen</h2>" in html and "abgeleitet</span>" in html and hinweis in html
    assert hinweis in vorgangsseiten.body(antwort, "ohne:2026", set(), {})
    assert "pb-abgeleitet" not in vorgangsseiten.body(alle["VO/0102/26"], "ohne:2026", set(), {}).split(
        "<h2>Bezieht sich auf</h2>")[1]
    # Feed: Folgevorlage mit Hinweis
    eintraege = [e for e in publish.events(anfrage, with_followups=True) if "#folge-" in e["id"]]
    assert eintraege and eintraege[0]["summary"] == f"Folgevorlage zu VO/0101/26 ({hinweis})"
