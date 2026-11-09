"""Geodaten Wuppertal laden, beschreiben und offline auswerten (Phase 1, Exploration).

Abgeleitet aus ratsatlas-koeln @d609111 (explore/geodaten.py, dort ausgeführt am 04.11.2026). Abweichungen von Köln
für den späteren gemeinsamen Kern: Datensatzliste nach CLAUDE.md 3.2 (Wuppertal) statt Kölner Katalogkennungen; der
Katalog wird nicht über einen festen DCAT-Pfad (Köln: /node/<n>/dcatapde.json) gelesen, sondern über Verweise, die die
Katalogseite selbst nennt; Direktdateien unter daten.wuppertal.de; zusätzlich Kontakt, Zeitfenster und
RATSATLAS_MESSUNG_FREIGEGEBEN wie in explore/oparl_messung.py; eigene Größengrenze je Datei; Auswertung ohne Netz
(Kommando `ableiten`); 12-Stunden-Regel, Laufvermerk und Markerdatei gemeinsam mit explore/oparl_messung.py (siehe
unten); Stand der Dateien aus dem HTTP-Kopf (Last-Modified) und den Zeitstempeln der Zip-Einträge.

Aufruf (vollständiger Befehl mit Obergrenze in explore/STUFEN.md, Stufe G; ohne Freigabe kein Abruf, auch nicht
einzelner Dateien):
  RATSATLAS_MESSUNG_FREIGEGEBEN=ja RATSATLAS_KONTAKT=contact@nozilla.de RATSATLAS_MAX_ANFRAGEN=10 \\
      python3 explore/geodaten.py laden
  python3 explore/geodaten.py ableiten [--feld adressen.strassenname=<Feld> ...]   (ohne Netz, nur aus dem Cache)
Kontakt contact@nozilla.de (vom Auftraggeber bestätigt, CLAUDE.md 9).

Ablauf `laden` (Vorgabe):
1. Datensätze mit Katalogseite auf offenedaten-wuppertal.de (Stadtbezirke, laufende B-Plan-Verfahren): Seite lesen;
   maschinenlesbare Beschreibung nur, wenn die Seite selbst auf eine verweist (eingebettetes JSON-LD,
   <link rel="alternate"> oder Verweis mit „dcat“, .jsonld oder .rdf; höchstens eine je Datensatz). Ob das Portal
   DCAT anbietet, ist offen. Ausgelesen werden Titel, Stand, Lizenz, Format und Download-Adressen aus DCAT
   (dct:/dcat:-Begriffe) bzw. schema.org; aus der HTML-Seite nur Verweise auf Dateien und auf Lizenztexte. Was fehlt,
   steht als „offen“ in geodaten_katalog.tsv. Von den Download-Adressen wird höchstens eine Datei je Datensatz geladen
   (JSON/GeoJSON vor Zip vor Tabelle, bei mehreren solche mit „4326“ im Namen zuerst), nur von Hosts der Stadt.
2. Direktdateien unter daten.wuppertal.de (Quartiere, Straßenverzeichnis, Adressen, rechtsverbindliche B-Pläne) laut
   CLAUDE.md 3.2; Lizenz laut Auftrag; Stand gemessen nur aus dem HTTP-Kopf der Antwort (Last-Modified, ETag; über
   abruf.kopfangaben) und bei Zip-Dateien aus den Zeitstempeln der Einträge, sonst „offen“ (geodaten_katalog.tsv,
   Spalten stand_http, etag, stand_zip).
3. Statistische Bezirke (optional): Adresse im Auftrag nicht genannt → nicht abgerufen, „offen“.
   Planungs-WMS: nur Verweis, wird nicht geladen.
4. Inhalt beschreiben: Ebenen, Feldnamen, Koordinatensystem, Ausdehnung, Anzahl, Feldstruktur, Beispiel →
   geodaten_felder.tsv. Für die Adressen kein Beispiel und keine Einzelwerte, nur Feldnamen, Typen und Füllgrad.
5. Danach `ableiten` (ohne Netz) aus den geladenen Dateien.

Kommando `ableiten` (ohne Netz; liest nur explore/_cache/, ruft hole() nie auf):
- geodaten_ableitungen.tsv: Zählprüfung gegen den Auftrag (10 Stadtbezirke, 69 Quartiere; Straßenverzeichnis ca. 2.160,
  B-Pläne 691 rechtsverbindlich und 100 laufend mit Datenstand laut Auftrag), Stand je geladener Datei (HTTP-Kopf,
  Zip-Einträge) mit Vergleich gegen den Stand laut Auftrag (Straßenverzeichnis 09/2021, B-Pläne 06/2026; Monat und
  Jahr), erkannte Feldnamen je Rolle (Regel oder
  Vorgabe über --feld), Kennzahlen der Zuordnung Adresse → Quartier, Muster der Hausnummern und Zusätze (nur Muster wie
  „99a“, keine Einzeladressen), Abgleich Straßenschlüssel Verzeichnis ↔ Adressen
- geodaten_gebiete.tsv: Namen der Stadtbezirke und Quartiere mit dem gemessenen Namensfeld
- strasse_quartier.tsv: Straßenname, Straßenschlüssel, Quartier, Anzahl Adresspunkte (Point-in-Polygon der
  Adresspunkte gegen die Quartiere, shapely; eine Straße in mehreren Quartieren erhält mehrere Zeilen; ein Punkt auf
  der Grenze zweier Quartiere zählt beim alphabetisch ersten, ihre Zahl steht in den Ableitungen)
- geodaten_bplan_nummern.tsv: Muster der Plannummern (Ziffer → 9, Großbuchstabe → A, Kleinbuchstabe → a) je gemessenem
  Feld mit Häufigkeit und einem Beispiel. B-Plan-Geometrien (CC BY-ND 4.0) werden nur gelesen, nie verändert oder
  geschrieben.
Feldnamen werden nicht angenommen: Sie werden über Regeln auf den gemessenen Feldnamen erkannt und mit der Regel
ausgewiesen; ohne Treffer bleibt die Rolle „offen“ und die Ableitung entfällt. Eine Vorgabe (--feld) überschreibt die
Erkennung und wird als „Vorgabe“ ausgewiesen. Rollen: strassenschluessel, strassenname, hausnummer, zusatz (adressen,
strassenverzeichnis), name_quartier (quartiere), name_bezirk (stadtbezirke, statistische_bezirke), plannummer
(bplaene_rechtsverbindlich, bplaene_laufend); Beispiel --feld quartiere.name_quartier=<Feld>.
Rückgabewerte: 0 fertig, 1 Abbruch vor der ersten Anfrage (bzw. `ableiten` ohne Dateien im Cache), 2 Ende nach einem
Abbruch während des Laufs (Ergebnisdateien unverändert, nur der Laufvermerk kommt hinzu), 3 geladen, aber Ableitungen
fehlgeschlagen, 128 + Signalnummer nach Strg+C, SIGTERM oder SIGHUP.

Abrufpolitik (über explore/abruf.py, nicht schwächer als in Köln; vor der ersten Anfrage geprüft, Rückgabewert 1):
mindestens 2 s Abstand (RATSATLAS_ABSTAND, Vorgabe 2), keine Wiederholung nach 429/5xx (RATSATLAS_WIEDERHOLUNGEN,
Vorgabe 0), Obergrenze der Anfragen ans Netz (RATSATLAS_MAX_ANFRAGEN, Pflicht), Kontakt im User-Agent
(RATSATLAS_KONTAKT, Pflicht, ohne Platzhalter „<…>“, beim Import von abruf.py gesetzt), RATSATLAS_MESSUNG_FREIGEGEBEN=ja
(Pflicht für alle Server der Stadt, auch offenedaten-wuppertal.de und daten.wuppertal.de) und Zeitfenster 23–1 Uhr
Ortszeit (RATSATLAS_ZEITFENSTER, wie explore/oparl_messung.py). Kontakt, Freigabe und Zeitfenster werden zusätzlich
vor jeder Anfrage geprüft; lokale Testserver (http://127.0.0.1, http://localhost) sind ausgenommen.
Eine Verbindung, Sperre gegen gleichzeitige Prozesse, Cache und Protokoll (_cache/abrufe.tsv) liefert abruf.py.
Größe: jede Datei hat eine eigene Obergrenze in MB (Adressen größer, mit Hinweis vor dem Abruf), übergeben als
max_bytes an abruf.hole; eine größere Antwort wird abgebrochen (Art `groesse`; nennt Content-Length mehr, ohne den
Inhalt zu lesen), nicht gespeichert und nur bei dieser Datei vermerkt. Eine Antwort, die länger als
die Gesamtfrist von abruf.py (60 s) braucht, gilt dort als mögliche Sperre und beendet den Lauf.
Weiterleitungen (HTTP 3xx) werden nicht verfolgt. Eine Weiterleitung oder ein anderer HTTP-Fehler (z. B. 404) bricht
nur den Abruf dieses Katalogs bzw. dieser Datei ab: Er wird mit der Meldung (bei einer Weiterleitung mit Ziel) in
geodaten_katalog.tsv bzw. geodaten_felder.tsv vermerkt, das Ziel steht in _cache/abrufe.tsv (Spalte ziel); die übrigen
Datensätze laufen weiter. Nach einem Abbruch der Art sperre (mögliche Sperre, auch abgeschnittene oder unlesbare
Antwort und HTTP 502/504), server (429/5xx), proxy, obergrenze, langsam (RATSATLAS_MAX_DAUER), parallel, gesperrt,
zeitfenster oder http mit 401, 403 oder 429 endet der ganze Lauf sofort (Rückgabewert 2) ohne weitere Anfrage; die
Ergebnisdateien bleiben dann unverändert. Ob daten.wuppertal.de und offenedaten-wuppertal.de im selben Netz liegen wie
oparl.wuppertal.de, ist offen; vorsorglich gilt die Kölner Regel (dort lag offenedaten-koeln.de im Netz der OParl-API,
ergebnisse/sessionnet_befunde.tsv in ratsatlas-koeln), nach diesen Signalen ruhen alle Abrufe (explore/STUFEN.md).
Durchgesetzt wird das über das gemeinsame Laufprotokoll ergebnisse/oparl_laeufe.tsv: `laden` prüft vor der ersten
Anfrage oparl_messung.letzter_abbruch() (ein Abbruch, Fehler oder unterbrochener Lauf eines der beiden Werkzeuge vor
weniger als 12 Stunden, auch eine Markerdatei _cache/lauf_offen.json ohne Vermerk, sperrt; weiter nur mit
RATSATLAS_NACH_ABBRUCH=ja nach Rücksprache), legt dieselbe Markerdatei an und vermerkt jeden Lauf, auch einen Abbruch,
mit Kommando `geodaten` in oparl_laeufe.tsv; oparl_messung.py liest diesen Vermerk vor seiner ersten Anfrage ebenso.
Das Zeitfenster gilt streng (23–1 Uhr; ein leerer oder weiterer Wert von RATSATLAS_ZEITFENSTER gilt als außerhalb).
Die geladenen Dateien bleiben in explore/_cache/ (nicht im Repository); die Zuordnung Datensatz → Adresse steht in
_cache/geodaten_dateien.tsv, damit `ableiten` ohne Netz die Dateien wiederfindet.
"""
import argparse
import collections
import csv
import datetime as dt
import email.utils
import html
import io
import json
import math
import os
import re
import signal
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abruf  # noqa: E402
import oparl_messung  # noqa: E402  (12-Stunden-Regel, Markerdatei, Zeitfenster, Laufprotokoll)
from abruf import Abbruch, hole  # noqa: E402

ERG = Path(os.environ.get("RATSATLAS_ERGEBNISSE", Path(__file__).resolve().parent / "ergebnisse"))
# gemeinsames Laufprotokoll mit explore/oparl_messung.py (12-Stunden-Regel in beide Richtungen)
LAEUFE = "oparl_laeufe.tsv"
MB = 1024 * 1024

KATALOG_BASIS = "https://offenedaten-wuppertal.de"
DATEN_BASIS = "https://daten.wuppertal.de"

# Datensätze laut CLAUDE.md 3.2. Je Eintrag: katalog (Katalogseite) oder datei (Direktdatei) oder keins von beiden
# (dann offen); lizenz_auftrag und anzahl_auftrag stammen aus dem Auftrag und werden gegen die Messung gestellt.
DATENSAETZE = [
    {"kennung": "stadtbezirke", "titel": "Stadtbezirke",
     "katalog": f"{KATALOG_BASIS}/dataset/stadtbezirke-wuppertal",
     "lizenz_auftrag": "prüfen", "anzahl_auftrag": (10, "genau"), "max_mb": 50},
    {"kennung": "quartiere", "titel": "Quartiere",
     "datei": f"{DATEN_BASIS}/Infrastruktur_Bauen_Wohnen/Quartiere_EPSG4326_JSON.json",
     "lizenz_auftrag": "CC BY 4.0", "anzahl_auftrag": (69, "genau"), "max_mb": 50},
    {"kennung": "statistische_bezirke", "titel": "Statistische Bezirke (optional)",
     "lizenz_auftrag": "prüfen", "anzahl_auftrag": (48, "genau"),
     "hinweis": "offen: Adresse im Auftrag nicht genannt (nur „offenedaten-wuppertal.de (GeoJSON)“), nicht abgerufen"},
    {"kennung": "strassenverzeichnis", "titel": "Straßenverzeichnis",
     "datei": f"{DATEN_BASIS}/Infrastruktur_Bauen_Wohnen/Strassenverzeichnis_CSV.zip",
     "lizenz_auftrag": "CC BY 4.0", "anzahl_auftrag": (2160, "ca., Stand 09/2021"), "max_mb": 20,
     "stand_auftrag": ((2021, 9), "Stand 09/2021, wöchentlich aktualisiert")},
    {"kennung": "adressen", "titel": "Georeferenzierte Bestandsadressen",
     "datei": f"{DATEN_BASIS}/Geografie_Geologie_Geodaten/Adressen_EPSG4326_JSON.json",
     "lizenz_auftrag": "CC BY 4.0", "max_mb": 200, "gross": True},
    {"kennung": "bplaene_rechtsverbindlich", "titel": "Rechtsverbindliche Bebauungspläne",
     "datei": f"{DATEN_BASIS}/Gesetze_Justiz/rvbBebauungsplanverfahren_EPSG4326_JSON.json",
     "lizenz_auftrag": "CC BY-ND 4.0 (Open.NRW abweichend: „Andere geschlossene Lizenz“)",
     "anzahl_auftrag": (691, "Stand 06/2026"), "max_mb": 100, "stand_auftrag": ((2026, 6), "Stand 06/2026")},
    {"kennung": "bplaene_laufend", "titel": "Laufende Bebauungsplanverfahren",
     "katalog": f"{KATALOG_BASIS}/dataset/laufende-bebauungsplanverfahren-wuppertal",
     "lizenz_auftrag": "CC BY-ND 4.0", "anzahl_auftrag": (100, "laut Auftrag"), "max_mb": 50},
    {"kennung": "planungs_wms", "titel": "Planungs-WMS", "verweis": "https://maps.wuppertal.de/planung",
     "lizenz_auftrag": "nicht angegeben",
     "hinweis": "nur Verweis, nicht geladen (ohne Lizenz nicht einbinden)"},
]
# Hosts der Stadt, von denen Dateien geladen werden (CLAUDE.md 3.1/3.2)
STADT_DOMAINS = ("wuppertal.de", "offenedaten-wuppertal.de")
# beschreibbare Formate; KML, GeoPackage und andere werden aufgeführt, aber nicht geladen
LADBAR = (".json", ".geojson", ".zip", ".csv", ".xlsx")
DATEI_ENDUNGEN = LADBAR + (".kml", ".kmz", ".gpkg", ".shp", ".xml", ".gml")
MAX_DATEIEN_JE_KATALOG = 1
# Datensätze, aus denen keine Einzelwerte in Ergebnisdateien gelangen (Datenschutz: keine Einzeladressen)
OHNE_EINZELWERTE = ("adressen",)
OFFEN = "offen"

DCAT = "http://www.w3.org/ns/dcat#"
DCT = "http://purl.org/dc/terms/"
DCATDE = "http://dcat-ap.de/def/dcatde/"
SDO = "http://schema.org/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
# Standardpräfixe für JSON-LD ohne eigene Präfixdefinition
PRAEFIXE = {"dcat": DCAT, "dct": DCT, "dcterms": DCT, "dcatde": DCATDE, "schema": SDO, "rdf": RDF}
# Merkmale je Spalte: DCAT-Begriff zuerst, dann schema.org
MERKMALE = {
    "titel": (DCT + "title", SDO + "name"),
    "stand": (DCT + "modified", SDO + "dateModified"),
    "lizenz": (DCT + "license", SDO + "license"),
    "format": (DCT + "format", DCAT + "mediaType", SDO + "encodingFormat"),
    "download_url": (DCAT + "downloadURL", SDO + "contentUrl"),
    "access_url": (DCAT + "accessURL", SDO + "url"),
    "namensnennung": (DCATDE + "licenseAttributionByText",),
    "distribution": (DCAT + "distribution", SDO + "distribution"),
}
DATASET_TYPEN = (DCAT + "Dataset", SDO + "Dataset")
# Verweise auf Lizenztexte in der HTML-Seite
RE_LIZENZ_URL = re.compile(r"creativecommons\.org/(?:licenses|publicdomain)|govdata\.de/dl-de|opendatacommons\.org/"
                           r"licenses", re.I)

# Mindestwerte wie für die OParl-Messung (explore/oparl_messung.py, STRENG_ABSTAND)
STRENG_ABSTAND = 2.0
# Abbruchsarten, nach denen der ganze Lauf endet (keine weitere Anfrage an die Stadt) …
ENDE = ("sperre", "server", "proxy", "obergrenze", "langsam", "parallel", "gesperrt", "zeitfenster", "tls")
# … ebenso HTTP-Antworten der Art `http` mit diesen Codes (STUFEN.md: nach 403 oder 429 ruhen alle Abrufe)
ENDE_HTTP = (401, 403, 429)

# Regeln zur Erkennung der Feldnamen je Rolle; geprüft auf dem kleingeschriebenen Feldnamen mit ae/oe/ue/ss.
# Reihenfolge = Vorrang; die greifende Regel wird ausgewiesen.
ROLLEN = {
    "strassenschluessel": (r"^str(asse)?n?_?schl(uessel)?$", r"str.*schl", r"schl(uessel)?$"),
    "strassenname": (r"^str(asse)?n?_?name$", r"^strasse$", r"^str$", r"str.*name", r"^name$"),
    "hausnummer": (r"^(hausnummer|hausnr|hsnr|hnr)$", r"hausn", r"^h(s)?nr"),
    "zusatz": (r"zusatz",),
    "name_quartier": (r"^quartier_?name$", r"quartier.*name|name.*quartier", r"^quartier$", r"^name$", r"name"),
    "name_bezirk": (r"^(stadt)?bezirk_?name$", r"bezirk.*name|name.*bezirk", r"^(stadt)?bezirk$", r"^name$", r"name"),
    "plannummer": (r"(plan|bp).*(nr|num)", r"^(nr|nummer)$", r"nummer|_nr$"),
}
# Rollen, deren Werte überwiegend Text ohne reine Ziffernfolge sein müssen
TEXTROLLEN = ("strassenname", "name_quartier", "name_bezirk")


class _Ende(Exception):
    """Ein Abbruch aus ENDE oder ENDE_HTTP: Der ganze Lauf endet."""


# ---------------------------------------------------------------------------------------------------------------------
# Abrufpolitik

def lokal(url):
    """Lokaler Testserver (wie explore/oparl_messung.lokal)."""
    t = urllib.parse.urlsplit(url)
    return t.scheme == "http" and t.hostname in ("127.0.0.1", "localhost")


def stadt_host(url):
    """Gehört die Adresse zu einem Host der Stadt (wuppertal.de mit Unterdomänen, offenedaten-wuppertal.de)?"""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in STADT_DOMAINS)


def im_zeitfenster(jetzt=None):
    """explore/oparl_messung.im_zeitfenster für Server der Stadt: RATSATLAS_ZEITFENSTER (Vorgabe 23-1) Ortszeit
    Europe/Berlin, nur innerhalb von 23–1 Uhr; ein leerer oder weiterer Wert gilt als außerhalb (geodaten.py fragt nur
    Hosts der Stadt, keine Testadressen)."""
    return oparl_messung.im_zeitfenster(jetzt)


def _kontakt_ok(kontakt):
    kontakt = (kontakt or "").strip()
    return bool(kontakt) and "<" not in kontakt and ">" not in kontakt


def vorgaben(umgebung=None):
    """Mindestwerte für den Abruf der Geodaten; liefert (werte, fehler). Fehlende Werte werden gesetzt (Abstand 2 s,
    keine Wiederholung), lockerere abgelehnt; Obergrenze RATSATLAS_MAX_ANFRAGEN, Kontakt RATSATLAS_KONTAKT und
    RATSATLAS_MESSUNG_FREIGEGEBEN=ja sind Pflicht. Das Zeitfenster prüft main() und jede Anfrage (zeitabhängig)."""
    env = os.environ if umgebung is None else umgebung
    fehler = []
    try:
        wiederholungen = int(env.get("RATSATLAS_WIEDERHOLUNGEN") or "0")
        abstand = float(env.get("RATSATLAS_ABSTAND") or STRENG_ABSTAND)
        max_anfragen = int(env.get("RATSATLAS_MAX_ANFRAGEN") or "0")
    except ValueError as e:
        return {}, [f"unlesbarer Wert ({e})"]
    if wiederholungen != 0:
        fehler.append("RATSATLAS_WIEDERHOLUNGEN muss 0 sein (keine Wiederholung nach 429/5xx)")
    if not (math.isfinite(abstand) and abstand >= STRENG_ABSTAND):
        fehler.append(f"RATSATLAS_ABSTAND muss mindestens {STRENG_ABSTAND:g} s sein (Abstand zwischen zwei Anfragen)")
    if max_anfragen <= 0:
        fehler.append("RATSATLAS_MAX_ANFRAGEN fehlt (Obergrenze der Anfragen ans Netz für diesen Lauf, vor dem Lauf "
                      "festlegen und freigeben lassen)")
    if not _kontakt_ok(env.get("RATSATLAS_KONTAKT")):
        fehler.append("RATSATLAS_KONTAKT fehlt oder enthält noch den Platzhalter „<…>“ (Kontakt im User-Agent)")
    if env.get("RATSATLAS_MESSUNG_FREIGEGEBEN") != "ja":
        fehler.append("RATSATLAS_MESSUNG_FREIGEGEBEN=ja fehlt (Abrufe bei der Stadt Wuppertal erst nach Freigabe "
                      "der Stufe G)")
    return {"wiederholungen": wiederholungen, "abstand": abstand, "max_anfragen": max_anfragen}, fehler


def _user_agent_mit_kontakt():
    """Steht ein Kontakt ohne Platzhalter im User-Agent von abruf.py (gesetzt beim Import aus RATSATLAS_KONTAKT)?"""
    return _kontakt_ok(abruf.KONTAKT) and abruf.KONTAKT.strip() in abruf.USER_AGENT


def _hole(url, endung, max_bytes=None):
    """Freigabe, Zeitfenster und Kontakt vor jeder Anfrage an die Stadt; lokale Testserver ausgenommen. Nur Hosts der
    Stadt werden abgefragt. `max_bytes` senkt die Größengrenze von abruf.py für diese Anfrage."""
    if not lokal(url):
        if not stadt_host(url):
            raise Abbruch(f"kein Host der Stadt Wuppertal, nicht abgefragt: {url}", "adresse")
        if os.environ.get("RATSATLAS_MESSUNG_FREIGEGEBEN") != "ja":
            raise Abbruch(f"Messung bei der Stadt Wuppertal nicht freigegeben (RATSATLAS_MESSUNG_FREIGEGEBEN): {url}", "gesperrt")
        if not im_zeitfenster():
            raise Abbruch(f"außerhalb des Zeitfensters (RATSATLAS_ZEITFENSTER): {url}", "zeitfenster")
        if not _user_agent_mit_kontakt():
            raise Abbruch(f"kein Kontakt im User-Agent (RATSATLAS_KONTAKT vor dem Start setzen): {url}", "gesperrt")
    return hole(url, endung, max_bytes=max_bytes)


def _pruefe_ende(e):
    """Ein Abbruch aus ENDE oder der Art http mit einem Code aus ENDE_HTTP beendet den ganzen Lauf; alle übrigen
    betreffen nur den Katalog bzw. die Datei."""
    if isinstance(e, Abbruch) and (e.art in ENDE or (e.art == "http" and e.code in ENDE_HTTP)):
        raise _Ende(e) from e


def _endung(url):
    return Path(urllib.parse.urlsplit(url).path).suffix.lower()


def geplante_anfragen():
    """Höchstzahl der Anfragen eines Laufs ohne Cache: je Katalog Seite, Beschreibung und Dateien, je Direktdatei eine."""
    n = 0
    for ds in DATENSAETZE:
        if ds.get("katalog"):
            n += 2 + MAX_DATEIEN_JE_KATALOG
        elif ds.get("datei"):
            n += 1
    return n


# ---------------------------------------------------------------------------------------------------------------------
# Katalog

class _Seite(HTMLParser):
    """Sammelt Titel, Verweise (a, link) und eingebettetes JSON-LD einer Katalogseite."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titel, self.verweise, self.jsonld = "", [], []
        self._in_titel = self._in_jsonld = False
        self._puffer = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in ("a", "link") and a.get("href"):
            self.verweise.append((tag, a))
        elif tag == "title":
            self._in_titel = True
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_jsonld, self._puffer = True, []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_titel = False
        elif tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld.append("".join(self._puffer))

    def handle_data(self, data):
        if self._in_titel:
            self.titel += data
        elif self._in_jsonld:
            self._puffer.append(data)


def _https(url):
    """Hosts der Stadt über HTTPS (CLAUDE.md 3.1: Kennungen mit http://, Abruf über https://)."""
    t = urllib.parse.urlsplit(url)
    if t.scheme == "http" and stadt_host(url):
        return urllib.parse.urlunsplit(("https",) + tuple(t)[1:])
    return url


def _beschreibungsverweis(seite, basis):
    """Adresse einer maschinenlesbaren Beschreibung, die die Seite selbst nennt (JSON-LD vor RDF/XML), sonst ""."""
    kandidaten = []
    for tag, a in seite.verweise:
        href = urllib.parse.urljoin(basis, html.unescape(a["href"]))
        typ = a.get("type", "").lower()
        h = urllib.parse.urlsplit(href).path.lower()
        if "ld+json" in typ or h.endswith(".jsonld") or ("dcat" in h and h.endswith(".json")):
            kandidaten.append((0, href))
        elif "rdf+xml" in typ or h.endswith(".rdf") or ("dcat" in h and h.endswith(".xml")):
            kandidaten.append((1, href))
    kandidaten = [k for k in kandidaten if lokal(k[1]) or stadt_host(k[1])]
    return min(kandidaten)[1] if kandidaten else ""


def _expandiere(schluessel, kontext, vokabular):
    if schluessel.startswith("@") or "://" in schluessel:
        return schluessel.replace("https://schema.org/", SDO)
    if ":" in schluessel:
        p, rest = schluessel.split(":", 1)
        basis = kontext.get(p) or PRAEFIXE.get(p)
        return (basis + rest).replace("https://schema.org/", SDO) if basis else schluessel
    if schluessel in kontext:
        return kontext[schluessel].replace("https://schema.org/", SDO)
    return (vokabular + schluessel) if vokabular else schluessel


def _kontext(ctx):
    """Präfixe und Begriffe aus @context (nur einfache Formen); liefert (kontext, vokabular)."""
    kontext, vokabular = {}, ""
    for c in ctx if isinstance(ctx, list) else [ctx]:
        if isinstance(c, str) and "schema.org" in c:
            vokabular = SDO
        elif isinstance(c, dict):
            for k, v in c.items():
                if k == "@vocab" and isinstance(v, str):
                    vokabular = v.replace("https://schema.org/", SDO)
                elif isinstance(v, str):
                    kontext[k] = v
                elif isinstance(v, dict) and isinstance(v.get("@id"), str):
                    kontext[k] = v["@id"]
    # Begriffe mit Präfix (z. B. "title": "dct:title") auflösen
    for k, v in list(kontext.items()):
        if ":" in v and "://" not in v:
            p, rest = v.split(":", 1)
            basis = kontext.get(p) or PRAEFIXE.get(p)
            if basis:
                kontext[k] = basis + rest
    return kontext, vokabular


def jsonld_knoten(daten):
    """Alle Knoten eines JSON-LD-Dokuments (expandierte oder kompakte Form, auch @graph und eingebettete Knoten) mit
    expandierten Schlüsseln und Typen."""
    if isinstance(daten, dict):
        kontext, vokabular = _kontext(daten.get("@context"))
        wurzeln = daten.get("@graph", [daten])
    else:
        kontext, vokabular = {}, ""
        wurzeln = daten if isinstance(daten, list) else []
    knoten = []

    def wandle(obj):
        if isinstance(obj, list):
            return [wandle(x) for x in obj]
        if not isinstance(obj, dict):
            return obj
        neu = {}
        for k, v in obj.items():
            if k == "@context":
                continue
            ek = _expandiere(k, kontext, vokabular)
            if k == "@type":
                v = [_expandiere(t, kontext, vokabular) for t in (v if isinstance(v, list) else [v])]
                neu[ek] = v
            else:
                neu[ek] = wandle(v)
        if "@type" in neu or any(k != "@value" and not k.startswith("@") for k in neu):
            knoten.append(neu)
        return neu

    wandle(wurzeln)
    return knoten


def _jsonld_werte(knoten, iri):
    out = []
    for v in (knoten.get(iri) or []) if isinstance(knoten.get(iri), list) else [knoten.get(iri)]:
        if v is None:
            continue
        if isinstance(v, dict):
            v = v.get("@value") or v.get("@id") or ""
        if isinstance(v, (str, int, float)) and str(v).strip():
            out.append(str(v).strip())
    return out


def _wert(knoten, merkmal, lesen):
    for iri in MERKMALE[merkmal]:
        werte = lesen(knoten, iri)
        if werte:
            return "; ".join(werte)
    return OFFEN


def zeilen_aus_jsonld(daten, kennung, quelle_url):
    """Katalogzeilen (je Distribution eine) aus JSON-LD (DCAT oder schema.org); Felder ohne Angabe: „offen“."""
    knoten = jsonld_knoten(daten)
    nach_id = {k["@id"]: k for k in knoten if isinstance(k.get("@id"), str)}
    zeilen = []
    for k in knoten:
        if not set(k.get("@type", [])) & set(DATASET_TYPEN):
            continue
        kopf = {"datensatz": kennung, "katalog_url": quelle_url, "quelle": "json-ld",
                "titel": _wert(k, "titel", _jsonld_werte), "stand_datensatz": _wert(k, "stand", _jsonld_werte),
                "lizenz_datensatz": _wert(k, "lizenz", _jsonld_werte)}
        dists = []
        for iri in MERKMALE["distribution"]:
            v = k.get(iri)
            for d in v if isinstance(v, list) else ([v] if v is not None else []):
                if isinstance(d, dict) and set(d) - {"@id"}:
                    dists.append(d)
                elif isinstance(d, dict) and d.get("@id") in nach_id:
                    dists.append(nach_id[d["@id"]])
                elif isinstance(d, str) and d in nach_id:
                    dists.append(nach_id[d])
        for d in dists or [{}]:
            zeilen.append({**kopf, "distribution": _wert(d, "titel", _jsonld_werte),
                           "format": _wert(d, "format", _jsonld_werte),
                           "lizenz_distribution": _wert(d, "lizenz", _jsonld_werte),
                           "namensnennung": _wert(d, "namensnennung", _jsonld_werte),
                           "stand_distribution": _wert(d, "stand", _jsonld_werte),
                           "download_url": _wert(d, "download_url", _jsonld_werte),
                           "access_url": _wert(d, "access_url", _jsonld_werte)})
    return zeilen


def _iri(tag):
    return tag[1:].replace("}", "", 1) if tag.startswith("{") else tag


def zeilen_aus_rdfxml(daten, kennung, quelle_url):
    """Katalogzeilen aus RDF/XML (DCAT); Felder ohne Angabe: „offen“."""
    wurzel = ET.fromstring(daten)
    nach_about = {el.get(f"{{{RDF}}}about"): el for el in wurzel.iter() if el.get(f"{{{RDF}}}about")}

    def typen(el):
        t = {_iri(el.tag)}
        t |= {x.get(f"{{{RDF}}}resource", "") for x in el if _iri(x.tag) == RDF + "type"}
        return t

    def lesen(el, iri):
        out = []
        for x in el:
            if _iri(x.tag) != iri:
                continue
            wert = x.get(f"{{{RDF}}}resource") or (x.text or "").strip()
            if not wert and len(x):   # eingebetteter Knoten, z. B. dct:LicenseDocument
                wert = x[0].get(f"{{{RDF}}}about") or (x[0].text or "").strip()
            if wert:
                out.append(wert)
        return out

    zeilen = []
    for el in wurzel.iter():
        if not typen(el) & set(DATASET_TYPEN):
            continue
        kopf = {"datensatz": kennung, "katalog_url": quelle_url, "quelle": "rdf-xml",
                "titel": _wert(el, "titel", lesen), "stand_datensatz": _wert(el, "stand", lesen),
                "lizenz_datensatz": _wert(el, "lizenz", lesen)}
        dists = []
        for x in el:
            if _iri(x.tag) not in MERKMALE["distribution"]:
                continue
            ref = x.get(f"{{{RDF}}}resource")
            if ref and ref in nach_about:
                dists.append(nach_about[ref])
            elif len(x):
                dists.append(x[0])
        for d in dists or [ET.Element("leer")]:
            zeilen.append({**kopf, "distribution": _wert(d, "titel", lesen), "format": _wert(d, "format", lesen),
                           "lizenz_distribution": _wert(d, "lizenz", lesen),
                           "namensnennung": _wert(d, "namensnennung", lesen),
                           "stand_distribution": _wert(d, "stand", lesen),
                           "download_url": _wert(d, "download_url", lesen),
                           "access_url": _wert(d, "access_url", lesen)})
    return zeilen


def zeilen_aus_html(seite, kennung, url, ohne=()):
    """Aus der HTML-Seite nur, was sie wörtlich als Verweis enthält: Dateien und Lizenztexte (je Datei eine Zeile);
    `ohne`: Adressen, die keine Datendateien sind (die maschinenlesbare Beschreibung)."""
    lizenzen = sorted({urllib.parse.urljoin(url, html.unescape(a["href"])) for _, a in seite.verweise
                       if RE_LIZENZ_URL.search(a["href"])})
    dateien = []
    for _, a in seite.verweise:
        href = urllib.parse.urljoin(url, html.unescape(a["href"]))
        if _endung(href) in DATEI_ENDUNGEN and href not in dateien and href not in ohne:
            dateien.append(href)
    kopf = {"datensatz": kennung, "katalog_url": url, "quelle": "html", "titel": " ".join(seite.titel.split()) or OFFEN,
            "stand_datensatz": OFFEN, "lizenz_datensatz": "; ".join(lizenzen) or OFFEN}
    return [{**kopf, "distribution": OFFEN, "format": _endung(d).lstrip(".") or OFFEN, "lizenz_distribution": OFFEN,
             "namensnennung": OFFEN, "stand_distribution": OFFEN, "download_url": d, "access_url": OFFEN}
            for d in dateien] or [{**kopf, "distribution": "keine Dateiverweise auf der Seite erkannt"}]


def katalog(url, kennung):
    """Katalogseite und, falls die Seite auf eine verweist, ihre maschinenlesbare Beschreibung; liefert Zeilen."""
    text = _hole(url, ".html").decode("utf-8", "replace")
    seite = _Seite()
    seite.feed(text)
    zeilen = []
    for block in seite.jsonld:   # eingebettetes JSON-LD (keine weitere Anfrage)
        try:
            zeilen += zeilen_aus_jsonld(json.loads(block), kennung, url + " (eingebettet)")
        except ValueError:
            zeilen.append({"datensatz": kennung, "katalog_url": url, "quelle": "json-ld",
                           "titel": "eingebettetes JSON-LD unlesbar"})
    beschreibung = "" if zeilen else _beschreibungsverweis(seite, url)
    daten = None
    if beschreibung:
        endung = ".jsonld" if not beschreibung.lower().endswith((".rdf", ".xml")) else ".rdf"
        try:
            daten = _hole(_https(beschreibung), endung)
        except Abbruch as e:   # nach ENDE endet der Lauf; sonst (404, Weiterleitung) bleibt die HTML-Seite
            _pruefe_ende(e)
            zeilen.append({"datensatz": kennung, "katalog_url": beschreibung, "quelle": endung.lstrip("."),
                           "titel": f"Beschreibung nicht geladen ({e})"})
    if daten is not None:
        try:
            if endung == ".rdf":
                zeilen += zeilen_aus_rdfxml(daten, kennung, beschreibung)
            else:
                zeilen += zeilen_aus_jsonld(json.loads(daten), kennung, beschreibung)
        except (ValueError, ET.ParseError) as e:   # unlesbar: nicht im Cache lassen (ein späterer Lauf fragt erneut)
            abruf._cachepfad(_https(beschreibung), endung).unlink(missing_ok=True)
            zeilen.append({"datensatz": kennung, "katalog_url": beschreibung, "quelle": endung.lstrip("."),
                           "titel": f"Beschreibung unlesbar ({type(e).__name__})"})
    if not zeilen:
        zeilen.append({"datensatz": kennung, "katalog_url": url, "quelle": "-",
                       "titel": "keine maschinenlesbare Beschreibung auf der Seite verwiesen (DCAT offen)"})
    return zeilen + zeilen_aus_html(seite, kennung, url, ohne={beschreibung} if beschreibung else ())


def waehle_dateien(zeilen, anzahl=MAX_DATEIEN_JE_KATALOG):
    """Ladbare Dateien aus den Katalogzeilen: nur Hosts der Stadt (oder lokal), JSON/GeoJSON vor Zip vor Tabelle, bei
    gleichem Rang zuerst solche mit „4326“ in der Adresse; höchstens `anzahl`."""
    rang = {".json": 0, ".geojson": 0, ".zip": 1, ".csv": 2, ".xlsx": 2}
    gesehen, kandidaten = set(), []
    for z in zeilen:
        for spalte in ("download_url", "access_url"):
            for u in str(z.get(spalte) or "").split("; "):
                u = _https(html.unescape(u.strip()))
                if not u or u == OFFEN or u in gesehen or not (stadt_host(u) or lokal(u)):
                    continue
                gesehen.add(u)
                if _endung(u) in LADBAR:
                    kandidaten.append((rang[_endung(u)], "4326" not in u, len(kandidaten), u))
    return [k[-1] for k in sorted(kandidaten)[:anzahl]]


# ---------------------------------------------------------------------------------------------------------------------
# Dateien lesen und beschreiben

def _tabelle(daten):
    """CSV lesen: Zeichensatz (utf-8, sonst cp1252) und Trennzeichen gemessen; liefert (kopf, zeilen, zeichensatz,
    trenner)."""
    try:
        text, zeichensatz = daten.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        text, zeichensatz = daten.decode("cp1252", "replace"), "cp1252"
    try:
        trenner = csv.Sniffer().sniff(text[:8192], delimiters=";,\t|").delimiter
    except csv.Error:
        trenner = ";" if text.count(";") > text.count(",") else ","
    zeilen = list(csv.reader(io.StringIO(text), delimiter=trenner))
    kopf = [k.strip() for k in zeilen[0]] if zeilen else []
    return kopf, [dict(zip(kopf, z)) for z in zeilen[1:] if any(c.strip() for c in z)], zeichensatz, trenner


def _prj_name(text):
    m = re.search(r'(?:PROJCS|GEOGCS|PROJCRS|GEOGCRS)\["([^"]+)"', text)
    return m.group(1) if m else text[:60]


def ebenen(name, daten):
    """Ebenen einer Datei: je Ebene {ebene, format, crs, typ, objekte: [(eigenschaften, rohgeometrie)], hinweis}.
    format: geojson, esri (ArcGIS-JSON mit attributes/geometry), shp oder tabelle."""
    n = name.lower()
    out = []
    if n.endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(daten))
        namen = z.namelist()
        for shp in [x for x in namen if x.lower().endswith(".shp")]:
            import shapefile
            basis = shp[:-4]
            teile = {e: z.read(x) for x in namen for e in (".shp", ".dbf", ".shx", ".prj", ".cpg")
                     if x.lower() == (basis + e).lower()}
            r = shapefile.Reader(shp=io.BytesIO(teile[".shp"]), dbf=io.BytesIO(teile[".dbf"]),
                                 shx=io.BytesIO(teile[".shx"]) if ".shx" in teile else None,
                                 encoding=(teile.get(".cpg", b"utf-8").decode().strip() or "utf-8"))
            felder = [f[0] for f in r.fields[1:]]
            objekte = [(dict(zip(felder, list(rec))), s) for s, rec in zip(r.shapes(), r.records())]
            out.append({"ebene": f"{name}:{shp}", "format": "shp", "typ": r.shapeTypeName, "felder": felder,
                        "crs": _prj_name(teile.get(".prj", b"").decode("latin-1")) or "nicht angegeben (ohne .prj)",
                        "objekte": objekte, "hinweis": ""})
        for x in namen:
            if x.lower().endswith((".csv", ".json", ".geojson", ".xlsx")):
                for e in ebenen(x, z.read(x)):
                    e["ebene"] = f"{name}:{e['ebene']}"
                    out.append(e)
        if not out:
            out.append({"ebene": name, "format": "zip", "typ": "", "felder": namen[:20], "crs": "", "objekte": [],
                        "hinweis": "keine beschreibbare Datei im Archiv"})
    elif n.endswith(".csv"):
        kopf, zeilen, zeichensatz, trenner = _tabelle(daten)
        out.append({"ebene": name, "format": "tabelle", "typ": "Tabelle", "felder": kopf, "crs": "",
                    "objekte": [(z, None) for z in zeilen], "hinweis": f"Zeichensatz {zeichensatz}, Trenner {trenner!r}"})
    elif n.endswith(".xlsx"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(daten), read_only=True)
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            kopf = [str(c) for c in next(it, ()) if c is not None]
            objekte = [(dict(zip(kopf, z)), None) for z in it if any(c is not None for c in z)]
            out.append({"ebene": f"{name}:{ws.title}", "format": "tabelle", "typ": "Tabelle", "felder": kopf,
                        "crs": "", "objekte": objekte, "hinweis": ""})
    elif n.endswith((".json", ".geojson")):
        d = json.loads(daten)
        if isinstance(d, dict) and isinstance(d.get("features"), list):
            feats = d["features"]
            esri = bool(feats) and isinstance(feats[0], dict) and "attributes" in feats[0]
            if esri:
                sr = d.get("spatialReference") or {}
                crs = (f"spatialReference wkid {sr.get('latestWkid') or sr.get('wkid')}" if sr
                       else "nicht angegeben (ArcGIS-JSON ohne spatialReference)")
                objekte = [(f.get("attributes") or {}, f.get("geometry")) for f in feats]
                typ = d.get("geometryType") or ""
            else:
                c = d.get("crs")
                crs = (str(((c or {}).get("properties") or {}).get("name") or json.dumps(c)[:80]) if c
                       else "nicht angegeben (GeoJSON ohne crs; RFC 7946 setzt WGS84 voraus)")
                objekte = [(f.get("properties") or {}, f.get("geometry")) for f in feats if isinstance(f, dict)]
                typen = collections.Counter((g or {}).get("type", "ohne") for _, g in objekte)
                typ = ", ".join(f"{t} {k}" for t, k in typen.most_common())
            felder = list(dict.fromkeys(k for p, _ in objekte for k in p))
            out.append({"ebene": name, "format": "esri" if esri else "geojson", "typ": typ, "felder": felder,
                        "crs": crs, "objekte": objekte, "hinweis": ""})
        else:
            out.append({"ebene": name, "format": "json", "typ": type(d).__name__, "crs": "", "objekte": [],
                        "felder": list(d)[:30] if isinstance(d, dict) else [], "hinweis": "keine features"})
    else:
        out.append({"ebene": name, "format": "", "typ": "", "felder": [], "crs": "", "objekte": [],
                    "hinweis": "Format nicht beschrieben"})
    return out


def _ring_flaeche(ring):
    return sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(ring, ring[1:] + ring[:1])) / 2


def geometrie(roh, fmt):
    """shapely-Geometrie aus GeoJSON, ArcGIS-JSON oder pyshp (nur im Speicher, für Ausdehnung und Point-in-Polygon);
    ohne Geometrie None."""
    from shapely.geometry import LineString, MultiLineString, MultiPoint, Point, Polygon, shape
    from shapely.ops import unary_union
    if not roh:
        return None
    if fmt == "shp":
        gi = roh.__geo_interface__
        return shape(gi) if gi and gi.get("type") not in (None, "Null") else None
    if fmt == "geojson":
        return shape(roh)
    if fmt == "esri":
        if "x" in roh and "y" in roh:
            return Point(roh["x"], roh["y"]) if roh["x"] is not None else None
        if roh.get("points"):
            return MultiPoint(roh["points"])
        if roh.get("paths"):
            return MultiLineString([LineString(p) for p in roh["paths"]])
        if roh.get("rings"):   # ArcGIS: äußere Ringe im Uhrzeigersinn (Fläche < 0), Löcher gegen den Uhrzeigersinn
            aussen = [r for r in roh["rings"] if _ring_flaeche(r) <= 0]
            loecher = [r for r in roh["rings"] if _ring_flaeche(r) > 0]
            polys = []
            for a in aussen:
                pa = Polygon(a)
                innen = [lo for lo in loecher if pa.contains(Point(lo[0][:2]))]
                polys.append(Polygon(a, innen))
            return unary_union(polys) if len(polys) > 1 else (polys[0] if polys else None)
    return None


def _geometrie_oder_none(roh, fmt):
    try:
        return geometrie(roh, fmt)
    except Exception:   # unlesbare Einzelgeometrie: zählt als „ohne Geometrie“
        return None


def _geometrien(ebene):
    if "_geom" not in ebene:
        ebene["_geom"] = [_geometrie_oder_none(g, ebene["format"]) for _, g in ebene["objekte"]]
    return ebene["_geom"]


def ausdehnung(geoms):
    """(minx, miny, maxx, maxy) über alle Geometrien oder None."""
    b = [g.bounds for g in geoms if g is not None and not g.is_empty]
    if not b:
        return None
    return (min(x[0] for x in b), min(x[1] for x in b), max(x[2] for x in b), max(x[3] for x in b))


def im_gradbereich(bbox):
    return bbox is not None and -180 <= bbox[0] <= bbox[2] <= 180 and -90 <= bbox[1] <= bbox[3] <= 90


def struktur(objekte, felder):
    """Je Feld: Typen und Füllgrad (ohne Werte)."""
    n = len(objekte) or 1
    teile = []
    for f in felder:
        typen = collections.Counter(type(p.get(f)).__name__ for p, _ in objekte
                                    if p.get(f) not in (None, ""))
        gefuellt = sum(typen.values())
        teile.append(f"{f}: {'/'.join(t for t, _ in typen.most_common()) or '-'} {100 * gefuellt / n:.0f}%")
    return " | ".join(teile)


def beschreibe(kennung, url, daten):
    """Zeilen für geodaten_felder.tsv; für Datensätze aus OHNE_EINZELWERTE ohne Beispiel."""
    out = []
    for e in ebenen(url.rsplit("/", 1)[-1], daten):
        geoms = _geometrien(e) if e["format"] in ("geojson", "esri", "shp") else []
        bbox = ausdehnung(geoms)
        fehlend = sum(1 for g in geoms if g is None)
        if kennung in OHNE_EINZELWERTE:
            beispiel = "ausgelassen (keine Einzeladressen in Ergebnisdateien)"
        else:
            beispiel = json.dumps(e["objekte"][0][0], ensure_ascii=False, default=str)[:300] if e["objekte"] else ""
        out.append({"datensatz": kennung, "url": url, "bytes": len(daten), "ebene": e["ebene"], "crs": e["crs"],
                    "ausdehnung": ", ".join(f"{v:.4f}" for v in bbox) if bbox else "",
                    "gradbereich": ("ja" if im_gradbereich(bbox) else "nein") if bbox else "",
                    "anzahl": len(e["objekte"]), "ohne_geometrie": fehlend if geoms else "", "typ": e["typ"],
                    "felder": " | ".join(map(str, e["felder"])), "struktur": struktur(e["objekte"], e["felder"])[:600],
                    "beispiel": beispiel, "hinweis": e["hinweis"]})
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Ableitungen ohne Netz

def _norm_feld(name):
    n = str(name).lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        n = n.replace(a, b)
    return n


def _text_anteil(objekte, feld):
    werte = [p.get(feld) for p, _ in objekte if p.get(feld) not in (None, "")]
    if not werte:
        return 0.0
    return sum(1 for w in werte if isinstance(w, str) and not w.strip().isdigit()) / len(werte)


def erkenne_feld(felder, objekte, rolle, vorgabe=None):
    """Feldname für eine Rolle; liefert (feld oder None, Herkunft). Herkunft: „Vorgabe“, „Regel <muster>“ (bei mehreren
    Treffern mit „mehrdeutig: …“) oder „offen“."""
    if vorgabe:
        if vorgabe in felder:
            return vorgabe, "Vorgabe"
        return None, f"offen (Vorgabe {vorgabe} nicht unter den Feldern)"
    for muster in ROLLEN[rolle]:
        treffer = [f for f in felder if re.search(muster, _norm_feld(f))]
        if rolle in TEXTROLLEN:
            treffer = [f for f in treffer if _text_anteil(objekte, f) >= 0.9]
        if treffer:
            hinweis = f"Regel {muster}" + (f"; mehrdeutig: {', '.join(treffer)}" if len(treffer) > 1 else "")
            return treffer[0], hinweis
    return None, OFFEN


def muster(wert):
    """Form eines Werts: Ziffer → 9, Großbuchstabe → A, Kleinbuchstabe → a, übrige Zeichen bleiben."""
    return re.sub(r"[a-zäöüß]", "a", re.sub(r"[A-ZÄÖÜ]", "A", re.sub(r"\d", "9", str(wert).strip())))


def _schluessel(wert):
    """Straßenschlüssel zum Abgleich: Ziffernfolgen ohne führende Nullen, sonst getrimmter Text."""
    s = str(wert).strip()
    if isinstance(wert, float) and wert.is_integer():
        s = str(int(wert))
    return str(int(s)) if s.isdigit() else s


def _erste_geo_ebene(e_liste):
    for e in e_liste:
        if e["format"] in ("geojson", "esri", "shp") and e["objekte"]:
            return e
    return e_liste[0] if e_liste else None


def ableiten(dateien, erg=None, feldvorgabe=None):
    """Auswertung ohne Netz. dateien: {kennung: (url, bytes)}; feldvorgabe: {"adressen.strassenname": "FELD", …}.
    Schreibt geodaten_ableitungen.tsv, geodaten_gebiete.tsv, strasse_quartier.tsv, geodaten_bplan_nummern.tsv;
    liefert die Zeilen der Ableitungen."""
    erg = ERG if erg is None else Path(erg)
    feldvorgabe = feldvorgabe or {}
    pruef, gebiete, sq_zeilen, bplan = [], [], [], []

    def zeile(pruefung, datensatz, wert="", auftrag="", ergebnis="", anmerkung=""):
        pruef.append({"pruefung": pruefung, "datensatz": datensatz, "wert": wert, "auftrag": auftrag,
                      "ergebnis": ergebnis, "anmerkung": anmerkung})

    geladen = {}
    for kennung, (url, daten) in dateien.items():
        try:
            geladen[kennung] = _erste_geo_ebene(ebenen(url.rsplit("/", 1)[-1], daten))
        except Exception as e:   # eine unlesbare Datei soll die übrigen Ableitungen nicht verhindern
            zeile("lesen", kennung, ergebnis="fehler", anmerkung=f"{type(e).__name__}: {e}"[:200])

    def feld(kennung, rolle):
        e = geladen[kennung]
        f, herkunft = erkenne_feld(e["felder"], e["objekte"], rolle, feldvorgabe.get(f"{kennung}.{rolle}"))
        zeile(f"feld {rolle}", kennung, f or "", ergebnis="erkannt" if f else OFFEN, anmerkung=herkunft)
        return f

    # Zählprüfung gegen den Auftrag
    for ds in DATENSAETZE:
        k = ds["kennung"]
        if "anzahl_auftrag" not in ds:
            continue
        soll, art = ds["anzahl_auftrag"]
        if k not in geladen or geladen[k] is None:
            zeile("anzahl", k, "", f"{soll} ({art})", OFFEN, "nicht geladen")
            continue
        n = len(geladen[k]["objekte"])
        if art == "genau":
            ergebnis = "gleich" if n == soll else "abweichend"
        else:
            ergebnis = f"Vergleich ({art}): {'gleich' if n == soll else f'Differenz {n - soll:+d}'}"
        zeile("anzahl", k, n, f"{soll} ({art})", ergebnis, geladen[k]["ebene"])

    # Stand je geladener Datei, Vergleich mit dem Stand laut Auftrag (Monat und Jahr)
    for ds in DATENSAETZE:
        k = ds["kennung"]
        if k not in dateien:
            continue
        stand = stand_der_datei(*dateien[k])
        monat, quelle = _monat(stand)
        soll, text = ds.get("stand_auftrag", (None, ""))
        if monat is None:
            ergebnis = OFFEN
        elif soll is None:
            ergebnis = f"gemessen ({quelle}), kein Stand im Auftrag"
        else:
            ergebnis = f"{'gleicher Monat' if monat == soll else 'abweichend'} ({quelle})"
        zeile("stand", k, f"{monat[1]:02d}/{monat[0]}" if monat else OFFEN, text, ergebnis,
              f"Last-Modified {stand['stand_http']}; ETag {stand['etag']}"
              + (f"; Zip {stand['stand_zip']}" if stand["stand_zip"] else ""))

    # Namen der Gebiete
    for k in ("stadtbezirke", "quartiere", "statistische_bezirke"):
        if geladen.get(k) is None:
            continue
        f = feld(k, "name_quartier" if k == "quartiere" else "name_bezirk")
        if not f:
            continue
        namen = collections.Counter(str(p.get(f)).strip() for p, _ in geladen[k]["objekte"])
        doppelt = {n: c for n, c in namen.items() if c > 1}
        zeile("verschiedene namen", k, len(namen), ergebnis="eindeutig" if not doppelt else "doppelt",
              anmerkung="; ".join(f"{n} ×{c}" for n, c in doppelt.items()))
        gebiete += [{"datensatz": k, "namensfeld": f, "name": n, "objekte": c} for n, c in sorted(namen.items())]

    # B-Plan-Nummern: Muster je erkanntem Feld (Geometrien werden nicht angefasst)
    for k in ("bplaene_rechtsverbindlich", "bplaene_laufend"):
        if geladen.get(k) is None:
            continue
        e = geladen[k]
        felder = []
        vorgabe = feldvorgabe.get(f"{k}.plannummer")
        if vorgabe:
            felder = [vorgabe] if vorgabe in e["felder"] else []
            zeile("feld plannummer", k, vorgabe if felder else "", ergebnis="erkannt" if felder else OFFEN,
                  anmerkung="Vorgabe" if felder else "Vorgabe nicht unter den Feldern")
        else:   # alle Felder, auf die eine Regel passt (Feldname gemessen, nicht angenommen)
            for m in ROLLEN["plannummer"]:
                felder += [f for f in e["felder"] if re.search(m, _norm_feld(f)) and f not in felder]
            zeile("feld plannummer", k, ", ".join(felder), ergebnis="erkannt" if felder else OFFEN,
                  anmerkung="alle Felder, auf die eine Regel passt" if felder else OFFEN)
        for f in felder:
            werte = [p.get(f) for p, _ in e["objekte"] if p.get(f) not in (None, "")]
            zaehler, beispiele = collections.Counter(), {}
            for w in werte:
                m = muster(w)
                zaehler[m] += 1
                beispiele.setdefault(m, str(w).strip())
            zeile("plannummern", k, len(werte), ergebnis=f"{len(set(map(str, werte)))} verschieden",
                  anmerkung=f"Feld {f}; ohne Wert: {len(e['objekte']) - len(werte)}")
            bplan += [{"datensatz": k, "feld": f, "muster": m, "anzahl": c, "beispiel": beispiele[m]}
                      for m, c in zaehler.most_common()]

    # Straßenverzeichnis: Schlüssel
    verz_schluessel = None
    if geladen.get("strassenverzeichnis") is not None:
        f = feld("strassenverzeichnis", "strassenschluessel")
        if f:
            verz_schluessel = {_schluessel(p.get(f)) for p, _ in geladen["strassenverzeichnis"]["objekte"]
                               if p.get(f) not in (None, "")}
            zeile("verschiedene strassenschluessel", "strassenverzeichnis", len(verz_schluessel),
                  "ca. 2.160 Straßen (Stand 09/2021)")

    # Adressen → Quartier (Point-in-Polygon); keine Einzeladressen in den Ergebnissen
    if geladen.get("adressen") is not None:
        a = geladen["adressen"]
        f_schl, f_name = feld("adressen", "strassenschluessel"), feld("adressen", "strassenname")
        f_hnr, f_zus = feld("adressen", "hausnummer"), feld("adressen", "zusatz")
        zeile("adresspunkte", "adressen", len(a["objekte"]))
        for f_, rolle in ((f_hnr, "hausnummer"), (f_zus, "zusatz")):
            if f_:
                formen = collections.Counter(muster(p.get(f_)) for p, _ in a["objekte"] if p.get(f_) not in (None, ""))
                leer = sum(1 for p, _ in a["objekte"] if p.get(f_) in (None, ""))
                zeile(f"{rolle} muster", "adressen", len(formen), anmerkung="; ".join(
                    f"{m} ×{c}" for m, c in formen.most_common(15)) + f"; ohne Wert ×{leer}")
        if f_schl and verz_schluessel is not None:
            adr_schl = {_schluessel(p.get(f_schl)) for p, _ in a["objekte"] if p.get(f_schl) not in (None, "")}
            zeile("schluessel verzeichnis ohne adresspunkt", "strassenverzeichnis", len(verz_schluessel - adr_schl))
            zeile("schluessel adressen nicht im verzeichnis", "adressen", len(adr_schl - verz_schluessel))
        sq_zeilen = _strasse_quartier(a, geladen.get("quartiere"), f_schl, f_name, feldvorgabe, zeile)

    erg.mkdir(parents=True, exist_ok=True)
    _schreibe(erg / "geodaten_ableitungen.tsv", pruef,
              ("pruefung", "datensatz", "wert", "auftrag", "ergebnis", "anmerkung"))
    _schreibe(erg / "geodaten_gebiete.tsv", gebiete, ("datensatz", "namensfeld", "name", "objekte"))
    _schreibe(erg / "strasse_quartier.tsv", sq_zeilen,
              ("strassenname", "strassenschluessel", "quartier", "adresspunkte"))
    _schreibe(erg / "geodaten_bplan_nummern.tsv", bplan, ("datensatz", "feld", "muster", "anzahl", "beispiel"))
    return pruef


def _strasse_quartier(adressen, quartiere, f_schl, f_name, feldvorgabe, zeile):
    """Zeilen der Straße-zu-Quartier-Tabelle; Kennzahlen über `zeile`."""
    import shapely
    from shapely.strtree import STRtree
    if quartiere is None:
        zeile("strasse_quartier", "adressen", ergebnis=OFFEN, anmerkung="Quartiere nicht geladen")
        return []
    if not f_name and not f_schl:
        zeile("strasse_quartier", "adressen", ergebnis=OFFEN, anmerkung="weder Straßenname noch -schlüssel erkannt")
        return []
    f_q, herkunft = erkenne_feld(quartiere["felder"], quartiere["objekte"], "name_quartier",
                                 feldvorgabe.get("quartiere.name_quartier"))
    if not f_q:
        zeile("strasse_quartier", "adressen", ergebnis=OFFEN, anmerkung=f"Namensfeld der Quartiere {herkunft}")
        return []
    q_geoms = _geometrien(quartiere)
    a_geoms = _geometrien(adressen)
    q_bbox, a_bbox = ausdehnung(q_geoms), ausdehnung(a_geoms)
    if (q_bbox is None or a_bbox is None or im_gradbereich(q_bbox) != im_gradbereich(a_bbox)
            or a_bbox[0] > q_bbox[2] or a_bbox[2] < q_bbox[0] or a_bbox[1] > q_bbox[3] or a_bbox[3] < q_bbox[1]):
        zeile("strasse_quartier", "adressen", ergebnis=OFFEN,
              anmerkung=f"Ausdehnungen passen nicht zusammen (Koordinatensystem oder Achsenfolge prüfen): Adressen "
                        f"{a_bbox}, Quartiere {q_bbox}")
        return []
    ungueltig = sum(1 for g in q_geoms if g is not None and not g.is_valid)
    # nur im Speicher und nur für die Prüfung; die Quelldatei bleibt unverändert
    polys = [shapely.make_valid(g) if g is not None and not g.is_valid else g for g in q_geoms]
    namen = [str(p.get(f_q)).strip() for p, _ in quartiere["objekte"]]
    gueltig_idx = [i for i, g in enumerate(polys) if g is not None]
    baum = STRtree([polys[i] for i in gueltig_idx])
    punkt_idx = [i for i, g in enumerate(a_geoms) if g is not None and g.geom_type == "Point"]
    ohne_punkt = len(a_geoms) - len(punkt_idx)
    treffer = collections.defaultdict(list)
    if punkt_idx:
        eingang, baum_idx = baum.query([a_geoms[i] for i in punkt_idx], predicate="intersects")
        for e_i, b_i in zip(eingang.tolist(), baum_idx.tolist()):
            treffer[punkt_idx[e_i]].append(namen[gueltig_idx[b_i]])
    zaehler = collections.Counter()
    namen_je_strasse = collections.defaultdict(collections.Counter)
    grenze = ohne = ohne_strasse = 0
    for i in punkt_idx:
        qs = sorted(set(treffer.get(i, [])))
        if not qs:
            ohne += 1
            continue
        p = adressen["objekte"][i][0]
        name = str(p.get(f_name) or "").strip() if f_name else ""
        schl = _schluessel(p.get(f_schl)) if f_schl and p.get(f_schl) not in (None, "") else ""
        if not schl and not name:
            ohne_strasse += 1
            continue
        grenze += len(qs) > 1
        strasse = (schl, "") if schl else ("", name)   # Schlüssel vor Name
        zaehler[(strasse, qs[0])] += 1
        namen_je_strasse[strasse][name] += 1
    zeile("adresspunkte im quartier", "adressen", sum(zaehler.values()), anmerkung=f"Namensfeld Quartiere {f_q} "
          f"({herkunft}); ungültige Quartiersgeometrien (nur im Speicher repariert): {ungueltig}")
    zeile("adresspunkte ohne quartier", "adressen", ohne)
    zeile("adresspunkte auf quartiersgrenze", "adressen", grenze, anmerkung="dem alphabetisch ersten Quartier zugeordnet")
    zeile("adressen ohne punktgeometrie", "adressen", ohne_punkt)
    zeile("adresspunkte ohne strassenangabe", "adressen", ohne_strasse)
    mehrnamig = sum(1 for c in namen_je_strasse.values() if len(c) > 1)
    if f_schl:
        zeile("strassenschluessel mit mehreren namen", "adressen", mehrnamig, anmerkung="häufigster Name verwendet")
    je_strasse = collections.Counter(s for s, _ in zaehler)
    zeile("strassen", "adressen", len(je_strasse), anmerkung=f"Schlüssel {f_schl or OFFEN}, Name {f_name or OFFEN}")
    zeile("strassen in mehreren quartieren", "adressen", sum(1 for c in je_strasse.values() if c > 1))
    zeilen = []
    for (s, q), c in zaehler.items():
        name = namen_je_strasse[s].most_common(1)[0][0]
        zeilen.append({"strassenname": name, "strassenschluessel": s[0] if f_schl else OFFEN, "quartier": q,
                       "adresspunkte": c})
    return sorted(zeilen, key=lambda z: (z["strassenname"], z["strassenschluessel"], z["quartier"]))


# ---------------------------------------------------------------------------------------------------------------------
# Lauf

def _schreibe(pfad, rows, spalten=None):
    spalten = list(spalten or dict.fromkeys(k for r in rows for k in r))
    with pfad.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, spalten, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: str(v).replace("\t", " ").replace("\n", " ") for k, v in r.items()})


ZUORDNUNG = "geodaten_dateien.tsv"   # im Cache: Datensatz → Adresse der geladenen Datei


def stand_der_datei(url, daten):
    """Stand einer geladenen Datei ohne Anfrage: Last-Modified und ETag der Antwort (Begleitdatei im Cache,
    abruf.kopfangaben), bei Zip die Zeitstempel der Einträge (frühester bis spätester, ZipInfo.date_time); fehlt eine
    Angabe, „offen“."""
    kopf = abruf.kopfangaben(url, _endung(url) or ".bin")
    stand = {"stand_http": kopf.get("Last-Modified") or OFFEN, "etag": kopf.get("ETag") or OFFEN, "stand_zip": ""}
    if _endung(url) == ".zip":
        try:
            zeiten = sorted(dt.datetime(*i.date_time).date() for i in zipfile.ZipFile(io.BytesIO(daten)).infolist()
                            if not i.is_dir())
            stand["stand_zip"] = (f"{zeiten[0].isoformat()} bis {zeiten[-1].isoformat()} ({len(zeiten)} Einträge)"
                                  if zeiten else OFFEN)
        except (zipfile.BadZipFile, ValueError) as e:
            stand["stand_zip"] = f"{OFFEN} ({type(e).__name__})"
    return stand


def _monat(stand):
    """(Jahr, Monat) aus stand_http (HTTP-Datum) oder dem spätesten Zip-Eintrag, sonst None; liefert (Wert, Quelle)."""
    if stand.get("stand_http") not in (None, "", OFFEN):
        try:
            t = email.utils.parsedate_to_datetime(stand["stand_http"])
            return (t.year, t.month), "Last-Modified"
        except (TypeError, ValueError):
            pass
    m = re.search(r"bis (\d{4})-(\d{2})-\d{2}", stand.get("stand_zip") or "")
    return ((int(m.group(1)), int(m.group(2))), "Zip-Einträge") if m else (None, "")


def _lade_datei(ds, url):
    """Eine Datei mit eigener Größengrenze (max_bytes für diese Anfrage; abruf.py nimmt das Kleinere aus dieser Grenze
    und abruf.MAX_BYTES und liest den Inhalt nicht, wenn Content-Length mehr nennt) und Hinweis vorab."""
    grenze = ds.get("max_mb", 50)
    print(f"{ds['titel']}: {url} (Obergrenze {grenze} MB"
          + ("; große Datei, die Antwort muss innerhalb der Gesamtfrist von abruf.py vollständig sein" if ds.get("gross")
             else "") + ")")
    daten = _hole(url, _endung(url) or ".bin", max_bytes=int(grenze * MB))
    print(f"  {len(daten) / MB:.1f} MB")
    return daten


def _laden():
    """Kataloge und Dateien; liefert (Katalogzeilen, Feldzeilen, {kennung: (url, bytes)}). Ein Abbruch aus ENDE kommt
    als _Ende."""
    kat, felder, dateien = [], [], {}
    for ds in DATENSAETZE:
        k = ds["kennung"]
        basis = {"datensatz": k, "lizenz_auftrag": ds.get("lizenz_auftrag", "")}
        urls = []
        if ds.get("katalog"):
            try:
                zeilen = katalog(ds["katalog"], k)
            except Abbruch as e:
                _pruefe_ende(e)
                print(f"Katalog {k}: {e}")
                kat.append({**basis, "katalog_url": ds["katalog"], "titel": f"nicht gefunden ({e})"})
                continue
            kat += [{**basis, **z} for z in zeilen]
            urls = waehle_dateien(zeilen)
            if not urls:
                felder.append({"datensatz": k, "url": ds["katalog"],
                               "ebene": "offen: keine ladbare Datei eines Hosts der Stadt im Katalogeintrag erkannt"})
        elif ds.get("datei"):
            kat.append({**basis, "katalog_url": OFFEN, "quelle": "Auftrag (CLAUDE.md 3.2), Direktdatei",
                        "titel": ds["titel"], "stand_datensatz": OFFEN, "lizenz_datensatz": OFFEN,
                        "download_url": ds["datei"]})
            urls = [ds["datei"]]
        else:
            kat.append({**basis, "katalog_url": ds.get("verweis", OFFEN), "quelle": "Auftrag (CLAUDE.md 3.2)",
                        "titel": f"{ds['titel']}: {ds.get('hinweis', OFFEN)}"})
        for url in urls:
            try:
                daten = _lade_datei(ds, url)
                dateien[k] = (url, daten)
                zeile_k = next((z for z in kat if z["datensatz"] == k), None)
                if zeile_k is not None:   # Stand der geladenen Datei (HTTP-Kopf, Zip-Einträge), sonst „offen“
                    zeile_k.update({"datei_geladen": url, **stand_der_datei(url, daten)})
                felder += beschreibe(k, url, daten)
            except Exception as e:   # Beschreibung soll für die übrigen Dateien weiterlaufen (außer nach ENDE)
                _pruefe_ende(e)
                felder.append({"datensatz": k, "url": url, "ebene": f"Fehler: {type(e).__name__}: {e}"[:200]})
    return kat, felder, dateien


def _zuordnung_schreiben(dateien):
    abruf.CACHE.mkdir(parents=True, exist_ok=True)
    _schreibe(abruf.CACHE / ZUORDNUNG, [{"datensatz": k, "url": u, "bytes": len(d)} for k, (u, d) in dateien.items()],
              ("datensatz", "url", "bytes"))


def dateien_aus_cache():
    """{kennung: (url, bytes)} nur aus explore/_cache/ (keine Anfrage): Zuordnung aus geodaten_dateien.tsv, für
    Direktdateien auch ohne Zuordnung über die Adresse laut DATENSAETZE."""
    urls = {ds["kennung"]: ds["datei"] for ds in DATENSAETZE if ds.get("datei")}
    pfad = abruf.CACHE / ZUORDNUNG
    if pfad.exists():
        with pfad.open(encoding="utf-8") as f:
            for z in csv.DictReader(f, delimiter="\t"):
                urls[z["datensatz"]] = z["url"]
    out = {}
    for k, url in urls.items():
        c = abruf._cachepfad(url, _endung(url) or ".bin")
        if c.exists():
            out[k] = (url, c.read_bytes())
    return out


def _feldvorgaben(liste):
    out = {}
    for eintrag in liste:
        schluessel, _, feld = eintrag.partition("=")
        if not feld or "." not in schluessel:
            raise SystemExit(f"--feld erwartet <datensatz>.<rolle>=<Feld>, nicht {eintrag!r}")
        out[schluessel] = feld
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Geodaten Wuppertal laden und beschreiben (Phase 1)")
    p.add_argument("kommando", nargs="?", default="laden", choices=("laden", "ableiten"))
    p.add_argument("--feld", action="append", default=[], help="Vorgabe <datensatz>.<rolle>=<Feld> für `ableiten`")
    a = p.parse_args([] if argv is None else list(argv))
    vorgabe = _feldvorgaben(a.feld)
    if a.kommando == "ableiten":
        dateien = dateien_aus_cache()
        if not dateien:
            print("Keine Geodaten im Cache (explore/_cache/); zuerst `laden` nach Freigabe.", file=sys.stderr)
            return 1
        ableiten(dateien, ERG, vorgabe)
        print(f"Ableitungen aus {len(dateien)} Dateien → {ERG}")
        return 0
    werte, fehler = vorgaben()
    if not fehler and not im_zeitfenster():
        fehler.append(f"außerhalb des Zeitfensters {os.environ.get('RATSATLAS_ZEITFENSTER', '23-1')} Uhr "
                      "(RATSATLAS_ZEITFENSTER)")
    if not fehler and not _user_agent_mit_kontakt():
        fehler.append("RATSATLAS_KONTAKT steht nicht im User-Agent von abruf.py (vor dem Start setzen)")
    if fehler:
        print("Abbruch vor der ersten Anfrage: " + "; ".join(fehler), file=sys.stderr)
        return 1
    vorher = oparl_messung.letzter_abbruch(ERG / LAEUFE, marker=oparl_messung._markerpfad())
    if vorher and os.environ.get("RATSATLAS_NACH_ABBRUCH") != "ja":
        grund = (f"Lauf {vorher.get('lauf')} ({vorher.get('kommando')}) vom {vorher.get('start') or '?'} wurde "
                 f"„{oparl_messung.NICHT_REGULAER}“ oder läuft noch (Markerdatei {vorher['marker']} ohne Vermerk)"
                 if vorher.get("marker") else
                 f"Lauf {vorher.get('lauf')} ({vorher.get('kommando')}) endete {vorher.get('ende') or '(ohne Ende)'} "
                 f"mit „{vorher.get('ergebnis')}“")
        print(f"Abbruch vor der ersten Anfrage: {grund}, vor weniger als "
              f"{oparl_messung.SPERRFRIST.total_seconds() / 3600:g} Stunden (gemeinsames Laufprotokoll {ERG / LAEUFE}). "
              "Nach einem Abbruch gilt: in dieser Nacht keine weitere Anfrage an Server der Stadt, Bericht an den "
              "Auftraggeber. Weiter nur nach Rücksprache mit RATSATLAS_NACH_ABBRUCH=ja.", file=sys.stderr)
        return 1
    abruf.ABSTAND, abruf.WIEDERHOLUNGEN = werte["abstand"], werte["wiederholungen"]
    abruf.MAX_ANFRAGEN = werte["max_anfragen"]
    geplant = geplante_anfragen()
    print(f"Höchstens {geplant} Anfragen ohne Cache; Obergrenze RATSATLAS_MAX_ANFRAGEN={abruf.MAX_ANFRAGEN}"
          + (" (kleiner: der Lauf endet an der Obergrenze)" if abruf.MAX_ANFRAGEN < geplant else ""))
    return _lauf(vorgabe)


def _laufnummer():
    datei = ERG / LAEUFE
    if not datei.exists():
        return 1
    with datei.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f), 1)


def _vermerk(lauf):
    """Hängt den Lauf an das gemeinsame Laufprotokoll ERG/oparl_laeufe.tsv an (Spalten wie explore/oparl_messung.py)."""
    ERG.mkdir(parents=True, exist_ok=True)
    datei = ERG / LAEUFE
    neu = not datei.exists()
    with datei.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, oparl_messung.LAEUFE_SPALTEN, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        if neu:
            w.writeheader()
        w.writerow({k: str(lauf.get(k, "")).replace("\t", " ").replace("\n", " ")
                    for k in oparl_messung.LAEUFE_SPALTEN})


def _lauf(vorgabe):
    """`laden` mit Laufvermerk und Markerdatei (wie oparl_messung.main): Marker vor der ersten Anfrage, Vermerk am Ende
    (ok, abbruch (<Art>), fehler (<Typ>) oder unterbrochen), dann Marker entfernen. Strg+C, SIGTERM und SIGHUP enden wie
    Strg+C (Vermerk „unterbrochen“)."""
    zeitzone = ZoneInfo("Europe/Berlin")
    lauf = {"lauf": _laufnummer(), "stufe": os.environ.get("RATSATLAS_STUFE", ""), "kommando": "geodaten",
            "parameter": "laden", "start": dt.datetime.now(zeitzone).isoformat(timespec="seconds"),
            "obergrenze": abruf.MAX_ANFRAGEN or "", "protokoll_von": abruf.protokollzeilen(),
            "ergebnis": oparl_messung.UNTERBROCHEN, "meldung": oparl_messung.NICHT_REGULAER}   # schlechter Fall zuerst
    marker = oparl_messung._marker_setzen(lauf)
    vorher = oparl_messung._signale_abfangen()
    abruf.unterbrochen = ""
    try:
        try:
            kat, felder, dateien = _laden()
        except _Ende as e:
            ursache = e.__cause__
            lauf["ergebnis"], lauf["meldung"] = f"abbruch ({ursache.art or 'sonstiges'})", str(ursache)
            print(f"Abbruch ({ursache.art}): {ursache}\nDer ganze Lauf endet ohne weitere Anfrage; die Ergebnisdateien "
                  f"bleiben unverändert. In dieser Nacht keine weitere Anfrage an Server der Stadt (12-Stunden-Regel, "
                  f"gilt auch für oparl_messung.py). Stoppen und berichten.", file=sys.stderr)
            return 2
        lauf["ergebnis"], lauf["meldung"] = "ok", ""
        ERG.mkdir(parents=True, exist_ok=True)
        _schreibe(ERG / "geodaten_katalog.tsv", kat)
        _schreibe(ERG / "geodaten_felder.tsv", felder)
        _zuordnung_schreiben(dateien)
        print(f"{len(kat)} Katalogzeilen, {len(felder)} beschriebene Ebenen → {ERG}")
        try:
            ableiten(dateien, ERG, vorgabe)   # ohne Netz
        except Exception as e:   # die geladenen Dateien liegen im Cache; `ableiten` lässt sich ohne Netz wiederholen
            lauf["meldung"] = f"Ableitungen fehlgeschlagen ({type(e).__name__}); Abruf vollständig"
            print(f"Ableitungen fehlgeschlagen ({type(e).__name__}: {e}); ohne Netz wiederholen mit "
                  "`python3 explore/geodaten.py ableiten`.", file=sys.stderr)
            return 3
        print(f"Ableitungen aus {len(dateien)} Dateien → {ERG}")
        return 0
    except KeyboardInterrupt as e:   # Strg+C, SIGTERM oder SIGHUP (oparl_messung._signal_beenden)
        grund = str(e) if str(e) in signal.Signals.__members__ else "SIGINT"
        lauf["ergebnis"] = oparl_messung.UNTERBROCHEN
        lauf["meldung"] = (f"unterbrochen während einer Anfrage ({grund}): mögliche Sperre, stoppen; "
                           f"{abruf.unterbrochen}" if abruf.unterbrochen else f"unterbrochen ({grund})")
        print(f"Unterbrochen ({grund}). In dieser Nacht keine weitere Anfrage (12-Stunden-Regel); stoppen und "
              "berichten.", file=sys.stderr)
        return 128 + signal.Signals[grund].value
    except Exception as e:   # unerwarteter Fehler: ebenfalls vermerken (sperrt 12 Stunden), dann weiterreichen
        lauf["ergebnis"], lauf["meldung"] = f"fehler ({type(e).__name__})", str(e)[:300]
        raise
    finally:
        oparl_messung._signale(signal.SIG_IGN)   # den Vermerk nicht unterbrechen
        ende = dt.datetime.now(zeitzone)
        lauf.update(abruf.zaehler(), ende=ende.isoformat(timespec="seconds"),
                    dauer_s=f"{(ende - dt.datetime.fromisoformat(lauf['start'])).total_seconds():.0f}",
                    protokoll_bis=abruf.protokollzeilen())
        _vermerk(lauf)
        oparl_messung._marker_entfernen(marker)   # erst nach dem Vermerk
        print(f"Lauf {lauf['lauf']} (geodaten): {lauf['netz']} Anfragen ans Netz, {lauf['cache']} aus dem Cache; "
              f"{lauf['ergebnis']}", file=sys.stderr)
        for s_, behandlung in vorher.items():
            if behandlung is not None:
                signal.signal(s_, behandlung)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
