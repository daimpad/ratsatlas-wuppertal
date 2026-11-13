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
TODO Messstufe 5: Wuppertaler Vorlagenarten (paperType, z. B. „Antwort auf Anfragen“, „Bericht“, „Gemeinsamer
Antrag …“), Beratungsrollen (z. B. „Entgegennahme o. B.“) und Kürzel ergänzen (Glossar Phase 4).

Beschlussergebnisse (CLAUDE.md 9, 13.11.2026 (4)): Die vier in Messstufe 4 beobachteten Werte von `agendaItem.result`
(Messlauf 5 `sitzungen --seiten 2`, 12.11.2026, `explore/ergebnisse/oparl_laeufe.tsv` und
`explore/ergebnisse/oparl_top_ergebnisse.tsv`) stehen vorn in ERGEBNISSE, mit Beleg in ERGEBNISSE_GEMESSEN; neu ist
„Entgegennahme ohne Beschluss“. Die übrigen Ergebnistexte stammen aus Bonn (allris-test @52fe9ca, Quelle dort
OParl-Lite) und sind in Wuppertal noch nicht beobachtet; sie bleiben für spätere Messungen stehen und tragen in
glossar.json und auf begriffe/ den Hinweis UEBERNOMMEN. Der Abgleich im Frontend ist wörtlich (site/app.js
`glossKeys`: Ergebnis an „ - “ geteilt, Teile getrimmt, exakter Schlüssel), deshalb stehen die Schlüssel genau wie in
der Quelle."""
import re

from . import config, process as proc, topics

ERGEBNISSE = {
    # in Wuppertal beobachtet (ERGEBNISSE_GEMESSEN)
    "ungeändert beschlossen": "Das Gremium hat dem Vorschlag in der vorgelegten Fassung zugestimmt.",
    "geändert beschlossen": "Das Gremium hat zugestimmt, aber mit Änderungen, etwa aus Änderungsanträgen.",
    # Bonner Wortlaut „Die Mehrheit des Gremiums hat dagegen gestimmt.“ ersetzt: abgelehnt ist ein Vorschlag auch bei
    # Stimmengleichheit, ohne dass eine Mehrheit dagegen gestimmt hat
    "abgelehnt": "Der Vorschlag hat in der Abstimmung keine Mehrheit gefunden.",
    # neu (Wuppertal); vorsichtig formuliert: Bedeutung nach der Wuppertaler Geschäftsordnung nicht geprüft (offen),
    # Bezug zur Beratungsrolle „Entgegennahme o. B.“ erst nach Messstufe 5
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
    "Entscheidung": "Dieses Gremium entscheidet abschließend.",
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
ROLLEN = ("Entscheidung", "Empfehlung", "Anhörung", "Kenntnisnahme", "Genehmigung", "Eilentscheidung")

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
    # Schema VO/NNNN/JJ (CLAUDE.md 3.1); wie Folgevorlagen gekennzeichnet sind: TODO Messstufe 5
    ("Vorlagennummer", "Kennung einer Vorlage, in Wuppertal z. B. VO/1380/26.", DATENFELD + ", Feld „reference“"),
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
    ("OB", "Oberbürgermeisterin oder Oberbürgermeister; leitet die Verwaltung und führt den Vorsitz im Rat.",
     "§§ 40, 62 GO NRW"),
    ("BV", "Bezirksvertretung.", "§ 36 GO NRW"),
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
          "TOP": "kuerzel", "GO NRW": "kuerzel", "OB": "kuerzel", "BV": "kuerzel", "HA": "kuerzel",
          "Bebauungsplan": "planung"}  # übrige: vorlagen
# Vorlagenart in den Daten → Begriff. Nur allgemeine Namen; die Bonner Arten sind entfernt. Wuppertaler Arten
# („Beschlussvorlage“ ist in der Stichprobe vom 09.11.2026 belegt, CLAUDE.md 3.1) vollständig nach Messstufe 5;
# unbekannte Arten erzeugen keinen Link
ARTEN = {
    "Stellungnahme der Verwaltung": "Stellungnahme der Verwaltung", "Beschlussvorlage": "Beschlussvorlage",
    "Mitteilungsvorlage": "Mitteilungsvorlage", "Änderungsantrag": "Änderungsantrag", "Antrag": "Antrag",
    "Große Anfrage": "Anfrage", "Kleine Anfrage": "Anfrage",
    "Anregungen und Beschwerden": "Anregungen und Beschwerden (Bürgerantrag)",
    "Dringlichkeitsantrag": "Dringlichkeitsantrag",
}
KUERZEL = {}   # wie Köln; Bonner Kürzel ST, AA, DA entfernt (TODO Messstufe 5)


def anker(begriff):
    """Sprungmarke auf begriffe/: „Stellungnahme der Verwaltung“ → „stellungnahme-der-verwaltung“."""
    s = begriff.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def glossar():
    return {
        "meta": {"note": "Allgemeine Erklärungen ohne Rechtsberatung; Fundstelle je Begriff. Ergebnistexte erscheinen "
                         "wörtlich wie in den Quellen."},
        "ergebnisse": ERGEBNISSE,
        # Beleg je Ergebnistext (ohne Rollen); `ergebnisse` bleibt Text je Schlüssel (site/app.js GLOSSAR)
        "ergebnisse_belege": {k: ergebnis_beleg(k) for k in ERGEBNISSE if k not in ROLLEN},
        "hinweise": proc.NOTES,
        "schritte": SCHRITTE,
        "evidenz": EVIDENZ,
        "staende": STAENDE,
        "themen": dict(topics.THEMES),
        "begriffe": [{"begriff": b, "erklaerung": e, "fundstelle": f, "gruppe": GRUPPE.get(b, "vorlagen"), "anker": anker(b)}
                     for b, e, f in BEGRIFFE],
        "gruppen": dict(GRUPPEN),
        "arten": {art: anker(b) for art, b in ARTEN.items()},
        "kuerzel": {k: anker(b) for k, b in KUERZEL.items()},
    }
