"""Haushaltsplan 2026/2027 der Stadt Wuppertal: Beträge je Produktbereich und bezirksbezogene Haushaltsansätze
(Zusatzthema `haushalt`, erste Stufe; Entscheidungen des Auftraggebers 17.11.2026, CLAUDE.md 9).

Quelle: die beiden PDF in `content/` (vom Auftraggeber abgelegt; Band 1 mit Haushaltssatzung, Gesamtplänen, Teilplänen der
Produktbereiche und Anlagen, Band 2 mit den Teilplänen der Produktgruppen). Gelesen wird nur Band 1, mit pdftotext
(poppler-utils) im Layout-Modus, ohne Netz. Die Dateien werden über SHA-256 im Stand vermerkt.

1. Gesamtergebnisplan (Seite mit „Gesamtergebnisplan“ und „Ordentliche Erträge“) und Teilergebnispläne der 17
   Produktbereiche (Abschnitt III.3.1), Zeilen 1–18 (ordentliche Erträge und Aufwendungen, ordentliches Ergebnis), acht
   Spalten: Ergebnis 2023, Ergebnis 2024, Ansatz 2025, Ansatz 2026, Ansatz 2027, Planung 2028–2030. Beträge in Euro, wie
   gedruckt (ganze Euro). Prüfsummen je Spalte: Zeilen 1–9 = 10, 11–16 = 17, 10 + 17 = 18 je Produktbereich und Summe
   der Produktbereiche = Gesamtergebnisplan (Zeilen 10, 17, 18). Abweichungen bis RUNDUNG Euro sind Rundung (der Plan
   rechnet mit Cent und druckt ganze Euro; gemessen 17.11.2026: höchstens 2 Euro).
2. Bezirksbezogene Haushaltsansätze (Anlage 9, § 37 Abs. 4 GO NRW): je Bezirksvertretung die Zeilen mit Fallgruppe
   (1: Verfügungsmittel und Pauschalen, über die die Bezirksvertretung allein entscheidet; 2: Ansätze, über die sie auf
   Vorschlag der Verwaltung entscheidet; 3: Maßnahmen, die dem Stadtbezirk zuordenbar sind), Art, Erläuterung (Name der
   Maßnahme, oft mit Straße) und Planung 2026–2030. Eine Summe je Bezirk druckt der Plan nicht; geprüft wird, dass jede
   Zeile mit Beträgen gelesen wurde (ungelesene Zeilen mit Zahlen führen zum Abbruch).

Nicht übernommen: Namen von Personen (Band 2 nennt je Produktgruppe eine verantwortliche Person), Texte des Vorberichts.
Lizenz: Der Haushaltsplan nennt keine Lizenz (nur für das Titelbild: CC BY-NC-ND, nicht verwendet); als Teil der
Haushaltssatzung dürfte er amtliches Werk sein (§ 5 UrhG) – eine Einschätzung wie in Bonn, keine gesicherte Auskunft;
die Frage geht an die Stadt (CLAUDE.md 9, 17.11.2026). Befund: Band 2 (Stand Mai 2026) beschriftet die Spalten 2026
und 2027 mit „Planung“, Band 1 (Juli 2026) mit „Ansatz“; Band 2 wird in dieser Stufe nicht gelesen.

Aufruf: python3 -m pipeline haushalt-wuppertal   (schreibt data/haushalt/*.tsv und data/haushalt/STAND.json)
"""
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import config

BAND1 = config.ROOT / "content" / "Haushalt_der_Stadt_Wuppertal_2026_2027-Band-1.pdf"
ZIEL = config.ROOT / "data" / "haushalt"
SPALTEN = ["Ergebnis 2023", "Ergebnis 2024", "Ansatz 2025", "Ansatz 2026", "Ansatz 2027", "Planung 2028",
           "Planung 2029", "Planung 2030"]
BEZIRK_SPALTEN = ["Planung 2026", "Planung 2027", "Planung 2028", "Planung 2029", "Planung 2030"]
RUNDUNG = 3   # Euro je Prüfsumme
ZAHL = r"-?\d{1,3}(?:\.\d{3})*"
ZEILE = re.compile(rf"^\s*(\d{{1,2}})\s+[=+\-]?\s+(.*?)\s*((?:{ZAHL}\s+){{7}}{ZAHL})\s*$")
PRODUKTBEREICH = re.compile(r"Produktbereich (\d{2}) – ([^\n]+)")
BEZIRK = re.compile(r"^\s*\d{1,2}\.\s+Bezirksvertretung\s+(.+?)\s*$")
BEZIRK_ZEILE = re.compile(rf"^\s*(?:([123])\)\s+)?(\S.*?\S)\s{{2,}}(\S.*?\S)\s+((?:{ZAHL}\s+){{4}}{ZAHL})\s*$")
LEER_ODER_KOPF = re.compile(r"^\s*$|Planung|Art Bezirksbezogene|^\s*20\d\d(\s+20\d\d)*\s*$|STADT WUPPERTAL|"
                            r"Stadt Wuppertal – Anlagen|^\s*\d{3}\s*$|Bezirksvertretung")


def _betrag(text):
    return int(text.replace(".", ""))


def seite(pdf, nr):
    """Text einer Seite (pdftotext -layout)."""
    return subprocess.run(["pdftotext", "-layout", "-f", str(nr), "-l", str(nr), str(pdf), "-"],
                          capture_output=True, text=True, check=True).stdout


def seitenzahl(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True).stdout
    return int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))


def ergebniszeilen(text):
    """{Zeilennummer: (Bezeichnung, [8 Beträge])} der Ergebnisplan-Zeilen einer Seite; die erste Fundstelle gilt."""
    out = {}
    for line in text.splitlines():
        m = ZEILE.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = (m.group(2).strip(), [_betrag(x) for x in m.group(3).split()])
    return out


def bezirkszeilen(text, bezirk=None, fallgruppe=None):
    """(Zeilen, Bezirk, Fallgruppe, ungelesen): Zeilen der bezirksbezogenen Ansätze einer Seite. Bezirk und Fallgruppe
    gelten bis zur nächsten Angabe (auch über Seiten hinweg). `ungelesen`: Zeilen mit Beträgen, die nicht passen."""
    zeilen, ungelesen = [], []
    for line in text.splitlines():
        b = BEZIRK.match(line)
        if b:
            bezirk, fallgruppe = b.group(1), None
            continue
        m = BEZIRK_ZEILE.match(line)
        if m and bezirk:
            fallgruppe = m.group(1) or fallgruppe
            zeilen.append({"bezirk": bezirk, "fallgruppe": fallgruppe, "art": m.group(2).strip(),
                           "erlaeuterung": m.group(3).strip(),
                           "betraege": [_betrag(x) for x in m.group(4).split()]})
            continue
        if bezirk and re.search(rf"{ZAHL}\s+{ZAHL}\s*$", line) and not LEER_ODER_KOPF.search(line):
            ungelesen.append(line.strip())
    return zeilen, bezirk, fallgruppe, ungelesen


def produktbereiche(pdf=BAND1):
    """(Gesamtergebnisplan, Produktbereiche, Seiten): Gesamtplan {Zeile: (Bezeichnung, Beträge, Seite)};
    Produktbereiche {Nummer: {"name", "zeilen": {Zeile: (Bezeichnung, Beträge, Seite)}}}."""
    gesamt, pb, aktuell = {}, {}, None
    for nr in range(1, seitenzahl(pdf) + 1):
        text = seite(pdf, nr)
        if not gesamt and "Gesamtergebnisplan" in text and "Ordentliche Erträge" in text:
            gesamt = {z: (b, w, nr) for z, (b, w) in ergebniszeilen(text).items() if int(z) <= 18}
        m = PRODUKTBEREICH.search(text)
        if m and "Teilergebnisplan" in text:
            aktuell = m.group(1)
            pb.setdefault(aktuell, {"name": m.group(2).strip(), "zeilen": {}})
        elif m:
            aktuell = None
        if aktuell and "Teilergebnisplan" in text:
            for z, (b, w) in ergebniszeilen(text).items():
                if int(z) <= 18:
                    pb[aktuell]["zeilen"].setdefault(z, (b, w, nr))
        if "Teilfinanzplan" in text and aktuell and len(pb[aktuell]["zeilen"]) >= 18:
            aktuell = None
    return gesamt, pb


def pruefen(gesamt, pb):
    """Liste der Prüfungen (Name, Spalte, Abweichung) mit Abweichung über RUNDUNG; leer = in Ordnung."""
    fehler = []
    nummern = [str(i) for i in range(1, 19)]
    for k, p in pb.items():
        fehlt = [z for z in nummern if z not in p["zeilen"]]
        if fehlt:
            fehler.append((f"Produktbereich {k}: Zeilen fehlen {fehlt}", None, None))
            continue
        w = {z: p["zeilen"][z][1] for z in nummern}
        for i in range(8):
            for name, soll, ist in ((f"PB {k}: Zeilen 1–9 = 10", sum(w[str(z)][i] for z in range(1, 10)), w["10"][i]),
                                    (f"PB {k}: Zeilen 11–16 = 17", sum(w[str(z)][i] for z in range(11, 17)), w["17"][i]),
                                    (f"PB {k}: 10 + 17 = 18", w["10"][i] + w["17"][i], w["18"][i])):
                if abs(soll - ist) > RUNDUNG:
                    fehler.append((name, SPALTEN[i], soll - ist))
    for z in ("10", "17", "18"):
        if z not in gesamt:
            fehler.append((f"Gesamtergebnisplan: Zeile {z} fehlt", None, None))
            continue
        for i in range(8):
            summe = sum(p["zeilen"][z][1][i] for p in pb.values() if z in p["zeilen"])
            if abs(summe - gesamt[z][1][i]) > RUNDUNG:
                fehler.append((f"Summe der Produktbereiche = Gesamtergebnisplan, Zeile {z}", SPALTEN[i],
                               summe - gesamt[z][1][i]))
    return fehler


def bezirke(pdf=BAND1):
    """(Zeilen mit Seite, ungelesene Zeilen) der Anlage „Übersichten der bezirksbezogenen Haushaltsansätze“."""
    zeilen, ungelesen, bezirk, fallgruppe, drin = [], [], None, None, False
    for nr in range(1, seitenzahl(pdf) + 1):
        text = seite(pdf, nr)
        # Tabellenseiten tragen den Spaltenkopf „Bezirksbezogene Haushaltsansätze“; dazwischen kann eine leere Seite
        # stehen (Seite 338). Die Anlage endet mit Anlage 10 (Liste der geplanten Investitionen)
        if "Bezirksbezogene Haushaltsansätze" in text:
            drin = True
        elif drin and ("Anlage 10" in text or "geplanten Investitionen" in text):
            break
        elif drin:
            if bezirkszeilen(text, bezirk, fallgruppe)[3]:
                raise SystemExit(f"Seite {nr}: Beträge ohne Spaltenkopf der bezirksbezogenen Ansätze")
            continue
        if not drin:
            continue
        z, bezirk, fallgruppe, u = bezirkszeilen(text, bezirk, fallgruppe)
        zeilen += [dict(x, seite=nr) for x in z]
        ungelesen += [(nr, x) for x in u]
    return zeilen, ungelesen


def _sha256(pfad):
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


def _tsv(pfad, kopf, zeilen):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with open(pfad, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(kopf)
        w.writerows(zeilen)


def auslesen(pdf=BAND1, ziel=ZIEL):
    """Liest Band 1, prüft und schreibt produktbereiche.tsv, bezirke.tsv und STAND.json nach `ziel`; bricht bei einer
    Prüfabweichung oder ungelesenen Zeilen ab, ohne etwas zu schreiben."""
    pdf, ziel = Path(pdf), Path(ziel)
    gesamt, pb = produktbereiche(pdf)
    fehler = pruefen(gesamt, pb)
    if len(pb) != 17:
        fehler.append((f"{len(pb)} statt 17 Produktbereiche", None, None))
    bz, ungelesen = bezirke(pdf)
    namen = sorted({z["bezirk"] for z in bz})
    if len(namen) != 10:
        fehler.append((f"{len(namen)} statt 10 Bezirksvertretungen: {namen}", None, None))
    if ungelesen:
        fehler.append((f"{len(ungelesen)} ungelesene Zeilen mit Beträgen, z. B. Seite {ungelesen[0][0]}", None, None))
    if fehler:
        raise SystemExit("Haushalt nicht übernommen:\n" + "\n".join(f"- {n} {s or ''} {d if d is not None else ''}"
                                                                   for n, s, d in fehler))
    quelle = f"content/{pdf.name}"
    zeilen = [["Gesamt", "Gesamtergebnisplan", z, b, SPALTEN[i], w[i], quelle, s]
              for z, (b, w, s) in sorted(gesamt.items(), key=lambda x: int(x[0])) for i in range(8)]
    zeilen += [[k, p["name"], z, b, SPALTEN[i], w[i], quelle, s]
               for k, p in sorted(pb.items()) for z, (b, w, s) in sorted(p["zeilen"].items(), key=lambda x: int(x[0]))
               for i in range(8)]
    _tsv(ziel / "produktbereiche.tsv", ["produktbereich", "name", "zeile", "bezeichnung", "spalte", "betrag_eur",
                                        "datei", "seite"], zeilen)
    _tsv(ziel / "bezirke.tsv", ["bezirksvertretung", "fallgruppe", "art", "erlaeuterung", "spalte", "betrag_eur",
                                "datei", "seite"],
         [[z["bezirk"], z["fallgruppe"] or "", z["art"], z["erlaeuterung"], BEZIRK_SPALTEN[i], z["betraege"][i], quelle,
           z["seite"]] for z in bz for i in range(5)])
    (ziel / "STAND.json").write_text(json.dumps({
        "quelle": quelle, "sha256": _sha256(pdf), "werkzeug": "pdftotext -layout (poppler-utils)",
        "haushaltsplan": "2026/2027", "produktbereiche": len(pb), "bezirksvertretungen": len(namen),
        "bezirkszeilen": len(bz), "pruefung": f"alle Prüfsummen innerhalb von {RUNDUNG} Euro (Rundung)",
        "lizenz": ("keine Angabe im Dokument (Titelbild CC BY-NC-ND, nicht verwendet); als Teil der Haushaltssatzung "
                   "vermutlich amtliches Werk (§ 5 UrhG), Klärung mit der Stadt offen"),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Haushalt 2026/2027: Gesamtergebnisplan und {len(pb)} Produktbereiche (Prüfsummen in Ordnung), "
          f"{len(bz)} bezirksbezogene Zeilen in {len(namen)} Bezirksvertretungen → {ziel}")
    return gesamt, pb, bz
