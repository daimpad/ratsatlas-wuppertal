# Entwurf: Bitte um schriftliche Bestätigung an die Stadt Wuppertal

> Stand 17.11.2026 · Bitte um schriftliche Bestätigung der mündlichen Zusage vom 13.11.2026 (CLAUDE.md 9) mit den Zahlen aus den Messstufen 1–5 (09.–13.11.2026), dem ersten Vollabruf (Nacht 16./17.11.2026) und dem Beginn des Dokumentabrufs (17.11.2026); Belege in der Anlage · Versand nur durch den Auftraggeber · **Einziger Platzhalter:** E-Mail-Adresse des Ratsbüros; dazu Name und ggf. Telefon in der Grußformel · Messstufe 6 entfiel als eigener Abruf (Entscheidung 15.11.2026); die Quote der PDF-Köpfe bleibt offen, bis der Dokumentabruf genug Texte geliefert hat · Zahlen des Vollabrufs aus der lokalen Abrufstatistik (`data/export/abrufstatistik.tsv`, `abrufstatistik_seiten.tsv`; nicht im Repository) · abgeleitet aus `ANFRAGE_stadt_koeln.md` in `daimpad/ratsatlas-koeln` · Statistik je Quartier als eigene Mail (`ANFRAGE_statistik_wuppertal.md`, Entscheidung 15.11.2026)

**An:** offenedaten@stadt.wuppertal.de (Open Data, Amt 402); Ratsbüro, 001.13 [E-Mail-Adresse des Ratsbüros]
**Betreff:** Ratsatlas Wuppertal – Bitte um schriftliche Bestätigung der Zusage vom 13.11.2026 (OParl-Schnittstelle, Lizenz, Abrufverfahren)

Sehr geehrte Damen und Herren,

vielen Dank für Ihre mündliche Zustimmung vom 13. November 2026 zum ehrenamtlichen „Ratsatlas Wuppertal“ (geplant unter wuppertal.ratsatlas.de, Quellcode offen unter https://github.com/daimpad/ratsatlas-wuppertal). Er soll Bürger:innen helfen, Vorlagen des Rates und der Bezirksvertretungen ab 2020 nach Ort, Stand der Beratung und Zuständigkeit zu finden; jede Angabe verweist auf das Original in Ihrem Ratsinformationssystem.

Vorab habe ich die Schnittstelle `oparl.wuppertal.de` in fünf Nächten vom 9. bis 13. November 2026 mit zusammen 27 Anfragen vermessen und in der Nacht vom 16. auf den 17. November 2026 den ersten Vollabruf durchgeführt (Anlage). Ich bitte Sie, folgende Punkte schriftlich zu bestätigen oder zu berichtigen:

1. **Umfang der Zusage**, wie ich ihn verstanden habe: (a) regelmäßiger Abruf der OParl-Schnittstelle; (b) Veröffentlichung der Ratsdaten mit Namensnennung; (c) Auswertung der PDF-Volltexte. Ich gehe davon aus, dass (b) auch daraus abgeleitete Angaben umfasst (Ortsbezug, Beratungsverlauf, federführende Stelle, einreichende Fraktionen); bitte bestätigen Sie das. Bis zu einer schriftlichen Lizenz veröffentliche ich aus den Dokumenten keine Zitate oder Auszüge und spiegele sie nicht, sondern verlinke sie.
2. **Lizenz und Namensnennung:** Das Feld `license` ist im System- und im Body-Objekt leer (`null`). Welche Lizenz bzw. Nutzungsbedingungen gelten für die OParl-Objekte und die verlinkten PDF-Dokumente, und welche Namensnennung wünschen Sie? Vorgesehen ist „Datenquelle: Stadt Wuppertal“ mit Link auf das Original. Wäre es möglich, das Feld `license` zu befüllen?
3. **Abrufverfahren:** Der erste Vollabruf lief in der Nacht vom 16. auf den 17. November 2026 von 23:06 bis 0:08 Uhr aus derselben Arbeitsumgebung wie die Messungen, mit zusammen 1.311 Anfragen und ohne Fehler, Wiederholung oder Weiterleitung: Body, Organisationsliste (3 Seiten, 240 Organisationen), Vorlagenliste (96 Seiten zu je 100 Vorlagen; die Grenze 2020 lag wie gemessen auf Seite 87, auf den Seiten 88 bis 91 standen noch einzelne Vorlagen mit Datum ab 2020, der Abruf endete nach fünf weiteren Seiten ohne solche Vorlage; zusammen 8.592 Vorlagen ab 2020) und Sitzungen (die ersten 2 Seiten der Sitzungsliste für künftige Termine und 1.209 Sitzungen einzeln, auf die Beratungen dieser Vorlagen verweisen; nicht die vollständige Liste). Im Mittel dauerte eine Vorlagenseite 4,6 Sekunden, eine einzelne Sitzung 0,5 Sekunden. Personen (`people`) werden nicht abgerufen. Künftig täglich nur geänderte Objekte (`modified_since`); in der Messung ergab der Filter für rund sechseinhalb Tage eine Seite mit 36 Vorlagen. Immer eine Verbindung, mindestens zwei Sekunden Abstand, nur zwischen 23 und 1 Uhr; Verhalten bei Fehlern siehe Anlage. Wünschen Sie ein anderes Zeitfenster oder eine andere Rate?
4. **Abruf aus GitHub Actions:** Der tägliche Abruf kommt aus wechselnden, geteilten Rechenzentrums-IP-Bereichen von GitHub, mit dem User-Agent `ratsatlas-wuppertal/<Version> (+https://github.com/daimpad/ratsatlas-wuppertal; contact@nozilla.de)`. Ist das für Sie in Ordnung, oder wünschen Sie eine Alternative (etwa eine feste Adresse)?
5. **PDF-Dokumente:** Die federführende Stelle (`underDirectionOf`) ist bei 7.323 von 8.592 Vorlagen ab 2020 angegeben (85 %); sie fehlt fast nur bei Anträgen und Anfragen der Fraktionen. Für die Ortsbestimmung und, wo diese Angabe fehlt, für die federführende Stelle werte ich seit dem 17. November 2026 die Anlagen (`auxiliaryFile`) der Vorlagen ab 2020 aus: 15.777 Dateien. Ausgenommen sind die Anlagen von 405 Vorlagen, deren Titel auf Anregungen und Beschwerden nach § 24 GO NRW oder auf Einwohnerinnen und Einwohner verweist, und der mit ihnen verbundenen Vorlagen (Datenschutz). Abweichend vom Zeitfenster der Schnittstelle laufen diese Abrufe auch tagsüber: eine Verbindung, tagsüber (6 bis 23 Uhr) mindestens fünf Sekunden Abstand, nachts mindestens zwei, keine Abrufe zwischen 23 und 1 Uhr, höchstens 2.000 Dateien am Tag; der erste Durchgang dauert damit etwa acht Tage. Die Dateien werden nur zur Textauswertung kurz gespeichert und danach gelöscht, nicht gespiegelt. Wie oft die federführende Stelle im Kopf eines Dokuments erkennbar ist, steht noch nicht fest. Sind Rate und Tageszeit für Sie in Ordnung?

Außerdem bitte ich um Auskunft zu vier Fragen:

- **HTTP 401:** Seite 250 der Vorlagenliste antwortete am 11.11.2026 um 23:09 Uhr mit HTTP 401 ohne Inhalt (Seite 240 war gefüllt). Liegt die Seite hinter dem Listenende, oder ist das eine Zugangsbeschränkung? Seiten in diesem Bereich frage ich nicht mehr ab.
- **Kürzel „AU“ und „OB“:** Was bedeuten „AU“ in Vorlagenarten wie „Antrag FDP / WfW Rat AU“ und „OB“, und gibt es eine Liste der Vorlagenarten und Kürzel?
- **Organisationsliste:** Wie sind „Jobcenter Wuppertal“, „Regionalbüro“, „UWG“, „BEG“, „AWG“, „DIE GRAUEN - Graue Panther-“, „Klinikum Wuppertal“ und „Stadthalle Wuppertal“ einzuordnen: als Dienststelle der Stadt, als Beteiligung bzw. eigene Einrichtung oder als Gruppe im Rat? Wofür stehen die drei Kürzel?
- **Bebauungspläne:** Auf offenedaten-wuppertal.de stehen die Bebauungspläne unter CC BY-ND 4.0, Open.NRW nennt „Andere geschlossene Lizenz“. Welche Angabe gilt? Die Geometrien würde ich nur unverändert anzeigen.

Bis zu Ihrer schriftlichen Bestätigung kennzeichne ich die Lizenz der Ratsdaten auf der Seite als „mündlich zugesagt, schriftlich ausstehend“. Für Rückfragen stehe ich gern zur Verfügung.

Mit freundlichen Grüßen
[Name]
contact@nozilla.de [ggf. Telefon]

---

## Anlage: Messergebnisse

Gemessen am 9., 10., 11., 12. und 13. November 2026 jeweils zwischen 23:07 und 23:15 Uhr, mit einer Verbindung und mindestens zwei Sekunden Abstand; erster Vollabruf am 16./17. November 2026 von 23:06 bis 0:08 Uhr unter denselben Bedingungen. Belege im Repository unter `explore/ergebnisse/` (Messprotokolle als TSV) und in `explore/STUFEN.md` (Abschnitte „Ergebnis“); Zahlen des Vollabrufs aus der Abrufstatistik der Arbeitsumgebung.

| Messgröße | Ergebnis | Beleg |
|---|---|---|
| Anfragen | Messung: 27 in 6 Läufen in 5 Nächten; 5 Läufe ohne Auffälligkeit, 1 Lauf endete mit HTTP 401 (siehe Frage). Vollabruf: 1.311 in einer Nacht, ohne Fehler, Wiederholung oder Weiterleitung | `oparl_laeufe.tsv` (`netz`, `ergebnis`, Läufe 1–6); Abrufstatistik des Vollabrufs |
| Antwortzeiten | Vorlagenseiten 3,94–4,61 s (12 Seiten); Vorlagen mit kodiertem `modified_since` 2,05 s; Sitzungen 1,59–1,95 s; Organisationen 0,67–1,83 s; System 0,72 s, Body 0,52 s | `STUFEN.md`, Stufe 1–4 |
| Seitengröße | 100 Objekte je Seite; eine Vorlagenseite 212.012–315.892 Bytes | `oparl_kennzahlen.tsv`; Spanne aus dem lokalen Abrufprotokoll (nicht im Repository) |
| Lizenzfelder | `license` in System und Body `null`; `licenseValidSince` 24.04.2020 | `oparl_kennzahlen.tsv` |
| `modified_since` | unkodiert ohne Wirkung, URL-kodiert wirksam (36 Vorlagen seit 2026-11-04T08:45:43+00:00, Abruf 10.11.2026); über mehrere Seiten und bei Löschungen nicht gemessen | `oparl_kennzahlen.tsv` |
| Grenze 2020 | Vorlagen absteigend nach `created` sortiert (nicht nach `date`); Grenzseite 87, Seiten 1–86 rund 8.560 Vorlagen mit `created` ab 01.01.2020 | `oparl_umfang.tsv`, `oparl_umfang_seiten.tsv` |
| Sicherheitsabstand | im Vollabruf: Seiten 88–91 mit je 1–2 Vorlagen mit `date` ab 2020 (`created` davor), Seiten 92–96 ohne; Abruf endet nach 5 Seiten in Folge ohne solche Vorlage | Abrufstatistik des Vollabrufs (je Seite) |
| Listenende | offen: Seite 240 gefüllt (mindestens 24.000 Vorlagen), Seite 250 HTTP 401 | `oparl_laeufe.tsv` Lauf 3 |
| Organisationen | 240 auf 3 Seiten, Listenende erreicht; Präfix `at` 95, `gr` 145 | `oparl_listen.tsv`, `oparl_organisationen.tsv` |
| Sitzungen | Liste nicht nach `start` sortiert; im Vollabruf daher nicht die ganze Liste, sondern die ersten 2 Seiten und 1.209 Sitzungen einzeln (alle 1.216 von Beratungen der Vorlagen ab 2020 verwiesenen vorhanden), zusammen 1.409; im Mittel 0,5 s je Sitzung | `oparl_sitzungen.tsv`; Abrufstatistik des Vollabrufs |
| Umfang erster Abruf | Vorlagen: 96 Seiten, 8.592 Vorlagen ab 2020 (1.008 ältere verworfen), rund 25 MB, im Mittel 4,6 s je Seite; Organisationen 0,4 MB; Sitzungen rund 17 MB; Dauer zusammen rund 61 Minuten | Abrufstatistik des Vollabrufs |
| Fehlerverhalten (Abruf der Schnittstelle) | nach HTTP 429, 5xx oder unlesbarer Antwort wachsende Pausen (1 Minute bis 3 Stunden), nur wenn die Pause vor dem Ende des Zeitfensters endet, `Retry-After` wird eingehalten; sonst und bei Zeitüberschreitung, Verbindungsabbruch, HTTP 401, 403 oder 404 Abbruch, neuer Versuch frühestens in der nächsten Nacht | `pipeline/abruf.py` (Kopf), `pipeline/config.py` (`ABRUF_PAUSEN`, `ABRUF_ZEITFENSTER`) |
| User-Agent der Vermessung | `ratsatlas-wuppertal-explore/0.1` mit derselben Projekt- und Kontaktadresse | `explore/abruf.py` (`USER_AGENT`) |
| Stichprobe 2020–2026 | 774 Vorlagen: `underDirectionOf` 663 (86 %), `auxiliaryFile` 771, `mainFile` 0, `location` 0, `keyword` 219 (28 %); Beratungen mit Sitzung, Tagesordnungspunkt und Rolle 100 %; 33 Vorlagenarten. Im Vollabruf `underDirectionOf` bei 7.323 von 8.592 (85 %) | `STUFEN.md`, Stufe 5; Abrufstatistik des Vollabrufs |
| Dokumentabruf (seit 17.11.2026) | 15.777 Dateien der Vorlagen ab 2020, Anlagen von 405 Vorlagen ausgenommen (§ 24 GO NRW und verbundene Vorlagen); tagsüber mindestens 5 s, nachts mindestens 2 s Abstand, keine Abrufe 23–1 Uhr, höchstens 2.000 Dateien am Tag; Erkennung der federführenden Stelle im Kopf: offen | `docs/DOKUMENTE.md`; Abrufprotokoll der Arbeitsumgebung |
