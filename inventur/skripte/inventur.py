"""Inventur der übernommenen Dateien (Phase 0): Einordnung je Datei mit Begründung, Kölner Vorarbeit und Fakten.

Aufruf aus dem Repository-Wurzelverzeichnis (nach fundstellen.py und fakten.py):
    python3 inventur/skripte/inventur.py > inventur/inventur_module.tsv
Eingänge: inventur/regeln.tsv (Muster → Einordnung; erstes passendes Muster gilt, fnmatch) und
inventur/fakten_module.tsv. Kategorien laut CLAUDE.md 7.0: generisch | Bonn-spezifisch, anpassen |
Köln-spezifisch, anpassen | Zusatzthema, deaktivieren | entfernen. Die Einordnung ist eine Vorlage zur Freigabe.
Bricht ab, wenn eine Datei ohne Regel bleibt oder eine Regel eine unbekannte Kategorie nennt.
"""
import csv
import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INV = ROOT / "inventur"
KATEGORIEN = {"generisch", "Bonn-spezifisch, anpassen", "Köln-spezifisch, anpassen", "Zusatzthema, deaktivieren",
              "entfernen"}


def lesen(pfad):
    with open(pfad, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def main():
    regeln = lesen(INV / "regeln.tsv")
    falsch = [r["muster"] for r in regeln if r["kategorie"] not in KATEGORIEN]
    if falsch:
        sys.exit("unbekannte Kategorie in regeln.tsv: " + ", ".join(falsch))
    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, quotechar=None)
    w.writerow(["datei", "zeilen", "kategorie", "funktion", "begruendung", "koeln_vorarbeit", "phase", "herkunft",
                "bonn_seit_koeln_basis", "koeln", "fundstellen", "begriff_ortsteil"])
    offen = []
    for f in lesen(INV / "fakten_module.tsv"):
        r = next((r for r in regeln if fnmatch.fnmatch(f["datei"], r["muster"])), None)
        if r is None:
            offen.append(f["datei"])
            continue
        w.writerow([f["datei"], f["zeilen"], r["kategorie"], r["funktion"], r["begruendung"], r["koeln_vorarbeit"],
                    r["phase"], f["herkunft"], f["bonn_seit_koeln_basis"], f["koeln"], f["fundstellen"],
                    f["begriff_ortsteil"]])
    if offen:
        sys.exit("ohne Einordnung: " + ", ".join(offen))


if __name__ == "__main__":
    main()
