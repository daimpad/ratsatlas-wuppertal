"""Benannte Orte aus dem Wuppertaler Open-Data-Katalog für die Ortsliste (Stufe B, CLAUDE.md 5.2) – ohne Netz.

Freigabe 16.11.2026 (Auswahl des Auftraggebers „Gezielt mit Regeln“, CLAUDE.md 9). Liest nur Dateien, die der
Auftraggeber am 16.11.2026 im Browser von `daten.wuppertal.de` geladen und in die Sitzung gegeben hat (unverändert, nur
im lokalen Cache `_cache/opendata/`, nicht versioniert); fragt keinen Server an. Lizenz aller Datensätze laut Katalog
(GovData-Spiegel des Open.NRW-Katalogs, gelesen am 16.11.2026): CC BY 4.0, Datenquelle Stadt Wuppertal.

Übernommen werden je Objekt nur Name, Art, Quartier und Stadtbezirk – keine Koordinaten, keine Kontaktfelder (Telefon,
E-Mail, Träger, Internetadressen). Quartier und Stadtbezirk ergeben sich per Punkt-in-Polygon gegen die Quartiere und
Stadtbezirke (Stufe G); bei Flächen zählt der Mittelwert der Außenringpunkte, bei Linien jeder Stützpunkt.

Regeln (CLAUDE.md 5.2; alles, was nicht gemessen ist, ist **Annahme** dieses Werkzeugs):
- Schwebebahnhaltestellen: nur mit Zusatz („Schwebebahnstation Kluse/Schauspielhaus“, „Schwebebahnhaltestelle …“,
  „Station …“, „Haltestelle …“), weil die Namen allein meist Straßen oder Plätze meinen (Stichprobe: 4 von 4 Treffern).
- Zugänge zu Bahntrassenradwegen (Punkte und Wege): je Trasse (Feld `TRASSE`) ein Eintrag „linie“ mit den Quartieren
  aller Zugänge; Annahme: die Quartiere der Zugänge sind die Quartiere der Trasse. Die Namen der Zugänge sind
  Straßennamen und werden nicht übernommen.
- Döppersberg: Quartier aus `ergebnisse/strasse_quartier.tsv` (Straße „Döppersberg“ im Straßenverzeichnis, Adresspunkte).
- Schulen: amtlicher Name und Kurzformen ohne „Gemeinschafts“, „Städtisches“, „Zweigstelle“ und ohne Klammerzusatz,
  der Bindestrichname ohne Ortszusatz („Erich-Fried-Gesamtschule Ronsdorf“ → „Erich-Fried-Gesamtschule“) und mit
  durchgehendem Bindestrich („Else Lasker-Schüler-…“ → „Else-Lasker-Schüler-…“), jeweils auch mit „…str.“ statt
  „…straße“; Namen, die nur eine Schulform sind, entfallen.
- Kinderspielplätze: nur als „Spielplatz <Name>“ bzw. „Kinderspielplatz <Name>“ (auch im Genitiv), ohne „(KSP)“.
- Veranstaltungsorte (`HAUPTNAME`): ohne die Namen in VERANSTALTUNG_AUS (zu allgemein bzw. nach einer Person benannte
  private Galerien); Teile von Namen mit „/“ zusätzlich als Varianten.
- Kindertageseinrichtungen und Kinder- und Jugendtreffs: nicht übernommen (Stichprobe: kein Treffer, Namen meist
  unspezifisch; Entscheidung des Auftraggebers 16.11.2026).
Gleiche Namen an mehreren Orten (z. B. Schule und Zweigstelle) werden zu einem Eintrag mit mehreren Quartieren.

Ergebnisse (versioniert):
- pipeline/orte_opendata.tsv: Einträge im Format von pipeline/orte_kuratiert.tsv
- ergebnisse/orte_opendata_zaehlung.tsv: Einträge je Datensatz und, mit --stichprobe, Titel mit Treffer je Art (ohne
  Titeltexte, CLAUDE.md 8)
Aufruf: python3 explore/orte_opendata.py [--daten _cache/opendata] [--stichprobe _cache/stichprobe_vorlagen.jsonl]
        [--ausgabe pipeline/orte_opendata.tsv] [--ergebnisse VERZ]
Rückgabewerte: 0 fertig, 1 Eingabe fehlt.
"""
import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
WURZEL = HIER.parent
sys.path.insert(0, str(WURZEL))
from pipeline import orte_kuratiert  # noqa: E402

DATEN = HIER / "_cache" / "opendata"
STICHPROBE = HIER / "_cache" / "stichprobe_vorlagen.jsonl"
AUSGABE = WURZEL / "pipeline" / "orte_opendata.tsv"
ERGEBNISSE = HIER / "ergebnisse"
STAND = "Browser-Download des Auftraggebers 16.11.2026"
LIZENZ = "Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0"

DATEIEN = {
    "quartiere": "Quartiere_EPSG4326_JSON.json",
    "stadtbezirke": "Stadtbezirke_EPSG4326_JSON.json",
    "schwebebahn": "Schwebebahnhoefe_EPSG4326_JSON.json",
    "zugaenge_punkte": "Zugaenge-Bahntrassenradwege-Punkte_EPSG4326_JSON.json",
    "zugaenge_wege": "Zugaenge-Bahntrassenradwege-Linien_EPSG4326_JSON.json",
    "schulen": "Schulen_EPSG4326_JSON.json",
    "spielplaetze": "Kinderspielplaetze_EPSG4326_JSON.json",
    "veranstaltung": "Veranstaltungsorte_EPSG4326_JSON.json",
}
TITEL = {
    "schwebebahn": "Schwebebahnhaltestellen Wuppertal",
    "zugaenge": "Zugangspunkte und Zugangswege zu Bahntrassenradwegen in Wuppertal",
    "schulen": "Schulen Wuppertal",
    "spielplaetze": "Kinderspielplätze Wuppertal",
    "veranstaltung": "Veranstaltungsorte Wuppertal",
}
SPALTEN = ["name", "varianten", "art", "verortung", "quartiere", "stadtbezirke", "geometrie", "beleg"]

STATION = ("Schwebebahnstation", "Schwebebahnhaltestelle", "Schwebebahnhof", "Station", "Haltestelle")
SPIELPLATZ = ("Spielplatz", "Spielplatzes", "Kinderspielplatz", "Kinderspielplatzes")
SCHULFORM = {"grundschule", "hauptschule", "realschule", "gesamtschule", "gymnasium", "förderschule", "berufskolleg",
             "schule", "griechische grundschule"}
SCHULFORM_RX = r"(?:Grundschule|Hauptschule|Realschule|Gesamtschule|Gymnasium|Förderschule|Schule)"
SCHULE_PRAEFIX = re.compile(r"^(?:Zweigstelle|Städtische[sr]?|Städt\.)\s+", re.I)
VERANSTALTUNG_AUS = {
    "ort": "zu allgemein", "Cinema": "zu allgemein", "INSEL": "zu allgemein", "LOCH": "zu allgemein",
    "die börse": "zu allgemein", "RAUM 2": "zu allgemein", "Open Ground": "zu allgemein",
    "Galerie GRÖLLE": "nach einer Person benannte private Galerie",
    "Hengesbach Gallery": "nach einer Person benannte private Galerie",
    "Design-Sammlung Schriefers": "nach einer Person benannte private Sammlung",
}


# --- Geometrie ---------------------------------------------------------------------------------------------------

def polygone(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def _im_ring(pt, ring):
    x, y = pt
    innen = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            innen = not innen
    return innen


def im_polygon(pt, geom):
    return any(_im_ring(pt, p[0]) and not any(_im_ring(pt, h) for h in p[1:]) for p in polygone(geom))


def punkte(geom):
    """Bezugspunkte eines Objekts: Punkt, Stützpunkte einer Linie, Mittelwert der Außenringpunkte einer Fläche."""
    t, c = geom["type"], geom["coordinates"]
    if t == "Point":
        return [tuple(c)]
    if t == "LineString":
        return [tuple(p) for p in c]
    if t == "MultiLineString":
        return [tuple(p) for linie in c for p in linie]
    ring = [p for poly in polygone(geom) for p in poly[0]]
    return [(sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))]


class Gebiete:
    def __init__(self, quartiere, stadtbezirke):
        self.q = [(f["properties"]["NAME"], f["geometry"]) for f in quartiere]
        self.b = [(f["properties"]["NAME"], f["geometry"]) for f in stadtbezirke]

    def paar(self, pt):
        q = next((n for n, g in self.q if im_polygon(pt, g)), None)
        b = next((n for n, g in self.b if im_polygon(pt, g)), None)
        return q, b


# --- Einträge ----------------------------------------------------------------------------------------------------

def _str_kurz(name):
    return re.sub(r"(?<=[a-zäöüß])straße\b", "str.", re.sub(r"\bStraße\b", "Str.", name))


def _varianten(*namen):
    out = []
    for n in namen:
        for v in (n, _str_kurz(n)):
            v = " ".join(v.split())
            if v and v not in out:
                out.append(v)
    return out


def schul_varianten(name):
    """[amtlicher Name, Kurzformen …] ohne reine Schulformen."""
    basis = re.sub(r"\s*\([^)]*\)", "", " ".join(name.split())).strip()
    kurz = SCHULE_PRAEFIX.sub("", basis)
    kurz = re.sub(r"^Gemeinschafts(?=grundschule\b)", "", kurz, flags=re.I)
    kurz = kurz[:1].upper() + kurz[1:]
    extra = []
    # „Erich-Fried-Gesamtschule Ronsdorf“ → „Erich-Fried-Gesamtschule“ (Bindestrichname vor dem Ortszusatz)
    m = re.match(rf"^([\w.]+(?:-[\w.]+)*-{SCHULFORM_RX})\s", kurz, re.I)
    if m:
        extra.append(m.group(1))
    # „Else Lasker-Schüler-Gesamtschule“ → „Else-Lasker-Schüler-Gesamtschule“
    m = re.match(rf"^(\w+) (\w[\w-]*-{SCHULFORM_RX})\b", kurz, re.I)
    if m:
        extra.append(f"{m.group(1)}-{m.group(2)}")
    return [n for n in _varianten(basis, kurz, *extra) if n.lower() not in SCHULFORM]


def spielplatz_name(name):
    return re.sub(r"\s*\(KSP\)\s*$", "", " ".join(name.split())).replace(",", ", ").replace(",  ", ", ")


def veranstaltung_varianten(name):
    name = " ".join(name.split())
    teile = [t.strip() for t in re.split(r"\s*/\s*", name) if len(t.strip()) >= 8] if "/" in name else []
    return _varianten(name, *teile)


class Sammler:
    """Einträge nach Name zusammenführen; Quartier-Bezirk-Paare in Reihenfolge des ersten Auftretens."""

    def __init__(self):
        self.e = {}

    def add(self, name, varianten, art, verortung, paare, beleg):
        e = self.e.setdefault(name, {"varianten": [], "art": art, "verortung": verortung, "paare": [], "beleg": beleg})
        for v in varianten:
            if v != name and v not in e["varianten"]:
                e["varianten"].append(v)
        for p in paare:
            if p[0] and p not in e["paare"]:
                e["paare"].append(p)

    def zeilen(self):
        out = []
        for name, e in self.e.items():
            # je Quartier ein Bezirk (das häufigste Paar zuerst gesehen); mehrere Quartiere → Fläche wird zur Linie
            je_q = {}
            for q, b in e["paare"]:
                je_q.setdefault(q, b)
            verortung = e["verortung"]
            if verortung in ("punkt", "flaeche") and len(je_q) > 1:
                verortung = "flaeche"
            out.append({"name": name, "varianten": "|".join(e["varianten"]), "art": e["art"], "verortung": verortung,
                        "quartiere": "|".join(je_q) or orte_kuratiert.OFFEN,
                        "stadtbezirke": "|".join(b or "" for b in je_q.values()) or orte_kuratiert.OFFEN,
                        "geometrie": "", "beleg": e["beleg"]})
        return sorted(out, key=lambda z: (z["art"], z["name"]))


def lade(pfad):
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)["features"]


def ableiten(daten, strasse_quartier):
    f = {k: lade(daten / v) for k, v in DATEIEN.items()}
    geb = Gebiete(f["quartiere"], f["stadtbezirke"])
    s = Sammler()
    zaehl = collections.Counter()

    def beleg(schluessel, regel):
        return f"{TITEL[schluessel]} ({STAND}); {LIZENZ}; {regel}"

    for o in f["schwebebahn"]:
        n = " ".join(o["properties"]["NAME"].split())
        paare = [geb.paar(p) for p in punkte(o["geometry"])]
        s.add(f"Schwebebahnstation {n}", [f"{p} {n}" for p in STATION[1:]], "Schwebebahnstation", "punkt", paare,
              beleg("schwebebahn", "nur mit Zusatz „Schwebebahnstation“, „Station“ o. Ä. (Annahme)"))
        zaehl["schwebebahn"] += 1

    trassen = collections.defaultdict(list)
    for o in f["zugaenge_punkte"] + f["zugaenge_wege"]:
        t = " ".join((o["properties"].get("TRASSE") or "").split())
        if t:
            trassen[t].extend(geb.paar(p) for p in punkte(o["geometry"]))
    for t, paare in sorted(trassen.items()):
        haeufig = collections.Counter(paare)
        paare = sorted(set(paare), key=lambda p: (-haeufig[p], p[0] or ""))
        s.add(t, [], "Bahntrassenradweg", "linie", paare,
              beleg("zugaenge", "Quartiere aller Zugänge (Punkte und Wege) der Trasse; Annahme: entsprechen der Trasse"))
        zaehl["bahntrassen"] += 1

    with open(strasse_quartier, encoding="utf-8", newline="") as fh:
        dopp = [z for z in csv.DictReader(fh, delimiter="\t") if z["strassenname"] == "Döppersberg"]
    if dopp:
        qn = [z["quartier"] for z in dopp]
        bez = {}
        for q, g in geb.q:
            if q in qn:
                bez[q] = next((b for b, bg in geb.b if any(im_polygon(p, bg) for p in punkte(g))), None)
        s.add("Döppersberg", [], "Platz und Bahnhofsumfeld", "flaeche", [(q, bez.get(q)) for q in qn],
              "Straßenverzeichnis und Georeferenzierte Bestandsadressen Wuppertal (Browser-Download des Auftraggebers "
              f"16.11.2026); {LIZENZ}; Quartier der Adresspunkte der Straße Döppersberg "
              "(explore/ergebnisse/strasse_quartier.tsv)")
        zaehl["doeppersberg"] += 1

    for o in f["schulen"]:
        namen = schul_varianten(o["properties"].get("Name") or "")
        if not namen:
            zaehl["schulen_ohne_namen"] += 1
            continue
        s.add(namen[0], namen[1:], "Schule", "punkt", [geb.paar(p) for p in punkte(o["geometry"])],
              beleg("schulen", "amtlicher Name und Kurzformen (Annahme)"))
        zaehl["schulen"] += 1

    for o in f["spielplaetze"]:
        n = spielplatz_name(o["properties"].get("name") or "")
        if not n:
            continue
        s.add(f"Spielplatz {n}", [f"{p} {n}" for p in SPIELPLATZ[1:]], "Kinderspielplatz", "flaeche",
              [geb.paar(p) for p in punkte(o["geometry"])],
              beleg("spielplaetze", "nur als „Spielplatz <Name>“ (Annahme)"))
        zaehl["spielplaetze"] += 1

    for o in f["veranstaltung"]:
        n = " ".join((o["properties"].get("HAUPTNAME") or "").split())
        if not n or n in VERANSTALTUNG_AUS:
            zaehl["veranstaltung_ausgeschlossen"] += 1
            continue
        v = veranstaltung_varianten(n)
        s.add(n, v[1:], "Veranstaltungsort", "punkt", [geb.paar(p) for p in punkte(o["geometry"])],
              beleg("veranstaltung", "Hauptname; Teile mit „/“ als Varianten"))
        zaehl["veranstaltung"] += 1
    return s.zeilen(), zaehl


def schreibe_tsv(pfad, zeilen, spalten):
    with open(pfad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, spalten, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(zeilen)


def titel_treffer(ausgabe, stichprobe):
    """Counter: Art → Zahl der Titel mit mindestens einem Treffer; dazu 'alle'."""
    liste = orte_kuratiert.Ortsliste(orte_kuratiert.laden(ausgabe))
    c = collections.Counter()
    n = 0
    with open(stichprobe, encoding="utf-8") as f:
        for z in f:
            t = json.loads(z).get("name") or ""
            if not t:
                continue
            n += 1
            arten = {o.art for o, *_ in liste.treffer(t)}
            c.update(arten)
            c["alle"] += bool(arten)
    return n, c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--daten", type=Path, default=DATEN)
    ap.add_argument("--stichprobe", type=Path, default=STICHPROBE)
    ap.add_argument("--ausgabe", type=Path, default=AUSGABE)
    ap.add_argument("--ergebnisse", type=Path, default=ERGEBNISSE)
    a = ap.parse_args(argv)
    fehlt = [v for v in DATEIEN.values() if not (a.daten / v).exists()]
    sq = a.ergebnisse / "strasse_quartier.tsv"
    if fehlt or not sq.exists():
        print("Eingabe fehlt:", ", ".join(fehlt + ([] if sq.exists() else [str(sq)])), file=sys.stderr)
        return 1
    zeilen, zaehl = ableiten(a.daten, sq)
    schreibe_tsv(a.ausgabe, zeilen, SPALTEN)
    out = [{"kennzahl": f"eintraege_{art}", "wert": str(k)}
           for art, k in sorted(collections.Counter(z["art"] for z in zeilen).items())]
    out += [{"kennzahl": f"objekte_{k}", "wert": str(v)} for k, v in sorted(zaehl.items())]
    out.append({"kennzahl": "eintraege_ohne_quartier",
                "wert": str(sum(1 for z in zeilen if z["quartiere"] == orte_kuratiert.OFFEN))})
    if a.stichprobe.exists():
        n, c = titel_treffer(a.ausgabe, a.stichprobe)
        out.append({"kennzahl": "titel_stichprobe", "wert": str(n)})
        out += [{"kennzahl": f"titel_mit_treffer_{k}", "wert": str(v)} for k, v in sorted(c.items())]
    schreibe_tsv(a.ergebnisse / "orte_opendata_zaehlung.tsv", out, ["kennzahl", "wert"])
    for z in out:
        print(f"{z['kennzahl']}\t{z['wert']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
