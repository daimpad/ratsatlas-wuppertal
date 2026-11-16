"""Akteure: Einreichende aus Vorlagenart und Titel; Auflösung der Sammelklasse „Co-Dezernat“.

Die OParl-API setzt `originatorPerson`/`originatorOrganization` nicht. Einreichende werden
deshalb abgeleitet und als abgeleitet gekennzeichnet (method, evidence).
"""
import csv
import json
import re

from . import config, vorlagenart

CO_DEZERNAT = "Co-Dezernat"   # Bonner Verwaltungsgliederung; TODO Messstufe 4 (organizations/at)

# Vorlagenarten aus Bonn (exakte Namen). Wuppertaler Arten wie „Antrag CDU“, „Gemeinsamer Antrag BV“, „Große Anfrage
# die Linke“ oder „Antwort auf Anfragen“ (CLAUDE.md 3.1) ordnet vorlagenart.zerlege zu (Phase 2, Regeltabelle aus
# Messstufe 5); maßgeblich für die Einordnung ist kategorie() unten, nicht die Mengen allein.
VERWALTUNG_TYPES = {
    "Beschlussvorlage",
    "Beschlussvorlage: Einleitung",
    "Beschlussvorlage: Auftrag",
    "Mitteilungsvorlage",
    "Stellungnahme der Verwaltung",
    "Informationsbrief",
    "Bürgerbrief",
    "Dringlichkeitsentscheidung OB",
}
EINWOHNER_TYPES = {
    "Bürgerantrag § 24 GO - Öffentlich",
    "Anregungen und Beschwerden",
    "Einwohnerfrage",
}
POLITIK_TYPES = {
    "Antrag",
    "Änderungsantrag",
    "Dringlichkeitsantrag",
    "Große Anfrage",
    "Kleine Anfrage",
}

# (Anzeigename, Muster im Titel, Muster im Namen der Fraktion/Gruppe in organizations.json)
# Wuppertal: nur die in CLAUDE.md 3.1/5.3 genannten Einreichenden (CDU, SPD, B90/Grüne, die Linke, AfD, FDP). Die Bonner
# Fraktionen und Gruppen (BBB, SBI, BIG, Allianz für Bonn, Rhein.Grün) sind entfernt, ebenso Volt, BSW, Die PARTEI und
# Piraten (in Wuppertal nicht belegt). TODO Messstufe 5: Fraktionen und Gruppen je Wahlperiode (2020–2025, 2025–2030)
# aus paperType und organizations, „FDP / WfW“ auflösen; Vorbild ratsatlas-koeln @d609111 (Partei mit von/bis). Dabei
# ausdrücklich prüfen, ob Volt, BSW, Die PARTEI oder Piraten in Wuppertal einreichen (Bonner Muster in allris-test
# @52fe9ca, pipeline/actors.py); bis dahin bleiben solche Anträge ohne Zuordnung zu einer Partei.
PARTIES = [
    ("CDU", r"CDU", r"^CDU"),
    ("SPD", r"SPD", r"^SPD"),
    ("Grüne", r"(?<![\w.])(?:Grüne|GRÜNE|Bündnis 90)", r"GRÜNE|Grüne"),
    ("FDP", r"FDP", r"^FDP"),
    ("Die Linke", r"(?<!\w)(?:Linke|LINKE)", r"Linke"),
    ("AfD", r"(?<!\w)AfD(?!\w)", r"^AfD|^Alternative für Deutschland"),
]
GROUPS = [
    ("Koalition", r"[Kk]oalition"),
    ("interfraktionell", r"[Ii]nterfraktionell"),
]
UNRESOLVED = r"u\.\s?w\."
KEYWORD = re.compile(r"(?:Änderungs|Dringlichkeits)?[Aa]ntrag|Anfrage|(?<!\w)(?:AA|ÄA)(?!\w)")
RAT_CLASSES = ("Fraktion", "Gruppen", "Einzelmandate")


def _segments(title):
    """Präfix vor dem ersten Doppelpunkt, sonst Fenster um „Antrag“/„Anfrage“."""
    head, sep, _ = title.partition(":")
    if sep and len(head) <= 100:
        yield head
    for m in KEYWORD.finditer(title):
        yield title[max(0, m.start() - 40): m.end() + 25]


def _active(org, date):
    return (not org.get("endDate") or org["endDate"] >= date) and (
        not org.get("startDate") or org["startDate"] <= date
    )


def _match_org(orgs, pattern, date, classes, bezirk=None):
    for cls in classes:
        for o in orgs:
            if o.get("classification") != cls or not re.search(pattern, o["name"]):
                continue
            if bezirk and not o["name"].endswith(bezirk):
                continue
            if _active(o, date):
                return o["id"]
    return None


def kategorie(paper_type):
    """Einordnung einer Vorlagenart: „verwaltung“, „einwohner“, „politik“ oder None. Zuerst die Bonner Namen, dann die
    Wuppertaler Zerlegung (vorlagenart.zerlege)."""
    if paper_type in VERWALTUNG_TYPES:
        return vorlagenart.VERWALTUNG
    if paper_type in EINWOHNER_TYPES:
        return "einwohner"
    if paper_type in POLITIK_TYPES:
        return vorlagenart.POLITIK
    return vorlagenart.kategorie(paper_type)


def _aus_vorlagenart(z, ptype, orgs, date, bezirke):
    """Einreichende aus der zerlegten Vorlagenart (eine Zeile; „aus Vorlagenart abgeleitet“)."""
    name = vorlagenart.anzeigename(z["einreichende"])
    org_pat = next((o for n, _, o in PARTIES if n == name), None)
    if z["einreichende"] in vorlagenart.EINZELMANDAT:
        return dict(actor=name, actor_type="Einzelmandat", organization_id=None, method="paper_type", evidence=ptype)
    if z["ebene"] == "BV":
        bezirk = next(iter(bezirke)) if len(bezirke) == 1 else None
        org = _match_org(orgs, org_pat, date, ("Bezirksfraktionen (intern)",), bezirk) if bezirk and org_pat else None
        return dict(actor=f"{name}-Bezirksfraktion" + (f" {bezirk}" if bezirk else ""), actor_type="Bezirksfraktion",
                    organization_id=org, method="paper_type", evidence=ptype)
    org = _match_org(orgs, org_pat, date, RAT_CLASSES) if org_pat else None
    return dict(actor=name, actor_type="Fraktion/Gruppe", organization_id=org, method="paper_type", evidence=ptype)


def originators(paper, orgs, bezirke=()):
    """Einreichende einer Vorlage als Liste von Zeilen (actor, actor_type, organization_id,
    method, evidence). `bezirke`: Stadtbezirke der befassten Bezirksvertretungen."""
    ptype, date = paper.get("paperType"), paper.get("date") or ""
    kat = kategorie(ptype)
    if kat == vorlagenart.VERWALTUNG:
        org = (paper.get("underDirectionOf") or [None])[0]
        return [dict(actor="Verwaltung", actor_type="Verwaltung", organization_id=org,
                     method="paper_type", evidence=ptype)]
    if kat == "einwohner":
        # Keine Namen natürlicher Personen (Datenschutz, CLAUDE.md 5.2).
        return [dict(actor="Einwohner:innen", actor_type="Einwohner:in", organization_id=None,
                     method="paper_type", evidence=ptype)]
    if kat != vorlagenart.POLITIK:
        return []
    z = vorlagenart.zerlege(ptype)
    if z and z["einreichende"] not in ("", "–"):
        # mehrere Einreichende (gemeinsamer Antrag, Regel 9) je eine Zeile
        return [_aus_vorlagenart({**z, "einreichende": e}, ptype, orgs, date, bezirke)
                for e in vorlagenart.einreichende_liste(z["einreichende"])]
    # Einreichende nicht in der Vorlagenart (Bonner Arten, „Gemeinsamer Antrag“): aus dem Titel, sonst offen
    for seg in _segments(paper.get("name") or ""):
        rows = _from_segment(seg.strip(), orgs, date, bezirke)
        if rows:
            return rows
    return []


def _from_segment(seg, orgs, date, bezirke):
    rows = []
    bezirks_fraktion = "Bezirksfraktion" in seg
    hits = sorted((m.start(), name, org_pat) for name, title_pat, org_pat in PARTIES
                  if (m := re.search(title_pat, seg)))
    for _, name, org_pat in hits:
        if bezirks_fraktion:
            bezirk = next(iter(bezirke)) if len(bezirke) == 1 else None
            org = _match_org(orgs, org_pat, date, ("Bezirksfraktionen (intern)",), bezirk) if bezirk else None
            actor = f"{name}-Bezirksfraktion" + (f" {bezirk}" if bezirk else "")
            rows.append(dict(actor=actor, actor_type="Bezirksfraktion", organization_id=org,
                             method="title", evidence=seg))
        else:
            org = _match_org(orgs, org_pat, date, RAT_CLASSES)
            rows.append(dict(actor=name, actor_type="Fraktion/Gruppe", organization_id=org,
                             method="title", evidence=seg))
    for name, pat in GROUPS:
        if re.search(pat, seg):
            rows.append(dict(actor=name, actor_type=name, organization_id=None,
                             method="title", evidence=seg))
    if rows and re.search(UNRESOLVED, seg):
        rows.append(dict(actor="weitere (u.w., nicht aufgelöst)", actor_type="unaufgelöst",
                         organization_id=None, method="title", evidence=seg))
    return rows


def amt_label(org):
    """Anzeigename eines Verwaltungsbereichs: Amt laut `classification`; bei „Co-Dezernat“
    der Verwaltungsbereich selbst (z. B. „01-2 Ratsbüro“)."""
    if not org:
        return None
    cls = org.get("classification")
    return org["name"] if cls == CO_DEZERNAT or not cls else cls


def responsibilities(paper, orgs_by_id, papers_by_id):
    """Federführung (strukturiert) und, bei „Co-Dezernat“, fachliche Zuständigkeit aus den
    Stellungnahmen der Verwaltung (abgeleitet). Fehlt `underDirectionOf`, gilt die eindeutige Stelle aus dem Kopf der
    Vorlagendokumente (Schritt `amtskopf`, CLAUDE.md 5.3): method „pdf_kopf“, derived 1, evidence nur die Fundstelle
    („Seite 1, Kopf, Zeile N“), keine Wörter aus dem Dokument; bei mehrdeutiger Stelle keine Zuordnung."""
    lead = (paper.get("underDirectionOf") or [None])[0]
    if not lead:
        kopf = _amtskopf(paper)
        return [dict(organization_id=kopf["organization_id"], kind="federfuehrend", method="pdf_kopf",
                     evidence=kopf["fundstelle"], derived=1)] if kopf else []
    klasse = aemterliste().get(lead)
    rows = [dict(organization_id=lead, kind="federfuehrend", method="underDirectionOf",
                 evidence=f"Ämterliste: {klasse}" if klasse else None, derived=0)]
    if (orgs_by_id.get(lead) or {}).get("classification") != CO_DEZERNAT:
        return rows
    seen = set()
    for sub_id in paper.get("subordinatedPaper") or []:
        sub = papers_by_id.get(sub_id)
        if not sub or sub.get("paperType") not in VERWALTUNG_TYPES:
            continue
        org = (sub.get("underDirectionOf") or [None])[0]
        if not org or org in seen or (orgs_by_id.get(org) or {}).get("classification") == CO_DEZERNAT:
            continue
        seen.add(org)
        rows.append(dict(organization_id=org, kind="fachlich", method="stellungnahme",
                         evidence=sub.get("reference"), derived=1))
    return rows


AEMTERLISTE = config.ROOT / "explore" / "ergebnisse" / "aemter.tsv"
_AEMTER = {}


def aemterliste(pfad=None):
    """Klasse je Organisation aus der Ämterliste (Phase 1, explore/aemter.py; Entscheidungen 13.11.2026): „amt“,
    „beteiligung“, „politisch“, „sonstig“ oder „offen“. Ohne Datei: leer (die Federführung bleibt ohne Klasse)."""
    pfad = pfad or AEMTERLISTE
    if pfad not in _AEMTER:
        try:
            with open(pfad, encoding="utf-8") as f:
                _AEMTER[pfad] = {z["id"]: z["klasse"] for z in csv.DictReader(f, delimiter="\t") if z.get("id")}
        except OSError:
            _AEMTER[pfad] = {}
    return _AEMTER[pfad]


_AMTSKOPF = {}
RE_FUNDSTELLE = re.compile(r"Seite [12], Kopf, Zeile \d+")


def amtskopf_ergebnisse(pfad=None):
    """Ergebnis des Schritts `amtskopf` (config.AMTSKOPF): {Vorlage: {organization_id, datei, fundstelle}}, nur
    Vorlagen mit eindeutiger Stelle. Fehlt die Datei oder ist sie unlesbar: leer (keine Federführung aus dem Kopf).
    Zwischengespeichert je Pfad und Änderungszeit."""
    pfad = pfad or config.AMTSKOPF
    try:
        marke = (str(pfad), pfad.stat().st_mtime_ns)
    except OSError:
        return {}
    if marke not in _AMTSKOPF:
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8")).get("vorlagen")
        except (OSError, ValueError, AttributeError):
            daten = None
        _AMTSKOPF.clear()
        _AMTSKOPF[marke] = daten if isinstance(daten, dict) else {}
    return _AMTSKOPF[marke]


def _amtskopf(paper):
    """Eintrag aus dem Kopf der Vorlagendokumente, nur wenn er zur Vorlage passt: Kennung einer Organisation mit Präfix
    at, Fundstelle in der festen Form und die Datei noch in mainFile/auxiliaryFile (sonst veraltet: Schritt erneut ausführen)."""
    e = amtskopf_ergebnisse().get(paper.get("id"))
    if not isinstance(e, dict) or "/organizations/at/" not in str(e.get("organization_id") or ""):
        return None
    if not RE_FUNDSTELLE.fullmatch(str(e.get("fundstelle") or "")):
        return None
    kennungen = set()
    for feld in ("mainFile", "auxiliaryFile"):   # wie aenderungen.DATEIFELDER und dokumente.aufgaben
        werte = paper.get(feld)
        werte = [werte] if isinstance(werte, dict) else werte if isinstance(werte, list) else []
        kennungen |= {f.get("id") or f.get("accessUrl") for f in werte if isinstance(f, dict) and not f.get("deleted")}
    return e if e.get("datei") in kennungen else None
