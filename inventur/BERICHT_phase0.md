# Phase 0 – Kopie und Inventur (Bericht)

Stand 09.11.2026 · Grundlage: `CLAUDE.md` (Prompt v0.1), Abschnitt 7.0 · Noch keine Wuppertaler Logik

## 1. Durchgeführt

- Kopie aus `daimpad/allris-test` @ `52fe9ca` per `git archive`, ohne Historie, ohne `data/` und, wie bei Köln, ohne die Bonner Berichts-, Phasen-, Test- und Evaluationsverzeichnisse.
- SessionNet-Adapter aus `daimpad/ratsatlas-koeln` @ `d609111` in eigenem Commit, unverändert: `pipeline/sessionnet.py`, `pipeline/abruf.py`, `tests/conftest.py`, `tests/test_sessionnet.py` und die nötigen Namen in `pipeline/config.py` (noch Kölner Werte). Herkunft in `NOTICE`.
- Bonner Workflows in `.github/workflows-inaktiv/`; `static.yml` nur manuell. `CLAUDE.md` mit Entscheidungen (Abschnitt 9).
- Inventur reproduzierbar über `inventur/skripte/` (`fundstellen.py` → `fundstellen.tsv`, `fakten.py` → `fakten_module.tsv`, `inventur.py` mit `regeln.tsv` → `inventur_module.tsv`).
- Methode: vier Agenten ordneten je eine Dateigruppe ein und verglichen dabei jede Datei mit der Kölner Fassung; je Gruppe prüfte ein weiterer Agent die Einordnung gegen den Code (29 Korrekturen übernommen); ein letzter suchte nach Lücken. Kein Projektcode wurde ausgeführt, keine Anfrage an eine Stadt gestellt.

## 2. Zahlen

| Einordnung | Dateien | davon Code-Zeilen in `pipeline/` und `site/`¹ |
|---|---|---|
| generisch | 37 | 1 534 (12 Dateien) |
| Bonn-spezifisch, anpassen | 50 | 10 278 (39 Dateien) |
| Köln-spezifisch, anpassen | 4 | 1 378 (2 Dateien; dazu 2 Testdateien) |
| Zusatzthema, deaktivieren | 44 | 10 904 (41 Dateien) |
| entfernen | 4 | – (Bonner Skill, Bonner `pages.yml` und `tests.yml`, `static.yml` in Phase 5) |

¹ ohne `site/vendor/`. `fundstellen.tsv`: 1 495 Zeilen in 101 Dateien, darunter 111 Bezüge auf OParl-Lite, 27 auf `SITE_URL`/`PAKET_URL`, 190 Bonner und Projekt-URLs, 85 Kölner Bezüge (vor allem in den übernommenen Adapterdateien). Die Hälfte der Treffer liegt in zehn Dateien, angeführt von `site/app.js` (136) und `site/index.html` (111).

Köln hat 61 der übernommenen Dateien bereits für eine SessionNet-Stadt umgestellt (Spalte `koeln_vorarbeit`). Bonn hat seit dem Kölner Ausgangsstand 9eea7ea 34 dieser Dateien weiterentwickelt und `pipeline/vorgangsseiten.py` neu angelegt.

## 3. Strukturelle Befunde

1. **Adapter noch nicht angeschlossen.** `sessionnet.beratungen()` schreibt `beratungen.jsonl`, `build.py` liest `consultations_lite.jsonl`; Köln setzt beide gleich. `__main__.py` ruft für `fetch` weiter den Bonner Abruf auf. Quellenkennungen (`oparl-bonn`, `oparl-lite`, `geo-bonn`) stehen fest in `build.py`, `process.py`, `check.py`, `geocode.py`.
2. **Bonner Abruf ohne Sperre.** `python -m pipeline fetch` fragt die Bonner API mit sechs parallelen Verbindungen ab; `verify`, `besetzung`, `anliegen`, `baustellen`, `wahlen` und `haushaltsplan` rufen Bonner Server ohne Abrufpolitik ab. `abruf.freigegeben()` ist nicht an den Host gebunden, und `OPARL_BODY` zeigt noch auf Bonn. Solange kein Workflow läuft, geschieht nichts davon automatisch.
3. **Zusatzthemen ohne Schalter.** `export.py`, `seo.py`, `check.py` und `__main__.py` rufen Chat, Themenseiten, Soll-Modell und Kontext unbedingt auf; die Module werden auf Modulebene importiert und lassen sich daher nicht löschen. Köln hat eine Schalterkette gebaut (`config.ZUSATZTHEMEN` → `meta.funktionen` → `data-funktion` in der Seite); sie ist übernehmbar. Die Datenschutzregel für Vorlagen aus der Einwohnerschaft liegt im Chat-Modul (`chat.einwohner`) und muss beim Abschalten erhalten bleiben.
4. **Zwei Ausgangsstände.** Kölner Fassungen beruhen auf 9eea7ea; Wuppertal auf 52fe9ca. Kölner Änderungen sind daher hunkweise zu übernehmen, nicht als ganze Dateien.
5. **Wuppertaler Datenform.** Bonner Logik setzt `mainFile` (Volltexte, Stufe C, Vorgangsseiten), sechsstellige Drucksachennummern (`ref[:6]`), Bonner Postleitzahlen (`5xxxx`), exakte Vorlagenarten und OSM-Straßenlinien voraus. Wuppertal hat nur `auxiliaryFile`, `VO/NNNN/JJ`, Einreichende im `paperType`, Straßen nur als Adresspunkte und keinen `legislativeTerm` im Body.
6. **B-Pläne werden vereinfacht.** `flaechen.write()` vereinfacht und rundet die B-Plan-Geometrien; das widerspricht CC BY-ND 4.0 (Verbot 6). Die Änderung gehört in `flaechen.write`, nicht in `simplify()`, das auch `kontext` nutzt.
7. **Bonner Zeitraum und Verweise.** „seit Oktober 2019“ steht fest in Export, Feeds und Seite. Problem-Links und Quellcode-Link zeigen auf `daimpad/ratsatlas-bonn`. `technikseite.write` bricht ohne `pages.yml` und `tests/browser/package.json` ab und damit `seo.write`.
8. **Bonner Skill aktiv.** `.claude/skills/allris-bonn/SKILL.md` wird in Wuppertaler Sitzungen geladen und nennt Bonner Schritte und Branches.

## 4. Kölner Vorarbeit, die nicht übernommen ist

Für die nächsten Phasen direkt nutzbar (Einzelheiten in den Spalten `koeln_vorarbeit` und `begruendung`):

| Phase | Kölner Dateien |
|---|---|
| 1 | `explore/` (`abruf.py`, `oparl_messung.py`, `STUFEN.md`, `testserver.py`, `probelauf.py`, `auswertung.py`, `geodaten.py`, `ANFRAGE_stadt_koeln.md`), `tests/test_messstufen.py`, Skill `ratsatlas-koeln` als Gerüst |
| 2 | `pipeline/geodaten.py`, `tools/testdaten.py`, `.github/workflows/tests.yml`, `tests/test_geodaten.py`, `tests/test_check.py`, Vorlage `tests/test_akteure_koeln.py` |
| 3 | `pipeline/bplan.py` (ohne Rundung), `tests/test_geokodierung.py`, `tests/test_bplan.py` |
| 4 | `tools/seite_bauen.py`, `tools/wcag_pruefen.js`, `kacheln.yml`, `tests/test_kacheln.py`, `tests/test_gebietsseiten.py` |
| 5–6 | `pages.yml`, `live.yml`, `pipeline/paket.py`, `docs/PLESK.md`, `tools/linkpruefung.py`, `tests/test_hinweise.py`, `tests/test_workflows.py` |

Nicht übernehmen: `pipeline/ebenen.py` (Kölner Zusatzebenen), `tests/test_anliegen.py`.

## 5. Offene Einordnungen (Ihre Entscheidung)

1. **Zusatzthemen**, vorläufig „deaktivieren“: Haushalt, Baustellen und Mängelmelder, Wahlen, Themenseiten, Ratsassistent, Soll-Modell mit Reiter „Prozesse“ und „Mitmachen“, Kennzahlen je Gebiet (`kontext`; in Köln eingeschaltet), Einfache Sprache, Kurzfassungen, Gremienbesetzung.
2. **Vorgangsseiten** (`vorgangsseiten.py`, in Bonn neu): vorläufig Kern („anpassen“), weil sie den Vorgang mit Beratungsfolge für Suchmaschinen erschließen.
3. **Vorschaubild** `og-image.jpg`: vorläufig „anpassen“ (Wuppertaler Bild in Phase 4, bis dahin nicht ausliefern); die Gegenprüfung schlug „entfernen“ vor.
4. **Bonner Tests** (`tests/` in allris-test) wurden wie bei Köln nicht übernommen; einzelne Tests generischer Module (`maske`, `geo`, `process`) ließen sich gezielt nachholen.

## 6. Vorschlag Phase 1 (Exploration, nur `explore/`)

1. Die Kölner Messwerkzeuge aus `explore/` übernehmen und auf Wuppertal einstellen (Body `0001`, 100 je Seite, `http`-IDs, `auxiliaryFile`, Präfixe `gr`/`at`, Datumsgrenze 2020, Zerlegung `paperType`). Probelauf nur gegen den lokalen Testserver.
2. Den Wuppertaler Skill aus dem Kölner Gerüst ableiten und den Bonner Skill entfernen.
3. Die Anfrage an die Stadt (Ratsbüro 001.13, offenedaten@stadt.wuppertal.de) nach Kölner Vorlage entwerfen, zur Versendung durch Sie.
4. Messungen gegen `oparl.wuppertal.de` und das einmalige Laden der Geodaten erst nach Ihrer Freigabe, gestuft mit festen Anfrageobergrenzen.
