---
name: ratsatlas-wuppertal
description: Arbeitsweise im Repository ratsatlas-wuppertal (Ratsatlas Wuppertal) – Phasen und Freigaben, Abrufpolitik und Sperre der Wuppertaler OParl-API, Messwerkzeuge in explore/, Tests mit lokalem Testserver, Konventionen zu Quellen, Lizenzen (CC BY 4.0, B-Pläne CC BY-ND 4.0), Datenschutz und Volltexten, Pull Requests. Verwenden bei jeder Änderung an pipeline/, site/, explore/, data/, inventur/ oder den Workflows.
---

# ratsatlas-wuppertal – Arbeitsweise

Auftrag, Entscheidungen und offene Punkte stehen in `CLAUDE.md` (Abschnitte 2, 8, 9); Herkunft des Codes in `NOTICE`; Einordnung jeder übernommenen Datei in `inventur/inventur_module.tsv` und `inventur/BERICHT_phase0.md`. Abgeleitet aus dem Skill des Ratsatlas Köln (`daimpad/ratsatlas-koeln` @ `d609111`, `.claude/skills/ratsatlas-koeln/SKILL.md`), der seinerseits auf dem Bonner Skill beruht. Diese Datei beschreibt, **wie** im Repository gearbeitet wird.

## Grundsätze

- **Phasen:** Vor jeder Phase (CLAUDE.md 7) einen kurzen Plan vorlegen und auf Freigabe warten; jede Entscheidung des Auftraggebers mit Datum in CLAUDE.md Abschnitt 9 eintragen. Messstufen in `explore/STUFEN.md` brauchen je eine eigene Freigabe.
- **Quellentreu:** Jede angezeigte Angabe ist auf ihr Quellobjekt (OParl-ID) rückführbar. Abgeleitetes trägt `method`, `confidence`, `evidence`, `source_object`, `geometry_level`. Keine erfundenen URLs, Feldnamen oder Zahlen; Ungemessenes als offen kennzeichnen.
- **Abruf der Stadt:** Anfragen an Server der Stadt Wuppertal (`*.wuppertal.de`, `offenedaten-wuppertal.de`) nur über die Abrufmodule (`pipeline/abruf.py`, in der Exploration `explore/abruf.py`): eine Verbindung, ≥ 2 s Abstand, Zeitfenster 23–1 Uhr, keine Wiederholung bei 429/5xx in der Messung, Weiterleitungen nicht folgen, Verbindungsabbruch = mögliche Sperre, User-Agent mit Projektadresse und Kontakt. Der regelmäßige Abruf (`pipeline/`) ist gesperrt ohne `RATSATLAS_STADT_INFORMIERT=ja` (erst nach Information der Stadt); die Messwerkzeuge in `explore/` ohne `RATSATLAS_MESSUNG_FREIGEGEBEN=ja`, das nur im Befehl einer vom Auftraggeber freigegebenen Stufe steht. Aus der Arbeitsumgebung nie ohne ausdrückliche Freigabe abrufen, auch nicht einzelne Dateien. Objekt-IDs der API beginnen mit `http://`: als Schlüssel unverändert speichern, abrufen über `https://`.
- **Bonner Abruf:** Der kopierte Bonner Code (`pipeline/fetch.py`, `verify.py`, Zusatzthemen) fragt Bonner Server ohne Abrufpolitik ab. Nicht ausführen; Umstellung in Phase 2 (`inventur/BERICHT_phase0.md` 3.2).
- **Datenschutz:** keine Wohnadressen natürlicher Personen; Anregungen und Beschwerden nach § 24 GO NRW nur auf Quartiers- oder Straßenebene; keine Personennamen aus dem System-Objekt, aus `people` oder aus Dokumenten.
- **Volltexte und PDFs:** nur lokal und im Zwischenspeicher (`explore/_cache/`, Workflow-Cache) verarbeiten; keine Zitate, Auszüge oder PDFs im Repository, auf der Seite oder im Datenpaket.
- **Lizenzen:** Namensnennung „Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0“; B-Pläne CC BY-ND 4.0: Geometrien nie vereinfachen, runden oder neu berechnen, nur unverändert anzeigen. OSM (ODbL) nur nachrangig und getrennt gekennzeichnet.
- **Zusatzthemen aus Bonn:** bleiben im Code und werden abgeschaltet (Entscheidung 09.11.2026, CLAUDE.md 9); Schalter nach Kölner Vorbild (`config.ZUSATZTHEMEN`, `data-funktion`) ab Phase 2.
- **Gemeinsamer Kern:** Abweichungen von Köln und Bonn so notieren (Docstring, Bericht), dass eine spätere Zusammenführung möglich bleibt. `daimpad/allris-test` und `daimpad/ratsatlas-koeln` nur lesen.
- **Sprache:** Oberfläche, Kommentare, Berichte und Commit-Nachrichten auf Deutsch, sachlich und ohne Superlative; „Quartier“ und „Stadtbezirk“ in allem, was Leser:innen sehen. Interne Namen aus Bonn (`ortsteil_bez`, `BONN` als Pfadkonstante) bleiben bis zum gemeinsamen Kern.

## Prüfen vor jedem Push

1. `pip install -r requirements.txt pytest` (einmalig), dann `python -m pytest -q tests` – lokaler OParl-Testserver, keine Anfragen an die Stadt. Stand nach Phase 0: in `tests/test_sessionnet.py` schlagen 19 Tests fehl, die an der Einbindung in Bonner `build`, `export` und `net` hängen (Phase 2); mehr dürfen es nicht werden.
2. Messwerkzeuge: `python3 explore/probelauf.py` (nur lokaler Testserver); Anfragezahlen müssen mit `explore/STUFEN.md` übereinstimmen.
3. Ab Phase 4 zusätzlich Seitenprüfung (Playwright, axe, Tastatur) nach Kölner Vorbild.

## Pull Requests

- Arbeitsbranch laut Sitzung; nach jedem Merge von `main` neu ansetzen.
- Claude führt eigene Pull Requests selbst zusammen, sobald sie grün sind (keine Konflikte, keine fehlgeschlagene Prüfung; Entscheidung 09.11.2026). Solange alle Workflows abgeschaltet sind, prüft keine CI – lokale Tests sind dann Pflicht.
- Keine Zugangsdaten im Repository; Netcup/Plesk richtet der Auftraggeber ein.
