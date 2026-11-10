# Mitmachen

Beiträge sind willkommen. Der Ratsatlas Wuppertal ist noch in Vorbereitung (siehe [README](README.md)); Auftrag, Entscheidungen und offene Punkte stehen in [CLAUDE.md](CLAUDE.md).

## Grundsätze

- **Quellentreu.** Keine erfundenen Inhalte, URLs, Feldnamen oder Zahlen. Jede Angabe ist auf ihr Quellobjekt rückführbar (OParl-ID, Fundstelle); Abgeleitetes trägt `method`, `confidence` und `evidence`.
- **Datenschutz.** Keine Verortung von Wohnadressen natürlicher Personen; keine Personennamen aus dem System-Objekt der Schnittstelle oder aus Dokumenten; Anregungen und Beschwerden nach § 24 GO NRW nur auf Quartiers- oder Straßenebene.
- **Abrufpolitik.** Ratsdaten (`oparl.wuppertal.de`) nur über `pipeline/abruf.py` bzw. `explore/abruf.py` (eine Verbindung, mindestens 2 s Abstand, nachts); beide sind ohne Freigabe gesperrt. Strukturdaten nur über `explore/strukturdaten/abruf_struktur.py` (tagsüber, je Host eine Verbindung, mindestens 2 s Abstand, Obergrenze je Host; `oparl.wuppertal.de` und `ris.wuppertal.de` ausgeschlossen). Kein Scraping von `ris.wuppertal.de`. Tests laufen nur gegen lokale Testserver.
- **Nicht ins Repository:** Rohdaten, Volltexte, Zitate, Auszüge oder PDFs der Stadt (Lizenz ungeklärt) und Zugangsdaten jeder Art.
- **Lizenzen.** Neue Quellen mit Lizenz in `pipeline/config.py` (`SOURCES`) und in `data/LICENSE-DATA.md` eintragen. Bebauungspläne (CC BY-ND 4.0) unverändert lassen. Code steht unter MIT.
- **Verständlich.** Die Seite richtet sich an Bürgerinnen und Bürger ohne Verwaltungswissen: Begriffe erklären, WCAG 2.1 AA wahren.

## Ablauf

1. Issue anlegen oder ein vorhandenes übernehmen (Vorlagen: Verortung prüfen, Fehler, Idee).
2. Branch anlegen, ändern, Tests ergänzen; bestehende Tests nicht abschwächen.
3. Lokal prüfen, ohne Anfragen an die Stadt (erfundene Testdaten):
   ```bash
   pip install -r requirements.txt pytest pypdf==6.17.0   # wie .github/workflows/tests.yml
   RATSATLAS_SPERRE=$(mktemp -d) python3 -m pytest -q tests
   (cd tests/browser && npm ci && npx playwright install chromium) && node --test "tests/browser/*.test.mjs"
   ```
4. Pull Request mit kurzer Beschreibung: was, warum, wie geprüft. Der Workflow `tests.yml` prüft jeden Pull Request; zusammengeführt wird erst, wenn er grün ist und keine Konflikte hat.

## Einstiegsaufgaben

- Ausschlussliste der Ortsnamen ergänzen: `explore/ortsnamen_ausschluss.tsv` (z. B. Gremien- und Gebäudenamen ohne Raumbezug).
- Regeln zur Zerlegung der Vorlagenart prüfen: `explore/paperType_regeln.tsv`.
- Offene Punkte aus `CLAUDE.md`, Abschnitt 8.
