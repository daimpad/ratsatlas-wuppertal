"""Ortsverzeichnis Wuppertal für die Verortung der Stufe B (Phase 3, CLAUDE.md 5.2; Plan vom 16.11.2026, Punkt 1–2).

Verbindet den Wuppertaler Ortsnamen-Abgleich (pipeline/ortsnamen.py, Verzeichnis) und die kuratierte Ortsliste
(pipeline/orte_kuratiert.py) mit dem Aufbau (pipeline/build.py). Die Klasse Wuppertal bietet die Schnittstelle, die build
und volltext von geocode.Gazetteer (Bonn, OSM-Straßen) kennen: `locate`, `street_re_for`, `streets`, `ot_by_name`,
`bezirk_point`. Abweichung für den gemeinsamen Kern: Bonn und Köln verorten mit Gazetteer; hier ersetzt das
Straßenverzeichnis der Stadt mit Straßenschlüssel und Adresspunkten die OSM-Straßen und die Kreuzungsregel.

Dateien (geschrieben von tools/geodaten_uebernehmen.py aus den Dateien der Stadt, CC BY 4.0):
- config.STRASSEN (versioniert): Straßen (Name, Schlüssel, Stadtbezirk laut Straßenverzeichnis) und die
  Straße-zu-Quartier-Tabelle (ortsnamen.strasse_quartier: je Straße und Quartier Zahl und Anteil der Adressen und ein
  Anzeigepunkt, nie ein einzelner Hauspunkt). „streets“ führt nur die Namen, wie maske.Maske sie liest.
- config.HAUSNUMMERN (nicht versioniert, .gitignore; Entscheidung über die Veröffentlichung offen): Adressindex
  (Straßen-ID, Hausnummer, Zusatz → Quartier, Stadtbezirk, Punkt) für „strasse+hausnummer“; den Hauspunkt
  („strasse+hausnummer_punkt“) gibt es nur, wenn die aufrufende Stelle ihn erlaubt (maske.hausnummer_punkt_erlaubt).
"""
import json
import re

from . import config, geo, ortsnamen, orte_kuratiert

# Objekt der Ortsliste als Name einer Gesellschaft oder eines Vereins (Phase 3, Titel des Vollabrufs 17.11.2026:
# „Jahresabschluss der Historische Stadthalle Wuppertal GmbH“, „Aufsichtsrat Tanztheater Pina Bausch GmbH“,
# „Trägerverein der Begegnungsstätte Alte Synagoge e.V.“): gemeint ist die Organisation, nicht der Ort; nicht verortet
FIRMA_NACH = re.compile(r"\s*(?:Wuppertal\s*)?(?:Service\s*)?(?:g?GmbH|mbH|AG|e\.\s?V\.?)(?![^\W_])")


def _meta(quelle, abruf, **mehr):
    q = config.SOURCES[quelle]
    return {"source": q["url"], "license": q["license"], "attribution": config.NAMENSNENNUNG, "retrieved_at": abruf,
            **mehr}


def schreiben(strassen, tabelle, adressindex, befund, abruf, strassen_ziel=None, hausnummern_ziel=None):
    """Schreibt config.STRASSEN und config.HAUSNUMMERN (Pfade abweichend für Tests)."""
    strassen_ziel = strassen_ziel or config.STRASSEN
    hausnummern_ziel = hausnummern_ziel or config.HAUSNUMMERN
    eindeutig = sorted({(s.name, s.schluessel or "", s.stadtbezirk or "") for s in strassen})
    zaehlung = {k: v for k, v in sorted(befund.get("zaehlung", {}).items())}
    daten = {
        "meta": _meta(config.QUELLE_STRASSEN, abruf, aenderung=(
            "abgeleitet: Straßen aus dem Straßenverzeichnis (je Name, Schlüssel und Stadtbezirk eine Zeile); Quartiere "
            "je Straße aus den georeferenzierten Bestandsadressen (Punkt in der Fläche des Quartiers); Anzeigepunkt "
            "Schwerpunkt der Adressen im Quartier oder, wenn er einem Hauspunkt zu nahe kommt, ein Punkt in der Fläche"),
            quelle_adressen=config.SOURCES[config.QUELLE_ADRESSEN]["url"], befund=zaehlung),
        "streets": sorted({s.name for s in strassen}),
        "strassen": [list(z) for z in eindeutig],
        "tabelle": {sid: [[z.quartier, z.stadtbezirk, z.anzahl, z.anteil, z.lon, z.lat, z.punkt] for z in zeilen]
                    for sid, zeilen in sorted(tabelle.items())},
    }
    strassen_ziel.parent.mkdir(parents=True, exist_ok=True)
    strassen_ziel.write_text(json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    hausnummern_ziel.write_text(json.dumps({
        "meta": _meta(config.QUELLE_ADRESSEN, abruf, hinweis="nicht veröffentlichen (Entscheidung offen)"),
        "adressen": [[sid, nr, zusatz, *wert] for (sid, nr, zusatz), wert in sorted(adressindex.items())],
    }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(eindeutig), len(tabelle), len(adressindex)


def _laden_strassen(pfad):
    if not pfad.exists():
        return [], {}
    d = json.loads(pfad.read_text(encoding="utf-8"))
    if "strassen" not in d:      # Bonner Format (geocode.write_gazetteer): hier nicht verwendbar
        return [], {}
    strassen = [ortsnamen.Strasse(n, s or None, bz or None) for n, s, bz in d["strassen"]]
    tabelle = {sid: [ortsnamen.StrasseQuartier(*z) for z in zeilen] for sid, zeilen in d["tabelle"].items()}
    return strassen, tabelle


def _laden_hausnummern(pfad):
    if not pfad.exists():
        return {}
    d = json.loads(pfad.read_text(encoding="utf-8"))
    return {(sid, nr, zusatz): tuple(wert) for sid, nr, zusatz, *wert in d.get("adressen", [])}


class Wuppertal:
    """Ortsverzeichnis mit der Schnittstelle von geocode.Gazetteer (siehe Modulbeschreibung)."""

    def __init__(self, ortsliste=None):
        quartiere = geo.features(config.ORTSTEILE)
        bezirke = geo.features(config.STADTBEZIRKE)
        self.ortsteile = [f["properties"] for f in quartiere]
        self.ot_by_name = {p["ortsteil_bez"]: p for p in self.ortsteile}
        fl_q = [ortsnamen.Flaeche(f["properties"]["ortsteil_bez"], f["properties"].get("bezirk_bez"), f["geometry"],
                                  f["properties"].get("ortsteil")) for f in quartiere]
        fl_b = [ortsnamen.Flaeche(f["properties"]["bezirk_bez"], f["properties"]["bezirk_bez"], f["geometry"],
                                  f["properties"].get("bezirk")) for f in bezirke]
        gebiete = ortsnamen.gebiete_aus_flaechen(fl_q, "quartier") + ortsnamen.gebiete_aus_flaechen(fl_b, "stadtbezirk")
        from shapely.geometry import Point
        self.bezirk_point = {g.name: Point(*g.punkt) for g in gebiete if g.ebene == "stadtbezirk"}
        self.streets, tabelle = _laden_strassen(config.STRASSEN)
        self.verzeichnis = ortsnamen.Verzeichnis(gebiete, self.streets, tabelle,
                                                 _laden_hausnummern(config.HAUSNUMMERN))
        # ohne Straßen (volltext mit street_re=False, wie Gazetteer): eine gefundene Straße würde sonst ein genanntes
        # Quartier verdecken, obwohl ihre Zeile danach entfiele
        self.ohne_strassen = ortsnamen.Verzeichnis(gebiete)
        self.ortsliste = orte_kuratiert.Ortsliste() if ortsliste is None else ortsliste

    def street_re_for(self, text):
        """Kein Vorfilter nötig (der Abgleich läuft über einen Index); True heißt: Straßen suchen."""
        return True

    def locate(self, text, bv_bezirke=(), street_re=None, *, punkt_erlaubt=False, source_object=None):
        """Zeilen wie Gazetteer.locate: Gebiete und Straßen (ortsnamen.Verzeichnis.verorte), dazu Objekte der
        kuratierten Ortsliste, deren Quartier nicht schon genannt ist. `street_re=False`: ohne Straßen (volltext)."""
        verz = self.ohne_strassen if street_re is False else self.verzeichnis
        rows = verz.verorte(text, bv_bezirke=bv_bezirke, punkt_erlaubt=punkt_erlaubt, source_object=source_object)
        ohne_firmen = list(text or "")
        for _ort, _fund, anf, ende in self.ortsliste.treffer(text):
            if FIRMA_NACH.match(text, ende):
                ohne_firmen[anf:ende] = " " * (ende - anf)
        objekte, self.vermerke = self.ortsliste.verorte("".join(ohne_firmen), source_object=source_object)
        schon = {r["ortsteil"] for r in rows if r.get("ortsteil")}
        return rows + [r for r in objekte if r["ortsteil"] not in schon]
