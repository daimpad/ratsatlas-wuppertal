"""Auswertung der Messstufen (explore/STUFEN.md) als Markdown auf stdout – ohne Netzzugriff.

Abgeleitet aus ratsatlas-koeln @d609111 (explore/auswertung.py). Abweichungen von Köln: Kennwerte zu `umfang`
(Gesamtzahl, Grenze 2020 nach `created`, Sortierung nach `created` maßgeblich und nach `date` informativ, Abstand
date − created, Ende von links.next) mit Regel Stufe 3 (regel_umfang), Präfixe der Organisationen, Beratungsrollen, Zerlegung der
Vorlagenart nach explore/paperType_regeln.tsv (regeln_laden, zerlege, papertyp_abdeckung) und die Regel für die
Stichprobe (regel_stichprobe) statt der Kölner Regel zum Jahresfilter; Gesamtzahl von meeting und person (aus
`pagination` oder `umfang --liste`, sonst ausdrücklich „offen“), Zeitraum und Sortierung der Sitzungsliste, Bezeichnungen
in den PDF-Köpfen; für Stufe 6 Erkennungs- (Kennung nach Regel gefunden, Annahme) und Abgleichquote mit
Wilson-Intervall, Verteilungen, Messwerte der Dateien, manuelle Kontrolle der Zuordnung, Hochrechnung der Federführung
nach Jahr gewichtet (Schätzung), neue Dokumente im Monat (Schätzung) und Regel Stufe 6 (pdf_abschnitt).

Liest das Abrufprotokoll _cache/abrufe.tsv und die TSVs in ergebnisse/ (oparl_laeufe.tsv, oparl_listen.tsv,
oparl_test.tsv, oparl_kennzahlen.tsv, oparl_umfang.tsv, oparl_umfang_meeting.tsv, oparl_umfang_person.tsv,
oparl_organisationstypen.tsv, oparl_stichprobe_*.tsv, oparl_papertypen.tsv, oparl_beratungsrollen.tsv,
oparl_referenzschema.tsv, oparl_top_ergebnisse.tsv, oparl_sitzungen.tsv, pdf_koepfe.tsv, pdf_koepfe_grundlage.tsv).
Fehlende Dateien werden übersprungen.
Je Stufe: Anfragen (Netz, Cache), Statuscodes, mittlere und höchste Antwortzeit, Bytes, Ergebnis; dazu Kennwerte
(Seitengröße, Form von links.next, Parametertests, Umfang, Feldabdeckung, Regel Stufe 5) und Auffälligkeiten
nach den Abbruchkriterien in STUFEN.md. Fehlt das Abrufprotokoll für einen Lauf (z. B. andere Arbeitsumgebung), gelten
Statuscodes und Antwortzeiten als „nicht prüfbar (Protokoll fehlt)“. Protokollzeilen gehören nur dann zu einem Lauf,
wenn sie im Bereich protokoll_von–protokoll_bis liegen und ihre Zeit (mit Zone) zwischen Start und Ende des Laufs
liegt; sonst „nicht prüfbar (Protokollzeilen passen nicht zum Lauf)“.
Ablehnungen durch den Proxy der Arbeitsumgebung (Status `proxy <Code>`: CONNECT-Antwort 403, 405, 407 oder HTTP 407)
stehen getrennt: Sie haben die Stadt nicht erreicht, zählen nicht zu den Antwortzeiten und gelten nicht als mögliche
Sperre. Andere CONNECT-Antworten (Status `tunnel <Code>`, z. B. 502/504: der Proxy erreicht die Stadt nicht, oder
429/503) gelten wie Verbindungsabbrüche als mögliche Sperre, ebenso 403, 429, 5xx und Status ohne Code (Name der
Ausnahme, z. B. TimeoutError, IncompleteRead bei einer abgeschnittenen Antwort, Gesamtfrist bei einer Tropf-Antwort
oder `unterbrochen`: Lauf während dieser Anfrage unterbrochen). HTTP 401 steht als „abgelehnt oder Sperre?“. Eine
gescheiterte Zertifikatsprüfung (Status `tls`) ist vermutlich eine Einstellung der Arbeitsumgebung (Zertifikat der
Gegenseite oder Sperrseite nicht ausgeschlossen); sie zählt wie eine Ablehnung durch den Proxy nicht zu den
Antwortzeiten. Zum Zeitfilter: „nicht unterscheidbar“ heißt, die erste Seite zeigt nicht, ob der Server die Grenze
anwendet (bei modified_since, wenn keine Vorlage fehlt, die laut Cache unter der Grenze lag).
Fehlende Gesamtzahlen in `pagination` stehen als „fehlt“.
Die Regel Stufe 5 gilt nur als erfüllt, wenn der letzte `stichprobe`-Lauf in oparl_laeufe.tsv „ok“ ist.
Aufruf: python3 explore/auswertung.py [--cache VERZ] [--ergebnisse VERZ] [--stufe S]
"""
import argparse
import collections
import csv
import datetime as dt
import math
import os
import re
import statistics
import sys
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

HIER = Path(__file__).resolve().parent
GRENZE_DAUER = 5.0     # Sekunden, Abbruchkriterium aus STUFEN.md
NICHT_PRUEFBAR = "nicht prüfbar (Protokoll fehlt)"
NICHT_ZUGEORDNET = "nicht prüfbar (Protokollzeilen passen nicht zum Lauf)"
PROXY_HINWEIS = ("Ablehnung durch den Proxy der Arbeitsumgebung, die Stadt wurde nicht erreicht, keine Sperre: nicht "
                 "wiederholen, berichten; Host im Netz der Arbeitsumgebung erlauben")
TLS_HINWEIS = ("Zertifikatsprüfung fehlgeschlagen: vermutlich Einstellung der Arbeitsumgebung (CA des Proxys); "
               "Zertifikat der Gegenseite oder Sperrseite nicht ausgeschlossen – berichten, nicht wiederholen")
UNTERBROCHEN_HINWEIS = ("Lauf während dieser Anfrage unterbrochen, etwa nach einem Zeitlimit des aufrufenden Werkzeugs: "
                        "mögliche Sperre, stoppen")
FILTER_HINWEIS = ("„nicht unterscheidbar“: Die erste Seite zeigt nicht, ob der Server diese Grenze anwendet (bei "
                  "modified_since, wenn keine Vorlage fehlt, die laut Cache unter der Grenze lag, etwa weil alle seither "
                  "geändert wurden).")
# Gesamtzahl einer Liste ohne pagination.totalElements und ohne Messung über `umfang --liste`
GESAMT_OFFEN = "Gesamtzahl offen"
# Regeltabelle zur Zerlegung von paperType (Art, Einreichende, Ebene); Startregeln nur aus CLAUDE.md 3.1
REGELN = HIER / "paperType_regeln.tsv"
OFFEN = "offen"       # nicht aus dem paperType ableitbar
KEINE = "–"           # paperType nennt keine Einreichenden (Regel mit „–“)
NICHT_ZERLEGT = "nicht zerlegt (keine Regel)"
MINDESTENS = 500      # Vorlagen 2020–2026 in der Stichprobe (CLAUDE.md 7.1)
# Stufe 6 (Annahmen für „Stufe 6 erfüllt“): mindestens 50 gelesene PDFs (Wilson-95-%-Intervall dann höchstens etwa
# ±14 Prozentpunkte breit) und höchstens 20 % der angefragten Dateien mit Fehler (HTTP 404/410, zu groß, kein PDF,
# verschlüsselt, defekt)
MINDESTENS_PDF = 50
HOECHSTENS_FEHLER = 0.2
Z95 = 1.96
# Treffer in pdf_koepfe.tsv, bei denen die PDF-Datei gelesen wurde (wie oparl_messung.GELESEN)
GELESEN = ("kennung", "nur außerhalb des Kopfes", "nein", "kein_text")


def lies(datei):
    if not Path(datei).exists():
        return []
    with open(datei, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def zahl(x, standard=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return standard


def ist_proxy(zeile):
    """Protokollzeile einer Ablehnung durch den Proxy der Arbeitsumgebung (explore/abruf.py, Status `proxy <Code>`)."""
    return str(zeile.get("status") or "").startswith("proxy")


def ist_tls(zeile):
    """Protokollzeile einer gescheiterten Zertifikatsprüfung (explore/abruf.py, Status `tls`)."""
    return str(zeile.get("status") or "") == "tls"


def angabe(wert):
    """Kennwert für die Anzeige: fehlend oder null („fehlt“, in Ergebnissen vor dem 08.11.2026 „None“) → „fehlt“."""
    return "fehlt" if wert in ("None", "fehlt") else (wert or "–")


def statistik(zeilen):
    """Kennzahlen über Protokollzeilen: Netz, Cache, Statuscodes, Antwortzeit Ø und max, Bytes. Ablehnungen durch den
    Proxy zählen zu Netz (Versuche, wie bei der Obergrenze) und werden als `proxy` getrennt gezählt; die Antwortzeiten
    gelten nur für Antworten des Servers."""
    netz = [z for z in zeilen if z.get("quelle") == "netz"]
    dauer = [zahl(z.get("dauer_s")) for z in netz if not (ist_proxy(z) or ist_tls(z))]
    status = collections.Counter(z.get("status") for z in netz)
    return {"netz": len(netz), "cache": sum(1 for z in zeilen if z.get("quelle") == "cache"),
            "proxy": sum(1 for z in netz if ist_proxy(z)),
            "status": ", ".join(f"{k}×{v}" for k, v in sorted(status.items())) or "–",
            "status_roh": status, "mittel": sum(dauer) / len(dauer) if dauer else None,
            "max": max(dauer) if dauer else None, "bytes": sum(int(zahl(z.get("bytes"))) for z in netz)}


def zeitpunkt(wert):
    """Zeitpunkt mit Zone; ohne Zone oder unlesbar → None (nicht vergleichbar)."""
    try:
        t = dt.datetime.fromisoformat(str(wert or ""))
    except ValueError:
        return None
    return t if t.tzinfo else None


def tag_ortszeit(wert):
    """Tag eines Zeitpunkts in Ortszeit Europe/Berlin (wie oparl_messung._erstellt; ohne Zone gilt Ortszeit), für die
    Anzeige von created; unlesbar oder nicht darstellbar → die ersten zehn Zeichen wie geliefert."""
    try:
        t = dt.datetime.fromisoformat(str(wert or "").replace("Z", "+00:00"))
        berlin = ZoneInfo("Europe/Berlin")
        return (t if t.tzinfo else t.replace(tzinfo=berlin)).astimezone(berlin).date().isoformat()
    except (ValueError, OverflowError):
        return str(wert or "")[:10]


def zeilen_des_laufs(lauf, protokoll):
    """(Protokollzeilen des Laufs, Grund). Zugeordnet wird nur, wenn der Bereich protokoll_von–protokoll_bis im
    Protokoll liegt und jede Zeile eine Zeit mit Zone zwischen Start und Ende des Laufs hat; sonst (None, Grund)."""
    if not protokoll:
        return None, NICHT_PRUEFBAR
    von, bis = int(zahl(lauf.get("protokoll_von"), -1)), int(zahl(lauf.get("protokoll_bis"), -1))
    start, ende = zeitpunkt(lauf.get("start")), zeitpunkt(lauf.get("ende"))
    if not (0 <= von <= bis <= len(protokoll)) or start is None or ende is None:
        return None, NICHT_ZUGEORDNET
    zz = protokoll[von:bis]
    for z in zz:
        t = zeitpunkt(z.get("zeit"))
        if t is None or not start <= t <= ende:
            return None, NICHT_ZUGEORDNET
    return zz, ""


def anteil(teil, ganz):
    return f"{100 * zahl(teil) / zahl(ganz):.0f} %" if zahl(ganz) else "–"


def sekunden(x):
    return "–" if x is None else f"{x:.2f}"


def form_next(nxt, liste=None):
    """Form von links.next: Pfad gleich der Liste?, Parameter, URL-Kodierung."""
    if not nxt:
        return "fehlt"
    t = urlsplit(nxt)
    namen = [x.partition("=")[0] for x in t.query.split("&") if x]
    teile = [f"Parameter {', '.join(namen) or '–'}", f"URL-kodiert {'ja' if '%' in t.query else 'nein'}"]
    if "+" in t.query:
        teile.append("„+“ unverändert")
    if liste:
        l = urlsplit(liste)
        teile.insert(0, "gleicher Pfad" if (l.netloc, l.path) == (t.netloc, t.path) else f"anderer Pfad {t.path}")
    return "; ".join(teile)


def lokal(url):
    t = urlsplit(url)
    return t.scheme == "http" and t.hostname in ("127.0.0.1", "localhost")


def tabelle(kopf, zeilen):
    aus = ["| " + " | ".join(kopf) + " |", "|" + "---|" * len(kopf)]
    aus += ["| " + " | ".join(str(x).replace("|", "/") for x in z) + " |" for z in zeilen]
    return aus


def status_hinweise(zeilen, kommando):
    """Antworten ans Netz außer 200, gezählt je (Status, Hinweis). Der Hinweis „erwartet“ gilt nur für eine 404 auf
    eine URL mit URL-Kodierung (%) im Kommando kennzahlen; Weiterleitungen nennen ihr Ziel."""
    aus = collections.Counter()
    for z in zeilen:
        code = z.get("status") or ""
        if z.get("quelle") != "netz" or code == "200":
            continue
        if code == "404" and kommando == "kennzahlen" and "%" in (z.get("url") or ""):
            hinweis = " (erwartet: Test mit URL-kodiertem Parameter)"
        elif code.startswith("3"):
            hinweis = f" (Weiterleitung nach {z.get('ziel') or '(ohne Ziel)'}, nicht verfolgt: stoppen)"
        elif ist_proxy(z):
            hinweis = f" ({PROXY_HINWEIS})"
        elif ist_tls(z):
            hinweis = f" ({TLS_HINWEIS})"
        elif code == "unterbrochen":
            hinweis = f" ({UNTERBROCHEN_HINWEIS})"
        elif code == "401":
            hinweis = " (abgelehnt oder Sperre?)"
        elif code.startswith("tunnel"):   # CONNECT-Antwort außer 403/405/407 (explore/abruf.py)
            grund = ("Begrenzung oder Überlastung" if code.split()[-1] in ("429", "503")
                     else "der Proxy erreicht den Server nicht")
            hinweis = f" (beim Verbindungsaufbau über den Proxy: {grund}; mögliche Sperre: stoppen)"
        elif not code.isdigit() or code in ("403", "429") or code.startswith("5"):
            hinweis = " (mögliche Sperre: stoppen)"
        else:
            hinweis = ""
        aus[(code, hinweis)] += 1
    return aus


def laeufe_abschnitt(laeufe, protokoll, stufe=None):
    aus, zugeordnet, auffaellig, proxy = [], set(), [], []
    je_lauf, je_stufe = [], collections.OrderedDict()
    for l in laeufe:
        zz, grund = zeilen_des_laufs(l, protokoll)
        if zz is not None:
            von = int(zahl(l.get("protokoll_von")))
            zugeordnet.update(range(von, von + len(zz)))
        if stufe and l.get("stufe") != stufe:
            continue
        if zz is not None:
            s = statistik(zz)
        else:   # Protokoll fehlt oder passt nicht (z. B. andere Arbeitsumgebung): nur die Zähler aus dem Lauf
            s = {"netz": l.get("netz"), "cache": l.get("cache"), "proxy": 0, "status": grund,
                 "status_roh": {}, "mittel": None, "max": None, "bytes": "–"}
        je_lauf.append((l, s))
        g = je_stufe.setdefault(l.get("stufe") or "–", {"kommandos": [], "zeilen": [], "laeufe": [], "ergebnisse": [],
                                                        "gruende": []})
        g["kommandos"].append(l.get("kommando"))
        g["laeufe"].append(l)
        g["ergebnisse"].append(l.get("ergebnis"))
        if zz is not None:
            g["zeilen"] += zz
        else:
            g["gruende"].append(grund)
        if s["proxy"]:
            hosts = ", ".join(sorted({urlsplit(z.get("url") or "").hostname or "?" for z in zz if ist_proxy(z)}))
            proxy.append(f"Lauf {l['lauf']} ({l['kommando']}): {s['proxy']} Anfrage(n) vom Proxy abgelehnt "
                         f"(Host {hosts})")
        elif l.get("ergebnis") == "abbruch (proxy)":
            proxy.append(f"Lauf {l['lauf']} ({l['kommando']}): Abbruch durch den Proxy; Protokoll {grund}")
        # Auffälligkeiten nach den Abbruchkriterien
        if l.get("ergebnis") != "ok":
            auffaellig.append(f"Lauf {l['lauf']} ({l['kommando']}): {l.get('ergebnis')} – {l.get('meldung', '')[:200]}")
        if zz is None:
            if str(l.get("netz")) != "0":
                auffaellig.append(f"Lauf {l['lauf']} ({l['kommando']}): Statuscodes und Antwortzeiten {grund}")
            continue
        for (code, hinweis), n in sorted(status_hinweise(zz, l.get("kommando")).items()):
            auffaellig.append(f"Lauf {l['lauf']} ({l['kommando']}): Status {code} × {n}{hinweis}")
        if s["max"] is not None and s["max"] > GRENZE_DAUER:
            auffaellig.append(f"Lauf {l['lauf']} ({l['kommando']}): Antwortzeit bis {s['max']:.1f} s "
                              f"(Grenze {GRENZE_DAUER:g} s)")

    aus.append("## Je Stufe\n")
    zeilen = []
    for st, g in je_stufe.items():
        if not g["gruende"]:
            s = statistik(g["zeilen"])
        else:   # mindestens ein Lauf ohne zugeordnete Protokollzeilen: keine Teilstatistik, nur die Zähler der Läufe
            s = {"netz": sum(int(zahl(l.get("netz"))) for l in g["laeufe"]),
                 "cache": sum(int(zahl(l.get("cache"))) for l in g["laeufe"]),
                 "status": "; ".join(dict.fromkeys(g["gruende"])), "mittel": None, "max": None, "bytes": "–"}
        ergebnis = "ok" if all(e == "ok" for e in g["ergebnisse"]) else "; ".join(sorted(set(g["ergebnisse"])))
        zeilen.append([st, ", ".join(dict.fromkeys(g["kommandos"])), s["netz"], s["cache"], s["status"],
                       sekunden(s["mittel"]), sekunden(s["max"]), s["bytes"], ergebnis])
    aus += tabelle(["Stufe", "Kommandos", "Netz", "Cache", "Status", "Ø s", "max s", "Bytes", "Ergebnis"], zeilen)

    aus.append("\n## Läufe\n")
    zeilen = [[l["lauf"], l.get("stufe") or "–", l["kommando"], l.get("parameter") or "–", l.get("start", ""),
               f"{l.get('dauer_s', '')} s", s["netz"], s["cache"], l.get("obergrenze") or "–", s["status"],
               sekunden(s["mittel"]), sekunden(s["max"]), s["bytes"], l.get("ergebnis")] for l, s in je_lauf]
    aus += tabelle(["Lauf", "Stufe", "Kommando", "Parameter", "Start", "Dauer", "Netz", "Cache", "Obergrenze",
                    "Status", "Ø s", "max s", "Bytes", "Ergebnis"], zeilen)

    rest = [z for i, z in enumerate(protokoll) if i not in zugeordnet]
    if rest and not stufe:
        hosts = collections.Counter(urlsplit(z.get("url", "")).hostname for z in rest)
        aus.append(f"\nWeitere Zeilen im Abrufprotokoll ohne Lauf (z. B. Zeit außerhalb eines Laufs): "
                   f"{len(rest)} ({', '.join(f'{h} × {n}' for h, n in hosts.most_common())})")
    if proxy:
        aus.append("\n## Ablehnungen durch den Proxy der Arbeitsumgebung\n")
        aus.append("Diese Anfragen haben die Stadt nicht erreicht; sie sind keine Antwort der Stadt und kein Hinweis auf "
                   "eine Sperre. Nicht wiederholen, sondern berichten: Der genannte Host muss im Netz der "
                   "Arbeitsumgebung erlaubt sein (für die OParl-API oparl.wuppertal.de, STUFEN.md, Stufe 1).\n")
        aus += [f"- {p}" for p in proxy]
    aus.append("\n## Auffälligkeiten\n")
    aus += [f"- {a}" for a in auffaellig] or ["- keine (Ergebnis ok, kein 429/5xx, keine Weiterleitung, keine "
                                              f"Antwort über {GRENZE_DAUER:g} s, kein Verbindungsabbruch)"]
    return aus


def regeln_laden(pfad=None):
    """Regeln aus explore/paperType_regeln.tsv in ihrer Reihenfolge (die erste passende gilt): Nummer, Muster (regulärer
    Ausdruck, ganzer paperType), Vorlagen für Art, Einreichende, Ebene und Zusatz (Literal oder {Gruppe}), Beleg."""
    with open(REGELN if pfad is None else pfad, encoding="utf-8", newline="") as f:
        regeln = list(csv.DictReader(f, delimiter="\t"))
    for r in regeln:
        r["re"] = re.compile(r["muster"])
    return regeln


def zerlege(papertype, regeln):
    """Zerlegung eines paperType nach der ersten passenden Regel: {regel, art, einreichende, ebene, zusatz, status}.
    Leere Angaben heißen „offen“, „–“ heißt: der paperType nennt keine Einreichenden. Ein Zusatz (z. B. „AU“) steht
    wörtlich, seine Bedeutung gilt als offen. Ohne passende Regel: status „nicht zerlegt (keine Regel)“."""
    text = " ".join(str(papertype or "").split())
    for r in regeln:
        m = r["re"].fullmatch(text)
        if not m:
            continue
        gruppen = {k: v or "" for k, v in m.groupdict().items()}
        werte = {k: (r.get(k) or "").format_map(collections.defaultdict(str, gruppen)).strip()
                 for k in ("art", "einreichende", "ebene", "zusatz")}
        for k in ("art", "einreichende", "ebene"):
            werte[k] = werte[k] or OFFEN
        status = "zerlegt" + (f" (Kürzel „{werte['zusatz']}“ offen)" if werte["zusatz"] else "")
        return {"regel": r["nr"], **werte, "status": status}
    return {"regel": "", "art": OFFEN, "einreichende": OFFEN, "ebene": OFFEN, "zusatz": "", "status": NICHT_ZERLEGT}


def ohne_einreichende(papertype, regeln):
    """Nennt der paperType laut Regeltabelle ausdrücklich keine Einreichenden (Regel mit „–“, z. B. „Beschlussvorlage“)?
    Dient pdf-koepfe als Auswahl der Verwaltungsvorlagen (Annahme, an der Liste der paperType zu prüfen)."""
    return zerlege(papertype, regeln)["einreichende"] == KEINE


def papertyp_abdeckung(zaehlung, regeln):
    """Zerlegung je paperType (zaehlung: Paare (paperType, anzahl)) und Abdeckungsquoten, gewichtet mit der Zahl der
    Vorlagen: zerlegt (eine Regel passt), Art, Einreichende (einschließlich „–“) und Ebene bestimmt, Kürzel offen.
    Dazu getrennt für politische Vorlagen (zerlegt, paperType nennt laut Regel Einreichende, also nicht „–“):
    „einreichende_genannt“ = Einreichende als Name bestimmt (weder „–“ noch offen), bezogen auf „politisch“.
    Liefert (Zeilen, Quoten); Quoten als (Anzahl, Gesamt)."""
    zeilen, q = [], collections.Counter()
    for papertype, anzahl in zaehlung:
        n = int(zahl(anzahl))
        z = zerlege(papertype, regeln)
        zeilen.append({"paperType": papertype, "anzahl": n, **z})
        q["gesamt"] += n
        q["zerlegt"] += n if z["regel"] else 0
        for k in ("art", "einreichende", "ebene"):
            q[k] += n if z[k] != OFFEN else 0
        q["kuerzel_offen"] += n if z["zusatz"] else 0
        if z["regel"] and z["einreichende"] != KEINE:
            q["politisch"] += n
            q["einreichende_genannt"] += n if z["einreichende"] != OFFEN else 0
    quoten = {k: (q[k], q["gesamt"]) for k in ("zerlegt", "art", "einreichende", "ebene", "kuerzel_offen")}
    quoten["einreichende_genannt"] = (q["einreichende_genannt"], q["politisch"])
    return zeilen, quoten


def regel_stichprobe(bedeckung, laeufe):
    """Urteil zur Regel aus STUFEN.md (Stufe 5) oder None ohne Zählungen. „erfüllt“ nur, wenn mindestens 500 Vorlagen
    2020–2026 vorliegen, jedes Jahr vertreten ist, keine doppelten Kennungen und keine Seite außerhalb der Sortierung
    nach created auftreten (Stufe 1: Liste nach created, nicht nach date sortiert, CLAUDE.md 9, 10.11.2026; die Zeile
    zur Sortierung nach date ist nur informativ) und der letzte stichprobe-Lauf in oparl_laeufe.tsv „ok“ ist."""
    werte = {z["feld"]: int(zahl(z["vorhanden"])) for z in bedeckung}
    menge = next((v for f, v in werte.items() if f.startswith("Vorlagen ") and " bis " in f), None)
    if menge is None:
        return None
    gruende = ([f"nur {menge} Vorlagen (mindestens {MINDESTENS})"] if menge < MINDESTENS else []) + [
        f"{f} {werte[f]}" for f in ("doppelte Kennungen", "Seiten nicht absteigend nach created") if werte.get(f)] + [
        f"{f}: {v}" for f, v in werte.items() if f.startswith("Jahre ") and f.endswith(" ohne Vorlage") and v]
    if gruende:
        return "nicht erfüllt (" + "; ".join(gruende) + ") – nicht weiter, berichten"
    letzte = [l for l in laeufe if l.get("kommando") == "stichprobe"]
    if not letzte:
        return "nicht prüfbar (kein stichprobe-Lauf in oparl_laeufe.tsv) – nicht weiter, berichten"
    if letzte[-1].get("ergebnis") != "ok":
        return (f"nicht prüfbar (Lauf abgebrochen) – letzter stichprobe-Lauf {letzte[-1].get('lauf')}: "
                f"{letzte[-1].get('ergebnis')}; nicht weiter, berichten")
    return "erfüllt"


def regel_umfang(umf, laeufe):
    """Urteil zur Regel aus STUFEN.md (Stufe 3) oder None ohne Zeilen aus oparl_umfang.tsv. „erfüllt“ nur, wenn die
    Grenzseite G (nach created) eine Zahl ist, die Sortierung nach created „ja“ lautet und der letzte umfang-Lauf (Liste
    paper) in oparl_laeufe.tsv „ok“ ist. Die Sortierung nach date ist nur informativ."""
    werte = {(z.get("objekt"), z.get("feld")): z.get("wert") or "" for z in umf}
    if not werte:
        return None
    gruende = []
    if not str(werte.get(("grenze", "grenzseite"), "")).isdigit():
        gruende.append(f"Grenzseite {werte.get(('grenze', 'grenzseite')) or 'fehlt'}")
    sortierung = werte.get(("sortierung", "created_absteigend"), "")
    if not sortierung.startswith("ja"):
        gruende.append(f"Sortierung nach created {sortierung or 'fehlt'}")
    if gruende:
        return "nicht erfüllt (" + "; ".join(gruende) + ") – nicht weiter, berichten"
    letzte = [l for l in laeufe if l.get("kommando") == "umfang" and "--liste" not in (l.get("parameter") or "")]
    if not letzte:
        return "nicht prüfbar (kein umfang-Lauf in oparl_laeufe.tsv) – nicht weiter, berichten"
    if letzte[-1].get("ergebnis") != "ok":
        return (f"nicht prüfbar (Lauf abgebrochen) – letzter umfang-Lauf {letzte[-1].get('lauf')}: "
                f"{letzte[-1].get('ergebnis')}; nicht weiter, berichten")
    return "erfüllt"


def _paar(sitz, zeit):
    """(TOPs mit result, TOPs) für vergangene bzw. künftige Sitzungen aus oparl_sitzungen.tsv."""
    return int(zahl(sitz.get(f"TOPs mit result ({zeit})"))), int(zahl(sitz.get(f"TOPs ({zeit})")))


def quote(paar):
    teil, ganz = paar
    return f"{teil} von {ganz} ({anteil(teil, ganz)})"


def gesamtzahlen(erg, werte):
    """Gesamtzahl von meeting und person: aus pagination.totalElements (kennzahlen), sonst aus `umfang --liste`
    (oparl_umfang_<liste>.tsv), sonst ausdrücklich „Gesamtzahl offen“."""
    aus = []
    for liste in ("meeting", "person"):
        w = werte.get(liste) or {}
        if not w:
            continue
        gesamt = angabe(w.get("pagination.totalElements"))
        if gesamt not in ("fehlt", "–"):
            aus.append(f"- {liste}: Gesamtzahl {gesamt} (pagination.totalElements)")
            continue
        umf = {z["feld"]: z["wert"] for z in lies(erg / f"oparl_umfang_{liste}.tsv")}
        if umf.get(f"{liste}_gesamt"):
            aus.append(f"- {liste}: Gesamtzahl {umf[f'{liste}_gesamt']} (umfang --liste {liste})")
        elif umf.get("letzte_seite"):
            aus.append(f"- {liste}: {GESAMT_OFFEN} (umfang --liste {liste}: letzte Seite {umf['letzte_seite']})")
        else:
            aus.append(f"- {liste}: {GESAMT_OFFEN} (pagination.totalElements fehlt; umfang --liste {liste} nicht "
                       "ausgeführt)")
    return ["\nGesamtzahl der Sitzungen und Personen:\n"] + aus if aus else []


def kennwerte(erg, laeufe=None):
    aus = ["\n## Kennwerte\n"]
    laeufe = lies(erg / "oparl_laeufe.tsv") if laeufe is None else laeufe
    test, kz = lies(erg / "oparl_test.tsv"), lies(erg / "oparl_kennzahlen.tsv")
    werte = collections.defaultdict(dict)
    for z in test + kz:            # Kennzahlen überschreiben den Test (neuerer Stand)
        werte[z["objekt"]][z["feld"]] = z["wert"]
    umf = lies(erg / "oparl_umfang.tsv")
    if werte or umf:
        quellen = [werte.get(o, {}).get("id") or werte.get(o, {}).get("url") or "" for o in ("system", "body", "paper")]
        quellen += [z["wert"] for z in umf if z["feld"] == "url"]
        if any(lokal(u) for u in quellen):
            aus.append("**Hinweis: Ergebnisse vom lokalen Testserver mit erfundenen Daten (Probelauf), nicht aus "
                       "Wuppertal.**\n")
    if werte:
        for objekt, felder in (("system", ("oparlVersion", "vendor", "product", "license")),
                               ("body", ("name", "license", "legislativeTerm", "location", "modified"))):
            if objekt in werte:
                aus.append(f"- {objekt}: " + "; ".join(f"{f} = {werte[objekt].get(f) or '(leer)'}"
                                                         for f in felder if f in werte[objekt]))
        zeilen = []
        for liste in ("paper", "meeting", "organization", "person"):
            w = werte.get(liste)
            if not w or "pagination.elementsPerPage" not in w:
                continue
            zeilen.append([liste, angabe(w.get("pagination.totalElements")),
                           angabe(w.get("pagination.elementsPerPage")), angabe(w.get("pagination.totalPages")),
                           w.get("objekte_erste_seite") or "–",
                           w.get("links.schluessel") or "–", form_next(w.get("links.next"), w.get("url"))])
        if zeilen:
            aus.append("")
            aus += tabelle(["Liste", "totalElements", "elementsPerPage", "totalPages", "Objekte 1. Seite",
                            "links", "links.next"], zeilen)
            aus += gesamtzahlen(erg, werte)
        p = werte.get("paper", {})
        if p.get("felder_erstes_objekt"):
            aus.append(f"\nFelder des ersten Objekts der Vorlagenliste: {p['felder_erstes_objekt']}")
        if p.get("id_schema"):
            aus.append(f"\nSchema der Kennungen (erste Seite): {p['id_schema']}; links.next: "
                       f"{p.get('links.next_schema', '–')}; date absteigend (erste Seite): "
                       f"{p.get('date_absteigend_erste_seite', '–')}")
        tests = [(f, w) for f, w in p.items() if f.startswith("test ")]
        if tests:
            aus.append("\nParametertests (Vorlagen):\n")
            aus += tabelle(["Test", "Antwort"], [[f[5:], w + (" – abgelehnt oder Sperre?" if "HTTP 401" in w else "")]
                                                 for f, w in tests])
            if p.get("grenze modified_since"):
                aus.append(f"\nGrenze modified_since: {p['grenze modified_since']}")
            if any("nicht unterscheidbar" in w for _, w in tests):
                aus.append(f"\n{FILTER_HINWEIS}")
        if "abbruch" in werte.get("lauf", {}):
            aus.append(f"\nTest/Kennzahlen abgebrochen: {werte['lauf']['abbruch']}")

    if umf:
        aus.append("\nUmfang der Vorlagenliste (oparl_umfang.tsv):\n")
        aus += tabelle(["Objekt", "Feld", "Wert"], [[z["objekt"], z["feld"], z["wert"]] for z in umf
                                                     if z["feld"] != "url"])
        urteil = regel_umfang(umf, laeufe)
        if urteil:   # Regel in STUFEN.md, Stufe 3
            aus.append(f"\nRegel Stufe 3 (Grenzseite G als Zahl, Sortierung nach created ja, Lauf ok): {urteil}")

    listen = lies(erg / "oparl_listen.tsv")
    if listen:
        aus.append("\nDurchlaufene Listen (oparl_listen.tsv):\n")
        je = collections.OrderedDict()
        for z in listen:
            je.setdefault(z["lauf"], []).append(z)
        zeilen = []
        for lauf, zz in je.items():
            enden = collections.Counter(z["ende"] for z in zz)
            zeilen.append([lauf, ", ".join(dict.fromkeys(z["liste"].split(" ")[0] for z in zz)), len(zz),
                           sum(int(zahl(z["seiten"])) for z in zz), sum(int(zahl(z["objekte"])) for z in zz),
                           "; ".join(f"{k} × {v}" for k, v in enden.items()),
                           form_next(next((z["erstes_next"] for z in zz if z["erstes_next"]), ""), zz[0]["url"])])
        aus += tabelle(["Lauf", "Liste", "Listen", "Seiten", "Objekte", "Ende", "links.next"], zeilen)

    typen = lies(erg / "oparl_organisationstypen.tsv")
    if typen:
        je = collections.Counter()
        for z in typen:
            je[z.get("praefix") or "?"] += int(zahl(z["anzahl"]))
        aus.append(f"\nOrganisationen: {sum(je.values())} erfasst; je Präfix: "
                   + ", ".join(f"{k} {v}" for k, v in je.most_common()) + "; organizationType je Präfix: "
                   + ", ".join(f"{z.get('praefix', '?')}/{z['organizationType']} {z['anzahl']}" for z in typen))

    bed = lies(erg / "oparl_stichprobe_bedeckung.tsv")
    if bed:
        aus.append("\nStichprobe – Feldabdeckung:\n")
        aus += tabelle(["Feld", "vorhanden", "von", "Anteil"],
                       [[z["feld"], z["vorhanden"], z["von"], anteil(z["vorhanden"], z["von"])] for z in bed])
        urteil = regel_stichprobe(bed, laeufe)
        if urteil:   # Regel in STUFEN.md, Stufe 5
            aus.append(f"\nRegel Stufe 5 (mindestens {MINDESTENS} Vorlagen 2020–2026, jedes Jahr vertreten, keine "
                       f"Doppelungen, Sortierung nach created): {urteil}")
    seiten = lies(erg / "oparl_stichprobe_seiten.tsv")
    if seiten:
        aus.append("\nStichprobe – Seiten: " + "; ".join(
            f"{z['seite']}: {z['objekte']} ({z['ab_stichtag']} ab Stichtag, {z['date_max']} bis {z['date_min']}"
            + (f"; created {tag_ortszeit(z['created_max'])} bis {tag_ortszeit(z['created_min'])} (Ortszeit)"
               if z.get("created_max") else "") + ")"
            for z in seiten))
    jahre = lies(erg / "oparl_stichprobe_jahre.tsv")
    if jahre:
        aus.append("\nStichprobe – Jahre (date): " + "; ".join(f"{z['jahr']}: {z['objekte']}" for z in jahre))
    for datei, schluessel, titel in (("oparl_papertypen.tsv", "paperType", "paperType"),
                                     ("oparl_beratungsrollen.tsv", "role", "Beratungsrollen (consultation.role)"),
                                     ("oparl_referenzschema.tsv", "schema", "Referenzschema"),
                                     ("oparl_top_ergebnisse.tsv", "result", "TOP-Ergebnisse (agendaItem.result)")):
        zz = lies(erg / datei)
        if zz:
            aus.append(f"\n{titel}: " + "; ".join(f"{z[schluessel]} {z['anzahl']}" for z in zz[:15])
                       + (f"; … ({len(zz) - 15} weitere)" if len(zz) > 15 else ""))
    sitz = {z["feld"]: z["wert"] for z in lies(erg / "oparl_sitzungen.tsv")}
    if sitz:
        aus.append(f"\nSitzungen (sitzungen): {sitz.get('Sitzungen insgesamt')} erfasst, start "
                   f"{sitz.get('start frühestes')} bis {sitz.get('start spätestes')}; vergangen "
                   f"{sitz.get('Sitzungen vergangen')}, künftig {sitz.get('Sitzungen künftig')}, ohne start "
                   f"{sitz.get('Sitzungen ohne start')}; Sortierung: {sitz.get('Sortierung nach start')}; TOPs mit result: "
                   f"vergangen {quote(_paar(sitz, 'vergangen'))}, künftig {quote(_paar(sitz, 'künftig'))}")
    if bed:
        aus.append("\nagendaItem.result für Beratungen der Stichprobe: offen (die Stichprobe zählt nur, ob "
                   "consultation.agendaItem gesetzt ist; `sitzungen` erfasst die ersten Seiten der Sitzungsliste ohne "
                   "Bezug zur Stichprobe)")
    pt = lies(erg / "oparl_papertypen.tsv")
    if pt and REGELN.exists():
        zeilen, q = papertyp_abdeckung([(z["paperType"], z["anzahl"]) for z in pt], regeln_laden())
        aus.append("\nZerlegung paperType (explore/paperType_regeln.tsv, „aus Vorlagenart abgeleitet“):\n")
        aus += tabelle(["paperType", "Anzahl", "Regel", "Art", "Einreichende", "Ebene", "Status"],
                       [[z["paperType"], z["anzahl"], z["regel"] or "–", z["art"], z["einreichende"], z["ebene"],
                         z["status"]] for z in zeilen])
        aus.append(f"\nAbdeckung (Vorlagen): zerlegt {quote(q['zerlegt'])}; Art {quote(q['art'])}; Einreichende "
                   f"(einschließlich „–“ der Verwaltungsvorlagen) {quote(q['einreichende'])}; Ebene {quote(q['ebene'])}; "
                   f"Kürzel offen {quote(q['kuerzel_offen'])}")
        aus.append(f"\nEinreichende genannt (ohne „–“), bezogen auf politische Vorlagen (zerlegt, paperType nennt "
                   f"Einreichende laut Regel): {quote(q['einreichende_genannt'])}")
    aus += pdf_abschnitt(erg, laeufe)
    return aus


def wilson(k, n, z=Z95):
    """Wilson-Intervall (Vorgabe 95 %) für den Anteil k von n als (unten, oben); None ohne n."""
    if not n:
        return None
    p, z2 = k / n, z * z
    nenner = 1 + z2 / n
    mitte = (p + z2 / (2 * n)) / nenner
    halb = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / nenner
    return max(0.0, mitte - halb), min(1.0, mitte + halb)


def prozent(x):
    return f"{100 * x:.0f} %"


def quote_wilson(k, n):
    """„k von n (x %; Wilson 95 % a–b %)“ oder „k von 0“."""
    w = wilson(k, n)
    return f"{k} von {n}" + (f" ({prozent(k / n)}; Wilson 95 % {prozent(w[0])}–{prozent(w[1])})" if w else "")


def pdf_zaehlung(zeilen):
    """Gruppen der Zeilen aus pdf_koepfe.tsv: ausgewählt (alle), versucht (Anfrage gestellt, ohne „nicht abgerufen“ und
    Abbruch), abgerufen (versucht ohne HTTP-Fehler), gelesen (PDF gelesen, Textebene geprüft), kennung (federführender
    Kandidat im Kopf), abgeglichen (Kennung einer Organisation aus organizations/at zugeordnet), fehler (versucht, aber
    nicht gelesen: HTTP 404/410, zu groß, kein PDF, verschlüsselt, defekt)."""
    versucht = [z for z in zeilen if (z.get("treffer") or "nicht abgerufen") != "nicht abgerufen"
                and not z["treffer"].startswith("abbruch")]
    abgerufen = [z for z in versucht if not z["treffer"].startswith("fehler: HTTP")]
    gelesen = [z for z in abgerufen if z["treffer"] in GELESEN]
    kennung = [z for z in gelesen if z["treffer"] == "kennung"]
    return {"ausgewaehlt": zeilen, "versucht": versucht, "abgerufen": abgerufen, "gelesen": gelesen,
            "kennung": kennung, "abgeglichen": [z for z in kennung if "/organizations/at/" in (z.get("abgleich") or "")],
            "fehler": [z for z in versucht if z["treffer"] not in GELESEN]}


def _zahlen(werte):
    return [int(w) for w in werte if str(w or "").isdigit()]


def vorlagen_ab_stichtag(erg):
    """Geschätzte Zahl der Vorlagen ab dem Stichtag aus oparl_umfang.tsv (Stufe 3), sonst None. Schätzung nach
    created (Vorlagen mit created ab dem Stichtag bis zur Grenzseite G); Vorlagen mit date ab dem Stichtag trotz created
    davor fehlen darin (Zeilen objekt=abstand)."""
    for z in lies(Path(erg) / "oparl_umfang.tsv"):
        if (z.get("objekt"), z.get("feld")) == ("grenze", "vorlagen_ab_stichtag"):
            m = re.match(r"\d+", z.get("wert") or "")
            return int(m.group()) if m else None
    return None


BESTAND_JAHR = "verwaltung_ohne_underDirectionOf_mit_datei_"


def je_jahr_zaehlen(zeilen, treffer):
    """{Jahr: (k, n)}: n Zeilen je Jahr, k davon in `treffer` (Teilmenge derselben Zeilen)."""
    ids = {id(z) for z in treffer}
    aus = {}
    for z in zeilen:
        k, n = aus.get(z.get("jahr") or "?", (0, 0))
        aus[z.get("jahr") or "?"] = (k + (id(z) in ids), n + 1)
    return aus


def gewichtete_quote(bestand, je_jahr, k, n, z=Z95):
    """Quote der Stufe 6 gewichtet mit dem Bestand je Jahr (Verwaltungsvorlagen ohne underDirectionOf mit Datei in der
    Stichprobe), weil die Auswahl gleich viele Vorlagen je Jahr nimmt, nicht proportional. Je Jahr q_j = k_j/n_j;
    Jahre ohne angefragte Datei erhalten die ungewichtete Quote k/n (Liste `ohne_auswahl`). Intervall: Näherung für
    geschichtete Anteile, Varianz je Jahr nach Agresti-Coull (p̃_j = (k_j + z²/2)/(n_j + z²)), auf 0–1 begrenzt.
    Liefert (q, unten, oben, ohne_auswahl) oder None ohne Bestand."""
    summe = sum(bestand.values())
    if not summe or not n:
        return None
    q, varianz, ohne = 0.0, 0.0, []
    for j, v in sorted(bestand.items()):
        kj, nj = je_jahr.get(j, (0, 0))
        if not nj:
            kj, nj = k, n
            ohne.append(j)
        w = v / summe
        p = (kj + z * z / 2) / (nj + z * z)
        q += w * kj / nj
        varianz += w * w * p * (1 - p) / (nj + z * z)
    d = z * math.sqrt(varianz)
    return q, max(0.0, q - d), min(1.0, q + d), ohne


def hochrechnung(grundlage, k, n, gesamt=None, je_jahr=None):
    """Schätzung der Abdeckung der Federführung für Vorlagen ab 2020: Anteil mit underDirectionOf (a) plus Anteil der
    Verwaltungsvorlagen ohne underDirectionOf mit Datei (v) mal Quote q aus Stufe 6, je bezogen auf die Stichprobe
    (s). Mit `je_jahr` ({Jahr: (k_j, n_j)}) und dem Bestand je Jahr in der Grundlage (BESTAND_JAHR…) ist q nach Jahr
    gewichtet (gewichtete_quote), sonst ungewichtet k/n mit Wilson-Intervall („gewichtet“ False: Die Auswahl ist gleich
    je Jahr, nicht proportional, die Schätzung kann verzerrt sein). Nicht enthalten: der Stichprobenfehler von a und v
    (Stufe 5, Seiten als Klumpen, Designeffekt unbekannt) und die Richtigkeit der Zuordnung (jeder Treffer zählt als
    richtig: Obergrenze, solange die manuelle Kontrolle fehlt). `gesamt`: Vorlagen ab 2020 (Stufe 3) für absolute
    Zahlen. None ohne Grundlage oder ohne n."""
    s = int(zahl(grundlage.get("stichprobe_vorlagen")))
    w = wilson(k, n)
    if not s or not w:
        return None
    a = int(zahl(grundlage.get("mit_underDirectionOf")))
    v = int(zahl(grundlage.get("verwaltung_ohne_underDirectionOf_mit_datei")))
    bestand = {f[len(BESTAND_JAHR):]: int(zahl(x)) for f, x in grundlage.items() if f.startswith(BESTAND_JAHR)}
    g = gewichtete_quote(bestand, je_jahr, k, n) if je_jahr is not None and bestand else None
    q, unten, oben, ohne = g if g else (k / n, w[0], w[1], [])
    werte = {"a": a / s, "v": v / s, "k": k, "n": n, "q_roh": k / n, "q": q, "q_unten": unten, "q_oben": oben,
             "gewichtet": bool(g), "ohne_auswahl": ohne,
             "anteil": (a + v * q) / s, "unten": (a + v * unten) / s, "oben": (a + v * oben) / s}
    if gesamt:
        werte.update({f"n_{x}": round(gesamt * werte[x]) for x in ("anteil", "unten", "oben", "v")})
    return werte


def monate_bis(laeufe, beginn=dt.date(2020, 1, 1)):
    """Monate vom 01.01.2020 bis zum Tag des letzten erfolgreichen umfang-Laufs (Zählung der Vorlagen ab 2020), als
    Kommazahl (30,44 Tage je Monat); None ohne solchen Lauf."""
    for l in reversed(laeufe):
        if l.get("kommando") == "umfang" and l.get("ergebnis") == "ok":
            t = zeitpunkt(l.get("start"))
            if t and t.date() > beginn:
                return (t.date() - beginn).days / 30.44
    return None


def kontrolle_lesen(erg, kennung_ids):
    """Manuelle Kontrolle der Zuordnung (pdf_koepfe_kontrolle.tsv, Spalten `id` und `urteil` „richtig“/„falsch“/„unklar“,
    sonst nichts; STUFEN.md Stufe 6): (richtig, geprüft), nur Zeilen zu Vorlagen mit Treffer `kennung`; None ohne Datei."""
    zeilen = lies(Path(erg) / "pdf_koepfe_kontrolle.tsv")
    if not zeilen:
        return None
    urteile = [(z.get("urteil") or "").strip() for z in zeilen if z.get("id") in kennung_ids]
    geprueft = [u for u in urteile if u in ("richtig", "falsch")]
    return sum(1 for u in geprueft if u == "richtig"), len(geprueft)


def regel_pdf(zaehlung, laeufe, grundlage):
    """Urteil „Stufe 6 erfüllt“ (STUFEN.md): letzter pdf-koepfe-Lauf „ok“, mindestens MINDESTENS_PDF gelesene PDFs,
    höchstens HOECHSTENS_FEHLER der versuchten Dateien mit Fehler, Ämterliste vorhanden. „erfüllt“ heißt: Die Zahlen sind
    für den Bericht und die Anfrage verwendbar, nicht, dass die Erkennungsquote hoch ist."""
    letzte = [l for l in laeufe if l.get("kommando") == "pdf-koepfe"]
    if not letzte:
        return "nicht prüfbar (kein pdf-koepfe-Lauf in oparl_laeufe.tsv)"
    if letzte[-1].get("ergebnis") != "ok":
        return (f"nicht erfüllt (letzter pdf-koepfe-Lauf {letzte[-1].get('lauf')}: {letzte[-1].get('ergebnis')}) – "
                "berichten")
    gelesen, versucht, fehler = (len(zaehlung[k]) for k in ("gelesen", "versucht", "fehler"))
    gruende = [f"nur {gelesen} PDFs gelesen (mindestens {MINDESTENS_PDF})"] if gelesen < MINDESTENS_PDF else []
    if versucht and fehler / versucht > HOECHSTENS_FEHLER:
        gruende.append(f"{fehler} von {versucht} Dateien mit Fehler (höchstens {prozent(HOECHSTENS_FEHLER)})")
    if str(grundlage.get("aemterliste", "fehlt")) in ("fehlt", "0"):
        gruende.append("Ämterliste fehlt oder leer (Stufe 4: organisationen)")
    return "nicht erfüllt (" + "; ".join(gruende) + ") – berichten" if gruende else "erfüllt"


def pdf_abschnitt(erg, laeufe):
    """Abschnitt Stufe 6 (pdf_koepfe.tsv, pdf_koepfe_grundlage.tsv): Erkennungs- und Abgleichquote mit Wilson-Intervall,
    Verteilungen nach Bezeichnung, Jahr und paperType, Lage der Kandidaten, Textebene, Bytes und Seiten, Hochrechnung
    der Federführung (Schätzung) und das Urteil „Stufe 6 erfüllt“. Nur Zahlen und Kennungen, kein Text aus PDFs."""
    pdf = lies(Path(erg) / "pdf_koepfe.tsv")
    if not pdf:
        return []
    g = {z["feld"]: z["wert"] for z in lies(Path(erg) / "pdf_koepfe_grundlage.tsv")}
    zz = pdf_zaehlung(pdf)
    n_ab, n_ge, n_ke, n_gl = (len(zz[k]) for k in ("abgerufen", "gelesen", "kennung", "abgeglichen"))
    treffer = collections.Counter(z.get("treffer") or "–" for z in pdf)
    aus = [f"\n### Stufe 6 – PDF-Köpfe\n",
           f"PDF-Köpfe (auxiliaryFile): {len(pdf)} Verwaltungsvorlagen ohne underDirectionOf ausgewählt, "
           f"{len(zz['versucht'])} angefragt, {n_ab} abgerufen (HTTP 200), {n_ge} PDFs gelesen; "
           + ", ".join(f"{k} {v}" for k, v in treffer.most_common())
           + "; je Jahr: " + ", ".join(f"{j} {n}" for j, n in sorted(collections.Counter(
               z.get("jahr") or "?" for z in pdf).items()))]
    if g:
        aus.append(f"\nGrundlage (Stichprobe Stufe 5): {g.get('stichprobe_vorlagen')} Vorlagen, davon mit "
                   f"underDirectionOf {g.get('mit_underDirectionOf')}; Verwaltungsvorlagen {g.get('verwaltungsvorlagen')}, "
                   f"davon ohne underDirectionOf {g.get('verwaltung_ohne_underDirectionOf')}, mit Datei "
                   f"{g.get('verwaltung_ohne_underDirectionOf_mit_datei')}; Auswahl {g.get('ausgewaehlt')} (--anzahl "
                   f"{g.get('anzahl')}); Größengrenze {g.get('pdf_max_bytes')} Bytes; Ämterliste {g.get('aemterliste')}")
    aus += ["",
            f"- Erkennungsquote (Kennung nach Regel im Kopf gefunden, Annahme, Zuordnung ungeprüft / abgerufen): "
            f"{quote_wilson(n_ke, n_ab)}",
            f"- bezogen auf gelesene PDFs: {quote_wilson(n_ke, n_ge)}",
            f"- Abgleichquote (einer Organisation aus organizations/at zugeordnet / Kennung erkannt): "
            f"{quote_wilson(n_gl, n_ke)}",
            f"- Abgleich: " + (", ".join(f"{k} {v}" for k, v in collections.Counter(
                "Kennung organizations/at" if "/organizations/at/" in (z.get("abgleich") or "") else z.get("abgleich")
                or "–" for z in zz["kennung"]).most_common()) or "–"),
            f"- Lage der Kandidaten im Kopf (PDFs mit Textebene): " + (", ".join(
                f"{k} {v}" for k, v in collections.Counter(z.get("lage") or "–" for z in zz["gelesen"]
                                                           if z["treffer"] != "kein_text").most_common()) or "–"),
            f"- Regel für den federführenden Kandidaten: " + (", ".join(f"{k} {v}" for k, v in collections.Counter(
                z.get("regel") for z in zz["kennung"]).most_common()) or "–")]
    bez = collections.Counter(z.get("bezeichnung") for z in zz["kennung"] if z.get("bezeichnung"))
    alle = collections.Counter(teil.split()[0] for z in zz["gelesen"] for teil in (z.get("kandidaten") or "").split("; ")
                               if teil.endswith(" Kopf"))

    def beleg(b):
        return b + ("" if b in ("Ressort", "Amt") else " (Annahme)")
    aus += [f"- je Bezeichnung (federführend): " + (", ".join(f"{beleg(k)} {v}" for k, v in bez.most_common()) or "–"),
            f"- je Bezeichnung (alle Kandidaten im Kopf): "
            + (", ".join(f"{beleg(k)} {v}" for k, v in alle.most_common()) or "–")]
    for titel, schluessel in (("je Jahr", "jahr"), ("je paperType", "paperType")):
        gruppen = collections.OrderedDict()
        for z in sorted(zz["abgerufen"], key=lambda z: z.get(schluessel) or ""):
            gruppen.setdefault(z.get(schluessel) or "?", []).append(z)
        aus.append(f"- Erkennung {titel} (erkannt/abgerufen): " + (", ".join(
            f"{k} {sum(1 for z in v if z['treffer'] == 'kennung')}/{len(v)}" for k, v in gruppen.items()) or "–"))
    ohne_text = sum(1 for z in zz["gelesen"] if z["treffer"] == "kein_text")
    groesse = _zahlen(z.get("bytes") for z in zz["abgerufen"])
    seiten = _zahlen(z.get("seiten") for z in zz["abgerufen"])
    dauer = [zahl(z.get("antwort_s")) for z in zz["versucht"] if z.get("quelle") == "netz" and z.get("antwort_s")]
    zu_gross = sum(1 for z in zz["versucht"] if z["treffer"] == "zu groß")
    aus += [f"- ohne Textebene (OCR nötig): {quote_wilson(ohne_text, n_ge)}; Fundstelle: " + (", ".join(
                f"{k} {v}" for k, v in collections.Counter(z.get("fundstelle") or "–" for z in zz["gelesen"]).items())
                or "–"),
            f"- Bytes (vollständig geladene Dateien, n = {len(groesse)}): "
            + (f"Median {statistics.median(groesse):.0f}, Summe {sum(groesse)}, Maximum {max(groesse)}"
               if groesse else "–") + f"; größer als die Grenze: {zu_gross}",
            f"- Seiten (n = {len(seiten)}): "
            + (f"Median {statistics.median(seiten):g}, Maximum {max(seiten)}" if seiten else "–"),
            f"- Antwortzeit (Netz, n = {len(dauer)}): "
            + (f"Ø {sum(dauer) / len(dauer):.2f} s, max {max(dauer):.2f} s" if dauer else "–"),
            f"- Klasse des PDF-Erzeugers: " + (", ".join(f"{k} {v}" for k, v in collections.Counter(
                z.get("erzeuger") for z in zz["abgerufen"] if z.get("erzeuger")).most_common()) or "–"),
            f"- Wahl der Datei: " + (", ".join(f"{k} {v}" for k, v in collections.Counter(
                z.get("auswahl") or "–" for z in pdf).most_common()) or "–")]
    kontrolle = kontrolle_lesen(erg, {z.get("id") for z in zz["kennung"]})
    aus.append("- Richtigkeit der Zuordnung (manuelle Kontrolle im lokalen Cache, nur richtig/falsch): " + (
        f"{quote_wilson(*kontrolle)} richtig" if kontrolle and kontrolle[1] else
        "nicht geprüft (pdf_koepfe_kontrolle.tsv fehlt oder ohne Urteil); jeder Treffer zählt bisher als richtig"))
    gesamt = vorlagen_ab_stichtag(erg)
    versucht = zz["versucht"]
    h = hochrechnung(g, n_ke, len(versucht), gesamt, je_jahr_zaehlen(versucht, zz["kennung"])) if g else None
    h_at = hochrechnung(g, n_gl, len(versucht), gesamt, je_jahr_zaehlen(versucht, zz["abgeglichen"])) if g else None
    if h:
        aus.append("\n**Hochrechnung der Federführung (Schätzung, Vorlagen ab 2020):** Anteil mit underDirectionOf "
                   f"{prozent(h['a'])}, Verwaltungsvorlagen ohne underDirectionOf mit Datei {prozent(h['v'])} (Stichprobe "
                   "Stufe 5).")
        for name, x in (("Kennung nach Regel gefunden", h), ("einer Organisation aus organizations/at zugeordnet", h_at)):
            quote = (f"{x['k']} von {x['n']} angefragten Dateien, nach Jahr gewichtet {prozent(x['q'])}, 95 % "
                     f"(Näherung) {prozent(x['q_unten'])}–{prozent(x['q_oben'])}" if x["gewichtet"] else
                     f"{x['k']} von {x['n']} angefragten Dateien, ungewichtet {prozent(x['q'])}, Wilson 95 % "
                     f"{prozent(x['q_unten'])}–{prozent(x['q_oben'])}")
            aus.append(f"- mit PDF-Kopf ({name}, {quote}): Abdeckung {prozent(x['anteil'])} "
                       f"({prozent(x['unten'])}–{prozent(x['oben'])})"
                       + (f", bei rund {gesamt} Vorlagen ab 2020 etwa {x['n_anteil']} ({x['n_unten']}–{x['n_oben']})"
                          if gesamt else ""))
        aus.append("- Einschränkungen: (1) Intervall nur aus der Unsicherheit der Quote in Stufe 6; der Stichprobenfehler "
                   "der Anteile aus Stufe 5 (Seiten als Klumpen) ist nicht enthalten. (2) Die Richtigkeit der Zuordnung "
                   "ist " + ("nur an der manuellen Kontrolle oben geprüft" if kontrolle and kontrolle[1] else
                             "ungeprüft: Jeder Treffer zählt als richtige Zuordnung (Obergrenze)") + ". (3) "
                   + ("Die Auswahl nimmt gleich viele Vorlagen je Jahr; die Quote ist deshalb mit dem Bestand je Jahr "
                      "gewichtet" + (f" (Jahre ohne angefragte Datei mit der ungewichteten Quote: "
                                     f"{', '.join(h['ohne_auswahl'])})" if h["ohne_auswahl"] else "")
                      if h["gewichtet"] else
                      "Die Auswahl nimmt gleich viele Vorlagen je Jahr, nicht proportional; ohne Bestand je Jahr in "
                      "pdf_koepfe_grundlage.tsv ist die Quote ungewichtet und kann verzerrt sein")
                   + ". Schätzung, keine Messung.")
        if gesamt and groesse:
            mittel = sum(groesse) / len(groesse)
            aus.append(f"- Umfang eines PDF-Abrufs (Schätzung): etwa {h['n_v']} Verwaltungsvorlagen ohne "
                       f"underDirectionOf mit Datei ab 2020, je eine Datei, bei mittlerer Größe {mittel:.0f} Bytes etwa "
                       f"{h['n_v'] * mittel / 1e6:.1f} MB; ohne Textebene etwa "
                       f"{prozent(ohne_text / n_ge) if n_ge else '–'} (Stufe C ohne Texterkennung nicht möglich)")
        monate = monate_bis(laeufe)
        if gesamt:
            aus.append("- Neue Dokumente im Monat (Schätzung für den weiteren Abruf, ANFRAGE Punkt 5): " + (
                f"etwa {h['n_v'] / monate:.0f} ({h['n_v']} Verwaltungsvorlagen ohne underDirectionOf mit Datei ab "
                f"2020 geteilt durch {monate:.1f} Monate bis zur Zählung in Stufe 3; Annahme: gleichmäßig über die "
                "Zeit verteilt)" if monate else "nicht berechenbar (kein erfolgreicher umfang-Lauf in oparl_laeufe.tsv)"))
    aus.append(f"\nRegel Stufe 6 (mindestens {MINDESTENS_PDF} PDFs gelesen, höchstens {prozent(HOECHSTENS_FEHLER)} "
               f"Fehler, Ämterliste vorhanden, Lauf ok): {regel_pdf(zz, laeufe, g)}")
    return aus


def auswertung(cache, erg, stufe=None):
    cache, erg = Path(cache), Path(erg)
    protokoll = lies(cache / "abrufe.tsv")
    laeufe = lies(erg / "oparl_laeufe.tsv")
    aus = ["# Auswertung der Messstufen", "",
           f"Quellen: {cache / 'abrufe.tsv'} ({len(protokoll)} Zeilen), {erg / 'oparl_laeufe.tsv'} "
           f"({len(laeufe)} Läufe)", ""]
    if laeufe:
        aus += laeufe_abschnitt(laeufe, protokoll, stufe)
    elif protokoll:
        s = statistik(protokoll)
        aus += ["## Abrufprotokoll (ohne Laufzuordnung)", "",
                f"Netz {s['netz']}, Cache {s['cache']}, Status {s['status']}, Ø {sekunden(s['mittel'])} s, "
                f"max {sekunden(s['max'])} s, {s['bytes']} Bytes"]
    else:
        aus.append("Noch keine Läufe.")
    return "\n".join(aus + kennwerte(erg, laeufe)) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Auswertung der Messstufen (Markdown)")
    ap.add_argument("--cache", default=os.environ.get("RATSATLAS_CACHE", HIER / "_cache"))
    ap.add_argument("--ergebnisse", default=os.environ.get("RATSATLAS_ERGEBNISSE", HIER / "ergebnisse"))
    ap.add_argument("--stufe", help="nur diese Stufe in den Tabellen der Läufe")
    a = ap.parse_args()
    sys.stdout.write(auswertung(a.cache, a.ergebnisse, a.stufe))


if __name__ == "__main__":
    main()
