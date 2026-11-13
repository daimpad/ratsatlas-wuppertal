"""Glossar: Beschlussergebnisse aus Messstufe 4 (CLAUDE.md 9, 13.11.2026 (4)).

Geprüft wird gegen die Messergebnisse im Repository (explore/ergebnisse/oparl_top_ergebnisse.tsv und
oparl_laeufe.tsv, nur gelesen), gegen den Abgleich im Frontend (site/app.js `glossKeys`, hier in Python nachgebildet)
und gegen die Seite begriffe/. Jede Prüfung hat eine Gegenprobe. Ohne Netz, ohne Daten der Stadt außer den
gemessenen Ergebniswörtern."""
import csv
import json
import re
from pathlib import Path

from pipeline import begriffsseite, gebietsseiten, glossar

ROOT = Path(__file__).resolve().parents[1]
ERG = ROOT / "explore" / "ergebnisse"


def _tsv(name):
    with open(ERG / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _gemessen():
    """Ergebniswerte aus Stufe 4 (ohne Kennzahlzeilen wie „(leer)“, „public=True“, „TOPs …“)."""
    out = {}
    for z in _tsv("oparl_top_ergebnisse.tsv"):
        r = z["result"]
        if r == "(leer)" or "=" in r or r.startswith(("TOPs ", "Sitzungen ")):
            continue
        out[r] = int(z["anzahl"])
    return out


def _gloss_keys(text, gloss):
    """Nachbildung von site/app.js: t.split(" - ").map(trim).filter(GLOSSAR[x])."""
    return [x.strip() for x in text.split(" - ") if x.strip() in gloss] if text else []


def test_frontend_abgleich_unveraendert():
    """Die Nachbildung passt nur, solange app.js wörtlich so abgleicht (Gegenprobe zur Nachbildung)."""
    js = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    assert 'const glossKeys = (t) => (t ? t.split(" - ").map((x) => x.trim()).filter((x) => GLOSSAR[x]) : []);' in js
    assert "ergebnisse: GLOSSAR" in js


def test_messwerte_haben_glossareintrag():
    gemessen = _gemessen()
    assert gemessen == {"ungeändert beschlossen": 18, "geändert beschlossen": 2, "abgelehnt": 1,
                        "Entgegennahme ohne Beschluss": 1}
    g = json.loads(json.dumps(glossar.glossar(), ensure_ascii=False))   # wie glossar.json
    for wert in gemessen:
        assert _gloss_keys(wert, g["ergebnisse"]) == [wert], wert
        assert g["ergebnisse"][wert].strip()
    # Gegenprobe: ein unbekannter Wert und eine Abkürzung der Rolle treffen nichts (Rollen erst nach Stufe 5)
    assert _gloss_keys("[Testdaten] unbekanntes Ergebnis", g["ergebnisse"]) == []
    assert _gloss_keys("Entgegennahme o. B.", g["ergebnisse"]) == []
    # zusammengesetzte Ergebnisse wie in Bonn („… - mit Protokollnotiz“) werden weiter zerlegt
    assert _gloss_keys("geändert beschlossen - mit Protokollnotiz", g["ergebnisse"]) == ["geändert beschlossen",
                                                                                         "mit Protokollnotiz"]


def test_beleg_je_ergebnis_passt_zur_messung():
    gemessen = _gemessen()
    assert glossar.ERGEBNISSE_GEMESSEN == gemessen
    kennzahl = {z["result"]: int(z["anzahl"]) for z in _tsv("oparl_top_ergebnisse.tsv")}
    m = glossar.MESSUNG_ERGEBNISSE
    assert m["tops_mit_ergebnis"] == kennzahl["TOPs mit result"] == sum(gemessen.values())
    assert m["tops_insgesamt"] == kennzahl["TOPs insgesamt"] and m["sitzungen"] == kennzahl["Sitzungen insgesamt"]
    lauf = next(z for z in _tsv("oparl_laeufe.tsv") if z["lauf"] == str(m["messlauf"]))
    assert (lauf["stufe"], lauf["kommando"], lauf["parameter"], lauf["ergebnis"]) == ("4", "sitzungen", "--seiten 2", "ok")
    assert lauf["start"].startswith(m["datum"]) and m["kommando"] == f'{lauf["kommando"]} {lauf["parameter"]}'

    belege = glossar.glossar()["ergebnisse_belege"]
    assert set(belege) == {k for k in glossar.ERGEBNISSE if k not in glossar.ROLLEN}
    for wert, n in gemessen.items():
        b = belege[wert]
        assert b["gemessen"] and b["messung"]["anzahl"] == n and b["messung"]["messlauf"] == 5
        assert b["beschriftung"] == "Fundstelle" and "Wuppertal" in b["fundstelle"]
        # sichtbarer Text ohne Zählwerte (Seite ohne Daten, Ratsdaten erst nach Phase 3); Abrufdatum als solches benannt
        assert "abgerufen am 12.11.2026" in b["fundstelle"] and "seit Juni 2026" in b["fundstelle"]
        assert not re.search(r"\d+ von \d+", b["fundstelle"]) and "Stichprobe vom" not in b["fundstelle"]
    # Gegenprobe: übernommene Ergebnisse sind gekennzeichnet, ohne Messung und nicht als Fundstelle beschriftet
    for wert in ("zur Kenntnis genommen", "vertagt", "erledigt durch Stellungnahme der Verwaltung"):
        assert not belege[wert]["gemessen"] and "messung" not in belege[wert]
        assert belege[wert]["beschriftung"] == "Herkunft"
        assert belege[wert]["fundstelle"].startswith("in Wuppertal bisher nicht beobachtet")
    # Rollen haben keinen Ergebnisbeleg (Beratungsrollen nach Stufe 5)
    assert not set(glossar.ROLLEN) & set(belege)


def test_gemessene_zuerst_und_nichts_geloescht():
    keys = list(glossar.ERGEBNISSE)
    assert keys[:4] == ["ungeändert beschlossen", "geändert beschlossen", "abgelehnt", "Entgegennahme ohne Beschluss"]
    # die Bonner Ergebnisse und Rollen bleiben (nur gekennzeichnet)
    for k in ("zur Kenntnis genommen", "vertagt", "zurückgezogen", "verwiesen", "nicht abgestimmt", "ohne Votum",
              "erledigt durch Stellungnahme der Verwaltung", "wg. Sitzungsabbruch nicht behandelt (vertagt)",
              "weitere Lesung erforderlich", "weitere Lesung",
              "bei Anerkennung der Tagesordnung nicht aufgenommen oder vertagt", "mit Protokollnotiz", "mit Maßgabe",
              *glossar.ROLLEN):
        assert k in glossar.ERGEBNISSE, k
    assert len(glossar.ERGEBNISSE) == 23


def test_erklaerungen_sachlich():
    e = glossar.ERGEBNISSE
    # abgelehnt: auch bei Stimmengleichheit; keine Behauptung „Mehrheit dagegen“
    assert "Mehrheit des Gremiums hat dagegen" not in e["abgelehnt"] and "keine Mehrheit" in e["abgelehnt"]
    # Entgegennahme ohne Beschluss: kein Beschluss, keine Rechtsfolge behauptet
    t = e["Entgegennahme ohne Beschluss"]
    assert "keinen Beschluss" in t
    for wort in ("bindend", "rechtskräftig", "wirksam", "endgültig", "erledigt", "Gemeindeordnung", "§"):
        assert wort not in t, wort
    assert "noch nicht geprüft" in glossar.ergebnis_beleg("Entgegennahme ohne Beschluss")["fundstelle"]
    # Gegenprobe: die übrigen gemessenen Werte tragen den Hinweis „nicht geprüft“ nicht
    assert "nicht geprüft" not in glossar.ergebnis_beleg("abgelehnt")["fundstelle"]


def test_begriffsseite_zeigt_ergebnisse_mit_fundstelle(tmp_path):
    begriffsseite.write(tmp_path, "https://wuppertal.ratsatlas.de/", gebietsseiten._page)
    html = (tmp_path / "begriffe" / "index.html").read_text(encoding="utf-8")
    abschnitt = html.split('<h2 id="ergebnisse">', 1)[1].split("<h2 ", 1)[0]
    dts = re.findall(r'<dt id="([^"]+)">([^<]+)</dt>', abschnitt)
    assert [b for _, b in dts][:4] == ["ungeändert beschlossen", "geändert beschlossen", "abgelehnt",
                                       "Entgegennahme ohne Beschluss"]
    assert ("entgegennahme-ohne-beschluss", "Entgegennahme ohne Beschluss") in dts
    assert abschnitt.count("Fundstelle: Ratsinformationssystem der Stadt Wuppertal") == 4
    assert abschnitt.count("so beobachtet bei Tagesordnungspunkten aus Sitzungen seit Juni 2026") == 4
    assert abschnitt.count("Herkunft: in Wuppertal bisher nicht beobachtet") == len(dts) - 4
    # Gegenproben: keine Zählwerte der Messung auf der Seite, kein „Fundstelle:“ vor „bisher nicht beobachtet“
    assert "von 22 Tagesordnungspunkten" not in html and "Stichprobe vom 12.11.2026" not in html
    assert "Fundstelle: in Wuppertal bisher nicht beobachtet" not in html
    # übrige Abschnitte behalten die Beschriftung „Fundstelle“
    assert "Herkunft:" not in html.split('<h2 id="ergebnisse">', 1)[0]
    # Gegenprobe: Rollen stehen nicht im Abschnitt Ergebnisse
    assert "Eilentscheidung" not in [b for _, b in dts]
    assert "Bonn" not in html and " ST?" not in html


def test_akkordeon_trifft_gemessene_ergebnisse():
    acc = begriffsseite.akkordeon(["Entgegennahme ohne Beschluss", "ungeändert beschlossen - mit Protokollnotiz"], "../")
    assert 'href="../begriffe/#entgegennahme-ohne-beschluss"' in acc
    assert 'href="../begriffe/#ungeaendert-beschlossen"' in acc and 'href="../begriffe/#mit-protokollnotiz"' in acc
    # Gegenprobe: unbekannter Wert ergibt kein Akkordeon
    assert begriffsseite.akkordeon(["[Testdaten] unbekannt"], "../") == ""
