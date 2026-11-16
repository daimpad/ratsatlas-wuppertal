"""Glossar für Seite und Ratsassistent (data/export/glossar.json, eine Quelle für beide).

- ergebnisse: Ergebnistexte und Rollen der Beratung, wie sie wörtlich in den Quellen stehen
- hinweise: Erläuterungen zu Prozessschritten (Schlüssel `note` in den Exporten, process.NOTES)
- schritte, evidenz, staende: Bezeichnungen der Prozessebene (process.py)
- themen: Bezeichnungen der abgeleiteten Themen (topics.py)
- begriffe: allgemeine Begriffe mit Fundstelle (Gemeindeordnung NRW bzw. Datenfeld), je mit Gruppe und Sprungmarke
  für die Seite begriffe/; allgemeine Erklärungen, keine Rechtsberatung
- arten, kuerzel: Vorlagenart bzw. Kürzel der Vorlagennummer → Sprungmarke des Begriffs (Erklärung im Vorgang)

Ergänzt am 02.11.2026 (Phase 0 „Verständlichkeit“, Entscheidungen des Auftraggebers): alle Vorlagenarten der Daten,
Kürzel, Haushalt und Bebauungsplan; einfachere Wörter für eigene Bezeichnungen der Seite („Anstoß“ statt
„Initiierung“, „Umsetzung“ statt „Vollzug“). Wo eine Vorlagenart in keinem Regelwerk beschrieben ist, ist die
Erklärung aus Titeln und Beratungsfolge erschlossen und so gekennzeichnet.

Wuppertal (Phase 2, Teil 6): Bonner Angaben entfernt wie in ratsatlas-koeln @d609111 – Stadt Bonn in den Fundstellen,
die Bonner Bezirke, die aus Bonner Titeln erschlossenen Vorlagenarten (Informationsbrief, Bürgerbrief, Einwohnerfrage,
Beschlussvorlage: Einleitung/Auftrag, Sammelvorlage nichtöffentlicher TOPs), die Kürzel ST/AA/DA der Bonner
Drucksachennummer und die Gruppe „Haushalt“ (Bonner Haushaltspläne; abgeschaltetes Zusatzthema). Abweichung von Köln:
Fundstelle „Geschäftsordnung“ nur als allgemeine Erklärung, solange die Wuppertaler Geschäftsordnung nicht geprüft ist.

Beratungsrollen und Vorlagenarten (CLAUDE.md 9, 13.11. und 16.11.2026): Die in Messstufe 5 beobachteten Rollen
(`consultation.role`, Messlauf 6 `stichprobe --seiten 8`, 13.11.2026, `explore/ergebnisse/oparl_beratungsrollen.tsv`)
stehen in ERGEBNISSE (Schlüssel wörtlich wie in der Quelle, Abgleich im Frontend wie bei den Ergebnissen) und vorn in
ROLLEN, mit Beleg in ROLLEN_GEMESSEN; was die Wuppertaler Geschäftsordnung mit ihnen genau meint, ist nicht geprüft
(OFFEN_ROLLEN). Die Strichreihe, die 24-mal statt einer Rolle steht, ist ein Platzhalter und keine Rolle
(process.rolle). Die Vorlagenarten (`paperType`, `explore/ergebnisse/oparl_papertypen.tsv`) sind nur als Art erklärt,
nicht je Kombination mit Einreichenden und Ebene; art_begriff ordnet einen Wert über pipeline/vorlagenart.py einer Art
zu. Bonner Arten, die in Wuppertal nicht vorkommen, sind nicht neu erklärt; bestehende Einträge bleiben.

Beschlussergebnisse (CLAUDE.md 9, 13.11.2026 (4)): Die vier in Messstufe 4 beobachteten Werte von `agendaItem.result`
(Messlauf 5 `sitzungen --seiten 2`, 12.11.2026, `explore/ergebnisse/oparl_laeufe.tsv` und
`explore/ergebnisse/oparl_top_ergebnisse.tsv`) stehen vorn in ERGEBNISSE, mit Beleg in ERGEBNISSE_GEMESSEN; neu ist
„Entgegennahme ohne Beschluss“. Die übrigen Ergebnistexte stammen aus Bonn (allris-test @52fe9ca, Quelle dort
OParl-Lite) und sind in Wuppertal noch nicht beobachtet; sie bleiben für spätere Messungen stehen und tragen in
glossar.json und auf begriffe/ den Hinweis UEBERNOMMEN. Der Abgleich im Frontend ist wörtlich (site/app.js
`glossKeys`: Ergebnis an „ - “ geteilt, Teile getrimmt, exakter Schlüssel), deshalb stehen die Schlüssel genau wie in
der Quelle."""
import re

from . import config, process as proc, topics, vorlagenart

ERGEBNISSE = {
    # in Wuppertal beobachtet (ERGEBNISSE_GEMESSEN)
    "ungeändert beschlossen": "Das Gremium hat dem Vorschlag in der vorgelegten Fassung zugestimmt.",
    "geändert beschlossen": "Das Gremium hat zugestimmt, aber mit Änderungen, etwa aus Änderungsanträgen.",
    # Bonner Wortlaut „Die Mehrheit des Gremiums hat dagegen gestimmt.“ ersetzt: abgelehnt ist ein Vorschlag auch bei
    # Stimmengleichheit, ohne dass eine Mehrheit dagegen gestimmt hat
    "abgelehnt": "Der Vorschlag hat in der Abstimmung keine Mehrheit gefunden.",
    # neu (Wuppertal); vorsichtig formuliert: Bedeutung nach der Wuppertaler Geschäftsordnung nicht geprüft (offen).
    # Ergebnis eines Tagesordnungspunkts, nicht die Beratungsrolle „Entgegennahme o. B.“ (anderes Feld); ob beide
    # zusammenhängen, ist nicht gemessen
    "Entgegennahme ohne Beschluss": "Das Gremium hat die Vorlage entgegengenommen, also zur Kenntnis erhalten, und dazu "
                                    "keinen Beschluss gefasst.",
    # aus Bonn übernommen, in Wuppertal noch nicht beobachtet (UEBERNOMMEN); „zur Kenntnis genommen“ ist inhaltlich nah
    # an „Entgegennahme ohne Beschluss“, aber ein anderer Wortlaut und bleibt deshalb eigener Schlüssel
    "zur Kenntnis genommen": "Das Gremium wurde informiert; über einen Beschluss wurde nicht abgestimmt.",
    "vertagt": "Die Beratung wurde auf eine spätere Sitzung verschoben.",
    "zurückgezogen": "Die Einreichenden haben die Vorlage zurückgenommen.",
    "verwiesen": "Die Vorlage wurde zur Beratung an ein anderes Gremium weitergegeben.",
    "nicht abgestimmt": "In dieser Sitzung fand keine Abstimmung statt.",
    "ohne Votum": "Das Gremium hat keine Empfehlung abgegeben.",
    "erledigt durch Stellungnahme der Verwaltung": "Der Antrag gilt als erledigt, weil die Verwaltung schriftlich "
                                                   "Stellung genommen hat.",
    "wg. Sitzungsabbruch nicht behandelt (vertagt)": "Die Sitzung wurde abgebrochen, bevor der Punkt beraten wurde; "
                                                      "er gilt als vertagt.",
    "weitere Lesung erforderlich": "Das Gremium hat beraten, aber noch nicht abschließend; der Punkt soll in einer "
                                   "weiteren Sitzung erneut beraten werden.",
    "weitere Lesung": "Das Gremium hat beraten, aber noch nicht abschließend; der Punkt soll in einer weiteren Sitzung "
                      "erneut beraten werden.",
    "bei Anerkennung der Tagesordnung nicht aufgenommen oder vertagt": "Der Punkt wurde zu Beginn der Sitzung von der "
                                                                       "Tagesordnung genommen oder verschoben.",
    "mit Protokollnotiz": "Zusätzlich wurde eine Anmerkung ins Protokoll aufgenommen.",
    "mit Maßgabe": "Der Beschluss gilt mit einer zusätzlichen Bedingung oder Vorgabe.",
    # Beratungsrollen (ROLLEN). In Wuppertal beobachtet (ROLLEN_GEMESSEN): „Entgegennahme o. B.“, „Entscheidung“,
    # „Empfehlung/Anhörung“, „Kenntnisnahme“; allgemein formuliert, Geschäftsordnung nicht geprüft (OFFEN_ROLLEN)
    "Entgegennahme o. B.": "Das Gremium erhält die Vorlage zur Information. „o. B.“ ist hier als „ohne Beschluss“ "
                           "gelesen; danach ist bei dieser Rolle kein Beschluss des Gremiums vorgesehen.",
    "Entscheidung": "Dieses Gremium entscheidet abschließend.",
    "Empfehlung/Anhörung": "Das Gremium berät die Vorlage, bevor ein anderes Gremium entscheidet: Es gibt eine "
                           "Empfehlung ab oder wird angehört. Welche der beiden Formen gemeint ist, unterscheidet die "
                           "Quelle nicht.",
    "Empfehlung": "Das Gremium berät vor und gibt eine Empfehlung an das entscheidende Gremium.",
    "Anhörung": "Das Gremium wird angehört; seine Stellungnahme ist nicht bindend.",
    "Kenntnisnahme": "Das Gremium wird informiert.",
    "Genehmigung": "Das Gremium genehmigt nachträglich eine Dringlichkeits- oder Eilentscheidung.",
    "Eilentscheidung": "Der Hauptausschuss entscheidet anstelle des Rates, weil die Angelegenheit keinen Aufschub duldet.",
}

# Beleg je beobachtetem Ergebnis: Zahl der Tagesordnungspunkte mit diesem `result` in Messlauf 5 (Stufe 4,
# `sitzungen --seiten 2`, 12.11.2026, ergebnis ok; explore/ergebnisse/oparl_laeufe.tsv Zeile 6,
# explore/ergebnisse/oparl_top_ergebnisse.tsv). Grundlage: 200 Sitzungen der ersten zwei Listenseiten, davon 12 vergangen
# mit 63 Tagesordnungspunkten; `result` bei 22 von 63 (explore/STUFEN.md, Ergebnis 12.11.2026). Kein Bezug zur
# Stichprobe der Vorlagen; weitere Werte sind möglich. tests/test_glossar.py vergleicht die Zahlen mit der TSV.
ERGEBNISSE_GEMESSEN = {"ungeändert beschlossen": 18, "geändert beschlossen": 2, "abgelehnt": 1,
                       "Entgegennahme ohne Beschluss": 1}
MESSUNG_ERGEBNISSE = {"messlauf": 5, "stufe": 4, "kommando": "sitzungen --seiten 2", "datum": "2026-11-12",
                      "datei": "explore/ergebnisse/oparl_top_ergebnisse.tsv", "feld": "agendaItem.result",
                      "tops_mit_ergebnis": 22, "tops_insgesamt": 63, "sitzungen_vergangen": 12, "sitzungen": 200}
# Sichtbare Fundstelle (begriffe/, glossar.json); ohne Städtenamen der Herkunft (tests/test_kern_ohne_bonn.py).
# Ohne Zählwerte: begriffe/ wird auch für die Seite ohne Daten gebaut (tools/seite_bauen.py → seo.write), Ratsdaten
# erst nach Phase 3 (CLAUDE.md 9, 13.11.2026); die Zahlen stehen nur in `messung` (glossar.json mit dem Datenexport).
# „seit Juni 2026“: die 12 vergangenen Sitzungen sind die frühesten der 200, `start` ab 15.06.2026 (explore/STUFEN.md,
# Ergebnis 12.11.2026); 12.11.2026 ist der Tag des Abrufs, nicht der Sitzungen.
BEOBACHTET = ("Ratsinformationssystem der Stadt {stadt} (OParl-API), Ergebnis eines Tagesordnungspunkts (Feld "
              "„result“); so beobachtet bei Tagesordnungspunkten aus Sitzungen seit Juni 2026 (abgerufen am 12.11.2026)")
UEBERNOMMEN = ("in {stadt} bisher nicht beobachtet; Wortlaut aus dem Ratsinformationssystem einer anderen Stadt "
               "übernommen, Erklärung allgemein")
OFFEN = {"Entgegennahme ohne Beschluss": "Erklärung allgemein; ob die Geschäftsordnung des Rates den Begriff näher "
                                         "bestimmt, ist noch nicht geprüft"}


def ergebnis_beleg(ergebnis):
    """Beleg eines Ergebnistexts (nicht der Rollen): gemessen (bool), Beschriftung und Text für die Seite
    („Fundstelle“ nur bei beobachteten Ergebnissen, sonst „Herkunft“), Messung mit Zählwerten (nur gemessen)."""
    if ergebnis in ERGEBNISSE_GEMESSEN:
        fund = BEOBACHTET.format(stadt=config.STADT_NAME)
        if ergebnis in OFFEN:
            fund += "; " + OFFEN[ergebnis]
        return {"gemessen": True, "beschriftung": "Fundstelle", "fundstelle": fund,
                "messung": {**MESSUNG_ERGEBNISSE, "anzahl": ERGEBNISSE_GEMESSEN[ergebnis]}}
    return {"gemessen": False, "beschriftung": "Herkunft", "fundstelle": UEBERNOMMEN.format(stadt=config.STADT_NAME)}


SCHRITTE = {
    "initiierung": "Anstoß", "vorbereitung": "Vorbereitung", "veroeffentlichung": "Datum der Vorlage",
    "beratung": "Beratung", "entscheidung": "Entscheidung", "folgevorlage": "Folgevorlage", "vollzug": "Umsetzung",
}

SCHRITTE_TEXT = {
    "initiierung": "Wie das Verfahren angestoßen wurde, etwa durch einen Antrag, eine Anfrage, einen Bürgerantrag oder eine "
                   "Vorlage der Verwaltung.",
    "vorbereitung": "Arbeit der Verwaltung, bevor eine Vorlage erscheint; von außen nicht einsehbar.",
    "veroeffentlichung": "Datum, unter dem die Vorlage im Ratsinformationssystem steht.",
    "beratung": "Ein Gremium berät die Vorlage; das Ergebnis steht wörtlich wie in der Quelle.",
    "entscheidung": "Beratung in dem Gremium, das abschließend entscheidet.",
    "folgevorlage": "Spätere Vorlage zum selben Vorgang, etwa eine Stellungnahme der Verwaltung oder ein Änderungsantrag.",
    "vollzug": "Umsetzung eines Beschlusses durch die Verwaltung; ob und wann sie geschieht, lässt sich aus öffentlichen "
               "Quellen nicht bestimmen.",
}
# Rollen der Beratungsfolge: zuerst die in Wuppertal beobachteten (ROLLEN_GEMESSEN, Reihenfolge nach Häufigkeit), dann
# die aus Bonn übernommenen (in Wuppertal nicht beobachtet, UEBERNOMMEN)
ROLLEN = ("Entgegennahme o. B.", "Entscheidung", "Empfehlung/Anhörung", "Kenntnisnahme",
          "Empfehlung", "Anhörung", "Genehmigung", "Eilentscheidung")
# Beleg je beobachteter Rolle: Zahl der Beratungen (`consultation`) mit dieser `role` in Messlauf 6 (Stufe 5,
# `stichprobe --seiten 8`, 13.11.2026, ergebnis ok; explore/ergebnisse/oparl_laeufe.tsv Zeile 7,
# explore/ergebnisse/oparl_beratungsrollen.tsv). Grundlage: 774 Vorlagen mit `date` 2020–2026 aus 8 Seiten der
# Vorlagenliste (explore/STUFEN.md, Ergebnis 13.11.2026). Dazu 24 Beratungen mit einer Strichreihe statt einer Rolle
# (STRICHREIHE_GEMESSEN; Platzhalter, nicht angezeigt). tests/test_glossar_rollen.py vergleicht die Zahlen mit der TSV.
ROLLEN_GEMESSEN = {"Entgegennahme o. B.": 555, "Entscheidung": 497, "Empfehlung/Anhörung": 429, "Kenntnisnahme": 2}
STRICHREIHE_GEMESSEN = 24
MESSUNG_ROLLEN = {"messlauf": 6, "stufe": 5, "kommando": "stichprobe --seiten 8", "datum": "2026-11-13",
                  "datei": "explore/ergebnisse/oparl_beratungsrollen.tsv", "feld": "consultation.role",
                  "vorlagen": 774, "beratungen": 1507}
# Sichtbare Fundstelle ohne Zählwerte (wie BEOBACHTET); 13.11.2026 ist der Tag des Abrufs
BEOBACHTET_ROLLE = ("Ratsinformationssystem der Stadt {stadt} (OParl-API), Rolle einer Beratung (Feld „role“); so "
                    "beobachtet in einer Stichprobe von Vorlagen aus den Jahren 2020 bis 2026 (abgerufen am 13.11.2026)")
GO_NICHT_GEPRUEFT = "was die Geschäftsordnung des Rates mit der Rolle genau meint, ist noch nicht geprüft"
OFFEN_ROLLEN = {
    "Entgegennahme o. B.": "„o. B.“ als „ohne Beschluss“ gelesen (Lesart aus dem Wortlaut, nicht belegt); "
                           "Erklärung allgemein; " + GO_NICHT_GEPRUEFT,
    "Entscheidung": "Erklärung allgemein; " + GO_NICHT_GEPRUEFT,
    "Empfehlung/Anhörung": "Erklärung allgemein; " + GO_NICHT_GEPRUEFT,
    "Kenntnisnahme": "Erklärung allgemein; " + GO_NICHT_GEPRUEFT,
}


def rolle_beleg(rolle):
    """Beleg einer Beratungsrolle wie ergebnis_beleg: „Fundstelle“ bei beobachteten Rollen (mit dem Hinweis aus
    OFFEN_ROLLEN), sonst „Herkunft“ (übernommen); Zählwerte nur in `messung`."""
    if rolle in ROLLEN_GEMESSEN:
        fund = BEOBACHTET_ROLLE.format(stadt=config.STADT_NAME)
        if rolle in OFFEN_ROLLEN:
            fund += "; " + OFFEN_ROLLEN[rolle]
        return {"gemessen": True, "beschriftung": "Fundstelle", "fundstelle": fund,
                "messung": {**MESSUNG_ROLLEN, "anzahl": ROLLEN_GEMESSEN[rolle]}}
    return {"gemessen": False, "beschriftung": "Herkunft", "fundstelle": UEBERNOMMEN.format(stadt=config.STADT_NAME)}


EVIDENZ = {  # Wortlaut wie in der Legende der Seite
    "belegt": "Als Datenobjekt in der Quelle vorhanden.",
    # Text aus ratsatlas-koeln @d609111 (glossar.py:69): in Wuppertal gibt es kein OParl-Lite (CLAUDE.md 3.2)
    "abgeleitet": "Aus Quelldaten erschlossen (z. B. Verknüpfung von Beratung und Sitzung, Titelmuster).",
    "nicht_öffentlich": "Findet regelmäßig statt, ist von außen aber nicht einsehbar.",
    "unklar": "Ob und wann der Schritt stattfindet, lässt sich aus öffentlichen Quellen nicht bestimmen.",
    "soll": "Nach Regelwerk zu erwarten (vereinfachtes Modell aus Gemeindeordnung, Geschäftsordnung, Satzungen, "
            "Zuständigkeitsordnung und Baugesetzbuch), in den Daten nicht dokumentiert. Das heißt nicht, dass der Schritt fehlt.",
}

STAENDE = {
    "entschieden": "Eine entscheidende Beratung hat ein abschließendes Ergebnis.",
    "beraten, ohne Entscheidung": "Alle Beratungen sind abgeschlossen, keine davon war entscheidend "
                                  "(z. B. Mitteilungen, die zur Kenntnis genommen wurden).",
    "in Beratung": "Mindestens eine Beratung hat ein Ergebnis, andere stehen aus oder wurden vertagt.",
    "offen": "Noch keine Beratung mit Ergebnis.",
    "ohne Beratungsfolge": "Für die Vorlage ist keine Beratung in einem Gremium erfasst.",
}

DATENFELD = f"Ratsinformationssystem der Stadt {config.STADT_NAME} (OParl-API)"
ALLGEMEIN = "allgemeine Erklärung"
# Vorlagenarten aus Messstufe 5 (Messlauf 6, 13.11.2026, explore/ergebnisse/oparl_papertypen.tsv); ohne Zählwerte
ART_BEOBACHTET = (DATENFELD + ", Feld „paperType“; so beobachtet in einer Stichprobe von Vorlagen aus den Jahren 2020 "
                  "bis 2026 (abgerufen am 13.11.2026)")
ART_ALLGEMEIN = ART_BEOBACHTET + "; Erklärung allgemein, die Geschäftsordnung des Rates ist noch nicht geprüft"
ART_ERSCHLOSSEN = ART_BEOBACHTET + "; Erklärung aus dem Wortlaut erschlossen, in keinem geprüften Regelwerk beschrieben"
# Wuppertaler Geschäftsordnung nicht geprüft: bis dahin allgemeine Erklärung (Köln: „Geschäftsordnung des Rates der
# Stadt Köln“); Name bleibt für die Zusammenführung
GESCHO = ALLGEMEIN
# Gruppen der Seite begriffe/ in dieser Reihenfolge (wie Köln ohne die Bonner Gruppe „Haushalt“, mit „Gebiete“)
GRUPPEN = [("vorlagen", "Vorlagen und Vorlagenarten"), ("gremium", "Gremien und Beteiligung"),
           ("verfahren", "Verfahren und Sitzungen"), ("gebiete", "Gebiete"), ("kuerzel", "Kürzel"),
           ("planung", "Planung")]
BEGRIFFE = [
    ("Vorlage", "Schriftstück, über das Rat, Bezirksvertretungen oder Ausschüsse beraten, etwa ein Antrag, eine "
                "Beschlussvorlage oder ein Bürgerantrag.", DATENFELD + ", Objekt „Paper“"),
    # Schema VO/NNNN/JJ (CLAUDE.md 3.1); Zusätze an der Nummer nach Messstufe 5 (pipeline/referenz.py), Bedeutung der
    # Kürzel nicht in der Quelle dokumentiert, daher nur als Annahme
    ("Vorlagennummer", "Kennung einer Vorlage, in Wuppertal z. B. VO/1380/26. Spätere Vorlagen zum selben Vorgang "
                       "tragen oft dieselbe Nummer mit einem Zusatz, etwa „/1-A“ (vermutlich Antwort), „/1-Neuf.“ "
                       "(vermutlich Neufassung) oder „/1-Erg.“ (vermutlich Ergänzung). Die Bedeutung der Zusätze ist "
                       "in der Quelle nicht erläutert; der Ratsatlas ordnet solche Vorlagen ihrer Ausgangsvorlage zu "
                       "und kennzeichnet das als abgeleitet.", DATENFELD + ", Feld „reference“"),
    ("Beschlussvorlage", "Vorlage der Verwaltung mit einem Beschlussvorschlag, über den ein Gremium entscheidet.",
     ALLGEMEIN),
    ("Mitteilungsvorlage", "Vorlage, mit der die Verwaltung ein Gremium informiert; ein Beschluss ist nicht vorgesehen.",
     ALLGEMEIN),
    ("Antrag", "Vorlage einer Fraktion, Gruppe oder eines Mitglieds, mit der ein Gremium um einen Beschluss gebeten "
               "wird.", ALLGEMEIN),
    ("Änderungsantrag", "Antrag, der eine andere Vorlage oder einen anderen Antrag ändern will.", ALLGEMEIN),
    ("Stellungnahme der Verwaltung", "Schriftliche Antwort der Verwaltung, meist auf einen Antrag oder eine Anfrage.",
     ALLGEMEIN),
    ("Anfrage", "Fragen einer Fraktion oder eines Mitglieds an die Verwaltung (Kleine oder Große Anfrage); die "
                "Verwaltung antwortet schriftlich oder in der Sitzung.", ALLGEMEIN),
    # Wuppertaler Vorlagenarten (Messstufe 5). „Antrag“, „Anfrage“ und „Beschlussvorlage“ stehen oben (allgemein)
    ("Große Anfrage", "Anfrage einer Fraktion, einer Gruppe oder eines Mitglieds an die Verwaltung. Die Antwort der "
                      "Verwaltung kann als eigene Vorlage erscheinen (Vorlagenart „Antwort auf Anfragen“).",
     ART_ALLGEMEIN),
    ("Gemeinsamer Antrag", "Antrag, den mehrere Fraktionen oder Gruppen zusammen einreichen. Wer beteiligt ist, nennt "
                           "die Vorlagenart nicht; der Ratsatlas lässt die Einreichenden dann offen.", ART_ALLGEMEIN),
    ("Gemeinsame große Anfrage", "Große Anfrage, die mehrere Fraktionen oder Gruppen zusammen stellen. Wer beteiligt "
                                 "ist, nennt die Vorlagenart nicht; der Ratsatlas lässt die Einreichenden dann offen.",
     ART_ALLGEMEIN),
    ("Bericht", "Vorlage, mit der die Verwaltung ein Gremium über ein Thema oder einen Sachstand unterrichtet. Ob ein "
                "Beschluss vorgesehen ist, zeigt die Rolle in der Beratungsfolge.", ART_ERSCHLOSSEN),
    ("Antwort auf Anfragen", "Vorlage, mit der die Verwaltung schriftlich auf eine Anfrage antwortet. Sie kann als "
                             "Folgevorlage mit der Anfrage verknüpft sein.", ART_ERSCHLOSSEN),
    ("Durchführungsbeschluss", "Beschlussvorlage der Verwaltung; dem Wortlaut nach soll ein Gremium beschließen, dass "
                               "eine Maßnahme ausgeführt wird.", ART_ERSCHLOSSEN),
    ("Grundsatzbeschluss", "Beschlussvorlage der Verwaltung; dem Wortlaut nach soll ein Gremium grundsätzlich über ein "
                           "Vorhaben entscheiden, etwa über Ziel oder Richtung, bevor Einzelheiten beschlossen werden.",
     ART_ERSCHLOSSEN),
    ("Satzungsbeschluss", "Beschlussvorlage der Verwaltung, mit der eine Satzung beschlossen werden soll, etwa ein "
                          "Bebauungsplan. Satzungen beschließt der Rat.", ART_BEOBACHTET + "; §§ 7, 41 GO NRW"),
    ("Einreichende (aus der Vorlagenart abgeleitet)", "In Wuppertal nennt die Vorlagenart oft, wer eine Vorlage "
     "einreicht, etwa „Antrag CDU“ oder „Große Anfrage die Linke“. Der Ratsatlas leitet die Einreichenden daraus ab und "
     "kennzeichnet sie als „aus der Vorlagenart abgeleitet“. Nennt die Vorlagenart keine Namen, etwa bei einem "
     "gemeinsamen Antrag, bleiben die Einreichenden offen. Maßgeblich ist das Original.",
     ART_BEOBACHTET + "; abgeleitet (Ratsatlas)"),
    ("Ebene in der Vorlagenart", "Am Ende der Vorlagenart steht oft, für welches Gremium eine Vorlage bestimmt ist: "
     "„Rat“ für den Rat der Stadt, „BV“ für eine Bezirksvertretung, etwa „Antrag B90/Grüne BV“ oder „Gemeinsamer "
     "Antrag Rat“. Danach folgen manchmal weitere Kürzel wie „AU“ oder „OB“; ihre Bedeutung ist offen. Der Ratsatlas "
     "zeigt sie wörtlich und deutet sie nicht.", ART_BEOBACHTET + "; Bedeutung der Kürzel „AU“ und „OB“ offen"),
    ("Anregungen und Beschwerden (Bürgerantrag)", "Jede Person kann sich schriftlich mit Anregungen oder Beschwerden "
     "in Angelegenheiten der Gemeinde an den Rat oder die Bezirksvertretung wenden, allein oder gemeinsam mit "
     "anderen. Unterschriften weiterer Personen sind dafür nicht nötig. Nicht zu verwechseln mit dem "
     "Einwohnerantrag.", "§ 24 GO NRW"),
    ("Einwohnerantrag", "Einwohnerinnen und Einwohner können beantragen, dass der Rat über eine bestimmte "
     "Angelegenheit berät und entscheidet. Der Antrag braucht die Unterschriften einer Mindestzahl von "
     "Einwohnerinnen und Einwohnern; Einzelheiten regelt die Gemeindeordnung. Nicht zu verwechseln mit dem "
     "Bürgerantrag (Anregungen und Beschwerden).", "§ 25 GO NRW"),
    ("Einwohnerfragestunde", "Zeit in einer Sitzung, in der Einwohnerinnen und Einwohner Fragen stellen können; "
                             "Einzelheiten regelt die Geschäftsordnung.", GESCHO),
    ("Rat", "Gewählte Vertretung der Bürgerinnen und Bürger; er ist für alle Angelegenheiten der Gemeinde zuständig, "
            "soweit nichts anderes bestimmt ist.", "§ 41 GO NRW"),
    # Zahl aus CLAUDE.md 2; Namen der Stadtbezirke erst nach Messstufe G (Gremiennamen Stufe 3/4)
    ("Bezirksvertretung", "Gewählte Vertretung eines Stadtbezirks in kreisfreien Städten. Wuppertal hat zehn "
     "Stadtbezirke und damit zehn Bezirksvertretungen. Sie entscheidet über Angelegenheiten, deren Bedeutung nicht "
     "wesentlich über den Stadtbezirk hinausgeht.", "§§ 36, 37 GO NRW"),
    ("Ausschuss", "Vom Rat gebildetes Gremium, das Beschlüsse vorbereitet oder in übertragenen Angelegenheiten "
                  "selbst entscheidet.", "§§ 41, 57 GO NRW"),
    ("Hauptausschuss", "Pflichtausschuss des Rates; er stimmt die Arbeit der Ausschüsse ab und kann in dringenden "
                       "Fällen anstelle des Rates entscheiden.", "§§ 59, 60 GO NRW"),
    ("Dringlichkeitsentscheidung", "Entscheidung in dringenden Fällen ohne Sitzung des zuständigen Gremiums; sie wird "
     "dem Gremium nachträglich zur Genehmigung vorgelegt.", "§ 60 GO NRW (Rat), § 36 GO NRW (Bezirksvertretung)"),
    ("Fraktion", "Zusammenschluss von Mitgliedern des Rates oder einer Bezirksvertretung.", "§ 56 GO NRW"),
    ("Öffentlichkeit von Sitzungen", "Sitzungen des Rates sind grundsätzlich öffentlich; für einzelne Angelegenheiten "
     "kann die Öffentlichkeit ausgeschlossen werden. Inhalte nichtöffentlicher Beratungen sind nicht einsehbar.",
     "§ 48 GO NRW"),
    ("Federführendes Amt", "Amt der Verwaltung, das eine Vorlage verantwortet.", DATENFELD + ", Feld „underDirectionOf“"),
    ("Beratungsfolge", "Reihenfolge der Gremien, die eine Vorlage beraten, jeweils mit Rolle (Entscheidung, Empfehlung, "
                       "Anhörung, Kenntnisnahme).", DATENFELD + ", Objekt „Consultation“"),
    ("Tagesordnungspunkt", "Punkt der Tagesordnung einer Sitzung; über ihn wird beraten und gegebenenfalls "
                           "abgestimmt. Das Ergebnis steht wörtlich wie im Ratsinformationssystem.",   # ratsatlas-koeln @d609111
     DATENFELD + ", Objekt „AgendaItem“"),
    ("Dringlichkeitsantrag", "Antrag, der ohne die übliche Frist auf die Tagesordnung kommen soll, weil die "
     "Angelegenheit keinen Aufschub duldet; ob er behandelt wird, entscheidet das Gremium.", GESCHO),
    ("Eilentscheidung (Hauptausschuss)", "Entscheidung des Hauptausschusses anstelle des Rates in einer Angelegenheit, "
     "die keinen Aufschub duldet; der Rat genehmigt sie nachträglich.", "§ 60 Abs. 1 GO NRW"),
    ("Stand eines Vorgangs", "Vom Ratsatlas aus der Beratungsfolge abgeleitet: entschieden, beraten ohne "
     "Entscheidung, in Beratung, offen oder ohne Beratungsfolge. Maßgeblich ist das Original.", "abgeleitet (Ratsatlas)"),
    # Gebiete: Zahlen aus CLAUDE.md 2 und 3.2; Namen der Quartiere und Stadtbezirke erst nach Messstufe G
    # Namensnennung nach CLAUDE.md 3.2 (config.NAMENSNENNUNG). Sichtbar heißt die Ebene „Quartier“; Schlüssel und Pfade
    # heißen weiter ortsteil/ortsteile (Kompatibilität mit Bonn/Köln)
    ("Quartier", "Kleinräumige Gliederung der Stadt; Wuppertal hat 69 Quartiere. Der Ratsatlas ordnet Vorlagen mit "
                 "Ortsbezug einem Quartier zu, wo das belegbar ist.", config.NAMENSNENNUNG + ", Datensatz „Quartiere“"),
    ("Stadtbezirk", "Wuppertal ist in zehn Stadtbezirke gegliedert; jeder hat eine Bezirksvertretung.",
     config.NAMENSNENNUNG + " (Lizenz laut Open-Data-Katalog), Datensatz „Stadtbezirke“"),
    # Kürzel (Bonner Kürzel ST, AA, DA der Drucksachennummer entfernt; Wuppertaler Kürzel: TODO Messstufe 5)
    ("TOP", "Tagesordnungspunkt einer Sitzung.", ALLGEMEIN),
    ("GO NRW", "Gemeindeordnung für das Land Nordrhein-Westfalen; sie regelt Aufgaben und Arbeit von Rat, Ausschüssen "
               "und Bezirksvertretungen.", "Gemeindeordnung NRW"),
    ("OB", "Oberbürgermeisterin oder Oberbürgermeister; leitet die Verwaltung und führt den Vorsitz im Rat. Am Ende "
           "einer Vorlagenart (etwa „Antrag DIE LINKE. Rat OB“) ist die Bedeutung offen.", "§§ 40, 62 GO NRW"),
    ("BV", "Bezirksvertretung; am Ende einer Vorlagenart die Ebene (siehe „Ebene in der Vorlagenart“).", "§ 36 GO NRW"),
    ("AU", "Kürzel am Ende mancher Wuppertaler Vorlagenarten, etwa „Antrag FDP / WfW Rat AU“. Die Bedeutung ist offen; "
           "der Ratsatlas zeigt das Kürzel wörtlich und deutet es nicht.", ART_BEOBACHTET + "; Bedeutung offen"),
    ("HA", "Hauptausschuss.", "§ 59 GO NRW"),
    # Planung (Gruppe „Haushalt“ mit den Bonner Haushaltsplänen entfernt; erst mit Freigabe des Zusatzthemas Haushalt)
    ("Bebauungsplan", "Satzung der Gemeinde, die festlegt, wie Grundstücke in einem Gebiet bebaut und genutzt werden "
     "dürfen.", "§§ 8, 10 BauGB"),
]
GRUPPE = {"Rat": "gremium", "Bezirksvertretung": "gremium", "Ausschuss": "gremium", "Hauptausschuss": "gremium",
          "Fraktion": "gremium", "Anregungen und Beschwerden (Bürgerantrag)": "gremium", "Einwohnerantrag": "gremium",
          "Einwohnerfragestunde": "gremium",
          "Dringlichkeitsentscheidung": "verfahren", "Eilentscheidung (Hauptausschuss)": "verfahren",
          "Öffentlichkeit von Sitzungen": "verfahren", "Federführendes Amt": "verfahren", "Beratungsfolge": "verfahren",
          "Tagesordnungspunkt": "verfahren", "Stand eines Vorgangs": "verfahren",
          "Quartier": "gebiete", "Stadtbezirk": "gebiete",
          "TOP": "kuerzel", "GO NRW": "kuerzel", "OB": "kuerzel", "BV": "kuerzel", "HA": "kuerzel", "AU": "kuerzel",
          "Bebauungsplan": "planung"}  # übrige: vorlagen
# Vorlagenart in den Daten bzw. Art nach der Zerlegung (vorlagenart.zerlege) → Begriff. Nur allgemeine Namen; die
# Bonner Arten sind entfernt. Wuppertaler Arten aus Messstufe 5 (explore/ergebnisse/oparl_papertypen.tsv): jede
# gemessene Vorlagenart führt über art_begriff zu einem Begriff; unbekannte Arten erzeugen keinen Link
ARTEN = {
    "Stellungnahme der Verwaltung": "Stellungnahme der Verwaltung", "Beschlussvorlage": "Beschlussvorlage",
    "Mitteilungsvorlage": "Mitteilungsvorlage", "Änderungsantrag": "Änderungsantrag", "Antrag": "Antrag",
    "Große Anfrage": "Große Anfrage", "Kleine Anfrage": "Anfrage", "Anfrage": "Anfrage",
    "Anregungen und Beschwerden": "Anregungen und Beschwerden (Bürgerantrag)",
    "Dringlichkeitsantrag": "Dringlichkeitsantrag",
    # Wuppertal (Messstufe 5); „Gemeinsame Große Anfrage“ ist die Art nach Regel 7, der Wert in der Quelle hat „große“
    "Gemeinsamer Antrag": "Gemeinsamer Antrag", "Gemeinsame große Anfrage": "Gemeinsame große Anfrage",
    "Gemeinsame Große Anfrage": "Gemeinsame große Anfrage", "Bericht": "Bericht",
    "Antwort auf Anfragen": "Antwort auf Anfragen", "Durchführungsbeschluss": "Durchführungsbeschluss",
    "Grundsatzbeschluss": "Grundsatzbeschluss", "Satzungsbeschluss": "Satzungsbeschluss",
}
KUERZEL = {}   # wie Köln; Bonner Kürzel ST, AA, DA entfernt (TODO Messstufe 5)


def art_begriff(paper_type):
    """Begriff zu einer Vorlagenart: wörtlich aus ARTEN, sonst über die Zerlegung („Antrag CDU“ → „Antrag“,
    „Gemeinsamer Antrag BV“ → „Gemeinsamer Antrag“); None, wenn keine Art passt."""
    if paper_type in ARTEN:
        return ARTEN[paper_type]
    z = vorlagenart.zerlege(paper_type)
    return ARTEN.get(z["art"]) if z else None


def anker(begriff):
    """Sprungmarke auf begriffe/: „Stellungnahme der Verwaltung“ → „stellungnahme-der-verwaltung“."""
    s = begriff.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def glossar(paper_types=()):
    """paper_types: Vorlagenarten der Daten (export.export); jede, die über art_begriff zu einem Begriff führt, kommt
    zusätzlich in `arten`, weil die Seite wörtlich nachschlägt (site/app.js `ARTEN[p.paper_type]`)."""
    arten = {art: anker(b) for art, b in ARTEN.items()}
    for pt in paper_types or ():
        b = art_begriff(pt)
        if b and pt not in arten:
            arten[pt] = anker(b)
    return {
        "meta": {"note": "Allgemeine Erklärungen ohne Rechtsberatung; Fundstelle je Begriff. Ergebnistexte erscheinen "
                         "wörtlich wie in den Quellen."},
        "ergebnisse": ERGEBNISSE,
        # Beleg je Ergebnistext (ohne Rollen); `ergebnisse` bleibt Text je Schlüssel (site/app.js GLOSSAR)
        "ergebnisse_belege": {k: ergebnis_beleg(k) for k in ERGEBNISSE if k not in ROLLEN},
        # Beleg je Beratungsrolle (beobachtet in Messstufe 5 oder übernommen)
        "rollen_belege": {k: rolle_beleg(k) for k in ROLLEN},
        "hinweise": proc.NOTES,
        "schritte": SCHRITTE,
        "evidenz": EVIDENZ,
        "staende": STAENDE,
        "themen": dict(topics.THEMES),
        "begriffe": [{"begriff": b, "erklaerung": e, "fundstelle": f, "gruppe": GRUPPE.get(b, "vorlagen"), "anker": anker(b)}
                     for b, e, f in BEGRIFFE],
        "gruppen": dict(GRUPPEN),
        "arten": arten,
        "kuerzel": {k: anker(b) for k, b in KUERZEL.items()},
    }
