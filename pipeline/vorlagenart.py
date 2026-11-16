"""Zerlegung der Wuppertaler Vorlagenart (`paperType`) in Art, Einreichende und Ebene (CLAUDE.md 5.3, Phase 2).

In Wuppertal steht in `paperType` oft, wer einreicht und auf welcher Ebene: „Antrag CDU“, „Antrag B90/Grüne BV“,
„Gemeinsamer Antrag Rat“, „Antrag FDP / WfW Rat AU“. Die Zerlegung ist „aus Vorlagenart abgeleitet“ und wird so
gekennzeichnet (actors.originators: method „paper_type“, evidence = paperType wörtlich).

Regeln: Die Regeln 1–4 sind die Regeltabelle aus Phase 1 (`explore/paperType_regeln.tsv`, Stufe 5 vom 13.11.2026:
96 % der Stichprobe zerlegt). Die Regeln 5–8 decken die Arten ab, für die Stufe 5 keine Regel fand
(`explore/ergebnisse/oparl_papertypen.tsv`): „Beschlussvorlage BV“, „Durchführungsbeschluss“, „Grundsatzbeschluss“,
„Satzungsbeschluss“, „Gemeinsame große Anfrage“, „Anfrage <Einreichende> BV“. Ihre Zuordnung (Verwaltung bzw.
Politik) ist eine **Annahme** aus dem Wortlaut. Die erste passende Regel gilt; das Muster muss den ganzen Wert treffen.
Kürzel nach der Ebene (z. B. „AU“, „OB“) bleiben als `zusatz` stehen; ihre Bedeutung ist offen (CLAUDE.md 8).
"""
import re

VERWALTUNG, POLITIK = "verwaltung", "politik"

# (Nr., Muster, Art, Einreichende, Ebene, Zusatz, Kategorie, Beleg); „{name}“ wird aus der benannten Gruppe gefüllt,
# „–“ heißt: keine Einreichenden (Verwaltungsvorlage), "" heißt: offen.
REGELN = [
    (1, r"(?P<art>Beschlussvorlage|Bericht|Antwort auf Anfragen)", "{art}", "–", "", "", VERWALTUNG,
     "explore/paperType_regeln.tsv Regel 1"),
    (2, r"Gemeinsamer Antrag (?P<ebene>Rat|BV)", "Gemeinsamer Antrag", "", "{ebene}", "", POLITIK,
     "explore/paperType_regeln.tsv Regel 2"),
    (3, r"(?P<art>Antrag|Große Anfrage) (?P<einreichende>(?:(?!\b(?:Rat|BV)\b).)+?) (?P<ebene>Rat|BV)"
        r"(?: (?P<zusatz>\S+))?", "{art}", "{einreichende}", "{ebene}", "{zusatz}", POLITIK,
     "explore/paperType_regeln.tsv Regel 3"),
    (4, r"(?P<art>Antrag|Große Anfrage) (?P<einreichende>(?:(?!\b(?:Rat|BV)\b).)+)", "{art}", "{einreichende}", "",
     "", POLITIK, "explore/paperType_regeln.tsv Regel 4"),
    (5, r"(?P<art>Beschlussvorlage) (?P<ebene>BV)", "{art}", "–", "{ebene}", "", VERWALTUNG,
     "Stufe 5 (13.11.2026), Annahme: Verwaltungsvorlage an eine Bezirksvertretung"),
    (6, r"(?P<art>Durchführungsbeschluss|Grundsatzbeschluss|Satzungsbeschluss)", "{art}", "–", "", "", VERWALTUNG,
     "Stufe 5 (13.11.2026), Annahme: Beschlussvorlage der Verwaltung"),
    (7, r"Gemeinsame große Anfrage", "Gemeinsame Große Anfrage", "", "", "", POLITIK,
     "Stufe 5 (13.11.2026), Annahme: wie Regel 2, Einreichende offen"),
    (8, r"(?P<art>Anfrage) (?P<einreichende>(?:(?!\b(?:Rat|BV)\b).)+?) (?P<ebene>Rat|BV)", "{art}", "{einreichende}",
     "{ebene}", "", POLITIK, "Stufe 5 (13.11.2026), Annahme: wie Regel 3 für „Anfrage“"),
]
_KOMPILIERT = [(nr, re.compile(muster), art, ein, eb, zu, kat, beleg)
               for nr, muster, art, ein, eb, zu, kat, beleg in REGELN]

# Einreichende laut paperType → Anzeigename wie actors.PARTIES (für Suche und Filter); was hier fehlt, bleibt wörtlich.
NAMEN = {
    "CDU": "CDU",
    "SPD": "SPD",
    "B90/Grüne": "Grüne",
    "B90/Gr": "Grüne",
    "die Linke": "Die Linke",
    "DIE LINKE.": "Die Linke",
    "AfD": "AfD",
    "FDP": "FDP",
}
# Einreichende, die keine Fraktion oder Gruppe sind
EINZELMANDAT = {"gewähltes Mitglied"}


def _fuelle(vorlage, m):
    return re.sub(r"\{(\w+)\}", lambda g: (m.group(g.group(1)) or "").strip(), vorlage)


def zerlege(paper_type):
    """dict(art, einreichende, ebene, zusatz, kategorie, regel, beleg) oder None (keine Regel)."""
    wert = " ".join(str(paper_type or "").split())
    if not wert:
        return None
    for nr, muster, art, ein, eb, zu, kat, beleg in _KOMPILIERT:
        m = muster.fullmatch(wert)
        if m:
            return {"art": _fuelle(art, m), "einreichende": _fuelle(ein, m), "ebene": _fuelle(eb, m),
                    "zusatz": _fuelle(zu, m), "kategorie": kat, "regel": nr, "beleg": beleg}
    return None


def kategorie(paper_type):
    """„verwaltung“, „politik“ oder None."""
    z = zerlege(paper_type)
    return z["kategorie"] if z else None


def anzeigename(einreichende):
    return NAMEN.get(einreichende, einreichende)
