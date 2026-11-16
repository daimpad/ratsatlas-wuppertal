"""Glossar: Beratungsrollen und Vorlagenarten aus Messstufe 5 (CLAUDE.md 9, 13.11. und 16.11.2026).

Geprüft wird gegen die Messergebnisse im Repository (explore/ergebnisse/oparl_beratungsrollen.tsv,
oparl_papertypen.tsv und oparl_laeufe.tsv, nur gelesen), gegen den Abgleich im Frontend (site/app.js `glossKeys`, in
tests/test_glossar.py nachgebildet), gegen die Seite begriffe/ und gegen Export und Vorgangsseite mit dem lokalen
Testserver (erfundene Daten, keine Anfrage an Server der Stadt). Jede Prüfung hat eine Gegenprobe."""
import csv
import json
import re
import sqlite3
from pathlib import Path

from pipeline import begriffsseite, build, config, export, gebietsseiten, glossar, process, sessionnet, vorgangsseiten, \
    vorlagenart

from test_glossar import _gloss_keys

ROOT = Path(__file__).resolve().parents[1]
ERG = ROOT / "explore" / "ergebnisse"
STRICHREIHE = "-" * 50


def _tsv(name):
    with open(ERG / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _rollen():
    """Gemessene Beratungsrollen ohne die Strichreihe (Platzhalter)."""
    return {z["role"]: int(z["anzahl"]) for z in _tsv("oparl_beratungsrollen.tsv") if process.rolle(z["role"])}


# Begriffe vor Messstufe 5 (Stand nach Phase 2, Teil 6); was hinzukommt, muss eine Wuppertaler Art, Ebene oder ein
# Wuppertaler Kürzel sein
BESTAND = {
    "Vorlage", "Vorlagennummer", "Beschlussvorlage", "Mitteilungsvorlage", "Antrag", "Änderungsantrag",
    "Stellungnahme der Verwaltung", "Anfrage", "Anregungen und Beschwerden (Bürgerantrag)", "Einwohnerantrag",
    "Einwohnerfragestunde", "Rat", "Bezirksvertretung", "Ausschuss", "Hauptausschuss", "Dringlichkeitsentscheidung",
    "Fraktion", "Öffentlichkeit von Sitzungen", "Federführendes Amt", "Beratungsfolge", "Tagesordnungspunkt",
    "Dringlichkeitsantrag", "Eilentscheidung (Hauptausschuss)", "Stand eines Vorgangs", "Quartier", "Stadtbezirk",
    "TOP", "GO NRW", "OB", "BV", "HA", "Bebauungsplan",
}
NEU_ARTEN = {"Große Anfrage", "Gemeinsamer Antrag", "Gemeinsame große Anfrage", "Bericht", "Antwort auf Anfragen",
             "Durchführungsbeschluss", "Grundsatzbeschluss", "Satzungsbeschluss"}
NEU_HINWEISE = {"Einreichende (aus der Vorlagenart abgeleitet)", "Ebene in der Vorlagenart", "AU"}
# Bonner Arten, Gruppen und Kürzel, die nicht neu erklärt werden (glossar.py Docstring, Phase 2 Teil 6)
BONNER = ("Informationsbrief", "Bürgerbrief", "Einwohnerfrage", "Beschlussvorlage: Einleitung", "Beschlussvorlage: "
          "Auftrag", "Sammelvorlage", "ST", "AA", "DA", "Produktbereich", "Haushalt", "Drucksachennummer")


def test_jede_gemessene_rolle_hat_glossareintrag():
    gemessen = _rollen()
    assert gemessen == {"Entgegennahme o. B.": 555, "Entscheidung": 497, "Empfehlung/Anhörung": 429,
                        "Kenntnisnahme": 2}
    g = json.loads(json.dumps(glossar.glossar(), ensure_ascii=False))   # wie glossar.json
    for rolle in gemessen:
        assert rolle in glossar.ROLLEN, rolle
        assert _gloss_keys(rolle, g["ergebnisse"]) == [rolle], rolle      # Abgleich wie site/app.js
        assert g["ergebnisse"][rolle].strip()
    # beobachtete Rollen stehen vorn, nach Häufigkeit; die übernommenen bleiben
    assert list(glossar.ROLLEN[:4]) == sorted(gemessen, key=gemessen.get, reverse=True)
    for rolle in ("Empfehlung", "Anhörung", "Genehmigung", "Eilentscheidung"):
        assert rolle in glossar.ROLLEN and rolle in glossar.ERGEBNISSE, rolle
    # Gegenprobe: die Strichreihe und ein unbekannter Wert treffen nichts
    assert _gloss_keys(STRICHREIHE, g["ergebnisse"]) == []
    assert _gloss_keys("[Testdaten] unbekannte Rolle", g["ergebnisse"]) == []


def test_beleg_je_rolle_passt_zur_messung():
    gemessen = _rollen()
    assert glossar.ROLLEN_GEMESSEN == gemessen
    strich = [z for z in _tsv("oparl_beratungsrollen.tsv") if not process.rolle(z["role"])]
    assert [int(z["anzahl"]) for z in strich] == [glossar.STRICHREIHE_GEMESSEN] == [24]
    m = glossar.MESSUNG_ROLLEN
    assert m["beratungen"] == sum(gemessen.values()) + glossar.STRICHREIHE_GEMESSEN
    lauf = next(z for z in _tsv("oparl_laeufe.tsv") if z["lauf"] == str(m["messlauf"]))
    assert (lauf["stufe"], lauf["kommando"], lauf["parameter"], lauf["ergebnis"]) == ("5", "stichprobe", "--seiten 8",
                                                                                       "ok")
    assert lauf["start"].startswith(m["datum"]) and m["kommando"] == f'{lauf["kommando"]} {lauf["parameter"]}'

    belege = glossar.glossar()["rollen_belege"]
    assert set(belege) == set(glossar.ROLLEN)
    for rolle, n in gemessen.items():
        b = belege[rolle]
        assert b["gemessen"] and b["messung"]["anzahl"] == n and b["beschriftung"] == "Fundstelle"
        assert "Wuppertal" in b["fundstelle"] and "abgerufen am 13.11.2026" in b["fundstelle"]
        # Geschäftsordnung nicht geprüft (wie OFFEN bei den Ergebnissen); keine Zählwerte im sichtbaren Text
        assert "noch nicht geprüft" in b["fundstelle"]
        for zahl in (n, m["vorlagen"], m["beratungen"]):
            assert not re.search(rf"\b{zahl}\b", b["fundstelle"]), (rolle, zahl)
    # „o. B.“ nur als Lesart gekennzeichnet
    assert "Lesart" in belege["Entgegennahme o. B."]["fundstelle"]
    assert "„ohne Beschluss“" in belege["Entgegennahme o. B."]["fundstelle"]
    # Gegenprobe: übernommene Rollen ohne Messung, als Herkunft beschriftet
    for rolle in ("Empfehlung", "Anhörung", "Genehmigung", "Eilentscheidung"):
        b = belege[rolle]
        assert not b["gemessen"] and "messung" not in b and b["beschriftung"] == "Herkunft"
        assert b["fundstelle"].startswith("in Wuppertal bisher nicht beobachtet")


def test_rollen_erklaerungen_vorsichtig():
    e = glossar.ERGEBNISSE
    t = e["Entgegennahme o. B."]
    assert "ohne Beschluss" in t and "gelesen" in t
    for rolle in glossar.ROLLEN_GEMESSEN:
        for wort in ("bindend", "rechtskräftig", "wirksam", "endgültig", "§", "immer", "stets"):
            assert wort not in e[rolle], (rolle, wort)
    assert "unterscheidet die Quelle nicht" in e["Empfehlung/Anhörung"]
    # Rolle und Ergebnis sind getrennte Schlüssel (anderes Feld der Quelle)
    assert "Entgegennahme ohne Beschluss" in e and e["Entgegennahme ohne Beschluss"] != t


def test_strichreihe_ist_keine_rolle():
    for wert in (STRICHREIHE, "-", " --- ", "–––", "——", "-–-", "−−"):
        assert process.rolle(wert) is None, wert
    for wert in (None, "", "   "):
        assert process.rolle(wert) is None
    # Gegenprobe: echte Rollen bleiben wörtlich, auch mit Strich im Wort
    for wert in ("Entgegennahme o. B.", "Empfehlung/Anhörung", "Vor-Beratung", "- Entscheidung -"):
        assert process.rolle(wert) == wert


def test_strichreihe_nicht_in_export_und_vorgangsseite(oparl):
    """Ende zu Ende mit dem lokalen Testserver: Vorlage 2 trägt die Strichreihe als Rolle, Vorlage 1 eine echte."""
    oparl.papers[1]["consultation"][0]["role"] = STRICHREIHE
    oparl.papers[0]["consultation"][0]["role"] = "Entgegennahme o. B."
    sessionnet.fetch_all()
    build.build()
    export.export()
    # Rohdaten bleiben unverändert: die Datenbank hält den Wert der Quelle
    db = sqlite3.connect(config.DB)
    roh = dict(db.execute("SELECT paper_id, role FROM consultation"))
    db.close()
    assert roh[oparl.papers[1]["id"]] == STRICHREIHE
    alle = {}
    for datei in (config.EXPORT / config.STADT).rglob("*.json"):
        for q in json.loads(datei.read_text(encoding="utf-8")).get("papers", []) if datei.parent.name in (
                "ortsteile", "bezirke", "ohne-ortsbezug") else []:
            alle[q["reference"]] = q
    strich, echt = alle[oparl.papers[1]["reference"]], alle[oparl.papers[0]["reference"]]
    beratung = lambda q: [s for s in q["steps"] if s["typ"] in ("beratung", "entscheidung")]
    assert beratung(strich) and all("role" not in s for s in beratung(strich))
    assert all(s.get("role") is None for s in strich["process"])
    for datei in config.EXPORT.rglob("*"):
        if datei.is_file() and datei.suffix in (".json", ".tsv", ".csv", ".xml", ".geojson"):
            assert "-----" not in datei.read_text(encoding="utf-8", errors="replace"), datei
    html = vorgangsseiten.body(strich, "ohne:2026", set(), {})
    assert "---" not in html and "()" not in html
    # Gegenprobe: eine echte Rolle erscheint auf der Vorgangsseite und im Akkordeon „Begriffe auf dieser Seite“
    assert [s.get("role") for s in beratung(echt)] == ["Entgegennahme o. B."]
    html = vorgangsseiten.body(echt, "ohne:2026", set(), {})
    assert "(Entgegennahme o. B.)" in html and 'begriffe/#rolle-entgegennahme-o-b' in html
    # glossar.json verweist die Vorlagenarten der Daten auf ihren Begriff, auch über die Zerlegung
    # („Antrag nach § 3“ der Testdaten → Art „Antrag“ nach Regel 4)
    g = json.loads((config.EXPORT / "glossar.json").read_text(encoding="utf-8"))
    assert g["arten"]["Beschlussvorlage"] == "beschlussvorlage" and g["arten"]["Antrag nach § 3"] == "antrag"


def test_jede_gemessene_vorlagenart_fuehrt_zu_einem_begriff():
    arten = [z["paperType"] for z in _tsv("oparl_papertypen.tsv")]
    assert len(arten) == 33
    begriffe = {b["begriff"] for b in glossar.glossar()["begriffe"]}
    ziele = {}
    for pt in arten:
        b = glossar.art_begriff(pt)
        assert b in begriffe, pt
        ziele[pt] = b
    assert ziele["Antrag FDP / WfW Rat AU"] == "Antrag" and ziele["Große Anfrage die Linke"] == "Große Anfrage"
    assert ziele["Gemeinsamer Antrag BV"] == "Gemeinsamer Antrag" and ziele["Anfrage SPD BV"] == "Anfrage"
    assert ziele["Gemeinsame große Anfrage"] == "Gemeinsame große Anfrage"
    assert ziele["Beschlussvorlage BV"] == "Beschlussvorlage" and ziele["Antwort auf Anfragen"] == "Antwort auf Anfragen"
    # die Art nach der Zerlegung führt zum selben Begriff wie der wörtliche Wert
    assert glossar.art_begriff(vorlagenart.zerlege("Gemeinsame große Anfrage")["art"]) == "Gemeinsame große Anfrage"
    # glossar.json mit den Vorlagenarten der Daten: jede gemessene Art hat einen Anker auf einen vorhandenen Begriff
    g = glossar.glossar(arten + ["[Testdaten] unbekannte Art"])
    anker = {b["anker"] for b in g["begriffe"]}
    assert all(g["arten"][pt] in anker for pt in arten)
    # Gegenprobe: unbekannte Arten erzeugen keinen Link; ohne Daten nur die allgemeinen Namen
    assert "[Testdaten] unbekannte Art" not in g["arten"] and glossar.art_begriff("Unbekannte Art") is None
    assert "Antrag CDU" not in glossar.glossar()["arten"]


def test_keine_bonner_begriffe_neu():
    g = glossar.glossar()
    begriffe = {b["begriff"]: b for b in g["begriffe"]}
    # nichts Bestehendes gelöscht
    assert BESTAND <= set(begriffe)
    # neu sind nur die Wuppertaler Arten, Ebene, Einreichende und das Kürzel AU
    assert set(begriffe) - BESTAND == NEU_ARTEN | NEU_HINWEISE
    for b in BONNER:
        assert b not in begriffe, b
    # jede neue Art ist Ziel mindestens einer gemessenen Vorlagenart
    gemessen = {glossar.art_begriff(z["paperType"]) for z in _tsv("oparl_papertypen.tsv")}
    assert NEU_ARTEN <= gemessen
    # neue Einträge nennen die Messung als Fundstelle, ohne Zählwerte und ohne Bonn
    for b in NEU_ARTEN | NEU_HINWEISE:
        f = begriffe[b]["fundstelle"]
        assert "Feld „paperType“" in f and "abgerufen am 13.11.2026" in f, b
        assert "Bonn" not in begriffe[b]["erklaerung"] + f
    assert begriffe["AU"]["gruppe"] == "kuerzel" and "offen" in begriffe["AU"]["erklaerung"]
    assert "offen" in begriffe["Ebene in der Vorlagenart"]["erklaerung"]
    for k in ("„Rat“", "„BV“", "„AU“", "„OB“"):
        assert k in begriffe["Ebene in der Vorlagenart"]["erklaerung"], k
    assert "aus der Vorlagenart abgeleitet" in begriffe["Einreichende (aus der Vorlagenart abgeleitet)"]["erklaerung"]
    # „OB“ in der Vorlagenart wird nicht als Oberbürgermeister gedeutet
    assert "Bedeutung offen" in begriffe["OB"]["erklaerung"]
    # Gegenprobe: die Prüfung findet einen Bonner Begriff, wenn er hinzukäme
    assert (set(begriffe) | {"Informationsbrief"}) - BESTAND != NEU_ARTEN | NEU_HINWEISE


def test_begriffsseite_zeigt_rollen_und_arten(tmp_path):
    begriffsseite.write(tmp_path, "https://wuppertal.ratsatlas.de/", gebietsseiten._page)
    html = (tmp_path / "begriffe" / "index.html").read_text(encoding="utf-8")
    abschnitt = html.split('<h2 id="rollen">', 1)[1].split("<h2 ", 1)[0]
    dts = re.findall(r'<dt id="([^"]+)">([^<]+)</dt>', abschnitt)
    assert [b for _, b in dts] == list(glossar.ROLLEN)
    assert ("rolle-entgegennahme-o-b", "Entgegennahme o. B.") in dts
    assert ("rolle-empfehlung-anhoerung", "Empfehlung/Anhörung") in dts
    assert abschnitt.count("Fundstelle: Ratsinformationssystem der Stadt Wuppertal") == 4
    assert abschnitt.count("Herkunft: in Wuppertal bisher nicht beobachtet") == len(dts) - 4
    assert "Reihe von Strichen" in abschnitt and "---" not in abschnitt
    # Gegenprobe: keine Zählwerte der Messung auf der Seite
    assert "555" not in html and "1507" not in html
    vorlagen = html.split('<h2 id="vorlagen">', 1)[1].split("<h2 ", 1)[0]
    for b in NEU_ARTEN | {"Einreichende (aus der Vorlagenart abgeleitet)", "Ebene in der Vorlagenart"}:
        assert f">{b}</dt>" in vorlagen, b
    assert ">AU</dt>" in html.split('<h2 id="kuerzel">', 1)[1].split("<h2 ", 1)[0]


def test_akkordeon_vorlagenart_ueber_zerlegung_und_rolle():
    acc = begriffsseite.akkordeon(["Antrag CDU", "Gemeinsamer Antrag BV"], "../", rollen=["Empfehlung/Anhörung"])
    assert 'href="../begriffe/#antrag"' in acc and 'href="../begriffe/#gemeinsamer-antrag"' in acc
    assert 'href="../begriffe/#rolle-empfehlung-anhoerung"' in acc and "Rolle: Empfehlung/Anhörung" in acc
    # Gegenprobe: Strichreihe als Rolle und unbekannte Art ergeben kein Akkordeon
    assert begriffsseite.akkordeon(["[Testdaten] unbekannt"], "../", rollen=[STRICHREIHE, None]) == ""
