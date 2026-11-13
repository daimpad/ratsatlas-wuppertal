"""Anlagen der Vorlagen herunterladen, Text extrahieren, PDF löschen (Schritt `dokumente`; CLAUDE.md 9, 13.11.2026,
„Download der Ratsdokumente“, Punkt 2).

Aufruf: `python3 -m pipeline dokumente`, nach dem Vollabruf (`fetch`), als eigener Prozess. Grundlage sind die Rohdaten
`config.PAPERS` (papers.jsonl): alle Dateien aus `auxiliaryFile` (und `mainFile`, falls vorhanden; Wuppertal liefert
keines, CLAUDE.md 3.1) der Vorlagen im Zeitraum (`sessionnet.im_zeitraum`, `date` ab 01.01.2020), ohne gelöschte
Vorlagen und Dateien. Je Datei:
1. laden über `downloadUrl`, sonst `accessUrl` (http:// auf Hosts der Stadt wird zu https://, `abruf.abrufadresse`);
   nur Hosts der Stadt, lokale Testserver und Testadressen (`abruf.abrufziel_erlaubt`), andere Hosts werden ohne
   Anfrage als `fremder_host` vermerkt;
2. Text extrahieren in einem eigenen Prozess mit Zeitgrenze (pypdf, sonst pdftotext; Seiten durch \\f getrennt);
3. Text gzip-komprimiert unter `config.TEXTE_ORDNER`/<schlüssel>.txt.gz speichern (atomar), das PDF sofort löschen.
   <schlüssel> sind die ersten 32 Hex-Zeichen von SHA-256 der Datei-Kennung (`id`, sonst `accessUrl`).
Texte bleiben lokal bzw. im Zwischenspeicher von GitHub Actions (data/raw/ ist nicht versioniert); sie gelangen nicht
ins Repository, auf die Seite, ins Datenpaket oder in Protokolle (CLAUDE.md 2, 6). Weiterverarbeitung (Amt aus dem
PDF-Kopf, Stufe C) liest sie über `text()` und `texte()`; volltext.py liest bis Phase 3 noch das Bonner texte.jsonl.

Fingerabdruck und Fortsetzung: Der Zustand `config.DOKUMENTE_ZUSTAND` hält je Datei-Kennung den Schlüssel, die
Vorlage, den Status und zwei Fingerabdrücke: `quelle` (SHA-256 über die Angaben der Quelle, die auch
pipeline/aenderungen.py als Ersetzung wertet: `aenderungen.FINGERABDRUCK` ohne Namen, also Adressen, Größe, Prüfsummen,
Typ, Zeitpunkte, `modified`) und den geladenen Inhalt (`groesse`, `sha256`, dazu `modified` der Quelle, `etag`,
`last_modified`). Eine Datei wird geladen, wenn sie neu ist, ihr Quell-Fingerabdruck sich geändert hat (dieselbe
Änderung, die das Änderungsprotokoll als `auxiliaryFile.angaben` oder neue Datei vermerkt; eine bloße Umbenennung lädt
nicht neu) oder ihr Text fehlt; unveränderte werden ohne Anfrage übersprungen. Ein neu geladener Inhalt wird mit dem
vorigen `sha256` verglichen (Protokoll `inhalt`: neu, gleich, geaendert); die Größe und eine SHA-1-Prüfsumme aus der
Quelle werden mit dem geladenen Inhalt abgeglichen (`pruefung`). Der Zustand wird atomar geschrieben, während des
Laufs höchstens alle `config.DOKUMENTE_ZUSTAND_SEKUNDEN` und am Ende jedes Laufs (auch nach Abbruch, Strg+C oder
SIGTERM, das holen() wie Strg+C behandelt); ein abgebrochener oder neu gestarteter Lauf setzt dort fort, nach einem
harten Abbruch (SIGKILL) werden höchstens die Dateien der letzten Spanne erneut geladen. Halbe PDFs aus einem hart
beendeten Lauf löscht der nächste Lauf vor allem anderen (nach der Sperre, siehe unten). Dateien, die nicht mehr in den Rohdaten stehen (Vorlage außerhalb des Zeitraums, Datei
entfernt oder gelöscht), verlieren Text und Eintrag, solange mindestens `fetch.MIN_ANTEIL` der bekannten Dateien noch
in den Rohdaten stehen (sonst Warnung, nichts gelöscht).

Status je Datei: `geladen` (Text vorhanden), `ohne_text` (PDF ohne Textebene, etwa ein Scan; keine Texterkennung),
`kein_pdf` (andere Dateiart, Medientyp ohne Parameter im Protokoll; neuer Versuch erst bei geänderter Quelle; ein
leerer Inhalt, Text, JSON oder XML gilt als verdächtig, `verdacht`, siehe abgewiesen), `verweigert` (HTTP 401/403),
`html` (HTML-Seite statt PDF), `zu_gross` (über `config.DOKUMENTE_MAX_DATEI_BYTES`; laut `size` der
Quelle ohne Anfrage, laut Content-Length nach dem Kopf, sonst nach dem Limit abgebrochen; neuer Versuch erst mit
höherem Limit oder geänderter Quelle), `fehlt` (HTTP 404/410; neuer Versuch nach `config.DOKUMENTE_FEHLT_TAGE`),
`extraktion_fehler` (PDF unlesbar oder Zeitgrenze; neuer Versuch erst bei geänderter Quelle).
Abgewiesen (`verweigert`, `html`, verdächtiges `kein_pdf`; etwa eine nicht öffentliche Anlage oder eine Sperr- oder
Fehlerseite): neuer Versuch nach `config.DOKUMENTE_ABGEWIESEN_TAGE`, am Ende der Reihenfolge.

Freigabe: Anfragen an andere als lokale Adressen nur mit `RATSATLAS_STADT_INFORMIERT=ja` **und**
`RATSATLAS_PDF_FREIGEGEBEN=ja`; ohne beides endet der Lauf vor der ersten Anfrage. Lokale Testserver (abruf.lokal)
sind ausgenommen.

Ratenlogik (eigene, weil die Dokumente nach Entscheidung des Auftraggebers auch tagsüber geladen werden; die
Abrufpolitik der OParl-Listen in pipeline/abruf.py bleibt unverändert):
- eine Verbindung; vor dem Aufräumen und dem ersten Schreiben des Zustands (nicht lokal) dieselbe Sperre wie der
  OParl-Abruf und die Messwerkzeuge (`abruf.sperre_halten`, abruf.lock): Läuft ein anderer Abrufprozess, endet der
  Lauf ohne Anfrage und ohne Zustand oder Arbeitsordner zu ändern;
- Abstand vom Ende einer Antwort bis zur nächsten Anfrage: tagsüber (6–23 Uhr Ortszeit Europe/Berlin,
  `config.DOKUMENTE_TAG`) mindestens 5 s, nachts (23–6 Uhr) mindestens 2 s (`MINDESTABSTAND`; kleinere Werte aus
  `RATSATLAS_DOKUMENTE_ABSTAND_TAG`/`_NACHT` werden mit Hinweis angehoben, nur für lokale Testserver nicht). Maßgeblich
  ist die Uhrzeit beim Warten (`abruf.uhr`). Gezählt ab dem Import wie in abruf.py;
- kein nächtliches Zeitfenster, aber Vorrang des OParl-Abrufs (`config.DOKUMENTE_OPARL_VORRANG`): Im Zeitfenster der
  OParl-Listen (`config.ABRUF_ZEITFENSTER`, 23–1 Uhr) und `config.DOKUMENTE_VORRANG_VORLAUF` Sekunden davor
  (Gesamtfrist, Extraktion, Abstand; also ab etwa 22:47 Uhr) beginnt keine Anfrage; der Lauf endet dort ohne Fehler
  (Art `vorrang`) und gibt so die Sperre für den nächtlichen Abruf frei. Eine Pause nach 429/5xx, die in diese Spanne
  reichte, wird nicht abgewartet: sofort `aufgegeben` (wie abruf.get_json mit fenster_offen_nach);
- Pausen und Abbruch wie `abruf.get_json`: nach HTTP 429, 5xx und CONNECT-Antwort 429/503 wachsende Pausen
  (`config.ABRUF_PAUSEN`, `Retry-After` mindestens eingehalten), danach Art `aufgegeben` (mit `nicht_vor` aus einem
  Retry-After über den Lauf hinaus); andere 4xx (außer 401/403/404/410) Art `http`; Zeitüberschreitung,
  Verbindungsabbruch, abgeschnittene Antwort und eine Antwort, die länger als `config.DOKUMENTE_GESAMTFRIST` dauert
  (geprüft nach jedem Empfang, read1), Art `sperre`; Weiterleitungen werden nicht verfolgt (Art `weiterleitung`);
  Proxy und TLS wie dort. HTTP 401/403, eine HTML-Seite statt eines PDFs (Content-Type text/html oder HTML-Element am
  Anfang ohne „%PDF-“) und eine verdächtige andere Antwort einer einzelnen Datei werden je Datei vermerkt (abgewiesen);
  erst `config.DOKUMENTE_ABGEWIESEN_IN_FOLGE` neu abgewiesene Dateien in Folge beenden den Lauf als mögliche Sperre
  (Art `http` mit 401/403 bzw. `sperrseite`; wie die Messstufen: zwei 401 in Folge). Eine schon zuvor abgewiesene Datei
  zählt dabei nicht mit, die Dateien einer solchen Serie werden im nächsten Lauf (am Ende) erneut angefragt. HTTP
  404/410 einer einzelnen Datei ist kein Abbruch; erst `config.DOKUMENTE_FEHLT_IN_FOLGE` in Folge (Art `http`).
  Lokale Dateifehler beim Schreiben (Platte voll, Berechtigung) enden als Art `platz` bzw. `lokal`, ohne Sperrverdacht;
- vor dem Lauf: 12-Stunden-Regel nach jedem eigenen Abbruch (außer `parallel`, `vorrang`, `grenze`), `nicht_vor` aus
  einem Retry-After, und die Pausen des OParl-Abrufs aus `config.ZUSTAND` (`sessionnet._pause_grund`: Sperrverdacht,
  Retry-After, Pausen nach mehreren Nächten). Ein eigener Abbruch mit möglicher Sperre (`moegliche_sperre`) wird auch
  dort vermerkt (`sperre_verdacht`, `letzter_abbruch`, `nicht_vor`), damit der nächtliche OParl-Abruf dieselbe Pause
  einhält: derselbe Server;
- Obergrenzen je Lauf: Anfragen (`config.DOKUMENTE_MAX_DATEIEN`), Bytes (`config.DOKUMENTE_MAX_BYTES`), Laufzeit
  (`config.DOKUMENTE_MAX_SEKUNDEN`, 0 = ohne), und je Kalendertag Ortszeit über alle Läufe Anfragen
  (`config.DOKUMENTE_MAX_TAG`, Zähler `tag` im Zustand, dem Tag des Laufbeginns zugerechnet; nicht für lokale
  Testserver); erreicht, endet bzw. beginnt der Lauf ohne Fehler (Art `grenze` bzw. übersprungen);
- Plattenplatz: unter `config.DOKUMENTE_MIN_FREI` freiem Platz beginnt kein Lauf und kein weiterer Download (Art
  `platz`, laut, kein Sperrverdacht);
- User-Agent mit Projektadresse und Kontakt wie abruf.py (`abruf._kopf_pruefen`).

Protokolle ohne Dateinamen, Titel, Personennamen und Text (Datenschutz, CLAUDE.md 2): `config.DOKUMENTE_PROTOKOLL` je
Datei (Kennungen der Vorlage und der Datei, Schlüssel, Ergebnis, Zahlen, gekürzte Prüfsumme, Medientyp ohne Parameter,
Meldungen mit Abrufadresse; keine lokalen Pfade) und
`config.DOKUMENTE_STATISTIK` je Lauf. Meldungen von pypdf werden im Extraktionsprozess unterdrückt und nicht
weitergereicht.

Schätzung (Werte nach Messstufe 6): Dauer ≈ N × (Abstand + Antwortzeit), mit N Dateien, Abstand 5 s (tagsüber) bzw.
2 s (nachts), Antwortzeit je Datei aus Stufe 6; Platz ≈ N × mittlere Größe des komprimierten Texts, dazu höchstens ein
PDF (bis `config.DOKUMENTE_MAX_DATEI_BYTES`) gleichzeitig; geladene Bytes je Lauf ≈ Zahl × mittlere PDF-Größe.

Abweichung für den gemeinsamen Kern: neu in Wuppertal, ohne Vorbild im übernommenen Kölner Adapter (sessionnet.py und
abruf.py aus ratsatlas-koeln @d609111 laden keine Anlagen) und in Bonn (Texte aus OParl-Lite, fetch.fetch_texts); siehe
NOTICE.
"""
import csv
import errno
import gzip
import hashlib
import http.client
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from importlib import util as importlib_util

from . import abruf, aenderungen, config, sessionnet
from .fetch import MIN_ANTEIL, _write

MINDESTABSTAND = {"tag": 5.0, "nacht": 2.0}   # Sekunden; für nicht lokale Adressen nicht unterschreitbar
ZUSTAND_VERSION = 1
ARBEIT = "_arbeit"   # Unterordner von TEXTE_ORDNER für das PDF während der Extraktion
STUECK = 64 * 1024
PROTOKOLL_SPALTEN = ["zeitpunkt", "vorlage", "datei", "schluessel", "ergebnis", "http", "bytes", "sekunden", "abstand",
                     "tageszeit", "seiten", "zeichen", "inhalt", "pruefung", "sha256", "meldung"]
STATISTIK_SPALTEN = ["datum", "ende", "dateien", "zu_laden", "angefragt", "geladen", "ohne_text", "unveraendert",
                     "zu_gross", "kein_pdf", "verweigert", "html", "fehlt", "extraktion_fehler", "fremder_host",
                     "ohne_adresse", "entfernt", "anfragen", "fehler", "wiederholungen", "weiterleitungen", "proxy", "bytes", "sekunden",
                     "offen", "frei_mib", "werkzeug"]
# Abbruchsarten ohne Fehler: kein Vermerk für die 12-Stunden-Regel
OHNE_FEHLER = ("parallel", "vorrang", "grenze")
# Abbruchsarten aus lokalen Fehlern (Dateisystem): kein Sperrverdacht, nur die eigene 12-Stunden-Regel
LOKAL = ("lokal", "platz")
# Status, deren Text vorhanden sein muss bzw. die ohne Änderung der Quelle nicht erneut geladen werden
MIT_TEXT = ("geladen", "ohne_text")
ENDGUELTIG = ("kein_pdf", "extraktion_fehler")
# abgewiesene Dateien (`abgewiesen`): erneuter Versuch nach config.DOKUMENTE_ABGEWIESEN_TAGE
ABGEWIESEN = ("verweigert", "html")
# Medientypen einer Antwort, die weder PDF noch HTML ist, aber eher eine Fehler- oder Drosselseite als eine Anlage
# (ebenso ein leerer Inhalt): `kein_pdf` mit `verdacht`
VERDAECHTIGE_TYPEN = ("application/json", "application/xml", "application/problem+json", "application/problem+xml")

# Ende der letzten Antwort (time.monotonic), beim Import gesetzt wie in abruf.py
_letzte = time.monotonic()
_hinweis_abstand = set()
_zaehler = {"anfragen": 0, "fehler": 0, "wiederholungen": 0, "weiterleitungen": 0, "proxy": 0, "bytes": 0,
            "sekunden": 0.0}

# Extraktion im eigenen Prozess (Zeitgrenze, Speichergrenze; Meldungen von pypdf unterdrückt): schreibt den Text nach
# argv[2] (Seiten durch \f getrennt, je Seite ein \f am Ende wie pdftotext) und gibt die Zahl der Seiten aus
_PYPDF = r"""
import logging, sys, warnings
logging.disable(logging.CRITICAL)
warnings.simplefilter("ignore")
from pypdf import PdfReader
r = PdfReader(sys.argv[1])
if r.is_encrypted:
    r.decrypt("")
n = 0
with open(sys.argv[2], "w", encoding="utf-8") as aus:
    for seite in r.pages:
        aus.write((seite.extract_text() or "") + "\f")
        n += 1
print(n)
"""


class ExtraktionFehler(RuntimeError):
    """Der Text einer Datei ließ sich nicht extrahieren (unlesbar, verschlüsselt, Zeitgrenze)."""


def _warnung(text):
    sessionnet._warnung(text)


# --- Zeit und Rate ---------------------------------------------------------------------------------------------------

def tageszeit(jetzt=None):
    """„tag“ (config.DOKUMENTE_TAG, 6–23 Uhr Ortszeit Europe/Berlin) oder „nacht“."""
    von, bis = config.DOKUMENTE_TAG
    h = abruf._ortszeit(jetzt).hour
    return "tag" if von <= h < bis else "nacht"


def abstand_fuer(jetzt=None, lokal=False):
    """Abstand in Sekunden vom Ende einer Antwort bis zur nächsten Anfrage zur Zeit `jetzt`: tagsüber
    config.DOKUMENTE_ABSTAND_TAG, nachts config.DOKUMENTE_ABSTAND_NACHT; für nicht lokale Adressen mindestens
    MINDESTABSTAND (kleinere oder unlesbare Werte werden einmal je Tageszeit mit Hinweis angehoben)."""
    zeit = tageszeit(jetzt)
    wert = config.DOKUMENTE_ABSTAND_TAG if zeit == "tag" else config.DOKUMENTE_ABSTAND_NACHT
    if lokal:
        return wert
    mindestens = MINDESTABSTAND[zeit]
    if isinstance(wert, (int, float)) and math.isfinite(wert) and wert >= mindestens:
        return float(wert)
    if zeit not in _hinweis_abstand:
        print(f"Hinweis: Abstand {wert!r} s ({zeit}) liegt unter dem Mindestabstand für Dokumente; es gilt "
              f"{mindestens:g} s.", file=sys.stderr)
        _hinweis_abstand.add(zeit)
    return mindestens


def vorrang_in(sekunden, jetzt=None):
    """Berührt die Spanne von `jetzt` bis `jetzt` + `sekunden` das Zeitfenster der OParl-Listen, in dem der OParl-Abruf
    Vorrang hat (config.DOKUMENTE_OPARL_VORRANG)? Ohne eingestelltes Zeitfenster nie. Das Fenster beginnt und endet zu
    vollen Stunden (Ortszeit; in Europe/Berlin auch volle Stunden in UTC): geprüft werden der Anfang, jede volle Stunde
    in der Spanne und das Ende."""
    if not config.DOKUMENTE_OPARL_VORRANG or abruf._fenster() is None:
        return False
    jetzt = jetzt or abruf.uhr()
    ende = jetzt + timedelta(seconds=max(0.0, sekunden))
    t = jetzt
    while t < ende:
        if abruf.im_zeitfenster(t):
            return True
        t = t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return abruf.im_zeitfenster(ende)


def vorrang_aktiv(jetzt=None):
    """Hat der OParl-Abruf Vorrang? Ja, wenn sein Zeitfenster offen ist oder innerhalb von
    config.DOKUMENTE_VORRANG_VORLAUF Sekunden beginnt (eine jetzt begonnene Datei endete sonst womöglich erst darin)."""
    return vorrang_in(config.DOKUMENTE_VORRANG_VORLAUF, jetzt)


def freigegeben(url):
    """Anfragen an nicht lokale Adressen nur nach Information der Stadt und eigener Freigabe der PDFs."""
    return abruf.lokal(url) or (os.environ.get("RATSATLAS_STADT_INFORMIERT") == "ja"
                                and os.environ.get("RATSATLAS_PDF_FREIGEGEBEN") == "ja")


def moegliche_sperre(fehler):
    """Wie sessionnet.moegliche_sperre, dazu eine HTML-Seite statt eines PDFs (Art `sperrseite`)."""
    return getattr(fehler, "art", "") == "sperrseite" or sessionnet.moegliche_sperre(fehler)


def statistik():
    return dict(_zaehler)


# --- Dateiinhalt -----------------------------------------------------------------------------------------------------

def pdf_kennung(kopf):
    """„%PDF-“ in den ersten 1024 Bytes (wie explore/oparl_messung.py)."""
    return b"%PDF-" in kopf[:1024]


def html_statt_pdf(kopf, content_type=""):
    """HTML statt PDF (mögliche Sperr- oder Fehlerseite): ohne PDF-Kennung, und Content-Type text/html oder ein
    HTML-Element am Anfang (wie explore/oparl_messung.py)."""
    if pdf_kennung(kopf):
        return False
    return "html" in (content_type or "").lower() or bool(
        re.search(rb"<(?:!doctype|html|head|body)\b", kopf[:1024].lower()))


def medientyp(content_type):
    """Medientyp ohne Parameter (ein Parameter wie name="…" kann einen Dateinamen tragen; nie protokollieren)."""
    return (content_type or "").split(";", 1)[0].strip().lower()[:80]


def verdaechtig(content_type, groesse):
    """Ist eine Antwort, die weder PDF noch HTML ist, eher eine Fehler- oder Drosselseite als eine Anlage? Leerer
    Inhalt, Text (text/*), JSON oder XML."""
    typ = medientyp(content_type)
    return (not groesse or typ.startswith("text/") or typ in VERDAECHTIGE_TYPEN or typ.endswith("+json")
            or typ.endswith("+xml"))


def abgewiesen(eintrag):
    """Wurde die Datei abgewiesen (HTTP 401/403, HTML statt PDF, verdächtige andere Antwort)?"""
    eintrag = eintrag or {}
    return eintrag.get("status") in ABGEWIESEN or (eintrag.get("status") == "kein_pdf" and bool(eintrag.get("verdacht")))


def _laenge(kopf):
    try:
        wert = int((kopf.get("Content-Length") or "").strip())
    except (ValueError, AttributeError):
        return None
    return wert if wert >= 0 else None


def _hole(url, ziel, grenze, pausen=None):
    """Lädt eine Datei nach `ziel` (Abrufpolitik oben; nach abruf.get_json, binär, mit Größenlimit). Liefert ein dict
    mit `status` (ok, fehlt, zu_gross, kein_pdf), `http`, `bytes`, `sekunden`, `abstand`, `tageszeit`, `content_type`,
    `etag`, `last_modified`, `sha256`; sonst abruf.Abbruch."""
    global _letzte
    if not freigegeben(url):
        raise abruf.Abbruch("PDF-Abruf gesperrt: RATSATLAS_STADT_INFORMIERT=ja und RATSATLAS_PDF_FREIGEGEBEN=ja "
                            "erforderlich (CLAUDE.md 5.1, 9)", "gesperrt")
    abruf._kopf_pruefen()
    grund = abruf.adresse_pruefen(url)
    if grund:
        _zaehler["fehler"] += 1
        raise abruf.Abbruch(f"ungültige Adresse ({grund}), nicht gesendet: {url}", "adresse")
    ziel_url = abruf.abrufadresse(url)
    ist_lokal = abruf.lokal(url)
    pausen = config.ABRUF_PAUSEN if pausen is None else pausen
    letzter_fehler = None
    retry_after = 0
    for versuch in range(len(pausen) + 1):
        if not ist_lokal and vorrang_aktiv():
            if letzter_fehler is not None:
                raise abruf._aufgegeben(url, letzter_fehler, versuch, ", Zeitfenster des OParl-Abrufs")
            raise abruf.Abbruch(f"Zeitfenster des OParl-Abrufs ({config.ABRUF_ZEITFENSTER} Uhr): Vorrang, Lauf endet",
                                "vorrang")
        if not ist_lokal:
            abruf.sperre_halten()
        jetzt = abruf.uhr()
        mindestens = abstand_fuer(jetzt, ist_lokal)
        warte = mindestens - (time.monotonic() - _letzte)
        if warte > 0:
            time.sleep(warte)
        start = time.monotonic()
        try:
            req = urllib.request.Request(ziel_url, headers={"User-Agent": config.USER_AGENT,
                                                            "Accept": "application/pdf, */*;q=0.1"})
        except ValueError as e:
            _zaehler["fehler"] += 1
            raise abruf.Abbruch(f"ungültige Adresse, nicht gesendet: {url} ({e})", "adresse") from e
        _zaehler["anfragen"] += 1
        ergebnis = {"http": None, "bytes": 0, "sekunden": 0.0, "abstand": mindestens, "tageszeit": tageszeit(jetzt),
                    "content_type": "", "etag": None, "last_modified": None, "sha256": None}
        gesendet = False
        try:
            with abruf._OEFFNER.open(req, timeout=90) as r:
                gesendet = True
                kopf = r.headers
                ergebnis.update(http=getattr(r, "status", 200), content_type=kopf.get("Content-Type") or "",
                                etag=kopf.get("ETag"), last_modified=kopf.get("Last-Modified"))
                laenge = _laenge(kopf)
                if laenge is not None and laenge > grenze:   # nur der Kopf: nicht lesen
                    ergebnis["status"] = "zu_gross"
                    ergebnis["bytes_angekuendigt"] = laenge
                else:
                    ergebnis.update(_lesen(r, url, ziel, grenze, laenge, start, ergebnis["content_type"]))
        except urllib.error.HTTPError as e:
            _zaehler["fehler"] += 1
            if 300 <= e.code < 400:
                _zaehler["weiterleitungen"] += 1
                _zaehler["sekunden"] += time.monotonic() - start
                ort = e.headers.get("Location") if e.headers else None
                try:
                    weiter = urllib.parse.urljoin(ziel_url, ort) if ort else ""
                except ValueError:
                    weiter = ort
                try:   # nur der Host in der Meldung: der Pfad des Ziels kann einen Dateinamen tragen
                    host = urllib.parse.urlsplit(weiter or "").hostname or "(ohne Host)"
                except ValueError:
                    host = "(unlesbar)"
                raise abruf.Abbruch(f"Weiterleitung HTTP {e.code} auf {host} nicht verfolgt: {url}", "weiterleitung",
                                    weiter, e.code) from e
            if abruf.proxy_ablehnung(e, url):
                _zaehler["sekunden"] += time.monotonic() - start
                raise abruf._proxy_abbruch(url, e.code) from e
            if e.code in (404, 410):
                _zaehler["sekunden"] += time.monotonic() - start
                ergebnis.update(status="fehlt", http=e.code, sekunden=time.monotonic() - start)
                return ergebnis
            if e.code in (401, 403):   # je Datei vermerkt; erst mehrere in Folge sind ein Abbruch (_laden)
                _zaehler["sekunden"] += time.monotonic() - start
                ergebnis.update(status="verweigert", http=e.code, sekunden=time.monotonic() - start)
                return ergebnis
            if e.code != 429 and e.code < 500:
                _zaehler["sekunden"] += time.monotonic() - start
                raise abruf.Abbruch(f"HTTP {e.code}: {url}", "http", code=e.code) from e
            letzter_fehler = e
            retry_after = abruf.retry_after_sekunden(e.headers.get("Retry-After") if e.headers else None)
        except http.client.InvalidURL as e:
            _zaehler["anfragen"] -= 1
            _zaehler["fehler"] += 1
            raise abruf.Abbruch(f"ungültige Adresse, nicht gesendet: {url} ({e})", "adresse") from e
        except ValueError as e:
            if abruf.zertifikatsfehler(e):
                _zaehler["fehler"] += 1
                _zaehler["sekunden"] += time.monotonic() - start
                raise _tls_abbruch(url, e) from e
            if not gesendet:
                _zaehler["anfragen"] -= 1
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException) as e:
            _zaehler["fehler"] += 1
            if abruf.zertifikatsfehler(e):
                _zaehler["sekunden"] += time.monotonic() - start
                raise _tls_abbruch(url, e) from e
            code = abruf.tunnel_status(e)
            if code not in abruf.TUNNEL_UEBERLAST:
                _zaehler["sekunden"] += time.monotonic() - start
                if code in abruf.PROXY_ABLEHNUNG:
                    raise abruf._proxy_abbruch(url, code) from e
                grund = (f"Der Proxy erreicht die Stadt nicht (HTTP {code} beim Verbindungsaufbau)" if code
                         else f"Antwort abgeschnitten oder unlesbar ({type(e).__name__})"
                         if isinstance(e, http.client.HTTPException)
                         else "Zeitüberschreitung oder Verbindungsabbruch")
                raise abruf.Abbruch(f"{grund}, mögliche Sperre: {url} ({e})", "sperre", code=code) from e
            letzter_fehler = e
        except abruf.Abbruch as e:   # aus _lesen (Gesamtfrist, abgeschnitten; lokale Dateifehler)
            if e.art not in LOKAL:
                _zaehler["fehler"] += 1
            _zaehler["sekunden"] += time.monotonic() - start
            raise
        finally:
            _letzte = time.monotonic()
        if letzter_fehler is None or ergebnis.get("status"):
            ergebnis["sekunden"] = time.monotonic() - start
            _zaehler["sekunden"] += ergebnis["sekunden"]
            _zaehler["bytes"] += ergebnis["bytes"]
            return ergebnis
        _zaehler["sekunden"] += time.monotonic() - start
        if versuch < len(pausen):
            if retry_after is None:
                raise abruf._aufgegeben(url, letzter_fehler, versuch + 1, ", Retry-After unlesbar", retry_after)
            if retry_after > max(pausen):
                dauer = f"{retry_after} s" if math.isfinite(retry_after) else "mit mehr als 12 Ziffern"
                raise abruf._aufgegeben(url, letzter_fehler, versuch + 1,
                                        f", Retry-After {dauer} länger als die längste Pause ({max(pausen)} s)",
                                        retry_after)
            pause = max(pausen[versuch], retry_after)
            if not ist_lokal and vorrang_in(pause + config.DOKUMENTE_VORRANG_VORLAUF):
                # wie abruf.get_json (fenster_offen_nach): keine Pause, die die Sperre in das Zeitfenster des
                # OParl-Abrufs hinein hielte; der Prozess endet und gibt sie frei
                raise abruf._aufgegeben(url, letzter_fehler, versuch + 1,
                                        f", Pause {pause:g} s reichte in das Zeitfenster des OParl-Abrufs (Vorrang)",
                                        retry_after)
            _zaehler["wiederholungen"] += 1
            time.sleep(pause)
    raise abruf._aufgegeben(url, letzter_fehler, len(pausen) + 1, retry_after=retry_after)


def _tls_abbruch(url, fehler):
    _zaehler["anfragen"] -= 1
    return abruf.Abbruch(f"Zertifikatsprüfung fehlgeschlagen (TLS): {url} ({fehler}); keine HTTP-Anfrage gesendet",
                         "tls")


def _lokaler_fehler(e, ziel):
    """Abbruch für einen lokalen Dateifehler beim Schreiben der Anlage (Platte voll, keine Berechtigung, Ordner fehlt):
    Art `platz` (ENOSPC, EDQUOT) oder `lokal`, kein Sperrverdacht; die Meldung nennt keinen Pfad."""
    try:
        ziel.unlink(missing_ok=True)
    except OSError:
        pass
    nummer = getattr(e, "errno", None)
    art = "platz" if nummer in (errno.ENOSPC, getattr(errno, "EDQUOT", errno.ENOSPC)) else "lokal"
    grund = os.strerror(nummer) if isinstance(nummer, int) else type(e).__name__
    return abruf.Abbruch(f"lokaler Dateifehler beim Schreiben einer Anlage ({grund}); keine Antwort der Stadt", art)


def _lesen(r, url, ziel, grenze, laenge, start, content_type):
    """Liest die Antwort in Stücken nach `ziel`: höchstens `grenze` Bytes (darüber `zu_gross`, nichts behalten); eine
    HTML-Seite statt PDF endet als `html`, eine andere Dateiart als `kein_pdf` (beide nicht weiter gelesen; ob das ein
    Abbruch ist, entscheidet _laden); weniger Bytes als Content-Length oder länger als die Gesamtfrist: Art `sperre`.
    Gelesen wird mit read1 (höchstens ein Empfangsvorgang je Stück), damit die Gesamtfrist auch bei einer Tropf-Antwort
    nach jedem Empfang geprüft wird. Lokale Dateifehler (Schreiben, Schließen) brechen mit Art `platz` oder `lokal` ab,
    nicht als mögliche Sperre (`_lokaler_fehler`)."""
    sha = hashlib.sha256()
    gelesen = 0
    kopf = b""
    geprueft = False
    lesen = getattr(r, "read1", None) or r.read
    try:
        aus = open(ziel, "wb")
    except OSError as e:
        raise _lokaler_fehler(e, ziel) from None

    def verwerfen():
        try:
            aus.close()
        except OSError:
            pass
        ziel.unlink(missing_ok=True)

    try:
        while True:
            stueck = lesen(STUECK)
            if not stueck:
                break
            gelesen += len(stueck)
            if gelesen > grenze:
                verwerfen()
                return {"status": "zu_gross", "bytes": gelesen}
            if not geprueft:
                kopf += stueck
                if len(kopf) >= 1024:
                    geprueft = True
                    art = _art_pruefen(kopf, content_type)
                    if art:
                        verwerfen()
                        return {"status": art, "bytes": gelesen}
            sha.update(stueck)
            try:
                aus.write(stueck)
            except OSError as e:
                verwerfen()
                raise _lokaler_fehler(e, ziel) from None
            if time.monotonic() - start > config.DOKUMENTE_GESAMTFRIST:
                verwerfen()
                raise abruf.Abbruch(f"Antwort länger als {config.DOKUMENTE_GESAMTFRIST} s (Tropf-Antwort?), mögliche "
                                    f"Sperre: {url}", "sperre")
        try:
            aus.close()
        except OSError as e:
            verwerfen()
            raise _lokaler_fehler(e, ziel) from None
    except BaseException:
        verwerfen()
        raise
    if not geprueft:
        art = _art_pruefen(kopf, content_type)
        if art:
            ziel.unlink(missing_ok=True)
            return {"status": art, "bytes": gelesen}
    if laenge is not None and gelesen < laenge:
        ziel.unlink(missing_ok=True)
        raise abruf.Abbruch(f"Antwort abgeschnitten ({gelesen} von {laenge} Bytes), mögliche Sperre: {url}", "sperre")
    return {"status": "ok", "bytes": gelesen, "sha256": sha.hexdigest()}


def _art_pruefen(kopf, content_type):
    """None für ein PDF; `html` für eine HTML-Seite statt PDF (mögliche Sperr- oder Fehlerseite); sonst `kein_pdf`."""
    if html_statt_pdf(kopf, content_type):
        return "html"
    return None if pdf_kennung(kopf) else "kein_pdf"


# --- Text ------------------------------------------------------------------------------------------------------------

def werkzeug():
    """Werkzeug der Textextraktion: „pypdf <Version>“, sonst „pdftotext“; None, wenn keines vorhanden ist."""
    if importlib_util.find_spec("pypdf") is not None:
        try:
            from importlib.metadata import version
            return f"pypdf {version('pypdf')}"
        except Exception:
            return "pypdf"
    return "pdftotext" if shutil.which("pdftotext") else None


def _grenzen():
    """Speichergrenze des Extraktionsprozesses (2 GiB Adressraum; nur wo resource verfügbar ist)."""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, 2 * 1024 ** 3))
    except (ImportError, ValueError, OSError):
        pass


def extrahieren(pdf, txt, mit=None):
    """Text aus `pdf` nach `txt` (UTF-8, Seiten mit \\f abgeschlossen) in einem eigenen Prozess mit Zeitgrenze
    (config.DOKUMENTE_EXTRAKTION_SEKUNDEN); Ausgaben des Werkzeugs werden verworfen (keine Inhalte im Log). Liefert die
    Zahl der Seiten; sonst ExtraktionFehler."""
    mit = mit or werkzeug()
    if not mit:
        raise ExtraktionFehler("kein Werkzeug (pypdf oder pdftotext)")
    if mit.startswith("pypdf"):
        befehl = [sys.executable, "-c", _PYPDF, pdf.name, txt.name]
    else:
        befehl = ["pdftotext", "-q", "-enc", "UTF-8", pdf.name, txt.name]
    try:
        r = subprocess.run(befehl, cwd=pdf.parent, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           stdin=subprocess.DEVNULL, timeout=config.DOKUMENTE_EXTRAKTION_SEKUNDEN,
                           preexec_fn=_grenzen if os.name == "posix" else None)
    except subprocess.TimeoutExpired as e:
        raise ExtraktionFehler(f"Zeitgrenze {config.DOKUMENTE_EXTRAKTION_SEKUNDEN} s") from e
    if r.returncode != 0 or not txt.exists():
        raise ExtraktionFehler(f"Rückgabewert {r.returncode}")
    if mit.startswith("pypdf"):
        try:
            return int(r.stdout.decode("ascii", "replace").strip().splitlines()[-1])
        except (ValueError, IndexError) as e:
            raise ExtraktionFehler("Seitenzahl unlesbar") from e
    return txt.read_text(encoding="utf-8", errors="replace").count("\f")


def schluessel(kennung):
    """Schlüssel einer Datei: die ersten 32 Hex-Zeichen von SHA-256 der Kennung."""
    return hashlib.sha256(kennung.encode("utf-8")).hexdigest()[:32]


def textpfad(s):
    return config.TEXTE_ORDNER / f"{s}.txt.gz"


def text(kennung):
    """Extrahierter Text einer Datei (Kennung wie in auxiliaryFile) oder None. Nur zur Verarbeitung; nie ausgeben."""
    pfad = textpfad(schluessel(kennung))
    if not pfad.exists():
        return None
    with gzip.open(pfad, "rt", encoding="utf-8") as f:
        return f.read()


def texte():
    """(Vorlage, Datei-Kennung, Text) für alle Dateien mit Text laut Zustand, in der Reihenfolge des Zustands."""
    for kennung, e in sorted(_zustand_lesen().get("dateien", {}).items()):
        if e.get("status") in MIT_TEXT:
            t = text(kennung)
            if t is not None:
                yield e.get("vorlage"), kennung, t


def _text_schreiben(txt, s):
    """Text atomar gzip-komprimiert unter textpfad(s) ablegen; liefert die Zahl der Zeichen."""
    inhalt = txt.read_text(encoding="utf-8", errors="replace")
    ziel = textpfad(s)
    tmp = ziel.with_name(ziel.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write(inhalt)
    os.replace(tmp, ziel)
    return len(inhalt.replace("\f", "").strip())


# --- Zustand und Protokolle ------------------------------------------------------------------------------------------

def _zustand_lesen():
    """Zustand; ohne Datei leer. Unlesbar: beiseitelegen (….defekt, Warnung) und neu beginnen (alle Dateien werden
    erneut geladen; das kostet Anfragen, verliert aber keine Daten der Stadt)."""
    pfad = config.DOKUMENTE_ZUSTAND
    if not pfad.exists():
        return {"version": ZUSTAND_VERSION, "dateien": {}}
    try:
        z = json.loads(pfad.read_text(encoding="utf-8"))
        if not isinstance(z, dict) or not isinstance(z.get("dateien", {}), dict):
            raise ValueError("kein JSON-Objekt mit „dateien“")
    except (ValueError, RecursionError) as e:
        os.replace(pfad, pfad.with_name(pfad.name + ".defekt"))
        _warnung(f"{pfad.name} unlesbar ({e}); beiseitegelegt als {pfad.name}.defekt, neu begonnen")
        return {"version": ZUSTAND_VERSION, "dateien": {}}
    z.setdefault("dateien", {})
    return z


def _zustand_schreiben(z):
    config.DOKUMENTE_ZUSTAND.parent.mkdir(parents=True, exist_ok=True)
    _write(config.DOKUMENTE_ZUSTAND, json.dumps(z, ensure_ascii=False, separators=(",", ":")) + "\n")


def _tsv_anhaengen(pfad, spalten, zeilen):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    neu = not pfad.exists() or pfad.stat().st_size == 0
    with open(pfad, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n", **aenderungen.TSV)
        if neu:
            w.writerow(spalten)
        for z in zeilen:
            w.writerow([aenderungen._sauber(z.get(k)) for k in spalten])


def _protokoll(zeile):
    _tsv_anhaengen(config.DOKUMENTE_PROTOKOLL, PROTOKOLL_SPALTEN,
                   [{"zeitpunkt": abruf.uhr().isoformat(timespec="seconds"), **zeile}])


def _zeit(wert):
    return sessionnet._zeit(wert)


# --- Aufgaben --------------------------------------------------------------------------------------------------------

def quelle_fingerabdruck(datei):
    """SHA-256 über die Angaben der Quelle, die eine Ersetzung anzeigen (aenderungen.FINGERABDRUCK, ohne Namen)."""
    fp = {k: datei[k] for k in aenderungen.FINGERABDRUCK if datei.get(k) is not None}
    return hashlib.sha256(json.dumps(fp, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def aufgaben(papers):
    """Dateien der Vorlagen im Zeitraum, neueste Vorlage zuerst (nach `date`, dann `created`), je Kennung einmal.
    Liefert (Liste der Aufgaben, Zähler für Verweise ohne Objekt)."""
    stichtag = sessionnet._stichtag()
    liste = [p for p in papers if isinstance(p, dict) and not p.get("deleted") and sessionnet.im_zeitraum(p, stichtag)]
    liste.sort(key=lambda p: (str(p.get("date") or ""), str(p.get("created") or ""), str(p.get("id") or "")),
               reverse=True)
    out, gesehen, ohne_objekt = [], set(), 0
    for p in liste:
        for feld in aenderungen.DATEIFELDER:
            werte = p.get(feld)
            werte = [werte] if isinstance(werte, (dict, str)) else werte if isinstance(werte, list) else []
            for f in werte:
                if isinstance(f, str):   # nur ein Verweis auf das File-Objekt: ohne Adresse nicht ladbar
                    ohne_objekt += 1
                    continue
                if not isinstance(f, dict) or f.get("deleted"):
                    continue
                kennung = f.get("id") if isinstance(f.get("id"), str) and f["id"] else f.get("accessUrl")
                if not isinstance(kennung, str) or not kennung or kennung in gesehen:
                    continue
                gesehen.add(kennung)
                url = next((f[k] for k in ("downloadUrl", "accessUrl") if isinstance(f.get(k), str) and f[k]), None)
                groesse = f.get("size") if isinstance(f.get("size"), int) and not isinstance(f.get("size"), bool) \
                    else None
                out.append({"kennung": kennung, "vorlage": p.get("id"), "url": url, "quelle": quelle_fingerabdruck(f),
                            "groesse_quelle": groesse, "sha1_quelle": f.get("sha1Checksum"),
                            "modified": f.get("modified")})
    return out, ohne_objekt


def noetig(eintrag, aufgabe, jetzt):
    """Muss die Datei (erneut) geladen werden? Neu, Quelle geändert, Text fehlt, `fehlt` seit config.DOKUMENTE_FEHLT_TAGE
    oder `zu_gross` unter einem inzwischen höheren Limit, abgewiesen (`abgewiesen`) seit
    config.DOKUMENTE_ABGEWIESEN_TAGE oder als Teil einer Serie, die einen Lauf beendete (`serie`); sonst nicht."""
    if not eintrag or eintrag.get("quelle") != aufgabe["quelle"]:
        return True
    status = eintrag.get("status")
    if abgewiesen(eintrag):   # vor ENDGUELTIG: ein verdächtiges kein_pdf wird wiederholt
        if eintrag.get("serie"):   # gehörte zu einer Serie, die den Lauf beendete: im nächsten Lauf (am Ende) erneut
            return True
        zuletzt = _zeit(eintrag.get("geprueft"))
        return zuletzt is None or jetzt - zuletzt >= timedelta(days=config.DOKUMENTE_ABGEWIESEN_TAGE)
    if status in MIT_TEXT:
        return not textpfad(eintrag.get("schluessel") or schluessel(aufgabe["kennung"])).exists()
    if status == "fehlt":
        zuletzt = _zeit(eintrag.get("geprueft"))
        return zuletzt is None or jetzt - zuletzt >= timedelta(days=config.DOKUMENTE_FEHLT_TAGE)
    if status == "zu_gross":
        return (eintrag.get("grenze") or 0) < config.DOKUMENTE_MAX_DATEI_BYTES and (
            eintrag.get("groesse") is None or eintrag["groesse"] <= config.DOKUMENTE_MAX_DATEI_BYTES)
    if status in ENDGUELTIG:
        return False
    return True


def _aufraeumen(z, kennungen):
    """Halbe PDFs und temporäre Dateien entfernen; Texte und Einträge von Dateien, die nicht mehr in den Rohdaten
    stehen, löschen (nur, wenn mindestens MIN_ANTEIL der bekannten Dateien noch dort stehen). Liefert die Zahl der
    entfernten Einträge."""
    arbeit = config.TEXTE_ORDNER / ARBEIT
    if arbeit.exists():
        shutil.rmtree(arbeit)
    for tmp in config.TEXTE_ORDNER.glob("*.tmp"):
        tmp.unlink(missing_ok=True)
    bekannt = z["dateien"]
    weg = [k for k in bekannt if k not in kennungen]
    if not weg:
        return 0
    if len(bekannt) - len(weg) < MIN_ANTEIL * len(bekannt):
        _warnung(f"Dokumente: {len(weg)} von {len(bekannt)} bekannten Dateien fehlen in den Rohdaten; nichts gelöscht "
                 f"(weniger als {MIN_ANTEIL:.0%} vorhanden, Rohdaten unvollständig?)")
        return 0
    for k in weg:
        e = bekannt.pop(k)
        textpfad(e.get("schluessel") or schluessel(k)).unlink(missing_ok=True)
    return len(weg)


# --- Lauf ------------------------------------------------------------------------------------------------------------

def _einstellungen_pruefen():
    """Zahlen der Einstellungen lesbar und sinnvoll; sonst ValueError vor der ersten Anfrage."""
    for name in ("DOKUMENTE_MAX_DATEIEN", "DOKUMENTE_MAX_BYTES", "DOKUMENTE_MAX_DATEI_BYTES", "DOKUMENTE_MIN_FREI"):
        wert = getattr(config, name)
        if isinstance(wert, bool) or not isinstance(wert, int) or wert < 1:
            raise ValueError(f"config.{name}={wert!r}: ganze Zahl ab 1 erwartet; keine Anfrage gesendet")
    if not isinstance(config.DOKUMENTE_MAX_SEKUNDEN, int) or config.DOKUMENTE_MAX_SEKUNDEN < 0:
        raise ValueError(f"config.DOKUMENTE_MAX_SEKUNDEN={config.DOKUMENTE_MAX_SEKUNDEN!r}: 0 oder mehr; keine Anfrage")
    if config.DOKUMENTE_MIN_FREI < 2 * config.DOKUMENTE_MAX_DATEI_BYTES:
        raise ValueError("config.DOKUMENTE_MIN_FREI muss mindestens doppelt so groß sein wie "
                         "config.DOKUMENTE_MAX_DATEI_BYTES; keine Anfrage gesendet")


def frei():
    """Freier Platz in Bytes am Ort von config.TEXTE_ORDNER."""
    ort = config.TEXTE_ORDNER
    while not ort.exists():
        ort = ort.parent
    return shutil.disk_usage(ort).free


def _pause_grund(z, lokal):
    """Grund, den Lauf ohne Anfrage zu überspringen: eigener Abbruch vor weniger als 12 Stunden, eigenes `nicht_vor`,
    Pause des OParl-Abrufs (sessionnet._pause_grund, auch ein unlesbarer Zustand dort). Lokal: None."""
    if lokal:
        return None
    jetzt = abruf.uhr()
    letzter = z.get("letzter_abbruch") or {}
    if letzter:
        zuletzt = _zeit(letzter.get("zuletzt"))
        if zuletzt is None or zuletzt > jetzt or jetzt - zuletzt < sessionnet.SPERRE_GLEICHE_NACHT:
            return f"Abbruch der Dokumente ({letzter.get('art') or 'unbekannt'}) vor weniger als 12 Stunden"
    nicht_vor = z.get("nicht_vor")
    if nicht_vor is not None:
        t = _zeit(nicht_vor)
        if t is None or jetzt < t:
            return f"Retry-After der Stadt: kein Abruf vor {nicht_vor}"
    try:
        grund = sessionnet._pause_grund(sessionnet._zustand(), lokal)
    except Exception as e:   # unlesbar oder ungeprüfte Werte (der OParl-Abruf prüft sie erst beim nächsten Lauf)
        return f"Zustand des OParl-Abrufs nicht prüfbar ({type(e).__name__}: {e})"
    return f"Pause des OParl-Abrufs: {grund}" if grund else None


def _abbruch_vermerken(e, z):
    """Abbruch im eigenen Zustand (12-Stunden-Regel, nicht_vor) und, bei möglicher Sperre, im Zustand des OParl-Abrufs
    vermerken (derselbe Server). `parallel`, `vorrang` und `grenze` sind kein Fehler."""
    art = getattr(e, "art", "")
    if art in OHNE_FEHLER:
        print(f"Dokumente: Lauf beendet ({art}): {e}")
        return
    jetzt = abruf.uhr()
    zeit = jetzt.isoformat(timespec="seconds")
    z["letzter_abbruch"] = {"zuletzt": zeit, "art": art, "code": getattr(e, "code", None), "meldung": str(e)[:300]}
    nicht_vor = getattr(e, "nicht_vor", None)
    if nicht_vor is not None:
        alt = _zeit(z.get("nicht_vor"))
        if alt is None or nicht_vor > alt:
            z["nicht_vor"] = nicht_vor.isoformat(timespec="seconds")
    if moegliche_sperre(e):
        try:
            oparl = sessionnet._zustand()
        except sessionnet.ZustandUnlesbar as f:   # der OParl-Abruf läuft ohnehin nicht, bis die Datei geprüft ist
            _warnung(f"Dokumente: Abbruch mit möglicher Sperre ({art}) nicht im Zustand des OParl-Abrufs vermerkt "
                     f"({f}). {e}"[:500])
            return
        verdacht = oparl.get("sperre_verdacht") or {}
        meldung = f"Dokumente: {e}"[:300]
        neu = {"sperre_verdacht": {"naechte": verdacht.get("naechte", 0) + 1, "zuletzt": zeit, "art": art,
                                   "code": getattr(e, "code", None), "meldung": meldung},
               "letzter_abbruch": {"zuletzt": zeit, "art": art, "code": getattr(e, "code", None), "meldung": meldung}}
        if nicht_vor is not None:
            alt = _zeit(oparl.get("nicht_vor"))
            if alt is None or nicht_vor > alt:
                neu["nicht_vor"] = nicht_vor.isoformat(timespec="seconds")
        sessionnet._zustand_aendern(**neu)
        _warnung(f"Dokumente: Abbruch mit möglicher Sperre ({art}); auch der OParl-Abruf pausiert (12-Stunden-Regel, "
                 f"Zähler der Nächte). {e}"[:500])
    else:
        _warnung(f"Dokumente: Abbruch ({art or type(e).__name__}); nächster Lauf frühestens in 12 Stunden. {e}"[:500])


def _sigterm(signum, frame):
    """SIGTERM (Ende eines Actions-Jobs, kill, systemd) wie Strg+C: SystemExit, damit die finally-Blöcke das PDF löschen
    und den Zustand schreiben."""
    raise SystemExit(128 + signum)


def holen():
    """Schritt `dokumente`: siehe Moduldoku. Während des Laufs beendet SIGTERM den Prozess über SystemExit (Aufräumen
    wie bei Strg+C); nur im Hauptthread, sonst bleibt die Behandlung unverändert."""
    _einstellungen_pruefen()
    gesetzt, alt = False, None
    if threading.current_thread() is threading.main_thread():
        try:
            alt = signal.signal(signal.SIGTERM, _sigterm)
            gesetzt = True
        except (ValueError, OSError):
            pass
    try:
        _holen()
    finally:
        if gesetzt:   # None: die vorige Behandlung stammte nicht aus Python, dann die Vorgabe
            signal.signal(signal.SIGTERM, signal.SIG_DFL if alt is None else alt)


def _tag(jetzt):
    """Kalendertag in Ortszeit Europe/Berlin (Tagesgrenze der Anfragen)."""
    return abruf._ortszeit(jetzt).date().isoformat()


def _heute_angefragt(z, tag):
    """Anfragen des Kalendertags `tag` laut Zustand (`tag`: Datum und Zahl; ein anderer Tag oder unlesbar: 0)."""
    t = z.get("tag") if isinstance(z.get("tag"), dict) else {}
    n = t.get("anfragen")
    return n if t.get("datum") == tag and isinstance(n, int) and not isinstance(n, bool) and n >= 0 else 0


def _holen():
    lauf_start = time.monotonic()
    zaehler_vorher = statistik()
    werte = {k: 0 for k in STATISTIK_SPALTEN if k not in ("datum", "ende", "frei_mib", "werkzeug")}
    werte.update(datum=abruf.uhr().isoformat(timespec="seconds"), ende="ok", werkzeug=werkzeug() or "")
    if not config.PAPERS.exists():
        print(f"Dokumente: {config.PAPERS.name} fehlt (erst `fetch`); keine Anfrage.")
        return
    papers = [json.loads(z) for z in config.PAPERS.read_text(encoding="utf-8").splitlines() if z.strip()]
    liste, werte["ohne_adresse"] = aufgaben(papers)
    werte["dateien"] = len(liste)
    # Sperre vor jedem Schreiben (Aufräumen des Arbeitsordners, Zustand): Ein zweiter Lauf greift nicht in einen
    # laufenden ein, sondern endet ohne Anfrage und ohne Änderung. Nur lokale Testserver ohne Sperre.
    lokal = abruf.lokal(config.OPARL_BODY) and all(abruf.lokal(a["url"]) for a in liste if a["url"])
    if not lokal:
        try:
            abruf.sperre_halten()
        except abruf.Abbruch as e:
            werte["ende"] = "uebersprungen"
            print(f"Dokumente übersprungen ({e}); Zustand und Arbeitsordner unverändert.")
            _tsv_anhaengen(config.DOKUMENTE_STATISTIK, STATISTIK_SPALTEN, [werte])
            return
    config.TEXTE_ORDNER.mkdir(parents=True, exist_ok=True)
    z = _zustand_lesen()
    werte["entfernt"] = _aufraeumen(z, {a["kennung"] for a in liste})
    if werte["entfernt"]:
        _zustand_schreiben(z)
    jetzt = abruf.uhr()
    tag = _tag(jetzt)
    zu_laden, wiederholen = [], []
    for a in liste:
        e = z["dateien"].get(a["kennung"])
        if not a["url"]:
            werte["ohne_adresse"] += 1
        elif not abruf.abrufziel_erlaubt(a["url"]):   # fremder Host: keine Anfrage
            werte["fremder_host"] += 1
            _eintrag(z, a, "fremder_host")
        elif a["groesse_quelle"] is not None and a["groesse_quelle"] > config.DOKUMENTE_MAX_DATEI_BYTES:
            if noetig(e, a, jetzt):   # laut Quelle zu groß: ohne Anfrage
                werte["zu_gross"] += 1
                _eintrag(z, a, "zu_gross", groesse=a["groesse_quelle"], grenze=config.DOKUMENTE_MAX_DATEI_BYTES)
                _protokoll({"vorlage": a["vorlage"], "datei": a["kennung"], "schluessel": schluessel(a["kennung"]),
                            "ergebnis": "zu_gross", "bytes": 0, "meldung": "laut size der Quelle, ohne Anfrage"})
        elif noetig(e, a, jetzt):
            # abgewiesene Dateien ans Ende: eine einzelne dauerhaft abgewiesene Datei blockiert so keinen Lauf
            (wiederholen if abgewiesen(e) and e.get("quelle") == a["quelle"] else zu_laden).append(a)
        else:
            werte["unveraendert"] += 1
    zu_laden += wiederholen
    werte["zu_laden"] = len(zu_laden)
    _zustand_schreiben(z)
    try:
        werte["frei_mib"] = frei() // 1024 ** 2
        if not zu_laden:
            print(f"Dokumente: {len(liste)} Dateien, nichts zu laden.")
            return
        grund = None
        if not all(freigegeben(a["url"]) for a in zu_laden):
            grund = ("PDF-Abruf gesperrt (RATSATLAS_STADT_INFORMIERT=ja und RATSATLAS_PDF_FREIGEGEBEN=ja "
                     "erforderlich)")
        elif not werte["werkzeug"]:
            raise ValueError("Weder pypdf noch pdftotext vorhanden (pip install pypdf); keine Anfrage gesendet")
        elif frei() < config.DOKUMENTE_MIN_FREI:
            grund = f"zu wenig Platz ({frei() // 1024 ** 2} MiB frei, mindestens {config.DOKUMENTE_MIN_FREI // 1024 ** 2})"
            werte["ende"] = "platz"
            _warnung(f"Dokumente: {grund}; keine Anfrage")
        else:
            grund = _pause_grund(z, lokal)
            if not grund and not lokal:
                if vorrang_aktiv():
                    grund = f"Zeitfenster des OParl-Abrufs ({config.ABRUF_ZEITFENSTER} Uhr) beginnt oder läuft, Vorrang"
                elif _heute_angefragt(z, tag) >= config.DOKUMENTE_MAX_TAG:
                    grund = (f"Tagesgrenze erreicht ({_heute_angefragt(z, tag)} Anfragen am {tag}, "
                             "RATSATLAS_DOKUMENTE_MAX_TAG)")
        if grund:
            if werte["ende"] == "ok":
                werte["ende"] = "uebersprungen"
            print(f"Dokumente übersprungen ({grund}); {len(zu_laden)} Dateien offen.")
            return
        _laden(z, zu_laden, werte, lauf_start, None if lokal else config.DOKUMENTE_MAX_TAG - _heute_angefragt(z, tag))
    finally:
        nachher = statistik()
        for k in ("anfragen", "fehler", "wiederholungen", "weiterleitungen", "proxy", "bytes"):
            werte[k] = nachher[k] - zaehler_vorher[k]
        werte["sekunden"] = round(nachher["sekunden"] - zaehler_vorher["sekunden"], 1)
        if werte["anfragen"]:   # Tageszähler (dem Tag des Laufbeginns zugerechnet)
            z["tag"] = {"datum": tag, "anfragen": _heute_angefragt(z, tag) + werte["anfragen"]}
        _zustand_schreiben(z)
        werte["offen"] = sum(1 for a in liste if a["url"] and abruf.abrufziel_erlaubt(a["url"])
                             and noetig(z["dateien"].get(a["kennung"]), a, abruf.uhr()))
        _tsv_anhaengen(config.DOKUMENTE_STATISTIK, STATISTIK_SPALTEN, [werte])
        arbeit = config.TEXTE_ORDNER / ARBEIT
        if arbeit.exists():
            shutil.rmtree(arbeit, ignore_errors=True)


def _eintrag(z, a, status, **mehr):
    alt = z["dateien"].get(a["kennung"]) or {}
    z["dateien"][a["kennung"]] = {**{k: alt[k] for k in ("sha256", "groesse") if k in alt},
                                  "schluessel": schluessel(a["kennung"]), "vorlage": a["vorlage"],
                                  "quelle": a["quelle"], "status": status, "modified": a["modified"],
                                  "geprueft": abruf.uhr().isoformat(timespec="seconds"), **mehr}


def _grenze_erreicht(start, lauf_start, tagesrest=None):
    """Obergrenze je Lauf oder je Kalendertag erreicht? `start`: Zähler zu Beginn des Laufs; `tagesrest`: Anfragen, die
    an diesem Tag noch erlaubt sind (None: ohne Tagesgrenze, lokale Testserver). Liefert den Grund oder None."""
    jetzt = statistik()
    angefragt = jetzt["anfragen"] - start["anfragen"]
    if angefragt >= config.DOKUMENTE_MAX_DATEIEN:
        return f"{angefragt} Anfragen (RATSATLAS_DOKUMENTE_MAX_DATEIEN)"
    if tagesrest is not None and angefragt >= tagesrest:
        return f"Tagesgrenze von {config.DOKUMENTE_MAX_TAG} Anfragen (RATSATLAS_DOKUMENTE_MAX_TAG)"
    if jetzt["bytes"] - start["bytes"] >= config.DOKUMENTE_MAX_BYTES:
        return "Bytes je Lauf erreicht (RATSATLAS_DOKUMENTE_MAX_BYTES)"
    if config.DOKUMENTE_MAX_SEKUNDEN and time.monotonic() - lauf_start >= config.DOKUMENTE_MAX_SEKUNDEN:
        return "Laufzeit erreicht (RATSATLAS_DOKUMENTE_MAX_SEKUNDEN)"
    return None


def _abgewiesen_abbruch(serie, r, status):
    """Abbruch nach config.DOKUMENTE_ABGEWIESEN_IN_FOLGE neu abgewiesenen Dateien in Folge: HTTP 401/403 als Art `http`
    (mögliche Sperre, SPERRE_HTTP), HTML oder verdächtige Antwort als Art `sperrseite`."""
    text = f"{len(serie)} Dateien in Folge abgewiesen (zuletzt {status}"
    if status == "verweigert":
        return abruf.Abbruch(f"{text}, HTTP {r['http']}), mögliche Sperre", "http", code=r["http"])
    return abruf.Abbruch(f"{text}, {medientyp(r['content_type']) or 'ohne Medientyp'}; mögliche Sperr- oder "
                         "Fehlerseite)", "sperrseite")


def _laden(z, zu_laden, werte, lauf_start, tagesrest=None):
    """Lädt die Dateien der Reihe nach (Obergrenzen, Platz, Abbruch). Das Protokoll erhält je Datei eine Zeile; der
    Zustand wird höchstens alle config.DOKUMENTE_ZUSTAND_SEKUNDEN geschrieben (und am Ende in holen, auch nach Abbruch).
    Abgewiesene Dateien (HTTP 401/403, HTML statt PDF, verdächtige Antwort) werden je Datei vermerkt; erst
    config.DOKUMENTE_ABGEWIESEN_IN_FOLGE neu abgewiesene in Folge beenden den Lauf als mögliche Sperre. Eine Datei, die
    schon zuvor abgewiesen war und es wieder ist, zählt nicht (setzt die Zählung aber auch nicht zurück): Sie steht am
    Ende der Reihenfolge, und ein Server, der alles abweist, fällt schon an den neuen Dateien davor auf."""
    arbeit = config.TEXTE_ORDNER / ARBEIT
    arbeit.mkdir(parents=True, exist_ok=True)
    pdf, txt = arbeit / "datei.pdf", arbeit / "datei.txt"
    start = statistik()
    fehlt_in_folge = 0
    serie = []   # Kennungen neu abgewiesener Dateien in Folge
    gesichert = time.monotonic()

    def sichern():
        nonlocal gesichert
        if time.monotonic() - gesichert >= config.DOKUMENTE_ZUSTAND_SEKUNDEN:
            _zustand_schreiben(z)
            gesichert = time.monotonic()

    try:
        for a in zu_laden:
            grenze = _grenze_erreicht(start, lauf_start, tagesrest)
            if grenze:
                raise abruf.Abbruch(f"Obergrenze: {grenze}", "grenze")
            if frei() < config.DOKUMENTE_MIN_FREI:
                raise abruf.Abbruch(f"zu wenig Platz ({frei() // 1024 ** 2} MiB frei)", "platz")
            s = schluessel(a["kennung"])
            zeile = {"vorlage": a["vorlage"], "datei": a["kennung"], "schluessel": s}
            vorher_abgewiesen = abgewiesen(z["dateien"].get(a["kennung"]))
            for p in (pdf, txt):
                p.unlink(missing_ok=True)
            try:
                r = _hole(a["url"], pdf, config.DOKUMENTE_MAX_DATEI_BYTES)
            except abruf.Abbruch as e:
                pdf.unlink(missing_ok=True)
                if e.art not in OHNE_FEHLER:
                    _protokoll({**zeile, "ergebnis": f"abbruch ({e.art})", "http": e.code, "meldung": str(e)[:300]})
                raise
            werte["angefragt"] += 1
            zeile.update(http=r["http"], bytes=r["bytes"], sekunden=round(r["sekunden"], 2), abstand=r["abstand"],
                         tageszeit=r["tageszeit"])
            status = r["status"]
            verdacht = status == "kein_pdf" and verdaechtig(r["content_type"], r["bytes"])
            ist_abgewiesen = status in ABGEWIESEN or verdacht
            fehlt_in_folge = fehlt_in_folge + 1 if status == "fehlt" else 0
            if not ist_abgewiesen:
                serie = []
            elif not vorher_abgewiesen:
                serie.append(a["kennung"])
            if status != "ok":
                pdf.unlink(missing_ok=True)
                textpfad(s).unlink(missing_ok=True)
                mehr = {"groesse": r.get("bytes_angekuendigt") or r["bytes"],
                        "grenze": config.DOKUMENTE_MAX_DATEI_BYTES} if status == "zu_gross" else {}
                if verdacht:
                    mehr["verdacht"] = True
                _eintrag(z, a, status, http=r["http"], **mehr)
                werte[status] += 1
                _protokoll({**zeile, "ergebnis": status + (" (verdächtig)" if verdacht else ""),
                            "meldung": medientyp(r["content_type"]) if status in ("kein_pdf", "html") else ""})
                if len(serie) >= config.DOKUMENTE_ABGEWIESEN_IN_FOLGE:
                    for k in serie:   # im nächsten Lauf erneut (am Ende), nicht erst nach der Frist
                        z["dateien"][k]["serie"] = True
                    raise _abgewiesen_abbruch(serie, r, status)
                if fehlt_in_folge >= config.DOKUMENTE_FEHLT_IN_FOLGE:
                    raise abruf.Abbruch(f"{fehlt_in_folge} Dateien in Folge mit HTTP 404/410 (Adressen prüfen)",
                                        "http", code=r["http"])
                sichern()
                continue
            vorher = (z["dateien"].get(a["kennung"]) or {}).get("sha256")
            inhalt = "neu" if not vorher else "gleich" if vorher == r["sha256"] else "geaendert"
            pruefung = _pruefung(a, r, pdf)
            try:
                seiten = extrahieren(pdf, txt, werte["werkzeug"])
                zeichen = _text_schreiben(txt, s)
                status = "geladen" if zeichen else "ohne_text"
            except ExtraktionFehler as e:
                seiten, zeichen, status = None, None, "extraktion_fehler"
                textpfad(s).unlink(missing_ok=True)
                zeile["meldung"] = str(e)[:120]
            finally:
                pdf.unlink(missing_ok=True)   # PDF sofort löschen
                txt.unlink(missing_ok=True)
            _eintrag(z, a, status, http=r["http"], groesse=r["bytes"], sha256=r["sha256"], etag=r["etag"],
                     last_modified=r["last_modified"], seiten=seiten, zeichen=zeichen, werkzeug=werte["werkzeug"])
            werte[status] += 1
            _protokoll({**zeile, "ergebnis": status, "seiten": seiten, "zeichen": zeichen, "inhalt": inhalt,
                        "pruefung": pruefung, "sha256": r["sha256"][:16]})
            sichern()
    except abruf.Abbruch as e:
        werte["ende"] = e.art or "abbruch"
        _abbruch_vermerken(e, z)
        if os.environ.get("RATSATLAS_STRENG") == "ja" and e.art not in OHNE_FEHLER:
            raise
    except Exception as e:
        werte["ende"] = "programmfehler"
        z["letzter_abbruch"] = {"zuletzt": abruf.uhr().isoformat(timespec="seconds"), "art": "programmfehler",
                                "code": None, "meldung": f"{type(e).__name__}: {e}"[:300]}
        raise
    except BaseException:   # SystemExit (SIGTERM), KeyboardInterrupt: aufräumen, Zustand schreibt holen
        werte["ende"] = "beendet"
        raise
    finally:
        for p in (pdf, txt):
            p.unlink(missing_ok=True)
    if werte["ende"] == "ok" or werte["ende"] in OHNE_FEHLER:
        z.pop("letzter_abbruch", None)
        nicht_vor = _zeit(z.get("nicht_vor"))
        if nicht_vor is not None and nicht_vor <= abruf.uhr():
            z.pop("nicht_vor", None)
    print(f"Dokumente: {werte['angefragt']} Dateien mit Antwort, {werte['geladen']} mit Text, {werte['ohne_text']} "
          f"ohne Text, {werte['unveraendert']} unverändert, Ende {werte['ende']}.")


def _pruefung(a, r, pdf):
    """Abgleich mit der Quelle: Größe (`size`) und SHA-1 (`sha1Checksum`), soweit angegeben: passt, abweichend (mit
    Angabe) oder ohne_angabe."""
    abweichend = []
    if a["groesse_quelle"] is not None and a["groesse_quelle"] != r["bytes"]:
        abweichend.append("size")
    if isinstance(a["sha1_quelle"], str) and a["sha1_quelle"]:
        sha1 = hashlib.sha1()
        with open(pdf, "rb") as f:
            for stueck in iter(lambda: f.read(STUECK), b""):
                sha1.update(stueck)
        if sha1.hexdigest().lower() != a["sha1_quelle"].strip().lower():
            abweichend.append("sha1Checksum")
    if abweichend:
        return "abweichend: " + ", ".join(abweichend)
    return "passt" if a["groesse_quelle"] is not None or a["sha1_quelle"] else "ohne_angabe"
