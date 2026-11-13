# Anlagen der Vorlagen laden (Schritt `dokumente`)

Grundlage: Entscheidung des Auftraggebers vom 13.11.2026 (Download der Ratsdokumente, Punkt 2). Technik im Kopf von `pipeline/dokumente.py`, Einstellungen in `pipeline/config.py`.

## Was der Schritt tut

- liest `data/raw/papers.jsonl` (erst nach `fetch`) und nimmt alle Dateien aus `auxiliaryFile` der Vorlagen mit `date` ab 01.01.2020;
- lädt jede neue oder geänderte Datei, extrahiert den Text, legt ihn komprimiert unter `data/raw/texte/` ab und löscht das PDF sofort;
- überspringt unveränderte Dateien ohne Anfrage (Fingerabdruck in `data/raw/zustand_dokumente.json`) und setzt nach einem Abbruch oder Neustart dort fort;
- schreibt `data/export/abruf_dokumente.tsv` (je Datei) und `data/export/abrufstatistik_dokumente.tsv` (je Lauf), ohne Dateinamen, Titel oder Text.

Texte, PDFs und Zitate gelangen nie ins Repository, auf die Seite oder ins Datenpaket.

## Erster Lauf (nach dem Vollabruf, aus der Arbeitsumgebung)

```bash
pip install pypdf==6.17.0      # oder pdftotext (poppler-utils)
RATSATLAS_STADT_INFORMIERT=ja RATSATLAS_PDF_FREIGEGEBEN=ja python3 -m pipeline dokumente
```

- Abstand tagsüber (6–23 Uhr) mindestens 5 s, nachts mindestens 2 s; zwischen 23 und 1 Uhr und 13 Minuten davor (ab etwa 22:47 Uhr) startet keine Anfrage (Vorrang des OParl-Abrufs), ein laufender Lauf endet dort ohne Fehler. Eine Pause nach 429/5xx, die in diese Zeit reichte, wird nicht abgewartet: Der Lauf gibt auf und gibt die Sperre frei.
- Je Lauf höchstens 2000 Anfragen und 3 GiB (`RATSATLAS_DOKUMENTE_MAX_DATEIEN`, `RATSATLAS_DOKUMENTE_MAX_BYTES`), auf Wunsch eine Laufzeitgrenze (`RATSATLAS_DOKUMENTE_MAX_SEKUNDEN`); je Kalendertag über alle Läufe höchstens 2000 Anfragen (`RATSATLAS_DOKUMENTE_MAX_TAG`, Annahme bis zur Festlegung durch den Auftraggeber). Danach erneut starten bzw. am nächsten Tag.
- Eine einzelne abgewiesene Datei (HTTP 401/403, HTML-Seite statt PDF, leere oder Text-/JSON-Antwort; etwa eine nicht öffentliche Anlage) wird vermerkt und nach 7 Tagen erneut angefragt, am Ende der Reihenfolge. Zwei neu abgewiesene Dateien in Folge beenden den Lauf als mögliche Sperre.
- Nach einem Abbruch (außer Obergrenze, Vorrang) folgt 12 Stunden kein Lauf. Eine mögliche Sperre (zwei Abweisungen in Folge, HTTP 429 oder 5xx nach Pausen, Verbindungsabbruch, Weiterleitung) pausiert auch den OParl-Abruf. Weiter erst nach Prüfung. Lokale Fehler (Platte voll, fehlende Berechtigung) zählen nicht als Sperre.
- Läuft schon ein Abruf (OParl oder Dokumente), endet ein zweiter Lauf ohne Anfrage und ohne Zustand oder Arbeitsordner zu ändern. SIGTERM (Ende eines Jobs) wird wie Strg+C behandelt: PDF gelöscht, Zustand geschrieben.
- Ergebnis prüfen: letzte Zeile von `data/export/abrufstatistik_dokumente.tsv` (`ende`, `offen`, `zu_gross`, `ohne_text`).

## GitHub Actions

Erst nach der schriftlichen Bestätigung der Stadt einschließlich der Abrufe aus GitHub-Netzen. Der Job braucht pypdf, `RATSATLAS_DOKUMENTE_MAX_SEKUNDEN` unter der Laufzeitgrenze des Jobs, und `data/raw/texte/` sowie `data/raw/zustand_dokumente.json` im Zwischenspeicher (nicht als Artefakt, nicht im Datenpaket), ohne den Arbeitsordner `data/raw/texte/_arbeit/` (dort liegt kurz das PDF in Bearbeitung; nach SIGKILL bleibt es bis zum nächsten Start liegen). Die Abrufprotokolle gehören nicht ungeprüft ins Datenpaket. Noch kein Workflow.

## Schätzung

Dauer ≈ N × (Abstand + Antwortzeit), Platz ≈ N × mittlere Größe eines komprimierten Texts (dazu höchstens ein PDF bis 25 MiB gleichzeitig), geladene Bytes ≈ N × mittlere PDF-Größe. Wegen der Tagesgrenze dauert der erste Abruf mindestens ⌈N / 2000⌉ Kalendertage (`RATSATLAS_DOKUMENTE_MAX_TAG`); 2000 Anfragen brauchen tagsüber bei 5 s Abstand plus Antwortzeit t etwa 2000 × (5 + t) s, bei t = 1 s rund 3,3 Stunden. N = Zahl der Vorlagen ab 2020 (Stufe 3: rund 8.560 nach `created`) × mittlere Zahl der Anlagen je Vorlage (Stufe 5). N, Antwortzeit und Größen liefert Messstufe 5 bzw. 6; bis dahin keine Zahlen.
