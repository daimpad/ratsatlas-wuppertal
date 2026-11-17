"""Bebauungspläne: Plannummern in Vorlagentiteln mit den Geltungsbereichen der Bebauungspläne der Stadt Wuppertal
abgleichen (CC BY-ND 4.0: Geometrien unverändert, CLAUDE.md 3.2). Wuppertal (Phase 3, 17.11.2026): rechtsverbindliche
Pläne und laufende Verfahren; Nummernschema der Titel in config.BPLAN_NUMMER (gefunden mit ortsnamen.plan_nummern),
Vergleichsform in canonical. Aufbau aus dem Ratsatlas Bonn; das Bonner Schema („6322-2“) bleibt erkannt."""
import json
import re

from shapely.geometry import shape
from shapely.ops import unary_union

from . import config

MIN_SHARE = 0.05  # Ortsteile mit weniger als 5 % der Planfläche bleiben unberücksichtigt


# Eigenschaften eines Plans: Bonner Modell (name, inkraft_seit, plan) oder die Feldnamen der Wuppertaler Quelle
# (config.GEO_FELDER["bplan"]; die Dateien bleiben unverändert, CC BY-ND 4.0, pipeline/bplan.py)
def _feld(props, bonn, rolle):
    wert = props.get(bonn)
    if wert in (None, ""):
        wert = props.get(config.GEO_FELDER["bplan"][rolle])
    return str(wert).strip() if wert is not None else ""


def plan_name(props):
    """Plannummer: „name“ (Bonner Modell) oder VERFAHREN (Wuppertal, z. B. „30A“)."""
    return _feld(props, "name", "nummer")


def inkraft(props):
    """Datum der Rechtskraft als JJJJ-MM-TT: „inkraft_seit“ oder Dat_Recht (TT.MM.JJJJ); sonst None."""
    if props.get("inkraft_seit"):
        return props["inkraft_seit"]
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", _feld(props, "inkraft_seit", "rechtskraft"))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def plan_pdf(props):
    """Plan (PDF): „plan“ oder Plan1; Werte ohne http(s) gelten als fehlend."""
    wert = _feld(props, "plan", "plan")
    return wert if re.match(r"https?://", wert) else None


def plan_key(name):
    """„6322-2 Teil A“ → „6322-2“ (Teilpläne gehören zur Plannummer im Titel)."""
    return (name or "").split(" ")[0]


BONN = re.compile(r"\d{4}-\d{1,3}")


def canonical(nr):
    """Vergleichsform. Bonn: „6322-2 Teil A“, „6622-2-A“, „7722-44 a“ → „6322-2A“, „6622-2A“, „7722-44A“.
    Wuppertal (Phase 3, 17.11.2026; Datensatz VERFAHREN wie „1273_2“, „1276_1V“, „805B_WEST“): Titel schreiben
    „1273/2“, „1276/1 V“, „805 B West“ → Schrägstrich als „_“, Buchstabe direkt an die Ziffer, Himmelsrichtung mit „_“,
    „Süd“ als „SUED“, alles groß."""
    n = (nr or "").strip()
    if BONN.match(n):
        n = re.sub(r"\s*Teil\s*", "", n, flags=re.I).upper()
        return re.sub(r"[\s-]+(?=[A-D]$|I{1,3}$)", "", n)
    n = n.upper().replace("Ü", "UE").replace("/", "_")
    n = re.sub(r"(?<=\d)\s+(?=[A-Z](?:\d|\b))(?![A-Z]{2})", "", n)      # „805 B“ → „805B“, „1276_1 V“ → „1276_1V“
    return re.sub(r"\s+", "_", n)                                         # „805B WEST“ → „805B_WEST“


def base_number(nr):
    """Grundnummer: Bonn „6322-2“; Wuppertal die führenden Ziffern („1273“ aus „1273_2“, „798“ aus „798A“).
    Annahme: Zusätze bezeichnen Teil- oder Änderungspläne derselben Grundnummer (Bedeutung nicht belegt)."""
    m = BONN.match(nr or "") or re.match(r"\d{2,4}(?!\d)", (nr or "").strip())
    return m.group(0) if m else None


# Treffer einer Plannummer im Datensatz der rechtskräftigen Pläne → Konfidenz der Verortung (B3)
CONFIDENCE = {"eindeutig": "hoch", "grundnummer": "niedrig", "mehrdeutig": "niedrig"}


class Plans:
    """Geltungsbereiche je Plannummer. Wuppertal (Phase 3, 17.11.2026): rechtsverbindliche Pläne und laufende Verfahren
    (config.BPLAN, config.BPLAN_LAUFEND); gleiche Nummer in beiden (Änderungsverfahren) gilt als ein Plan."""
    def __init__(self, path=None):
        self.by_nr, self.by_full, self.by_base = {}, {}, {}
        pfade = [path] if path is not None else [config.BPLAN, config.BPLAN_LAUFEND]
        for path in pfade:
            if not path.exists():
                continue
            for f in json.loads(path.read_text())["features"]:
                name = plan_name(f["properties"])
                self.by_nr.setdefault(plan_key(name), []).append(f)
                self.by_full.setdefault(canonical(name), []).append(f)
                self.by_base.setdefault(base_number(name), []).append(f)

    def match(self, nr):
        return self.classify(nr)[1]

    def classify(self, nr):
        """(Klasse, Features): eindeutig (genau ein Plan, ggf. Teilplan), grundnummer (Zusatz im Titel,
        im Datensatz nur die Grundnummer), mehrdeutig (mehrere Pläne), nicht_im_datensatz."""
        full, base = canonical(nr), base_number(nr)
        hits = self.by_full.get(full)
        if not hits:
            hits = self.by_base.get(base, [])
            if hits and full != base:
                return "grundnummer", hits
        names = {plan_name(f["properties"]) for f in hits}
        if not hits:
            return "nicht_im_datensatz", []
        return ("eindeutig" if len(names) == 1 else "mehrdeutig"), hits


def plan_locations(plan_rows, ortsteile, plans=None):
    """plan_rows: (paper_id, plannummer, fundstelle). Liefert Orte (je Plan und berührtem Ortsteil,
    Punkt = innerer Punkt der Schnittfläche) und Ortsbezüge der Stufe B (Methode B3: Konfidenz „hoch“
    bei eindeutigem Treffer, sonst „niedrig“)."""
    plans = plans or Plans()
    locations, rows = {}, []
    for pid, nr, evidence in plan_rows:
        cls, hits = plans.classify(nr)
        if not hits:
            continue
        by_name = {}
        for f in hits:  # mehrere Flächen desselben Plans (z. B. 7219-15) zusammenführen
            by_name.setdefault(plan_name(f["properties"]), []).append(shape(f["geometry"]).buffer(0))
        for name, geoms in by_name.items():
            parts = ortsteile.overlaps(unary_union(geoms))
            for ot, part, _ in [x for x in parts if x[2] >= MIN_SHARE] or parts[:1]:
                pt = part.representative_point()
                loc_id = f"bplan:{name}|{ot['ortsteil_bez']}"
                locations[loc_id] = (loc_id, None, None, None, f"Bebauungsplan {name}", round(pt.x, 6),
                                     round(pt.y, 6), ot["ortsteil_bez"], ot["ortsteil"], ot["bezirk_bez"],
                                     "bebauungsplan", config.QUELLE_BPLAN)
                rows.append((pid, loc_id, "B", "bebauungsplan", CONFIDENCE[cls], evidence, pid))
    return locations, rows


# Verfahrensschritte der Bauleitplanung, aus dem Titel abgeleitet; Fundstelle im BauGB. Reihenfolge = Ablauf.
STEPS = [
    # „in Aufstellung befindlich“ beschreibt nur den Stand, keinen Beschluss
    ("aufstellung", "Aufstellungsbeschluss", "§ 2 Abs. 1 BauGB",
     r"aufstellungsbeschluss|beschluss (?:zur|über die) aufstellung|(?<!in )aufstellung (?:des|der|eines)|einleitung des \w*verfahrens|einleitungsbeschluss"),
    ("fruehzeitig", "Frühzeitige Beteiligung", "§ 3 Abs. 1, § 4 Abs. 1 BauGB", r"frühzeitig"),
    ("veroeffentlichung", "Veröffentlichung (Offenlage)", "§ 3 Abs. 2, § 4 Abs. 2 BauGB", r"veröffentlichung|offenlage|offenlegung|auslegung"),
    ("satzung", "Satzungsbeschluss", "§ 10 Abs. 1 BauGB", r"satzungsbeschluss|als satzung"),
]
KINDS = [("aenderung", r"\d\.\s*änderung|änderung des bebauungsplan"), ("aufhebung", r"aufhebung")]


def title_steps(title):
    """Verfahrensschritte und Art (Änderung, Aufhebung), die der Titel nennt – abgeleitet."""
    t = (title or "").lower()
    return ([k for k, _, _, rx in STEPS if re.search(rx, t)], [k for k, rx in KINDS if re.search(rx, t)])


def register(papers, plans=None):
    """Je Plannummer aus den Titeln: zugeordnete Pläne (belegt, Stadt Wuppertal), berührte Ortsteile und die
    Vorlagen chronologisch mit den im Titel genannten Verfahrensschritten (abgeleitet). Grundlage für die
    Planchronik; vereinfachte Verfahren (§§ 13, 13a BauGB) haben weniger Schritte."""
    plans = plans or Plans()
    out = {}
    for p in papers:
        for x in p.get("plans") or []:
            e = out.get(x["nr"])
            if e is None:
                cls, hits = plans.classify(x["nr"])
                seen = {}
                for f in hits:
                    seen.setdefault(plan_name(f["properties"]), {
                        "name": plan_name(f["properties"]), "inkraft_seit": inkraft(f["properties"]),
                        "plan": plan_pdf(f["properties"]), "begruendung": f["properties"].get("begruendung")})
                e = out[x["nr"]] = {"nr": x["nr"], "treffer": cls, "plaene": sorted(seen.values(), key=lambda v: v["name"]),
                                    "ortsteile": set(), "vorlagen": []}
            e["ortsteile"] |= {l["ortsteil"] for l in p["locations"] if l["method"] == "bebauungsplan" and l.get("ortsteil")
                               and (l.get("name") or "").removeprefix("Bebauungsplan ") in {v["name"] for v in e["plaene"]}}
            steps, kinds = title_steps(p["name"])
            e["vorlagen"].append({"drucksache": p["reference"], "datum": p["date"], "titel": p["name"],
                                  "art": p["paper_type"], "stand": p.get("stand"), "schritte": steps, "arten": kinds,
                                  "fundstelle": x["evidence"]})
    for e in out.values():
        e["ortsteile"] = sorted(e["ortsteile"])
        e["vorlagen"].sort(key=lambda v: (v["datum"] or "", v["drucksache"]))
    return {"schritte": [{"id": k, "label": label, "fundstelle": ref} for k, label, ref, _ in STEPS],
            "plaene": sorted(out.values(), key=lambda e: e["nr"])}
