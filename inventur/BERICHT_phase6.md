# Bericht Phase 6 – Verifikation

Stand 24.11.2026 (erneute Verifikation ergänzt). Plan freigegeben am 23.11.2026 (CLAUDE.md 9). Grundlage: nächtlicher Lauf von `pages.yml` am 23.11.2026 (Start 23:12 Uhr, Schritt „Verifikation gegen die OParl-API“ 23:25–23:27 Uhr), Ergebnis aus dem Datenpaket der Hauptadresse (`export/verifikation_oparl.json`, `.tsv`, `verifikation_pruefliste.tsv`).

## 1. Stichprobe gegen die OParl-API

| Angabe | Wert |
|---|---|
| Stichprobe (Startwert 20261123) | 50 Vorlagen |
| geprüft | 50 |
| in allen Feldern übereinstimmend | 47 |
| abweichend | 3 |
| seit dem Abruf geändert | 0 |
| nicht gefunden (HTTP 404) | 0 |
| Ende | vollständig, kein Abbruch |
| Anfragen an die Stadt | 50 (je Vorlage eine) |

Geprüft wurden je Vorlage 7 Felder (350 Vergleiche): Nummer, Titel, Datum, Vorlagenart, Federführung, Zahl der Beratungen und Anlagen. 347 stimmen überein. Nummer, Titel, Datum, Vorlagenart, Federführung und Anlagen stimmen in allen 50 Vorlagen.

### Abweichungen: Zahl der Beratungen

| Drucksache | Ratsatlas | OParl-API |
|---|---|---|
| VO/1139/24 | 1 | 2 |
| VO/0373/23 | 4 | 7 |
| VO/1420/22 | 2 | 3 |

**Ursache im Code, nicht in der Quelle.** Wuppertal verwendet dieselbe Beratungskennung (`consultation.id`) erneut, wenn eine Vorlage in einer späteren Sitzung wieder beraten wird, etwa nach einer Vertagung; Sitzung und TOP sind dann andere. Die Datenbank (`pipeline/build.py`) führte die Kennung als Primärschlüssel. Deshalb überschrieb die spätere Sitzung die frühere, und in der Prozesslinie fehlte die frühere Station. Im lokalen Abrufstand betrifft das 505 Vorlagen und 745 von 18.130 Beratungseinträgen (4,1 %).

**Behoben** (`sessionnet.beratung_schluessel`): Jede Wiederholung einer Kennung innerhalb einer Vorlage erhält den Zusatz „#2“, „#3“ usw. Adapter (`beratungen.jsonl`) und Aufbau verwenden dieselben Schlüssel. Die Kennung wird nicht exportiert. Tests: `tests/test_verifikation.py` (Ende-zu-Ende mit wiederholter Kennung, Verifikation stimmt danach überein).

Wirksam wurde die Behebung mit dem nächtlichen Abruf vom 24.11.2026, der `beratungen.jsonl` neu schrieb.

### Erneute Verifikation am 24.11.2026

Auf Knopfdruck (`pages.yml` mit „abruf“ und „verifikation“, 23:42–23:57 Uhr) nach dem nächtlichen Lauf; neue Stichprobe mit Startwert 20261124:

| Angabe | Wert |
|---|---|
| geprüft | 50 von 50 |
| in allen Feldern übereinstimmend | 50 |
| abweichend, seit dem Abruf geändert, nicht gefunden | 0 |
| Ende | vollständig, kein Abbruch |
| Anfragen an die Stadt | 50 für die Verifikation, dazu 133 für den vorangehenden Abruf |

Die Prüfliste im Datenpaket (`export/verifikation_pruefliste.tsv`, 20 Vorlagen) stammt aus dieser Stichprobe und zeigt die vollständige Beratungsfolge.

Abweichend von Köln und Bonn: Dort gibt es keine wiederholten Kennungen. Das ist für den gemeinsamen Kern notiert.

## 2. Linkprüfung

Lauf vom 23.11.2026 mit den Ratsdaten (`inventur/audit_links.tsv`):

- 55.212 Verweise geprüft;
- 50.144 davon ok;
- 5.068 nicht geprüft: Server der Stadt und `mailto:`;
- kein Fehler.

## 3. Namensnennung und Quellen

`tools/seite_bauen.namensnennung_pruefen` prüft bei jedem Bau zweierlei:

- Jede ausgelieferte HTML-Seite trägt die Namensnennung der Geodaten.
- Seiten aus Ratsdaten nennen zusätzlich die Quelle.

Der Lauf vom 23.11.2026 bestand diese Prüfung.

Im Datenpaket stehen beide Namensnennungen und der Lizenzvermerk der Ratsdaten („mündlich zugesagt, schriftlich ausstehend“) in `LIESMICH.txt` und `LICENSE-DATA.md`.

## 4. Offen

- **Abgleich von Hand mit ris.wuppertal.de:** `export/verifikation_pruefliste.tsv` im Datenpaket enthält 20 Vorlagen (Nummer, Titel, Datum, Beratungsfolge, Link zur ersten Anlage, Spalten für Urteil und Anmerkung). Den Abgleich übernimmt der Auftraggeber; Abrufe von ris.wuppertal.de aus der Pipeline gibt es nicht (CLAUDE.md 6). Grundlage ist die Prüfliste vom 24.11.2026.
- Schriftliche Bestätigung und Lizenz der Ratsdaten (CLAUDE.md 8).
