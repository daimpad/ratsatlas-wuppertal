"""Fakten je Datei für die Inventur (Phase 0): Herkunft, Änderungen in Bonn und Köln, Fundstellen.

Aufruf aus dem Repository-Wurzelverzeichnis, mit lesenden Klonen der beiden Vorlagen:
    python3 inventur/skripte/fakten.py --bonn ../daimpad/allris-test --koeln ../daimpad/ratsatlas-koeln \
        > inventur/fakten_module.tsv
Der Klon von allris-test braucht die Historie bis 9eea7ea (Basis der Kölner Kopie), etwa
`git fetch --depth=400 origin main`.

Spalten:
- herkunft: allris-test | ratsatlas-koeln | neu (Wuppertal)
- bonn_seit_koeln_basis: Änderung in allris-test zwischen 9eea7ea (Basis Köln) und 52fe9ca (Basis Wuppertal)
- koeln: in ratsatlas-koeln @d609111 unverändert gegenüber 9eea7ea | angepasst (+/- Zeilen) | nicht vorhanden
- koeln_kategorie, koeln_begruendung: Einordnung in inventur/inventur_module.tsv von ratsatlas-koeln
- fundstellen: Zeilen in inventur/fundstellen.tsv; begriff_ortsteil: Zeilen mit „Ortsteil“ (Gebietsbegriff Bonns)
"""
import argparse
import csv
import difflib
import io
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BONN_BASIS_KOELN = "9eea7eaaba8d822ac6e4b7a96357e64cce406e47"
BONN_BASIS = "52fe9cad6d66ad9dc5df96deb645b175f5543cac"
KOELN_BASIS = "d6091117b82da1d70ee2bd10a764d7be1e0c0361"
AUS_KOELN = {"pipeline/sessionnet.py", "pipeline/abruf.py", "tests/conftest.py", "tests/test_sessionnet.py"}
NEU = {".github/workflows/static.yml", "CLAUDE.md", "NOTICE"}


def show(repo, rev, pfad):
    r = subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{pfad}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def bonn_pfad(rel):
    """Pfad in allris-test (die Bonner Workflows liegen hier in .github/workflows-inaktiv/)."""
    return rel.replace(".github/workflows-inaktiv/", ".github/workflows/")


def koeln_pfade(rel):
    """Kandidaten für denselben Inhalt in ratsatlas-koeln (dort teils umbenannt oder verschoben)."""
    p = bonn_pfad(rel)
    kand = [p]
    if p.startswith(".github/workflows/"):
        name = p.rsplit("/", 1)[1]
        stamm = name[:-4]
        kand = [f".github/workflows-inaktiv/{stamm}_bonn.yml", f".github/workflows-inaktiv/{name}", p]
    if p.startswith(".claude/skills/allris-bonn/"):
        kand = [p, p.replace("allris-bonn", "ratsatlas-koeln")]
    return kand


def zeilen_diff(a, b):
    a = a.decode("utf-8", "replace").splitlines()
    b = b.decode("utf-8", "replace").splitlines()
    plus = minus = 0
    for z in difflib.unified_diff(a, b, lineterm="", n=0):
        if z.startswith("+") and not z.startswith("+++"):
            plus += 1
        elif z.startswith("-") and not z.startswith("---"):
            minus += 1
    return plus, minus


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bonn", required=True)
    ap.add_argument("--koeln", required=True)
    a = ap.parse_args()
    bonn, koeln = Path(a.bonn), Path(a.koeln)

    kinv = {}
    roh = show(koeln, KOELN_BASIS, "inventur/inventur_module.tsv") or b""
    for row in csv.DictReader(io.StringIO(roh.decode("utf-8")), delimiter="\t"):
        kinv[row["datei"]] = row

    fund = Counter()
    with open(ROOT / "inventur" / "fundstellen.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            fund[row["datei"]] += 1

    dateien = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split("\n")
    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_NONE, quotechar=None)
    w.writerow(["datei", "zeilen", "herkunft", "bonn_seit_koeln_basis", "koeln", "koeln_pfad", "koeln_kategorie",
                "koeln_begruendung", "fundstellen", "begriff_ortsteil"])
    rx_ortsteil = re.compile(r"ortsteil", re.I)
    for rel in sorted(d for d in dateien if d):
        if rel.startswith("inventur/"):
            continue
        p = ROOT / rel
        daten = p.read_bytes()
        try:
            text = daten.decode("utf-8")
            zeilen = len(text.splitlines())
            ortsteil = sum(1 for z in text.splitlines() if rx_ortsteil.search(z))
        except UnicodeDecodeError:
            zeilen, ortsteil = "", 0
        if rel in NEU:
            herkunft = "neu (Wuppertal)"
        elif rel in AUS_KOELN:
            herkunft = "ratsatlas-koeln"
        elif rel == "pipeline/config.py":
            herkunft = "allris-test + ratsatlas-koeln (Abrufpolitik)"
        else:
            herkunft = "allris-test"

        bp = bonn_pfad(rel)
        b_jetzt = show(bonn, BONN_BASIS, bp)
        b_basis = show(bonn, BONN_BASIS_KOELN, bp)
        if herkunft == "ratsatlas-koeln" or herkunft.startswith("neu"):
            bonn_status = "–"
        elif b_jetzt is None:
            bonn_status = "?"
        elif b_basis is None:
            bonn_status = "neu seit 9eea7ea"
        elif b_basis == b_jetzt:
            bonn_status = "unverändert"
        else:
            pl, mi = zeilen_diff(b_basis, b_jetzt)
            bonn_status = f"geändert (+{pl}/-{mi})"

        k_status, k_pfad = "nicht vorhanden", ""
        for kp in ([] if herkunft.startswith("neu") else koeln_pfade(rel)):
            k = show(koeln, KOELN_BASIS, kp)
            if k is None:
                continue
            k_pfad = kp
            if herkunft == "ratsatlas-koeln":
                k_status = "Quelle (unverändert übernommen)" if k == daten else "Quelle (abweichend)"
            elif b_basis is None:
                k_status = "vorhanden (in Bonn neu seit 9eea7ea)"
            elif k == b_basis:
                k_status = "unverändert"
            else:
                pl, mi = zeilen_diff(b_basis, k)
                k_status = f"angepasst (+{pl}/-{mi})"
            break
        if herkunft.startswith("neu"):
            k_status = "–"
        kr = kinv.get(k_pfad) or kinv.get(rel) or {}
        w.writerow([rel, zeilen, herkunft, bonn_status, k_status, k_pfad, kr.get("kategorie", ""),
                    kr.get("begruendung", ""), fund.get(rel, 0), ortsteil])


if __name__ == "__main__":
    main()
