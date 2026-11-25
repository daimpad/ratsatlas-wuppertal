# Phase 3 – Verortung: Zwischenbericht

Stand 17.11.2026 · Grundlage: Vollabruf vom 16./17.11.2026 (8.592 Vorlagen ab 2020), Geodaten der Stadt vom 16.11.2026,
Texte aus dem Dokumentabruf (Stand: 1.122 Vorlagen mit Text von etwa 8.000 möglichen). Lokaler Lauf in einer
Arbeitskopie, nichts veröffentlicht. Plan: CLAUDE.md 9 (16.11.2026, Punkte 1–8).

## Umgesetzt

| Punkt | Stand |
|---|---|
| 1 Grundlagen | Straßenverzeichnis (2.289 Einträge) und 61.714 Bestandsadressen übernommen; Straße-zu-Quartier-Tabelle für 2.165 Straßen (`data/geo/strassen_wuppertal.json`); Adressindex versioniert (`data/geo/hausnummern_wuppertal.json`, Entscheidung 17.11.2026), nicht auf der Seite |
| 2 Stufe B auf Titeln | Wuppertaler Ortsnamen-Abgleich (`pipeline/ortsnamen.py`) im Aufbau über `pipeline/ortsverzeichnis.py`; B-Plan-Nummern nach Wuppertaler Schema, auch laufende Verfahren; `district_from_committee` |
| 3 Stufe B auf Volltext | Texte aus dem Dokumentabruf, erste Anlage mit Text als Hauptdokument (Annahme); Kopf bis zur Beratungsfolge, Gremien und Dienstadressen ausgeblendet; nur Name und Teil des Dokuments gespeichert |
| 4 Kuratierte Ortsliste | eingebunden; Gesellschaften („… GmbH“, „e.V.“) nicht verortet; lange Objekte (Trassen) nur ohne genaueren Ort im selben Titel |
| 6 Datenschutz | Hauskoordinate nur mit `maske.hausnummer_punkt_erlaubt` (nicht bei Eingaben, verbundenen Vorlagen, Bauaufsicht, Umwelt) |
| 5 Stufe C | nicht begonnen (gesonderte Entscheidung) |

## Abdeckung (lokaler Lauf nach den Korrekturen)

- Ortsbezug aus dem Titel (Stufe B): 2.866 von 8.592 Vorlagen (33 %); davon 231 mit eindeutigem Bebauungsplan.
- Aus dem Volltext zusätzlich: 250 Vorlagen (bei 1.122 Vorlagen mit Text, vor der Regel der zwei Nennungen); nach den
  Korrekturen 76 (1.122 mit Text) und am 17.11.2026 nachmittags 85 (1.226 Vorlagen mit Text aus 2.109 Dateien, etwa
  13 % des Dokumentabrufs). Befunde des Laufs: 515 ohne Ort, 120 nur einzelne Erwähnung eines Stadtbezirks, 92 Titel
  ohne gemeinsamen Ort, 34 Listen, 1 nur in Anlagen genannt.
- Stadtbezirk nur aus der beratenden Bezirksvertretung (schwach): weitere rund 875 Vorlagen.
- Ohne jeden Ortsbezug bleiben rund 55 %; viele davon sind stadtweite Themen (Haushalt, Satzungen, Gesellschaften).

## Prüfung der Präzision (Punkt 7)

Stichprobe: je Methode 50 Vorlagen (Zufall mit festem Startwert), geprüft am Titel durch einen eigenständigen
Prüfdurchgang mit einem Sprachmodell (nicht von Hand). Gemessen **vor** den Korrekturen unten.

| Methode | n | richtig | teilweise | falsch | unklar | Präzision | mit „teilweise“ |
|---|---|---|---|---|---|---|---|
| Bebauungsplan | 50 | 48 | 2 | 0 | 0 | 0,96 | 1,00 |
| Hausnummer | 50 | 49 | 1 | 0 | 0 | 0,98 | 1,00 |
| Gebietsname | 50 | 48 | 1 | 1 | 0 | 0,96 | 0,98 |
| Teilname | 50 | 46 | 0 | 3 | 1 | 0,94 | 0,94 |
| Bezirksvertretung (schwach) | 50 | 45 | 0 | 3 | 2 | 0,94 | 0,94 |
| vererbt | 23 | 20 | 0 | 2 | 1 | 0,91 | 0,91 |
| Straße | 50 | 42 | 8 | 0 | 0 | 0,84 | 1,00 |
| Ortsliste | 50 | 34 | 15 | 0 | 1 | 0,69 | 1,00 |
| **gesamt** | 373 | 332 | 27 | 9 | 5 | **0,90** | **0,98** |

Korrekturen danach (nicht erneut gemessen):
- „Höhe“ (Quartier und Straße in Vohwinkel) nicht in „in/auf Höhe“, „Höhe von/der …“, „Kleine Höhe“ und „Höhe <Name>“
  (Ausschlüsse 5–8); im Volltext nur mit Hausnummer.
- Keine Teilnamen bei Quartiersnamen in Straßenform („Fr.-Engels-Allee“ ergab „Fr.“, „Engels“).
- Straße: Quartiere am Rand mit weniger als 3 Adressen oder unter 5 % der Adressen entfallen (das Hauptquartier bleibt).
- Trassen (Nordbahntrasse über 21 Quartiere) nicht verteilt, wenn der Titel einen genaueren Ort nennt (14 der 15
  Teiltreffer der Ortsliste).
- Folgevorlagen nur bei Vorlagennummern mit vier Ziffern („VO/107/23“ traf eine fremde Vorlage).

Damit sind 3 der 9 Fehltreffer und die meisten Teiltreffer behoben. Offen: stadtweite Themen, die nur eine
Bezirksvertretung beraten hat (3), Namen mit Vorsatz („Klein Beek“), Schulnamen nach einem Umzug, eine fragliche
Verknüpfung der Quelle.

## Zweite und dritte Messung (nach den Korrekturen)

Zweite Stichprobe: 419 Fälle (je Methode bis 50, neu gezogen, jetzt mit Volltext), gleiche Prüfmethode, aber
strengerer Maßstab für „teilweise“ (zu breit verortet gilt als teilweise). Präzision ohne Volltext 0,81, mit
Teiltreffern 0,99; Bebauungsplan 0,98, Hausnummer 0,96, Straße 0,82, Gebietsname 0,80, Bezirksvertretung 0,78,
Ortsliste 0,76, Teilname 0,60 (fast nur „teilweise“: Teilname auf den ganzen Stadtbezirk statt auf die Quartiere).

Volltext: 0,26 (mit Teiltreffern 0,52). Hauptursache (24 von 50): der Nachname „Berg“ im Unterschriftenblock traf die
gleichnamige Straße – zugleich ein Datenschutzfehler (Personenname als Ortsbeleg). Behoben: Unterschriften- und
Kontaktblöcke ausgeblendet, Silbentrennung zusammengezogen, „Berg“, „Schlüssel“, „Ausblick“, „Steinberg“, „Höfen“,
„Johannes-Rau-Platz“ im Volltext nur mit Hausnummer. Dritte Stichprobe nur Volltext (50 Fälle): 0,46 (0,78). Danach
zusätzlich Anschriften mit Postleitzahl ausgeblendet und jeder Ort im Volltext nur bei mindestens zwei Nennungen oder im
Bezirk einer befassten Bezirksvertretung: in derselben Stichprobe fallen alle 11 Fehltreffer weg (verbleibend 13
richtig, 8 teilweise: 0,62 bzw. 1,00; an derselben Stichprobe gemessen, daher nur eine Schätzung), aber auch 10
richtige. Volltext verortet damit 76 statt 169 Vorlagen (bei 1.122 mit Text).

Außerdem: Teilnamen mehrerer Quartiere („Wichlinghausen“, „Beyenburg“, „Nächstebreck“, „Uellendahl“) führen auf diese
Quartiere statt auf den Stadtbezirk („Langerfeld“ bleibt Stadtbezirk, Annahme); Vereinsnamen mit Gebietsnamen
(Ausschluss 9) und „Schiedsamtsbezirk …“ (10) verorten nicht.

## Federführung aus dem PDF-Kopf (17.11.2026, ohne Netz)

`python3 -m pipeline amtskopf` mit den bis dahin geladenen Texten: Von 8.592 Vorlagen ab 2020 haben 7.323 (85 %)
`underDirectionOf`; von den übrigen 1.269 sind nur 2 Verwaltungsvorlagen (beide 2024, Dateien noch nicht geladen), der
Rest Anträge und Anfragen der Fraktionen, für die keine Federführung der Verwaltung zu erwarten ist. Der PDF-Kopf
ergänzt die Federführung daher höchstens in Einzelfällen; die Quote je Datei bleibt ohne Gewicht. Nachtrag 23.11.2026:
mit den Texten von 6.454 Vorlagen ebenso 2 Verwaltungsvorlagen ohne `underDirectionOf`, in beiden keine Nummer im Kopf.
Nachtrag 25.11.2026 (Dokumentabruf abgeschlossen, alle 15.777 Dateien, Texte von 8.169 Vorlagen): unverändert 2
Verwaltungsvorlagen ohne `underDirectionOf`, in beiden keine Nummer im Kopf; die Federführung bleibt bei 7.323 von
8.592 Vorlagen (85 %). Verortung aus dem Volltext: 606 Vorlagen (1.487 Ortsbezüge).

## Prüfung von Hand (19.11.2026)

Der Auftraggeber hat 30 Verortungen von Hand geprüft: 26 richtig, 4 teilweise, 0 falsch. Präzision 0,87 (95-%-Intervall
0,70–0,95), mit Teiltreffern 1,00. Die Korrekturen danach (Objektnamen verdecken Gebietsnamen, Straße im Objektnamen,
Kurzformen mit Ergänzungsstrich, „Innenstadt Elberfeld/Barmen“, „GS“ für Grundschulen) stehen in CLAUDE.md 9.

## Offen

- Erneute Messung nach den Korrekturen vom 19.11.2026.
- Volltext erneut, wenn der Dokumentabruf vollständig ist (etwa 24.11.2026).
- Stufe C (Sprachmodell) nach gesonderter Entscheidung.
