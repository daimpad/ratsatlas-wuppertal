"""Flächen für die Webseite (data/export/<stadt>/flaechen/*.json).

Quartiere und Stadtbezirke: Die Seite braucht für Navigation und Umrisse keine Zentimetergenauigkeit. Vereinfacht wird
mit etwa 2 m Toleranz (Douglas-Peucker, Topologie je Fläche erhalten), Koordinaten auf 5 Nachkommastellen (rund 1 m).

Bebauungspläne: unverändert. Die Geometrien der Stadt Wuppertal stehen unter CC BY-ND 4.0 (CLAUDE.md 3.2 und 6);
Vereinfachen, Runden und Reparieren (make_valid) wären eine Bearbeitung. write() übernimmt sie deshalb ohne simplify()
mit denselben Zahlenwerten (json-Rundlauf, nur kompakt geschrieben) und ergänzt auf oberster Ebene einen Lizenzhinweis
(„meta“, ein zusätzliches Element der FeatureCollection; Features bleiben unberührt). Ungültige Flächen bleiben
ungültig; Leaflet zeichnet sie trotzdem.

Abweichung für den gemeinsamen Kern: ratsatlas-koeln @d609111 (flaechen.py) vereinfacht auch die Bebauungspläne, dort
zulässig (dl-de/by 2.0). Künftig je Quelle angeben, ob die Geometrie bearbeitet werden darf (hier UNVERAENDERT).

Die Dateien enden auf .json, damit Webserver sie wie die übrigen Daten komprimieren. Für Verortung und Datenpaket
bleiben die Flächen in data/geo/ maßgeblich. simplify() bleibt unverändert, kontext.py nutzt es."""
import json

from shapely import make_valid
from shapely.geometry import MultiPolygon, mapping, shape

from . import config

TOLERANZ = 0.00002  # Grad, etwa 1,4 m in Nord-Süd- und 2,2 m in Ost-West-Richtung
NACHKOMMA = 5
# Schlüssel → Quelldatei; die Pfade werden beim Aufruf gelesen (Tests lenken config um)
DATEIEN = {"ortsteile": lambda: config.ORTSTEILE, "bezirke": lambda: config.STADTBEZIRKE,
           "bebauungsplaene": lambda: config.BPLAN}
# Flächen, deren Lizenz keine Bearbeitung erlaubt (CC BY-ND 4.0): ohne Vereinfachung, Rundung oder make_valid
UNVERAENDERT = {"bebauungsplaene"}


def _round(o):
    if isinstance(o, float):
        return round(o, NACHKOMMA)
    if isinstance(o, (list, tuple)):
        return [_round(x) for x in o]
    return o


def _gueltig(g):
    """Flächen, die sich selbst schneiden (in den Quelldaten der Stadt z. B. Bebauungsplan 8118-1), gültig machen; aus
    einer gemischten Sammlung nach make_valid bleiben nur die Flächen."""
    if g.is_valid or g.geom_type not in ("Polygon", "MultiPolygon"):
        return g
    v = make_valid(g)
    if v.geom_type == "GeometryCollection":
        polys = [x for x in v.geoms if x.geom_type in ("Polygon", "MultiPolygon")]
        v = MultiPolygon([q for x in polys for q in (x.geoms if x.geom_type == "MultiPolygon" else [x])])
    return v


def simplify(collection, toleranz=TOLERANZ):
    """FeatureCollection mit vereinfachten Geometrien; Eigenschaften unverändert, leere Geometrien bleiben leer."""
    feats = []
    for f in collection.get("features", []):
        g = f.get("geometry")
        if g:
            s = _gueltig(shape(g))
            v = s.simplify(toleranz, preserve_topology=True)
            g = _round(mapping(v if not v.is_empty else s))
        feats.append({"type": "Feature", "properties": f.get("properties", {}), "geometry": g})
    return {"type": "FeatureCollection", "features": feats}


def unveraendert(collection):
    """FeatureCollection der Bebauungspläne für die Seite: Features unverändert (gleiche Objekte, gleiche Zahlen), dazu
    Lizenz und Namensnennung unter „meta“ (CC BY-ND 4.0). Ein vorhandenes „meta“ der Quelle bleibt erhalten."""
    meta = dict(collection.get("meta") or {})
    meta.setdefault("license", config.SOURCES[config.QUELLE_BPLAN]["license"])
    meta.setdefault("attribution", config.NAMENSNENNUNG_BPLAN)
    meta["geometrie"] = "unverändert (CC BY-ND 4.0: keine Vereinfachung, Rundung oder Reparatur)"
    return {**collection, "meta": meta}


def write(out):
    """Schreibt die Flächen nach out/flaechen/ (Quartiere und Stadtbezirke vereinfacht, Bebauungspläne unverändert);
    fehlende Quelldateien werden übersprungen."""
    target = out / "flaechen"
    target.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name, quelle in DATEIEN.items():
        src = quelle()
        if not src.exists():
            continue
        roh = json.loads(src.read_text(encoding="utf-8"))
        data = unveraendert(roh) if name in UNVERAENDERT else simplify(roh)
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        (target / f"{name}.json").write_text(text, encoding="utf-8")
        sizes[name] = len(text)
    return sizes
