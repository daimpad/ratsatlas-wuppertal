"""Ämterliste aus den Organisationen mit Präfix `at` (Phase 1, CLAUDE.md 5.3 und 9 vom 13.11.2026) – ohne Netz.

Neu in Wuppertal (in ratsatlas-koeln @d609111 ohne Gegenstück). Liest nur ergebnisse/oparl_organisationen.tsv (Stufe 4,
Kommando `organisationen`, Lauf 4 vom 12.11.2026) und ruft nichts ab. In der Quelle sind `organizationType` und
`classification` bei allen 95 Organisationen mit Präfix `at` leer (unter `gr` trägt nur gr/244 eine `classification`;
STUFEN.md, Ergebnis Stufe 4); die Klasse wird deshalb allein aus dem Namen abgeleitet.

Regel: Die Muster in REGELN werden der Reihe nach geprüft, die erste passende bestimmt Klasse und Regelnummer. Zuerst
stehen die Grenzfälle (Klasse `offen` mit Frage an den Auftraggeber), dann politische Gruppen, Beteiligungen mit
Rechtsform im Namen und zuletzt die Merkmale der Verwaltung. Trifft kein Muster, ist die Klasse `offen` (Regel R0).
Klassen:
- `amt`: Dienststelle der Stadtverwaltung (Amt, Ressort, Stadtbetrieb, Geschäftsbereich, Büro)
- `beteiligung`: Unternehmen mit Rechtsform im Namen (GmbH, AG …)
- `politisch`: Ratsgruppe, Fraktion, Wählergruppe
- `offen`: Grenzfall oder ohne Merkmal; Frage und Vorschlag in den Spalten `frage` und `vorschlag`
Nummer: Dienststellennummer im Namen (Form NNN oder NNN.N, z. B. „402“, „403.5“, „001.11“; vorne, nach „Ressort“,
„Stadtbetrieb“, „Amt“ oder „Geschäftsbereichsbüro“), sonst Nummer des Geschäftsbereichs (Form N oder N.N nach
„Geschäftsbereich“ oder „GB“). Mehrere Organisationen mit derselben Nummer sind nicht als Fassungen oder
Nachfolger belegt: Unter einer Nummer stehen auch gleichzeitig bestehende, verschieden benannte Stellen (403:
„Finanzen“ und „Beteiligungsmanagement“, beide startDate 1999-10-01, ohne endDate, daneben „Kämmerei“), und im
Rohdaten-Cache werden mehrere Kennungen derselben Nummer in denselben Jahren verwendet (Gegenprobe mit --cache).
Die Spalte `startfolge` beschreibt deshalb nur die Lage des startDate in der Gruppe gleicher Nummer, keine Nachfolge
und keine Gültigkeit: `mit endDate` (endDate in der Quelle gesetzt), `früherer Beginn` (ohne endDate, eine andere
hat ein späteres startDate), `spätester Beginn` (spätestes startDate der Gruppe, ohne endDate), `einzige` (keine
andere mit derselben Nummer). Keine Organisation wird über startDate oder endDate automatisch gewählt; angezeigt
wird immer der Name der Kennung, auf die eine Vorlage verweist.
Hinweise in `bemerkung` (kein Beleg): eine andere Organisation beginnt am Tag des endDate oder am Tag danach
(„zeitlich anschließend“, mögliche Nachfolge ohne gleiche Nummer); bei Klassen außer `amt` ein endDate bis 90 Tage
nach einer Kommunalwahl (13.09.2020, 14.09.2025; CLAUDE.md 2), was auf eine Gruppe im Rat deuten kann.

Ergebnis (versioniert): ergebnisse/aemter.tsv, je Organisation mit Präfix `at` eine Zeile (Kennung unverändert, Name
wie in der Quelle). Auf stdout die Zahlen je Klasse und je Regel; mit --cache zusätzlich zwei Gegenproben, die nur
gelesen und nicht gespeichert werden: (1) welche Klassen die `underDirectionOf`-Verweise der Vorlagenseiten im
Rohdaten-Cache treffen, (2) welche Dienststellennummern der Abgleich für Stufe 6 (oparl_messung.amt_abgleichen) nicht
eindeutig einer Organisation zuordnet.
Aufruf: python3 explore/aemter.py [--organisationen DATEI] [--ergebnisse VERZ] [--cache VERZ]
Der Abgleich für Stufe 6 importiert oparl_messung.py und damit abruf.py, ruft aber keine Abruffunktion auf.
Rückgabewerte: 0 fertig, 1 Eingabe fehlt oder ohne Organisation mit Präfix at.
"""
import argparse
import collections
import csv
import datetime
import glob
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ERG = HIER / "ergebnisse"
QUELLE = ERG / "oparl_organisationen.tsv"
ZIEL = "aemter.tsv"
KLASSEN = ("amt", "beteiligung", "politisch", "offen")
SPALTEN = ["id", "name", "klasse", "regel", "merkmal", "nummer", "nummernart", "startDate", "endDate", "startfolge",
           "gleiche_nummer", "frage", "vorschlag", "bemerkung"]
KOMMUNALWAHLEN = (datetime.date(2020, 9, 13), datetime.date(2025, 9, 14))   # CLAUDE.md 2
TAGE_NACH_WAHL = 90   # Festlegung dieses Werkzeugs, keine Angabe der Stadt

# (Nummer, Klasse, Muster, Merkmal, Frage, Vorschlag) – Reihenfolge ist Teil der Regel
REGELN = [
    ("G1", "offen", r"^Eigenbetrieb\b", "„Eigenbetrieb“ am Anfang",
     "Eigenbetriebe als Teil der Verwaltung (amt) oder getrennt von den Ämtern führen?",
     ("amt mit Zusatz „Eigenbetrieb“: ohne eigene Rechtsform im Namen; in Vorlagen als federführend eingetragen "
      "(Gegenprobe Cache, STUFEN.md Stufe 4)")),
    ("G2", "offen", r"^[A-ZÄÖÜ]{2,5}$", "nur ein Kürzel aus Großbuchstaben",
     "Wofür steht das Kürzel (Wählergruppe, Gesellschaft oder Dienststelle)?",
     "offen lassen, bis die Bedeutung belegt ist; Name wie in der Quelle anzeigen"),
    ("G3", "offen", r"(?i)personalrat", "„Personalrat“ im Namen",
     "Personalvertretung der Beschäftigten: eigene Klasse „sonstig“ statt amt?",
     "sonstig: Vertretung der Beschäftigten, keine Dienststelle mit Nummer"),
    ("G4", "offen", r"^Gleichstellungsstelle\b", "„Gleichstellungsstelle“ ohne Dienststellennummer",
     "Gleichstellungsstelle als Dienststelle der Verwaltung (amt) führen?",
     "amt: Stelle der Stadtverwaltung; in Vorlagen als federführend eingetragen (Gegenprobe Cache)"),
    ("G5", "offen", r"^Regionalbüro$", "„Regionalbüro“ ohne Zusatz",
     "Ist das Regionalbüro eine Dienststelle der Stadt oder eine Einrichtung mit anderen Trägern?",
     "offen lassen, bis der Träger belegt ist"),
    ("G6", "offen", r"^Jobcenter\b", "„Jobcenter“ am Anfang",
     "Jobcenter als Dienststelle der Stadt oder als eigene Einrichtung (Beteiligung) führen?",
     "beteiligung erst nach Bestätigung der Rechtsform; bis dahin offen"),
    ("G7", "offen", r"^DIE GRAUEN\b", "Parteiname ohne „Ratsgruppe“ oder „Fraktion“",
     "Gruppe im Rat (politisch)?",
     "politisch, wenn die Stadt oder das Ratsbüro die Gruppe bestätigt"),
    ("P1", "politisch", r"\b(?:Ratsgruppe|Fraktion|Wählergruppe|Wählergemeinschaft)\b",
     "„Ratsgruppe“, „Fraktion“ oder „Wählergruppe“ im Namen", "", ""),
    ("B1", "beteiligung", r"\b(?:gGmbH|GmbH|mbH|AG|KG)(?=$|[\s,)])", "Rechtsform im Namen (GmbH, mbH, AG, KG)",
     "", ""),
    ("A1", "amt", r"^\d{3}(?:\.\d{1,2})?(?=\s)", "Dienststellennummer am Anfang (NNN oder NNN.N)", "", ""),
    ("A2", "amt", r"\b(?:Ressort|Stadtbetrieb|Amt) \d{3}\b", "„Ressort“, „Stadtbetrieb“ oder „Amt“ mit Nummer NNN",
     "", ""),
    ("A3", "amt", r"^(?:Geschäftsbereich \d(?:\.\d)?\b|GB ?\d\b)", "„Geschäftsbereich“ oder „GB“ mit Nummer", "", ""),
    ("A4", "amt", r"büro\b", "Wort endet auf „büro“ (Geschäftsbereichsbüro, Projektbüro)", "", ""),
    ("A5", "amt", r"\w+amt\b", "Wort endet auf „amt“ (z. B. Ordnungsamt)", "", ""),
]
OHNE_REGEL = ("R0", "offen", "kein Merkmal im Namen", "Welcher Klasse gehört die Organisation an?")
# Vorschläge für Organisationen ohne Merkmal (R0): ausdrücklich unbelegt, nur als Vorschlag an den Auftraggeber
_VORSCHLAG_EINRICHTUNG = ("beteiligung (unbelegt): Einrichtung mit eigenem Namen ohne Dienststellennummer; "
                          "Rechtsform nicht im Namen, Bestätigung nötig")
VORSCHLAG_OHNE_REGEL = {"Klinikum Wuppertal": _VORSCHLAG_EINRICHTUNG, "Stadthalle Wuppertal": _VORSCHLAG_EINRICHTUNG}
_REGELN = [(nr, kl, re.compile(m), merk, fr, vo) for nr, kl, m, merk, fr, vo in REGELN]
NUMMER_DIENSTSTELLE = [re.compile(r"^(\d{3}(?:\.\d{1,2})?)(?=\s)"),
                       re.compile(r"\b(?:Ressort|Stadtbetrieb|Amt) (\d{3})\b"),
                       re.compile(r"\bGeschäftsbereichsbüro (\d{3}(?:\.\d)?)\b")]
NUMMER_GESCHAEFTSBEREICH = [re.compile(r"^Geschäftsbereich (\d(?:\.\d)?)\b"), re.compile(r"^GB ?(\d)\b")]


def lies_tsv(pfad):
    with open(pfad, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def leer(wert):
    """Werte „None“ und leere Zellen aus oparl_organisationen.tsv als leere Zeichenkette."""
    wert = (wert or "").strip()
    return "" if wert == "None" else wert


def norm(name):
    return " ".join((name or "").split())


def klasse(name):
    """(Regelnummer, Klasse, Merkmal, Frage, Vorschlag) für einen Namen; erste passende Regel aus REGELN."""
    n = norm(name)
    for nr, kl, rx, merk, frage, vorschlag in _REGELN:
        if rx.search(n):
            return nr, kl, merk, frage, vorschlag
    nr, kl, merk, frage = OHNE_REGEL
    return nr, kl, merk, frage, VORSCHLAG_OHNE_REGEL.get(n, "")


def nummer(name):
    """(Nummer, Art) aus dem Namen: Dienststellennummer vor Geschäftsbereichsnummer; sonst ("", "")."""
    n = norm(name)
    for rx in NUMMER_DIENSTSTELLE:
        m = rx.search(n)
        if m:
            return m.group(1), "dienststelle"
    for rx in NUMMER_GESCHAEFTSBEREICH:
        m = rx.search(n)
        if m:
            return m.group(1), "geschaeftsbereich"
    return "", ""


def _id_zahl(kennung):
    m = re.search(r"/(\d+)$", kennung or "")
    return int(m.group(1)) if m else -1


def kurz(kennung):
    return "at/" + str(_id_zahl(kennung))


def _wahlhinweis(ende):
    try:
        tag = datetime.date.fromisoformat(ende)
    except ValueError:
        return ""
    for wahl in KOMMUNALWAHLEN:
        if 0 <= (tag - wahl).days <= TAGE_NACH_WAHL:
            return (f"endDate {(tag - wahl).days} Tage nach der Kommunalwahl am {wahl:%d.%m.%Y} (CLAUDE.md 2); "
                    "Hinweis, kein Beleg")
    return ""


def _tag_und_folgetag(ende):
    try:
        tag = datetime.date.fromisoformat(ende)
    except ValueError:
        return ()
    return (tag.isoformat(), (tag + datetime.timedelta(days=1)).isoformat())


def tabelle(organisationen):
    """Zeilen für aemter.tsv aus den Zeilen von oparl_organisationen.tsv (nur Präfix at), nach Kennung aufsteigend."""
    zeilen = []
    for o in organisationen:
        if o.get("praefix") != "at":
            continue
        nr, kl, merk, frage, vorschlag = klasse(o.get("name"))
        num, art = nummer(o.get("name"))
        zeilen.append({"id": o["id"], "name": o.get("name") or "", "klasse": kl, "regel": nr, "merkmal": merk,
                       "nummer": num, "nummernart": art, "startDate": leer(o.get("startDate")),
                       "endDate": leer(o.get("endDate")), "startfolge": "einzige", "gleiche_nummer": "",
                       "frage": frage, "vorschlag": vorschlag, "bemerkung": ""})
    zeilen.sort(key=lambda z: _id_zahl(z["id"]))
    gruppen = collections.defaultdict(list)
    for z in zeilen:
        if z["nummer"]:
            gruppen[(z["nummernart"], z["nummer"])].append(z)
    for gruppe in gruppen.values():
        if len(gruppe) < 2:
            continue
        spaetester = max(z["startDate"] for z in gruppe)
        for z in gruppe:
            z["gleiche_nummer"] = ", ".join(kurz(a["id"]) for a in gruppe if a is not z)
            if z["endDate"]:
                z["startfolge"] = "mit endDate"
            elif z["startDate"] < spaetester:
                z["startfolge"] = "früherer Beginn"
            else:
                z["startfolge"] = "spätester Beginn"
    namen = collections.defaultdict(list)
    for z in zeilen:
        namen[norm(z["name"])].append(z)
    for z in zeilen:
        teile = []
        if z["klasse"] == "amt" and not z["nummer"]:
            teile.append("ohne Nummer im Namen")
        andere = [kurz(a["id"]) for a in namen[norm(z["name"])] if a is not z]
        if andere:
            teile.append("gleicher Name wie " + ", ".join(andere))
        gleiche_start = [kurz(a["id"]) for a in gruppen.get((z["nummernart"], z["nummer"]), [])
                         if a is not z and z["startfolge"] == a["startfolge"] != "mit endDate"
                         and z["startDate"] == a["startDate"]]
        if gleiche_start:
            teile.append("gleiches startDate wie " + ", ".join(gleiche_start))
        if z["endDate"]:
            anschluss = [f"{kurz(a['id'])} ({a['startDate']})" for a in zeilen
                         if a is not z and a["startDate"] in _tag_und_folgetag(z["endDate"])]
            if anschluss:
                teile.append("zeitlich anschließend beginnt " + ", ".join(anschluss) + "; Hinweis, kein Beleg")
            hinweis = _wahlhinweis(z["endDate"]) if z["klasse"] != "amt" else ""
            if hinweis:
                teile.append(hinweis)
        z["bemerkung"] = "; ".join(teile)
    return zeilen


def zaehlung(zeilen):
    """(je Klasse, je Regel) als Counter."""
    return (collections.Counter(z["klasse"] for z in zeilen), collections.Counter(z["regel"] for z in zeilen))


def schreibe(zeilen, pfad):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SPALTEN, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(zeilen)


def gegenprobe_verweise(cache, zeilen):
    """Liest Vorlagenseiten (JSON, Objekte vom Typ Paper) im Rohdaten-Cache und zählt die Ziele von `underDirectionOf`
    je Klasse. Rückgabe als dict: vorlagen, mit_verweis, je_klasse (Counter), je_id (Counter), ab_2020_created und
    ab_2020_date (Verweise aus Vorlagen mit `created` bzw. `date` ab 2020; der Zeitumfang in CLAUDE.md 2 richtet sich
    nach `date`), jahre_created und jahre_date (Vorlagen je Jahr), zeitraum (je Kennung kleinstes und größtes `date`
    der verweisenden Vorlagen). Nichts wird gespeichert, Titel und Namen werden nicht ausgewertet."""
    nach_id = {z["id"]: z for z in zeilen}
    gesehen, mit, ab_2020_created, ab_2020_date = set(), 0, 0, 0
    je_klasse, je_id = collections.Counter(), collections.Counter()
    jahre_created, jahre_date, zeitraum = collections.Counter(), collections.Counter(), {}
    for datei in sorted(glob.glob(str(Path(cache) / "*.json"))):
        try:
            with open(datei, encoding="utf-8") as f:
                daten = json.load(f)
        except (OSError, ValueError):
            continue
        for p in daten.get("data", []) if isinstance(daten, dict) else []:
            if not isinstance(p, dict) or not str(p.get("type", "")).endswith("/Paper") or p.get("id") in gesehen:
                continue
            gesehen.add(p.get("id"))
            ziele = p.get("underDirectionOf") or []
            erstellt, datum = str(p.get("created") or "")[:10], str(p.get("date") or "")[:10]
            jahre_created[erstellt[:4] or "ohne"] += 1
            jahre_date[datum[:4] or "ohne"] += 1
            mit += bool(ziele)
            ab_2020_created += len(ziele) if erstellt[:4] >= "2020" else 0
            ab_2020_date += len(ziele) if datum[:4] >= "2020" else 0
            for ziel in ziele:
                je_klasse[nach_id[ziel]["klasse"] if ziel in nach_id else "nicht in der Ämterliste"] += 1
                je_id[ziel] += 1
                if datum:
                    von, bis = zeitraum.get(ziel, (datum, datum))
                    zeitraum[ziel] = (min(von, datum), max(bis, datum))
    return {"vorlagen": len(gesehen), "mit_verweis": mit, "je_klasse": je_klasse, "je_id": je_id,
            "ab_2020_created": ab_2020_created, "ab_2020_date": ab_2020_date, "jahre_created": jahre_created,
            "jahre_date": jahre_date, "zeitraum": zeitraum}


def gleichzeitig_verwendet(zeilen, zeitraum):
    """Je Nummer mit mehreren Organisationen die Kennungen, deren Zeiträume (`date` der verweisenden Vorlagen im
    Cache) sich mit dem einer anderen Kennung derselben Nummer überschneiden. Rückgabe {(Art, Nummer): [Kennung …]}.
    Beleg dafür, dass gleiche Nummer keine Nachfolge bedeutet; nur so aussagekräftig wie der Cache."""
    gruppen = collections.defaultdict(list)
    for z in zeilen:
        if z["nummer"] and z["id"] in zeitraum:
            gruppen[(z["nummernart"], z["nummer"])].append(z["id"])
    ergebnis = {}
    for schluessel, ids in sorted(gruppen.items()):
        ueber = sorted({a for a in ids for b in ids if a != b and zeitraum[a][0] <= zeitraum[b][1]
                        and zeitraum[b][0] <= zeitraum[a][1]}, key=_id_zahl)
        if ueber:
            ergebnis[schluessel] = ueber
    return ergebnis


def nach_end_date(zeilen, zeitraum):
    """Kennungen mit endDate, auf die eine Vorlage mit späterem `date` verweist: {Kennung: (endDate, spätestes date)}.
    Beleg dafür, dass endDate kein sicheres Ende der Verwendung ist; nur so aussagekräftig wie der Cache."""
    return {z["id"]: (z["endDate"], zeitraum[z["id"]][1]) for z in zeilen
            if z["endDate"] and z["id"] in zeitraum and zeitraum[z["id"]][1] > z["endDate"]}


def gegenprobe_abgleich(zeilen, organisationen_datei):
    """Dienststellennummern der Klasse amt, die oparl_messung.amt_abgleichen (Stufe 6) nicht eindeutig zuordnet."""
    sys.path.insert(0, str(HIER))
    import oparl_messung   # noqa: E402  (lädt abruf.py mit; genutzt werden nur aemterliste und amt_abgleichen)
    aemter = oparl_messung.aemterliste(organisationen_datei)
    ergebnis = {}
    for num in sorted({z["nummer"] for z in zeilen if z["nummernart"] == "dienststelle" and z["klasse"] == "amt"}):
        treffer = oparl_messung.amt_abgleichen(num, aemter)
        if not treffer.startswith("http"):
            ergebnis[num] = treffer
    return ergebnis


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ämterliste aus den Organisationen mit Präfix at (ohne Netz)")
    ap.add_argument("--organisationen", default=str(QUELLE))
    ap.add_argument("--ergebnisse", default=str(ERG))
    ap.add_argument("--cache", default=None, help="Verzeichnis mit Rohdaten (*.json) für die Gegenprobe; nur lesen")
    a = ap.parse_args(argv)
    quelle = Path(a.organisationen)
    if not quelle.exists():
        print(f"Eingabe fehlt: {quelle} (zuerst Stufe 4, organisationen)", file=sys.stderr)
        return 1
    zeilen = tabelle(lies_tsv(quelle))
    if not zeilen:
        print("Keine Organisation mit Präfix at in der Eingabe", file=sys.stderr)
        return 1
    schreibe(zeilen, Path(a.ergebnisse) / ZIEL)
    je_klasse, je_regel = zaehlung(zeilen)
    print(f"{len(zeilen)} Organisationen mit Präfix at → {Path(a.ergebnisse) / ZIEL}")
    print("Klassen: " + ", ".join(f"{k} {je_klasse.get(k, 0)}" for k in KLASSEN))
    print("Regeln: " + ", ".join(f"{r} {je_regel[r]}" for r in sorted(je_regel)))
    print("Startfolge bei gleicher Nummer: " + ", ".join(f"{k} {v}" for k, v in sorted(collections.Counter(
        z["startfolge"] for z in zeilen).items())))
    nicht_eindeutig = gegenprobe_abgleich(zeilen, quelle)
    print(f"Abgleich Stufe 6 nicht eindeutig: {len(nicht_eindeutig)} Nummern"
          + "".join(f"\n  {n}: {t}" for n, t in nicht_eindeutig.items()))
    if a.cache:
        if not Path(a.cache).is_dir():
            print(f"Gegenprobe: Cache fehlt ({a.cache})")
        else:
            g = gegenprobe_verweise(a.cache, zeilen)
            je_kl, je_id = g["je_klasse"], g["je_id"]
            print(f"Gegenprobe Cache: {g['vorlagen']} Vorlagen, {g['mit_verweis']} mit underDirectionOf, "
                  f"{sum(je_kl.values())} Verweise auf {len(je_id)} Organisationen (aus Vorlagen ab 2020: "
                  f"{g['ab_2020_date']} nach date, {g['ab_2020_created']} nach created); je Klasse: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(je_kl.items())))
            for feld in ("created", "date"):
                print(f"  Vorlagen je Jahr nach {feld}: "
                      + ", ".join(f"{j} {n}" for j, n in sorted(g["jahre_" + feld].items())))
            nach_id = {z["id"]: z for z in zeilen}
            for kennung, anzahl in sorted(je_id.items(), key=lambda x: (-x[1], _id_zahl(x[0]))):
                z = nach_id.get(kennung)
                if z and z["klasse"] != "amt":
                    print(f"  {kurz(kennung)} {z['klasse']} ({z['regel']}): {anzahl}")
            zr = g["zeitraum"]
            for (art, num), ids in gleichzeitig_verwendet(zeilen, zr).items():
                print(f"  gleiche Nummer {num} ({art}), Zeiträume überschneiden sich: "
                      + ", ".join(f"{kurz(i)} ({je_id[i]} Vorlagen, date {zr[i][0]} bis {zr[i][1]})" for i in ids))
            for kennung, (ende, spaet) in sorted(nach_end_date(zeilen, zr).items(), key=lambda x: _id_zahl(x[0])):
                print(f"  {kurz(kennung)} endDate {ende}, verwiesen noch von Vorlagen mit date bis {spaet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
