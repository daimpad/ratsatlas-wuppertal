# Lizenzen der Daten

> **Entwurf – Lizenz der Ratsdaten ungeklärt, siehe CLAUDE.md 8.** Stand 10.11.2026. Noch liegen keine Daten im Repository oder auf einer veröffentlichten Seite; diese Datei beschreibt, was geplant ist.

Der Code steht unter MIT ([LICENSE im Repository](https://github.com/daimpad/ratsatlas-wuppertal/blob/main/LICENSE)). Für die Daten in `data/` und im Datenpaket gilt:

## Daten der Stadt Wuppertal

| Datei (geplant) | Quelle | Lizenz | Namensnennung |
|---|---|---|---|
| `geo/quartiere_wuppertal.geojson` | Stadt Wuppertal, Quartiere (69), `https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Quartiere_EPSG4326_JSON.json` | CC BY 4.0 | Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0 |
| `geo/stadtbezirke_wuppertal.geojson` | Stadt Wuppertal, Stadtbezirke (10), `https://offenedaten-wuppertal.de/dataset/stadtbezirke-wuppertal` | laut Open-Data-Katalog CC BY 4.0 (Quellenprüfung 10.11.2026); Prüfung der Datei in Messstufe G offen | wie oben |
| `geo/strassen_wuppertal.json` | abgeleitet aus Stadt Wuppertal, Straßenverzeichnis, `https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Strassenverzeichnis_CSV.zip` | CC BY 4.0 | wie oben |
| `geo/hausnummern_wuppertal.json` | abgeleitet aus Stadt Wuppertal, georeferenzierte Bestandsadressen, `https://daten.wuppertal.de/Geografie_Geologie_Geodaten/Adressen_EPSG4326_JSON.json` | CC BY 4.0 | wie oben |
| `geo/bebauungsplaene_wuppertal.geojson` | Stadt Wuppertal, rechtsverbindliche Bebauungspläne, `https://daten.wuppertal.de/Gesetze_Justiz/rvbBebauungsplanverfahren_EPSG4326_JSON.json`; Geometrien unverändert | CC BY-ND 4.0 (Open.NRW nennt abweichend „Andere geschlossene Lizenz“; Klärung offen, CLAUDE.md 8) | Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0 |

Alle Dateien entstehen erst nach Messstufe G (`explore/STUFEN.md`).

## Ratsdaten (OParl-API)

- Quelle: Stadt Wuppertal, Ratsinformationssystem, OParl-API `https://oparl.wuppertal.de/oparl/bodies/0001`.
- Lizenz: **ungeklärt.** Das Feld `license` ist in System und Body leer; im Open-Data-Portal gibt es keinen OParl-Datensatz. Die Anfrage an die Stadt folgt nach den Messungen (`explore/ANFRAGE_stadt_wuppertal.md`).
- Bis zur Klärung: Namensnennung „Stadt Wuppertal“ immer; keine Volltexte, Zitate, Auszüge oder PDFs, nur abgeleitete Verortungen mit Fundstelle (erkannter Name und Dokumentteil).

## Weitere Quellen

| Quelle | Lizenz | Verwendung |
|---|---|---|
| OpenStreetMap (Photon/Nominatim) | ODbL 1.0, © OpenStreetMap-Mitwirkende | nur nachrangig für Orte ohne Adresse, getrennt gekennzeichnet |
| Planungs-WMS der Stadt (`https://maps.wuppertal.de/planung`) | nicht angegeben | nur Verweis, nicht eingebunden |
| Wegweiser Kommune (Bertelsmann Stiftung) | CC0 1.0 | Strukturdaten der Gesamtstadt; noch nicht eingebunden (`explore/strukturdaten/`) |

## Abgeleitete Daten des Projekts

Verortungen, Zuordnungen, Audit-Protokolle und Abrufstatistik: Lizenz **bis zur Lizenzklärung (CLAUDE.md 8) nicht festgelegt.** Vorschlag (Entwurf): CC BY 4.0 mit der Namensnennung der Quellen; ausgenommen bleiben die Bebauungspläne (unverändert, CC BY-ND 4.0) und Ableitungen aus OpenStreetMap (ODbL 1.0).

## Namensnennung

Auf jeder Seite und in jedem Export, auch wo die Lizenz sie nicht verlangt:

- „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0“
- Bebauungspläne: „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0“
- Ratsdaten: „Quelle: Stadt Wuppertal, Ratsinformationssystem (OParl-API)“ mit Link zum Original
