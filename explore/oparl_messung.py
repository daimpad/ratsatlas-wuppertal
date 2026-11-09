"""Messung der Wuppertaler OParl-API (Phase 1) – nur gestuft nach explore/STUFEN.md, jede Stufe erst nach Freigabe.

Abgeleitet aus ratsatlas-koeln @d609111 (explore/oparl_messung.py). Unverändert übernommen sind Abrufpolitik,
Sperren, Laufprotokoll, Markerdatei, Signalbehandlung und Filterurteil. Abweichungen von Köln (für den späteren
gemeinsamen Kern notiert):
- Endpunkte https://oparl.wuppertal.de/oparl/system und …/bodies/0001 (CLAUDE.md 3.1); Objekt-IDs und links.next mit
  http:// werden vor dem Abruf auf https:// umgeschrieben (abruf.abrufadresse), als Schlüssel bleiben sie unverändert
- 100 Objekte je Seite statt 25; `kennzahlen` prüft nur modified_since (unkodiert und URL-kodiert), nicht mehr
  created_since/created_until und limit (die Datumsgrenze misst `umfang`, die Seitengröße steht schon fest)
- neues Kommando `umfang`: letzte Seite der Vorlagenliste und Seite mit der Datumsgrenze 01.01.2020 per Bisektion über
  konstruierte Seitenadressen `?page=N` (nur, wenn links.next der ersten Seite genau diese Form hat), Sortierung nach
  `date`, Ende von links.next; mit `--liste meeting|person` nur das Listenende (Gesamtzahl), wenn `pagination` keine
  Gesamtzahl liefert, Bereich `--ende-seiten` dann Pflicht
- `sitzungen` erfasst je Seite Zeitraum (`start`), künftige Sitzungen und die Sortierung nach `start`, Abdeckung von
  `agendaItem.result` getrennt nach vergangenen und künftigen Sitzungen
- `kennzahlen` schreibt vom System-Objekt nur, ob `contactEmail` und `contactName` gesetzt sind (bei contactEmail mit
  Domain), keine Werte (CLAUDE.md 2 und 3.1: die dort genannte Person wird nicht veröffentlicht)
- Anfragen nur an Hosts der Stadt (abruf.stadt_host) und an die Hosts von SYSTEM und BODY; ein lokaler Probelauf
  (SYSTEM und BODY lokal) fragt nur lokale Adressen, ein Lauf gegen die Stadt nie lokale (Abbruch der Art `adresse`)
- RATSATLAS_ZEITFENSTER darf nur für Testadressen (Loopback, Domain .invalid) leer oder weiter als 23–1 Uhr sein
- `stichprobe` ohne Jahresfilter: Seiten gleichmäßig über 1 bis zur letzten Seite mit Vorlagen ab 2020 (aus `umfang`),
  weil die Wirkung von created_* in Wuppertal ungemessen ist (in Köln unkodiert übergangen)
- `organisationen` zählt Präfixe der Kennungen (organizations/gr/<n>, organizations/at/<n>, weitere)
- `pdf-koepfe` (Stufe 6) liest den Kopf einer Datei aus `auxiliaryFile` (Wuppertal liefert kein `mainFile`) von
  Verwaltungsvorlagen ohne `underDirectionOf`: Datei nach Name als Vorlage erkannt, sonst die erste (datei_waehlen,
  Annahme); Seite 1, bei leerem Text Seite 2; alle Kandidaten (Ressort, Amt; als Annahme Stadtbetrieb, Geschäftsbereich,
  Eigenbetrieb) mit Zeile und Lage zum ersten Abschnitt, Regel für den federführenden Kandidaten (Annahme); Abgleich mit
  organizations/at; Messwerte je Datei ohne Textinhalt (Bytes, Seiten, Textebene, Antwortzeit aus dem Abrufprotokoll,
  Klasse des PDF-Erzeugers); Größengrenze über abruf.MAX_BYTES während des Kommandos (abruf.py unverändert)

Aufruf (Reihenfolge und genaue Befehle mit Obergrenzen: explore/STUFEN.md):
  ... python3 explore/oparl_messung.py test           (genau 3 Anfragen: System, Body, erste Seite der Vorlagen)
  ... python3 explore/oparl_messung.py kennzahlen     (8 Anfragen)
  ... python3 explore/oparl_messung.py umfang [--grenze-seiten 50 150] [--ende-seiten 240 250] [--stichtag 2020-01-01]
  ... python3 explore/oparl_messung.py umfang --liste meeting|person --ende-seiten V B   (nur ohne totalElements)
  ... python3 explore/oparl_messung.py organisationen [--seiten 5]
  ... python3 explore/oparl_messung.py sitzungen [--seiten 2]
  ... python3 explore/oparl_messung.py stichprobe [--seiten 8] [--grenzseite G]
  ... python3 explore/oparl_messung.py pdf-koepfe [--anzahl 100]
Jede Liste hat eine Seitengrenze (--seiten, Vorgabe je Kommando; 0 = ohne Grenze, nur ausdrücklich).
Ohne RATSATLAS_MESSUNG_FREIGEGEBEN=ja bricht jedes Kommando vor der ersten Anfrage an die Stadt ab (eigene Freigabe je
Stufe, CLAUDE.md 9; der regelmäßige Abruf in pipeline/ bleibt bis zur Information der Stadt gesperrt); lokale Testserver (http://127.0.0.1, http://localhost) sind ausgenommen
(explore/testserver.py). Anfragen an die Stadt nur im Zeitfenster 23–1 Uhr Ortszeit (RATSATLAS_ZEITFENSTER), geprüft vor
jeder Anfrage; ein leerer Wert oder ein weiteres Fenster gilt nur für Testadressen (testadresse), sonst als außerhalb. `pdf-koepfe` lädt PDFs und läuft zusätzlich nur mit RATSATLAS_PDF_FREIGEGEBEN=ja (eigene Freigabe der
Stufe 6 vor der Anfrage an die Stadt, CLAUDE.md 9; Lizenz der PDFs offen, CLAUDE.md 8).
Für Anfragen an die Stadt gelten strenge Vorgaben (sichere_vorgaben): keine Wiederholung nach 429/5xx
(RATSATLAS_WIEDERHOLUNGEN, Vorgabe 0), höchstens 5 s je Antwort (RATSATLAS_MAX_DAUER, Vorgabe 5), mindestens 2 s Abstand
zwischen zwei Anfragen (RATSATLAS_ABSTAND, Vorgabe 2); RATSATLAS_MAX_ANFRAGEN und RATSATLAS_KONTAKT (ohne Platzhalter)
sind Pflicht. Lockerere Werte werden vor der ersten Anfrage abgelehnt.
Parameter werden ohne URL-Kodierung angehängt (SessionNet in Wuppertal laut meine-stadt-transparent: 404 bei %3A/%2B,
Stand ca. 2021, heutige Gültigkeit offen; Quelle explore/ergebnisse/sessionnet_befunde.tsv in ratsatlas-koeln; Köln
dagegen: Zeitfilter wirken nur URL-kodiert); `kennzahlen` prüft beide Formen einmal und beurteilt modified_since
ohne weitere Anfrage aus dem Vergleich mit der ungefilterten ersten Seite (_filter_urteil): Die Grenze ist der Median von
`modified` der ersten Hälfte dieser Seite; „ja“ nur, wenn eine Vorlage, die dort unter der Grenze lag, in der gefilterten
Antwort fehlt. Eine 401 auf einen Parametertest gilt als „Parameter abgelehnt“, zwei 401 in Folge brechen ab.
Abruf über explore/abruf.py (eine Verbindung, Abstand ≥ 2 s nach Ende der Antwort, auch vor der ersten Anfrage
eines Prozesses, Cache, Protokoll, Obergrenze RATSATLAS_MAX_ANFRAGEN, Weiterleitungen werden nicht verfolgt).
Paginierung über links.next; Schutz vor Schleifen: Abbruch bei wiederholter Folgeadresse und bei einer Seite ohne neue
Kennungen. Konstruierte Seitenadressen nur in `umfang` und `stichprobe`, und nur in der Form, die links.next der ersten
Seite zeigt (sonst Abbruch der Art `form` ohne weitere Anfrage); eine HTTP-Fehlantwort darauf bricht ab wie sonst.
Jeder Lauf wird in ergebnisse/oparl_laeufe.tsv vermerkt (Stufe aus RATSATLAS_STUFE, Zeilen in _cache/abrufe.tsv),
jede durchlaufene Liste in ergebnisse/oparl_listen.tsv. Bei einem Abbruch endet der Lauf mit Rückgabewert 2. Lehnt der
Proxy der Arbeitsumgebung die Verbindung ab (Art `proxy`: CONNECT-Antwort 403/405/407 oder HTTP 407), hat keine
Anfrage die Stadt erreicht: nicht wiederholen, sondern berichten; der Host muss im Netz der Arbeitsumgebung erlaubt
sein (explore/STUFEN.md, Stufe 1). Meldet der Proxy 502/504 (Stadt nicht erreicht, beim Verbindungsaufbau oder als
Antwort im Tunnel) oder ist eine Antwort abgeschnitten oder unlesbar, gilt das als mögliche Sperre (Art `sperre`),
429/503 als Art `server`. Scheitert die Zertifikatsprüfung (Art `tls`), ist das vermutlich eine Einstellung der
Arbeitsumgebung (CA des Proxys; Zertifikat der Gegenseite oder Sperrseite nicht ausgeschlossen); der Lauf bricht ab.
Nach einem Abbruch gilt: in dieser Nacht keine weitere Anfrage (STUFEN.md). Vor der ersten Anfrage an eine nicht
lokale Adresse prüft main() deshalb oparl_laeufe.tsv: Endete der letzte Lauf vor weniger als 12 Stunden mit
„abbruch (…)“, „fehler (…)“ oder „unterbrochen“ (Strg+C, SIGTERM etwa nach dem Zeitlimit des aufrufenden Werkzeugs,
SIGHUP, wenn nicht ignoriert wie mit nohup; alle enden wie Strg+C, ein zweites Signal danach wird ignoriert; ein Lauf
gilt als „unterbrochen“, bis er regulär endet), bricht das Kommando ohne Anfrage ab (Rückgabewert 1). Ebenso nach
einem hart beendeten Lauf (SIGKILL, Absturz): Vor der ersten Anfrage an die Stadt legt main() die Markerdatei
_cache/lauf_offen.json an und entfernt sie erst nach dem Vermerk; liegt sie ohne Vermerk und ist der Lauf jünger als 12
Stunden, gilt er als „nicht regulär beendet“ (ein älterer Marker wird gemeldet und entfernt). Weiter nur nach
Rücksprache mit dem Auftraggeber: RATSATLAS_NACH_ABBRUCH=ja. Ein zweiter gleichzeitiger Prozess (auch mit anderem
Cache oder aus einer anderen Arbeitskopie) bricht vor seiner ersten Anfrage ab (Art `parallel`, Sperre
~/.cache/ratsatlas-wuppertal/abruf.lock in explore/abruf.py, Ort über RATSATLAS_SPERRE). Eine Antwort, die kein JSON
ist, wird aus dem Cache entfernt, auch in Listen und Parametertests (ein späterer Lauf fragt erneut, statt sie ohne
Anfrage zu lesen).
Ergebnisse als TSV unter explore/ergebnisse/; Rohdaten, PDFs und die Stichprobendatei für `pdf-koepfe` und
explore/ortsnamen.py (_cache/stichprobe_vorlagen.jsonl: nur id, Titel `name`, reference, paperType, date, ob
underDirectionOf gesetzt ist, Adresse und Zahl der Dateien aus auxiliaryFile, je Datei `name`, `fileName`, `mimeType`
und Adresse für die Wahl der Datei in `pdf-koepfe`) bleiben im Cache (nicht im Repository).
Aus PDFs werden nur abgeleitete Kennungen (Amtskennung wie „Ressort <Nummer>“), Trefferart, Zeilennummern, Abgleich mit
organizations/at, die Fundstelle als Dokumentteil und Zahlen ohne Inhalt (Bytes, Seiten, Textebene, Klasse des
Erzeugers) gespeichert, keine Textauszüge, keine Namen, Telefonnummern oder E-Mail-Adressen (auch nicht gekürzt).
"""
import argparse
import collections
import contextlib
import csv
import datetime as dt
import io
import ipaddress
import json
import logging
import math
import os
import re
import signal
import sys
import urllib.parse
import warnings
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abruf  # noqa: E402
from abruf import Abbruch, hole  # noqa: E402

STADT = "Wuppertal"
SYSTEM = os.environ.get("RATSATLAS_OPARL_SYSTEM", "https://oparl.wuppertal.de/oparl/system")
BODY = os.environ.get("RATSATLAS_OPARL_BODY", "https://oparl.wuppertal.de/oparl/bodies/0001")
ERG = Path(os.environ.get("RATSATLAS_ERGEBNISSE", Path(__file__).resolve().parent / "ergebnisse"))
# Seitengrenze je Kommando, wenn --seiten fehlt (stichprobe: Zahl der verteilten Seiten; sonst Seiten der Liste)
SEITEN_VORGABE = {"stichprobe": 8, "organisationen": 5, "sitzungen": 2}
# Bereiche für die Bisektion in `umfang` (CLAUDE.md 3.1, Stichprobe 09.11.2026): Seite 240 gefüllt, Seite 250 leer;
# Datumsgrenze 01.01.2020 geschätzt zwischen Seite 50 und 150. Beide Bereiche werden zuerst an ihren Enden geprüft.
GRENZE_SEITEN = (50, 150)
ENDE_SEITEN = (240, 250)
STICHTAG = "2020-01-01"   # Vorlagen mit `date` ab diesem Tag (CLAUDE.md 2)
# Antworten, die in den Parametertests von `kennzahlen` als „Parameter abgelehnt“ gelten (kein Abbruch)
ABGELEHNT = (400, 401, 404)
# strenge Vorgaben für Anfragen an die Stadt (explore/STUFEN.md, Abbruchkriterien)
STRENG_DAUER = 5.0
STRENG_ABSTAND = 2.0   # Sekunden vom Ende einer Antwort bis zur nächsten Anfrage (CLAUDE.md 5.1)
# Stunden des Zeitfensters 23–1 Uhr Ortszeit (STUFEN.md); weitere Fenster nur für Testadressen
ERLAUBTE_STUNDEN = {23, 0}
# nach einem Abbruch oder Fehler keine weitere Anfrage an die Stadt in dieser Frist (STUFEN.md: „in dieser Nacht keine
# weitere Anfrage und keine weitere Stufe“); Freigabe nur nach Rücksprache mit RATSATLAS_NACH_ABBRUCH=ja
SPERRFRIST = dt.timedelta(hours=12)
# Ergebnisse, nach denen die Sperrfrist gilt: Abbruch, Fehler und ein unterbrochener Lauf (Strg+C, Signal oder ein Ende
# ohne regulären Abschluss)
RE_ABBRUCH = re.compile(r"^(?:(?:abbruch|fehler) \(|unterbrochen\b)")
UNTERBROCHEN = "unterbrochen"
# Signale, die einen Lauf wie Strg+C beenden (Vermerk „unterbrochen“ statt eines Endes ohne Vermerk): SIGTERM etwa nach
# dem Zeitlimit des aufrufenden Werkzeugs, SIGHUP beim Schließen des Terminals (nur, wenn nicht ignoriert wie mit nohup).
# SIGKILL lässt sich nicht abfangen.
SIGNALE = (signal.SIGTERM, signal.SIGHUP)
# fehlende Gesamtzahlen in `pagination` (Köln, Stufe 1; für Wuppertal offen)
FEHLT = "fehlt"
# Markerdatei eines laufenden Laufs an die Stadt neben _cache/abrufe.tsv (gitignoriert): angelegt vor der ersten Anfrage,
# entfernt am regulären Ende (auch nach einem Abbruch mit Vermerk). Bleibt sie nach einer harten Beendigung liegen
# (SIGKILL, Absturz der Arbeitsumgebung: kein Vermerk in oparl_laeufe.tsv), gilt der Lauf als „nicht regulär beendet“.
MARKER = "lauf_offen.json"
NICHT_REGULAER = "nicht regulär beendet"
# Stichprobe für pdf-koepfe: nur im Cache (nicht im Repository), ohne File-Objekte
STICHPROBE = abruf.CACHE / "stichprobe_vorlagen.jsonl"

RE_VO = re.compile(r"^VO/\d{4}/\d{2}$")   # Schema der Referenz laut CLAUDE.md 3.1, z. B. VO/1380/26
RE_PRAEFIX = re.compile(r"/organizations/([^/?#]+)/[^/?#]+$")
# --- Stufe 6: PDF-Köpfe (pdf-koepfe). Wuppertaler Kopfformate sind ungemessen; alles außer „Amt 402“ und „Ressort 102“
# (CLAUDE.md 3.1/3.2) ist Annahme und steht so in pdf_koepfe.tsv (Spalten bezeichnung_beleg, regel, auswahl). ---
# Bezeichnung mit Nummer (zwei oder drei Ziffern, ggf. mit Unterteilung wie 001.13). Belegt: Ressort, Amt. Nicht belegte
# Suchannahmen: Stadtbetrieb, Geschäftsbereich, Eigenbetrieb. Zwischen Bezeichnung und Nummer auch ein Zeilenumbruch.
BEZEICHNUNG_BELEGT = ("Ressort", "Amt")
BEZEICHNUNG_ANNAHME = ("Stadtbetrieb", "Geschäftsbereich", "Eigenbetrieb")
# Hinter der Nummer keine weitere Ziffer und kein Punkt mit Ziffer (Teilnummer); ein Satzpunkt („Amt 402.“) ist erlaubt.
RE_AMT = re.compile(r"\b(Ressort|Stadtbetrieb|Geschäftsbereich|Eigenbetrieb|Amt)\s+(\d{2,3}(?:\.\d{1,3})*)(?!\d|\.\d)")
# Beginn des ersten Abschnitts nach dem Kopf (Annahme: Zeile beginnt mit einem dieser Wörter); Kandidaten davor gelten
# als Kopf. Ohne erkannten Abschnitt gelten die ersten KOPF_ZEILEN Zeilen (ohne Leerzeilen) als Kopf (Annahme).
RE_ABSCHNITT = re.compile(r"(?:Beschlussvorschlag|Begründung|Sachverhalt)\b")
KOPF_ZEILEN = 30
# Wahl der Datei aus auxiliaryFile (Annahme): Name oder Dateiname nennt die Referenz der Vorlage oder die Vorlage selbst
# und ist nicht als Anlage bezeichnet; sonst die erste Datei. Wortgrenzen ohne \b: Unterstrich, Ziffer, Punkt usw.
# gelten als Trenner („Anlage_1_…“, „Anlage1.pdf“, „Vorlage_VO_…“), nur ein Buchstabe davor oder danach nicht.
VOR, NACH = r"(?<![^\W\d_])", r"(?![^\W\d_])"
RE_VORLAGE_NAME = re.compile(rf"{VOR}(?:Vorlage|Beschlussvorlage|Verwaltungsvorlage|Drucksache){NACH}", re.I)
RE_ANLAGE = re.compile(rf"{VOR}(?:Anlagen?|Anhang|Anhänge){NACH}", re.I)
# höchste Größe einer PDF-Datei in Bytes: abruf.MAX_BYTES wird während pdf-koepfe darauf gesetzt (abruf.py liest dann
# höchstens eine Grenze + 1 Byte, speichert nichts und meldet Art `groesse`; die Datei gilt als „zu groß“, der Lauf geht
# weiter). RATSATLAS_PDF_MAX_BYTES darf die Grenze nur senken (Tests). Annahme: Vorlagen sind kleiner als 10 MiB.
PDF_MAX_BYTES = 10 * 1024 * 1024
# höchste Zahl der Vorlagen je pdf-koepfe-Lauf (--anzahl, STUFEN.md: höchstens 100 PDF-Anfragen)
PDF_HOECHSTENS = 100
# Klasse des PDF-Erzeugers aus den Metadaten Producer/Creator, nur als grobe Klasse (Annahme; Rohwerte können Dateinamen
# oder Namen enthalten und werden nie gespeichert). Reihenfolge: erste passende Klasse gilt.
ERZEUGER_KLASSEN = (
    ("Scan/Texterkennung", ("scan", "ocr", "abbyy", "finereader", "kofax", "canon", "ricoh", "kyocera", "xerox",
                            "konica", "toshiba", "brother")),
    ("Office-Programm", ("microsoft", "word", "excel", "powerpoint", "libreoffice", "openoffice", "writer")),
    ("Adobe", ("adobe", "acrobat", "distiller", "indesign")),
    ("PDF-Bibliothek", ("itext", "pdflib", "reportlab", "ghostscript", "tcpdf", "fpdf", "pdfsharp", "aspose", "pdftk",
                        "qpdf", "pypdf", "cairo", "skia", "wkhtmltopdf", "pdfium")))
# Treffer, die als „PDF gelesen“ gelten (Textebene geprüft)
GELESEN = ("kennung", "nur außerhalb des Kopfes", "nein", "kein_text")
# Leerzeichen-Varianten, Bindestriche und unsichtbare Zeichen für die Normalisierung des Kopftexts
_ZEICHEN = {**dict.fromkeys(map(ord, "\t           　"),
                            " "),
            **dict.fromkeys(map(ord, "‐‑‒–−"), "-"),
            **dict.fromkeys(map(ord, "­​‌‍﻿"), None)}

_LISTEN = []   # je durchlaufener Liste ein Eintrag für oparl_listen.tsv


def lokal(url):
    t = urllib.parse.urlsplit(url)
    return t.scheme == "http" and t.hostname in ("127.0.0.1", "localhost")


def testadresse(url):
    """Adresse, die kein Server der Stadt sein kann: Loopback (127.0.0.0/8, ::1, localhost) oder die reservierte Domain
    .invalid (RFC 2606). Nur für sie darf RATSATLAS_ZEITFENSTER leer (aus) oder weiter als 23–1 Uhr sein (Tests)."""
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower().rstrip(".")
    if host == "localhost" or host == "invalid" or host.endswith(".invalid"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _stunden(fenster):
    """Stunden (0–23), die ein Zeitfenster „von-bis“ umfasst (über Mitternacht möglich; von = bis: alle)."""
    von, bis = (int(x) for x in fenster.split("-"))
    return set(range(von, bis)) if von < bis else set(range(von, 24)) | set(range(0, bis))


def im_zeitfenster(jetzt=None, url=None):
    """Liegt `jetzt` (Vorgabe: jetzt, Europe/Berlin) im Zeitfenster RATSATLAS_ZEITFENSTER (Vorgabe 23-1)? Für alle
    Adressen außer Testadressen (testadresse) gilt nur ein Fenster innerhalb von 23–1 Uhr (ERLAUBTE_STUNDEN): ein leerer
    Wert oder ein weiteres Fenster (z. B. 0-24, 1-1, 8-20) gilt dann als außerhalb."""
    fenster = os.environ.get("RATSATLAS_ZEITFENSTER", "23-1").strip()
    test = testadresse(url)
    if not fenster:
        return test
    if not test and not _stunden(fenster) <= ERLAUBTE_STUNDEN:
        return False
    von, bis = (int(x) for x in fenster.split("-"))
    h = (jetzt or dt.datetime.now(ZoneInfo("Europe/Berlin"))).hour
    return von <= h < bis if von < bis else (h >= von or h < bis)


def sichere_vorgaben(umgebung=None):
    """Strenge Vorgaben für Anfragen an die Stadt; liefert (werte, fehler). Fehlende Werte werden gesetzt
    (Wiederholungen 0, höchstens 5 s je Antwort, 2 s Abstand), lockerere abgelehnt; Obergrenze und Kontakt sind
    Pflicht."""
    env = os.environ if umgebung is None else umgebung
    fehler = []
    try:
        wiederholungen = int(env.get("RATSATLAS_WIEDERHOLUNGEN") or "0")
        max_dauer = float(env.get("RATSATLAS_MAX_DAUER") or STRENG_DAUER)
        max_anfragen = int(env.get("RATSATLAS_MAX_ANFRAGEN") or "0")
        abstand = float(env.get("RATSATLAS_ABSTAND") or STRENG_ABSTAND)
    except ValueError as e:
        return {}, [f"unlesbarer Wert ({e})"]
    if wiederholungen != 0:
        fehler.append("RATSATLAS_WIEDERHOLUNGEN muss 0 sein (keine Wiederholung nach 429/5xx)")
    if not 0 < max_dauer <= STRENG_DAUER:
        fehler.append(f"RATSATLAS_MAX_DAUER muss größer als 0 und höchstens {STRENG_DAUER:g} s sein")
    if not (math.isfinite(abstand) and abstand >= STRENG_ABSTAND):
        fehler.append(f"RATSATLAS_ABSTAND muss mindestens {STRENG_ABSTAND:g} s sein (Abstand zwischen zwei Anfragen)")
    if max_anfragen <= 0:
        fehler.append("RATSATLAS_MAX_ANFRAGEN fehlt (Obergrenze der Stufe laut explore/STUFEN.md)")
    kontakt = (env.get("RATSATLAS_KONTAKT") or "").strip()
    if not kontakt or "<" in kontakt or ">" in kontakt:
        fehler.append("RATSATLAS_KONTAKT fehlt oder enthält noch den Platzhalter „<…>“")
    return {"wiederholungen": wiederholungen, "max_dauer": max_dauer, "max_anfragen": max_anfragen,
            "abstand": abstand}, fehler


def _streng_aktiv():
    """Gelten in explore/abruf.py die strengen Vorgaben? (Prüfung vor jeder Anfrage an die Stadt)"""
    return (abruf.WIEDERHOLUNGEN == 0 and 0 < abruf.MAX_DAUER <= STRENG_DAUER and abruf.MAX_ANFRAGEN > 0
            and abruf.ABSTAND >= STRENG_ABSTAND
            and bool(abruf.KONTAKT.strip()) and "<" not in abruf.KONTAKT and ">" not in abruf.KONTAKT)


def _host(url):
    return (urllib.parse.urlsplit(url or "").hostname or "").lower().rstrip(".")


def erlaubter_host(url):
    """Darf an diese Abrufadresse gesendet werden? Ein lokaler Probelauf (SYSTEM und BODY lokal) fragt nur lokale
    Adressen; ein Lauf gegen die Stadt nie lokale, sondern nur Hosts der Stadt (abruf.stadt_host) und die Hosts von SYSTEM
    und BODY (Tests gegen 127.0.0.2 oder example.invalid). Adressen aus der API (links.next, Listen im Body,
    auxiliaryFile) gehen so an keinen fremden Host."""
    probelauf = lokal(SYSTEM) and lokal(BODY)
    if lokal(url):
        return probelauf
    if probelauf:
        return False
    host = _host(url)
    return abruf.stadt_host(host) or host in {_host(SYSTEM), _host(BODY)}


# 12-Stunden-Regel in diesem Prozess geprüft (main() vor dem Lauf, sonst _hole vor der ersten Anfrage an die Stadt)
_sperrfrist_geprueft = False


def _sperrfrist_pruefen(url):
    """12-Stunden-Regel vor der ersten nicht lokalen Anfrage eines Prozesses, falls main() sie nicht geprüft hat (etwa
    beim Aufruf einzelner Kommandos aus einem anderen Skript)."""
    global _sperrfrist_geprueft
    if _sperrfrist_geprueft:
        return
    vorher = letzter_abbruch()
    if vorher and os.environ.get("RATSATLAS_NACH_ABBRUCH") != "ja":
        raise Abbruch(f"Lauf {vorher.get('lauf')} ({vorher.get('kommando')}) endete mit „{vorher.get('ergebnis')}“ vor "
                      f"weniger als {SPERRFRIST.total_seconds() / 3600:g} Stunden; keine Anfrage (RATSATLAS_NACH_ABBRUCH): "
                      f"{url}", "gesperrt")
    _sperrfrist_geprueft = True


def _hole(url, endung=".json"):
    """Abrufadresse (http:// auf Hosts der Stadt → https://), dann erlaubter Host, Freigabe, Zeitfenster, strenge
    Vorgaben, PDF-Freigabe und 12-Stunden-Regel vor jeder Anfrage an die Stadt; lokale Testserver ausgenommen."""
    url = abruf.abrufadresse(url)
    if not erlaubter_host(url):
        raise Abbruch(f"Host nicht erlaubt (weder Host der Stadt noch von RATSATLAS_OPARL_SYSTEM/BODY, bzw. lokal und "
                      f"nicht lokal gemischt), nicht gesendet: {url}", "adresse")
    if not lokal(url):
        if os.environ.get("RATSATLAS_MESSUNG_FREIGEGEBEN") != "ja":
            raise Abbruch(f"Messung bei der Stadt {STADT} nicht freigegeben (RATSATLAS_MESSUNG_FREIGEGEBEN): {url}", "gesperrt")
        if not im_zeitfenster(url=url):
            raise Abbruch(f"außerhalb des Zeitfensters (RATSATLAS_ZEITFENSTER, nur 23–1 Uhr): {url}", "zeitfenster")
        if not _streng_aktiv():
            raise Abbruch(f"strenge Vorgaben nicht aktiv (Wiederholungen 0, höchstens {STRENG_DAUER:g} s, Abstand "
                          f"mindestens {STRENG_ABSTAND:g} s, Obergrenze, Kontakt): {url}", "gesperrt")
        if endung == ".pdf" and os.environ.get("RATSATLAS_PDF_FREIGEGEBEN") != "ja":
            raise Abbruch(f"PDF-Abruf nicht freigegeben (RATSATLAS_PDF_FREIGEGEBEN): {url}", "gesperrt")
        _sperrfrist_pruefen(url)
    return hole(url, endung)


def _mit_parametern(url, **params):
    if params:   # ohne URL-Kodierung, wie pipeline/sessionnet.py
        url += ("&" if "?" in url else "?") + "&".join(f"{k}={v}" for k, v in params.items())
    return url


def _json_von(adresse, lesen=None):
    """JSON der Antwort (`lesen`: Ersatz für den Abruf, z. B. aus dem Cache); eine unlesbare Antwort bleibt nicht im Cache
    (ein späterer Lauf würde sie ohne Anfrage lesen)."""
    try:
        return json.loads(lesen() if lesen else _hole(adresse))
    except ValueError:
        pfad = abruf._cachepfad(adresse, ".json")
        pfad.unlink(missing_ok=True)
        abruf._begleitpfad(pfad).unlink(missing_ok=True)   # Kopfangaben der entfernten Antwort
        raise


def _json(url, **params):
    return _json_von(_mit_parametern(url, **params))


def _wert(v):
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _schreibe(name, zeilen):
    ERG.mkdir(parents=True, exist_ok=True)
    spalten = list(dict.fromkeys(k for z in zeilen for k in z))
    with (ERG / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, spalten, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for z in zeilen:
            w.writerow({k: str(v).replace("\t", " ").replace("\n", " ") for k, v in z.items()})
    print(f"→ {ERG / name} ({len(zeilen)} Zeilen)")


def _anhaengen(name, spalten, zeilen):
    ERG.mkdir(parents=True, exist_ok=True)
    datei = ERG / name
    neu = not datei.exists()
    with datei.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, spalten, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        if neu:
            w.writeheader()
        for z in zeilen:
            w.writerow({k: str(z.get(k, "")).replace("\t", " ").replace("\n", " ") for k in spalten})


def _seiten(url, max_seiten=None, name="", **params):
    """Folgt links.next und liefert (seite_nr, antwort). Endet am Ende der Liste, an der Seitengrenze, bei einer
    schon besuchten Folgeadresse oder bei einer Seite ohne neue Kennungen (Schleifenschutz wie pipeline/sessionnet.py).
    Das Ende wird in _LISTEN vermerkt („abgebrochen“, solange es nicht erreicht ist). Adressen bleiben wie in der
    Quelle (auch http://); abgerufen wird über _hole (https://)."""
    start = _mit_parametern(url, **params)
    eintrag = {"liste": name, "url": start, "grenze": max_seiten or "", "seiten": 0, "objekte": 0,
               "ende": "abgebrochen", "erstes_next": ""}
    _LISTEN.append(eintrag)
    besucht, kennungen = {start}, set()
    seite, nr = _json_von(start), 1
    while True:
        ids = {o.get("id") for o in seite.get("data") or [] if isinstance(o, dict)}
        if nr > 1 and not ids - kennungen:
            eintrag["ende"] = "Seite ohne neue Kennungen"
            return
        kennungen |= ids
        eintrag["seiten"], eintrag["objekte"] = nr, len(kennungen)
        yield nr, seite
        nxt = (seite.get("links") or {}).get("next")
        if nxt and not eintrag["erstes_next"]:
            eintrag["erstes_next"] = nxt
        if not nxt:
            eintrag["ende"] = "Ende der Liste (kein links.next)"
            return
        if max_seiten and nr >= max_seiten:
            eintrag["ende"] = f"Seitengrenze {max_seiten}"
            return
        if nxt in besucht:
            eintrag["ende"] = "links.next wiederholt"
            return
        besucht.add(nxt)
        seite, nr = _json_von(nxt), nr + 1


def _angabe(pag, schluessel):
    """Wert aus `pagination`; fehlt er oder ist er null (keine Gesamtzahlen), „fehlt“ statt None."""
    wert = (pag if isinstance(pag, dict) else {}).get(schluessel)
    return FEHLT if wert is None else wert


def _liste_kennwerte(objekt, antwort):
    pag, links = antwort.get("pagination") or {}, antwort.get("links") or {}
    zeilen = [{"objekt": objekt, "feld": f"pagination.{k}", "wert": _angabe(pag, k)}
              for k in ("totalElements", "elementsPerPage", "currentPage", "totalPages")]
    return zeilen + [
        {"objekt": objekt, "feld": "objekte_erste_seite", "wert": len(antwort.get("data") or [])},
        {"objekt": objekt, "feld": "pagination.schluessel", "wert": ",".join(sorted(pag))},
        {"objekt": objekt, "feld": "links.schluessel", "wert": ",".join(sorted(links))},
        {"objekt": objekt, "feld": "links.next", "wert": links.get("next") or ""}]


def _schema(url):
    """Schema einer Adresse aus der Quelle (http, https) oder „–“."""
    return urllib.parse.urlsplit(url).scheme or "–" if url else "–"


def _datum(o):
    """`date` einer Vorlage als datetime.date (erste zehn Zeichen, ISO), sonst None."""
    try:
        return dt.date.fromisoformat(str(o.get("date") or "")[:10])
    except ValueError:
        return None


def _absteigend(objekte):
    """Verletzungen der Sortierung nach `date` absteigend innerhalb einer Seite (gleiche Daten erlaubt); Objekte ohne
    lesbares `date` zählen nicht. Liefert (Verletzungen, Objekte mit date)."""
    daten = [d for d in (_datum(o) for o in objekte if isinstance(o, dict)) if d]
    return sum(1 for a, b in zip(daten, daten[1:]) if b > a), len(daten)


def test(_):
    """Erster Kontakt mit höchstens drei Anfragen: Erreichbarkeit, Antwortzeit, Seitengröße, Form von links.next,
    Schema der Kennungen, Sortierung der ersten Seite nach `date`."""
    zeilen = []
    try:
        system = _json(SYSTEM)
        zeilen.append({"objekt": "system", "feld": "id", "wert": system.get("id")})
        zeilen += [{"objekt": "system", "feld": k, "wert": _wert(system.get(k))[:200]}
                   for k in ("oparlVersion", "vendor", "product", "license")]
        body = _json(BODY)
        zeilen.append({"objekt": "body", "feld": "id", "wert": body.get("id")})
        zeilen += [{"objekt": "body", "feld": k, "wert": _wert(body.get(k))[:200]}
                   for k in ("name", "license", "paper", "modified")]
        if body.get("paper"):
            s = _json(body["paper"])
            daten = [o for o in s.get("data") or [] if isinstance(o, dict)]
            zeilen += _liste_kennwerte("paper", s)
            zeilen.append({"objekt": "paper", "feld": "felder_erstes_objekt",
                           "wert": ",".join(sorted((daten or [{}])[0].keys()))})
            zeilen.append({"objekt": "paper", "feld": "id_schema",
                           "wert": ",".join(sorted({_schema(o.get("id")) for o in daten})) or "–"})
            zeilen.append({"objekt": "paper", "feld": "links.next_schema",
                           "wert": _schema((s.get("links") or {}).get("next"))})
            verletzt, n = _absteigend(daten)
            zeilen.append({"objekt": "paper", "feld": "date_absteigend_erste_seite",
                           "wert": ("ja" if not verletzt else f"nein ({verletzt} Verletzungen)") + f" (n = {n})"})
    except Abbruch as e:
        zeilen.append({"objekt": "lauf", "feld": "abbruch", "wert": str(e)})
        raise
    finally:
        _schreibe("oparl_test.tsv", zeilen)


def _zeitpunkt(wert):
    """ISO-Zeitpunkt; ohne Zeitzone gilt Ortszeit Europe/Berlin; unlesbar → None."""
    try:
        t = dt.datetime.fromisoformat(str(wert).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=ZoneInfo("Europe/Berlin"))


def _utc(t):
    """Zeitpunkt in UTC, sekundengenau, mit „+00:00“ (wie pipeline/sessionnet.py, ohne URL-Kodierung angehängt)."""
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()


def _neueste_zuerst(objekte):
    """Ist die Seite nach `created` absteigend sortiert? Dann stehen neue Vorlagen vorn."""
    zeiten = [_zeitpunkt(o["created"]) if o.get("created") else None for o in objekte]
    return (len(zeiten) >= 2 and None not in zeiten and zeiten[0] > zeiten[-1]
            and all(a >= b for a, b in zip(zeiten, zeiten[1:])))


def _grenze_modified(basis):
    """(Grenze für modified_since, Herkunft) aus der ungefilterten ersten Seite: Median von `modified` ihrer ersten
    Hälfte (bei neueste zuerst die Vorlagen, die auch nach einigen neuen Vorlagen seit Stufe 1 noch auf der ersten Seite
    stehen). Ein Server, der den Filter überginge, müsste dann Vorlagen mit älterem `modified` liefern. Ohne lesbares
    `modified`: vor 7 Tagen."""
    kopf = basis[:max(1, (len(basis) + 1) // 2)]
    zeiten = sorted(t for t in (_zeitpunkt(o["modified"]) for o in kopf if o.get("modified")) if t)
    if not zeiten:
        return _utc(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)), "vor 7 Tagen (kein lesbares modified)"
    return _utc(zeiten[len(zeiten) // 2]), (f"Median von modified der ersten {len(kopf)} Vorlagen der ungefilterten "
                                            "ersten Seite")


def _dauer_text(abstand):
    """Zeitabstand lesbar: Sekunden, Minuten, Stunden (bis 2 Tage), sonst Tage mit einer Nachkommastelle."""
    s = int(abs(abstand.total_seconds()))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min"
    if s < 2 * 86400:
        h, m = divmod(s // 60, 60)
        return f"{h} h" + (f" {m} min" if m else "")
    return f"{s / 86400:.1f} Tage".replace(".", ",")


def _filter_urteil(basis, antwort, feld, von=None, bis=None):
    """Urteil je Grenze eines Zeitfilters ({"von": …, "bis": …}) aus der gefilterten ersten Seite `antwort` und der
    ungefilterten ersten Seite `basis`, ohne weitere Anfrage:
    - „nein“: Die Antwort enthält Objekte jenseits der Grenze; dazu, wie weit das äußerste davon jenseits liegt
      („frühestes modified 1 h vor der Grenze“: um 1 h deutet auf einen Versatz, etwa „+“ als Leerzeichen und damit
      Ortszeit, bis 24 h auf Tagesgenauigkeit, mehr auf einen übergangenen Filter).
    - „ja“: Ein Server, der nur diese Grenze überginge, hätte Objekte jenseits der Grenze liefern müssen, und solche fehlen
      in der Antwort. Die ungefilterte Seite enthält Objekte jenseits der Grenze, die die übrige Grenze einhalten und deren
      Kennung in der Antwort fehlt (`modified` kann sich seit der ungefilterten Seite geändert haben: Sind alle Vorlagen
      seither geändert, liefert auch ein Server ohne Filter nur Objekte diesseits der Grenze, aber mit denselben
      Kennungen): bei „bis“ irgendwo (neue Vorlagen liegen ebenfalls jenseits), bei „von“ und neueste zuerst auf den
      ersten Plätzen, die neue Vorlagen seit der ungefilterten Seite (Kennungen dort nicht enthalten, created nicht älter
      als ihre jüngste Vorlage) nicht verdrängt haben können (ein Server ohne Filter lieferte eine ebenso lange Seite).
    - sonst „nicht unterscheidbar“ (z. B. alle modified gleich oder seit der ungefilterten Seite geändert; bei neueste
      zuerst created_since), mit dem Vergleich der Kennungen."""
    def zeit(o):
        return _zeitpunkt(o[feld]) if o.get(feld) else None

    def jenseits(o, seite):
        t, g = zeit(o), (von if seite == "von" else bis)
        return g is not None and t is not None and (t < g if seite == "von" else t > g)

    if not antwort:
        return {s: "keine Objekte" for s, g in (("von", von), ("bis", bis)) if g is not None}
    ids, antwort_ids = {o.get("id") for o in basis}, {o.get("id") for o in antwort}
    fremd = [o for o in antwort if o.get("id") not in ids]
    juengste = max((t for t in (_zeitpunkt(o["created"]) for o in basis if o.get("created")) if t), default=None)
    neu = sum(1 for o in fremd if juengste is None or not o.get("created")
              or (_zeitpunkt(o["created"]) or juengste) >= juengste)
    urteil = {}
    for seite, andere in (("von", "bis"), ("bis", "von")):
        if (von if seite == "von" else bis) is None:
            continue
        verletzt = [zeit(o) for o in antwort if jenseits(o, seite)]
        plaetze = basis[:max(len(basis) - neu, 0)] if seite == "von" and _neueste_zuerst(basis) else basis
        if verletzt:
            richtung = "vor" if seite == "von" else "nach"
            aeusserst = min(verletzt) if seite == "von" else max(verletzt)
            urteil[seite] = (f"nein ({len(verletzt)} von {len(antwort)} {richtung} der Grenze; "
                             f"{'frühestes' if seite == 'von' else 'spätestes'} {feld} "
                             f"{_dauer_text(aeusserst - (von if seite == 'von' else bis))} {richtung} der Grenze)")
        elif any(jenseits(o, seite) and not jenseits(o, andere) and o.get("id") not in antwort_ids for o in plaetze):
            urteil[seite] = "ja"
        else:
            urteil[seite] = ("nicht unterscheidbar (" + ("gleiche Kennungen wie ohne Filter" if not fremd else
                                                         f"{len(fremd)} Kennungen nicht auf der ungefilterten Seite")
                             + ("; neueste zuerst: die erste Seite zeigt nur die jüngsten Vorlagen"
                                if seite == "von" and bis is not None and _neueste_zuerst(basis) else "") + ")")
    return urteil


def _parametertests(url, basis, zeilen):
    """Parametertests an der Vorlagenliste, in dieser Reihenfolge: modified_since unkodiert (Grenze aus der ungefilterten
    ersten Seite), modified_since URL-kodiert mit derselben Grenze (SessionNet in Wuppertal laut meine-stadt-transparent:
    HTTP 404, Stand ca. 2021, heutige Gültigkeit offen, Quelle sessionnet_befunde.tsv in ratsatlas-koeln; Köln: nur
    kodiert wirksam). HTTP 400, 401 und 404 gelten als „Parameter abgelehnt“ (Messung geht weiter),
    zwei 401 in Folge brechen ab (abgelehnt oder Sperre?); jede andere Fehlantwort bricht nach dieser Anfrage ab; eine
    zu langsame Antwort wird mit der Zahl der Objekte vermerkt, dann Abbruch."""
    basis = [o for o in basis if isinstance(o, dict)]
    seit, herkunft = _grenze_modified(basis)
    zeilen.append({"objekt": "paper", "feld": "grenze modified_since", "wert": f"{seit} ({herkunft})"})
    tests = [(f"test modified_since={seit}", _mit_parametern(url, modified_since=seit), {"von": _zeitpunkt(seit)}),
             ("test modified_since URL-kodiert",
              url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"modified_since": seit}),
              {"von": _zeitpunkt(seit)})]
    zuvor_401 = False
    for feld, adresse, grenzen in tests:
        try:
            a = _json_von(adresse)
        except Abbruch as e:
            if e.art == "http" and e.code == 401 and zuvor_401:
                raise Abbruch(f"zweimal HTTP 401 in Folge (abgelehnt oder Sperre?): {e}", "http", 401) from e
            if e.art == "http" and e.code in ABGELEHNT:   # Parameter abgelehnt; Messung geht weiter
                zeilen.append({"objekt": "paper", "feld": feld, "wert": f"Parameter abgelehnt (HTTP {e.code})"})
                zuvor_401 = e.code == 401
                continue
            if e.art == "langsam":   # vollständig und gespeichert, aber zu langsam: Messwert vermerken, dann Abbruch
                try:
                    n = len(_json_von(adresse, abruf._cachepfad(adresse, ".json").read_bytes).get("data") or [])
                except (OSError, ValueError, AttributeError):
                    n = "?"
                zeilen.append({"objekt": "paper", "feld": feld, "wert": f"objekte={n}; {e}"})
            raise   # jede andere Fehlantwort bricht nach dieser Anfrage ab
        zuvor_401 = False
        daten = [o for o in a.get("data") or [] if isinstance(o, dict)]
        wert = f"objekte={len(daten)}; totalElements={_angabe(a.get('pagination'), 'totalElements')}"
        wert += f"; filter_wirksam={_filter_urteil(basis, daten, 'modified', **grenzen)['von']}"
        zeilen.append({"objekt": "paper", "feld": feld, "wert": wert})


def _kontaktfelder(objekt):
    """contactEmail und contactName nur als „vorhanden“/„leer“ (bei contactEmail mit Domain), nie die Werte: CLAUDE.md 2
    und 3.1, die im System-Objekt genannte Person wird nicht veröffentlicht."""
    zeilen = []
    for k in ("contactEmail", "contactName"):
        wert = str(objekt.get(k) or "").strip()
        angabe = "leer"
        if wert:
            domain = wert.rsplit("@", 1)[1].strip().lower() if k == "contactEmail" and "@" in wert else ""
            angabe = "vorhanden" + (f" (Domain {domain})" if re.fullmatch(r"[a-z0-9.-]+", domain) else "")
        zeilen.append({"objekt": "system", "feld": k, "wert": angabe})
    return zeilen


def kennzahlen(_):
    """8 Anfragen: System, Body, erste Seite von paper/meeting/organization/person, danach zwei Parametertests an paper
    (_parametertests)."""
    zeilen = []
    try:
        system, body = _json(SYSTEM), _json(BODY)
        zeilen += [{"objekt": "system", "feld": k, "wert": _wert(system.get(k))[:200]}
                   for k in ("oparlVersion", "name", "vendor", "product", "license", "website")]
        zeilen += _kontaktfelder(system)
        zeilen += [{"objekt": "body", "feld": k, "wert": _wert(body.get(k))[:200]}
                   for k in ("name", "license", "licenseValidSince", "oparlSince", "legislativeTerm", "location",
                             "modified")]
        vorlagen = None
        for name in ("paper", "meeting", "organization", "person"):
            url = body.get(name)
            if not url:
                zeilen.append({"objekt": name, "feld": "url", "wert": "fehlt im Body"})
                continue
            basis = _json(url)
            zeilen.append({"objekt": name, "feld": "url", "wert": url})
            zeilen += _liste_kennwerte(name, basis)
            if name == "paper":
                vorlagen = basis
        if vorlagen is not None:
            _parametertests(body["paper"], vorlagen.get("data") or [], zeilen)
    except Abbruch as e:
        zeilen.append({"objekt": "lauf", "feld": "abbruch", "wert": str(e)})
        raise
    finally:
        _schreibe("oparl_kennzahlen.tsv", zeilen)


def seitenform(liste, erste):
    """Funktion Seitennummer → Adresse für konstruierte Seiten der Liste `liste`, abgeleitet aus links.next ihrer ersten
    Seite `erste`: nur wenn links.next denselben Host und Pfad wie die Liste hat und als einzigen Parameter `page=2`
    (Wuppertal laut CLAUDE.md 3.1: `?page=N`). Seite 1 ist die Liste selbst. Ohne links.next (nur eine Seite) None;
    jede andere Form: Abbruch der Art `form` (keine Anfrage)."""
    nxt = (erste.get("links") or {}).get("next")
    if not nxt:
        return None
    t, l = urllib.parse.urlsplit(nxt), urllib.parse.urlsplit(liste)
    if (t.hostname, t.port, t.path) != (l.hostname, l.port, l.path) or t.query != "page=2" or l.query:
        raise Abbruch(f"links.next der ersten Seite hat nicht die Form <Liste>?page=2 ({nxt}); keine konstruierten "
                      "Seitenadressen", "form")
    return lambda nr: liste if nr == 1 else urllib.parse.urlunsplit(t._replace(query=f"page={nr}"))


def _seiteninfo(nr, antwort, stichtag):
    daten = [o for o in antwort.get("data") or [] if isinstance(o, dict)]
    tage = [d for d in (_datum(o) for o in daten) if d]
    verletzt, _ = _absteigend(daten)
    links = antwort.get("links") or {}
    return {"seite": nr, "objekte": len(daten), "ab_stichtag": sum(1 for d in tage if d >= stichtag),
            "date_max": max(tage).isoformat() if tage else "", "date_min": min(tage).isoformat() if tage else "",
            "ohne_date": len(daten) - len(tage), "absteigend": "–" if len(tage) < 2 else ("ja" if not verletzt else
                                                                                           f"nein ({verletzt})"),
            "links_schluessel": ",".join(sorted(links)) if isinstance(links, dict) else _wert(links),
            "links_next": (links.get("next") or "") if isinstance(links, dict) else ""}


def _sortierung(infos):
    """Urteil zur Sortierung nach `date` absteigend über die abgerufenen Seiten: in jeder Seite und zwischen Seiten in
    der Reihenfolge der Seitennummer (frühestes Datum einer Seite ≥ spätestes Datum jeder späteren Seite)."""
    gefuellt = sorted((i for i in infos if i["date_max"]), key=lambda i: i["seite"])
    innen = sum(1 for i in gefuellt if i["absteigend"].startswith("nein"))
    zwischen = sum(1 for a, b in zip(gefuellt, gefuellt[1:]) if b["date_max"] > a["date_min"])
    if not gefuellt:
        return "nicht prüfbar (keine Seite mit date)"
    if innen or zwischen:
        return (f"nein ({innen} Seiten innen nicht absteigend, {zwischen} Seitenübergänge verletzt; "
                f"{len(gefuellt)} Seiten geprüft)")
    return f"ja ({len(gefuellt)} Seiten geprüft, je Seite und zwischen den Seiten)"


def _bisektion(holen, lo, hi, gilt):
    """Kleinste Seite in (lo, hi], für die `gilt` wahr ist, wenn `gilt(lo)` falsch und `gilt(hi)` wahr ist (monotone
    Folge). Ruft höchstens ceil(log2(hi − lo)) Seiten zwischen den Enden ab. Liefert (lo, hi) am Ende (hi − lo = 1)."""
    while hi - lo > 1:
        mitte = (lo + hi) // 2
        if gilt(holen(mitte)):
            hi = mitte
        else:
            lo = mitte
    return lo, hi


def hoechstzahl_umfang(grenze=GRENZE_SEITEN, ende=ENDE_SEITEN):
    """Rechnerische Höchstzahl der Anfragen von `umfang` ohne Cache: Body, erste Seite, je Bereich zwei Enden und
    ceil(log2(Breite)) Schritte. Für `--liste meeting|person` gibt es nur den Bereich des Listenendes (grenze=None)."""
    return 2 + sum(2 + math.ceil(math.log2(b - a)) for a, b in (r for r in (grenze, ende) if r) if b - a >= 1)


def _listenende(holen, infos, lo, hi, groesse, objekt, zeilen):
    """Letzte gefüllte Seite L im Bereich (lo, hi) per Bisektion (zuerst die beiden Enden; liegt das Ende nicht im
    Bereich, wird es vermerkt und ohne weitere Anfrage übersprungen); Gesamtzahl (L − 1) × Seitengröße + Objekte auf L;
    Form von `links` auf der letzten und der ersten leeren Seite. Nur Zahlen und Schlüssel, keine Inhalte der Objekte."""
    def gefuellt(seite):
        return bool(seite.get("data"))
    zeilen.append({"objekt": "ende", "feld": "bereich", "wert": f"{lo}–{hi}"})
    if not gefuellt(holen(lo)):
        zeilen.append({"objekt": "ende", "feld": "letzte_seite", "wert": f"nicht im Bereich (Seite {lo} leer)"})
    elif gefuellt(holen(hi)):
        zeilen.append({"objekt": "ende", "feld": "letzte_seite", "wert": f"nicht im Bereich (Seite {hi} gefüllt)"})
    else:
        lo, hi = _bisektion(holen, lo, hi, lambda s: not gefuellt(s))
        letzte, leer = holen(lo), holen(hi)
        zeilen += [{"objekt": "ende", "feld": "letzte_seite", "wert": lo},
                   {"objekt": "ende", "feld": "objekte_letzte_seite", "wert": len(letzte.get("data") or [])},
                   {"objekt": "ende", "feld": f"{objekt}_gesamt" if objekt != "paper" else "vorlagen_gesamt",
                    "wert": f"{(lo - 1) * groesse + len(letzte.get('data') or [])} (bei {groesse} je Seite)"},
                   {"objekt": "ende", "feld": "links_letzte_seite",
                    "wert": f"Schlüssel {infos[lo]['links_schluessel'] or '(keine)'}; next "
                            f"{'vorhanden' if infos[lo]['links_next'] else 'fehlt oder leer'}"},
                   {"objekt": "ende", "feld": "links_leere_seite",
                    "wert": f"Seite {hi}: Objekte {len(leer.get('data') or [])}; Schlüssel "
                            f"{infos[hi]['links_schluessel'] or '(keine)'}; next "
                            f"{'vorhanden' if infos[hi]['links_next'] else 'fehlt oder leer'}"}]


def umfang(a):
    """Umfang der Vorlagenliste mit wenigen Anfragen: Body und erste Seite (mit dem Cache aus Stufe 1 und 2 ohne
    Anfrage), dann über konstruierte Seiten `?page=N` (seitenform) (1) die Datumsgrenze: kleinste Seite G im Bereich
    --grenze-seiten, deren Vorlagen alle ein `date` vor --stichtag haben, (2) das Ende: letzte gefüllte Seite L im Bereich
    --ende-seiten. Je Bereich zuerst die beiden Enden; liegt das Gesuchte nicht im Bereich, wird es vermerkt und ohne
    weitere Anfrage übersprungen. Dazu Sortierung nach `date` (je Seite und zwischen den Seiten), Ende von links.next
    (Form von `links` auf der letzten und der ersten leeren Seite) und die Gesamtzahl (L − 1) × Seitengröße + Objekte
    auf L. Ergebnisse: oparl_umfang.tsv, oparl_umfang_seiten.tsv."""
    if getattr(a, "liste", "paper") != "paper":
        return umfang_liste(a)
    stichtag = dt.date.fromisoformat(a.stichtag)
    zeilen, infos, geholt = [], {}, {}
    try:
        body = _json(BODY)
        liste = body["paper"]
        erste = _json(liste)
        geholt[1] = erste
        infos[1] = _seiteninfo(1, erste, stichtag)
        groesse = len(erste.get("data") or [])
        zeilen += [{"objekt": "paper", "feld": "url", "wert": liste},
                   {"objekt": "paper", "feld": "seitengroesse", "wert": groesse},
                   {"objekt": "paper", "feld": "pagination.totalElements",
                    "wert": _angabe(erste.get("pagination"), "totalElements")},
                   {"objekt": "paper", "feld": "links.next_erste_seite",
                    "wert": (erste.get("links") or {}).get("next") or ""}]
        adresse = seitenform(liste, erste)
        if adresse is None:
            zeilen.append({"objekt": "paper", "feld": "seitenform", "wert": "nur eine Seite (kein links.next)"})
            return
        zeilen.append({"objekt": "paper", "feld": "seitenform", "wert": "<Liste>?page=N (aus links.next)"})

        def holen(nr):
            if nr not in geholt:
                geholt[nr] = _json_von(adresse(nr))
                infos[nr] = _seiteninfo(nr, geholt[nr], stichtag)
            return geholt[nr]

        def neu(seite):   # mindestens eine Vorlage ab dem Stichtag
            return any((_datum(o) or dt.date.min) >= stichtag for o in seite.get("data") or [] if isinstance(o, dict))

        lo, hi = a.grenze_seiten
        zeilen += [{"objekt": "grenze", "feld": "stichtag", "wert": stichtag.isoformat()},
                   {"objekt": "grenze", "feld": "bereich", "wert": f"{lo}–{hi}"}]
        if not neu(holen(lo)):
            zeilen.append({"objekt": "grenze", "feld": "grenzseite",
                           "wert": f"nicht im Bereich (Seite {lo} ohne Vorlage ab {stichtag.isoformat()})"})
        elif neu(holen(hi)):
            zeilen.append({"objekt": "grenze", "feld": "grenzseite",
                           "wert": f"nicht im Bereich (Seite {hi} mit Vorlagen ab {stichtag.isoformat()})"})
        else:
            lo, hi = _bisektion(holen, lo, hi, lambda s: not neu(s))
            n_lo = infos[lo]["ab_stichtag"]
            zeilen += [{"objekt": "grenze", "feld": "grenzseite", "wert": hi},
                       {"objekt": "grenze", "feld": "letzte_seite_ab_stichtag", "wert": lo},
                       {"objekt": "grenze", "feld": "vorlagen_ab_stichtag",
                        "wert": f"{(lo - 1) * groesse + n_lo} (Schätzung bei {groesse} je Seite und Sortierung nach "
                                "date)"}]

        lo, hi = a.ende_seiten
        _listenende(holen, infos, lo, hi, groesse, "paper", zeilen)
    except Abbruch as e:
        zeilen.append({"objekt": "lauf", "feld": "abbruch", "wert": str(e)})
        raise
    finally:
        if infos:
            zeilen += [{"objekt": "sortierung", "feld": "date_absteigend", "wert": _sortierung(infos.values())},
                       {"objekt": "paper", "feld": "id_schema", "wert": ",".join(sorted(
                           {_schema(o.get("id")) for s in geholt.values() for o in s.get("data") or []
                            if isinstance(o, dict)})) or "–"}]
            _schreibe("oparl_umfang_seiten.tsv", [infos[n] for n in sorted(infos)])
        _schreibe("oparl_umfang.tsv", zeilen)


def umfang_liste(a):
    """`umfang --liste meeting|person`: Gesamtzahl einer weiteren Liste. Body und erste Seite (mit dem Cache aus Stufe 2
    ohne Anfrage); liefert `pagination.totalElements` eine Zahl, gilt sie ohne weitere Anfrage. Sonst das Listenende per
    Bisektion im Bereich --ende-seiten über konstruierte Seiten `?page=N` (seitenform). Nur Zahlen, Schlüssel und Form
    von links, keine Namen (Personen werden nur gezählt). Ergebnisse: oparl_umfang_<liste>.tsv,
    oparl_umfang_<liste>_seiten.tsv (Seite, Objekte, links)."""
    name = a.liste
    zeilen, infos, geholt = [], {}, {}
    stichtag = dt.date.fromisoformat(a.stichtag)
    try:
        body = _json(BODY)
        liste = body.get(name)
        if not liste:
            zeilen.append({"objekt": name, "feld": "url", "wert": "fehlt im Body"})
            return
        erste = _json(liste)
        geholt[1], infos[1] = erste, _seiteninfo(1, erste, stichtag)
        groesse = len(erste.get("data") or [])
        gesamt = _angabe(erste.get("pagination"), "totalElements")
        zeilen += [{"objekt": name, "feld": "url", "wert": liste},
                   {"objekt": name, "feld": "seitengroesse", "wert": groesse},
                   {"objekt": name, "feld": "pagination.totalElements", "wert": gesamt}]
        if gesamt != FEHLT:
            zeilen.append({"objekt": "ende", "feld": f"{name}_gesamt",
                           "wert": f"{gesamt} (pagination.totalElements, ohne weitere Anfrage)"})
            return
        adresse = seitenform(liste, erste)
        if adresse is None:
            zeilen.append({"objekt": "ende", "feld": f"{name}_gesamt",
                           "wert": f"{groesse} (nur eine Seite, kein links.next)"})
            return

        def holen(nr):
            if nr not in geholt:
                geholt[nr] = _json_von(adresse(nr))
                infos[nr] = _seiteninfo(nr, geholt[nr], stichtag)
            return geholt[nr]
        lo, hi = a.ende_seiten
        _listenende(holen, infos, lo, hi, groesse, name, zeilen)
    except Abbruch as e:
        zeilen.append({"objekt": "lauf", "feld": "abbruch", "wert": str(e)})
        raise
    finally:
        if infos:
            _schreibe(f"oparl_umfang_{name}_seiten.tsv", [
                {k: infos[n][k] for k in ("seite", "objekte", "links_schluessel", "links_next")} for n in sorted(infos)])
        _schreibe(f"oparl_umfang_{name}.tsv", zeilen)


def _praefix(kennung):
    m = RE_PRAEFIX.search(str(kennung or ""))
    return m.group(1) if m else "(ohne Präfix)"


def organisationen(a):
    """Organisationsliste bis zur Seitengrenze: je Organisation Kennung (unverändert), Präfix (gr, at, weitere), Name,
    Kurzname, organizationType, classification, Zeitraum; Zählung je Präfix und organizationType. Die Organisationen mit
    Präfix `at` dienen `pdf-koepfe` als Ämterliste."""
    body = _json(BODY)
    typen, zeilen = collections.Counter(), []
    for _, seite in _seiten(body["organization"], a.seiten, name="organization"):
        for o in seite.get("data", []):
            if not isinstance(o, dict):
                continue
            praefix = _praefix(o.get("id"))
            typen[(praefix, o.get("organizationType") or "(leer)")] += 1
            zeilen.append({"id": o.get("id"), "praefix": praefix, "name": o.get("name"), "kurz": o.get("shortName"),
                           "organizationType": o.get("organizationType"), "classification": o.get("classification"),
                           "startDate": o.get("startDate"), "endDate": o.get("endDate")})
    _schreibe("oparl_organisationen.tsv", zeilen)
    _schreibe("oparl_organisationstypen.tsv", [{"praefix": p, "organizationType": t, "anzahl": n}
                                                for (p, t), n in sorted(typen.items(), key=lambda x: (x[0][0], -x[1]))])
    e = _LISTEN[-1]
    je = collections.Counter(z["praefix"] for z in zeilen)
    print(f"{e['objekte']} Organisationen auf {e['seiten']} Seiten ({', '.join(f'{p} {n}' for p, n in je.items())}); "
          f"{e['ende']}")


def _reihenfolge(zeiten):
    """Reihenfolge einer Folge von Zeitpunkten: „aufsteigend“, „absteigend“ (gleiche Werte erlaubt), „ungeordnet“ oder
    „–“ (weniger als zwei)."""
    if len(zeiten) < 2:
        return "–"
    if all(a <= b for a, b in zip(zeiten, zeiten[1:])):
        return "aufsteigend"
    if all(a >= b for a, b in zip(zeiten, zeiten[1:])):
        return "absteigend"
    return "ungeordnet"


def sortierung_sitzungen(infos):
    """Urteil zur Sortierung der Sitzungsliste nach `start` über die abgerufenen Seiten (je Seite und zwischen den Seiten
    in der Reihenfolge der Seitennummer)."""
    gefuellt = [i for i in infos if i["start_min"]]
    if not gefuellt:
        return "nicht prüfbar (keine Sitzung mit start)"
    richtungen = {i["reihenfolge"] for i in gefuellt} - {"–"}
    if len(richtungen) == 1 and richtungen <= {"aufsteigend", "absteigend"}:
        richtung = richtungen.pop()
        paare = list(zip(gefuellt, gefuellt[1:]))
        verletzt = sum(1 for a, b in paare if (b["start_min"] < a["start_max"] if richtung == "aufsteigend"
                                               else b["start_max"] > a["start_min"]))
        if not verletzt:
            return f"{richtung} nach start ({len(gefuellt)} Seiten geprüft, je Seite und zwischen den Seiten)"
        return f"nein ({richtung} je Seite, {verletzt} Seitenübergänge verletzt; {len(gefuellt)} Seiten geprüft)"
    return f"nein (je Seite: {', '.join(sorted(i['reihenfolge'] for i in gefuellt))})"


def sitzungen(a):
    """Sitzungsliste bis zur Seitengrenze: Werte und Abdeckung von agendaItem.result, Anteil public, je Seite Zeitraum
    (`start` min/max), künftige Sitzungen und Reihenfolge nach `start`; result-Abdeckung getrennt nach vergangenen und
    künftigen Sitzungen (künftig: start nach dem Zeitpunkt der Messung). Bezug zur Stichprobe der Vorlagen besteht nicht
    (die Seiten zeigen nur einen Ausschnitt der Sitzungen)."""
    body = _json(BODY)
    jetzt = dt.datetime.now(ZoneInfo("Europe/Berlin"))
    ergebnisse, oeff, z = collections.Counter(), collections.Counter(), collections.Counter()
    infos = []
    for nr, seite in _seiten(body["meeting"], a.seiten, name="meeting"):
        zeiten = []
        info = {"seite": nr, "sitzungen": 0, "start_min": "", "start_max": "", "kuenftig": 0, "ohne_start": 0}
        for m in seite.get("data", []):
            if not isinstance(m, dict):
                continue
            z["Sitzungen insgesamt"] += 1
            info["sitzungen"] += 1
            t = _zeitpunkt(m["start"]) if m.get("start") else None
            zeit = "ohne start" if t is None else ("künftig" if t > jetzt else "vergangen")
            z[f"Sitzungen {zeit}"] += 1
            if t is None:
                info["ohne_start"] += 1
            else:
                zeiten.append(t)
                info["kuenftig"] += zeit == "künftig"
            for top in m.get("agendaItem") or []:
                if not isinstance(top, dict):
                    continue
                result = (top.get("result") or "").strip()
                z["TOPs insgesamt"] += 1
                z["TOPs mit result"] += bool(result)
                z[f"TOPs ({zeit})"] += 1
                z[f"TOPs mit result ({zeit})"] += bool(result)
                ergebnisse[result or "(leer)"] += 1
                oeff[str(top.get("public"))] += 1
        if zeiten:
            info["start_min"], info["start_max"] = min(zeiten).isoformat(), max(zeiten).isoformat()
        info["reihenfolge"] = _reihenfolge(zeiten)
        infos.append(info)
    _schreibe("oparl_top_ergebnisse.tsv", [{"result": k, "anzahl": v} for k, v in ergebnisse.most_common()]
              + [{"result": f"public={k}", "anzahl": v} for k, v in oeff.items()]
              + [{"result": k, "anzahl": z[k]} for k in ("TOPs mit result", "TOPs insgesamt", "Sitzungen insgesamt")])
    zusammen = [{"feld": k, "wert": z[k]} for k in (
        "Sitzungen insgesamt", "Sitzungen vergangen", "Sitzungen künftig", "Sitzungen ohne start",
        "TOPs (vergangen)", "TOPs mit result (vergangen)", "TOPs (künftig)", "TOPs mit result (künftig)",
        "TOPs (ohne start)", "TOPs mit result (ohne start)")]
    starts = [i[k] for i in infos for k in ("start_min", "start_max") if i[k]]
    zusammen += [{"feld": "start frühestes", "wert": min(starts) if starts else "–"},
                 {"feld": "start spätestes", "wert": max(starts) if starts else "–"},
                 {"feld": "Zeitpunkt der Messung", "wert": jetzt.isoformat(timespec="seconds")},
                 {"feld": "Sortierung nach start", "wert": sortierung_sitzungen(infos)}]
    _schreibe("oparl_sitzungen.tsv", zusammen)
    _schreibe("oparl_sitzungen_seiten.tsv", infos)


def verteilte_seiten(letzte, anzahl):
    """`anzahl` Seitennummern gleichmäßig über 1 … `letzte` (beide Enden enthalten); bei weniger Seiten alle."""
    if letzte < 1 or anzahl < 1:
        return []
    if letzte <= anzahl:
        return list(range(1, letzte + 1))
    if anzahl == 1:
        return [1]
    return sorted({1 + round(i * (letzte - 1) / (anzahl - 1)) for i in range(anzahl)})


def grenzseite_aus_umfang(datei=None):
    """Grenzseite G aus ergebnisse/oparl_umfang.tsv (Kommando `umfang`), sonst None."""
    datei = ERG / "oparl_umfang.tsv" if datei is None else Path(datei)
    if not datei.exists():
        return None
    with datei.open(encoding="utf-8", newline="") as f:
        for z in csv.DictReader(f, delimiter="\t"):
            if (z.get("objekt"), z.get("feld")) == ("grenze", "grenzseite") and str(z.get("wert")).isdigit():
                return int(z["wert"])
    return None


def _erste_datei(p):
    """(Adresse der ersten Datei aus auxiliaryFile – downloadUrl, sonst accessUrl –, Zahl der Dateien); Dateinamen und
    Volltexte werden nicht übernommen."""
    dateien = [f for f in p.get("auxiliaryFile") or [] if isinstance(f, dict)]
    erste = dateien[0] if dateien else {}
    return erste.get("downloadUrl") or erste.get("accessUrl"), len(dateien)


def _dateiliste(p):
    """Je Datei aus auxiliaryFile nur `name`, `fileName`, `mimeType` und die Adresse (downloadUrl, sonst accessUrl), in
    der Reihenfolge der Quelle; für die Wahl der Datei in pdf-koepfe (datei_waehlen). Nur in der Stichprobendatei im Cache
    (Namen können Personennamen enthalten), keine File-Objekte, kein Volltext."""
    return [{"name": f.get("name"), "fileName": f.get("fileName"), "mimeType": f.get("mimeType"),
             "url": f.get("downloadUrl") or f.get("accessUrl")}
            for f in p.get("auxiliaryFile") or [] if isinstance(f, dict)]


def _bedeckung(papers):
    felder = ["underDirectionOf", "originatorPerson", "originatorOrganization", "mainFile", "auxiliaryFile",
              "location", "keyword", "consultation", "relatedPaper", "superordinatedPaper", "subordinatedPaper", "date"]
    n = len(papers)
    zeilen = [{"feld": f, "vorhanden": sum(1 for p in papers if p.get(f)), "von": n} for f in felder]

    def beratungen(p):
        return [c for c in p.get("consultation") or []]
    zeilen += [
        {"feld": "underDirectionOf → organizations/at", "vorhanden": sum(
            1 for p in papers if p.get("underDirectionOf")
            and all(_praefix(u if isinstance(u, str) else (u or {}).get("id")) == "at" for u in p["underDirectionOf"])),
         "von": n},
        {"feld": "consultation als Verweis (nicht eingebettet)",
         "vorhanden": sum(1 for p in papers if any(isinstance(c, str) for c in beratungen(p))), "von": n}]
    for teil in ("meeting", "agendaItem", "role"):
        zeilen.append({"feld": f"consultation.{teil}", "vorhanden": sum(
            1 for p in papers if any(isinstance(c, dict) and c.get(teil) for c in beratungen(p))), "von": n})
    loc = collections.Counter()
    for p in papers:
        for l in p.get("location") or []:
            l = l if isinstance(l, dict) else {}
            for k in ("description", "streetAddress", "postalCode", "subLocality", "locality", "room", "geojson"):
                if l.get(k):
                    loc[k] += 1
    zeilen += [{"feld": f"location.{k}", "vorhanden": v, "von": n} for k, v in sorted(loc.items())]
    return zeilen


def stichprobe(a):
    """Stichprobe über 2020–2026 ohne Jahresfilter: `--seiten` Seiten gleichmäßig über 1 … G − 1 (G = Grenzseite aus
    `umfang` oder --grenzseite; Seite G − 1 ist die letzte mit Vorlagen ab dem Stichtag), abgerufen über konstruierte
    Seitenadressen (seitenform). Gezählt werden nur Vorlagen mit `date` vom Stichtag bis Ende --bis; ältere und jüngere
    werden verworfen und gezählt, ebenso doppelte Kennungen und Seiten, die nicht nach `date` absteigend sind. Ohne
    Grenzseite Abbruch vor der ersten Anfrage."""
    stichtag, ende = dt.date.fromisoformat(a.stichtag), dt.date(a.bis, 12, 31)
    g = a.grenzseite or grenzseite_aus_umfang()
    if not g:
        raise Abbruch(f"zuerst: umfang (keine Grenzseite in {ERG / 'oparl_umfang.tsv'}; oder --grenzseite)",
                      "voraussetzung")
    nummern = verteilte_seiten(g - 1, a.seiten)
    if not nummern:
        raise Abbruch(f"keine Seite vor der Grenzseite {g}", "voraussetzung")
    body = _json(BODY)
    liste = body["paper"]
    papers, gesehen, infos = [], set(), []
    zaehl = collections.Counter()   # vor_stichtag, nach_ende, doppelt, ohne_date
    vollstaendig = False
    try:
        erste = _json(liste)
        adresse = seitenform(liste, erste)
        if adresse is None and nummern != [1]:
            raise Abbruch("Vorlagenliste hat nur eine Seite (kein links.next)", "form")
        for nr in nummern:
            seite = erste if nr == 1 else _json_von(adresse(nr))
            infos.append(_seiteninfo(nr, seite, stichtag))
            for p in seite.get("data") or []:
                if not isinstance(p, dict):
                    continue
                if p.get("id") in gesehen:
                    zaehl["doppelt"] += 1
                    continue
                gesehen.add(p.get("id"))
                d = _datum(p)
                if d is None:
                    zaehl["ohne_date"] += 1
                elif d < stichtag:
                    zaehl["vor_stichtag"] += 1
                elif d > ende:
                    zaehl["nach_ende"] += 1
                else:
                    p["_seite"] = nr
                    papers.append(p)
        vollstaendig = True
    finally:
        if infos:   # Teilergebnis bei Abbruch; ohne Seiten bleiben frühere Ergebnisse unverändert
            _stichprobe_schreiben(papers, infos, zaehl, vollstaendig, stichtag, ende, g)
    print(f"{len(papers)} Vorlagen {stichtag.isoformat()} bis {ende.isoformat()} aus den Seiten "
          f"{', '.join(map(str, nummern))} (Grenzseite {g})")


def _stichprobe_schreiben(papers, infos, zaehl, vollstaendig, stichtag, ende, g):
    typen = collections.Counter(p.get("paperType") or "(leer)" for p in papers)
    ref = collections.Counter("VO/NNNN/JJ" if RE_VO.match(p.get("reference") or "") else "anderes" for p in papers)
    rollen = collections.Counter((c.get("role") or "(leer)") for p in papers for c in p.get("consultation") or []
                                 if isinstance(c, dict))
    jahre = collections.Counter(str(_datum(p).year) for p in papers)
    ohne_jahr = [j for j in range(stichtag.year, ende.year + 1) if str(j) not in jahre]
    if vollstaendig:   # nur eine vollständige Stichprobe dient pdf-koepfe als Grundlage
        STICHPROBE.parent.mkdir(parents=True, exist_ok=True)
        with STICHPROBE.open("w", encoding="utf-8") as f:
            for p in papers:
                datei, n = _erste_datei(p)
                f.write(json.dumps({"id": p.get("id"), "name": p.get("name"), "reference": p.get("reference"),
                                    "paperType": p.get("paperType"), "date": p.get("date"),
                                    "underDirectionOf": bool(p.get("underDirectionOf")), "datei": datei,
                                    "dateien": n, "dateiliste": _dateiliste(p)}, ensure_ascii=False) + "\n")
    geladen = len(papers) + sum(zaehl.values()) - zaehl["doppelt"]
    _schreibe("oparl_stichprobe_bedeckung.tsv", _bedeckung(papers) + [
        {"feld": f"Vorlagen {stichtag.isoformat()} bis {ende.isoformat()}", "vorhanden": len(papers), "von": geladen},
        {"feld": "verworfen: date vor dem Stichtag", "vorhanden": zaehl["vor_stichtag"], "von": geladen},
        {"feld": "verworfen: date nach dem Ende", "vorhanden": zaehl["nach_ende"], "von": geladen},
        {"feld": "verworfen: ohne lesbares date", "vorhanden": zaehl["ohne_date"], "von": geladen},
        {"feld": "doppelte Kennungen", "vorhanden": zaehl["doppelt"], "von": geladen + zaehl["doppelt"]},
        {"feld": "Seiten nicht absteigend nach date", "vorhanden": sum(1 for i in infos
                                                                        if i["absteigend"].startswith("nein")),
         "von": len(infos)},
        {"feld": f"Jahre {stichtag.year}–{ende.year} ohne Vorlage", "vorhanden": len(ohne_jahr),
         "von": ende.year - stichtag.year + 1},
        {"feld": f"Seiten (Grenzseite {g})", "vorhanden": len(infos), "von": len(infos)}])
    _schreibe("oparl_stichprobe_seiten.tsv", infos)
    _schreibe("oparl_papertypen.tsv", [{"paperType": k, "anzahl": v} for k, v in typen.most_common()])
    _schreibe("oparl_beratungsrollen.tsv", [{"role": k, "anzahl": v} for k, v in rollen.most_common()])
    _schreibe("oparl_referenzschema.tsv", [{"schema": k, "anzahl": v} for k, v in ref.most_common()])
    _schreibe("oparl_stichprobe_jahre.tsv", [{"jahr": j, "objekte": n} for j, n in sorted(jahre.items())])


def jahr_der_vorlage(p):
    """Jahr aus der Referenz VO/NNNN/JJ (20JJ), sonst aus `date`, sonst „?“."""
    ref = p.get("reference") or ""
    if RE_VO.match(ref):
        return f"20{ref[-2:]}"
    return str(p.get("date") or "")[:4] or "?"


def auswahl_je_jahr(vorlagen, anzahl):
    """Gleichmäßig über die Jahre (jahr_der_vorlage): reihum je Jahr, neuere Jahre zuerst, damit ein Rest bei
    ungleicher Teilung den aktuellen Vorlagenköpfen zugutekommt."""
    je_jahr = collections.defaultdict(list)
    for p in vorlagen:
        je_jahr[jahr_der_vorlage(p)].append(p)
    gruppen = [je_jahr[j] for j in sorted(je_jahr, reverse=True)]
    aus = [g[i] for i in range(max(map(len, gruppen), default=0)) for g in gruppen if i < len(g)]
    return aus[:anzahl]


def aemterliste(datei=None):
    """Organisationen mit Präfix `at` aus ergebnisse/oparl_organisationen.tsv (Kommando `organisationen`) als Liste
    (Kennung, Name und Kurzname); None, wenn die Datei fehlt."""
    datei = ERG / "oparl_organisationen.tsv" if datei is None else Path(datei)
    if not datei.exists():
        return None
    with datei.open(encoding="utf-8", newline="") as f:
        return [(z["id"], f"{z.get('name') or ''} {z.get('kurz') or ''}") for z in csv.DictReader(f, delimiter="\t")
                if z.get("praefix") == "at"]


def amt_abgleichen(nummer, aemter):
    """Abgleich einer erkannten Nummer (z. B. „402“) mit der Ämterliste: Kennung der einzigen at-Organisation, deren Name
    oder Kurzname die Nummer als eigenes Zahlwort enthält; sonst „mehrdeutig (n)“ oder „kein Treffer in
    organizations/at“; ohne Ämterliste „Ämterliste fehlt (zuerst organisationen)“, mit leerer „Ämterliste leer (…)“
    (z. B. Seitengrenze vor den at-Organisationen: organisationen bis zum Ende der Liste, STUFEN.md Stufe 4)."""
    if aemter is None:
        return "Ämterliste fehlt (zuerst organisationen)"
    if not aemter:
        return "Ämterliste leer (keine Organisation mit Präfix at erfasst)"
    muster = re.compile(rf"(?<!\d)(?<!\d\.){re.escape(nummer)}(?!\d|\.\d)")   # Satzpunkt erlaubt, Teilnummer nicht
    treffer = [k for k, text in aemter if muster.search(text)]
    if len(treffer) == 1:
        return treffer[0]
    return f"mehrdeutig ({len(treffer)})" if treffer else "kein Treffer in organizations/at"


def pdf_grenze(umgebung=None):
    """Größengrenze einer PDF-Datei in Bytes: PDF_MAX_BYTES; RATSATLAS_PDF_MAX_BYTES darf sie nur senken (Tests),
    unlesbare oder höhere Werte gelten nicht."""
    env = os.environ if umgebung is None else umgebung
    try:
        wert = int(env.get("RATSATLAS_PDF_MAX_BYTES") or PDF_MAX_BYTES)
    except ValueError:
        return PDF_MAX_BYTES
    return wert if 0 < wert <= PDF_MAX_BYTES else PDF_MAX_BYTES


def _referenzmuster(reference):
    """Muster für die Referenz VO/NNNN/JJ in einem Dateinamen (Trenner /, _, -, Punkt oder Leerzeichen; führende
    Nullen und „20“ vor dem Jahr frei), sonst None."""
    m = re.fullmatch(r"VO/(\d{4})/(\d{2})", reference or "")
    if not m:
        return None
    return re.compile(rf"(?<!\d)0*{int(m.group(1))}\s*[/_\-. ]\s*(?:20)?{m.group(2)}(?!\d)")


def datei_waehlen(p):
    """(Adresse, Platz ab 1, Zahl der Dateien, Regel) der Datei, deren Kopf gelesen wird. Annahme (an Stufe 6 zu prüfen):
    zuerst eine Datei, deren `name` oder `fileName` die Referenz der Vorlage nennt, dann eine, die „Vorlage“,
    „Beschlussvorlage“, „Verwaltungsvorlage“, „Drucksache“ oder den paperType nennt; jeweils nicht als Anlage oder Anhang
    bezeichnet und nicht mit einem mimeType ohne „pdf“. Sonst die erste Datei mit Adresse. Eine Stichprobendatei ohne
    Dateiliste (vor der Ergänzung erzeugt) liefert die erste Datei. Ohne Adresse: (None, 0, n, Grund)."""
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
    """Zeilen des Seitentexts ohne Leerzeilen: geschützte und schmale Leerzeichen → Leerzeichen, Bindestrich-Varianten →
    „-“, weiche Trennzeichen entfernt, Silbentrennung am Zeilenende verbunden („Stadt-“ + „betrieb“ → „Stadtbetrieb“,
    nur vor einem Kleinbuchstaben), Leerraum je Zeile zusammengefasst."""
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").translate(_ZEICHEN)
    t = re.sub(r"(?<=[^\W\d_])- *\n *(?=[a-zäöüß])", "", t)
    return [z for z in (" ".join(teil.split()) for teil in t.split("\n")) if z]


def _hat_text(zeilen):
    return any(re.search(r"\w", z) for z in zeilen)


def kopf_kandidaten(zeilen):
    """Alle Kandidaten (Bezeichnung mit Nummer, RE_AMT) einer Seite: je Kandidat Bezeichnung, Nummer, Kennung, Zeile
    (ab 1, ohne Leerzeilen) und ob er im Kopf steht (vor dem ersten Abschnitt RE_ABSCHNITT; ohne Abschnitt in den ersten
    KOPF_ZEILEN Zeilen, Annahme). Liefert (Kandidaten, Zeile des ersten Abschnitts oder None). Kein Text im Ergebnis."""
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
    """(Kandidat oder None, Lage, Regel) nach der Regel (Annahme): Unter den Kandidaten im Kopf gilt der erste mit
    belegter Bezeichnung (Ressort, Amt) als federführend, sonst der erste. Lage: „keiner“, „ein Kandidat“, „mehrere
    gleiche“ (gleiche Kennung) oder „mehrere verschiedene“ (nur Kandidaten im Kopf); Kandidaten nur außerhalb des Kopfes:
    kein federführender."""
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


def erzeuger_klasse(metadaten):
    """Grobe Klasse des PDF-Erzeugers aus Producer und Creator (ERZEUGER_KLASSEN), „andere“ oder „fehlt“; die Rohwerte
    werden nicht zurückgegeben."""
    try:
        werte = " ".join(str(metadaten.get(k) or "") for k in ("/Producer", "/Creator")).lower() if metadaten else ""
    except Exception:   # unlesbare Metadaten
        return "unlesbar"
    if not werte.strip():
        return "fehlt"
    return next((klasse for klasse, woerter in ERZEUGER_KLASSEN if any(w in werte for w in woerter)), "andere")


@contextlib.contextmanager
def _pypdf_still():
    """Meldungen von pypdf (logging und warnings) unterdrücken: Sie könnten Inhalte der Datei nennen."""
    logger = logging.getLogger("pypdf")
    pegel = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        logger.setLevel(pegel)


def pdf_kennung(inhalt):
    """Dateikennung: „%PDF-“ in den ersten 1024 Bytes (wie PDF-Leser es dulden; nicht nur am Dateianfang). Dieselbe
    Regel gilt für die Spalte `pdf_kennung` und für die Prüfung auf eine HTML-Seite in _pdf_holen."""
    return b"%PDF-" in inhalt[:1024]


def html_statt_pdf(inhalt):
    """HTML-Seite statt PDF (mögliche Sperr- oder Fehlerseite): ohne Dateikennung, mit einem HTML-Element am Anfang."""
    return not pdf_kennung(inhalt) and bool(re.search(rb"<(?:!doctype|html|head|body)\b", inhalt[:1024].lower()))


def pdf_auswerten(inhalt, aemter):
    """Messwerte und Kopferkennung einer PDF-Datei als Spalten von pdf_koepfe.tsv, ohne Textinhalt: Dateikennung,
    Seiten, Textebene (Seite 1, bei leerem Text Seite 2), Klasse des Erzeugers, Kandidaten mit Zeile und Lage, der
    federführende Kandidat (federfuehrend) und sein Abgleich mit organizations/at (amt_abgleichen). Meldungen von pypdf
    werden unterdrückt."""
    with _pypdf_still():
        return _pdf_auswerten(inhalt, aemter)


def _pdf_auswerten(inhalt, aemter):
    from pypdf import PdfReader
    z = {"pdf_kennung": "ja" if pdf_kennung(inhalt) else "nein"}
    if z["pdf_kennung"] == "nein":
        return {**z, "treffer": "kein PDF"}
    try:
        r = PdfReader(io.BytesIO(inhalt))
        if r.is_encrypted:
            try:
                entschluesselt = r.decrypt("")
            except Exception:
                entschluesselt = 0
            if not entschluesselt:
                return {**z, "treffer": "verschlüsselt"}
        seiten = len(r.pages)
        z["seiten"] = seiten
        if not seiten:
            return {**z, "treffer": "fehler: keine Seite"}
        z["erzeuger"] = erzeuger_klasse(r.metadata)
        zeilen, nr = text_normalisieren(r.pages[0].extract_text() or ""), 1
        if not _hat_text(zeilen) and seiten > 1:   # höchstens Seite 2, als eigene Fundstelle
            zeilen, nr = text_normalisieren(r.pages[1].extract_text() or ""), 2
    except Exception as e:   # einzelne defekte Dateien sollen die Messung nicht abbrechen (nur der Name der Ausnahme)
        return {**z, "treffer": f"fehler: {type(e).__name__}"}
    if not _hat_text(zeilen):
        return {**z, "treffer": "kein_text", "textebene": "nein (OCR nötig)",
                "fundstelle": "Seite 1" + (" und 2" if seiten > 1 else "")}
    kandidaten, abschnitt = kopf_kandidaten(zeilen)
    feder, lage, regel = federfuehrend(kandidaten)
    z.update(textebene="ja" if nr == 1 else "ja (ab Seite 2)", fundstelle=f"Seite {nr}", zeilen=len(zeilen),
             abschnitt_zeile=abschnitt or f"kein Abschnitt (Kopf = erste {KOPF_ZEILEN} Zeilen, Annahme)",
             kandidaten_n=len(kandidaten), kandidaten_kopf=sum(1 for k in kandidaten if k["kopf"]), lage=lage,
             kandidaten="; ".join(f"{k['kennung']} Z{k['zeile']} {'Kopf' if k['kopf'] else 'außerhalb'}"
                                  for k in kandidaten), regel=regel,
             treffer="kennung" if feder else ("nur außerhalb des Kopfes" if kandidaten else "nein"))
    if feder:
        z.update(bezeichnung=feder["bezeichnung"], kennung=feder["kennung"], zeile=feder["zeile"],
                 bezeichnung_beleg=("belegt (CLAUDE.md 3.1/3.2)" if feder["bezeichnung"] in BEZEICHNUNG_BELEGT
                                    else "Annahme"),
                 vor_abschnitt="ja" if abschnitt else "kein Abschnitt erkannt",
                 abgleich=amt_abgleichen(feder["nummer"], aemter))
    return z


def _protokollzeile(url):
    """Letzte Netzzeile des Abrufprotokolls (_cache/abrufe.tsv) zur Abrufadresse: Status, Bytes, Dauer; sonst None."""
    adresse = abruf.abrufadresse(url)
    if not abruf.PROTOKOLL.exists():
        return None
    with abruf.PROTOKOLL.open(encoding="utf-8", newline="") as f:
        zeilen = [z for z in csv.DictReader(f, delimiter="\t") if z.get("url") == adresse and z.get("quelle") == "netz"]
    return zeilen[-1] if zeilen else None


PDF_SPALTEN = ("id", "reference", "jahr", "paperType", "datei", "auswahl", "treffer", "fundstelle", "textebene",
               "seiten", "bytes", "pdf_kennung", "erzeuger", "antwort_s", "quelle", "zeilen", "abschnitt_zeile",
               "kandidaten_n", "kandidaten_kopf", "lage", "kandidaten", "regel", "bezeichnung", "bezeichnung_beleg",
               "kennung", "zeile", "vor_abschnitt", "abgleich")


def _html_entfernen(url):
    """Cache-Eintrag einer HTML-Antwort samt Begleitdatei entfernen."""
    pfad = abruf._cachepfad(url, ".pdf")
    pfad.unlink(missing_ok=True)
    abruf._begleitpfad(pfad).unlink(missing_ok=True)


def _pdf_holen(url, z):
    """Holt eine PDF-Datei über _hole (Freigabe, Zeitfenster, strenge Vorgaben, 12-Stunden-Regel); trägt Quelle (netz
    oder cache) und Antwortzeit aus dem Abrufprotokoll in `z` ein. Liefert den Inhalt oder None (Datei übersprungen:
    HTTP 404/410, größer als die Grenze). Eine HTML-Antwort (mögliche Sperr- oder Fehlerseite) wird aus dem Cache
    entfernt und bricht ab (Art `inhalt`), auch wenn sie zugleich zu langsam war; jeder andere Abbruch wird vermerkt
    und weitergereicht.
    Ohne Änderung an abruf.py nachgezogen (abruf.hole prüft die Größe vor der Antwortzeit und speichert vor der Prüfung
    auf `langsam`): Eine Datei über der Größengrenze, deren Antwort länger als RATSATLAS_MAX_DAUER dauerte, beendet den
    Lauf wie jede langsame Antwort (Art `langsam`); eine langsame Antwort, die HTML ist, wird aus dem Cache entfernt."""
    vorher = abruf.zaehler()["netz"]
    try:
        inhalt = _hole(url, ".pdf")
    except Abbruch as e:
        zeile = _protokollzeile(url) if abruf.zaehler()["netz"] > vorher else None
        if zeile:
            z.update(quelle="netz", antwort_s=zeile.get("dauer_s", ""))
        if e.art == "http" and e.code in (404, 410):   # einzelne fehlende Datei: weiter
            z["treffer"] = f"fehler: HTTP {e.code}"
            return None
        if e.art == "groesse":   # nicht gespeichert, nicht gelesen; abruf.py hat höchstens Grenze + 1 Byte gelesen
            z.update(treffer="zu groß", bytes=f"> {abruf.MAX_BYTES}")
            try:
                dauer = float(zeile.get("dauer_s") or 0) if zeile else 0.0
            except ValueError:
                dauer = 0.0
            if abruf.MAX_DAUER and dauer > abruf.MAX_DAUER:   # Antwortzeit gilt auch für zu große Dateien
                z["treffer"] = "abbruch (langsam)"
                raise Abbruch(f"Antwortzeit {dauer:.1f} s über {abruf.MAX_DAUER:g} s (RATSATLAS_MAX_DAUER) bei einer "
                              f"Datei über der Größengrenze (nicht gespeichert): {url}", "langsam") from e
            return None
        if e.art == "langsam":   # abruf.py hat die Antwort vor dieser Prüfung gespeichert
            pfad = abruf._cachepfad(url, ".pdf")
            if pfad.exists() and html_statt_pdf(pfad.read_bytes()[:1024]):
                _html_entfernen(url)
                z["treffer"] = "abbruch (inhalt)"
                raise Abbruch(f"HTML statt PDF (mögliche Sperr- oder Fehlerseite), aus dem Cache entfernt; dazu: {e}",
                              "inhalt") from e
        z["treffer"] = f"abbruch ({e.art or 'sonstiges'})"
        raise
    netz = abruf.zaehler()["netz"] > vorher
    zeile = _protokollzeile(url)
    z.update(quelle="netz" if netz else "cache", antwort_s=zeile.get("dauer_s", "") if zeile else "", bytes=len(inhalt))
    if html_statt_pdf(inhalt):
        _html_entfernen(url)
        z["treffer"] = "abbruch (inhalt)"
        raise Abbruch(f"HTML statt PDF (mögliche Sperr- oder Fehlerseite), aus dem Cache entfernt: {url}", "inhalt")
    return inhalt


def pdf_koepfe(a):
    """Stufe 6: Kopf einer Datei aus auxiliaryFile (datei_waehlen) von bis zu --anzahl Verwaltungsvorlagen ohne
    underDirectionOf aus der Stichprobe, gleichmäßig über die Jahre; eine Anfrage je ausgewählter Vorlage. Als
    Verwaltungsvorlage gilt eine Vorlage, deren paperType laut explore/paperType_regeln.tsv keine Einreichenden nennt
    (Annahme, an der Liste der paperType aus Stufe 5 zu prüfen). Je Datei Messwerte und Kopferkennung (pdf_auswerten)
    in pdf_koepfe.tsv, die Zählungen der Stichprobe für die Hochrechnung in pdf_koepfe_grundlage.tsv; keine Textauszüge,
    keine Namen, Telefonnummern oder E-Mail-Adressen. Größengrenze: abruf.MAX_BYTES wird für die Dauer des Kommandos auf
    pdf_grenze() gesenkt (abruf.py bleibt unverändert)."""
    from pypdf import PdfReader  # noqa: F401  (fehlt pypdf, endet das Kommando vor der ersten Anfrage)
    import auswertung

    if not STICHPROBE.exists():
        raise Abbruch(f"zuerst: stichprobe ({STICHPROBE} fehlt; die Datei entsteht nur bei einer vollständigen "
                      "Stichprobe in derselben Arbeitsumgebung)", "voraussetzung")
    regeln = auswertung.regeln_laden()
    papers = [json.loads(z) for z in STICHPROBE.open(encoding="utf-8")]
    verwaltung = [p for p in papers if auswertung.ohne_einreichende(p.get("paperType"), regeln)]
    ohne = [p for p in verwaltung if not p.get("underDirectionOf")]
    mit_datei = [p for p in ohne if datei_waehlen(p)[0]]
    vv = auswahl_je_jahr(mit_datei, a.anzahl)
    aemter = aemterliste()
    grenze = pdf_grenze()
    jahre = collections.Counter(jahr_der_vorlage(p) for p in vv)
    # Bestand je Jahr für die gewichtete Hochrechnung (die Auswahl ist gleich je Jahr, nicht proportional)
    bestand = collections.Counter(jahr_der_vorlage(p) for p in mit_datei)
    _schreibe("pdf_koepfe_grundlage.tsv", [
        {"feld": "stichprobe_vorlagen", "wert": len(papers)},
        {"feld": "mit_underDirectionOf", "wert": sum(1 for p in papers if p.get("underDirectionOf"))},
        {"feld": "verwaltungsvorlagen", "wert": len(verwaltung)},
        {"feld": "verwaltung_ohne_underDirectionOf", "wert": len(ohne)},
        {"feld": "verwaltung_ohne_underDirectionOf_mit_datei", "wert": len(mit_datei)},
        {"feld": "ausgewaehlt", "wert": len(vv)},
        {"feld": "anzahl", "wert": a.anzahl},
        {"feld": "pdf_max_bytes", "wert": grenze},
        {"feld": "aemterliste", "wert": "fehlt" if aemter is None else len(aemter)},
        *({"feld": f"ausgewaehlt_{j}", "wert": n} for j, n in sorted(jahre.items())),
        *({"feld": f"verwaltung_ohne_underDirectionOf_mit_datei_{j}", "wert": n} for j, n in sorted(bestand.items()))])
    print(f"{len(verwaltung)} Verwaltungsvorlagen (paperType ohne Einreichende) in der Stichprobe, {len(ohne)} ohne "
          f"underDirectionOf, {len(mit_datei)} davon mit Datei; Auswahl {len(vv)}: "
          + ", ".join(f"{j} {n}" for j, n in sorted(jahre.items()))
          + ("" if aemter is not None else "; Ämterliste fehlt (organisationen)"))
    zeilen = []
    alt_max = abruf.MAX_BYTES
    abruf.MAX_BYTES = min(alt_max, grenze)
    try:
        for p in vv:
            url, platz, n, regel = datei_waehlen(p)
            z = dict.fromkeys(PDF_SPALTEN, "")
            z.update(id=p["id"], reference=p.get("reference"), jahr=jahr_der_vorlage(p), paperType=p.get("paperType"),
                     datei=f"auxiliaryFile {platz} von {n}", auswahl=regel, treffer="nicht abgerufen")
            zeilen.append(z)
            inhalt = _pdf_holen(url, z)
            if inhalt is not None:
                z.update(pdf_auswerten(inhalt, aemter))
    finally:
        abruf.MAX_BYTES = alt_max
        _schreibe("pdf_koepfe.tsv", zeilen)
    print(dict(collections.Counter(z["treffer"] for z in zeilen)))


KOMMANDOS = {"test": test, "kennzahlen": kennzahlen, "umfang": umfang, "organisationen": organisationen,
             "sitzungen": sitzungen, "stichprobe": stichprobe, "pdf-koepfe": pdf_koepfe}
LAEUFE_SPALTEN = ["lauf", "stufe", "kommando", "parameter", "start", "ende", "dauer_s", "netz", "cache",
                  "obergrenze", "protokoll_von", "protokoll_bis", "ergebnis", "meldung"]
LISTEN_SPALTEN = ["lauf", "liste", "grenze", "seiten", "objekte", "ende", "erstes_next", "url"]


def _parameter(a):
    if a.kommando in ("organisationen", "sitzungen"):
        return f"--seiten {a.seiten}"
    if a.kommando == "umfang" and a.liste != "paper":
        return f"--liste {a.liste} --ende-seiten {a.ende_seiten[0]} {a.ende_seiten[1]}"
    if a.kommando == "umfang":
        return (f"--grenze-seiten {a.grenze_seiten[0]} {a.grenze_seiten[1]} --ende-seiten {a.ende_seiten[0]} "
                f"{a.ende_seiten[1]} --stichtag {a.stichtag}")
    if a.kommando == "stichprobe":
        return f"--seiten {a.seiten}" + (f" --grenzseite {a.grenzseite}" if a.grenzseite else "")
    return f"--anzahl {a.anzahl}" if a.kommando == "pdf-koepfe" else ""


def _laufnummer():
    datei = ERG / "oparl_laeufe.tsv"
    if not datei.exists():
        return 1
    with datei.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f), 1)


def _markerpfad():
    return abruf.PROTOKOLL.parent / MARKER


def _marker_setzen(lauf):
    """Legt die Markerdatei an (Lauf, Stufe, Kommando, Parameter, Start, Prozess); liefert ihren Inhalt."""
    text = json.dumps({**{k: lauf[k] for k in ("lauf", "stufe", "kommando", "parameter", "start")}, "pid": os.getpid()},
                      ensure_ascii=False)
    pfad = _markerpfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")
    return text


def _marker_entfernen(text):
    """Entfernt die Markerdatei, wenn sie noch die dieses Laufs ist."""
    try:
        if _markerpfad().read_text(encoding="utf-8") == text:
            _markerpfad().unlink()
    except OSError:
        pass


def _marker_pruefen(marker, zeilen, jetzt):
    """Markerdatei eines Laufs ohne Vermerk in oparl_laeufe.tsv: jünger als SPERRFRIST (oder unlesbar) → Eintrag wie
    eine Zeile mit „nicht regulär beendet“; älter → gemeldet und entfernt; ein Marker, dessen Lauf vermerkt ist (Ende
    zwischen Vermerk und Entfernen), wird ebenfalls entfernt (der Vermerk gilt). Sonst None."""
    if not marker.exists():
        return None
    try:
        m = json.loads(marker.read_text(encoding="utf-8"))
        m = m if isinstance(m, dict) else {}
    except (OSError, ValueError):
        m = {}
    if m and any(z.get("lauf") == str(m.get("lauf")) and z.get("start") == m.get("start") for z in zeilen):
        marker.unlink(missing_ok=True)
        return None
    start = _zeitpunkt(m.get("start") or "") if m else None
    eintrag = {"lauf": m.get("lauf", "?"), "stufe": m.get("stufe", ""), "kommando": m.get("kommando", "?"),
               "start": m.get("start", ""), "ende": "", "ergebnis": NICHT_REGULAER, "marker": str(marker),
               "meldung": f"Markerdatei {marker} ohne Vermerk in oparl_laeufe.tsv"}
    if start is None or jetzt - start < SPERRFRIST:
        return eintrag
    print(f"Hinweis: Lauf {eintrag['lauf']} ({eintrag['kommando']}, Stufe {eintrag['stufe'] or '?'}) vom "
          f"{eintrag['start']} wurde {NICHT_REGULAER} (Markerdatei {marker} ohne Vermerk, älter als "
          f"{SPERRFRIST.total_seconds() / 3600:g} Stunden); Marker entfernt. Im Bericht vermerken.", file=sys.stderr)
    marker.unlink(missing_ok=True)
    return None


def letzter_abbruch(datei=None, jetzt=None, marker=None):
    """Der letzte Lauf aus oparl_laeufe.tsv (Zeile als dict), wenn er vor weniger als SPERRFRIST mit „abbruch (…)“,
    „fehler (…)“ oder „unterbrochen“ (Strg+C, SIGTERM, SIGHUP) endete, sonst None. Maßgeblich ist `ende` (ohne Zone:
    Ortszeit Europe/Berlin); fehlt es oder ist es unlesbar, gilt der Lauf vorsichtshalber als gerade beendet. Vorher die
    Markerdatei (`marker`; Vorgabe neben _cache/abrufe.tsv, nur wenn auch `datei` die Vorgabe ist): Ein Lauf ohne
    Vermerk, der vor weniger als SPERRFRIST begann (hart beendet), gilt als „nicht regulär beendet“ (_marker_pruefen)."""
    if datei is None:
        datei, marker = ERG / "oparl_laeufe.tsv", _markerpfad() if marker is None else marker
    datei, zeilen = Path(datei), []
    if datei.exists():
        with datei.open(encoding="utf-8", newline="") as f:
            zeilen = list(csv.DictReader(f, delimiter="\t"))
    jetzt = jetzt or dt.datetime.now(ZoneInfo("Europe/Berlin"))
    offen = _marker_pruefen(Path(marker), zeilen, jetzt) if marker is not None else None
    if offen:
        return offen
    if not zeilen or not RE_ABBRUCH.match(zeilen[-1].get("ergebnis") or ""):
        return None
    letzter = zeilen[-1]
    ende = _zeitpunkt(letzter.get("ende") or "")
    return letzter if ende is None or jetzt - ende < SPERRFRIST else None


def _signal_beenden(nummer, _rahmen):
    """Strg+C, SIGTERM oder SIGHUP: endet wie Strg+C, damit der Lauf als „unterbrochen“ vermerkt wird (12-Stunden-Regel).
    Weitere Signale bleiben ab hier ohne Wirkung (_signal_ohne_wirkung; ein zweites kurz danach unterbräche sonst den
    Vermerk)."""
    _signale(_signal_ohne_wirkung)
    raise KeyboardInterrupt(signal.Signals(nummer).name)


def _signal_ohne_wirkung(_nummer, _rahmen):
    """Ein weiteres Signal nach dem ersten: ohne Wirkung (statt SIG_IGN, damit ein schon zugestelltes Signal keine
    Meldung „ignored due to race condition“ erzeugt)."""


def _signale(behandlung, signale=(signal.SIGINT, *SIGNALE)):
    """Setzt die Behandlung der Signale; liefert die vorige je Signal."""
    return {s: signal.signal(s, behandlung) for s in signale}


def _signale_abfangen():
    """_signal_beenden für Strg+C (nur statt der Vorgabe von Python; im Hintergrund ignoriert bleibt ignoriert), SIGTERM
    und SIGHUP (nur bei SIG_DFL: mit nohup bleibt SIGHUP ignoriert). Liefert die vorige Behandlung aller drei Signale."""
    vorher = {s: signal.getsignal(s) for s in (signal.SIGINT, *SIGNALE)}
    for s, alt in vorher.items():
        if (s == signal.SIGINT and alt is not signal.default_int_handler) or (s == signal.SIGHUP
                                                                             and alt != signal.SIG_DFL):
            continue
        signal.signal(s, _signal_beenden)
    return vorher


def main(argv=None):
    global _sperrfrist_geprueft
    ap = argparse.ArgumentParser()
    ap.add_argument("kommando", choices=list(KOMMANDOS))
    ap.add_argument("--seiten", type=int, default=None,
                    help="stichprobe: Zahl der verteilten Seiten (Vorgabe 8); organisationen (5), sitzungen (2): Seiten "
                         "der Liste, 0 = ohne Seitengrenze")
    ap.add_argument("--grenze-seiten", type=int, nargs=2, default=list(GRENZE_SEITEN), metavar=("VON", "BIS"),
                    help="umfang: Bereich für die Seite mit der Datumsgrenze (CLAUDE.md 3.1: 50 150)")
    ap.add_argument("--ende-seiten", type=int, nargs=2, default=None, metavar=("VON", "BIS"),
                    help="umfang: Bereich für die letzte Seite (Vorlagen laut CLAUDE.md 3.1: 240 gefüllt, 250 leer; "
                         "für --liste meeting|person Pflicht, festzulegen nach Stufe 2/4)")
    ap.add_argument("--liste", choices=("paper", "meeting", "person"), default="paper",
                    help="umfang: Liste (Vorgabe paper; meeting und person nur Listenende und Gesamtzahl)")
    ap.add_argument("--stichtag", default=STICHTAG, help="umfang, stichprobe: Vorlagen mit date ab diesem Tag")
    ap.add_argument("--bis", type=int, default=2026, help="stichprobe: letztes Jahr")
    ap.add_argument("--grenzseite", type=int, default=None,
                    help="stichprobe: Grenzseite statt des Werts aus ergebnisse/oparl_umfang.tsv")
    ap.add_argument("--anzahl", type=int, default=100)
    a = ap.parse_args(argv)
    if a.kommando == "pdf-koepfe" and not 1 <= a.anzahl <= PDF_HOECHSTENS:
        ap.error(f"--anzahl: 1 bis {PDF_HOECHSTENS} (Stufe 6, explore/STUFEN.md)")
    if a.seiten is None:
        a.seiten = SEITEN_VORGABE.get(a.kommando, 2)
    if a.ende_seiten is None:
        if a.kommando == "umfang" and a.liste != "paper":
            ap.error("--ende-seiten ist mit --liste meeting|person Pflicht (Bereich nach Stufe 2/4 festlegen, "
                     "explore/STUFEN.md)")
        a.ende_seiten = list(ENDE_SEITEN)
    for name in ("grenze_seiten", "ende_seiten"):
        von, bis = getattr(a, name)
        if not 1 <= von < bis:
            ap.error(f"--{name.replace('_', '-')}: 1 ≤ VON < BIS")
    if not (lokal(SYSTEM) and lokal(BODY)):
        if os.environ.get("RATSATLAS_MESSUNG_FREIGEGEBEN") != "ja":
            sys.exit(f"Abbruch: Messung bei der Stadt {STADT} nicht freigegeben (CLAUDE.md 9: eigene Freigabe je Stufe). "
                     "Erst nach Freigabe mit RATSATLAS_MESSUNG_FREIGEGEBEN=ja ausführen.")
        if not (im_zeitfenster(url=SYSTEM) and im_zeitfenster(url=BODY)):
            sys.exit(f"Abbruch: außerhalb des Zeitfensters {os.environ.get('RATSATLAS_ZEITFENSTER', '23-1')} Uhr "
                     "Ortszeit (RATSATLAS_ZEITFENSTER; leer oder weiter als 23–1 Uhr nur für Testadressen).")
        if a.kommando == "pdf-koepfe" and os.environ.get("RATSATLAS_PDF_FREIGEGEBEN") != "ja":
            sys.exit("Abbruch: PDF-Abruf nur nach eigener Freigabe der Stufe 6 (RATSATLAS_PDF_FREIGEGEBEN=ja, "
                     "explore/STUFEN.md).")
        werte, fehler = sichere_vorgaben()
        if fehler:
            sys.exit("Abbruch vor der ersten Anfrage: " + "; ".join(fehler) + " (Befehle: explore/STUFEN.md).")
        vorher = letzter_abbruch()
        if vorher and os.environ.get("RATSATLAS_NACH_ABBRUCH") != "ja":
            grund = (f"Lauf {vorher.get('lauf')} ({vorher.get('kommando')}) vom {vorher.get('start') or '?'} wurde "
                     f"„{NICHT_REGULAER}“ oder läuft noch (Markerdatei {vorher['marker']} ohne Vermerk in "
                     "oparl_laeufe.tsv, etwa nach SIGKILL oder einem Absturz der Arbeitsumgebung); begonnen"
                     if vorher.get("marker") else
                     f"Lauf {vorher.get('lauf')} ({vorher.get('kommando')}) endete {vorher.get('ende') or '(ohne Ende)'}"
                     f" mit „{vorher.get('ergebnis')}“")
            sys.exit(f"Abbruch vor der ersten Anfrage: {grund}, vor weniger als "
                     f"{SPERRFRIST.total_seconds() / 3600:g} Stunden. Nach einem Abbruch gilt: in dieser Nacht keine "
                     "weitere Anfrage und keine weitere Stufe, Bericht an den Auftraggeber (explore/STUFEN.md). "
                     "Weiter nur nach Rücksprache mit RATSATLAS_NACH_ABBRUCH=ja.")
        abruf.WIEDERHOLUNGEN, abruf.MAX_DAUER = werte["wiederholungen"], werte["max_dauer"]
        abruf.ABSTAND = werte["abstand"]
        _sperrfrist_geprueft = True   # geprüft; _hole prüft nicht erneut (der eigene Marker folgt gleich)

    zeitzone = ZoneInfo("Europe/Berlin")
    lauf = {"lauf": _laufnummer(), "stufe": os.environ.get("RATSATLAS_STUFE", ""), "kommando": a.kommando,
            "parameter": _parameter(a), "start": dt.datetime.now(zeitzone).isoformat(timespec="seconds"),
            "obergrenze": abruf.MAX_ANFRAGEN or "", "protokoll_von": abruf.protokollzeilen(),
            "ergebnis": UNTERBROCHEN, "meldung": NICHT_REGULAER}   # schlechter Fall zuerst
    rueckgabe, abruf.unterbrochen = 0, ""
    # Marker vor der ersten Anfrage an die Stadt (ein hart beendeter Lauf ohne Vermerk sperrt so 12 Stunden)
    marker = None if lokal(SYSTEM) and lokal(BODY) else _marker_setzen(lauf)
    vorher = _signale_abfangen()
    try:
        KOMMANDOS[a.kommando](a)
        lauf["ergebnis"], lauf["meldung"] = "ok", ""
    except Abbruch as e:
        lauf["ergebnis"], lauf["meldung"], rueckgabe = f"abbruch ({e.art or 'sonstiges'})", str(e), 2
        if e.art == "proxy":   # Ablehnung in der Arbeitsumgebung, nicht durch die Stadt
            hinweis = (f"Der Proxy der Arbeitsumgebung hat die Verbindung abgelehnt; keine Anfrage hat die Stadt "
                       f"erreicht, kein Hinweis auf eine Sperre. Nicht wiederholen, sondern berichten: Der Host "
                       f"{urllib.parse.urlsplit(SYSTEM).hostname} muss im Netz der Arbeitsumgebung erlaubt sein "
                       f"(explore/STUFEN.md, Stufe 1).")
        elif e.art == "sperre":   # auch 502/504 des Proxys und abgeschnittene oder unlesbare Antworten
            hinweis = ("Mögliche Sperre: in dieser Nacht keine weitere Anfrage, alle Abrufe ruhen bis zur Klärung mit "
                       "der Stadt. Stoppen und berichten (explore/STUFEN.md).")
        elif e.art == "tls":   # vermutlich Einstellung der Arbeitsumgebung
            hinweis = ("Die Zertifikatsprüfung ist gescheitert: vermutlich eine Einstellung der Arbeitsumgebung "
                       "(CA des Proxys); ein Zertifikat der Gegenseite oder eine Sperrseite ist nicht ausgeschlossen. "
                       "Keine HTTP-Anfrage gesendet. Berichten, nicht wiederholen; in dieser Nacht keine weitere "
                       "Anfrage (12-Stunden-Regel).")
        elif e.art == "parallel":   # ein anderer Prozess hält die Sperre auf den Cache
            hinweis = ("Ein anderer Abrufprozess läuft noch; keine Anfrage gesendet. Prozesse nur nacheinander "
                       "starten; stoppen und berichten (explore/STUFEN.md).")
        else:
            hinweis = "Stoppen und berichten (explore/STUFEN.md)."
        print(f"Abbruch: {e}\n{hinweis}", file=sys.stderr)
    except KeyboardInterrupt as e:   # Strg+C, SIGTERM oder SIGHUP (_signal_beenden)
        grund = str(e) if str(e) in signal.Signals.__members__ else "SIGINT"
        lauf["meldung"] = (f"unterbrochen während einer Anfrage ({grund}): mögliche Sperre, stoppen; "
                           f"{abruf.unterbrochen}" if abruf.unterbrochen else f"unterbrochen ({grund})")
        lauf["ergebnis"], rueckgabe = UNTERBROCHEN, 128 + signal.Signals[grund].value
        print(f"Unterbrochen ({grund}){' während einer Anfrage: mögliche Sperre' if abruf.unterbrochen else ''}. In "
              "dieser Nacht keine weitere Anfrage und keine weitere Stufe (12-Stunden-Regel, RATSATLAS_NACH_ABBRUCH); "
              "stoppen und berichten (explore/STUFEN.md).", file=sys.stderr)
    except Exception as e:   # z. B. HTML statt JSON: ebenfalls stoppen und berichten
        lauf["ergebnis"], lauf["meldung"], rueckgabe = f"fehler ({type(e).__name__})", str(e)[:300], 1
        print(f"Fehler: {type(e).__name__}: {e}\nStoppen und berichten (explore/STUFEN.md).", file=sys.stderr)
    finally:
        _signale(signal.SIG_IGN)   # den Vermerk nicht unterbrechen
        ende = dt.datetime.now(zeitzone)
        lauf.update(abruf.zaehler(), ende=ende.isoformat(timespec="seconds"),
                    dauer_s=f"{(ende - dt.datetime.fromisoformat(lauf['start'])).total_seconds():.0f}",
                    protokoll_bis=abruf.protokollzeilen())
        _anhaengen("oparl_laeufe.tsv", LAEUFE_SPALTEN, [lauf])
        _anhaengen("oparl_listen.tsv", LISTEN_SPALTEN, [{**e, "lauf": lauf["lauf"]} for e in _LISTEN])
        if marker:   # erst nach dem Vermerk (sonst bliebe ein hart beendeter Lauf ohne Spur)
            _marker_entfernen(marker)
        print(f"Lauf {lauf['lauf']}: {lauf['netz']} Anfragen ans Netz, {lauf['cache']} aus dem Cache; "
              f"{lauf['ergebnis']}", file=sys.stderr)
        for s, behandlung in vorher.items():
            if behandlung is not None:   # None: nicht aus Python gesetzt, bleibt ignoriert
                signal.signal(s, behandlung)
    return rueckgabe


if __name__ == "__main__":
    sys.exit(main())
