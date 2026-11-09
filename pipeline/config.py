"""Pfade, Quellen und Lizenzen der Pipeline."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
GEO = ROOT / "data" / "geo"
BUILD = ROOT / "data" / "build"
EXPORT = ROOT / "data" / "export"

PAPERS = RAW / "papers.jsonl"
ORGANIZATIONS = RAW / "organizations.json"
VERWALTUNGSBEREICHE = RAW / "verwaltungsbereiche.json"
CONSULTATIONS_LITE = RAW / "consultations_lite.jsonl"
MEETINGS = RAW / "meetings.json"
LEGISLATIVE_TERMS = RAW / "legislative_terms.json"
BESETZUNG = RAW / "besetzung.json"   # Auszug laufender Mitgliedschaften ohne Kontaktdaten (pipeline/besetzung.py)
OSM_STREETS = RAW / "osm_streets.json"
# Volltexte der Hauptdokumente (aus OParl-Lite, dort aus den PDFs der Stadt extrahiert): nur zur Verarbeitung,
# lokal und im Zwischenspeicher des Workflows; nie im Repository, auf der Seite oder im Datenpaket
TEXTE = RAW / "texte.jsonl"
OSM_TILES = RAW / "osm_tiles"
STAND = RAW / "STAND.json"
ORTSTEILE = GEO / "ortsteile_bonn.geojson"
STADTBEZIRKE = GEO / "stadtbezirke_bonn.geojson"
# Straßenverzeichnis (Name → Lagen je Ortsteil), abgeleitet aus OSM; im Repository, damit die
# Aktualisierung ohne Overpass auskommt. Neu erzeugen mit `python -m pipeline gazetteer`.
STRASSEN = GEO / "strassen_bonn.json"
BPLAN = GEO / "bebauungsplaene_bonn.geojson"
PLAN_LOG = GEO / "bebauungsplaene_protokoll.tsv"  # Änderungen zwischen Abrufen (neu, entfallen, Inkrafttreten)
BPLAN_URL = "https://stadtplan.bonn.de/geojson?Thema=20074"
# Hausnummern (Straße → Ortsteil → Nummern), reduziert aus dem georeferenzierten Verzeichnis der Stadt; dient nur
# dazu, bei Titeln mit Hausnummer den Ortsteil einer Straße zu bestimmen, die durch mehrere Ortsteile läuft.
HAUSNUMMERN = GEO / "hausnummern_bonn.json"
HAUSNUMMERN_URL = "https://stadtplan.bonn.de/geojson?OD=171"
OBJEKTE = GEO / "objekte_bonn.json"
DB = BUILD / "allris.sqlite"

OPARL_BODY = "https://www.bonn.sitzung-online.de/oparl/bodies/1"
LITE_GRAPHQL = "https://oparl.bonn.machdenstaat.de/graphql"
OVERPASS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
# Umgebendes Rechteck der 51 Ortsteile (Süd, West, Nord, Ost), für den Kachelabruf gerundet
BONN_BBOX = (50.63, 7.02, 50.78, 7.22)
USER_AGENT = "allris-bonn-pipeline (https://github.com/daimpad/ratsatlas-bonn)"

# Quelle je Datensatz; wird in die Datenbank und in jeden Export übernommen.
SOURCES = {
    "oparl-bonn": {
        "url": OPARL_BODY,
        "license": "CC0 1.0 (Stadt Bonn, Datensatz „Ratsinformationssystem OParl-API“)",
    },
    "oparl-lite": {
        "url": LITE_GRAPHQL,
        "license": "CC BY 4.0 (OParl-Lite Bonn, machdenstaat)",
    },
    "osm": {
        "url": "https://www.openstreetmap.org (Overpass API)",
        "license": "ODbL 1.0, © OpenStreetMap-Mitwirkende",
    },
    "geo-bonn": {
        "url": "https://opendata.bonn.de/dataset/flächen-der-ortsteile",
        "license": "CC0 1.0 (Stadt Bonn)",
    },
    "bplan-bonn": {
        "url": "https://opendata.bonn.de/dataset/lage-der-bebauungspläne",
        "license": "CC0 1.0 (Stadt Bonn, Datensatz „Lage der Bebauungspläne“)",
    },
    "hnr-bonn": {
        "url": "https://opendata.bonn.de/dataset/strassenliste-straßennamen-straßenverzeichnis-hausnummern-georeferenziert",
        "license": "CC0 1.0 (Stadt Bonn, Datensatz „Hausnummern georeferenziert“)",
    },
}

PILOT_ORTSTEIL = "Endenich"

# Archiv der Baustellen (Branch „archiv“, im Workflow nach _archiv ausgecheckt)
BAUSTELLEN_ARCHIV = Path(os.environ.get("BAUSTELLEN_ARCHIV", ROOT / "_archiv"))
# noch nicht in SOURCES, solange die Baustellen nicht auf der Seite erscheinen
BAUSTELLEN_LICENSE = ("CC0 1.0 (Stadt Bonn, Baustellen tagesaktuell und geplant; Lizenz laut Auftraggeber, die Datensätze "
                      "sind nicht mehr im Katalog von opendata.bonn.de)")

# Öffentliche Adresse der Seite (für absolute Links in Feeds, Kalender und DCAT-Beschreibung)
SITE_URL = os.environ.get("SITE_URL", "https://bonn.ratsatlas.de/")   # bis 04.11.2026 ris-bonn.datenatlas.de (leitet weiter)
# Das Datenpaket (Zip) liegt nur auf GitHub Pages; der Branch `deploy` für die Hauptadresse enthält es nicht
# (pages.yml, Schritt „Branch deploy“, setzt dieselbe Adresse in index.html und datenschutz.html)
PAKET_URL = os.environ.get("PAKET_URL", "https://daimpad.github.io/ratsatlas-bonn/data/export/allris-bonn-export.zip")


# ---------------------------------------------------------------------------------------------------------------------
# Übernommen aus daimpad/ratsatlas-koeln @d6091117b82da1d70ee2bd10a764d7be1e0c0361 (pipeline/config.py), Namen und Werte unverändert,
# soweit pipeline/sessionnet.py, pipeline/abruf.py und ihre Tests diese Namen brauchen (Phase 0). Die Werte sind noch
# die Kölner; die Umstellung auf Wuppertal (Endpunkt, Body 0001, Stadtname, User-Agent) folgt in Phase 2.
# Nicht übernommen: die Kölner Neudefinition von OPARL_BODY und USER_AGENT (die Bonner Werte oben bleiben bis Phase 2).
# Ohne RATSATLAS_STADT_INFORMIERT=ja sendet abruf.py keine Anfrage an eine Stadt.
# ---------------------------------------------------------------------------------------------------------------------
# OParl-API der Stadt Köln (SessionNet); Abruf nur nach Information der Stadt (CLAUDE.md 9)
OPARL_SYSTEM = os.environ.get("RATSATLAS_OPARL_SYSTEM", "https://buergerinfo.stadt-koeln.de/oparl/system")
# Zustand des inkrementellen Abrufs (letzte Änderungszeitpunkte je Liste) und Abrufstatistik je Lauf
ZUSTAND = RAW / "zustand_abruf.json"
ABRUFSTATISTIK = EXPORT / "abrufstatistik.tsv"
# Abrufpolitik (CLAUDE.md 5.1): eine Verbindung, Abstand in Sekunden, nächtliches Zeitfenster (Ortszeit Köln),
# wachsende Pausen nach Fehlern bis zu mehreren Stunden
ABRUF_ABSTAND = float(os.environ.get("RATSATLAS_ABSTAND", "2.0"))
# Zeitfenster 23–1 Uhr: laut mandari erlaubt die Stadt Abrufe nur dann (ohne Quelle der Stadt; Anfrage offen,
# explore/ergebnisse/sessionnet_befunde.tsv)
ABRUF_ZEITFENSTER = os.environ.get("RATSATLAS_ZEITFENSTER", "23-1")   # Stunden von-bis; leer = ohne Zeitfenster
# Seiten je Liste und Lauf (Schutz vor Schleifen); eine Fortsetzung zählt in ihrem Lauf neu. Mit 2 s Abstand und dem
# Zeitfenster 23–1 Uhr schafft ein Lauf höchstens rund 2600–3300 Seiten (je Seite 2 s Abstand plus Antwortzeit); die
# Grenze von 4000 wirkt daher nur ohne Zeitfenster oder mit einem kleineren Wert
ABRUF_MAX_SEITEN = int(os.environ.get("RATSATLAS_MAX_SEITEN", "4000"))
# Gesamtgrenze eines Vollabrufs über seine Fortsetzungen hinweg: höchstens ABRUF_MAX_SEITEN_FAKTOR × ABRUF_MAX_SEITEN
# Seiten (Schutz gegen eine Liste, die endlos neue Kennungen erzeugt); darüber Abbruch der Art `liste` (sessionnet.py)
ABRUF_MAX_SEITEN_FAKTOR = 3
ABRUF_PAUSEN = [60, 300, 1800, 3600, 3 * 3600]
ABRUF_SEITENGROESSE = os.environ.get("RATSATLAS_LIMIT", "")          # leer = Vorgabe des Servers (25)

# Rohdatei der Beratungen des SessionNet-Adapters (in Köln zugleich CONSULTATIONS_LITE)
BERATUNGEN = RAW / "beratungen.jsonl"

# Quellenkennungen in Datenbank und Exporten
QUELLE_OPARL = "oparl-koeln"      # Vorlagen, Organisationen, Beratungen
QUELLE_SITZUNG = "oparl-koeln"    # Sitzungen und TOPs (in Bonn aus OParl-Lite, in Köln aus derselben API)

# Stadt: Schlüssel für Exportpfade (data/export/koeln) und Bezeichnung auf der Seite
STADT = "koeln"
