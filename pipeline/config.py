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
# Seitenprotokoll des Vorlagenabrufs (je Seite: Zahl der Vorlagen, Spannen von `date` und `created`, Zeitfilter);
# nur Zahlen und Zeitpunkte, keine Titel, Namen oder Dateinamen
ABRUFSTATISTIK_SEITEN = EXPORT / "abrufstatistik_seiten.tsv"
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
# Zeitfilter des Vollabrufs der Vorlagen (CLAUDE.md 2 und 5.1; Phase 2, Entscheidung 13.11.2026). Die Vorlagenliste ist
# absteigend nach `created` sortiert (Stufe 1 und 3); gelesen wird über links.next bis zur ersten Seite, deren Vorlagen
# alle ein `created` vor DATEN_AB haben (Grenzseite, Stufe 3: G = 87), und danach so viele weitere Seiten in Folge ohne
# Vorlage im Zeitraum (`date` ab DATEN_AB), wie ABRUF_SICHERHEITSABSTAND angibt; eine Seite mit Treffer setzt die Zählung
# zurück. Vorgabe 5, begründet aus Stufe 3: Auf Seite 86 lagen 14, auf Seite 87 (G) noch 7 Vorlagen mit `date` ab 2020
# trotz `created` davor (Abstand bis 516 Tage); halbiert sich die Zahl je Seite weiter, sind ab der vierten Seite nach G
# weniger als 0,5 zu erwarten, die fünfte gibt Reserve. Die Seiten ab 88 sind nicht gemessen: Die nötige Größe ist offen
# und wird am ersten Vollabruf aus dem Seitenprotokoll (ABRUFSTATISTIK_SEITEN) geprüft. Mindestens 1
ABRUF_SICHERHEITSABSTAND = int(os.environ.get("RATSATLAS_SICHERHEITSABSTAND", "5"))
# Sitzungen (Entscheidung 13.11.2026): nicht die ganze Sitzungsliste, sondern die von Beratungen der Vorlagen im Zeitraum
# verwiesenen Sitzungen einzeln über ihre Kennung, dazu die ersten ABRUF_SITZUNGSSEITEN Seiten der Sitzungsliste für
# künftige Termine (Stufe 4: die Seiten 1 und 2 enthielten 188 künftige Sitzungen bis 09.09.2030; die Liste ist nicht
# nach `start` sortiert). 0 = keine Seite der Liste
ABRUF_SITZUNGSSEITEN = int(os.environ.get("RATSATLAS_SITZUNGSSEITEN", "2"))
# Schon geholte Sitzungen werden erneut einzeln abgerufen, solange ihr `start` in der Zukunft oder höchstens so viele Tage
# zurück liegt (Ergebnisse der TOPs werden nach der Sitzung eingetragen). Annahme, nicht gemessen
SITZUNG_NACHLAUF_TAGE = int(os.environ.get("RATSATLAS_SITZUNG_NACHLAUF", "60"))
# Sitzungen, deren Einzelabruf mit HTTP 404 oder 410 endete, werden erst nach so vielen Tagen erneut angefragt
SITZUNG_FEHLT_TAGE = 7
# So viele Einzelabrufe in Folge mit HTTP 404/410 beenden den Lauf (Einzeladresse der Sitzungen prüfen; Form und Antwort
# einer einzelnen Sitzung sind nicht gemessen). Einzelne Sitzungen mit HTTP 401/403 (etwa nicht öffentlich) werden
# vermerkt und nach SITZUNG_FEHLT_TAGE erneut angefragt; erst so viele neu abgewiesene in Folge beenden den Lauf
SITZUNG_FEHLT_IN_FOLGE = 5
SITZUNG_ABGEWIESEN_IN_FOLGE = 2
# Künftige Sitzungen im Cache, die nur aus den ersten Seiten der Liste stammen, auf die keine Vorlage verweist und die
# in diesem Lauf nicht mehr auf diesen Seiten standen: höchstens so viele je Lauf einzeln erneuert (Absagen,
# Verschiebungen); Annahme, nicht gemessen
SITZUNG_KUENFTIGE_HOECHSTENS = int(os.environ.get("RATSATLAS_SITZUNG_KUENFTIGE", "50"))
# Anlagen der Vorlagen (auxiliaryFile; Entscheidung 13.11.2026 zum Download der Ratsdokumente, pipeline/dokumente.py):
# PDF laden, Text extrahieren, PDF sofort löschen. Texte nur lokal bzw. im Zwischenspeicher von GitHub Actions unter
# TEXTE_ORDNER (data/raw/, nicht versioniert), nie im Repository, auf der Seite oder im Datenpaket (CLAUDE.md 2, 6).
# Zustand mit Fingerabdruck je Datei (fortsetzbar), Abrufprotokoll je Datei und Statistik je Lauf ohne Dateinamen
TEXTE_ORDNER = RAW / "texte"
DOKUMENTE_ZUSTAND = RAW / "zustand_dokumente.json"
DOKUMENTE_PROTOKOLL = EXPORT / "abruf_dokumente.tsv"
DOKUMENTE_STATISTIK = EXPORT / "abrufstatistik_dokumente.tsv"
# Eigene Ratenlogik für Dokumente (Abweichung vom nächtlichen Zeitfenster der OParl-Listen nach Entscheidung des
# Auftraggebers, 13.11.2026): tagsüber (DOKUMENTE_TAG, Stunden von–bis Ortszeit Europe/Berlin) mindestens 5 s, nachts
# mindestens 2 s vom Ende einer Antwort bis zur nächsten Anfrage; kleinere Werte gelten nur für lokale Testserver
DOKUMENTE_TAG = (6, 23)
DOKUMENTE_ABSTAND_TAG = float(os.environ.get("RATSATLAS_DOKUMENTE_ABSTAND_TAG", "5"))
DOKUMENTE_ABSTAND_NACHT = float(os.environ.get("RATSATLAS_DOKUMENTE_ABSTAND_NACHT", "2"))
# Obergrenzen je Lauf: Zahl der Anfragen, geladene Bytes und Laufzeit in Sekunden (0 = ohne Laufzeitgrenze; in GitHub
# Actions kleiner als die Grenze des Jobs wählen, damit der Zwischenspeicher noch gesichert wird). Annahmen, nicht
# gemessen (Größe der Anlagen misst Stufe 6)
DOKUMENTE_MAX_DATEIEN = int(os.environ.get("RATSATLAS_DOKUMENTE_MAX_DATEIEN", "2000"))
DOKUMENTE_MAX_BYTES = int(os.environ.get("RATSATLAS_DOKUMENTE_MAX_BYTES", str(3 * 1024 ** 3)))
DOKUMENTE_MAX_SEKUNDEN = int(os.environ.get("RATSATLAS_DOKUMENTE_MAX_SEKUNDEN", "0"))
# Größenlimit je Datei: darüber wird nur der Kopf gelesen (Content-Length) bzw. nach dem Limit abgebrochen, die Datei
# als „zu groß“ vermerkt und übersprungen
DOKUMENTE_MAX_DATEI_BYTES = int(os.environ.get("RATSATLAS_DOKUMENTE_MAX_DATEI_BYTES", str(25 * 1024 ** 2)))
# freier Plattenplatz unter TEXTE_ORDNER, unter dem kein Lauf beginnt und kein weiterer Download folgt
DOKUMENTE_MIN_FREI = int(os.environ.get("RATSATLAS_DOKUMENTE_MIN_FREI", str(2 * 1024 ** 3)))
# höchste Dauer der Textextraktion je Datei (eigener Prozess) und eines Downloads insgesamt, in Sekunden
DOKUMENTE_EXTRAKTION_SEKUNDEN = 120
DOKUMENTE_GESAMTFRIST = 600
# Vorrang des OParl-Abrufs: Im Zeitfenster der OParl-Listen (ABRUF_ZEITFENSTER, 23–1 Uhr) beginnt keine Anfrage für
# Dokumente; ein laufender Lauf endet dort ohne Fehler (Art `vorrang`), damit der nächtliche Abruf die Sperre
# (abruf.lock) bekommt. RATSATLAS_DOKUMENTE_VORRANG=nein hebt das auf (etwa wenn in der Nacht kein OParl-Abruf läuft)
DOKUMENTE_OPARL_VORRANG = os.environ.get("RATSATLAS_DOKUMENTE_VORRANG", "ja") != "nein"
# Dateien, die mit HTTP 404 oder 410 antworteten, werden erst nach so vielen Tagen erneut angefragt; so viele in Folge
# beenden den Lauf (Art `http`, vermutlich ein Fehler der Adressen, keine fehlenden Einzeldateien)
DOKUMENTE_FEHLT_TAGE = 7
DOKUMENTE_FEHLT_IN_FOLGE = 5
# Abgewiesene Dateien (HTTP 401/403, HTML-Seite statt PDF, verdächtige andere Antwort wie leerer Inhalt, Text oder JSON;
# etwa eine nicht öffentliche Anlage): je Datei vermerkt, erneuter Versuch nach DOKUMENTE_ABGEWIESEN_TAGE Tagen; erst so
# viele neu abgewiesene Dateien in Folge beenden den Lauf als mögliche Sperre (wie die Messstufen: zwei 401 in Folge)
DOKUMENTE_ABGEWIESEN_TAGE = 7
DOKUMENTE_ABGEWIESEN_IN_FOLGE = 2
# Vorrang des OParl-Abrufs mit Vorlauf: keine Datei beginnt, wenn das Zeitfenster der OParl-Listen innerhalb so vieler
# Sekunden beginnt (Gesamtfrist eines Downloads, Extraktion und Abstand), und keine Pause nach 429/5xx reicht hinein
DOKUMENTE_VORRANG_VORLAUF = DOKUMENTE_GESAMTFRIST + DOKUMENTE_EXTRAKTION_SEKUNDEN + 60
# Obergrenze der Anfragen je Kalendertag (Ortszeit Europe/Berlin) über alle Läufe; Annahme wie DOKUMENTE_MAX_DATEIEN,
# nicht gemessen; die Zahl legt der Auftraggeber mit den Messwerten aus Stufe 6 fest
DOKUMENTE_MAX_TAG = int(os.environ.get("RATSATLAS_DOKUMENTE_MAX_TAG", "2000"))
# Zustand der Dokumente höchstens alle so viele Sekunden schreiben (und am Ende jedes Laufs, auch nach Abbruch oder
# SIGTERM); nach einem harten Abbruch (SIGKILL) werden höchstens die Dateien dieser Spanne erneut geladen
DOKUMENTE_ZUSTAND_SEKUNDEN = 30
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
# Beginn des Zeitraums (CLAUDE.md 2: Vorlagen mit date ab 01.01.2020): für Texte, Zeitachse, den Ersatzzeitpunkt leerer
# Feeds und den Zeitfilter des Abrufs (pipeline/sessionnet.py, ABRUF_SICHERHEITSABSTAND oben)
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
