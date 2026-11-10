# Strukturdaten Wuppertal – Bericht Phase 0 (Quellenprüfung)

## 1. Stand
- 10.11.2026, Auftrag `PROMPT_strukturdaten_v0.1.md`, Entscheidung 10.11.2026 in `CLAUDE.md` 9
- Abrufe nur über `abruf_struktur.py`, tagsüber, 1 Verbindung, mindestens 2 s Abstand; Protokoll `audit_abruf.tsv` (Z. = Dateizeile mit Kopfzeile)
- 26 Anfragen: offenedaten-wuppertal.de 9, daten.wuppertal.de 6 (5 HEAD, 1 CSV mit 1,7 kB), www.wuppertal.de 3 (davon 2 dbstatistik), wegweiser-kommune.de 8; daten.wuppertal.de und dbstatistik nennt `CLAUDE.md` 9 nicht → Frage 5
- kein 429/5xx, keine Sperre (403 von www.wuppertal.de sperrt erst seit der Nachbesserung des Werkzeugs; keine weiteren Anfragen dorthin); keine Anfrage an oparl/ris; keine Geometrien geladen; Rohdaten nur in `explore/_cache/strukturdaten/`
- Quellenliste: `audit_quellen.tsv` (Bonn, Köln und KECK/Portal aus der Vorlage, nicht erneut geprüft)

## 2. Abbruchkriterium: greift vorläufig (Open-Data-Katalog geprüft; Statistik-Info und dbstatistik nicht prüfbar, 403)
- Keine geprüfte Quelle liefert Bevölkerungs- oder Sozialwerte je Quartier oder statistischem Bezirk maschinenlesbar und offen lizenziert
- Grundlage ist der vollständige Katalog: 124 Datensätze (Z. 17). Statistiktabellen (Team Statistik und Wahlen) nur für die Gesamtstadt: Gebäude-CSV am Inhalt geprüft (Z. 21: keine Raumspalte), übrige vier laut Katalogbeschreibung
- Statistik-Info und Statistik-Datenbank antworten mit HTTP 403 (Z. 18–20; Herkunft ungeprüft, Kopfzeilen nicht gespeichert); nicht umgangen. Laut Katalog ist die Statistik-Datenbank ein HTML-Abfragetool (bau1 mit Verteilung auf Stadtbezirke); Statistik-Info ist im Katalog nicht verzeichnet, Format ungeprüft. Endgültig erst nach Prüfung von Hand oder Antwort der Stadt (Frage 2)
- Grenzfälle (kleinräumig, offen, aber keine Bevölkerungs- oder Sozialwerte; Z. 17, 22, 23) → Frage 1:
  - ALKIS-Nutzungsarten pro Baublock (CSV, CC BY 4.0, 2012–2026): nur Flächennutzung
  - Wohn- und Nichtwohngebäude-Baujahre (Adresspunkte, CSV/GeoJSON, CC BY 4.0): auf Quartiere aggregierbar
  - Wahlergebnisse 2020 je Stimmbezirk und Stadtbezirk (CSV, CC BY 4.0); Stimmbezirke laut Katalog 2025 neu zugeschnitten
- Ausgeschlossen: Wohnlagen (Adressen und Polygone, dl-by-de/2.0), wertende Klassifikation (Auftrag 5.3)
- Es werden keine Werte aus PDFs oder Karten entnommen

## 3. Wuppertaler Quellen
| Quelle | Raumebene | Format | Lizenz | Status | Beleg |
|---|---|---|---|---|---|
| Quartiere (Geometrie) | 69 Quartiere | GeoJSON 4326/25832, KML, Shape | CC BY 4.0 | nutzbar, keine Werte | Z. 5, 8, 25 |
| Stadtbezirke (Geometrie) | 10 Stadtbezirke | wie oben | CC BY 4.0 (neu belegt) | nutzbar, keine Werte | Z. 17, 26 |
| Statistische Bezirke (Geometrie) | 48 stat. Bezirke | wie oben | CC BY 4.0 | nutzbar, keine Werte | Z. 17, 27 |
| Bevölkerungsdichte | 1-km-Raster (220 Zellen) | wie oben | CC BY 4.0 | nutzbar, Stichtag ungeprüft | Z. 17, 24 |
| ALKIS-Nutzung pro Baublock | Baublock → stat. Bezirk exakt | CSV (zip) | CC BY 4.0 | nutzbar, nur Fläche | Z. 22, 23 |
| Statistiktabellen | Gesamtstadt | CSV, XLS | CC BY 4.0 | nur Gesamtstadt | Z. 17, 21 |
| Gebäude-Baujahre (Wohn-, Nichtwohngebäude) | Adresspunkt | CSV, GeoJSON | CC BY 4.0 | Grenzfall, nur Gebäude | Z. 17 |
| Wahlergebnisse 2020 | Stimm-, Wahl-, Stadtbezirke | CSV | CC BY 4.0 | Grenzfall, keine Strukturdaten | Z. 17 |
| Wohnlagen | Polygon, Adresspunkt | GeoJSON, CSV | dl-by-de/2.0 | ausgeschlossen (wertend) | Z. 17 |
| Statistik-Datenbank (dbstatistik) | höchstens Stadtbezirke belegt (bau1) | HTML | ungeprüft | 403 | Z. 17 (Katalog), Z. 19, 20 (403) |
| Statistik-Info | ungeprüft | ungeprüft | ungeprüft | 403, nicht im Katalog | Z. 18 |

## 4. Raumebenen im Repo
- Geokodierung: `location.level` = strasse / ortsteil / stadtbezirk (`pipeline/build.py` Z. 41); Ortsteil-Ebene = 69 Quartiere, Bezirksebene = 10 Stadtbezirke (`pipeline/config.py` Z. 32–37)
- Die Geodateien fehlen noch (`data/` nicht vorhanden; sie entstehen nach Messstufe G). `geocode.py` enthält noch die Bonner Namenslogik (Phase 3)
- Statistische Bezirke werden im Code nicht genutzt; eine Zuordnung stat. Bezirk → Quartier gibt es nicht
- `kontext.py` (Bonner Zusatzthema, aus) taugt als Muster (Raster → Gebiet, Meta je Kennzahl), aber nicht als Format; der Vertrag ersetzt `kontext.json`
- Schalter: neuer Schlüssel `strukturdaten: False` in `config.ZUSATZTHEMEN`, zusätzlich `meta.json.veroeffentlichen` als zweite Sperre

## 5. Vorschlag Wegweiser-Indikatoren (12; Friendly-URLs aus `indicator/list`, Z. 6)
| Name | Friendly-URL | Einheit | Datenhalter | Jahre | auch kleinräumig? |
|---|---|---|---|---|---|
| Bevölkerung | `bevoelkerung` | Anzahl | Stat. Ämter der Länder | 2006–2023 | ungeprüft |
| Bevölkerungsentwicklung 5 J. | `bevoelkerungsentwicklung-ueber-die-letzten-5-jahre` | % | Stat. Ämter, ZEFIR | 2016–2023 | ungeprüft |
| Durchschnittsalter | `durchschnittsalter` | Jahre | Stat. Ämter, ZEFIR | 2006–2023 | ungeprüft |
| Jugendquotient | `jugendquotient` | u20 je 100 der AG 20–64 | Stat. Ämter, ZEFIR | 2006–2023 | ungeprüft |
| Altenquotient | `altenquotient` | ab 65 je 100 der AG 20–64 | Stat. Ämter, ZEFIR | 2006–2023 | ungeprüft |
| SGB II-Quote | `sgb-ii-quote` | % | Stat. Ämter, BA, ZEFIR | 2006–2023 | ungeprüft |
| Kinderarmut | `kinderarmut` | % | Stat. Ämter, BA, ZEFIR | 2006–2023 | ungeprüft |
| Arbeitslose an den SvB | `arbeitslose-an-den-svb` | % | BA, ZEFIR | 2007–2023 | ungeprüft; ≠ amtliche Quote |
| Anteil Ausländer:innen | `auslaenderanteil` | % | Stat. Ämter, ZEFIR | 2006–2023 | ungeprüft |
| Einpersonen-Haushalte | `einpersonen-haushalte` | % | Nexiga GmbH, ZEFIR | 2006–2022 | ungeprüft |
| Wohnfläche pro Person | `wohnflaeche-pro-person` | m² | Stat. Ämter, ZEFIR | 2006–2023 | ungeprüft |
| Einwohner:innendichte | `einwohnerdichte` | EW je ha | Stat. Ämter, ZEFIR | 2006–2023 | bedingt: Raster EW_KM2 (je km²) |
- Kommunen: `wuppertal`, `bonn`, `koeln` (Z. 11–13). „Haushaltsgröße“ und „Wohnungsbau“ haben keinen direkten Indikator; als Ersatz dienen `einpersonen-haushalte` und `wohnflaeche-pro-person` (Alternative für Wohnungsbau: Frage 3)
- Lizenz CC0 1.0 (Z. 2, 14); `info.version` 3.12.0 (Z. 3), Datenstand 2026-10-15T08:45:18.099083Z-ec57fa (Z. 16)

## 6. Lücken und Risiken
- Statistik-Info und dbstatistik: Inhalt, Raumebene und Lizenz bleiben offen, solange niemand von Hand prüft oder die Stadt antwortet
- Bevölkerungsdichte: Stichtag von EW_KM2 fehlt in den Metadaten. 220 Zellen sind für 69 Quartiere grob, und die Flächengewichtung unterstellt eine Gleichverteilung (Wald, Talsperren) → nur `status=abgeleitet`, mit Unschärfe im Metatext
- Wegweiser: Schnittstelle unversioniert; die Export-friendlyUrl ist in OpenAPI und Open-Data-Seite nur beschreibend mit Beispiel dokumentiert, ohne formale Grammatik; CSV mit Kopf und Fuß (`raw=true` laut OpenAPI, nicht erprobt); Ist-Daten nur bis 2023
- Unterschiedliche Definitionen: `arbeitslose-an-den-svb` ist nicht die amtliche Quote; Dichte je ha (Wegweiser) gegenüber je km² (Raster) → nicht vermischen
- Quartiere sind keine strenge Obergruppe der Baublöcke → Baublockwerte nur näherungsweise auf Quartiere (`zuordnung.tsv` mit Methode und Konfidenz)
- `last-modified` 07.11.2026 bei allen abgefragten Dateien unter Infrastruktur_Bauen_Wohnen (Z. 21, 24–27): vermutlich Neuerzeugung, nicht Datenstand; ALKIS 2026: 10.06.2026 (Z. 22)
- Katalog-API: `package_search` liefert 404; jeder Aufruf wird per 302 auf `&page=0` umgeleitet und zählt doppelt → `&page=0` gleich mitgeben

## 7. Vorgeschlagener Umfang Phase 1 (bei greifendem Abbruchkriterium)
- Adapter und Frontend erst, wenn Köln und Bonn den Vertrag „Strukturdaten v1“ umgesetzt haben (CLAUDE.md 9)
- Wegweiser-Vergleich Bonn/Köln/Wuppertal für die 12 Indikatoren → `gesamtstadt.tsv`, `indikatoren.tsv`, `meta.json`
- Bevölkerungsdichte: 1-km-Raster flächengewichtet auf 69 Quartiere (und 10 Stadtbezirke), `status=abgeleitet`, `zuordnung.tsv`; Namensnennung „Stadt Wuppertal“, CC BY 4.0
- README-Vermerk, welche kleinräumigen Daten fehlen
- Entwurf einer Open-Data-Anfrage an die Statistikstelle (wird in Phase 1 geschrieben, nicht jetzt)
- Schalter `strukturdaten` in `ZUSATZTHEMEN`, standardmäßig aus

## 8. Offene Fragen an den Auftraggeber
1. Sollen Grenzfälle als optionale Indikatoren gelten: ALKIS-Nutzung pro Baublock (z. B. Anteil Wohnbau- oder Grünfläche je stat. Bezirk), Gebäude-Baujahre je Quartier, Wahlergebnisse? Dann wäre das Kriterium formal nicht ganz erfüllt
2. Prüfen Sie Statistik-Info und die Statistik-Datenbank von Hand im Browser, oder geht die Frage gleich in die Open-Data-Anfrage (statistik@stadt.wuppertal.de, Funktionsadresse laut Katalog)? Und soll sie getrennt von der OParl-Anfrage oder gemeinsam mit ihr gestellt werden?
3. Bestätigen Sie die 12 Indikatoren, auch `einpersonen-haushalte` mit einem privaten Datenhalter (Nexiga GmbH)? Für „Wohnungsbau“ statt oder neben `wohnflaeche-pro-person`: `wohnungen-in-ein-zweifamilienhaeusern` (%, Stat. Ämter, ZEFIR, 2006–2023; Z. 6), passend zur Spalte `WOHNGEBAEUDE_EinUndZweifamilienhaus_WOHNUNGEN` der Gebäude-CSV (Z. 21)
4. Bevölkerungsdichte: nur abgeleitet je Quartier zeigen, oder zusätzlich das Raster unverändert als eigene Ebene?
5. Abgefragt wurden auch daten.wuppertal.de (nur HEAD oder Dateien < 2 MB) und www.wuppertal.de/dbstatistik. Soll der Eintrag in `CLAUDE.md` 9 so ergänzt werden?
