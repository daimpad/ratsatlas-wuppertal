<p align="center"><img src="site/favicon.svg" width="64" height="64" alt=""></p>

<h1 align="center">Ratsatlas Wuppertal</h1>

<p align="center"><strong>Womit befassen sich Rat, Ausschüsse und Bezirksvertretungen der Stadt Wuppertal – wo, wann und wer ist beteiligt?</strong></p>

<p align="center">
  <a href="https://github.com/daimpad/ratsatlas-wuppertal/actions/workflows/tests.yml"><img src="https://github.com/daimpad/ratsatlas-wuppertal/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Code-MIT-2563eb" alt="Code: MIT"></a>
  <a href="data/LICENSE-DATA.md"><img src="https://img.shields.io/badge/Daten-siehe%20LICENSE--DATA-6b7280" alt="Daten: siehe data/LICENSE-DATA.md"></a>
</p>

> **Stand 10.11.2026: in Vorbereitung.** Es gibt noch keine Ratsdaten. Die Veröffentlichung ist eingerichtet (`.github/workflows/pages.yml`), Daten folgen nach den Messungen; bis dahin zeigt die Seite „Daten nicht verfügbar“ und ist nicht indexiert (`noindex`). Phase 1 (Messungen an der Schnittstelle der Stadt) läuft; der regelmäßige Abruf bleibt gesperrt, bis die Stadt informiert ist.

Der Ratsatlas Wuppertal soll die öffentlichen Vorlagen aus dem Ratsinformationssystem der Stadt Wuppertal ab 2020 auf einer Karte, einer Zeitleiste und als Liste zeigen – für Bürgerinnen und Bürger ohne Verwaltungswissen. Jede Angabe führt zum Original; was abgeleitet ist, ist gekennzeichnet.

**Seite (Veröffentlichung eingerichtet, Daten folgen):** https://wuppertal.ratsatlas.de/ · Ausweichadresse: https://daimpad.github.io/ratsatlas-wuppertal/ · **Technik:** [TECHNIK.md](TECHNIK.md) (noch Bonner Stand, Überarbeitung in Phase 5)

## Ziel

| Frage | Was die Seite zeigen soll |
|---|---|
| **Wo?** | Vorlagen mit Ortsbezug auf der Karte; Auswahl nach 10 Stadtbezirken und 69 Quartieren, wo belegbar bis zu Straße, Adresse oder Bebauungsplan. |
| **Wann?** | Je Vorlage eine Prozesslinie: Veröffentlichung, Beratungen (Gremium, Datum, Tagesordnungspunkt, Rolle, Ergebnis wörtlich), Folgevorlagen; kommende Sitzungen als offene Stationen. |
| **Wer?** | Federführendes Amt, befasste Gremien (Rat, Ausschüsse, 10 Bezirksvertretungen), einreichende Fraktionen und Gruppen. |

Dazu Liste, Suche, Erklärung der Begriffe, Feeds und ein Datenpaket. Zeitraum: Vorlagen ab 01.01.2020 (Wahlperioden 2020–2025 und 2025–2030). Die Bonner Zusatzthemen (u. a. Haushalt, Baustellen, Wahlen, Themenseiten, Ratsassistent) sind abgeschaltet, nicht gelöscht (CLAUDE.md 9).

## Stand der Arbeit

| Phase | Stand |
|---|---|
| 0 Kopie und Inventur | abgeschlossen ([inventur/BERICHT_phase0.md](inventur/BERICHT_phase0.md)) |
| 1 Exploration | läuft: Messstufen nach [explore/STUFEN.md](explore/STUFEN.md), je Stufe eigene Freigabe; Stufe 1 am 09.11.2026 mit Ergebnis `ok` (Vorlagenseite 4,11 s, nahe der Grenze von 5 s; Liste nach `created` statt `date` sortiert, Messung für Stufe 3 darauf angepasst); Stufe 2 freigegeben |
| 2 Datenpipeline | messunabhängige Teile vorgezogen (Adapter angeschlossen, Abruf gesperrt, Zusatzthemen abgeschaltet); Zeitfilter, inkrementeller Abruf und Änderungsprotokoll nach den Messungen |
| 4 Frontend | teilweise vorgezogen: „Quartier“ statt „Ortsteil“, Browser-Tests, erste WCAG-Prüfung mit erfundenen Daten ([inventur/WCAG_vorpruefung.md](inventur/WCAG_vorpruefung.md)); Kontrast über dem Kartenbild, Zoom und Bildschirmleser offen |
| 5 Repository und Deployment | Dokumentation in Arbeit; Veröffentlichung ohne Daten eingerichtet (`pages.yml`: Branch `deploy` ohne Historie, GitHub Pages; Plesk nach [docs/PLESK.md](docs/PLESK.md)); täglicher Lauf mit Abruf aus |
| 3 Geokodierung, 6 Verifikation | offen |

## Herkunft

- Ausgangsstand ist der Code des Ratsatlas Bonn (daimpad/allris-test) @ `52fe9ca`, als unabhängige Kopie ohne Daten und mit eigener Historie (https://github.com/daimpad/allris-test).
- SessionNet-Adapter, Messwerkzeuge in `explore/`, Test-Workflow und weitere Teile aus [daimpad/ratsatlas-koeln](https://github.com/daimpad/ratsatlas-koeln) @ `d609111`.
- Einzelheiten und Drittanbieter-Bestandteile: [NOTICE](NOTICE).

## Quellen und Lizenzen

| Quelle | Wofür | Lizenz |
|---|---|---|
| OParl-API der Stadt Wuppertal (`oparl.wuppertal.de`, Somacos Session) | Vorlagen, Beratungen, Sitzungen, Gremien, Ämter | **ungeklärt** (Feld `license` leer; Anfrage an die Stadt offen, CLAUDE.md 8); Namensnennung „Stadt Wuppertal“ immer |
| Quartiere, Straßenverzeichnis, georeferenzierte Bestandsadressen (`daten.wuppertal.de`) | Gebiete und Verortung | CC BY 4.0 |
| Stadtbezirke (`offenedaten-wuppertal.de`) | Gebiete | laut Open-Data-Katalog CC BY 4.0 (Quellenprüfung 10.11.2026); Prüfung der Datei in Messstufe G offen |
| Bebauungspläne: rechtsverbindliche und laufende Verfahren | Verortung über die Plannummer; Flächen unverändert | CC BY-ND 4.0; Open.NRW nennt abweichend „Andere geschlossene Lizenz“, Klärung offen |
| OpenStreetMap | nur nachrangig für Orte ohne Adresse, getrennt gekennzeichnet | ODbL 1.0 |

Namensnennung auf jeder Seite und in jedem Export ([data/LICENSE-DATA.md](data/LICENSE-DATA.md), Entwurf; noch sind keine dieser Daten im Repository, die Geodaten werden in Messstufe G geladen):

- „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0“
- Bebauungspläne: „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0“

## Grenzen

- **Zeitraum:** Vorlagen vor dem 01.01.2020 sind nicht enthalten. Der Umfang der Vorlagenliste wird in Messstufe 3 bestimmt.
- **Verortung in Stufen:** A (Ort aus der Quelle) entfällt voraussichtlich (Stichprobe: 0 von 100 mit `location`; Prüfung in Messstufe 5); B über Adressen, Straßen, Quartiere, Stadtbezirke und Plannummern; C per Sprachmodell nur ohne B-Treffer und gekennzeichnet. Jede Verortung nennt Methode, Konfidenz und Fundstelle. Präzision noch nicht gemessen (Phase 3).
- **Ableitungen:** Einreichende sind aus der Vorlagenart abgeleitet. Das federführende Amt nennt die Quelle nicht immer (Stichprobe: 75 von 100); die Ergänzung aus dem Kopf der Vorlage wird noch gemessen.
- **Volltexte:** Bis zur Lizenzklärung keine Volltexte, Zitate, Auszüge oder PDFs der Stadt; die Seite verlinkt auf das Original.
- **Datenschutz:** keine Verortung von Wohnadressen natürlicher Personen; Anregungen und Beschwerden nach § 24 GO NRW nur auf Quartiers- oder Straßenebene; keine Personennamen aus dem System-Objekt der Schnittstelle oder aus Dokumenten ([site/datenschutz.html](site/datenschutz.html)).
- **Nicht einsehbar:** nichtöffentliche Beratungen und die Arbeit innerhalb der Verwaltung.
- **Maßgeblich** ist immer das Original im Ratsinformationssystem (https://ris.wuppertal.de/).

## Abruf der Ratsdaten

- Nur über die OParl-Schnittstelle, kein Scraping von `ris.wuppertal.de`.
- Eine Verbindung, mindestens 2 s Abstand, nachts (23–1 Uhr), nach Fehlern Pausen bis 3 Stunden (regelmäßiger Abruf; bei Messungen höchstens 30 min, danach Abbruch), User-Agent mit Projektadresse und Kontakt.
- Regelmäßiger Abruf (`pipeline/abruf.py`) gesperrt, bis die Stadt informiert ist; Messungen (`explore/`) nur mit eigener Freigabe und nicht aus GitHub Actions.
- Fällt der Abruf aus, zeigt die Seite den letzten gültigen Datenstand und kennzeichnet ihn als solchen.

## Entwickeln

```bash
pip install -r requirements.txt pytest pypdf==6.17.0             # wie .github/workflows/tests.yml
RATSATLAS_SPERRE=$(mktemp -d) python3 -m pytest -q tests        # ohne Anfragen an die Stadt
(cd tests/browser && npm ci && npx playwright install chromium) && node --test "tests/browser/*.test.mjs"
python3 tools/seite_bauen.py && python3 -m http.server -d _site 8000   # fertige Seite wie pages.yml
```

Ordner: `pipeline/` Abruf, Aufbereitung und Seitenbau · `site/` Seite · `explore/` Messwerkzeuge der Phase 1 · `inventur/` Inventur und Berichte · `tests/` Tests mit erfundenen Daten · `tools/seite_bauen.py` fertige Seite bauen · `.github/workflows/` Tests und Veröffentlichung (ohne Abruf) · `.github/workflows-inaktiv/` übernommene Bonner Workflows und `static.yml`, abgeschaltet.

## Mitmachen, Kontakt, Lizenz

Hinweise auf falsche Orte oder Fehler bitte als [Issue](https://github.com/daimpad/ratsatlas-wuppertal/issues/new/choose); wie man am Code mitarbeitet, steht in [CONTRIBUTING.md](CONTRIBUTING.md).

Kontakt: contact@nozilla.de · [Impressum](https://nozilla.de/impressum/) · Code: [MIT](LICENSE) · Daten: [data/LICENSE-DATA.md](data/LICENSE-DATA.md) (Entwurf) · Herkunft und Drittanbieter: [NOTICE](NOTICE)
