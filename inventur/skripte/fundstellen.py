"""Fundstellen Bonner und Kölner Bezüge im übernommenen Code (Phase 0, Inventur).

Aufruf aus dem Repository-Wurzelverzeichnis: python3 inventur/skripte/fundstellen.py > inventur/fundstellen.tsv
Durchsucht alle versionierten Textdateien außer inventur/, explore/ und CLAUDE.md (der Auftrag nennt Bonn und Köln
als Vorlagen). Eine Zeile kann mehrere Kategorien tragen. Abgeleitet aus ratsatlas-koeln @d609111
(inventur/skripte/fundstellen.py), ergänzt um Kölner Bezüge.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 51 Ortsteile und Stadtbezirke Bonns (Liste aus ratsatlas-koeln, dort laut ortsteile_bonn.geojson in allris-test @9eea7ea)
ORTSTEILE_BONN = ("Alt-Godesberg|Auerberg|Beuel-Mitte|Beuel-Ost|Bonn-Castell|Bonn-Zentrum|Brüser Berg|Buschdorf|"
                  "Dottendorf|Dransdorf|Duisdorf|Endenich|Friesdorf|Geislar|Godesberg-Nord|Godesberg-Villenviertel|"
                  "Graurheindorf|Gronau|Hardthöhe|Heiderhof|Hochkreuz|Hoholz|Holtorf|Holzlar|Ippendorf|Kessenich|"
                  "Küdinghoven|Lannesdorf|Lengsdorf|Lessenich|Meßdorf|Limperich|Mehlem|Muffendorf|Nordstadt|Oberkassel|"
                  "Pennenfeld|Plittersdorf|Poppelsdorf|Pützchen|Bechlinghoven|Ramersdorf|Röttgen|Rüngsdorf|"
                  "Schwarzrheindorf|Vilich-Rheindorf|Schweinheim|Südstadt|Tannenbusch|Venusberg|Vilich|Müldorf|Weststadt|"
                  "Ückesdorf").split("|")
BEZIRKE_BONN = ["Bad Godesberg", "Beuel", "Hardtberg"]
# Kölner Stadtbezirke (ohne „Innenstadt“, das auch allgemein vorkommt) und Beispielorte aus den Kölner Tests
ORTE_KOELN = ["Rodenkirchen", "Lindenthal", "Ehrenfeld", "Nippes", "Chorweiler", "Porz", "Kalk", "Mülheim",
              "Venloer Straße"]

MUSTER = [
    ("url_bonn", re.compile(r"https?://[^\s\"')>]*bonn[^\s\"')>]*", re.I)),
    ("url_koeln", re.compile(r"https?://[^\s\"')>]*(koeln|köln|cologne)[^\s\"')>]*", re.I)),
    ("url_projekt", re.compile(r"(daimpad\.github\.io/(allris-test|ratsatlas-bonn|ratsatlas-koeln)|"
                               r"github\.com/daimpad/(allris-test|ratsatlas-bonn|ratsatlas-koeln)|ris-bonn\.datenatlas\.de|"
                               r"(bonn|koeln)\.ratsatlas\.de)", re.I)),
    ("site_url", re.compile(r"\b(SITE_URL|PAKET_URL)\b")),
    ("oparl_lite", re.compile(r"(machdenstaat|OParl-Lite|oparl_lite|LITE_GRAPHQL|consultations_lite|fetch-lite)", re.I)),
    ("name_allris_bonn", re.compile(r"allris-bonn", re.I)),
    ("ortsteil_bonn", re.compile(r"\b(" + "|".join(re.escape(o) for o in ORTSTEILE_BONN) + r")\b")),
    ("bezirk_bonn", re.compile(r"\b(" + "|".join(re.escape(b) for b in BEZIRKE_BONN) + r")\b")),
    ("ort_koeln", re.compile(r"\b(" + "|".join(re.escape(o) for o in ORTE_KOELN) + r")\b")),
    ("bonn", re.compile(r"\bBonn(er|s)?\b|_bonn\b|/bonn/|\bbonn\b", re.I)),
    ("koeln", re.compile(r"\bKöln(er|s)?\b|\bkoeln\b|_koeln\b|/koeln/|ratsatlas-koeln", re.I)),
]


def dateien():
    """Versionierte Dateien (ohne Caches und lokale Rohdaten)."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [n for n in out.split("\n") if n and (ROOT / n).is_file()]


def main():
    out = sys.stdout
    out.write("datei\tzeile\tkategorie\ttreffer\tauszug\n")
    for rel in dateien():
        if rel.startswith(("inventur/", "explore/")) or rel == "CLAUDE.md":
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for nr, zeile in enumerate(text.splitlines(), 1):
            for kat, rx in MUSTER:
                treffer = sorted({m.group(0) for m in rx.finditer(zeile)})
                if treffer:
                    auszug = zeile.strip().replace("\t", " ")[:160]
                    out.write(f"{rel}\t{nr}\t{kat}\t{' | '.join(treffer)}\t{auszug}\n")


if __name__ == "__main__":
    main()
