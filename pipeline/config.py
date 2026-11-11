"""Pfade, Quellen, Lizenzen und Abrufpolitik der Pipeline (Ratsatlas Wuppertal).

Aufbau nach ratsatlas-koeln @d609111 (pipeline/config.py); Werte auf Wuppertal umgestellt (CLAUDE.md 2, 3, 9). Was
noch nicht gemessen ist (Geodaten nach Stufe G, Wahlperioden, Zeitfilter), bleibt offen und ist als TODO markiert."""
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
# Beratungen mit Sitzung und TOP (in Bonn aus OParl-Lite; in Köln und Wuppertal vom SessionNet-Adapter aus den Sitzungen
# abgeleitet, gleiches Format: uri, meeting{uri,name,startDate,cancelled}, agendaItem{uri,number,name,result,public})
BERATUNGEN = RAW / "beratungen.jsonl"
CONSULTATIONS_LITE = BERATUNGEN
MEETINGS = RAW / "meetings.json"
# Wahlperioden: Wuppertal setzt body.legislativeTerm nicht (CLAUDE.md 3.1); die Datei bleibt dann leer. Beginn und Ende
# der Wahlperioden 2020–2025 und 2025–2030 sind nicht belegt (nur die Wahltage) – TODO nach Messstufe 3
LEGISLATIVE_TERMS = RAW / "legislative_terms.json"
BESETZUNG = RAW / "besetzung.json"   # Auszug laufender Mitgliedschaften ohne Kontaktdaten (pipeline/besetzung.py)
OSM_STREETS = RAW / "osm_streets.json"
# Volltexte (in Wuppertal aus auxiliaryFile, Phase 3): nur zur Verarbeitung, lokal und im Zwischenspeicher des
# Workflows; nie im Repository, auf der Seite oder im Datenpaket (CLAUDE.md 2 und 6)
TEXTE = RAW / "texte.jsonl"
OSM_TILES = RAW / "osm_tiles"
STAND = RAW / "STAND.json"
# Gebiete und Straßen: entstehen erst nach Messstufe G aus den Geodaten der Stadt (CLAUDE.md 3.2: 69 Quartiere,
# 10 Stadtbezirke, Straßenverzeichnis, Bestandsadressen, B-Pläne); bis dahin fehlen die Dateien (TODO Phase 2/3).
# Die Eigenschaften der Flächen heißen wie in Bonn (ortsteil, ortsteil_bez, bezirk, bezirk_bez); angezeigt wird
# „Quartier“ und „Stadtbezirk“
ORTSTEILE = GEO / "quartiere_wuppertal.geojson"
STADTBEZIRKE = GEO / "stadtbezirke_wuppertal.geojson"
STRASSEN = GEO / "strassen_wuppertal.json"
BPLAN = GEO / "bebauungsplaene_wuppertal.geojson"     # CC BY-ND 4.0: Geometrien unverändert
PLAN_LOG = GEO / "bebauungsplaene_protokoll.tsv"
HAUSNUMMERN = GEO / "hausnummern_wuppertal.json"
OBJEKTE = GEO / "objekte_wuppertal.json"              # kuratierte Ortsliste (CLAUDE.md 5.2), Phase 3
DB = BUILD / "allris.sqlite"
# Feldnamen der Geodaten der Stadt für pipeline/ortsnamen.py (aus_feldern), an dieser einen Stelle. Stand: nicht
# gemessen. CLAUDE.md 3.2 nennt für das Straßenverzeichnis „u. a.“ STRSCHL, STRNAME, STADTBEZIRK; diese Angaben und alle
# übrigen Felder prüft Messstufe G (explore/geodaten.py, ROLLEN). None = offen (aus_feldern bricht mit FeldFehlt ab);
# False = in der Quelle nicht vorhanden (erst nach Stufe G eintragen). Koordinaten kommen aus der Geometrie, nicht aus
# Feldern
GEO_FELDER = {
    "strassen": {"schluessel": "STRSCHL", "name": "STRNAME", "stadtbezirk": "STADTBEZIRK"},   # CLAUDE.md 3.2, zu prüfen
    "adressen": {"schluessel": None, "strasse": None, "hausnummer": None, "zusatz": None, "stadtbezirk": None},
    "quartiere": {"name": None, "nummer": None, "stadtbezirk": None},
    "stadtbezirke": {"name": None, "nummer": None},
}
# Schema der B-Plan-Nummern in Titeln (regulärer Ausdruck für eine Nummer): offen bis Messstufe G; ohne Schema findet
# ortsnamen.plan_nummern nichts
BPLAN_NUMMER = None

# OParl-API der Stadt Wuppertal (Somacos SessionNet, CLAUDE.md 3.1); Abruf nur nach Information der Stadt (5.1, 9)
OPARL_SYSTEM = os.environ.get("RATSATLAS_OPARL_SYSTEM", "https://oparl.wuppertal.de/oparl/system")
OPARL_BODY = os.environ.get("RATSATLAS_OPARL_BODY", "https://oparl.wuppertal.de/oparl/bodies/0001")
# Zustand des inkrementellen Abrufs (letzte Änderungszeitpunkte je Liste) und Abrufstatistik je Lauf
ZUSTAND = RAW / "zustand_abruf.json"
ABRUFSTATISTIK = EXPORT / "abrufstatistik.tsv"
# Änderungsprotokoll der Vorlagen (CLAUDE.md 5.1, pipeline/aenderungen.py): Vorstand des vorigen Laufs (nur
# Vergleichswerte, nicht veröffentlicht) und Protokoll, fortlaufend angehängt wie die Abrufstatistik
VORSTAND = RAW / "vorstand_aenderungen.json"
AENDERUNGEN = EXPORT / "audit_aenderungen.tsv"
# Abrufpolitik (CLAUDE.md 5.1): eine Verbindung, Abstand in Sekunden, nächtliches Zeitfenster (Ortszeit Europe/Berlin),
# wachsende Pausen nach Fehlern bis zu mehreren Stunden
ABRUF_ABSTAND = float(os.environ.get("RATSATLAS_ABSTAND", "2.0"))
# Zeitfenster 23–1 Uhr: vorsichtige Vorgabe aus Köln (dort laut mandari, ohne Quelle der Stadt). Für Wuppertal gibt es
# keine Angabe der Stadt; Abrufrate und -zeit sind Teil der Anfrage (explore/ANFRAGE_stadt_wuppertal.md, CLAUDE.md 8)
# Stunden von-bis; für Server der Stadt nur innerhalb von 23–1 Uhr (engere Fenster erlaubt). Leer oder weiter (0-24,
# 22-2) gilt nur für Testadressen (Loopback, .invalid), sonst bricht der Abruf ohne Anfrage ab (abruf.fenster_zulaessig)
ABRUF_ZEITFENSTER = os.environ.get("RATSATLAS_ZEITFENSTER", "23-1")
# Seiten je Liste und Lauf (Schutz vor Schleifen); eine Fortsetzung zählt in ihrem Lauf neu. Mit 2 s Abstand und dem
# Zeitfenster 23–1 Uhr schafft ein Lauf höchstens rund 2600–3300 Seiten (je Seite 2 s Abstand plus Antwortzeit); die
# Grenze von 4000 wirkt daher nur ohne Zeitfenster oder mit einem kleineren Wert
ABRUF_MAX_SEITEN = int(os.environ.get("RATSATLAS_MAX_SEITEN", "4000"))
# Gesamtgrenze eines Vollabrufs über seine Fortsetzungen hinweg: höchstens ABRUF_MAX_SEITEN_FAKTOR × ABRUF_MAX_SEITEN
# Seiten (Schutz gegen eine Liste, die endlos neue Kennungen erzeugt); darüber Abbruch der Art `liste` (sessionnet.py)
ABRUF_MAX_SEITEN_FAKTOR = 3
ABRUF_PAUSEN = [60, 300, 1800, 3600, 3 * 3600]
# leer = Vorgabe des Servers (Wuppertal: 100 Objekte je Seite, CLAUDE.md 3.1; ein Parameter `limit` ist nicht gemessen)
ABRUF_SEITENGROESSE = os.environ.get("RATSATLAS_LIMIT", "")
# OpenStreetMap nur nachrangig (CLAUDE.md 3.2); fetch-objects ist abgeschaltet, bis STADT_BBOX vorliegt
OVERPASS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
# Umgebendes Rechteck des Stadtgebiets (Süd, West, Nord, Ost): offen bis Messstufe G (aus den Flächen der Stadtbezirke
# bzw. Quartiere ableiten, nicht schätzen). None: kein Kachelabruf, DCAT ohne bbox
STADT_BBOX = None
# Kontakt im User-Agent: festgelegt auf contact@nozilla.de (Entscheidung 09.11.2026, CLAUDE.md 9). RATSATLAS_KONTAKT
# darf nur denselben Wert tragen (Leerraum am Rand, etwa ein Zeilenumbruch aus der Repository-Variable, entfällt); ein
# anderer Wert steht in KONTAKT_ABWEICHEND, und abruf.get_json bricht dann vor der ersten Anfrage laut ab
KONTAKT = "contact@nozilla.de"
_KONTAKT_UMGEBUNG = os.environ.get("RATSATLAS_KONTAKT", "").strip()
KONTAKT_ABWEICHEND = _KONTAKT_UMGEBUNG if _KONTAKT_UMGEBUNG and _KONTAKT_UMGEBUNG != KONTAKT else None
USER_AGENT = f"ratsatlas-wuppertal/0.1 (+https://github.com/daimpad/ratsatlas-wuppertal; {KONTAKT})"

# Quellenkennungen in Datenbank und Exporten
QUELLE_OPARL = "oparl-wuppertal"      # Vorlagen, Organisationen, Beratungen
QUELLE_SITZUNG = "oparl-wuppertal"    # Sitzungen und TOPs (in Bonn aus OParl-Lite, in Wuppertal aus derselben API)
QUELLE_GEO = "geo-wuppertal"          # Quartiere
QUELLE_STADTBEZIRKE = "stadtbezirke-wuppertal"
QUELLE_STRASSEN = "strassen-wuppertal"
QUELLE_ADRESSEN = "adressen-wuppertal"
QUELLE_BPLAN = "bplan-wuppertal"
# Namensnennung wörtlich aus CLAUDE.md 3.2 (Geodaten CC BY 4.0, B-Pläne CC BY-ND 4.0)
NAMENSNENNUNG = "Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0"
NAMENSNENNUNG_BPLAN = "Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0"
# Lizenz der OParl-Daten: Body-Feld `license` leer, kein OParl-Datensatz im Open-Data-Portal (CLAUDE.md 3.1, 8).
# Lizenztexte stehen in jedem Export: ohne Verweise auf interne Arbeitsdateien (CLAUDE.md, Messstufen)
LIZENZ_OPARL = ("Lizenz ungeklärt (Body-Feld license leer, kein OParl-Datensatz im Open-Data-Portal; Anfrage an die "
                "Stadt offen); Quelle: Stadt Wuppertal, Ratsinformationssystem (OParl-API)")

# Quelle je Datensatz; wird in die Datenbank und in jeden Export übernommen. URLs wie in CLAUDE.md 3.2
SOURCES = {
    QUELLE_OPARL: {
        "url": OPARL_BODY,
        "license": LIZENZ_OPARL,
    },
    QUELLE_GEO: {
        "url": "https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Quartiere_EPSG4326_JSON.json",
        "license": "CC BY 4.0 (Stadt Wuppertal, Quartiere); " + NAMENSNENNUNG,
    },
    QUELLE_STADTBEZIRKE: {
        # Schreibweise aus CLAUDE.md 3.2 ohne Schema; https:// ergänzt. Lizenz laut Open-Data-Katalog (Katalogprüfung
        # 10.11.2026, explore/strukturdaten/audit_quellen.tsv, Zeile „Stadtbezirke Wuppertal (Geometrie)“: cc-by/4.0);
        # Adresse und Datei selbst prüft Messstufe G
        "url": "https://offenedaten-wuppertal.de/dataset/stadtbezirke-wuppertal",
        "license": ("CC BY 4.0 (Stadt Wuppertal, Stadtbezirke; laut Open-Data-Katalog, 10.11.2026; Prüfung der Datei "
                    "steht aus); " + NAMENSNENNUNG),
    },
    QUELLE_STRASSEN: {
        "url": "https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Strassenverzeichnis_CSV.zip",
        "license": "CC BY 4.0 (Stadt Wuppertal, Straßenverzeichnis); " + NAMENSNENNUNG,
    },
    QUELLE_ADRESSEN: {
        "url": "https://daten.wuppertal.de/Geografie_Geologie_Geodaten/Adressen_EPSG4326_JSON.json",
        "license": "CC BY 4.0 (Stadt Wuppertal, georeferenzierte Bestandsadressen); " + NAMENSNENNUNG,
    },
    QUELLE_BPLAN: {
        "url": "https://daten.wuppertal.de/Gesetze_Justiz/rvbBebauungsplanverfahren_EPSG4326_JSON.json",
        "license": ("CC BY-ND 4.0 (Stadt Wuppertal, rechtsverbindliche Bebauungspläne; Open.NRW nennt abweichend "
                    "„Andere geschlossene Lizenz“, Klärung offen); Geometrien unverändert; "
                    + NAMENSNENNUNG_BPLAN),
    },
    "osm": {
        "url": "https://www.openstreetmap.org/copyright",
        "license": ("ODbL 1.0, © OpenStreetMap-Mitwirkende (Ortsbezüge nur nachrangig, getrennt gekennzeichnet; "
                    "Kartenhintergrund: Kacheln von tile.openstreetmap.org nach der Tile Usage Policy der OSMF)"),
    },
}

# Stadt: Schlüssel für Exportpfade (data/export/wuppertal) und Bezeichnung auf der Seite
STADT = "wuppertal"
STADT_NAME = "Wuppertal"
SEITENNAME = "Ratsatlas Wuppertal"
# Beginn des Zeitraums (CLAUDE.md 2: Vorlagen mit date ab 01.01.2020). Hier nur für Texte, Zeitachse und den Ersatz-
# zeitpunkt leerer Feeds; das Verwerfen älterer Vorlagen beim Abruf hängt an der Messung der Sortierung (Messstufe 1/2)
DATEN_AB = "2020-01-01"

# Kein Pilotgebiet (CLAUDE.md 2); bleibt für Module, die den Bonner Pilot noch kennen (check.py, verify.py)
PILOT_ORTSTEIL = None

# Zusatzthemen aus Bonn: deaktiviert, nicht gelöscht (CLAUDE.md 5.4, Entscheidung 09.11.2026 zu Phase 0); einzeln
# freizugeben. Anders als in Köln auch „kontext“ (Kennzahlen je Gebiet) aus; „technik“ bis Phase 5 aus
ZUSATZTHEMEN = {
    "haushalt": False, "baustellen": False, "anliegen": False, "wahlen": False, "themenseiten": False,
    "kontext": False, "soll": False, "chat": False,
    "einfache_sprache": False, "kurzfassungen": False, "mitmachen": False, "besetzung": False,
    # Seite technik/ (aus den Workflows erzeugt; Phase 5)
    "technik": False,
}

# Archiv der Baustellen (Bonn, deaktiviert; Branch „archiv“, im Workflow nach _archiv ausgecheckt)
BAUSTELLEN_ARCHIV = Path(os.environ.get("BAUSTELLEN_ARCHIV", ROOT / "_archiv"))
# noch nicht in SOURCES, solange die Baustellen nicht auf der Seite erscheinen
BAUSTELLEN_LICENSE = ("CC0 1.0 (Stadt Bonn, Baustellen tagesaktuell und geplant; Lizenz laut Auftraggeber, die Datensätze "
                      "sind nicht mehr im Katalog von opendata.bonn.de)")

# Öffentliche Adresse der Seite (für absolute Links in Feeds, Kalender und DCAT-Beschreibung; CLAUDE.md 2)
SITE_URL = os.environ.get("SITE_URL", "https://wuppertal.ratsatlas.de/")
# Das Datenpaket (Zip) liegt nur auf der Ausweichadresse (GitHub Pages); der Branch `deploy` enthält es nicht
PAKET_URL = os.environ.get("PAKET_URL",
                           "https://daimpad.github.io/ratsatlas-wuppertal/data/export/ratsatlas-wuppertal-export.zip")
