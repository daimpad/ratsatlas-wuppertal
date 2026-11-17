# Lizenzen der Daten

> **Entwurf – Lizenz der Ratsdaten ungeklärt (Feld `license` der Schnittstelle leer, Anfrage an die Stadt offen).** Stand 11.11.2026. Noch liegen keine Daten im Repository oder auf einer veröffentlichten Seite; diese Datei beschreibt, was geplant ist.

Der Code steht unter MIT ([LICENSE im Repository](https://github.com/daimpad/ratsatlas-wuppertal/blob/main/LICENSE)). Für die Daten in `data/` und im Datenpaket gilt:

## Daten der Stadt Wuppertal

| Datei (geplant) | Quelle | Lizenz | Namensnennung |
|---|---|---|---|
| `geo/quartiere_wuppertal.geojson` | Stadt Wuppertal, Quartiere (69), `https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Quartiere_EPSG4326_JSON.json` | CC BY 4.0 | Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0 |
| `geo/stadtbezirke_wuppertal.geojson` | Stadt Wuppertal, Stadtbezirke (10), `https://offenedaten-wuppertal.de/dataset/stadtbezirke-wuppertal` | laut Open-Data-Katalog CC BY 4.0 (Quellenprüfung 10.11.2026); Prüfung der Datei selbst steht aus | wie oben |
| `geo/strassen_wuppertal.json` | abgeleitet aus Stadt Wuppertal, Straßenverzeichnis, `https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Strassenverzeichnis_CSV.zip` | CC BY 4.0 | wie oben |
| `geo/hausnummern_wuppertal.json` | abgeleitet aus Stadt Wuppertal, georeferenzierte Bestandsadressen, `https://daten.wuppertal.de/Geografie_Geologie_Geodaten/Adressen_EPSG4326_JSON.json` | CC BY 4.0 | wie oben |
| `geo/bebauungsplaene_wuppertal.geojson` | Stadt Wuppertal, rechtsverbindliche Bebauungspläne, `https://daten.wuppertal.de/Gesetze_Justiz/rvbBebauungsplanverfahren_EPSG4326_JSON.json`; Features (Geometrie und Eigenschaften) unverändert, nur Feld `meta` ergänzt | CC BY-ND 4.0 (Open.NRW nennt abweichend „Andere geschlossene Lizenz“; Klärung offen) | Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0 |
| `geo/bebauungsplaene_laufend_wuppertal.geojson` | Stadt Wuppertal, laufende Bebauungsplanverfahren, `https://offenedaten-wuppertal.de/dataset/laufende-bebauungsplanverfahren-wuppertal`; Features unverändert, nur Feld `meta` ergänzt | CC BY-ND 4.0 | wie bei den Bebauungsplänen |
| `export/wuppertal/flaechen/ortsteile.json`, `export/wuppertal/flaechen/bezirke.json` | abgeleitet aus den Quartieren und Stadtbezirken oben: Geometrie vereinfacht (Toleranz etwa 2 m), sich selbst schneidende Flächen gültig gemacht und gerundet, für die Karte der Seite | CC BY 4.0 | wie oben; Lizenz, Namensnennung und Hinweis auf die Änderung im Feld `meta` der Datei |
| `export/wuppertal/flaechen/bebauungsplaene.json`, `export/wuppertal/flaechen/bebauungsplaene_laufend.json` | Bebauungspläne und laufende Verfahren wie oben, Geometrien unverändert | CC BY-ND 4.0 | wie bei den Bebauungsplänen; im Feld `meta` der Datei |

Haushalt (seit 17.11.2026, noch nicht auf der Seite): `haushalt/produktbereiche.tsv`, `haushalt/bezirke.tsv` und `haushalt/STAND.json` – Beträge aus dem Haushaltsplan 2026/2027 der Stadt Wuppertal, Band 1 (Gesamtergebnisplan, Teilergebnispläne der Produktbereiche, Anlage 9 „bezirksbezogene Haushaltsansätze“), je Betrag mit Datei und Seite. Der Haushaltsplan nennt keine Lizenz (nur das nicht verwendete Titelbild: CC BY-NC-ND); als Teil der Haushaltssatzung vermutlich amtliches Werk (§ 5 UrhG), Klärung mit der Stadt offen. Quelle: Stadt Wuppertal, Haushaltsplan 2026/2027.

Stand 17.11.2026: Die Quartiere, Stadtbezirke, rechtsverbindlichen Bebauungspläne und laufenden Verfahren liegen im Repository unter `data/geo/` (vom Auftraggeber am 16.11.2026 von den Servern der Stadt geladen, übernommen mit `tools/geodaten_uebernehmen.py`). Bei Quartieren und Stadtbezirken sind nur die Eigenschaften umbenannt und der Stadtbezirk der Quartiere abgeleitet (Feld `meta`, Angabe `aenderung`); die Geometrien sind unverändert. Seit 17.11.2026 (Phase 3) liegen dort auch das Straßenverzeichnis mit der Straße-zu-Quartier-Tabelle (`geo/strassen_wuppertal.json`) und der Adressindex aus den georeferenzierten Bestandsadressen (`geo/hausnummern_wuppertal.json`: Straßenschlüssel, Hausnummer, Zusatz, Quartier, Stadtbezirk, Koordinate; Entscheidung des Auftraggebers). Beide dienen der Verortung und werden nicht mit der Seite ausgeliefert; auf der Seite erscheint eine Hauskoordinate nur bei einzelnen Vorlagen, wo sie erlaubt ist (nicht bei Eingaben aus der Einwohnerschaft, Bauaufsicht und Umwelt).

## Ratsdaten (OParl-API)

- Quelle: Stadt Wuppertal, Ratsinformationssystem, OParl-API `https://oparl.wuppertal.de/oparl/bodies/0001`.
- Lizenz: **ungeklärt, mündlich zugesagt, schriftlich ausstehend.** Das Feld `license` ist in System und Body leer; im Open-Data-Portal gibt es keinen OParl-Datensatz. Die Stadt Wuppertal hat am 13.11.2026 mündlich zugestimmt (regelmäßiger Abruf der Schnittstelle, Veröffentlichung der Ratsdaten mit Namensnennung, Auswertung der PDF-Volltexte); die schriftliche Bestätigung steht aus. Zitate, Auszüge und PDFs werden weiterhin nicht veröffentlicht.
- Bis zur Klärung: Namensnennung „Stadt Wuppertal“ immer; keine Volltexte, Zitate, Auszüge oder PDFs, nur abgeleitete Verortungen mit Fundstelle (erkannter Name und Dokumentteil).
- Texte aus den Anlagen der Vorlagen werden nur zur Verarbeitung extrahiert; sie stehen nicht in diesem Repository, auf der Seite oder im Datenpaket. Das Abrufprotokoll der Anlagen (`export/abruf_dokumente.tsv`, `export/abrufstatistik_dokumente.tsv`) enthält Kennungen, Zahlen, Prüfsummen, den Medientyp ohne Parameter und Fehlermeldungen mit der Abrufadresse, keine Dateinamen und keinen Text; es ist für die Prüfung des Abrufs gedacht und gehört nicht ungeprüft ins Datenpaket.

## Weitere Quellen

| Quelle | Lizenz | Verwendung |
|---|---|---|
| OpenStreetMap (Photon/Nominatim) | ODbL 1.0, © OpenStreetMap-Mitwirkende | nur nachrangig für Orte ohne Adresse, getrennt gekennzeichnet |
| OpenStreetMap, Kacheln von `tile.openstreetmap.org` | Daten ODbL 1.0, © OpenStreetMap-Mitwirkende; für die Kartendarstellung nennt openstreetmap.org/copyright keine Lizenz (geprüft 10.11.2026, offen), Kacheln nach der Tile Usage Policy der OSMF | graue und farbige Karte der Seite; Vorschaubild `vorschaubild.jpg` (`tools/vorschaubild.mjs`; im Bild steht „© OpenStreetMap-Mitwirkende“, der Hinweis auf die ODbL fehlt dort noch, offen) |
| Planungs-WMS der Stadt (`https://maps.wuppertal.de/planung`) | nicht angegeben | nur Verweis, nicht eingebunden |
| Wegweiser Kommune (Bertelsmann Stiftung) | CC0 1.0 | Strukturdaten der Gesamtstadt; noch nicht eingebunden |

## Abgeleitete Daten des Projekts

Verortungen, Zuordnungen, Audit-Protokolle und Abrufstatistik: Lizenz **bis zur Lizenzklärung der Ratsdaten nicht festgelegt.** Die TSV-Dateien in `export/` (Audit-Protokolle, Stichproben, Abrufstatistik) enthalten Titel und Vorlagenarten aus den Ratsdaten (Lizenz ungeklärt) und Namen von Quartieren und Stadtbezirken (Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0); eine Kopie dieser Datei liegt daneben. Vorschlag (Entwurf): CC BY 4.0 mit der Namensnennung der Quellen; ausgenommen bleiben die Bebauungspläne (unverändert, CC BY-ND 4.0) und Ableitungen aus OpenStreetMap (ODbL 1.0).

## Namensnennung

Auf jeder Seite und in jedem Export, auch wo die Lizenz sie nicht verlangt:

- „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0“
- Bebauungspläne: „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0“
- Ratsdaten: „Quelle: Stadt Wuppertal, Ratsinformationssystem (OParl-API)“ mit Link zum Original
