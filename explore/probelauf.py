"""Probelauf der Messstufen gegen den lokalen Testserver – keine Anfrage an die Stadt oder an andere Adressen.

Abgeleitet aus ratsatlas-koeln @d609111 (explore/probelauf.py); Stufen und Obergrenzen für Wuppertal (STUFEN.md).
Startet explore/testserver.py (Wuppertaler Antwortform laut CLAUDE.md 3.1, erfundene Daten) auf 127.0.0.1 und führt
die Kommandos aus STUFEN zweimal aus:
- „Folge“: in der Reihenfolge der Stufen mit gemeinsamem Cache, wie die echten Nächte in derselben Arbeitsumgebung
- „leerer Cache“: jedes Kommando mit eigenem, leerem Cache (ungünstigster Fall, z. B. neue Arbeitsumgebung); die
  Ergebnisse (ergebnisse/, darin oparl_umfang.tsv für `stichprobe` und oparl_organisationen.tsv für `pdf-koepfe`)
  bleiben gemeinsam; `pdf-koepfe` bekommt dabei nur die Stichprobendatei aus Stufe 5, ohne die Rohdaten
Zählt je Schritt die Anfragen ans Netz und aus dem Cache (laut oparl_laeufe.tsv und laut Testserver) und prüft sie
gegen die Obergrenze, die in STUFEN.md für die echte Messung steht. Ausgabe als Markdown.

Die Obergrenzen sind die Zahlen ohne Cache, für `umfang` die rechnerische Höchstzahl der Bisektion
(oparl_messung.hoechstzahl_umfang: Body, erste Seite, je Bereich zwei Enden und ceil(log2(Breite)) Schritte); der
Probelauf liegt darunter, weil die Schritte vom Ort der Grenze abhängen. Für Wuppertal gelten die Zahlen, wenn der
Body die vier Listen nennt, die Organisationsliste mindestens 5 und die Sitzungsliste mindestens 2 Seiten hat und die
Stichprobe genug Verwaltungsvorlagen ohne underDirectionOf mit Datei enthält; sonst sind es weniger.
Stufe 6 (`pdf-koepfe`) liest erfundene PDFs in acht Kopfvarianten (testserver.pdf_kopf: ein Kandidat, mehrere
gleiche oder verschiedene, Kandidat nur nach dem Abschnitt, ohne Kandidat, ohne Textebene, Kopf auf Seite 2,
Silbentrennung); die Fehlervarianten (404, defekte, große Datei, HTML) prüft nur tests/test_messstufen.py. Die
Anfragezahl (eine je ausgewählter Vorlage, höchstens 100) hängt nicht vom Inhalt der Dateien ab.
Nicht im Probelauf: Stufe G (explore/geodaten.py, Höchstzahl geodaten.geplante_anfragen(), ohne Netz geprüft in
tests/test_messstufen.py), die optionalen Befehle mit Platzhaltern in Stufe 4 und explore/ortsnamen.py (ohne Netz).
Aufruf: python3 explore/probelauf.py [--ziel VERZEICHNIS]   (ohne --ziel: temporäres Verzeichnis)
"""
import argparse
import csv
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from testserver import Testserver  # noqa: E402

# Stichprobendatei im Cache, Grundlage für pdf-koepfe (oparl_messung.STICHPROBE)
STICHPROBE = "stichprobe_vorlagen.jsonl"

# (Stufe, Kommando, Parameter, Obergrenze RATSATLAS_MAX_ANFRAGEN) – gleiche Werte wie in STUFEN.md
STUFEN = [
    ("1", "test", [], 3),
    ("2", "kennzahlen", [], 8),
    ("3", "umfang", [], 17),
    ("4", "organisationen", ["--seiten", "5"], 6),
    ("4", "sitzungen", ["--seiten", "2"], 3),
    ("5", "stichprobe", ["--seiten", "8"], 9),
    ("6", "pdf-koepfe", ["--anzahl", "100"], 100),
]


def umgebung(server, cache, ergebnisse, obergrenze, stufe=""):
    """Umgebung für oparl_messung.py gegen den lokalen Testserver; Sperr- und Freigabevariablen werden entfernt."""
    assert server.system_url.startswith("http://127.0.0.1:") and server.body_url.startswith("http://127.0.0.1:")
    env = {k: v for k, v in os.environ.items() if not k.startswith("RATSATLAS_")}
    keine = ",".join(x for x in (env.get("NO_PROXY", ""), "127.0.0.1,localhost") if x)
    env.update({"RATSATLAS_OPARL_SYSTEM": server.system_url, "RATSATLAS_OPARL_BODY": server.body_url,
                "RATSATLAS_ZEITFENSTER": "", "RATSATLAS_ABSTAND": "0", "RATSATLAS_CACHE": str(cache),
                "RATSATLAS_ERGEBNISSE": str(ergebnisse), "RATSATLAS_MAX_ANFRAGEN": str(obergrenze),
                "RATSATLAS_WIEDERHOLUNGEN": "0", "RATSATLAS_MAX_DAUER": "5", "RATSATLAS_STUFE": stufe,
                "RATSATLAS_SPERRE": str(Path(cache).parent / "sperre"),   # Sperrdatei je Probelauf, nicht in ~/.cache
                "NO_PROXY": keine, "no_proxy": keine})
    return env


def messung(server, cache, ergebnisse, kommando, parameter=(), obergrenze=0, stufe="", **zusatz):
    """Führt ein Kommando aus; liefert Rückgabewert, Ausgaben, Anfragen laut Testserver und die Zeile des Laufs."""
    env = umgebung(server, cache, ergebnisse, obergrenze, stufe)
    env.update(zusatz)
    vorher = len(server.anfragen)
    r = subprocess.run([sys.executable, str(HIER / "oparl_messung.py"), kommando, *parameter], env=env,
                       capture_output=True, text=True, timeout=300)
    laeufe = Path(ergebnisse) / "oparl_laeufe.tsv"
    zeile = {}
    if laeufe.exists():
        with laeufe.open(encoding="utf-8") as f:
            zeile = list(csv.DictReader(f, delimiter="\t"))[-1]
    return {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "server": len(server.anfragen) - vorher,
            "lauf": zeile}


def probelauf(ziel):
    ziel = Path(ziel)
    mit_pdf = importlib.util.find_spec("pypdf") is not None
    zeilen, stichprobe = [], None
    with Testserver() as server:
        for nr, (stufe, kommando, parameter, obergrenze) in enumerate(STUFEN, 1):
            if kommando == "pdf-koepfe" and not mit_pdf:
                zeilen.append({"stufe": stufe, "kommando": kommando, "parameter": " ".join(parameter),
                               "obergrenze": obergrenze, "ergebnis": "übersprungen (pypdf fehlt)"})
                continue
            folge = messung(server, ziel / "folge" / "cache", ziel / "folge" / "ergebnisse", kommando, parameter,
                            obergrenze, stufe)
            cache = ziel / "leer" / f"cache_{nr}"
            if kommando == "pdf-koepfe" and stichprobe:   # Rohdaten-Cache leer, nur die Stichprobendatei aus Stufe 5
                cache.mkdir(parents=True, exist_ok=True)
                shutil.copy(stichprobe, cache / STICHPROBE)
            leer = messung(server, cache, ziel / "leer" / "ergebnisse", kommando, parameter, obergrenze, stufe)
            if (cache / STICHPROBE).exists():
                stichprobe = cache / STICHPROBE
            ok = all(m["rc"] == 0 and int(m["lauf"].get("netz") or -1) == m["server"] <= obergrenze
                     for m in (folge, leer))
            zeilen.append({"stufe": stufe, "kommando": kommando, "parameter": " ".join(parameter),
                           "netz_folge": folge["server"], "cache_folge": folge["lauf"].get("cache"),
                           "netz_leer": leer["server"], "obergrenze": obergrenze,
                           "ergebnis": "ok" if ok else f"FEHLER: {folge['stderr'][-300:]} {leer['stderr'][-300:]}"})
    return zeilen


def markdown(zeilen):
    aus = ["| Stufe | Kommando | Parameter | ans Netz (Folge) | aus Cache (Folge) | ans Netz (leerer Cache) "
           "| Obergrenze | Ergebnis |", "|---|---|---|---:|---:|---:|---:|---|"]
    for z in zeilen:
        aus.append(f"| {z['stufe']} | {z['kommando']} | {z['parameter'] or '–'} | {z.get('netz_folge', '–')} | "
                   f"{z.get('cache_folge', '–')} | {z.get('netz_leer', '–')} | {z['obergrenze']} | {z['ergebnis']} |")
    return "\n".join(aus)


def main():
    ap = argparse.ArgumentParser(description="Probelauf der Messstufen gegen den lokalen Testserver")
    ap.add_argument("--ziel", help="Verzeichnis für Cache und Ergebnisse (Vorgabe: temporär)")
    a = ap.parse_args()
    if a.ziel:
        zeilen = probelauf(a.ziel)
    else:
        with tempfile.TemporaryDirectory() as t:
            zeilen = probelauf(t)
    print(markdown(zeilen))
    return 0 if all(z["ergebnis"] in ("ok", "übersprungen (pypdf fehlt)") for z in zeilen) else 1


if __name__ == "__main__":
    sys.exit(main())
