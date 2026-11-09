"""Ortsnamen in Vorlagentiteln: Ausschlussliste an Titeln testen (Phase 1, CLAUDE.md 5.2 und 7.1) – ohne Netz.

Neu in Wuppertal (in ratsatlas-koeln @d609111 ohne Gegenstück). Liest nur, was frühere Schritte angelegt haben, und
ruft nichts ab:
- Titel (`name`) der Stichprobe aus _cache/stichprobe_vorlagen.jsonl (oparl_messung.py stichprobe, Stufe 5; die Datei
  liegt nur im Cache und wird nicht versioniert)
- Namen der Stadtbezirke und Quartiere aus ergebnisse/geodaten_gebiete.tsv (geodaten.py, gemessenes Namensfeld, Stufe G)
- Ausschlussliste explore/ortsnamen_ausschluss.tsv (reguläre Ausdrücke; Platzhalter {name} steht für jeden Namen des
  Verzeichnisses)
Auswahl: --anzahl Titel (Vorgabe 300) gleichmäßig über die Jahre (oparl_messung.auswahl_je_jahr: reihum je Jahr, neuere
Jahre zuerst), innerhalb eines Jahres in zufälliger Reihenfolge mit fester Saat (--saat), damit die Auswahl wiederholbar
ist.
Verzeichnis: alle Namen aus geodaten_gebiete.tsv mit ihrer Ebene (Stadtbezirk, Quartier, statistischer Bezirk);
Doppelnamen mit Bindestrich zusätzlich in ihren Teilen (Langerfeld-Beyenburg → Langerfeld, Beyenburg; CLAUDE.md 5.2).
Teile, die nur eine Himmelsrichtung oder „Mitte“ sind (TEIL_OHNE_ORT, z. B. „West“ aus „Elberfeld-West“), und Teile
unter drei Zeichen werden nicht aufgenommen (Annahme dieses Werkzeugs, keine Angabe der Stadt). Historische
Stadtteilnamen, Straßen und B-Plan-Nummern gehören nicht zum Verzeichnis (offen, Phase 3).
Abgleich je Titel: zuerst die Ausschlussregeln (ihre Spannen sind gesperrt), dann die Namen nach Länge absteigend
(„längster Treffer zuerst“: Oberbarmen vor Barmen, Elberfeld-West vor Elberfeld) mit Wortgrenzen (kein Buchstabe, keine
Ziffer davor oder danach), Groß- und Kleinschreibung wie im Verzeichnis. Ein Name in einer schon von einem längeren
Namen belegten Spanne zählt nicht; liegt er in einer gesperrten Spanne, zählt er als „ausgeschlossen (Regel n)“.
Abgeleitete Formen wie „Barmer“ oder „Elberfelder“ trifft der Abgleich wegen der Wortgrenze nicht.
Ergebnisse (versioniert; ohne Titeltexte, solange die Lizenz der OParl-Daten offen ist, CLAUDE.md 8):
- ergebnisse/ortsnamen_titel.tsv: je ausgewähltem Titel Kennung (OParl-ID), Jahr, erkannte Namen, Ebenen,
  ausgeschlossene Namen mit Regel und die Nummern der Regeln, die im Titel greifen
- ergebnisse/ortsnamen_zaehlung.tsv: Zählungen (Titel mit Treffer, je Ebene, je Name, je Ausschlussregel) und der Anteil
  der Titel mit Gebietsnamen als Schätzung für Stufe B (Untergrenze: ohne Straßen, Adressen und B-Plan-Nummern; ob der
  Ortsbezug zutrifft, prüft erst die manuelle Durchsicht in Phase 3)
Auf stdout zusätzlich das Wort vor jedem Treffer mit Häufigkeit (Kandidaten zur Erweiterung der Ausschlussliste; nicht
gespeichert). Erweiterungen der Ausschlussliste nur mit Beleg in der Spalte `beleg`.
Aufruf: python3 explore/ortsnamen.py [--anzahl 300] [--saat 20200101] [--stichprobe DATEI] [--gebiete DATEI]
        [--ausschluss DATEI] [--ergebnisse VERZ]
Rückgabewerte: 0 fertig, 1 Eingabe fehlt (zuerst stichprobe bzw. geodaten.py) oder Stichprobendatei ohne Titel.
"""
import argparse
import collections
import csv
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oparl_messung  # noqa: E402  (Pfade, auswahl_je_jahr, jahr_der_vorlage; ohne Netz)

HIER = Path(__file__).resolve().parent
AUSSCHLUSS = HIER / "ortsnamen_ausschluss.tsv"
ANZAHL = 300          # CLAUDE.md 7.1: „Ausschlussliste Ortsnamen an 300 Titeln testen“
SAAT = 20200101       # feste Saat der Auswahl (wiederholbar)
EBENEN = {"stadtbezirke": "stadtbezirk", "quartiere": "quartier", "statistische_bezirke": "statistischer bezirk"}
# Teile eines Doppelnamens, die allein keinen Ort bezeichnen (Annahme dieses Werkzeugs)
TEIL_OHNE_ORT = {"Nord", "Süd", "Ost", "West", "Mitte", "Zentrum", "Nordost", "Nordwest", "Südost", "Südwest"}
OHNE_TITEL = "(ohne Titel)"


def lies_tsv(pfad):
    with open(pfad, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def verzeichnis(gebiete):
    """Name → {"ebenen": Menge der Ebenen, "teil_von": Doppelnamen, aus denen der Name als Teil stammt} aus den Zeilen
    von geodaten_gebiete.tsv (datensatz, namensfeld, name, objekte)."""
    verz = collections.defaultdict(lambda: {"ebenen": set(), "teil_von": set()})
    for z in gebiete:
        name = " ".join(str(z.get("name") or "").split())
        if not name or name == "None":
            continue
        verz[name]["ebenen"].add(EBENEN.get(z.get("datensatz"), z.get("datensatz") or "?"))
    for name in [n for n in verz if "-" in n]:
        for teil in (t.strip() for t in name.split("-")):
            if len(teil) >= 3 and teil not in TEIL_OHNE_ORT:
                verz[teil]["teil_von"].add(name)
    return dict(verz)


def ebenen_text(eintrag):
    teile = sorted(eintrag["ebenen"]) + [f"teil von {n}" for n in sorted(eintrag["teil_von"])]
    return ", ".join(teile)


def _namensmuster(name):
    return rf"(?<![^\W_]){re.escape(name)}(?![^\W_])"


def ausschluss_laden(pfad, namen):
    """Regeln der Ausschlussliste mit übersetztem Platzhalter {name} (alle Namen, längste zuerst)."""
    alle = "(?:" + "|".join(re.escape(n) for n in sorted(namen, key=lambda n: (-len(n), n))) + ")" if namen else "(?!)"
    regeln = []
    for z in lies_tsv(pfad):
        z["re"] = re.compile(z["muster"].replace("{name}", alle))
        regeln.append(z)
    return regeln


def finde(titel, namen, regeln, muster=None):
    """Abgleich eines Titels: (Treffer, ausgeschlossen, greifende Regeln, Wörter vor den Treffern). `namen` nach Länge
    absteigend; Treffer und ausgeschlossene Namen ohne Wiederholung in der Reihenfolge des Abgleichs."""
    belegt = [None] * len(titel)
    greifend = []
    for r in regeln:
        for m in r["re"].finditer(titel):
            greifend.append(r["nr"])
            for i in range(m.start(), m.end()):
                belegt[i] = belegt[i] or ("aus", r["nr"])
    treffer, aus, vorworte = [], [], []
    for name in namen:
        rx = (muster or {}).get(name) or re.compile(_namensmuster(name))
        for m in rx.finditer(titel):
            spanne = belegt[m.start():m.end()]
            if "treffer" in spanne:
                continue   # Teil eines längeren Treffers
            sperre = next((b for b in spanne if b), None)
            if sperre:
                if (name, sperre[1]) not in aus:
                    aus.append((name, sperre[1]))
                continue
            for i in range(m.start(), m.end()):
                belegt[i] = "treffer"
            if name not in treffer:
                treffer.append(name)
            vor = re.search(r"([^\W\d_][\w.]*)[^\w]*$", titel[:m.start()])
            vorworte.append(vor.group(1) if vor else "(Titelanfang)")
    return treffer, aus, list(dict.fromkeys(greifend)), vorworte


def auswahl(vorlagen, anzahl=ANZAHL, saat=SAAT):
    """`anzahl` Vorlagen gleichmäßig über die Jahre; innerhalb eines Jahres zufällig mit fester Saat."""
    liste = sorted(vorlagen, key=lambda p: str(p.get("id")))
    random.Random(saat).shuffle(liste)
    return oparl_messung.auswahl_je_jahr(liste, anzahl)


def auswerten(vorlagen, verz, regeln, gesamt=None, saat=SAAT):
    """(Zeilen je Titel, Zählung, Wörter vor Treffern) für die ausgewählten Vorlagen."""
    namen = sorted(verz, key=lambda n: (-len(n), n))
    muster = {n: re.compile(_namensmuster(n)) for n in namen}
    zeilen, je_name, je_ebene, je_regel, vor = [], collections.Counter(), collections.Counter(), collections.Counter(), \
        collections.Counter()
    regel_mit_name = collections.Counter()
    mit, nur_aus, ohne_titel = 0, 0, 0
    for p in vorlagen:
        titel = " ".join(str(p.get("name") or "").split())
        if not titel:
            ohne_titel += 1
        treffer, aus, greifend, vorworte = finde(titel, namen, regeln, muster)
        vor.update(vorworte)
        je_regel.update(greifend)
        regel_mit_name.update({nr for _, nr in aus})
        je_name.update(treffer)
        ebenen = {e for n in treffer for e in (verz[n]["ebenen"] or {"teil eines Doppelnamens"})}
        je_ebene.update(ebenen)
        mit += bool(treffer)
        nur_aus += bool(aus) and not treffer
        zeilen.append({"id": p.get("id"), "jahr": oparl_messung.jahr_der_vorlage(p),
                       "treffer": "; ".join(treffer) if titel else OHNE_TITEL,
                       "ebenen": "; ".join(ebenen_text(verz[n]) for n in treffer),
                       "ausgeschlossen": "; ".join(f"{n} (Regel {nr})" for n, nr in aus),
                       "regeln": ", ".join(greifend)})
    n = len(vorlagen)

    def anteil(x):
        return f"{100 * x / n:.0f} %" if n else "–"
    jahre = collections.Counter(z["jahr"] for z in zeilen)
    teile = sum(1 for e in verz.values() if e["teil_von"] and not e["ebenen"])
    zaehlung = [
        {"kennzahl": "titel ausgewählt", "wert": n, "anmerkung": f"aus {gesamt if gesamt is not None else n} Vorlagen "
                                                                f"der Stichprobe, Saat {saat}"},
        {"kennzahl": "titel je jahr", "wert": len(jahre),
         "anmerkung": "; ".join(f"{j} {c}" for j, c in sorted(jahre.items(), reverse=True))},
        {"kennzahl": "titel ohne name", "wert": ohne_titel, "anmerkung": ""},
        {"kennzahl": "verzeichnis", "wert": len(verz),
         "anmerkung": "; ".join(f"{e} {sum(1 for v in verz.values() if e in v['ebenen'])}"
                                for e in sorted({e for v in verz.values() for e in v["ebenen"]}))
                      + f"; nur als Teil eines Doppelnamens {teile}"},
        {"kennzahl": "titel mit treffer", "wert": mit, "anmerkung": anteil(mit)},
        {"kennzahl": "titel nur mit ausgeschlossenem namen", "wert": nur_aus, "anmerkung": anteil(nur_aus)},
        {"kennzahl": "schätzung stufe b (gebietsnamen)", "wert": f"{mit} von {n}",
         "anmerkung": f"{anteil(mit)}; Untergrenze für Stufe B ohne Straßen, Adressen und B-Plan-Nummern; ob der "
                      "Ortsbezug zutrifft, ist ungeprüft (manuelle Durchsicht in Phase 3)"}]
    zaehlung += [{"kennzahl": f"titel mit treffer: {e}", "wert": c, "anmerkung": anteil(c)}
                 for e, c in sorted(je_ebene.items())]
    zaehlung += [{"kennzahl": f"ausschluss regel {r['nr']} ({r['art']})", "wert": je_regel[r["nr"]],
                  "anmerkung": f"Titel mit Treffer der Regel; davon mit Namen des Verzeichnisses im Ausdruck "
                               f"{regel_mit_name[r['nr']]}"} for r in regeln]
    zaehlung += [{"kennzahl": f"name {k}", "wert": c, "anmerkung": ebenen_text(verz[k])}
                 for k, c in sorted(je_name.items(), key=lambda x: (-x[1], x[0]))]
    return zeilen, zaehlung, vor


def schreibe(pfad, zeilen, spalten):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with pfad.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, spalten, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for z in zeilen:
            w.writerow({k: str(z.get(k, "")).replace("\t", " ").replace("\n", " ") for k in spalten})
    print(f"→ {pfad} ({len(zeilen)} Zeilen)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ortsnamen in Vorlagentiteln, Ausschlussliste testen (ohne Netz)")
    ap.add_argument("--anzahl", type=int, default=ANZAHL)
    ap.add_argument("--saat", type=int, default=SAAT)
    ap.add_argument("--stichprobe", default=str(oparl_messung.STICHPROBE))
    ap.add_argument("--gebiete", default=str(oparl_messung.ERG / "geodaten_gebiete.tsv"))
    ap.add_argument("--ausschluss", default=str(AUSSCHLUSS))
    ap.add_argument("--ergebnisse", default=str(oparl_messung.ERG))
    a = ap.parse_args(argv)
    stichprobe, gebiete, erg = Path(a.stichprobe), Path(a.gebiete), Path(a.ergebnisse)
    if not stichprobe.exists():
        print(f"Stichprobendatei fehlt ({stichprobe}): zuerst oparl_messung.py stichprobe (Stufe 5).", file=sys.stderr)
        return 1
    if not gebiete.exists():
        print(f"Gebietsnamen fehlen ({gebiete}): zuerst geodaten.py laden (Stufe G) bzw. ableiten.", file=sys.stderr)
        return 1
    with stichprobe.open(encoding="utf-8") as f:
        vorlagen = [json.loads(z) for z in f if z.strip()]
    if vorlagen and not any("name" in p for p in vorlagen):
        print(f"Stichprobendatei ohne Titel ({stichprobe}; vor der Ergänzung um `name` erzeugt). Neue Stichprobe nur "
              "nach Freigabe (explore/STUFEN.md, Stufe 5).", file=sys.stderr)
        return 1
    verz = verzeichnis(lies_tsv(gebiete))
    if not verz:
        print(f"Keine Gebietsnamen in {gebiete}.", file=sys.stderr)
        return 1
    regeln = ausschluss_laden(a.ausschluss, list(verz))
    gewaehlt = auswahl(vorlagen, a.anzahl, a.saat)
    zeilen, zaehlung, vor = auswerten(gewaehlt, verz, regeln, len(vorlagen), a.saat)
    schreibe(erg / "ortsnamen_titel.tsv", zeilen, ["id", "jahr", "treffer", "ebenen", "ausgeschlossen", "regeln"])
    schreibe(erg / "ortsnamen_zaehlung.tsv", zaehlung, ["kennzahl", "wert", "anmerkung"])
    print("Wort vor einem Treffer (Kandidaten für die Ausschlussliste, nicht gespeichert): "
          + ("; ".join(f"{w} {c}" for w, c in vor.most_common(30)) or "–"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
