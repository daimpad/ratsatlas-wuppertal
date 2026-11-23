"""Datenpaket (Zip) des Ratsatlas Wuppertal: data/export/ratsatlas-wuppertal-export.zip (CLAUDE.md 2: Ergebnisse als
Zip-Paket, Audit-Protokolle als TSV). Phase 5, freigegeben am 23.11.2026 (CLAUDE.md 9): veröffentlicht mit der Vorschau,
ohne den Adressindex (nur Verweis auf die Quelle).

Aufruf: `python3 -m pipeline package`, nach `export`. Ohne Netz. Nach ratsatlas-koeln (`pipeline/paket.py` @ d609111);
Abweichungen für den gemeinsamen Kern:
- Ausgeliefert auf beiden Adressen: Das Paket liegt in data/export und kommt mit tools/seite_bauen.py in die Seite, also
  in den Branch deploy (Hauptadresse) und auf GitHub Pages; Köln liefert es nur auf Pages aus. So lädt der Browser es
  vom Server dieser Seite, ohne Übermittlung an GitHub (Datenschutzerklärung unverändert).
- Reproduzierbar: feste Reihenfolge und fester Zeitstempel je Eintrag, damit ein unveränderter Datenstand kein neues
  Paket und keinen neuen Commit im Branch deploy erzeugt.
- Inhalt fest geregelt (INHALT_GEO, AUSGENOMMEN): ohne Adressindex (Entscheidung 23.11.2026), ohne Protokolle des
  Dokumentabrufs (enthalten Abrufadressen; data/LICENSE-DATA.md), ohne Feeds; Haushalt nur mit dem Zusatzthema.

Nie im Paket: Rohdaten der Schnittstelle (data/raw), Texte und PDFs aus dem Dokumentabruf, die Haushalts-PDFs in
content/ (CLAUDE.md 2, 6). Die Bebauungspläne liegen als Byte-Kopie bei (CC BY-ND 4.0)."""
import zipfile
from pathlib import Path

from . import config

ORDNER = "ratsatlas-wuppertal"
DATEI = "ratsatlas-wuppertal-export.zip"
ZEIT = (2020, 1, 1, 0, 0, 0)          # fester Zeitstempel je Eintrag (reproduzierbar)

# Geodaten aus data/geo: Flächen der Stadt (Quartiere, Stadtbezirke; nur Eigenschaften umbenannt), Bebauungspläne
# unverändert und das Straßenverzeichnis mit Straße-zu-Quartier-Tabelle. Nicht der Adressindex (config.HAUSNUMMERN).
INHALT_GEO = (config.ORTSTEILE, config.STADTBEZIRKE, config.BPLAN, config.BPLAN_LAUFEND, config.STRASSEN)
# In data/export, aber nicht im Paket: Feeds (auf der Seite), Assistent, Paket selbst; Protokolle des Dokumentabrufs
# (nur lokal, mit Abrufadressen)
AUSGENOMMEN_ORDNER = {"feeds", "chat"}
AUSGENOMMEN_DATEIEN = {config.DOKUMENTE_PROTOKOLL.name, config.DOKUMENTE_STATISTIK.name, DATEI,
                       "LICENSE-DATA.md"}   # liegt oben im Paket
HAUSHALT = config.ROOT / "data" / "haushalt"
BERICHTE = {"BERICHT_phase3_verortung.md": None, "BERICHT_haushalt_phase0.md": "haushalt"}

LIESMICH = f"""Ratsatlas Wuppertal – Datenpaket

Abgeleitet aus dem Ratsinformationssystem der Stadt Wuppertal (OParl-API) und den offenen Geodaten der Stadt Wuppertal.
Maßgeblich ist immer das Original im Ratsinformationssystem (https://ris.wuppertal.de/).

Namensnennung
- {config.NAMENSNENNUNG}
- Bebauungspläne: {config.NAMENSNENNUNG_BPLAN} (Dateien unverändert)
- Ratsdaten: Quelle: Stadt Wuppertal, Ratsinformationssystem (OParl-API). Lizenz: {config.LIZENZ_OPARL}
Lizenzen je Datei und offene Punkte: LICENSE-DATA.md

Inhalt
- export/wuppertal/: Vorlagen je Quartier, Stadtbezirk und ohne Ortsbezug, Suche, Zeitleiste, Abläufe, verortete
  Vorlagen (GeoJSON), Flächen der Karte, Datensatzbeschreibung (DCAT), Termine (iCalendar)
- export/audit_*.tsv: Prüfprotokolle (Verortung mit Stufe, Methode, Konfidenz und Fundstelle; Abläufe; Zeit;
  Änderungen an Vorlagen; Bebauungspläne; Amt im Kopf der Vorlage)
- export/stichprobe_*.tsv und Unterordner: Stichproben zur Prüfung von Hand
- export/verifikation_*: Stichprobe veröffentlichter Vorlagen gegen die OParl-API und Prüfliste für den Abgleich
  von Hand mit dem Ratsinformationssystem
- export/abrufstatistik*.tsv: Anfragen, Fehler und Dauer je Abruf der Schnittstelle
- geo/: Quartiere, Stadtbezirke, rechtsverbindliche und laufende Bebauungspläne, Straßenverzeichnis mit Quartieren
- volltext/orte_volltext.json: aus den Anlagen der Vorlagen abgeleitete Orte (Name, Ebene, Quartier, Methode,
  Konfidenz, Dokumentteil); kein Text, keine Zitate
- haushalt/ (nur mit dem Thema Haushalt): Beträge aus dem Haushaltsplan 2026/2027 mit Fundstelle
- berichte/: Berichte zur Verortung und zum Haushalt

Nicht enthalten
- Texte, Auszüge und PDFs der Ratsdokumente (Lizenz ausstehend) und Rohdaten der Schnittstelle
- der Adressindex aus den georeferenzierten Bestandsadressen; Quelle: Stadt Wuppertal,
  https://daten.wuppertal.de/Geografie_Geologie_Geodaten/Adressen_EPSG4326_JSON.json (CC BY 4.0)

Abgeleitete Angaben (Einreichende aus der Vorlagenart, Ortsbezüge, Folgevorlagen) sind in den Feldern method,
confidence und evidence gekennzeichnet. Personennamen und Wohnadressen werden nicht verortet.
Quellcode: https://github.com/daimpad/ratsatlas-wuppertal (MIT)
"""


def _eintrag(z, name, daten):
    info = zipfile.ZipInfo(f"{ORDNER}/{name}", date_time=ZEIT)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    z.writestr(info, daten)


def dateien():
    """(Name im Paket, Quelldatei) in fester Reihenfolge."""
    out = []
    for path in sorted(config.EXPORT.rglob("*")):
        rel = path.relative_to(config.EXPORT)
        if path.is_file() and path.suffix != ".zip" and path.name not in AUSGENOMMEN_DATEIEN \
                and not AUSGENOMMEN_ORDNER & set(rel.parts):
            out.append((f"export/{rel.as_posix()}", path))
    out += [(f"geo/{p.name}", p) for p in INHALT_GEO if p.is_file()]
    if config.VOLLTEXT_ORTE.is_file():
        out.append((f"volltext/{config.VOLLTEXT_ORTE.name}", config.VOLLTEXT_ORTE))
    if config.ZUSATZTHEMEN.get("haushalt") and HAUSHALT.is_dir():
        out += [(f"haushalt/{p.name}", p) for p in sorted(HAUSHALT.iterdir()) if p.suffix in (".tsv", ".json", ".geojson")]
    for name, thema in BERICHTE.items():
        pfad = config.ROOT / "inventur" / name
        if pfad.is_file() and (thema is None or config.ZUSATZTHEMEN.get(thema)):
            out.append((f"berichte/{name}", pfad))
    return out


def write(target=None):
    target = Path(target or config.EXPORT / DATEI)
    if not (config.EXPORT / config.STADT / "index.json").is_file():
        raise SystemExit(f"Datenpaket: {config.EXPORT / config.STADT / 'index.json'} fehlt – erst `export`.")
    inhalt = dateien()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        _eintrag(z, "LIESMICH.txt", LIESMICH)
        _eintrag(z, "LICENSE-DATA.md", (config.ROOT / "data" / "LICENSE-DATA.md").read_bytes())
        for name, path in inhalt:
            _eintrag(z, name, path.read_bytes())
    print(f"Datenpaket → {target} ({len(inhalt) + 2} Dateien, {target.stat().st_size // 1024} KB)")
    return target
