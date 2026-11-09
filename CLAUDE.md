# Prompt: „ratsatlas-wuppertal“ – Ratsinformationen der Stadt Wuppertal räumlich, zeitlich und nach Akteuren erschließen

> Entwurf v0.1 (09.11.2026) · Zur Ausführung in Claude Code · Vorlage: Ratsatlas Bonn (`daimpad/allris-test`, künftig `daimpad/ratsatlas-bonn`); SessionNet-Adapter aus `daimpad/ratsatlas-koeln`
> Vor jeder Phase (Abschnitt 7) legst du einen kurzen Plan vor und wartest auf Freigabe.

## 1. Rolle

Du arbeitest als Webentwickler:in mit Erfahrung in Open-Data-Pipelines und Geodaten **und** als Beauftragte:r für Bürgerbeteiligung. Technische Entscheidungen triffst du so, dass Bürger:innen ohne Verwaltungswissen Ratsinformationen finden, verstehen und einordnen können. Du arbeitest quellentreu: keine erfundenen Inhalte, URLs, Feldnamen oder Zahlen; jede angezeigte Information ist auf ihr Quellobjekt rückführbar. Was du nicht messen konntest, kennzeichnest du als offen.

## 2. Rahmenentscheidungen

| Punkt | Entscheidung |
|---|---|
| Repository | `daimpad/ratsatlas-wuppertal`, öffentlich (Name nach Schema `ratsatlas-<stadt>`; vor Anlage bestätigen lassen) |
| Seitenname | **Ratsatlas Wuppertal** |
| Code-Basis | **Unabhängige Kopie** von `daimpad/allris-test` (kein Fork, eigene Historie, ohne `data/`); **SessionNet-Adapter** und zugehörige Tests aus `daimpad/ratsatlas-koeln` übernehmen und auf Wuppertal einstellen. Herkunft beider Teile (Repo, Commit-Hash) in README und `NOTICE`. Ein gemeinsamer Kern `ratsatlas` ist **nicht** Teil dieses Auftrags; Abweichungen des übernommenen Adapters notierst du so, dass die spätere Zusammenführung möglich bleibt |
| Unverändert | `daimpad/allris-test` und `daimpad/ratsatlas-koeln` werden nur gelesen, nie verändert |
| Gestaltung | wie Ratsatlas Bonn (Glass-Stil, Tokens aus `site/style.css`, Schrift Inter lokal, kontraststarke Violetttöne); Texte und Marke auf Wuppertal umgestellt |
| Räumlicher Umfang | Ganz Wuppertal von Beginn an: 10 Stadtbezirke, 69 Quartiere; kein Pilotgebiet |
| Zeitlicher Umfang | Vorlagen mit `date` ab **01.01.2020**; ältere Vorlagen werden nicht abgerufen bzw. verworfen. Wahlperioden 2020–2025 und 2025–2030 (Kommunalwahlen NRW 13.09.2020 und 14.09.2025) |
| Veröffentlichung | Hauptadresse `https://wuppertal.ratsatlas.de/` (Netcup-Webhosting, Plesk-Git aus Branch `deploy` mit Webhook, `SITE_URL`); Ausweichadresse GitHub Pages `https://daimpad.github.io/ratsatlas-wuppertal/` mit Canonical auf die Hauptadresse |
| Build | ausschließlich GitHub Actions |
| Code-Lizenz | MIT; Daten mit eigener LICENSE-Datei (`data/LICENSE-DATA.md`) |
| Sprachmodelle | zulässig für Ortsextraktion (Stufe C) und Kurzfassungen – mit Kennzeichnung, Konfidenz und Link zum Original |
| Volltexte/PDFs | bis zur Lizenzklärung (Abschnitt 8): Verarbeitung nur lokal und im Workflow-Zwischenspeicher; **keine Zitate, keine Auszüge, keine PDF-Spiegelung**; im Datenpaket nur abgeleitete Verortungen mit Fundstelle als erkanntem Namen und Dokumentteil |
| Datenschutz | keine Verortung von Wohnadressen natürlicher Personen; Anregungen und Beschwerden nach § 24 GO NRW nur auf Quartiers- oder Straßenebene; keine Personennamen aus dem System-Objekt oder aus Dokumenten auf der Seite |
| Auslieferung | Ergebnisse je Phase als Zip-Paket; Audit-Protokolle als TSV |
| Arbeitsweise | diese Datei als `CLAUDE.md`; eigener Skill `.claude/skills/ratsatlas-wuppertal/SKILL.md` (aus dem Bonner Skill abgeleitet) |

## 3. Datenquellen (Stand 09.11.2026 – in Phase 1 verifizieren)

### 3.1 Primärquelle: OParl-API der Stadt Wuppertal (Somacos Session)
- System: `https://oparl.wuppertal.de/oparl/system` – erreichbar; `oparlVersion` 1.1; `vendor` Somacos, Schnittstelle v1.6.1; `created` 24.04.2020
- Body: `https://oparl.wuppertal.de/oparl/bodies/0001` – heißt in der Quelle „Instance 0001“ (Anzeige: „Stadt Wuppertal“); `license` **leer**; `legislativeTerm` und `location` nicht gesetzt
- Listen: `…/bodies/0001/papers`, `/meetings`, `/organizations`, `/people`; 100 Objekte je Seite; Paginierung über `links.next` (`?page=N`)
- Oberfläche: `https://ris.wuppertal.de/` (SessionNet 5.5.1)
- **Stichprobe vom 09.11.2026** (erste Seite, 100 Vorlagen, alle von 2026; dazu einzelne Seitenabrufe):
  - Bestand ca. 24.000–25.000 Vorlagen (Seite 240 gefüllt, Seite 250 leer), absteigend nach Datum bis etwa 2003; Grenze 01.01.2020 liegt geschätzt zwischen Seite 50 und 150 (in Phase 1 messen)
  - `reference` im Schema `VO/NNNN/JJ` (z. B. `VO/1380/26`)
  - `consultation` verweist **direkt** auf `meeting` und `agendaItem` (wie Köln) → Prozesslinie aus einer Quelle; `role` z. B. „Entgegennahme o. B.“
  - `underDirectionOf` bei 75 von 100 gesetzt, verweist auf `organizations/at/<n>`; Gremien liegen unter `organizations/gr/<n>`
  - `paperType` enthält oft die Einreichenden und die Ebene: „Antrag CDU“, „Antrag B90/Grüne BV“, „Gemeinsamer Antrag BV“, „Gemeinsamer Antrag Rat“, „Große Anfrage die Linke“, „Antrag FDP / WfW Rat AU“; daneben „Bericht“, „Beschlussvorlage“, „Antwort auf Anfragen“
  - `location` bei 0 von 100 → **keine Stufe A**
  - kein `mainFile`; Dokumente nur als `auxiliaryFile` (`accessUrl` `…/downloadfiles/a/<n>.pdf`, `downloadUrl` `…/downloadfiles/<n>.pdf`)
  - `keyword` bei 35 von 100
  - Objekt-IDs verwenden `http://`; Abruf über `https://` funktioniert → IDs als Schlüssel unverändert speichern, Abrufe über HTTPS
  - `robots.txt` auf `oparl.wuppertal.de` nicht vorhanden (404)
- Kontakte: Open Data: Amt 402, offenedaten@stadt.wuppertal.de; RIS: 001.13 Ratsbüro (Gremienangelegenheiten 001.1). Die im System-Objekt genannte Person wird nicht veröffentlicht.
- **Abrufrisiko:** Somacos-Kunden lizenzieren OParl gesondert; in Dortmund wurde die Session-Schnittstelle „aus Sicherheitsgründen“ abgeschaltet; Köln sperrte den IP-Bereich eines Projekts nach vielen Abrufen. Daher gilt die Abrufpolitik in 5.1.

### 3.2 Geobasisdaten (Ressort 102 Vermessung, Katasteramt und Geodaten; überwiegend CC BY 4.0)
| Datensatz | Quelle | Lizenz | Verwendung |
|---|---|---|---|
| Stadtbezirke (10) | `offenedaten-wuppertal.de/dataset/stadtbezirke-wuppertal` (GeoJSON WGS84/UTM32, Shape, KML) | prüfen | Filter, Zuordnung Bezirksvertretung |
| Quartiere (69) | `https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Quartiere_EPSG4326_JSON.json` | CC BY 4.0 | Point-in-Polygon, Filter, Gazetteer |
| Statistische Bezirke (48) | `offenedaten-wuppertal.de` (GeoJSON) | prüfen | optional |
| Straßenverzeichnis (ca. 2.160 Straßen, Stand 09/2021, wöchentlich) | `https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/Strassenverzeichnis_CSV.zip` (Felder u. a. STRSCHL, STRNAME, STADTBEZIRK, Hausnummernbereiche) | CC BY 4.0 | Gazetteer Stufe B |
| Georeferenzierte Bestandsadressen | `https://daten.wuppertal.de/Geografie_Geologie_Geodaten/Adressen_EPSG4326_JSON.json` (Straßenschlüssel, Name, Hausnummer, Zusatz, Stadtbezirk, Koordinate; ohne PLZ, ohne Quartier) | CC BY 4.0 | Hauskoordinaten; Straße → Quartier per Point-in-Polygon ableiten |
| Rechtsverbindliche B-Pläne (691, Stand 06/2026) | `https://daten.wuppertal.de/Gesetze_Justiz/rvbBebauungsplanverfahren_EPSG4326_JSON.json` | **CC BY-ND 4.0** (Open.NRW nennt abweichend „Andere geschlossene Lizenz“) | Stufe B über Plannummer; Geometrien unverändert anzeigen |
| Laufende B-Plan-Verfahren (100) | `offenedaten-wuppertal.de/dataset/laufende-bebauungsplanverfahren-wuppertal` | CC BY-ND 4.0 | wie oben |
| Planungs-WMS | `https://maps.wuppertal.de/planung` | nicht angegeben | nur Verweis, nicht einbinden ohne Lizenz |

Namensnennung auf jeder Seite und in jedem Export: „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0“ (B-Pläne: CC BY-ND 4.0). OpenStreetMap (Photon/Nominatim, ODbL) nur nachrangig für Orte ohne Adresse (Plätze, Brücken, Schwebebahnstationen), getrennt gekennzeichnet. Bonner Abhängigkeiten von OParl-Lite (machdenstaat) entfallen; einen Wuppertaler Volltextspiegel gibt es nicht, Politik bei uns ist veraltet.

## 4. Ziel

Eine öffentliche, statisch auslieferbare Webanwendung, die die Wuppertaler Ratsinformationen ab 2020 in drei Dimensionen erschließt – jeweils mit Quellenangabe:

1. **Räumlich (Wo?)** – Karte aller Vorlagen mit Ortsbezug; Filter nach Stadtbezirk und Quartier, wo belegbar auf Straßen-, Adress- oder B-Plan-Ebene.
2. **Zeitlich (Wann? Wo steht das Verfahren?)** – Prozesslinie je Vorlage: Veröffentlichung → Beratungen (Gremium, Datum, TOP, Rolle, Ergebnis wörtlich) → Folgevorlagen (z. B. „Antwort auf Anfragen“ zu „Große Anfrage“). Kommende Sitzungen als offene Stationen.
3. **Akteursbezogen (Wer?)** – federführendes Amt (`underDirectionOf`), befasste Gremien (Rat, Ausschüsse, 10 Bezirksvertretungen), einreichende Fraktionen und Gruppen.

## 5. Funktionale Anforderungen (Abweichungen von Bonn)

### 5.1 Abruf
- SessionNet-Adapter aus `ratsatlas-koeln` mit Wuppertaler Konfiguration (Endpunkt, Body `0001`, Stadtname); Ausgabe im **unveränderten Bonner Datenmodell**, damit Frontend und Export möglichst unverändert bleiben
- Zeitfilter: Abruf der Vorlagenliste bis zur ersten Seite, deren Vorlagen alle vor 2020 liegen; vorher messen, ob die Liste verlässlich absteigend nach `date` sortiert ist, sonst vollständig paginieren und filtern
- Abrufpolitik: 1 Verbindung, mindestens 1–2 s Abstand, nächtliches Zeitfenster, inkrementell über `modified_since` (Unterstützung in Phase 1 messen), Backoff bis zu mehreren Stunden, User-Agent mit Projektadresse und Kontakt, Zustandsdatei und Rohdaten-Cache; **erster Vollabruf erst nach Information der Stadt** (Ratsbüro und offenedaten@stadt.wuppertal.de)
- Fällt der Abruf aus, wird der letzte gültige Datenstand ausgeliefert und als solcher angezeigt
- **Änderungsprotokoll:** Das Lokalportal njuuz bemängelt nachgelieferte oder ersetzte Drucksachen ohne Versionierung. Die Pipeline vergleicht je Lauf `modified`, Dateiliste (`auxiliaryFile`) und Beratungsfolge mit dem Vorstand und schreibt Änderungen nach `audit_aenderungen.tsv` (Vorlage, Feld, alt, neu, Zeitpunkt). Auf der Vorgangsseite: „Unterlagen geändert am …“

### 5.2 Geokodierung
| Stufe | Methode in Wuppertal | Konfidenz |
|---|---|---|
| A | entfällt (kein `location` in der Quelle); falls Phase 1 doch Treffer findet, wie in Bonn übernehmen | hoch |
| B | Adressabgleich Straße + Hausnummer gegen Bestandsadressen → Punkt; Straße ohne Hausnummer → Straßenverlauf aus Adresspunkten bzw. Quartier(e); Quartiers-, Stadtbezirks- und historische Stadtteilnamen; B-Plan-Nummern; Point-in-Polygon gegen die 69 Quartiere | mittel (Adresse: hoch) |
| C | LLM-Extraktion aus `auxiliaryFile`-Volltext nur ohne B-Treffer, Verifikation gegen B | niedrig bis mittel, gekennzeichnet |

Zusätzlich schwache Evidenz `district_from_committee`: nur eine Bezirksvertretung berät bzw. `paperType` endet auf „BV“ und die beratende BV ist eindeutig → Stadtbezirk. Jede Verortung trägt `method`, `confidence`, `evidence`, `source_object`, `geometry_level`.

**Wuppertaler Eigenheiten bei Ortsnamen:**
- Teilzeichenketten: „Barmen“ ⊂ „Oberbarmen“, „Elberfeld“ ⊂ „Elberfeld-West“ → Abgleich nach dem Prinzip „längster Treffer zuerst“ mit Wortgrenzen
- Doppelnamen auch in Teilen: „Langerfeld-Beyenburg“ (Langerfeld, Beyenburg), „Uellendahl-Katernberg“ (Uellendahl, Katernberg)
- Ausschlüsse: Gremien- und Ortsnamen ohne Raumbezug der Vorlage (z. B. „BV Barmen“, „Rathaus Barmen“, Sitzungsort) sowie Eigennamen wie „Barmer“ (Krankenkasse) – Ausschlussliste in Phase 1 an echten Titeln erweitern
- Straßennamen amtlich abgekürzt („…str.“ statt „…straße“) → Normalisierung beider Seiten, Varianten mit und ohne Bindestrich
- Straßenverzeichnis und Adressen kennen nur den Stadtbezirk → Straße-zu-Quartier-Tabelle aus Adresspunkten ableiten (Straßen über mehrere Quartiere als Mehrfachzuordnung)
- Objekte mit Stadtbezug ohne Adresse (Schwebebahn, Nordbahntrasse, Döppersberg, Talsperren) als kleine kuratierte Ortsliste mit Quelle

### 5.3 Akteure
- Federführung: `underDirectionOf` (Organisation `at/<n>`, Name aus `organizations`); sonst Kopf der Verwaltungsvorlage im PDF → Abgleich mit der Ämterliste aus `organizations/at`; Methode und Fundstelle ausweisen
- Einreichende: aus `paperType` zerlegen in Art (Antrag, Große Anfrage, Gemeinsamer Antrag …), Einreichende (Fraktion/Gruppe, z. B. CDU, SPD, B90/Grüne, die Linke, AfD, FDP / WfW) und Ebene (Rat, BV, weitere Kürzel wie „AU“ in Phase 1 klären); datumsabhängig je Wahlperiode; als „aus Vorlagenart abgeleitet“ kennzeichnen. „Gemeinsamer Antrag“ ohne Namen: Einreichende offen lassen
- Beratungsrollen (z. B. „Entgegennahme o. B.“) wörtlich anzeigen und im Glossar erklären

### 5.4 Funktionsumfang der ersten Auslieferung
Übernommen und auf Wuppertal umgestellt: Karte, Liste, Vorgang mit Prozesslinie, Gebiete (Stadtbezirke/Quartiere), Startansicht ganz Wuppertal mit anklickbaren Stadtbezirken, Suche, Verstehen (Begriffe, Verlässlichkeit), Datenpaket, Feeds, Datenschutz, Quellen- und Lizenzhinweise, graue Kartenkacheln für das Wuppertaler Stadtgebiet.
**Deaktiviert, nicht gelöscht** (per Konfiguration abschaltbar, spätere Freigabe einzeln): Bonn-spezifische Zusatzthemen wie Haushalt, Baustellen, Wahlen/Kandidaturen, Themenseiten, Ratsassistent (Chat) – endgültige Liste aus der Inventur in Phase 0.

## 6. Verbote

- keine Änderungen an `daimpad/allris-test` und `daimpad/ratsatlas-koeln`
- keine Bonner oder Kölner Daten (`data/`) übernehmen
- keine Zugangsdaten im Repository; Netcup-Zugang nur manuell durch den Auftraggeber
- keine Volltexte, Zitate oder PDFs im Repository, auf der Seite oder im Datenpaket bis zur Lizenzklärung
- keine Bearbeitung der B-Plan-Geometrien (CC BY-ND 4.0)
- kein Scraping von `ris.wuppertal.de`, solange die OParl-Schnittstelle verfügbar ist

## 7. Vorgehen in Phasen (nach jeder Phase Bericht und Freigabe)

0. **Kopie und Inventur**
   - `gh auth status`; Repo-Namen bestätigen lassen; `daimpad/ratsatlas-wuppertal` anlegen; Code aus `allris-test` **ohne** `data/`, ohne Historie übernehmen (`git archive`), erster Commit „Ausgangsstand aus allris-test @<Hash>“
   - SessionNet-Adapter, Konfiguration und Tests aus `ratsatlas-koeln` in eigenem Commit übernehmen („Adapter aus ratsatlas-koeln @<Hash>“); ist dort noch kein Adapter vorhanden, meldest du das und schlägst den Aufbau nach dessen Vorbild vor
   - `inventur_module.tsv`: je Datei/Modul Einordnung *generisch* / *Bonn-spezifisch, anpassen* / *Köln-spezifisch, anpassen* / *Zusatzthema, deaktivieren* / *entfernen*, mit Begründung
   - alle Fundstellen von „Bonn“, „Köln“, Bonner und Kölner URLs, `SITE_URL`, OParl-Lite, Orts- und Bezirksnamen auflisten
   - Ergebnis: Inventurbericht und Plan; noch keine Wuppertaler Logik
1. **Exploration Wuppertal (ohne Produktionscode, Skripte unter `explore/`)**
   - API messen (gedrosselt): Gesamtzahl `papers`, Seite mit Datumsgrenze 2020, Sortierung, `modified_since`, Ende von `links.next`; `meetings`, `organizations` (Präfixe `gr`, `at`, weitere), `people`
   - Stichprobe ≥ 500 Vorlagen 2020–2026: Abdeckung `underDirectionOf`, `originator*`, `auxiliaryFile`, `location`, `keyword`, `consultation.meeting/agendaItem`, `agendaItem.result`; Listen aller `paperType`, Beratungsrollen und `organizationType`
   - Zerlegung `paperType` → Art/Einreichende/Ebene: Regeltabelle und Abdeckungsquote
   - 100 Verwaltungsvorlagen ohne `underDirectionOf`: Erkennungsquote des Amts im PDF-Kopf
   - Geodaten laden: Feldnamen, Koordinatensystem, Stand; Straße-zu-Quartier-Tabelle; B-Plan-Nummernschema; Ausschlussliste Ortsnamen an 300 Titeln testen
   - Bericht wie Bonner `BERICHT_phase0.md`: Anteil Stufe B/C (Schätzung), Datenqualität, Lücken, Risiken
2. **Datenpipeline**: Adapter mit Zeitfilter, inkrementeller Abruf, Normalisierung ins Bonner Modell, Änderungsprotokoll, Abrufstatistik als TSV
3. **Geokodierung** nach 5.2 mit `audit_geokodierung.tsv`; manuelle Prüfung von 50 Vorlagen je Methode, Präzision im Bericht
4. **Frontend**: Texte, Marke, Startansicht, Gebiete, Glossar (inkl. Wuppertaler Beratungsrollen und Vorlagenarten) auf Wuppertal; Kartenkacheln für Wuppertal; WCAG-2.1-AA-Prüfung (axe, Tastatur, Kontrast)
5. **Repository und Deployment**: README (Ziel, Herkunft aus allris-test und ratsatlas-koeln, Quellen, Lizenzen, Grenzen, Datenstand), LICENSE, `data/LICENSE-DATA.md`, NOTICE, CONTRIBUTING, Issue-Vorlagen; Workflows (täglicher Lauf, `deploy`-Branch ohne Historie, Pages-Ausweichadresse); Plesk-Checkliste für den Auftraggeber
6. **Verifikation**: Stichprobe gegen `ris.wuppertal.de`, Linkprüfung, Lizenz- und Datenschutzhinweise vollständig, Audit-TSVs im Zip-Paket

## 8. Offene Punkte

- **Lizenz** der OParl-Daten und PDFs: Body-Feld `license` leer, kein OParl-Datensatz im Open-Data-Portal → schriftliche Anfrage an Ratsbüro (001.13) und offenedaten@stadt.wuppertal.de (Lizenz, abgeleitete Daten, Abrufrate, Abrufe aus GitHub-Actions-IP-Bereichen); Argument: Open-Data-Dienstanweisung vom 18.10.2019 und OParl-Pilot Open.NRW 2017; bis dahin Namensnennung immer angeben
- Bedeutung der Kürzel in `paperType` (z. B. „AU“) und vollständige Liste der Fraktionen und Gruppen je Wahlperiode
- Abdeckung `underDirectionOf` über 2020–2026 und Qualität der PDF-Kopf-Erkennung
- Lizenzwiderspruch bei B-Plänen (CC BY-ND 4.0 vs. „Andere geschlossene Lizenz“)
- Umgang mit nicht öffentlichen TOPs, zurückgezogenen und nachträglich ersetzten Vorlagen
- Aufnahme als Kachel „in Vorbereitung“ auf der Landingpage `ratsatlas.de` (`staedte.json`, separates Repo)
- welche Bonner Zusatzthemen für Wuppertal später sinnvoll sind

## 9. Entscheidungen

- 09.11.2026 (Phase 0): Das Repository `daimpad/ratsatlas-wuppertal` bestand bereits; Kopie aus `daimpad/allris-test` @ `52fe9ca` ohne `data/` und, wie bei Köln, ohne die Bonner Berichts-, Phasen-, Test- und Evaluationsverzeichnisse. Adapter aus `daimpad/ratsatlas-koeln` @ `d609111`. Herkunft in `NOTICE`.
- 09.11.2026: Die Bonner Workflows liegen in `.github/workflows-inaktiv/`; `static.yml` startet nur manuell, bis Phase 5.
- 09.11.2026: Für Phase 0 genügt der Pull Request; kein eigenes Zip-Paket.
- 09.11.2026: Pull Requests dieses Projekts führt Claude selbst zusammen, sobald sie grün sind (keine Konflikte, keine fehlgeschlagene Prüfung). Solange alle Workflows abgeschaltet sind, prüft keine CI die Tests.
- 09.11.2026 (Abschluss Phase 0, `inventur/BERICHT_phase0.md` Abschnitt 5): Alle Bonner Zusatzthemen bleiben abgeschaltet (Haushalt, Baustellen und Mängelmelder, Wahlen, Themenseiten, Ratsassistent, Soll-Modell mit „Prozesse“ und „Mitmachen“, Kennzahlen je Gebiet, Einfache Sprache, Kurzfassungen, Gremienbesetzung). Die Vorgangsseiten (`pipeline/vorgangsseiten.py`) gehören zum Kern. Das Bonner Vorschaubild `site/og-image.jpg` wird in Phase 4 durch ein Wuppertaler Bild ersetzt und bis dahin nicht ausgeliefert.
- 09.11.2026: Phase 1 freigegeben. Messungen gegen `oparl.wuppertal.de` und das Laden der Geodaten nur gestuft nach `explore/STUFEN.md`, jede Stufe nach eigener Freigabe.
- 09.11.2026: Reihenfolge abweichend von Köln: erst die gestuften Messungen (`explore/STUFEN.md`, je Stufe eigene Freigabe), danach die Anfrage an die Stadt (`explore/ANFRAGE_stadt_wuppertal.md`) mit den gemessenen Zahlen. Die Messwerkzeuge haben dafür eine eigene Freigabe statt `RATSATLAS_STADT_INFORMIERT`; der regelmäßige Abruf (`pipeline/`) bleibt bis nach der Information der Stadt gesperrt (5.1). Kontakt im User-Agent: `contact@nozilla.de`.
