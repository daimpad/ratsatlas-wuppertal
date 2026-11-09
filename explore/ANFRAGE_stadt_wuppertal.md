# Entwurf: Anfrage an die Stadt Wuppertal

> Stand 09.11.2026 · zur Versendung durch den Auftraggeber **nach** den Messstufen (`STUFEN.md`, CLAUDE.md 9) · Platzhalter in eckigen Klammern; Zahlen aus `explore/ergebnisse/` eintragen (Punkt 5 aus der Auswertung Stufe 6, `auswertung.py --stufe 6`: „Erkennungsquote … / abgerufen“ (Kennung nach Regel gefunden, bezogen auf abgerufene Dokumente), „Richtigkeit der Zuordnung“ (manuelle Kontrolle, `pdf_koepfe_kontrolle.tsv`, vorher eintragen), „ohne Textebene“, „Bytes … Summe“ und „Neue Dokumente im Monat (Schätzung)“) · abgeleitet aus `ANFRAGE_stadt_koeln.md` in `daimpad/ratsatlas-koeln`

**An:** offenedaten@stadt.wuppertal.de (Open Data, Amt 402); Ratsbüro, 001.13 [E-Mail-Adresse des Ratsbüros]
**Betreff:** Nutzung der OParl-Schnittstelle für ein zivilgesellschaftliches Informationsangebot („Ratsatlas Wuppertal“) – Lizenz, Abrufrate und Zeitfenster

Sehr geehrte Damen und Herren,

ich entwickle ehrenamtlich den „Ratsatlas Wuppertal“ (geplante Adresse wuppertal.ratsatlas.de, Quellcode offen unter https://github.com/daimpad/ratsatlas-wuppertal). Das Angebot soll Bürger:innen ohne Verwaltungswissen helfen, Vorlagen des Rates und der Bezirksvertretungen ab 2020 räumlich (Stadtbezirk, Quartier, Straße), zeitlich (Stand der Beratung) und nach Zuständigkeit zu finden. Jede Angabe verweist auf das Original in Ihrem Ratsinformationssystem. Vergleichbare Angebote gibt es für Bonn und Köln.

Um den Aufwand für Ihre Server abschätzen zu können, habe ich die Schnittstelle `oparl.wuppertal.de` zwischen dem [Datum] und dem [Datum] in [Zahl] kleinen Stufen vermessen: zusammen [N] Anfragen, nachts zwischen 23 und 1 Uhr, mit einer Verbindung und mindestens zwei Sekunden Abstand. Dabei habe ich rund [Zahl] Vorlagen insgesamt und rund [Zahl] Vorlagen ab dem 01.01.2020 gezählt. Bevor ich einen regelmäßigen Abruf einrichte, möchte ich Sie informieren und fünf Punkte klären:

1. **Lizenz:** Das Feld `license` des Body-Objekts ist leer, und im Open-Data-Portal habe ich keinen Datensatz zur OParl-Schnittstelle gefunden. Unter welcher Lizenz stehen die OParl-Objekte und die über `accessUrl`/`downloadUrl` verlinkten Dokumente (PDF)? Die Open-Data-Dienstanweisung der Stadt vom 18.10.2019 und die Teilnahme Wuppertals am OParl-Pilot von Open.NRW (2017) lassen eine offene Lizenz erwarten. Unabhängig davon werde ich die Quelle immer mit „Datenquelle: Stadt Wuppertal“ angeben.
2. **Abgeleitete Daten:** Darf ich aus den Daten abgeleitete Angaben veröffentlichen? Gemeint sind Ortsbezüge (Stadtbezirk, Quartier, Straße), Beratungsverläufe, die federführende Stelle und die einreichenden Fraktionen. Die Dokumente selbst würde ich nicht spiegeln, sondern nur verlinken; aus den PDFs würden keine Textauszüge veröffentlicht.
3. **Abrufrate und Zeitfenster:** Geplant sind eine Verbindung zur Zeit, mindestens zwei Sekunden Abstand zwischen zwei Anfragen und Abrufe nur nachts zwischen 23 und 1 Uhr; nach dem ersten Abzug nur geänderte Objekte (`modified_since`), und nur Vorlagen ab dem 01.01.2020. Der erste Abzug umfasst nach der Vermessung etwa [Zahl] Anfragen über [Zahl] Nächte, danach je Nacht etwa [Zahl]. Nach Serverfehlern würde mit wachsenden Pausen wiederholt; bei Zeitüberschreitungen oder Verbindungsabbrüchen bricht der Abruf bis zur nächsten Nacht ab. Entspricht das Ihren Vorgaben, oder bevorzugen Sie ein anderes Zeitfenster oder eine andere Rate? Gibt es für den ersten Abzug einen Massenexport?
4. **Absender:** Der regelmäßige Abruf erfolgt aus GitHub Actions, also aus Rechenzentrums-IP-Bereichen, die wechseln und von vielen Nutzern geteilt werden, mit dem User-Agent `ratsatlas-wuppertal/<Version> (+https://github.com/daimpad/ratsatlas-wuppertal; [Kontaktadresse])`. Ist das für Sie tragbar, oder wünschen Sie einen Abruf von einer festen Adresse?
5. **Dokumente:** Bei etwa [Zahl] % der Vorlagen ab 2020 ist keine federführende Stelle (`underDirectionOf`) angegeben. Ob sie sich aus dem Kopf der Verwaltungsvorlagen ergänzen lässt, habe ich im Rahmen der Vermessung einmalig an [Zahl] PDF-Dokumenten geprüft (zusammen rund [Zahl] MB, nachts, eine Verbindung, mindestens zwei Sekunden Abstand). Eine Angabe der Form „Amt …“ oder „Ressort …“ fand sich im Kopf bei [Zahl] von [Zahl] abgerufenen Dokumenten ([Zahl] %); bei einer Kontrolle von [Zahl] dieser Treffer war die Stelle in [Zahl] Fällen richtig zugeordnet. Bei [Zahl] Dokumenten fehlte eine Textebene. Die Dokumente liegen nur lokal bei mir; veröffentlicht würde nur die erkannte Stelle, kein Text und keine Namen. Für den weiteren Abruf bitte ich um Ihre Zustimmung: nur das Vorlagendokument neuer Verwaltungsvorlagen ohne Angabe der federführenden Stelle, nach meiner Schätzung etwa [Zahl] Dokumente im Monat, im selben Zeitfenster und mit derselben Rate wie oben. Ist das gestattet, und wenn ja, in welchem Umfang?

Außerdem zwei Rückfragen:

- **Vorlagenarten:** Die Vorlagenart (`paperType`) nennt oft die Einreichenden und die Ebene, etwa „Antrag FDP / WfW Rat AU“. Was bedeutet das Kürzel „AU“, und gibt es eine Liste der verwendeten Vorlagenarten und Kürzel?
- **Bebauungspläne:** Die Datensätze zu rechtsverbindlichen und laufenden Bebauungsplänen stehen auf offenedaten-wuppertal.de unter CC BY-ND 4.0; Open.NRW nennt dagegen „Andere geschlossene Lizenz“. Welche Angabe gilt? Ich würde die Geometrien nur unverändert anzeigen.

Wäre es zudem möglich, das Body-Feld `license` mit der geltenden Lizenz zu befüllen?

Den regelmäßigen Abruf richte ich erst nach Ihrer Antwort ein; bis dahin stelle ich keine weiteren Anfragen an die Schnittstelle. Für Rückfragen stehe ich gern zur Verfügung.

Mit freundlichen Grüßen
[Name]
[Kontaktadresse, ggf. Telefon]
