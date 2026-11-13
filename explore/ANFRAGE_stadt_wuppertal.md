# Entwurf: Bitte um schriftliche Bestätigung an die Stadt Wuppertal

> Stand 13.11.2026 · Bitte um schriftliche Bestätigung der mündlichen Zusage vom 13.11.2026 (CLAUDE.md 9) mit den Zahlen aus den Messstufen 1–4 (09.–12.11.2026), Belege in der Anlage · Versand nur durch den Auftraggeber, **nach** den Messstufen 5 und 6 (`STUFEN.md`) · **Platzhalter:** **[STUFE 5: …]** und **[STUFE 6: …]** nach der jeweiligen Stufe ausfüllen (`auswertung.py --stufe 5` bzw. `--stufe 6`; Punkt 5: „Erkennungsquote … / abgerufen“, „Richtigkeit der Zuordnung“ (k von n) aus `pdf_koepfe_kontrolle.tsv` – die Quote erst nach dieser Kontrolle eintragen (`STUFEN.md`, Stufe 6, „Manuelle Kontrolle“) –, „Umfang eines PDF-Abrufs (Schätzung)“ (Dateien, MB) und „Neue Dokumente im Monat (Schätzung)“; Anlage: zusätzlich „ohne Textebene“ und „Bytes … Summe“); **[PHASE 2: …]** mit dem im Adapter gewählten Sicherheitsabstand hinter Grenzseite 87 ausfüllen (CLAUDE.md 9, 13.11.2026, Phase 2); Zahl der Nächte und Summe der Anfragen im zweiten Absatz neu zählen (`ergebnisse/oparl_laeufe.tsv`, Spalte `netz`); übrige Platzhalter in eckigen Klammern · **Bedingung für den Versand:** Punkt 3 beschreibt das Verfahren als geplant (Phase 2, CLAUDE.md 9, 13.11.2026). Stand 13.11.2026 leistet der Adapter es noch nicht: `pipeline/sessionnet.py` hängt `modified_since` unkodiert an (`_mit_parametern`; diese Form war in Stufe 2 wirkungslos, `oparl_kennzahlen.tsv`), liest die Vorlagenliste ohne Zeitgrenze bis zum Listenende (`liste`) und bricht bei unwirksamem Filter nicht ab (`_filter_wirksam` schreibt nur in die Statistik). Den Satz mit den Zahlen zum inkrementellen Abruf („Danach …“) nur versenden, wenn der Adapter bis dahin `modified_since` URL-kodiert sendet, nach `created` bis Seite 87 plus Sicherheitsabstand liest und bei unwirksamem Filter abbricht; sonst den Satz ohne Zahlen als geplantes Verfahren stehen lassen und keinen laufenden Abruf behaupten · **Versand vor dem ersten Vollabruf** (Nacht 16./17.11.2026): Punkt 3 bleibt im Futur; die Seitenzahl der Sitzungsliste bleibt „noch unbekannt“ (gemessen nur Seiten 1–2, `oparl_listen.tsv`) · **Versand danach:** Punkt 3 in die Vergangenheit setzen und die tatsächlichen Seitenzahlen eintragen · abgeleitet aus `ANFRAGE_stadt_koeln.md` in `daimpad/ratsatlas-koeln`

**An:** offenedaten@stadt.wuppertal.de (Open Data, Amt 402); Ratsbüro, 001.13 [E-Mail-Adresse des Ratsbüros]; statistik@stadt.wuppertal.de (Statistik, Funktionsadresse laut Open-Data-Katalog; nur Punkt 6)
**Betreff:** Ratsatlas Wuppertal – Bitte um schriftliche Bestätigung der Zusage vom 13.11.2026 (OParl-Schnittstelle, Lizenz, Abrufverfahren)

Sehr geehrte Damen und Herren,

vielen Dank für Ihre mündliche Zustimmung vom 13. November 2026 zum ehrenamtlichen „Ratsatlas Wuppertal“ (geplant unter wuppertal.ratsatlas.de, Quellcode offen unter https://github.com/daimpad/ratsatlas-wuppertal). Er soll Bürger:innen helfen, Vorlagen des Rates und der Bezirksvertretungen ab 2020 nach Ort, Stand der Beratung und Zuständigkeit zu finden; jede Angabe verweist auf das Original in Ihrem Ratsinformationssystem.

Vorab habe ich die Schnittstelle `oparl.wuppertal.de` in vier Nächten vom 9. bis 12. November 2026 **[STUFE 5/6: Zeitraum und Zahl der Nächte ergänzen]** mit zusammen 22 Anfragen **[STUFE 5/6: Summe neu zählen]** vermessen (Anlage). Ich bitte Sie, folgende Punkte schriftlich zu bestätigen oder zu berichtigen:

1. **Umfang der Zusage**, wie ich ihn verstanden habe: (a) regelmäßiger Abruf der OParl-Schnittstelle; (b) Veröffentlichung der Ratsdaten mit Namensnennung; (c) Auswertung der PDF-Volltexte. Ich gehe davon aus, dass (b) auch daraus abgeleitete Angaben umfasst (Ortsbezug, Beratungsverlauf, federführende Stelle, einreichende Fraktionen); bitte bestätigen Sie das. Bis zu einer schriftlichen Lizenz veröffentliche ich aus den Dokumenten keine Zitate oder Auszüge und spiegele sie nicht, sondern verlinke sie.
2. **Lizenz und Namensnennung:** Das Feld `license` ist im System- und im Body-Objekt leer (`null`). Welche Lizenz bzw. Nutzungsbedingungen gelten für die OParl-Objekte und die verlinkten PDF-Dokumente, und welche Namensnennung wünschen Sie? Vorgesehen ist „Datenquelle: Stadt Wuppertal“ mit Link auf das Original. Wäre es möglich, das Feld `license` zu befüllen?
3. **Abrufverfahren (geplant):** Erster Vollabruf in der Nacht vom 16. auf den 17. November 2026 aus derselben Arbeitsumgebung wie die Messungen: Body, Organisationsliste (3 Seiten), Vorlagenliste bis zur Grenze 2020 (87 Seiten zu je 100 Vorlagen, nach den gemessenen Antwortzeiten etwa 9 bis 10 Minuten, dazu ein Sicherheitsabstand von **[PHASE 2: Zahl]** Seiten) und die vollständige Sitzungsliste (Seitenzahl noch unbekannt, da nicht nach Datum sortiert). Personen (`people`) werden nicht abgerufen. Danach täglich nur geänderte Objekte (`modified_since`); in der Messung ergab der Filter für rund sechseinhalb Tage eine Seite mit 36 Vorlagen. Immer eine Verbindung, mindestens zwei Sekunden Abstand, nur zwischen 23 und 1 Uhr; Verhalten bei Fehlern siehe Anlage. Wünschen Sie ein anderes Zeitfenster oder eine andere Rate?
4. **Abruf aus GitHub Actions:** Der tägliche Abruf kommt aus wechselnden, geteilten Rechenzentrums-IP-Bereichen von GitHub, mit dem User-Agent `ratsatlas-wuppertal/<Version> (+https://github.com/daimpad/ratsatlas-wuppertal; contact@nozilla.de)`. Ist das für Sie in Ordnung, oder wünschen Sie eine Alternative (etwa eine feste Adresse)?
5. **PDF-Dokumente:** Bei etwa **[STUFE 5: Zahl]** % der Vorlagen ab 2020 fehlt die federführende Stelle (`underDirectionOf`). In einer einmaligen Prüfung von **[STUFE 6: Zahl]** Dokumenten (rund **[STUFE 6: Zahl]** MB) fand sich im Kopf eine Dienststellenkennung (etwa „Amt …“, „Ressort …“ oder „Stadtbetrieb …“) bei **[STUFE 6: Zahl]** von **[STUFE 6: Zahl]** (**[STUFE 6: Zahl]** %); bei einer Stichprobenkontrolle war sie in **[STUFE 6: k von n]** Fällen richtig zugeordnet. Geplant ist, einmalig das Vorlagendokument der Verwaltungsvorlagen ab 2020 ohne diese Angabe abzurufen (etwa **[STUFE 6: Zahl]** Dokumente, rund **[STUFE 6: Zahl]** MB), danach etwa **[STUFE 6: Zahl]** neue im Monat. Später sollen für die Ortsbestimmung auch Dokumente von Vorlagen ausgewertet werden, deren Ort sich anders nicht bestimmen lässt (Umfang noch offen). Alle Abrufe mit derselben Rate und im selben Zeitfenster.
6. **Statistik je Quartier:** Gibt es Bevölkerungs- und Sozialdaten (z. B. Einwohner, Altersstruktur, SGB-II-Quote) je Quartier oder statistischem Bezirk als CSV oder XLSX unter offener Lizenz, oder ließen sie sich im Open-Data-Portal veröffentlichen? Statistik-Info und Statistik-Datenbank ließen sich bei meinen automatisierten Abrufen nicht laden (HTTP 403, Ursache ungeklärt). Angezeigt würden die Werte neutral, mit Quelle und Stichtag, ohne Rangfolgen.

Außerdem bitte ich um Auskunft zu vier Fragen:

- **HTTP 401:** Seite 250 der Vorlagenliste antwortete am 11.11.2026 um 23:09 Uhr mit HTTP 401 ohne Inhalt (Seite 240 war gefüllt). Liegt die Seite hinter dem Listenende, oder ist das eine Zugangsbeschränkung? Seiten in diesem Bereich frage ich nicht mehr ab.
- **Kürzel „AU“:** Was bedeutet „AU“ in Vorlagenarten wie „Antrag FDP / WfW Rat AU“, und gibt es eine Liste der Vorlagenarten und Kürzel?
- **Organisationsliste:** Wie sind „Jobcenter Wuppertal“, „Regionalbüro“, „UWG“, „BEG“, „AWG“, „DIE GRAUEN - Graue Panther-“, „Klinikum Wuppertal“ und „Stadthalle Wuppertal“ einzuordnen: als Dienststelle der Stadt, als Beteiligung bzw. eigene Einrichtung oder als Gruppe im Rat? Wofür stehen die drei Kürzel?
- **Bebauungspläne:** Auf offenedaten-wuppertal.de stehen die Bebauungspläne unter CC BY-ND 4.0, Open.NRW nennt „Andere geschlossene Lizenz“. Welche Angabe gilt? Die Geometrien würde ich nur unverändert anzeigen.

Bis zu Ihrer schriftlichen Bestätigung kennzeichne ich die Lizenz der Ratsdaten auf der Seite als „mündlich zugesagt, schriftlich ausstehend“. Für Rückfragen stehe ich gern zur Verfügung.

Mit freundlichen Grüßen
[Name]
contact@nozilla.de [ggf. Telefon]

---

## Anlage: Messergebnisse

Gemessen am 9., 10., 11. und 12. November 2026 jeweils zwischen 23:08 und 23:15 Uhr **[STUFE 5/6: ergänzen]**, mit einer Verbindung und mindestens zwei Sekunden Abstand. Belege im Repository unter `explore/ergebnisse/` (Messprotokolle als TSV) und in `explore/STUFEN.md` (Abschnitte „Ergebnis“).

| Messgröße | Ergebnis | Beleg |
|---|---|---|
| Anfragen | 22 in 5 Läufen; 4 Läufe ohne Auffälligkeit, 1 Lauf endete mit HTTP 401 (siehe Frage) | `oparl_laeufe.tsv` (`netz`, `ergebnis`) |
| Antwortzeiten | Vorlagenseiten 3,94–4,61 s (12 Seiten); Vorlagen mit kodiertem `modified_since` 2,05 s; Sitzungen 1,59–1,95 s; Organisationen 0,67–1,83 s; System 0,72 s, Body 0,52 s | `STUFEN.md`, Stufe 1–4 |
| Seitengröße | 100 Objekte je Seite; eine Vorlagenseite 212.012–315.892 Bytes | `oparl_kennzahlen.tsv`; Spanne aus dem lokalen Abrufprotokoll (nicht im Repository) |
| Lizenzfelder | `license` in System und Body `null`; `licenseValidSince` 24.04.2020 | `oparl_kennzahlen.tsv` |
| `modified_since` | unkodiert ohne Wirkung, URL-kodiert wirksam (36 Vorlagen seit 2026-11-04T08:45:43+00:00, Abruf 10.11.2026); über mehrere Seiten und bei Löschungen nicht gemessen | `oparl_kennzahlen.tsv` |
| Grenze 2020 | Vorlagen absteigend nach `created` sortiert (nicht nach `date`); Grenzseite 87, Seiten 1–86 rund 8.560 Vorlagen mit `created` ab 01.01.2020 | `oparl_umfang.tsv`, `oparl_umfang_seiten.tsv` |
| Sicherheitsabstand | offen: 14 Vorlagen auf Seite 86 und 7 auf Seite 87 mit `date` ab 2020, aber `created` davor; Seiten 88–99 nicht gemessen | `oparl_umfang_seiten.tsv` |
| Listenende | offen: Seite 240 gefüllt (mindestens 24.000 Vorlagen), Seite 250 HTTP 401 | `oparl_laeufe.tsv` Lauf 3 |
| Organisationen | 240 auf 3 Seiten, Listenende erreicht; Präfix `at` 95, `gr` 145 | `oparl_listen.tsv`, `oparl_organisationen.tsv` |
| Sitzungen | Gesamtzahl offen; nicht nach `start` sortiert, daher vollständig zu lesen | `oparl_sitzungen.tsv`, `oparl_sitzungen_seiten.tsv` |
| Umfang erster Abruf (Vorlagen) | 87 Seiten: etwa 8,6–9,6 Minuten (je Seite 2 s Abstand plus 3,94–4,61 s), rund 18–28 MB | Rechnung aus „Antwortzeiten“ und „Seitengröße“ |
| Fehlerverhalten (geplanter Abruf) | nach HTTP 429, 5xx oder unlesbarer Antwort wachsende Pausen (1 Minute bis 3 Stunden), nur wenn die Pause vor dem Ende des Zeitfensters endet, `Retry-After` wird eingehalten; sonst und bei Zeitüberschreitung, Verbindungsabbruch, HTTP 401, 403 oder 404 Abbruch, neuer Versuch frühestens in der nächsten Nacht | `pipeline/abruf.py` (Kopf), `pipeline/config.py` (`ABRUF_PAUSEN`, `ABRUF_ZEITFENSTER`) |
| User-Agent der Vermessung | `ratsatlas-wuppertal-explore/0.1` mit derselben Projekt- und Kontaktadresse | `explore/abruf.py` (`USER_AGENT`) |
| Stichprobe 2020–2026 | **[STUFE 5: Abdeckung `underDirectionOf`, `auxiliaryFile`, `keyword`, `location`; Vorlagenarten und Beratungsrollen]** | `oparl_stichprobe_*.tsv` |
| PDF-Köpfe | **[STUFE 6: abgerufene Dokumente, MB, Erkennungsquote, Richtigkeit laut Kontrolle, ohne Textebene]** | `pdf_koepfe.tsv`, `pdf_koepfe_kontrolle.tsv` |
