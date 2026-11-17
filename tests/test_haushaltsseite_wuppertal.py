"""pipeline/haushaltsseite_wuppertal.py und data/haushalt/massnahmen.geojson (Plan vom 17.11.2026, CLAUDE.md 9): Seite
haushalt/ aus den ausgelesenen Daten (Band 1), Ansichten Ansatz 2026/2027 und Ergebnis 2024, Bezirksvertretungen mit
Fallgruppen, verortete Maßnahmen mit Kennzeichnung. Ohne Netz."""
import json

from pipeline import config, haushalt_wuppertal as h, haushaltsseite_wuppertal as s


def test_daten_im_bonner_format_und_summen():
    d = s.daten()
    assert len(d["produktbereiche"]) == 17
    assert [a["key"] for a in d["ansichten"]] == ["plan2026", "plan2027", "ist2024"]
    # Aufwendungen positiv; Summe der Produktbereiche = Gesamtergebnisplan Zeile 17 (Rundung)
    a26 = d["ansichten"][0]
    assert abs(a26["summe"] + d["gesamt"][(17, "Ansatz 2026")][0]) <= h.RUNDUNG
    assert all(p["plan"][2026]["betrag"] >= 0 for p in d["produktbereiche"])
    assert d["gesamt"][(18, "Ansatz 2026")] == (-90780578, 96)       # Band 1, S. 96
    assert abs(a26["ergebnis"] - (-90780578)) <= h.RUNDUNG
    assert len(d["bezirke"]) == 10


def test_seite_inhalt():
    html = s.body(s.daten())
    assert html.count('class="hh-radio"') == 3 and "Ergebnis 2024" in html
    assert "2028" not in html.split('<h2 id="bezirke">')[0]       # keine Finanzplanung außerhalb der Bezirke
    assert html.count('<details class="hh-mehr" id="bv-') == 10
    assert "Band 1, S. 96" in html and "Ort abgeleitet:" in html
    assert "Lizenz" in html and "Band 2" in html                    # offene Punkte genannt
    assert "je Einwohner" not in html.replace("Werte je Einwohner", "")
    assert "thema/" not in html and "haushalt.js" not in html      # keine Themenseiten, kein Zoom-Skript
    assert "(1 Zeilen" not in html
    assert ">2 Bezirksvertretung" not in html and ">4204 " not in html          # Kennziffern ausgeblendet


def test_anzeigename():
    assert s.anzeigename("4204_Kunstrasenkleinspielfeld Löhrerlen") == "Kunstrasenkleinspielfeld Löhrerlen"
    assert s.anzeigename("2_Bezirksvertretung Barmen") == "Bezirksvertretung Barmen"
    assert s.anzeigename("Brücke Moritzstraße") == "Brücke Moritzstraße"


def test_massnahmen_gekennzeichnet():
    geo = json.loads((config.ROOT / "data" / "haushalt" / "massnahmen.geojson").read_text(encoding="utf-8"))
    f = geo["features"]
    m = geo["meta"]
    assert m["zeilen"] == 192 and m["zeilen_verortet"] == len(f) > 100           # Zeilen der Fallgruppe 3
    assert m["massnahmen"] == len({(x["properties"]["bezirksvertretung"], x["properties"]["massnahme"]) for x in f}) + \
        (m["massnahmen"] - m["verortet"]) and m["massnahmen"] < m["zeilen"]           # Maßnahme = Name je BV
    for x in f:
        p = x["properties"]
        assert p["konfidenz"] == "niedrig" and p["hinweis"] == h.HINWEIS_ORT
        assert h._bezirksname(p["stadtbezirk"]) == h._bezirksname(p["bezirksvertretung"])
        assert p["fundstelle"].startswith(h.FUNDSTELLE + ", S. ") and "content/" not in p["fundstelle"]
        lon, lat = x["geometry"]["coordinates"]
        assert 7.0 < lon < 7.35 and 51.16 < lat < 51.33                # Stadtgebiet Wuppertal (grob)
        assert set(p["betraege"]) == {"2026", "2027", "2028", "2029", "2030"}


def test_write(tmp_path):
    def page(site_url, pfad, titel, beschreibung, body, root):
        return f"<title>{titel}</title>{body}"
    assert s.write(tmp_path, "https://example.org/", page) == ["haushalt/"]
    assert (tmp_path / "haushalt" / "index.html").read_text(encoding="utf-8").startswith("<title>Haushalt auf einen Blick")
    assert (tmp_path / "haushalt" / "massnahmen.geojson").read_bytes() == \
        (config.ROOT / "data" / "haushalt" / "massnahmen.geojson").read_bytes()
