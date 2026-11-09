"""Prüfung: Kennzahlen, Verknüpfungsquote, Datenschutz.

Wuppertal: Die Bonner Vergleichswerte (Phase-0-Bericht Bonn) und die Zeilen zum Bonner Pilot-Ortsteil sind entfernt;
Wuppertaler Vergleichswerte folgen nach den Messstufen (TODO, nicht schätzen). Quellenkennung und Exportpfad aus config,
Zusatzthemen (Besetzung, Prozessarten, Kontextdaten) nur, wenn in config.ZUSATZTHEMEN freigegeben. Die vollständige Kölner Neufassung
(ratsatlas-koeln @d609111, Gebietszahlen, Hauskoordinaten) folgt mit Phase 3."""
import json
import re
import sqlite3

from . import actors, besetzung, config, kontext, maske


def check():
    db = sqlite3.connect(config.DB)
    one = lambda sql, *a: db.execute(sql, a).fetchone()[0]
    pct = lambda n, d: f"{n} von {d} ({100 * n / d:.1f} %)" if d else "–"

    found = {
        "Vorlagen": one("SELECT COUNT(*) FROM paper"),
        "Vorlagen mit Koordinate": one(
            "SELECT COUNT(DISTINCT pl.paper_id) FROM paper_location pl "
            "JOIN location l ON l.id = pl.location_id WHERE l.lon IS NOT NULL"),
        "Vorlagen mit Koordinate in einem Quartier": one(
            "SELECT COUNT(DISTINCT pl.paper_id) FROM paper_location pl "
            "JOIN location l ON l.id = pl.location_id WHERE l.ortsteil IS NOT NULL"),
        "Quartiere mit mind. einer Vorlage": one(
            "SELECT COUNT(DISTINCT ortsteil) FROM location WHERE ortsteil IS NOT NULL"),
    }
    print("Kennzahl\tjetzt")   # Vergleichswerte erst nach den Messstufen (TODO)
    for k, v in found.items():
        print(f"{k}\t{v}")

    cons = one("SELECT COUNT(*) FROM consultation")
    print("\nVerknüpfung Beratung ↔ Sitzung")
    print("mit Sitzung:", pct(one("SELECT COUNT(*) FROM consultation WHERE meeting_id IS NOT NULL"), cons))
    print("mit TOP-Ergebnis:", pct(one(
        "SELECT COUNT(*) FROM consultation c JOIN agenda_item a ON a.id = c.agenda_item_id "
        "WHERE a.result IS NOT NULL AND a.result <> ''"), cons))

    politik = tuple(actors.POLITIK_TYPES)
    marks = ",".join("?" * len(politik))
    n_pol = one(f"SELECT COUNT(*) FROM paper WHERE paper_type IN ({marks})", *politik)
    n_pol_orig = one(
        f"SELECT COUNT(DISTINCT p.id) FROM paper p JOIN paper_originator o ON o.paper_id = p.id "
        f"WHERE p.paper_type IN ({marks})", *politik)
    print("\nEinreichende")
    print("Anträge/Anfragen mit abgeleiteten Einreichenden:", pct(n_pol_orig, n_pol))
    print("Vorlagen mit Einreichenden insgesamt:",
          pct(one("SELECT COUNT(DISTINCT paper_id) FROM paper_originator"), found["Vorlagen"]))
    print("davon einer Ratsfraktion/-gruppe zugeordnet:",
          one("SELECT COUNT(*) FROM paper_originator WHERE actor_type IN ('Fraktion/Gruppe', 'Bezirksfraktion') "
              "AND organization_id IS NOT NULL"), "von",
          one("SELECT COUNT(*) FROM paper_originator WHERE actor_type IN ('Fraktion/Gruppe', 'Bezirksfraktion')"),
          "Nennungen")

    n_co = one("SELECT COUNT(*) FROM paper p JOIN organization o ON o.id = p.under_direction_of "
               "WHERE o.classification = ?", actors.CO_DEZERNAT)
    # wie ratsatlas-koeln @d609111: Bonner Einstufung, „nicht anwendbar“ ohne solche Vorlagen (TODO Messstufe 4)
    print("\nCo-Dezernat (Einstufung der Bonner Verwaltungsbereiche)")
    if n_co:
        print("fachliche Zuständigkeit über Stellungnahme abgeleitet:", pct(one(
            "SELECT COUNT(DISTINCT paper_id) FROM paper_responsibility WHERE kind = 'fachlich'"), n_co))
    else:
        print("nicht anwendbar: keine Vorlage mit federführendem „Co-Dezernat“ (ob die Wuppertaler API diese "
              "Einstufung kennt, ist ungemessen)")

    print("\nGeokodierung")
    for stage in ("A", "B"):
        print(f"Vorlagen mit Ortsbezug Stufe {stage}:", pct(one(
            "SELECT COUNT(DISTINCT paper_id) FROM paper_location WHERE stage = ? AND method <> 'vererbt'",
            stage), found["Vorlagen"]))
    print("Vorlagen mit vererbtem Ortsbezug:",
          one("SELECT COUNT(DISTINCT paper_id) FROM paper_location WHERE method = 'vererbt'"))
    print("Vorlagen mit Ortsbezug insgesamt:",
          pct(one("SELECT COUNT(DISTINCT paper_id) FROM paper_location"), found["Vorlagen"]))
    # Stufe B gegen Stufe A, für Vorlagen mit beidem. Straßentreffer aus OParl-Locations sind nicht
    # unabhängig von Stufe A (gleiche Punkte) und werden getrennt ausgewiesen.
    n_a = one("SELECT COUNT(DISTINCT paper_id) FROM paper_location WHERE stage = 'A' AND method <> 'vererbt'")
    pairs = db.execute(
        "SELECT b.paper_id, lb.level || ' (' || lb.source || ')', (SELECT COUNT(*) FROM paper_location a "
        "JOIN location la ON la.id = a.location_id WHERE a.paper_id = b.paper_id AND a.stage = 'A' "
        "AND la.ortsteil = lb.ortsteil) FROM paper_location b JOIN location lb ON lb.id = b.location_id "
        "WHERE b.stage = 'B' AND b.method <> 'vererbt' AND lb.level <> 'stadtbezirk' AND b.paper_id IN "
        "(SELECT paper_id FROM paper_location WHERE stage = 'A' AND method <> 'vererbt')").fetchall()
    print("Vorlagen mit Stufe A, für die Stufe B einen Ortsteil findet:",
          pct(len({p for p, *_ in pairs}), n_a))
    # je Vorlage: trifft mindestens ein Ortsbezug dieser Art den Ortsteil aus Stufe A?
    for kind in sorted({k for _, k, _ in pairs}):
        hits = {}
        for pid, k, ok in pairs:
            if k == kind:
                hits[pid] = hits.get(pid, False) or bool(ok)
        note = " – nicht unabhängig von Stufe A" if config.QUELLE_OPARL in kind else ""
        print(f"  Vorlagen mit Ortsteil wie Stufe A, Ebene {kind}:",
              pct(sum(hits.values()), len(hits)) + note)

    # Straße und Beschreibung der Orte aus der OParl-API; Postleitzahlen sind keine Hausnummern. Bonn strich nur
    # Bonner PLZ (5xxxx); hier jede fünfstellige Zahl. TODO: Wuppertal liefert laut Stichprobe kein `location`
    # (CLAUDE.md 3.1) – Regel nach den Messstufen prüfen
    texts = [r[0] for r in db.execute(
        "SELECT street FROM location WHERE street IS NOT NULL AND source = ? UNION ALL "
        "SELECT description FROM location WHERE description IS NOT NULL AND source = ?",
        (config.QUELLE_OPARL, config.QUELLE_OPARL))]
    with_number = [s for s in texts if re.search(r"\d", re.sub(r"\b[0-9]{5}\b", "", s))]
    with_nr = one("SELECT COUNT(DISTINCT paper_id) FROM paper_plan")
    with_area = one("SELECT COUNT(DISTINCT paper_id) FROM paper_location WHERE method = 'bebauungsplan'")
    print("\nBebauungspläne")
    print("Vorlagen mit Plannummer im Titel:", with_nr, "· davon mit Geltungsbereich:", pct(with_area, with_nr))

    print("\nDatenschutz")
    print("Orte mit Hausnummer in Straße oder Beschreibung:", len(with_number), with_number[:5])
    offen = titel_mit_hausnummer(maske.aus_db(db))
    print("Titel aus Einwohnerschaft, Bauordnung und Naturschutz mit Hausnummer in Suche und GeoJSON:", len(offen), offen[:5])
    db.close()
    if with_number:
        raise SystemExit("Prüfung fehlgeschlagen: Hausnummern in Ortsangaben (CLAUDE.md 5.2).")
    if offen:
        raise SystemExit("Prüfung fehlgeschlagen: Hausnummern in Titeln aus Einwohnerschaft, Bauordnung oder Naturschutz (maske.py).")

    zusatzthemen()


def zusatzthemen():
    """Prüfungen der Bonner Zusatzthemen nur, wenn freigegeben (config.ZUSATZTHEMEN); abgeschaltete werden ausgewiesen.
    Nach ratsatlas-koeln @d609111 (check.zusatzthemen), ohne die Kölner Sammlung fehlender Prüfungen: ein Befund bricht
    wie bisher ab. Die Datenschutzprüfung oben gehört zum Kern und läuft ohne Schalter."""
    an = config.ZUSATZTHEMEN.get
    befunde = []

    print("\nBesetzung der Gremien (Zusatzthema „besetzung“)")
    if not an("besetzung"):
        print("abgeschaltet (config.ZUSATZTHEMEN) – nicht geprüft")
    elif config.BESETZUNG.exists():
        doc = json.loads(config.BESETZUNG.read_text())
        b = besetzung.pruefen_auszug(doc)
        print(f"{len(doc['mitgliedschaften'])} laufende Mitgliedschaften, {len(doc['personen'])} Personen namentlich; "
              f"Befunde: {b or 'keine'}")
        befunde += [f"Besetzung: {x}" for x in b]

    print("\nProzessarten (Zusatzthema „soll“)")
    pz = config.EXPORT / config.STADT / "prozessarten.json"
    if not an("soll"):
        print("abgeschaltet (config.ZUSATZTHEMEN) – nicht geprüft")
    elif pz.exists():
        b = besetzung.pruefen_auszug({"mitgliedschaften": [], "rest": json.loads(pz.read_text())})
        print(f"prozessarten.json: Befunde: {b or 'keine'}")
        befunde += [f"prozessarten.json: {x}" for x in b]

    print("\nKontextdaten je Quartier (Zusatzthema „kontext“)")
    if not an("kontext"):
        print("abgeschaltet (config.ZUSATZTHEMEN) – nicht geprüft")
    else:
        befunde += [f"Kontextdaten: {x}" for x in kontext.pruefen()]

    if befunde:
        raise SystemExit(f"Prüfung fehlgeschlagen: Zusatzthemen ({'; '.join(befunde)}).")
    return befunde


def titel_mit_hausnummer(m, base=None):
    """Drucksachen aus der Einwohnerschaft, deren Titel in suche.json oder vorlagen.geojson noch eine Hausnummer
    trägt (Entscheidung des Auftraggebers 24.10.2026: überall ausblenden)."""
    base = base or config.EXPORT / config.STADT
    offen = set()
    if (f := base / "suche.json").exists():
        offen |= {r[0] for r in json.loads(f.read_text())["rows"] if m.offen(r[1], r[0])}
    if (f := base / "vorlagen.geojson").exists():
        offen |= {x["properties"]["reference"] for x in json.loads(f.read_text())["features"]
                  if m.offen(x["properties"].get("name"), x["properties"]["reference"])}
    return sorted(offen)
