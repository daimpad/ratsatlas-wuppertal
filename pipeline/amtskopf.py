"""Federführendes Amt aus dem Kopf der Vorlagendokumente, ohne Netz (Schritt `amtskopf`; CLAUDE.md 5.3 und 9,
Entscheidungen vom 13.11.2026 zu Stufe 6 und vom 15.11.2026 „Messstufe 6 entfällt als eigener Abruf“).

Aufruf: `python3 -m pipeline amtskopf`, nach `dokumente`. Keine Anfrage ans Netz: gelesen werden nur die Rohdaten
(`config.PAPERS`), die Texte aus dem Dokumentabruf (`dokumente.text`, gz-Text unter `config.TEXTE_ORDNER`, Seiten
durch \\f getrennt) und dessen Zustand (`config.DOKUMENTE_ZUSTAND`, nur lesend).

Ausgewertet werden alle Verwaltungsvorlagen (`actors.kategorie` = Verwaltung; Bonner Namen und `vorlagenart.REGELN`,
Regeln 1, 5 und 6) im Zeitraum ab 2020 ohne `underDirectionOf`, deren Anlagen der Dokumentabruf lädt (`dokumente.aufgaben`:
ohne gelöschte Vorlagen und Dateien, ohne die nach § 24 GO NRW ausgenommenen). Je Vorlage eine Datei, gewählt wie in
Stufe 6 (`datei_waehlen`: Name nennt die Referenz, dann die Vorlage, sonst die erste Datei; Annahme). Regeln und
Kategorien sind die der Stufe 6 (explore/STUFEN.md, Abschnitt „Stufe 6 – PDF-Köpfe“):
- Seite 1, bei leerem Text höchstens Seite 2 (eigene Fundstelle „Seite 2“); die Seiten trennt \\f, das der
  Dokumentabruf nach jeder Seite schreibt (pypdf und pdftotext). Ein Text ohne \\f gilt als eine Seite (Spalte
  `seitengrenzen` „nein“);
- Normalisierung, Kandidaten „Bezeichnung Nummer“, Kopf bis zur ersten Zeile mit „Beschlussvorschlag“, „Begründung“
  oder „Sachverhalt“, sonst die ersten 30 Zeilen; Regel für den federführenden Kandidaten; Abgleich der Nummer mit den
  Organisationen mit Präfix `at`; „Nummer erkannt, Stelle mehrdeutig“ ohne Wahl einer Stelle.

Die reinen Textfunktionen sind aus explore/oparl_messung.py (pdf-koepfe) und explore/auswertung.py (stelle_kategorie)
übernommen, nicht importiert (die Messwerkzeuge laden ihr eigenes Abrufmodul und setzen sys.path);
tests/test_amtskopf.py prüft, dass beide Fassungen gleich arbeiten. Eine Änderung der Regeln gehört in beide Dateien.

Ämterliste: Organisationen mit Präfix `at` aus `config.ORGANIZATIONS` (Vollabruf; Name und Kurzname), sonst aus
explore/ergebnisse/oparl_organisationen.tsv (Stufe 4, wie in Stufe 6). Alle `at`-Organisationen, unabhängig von der
Klasse in explore/ergebnisse/aemter.tsv (wie Stufe 6).

Ergebnisse (data/ ist nicht versioniert):
- `config.AMTSKOPF_AUDIT` (audit_amtskopf.tsv): je Vorlage eine Zeile wie explore/ergebnisse/pdf_koepfe.tsv, aber nur
  Kennungen, Kategorien, Zeilennummern und Zählungen; keine Textauszüge, keine Dateinamen, keine Namen, Telefonnummern
  oder E-Mail-Adressen. „Kennung“ heißt eine Bezeichnung aus der festen Liste (Ressort, Amt, Stadtbetrieb,
  Geschäftsbereich, Eigenbetrieb) mit ihrer Nummer, etwa „Amt 402“.
- `config.AMTSKOPF` (amtskopf.json): je Vorlage mit eindeutiger Stelle die Kennung der Organisation, die Datei, Seite
  und Zeile; liest actors.responsibilities (method „pdf_kopf“, derived 1, evidence nur die Fundstelle).
- Zusammenfassung auf der Konsole: Zahl je Kategorie, Quoten wie Stufe 6 (je abgerufene Datei), je Jahr und nach dem
  Bestand je Jahr gewichtet (solange der Dokumentabruf nicht alle Jahre gleich weit geladen hat, Schätzung), dazu die
  Abdeckung der Federführung ab 2020. Jeder Treffer zählt als richtig (Obergrenze), solange keine manuelle Kontrolle
  vorliegt.

Abweichung für den gemeinsamen Kern: neu in Wuppertal (Köln hat keine PDF-Köpfe, Bonn die Federführung aus der API).
"""
import collections
import csv
import json
import re
from pathlib import Path

from . import aenderungen, config, dokumente, sessionnet, vorlagenart
from .fetch import _write

# --- Regeln der Stufe 6, unverändert aus explore/oparl_messung.py (Gleichheit: tests/test_amtskopf.py) -------------
RE_VO = re.compile(r"^VO/\d{4}/\d{2}$")   # Schema der Referenz laut CLAUDE.md 3.1, z. B. VO/1380/26
RE_PRAEFIX = re.compile(r"/organizations/([^/?#]+)/[^/?#]+$")
BEZEICHNUNG_BELEGT = ("Ressort", "Amt")
BEZEICHNUNG_ANNAHME = ("Stadtbetrieb", "Geschäftsbereich", "Eigenbetrieb")
# Hinter der Nummer keine weitere Ziffer und kein Punkt mit Ziffer (Teilnummer); ein Satzpunkt („Amt 402.“) ist erlaubt.
RE_AMT = re.compile(r"\b(Ressort|Stadtbetrieb|Geschäftsbereich|Eigenbetrieb|Amt)\s+(\d{2,3}(?:\.\d{1,3})*)(?!\d|\.\d)")
# Beginn des ersten Abschnitts nach dem Kopf (Annahme); ohne Abschnitt die ersten KOPF_ZEILEN Zeilen (Annahme)
RE_ABSCHNITT = re.compile(r"(?:Beschlussvorschlag|Begründung|Sachverhalt)\b")
KOPF_ZEILEN = 30
VOR, NACH = r"(?<![^\W\d_])", r"(?![^\W\d_])"
RE_VORLAGE_NAME = re.compile(rf"{VOR}(?:Vorlage|Beschlussvorlage|Verwaltungsvorlage|Drucksache){NACH}", re.I)
RE_ANLAGE = re.compile(rf"{VOR}(?:Anlagen?|Anhang|Anhänge){NACH}", re.I)
# Leerzeichen-Varianten, Bindestriche und unsichtbare Zeichen für die Normalisierung des Kopftexts
_ZEICHEN = {**dict.fromkeys(map(ord, "\t           　"),
                            " "),
            **dict.fromkeys(map(ord, "‐‑‒–−"), "-"),
            **dict.fromkeys(map(ord, "­​‌‍﻿"), None)}
# Treffer, die als „PDF gelesen“ gelten (Textebene geprüft)
GELESEN = ("kennung", "nur außerhalb des Kopfes", "nein", "kein_text")
# Ergebnis-Kategorien (Spalte `stelle`) wie explore/auswertung.py
STELLE_EINDEUTIG = "Nummer erkannt, Stelle eindeutig"
STELLE_MEHRDEUTIG = "Nummer erkannt, Stelle mehrdeutig"
STELLE_OHNE = "Nummer erkannt, keine Stelle in organizations/at"
STELLE_LISTE_FEHLT = "Nummer erkannt, Ämterliste fehlt oder leer"
STELLE_UNBEKANNT = "Nummer erkannt, Abgleich fehlt"
NICHT_IM_KOPF = "keine Nummer im Kopf erkannt"
OHNE_TEXTEBENE = "keine Textebene (OCR nötig)"
NICHT_GELESEN = "PDF nicht gelesen"
STELLEN = (STELLE_EINDEUTIG, STELLE_MEHRDEUTIG, STELLE_OHNE, STELLE_LISTE_FEHLT, STELLE_UNBEKANNT, NICHT_IM_KOPF,
           OHNE_TEXTEBENE, NICHT_GELESEN)

# --- Wuppertaler Pipeline: Treffer ohne gelesenen Text, aus dem Zustand des Dokumentabrufs --------------------------
NICHT_ABGERUFEN = "nicht abgerufen"   # noch nicht geladen (Dokumentabruf unvollständig) oder Text fehlt
# Status im Zustand des Dokumentabrufs → Treffer (wie die Fehler je Datei in Stufe 6)
TREFFER_JE_STATUS = {"zu_gross": "zu groß", "kein_pdf": "kein PDF", "extraktion_fehler": "fehler: Extraktion",
                     "fehlt": "fehler: HTTP 404/410", "verweigert": "fehler: abgewiesen (HTTP 401/403)",
                     "html": "fehler: abgewiesen (HTML statt PDF)"}
# abgerufen, aber nicht gelesen (zählt wie in Stufe 6 im Nenner „abgerufen“); HTTP 404/410 und Abweisungen nicht
FEHLER_ABGERUFEN = ("zu groß", "kein PDF", "fehler: Extraktion")
ORGANISATIONEN_TSV = config.ROOT / "explore" / "ergebnisse" / "oparl_organisationen.tsv"
SPALTEN = ("id", "reference", "jahr", "paperType", "datei", "datei_platz", "auswahl", "status_dokument", "treffer",
           "fundstelle", "seiten", "seitengrenzen", "zeilen", "abschnitt_zeile", "kandidaten_n", "kandidaten_kopf",
           "lage", "kandidaten", "regel", "bezeichnung", "bezeichnung_beleg", "kennung", "zeile", "vor_abschnitt",
           "abgleich", "stelle", "stellen")


def jahr_der_vorlage(p):
    """Jahr aus der Referenz VO/NNNN/JJ (20JJ), sonst aus `date`, sonst „?“."""
    ref = p.get("reference") or ""
    if RE_VO.match(ref):
        return f"20{ref[-2:]}"
    return str(p.get("date") or "")[:4] or "?"


def amt_kandidaten(nummer, aemter):
    """Kennungen aller at-Organisationen, deren Name oder Kurzname die Nummer als eigenes Zahlwort enthält, in der
    Reihenfolge der Ämterliste; [] ohne oder mit leerer Ämterliste. Bei mehreren wird keine gewählt (CLAUDE.md 9,
    13.11.2026)."""
    if not aemter:
        return []
    muster = re.compile(rf"(?<!\d)(?<!\d\.){re.escape(nummer)}(?!\d|\.\d)")   # Satzpunkt erlaubt, Teilnummer nicht
    return [k for k, text in aemter if muster.search(text)]


def amt_abgleichen(nummer, aemter):
    """Kennung der einzigen passenden at-Organisation; sonst „mehrdeutig (n)“ oder „kein Treffer in organizations/at“;
    ohne Ämterliste „Ämterliste fehlt (…)“, mit leerer „Ämterliste leer (…)“."""
    if aemter is None:
        return "Ämterliste fehlt (zuerst organisationen)"
    if not aemter:
        return "Ämterliste leer (keine Organisation mit Präfix at erfasst)"
    treffer = amt_kandidaten(nummer, aemter)
    if len(treffer) == 1:
        return treffer[0]
    return f"mehrdeutig ({len(treffer)})" if treffer else "kein Treffer in organizations/at"


def _referenzmuster(reference):
    """Muster für die Referenz VO/NNNN/JJ in einem Dateinamen, sonst None."""
    m = re.fullmatch(r"VO/(\d{4})/(\d{2})", reference or "")
    if not m:
        return None
    return re.compile(rf"(?<!\d)0*{int(m.group(1))}\s*[/_\-. ]\s*(?:20)?{m.group(2)}(?!\d)")


def datei_waehlen(p):
    """(Adresse, Platz ab 1, Zahl der Dateien, Regel) der Datei, deren Kopf gelesen wird, aus `p["dateiliste"]`
    (je Datei name, fileName, mimeType, url). Annahme wie Stufe 6: zuerst eine Datei, deren Name die Referenz nennt,
    dann eine, die die Vorlage oder den paperType nennt, jeweils nicht als Anlage bezeichnet und nicht mit einem
    mimeType ohne „pdf“; sonst die erste Datei mit Adresse."""
    liste = [d for d in p.get("dateiliste") or [] if isinstance(d, dict)]
    if not liste:
        n = p.get("dateien") or 0
        return (p.get("datei"), 1, n or "?", "erste Datei (Stichprobe ohne Dateiliste)") if p.get("datei") else (
            None, 0, n, "keine Datei")
    ref = _referenzmuster(p.get("reference"))
    art = (p.get("paperType") or "").strip()
    art_muster = re.compile(rf"{VOR}{re.escape(art)}{NACH}", re.I) if art else None

    def text(d):
        return " ".join(str(d.get(k) or "") for k in ("name", "fileName"))

    def moeglich(d):
        mime = str(d.get("mimeType") or "").lower()
        return bool(d.get("url")) and not RE_ANLAGE.search(text(d)) and (not mime or "pdf" in mime)

    for regel, pruefen in (("Name nennt die Referenz", lambda t: ref and ref.search(t)),
                           ("Name nennt die Vorlage", lambda t: RE_VORLAGE_NAME.search(t)
                            or (art_muster and art_muster.search(t)))):
        for i, d in enumerate(liste, 1):
            if moeglich(d) and pruefen(text(d)):
                return d["url"], i, len(liste), f"{regel} (Annahme)"
    for i, d in enumerate(liste, 1):
        if d.get("url"):
            return d["url"], i, len(liste), "erste Datei (kein Name als Vorlage erkannt)"
    return None, 0, len(liste), "keine Datei mit Adresse"


def text_normalisieren(text):
    """Zeilen des Seitentexts ohne Leerzeilen; Leerzeichen- und Bindestrich-Varianten vereinheitlicht, weiche
    Trennzeichen entfernt, Silbentrennung am Zeilenende verbunden (nur vor einem Kleinbuchstaben)."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").translate(_ZEICHEN)
    t = re.sub(r"(?<=[^\W\d_])- *\n *(?=[a-zäöüß])", "", t)
    return [z for z in (" ".join(teil.split()) for teil in t.split("\n")) if z]


def _hat_text(zeilen):
    return any(re.search(r"\w", z) for z in zeilen)


def kopf_kandidaten(zeilen):
    """Alle Kandidaten einer Seite mit Bezeichnung, Nummer, Kennung, Zeile (ab 1, ohne Leerzeilen) und Lage zum Kopf;
    dazu die Zeile des ersten Abschnitts oder None. Kein Text im Ergebnis."""
    abschnitt = next((i for i, z in enumerate(zeilen, 1) if RE_ABSCHNITT.match(z)), None)
    grenze = abschnitt if abschnitt else KOPF_ZEILEN + 1
    text = "\n".join(zeilen)
    aus = []
    for m in RE_AMT.finditer(text):
        zeile = text.count("\n", 0, m.start()) + 1
        aus.append({"bezeichnung": m.group(1), "nummer": m.group(2), "kennung": f"{m.group(1)} {m.group(2)}",
                    "zeile": zeile, "kopf": zeile < grenze})
    return aus, abschnitt


def federfuehrend(kandidaten):
    """(Kandidat oder None, Lage, Regel): unter den Kandidaten im Kopf der erste mit belegter Bezeichnung (Ressort,
    Amt), sonst der erste (Annahme); Kandidaten nur außerhalb des Kopfes ergeben keinen federführenden."""
    kopf = [k for k in kandidaten if k["kopf"]]
    if not kopf:
        return None, "keiner", ("nur außerhalb des Kopfes, kein federführender Kandidat" if kandidaten else "")
    verschieden = len({k["kennung"] for k in kopf})
    lage = "ein Kandidat" if len(kopf) == 1 else ("mehrere gleiche" if verschieden == 1 else "mehrere verschiedene")
    if verschieden == 1:
        return kopf[0], lage, "einzige Kennung im Kopf"
    belegt = [k for k in kopf if k["bezeichnung"] in BEZEICHNUNG_BELEGT]
    if belegt:
        return belegt[0], lage, "erster Kandidat im Kopf mit belegter Bezeichnung Ressort/Amt (Annahme)"
    return kopf[0], lage, "erster Kandidat im Kopf (Annahme)"


def stelle_kategorie(z):
    """Ergebnis-Kategorie einer Zeile allein aus `treffer` und `abgleich` (wie explore/auswertung.stelle_kategorie)."""
    treffer = z.get("treffer") or "nicht abgerufen"
    if treffer != "kennung":
        if treffer == "kein_text":
            return OHNE_TEXTEBENE
        return NICHT_IM_KOPF if treffer in GELESEN else NICHT_GELESEN
    abgleich = z.get("abgleich") or ""
    if "/organizations/at/" in abgleich:
        return STELLE_EINDEUTIG
    if abgleich.startswith("mehrdeutig"):
        return STELLE_MEHRDEUTIG
    if abgleich.startswith("kein Treffer"):
        return STELLE_OHNE
    return STELLE_LISTE_FEHLT if abgleich.startswith("Ämterliste") else STELLE_UNBEKANNT


# --- Auswertung eines Texts aus dem Dokumentabruf ------------------------------------------------------------------

def seiten(text):
    """Seiten eines Texts aus dem Dokumentabruf (jede Seite mit \\f abgeschlossen) und ob Seitengrenzen vorhanden
    sind. Ohne \\f gilt der ganze Text als eine Seite."""
    if "\f" not in text:
        return [text], False
    teile = text.split("\f")
    if teile and teile[-1] == "":   # \f am Ende jeder Seite: das letzte Stück ist leer
        teile.pop()
    return teile, True


def text_auswerten(text, aemter):
    """Kopferkennung eines Texts als Spalten der Audit-Tabelle (ohne Textinhalt): Seite 1, bei leerem Text Seite 2;
    Kandidaten mit Zeile und Lage, der federführende Kandidat und sein Abgleich mit organizations/at (bei
    „mehrdeutig (n)“ in `stellen` alle passenden Kennungen, keine gewählt)."""
    teile, grenzen = seiten(text or "")
    z = {"seiten": len(teile), "seitengrenzen": "ja" if grenzen else "nein"}
    zeilen, nr = text_normalisieren(teile[0] if teile else ""), 1
    if not _hat_text(zeilen) and len(teile) > 1:   # höchstens Seite 2, als eigene Fundstelle
        zeilen, nr = text_normalisieren(teile[1]), 2
    if not _hat_text(zeilen):
        return {**z, "treffer": "kein_text", "fundstelle": "Seite 1" + (" und 2" if len(teile) > 1 else "")}
    kandidaten, abschnitt = kopf_kandidaten(zeilen)
    feder, lage, regel = federfuehrend(kandidaten)
    z.update(fundstelle=f"Seite {nr}", zeilen=len(zeilen),
             abschnitt_zeile=abschnitt or f"kein Abschnitt (Kopf = erste {KOPF_ZEILEN} Zeilen, Annahme)",
             kandidaten_n=len(kandidaten), kandidaten_kopf=sum(1 for k in kandidaten if k["kopf"]), lage=lage,
             kandidaten="; ".join(f"{k['kennung']} Z{k['zeile']} {'Kopf' if k['kopf'] else 'außerhalb'}"
                                  for k in kandidaten), regel=regel,
             treffer="kennung" if feder else ("nur außerhalb des Kopfes" if kandidaten else "nein"))
    if feder:
        abgleich = amt_abgleichen(feder["nummer"], aemter)
        z.update(bezeichnung=feder["bezeichnung"], kennung=feder["kennung"], zeile=feder["zeile"],
                 bezeichnung_beleg=("belegt (CLAUDE.md 3.1/3.2)" if feder["bezeichnung"] in BEZEICHNUNG_BELEGT
                                    else "Annahme"),
                 vor_abschnitt="ja" if abschnitt else "kein Abschnitt erkannt", abgleich=abgleich)
        if abgleich.startswith("mehrdeutig"):   # alle passenden Organisationen, keine gewählt
            z["stellen"] = "; ".join(amt_kandidaten(feder["nummer"], aemter))
    return z


def fundstelle(z):
    """Fundstelle als Dokumentteil für `evidence`, ohne Wörter aus dem Dokument: „Seite 1, Kopf, Zeile 4“."""
    return f"{z['fundstelle']}, Kopf, Zeile {z['zeile']}"


# --- Ämterliste ---------------------------------------------------------------------------------------------------

def _praefix(kennung):
    m = RE_PRAEFIX.search(kennung or "")
    return m.group(1) if m else ""


def aemterliste():
    """(Liste aus (Kennung, „Name Kurzname“) der Organisationen mit Präfix at, Quelle): aus config.ORGANIZATIONS
    (Vollabruf), wenn dort mindestens eine steht, sonst aus explore/ergebnisse/oparl_organisationen.tsv (Stufe 4);
    (None, Grund) ohne beides."""
    try:
        orgs = json.loads(config.ORGANIZATIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        orgs = []
    at = [(o["id"], f"{o.get('name') or ''} {o.get('shortName') or ''}") for o in orgs if isinstance(o, dict)
          and isinstance(o.get("id"), str) and not o.get("deleted") and _praefix(o["id"]) == "at"]
    if at:
        return at, f"{config.ORGANIZATIONS.name} (Vollabruf)"
    try:
        with open(ORGANISATIONEN_TSV, encoding="utf-8", newline="") as f:
            at = [(z["id"], f"{z.get('name') or ''} {z.get('kurz') or ''}") for z in csv.DictReader(f, delimiter="\t")
                  if z.get("praefix") == "at"]
        return at, "explore/ergebnisse/oparl_organisationen.tsv (Stufe 4)"
    except OSError:
        return None, "fehlt"


# --- Schritt ------------------------------------------------------------------------------------------------------

def _papers():
    if not config.PAPERS.exists():
        return None
    with open(config.PAPERS, encoding="utf-8") as f:
        return [p for p in (json.loads(z) for z in f if z.strip()) if isinstance(p, dict)]


def _zustand():
    """Status je Datei-Kennung aus dem Zustand des Dokumentabrufs, nur lesend (ein unlesbarer Zustand gilt als leer und
    wird hier nicht beiseitegelegt)."""
    try:
        z = json.loads(config.DOKUMENTE_ZUSTAND.read_text(encoding="utf-8"))
        return {k: (e or {}).get("status") for k, e in z.get("dateien", {}).items() if isinstance(e, dict)}
    except (OSError, ValueError, AttributeError):
        return {}


def _dateiliste(p, erlaubt):
    """Dateien der Vorlage wie in der Stichprobe der Stufe 6 (name, fileName, mimeType; als `url` die Datei-Kennung wie
    im Dokumentabruf), nur solche, die der Dokumentabruf lädt."""
    aus = []
    for feld in aenderungen.DATEIFELDER:
        werte = p.get(feld)
        werte = [werte] if isinstance(werte, dict) else werte if isinstance(werte, list) else []
        for f in werte:
            if not isinstance(f, dict) or f.get("deleted"):
                continue
            kennung = f.get("id") if isinstance(f.get("id"), str) and f["id"] else f.get("accessUrl")
            if kennung in erlaubt:
                aus.append({k: f.get(k) for k in ("name", "fileName", "mimeType")} | {"url": kennung})
    return aus


def zeilen_erzeugen(papers, aemter):
    """Zeilen der Audit-Tabelle und Zähler für die Zusammenfassung. Ohne Netz, ohne Textinhalt im Ergebnis."""
    from . import actors   # erst hier: actors liest das Ergebnis dieses Schritts
    aufgaben, _ = dokumente.aufgaben(papers)
    dateien = collections.defaultdict(set)
    for a in aufgaben:
        dateien[a["vorlage"]].add(a["kennung"])
    status = _zustand()
    stichtag = sessionnet._stichtag()
    zaehler = collections.Counter()
    zeilen = []
    for p in papers:
        if p.get("deleted") or not sessionnet.im_zeitraum(p, stichtag):
            continue
        zaehler["ab_2020"] += 1
        if p.get("underDirectionOf"):
            zaehler["mit_underDirectionOf"] += 1
            continue
        if actors.kategorie(p.get("paperType")) != vorlagenart.VERWALTUNG:
            continue
        zaehler["verwaltung_ohne"] += 1
        if p.get("id") in dokumente.AUSGESCHLOSSEN:
            zaehler["ausgenommen"] += 1
            continue
        url, platz, n, regel = datei_waehlen({**p, "dateiliste": _dateiliste(p, dateien.get(p.get("id"), set()))})
        if not url:
            zaehler["ohne_datei"] += 1
            continue
        z = dict.fromkeys(SPALTEN, "")
        z.update(id=p["id"], reference=p.get("reference"), jahr=jahr_der_vorlage(p), paperType=p.get("paperType"),
                 datei=url, datei_platz=f"auxiliaryFile {platz} von {n}", auswahl=regel,
                 status_dokument=status.get(url) or "nicht im Zustand")
        t = dokumente.text(url) if status.get(url) in dokumente.MIT_TEXT else None
        if t is None:
            z["treffer"] = TREFFER_JE_STATUS.get(status.get(url), NICHT_ABGERUFEN)
        else:
            z.update(text_auswerten(t, aemter))
        z["stelle"] = stelle_kategorie(z)
        zeilen.append(z)
    return zeilen, zaehler


def _abgerufen(z):
    return z["treffer"] in GELESEN or z["treffer"] in FEHLER_ABGERUFEN


def gewichtet(zeilen, treffer):
    """Quote k/n je abgerufene Datei, nach dem Bestand je Jahr gewichtet: Σ_j (Bestand_j / Bestand) · k_j/n_j. Bestand
    sind alle Zeilen (auch ohne Text), n die abgerufenen, k die mit `treffer(z)`. Jahre ohne abgerufene Datei erhalten
    die ungewichtete Quote (Liste). Liefert (Quote, Jahre ohne Abruf) oder None ohne abgerufene Datei."""
    bestand = collections.Counter(z["jahr"] for z in zeilen)
    abgerufen = [z for z in zeilen if _abgerufen(z)]
    if not abgerufen:
        return None
    k_alle = sum(1 for z in abgerufen if treffer(z))
    q, ohne = 0.0, []
    for jahr, b in sorted(bestand.items()):
        nj = [z for z in abgerufen if z["jahr"] == jahr]
        if nj:
            q += b / len(zeilen) * sum(1 for z in nj if treffer(z)) / len(nj)
        else:
            q += b / len(zeilen) * k_alle / len(abgerufen)
            ohne.append(jahr)
    return q, ohne


def _quote(k, n):
    return f"{k} von {n}" + (f" ({100 * k / n:.0f} %)" if n else "")


def zusammenfassung(zeilen, zaehler, quelle_aemter, n_aemter):
    """Zeilen der Konsolenausgabe: Zählungen und Quoten, ohne Kennungen von Vorlagen und ohne Textinhalt."""
    abgerufen = [z for z in zeilen if _abgerufen(z)]
    gelesen = [z for z in zeilen if z["treffer"] in GELESEN]
    kat = collections.Counter(z["stelle"] for z in zeilen)
    nummer = lambda z: z["treffer"] == "kennung"            # noqa: E731
    eindeutig = lambda z: z["stelle"] == STELLE_EINDEUTIG     # noqa: E731
    aus = [f"Ämterliste: {'fehlt' if n_aemter is None else n_aemter} Organisationen mit Präfix at aus {quelle_aemter}",
           f"Vorlagen ab 2020: {zaehler['ab_2020']}, davon mit underDirectionOf {zaehler['mit_underDirectionOf']}; "
           f"Verwaltungsvorlagen ohne underDirectionOf {zaehler['verwaltung_ohne']} (ausgenommen nach § 24 GO NRW "
           f"{zaehler['ausgenommen']}, ohne Datei {zaehler['ohne_datei']}, ausgewertet {len(zeilen)})",
           f"Dateien: Text gelesen {len(gelesen)}, abgerufen (Nenner wie Stufe 6) {len(abgerufen)}, "
           f"noch nicht abgerufen {sum(1 for z in zeilen if z['treffer'] == NICHT_ABGERUFEN)}",
           "Kategorie (stelle): " + "; ".join(f"{k} {kat[k]}" for k in STELLEN if kat[k])]
    k_n, k_e = sum(1 for z in abgerufen if nummer(z)), sum(1 for z in abgerufen if eindeutig(z))
    aus += [f"Nummer im Kopf erkannt (je abgerufene Datei): {_quote(k_n, len(abgerufen))}; Stelle eindeutig "
            f"{_quote(k_e, len(abgerufen))}, mehrdeutig {kat[STELLE_MEHRDEUTIG]}, keine Stelle {kat[STELLE_OHNE]}",
            "Je Jahr (Bestand / abgerufen / Nummer erkannt / Stelle eindeutig):"]
    for jahr in sorted({z["jahr"] for z in zeilen}):
        zj = [z for z in zeilen if z["jahr"] == jahr]
        aj = [z for z in zj if _abgerufen(z)]
        aus.append(f"  {jahr}: {len(zj)} / {len(aj)} / {sum(1 for z in aj if nummer(z))} / "
                   f"{sum(1 for z in aj if eindeutig(z))}")
    for name, f in (("Nummer erkannt", nummer), ("Stelle eindeutig", eindeutig)):
        g = gewichtet(zeilen, f)
        if g:
            aus.append(f"Nach Bestand je Jahr gewichtet, {name}: {100 * g[0]:.0f} % (Schätzung"
                       + (f"; ohne abgerufene Datei, mit der ungewichteten Quote: {', '.join(g[1])}" if g[1] else "")
                       + ")")
    feder = zaehler["mit_underDirectionOf"] + kat[STELLE_EINDEUTIG]
    aus.append(f"Federführung ab 2020: underDirectionOf {zaehler['mit_underDirectionOf']} + PDF-Kopf (Stelle "
               f"eindeutig) {kat[STELLE_EINDEUTIG]} = {_quote(feder, zaehler['ab_2020'])} Vorlagen; jeder Treffer "
               "zählt als richtig (Obergrenze, manuelle Kontrolle offen)")
    return aus


def ergebnis(zeilen):
    """Inhalt von config.AMTSKOPF: je Vorlage mit eindeutiger Stelle Organisation, Datei, Seite und Zeile."""
    return {"version": 1, "methode": "pdf_kopf",
            "vorlagen": {z["id"]: {"organization_id": z["abgleich"], "datei": z["datei"],
                                   "fundstelle": fundstelle(z)}
                         for z in zeilen if z["stelle"] == STELLE_EINDEUTIG}}


def _tsv_schreiben(pfad, zeilen):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(pfad) + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n", **aenderungen.TSV)
        w.writerow(SPALTEN)
        for z in zeilen:
            w.writerow([aenderungen._sauber(z.get(k)) for k in SPALTEN])
    tmp.replace(pfad)


def auswerten():
    """Schritt `amtskopf`: Audit-Tabelle, Ergebnis für actors.responsibilities und Zusammenfassung; keine Anfrage."""
    papers = _papers()
    if papers is None:
        print(f"{config.PAPERS.name} fehlt (zuerst fetch); nichts ausgewertet.")
        return
    aemter, quelle = aemterliste()
    zeilen, zaehler = zeilen_erzeugen(papers, aemter)
    _tsv_schreiben(config.AMTSKOPF_AUDIT, zeilen)
    config.AMTSKOPF.parent.mkdir(parents=True, exist_ok=True)
    _write(config.AMTSKOPF, json.dumps(ergebnis(zeilen), ensure_ascii=False, indent=1) + "\n")
    for z in zusammenfassung(zeilen, zaehler, quelle, None if aemter is None else len(aemter)):
        print(z)
    print(f"Audit: {config.AMTSKOPF_AUDIT}; Ergebnis für die Federführung: {config.AMTSKOPF}")
