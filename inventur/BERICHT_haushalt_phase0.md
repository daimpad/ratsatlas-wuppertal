# Haushalt 2026/2027 – erste Stufe: Bericht

Stand 17.11.2026 · Entscheidungen des Auftraggebers 17.11.2026: Produktbereiche und bezirksbezogene Ansätze, erst
Bericht, dann Seite; öffentlich zusammen mit den Ratsdaten. Werkzeug: `python3 -m pipeline haushalt-wuppertal`
(`pipeline/haushalt_wuppertal.py`), lokal, ohne Netz.

## Quelle

- Haushaltsplan der Stadt Wuppertal 2026/2027, Band 1 (458 Seiten, erstellt 28.07.2026) und Band 2 (961 Seiten,
  erstellt 20.05.2026), vom Auftraggeber in `content/` abgelegt; gelesen wird in dieser Stufe nur Band 1.
- Lizenz: keine Angabe im Dokument; nur das Titelbild trägt „CC BY-NC-ND“ (nicht verwendet). Als Teil der
  Haushaltssatzung vermutlich amtliches Werk (§ 5 UrhG) – Einschätzung, keine Auskunft; Frage an die Stadt offen.

## Ergebnis

| Teil | Inhalt | Prüfung |
|---|---|---|
| Gesamtergebnisplan (S. 96) und 17 Produktbereiche (S. 103–153) | Zeilen 1–18 (ordentliche Erträge, Aufwandsarten, ordentliches Ergebnis), Ergebnis 2023 und 2024, Ansatz 2025–2027, Planung 2028–2030 | Zeilen 1–9 = 10, 11–16 = 17, 10 + 17 = 18 je Produktbereich; Summe der Produktbereiche = Gesamtplan; alle Abweichungen höchstens 2 Euro (Rundung auf ganze Euro) |
| Bezirksbezogene Haushaltsansätze (Anlage 9, S. 326–341) | 292 Zeilen in 10 Bezirksvertretungen: 20 Zeilen Fallgruppe 1 (Verfügungsmittel, Pauschalen), 80 Fallgruppe 2 (Ansätze auf Vorschlag der Verwaltung), 192 Fallgruppe 3 (Maßnahmen); Planung 2026–2030 | keine Summen im Plan; alle Zeilen mit Beträgen gelesen (ungelesene führen zum Abbruch), Zahl je Seite gegen den Text gezählt |

Gesamtergebnisplan, Ansatz 2026: ordentliche Erträge 1.855.595.114 €, ordentliche Aufwendungen −1.946.375.692 €,
ordentliches Ergebnis −90.780.578 €; Ansatz 2027: −80.304.034 €.

Mittel der Fallgruppe 1 je Bezirksvertretung 2026 (Verfügungsmittel und Unterhaltungspauschale): zwischen 60.581 €
(Heckinghausen) und 167.808 € (Barmen).

Verortung der Maßnahmen (Fallgruppe 3) mit dem Ortsnamen-Abgleich der Phase 3, nur als Schätzung: 123 von 192 mit Ort
(64 %), davon 121 im Stadtbezirk der jeweiligen Bezirksvertretung.

Dateien: `data/haushalt/produktbereiche.tsv`, `data/haushalt/bezirke.tsv` (je Betrag mit Datei und Seite),
`data/haushalt/STAND.json` (SHA-256 der Quelle). Keine Personennamen (Band 2 nennt je Produktgruppe eine verantwortliche
Person; nicht gelesen).

## Befunde

- Band 2 beschriftet die Spalten 2026 und 2027 mit „Planung“, Band 1 mit „Ansatz“; Band 2 ist zwei Monate älter.
  Vor einer Verbindung beider Bände (Produktgruppen) zu klären, ob Band 2 ein Entwurfsstand ist.
- Seite 338 ist leer (zwischen Ronsdorf und Uellendahl-Katernberg).
- Fallgruppe 3 nennt Maßnahmen mit Straßen, Brücken und Plätzen („Brücke Fischertal“, „Radweg Hatzfeldtrasse“): der
  räumliche Bezug des Haushalts zu Stadtbezirken und Quartieren.

## Offen (nächster Schritt nach Freigabe)

- Darstellung auf der Seite (Plan zur Freigabe): Haushalt je Produktbereich, Mittel und Maßnahmen je Bezirksvertretung,
  Verknüpfung der Maßnahmen mit Karte und Vorlagen.
- Lizenzfrage an die Stadt; Klärung Band 2.
