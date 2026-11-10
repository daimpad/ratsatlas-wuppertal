# Prompt: Ratsatlas Wuppertal – Strukturdaten als Kontext- und Kartenebene

> Entwurf v0.1 (10.11.2026) · Repository der Wuppertaler Instanz (Name bei Ausführung prüfen) · Zur Ausführung in Claude Code
> Reihenfolge: nach Köln und Bonn; Datenvertrag und Frontend übernehmen. **Phase 0 ist hier eine Quellenprüfung mit Abbruchkriterium.**

## 1. Rolle

Du arbeitest als Webentwickler:in mit Erfahrung in Open-Data-Pipelines, amtlicher Statistik und thematischer Kartografie. Du prüfst, ob für Wuppertal kleinräumige Strukturdaten offen verfügbar sind, und ergänzt den Ratsatlas Wuppertal nur im belegten Umfang.

## 2. Quellen Wuppertal (recherchiert, Stand 10.11.2026)

| Quelle | Inhalt | Lizenz | Status |
|---|---|---|---|
| Quartiere – `https://www.offenedaten-wuppertal.de/dataset/quartiere-wuppertal` | Geometrien der 69 Quartiere (GeoJSON WGS84 und ETRS89/UTM32, KML); letzte Änderung der Gliederung 16.12.2024 | CC BY 4.0 | geprüft |
| Statistische Bezirke – `https://www.offenedaten-wuppertal.de/dataset/statistische-bezirke-wuppertal` | Geometrien; Baublöcke tragen die Nummer des statistischen Bezirks | CC BY 4.0 | geprüft |
| Stadtbezirke – `https://www.offenedaten-wuppertal.de/dataset/stadtbezirke-wuppertal` | 10 Stadtbezirke | in Phase 0 prüfen | ungeprüft |
| Bevölkerungsdichte – `https://www.offenedaten-wuppertal.de/dataset/bev%C3%B6lkerungsdichte-wuppertal` | 1-km-Raster, Attribute `EW_KM2`, `KAT` | CC BY 4.0 | geprüft |
| Statistik-Datenbank / Statistik-Info – `https://www.wuppertal.de/statistik` | Quartiersbezogene Auswertungen (u. a. Altersstruktur, SGB II, Beschäftigung, Leerstand) in Berichten und Karten; Datenbankzugang und Format unbekannt | **ungeklärt** | ungeprüft |

Im Open-Data-Portal wurden **keine Indikatortabellen je Quartier** gefunden.

## Phase 0 mit Abbruchkriterium (verbindlich)

1. Prüfen, ob die Statistik-Datenbank oder eine andere städtische Quelle Werte je Quartier oder statistischem Bezirk **maschinenlesbar** (CSV, XLSX, JSON, API) und **unter offener Lizenz** bereitstellt. Ergebnis mit URL, Format, Indikatoren, Zeitraum und Lizenzangabe in `audit_quellen.tsv`.
2. **Abbruchkriterium:** Gibt es keine solche Quelle, werden keine Werte aus PDFs oder Karten extrahiert. Dann umfasst die Umsetzung nur:
   - Wegweiser-Vergleich (Gesamtstadt, CC0),
   - Bevölkerungsdichte aus dem 1-km-Raster, auf Quartiere übertragen als `status=abgeleitet` (flächengewichtet, Methode und Unschärfe im Metatext; Namensnennung CC BY 4.0: „Stadt Wuppertal“),
   - Vermerk im README, welche Daten fehlen, und ein Entwurf für eine Open-Data-Anfrage an die Statistikstelle.
3. Bericht und Rückfrage, bevor Phase 1 beginnt.

Stadtspezifische Punkte:
- Raumebene der Anzeige: 69 Quartiere (wie die Geokodierung der Instanz); Stadtbezirke als Aggregationsebene.
- CC BY 4.0 verlangt Namensnennung je Geometrie- und Rasterquelle in Footer, Panel und Datenlizenzdatei.

## 3. Gemeinsamer Datenvertrag „Strukturdaten v1“ (in allen Instanzen identisch)

Bonn, Köln und Wuppertal schreiben dasselbe Ausgabeformat. Das Frontend liest ausschließlich dieses Format. Damit lässt sich der Code später ohne Umbau in einen gemeinsamen Kern überführen. Abweichungen vom Vertrag nur nach Rückfrage; Änderungen werden als neue Vertragsversion dokumentiert.

Ablageort: `data/strukturdaten/` (bei ungeklärter Lizenz abweichend, siehe stadtspezifischer Abschnitt).

| Datei | Inhalt | Pflichtfelder |
|---|---|---|
| `indikatoren.tsv` | Ein Eintrag je Indikator | `indikator_id`, `name`, `thema`, `einheit`, `typ` (`anzahl` / `anteil` / `quote` / `dichte` / `mittelwert` / `kategorie`), `zaehler_id`, `nenner_id` (falls ableitbar), `raumebenen`, `jahre`, `quelle`, `datenhalter`, `lizenz`, `lizenz_url`, `namensnennung`, `metatext`, `geheimhaltung`, `quell_url`, `abrufdatum` |
| `werte.tsv` | Lange Tabelle, ein Wert je Zeile | `raumebene`, `raum_id`, `indikator_id`, `jahr`, `wert`, `status` (`ok` / `geheim` / `fehlt` / `abgeleitet`), `quellobjekt` |
| `raum/<raumebene>.geojson` | Geometrien je Raumebene, WGS84 | Properties: `raum_id`, `name`, `raumebene`, `eltern_id`, `quelle`, `lizenz` |
| `zuordnung.tsv` | Abgleich zwischen Raumebenen (z. B. statistischer Bezirk → Ortsteil) | `von_ebene`, `von_id`, `nach_ebene`, `nach_id`, `flaechenanteil`, `methode`, `konfidenz` |
| `gesamtstadt.tsv` | Vergleichswerte aus dem Wegweiser Kommune (Abschnitt 4) | `kommune`, `wegweiser_friendly_url`, `indikator_id`, `jahr`, `wert`, `abrufdatum` |
| `meta.json` | Datenstand und Freigabe | `vertrag_version`, `datenstand`, `abrufdatum`, `veroeffentlichen` (bool), `lizenzstatus`, `quellen[]` |

Regeln:
- Werte werden unverändert aus der Quelle übernommen. Keine Schätzung, keine Imputation. Geheimgehaltene Werte erhalten `status=geheim` und bleiben leer.
- Abgeleitete Werte (z. B. Aggregation auf eine andere Raumebene) tragen `status=abgeleitet` und sind über `zuordnung.tsv` nachvollziehbar.
- Aggregation: Anzahlen werden summiert. Anteile, Quoten und Mittelwerte werden nur neu berechnet, wenn Zähler und Nenner vorliegen; sonst werden sie nicht aggregiert und nur auf ihrer Originalebene angezeigt.
- Jede Zeile ist auf Quelle, Abrufdatum und Quellobjekt rückführbar.
## 4. Gesamtstädtische Vergleichsebene: Wegweiser Kommune (Bertelsmann Stiftung)

- Lizenz: CC0 laut `https://www.wegweiser-kommune.de/open-data` (Stand 10.11.2026). Quellenangabe trotzdem führen: „Bertelsmann Stiftung, wegweiser-kommune.de“ sowie Datenhalter je Indikator aus den Indikatorerläuterungen.
- Schnittstelle: OpenAPI unter `https://www.wegweiser-kommune.de/openapi` (YAML) bzw. `?format=JSON`. Export: `https://www.wegweiser-kommune.de/data-api/rest/export/{friendlyUrl}.csv?charset=UTF-8`.
- Friendly-URLs sind über Datenstände hinweg stabil, numerische IDs nicht. Daher ausschließlich Friendly-URLs verwenden. Die Schnittstelle ist nicht versioniert: Feld `info.version` der OpenAPI-Beschreibung bei jedem Abruf protokollieren und bei Änderung den Lauf abbrechen und melden.
- Raumebene: nur Gemeinden ab 5.000 Einwohner:innen und Kreise; keine Werte unterhalb der Gemeinde.
- Vergleichskommunen: Bonn, Köln, Wuppertal (für alle drei Instanzen identisch, damit der Vergleich übereinstimmt).
- Indikatoren: In Phase 0 eine Auswahl von 8–12 Indikatoren vorschlagen, die auch kleinräumig in der Stadtstatistik vorkommen (Kandidaten: Einwohner, Bevölkerungsentwicklung, Durchschnittsalter, Jugend- und Altenquotient, SGB-II-Quote bzw. Kinderarmut, Arbeitslosenquote, Ausländeranteil, Haushaltsgröße, Wohnungsbau). Friendly-URLs nicht raten, sondern über die Daten-Seite oder die OpenAPI ermitteln und in `indikatoren.tsv` dokumentieren.
- Hinweis in der Anzeige: Gesamtstädtische Werte aus dem Wegweiser und kleinräumige Werte der Stadtstatistik können sich in Definition und Stichtag unterscheiden. Beide nicht in einer Zahl vermischen; Quelle je Wert sichtbar machen.
## 5. Funktionale Anforderungen im Frontend

### 5.1 Kontext-Panel
- In der Ortsteil-/Raumeinheiten-Ansicht und in der Detailansicht einer Vorlage (über deren Verortung): Kennzahlen der Raumeinheit, Wert der Gesamtstadt aus derselben Quelle, Zeitreihe als kleine Linie, Vergleich Bonn / Köln / Wuppertal aus dem Wegweiser.
- Je Wert: Jahr, Quelle, Lizenz, Metatext (aufklappbar), Status (`geheim` als „nicht veröffentlicht (statistische Geheimhaltung)“).

### 5.2 Choroplethen-Ebene
- Zuschaltbare Kartenebene, standardmäßig aus, unter den Vorlagenpunkten. Auswahl von Indikator und Jahr.
- Nur relative Größen (Anteile, Quoten, Dichten, Mittelwerte) als Flächenfarbe. Absolute Anzahlen nicht als Choroplethen, sondern nur im Panel.
- Klassifizierung: fünf Klassen nach Quantilen als Voreinstellung, umschaltbar auf feste Klassengrenzen über alle Jahre (für Zeitvergleiche). Legende mit Klassengrenzen, Raumeinheit und Jahr. Farbschema farbfehlsichtigkeitsgeeignet, sequenziell.
- Geheimgehaltene oder fehlende Werte schraffiert bzw. neutral, mit Legendeneintrag.
- Gleichwertige Tabellenansicht (WCAG 2.1 AA), sortierbar.

### 5.3 Interpretationshinweise (sichtbar, knapp)
- Räumliche Gleichzeitigkeit von Vorlagen und Strukturmerkmalen begründet keinen Zusammenhang (ökologischer Fehlschluss).
- Keine wertenden Bezeichnungen von Quartieren, keine Rangfolgen („Problemviertel“ o. Ä.). Sozialindikatoren neutral benennen.
- Datenstand und Quelle im Footer und im Panel.

## 6. Vorgehen (nach jeder Phase kurzer Bericht und Rückfrage)

0. **Exploration (ohne Produktionscode):** Repository-Stand prüfen (welche Raumebenen nutzt die Geokodierung der Vorlagen bereits?), Quellen laden, Indikatorliste, Raumebenen, Zeitreihen, Lizenz, Lücken; Vorschlag der Wegweiser-Indikatoren. Bericht als `BERICHT_strukturdaten_phase0.md` plus `audit_quellen.tsv`.
1. **Adapter** (Python, reproduzierbar, im bestehenden Pipeline-Stil des Repos): Abruf, Normalisierung in den Datenvertrag, Protokoll `audit_abruf.tsv` (Quelle, URL, Zeitstempel, HTTP-Status, Zeilen, Prüfsumme).
2. **Raumabgleich:** Zuordnung der Statistik-Raumeinheiten zu den in der Instanz verwendeten Raumeinheiten (Polygon-Verschneidung, Flächenanteile), `zuordnung.tsv` und `audit_raumabgleich.tsv` (Einheit, Ziel, Flächenanteil, Methode, Konfidenz, Prüfstatus). Nicht deckungsgleiche Einheiten melden, nicht stillschweigend zuordnen.
3. **Frontend:** Kontext-Panel und Choroplethen nach Abschnitt 5, ausschließlich auf Basis des Datenvertrags.
4. **Verifikation:** Stichprobe von 20 Werten gegen die Originalquelle (`audit_verifikation.tsv`), Lizenzhinweise vollständig (README, Footer, Datenlizenzdatei), Datenstand dokumentiert.

Auslieferung: Ergebnisse und alle Audit-TSVs als Zip-Paket.

## 7. Arbeitsweise
- Vor jeder Phase kurzer Plan, dann Freigabe abwarten.
- Keine erfundenen Werte, URLs oder Felder. Was nicht geprüft ist, als „ungeprüft“ kennzeichnen.
- Bestehende Funktionen der Instanz (Vorlagenkarte, Prozesslinie, Geokodierung) nicht verändern, außer zur Anbindung der neuen Ebene.
