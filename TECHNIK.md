# Ratsatlas Wuppertal – Technik

Technische Beschreibung von Pipeline, Seite und Betrieb, Stand 10.11.2026. Worum es inhaltlich geht, steht in der [README](README.md); Auftrag, Abrufpolitik und Entscheidungen stehen in [CLAUDE.md](CLAUDE.md), die Herkunft des Codes in [NOTICE](NOTICE).

**Stand: online ohne Daten.** Die Seite ist veröffentlicht, enthält aber noch keine Ratsdaten: Sie zeigt „Daten nicht verfügbar“ und trägt `noindex`. Der regelmäßige Abruf ist gesperrt, bis die Stadt informiert ist (CLAUDE.md 5.1 und 9).

## Aufbau des Repositorys

- `pipeline/` – Kern aus dem Ratsatlas Bonn (`daimpad/allris-test` @ `52fe9ca`): Aufbereitung in SQLite (`pipeline/build.py`), Geokodierung (`pipeline/geocode.py`, `pipeline/geo.py`), Bebauungspläne (`pipeline/bplan.py`, Geometrien unverändert), Flächen (`pipeline/flaechen.py`), Export (`pipeline/export.py`), Prüfung (`pipeline/check.py`), Seiten (`pipeline/seo.py`, `pipeline/gebietsseiten.py`, `pipeline/vorgangsseiten.py`, `pipeline/begriffsseite.py`, `pipeline/rssseite.py`), Einstellungen (`pipeline/config.py`). Abruf über den SessionNet-Adapter aus `daimpad/ratsatlas-koeln` @ `d609111` (`pipeline/sessionnet.py`, `pipeline/abruf.py`).
- `site/` – statische Seite: `site/index.html`, `site/app.js` (Karte mit Leaflet, Liste, Filter), `site/timeline.js` (Zeitleiste), `site/tour.js`, `site/style.css`, `site/datenschutz.html`, `site/404.html`, Vorschaubild `site/vorschaubild.jpg`; Leaflet und Leaflet.markercluster in `site/vendor/`, Schrift Inter in `site/fonts/`.
- `tools/` – Seite bauen (`tools/seite_bauen.py`), Live-Prüfung (`tools/live_pruefen.py`), Linkprüfung (`tools/links_pruefen.py`), Vorschaubild (`tools/vorschaubild.mjs`).
- `explore/` – Messwerkzeuge der Phase 1 ohne Produktionscode (`explore/README.md`, Stufenplan `explore/STUFEN.md`, Anfrage an die Stadt `explore/ANFRAGE_stadt_wuppertal.md`); Quellenprüfung Strukturdaten in `explore/strukturdaten/`.
- `inventur/` – Inventur der Bonner Kopie (`inventur/BERICHT_phase0.md`), WCAG-Vorprüfung (`inventur/WCAG_vorpruefung.md`), letzter Lauf der Linkprüfung (`inventur/audit_links.tsv`).
- `tests/` – Python-Tests mit erfundenen Daten und lokalen Testservern; Browser-Prüfung in `tests/browser/`.
- `deploy/htaccess` – Apache-Einstellungen für die Hauptadresse (Sicherheitskopfzeilen, Zwischenspeicher, gesperrte Pfade); `docs/PLESK.md` – Checkliste für die Einrichtung in Plesk.
- `data/LICENSE-DATA.md` – Lizenzen der Daten (Entwurf). Rohdaten, Datenbank und Export (`data/raw/`, `data/build/`, `data/export/`) werden nicht versioniert.
- `.github/workflows/` – aktive Workflows; `.github/workflows-inaktiv/` – aus Bonn übernommene Workflows, die nicht laufen; `.github/dependabot.yml`; Issue-Vorlagen in `.github/ISSUE_TEMPLATE/`.
- `.claude/skills/ratsatlas-wuppertal/SKILL.md` – Arbeitsweise für Claude Code.

## Datenquelle und Abruf

Primärquelle ist die OParl-API der Stadt Wuppertal (Somacos SessionNet, Body `0001`; Endpunkte in `pipeline/config.py`, für Tests über `RATSATLAS_OPARL_SYSTEM` und `RATSATLAS_OPARL_BODY` umlenkbar). Der Adapter `pipeline/sessionnet.py` schreibt die Rohdaten im Bonner Format nach `data/raw/` (u. a. `papers.jsonl`, `organizations.json`, `meetings.json`, `beratungen.jsonl`), dazu den Zustand des inkrementellen Abrufs `data/raw/zustand_abruf.json` und die Abrufstatistik `data/export/abrufstatistik.tsv`. Die Kennungen der Quelle (`http://`) bleiben Schlüssel; abgerufen wird über `https://`.

Sperren und Freigaben:

| Werkzeug | Sperre | Freigabe |
|---|---|---|
| regelmäßiger Abruf (`pipeline/abruf.py`) | jede nicht lokale Adresse | `RATSATLAS_STADT_INFORMIERT=ja`, erst nach Information der Stadt; lokal (127.0.0.1, localhost, ::1) immer |
| Messungen (`explore/oparl_messung.py`, `explore/geodaten.py`, Abruf über `explore/abruf.py`) | Server der Stadt | `RATSATLAS_MESSUNG_FREIGEGEBEN=ja` je freigegebener Stufe; PDF-Köpfe (Stufe 6) zusätzlich `RATSATLAS_PDF_FREIGEGEBEN=ja` |
| Quellenprüfung Strukturdaten (`explore/strukturdaten/abruf_struktur.py`) | nur Hosts aus `ERLAUBTE_HOSTS` (`www.offenedaten-wuppertal.de`, `offenedaten-wuppertal.de`, `www.wuppertal.de`, `daten.wuppertal.de`, `www.wegweiser-kommune.de`); `oparl.wuppertal.de` und `ris.wuppertal.de` verboten; `daten.wuppertal.de` nur HEAD oder höchstens 2 MB; je Host eine Verbindung, mindestens 2 s Abstand, höchstens 40 Anfragen; Protokoll `explore/strukturdaten/audit_abruf.tsv` | keine Umgebungsvariable; Aufruf nur von Hand, tagsüber, nach der Entscheidung zu den Strukturdaten in CLAUDE.md 9 (10.11.2026) |
| übrige Abrufe aus Bonn (`pipeline/net.py`) | Adressen der Stadt, auch als Ziel einer Weiterleitung | keine; solche Abrufe gehören auf `pipeline/abruf.py` |

Die Abrufpolitik (eine Verbindung, Abstand, nächtliches Zeitfenster, Pausen nach Fehlern, User-Agent mit Projektadresse und Kontakt) steht in CLAUDE.md 5.1; die Umsetzung ist im Kopf von `pipeline/abruf.py` und `explore/abruf.py` beschrieben, die Einstellungen in `pipeline/config.py` und `explore/README.md`. `pipeline/abruf.py` und `explore/abruf.py` teilen die Sperrdatei `abruf.lock` im Ordner aus `RATSATLAS_SPERRE` (Vorgabe: Cache-Ordner im Benutzerverzeichnis, außerhalb des Checkouts), damit nie zwei Prozesse gleichzeitig die OParl-API abrufen; `explore/strukturdaten/abruf_struktur.py` sperrt im selben Ordner je Host mit eigenen Dateien (`struktur-<host>.lock`). Messungen und Quellenprüfung werden lokal gestartet; kein Workflow ruft sie auf.

Aufruf der Pipeline: `python3 -m pipeline <schritt>`. Aktiv sind `fetch` (Adapter, gesperrt wie oben), `build`, `export`, `check` und `seo`; `all` führt derzeit `fetch` und `build` aus. Die aus Bonn übernommenen Abrufschritte (etwa `fetch-plans`, `gazetteer`, `verify`, `package`) brechen ohne Anfrage mit einem Hinweis auf ihren Wuppertaler Ersatz ab (`pipeline/__main__.py`).

## Zusatzthemen

Die Bonner Zusatzthemen bleiben im Code, sind aber über `ZUSATZTHEMEN` in `pipeline/config.py` abgeschaltet (CLAUDE.md 9): `haushalt`, `baustellen`, `anliegen` (Mängelmelder), `wahlen`, `themenseiten`, `kontext` (Kennzahlen je Gebiet), `soll` (Prozesse, Soll-Modell), `chat` (Ratsassistent), `einfache_sprache`, `kurzfassungen`, `mitmachen`, `besetzung` und `technik` (Seite „So funktioniert der Ratsatlas“). Ihre Schritte in `pipeline/__main__.py` brechen ab, ihre Module liefert `tools/seite_bauen.py` nicht aus, ihre Elemente auf der Seite tragen `data-funktion` und bleiben verborgen.

## Geokodierung

Stufe B für Wuppertal entsteht in `pipeline/ortsnamen.py` (CLAUDE.md 5.2; vorgezogen ohne Geodaten der Stadt, Freigabe 10.11.2026). Das Modul liest keine Dateien von selbst und ruft nichts ab; geprüft ist es nur mit erfundenen Daten (`tests/test_ortsnamen.py`). In `pipeline/build.py` ist es noch nicht eingebunden: Bis Phase 3 arbeitet `pipeline/geocode.py` unverändert mit den Regeln aus Bonn.

Was steht:

- Ortsnamen: eine Normalisierung für Text und Verzeichnis (Groß- und Kleinschreibung, „ß“/„ss“, Bindestrich, Schrägstrich und Leerzeichen gleich, „…str.“ = „…straße“), Fundstelle in Originalschreibweise; längster Treffer zuerst mit Wortgrenzen („Oberbarmen“ vor „Barmen“, „Elberfeld-West“ vor „Elberfeld“); Doppelnamen auch in Teilen (Konfidenz niedrig); mehrdeutige Namen als Stadtbezirk oder mit Kennzeichnung „mehrdeutig“; Genitiv auf „s“, aber keine abgeleiteten Adjektive.
- Ausschlüsse: dieselben Regeln wie `explore/ortsnamen_ausschluss.tsv` (BV, Bezirksvertretung, Rathaus, „Barmer“); ein Test hält beide gleich. Abgeglichen wird wie bei den Namen ohne Unterschied der Groß- und Kleinschreibung und mit beliebigem Trenner („BV-Barmen“, Zeilenumbruch). Mehrzahl und Aufzählungen („Bezirksvertretungen Barmen und Oberbarmen“) erfasst die Liste noch nicht.
- Straßen: Straßenschlüssel der Stadt statt Abstandsregel; gleichnamige Straßen werden über genannte Quartiere, Stadtbezirke oder die befasste Bezirksvertretung eingegrenzt, sonst als mehrdeutig ausgewiesen.
- Hausnummern: Hauskoordinate (Konfidenz hoch) nur, wenn die aufrufende Stelle sie erlaubt; sonst nur das Quartier der Adresse. Eine Zahl gilt nur als Hausnummer, wenn danach Satzende, ein Satzzeichen, ein Strich oder ein Bindewort folgt („Probestraße 3 und 5“, nicht „Probestraße 3 Bäume“). Die Nummer steht nie in Name oder Fundstelle; das prüft bisher nur `tests/test_ortsnamen.py`, `pipeline/check.py` prüft nur Ortsangaben der Stufe A.
- Straße-zu-Quartier-Tabelle aus Adresspunkten nach denselben Regeln wie `explore/geodaten.py` (Straßenschlüssel ohne führende Nullen, ungültige Flächen nur im Speicher repariert); Anzeigepunkt nie ein einzelnes Haus: höchstens so nah wie ein Mindestabstand (vorläufig 25 m) an einem Hauspunkt, sonst ein Punkt in der Fläche des Quartiers.
- Feldnamen der Geodaten an einer Stelle: `GEO_FELDER` in `pipeline/config.py`; offene Felder brechen ab, statt geraten zu werden.

Offen bis zu den Messstufen: Feldnamen, Schreibweise und Koordinatensystem der Geodaten, Eindeutigkeit der Straßenschlüssel, Schema der B-Plan-Nummern (`BPLAN_NUMMER`) und Quartiersnamen, die mit Teilnamen kollidieren (Stufe G); Gremiennamen der Bezirksvertretungen und weitere Ausschlüsse (Stufe 3); Ämter und Vorlagenarten, von denen abhängt, wann eine Hauskoordinate erlaubt ist, nie bei Eingaben nach § 24 GO NRW (Stufen 4 und 5); Ausschlüsse, Gattungs- und historische Namen an echten Titeln. Offen bis Phase 3: Mindestabstand des Anzeigepunkts und `min_anteil`; Mehrzahl und Aufzählungen von Gremiennamen in den Ausschlüssen (mit Stufe 3). In Phase 3 folgen die Einbindung, die kuratierte Ortsliste (Schwebebahn, Nordbahntrasse …), `audit_geokodierung.tsv`, die Prüfung der Stufe B in `pipeline/check.py` (keine Ziffern in Fundstellen, Zeilen der Ebene „adresse“, keine Hauskoordinate bei Eingaben nach § 24 GO NRW), ein eigener Ortsschlüssel für Zeilen der Ebene „adresse“ in `build._add_location` (bisher fielen dort alle Adressen einer Straße unter `adresse:<Name>` zusammen, mit falscher Quelle) und die Beschriftung der neuen Methoden auf der Karte.

## Seite

`python3 tools/seite_bauen.py [ziel]` stellt die Seite aus `site/` zusammen (Vorgabe `_site/`), erzeugt Gebiets-, Begriffs-, Feed- und Vorgangsseiten, `robots.txt` und Sitemaps (`pipeline/seo.py`, absolute Adressen aus `SITE_URL`), übernimmt `deploy/htaccess` als `.htaccess` und schreibt `version.txt` (Commit, aus dem die Seite gebaut ist). Ohne Datenexport zeigt die Seite „Daten nicht verfügbar“ und trägt `noindex` in jeder Seite; Sitemaps entfallen dann. Ohne Netz:

```bash
python3 tools/seite_bauen.py _site && python3 -m http.server -d _site 8000
```

Karte: Standard ist die graue Karte (Kacheln von OpenStreetMap mit Graufilter, Klasse `map-gray`), wählbar die farbige. Eigene graue Kacheln (`pipeline/kacheln/`) sind noch nicht in Betrieb. Das Vorschaubild für geteilte Links zeigt die graue Karte; es entsteht einmalig mit `node tools/vorschaubild.mjs` (Herkunft und Lizenz in NOTICE). Vorher Playwright installieren wie für die Browser-Prüfung (`cd tests/browser && npm ci && npx playwright install chromium`); hinter einem Proxy mit `NODE_USE_ENV_PROXY=1`. Das Skript ruft bis zu 40 Kacheln von `tile.openstreetmap.org` ab und keine Server der Stadt; `node tools/vorschaubild.mjs --probe` läuft ohne Netz und schreibt nicht ins Repository.

## Veröffentlichung und Workflows

| Workflow | Auslöser | Aufgabe |
|---|---|---|
| `.github/workflows/tests.yml` | Pull Requests, Push auf `main` | Python-Tests, Syntax der Skripte der Seite, Browser-Prüfung |
| `.github/workflows/pages.yml` | Push auf `main`, auf Knopfdruck | Seite bauen ohne Abruf; Branch `deploy` ohne Historie für Plesk (Hauptadresse https://wuppertal.ratsatlas.de/); GitHub Pages als Ausweichadresse (https://daimpad.github.io/ratsatlas-wuppertal/, Canonical auf die Hauptadresse) |
| `.github/workflows/live.yml` | nach `pages.yml`, täglich, auf Knopfdruck | Live-Prüfung beider Adressen mit `tools/live_pruefen.py`: Status, Titel, Canonical, `noindex`, Sicherheitskopfzeilen, Umleitung auf HTTPS, gesperrte Pfade, Zertifikat, ausgelieferter Stand gleich Branch `deploy` |
| `.github/workflows/links.yml` | monatlich, auf Knopfdruck | Linkprüfung der gebauten Seite mit `tools/links_pruefen.py`; Server der Stadt und die Kachelserver werden nicht angefragt, ihre Links als „nicht geprüft“ ausgewiesen |

Keiner dieser Workflows fragt Server der Stadt an; ein täglicher Lauf mit Abruf ist noch nicht eingerichtet. Repository-Variable: `SITE_URL` (Vorgabe https://wuppertal.ratsatlas.de/). Keine Zugangsdaten im Repository; Plesk holt den Branch `deploy` per Webhook (`docs/PLESK.md`).

Die Actions sind in den Workflows fest auf Commits gesetzt. `.github/dependabot.yml` schlägt monatlich gebündelte Aktualisierungen in einem Pull Request vor (neue Versionen frühestens nach 14 Tagen); `.github/workflows-inaktiv/` und die npm-Pakete der Tests erfasst Dependabot nicht. Pull Requests von Dependabot werden wie alle anderen zusammengeführt, sobald sie grün sind.

## Tests

Alle Tests laufen ohne Anfragen an Server der Stadt, mit erfundenen Daten und lokalen Testservern auf 127.0.0.1: OParl-Testserver für Adapter und Pipeline (`tests/oparl_testserver.py`, Fixture in `tests/conftest.py`), Testserver der Messwerkzeuge (`explore/testserver.py`, Probelauf `explore/probelauf.py`), Testseite der Browser-Prüfung (`tests/browser/testseite.py`, ausgeliefert von `tests/browser/hilfe.mjs`, das Anfragen an fremde Hosts abbricht und als Fehler meldet).

```bash
pip install -r requirements.txt pytest pypdf==6.17.0       # wie tests.yml
RATSATLAS_SPERRE=$(mktemp -d) python3 -m pytest -q tests/
(cd tests/browser && npm ci && npx playwright install chromium)
node --test "tests/browser/*.test.mjs"                     # Playwright, axe-core (WCAG 2.1 A und AA), Tastatur, Kontrast
```

Playwright und axe-core sind in `tests/browser/package-lock.json` fest gesetzt.

## Offen

- Messstufen 2 bis 6 und G (`explore/STUFEN.md`); Stufe 1 ist ausgeführt. Danach Anfrage an die Stadt und erst dann der erste Abruf.
- Phase 2: Zeitfilter ab 01.01.2020, `modified_since`, Zerlegung von `paperType`, Änderungsprotokoll `audit_aenderungen.tsv`, täglicher Lauf mit Abruf und Datenpaket.
- Phase 3: Geokodierung nach CLAUDE.md 5.2 mit den Wuppertaler Geodaten (noch nicht im Repository): `pipeline/ortsnamen.py` einbinden (Abschnitt Geokodierung); `pipeline/geocode.py` arbeitet bis dahin mit den aus Bonn übernommenen Regeln.
- Lizenz der Ratsdaten und PDFs (CLAUDE.md 8); bis dahin keine Volltexte, Zitate oder PDFs.
