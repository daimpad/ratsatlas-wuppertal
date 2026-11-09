"""Auswertung der Messstufen (explore/STUFEN.md) als Markdown auf stdout – ohne Netzzugriff.

Abgeleitet aus ratsatlas-koeln @d609111 (explore/auswertung.py). Abweichungen von Köln: Kennwerte zu `umfang`
(Gesamtzahl, Datumsgrenze, Sortierung, Ende von links.next), Präfixe der Organisationen, Beratungsrollen, Zerlegung der
Vorlagenart nach explore/paperType_regeln.tsv (regeln_laden, zerlege, papertyp_abdeckung) und die Regel für die
Stichprobe (regel_stichprobe) statt der Kölner Regel zum Jahresfilter; Gesamtzahl von meeting und person (aus
`pagination` oder `umfang --liste`, sonst ausdrücklich „offen“), Zeitraum und Sortierung der Sitzungsliste, Bezeichnungen
in den PDF-Köpfen.

Liest das Abrufprotokoll _cache/abrufe.tsv und die TSVs in ergebnisse/ (oparl_laeufe.tsv, oparl_listen.tsv,
oparl_test.tsv, oparl_kennzahlen.tsv, oparl_umfang.tsv, oparl_umfang_meeting.tsv, oparl_umfang_person.tsv,
oparl_organisationstypen.tsv, oparl_stichprobe_*.tsv, oparl_papertypen.tsv, oparl_beratungsrollen.tsv,
oparl_referenzschema.tsv, oparl_top_ergebnisse.tsv, oparl_sitzungen.tsv, pdf_koepfe.tsv).
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
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

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
    nach date auftreten und der letzte stichprobe-Lauf in oparl_laeufe.tsv „ok“ ist."""
    werte = {z["feld"]: int(zahl(z["vorhanden"])) for z in bedeckung}
    menge = next((v for f, v in werte.items() if f.startswith("Vorlagen ") and " bis " in f), None)
    if menge is None:
        return None
    gruende = ([f"nur {menge} Vorlagen (mindestens {MINDESTENS})"] if menge < MINDESTENS else []) + [
        f"{f} {werte[f]}" for f in ("doppelte Kennungen", "Seiten nicht absteigend nach date") if werte.get(f)] + [
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
                       f"Doppelungen, Sortierung nach date): {urteil}")
    seiten = lies(erg / "oparl_stichprobe_seiten.tsv")
    if seiten:
        aus.append("\nStichprobe – Seiten: " + "; ".join(
            f"{z['seite']}: {z['objekte']} ({z['ab_stichtag']} ab Stichtag, {z['date_max']} bis {z['date_min']})"
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
    pdf = lies(erg / "pdf_koepfe.tsv")
    if pdf:
        treffer = collections.Counter(z.get("treffer") or "keine_datei" for z in pdf)
        mit = sum(v for k, v in treffer.items() if k not in ("keine_datei", "nicht abgerufen")
                  and not k.startswith("fehler: HTTP"))
        abgeglichen = sum(1 for z in pdf if "/organizations/at/" in (z.get("abgleich") or ""))
        jahre_pdf = collections.Counter(z.get("jahr") or "?" for z in pdf)
        bezeichnungen = collections.Counter(z.get("bezeichnung") for z in pdf if z.get("bezeichnung"))
        aus.append(f"\nPDF-Köpfe (auxiliaryFile): {len(pdf)} Verwaltungsvorlagen ohne underDirectionOf, {mit} Dateien "
                   "ausgewertet; " + ", ".join(f"{k} {v}" for k, v in treffer.most_common())
                   + "; je Jahr: " + ", ".join(f"{j} {n}" for j, n in sorted(jahre_pdf.items()))
                   + "; je Bezeichnung: " + (", ".join(f"{k} {v}" for k, v in bezeichnungen.most_common()) or "–")
                   + (f"; Erkennungsquote Amtskennung: {100 * treffer['kennung'] / mit:.0f} %; davon einer "
                      f"Organisation aus organizations/at zugeordnet: {abgeglichen}" if mit else ""))
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
