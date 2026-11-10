"""Ortsnamen-Abgleich für Stufe B (pipeline/ortsnamen.py; CLAUDE.md 5.2, Freigabe 10.11.2026).

Alle Daten sind erfunden: Quartiere „Testquartier A/B/C/L“ und „Langerfeld-Testhang“, Straßen „Probestraße“, „Musterweg“,
„Großer Musterweg“, „Barmer Probestraße“, „Probe-Allee“, „Testgasse“, „Ohnepunktweg“, „Zwillingsweg“, „Am Probehang“,
Schlüssel „T001“ …, Flächen als Rechtecke bei lon/lat 0–3 (kein Ort in Wuppertal). Echte Namen nur für die zehn
Stadtbezirke (CLAUDE.md 2) und die Beispiele aus CLAUDE.md 5.2 („Barmer“ als Eigenname); ihre Punkte sind erfunden.
Zeichenketten wie „Barmer Testkasse“ oder „Barmenix“ sind erfunden und prüfen nur Wortgrenzen und Ausschlüsse. Ohne Netz
und ohne Geodaten der Stadt.
"""
import re
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box, mapping

from pipeline import config
from pipeline import ortsnamen as o

ROOT = Path(__file__).resolve().parents[1]

STADTBEZIRKE = ["Elberfeld", "Elberfeld-West", "Uellendahl-Katernberg", "Vohwinkel", "Cronenberg", "Barmen",
                "Oberbarmen", "Heckinghausen", "Langerfeld-Beyenburg", "Ronsdorf"]
# erfundene Flächen (Name, Stadtbezirk, Geometrie)
QUARTIERE = [
    o.Flaeche("Testquartier A", "Ronsdorf", box(0, 0, 1, 1)),
    o.Flaeche("Testquartier B", "Ronsdorf", box(1, 0, 2, 1)),
    o.Flaeche("Testquartier C", "Barmen", box(2, 0, 3, 1)),
    o.Flaeche("Langerfeld-Testhang", "Langerfeld-Beyenburg", box(0, 2, 1, 3)),
    # L-förmig: der Schwerpunkt zweier Adressen in den Enden liegt außerhalb
    o.Flaeche("Testquartier L", "Cronenberg", Polygon([(0, 5), (3, 5), (3, 6), (1, 6), (1, 8), (0, 8)])),
]


def _adr(schl, strasse, nr, lon, lat, zusatz=None, bz=None):
    return o.Adresse(schl, strasse, nr, zusatz, lon, lat, bz)


ADRESSEN = (
    # Probestraße T001: 6 Adressen in A (1–4, 12, 12a), 4 in B (7–10) → 60/40
    [_adr("T001", "Probestraße", str(n), 0.1 * n, 0.5) for n in range(1, 5)]
    + [_adr("T001", "Probestraße", "12", 0.6, 0.5), _adr("T001", "Probestraße", "12", 0.7, 0.5, "a")]
    + [_adr("T001", "Probestraße", str(n), 1.0 + 0.1 * (n - 5), 0.5) for n in range(7, 11)]
    # Musterweg: zwei Straßen gleichen Namens (T002 in A, T003 in Langerfeld-Testhang); Nr. 5 nur in T002, Nr. 7 in beiden
    + [_adr("T002", "Musterweg", "5", 0.2, 0.8), _adr("T002", "Musterweg", "7", 0.3, 0.8)]
    + [_adr("T003", "Musterweg", "7", 0.2, 2.5), _adr("T003", "Musterweg", "9", 0.4, 2.5)]
    + [_adr("T004", "Großer Musterweg", "1", 1.2, 0.8), _adr("T004", "Großer Musterweg", "3", 1.4, 0.8)]
    + [_adr("T005", "Barmer Probestraße", "2", 2.2, 0.5), _adr("T005", "Barmer Probestraße", "4", 2.4, 0.5)]
    + [_adr("T006", "Probe-Allee", "1", 2.2, 0.3), _adr("T006", "Probe-Allee", "3", 2.4, 0.3)]
    + [_adr("T007", "Testgasse", "1", 2.3, 0.7), _adr("T007", "Testgasse", "2", 2.5, 0.7)]
    # Zwillingsweg: zwei gleichnamige Straßen im selben Stadtbezirk (T010 in A, T011 in B)
    + [_adr("T010", "Zwillingsweg", "1", 0.5, 0.1), _adr("T010", "Zwillingsweg", "2", 0.6, 0.1)]
    + [_adr("T011", "Zwillingsweg", "1", 1.5, 0.1), _adr("T011", "Zwillingsweg", "2", 1.6, 0.1)]
    + [_adr("T012", "Am Probehang", "1", 2.6, 0.2), _adr("T012", "Am Probehang", "3", 2.7, 0.2)]
)
STRASSEN = [o.Strasse("Probestraße", "T001", "Ronsdorf"), o.Strasse("Musterweg", "T002", "Ronsdorf"),
            o.Strasse("Musterweg", "T003", "Langerfeld-Beyenburg"), o.Strasse("Großer Musterweg", "T004", "Ronsdorf"),
            o.Strasse("Barmer Probestraße", "T005", "Barmen"), o.Strasse("Probe-Allee", "T006", "Barmen"),
            o.Strasse("Testgasse (Testquartier C)", "T007", "Barmen"), o.Strasse("Ohnepunktweg", "T008", "Vohwinkel"),
            o.Strasse("Zwillingsweg", "T010", "Ronsdorf"), o.Strasse("Zwillingsweg", "T011", "Ronsdorf"),
            o.Strasse("Am Probehang", "T012", "Barmen")]


def _gebiete(quartiere=QUARTIERE):
    bz = [o.Gebiet(n, "stadtbezirk", n, str(i + 1), (10.0 + i, 50.0)) for i, n in enumerate(STADTBEZIRKE)]
    return bz + o.gebiete_aus_flaechen(quartiere, "quartier")


@pytest.fixture(scope="module")
def tabelle():
    return o.strasse_quartier(ADRESSEN, QUARTIERE)


@pytest.fixture(scope="module")
def v(tabelle):
    tab, idx, _ = tabelle
    return o.Verzeichnis(_gebiete(), STRASSEN, tab, idx)


def kurz(rows):
    return [(r["name"], r["method"], r["confidence"]) for r in rows]


# --- Normalisierung ---------------------------------------------------------------------------------------------------

def test_strassenabkuerzungen_ergeben_denselben_schluessel():
    formen = ["Probestr.", "Probestrasse", "Probestraße", "Probe-Straße", "Probe Straße", "Probe-Str.", "PROBESTRASSE",
              "PROBESTR."]
    assert {o.schluessel(f) for f in formen} == {"probestrasse"}
    # nicht: Wörter, die nur mit „str“ beginnen oder weitergehen
    assert o.schluessel("Probestrecke") == "probestrecke" and o.schluessel("Probestraßenbau") == "probestrassenbau"


@pytest.mark.parametrize("text,fund", [("Sanierung der Probestr. ab Mai", "Probestr."),
                                       ("Sanierung der Probe-Straße", "Probe-Straße"),
                                       ("Sanierung der Probe Str. im Mai", "Probe Str."),
                                       ("SANIERUNG DER PROBESTRASSE", "PROBESTRASSE")])
def test_fundstelle_in_originalschreibweise(v, text, fund):
    rows = v.verorte(text)
    assert rows and {r["evidence"] for r in rows} == {fund}
    assert {r["name"] for r in rows} == {"Probestraße"}


def test_bindestrich_und_leerzeichen_gleich_zusammenschreibung_nicht(v):
    assert o.schluessel("Probe-Muster-Allee") == o.schluessel("Probe Muster Allee") == \
        o.schluessel("Probe-Muster Allee") == o.schluessel("Probe – Muster / Allee")
    assert kurz(v.verorte("Bäume in der Probe Allee")) == [("Probe-Allee", "strasse", "mittel")]
    assert v.verorte("Bäume in der Probeallee") == []


def test_klammerzusatz_nur_im_verzeichnis(v):
    assert o.namensschluessel("Testgasse (Testquartier C)") == ("Testgasse", "Testquartier C")
    assert o.namensschluessel("Testgasse") == ("Testgasse", None)
    assert kurz(v.verorte("Ampel Testgasse")) == [("Testgasse", "strasse", "mittel")]


def test_eszett_und_ss(v):
    assert kurz(v.verorte("Grosser Musterweg")) == kurz(v.verorte("Großer Musterweg")) == \
        [("Großer Musterweg", "strasse", "mittel")]


def test_grossschreibung(v):
    assert v.verorte("auf dem musterweg") == []
    assert {r["method"] for r in v.verorte("AUF DEM MUSTERWEG")} == {"strasse_mehrdeutig"}
    assert v.verorte("in barmen") == [] and kurz(v.verorte("IN BARMEN")) == [("Barmen", "stadtbezirk_name", "mittel")]


def test_indextabelle_fuehrt_auf_das_original():
    text = "Ausbau Probe-Str. 12 in Groß Testhausen"
    norm, anf, end = o.normalisiere(text)
    assert norm == "ausbau probestrasse 12 in gross testhausen"
    i = norm.index("probestrasse")
    assert text[anf[i]:end[i + len("probestrasse") - 1]] == "Probe-Str."
    j = norm.index("gross")
    assert text[anf[j]:end[j + 4]] == "Groß"


# --- Gebiete ----------------------------------------------------------------------------------------------------------

def test_laengster_treffer_oberbarmen(v):
    assert kurz(v.verorte("Spielplatz in Oberbarmen")) == [("Oberbarmen", "stadtbezirk_name", "mittel")]


def test_elberfeld_west_und_elberfeld(v):
    rows = v.verorte("Radweg zwischen Elberfeld-West und Elberfeld")
    assert kurz(rows) == [("Elberfeld-West", "stadtbezirk_name", "mittel"), ("Elberfeld", "stadtbezirk_name", "mittel")]
    # „Elberfeld“ ist zugleich Teilname von „Elberfeld-West“: der volle Name gilt, die andere Lesart steht in kandidaten
    assert rows[1]["kandidaten"] == ["stadtbezirk Elberfeld-West"]
    assert kurz(v.verorte("Elberfeld West")) == [("Elberfeld-West", "stadtbezirk_name", "mittel")]


def test_name_nach_bindestrich(v):
    assert kurz(v.verorte("Schule in Wuppertal-Barmen")) == [("Barmen", "stadtbezirk_name", "mittel")]


@pytest.mark.parametrize("text", ["Langerfeld-Beyenburg", "Langerfeld Beyenburg", "Langerfeld/Beyenburg",
                                  "Langerfeld – Beyenburg"])
def test_doppelname_voll(v, text):
    rows = v.verorte(f"Sportplatz {text}")
    assert kurz(rows) == [("Langerfeld-Beyenburg", "stadtbezirk_name", "mittel")] and rows[0]["evidence"] == text


def test_doppelname_teil(v):
    rows = v.verorte("Sportplatz Beyenburg")
    assert kurz(rows) == [("Langerfeld-Beyenburg", "stadtbezirk_teilname", "niedrig")]
    assert rows[0]["level"] == "stadtbezirk" and rows[0]["ortsteil"] is None


def test_zwei_teilnamen_eine_zeile(v):
    rows = v.verorte("Uellendahl und Katernberg")
    assert kurz(rows) == [("Uellendahl-Katernberg", "stadtbezirk_teilname", "niedrig")]
    assert rows[0]["evidence"] == "Uellendahl; Katernberg"


def test_himmelsrichtung_allein_kein_ort(v):
    assert v.verorte("Ausfahrt West") == [] and v.verorte("Mitte") == []


def test_mehrdeutig_im_selben_stadtbezirk(v):
    """„Langerfeld“: Teil des Stadtbezirks und des erfundenen Quartiers „Langerfeld-Testhang“ im selben Stadtbezirk."""
    rows = v.verorte("Bolzplatz Langerfeld")
    assert kurz(rows) == [("Langerfeld-Beyenburg", "stadtbezirk_teilname", "niedrig")]
    assert rows[0]["kandidaten"] == ["stadtbezirk Langerfeld-Beyenburg", "quartier Langerfeld-Testhang"]


def test_mehrdeutig_in_zwei_stadtbezirken():
    qs = [o.Flaeche("Langerfeld-Testhang", "Ronsdorf", box(0, 2, 1, 3))]
    v2 = o.Verzeichnis(_gebiete(qs))
    rows = v2.verorte("Bolzplatz Langerfeld")
    assert sorted(kurz(rows)) == [("Langerfeld-Beyenburg", "stadtbezirk_mehrdeutig", "niedrig"),
                                  ("Langerfeld-Testhang", "ortsteil_mehrdeutig", "niedrig")]
    assert all(len(r["kandidaten"]) == 2 for r in rows)


def test_genitiv(v):
    assert kurz(v.verorte("Vohwinkels Mitte")) == [("Vohwinkel", "stadtbezirk_name", "mittel")]
    v2 = o.Verzeichnis(_gebiete(), genitiv=False)
    assert v2.verorte("Vohwinkels Mitte") == []


@pytest.mark.parametrize("text", ["Barmer Testanlagen", "Barmener Straßenfest", "Barmenix", "Oberbarmener"])
def test_abgeleitete_formen_kein_gebiet(v, text):
    assert [r for r in v.verorte(text) if r["level"] in ("ortsteil", "stadtbezirk")] == []


def test_quartier_ausserhalb_der_bezirksvertretung(v):
    assert kurz(v.verorte("Spielplatz Testquartier A")) == [("Testquartier A", "ortsteil_name", "mittel")]
    assert kurz(v.verorte("Spielplatz Testquartier A", bv_bezirke={"Barmen"})) == \
        [("Testquartier A", "ortsteil_name", "niedrig")]
    assert kurz(v.verorte("Spielplatz Testquartier A", bv_bezirke={"Ronsdorf"})) == \
        [("Testquartier A", "ortsteil_name", "mittel")]


def test_quartier_deckt_stadtbezirk(v):
    rows = v.verorte("Testquartier A in Ronsdorf")
    assert kurz(rows) == [("Testquartier A", "ortsteil_name", "mittel")]
    assert rows[0]["bezirk"] == "Ronsdorf" and rows[0]["source"] == config.QUELLE_GEO


def test_varianten_und_historische_namen_nur_aus_tabellen():
    qs = [o.Flaeche("Testquartier A", "Ronsdorf", box(0, 0, 1, 1))]
    gebiete = [g if g.name != "Testquartier A" else o.Gebiet(g.name, g.ebene, g.stadtbezirk, g.nummer, g.punkt,
                                                               (("Testquartier Alpha", "erfundener Beleg"),))
               for g in _gebiete(qs)]
    v2 = o.Verzeichnis(gebiete, historisch={"Alt-Testheim": ("Testquartier A", "erfundener Beleg")})
    assert kurz(v2.verorte("Testquartier Alpha")) == [("Testquartier A", "ortsteil_variante", "mittel")]
    assert kurz(v2.verorte("Alt-Testheim")) == [("Testquartier A", "ortsteil_historisch", "mittel")]
    assert o.Verzeichnis(_gebiete(qs)).verorte("Alt-Testheim") == []


# --- Ausschlüsse ------------------------------------------------------------------------------------------------------

def test_bv_barmen_ausgeschlossen(v):
    assert v.verorte("Sitzung der BV Barmen") == []
    aus = [t for t in v.treffer("Sitzung der BV Barmen") if t.art == "ausschluss"]
    assert [(t.fundstelle, t.regel, t.eintraege) for t in aus] == [("BV Barmen", "1", ("Barmen",))]


def test_bezirksvertretung_mit_doppelnamen(v):
    assert v.verorte("Bezirksvertretung Elberfeld-West") == []
    aus = [t for t in v.treffer("Bezirksvertretung Elberfeld-West") if t.art == "ausschluss"]
    assert aus[0].regel == "2" and aus[0].fundstelle == "Bezirksvertretung Elberfeld-West"
    assert v.verorte("BV Langerfeld/Beyenburg") == []


def test_rathaus(v):
    assert v.verorte("Sanierung Rathaus Barmen") == []


@pytest.mark.parametrize("text", ["Barmer Testkasse", "Vertrag mit der Barmer", "VERTRAG MIT DER BARMER"])
def test_barmer_eigenname(v, text):
    assert v.verorte(text) == []
    assert [t.regel for t in v.treffer(text)] == ["4"]


def test_ausschluss_laesst_anderen_ort_stehen(v):
    assert kurz(v.verorte("BV Barmen: Spielplatz in Oberbarmen")) == [("Oberbarmen", "stadtbezirk_name", "mittel")]


def test_strasse_vor_ausschluss(v):
    rows = v.verorte("Ampel Barmer Probestraße")
    assert kurz(rows) == [("Barmer Probestraße", "strasse", "mittel")]
    assert not [t for t in v.treffer("Ampel Barmer Probestraße") if t.art == "ausschluss"]


def test_ausschluesse_im_gleichlauf_mit_explore():
    assert o.ausschluesse_aus_tsv(ROOT / "explore" / "ortsnamen_ausschluss.tsv") == o.AUSSCHLUESSE


# --- Straßen ----------------------------------------------------------------------------------------------------------

def test_strasse_ueber_zwei_quartiere(v):
    rows = v.verorte("Sanierung Probestraße")
    assert [(r["ortsteil"], r["anteil"], r["method"]) for r in rows] == [("Testquartier A", 0.6, "strasse"),
                                                                         ("Testquartier B", 0.4, "strasse")]
    assert {r["level"] for r in rows} == {"strasse"} and {r["bezirk"] for r in rows} == {"Ronsdorf"}


def test_gleicher_name_verschiedene_schluessel(v):
    rows = v.verorte("Musterweg")
    assert {(r["ortsteil"], r["method"], r["confidence"]) for r in rows} == \
        {("Testquartier A", "strasse_mehrdeutig", "niedrig"), ("Langerfeld-Testhang", "strasse_mehrdeutig", "niedrig")}
    rows = v.verorte("Musterweg in Ronsdorf")
    assert [(r["ortsteil"], r["method"], r["confidence"]) for r in rows] == \
        [("Testquartier A", "strasse+bezirk", "mittel")]
    rows = v.verorte("Musterweg", bv_bezirke={"Langerfeld-Beyenburg"})
    assert [(r["ortsteil"], r["method"]) for r in rows] == [("Langerfeld-Testhang", "strasse+bezirk")]


def test_strasse_und_quartier(v):
    rows = v.verorte("Probestraße in Testquartier B")
    assert [(r["level"], r["ortsteil"], r["method"]) for r in rows] == [("strasse", "Testquartier B", "strasse+ortsteil")]
    rows = v.verorte("Musterweg im Testquartier A")
    assert [(r["ortsteil"], r["method"], r["confidence"]) for r in rows] == \
        [("Testquartier A", "strasse+ortsteil", "mittel")]


def test_laengere_strasse_zuerst(v):
    assert kurz(v.verorte("Großer Musterweg")) == [("Großer Musterweg", "strasse", "mittel")]


def test_strasse_ausserhalb_der_bezirksvertretung(v):
    assert {r["confidence"] for r in v.verorte("Probestraße", bv_bezirke={"Barmen"})} == {"niedrig"}


def test_gattungsname_niedrig(tabelle):
    tab, idx, _ = tabelle
    v2 = o.Verzeichnis(_gebiete(), STRASSEN, tab, idx, gattung={"Probestraße"})
    assert {r["confidence"] for r in v2.verorte("Probestraße")} == {"niedrig"}


def test_strasse_ohne_adresspunkte(v):
    rows = v.verorte("Ohnepunktweg")
    assert [(r["level"], r["name"], r["method"], r["confidence"], r["source"]) for r in rows] == \
        [("stadtbezirk", "Vohwinkel", "strasse_stadtbezirk", "niedrig", config.QUELLE_STRASSEN)]


# --- Hausnummern ------------------------------------------------------------------------------------------------------

def test_hausnummer_mit_punkt(v):
    rows = v.verorte("Umbau Probestraße 3", punkt_erlaubt=True)
    assert len(rows) == 1
    r = rows[0]
    assert (r["level"], r["method"], r["confidence"], r["evidence"], r["ortsteil"]) == \
        ("adresse", "strasse+hausnummer_punkt", "hoch", "Probestraße", "Testquartier A")
    assert (r["lon"], r["lat"]) == (pytest.approx(0.3), 0.5) and r["source"] == config.QUELLE_ADRESSEN


def test_hausnummer_ohne_punkt(v, tabelle):
    rows = v.verorte("Umbau Probestraße 8")
    assert [(r["level"], r["method"], r["ortsteil"]) for r in rows] == \
        [("strasse", "strasse+hausnummer", "Testquartier B")]
    tab = tabelle[0]["s:T001"]
    b = next(e for e in tab if e.quartier == "Testquartier B")
    assert (rows[0]["lon"], rows[0]["lat"]) == (b.lon, b.lat)
    assert (rows[0]["lon"], rows[0]["lat"]) != (pytest.approx(0.8), 0.5)   # nicht der Hauspunkt


def test_hausnummer_zusatz(v):
    rows = v.verorte("Probestraße 12a", punkt_erlaubt=True)
    assert [(r["level"], r["lon"]) for r in rows] == [("adresse", pytest.approx(0.7))]
    rows = v.verorte("Probestraße 12 b", punkt_erlaubt=True)
    assert [(r["level"], r["method"], r["ortsteil"]) for r in rows] == \
        [("strasse", "strasse+hausnummer", "Testquartier A")]
    assert "Zusatz" in rows[0]["hinweis"]


@pytest.mark.parametrize("text", ["Probestraße 2025", "Probestr. 2. Bauabschnitt", "Probestraße 1900 bis 1950"])
def test_keine_hausnummer(v, text):
    rows = v.verorte(text, punkt_erlaubt=True)
    assert {r["method"] for r in rows} == {"strasse"} and len(rows) == 2 and "hinweis" not in rows[0]


def test_nummer_mit_nr_und_bereich(v):
    assert [r["ortsteil"] for r in v.verorte("Musterweg Nr. 5", punkt_erlaubt=True)] == ["Testquartier A"]
    rows = v.verorte("Probestraße 12-14", punkt_erlaubt=True)
    assert [(r["level"], r["lon"]) for r in rows] == [("adresse", pytest.approx(0.6))]


def test_nummer_nicht_im_verzeichnis(v):
    rows = v.verorte("Probestraße 99", punkt_erlaubt=True)
    assert {r["method"] for r in rows} == {"strasse"} and {r["hinweis"] for r in rows} == {"Hausnummer nicht im Verzeichnis"}


def test_nummer_loest_gleichnamige_strassen(v):
    rows = v.verorte("Musterweg 9")
    assert [(r["ortsteil"], r["method"]) for r in rows] == [("Langerfeld-Testhang", "strasse+hausnummer")]
    rows = v.verorte("Musterweg 7")   # in beiden Straßen
    assert {r["method"] for r in rows} == {"strasse_mehrdeutig"}
    assert {r["hinweis"] for r in rows} == {"Hausnummer in mehreren gleichnamigen Straßen"}


def test_hausnummer_entscheidet_vor_genanntem_quartier(v):
    """Nr. 8 liegt in B; ein genanntes Quartier A derselben Straße gilt als Lagebezeichnung (wie Bonn)."""
    rows = v.verorte("Probestraße 8 im Testquartier A")
    assert [(r["ortsteil"], r["method"]) for r in rows] == [("Testquartier B", "strasse+hausnummer")]


TEXTE = ["Umbau Probestraße 3", "Probestraße 12a und Musterweg Nr. 5 in Ronsdorf", "Probestr. 2. Bauabschnitt",
         "Musterweg 7", "Probestraße 12 b", "Langerfeld", "BV Barmen: Probe-Allee 1", "Ohnepunktweg 4",
         "Testquartier A, Probestraße 8"]


@pytest.mark.parametrize("punkt", [True, False])
def test_keine_ziffern_in_fundstelle_und_name(v, punkt):
    for text in TEXTE:
        for r in v.verorte(text, punkt_erlaubt=punkt):
            assert not re.search(r"\d", r["evidence"] or "") and not re.search(r"\d", r["name"] or ""), (text, r)
            assert "hausnummer" not in r


def test_source_object_wird_durchgereicht(v):
    rows = v.verorte("Probestraße in Barmen", source_object="https://test.invalid/papers/1")
    assert rows and {r["source_object"] for r in rows} == {"https://test.invalid/papers/1"}


def test_felder_wie_gazetteer(v):
    felder = {"level", "name", "ortsteil", "bezirk", "lon", "lat", "method", "confidence", "evidence", "source",
              "source_object"}
    for text in TEXTE:
        for r in v.verorte(text):
            assert felder <= set(r), (text, r)


# --- Straße-zu-Quartier-Tabelle ---------------------------------------------------------------------------------------

def test_tabelle_anteile(tabelle):
    tab, idx, befund = tabelle
    assert [(e.quartier, e.anzahl, e.anteil, e.punkt) for e in tab["s:T001"]] == \
        [("Testquartier A", 6, 0.6, "adressen"), ("Testquartier B", 4, 0.4, "adressen")]
    assert idx[("s:T001", "12", "a")][0] == "Testquartier A" and ("s:T001", "12", "") in idx
    assert befund["namen"]["s:T001"] == "Probestraße"
    assert befund["zaehlung"]["ohne quartier"] == 0


def test_tabelle_sonderfaelle():
    qs = QUARTIERE
    adressen = [
        _adr("X1", "Testweg", "1", 1.0, 0.5),            # auf der Grenze A/B → A
        _adr("X1", "Testweg", "2", 1.5, 0.5),
        _adr("X1", "Testweg", "3", 2.5, 3.5),            # ohne Quartier (innerhalb der Ausdehnung)
        _adr("X2", "Testpfad", "1", 2.5, 5.5),           # L-förmiges Quartier, beide Enden
        _adr("X2", "Test-Pfad", "2", 0.5, 7.5),          # Schlüssel vor Name; zweite Schreibweise
        _adr("X2", "Testpfad", "3", 2.6, 5.5),
        _adr(None, "Ohneschlüsselweg", "1", 0.5, 0.2),   # ohne Schlüssel: über den Namen
        _adr(None, "Ohneschlüsselweg", "2", 0.6, 0.2, bz="Barmen"),   # Stadtbezirk der Adresse weicht ab
        _adr(None, None, "1", 0.5, 0.5),                 # ohne Straßenangabe
        _adr("X3", "Einzelweg", "1", 2.8, 0.9),          # einzige Adresse im Quartier
    ]
    tab, idx, befund = o.strasse_quartier(adressen, qs)
    z = befund["zaehlung"]
    assert (z["auf grenze"], z["ohne quartier"], z["ohne straßenangabe"], z["stadtbezirk abweichend"],
            z["schlüssel mit mehreren namen"]) == (1, 1, 1, 1, 1)
    assert [e.quartier for e in tab["s:X1"]] == ["Testquartier A", "Testquartier B"]
    assert befund["namen"]["s:X2"] == "Testpfad"
    (lq,) = tab["s:X2"]
    flaeche = QUARTIERE[-1].geometrie
    from shapely.geometry import Point
    assert lq.quartier == "Testquartier L" and flaeche.covers(Point(lq.lon, lq.lat))
    assert (lq.lon, lq.lat) != (pytest.approx(1.9), pytest.approx(6.1667, abs=1e-3))   # Schwerpunkt liegt außerhalb
    assert [e.quartier for e in tab["n:ohneschlüsselweg"]] == ["Testquartier A"]
    (einzel,) = tab["s:X3"]
    assert einzel.punkt == "quartier" and (einzel.lon, einzel.lat) != (2.8, 0.9)


def test_tabelle_schwerpunkt_auf_hauspunkt():
    adressen = [_adr("X", "Reihe", str(n), 0.1 * n, 0.5) for n in (1, 2, 3)]   # Schwerpunkt = mittleres Haus
    tab, _, _ = o.strasse_quartier(adressen, QUARTIERE)
    assert tab["s:X"][0].punkt == "quartier"


def test_tabelle_falsche_achsenfolge():
    adressen = [_adr("X", "Testweg", "1", 50.0, 7.0)]
    with pytest.raises(ValueError, match="Achsenfolge"):
        o.strasse_quartier(adressen, QUARTIERE)


def test_quartier_stadtbezirk_und_gebiete():
    bezirke = [o.Flaeche("Ronsdorf", "Ronsdorf", box(0, 0, 2, 1)), o.Flaeche("Barmen", "Barmen", box(2, 0, 3, 1))]
    ohne = [o.Flaeche("Testquartier C", None, mapping(box(2, 0, 3, 1))), o.Flaeche("Draußen", None, box(9, 9, 10, 10))]
    neu, offen = o.quartier_stadtbezirk(ohne, bezirke)
    assert [q.stadtbezirk for q in neu] == ["Barmen", None] and offen == ["Draußen"]
    (g,) = o.gebiete_aus_flaechen(neu[:1], "quartier")
    assert (g.name, g.ebene, g.stadtbezirk) == ("Testquartier C", "quartier", "Barmen") and 2 <= g.punkt[0] <= 3


# --- Felder der Quelle und B-Plan-Nummern -----------------------------------------------------------------------------

def test_geo_felder_offen_bis_stufe_g():
    assert config.GEO_FELDER["strassen"] == {"schluessel": "STRSCHL", "name": "STRNAME", "stadtbezirk": "STADTBEZIRK"}
    for art in ("adressen", "quartiere", "stadtbezirke"):
        assert set(config.GEO_FELDER[art].values()) == {None}, art
    assert config.BPLAN_NUMMER is None


def test_aus_feldern():
    with pytest.raises(o.FeldFehlt, match="offen"):
        o.aus_feldern([{"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [0, 0]}}],
                      "adressen")
    with pytest.raises(o.FeldFehlt, match="STRNAME"):
        o.aus_feldern([{"STRSCHL": "1", "STADTBEZIRK": "x"}], "strassen")
    zeilen = [{"STRSCHL": "T001", "STRNAME": "Probestraße", "STADTBEZIRK": "Ronsdorf"}]
    assert o.aus_feldern(zeilen, "strassen") == [o.Strasse("Probestraße", "T001", "Ronsdorf")]
    test = {"adressen": {"schluessel": "s", "strasse": "n", "hausnummer": "h", "zusatz": "z", "stadtbezirk": False},
            "quartiere": {"name": "q", "nummer": False, "stadtbezirk": False}}
    adr = o.aus_feldern([{"type": "Feature", "properties": {"s": "T1", "n": "Testweg", "h": 7, "z": ""},
                          "geometry": {"type": "Point", "coordinates": [0.5, 0.25]}}], "adressen", test)
    assert adr == [o.Adresse("T1", "Testweg", "7", None, 0.5, 0.25, None)]
    (q,) = o.aus_feldern([{"type": "Feature", "properties": {"q": "Testquartier A"}, "geometry": mapping(box(0, 0, 1, 1))}],
                         "quartiere", test)
    assert (q.name, q.stadtbezirk, q.nummer) == ("Testquartier A", None, None)


def test_plan_nummern():
    assert o.plan_nummern("Bebauungsplan Nr. 123A") == []   # Schema offen
    schema = r"\d{3}[A-Z]?"   # erfunden
    assert o.plan_nummern("Bebauungsplan Nr. 123A und 456 – Testquartier", schema) == \
        [("123A", "Bebauungsplan Nr. 123A und 456"), ("456", "Bebauungsplan Nr. 123A und 456")]
    assert o.plan_nummern("Vorlage 123 zum Spielplatz", schema) == []


# --- Allgemein --------------------------------------------------------------------------------------------------------

def test_modul_ohne_netz():
    """Kein Abruf, kein Dateizugriff von selbst (außer ausschluesse_aus_tsv mit übergebenem Pfad), kein „.locate(“
    (tests/test_live_pruefen.py wertet es als Nutzung von geolocation); Bonner Namen prüft tests/test_kern_ohne_bonn.py."""
    quelle = (ROOT / "pipeline" / "ortsnamen.py").read_text(encoding="utf-8")
    for wort in ("urlopen", "urllib", "requests", "socket", "http.client", "urlretrieve", "from .net", "from .abruf",
                 "from .fetch", "read_text(", "config.GEO /", "config.ORTSTEILE", "config.STRASSEN"):
        assert wort not in quelle, wort
    assert not re.search(r"\.locate\(", quelle)
    assert '"pipeline/ortsnamen.py"' in (ROOT / "tests" / "test_kern_ohne_bonn.py").read_text(encoding="utf-8")


# --- Nachprüfung 10.11.2026 -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["Sitzung der BV\nBarmen", "Sitzung der BV Barmen", "Sitzung der BV  Barmen",
                                  "Sitzung der BV-Barmen", "SITZUNG DER BV BARMEN", "BEZIRKSVERTRETUNG BARMEN",
                                  "Bezirksvertretung\nElberfeld-West", "Rathaus\nBarmen", "Rathaus - Barmen"])
def test_ausschluss_in_anderer_schreibweise(v, text):
    """Ausschlüsse unter denselben Bedingungen wie der Namensabgleich: Trenner und Groß-/Kleinschreibung."""
    assert v.verorte(text) == []
    assert [t.art for t in v.treffer(text)] == ["ausschluss"]


def test_ausschluss_mit_wortgrenze_hinter_dem_namen(tabelle):
    """Ohne Wortgrenze hinter {name} verdeckte „Halle Testquartier A“ den Anfang der kürzeren Straße
    „Testquartier Allee“ (erfundene Regel und Straße)."""
    tab, idx, _ = tabelle
    regel = (o.Ausschluss("T", "test", r"\bHalle {name}", "erfunden"),)
    v2 = o.Verzeichnis(_gebiete(), [o.Strasse("Testquartier Allee", None, "Ronsdorf")], tab, idx, ausschluesse=regel)
    assert [t.art for t in v2.treffer("Halle Testquartier Allee")] == ["strasse"]
    assert [t.art for t in v2.treffer("Halle Testquartier A")] == ["ausschluss"]


def test_ausschluss_vor_strasse_bei_gleicher_laenge(tabelle):
    tab, idx, _ = tabelle
    v2 = o.Verzeichnis(_gebiete(), [o.Strasse("Barmer", "T020", "Barmen")], tab, idx)
    assert [t.art for t in v2.treffer("Vertrag mit der Barmer")] == ["ausschluss"]


def test_wortgrenze_am_anfang(v):
    assert v.verorte("SPIELPLATZ UNTERBARMEN") == [] and v.verorte("Spielplatz Unterbarmen") == []


@pytest.mark.parametrize("text", ["Probestraße 3 Bäume", "Probestraße 4 Wochen gesperrt", "Probestraße 12 B-Plan",
                                  "Probestraße 3 Jahre Bauzeit"])
def test_zahl_vor_einem_wort_keine_hausnummer(v, text):
    rows = v.verorte(text, punkt_erlaubt=True)
    assert [(r["level"], r["ortsteil"], r["method"]) for r in rows] == [("strasse", "Testquartier A", "strasse"),
                                                                        ("strasse", "Testquartier B", "strasse")]
    assert {r["hinweis"] for r in rows} == {"Zahl hinter dem Straßennamen nicht als Hausnummer gewertet"}


@pytest.mark.parametrize("text", ["Probestraße 3 und 4", "Probestraße 3 bis 4", "Probestraße 3, Umbau",
                                  "Probestraße 3 in Ronsdorf", "Probestraße 3 Ecke Testgasse", "Probestraße 3/4",
                                  "Probestraße 3 (Umbau)"])
def test_hausnummer_vor_bindewort_oder_satzzeichen(v, text):
    rows = [r for r in v.verorte(text, punkt_erlaubt=True) if r["name"] == "Probestraße"]
    assert [(r["level"], r["lon"]) for r in rows] == [("adresse", pytest.approx(0.3))]


def test_zusatz_nicht_aus_dem_naechsten_wort(v):
    rows = v.verorte("Probestraße 12 a, Umbau", punkt_erlaubt=True)
    assert [(r["level"], r["lon"]) for r in rows] == [("adresse", pytest.approx(0.7))]
    rows = v.verorte("Probestraße 12 Bauabschnitt", punkt_erlaubt=True)
    assert all("Zusatz" not in r.get("hinweis", "") for r in rows) and {r["level"] for r in rows} == {"strasse"}


def test_mehrere_fundstellen_einer_strasse(v):
    rows = v.verorte("Probestraße und Probestr.")
    assert [(r["ortsteil"], r["evidence"]) for r in rows] == [("Testquartier A", "Probestraße; Probestr."),
                                                              ("Testquartier B", "Probestraße; Probestr.")]
    # die Hausnummer entscheidet; das Quartier B der Fundstelle ohne Nummer entfällt
    rows = v.verorte("Probestraße: Ausbau zwischen Probestraße 2 und 10", punkt_erlaubt=True)
    assert [(r["level"], r["ortsteil"], r["method"]) for r in rows] == \
        [("adresse", "Testquartier A", "strasse+hausnummer_punkt")]
    rows = v.verorte("Probestraße 2 und Probestraße 3")
    assert [(r["ortsteil"], r["method"], r["evidence"]) for r in rows] == \
        [("Testquartier A", "strasse+hausnummer", "Probestraße")]


def test_gleichnamige_strassen_im_selben_stadtbezirk_ueber_quartier(v):
    rows = v.verorte("Zwillingsweg im Testquartier B")
    assert [(r["ortsteil"], r["method"], r["confidence"]) for r in rows] == \
        [("Testquartier B", "strasse+ortsteil", "mittel")]
    assert {r["method"] for r in v.verorte("Zwillingsweg in Ronsdorf")} == {"strasse_mehrdeutig"}


def test_strasse_mit_anderem_stadtbezirk_niedrig(v):
    rows = [r for r in v.verorte("Probestraße in Barmen") if r["name"] == "Probestraße"]
    assert rows and {r["confidence"] for r in rows} == {"niedrig"}
    assert {r["confidence"] for r in v.verorte("Probestraße in Ronsdorf")} == {"mittel"}


def test_praeposition_am_anfang_des_namens(v):
    assert kurz(v.verorte("Spielplatz am Probehang")) == [("Am Probehang", "strasse", "mittel")]
    assert kurz(v.verorte("Spielplatz Am Probehang")) == [("Am Probehang", "strasse", "mittel")]
    assert v.verorte("spielplatz am probehang") == []


def test_strassenschluessel_wie_explore(tabelle):
    """Schlüssel wie explore/geodaten.py _schluessel: „00123“, 123 und 123.0 sind dieselbe Straße."""
    adressen = [_adr(123, "Schlüsselweg", "1", 0.2, 0.3), _adr(123.0, "Schlüsselweg", "2", 0.4, 0.3)]
    tab, idx, _ = o.strasse_quartier(adressen, QUARTIERE)
    assert list(tab) == ["s:123"]
    v2 = o.Verzeichnis(_gebiete(), [o.Strasse("Schlüsselweg", "00123", "Ronsdorf")], tab, idx)
    assert kurz(v2.verorte("Sanierung Schlüsselweg")) == [("Schlüsselweg", "strasse", "mittel")]


@pytest.mark.parametrize("punkte", [[(0.1, 0.5), (0.2, 0.5), (0.3, 0.50003)],                 # fast gerade
                                    [(0.1000001, 0.5), (0.2, 0.5), (0.2999999, 0.5000004)]])  # Rundung trifft Haus
def test_anzeigepunkt_mit_mindestabstand(punkte):
    adressen = [_adr("X", "Reihe", str(i), x, y) for i, (x, y) in enumerate(punkte)]
    tab, _, _ = o.strasse_quartier(adressen, QUARTIERE)
    assert tab["s:X"][0].punkt == "quartier"
    # Gegenprobe: ohne Mindestabstand bliebe der Schwerpunkt (nahe einem Haus)
    tab, _, _ = o.strasse_quartier(adressen, QUARTIERE, mindestabstand_m=0.0)
    assert tab["s:X"][0].punkt == "adressen"


def test_ungueltige_flaeche_nur_im_speicher_repariert():
    schleife = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])   # Achterschleife, ungültig
    qs = [o.Flaeche("Testquartier S", "Ronsdorf", schleife)]
    tab, _, befund = o.strasse_quartier([_adr("X", "Testweg", "1", 0.1, 0.5), _adr("X", "Testweg", "2", 0.9, 0.5)], qs)
    assert befund["zaehlung"]["ungültige fläche"] == 1 and [e.quartier for e in tab["s:X"]] == ["Testquartier S"]
    assert not qs[0].geometrie.is_valid   # übergebene Geometrie unverändert


def test_min_anteil_und_doppelte_adresse():
    tab, _, _ = o.strasse_quartier(ADRESSEN, QUARTIERE, min_anteil=0.5)
    assert [e.quartier for e in tab["s:T001"]] == ["Testquartier A"]
    doppelt = [_adr("D", "Doppelweg", "1", 0.5, 0.5), _adr("D", "Doppelweg", "1", 1.5, 0.5)]
    _, idx, befund = o.strasse_quartier(doppelt, QUARTIERE)
    assert befund["zaehlung"]["doppelte adresse"] == 1 and idx[("s:D", "1", "")][0] == "Testquartier A"


def test_kurze_teile_genitiv_ausnahmen_und_kurze_strassen():
    qs = [o.Flaeche("Xy-Testfeld", "Ronsdorf", box(0, 0, 1, 1)), o.Flaeche("Testhaus", "Ronsdorf", box(1, 0, 2, 1))]
    v2 = o.Verzeichnis(_gebiete(qs), [o.Strasse("Weg", "W1", "Ronsdorf")])
    assert v2.verorte("Platz Xy") == []                                   # Teil unter drei Zeichen
    assert kurz(v2.verorte("Platz Testfeld")) == [("Xy-Testfeld", "ortsteil_teilname", "niedrig")]
    assert v2.verorte("Platz Testhauss") == []                            # kein Genitiv nach „s“
    assert kurz(v2.verorte("Platz Testhaus")) == [("Testhaus", "ortsteil_name", "mittel")]
    assert v2.verorte("Weg") == []                                        # Straßennamen unter vier Zeichen nicht


def test_nfc_in_verzeichnis_und_text():
    import unicodedata
    nfd = unicodedata.normalize("NFD", "Testmühle")
    qs = [o.Flaeche(nfd, "Ronsdorf", box(0, 0, 1, 1))]
    v2 = o.Verzeichnis(_gebiete(qs))
    assert [r["level"] for r in v2.verorte("Brücke Testmühle")] == ["ortsteil"]
    assert o.schluessel(nfd) == o.schluessel("Testmühle")
