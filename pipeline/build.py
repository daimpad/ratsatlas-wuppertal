"""Normalisierung der Rohdaten in eine SQLite-Datenbank (data/build/allris.sqlite)."""
import csv
import json
import re
import random
import sqlite3
from collections import Counter

from . import actors, config
from .geo import Ortsteile
from .ortsnamen import plan_nummern
from .ortsverzeichnis import Wuppertal
from .plans import Plans, plan_locations
from . import volltext
from .objekte import Objekte
from . import referenz

SCHEMA = """
CREATE TABLE source (
  name TEXT PRIMARY KEY, url TEXT, license TEXT, retrieved_at TEXT);
CREATE TABLE organization (
  id TEXT PRIMARY KEY, name TEXT, short_name TEXT, org_type TEXT, classification TEXT,
  label TEXT, start_date TEXT, end_date TEXT, web TEXT, source TEXT);
CREATE TABLE paper (
  id TEXT PRIMARY KEY, reference TEXT, name TEXT, paper_type TEXT, date TEXT,
  under_direction_of TEXT REFERENCES organization, web TEXT,
  main_file_url TEXT, main_file_name TEXT, source TEXT);
-- method: „oparl“ (superordinatedPaper/subordinatedPaper) oder „referenz“ (aus der Vorlagennummer abgeleitet,
-- pipeline/referenz.py; derived = 1, evidence = Zusatz und Grundnummer)
CREATE TABLE paper_relation (
  parent_id TEXT, child_id TEXT, source TEXT, method TEXT, evidence TEXT, derived INTEGER,
  PRIMARY KEY (parent_id, child_id));
CREATE TABLE meeting (
  id TEXT PRIMARY KEY, name TEXT, start_date TEXT, cancelled INTEGER, source TEXT);
CREATE TABLE agenda_item (
  id TEXT PRIMARY KEY, meeting_id TEXT REFERENCES meeting, number TEXT, name TEXT,
  result TEXT, public INTEGER, source TEXT);
CREATE TABLE consultation (
  id TEXT PRIMARY KEY, paper_id TEXT REFERENCES paper, position INTEGER,
  organization_id TEXT REFERENCES organization, role TEXT, authoritative INTEGER,
  meeting_id TEXT REFERENCES meeting, agenda_item_id TEXT REFERENCES agenda_item,
  source TEXT, link_source TEXT);
CREATE TABLE location (
  id TEXT PRIMARY KEY, street TEXT, postal_code TEXT, sub_locality TEXT, description TEXT,
  lon REAL, lat REAL, ortsteil TEXT, ortsteil_nr INTEGER, stadtbezirk TEXT,
  level TEXT /* strasse | ortsteil | stadtbezirk */, source TEXT);
CREATE TABLE paper_location (
  paper_id TEXT REFERENCES paper, location_id TEXT REFERENCES location, stage TEXT,
  method TEXT, confidence TEXT, evidence TEXT, source_object TEXT,
  PRIMARY KEY (paper_id, location_id, method));
CREATE TABLE paper_plan (
  paper_id TEXT REFERENCES paper, plan_nr TEXT, evidence TEXT, match TEXT,
  PRIMARY KEY (paper_id, plan_nr));
-- Ortsbezüge aus dem Titel, die einem eindeutig zugeordneten Bebauungsplan weichen (Vorrang B3, Audit)
CREATE TABLE plan_precedence (
  paper_id TEXT REFERENCES paper, location_id TEXT REFERENCES location, method TEXT, evidence TEXT);
CREATE TABLE paper_originator (
  paper_id TEXT REFERENCES paper, actor TEXT, actor_type TEXT,
  organization_id TEXT REFERENCES organization, method TEXT, evidence TEXT, derived INTEGER);
CREATE TABLE paper_responsibility (
  paper_id TEXT REFERENCES paper, organization_id TEXT REFERENCES organization, kind TEXT,
  method TEXT, evidence TEXT, derived INTEGER);
CREATE INDEX consultation_paper ON consultation(paper_id);
CREATE INDEX relation_child ON paper_relation(child_id);
CREATE INDEX paper_location_loc ON paper_location(location_id);
CREATE INDEX location_ortsteil ON location(ortsteil);
CREATE INDEX originator_paper ON paper_originator(paper_id);
CREATE INDEX responsibility_paper ON paper_responsibility(paper_id);
"""


def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# Zahlen mit bis zu vier Stellen gelten in Ortsangaben der Stadt als Hausnummern; fünfstellige Zahlen (Postleitzahlen)
# nie (die Grenzen (?<!\d) … (?!\d) schließen sie aus; Bonn prüfte zusätzlich auf 5xxxx, ohne Wirkung); check.py prüft
_NUMMER = re.compile(r"(?<!\d)\d{1,4}(?:\s?[a-zA-Z](?![a-zA-ZäöüÄÖÜß]))?"
                     r"(?:\s*(?:-|–|/|bis)\s*\d{1,4}(?:\s?[a-zA-Z](?![a-zA-ZäöüÄÖÜß]))?)?(?!\d)")


def ohne_hausnummer(text):
    """Ortsangabe der Stadt ohne Hausnummer (CLAUDE.md 5.2): bisher hätte eine Hausnummer in der Quelle die
    tägliche Veröffentlichung angehalten, statt die Straße zu zeigen (Code-Prüfung 23.10.2026)."""
    out = re.sub(r"\s+,", ",", re.sub(r"\s{2,}", " ", _NUMMER.sub("", (text or "").strip()))).strip(" ,")
    return out or None


def build():
    for path in (config.PAPERS, config.ORGANIZATIONS):
        if not path.exists():
            raise SystemExit(f"Fehlt: {path} – zuerst `python -m pipeline fetch` ausführen.")
    if not config.CONSULTATIONS_LITE.exists():
        print(f"Hinweis: {config.CONSULTATIONS_LITE} fehlt – Beratungen ohne Sitzung/TOP.")
    # dieselbe Vorlage kann beim seitenweisen Abruf zweimal vorkommen (neue Vorlagen verschieben die Seiten);
    # doppelt eingetragene Einreichende und Zuständigkeiten vermeiden (Code-Prüfung 23.10.2026)
    papers = list({p["id"]: p for p in _read_jsonl(config.PAPERS) if not p.get("deleted")}.values())
    orgs = json.loads(config.ORGANIZATIONS.read_text())
    lite = ({c["uri"]: c for c in _read_jsonl(config.CONSULTATIONS_LITE)}
            if config.CONSULTATIONS_LITE.exists() else {})
    stand = json.loads(config.STAND.read_text()) if config.STAND.exists() else {}

    config.BUILD.mkdir(parents=True, exist_ok=True)
    config.EXPORT.mkdir(parents=True, exist_ok=True)   # Audits entstehen schon beim Aufbau
    config.DB.unlink(missing_ok=True)
    db = sqlite3.connect(config.DB)
    db.executescript(SCHEMA)

    # Abrufzeitpunkte je Quelle (Quellenkennungen aus config, Hunk aus ratsatlas-koeln @d609111); Geodaten erst nach
    # Messstufe G (bis dahin None)
    strassen_stand = (json.loads(config.STRASSEN.read_text())["meta"].get("retrieved_at")
                      if config.STRASSEN.exists() else None)
    bplan_stand = (json.loads(config.BPLAN.read_text())["meta"].get("retrieved_at")
                   if config.BPLAN.exists() else None)
    hnr_stand = (json.loads(config.HAUSNUMMERN.read_text())["meta"].get("retrieved_at")
                 if config.HAUSNUMMERN.exists() else None)
    # Gebiete und laufende Verfahren: Abrufdatum aus dem „meta“ der Dateien in data/geo (tools/geodaten_uebernehmen.py)
    meta = lambda pfad: (json.loads(pfad.read_text()).get("meta", {}).get("retrieved_at") if pfad.exists() else None)
    retrieved = {
        config.QUELLE_OPARL: stand.get("papers"),
        config.QUELLE_GEO: stand.get("geo") or meta(config.ORTSTEILE),
        config.QUELLE_STADTBEZIRKE: stand.get("geo") or meta(config.STADTBEZIRKE),
        config.QUELLE_BPLAN_LAUFEND: meta(config.BPLAN_LAUFEND),
        config.QUELLE_STRASSEN: stand.get("geo") or strassen_stand,
        config.QUELLE_ADRESSEN: stand.get("hausnummern") or hnr_stand,
        config.QUELLE_BPLAN: stand.get("bplan") or bplan_stand,
        "osm": stand.get("objekte"),
    }
    db.executemany("INSERT INTO source VALUES (?,?,?,?)",
                   [(k, v["url"], v["license"], retrieved.get(k)) for k, v in config.SOURCES.items()])

    orgs_by_id = {o["id"]: o for o in orgs}
    db.executemany(
        f"INSERT INTO organization VALUES (?,?,?,?,?,?,?,?,?,'{config.QUELLE_OPARL}')",
        [(o["id"], o["name"], o.get("shortName"), o.get("organizationType"),
          o.get("classification"),
          actors.amt_label(o) if o.get("organizationType") == "Verwaltungsbereich" else o["name"],
          o.get("startDate"), o.get("endDate"), o.get("web")) for o in orgs])

    papers_by_id = {p["id"]: p for p in papers}
    ortsteile = Ortsteile()
    meetings, agenda, locations, bv_bezirke = {}, {}, {}, {}
    rows = {k: [] for k in ("paper", "rel", "cons", "ploc", "orig", "resp", "plan")}

    for p in papers:
        mf = p.get("mainFile") or {}
        rows["paper"].append((p["id"], p.get("reference"), p.get("name"), p.get("paperType"),
                              p.get("date"), (p.get("underDirectionOf") or [None])[0],
                              p.get("web"), mf.get("accessUrl"), mf.get("fileName")))
        for child in p.get("subordinatedPaper") or []:
            rows["rel"].append((p["id"], child))
        for parent in p.get("superordinatedPaper") or []:
            rows["rel"].append((parent, p["id"]))

        bezirke = set()
        for pos, c in enumerate(p.get("consultation") or []):
            org = (c.get("organization") or [None])[0]
            name = (orgs_by_id.get(org) or {}).get("name", "")
            bz = bv_bezirk(name)
            if bz:
                bezirke.add(bz)
            lc = lite.get(c["id"]) or {}
            m, a = lc.get("meeting"), lc.get("agendaItem")
            if m:
                meetings[m["uri"]] = (m["uri"], m.get("name"), m.get("startDate"),
                                      int(bool(m.get("cancelled"))))
            if a:
                agenda[a["uri"]] = (a["uri"], m["uri"] if m else None, a.get("number"),
                                    a.get("name"), a.get("result"),
                                    None if a.get("public") is None else int(a["public"]))
            rows["cons"].append((c["id"], p["id"], pos, org, c.get("role"),
                                 int(bool(c.get("authoritative"))),
                                 m["uri"] if m else None, a["uri"] if a else None,
                                 config.QUELLE_SITZUNG if (m or a) else None))

        for loc in p.get("location") or []:
            geom = (loc.get("geojson") or {}).get("geometry") or {}
            lon = lat = ot = None
            if geom.get("type") == "Point":
                lon, lat = geom["coordinates"][:2]
                ot = ortsteile.locate(lon, lat)
                level, method, conf = "strasse", "oparl_location", "hoch"
            else:
                # Ort nur als subLocality ohne Geometrie → Gebietsfläche (Köln, ratsatlas-koeln @d609111). Wuppertal
                # liefert laut Stichprobe kein `location` (CLAUDE.md 3.1, 5.2: Stufe A entfällt, Messstufe 1–2)
                treffer = ortsteile.by_name(loc.get("subLocality"))
                if treffer:
                    ot, pt = treffer
                    lon, lat = round(pt.x, 6), round(pt.y, 6)
                    level, method, conf = "ortsteil", "oparl_sublocality", "mittel"
                else:
                    level, method, conf = "strasse", "oparl_location", "niedrig"
            locations[loc["id"]] = (
                loc["id"], ohne_hausnummer(loc.get("streetAddress")), loc.get("postalCode"),
                loc.get("subLocality"), ohne_hausnummer(loc.get("description")), lon, lat,
                ot["ortsteil_bez"] if ot else None, ot["ortsteil"] if ot else None,
                ot["bezirk_bez"] if ot else None, level, config.QUELLE_OPARL)
            rows["ploc"].append((p["id"], loc["id"], "A", method, conf,
                                 ohne_hausnummer(loc.get("description")) or loc.get("subLocality"), loc["id"]))

        bv_bezirke[p["id"]] = bezirke
        for nr, ev in plan_nummern(p.get("name")):
            rows["plan"].append((p["id"], nr, ev))
        for r in actors.originators(p, orgs, bezirke):
            rows["orig"].append((p["id"], r["actor"], r["actor_type"], r["organization_id"],
                                 r["method"], r["evidence"], 1))
        for r in actors.responsibilities(p, orgs_by_id, papers_by_id):
            rows["resp"].append((p["id"], r["organization_id"], r["kind"], r["method"],
                                 r["evidence"], r["derived"]))

    # Wuppertal: Straßenverzeichnis und Adressen der Stadt statt OSM-Straßen (pipeline/ortsverzeichnis.py); Stufe A
    # gibt es nicht (kein `location` in der Quelle), daher keine Straßenpunkte aus OParl
    gaz = Wuppertal()
    rows["ploc"] += _stage_b(papers, bv_bezirke, locations, gaz, _punkt_erlaubt(papers, orgs_by_id))
    plans = Plans()
    rows["plan"] = [(pid, nr, ev, plans.classify(nr)[0]) for pid, nr, ev in rows["plan"]]
    plan_locs, plan_rows = plan_locations([r[:3] for r in rows["plan"]], ortsteile, plans)
    locations.update(plan_locs)
    # Vorrang: Bei eindeutigem Plan gilt der Geltungsbereich; Straßen- und Ortsnamen aus dem Titel treten zurück
    sure = {r[0] for r in plan_rows if r[4] == "hoch"}
    precedence = [(r[0], r[1], r[3], r[5]) for r in rows["ploc"] if r[0] in sure and r[2] == "B"]
    rows["ploc"] = [r for r in rows["ploc"] if not (r[0] in sure and r[2] == "B")]
    rows["ploc"] += plan_rows
    print(f"Bebauungspläne: {len({r[0] for r in plan_rows})} Vorlagen mit Geltungsbereich, "
          f"{len({r[0] for r in rows['plan']})} mit Plannummer im Titel, "
          f"{len(sure)} eindeutig (Vorrang vor {len(precedence)} Ortsbezügen aus dem Titel)")
    rows["ploc"] += _objects_in_titles(papers, locations, gaz, {r[0] for r in rows["ploc"]})
    rows["ploc"] += _fulltext(papers, bv_bezirke, locations, gaz, {r[0] for r in rows["ploc"]})
    rows["rel"] += _aus_referenz(papers, rows["rel"])
    rows["ploc"] += _inherited(papers, papers_by_id, rows["ploc"])
    rows["ploc"] += _from_committee(papers, bv_bezirke, locations, gaz, {r[0] for r in rows["ploc"]})

    # OR REPLACE: ändert sich die Quelle während des seitenweisen Abrufs, kann eine Vorlage doppelt kommen
    db.executemany(f"INSERT OR REPLACE INTO paper VALUES (?,?,?,?,?,?,?,?,?,'{config.QUELLE_OPARL}')", rows["paper"])
    db.executemany(f"INSERT OR IGNORE INTO paper_relation VALUES (?,?,'{config.QUELLE_OPARL}',?,?,?)",
                   [r if len(r) == 5 else (*r, "oparl", None, 0) for r in rows["rel"]])
    db.executemany(f"INSERT INTO meeting VALUES (?,?,?,?,'{config.QUELLE_SITZUNG}')", meetings.values())
    db.executemany(f"INSERT INTO agenda_item VALUES (?,?,?,?,?,?,'{config.QUELLE_SITZUNG}')", agenda.values())
    db.executemany(f"INSERT OR REPLACE INTO consultation VALUES (?,?,?,?,?,?,?,?,'{config.QUELLE_OPARL}',?)", rows["cons"])
    db.executemany("INSERT INTO location VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", locations.values())
    db.executemany("INSERT OR IGNORE INTO paper_plan VALUES (?,?,?,?)", rows["plan"])
    db.executemany("INSERT INTO plan_precedence VALUES (?,?,?,?)", precedence)
    db.executemany("INSERT OR IGNORE INTO paper_location VALUES (?,?,?,?,?,?,?)", rows["ploc"])
    db.executemany("INSERT INTO paper_originator VALUES (?,?,?,?,?,?,?)", rows["orig"])
    db.executemany("INSERT INTO paper_responsibility VALUES (?,?,?,?,?,?)", rows["resp"])
    db.commit()
    db.close()
    print(f"{len(papers)} Vorlagen, {len(rows['cons'])} Beratungen, {len(meetings)} Sitzungen, "
          f"{len(agenda)} TOPs, {len(locations)} Orte → {config.DB}")


def _add_location(r, locations, gaz):
    """Ort einer Gazetteer-Zeile in die Ortstabelle; liefert die Orts-ID."""
    if r["level"] == "strasse":
        loc_id, source = f"strasse:{r['name']}|{r['ortsteil']}", r["source"]
    elif r["level"] == "adresse":   # Hauskoordinate (nur wo erlaubt): eigener Schlüssel je Punkt, Name ohne Nummer
        loc_id, source = f"adresse:{r['name']}|{r['lon']:.6f},{r['lat']:.6f}", r["source"]
    elif r["level"] == "objekt":   # Objekt der kuratierten Ortsliste bzw. Gebäude oder Anlage aus OSM (Stufe C)
        loc_id, source = f"objekt:{r['name']}|{r['ortsteil']}", r.get("source") or "osm"
    else:
        loc_id, source = f"{r['level']}:{r['name']}", config.QUELLE_GEO
    nr = (gaz.ot_by_name.get(r["ortsteil"]) or {}).get("ortsteil") if r["ortsteil"] else None
    locations[loc_id] = (loc_id, r["name"] if r["level"] in ("strasse", "adresse", "objekt") else None, None, None,
                         r["name"], r["lon"], r["lat"], r["ortsteil"], nr, r["bezirk"],
                         r["level"], source)
    return loc_id


def _objects_in_titles(papers, locations, gaz, placed):
    """Gebäude und Anlagen aus dem Verzeichnis (OSM) im Titel von Vorlagen ohne eigenen Ortsbezug (Stufe B, Methode
    „objekt_name“, Konfidenz „niedrig“); Audit und einmalig eine Stichprobe."""
    obj = Objekte()
    if not len(obj):
        return []
    out, audit, found = [], [], {}
    for p in papers:
        if p["id"] in placed:
            continue
        for o in obj.im_titel(p.get("name")):
            r = dict(level="objekt", name=o["name"], ortsteil=o["ortsteil"], bezirk=o["bezirk"], lon=o["lon"], lat=o["lat"])
            ev = f"Name im Titel: {o['name']}; Lage laut OpenStreetMap ({o['art']}, {o['osm']})"
            out.append((p["id"], _add_location(r, locations, gaz), "B", "objekt_name", "niedrig", ev, p["id"]))
            audit.append((p["reference"], o["name"], o["art"], o["ortsteil"], o["osm"]))
            found.setdefault(p["reference"], (p, []))[1].append(o)
    _write(config.EXPORT / "audit_objekte_titel.tsv", ["drucksache", "gebäude oder anlage", "art", "ortsteil", "osm"],
           sorted(audit))
    print(f"Gebäude und Anlagen im Titel: {len(found)} Vorlagen ohne eigenen Ortsbezug, {len(out)} Ortsbezüge")
    path = config.EXPORT / "objekte" / "stichprobe_objekte.tsv"
    if found and not path.exists():
        pick = sorted(random.Random(20261021).sample(sorted(found), min(30, len(found))))
        path.parent.mkdir(parents=True, exist_ok=True)
        _write(path, ["nr", "drucksache", "titel", "link", "gebäude oder anlage (Ortsteil)", "urteil (richtig/teilweise/falsch)",
                      "anmerkung"],
               [[i, ref, found[ref][0].get("name"), found[ref][0].get("web") or "",
                 "; ".join(f"{o['name']} ({o['ortsteil']})" for o in found[ref][1]), "", ""]
                for i, ref in enumerate(pick, 1)])
        print(f"Stichprobe Gebäude und Anlagen: {len(pick)} → {path}")
    return out


def _fulltext(papers, bv_bezirke, locations, gaz, placed):
    """Ortsbezüge aus dem Volltext der Hauptdatei (volltext.py) für Vorlagen ohne eigenen Ortsbezug; Audit und
    einmalig eine Stichprobe (ohne Textauszüge).

    Mit Texten (lokal, Dokumentabruf) schreibt der Schritt die abgeleiteten Orte nach config.VOLLTEXT_ORTE (versioniert:
    je Vorlage Befund, Dokumentteil und die Zeilen der Verortung, kein Text). Ohne Texte (GitHub Actions) liest er sie
    von dort und wendet dieselben Regeln an (Entscheidung 17.11.2026, CLAUDE.md 2)."""
    texts = volltext.load_texts()
    mit_texten = bool(texts) or config.TEXTE_ORDNER.exists()
    gespeichert = {} if mit_texten else volltext.gespeicherte_orte()
    if not mit_texten and not gespeichert:
        print(f"Volltext: weder {config.TEXTE} noch {config.TEXTE_ORDNER} noch {config.VOLLTEXT_ORTE.name} – keine "
              "Verortung aus Dokumenten.")
        return []
    text_von = lambda p: texts.get((p.get("mainFile") or {}).get("id")) or volltext.haupttext(p)
    out, audit, found, ablage = [], [], {}, {}
    kette = volltext.einwohner_kette(papers)
    for p in papers:
        if p["id"] in placed or not volltext.allowed(p.get("paperType")) or p["id"] in kette:
            continue
        if mit_texten:
            text = text_von(p)
            if not text:
                continue
            if volltext.titel_ohne_ort(p.get("name")):
                audit.append((p["reference"], "Titel ohne gemeinsamen Ort, nicht verortet", "", "", "", "", "", ""))
                continue
            rows, info = volltext.locate(gaz, text, bv_bezirke.get(p["id"], ()))
        else:
            g = gespeichert.get(p["id"])
            if not g:
                continue
            rows, info = g["zeilen"], {"befund": g["befund"], "teil": g.get("teil", "")}
        if not rows:
            audit.append((p["reference"], info["befund"], info.get("teil", ""), "", "", "", "", ""))
        for r in rows:
            out.append((p["id"], _add_location(r, locations, gaz), "B", r["method"], r["confidence"], r["evidence"], p["id"]))
            audit.append((p["reference"], info["befund"], r["teil"], r["method"], r["name"], r["ortsteil"] or "",
                          r["confidence"], r["nennungen"]))
        if rows:
            found[p["reference"]] = (p, rows)
            ablage[p["id"]] = {"befund": info["befund"], "teil": rows[0]["teil"], "zeilen": rows}
    _write(config.EXPORT / "audit_volltext.tsv",
           ["drucksache", "befund", "teil", "methode", "ort", "ortsteil", "konfidenz", "nennungen"], sorted(audit, key=str))
    if mit_texten:
        n_text = sum(1 for p in papers if text_von(p))
        volltext.orte_speichern(ablage, n_text)
    else:
        n_text = f"{len(gespeichert)} gespeicherte"
    befunde = Counter(a[1].split(" (")[0] for a in {(a[0], a[1]) for a in audit})
    print(f"Volltext: {n_text} Vorlagen mit Text, {len(found)} neu verortet ({len(out)} Ortsbezüge); Befunde {dict(befunde)}")
    _fulltext_sample(found)
    return out


def _fulltext_sample(found):
    """30 Vorgänge mit Verortung aus dem Volltext zur Prüfung (je Vorgang eine Zeile; wird nie überschrieben)."""
    path = config.EXPORT / "volltext" / "stichprobe_volltext.tsv"
    if path.exists() or not found:
        return
    seen, cases = set(), []
    for ref in sorted(found):
        if ref[:6] not in seen:
            seen.add(ref[:6]); cases.append(ref)
    pick = sorted(random.Random(20261020).sample(cases, min(30, len(cases))))
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, ["nr", "drucksache", "titel", "link", "orte (Ortsteil)", "konfidenz", "teil", "urteil (richtig/falsch/unklar)",
                  "anmerkung"],
           [[i, ref, found[ref][0].get("name"), found[ref][0].get("web") or "",
             "; ".join(f"{r['name']} ({r['ortsteil']})" if r["ortsteil"] and r["level"] == "strasse" else r["name"] for r in found[ref][1]),
             "/".join(sorted({r["confidence"] for r in found[ref][1]})), found[ref][1][0]["teil"], "", ""]
            for i, ref in enumerate(pick, 1)])
    print(f"Stichprobe Volltext: {len(pick)} → {path}")


def _write(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _punkt_erlaubt(papers, orgs_by_id):
    """Vorlagen-ID → darf eine Hausnummer im Titel auf die Hauskoordinate führen (maske.hausnummer_punkt_erlaubt:
    nicht bei Eingaben aus der Einwohnerschaft und verbundenen Vorlagen, Bauaufsicht und Umweltschutz, Beratung in
    Gremien für Anregungen und Beschwerden bzw. Bürgerbeteiligung)."""
    from . import maske
    kette = volltext.einwohner_kette(papers)
    name = lambda oid: (orgs_by_id.get(oid) or {}).get("name")
    out = {}
    for p in papers:
        amt = next((name(o) for o in (p.get("underDirectionOf") or []) if name(o)), None)
        gremien = [name((c.get("organization") or [None])[0]) for c in p.get("consultation") or []]
        out[p["id"]] = maske.hausnummer_punkt_erlaubt(p, einwohner=kette, amt_name=amt, gremien=gremien)
    return out


def _stage_b(papers, bv_bezirke, locations, gaz, punkt_erlaubt=None):
    """Stufe B: Ortsbezüge aus dem Titel (Straße mit oder ohne Hausnummer, Quartier, Stadtbezirk, Objekt der Ortsliste);
    `punkt_erlaubt`: Vorlagen-ID → Hauskoordinate zulässig (Vorgabe: nie)."""
    if not gaz.streets:
        print(f"Hinweis: {config.STRASSEN} fehlt oder ist leer – Stufe B ohne Straßen.")
    punkt_erlaubt = punkt_erlaubt or {}
    out, hnr = [], {}
    for p in papers:
        for r in gaz.locate(p.get("name"), bv_bezirke.get(p["id"], ()), punkt_erlaubt=punkt_erlaubt.get(p["id"], False),
                            source_object=p["id"]):
            if "hnr_vorher" in r:
                hnr.setdefault((p["reference"], r["name"]), (r["hnr_vorher"], r.get("hnr_ohne_lage") or r["ortsteil"],
                                                              "hnr_ohne_lage" not in r, p))
            out.append((p["id"], _add_location(r, locations, gaz), "B", r["method"], r["confidence"], r["evidence"], p["id"]))
    print(f"Stufe B: {len({r[0] for r in out})} Vorlagen, {len(out)} Ortsbezüge")
    _hnr_audit(hnr)
    return out


def _hnr_audit(hnr):
    """Wirkung der Regel „strasse+hausnummer“ je Vorlage und Straße (ohne die Hausnummer selbst); dazu einmalig
    eine Stichprobe zur Prüfung von Hand (je Vorgang eine Zeile: alle geänderten, dazu eindeutige bis 30; wird nie
    überschrieben)."""
    def wirkung(before, after, used):
        if not used:
            return "ohne Wirkung: Abschnitt im Ortsteil fehlt im Straßenverzeichnis"
        return "bestätigt" if before == [after] else "eindeutig" if after in before else "geändert"
    rows = sorted((ref, street, "; ".join(before), after, wirkung(before, after, used))
                  for (ref, street), (before, after, used, _) in hnr.items())
    with open(config.EXPORT / "audit_hausnummern.tsv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["drucksache", "strasse", "ortsteile_ohne_hausnummer", "ortsteil_der_hausnummer", "wirkung"])
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r[4]] = counts.get(r[4], 0) + 1
    print(f"Hausnummern: {len(rows)} Nennungen", counts)
    sample_file = config.EXPORT / "hausnummern" / "stichprobe_hausnummern.tsv"
    if sample_file.exists():
        return
    papers = {(ref, street): v[3] for (ref, street), v in hnr.items()}
    def one_per_case(rs):  # Stellungnahmen und Änderungsanträge teilen die sechsstellige Drucksachennummer
        seen, out = set(), []
        for r in rs:
            if r[0][:6] not in seen:
                seen.add(r[0][:6]); out.append(r)
        return out
    changed = one_per_case([r for r in rows if r[4] == "geändert"])
    clear = [r for r in one_per_case([r for r in rows if r[4] == "eindeutig"]) if r[0][:6] not in {c[0][:6] for c in changed}]
    pick = changed + random.Random(20261020).sample(clear, min(len(clear), 30 - len(changed)))
    sample_file.parent.mkdir(parents=True, exist_ok=True)
    with open(sample_file, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["nr", "drucksache", "titel", "link", "strasse", "ortsteile_ohne_hausnummer", "ortsteil_der_hausnummer",
                    "wirkung", "urteil (richtig/falsch/unklar)", "anmerkung"])
        for i, r in enumerate(pick, 1):
            p = papers[(r[0], r[1])]
            w.writerow([i, r[0], p.get("name"), p.get("web") or "", *r[1:], "", ""])
    print(f"Stichprobe Hausnummern: {len(pick)} → {sample_file}")


def _aus_referenz(papers, oparl_rel):
    """Abgeleitete Verknüpfungen aus der Vorlagennummer (pipeline/referenz.py): Vorlage mit Zusatz (z. B. „…/1-A“) →
    Vorlage mit der Grundnummer, nur wo OParl dasselbe Paar nicht schon verknüpft (in einer der beiden Richtungen;
    Wuppertal führt eine Neufassung in OParl als übergeordnet zur Ausgangsvorlage, Rohdaten-Cache 16.11.2026).
    Zeilen: (parent_id, child_id, method, evidence, derived). Wuppertaler Ergänzung (nicht in Bonn und Köln)."""
    paare = {frozenset(r[:2]) for r in oparl_rel}
    out = [(z["parent"], child, referenz.METHODE, z["evidence"], 1)
           for child, z in referenz.zuordnung(papers).items() if frozenset((z["parent"], child)) not in paare]
    print(f"Folgevorlagen aus der Referenz abgeleitet: {len(out)}")
    return out


# Konfidenz einer über die Referenz abgeleiteten Vererbung: eine Stufe unter der Ausgangsvorlage (die Verknüpfung
# selbst ist abgeleitet, nicht aus OParl)
_EINE_STUFE_NIEDRIGER = {"hoch": "mittel", "mittel": "niedrig", "niedrig": "niedrig"}


def _inherited(papers, papers_by_id, own_rows):
    """Vorlagen ohne eigenen Ortsbezug erben die Ortsbezüge der übergeordneten Vorlage (OParl `superordinatedPaper`).
    Zusätzlich (Entscheidung des Auftraggebers 16.11.2026, CLAUDE.md 9): Antworten erben den Ort ihrer Anfrage, auch
    wenn OParl sie nicht verknüpft, über die Vorlagennummer (referenz.zuordnung, Zusatz mit dem Kürzel „A“, vermutlich
    Antwort); Konfidenz eine Stufe niedriger, im Beleg als „aus der Referenz abgeleitet“ gekennzeichnet."""
    own = {}
    for r in own_rows:
        own.setdefault(r[0], []).append(r)
    abgeleitet = referenz.zuordnung(papers)
    out = []
    for p in papers:
        if p["id"] in own:
            continue
        eltern = list(p.get("superordinatedPaper") or [])
        for parent_id in eltern:
            parent = papers_by_id.get(parent_id)
            # abgeleitet, daher Stufe B; die Konfidenz liegt höchstens bei „mittel“
            for _, loc_id, _, _, conf, _, _ in own.get(parent_id, []):
                out.append((p["id"], loc_id, "B", "vererbt", "mittel" if conf == "hoch" else conf,
                            f"übergeordnete Vorlage {parent.get('reference') if parent else parent_id}",
                            parent_id))
        z = abgeleitet.get(p["id"])
        if z and "A" in z["kuerzel"] and z["parent"] not in eltern:
            parent = papers_by_id.get(z["parent"])
            for _, loc_id, _, _, conf, _, _ in own.get(z["parent"], []):
                out.append((p["id"], loc_id, "B", "vererbt", _EINE_STUFE_NIEDRIGER.get(conf, "niedrig"),
                            f"Anfrage {parent.get('reference') if parent else z['parent']} "
                            f"({referenz.hinweis(p.get('reference'))})", z["parent"]))
    print(f"Vererbt: {len({r[0] for r in out})} Vorlagen")
    return out


# Gremiennamen von Bezirksvertretungen (Hunk aus ratsatlas-koeln @d609111): „Bezirksvertretung 4 (Name)“,
# „Bezirksvertretung Name“, „BV Name“. Wuppertaler Abweichung: ohne Zuordnung einer bloßen Nummer zum Stadtbezirk
# (Köln: BEZIRKE_KOELN); Format und Nummern der Wuppertaler Bezirksvertretungen (organizations/gr/<n>) misst Stufe 3
BV_NAME = re.compile(r"^(?:Bezirksvertretung|BV)\s+(?:(\d+)\s*)?(?:\((.+)\)|(.+))?$")


def bv_bezirk(name):
    """Stadtbezirk einer Bezirksvertretung aus dem Gremiennamen: „Bezirksvertretung 3 (Name)“ → „Name“,
    „Bezirksvertretung Name“ → „Name“, „BV Name“ → „Name“; nur eine Nummer ohne Namen → None (TODO Stufe 3)."""
    m = BV_NAME.match((name or "").strip())
    if not m:
        return None
    _nr, klammer, rest = m.groups()
    if klammer or rest:
        return (klammer or rest).strip()
    return None


def _from_committee(papers, bv_bezirke, locations, gaz, placed):
    """Schwache Evidenz `district_from_committee` (CLAUDE.md 5.2): Vorlagen ohne jeden anderen Ortsbezug, die in genau
    einer Bezirksvertretung beraten wurden, erhalten deren Stadtbezirk (Konfidenz niedrig). Die zweite Regel aus 5.2
    (`paperType` endet auf „BV“) folgt mit der Zerlegung von `paperType` nach den Messstufen (TODO Phase 2)."""
    out = []
    for p in papers:
        bz = bv_bezirke.get(p["id"]) or set()
        if p["id"] in placed or len(bz) != 1:
            continue
        name = next(iter(bz))
        if name not in gaz.bezirk_point:
            continue
        pt = gaz.bezirk_point[name]
        r = dict(level="stadtbezirk", name=name, ortsteil=None, bezirk=name, lon=round(pt.x, 6), lat=round(pt.y, 6))
        out.append((p["id"], _add_location(r, locations, gaz), "B", "district_from_committee", "niedrig",
                    f"nur in der Bezirksvertretung {name} beraten", p["id"]))
    print(f"Stadtbezirk aus der beratenden Bezirksvertretung: {len(out)} Vorlagen")
    return out
