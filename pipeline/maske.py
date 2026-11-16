"""Hausnummern in Titeln von Vorlagen aus der Einwohnerschaft ausblenden (Datenschutz, CLAUDE.md 5.2).

Gilt für Bürgeranträge, Anregungen und Beschwerden, Einwohnerfragen und Bürgerbriefe sowie alle Vorlagen, die mit
ihnen über- oder untergeordnet verbunden sind (einwohner). Dieselbe Regel wie `masker()` in
site/chat/tools.js: eine Hausnummer hinter einem bekannten Straßennamen oder einer Straßen-Endung wird durch
OHNE_NR ersetzt. Entscheidung des Auftraggebers 24.10.2026: auf Seite, in Feeds, Suche und offenen Daten wie im
Assistenten; das Original bleibt über den Link ins Ratsinformationssystem erreichbar.
Verortung und Audit der Geokodierung arbeiten weiter mit dem vollen Titel aus der Datenbank (die Hausnummer
bestimmt den Ortsteil, angezeigt wird nur die Straße).
Erweitert am 26.10.2026 (Entscheidung des Auftraggebers): auch Vorlagen, die das Bauordnungsamt (63) oder eine Untere
Naturschutzbehörde (56-3, 67-6) federführend betreut (Bauanträge und Fällgenehmigungen auf Grundstücken), und ihre
verbundenen Vorlagen.
Ergänzt am 01.11.2026 (Lücke aus der Phase 0 „Verständlichkeit“: 27 Titel aus 15 Vorgängen): auch eine Nummer hinter
„Hausnummer(n)“, „Hausnr.“, „Haus-Nr.“ oder „Haus Nr.“ (ersetzt samt dem Wort) und hinter „Straße Nr.“.

Kernmodul (CLAUDE.md 2 Datenschutz, § 24 GO NRW): Die Regel für Vorlagen aus der Einwohnerschaft (EINWOHNER,
EINWOHNER_TITEL, einwohner) stand in Bonn und Köln in chat.py (Ratsassistent). Sie gilt auch bei abgeschaltetem Chat
(config.ZUSATZTHEMEN["chat"]) für Vorgangsseiten (export, publish.has_page), Hausnummern in Titeln (hier) und die
Verortung aus dem Volltext (volltext.einwohner_kette) und steht deshalb hier; chat.py behält die Namen als Alias.
Abweichung von ratsatlas-koeln @d609111 für den gemeinsamen Kern; löst nebenbei den Ringimport maske ↔ chat.
Wuppertal (Messstufe 5, 13.11.2026; Entscheidung 15.11.2026, CLAUDE.md 9): keine eigene Vorlagenart und kein eigener
Ausschuss für Anregungen und Beschwerden (Bürgeranträge meist als „Beschlussvorlage“); maßgeblich ist EINWOHNER_TITEL.
EINWOHNER behält die Bonner Namen (in Wuppertal ohne Treffer, unschädlich).
Wuppertal (Phase 3 vorab, Freigabe 16.11.2026, CLAUDE.md 9): AMT_PRIVAT nennt die Ressorts 103 (Umwelt, Grünflächen
und Forsten; Entscheidung des Auftraggebers 16.11.2026, z. B. Baumfällungen auf Privatgrundstücken), 105 (Baurecht bzw.
Bauen und Wohnen, mit der Bauaufsicht) und 106 (Umweltschutz) aus der Ämterliste (explore/ergebnisse/aemter.tsv, Stufe 4).
**Annahme:** Dass Bauanträge und Fällgenehmigungen dort federführend liegen, ist aus den Namen geschlossen, nicht belegt. Die Regel ist bewusst eher zu weit: Bei
diesen Vorlagen wird nur die Hausnummer im Titel ausgeblendet, Straße und Quartier bleiben."""
import json
import re
from collections import defaultdict

from . import config

# Vorlagen aus der Einwohnerschaft (Bonner Vorlagenarten, in Wuppertal ohne Treffer, siehe oben); wie EINWOHNER und EINWOHNER_TITEL in
# site/chat/tools.js
EINWOHNER = {"Bürgerantrag § 24 GO - Öffentlich", "Anregungen und Beschwerden", "Einwohnerfrage", "Bürgerbrief"}
EINWOHNER_TITEL = re.compile(r"bürgerantrag|einwohner|anregung|beschwerde", re.I)

OHNE_NR = "[Hausnummer ausgelassen]"
# Bauaufsicht, Umwelt und Grünflächen sowie Umweltschutz (Wuppertal, Ressorts 103, 105 und 106; siehe oben): Titel nennen oft private
# Baugrundstücke mit Hausnummer. Namen laut Quelle z. B. „Ressort 105 - Baurecht, Grundstücke und Wohnen“.
AMT_PRIVAT = re.compile(r"^(?:Ressort\s+)?10[356](?!\d)")
_L = r"[^\W\d_]"   # Buchstabe (wie \p{L})
# wie NR und SUFFIX in site/chat/tools.js
NR = (rf"\d{{1,3}}(?:\s?[a-zA-Z](?!{_L}))?(?:\s*(?:-|–|bis|und|u\.|/|,)\s*\d{{1,3}}(?:\s?[a-zA-Z](?!{_L}))?)*(?!\d)")
SUFFIX = (rf"(?:{_L}|[.-])*(?:straße|strasse|str\.|weg|platz|gasse|allee|ring|ufer|damm|pfad|chaussee|hof|markt|"
          r"graben|berg|feld)")


# „Hausnummer 82“, „Haus-Nr. 264“, „Haus Nr. 5“, „Hausnummern 36 bis 40“, „(neben Haus-Nr.) 68“ (wie WORT in
# site/chat/tools.js); eine schließende Klammer bleibt stehen
WORT = re.compile(rf"\b(?:hausnummern?|hausnr\.?|haus-nr\.?|haus\s+nr\.?)\s*(\))?\s*{NR}", re.I)


def _muster(strassen):
    names = sorted({s for s in strassen if s}, key=len, reverse=True)
    return re.compile(rf"((?:{'|'.join([*map(re.escape, names), SUFFIX])})\s+)(?:nr\.?\s*)?{NR}", re.I)


def einwohner(papers, auch=None):
    """Drucksachen von Vorlagen aus der Einwohnerschaft und aller Vorlagen, die mit ihnen über- oder untergeordnet
    verbunden sind (auch über mehrere Stufen): Stellungnahmen und Mitteilungen zu einem Bürgerantrag nennen oft
    dieselbe Anschrift, tragen aber weder die Art noch das Wort im Titel (Code-Prüfung 23.10.2026).
    auch: weitere Ausgangsvorlagen (privat: Bauordnung und Naturschutz, nur zum Ausblenden der Hausnummer)."""
    nachbarn = defaultdict(set)
    for p in papers:
        for r in p["superordinated"] + p["subordinated"]:
            nachbarn[p["reference"]].add(r["reference"])
            nachbarn[r["reference"]].add(p["reference"])
    offen = [p["reference"] for p in papers
             if p["paper_type"] in EINWOHNER or EINWOHNER_TITEL.search(p["name"] or "") or (auch and auch(p))]
    gesehen = set(offen)
    while offen:
        for n in nachbarn[offen.pop()]:
            if n not in gesehen:
                gesehen.add(n)
                offen.append(n)
    return sorted(gesehen)


def privat(p):
    """Federführend Bauordnungsamt oder Untere Naturschutzbehörde (Name der Organisationseinheit oder Amtsbezeichnung;
    Datenbank: amt_name, Export: responsibility)."""
    namen = [p.get("amt_name"), p.get("amt")] + [r.get("name") for r in p.get("responsibility") or []
                                                 if r.get("kind") == "federfuehrend"]
    return any(AMT_PRIVAT.match(n or "") for n in namen)


class Maske:
    """maske(titel, drucksache) → Titel ohne Hausnummer, wenn die Drucksache zur Einwohnerschaft gehört."""

    def __init__(self, refs, strassen=None):
        self.refs = set(refs)
        if strassen is None:
            strassen = json.loads(config.STRASSEN.read_text())["streets"] if config.STRASSEN.exists() else []
        self.rx = _muster(strassen)

    def _betroffen(self, titel, ref):
        # ohne Ziffer keine Hausnummer: spart die teure Regex bei den meisten Titeln (gleiche Ergebnisse)
        return bool(titel) and ref in self.refs and any(c.isdigit() for c in titel)

    def __call__(self, titel, ref):
        if not self._betroffen(titel, ref):
            return titel
        return WORT.sub(lambda m: OHNE_NR + (m.group(1) or ""), self.rx.sub(lambda m: m.group(1) + OHNE_NR, titel))

    def offen(self, titel, ref):
        """Bleibt nach dem Ausblenden eine Hausnummer stehen? (Prüfung in check.py)"""
        return self._betroffen(titel, ref) and bool(self.rx.search(titel) or WORT.search(titel))


def vorlagen(db):
    """Alle Vorlagen der Datenbank mit Art, Titel (ungekürzt), federführender Stelle und Beziehungen, wie
    einwohner() sie erwartet."""
    spalten = {r[1] for r in db.execute("PRAGMA table_info(paper)")}
    amt = ("(SELECT name FROM organization o WHERE o.id = paper.under_direction_of)"
           if "under_direction_of" in spalten else "NULL")
    papers = {r[0]: {"reference": r[1], "paper_type": r[2], "name": r[3], "amt_name": r[4], "superordinated": [],
                     "subordinated": []}
              for r in db.execute(f"SELECT id, reference, paper_type, name, {amt} FROM paper")}
    has_rel = db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'paper_relation'").fetchone()
    for parent, child in db.execute("SELECT parent_id, child_id FROM paper_relation") if has_rel else ():
        if parent in papers and child in papers:
            papers[child]["superordinated"].append({"reference": papers[parent]["reference"]})
            papers[parent]["subordinated"].append({"reference": papers[child]["reference"]})
    return list(papers.values())


def aus_db(db, strassen=None):
    """Maske für alle Vorlagen der Datenbank (Einwohnerschaft, Bauordnung, Naturschutz und verbundene Vorlagen)."""
    return Maske(einwohner(vorlagen(db), auch=privat), strassen)


# Gremien, deren Beratung auf eine Eingabe aus der Einwohnerschaft hinweist (Köln: Ausschuss für Anregungen und
# Beschwerden; Wuppertal laut Stufe 4 ohne eigenen Ausschuss, dafür „Beirat Bürgerbeteiligung“ unter organizations/gr)
GREMIUM_EINGABE = re.compile(r"(?i)anregungen und beschwerden|bürgerbeteiligung")
EINGABE = re.compile(r"(?i)§\s*24\b|eingabe|petition|einwohner(?:innen)?antrag|" + EINWOHNER_TITEL.pattern)


def hausnummer_punkt_erlaubt(paper, *, einwohner=(), amt_name=None, gremien=()):
    """Darf eine Straße mit Hausnummer im Titel auf die Hauskoordinate gesetzt werden (Phase 3, CLAUDE.md 2 Datenschutz
    und 5.2; Wuppertaler Fassung von ratsatlas-koeln @d609111 pipeline/geocode.hausnummer_punkt_erlaubt)?

    Nein bei Vorlagen aus der Einwohnerschaft und allen mit ihnen verbundenen (`einwohner`: Kennungen bzw. Referenzen
    aus einwohner() oder volltext.einwohner_kette), bei Vorlagenart oder Titel mit Hinweis auf eine Eingabe, bei
    federführender Bauaufsicht oder Umweltschutz (AMT_PRIVAT über `amt_name`) und bei jeder Beratung in einem Gremium
    für Anregungen und Beschwerden bzw. Bürgerbeteiligung (`gremien`: Namen). Dann bleibt höchstens die Straße oder das
    Quartier der Adresse (ortsnamen.Verzeichnis.verorte mit punkt_erlaubt=False); die Hausnummer erscheint nicht."""
    if paper.get("id") in einwohner or paper.get("reference") in einwohner:
        return False
    if EINGABE.search(paper.get("paperType") or "") or EINGABE.search(paper.get("name") or ""):
        return False
    if AMT_PRIVAT.match(amt_name or ""):
        return False
    return not any(GREMIUM_EINGABE.search(g or "") for g in gremien)
