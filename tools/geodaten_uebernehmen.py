"""Geodaten der Stadt Wuppertal für Seite und Verortung nach data/geo/ übernehmen (versioniert; CLAUDE.md 9, 17.11.2026).

Aufruf (ohne Netz; die Dateien hat der Auftraggeber am 16.11.2026 im Browser geladen, explore/STUFEN.md Stufe G):
  python3 -I tools/geodaten_uebernehmen.py --stadtbezirke <Stadtbezirke_EPSG4326_JSON.json> \
      --quartiere <Quartiere_EPSG4326_JSON.json> --bplan <rvbBebauungsplanverfahren_EPSG4326_JSON.json> \
      --bplan-laufend <lfdBebauungsplanverfahren_EPSG4326_JSON.json> \
      --strassen <Strassenverzeichnis_CSV.zip> --adressen <Adressen_EPSG4326_JSON.json> [--abruf 2026-11-16]

- Stadtbezirke und Quartiere (CC BY 4.0): Geometrien unverändert, Eigenschaften ins Bonner Modell umbenannt (bezirk,
  bezirk_bez; ortsteil, ortsteil_bez) nach config.GEO_FELDER. Die Quartiersdatei kennt keinen Stadtbezirk: er wird per
  Point-in-Polygon (Punkt in der Fläche des Quartiers) aus den Stadtbezirken abgeleitet und gegen die erste Ziffer der
  Quartiersnummer geprüft (Messung 17.11.2026: alle 69 Quartiere zu mindestens 99 % ihrer Fläche im Stadtbezirk dieser
  Ziffer); bei Abweichung Abbruch. „meta“ nennt Quelle, Lizenz, Namensnennung, Abrufdatum und die Änderung.
- Bebauungspläne (rechtsverbindlich und laufend, CC BY-ND 4.0): mit pipeline/bplan.speichern, Features unverändert
  (gleiche Geometrie, gleiche Eigenschaften mit den Feldnamen der Quelle, gleiche Reihenfolge), nur „meta“ mit Quelle,
  Lizenz, Namensnennung und Abrufdatum ergänzt (CLAUDE.md 6); vorher geprüft: Plannummer und Geometrie je Fläche.
- Straßenverzeichnis und Adressen (Phase 3, 17.11.2026; --strassen und --adressen): config.STRASSEN (versioniert:
  Straßen und Straße-zu-Quartier-Tabelle) und config.HAUSNUMMERN (versioniert: Adressindex), siehe
  pipeline/ortsverzeichnis.py. Jede Gruppe von Dateien ist einzeln aufrufbar.

Abweichung für den gemeinsamen Kern: Bonn und Köln laden ihre Geodaten im Workflow (fetch-geo); Wuppertal versioniert
sie, damit aus GitHub Actions keine Anfrage an Server der Stadt geht.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import bplan, config  # noqa: E402

AENDERUNG = ("Geometrien unverändert; Eigenschaften umbenannt ({felder}){zusatz}; die unveränderten Daten stehen in "
             "der Quelle")


def _lesen(pfad):
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    if daten.get("type") != "FeatureCollection" or not daten.get("features"):
        raise SystemExit(f"{pfad}: keine FeatureCollection mit Flächen")
    return daten


def _meta(quelle, abruf, felder, zusatz=""):
    q = config.SOURCES[quelle]
    return {"source": q["url"], "license": q["license"], "attribution": config.NAMENSNENNUNG, "retrieved_at": abruf,
            "aenderung": AENDERUNG.format(felder=felder, zusatz=zusatz)}


def _schreiben(pfad, daten):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(daten, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def stadtbezirke(roh, abruf):
    f = config.GEO_FELDER["stadtbezirke"]
    feats = []
    for x in roh["features"]:
        p = x["properties"]
        nr, name = str(p[f["nummer"]]).strip(), str(p[f["name"]]).strip()
        if not nr or not name or not x.get("geometry"):
            raise SystemExit(f"Stadtbezirk ohne Nummer, Name oder Geometrie: {p}")
        feats.append({"type": "Feature", "properties": {"bezirk": nr, "bezirk_bez": name}, "geometry": x["geometry"]})
    return {"type": "FeatureCollection", "features": feats,
            "meta": _meta(config.QUELLE_STADTBEZIRKE, abruf, f"{f['nummer']} → bezirk, {f['name']} → bezirk_bez")}


def quartiere(roh, bezirke, abruf):
    from shapely.geometry import shape
    f = config.GEO_FELDER["quartiere"]
    flaechen = [(b["properties"], shape(b["geometry"])) for b in bezirke["features"]]
    feats = []
    for x in roh["features"]:
        p = x["properties"]
        nr, name = str(p[f["nummer"]]).strip(), str(p[f["name"]]).strip()
        if not nr or not name or not x.get("geometry"):
            raise SystemExit(f"Quartier ohne Nummer, Name oder Geometrie: {p}")
        punkt = shape(x["geometry"]).representative_point()
        treffer = [b for b, g in flaechen if g.contains(punkt)]
        if len(treffer) != 1 or treffer[0]["bezirk"] != nr[0]:
            raise SystemExit(f"Quartier {nr} {name}: Stadtbezirk nicht eindeutig "
                             f"({[b['bezirk'] for b in treffer]}, erwartet {nr[0]})")
        b = treffer[0]
        feats.append({"type": "Feature", "geometry": x["geometry"], "properties": {
            "ortsteil": nr, "ortsteil_bez": name, "bezirk": b["bezirk"], "bezirk_bez": b["bezirk_bez"]}})
    return {"type": "FeatureCollection", "features": feats, "meta": _meta(
        config.QUELLE_GEO, abruf, f"{f['nummer']} → ortsteil, {f['name']} → ortsteil_bez",
        "; Stadtbezirk (bezirk, bezirk_bez) abgeleitet: Punkt in der Fläche des Quartiers in den Flächen der "
        "Stadtbezirke, geprüft gegen die erste Ziffer der Quartiersnummer")}


def bplan_pruefen(pfad):
    nummer = config.GEO_FELDER["bplan"]["nummer"]
    daten = _lesen(pfad)
    ohne = [i for i, x in enumerate(daten["features"])
            if not x.get("geometry") or not str((x.get("properties") or {}).get(nummer) or "").strip()]
    if ohne:
        raise SystemExit(f"{pfad}: {len(ohne)} Flächen ohne Geometrie oder {nummer}")
    return daten


def strassen_und_adressen(strassen_zip, adressen_json, quartiere_pfad, abruf):
    """Straßenverzeichnis (Zip mit CSV, Semikolon, UTF-8 mit BOM) und Bestandsadressen (GeoJSON) → config.STRASSEN und
    config.HAUSNUMMERN über pipeline/ortsverzeichnis.schreiben; Quartiere aus der übernommenen Datei (Bonner Modell)."""
    import csv
    import io
    import zipfile
    from pipeline import ortsnamen, ortsverzeichnis
    with zipfile.ZipFile(strassen_zip) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        zeilen = list(csv.DictReader(io.StringIO(z.read(name).decode("utf-8-sig")), delimiter=";"))
    strassen = ortsnamen.aus_feldern(zeilen, "strassen")
    adressen = ortsnamen.aus_feldern(_lesen(adressen_json)["features"], "adressen")
    qua = _lesen(quartiere_pfad)["features"]
    flaechen = [ortsnamen.Flaeche(f["properties"]["ortsteil_bez"], f["properties"]["bezirk_bez"], f["geometry"],
                                  f["properties"].get("ortsteil")) for f in qua]
    tabelle, adressindex, befund = ortsnamen.strasse_quartier(adressen, flaechen)
    return ortsverzeichnis.schreiben(strassen, tabelle, adressindex, befund, abruf), befund["zaehlung"]


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--stadtbezirke")
    a.add_argument("--quartiere")
    a.add_argument("--bplan")
    a.add_argument("--bplan-laufend")
    a.add_argument("--strassen", help="Strassenverzeichnis_CSV.zip (mit --adressen)")
    a.add_argument("--adressen", help="Adressen_EPSG4326_JSON.json (mit --strassen)")
    a.add_argument("--abruf", default="2026-11-16", help="Tag des Downloads (JJJJ-MM-TT)")
    a.add_argument("--ziel", default=None, help="Vorgabe: config.GEO")
    args = a.parse_args(argv)
    ziel = Path(args.ziel) if args.ziel else config.GEO
    if bool(args.stadtbezirke) != bool(args.quartiere):
        raise SystemExit("--stadtbezirke und --quartiere nur zusammen")
    if bool(args.strassen) != bool(args.adressen):
        raise SystemExit("--strassen und --adressen nur zusammen")
    if args.stadtbezirke:
        bez = stadtbezirke(_lesen(args.stadtbezirke), args.abruf)
        qua = quartiere(_lesen(args.quartiere), bez, args.abruf)
        _schreiben(ziel / config.STADTBEZIRKE.name, bez)
        _schreiben(ziel / config.ORTSTEILE.name, qua)
        print(f"{len(bez['features'])} Stadtbezirke, {len(qua['features'])} Quartiere → {ziel}")
    for datei, pfad, quelle in ((args.bplan, config.BPLAN, config.QUELLE_BPLAN),
                                (args.bplan_laufend, config.BPLAN_LAUFEND, config.QUELLE_BPLAN_LAUFEND)):
        if datei:
            n = bplan.speichern(bplan_pruefen(datei), ziel / pfad.name, jetzt=args.abruf, quelle=quelle)
            print(f"{pfad.name}: {n} Pläne → {ziel}")
    if args.strassen:
        (n_str, n_tab, n_adr), zaehlung = strassen_und_adressen(args.strassen, args.adressen,
                                                                ziel / config.ORTSTEILE.name, args.abruf)
        print(f"{n_str} Straßen, {n_tab} Straßen mit Quartier, {n_adr} Adressen; Befund {dict(zaehlung)}")


if __name__ == "__main__":
    main()
