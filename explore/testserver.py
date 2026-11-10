"""Lokaler OParl-Testserver mit erfundenen Daten für Probeläufe der Messstufen (explore/STUFEN.md).

Abgeleitet aus ratsatlas-koeln @d609111 (explore/testserver.py), umgestellt auf die Wuppertaler Antwortform laut
CLAUDE.md 3.1 (Stichprobe vom 09.11.2026). Keine Daten der Stadt Wuppertal: Namen tragen „[Testdaten]“, alle Adressen
zeigen auf 127.0.0.1 (in Tests auch eine andere Loopback-Adresse wie 127.0.0.2, Parameter `host`). Nachgebildet ist nur,
was CLAUDE.md 3.1 nennt:
- System …/oparl/system → Body …/oparl/bodies/0001 („Instance 0001“, ohne `license`, `legislativeTerm`, `location`);
  das System nennt ein erfundenes `contactEmail` und `contactName` (Prüfung: Kontaktwerte gelangen in keine
  Ergebnisdatei)
  mit den Listen …/papers, …/meetings, …/organizations, …/people; 100 Objekte je Seite
- Paginierung über links.next mit `?page=N`; eine Seite hinter der letzten ist leer (Wuppertal: „Seite 250 leer“);
  Folgeseiten übernehmen alle Parameter ohne URL-Kodierung
- Objekt-IDs mit http:// (hier ohnehin, der Testserver spricht nur http)
- Vorlagen absteigend nach `created`; `date` einige Tage später (erfundene Abstände; Wuppertal laut Stufe 1 am
  10.11.2026: erste Seite nicht nach `date`, aber nach `created` sortiert, CLAUDE.md 9), daher Verletzungen der
  Reihenfolge nach `date`; `reference` im Schema VO/NNNN/JJ; `paperType` aus den Beispielen in CLAUDE.md 3.1
  (dazu eine erkennbar erfundene Art, die keine Regel trifft); `underDirectionOf` → organizations/at/<n>;
  `consultation` eingebettet mit direktem Verweis auf `meeting` und `agendaItem` und `role` (u. a. „Entgegennahme o. B.“);
  `keyword` bei einem Teil; nur `auxiliaryFile` mit accessUrl …/downloadfiles/a/<n>.pdf und downloadUrl
  …/downloadfiles/<n>.pdf (kleine PDF-Datei mit erfundenem Kopf in acht Varianten, pdf_kopf; Fehlervarianten wie
  404, defekte, große Datei oder HTML über Testserver.pdf_variante); bei einer Datei heißt sie „[Testdaten] Vorlage“,
  bei mehreren steht die Vorlage (Art und Referenz im Namen) zwischen zwei Anlagen; kein `location`, kein `mainFile`
- Organisationen unter organizations/gr/<n> (Gremien) und organizations/at/<n> (Ämter); dazu der erkennbar erfundene
  Präfix `zz`, um die Zählung weiterer Präfixe zu prüfen
Erfunden sind Mengen, Verteilungen, Namen, Nummern, Pfade der Dateien und Kennungen der Vorlagen, Sitzungen und TOPs
sowie die Werte von `organizationType` und `agendaItem.result`. Die Zahl der Vorlagen (24 550, letzte Seite 246) und
die Lage der Grenze 01.01.2020 nach `created` (Seite um 72) folgen nur der Größenordnung aus CLAUDE.md 3.1 (Seite 240 gefüllt,
Seite 250 leer; Grenze geschätzt zwischen Seite 50 und 150). Ob Wuppertal Gesamtzahlen in `pagination` liefert, ist offen
(Parameter `gesamtzahlen`, Vorgabe ohne). URL-kodierte Parameter (%3A, %2B …) ergeben HTTP 404 wie bei SessionNet in
Wuppertal laut meine-stadt-transparent (Stand ca. 2021, heutige Gültigkeit offen; Quelle
explore/ergebnisse/sessionnet_befunde.tsv in ratsatlas-koeln), mit
`kodierte_parameter="dekodieren"` werden sie wie in Köln (Stufe 2, 08.11.2026) dekodiert angewandt.
Welche Felder, Typen und Mengen die Stadt tatsächlich liefert, ist offen; das messen die Stufen. Erfunden sind auch die
Abstände `date` − `created` (VERSATZ, Ausreißer von 30 Tagen bei k % 50 == 7, −1 Tag bei k % 97 == 0, dadurch
Vorlagen mit `created` knapp vor 2020 und `date` ab 2020); `created` der Vorlagen um 10 Uhr Ortszeit, also mit
wechselndem Offset +01:00/+02:00; mit `date_versatz=False` gilt `date` = Tag von `created`
(Liste auch nach `date` sortiert, wie vor der Messung von Stufe 1 angenommen).

Die Vorlagen werden erst beim Ausliefern einer Seite erzeugt (Vorlage k = 0 ist die jüngste); Filter laufen über
einfache Kennwerte je k.

Aufruf: python3 explore/testserver.py [--port 8765]   (Ende mit Strg+C)
"""
import argparse
import datetime as dt
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

SEITE = 100
VORLAGEN = 24_550            # letzte Seite 246 (50 Vorlagen), Seite 247 leer
AELTESTES_DATUM = dt.date(2003, 1, 2)
JUENGSTES_DATUM = dt.date(2026, 11, 7)   # fest, damit Seitennummern in Tests und Probelauf gleich bleiben
SITZUNGEN = 600              # 6 Seiten
GREMIEN, AEMTER, WEITERE = 580, 60, 10   # 650 Organisationen, 7 Seiten
PERSONEN = 300               # 3 Seiten
OPARL = "https://schema.oparl.org/1.1/"
# Vorlagenarten: Muster aus CLAUDE.md 3.1; die Zuordnung zu Vorlagen ist erfunden. Index k % 10.
# erfundene Abstände date − Tag von created in Tagen, Index k % 8 (Wuppertal: Abstand ungemessen, siehe Stufe 3)
VERSATZ = (3, 0, 7, 1, 5, 2, 9, 4)
VERSATZ_AUSREISSER = 30      # k % 50 == 7
VERSATZ_NEGATIV = -1         # k % 97 == 0 (date vor created)
ARTEN_VERWALTUNG = ("Beschlussvorlage", "Beschlussvorlage", "Beschlussvorlage", "Bericht", "Bericht",
                    "Antwort auf Anfragen")
ARTEN_POLITIK = ("Antrag CDU", "Antrag B90/Grüne BV", "Gemeinsamer Antrag BV", "Gemeinsamer Antrag Rat",
                 "Große Anfrage die Linke", "Antrag FDP / WfW Rat AU", "[Testdaten] Sonstige Vorlage")
ROLLEN = ("Entgegennahme o. B.", "[Testdaten] Rolle B")
ERGEBNISSE = ("[Testdaten] Ergebnis A", "[Testdaten] Ergebnis B", None)
KODIERT = ("404", "dekodieren")


def _zeit(wert):
    return dt.datetime.fromisoformat(wert.replace("Z", "+00:00"))


def _pdf_text(z: str) -> str:
    return z.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf(seiten, metadaten=None) -> bytes:
    """Kleine PDF-Datei, lesbar für pypdf: je Seite eine Liste von Textzeilen (Helvetica, WinAnsiEncoding); eine leere
    Liste ergibt eine Seite ohne Textebene (nur eine graue Fläche, wie ein Scan ohne Texterkennung). Eine Zeichenkette
    statt einer Liste gilt als eine Seite mit einer Zeile. `metadaten`: Einträge des Info-Wörterbuchs (z. B. Producer)."""
    if isinstance(seiten, str):
        seiten = [[seiten] if seiten else []]
    objekte = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    kinder = []
    for zeilen in seiten:
        if zeilen:
            inhalt = ("BT /F1 11 Tf 56 780 Td 14 TL " + " ".join(f"({_pdf_text(z)}) Tj T*" for z in zeilen)
                      + " ET").encode("latin-1")
        else:
            inhalt = b"0.9 g 56 600 480 180 re f"
        objekte.append(b"<< /Length %d >>\nstream\n" % len(inhalt) + inhalt + b"\nendstream")
        objekte.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                       b"/Resources << /Font << /F1 3 0 R >> >> >>" % len(objekte))
        kinder.append(len(objekte))
    objekte[1] = (b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kinder)
                  + b"] /Count %d >>" % len(kinder))
    info = b""
    if metadaten:
        objekte.append(b"<< " + b" ".join(b"/%s (%s)" % (k.encode(), _pdf_text(v).encode("latin-1"))
                                          for k, v in metadaten.items()) + b" >>")
        info = b" /Info %d 0 R" % len(objekte)
    aus, positionen = bytearray(b"%PDF-1.4\n"), []
    for nr, o in enumerate(objekte, 1):
        positionen.append(len(aus))
        aus += b"%d 0 obj\n" % nr + o + b"\nendobj\n"
    xref = len(aus)
    aus += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)
    for p in positionen:
        aus += b"%010d 00000 n \n" % p
    aus += b"trailer\n<< /Size %d /Root 1 0 R%s >>\nstartxref\n%d\n%%%%EOF\n" % (len(objekte) + 1, info, xref)
    return bytes(aus)


# erfundene Bearbeiterangaben im Kopf (Variante 2): dürfen in keiner Ergebnisdatei und keiner Ausgabe erscheinen
BEARBEITUNG = ("[Testdaten] Bearbeitung: Erika Erfunden-Musterfrau", "[Testdaten] Telefon 0202 99 88 77 66",
               "E-Mail erika.erfunden@pdf-test.invalid")
PDF_VARIANTEN = 8


def pdf_kopf(nr: int):
    """Erfundener Inhalt der Datei <nr> als (Seiten, Metadaten), Variante nr % 8. Wuppertaler Kopfformate sind
    ungemessen; die Varianten prüfen nur die Erkennung: 0 ein Kandidat (Ressort aus der Ämterliste), 1 mehrere
    verschiedene (Geschäftsbereich und Ressort), 2 mehrere gleiche mit erfundenen Bearbeiterangaben (Name, Telefon,
    E-Mail, auch als Autor in den Metadaten), 3 Kandidat nur nach dem Abschnitt, 4 Text ohne Kandidat, 5 ohne
    Textebene, 6 Seite 1 leer und Kopf auf Seite 2, 7 Silbentrennung „Stadt-“/„betrieb 999“ (ohne Gegenstück in der
    Ämterliste)."""
    r = 901 + nr % AEMTER
    word, scan = {"Producer": "[Testdaten] Microsoft Word"}, {"Producer": "[Testdaten] Scanner"}
    return ((([["[Testdaten] Stadt Beispiel", f"Ressort {r}", "[Testdaten] Beschlussvorlage", "Beschlussvorschlag",
                "[Testdaten] Der Rat beschliesst."]], word),
             ([["[Testdaten] Geschäftsbereich 99", f"Ressort {r}", "Beschlussvorschlag", "[Testdaten] Text"]], word),
             ([[f"Amt {r}", *BEARBEITUNG, f"Amt {r}", "Begründung", "[Testdaten] Text"]],
              {**word, "Author": BEARBEITUNG[0]}),
             ([["[Testdaten] Vorlage ohne Kopfangabe", "Begründung", f"[Testdaten] siehe Ressort {r}"]], {}),
             ([["[Testdaten] Vorlage ohne Kopfangabe"]], {"Producer": "[Testdaten] Ghostscript"}),
             ([[]], scan),
             ([[], [f"Ressort {r}", "Sachverhalt", "[Testdaten] Text"]], scan),
             ([["[Testdaten] Stadt-", "betrieb 999", "Beschlussvorschlag"]], {}))[nr % PDF_VARIANTEN])


# Fehlervarianten einer Datei (Testserver.pdf_variante): HTTP 404, defekte Datei, große Datei (gültige PDF mit
# Füllkommentar, Testserver.pdf_gross_bytes), HTML statt PDF (Sperr- oder Fehlerseite), andere Datei (kein PDF)
DEFEKT = b"%PDF-1.4\n%[Testdaten] defekt\n1 0 obj\n<<"
FEHLERVARIANTEN = ("404", "defekt", "gross", "html", "anderes")


class Daten:
    """Erfundene Objekte; deterministisch (`created` der Vorlagen fest vom 02.01.2003 bis 07.11.2026, `date` einige
    Tage später, mit `date_versatz=False` gleich dem Tag von `created`) bis auf die Änderungszeitpunkte der jüngsten 100
    Vorlagen (in den letzten 100 Stunden, für modified_since)."""

    def __init__(self, basis, vorlagen=VORLAGEN, gesamtzahlen=False, date_versatz=True):
        self.basis, self.anzahl, self.gesamtzahlen = basis, vorlagen, gesamtzahlen
        self.date_versatz = date_versatz
        self.system_url = f"{basis}/oparl/system"
        self.body_url = f"{basis}/oparl/bodies/0001"
        self.jetzt = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.juengstes = JUENGSTES_DATUM
        self.spanne = (self.juengstes - AELTESTES_DATUM).days
        self.alle_geaendert = None   # Zeitpunkt: alle Vorlagen seither geändert (Tests)
        self.ordnung = None          # Reihenfolge der Vorlagen (Liste von k); None: k aufsteigend (created absteigend)
        b = self.body_url
        self.organisationen = []
        for praefix, n_max in (("at", AEMTER), ("zz", WEITERE), ("gr", GREMIEN)):   # Reihenfolge erfunden
            for n in range(1, n_max + 1):
                o = {"id": f"{b}/organizations/{praefix}/{n}", "type": OPARL + "Organization", "body": b,
                     "created": "2020-04-24T08:00:00+02:00", "modified": "2025-11-01T08:00:00+01:00"}
                if praefix == "gr":
                    o.update(name=f"[Testdaten] Gremium {n}", shortName=f"Gr {n}")
                    if n % 10:
                        o["organizationType"] = "[Testdaten] Gremium"
                elif praefix == "at":
                    o.update(name=f"[Testdaten] Ressort {900 + n} Beispiel", shortName=f"R {900 + n}",
                             organizationType="[Testdaten] Verwaltung")
                else:
                    o.update(name=f"[Testdaten] Weitere Organisation {n}")
                self.organisationen.append(o)
        self.personen = [{"id": f"{b}/people/{n}", "type": OPARL + "Person", "body": b,
                          "name": f"[Testdaten] Person {n}", "created": "2020-04-24T08:00:00+02:00",
                          "modified": "2025-11-01T08:00:00+01:00"} for n in range(1, PERSONEN + 1)]
        self.sitzungen = []
        for n in range(1, SITZUNGEN + 1):
            tag = dt.date(2020, 1, 6) + dt.timedelta(days=4 * (n - 1))
            mid = f"{b}/meetings/{n}"
            tops = [{"id": f"{b}/agendaitems/{n}-{t}", "type": OPARL + "AgendaItem", "meeting": mid,
                     "number": f"{t}", "name": f"[Testdaten] Tagesordnungspunkt {t}", "public": (n + t) % 7 != 0,
                     **({"result": ERGEBNISSE[(n + t) % len(ERGEBNISSE)]} if ERGEBNISSE[(n + t) % len(ERGEBNISSE)]
                        else {})}
                    for t in range(1, 4 + n % 6)]
            self.sitzungen.append({
                "id": mid, "type": OPARL + "Meeting", "name": f"[Testdaten] Sitzung {n}",
                "start": f"{tag.isoformat()}T17:00:00+01:00", "end": f"{tag.isoformat()}T20:00:00+01:00",
                "organization": [f"{b}/organizations/gr/{1 + n % GREMIEN}"], "agendaItem": tops,
                "created": f"{tag.isoformat()}T08:00:00+01:00", "modified": f"{tag.isoformat()}T21:00:00+01:00"})
        for liste in (self.sitzungen, self.organisationen, self.personen):
            for o in liste:
                o["_c"], o["_m"] = _zeit(o["created"]), _zeit(o["modified"])

    # --- Kennwerte je Vorlage k (k = 0 jüngste) ---
    def erstellt_tag(self, k):
        """Tag von `created` (Ortszeit); absteigend in k."""
        return self.juengstes - dt.timedelta(days=k * self.spanne // self.anzahl)

    def versatz(self, k):
        """Erfundener Abstand `date` − Tag von `created` in Tagen (0 ohne date_versatz)."""
        if not self.date_versatz:
            return 0
        if k % 97 == 0:
            return VERSATZ_NEGATIV
        if k % 50 == 7:
            return VERSATZ_AUSREISSER
        return VERSATZ[k % len(VERSATZ)]

    def datum(self, k):
        """`date` der Vorlage k: Tag von `created` plus versatz(k); nicht monoton in k."""
        return self.erstellt_tag(k) + dt.timedelta(days=self.versatz(k))

    def erstellt(self, k):
        """`created`: 10 Uhr Ortszeit Europe/Berlin, also +01:00 im Winter und +02:00 im Sommer (erfunden)."""
        return dt.datetime.combine(self.erstellt_tag(k), dt.time(10), BERLIN)

    def geaendert(self, k):
        if self.alle_geaendert is not None:
            return self.alle_geaendert
        if k < 100:   # die jüngsten Vorlagen in den letzten 100 Stunden geändert
            return self.jetzt - dt.timedelta(hours=k + 1)
        return self.erstellt(k) + dt.timedelta(days=5)

    def vorlage(self, k):
        b, nr = self.body_url, self.anzahl - k
        pid = f"{b}/papers/{nr}"
        art = (ARTEN_VERWALTUNG[k % 10] if k % 10 < 6
               else ARTEN_POLITIK[(k % 10 - 6 + 4 * (k // 10)) % len(ARTEN_POLITIK)])
        datum = self.datum(k)
        p = {"id": pid, "type": OPARL + "Paper", "body": b, "name": f"[Testdaten] Vorlage {nr}",
             "reference": f"VO/{nr % 10000:04d}/{datum.year % 100:02d}", "paperType": art,
             "date": datum.isoformat(), "created": self.erstellt(k).isoformat(),
             "modified": self.geaendert(k).isoformat()}
        if (k // 10) % 3:
            p["underDirectionOf"] = [f"{b}/organizations/at/{1 + k % AEMTER}"]
        if k % 20 < 7:
            p["keyword"] = [f"[Testdaten] Schlagwort {k % 5}"]
        n = 1 + k % 3   # eine Datei: „Vorlage“; mehrere: Anlage 1, Vorlage mit Art und Referenz, Anlage 2
        namen = (["[Testdaten] Vorlage"] if n == 1 else
                 ["[Testdaten] Anlage 1", f"[Testdaten] {art} {p['reference']}", "[Testdaten] Anlage 2"][:n])
        p["auxiliaryFile"] = [self._datei(3 * nr + j, name) for j, name in enumerate(namen)]
        if k % 9:
            m = self.sitzungen[k % SITZUNGEN]
            p["consultation"] = [{"id": f"{b}/consultations/{nr}-{j}", "type": OPARL + "Consultation",
                                  "paper": pid, "meeting": m["id"],
                                  "agendaItem": m["agendaItem"][(k + j) % len(m["agendaItem"])]["id"],
                                  "organization": m["organization"], "role": ROLLEN[(k + j) % len(ROLLEN)]}
                                 for j in range(1 + k % 2)]
        return p

    def _datei(self, nr, name):
        b = self.body_url
        return {"id": f"{b}/files/{nr}", "type": OPARL + "File", "name": name,
                "fileName": f"{nr}.pdf", "mimeType": "application/pdf",
                "accessUrl": f"{b}/downloadfiles/a/{nr}.pdf", "downloadUrl": f"{b}/downloadfiles/{nr}.pdf"}

    @property
    def vorlagen(self):
        """Alle Vorlagen in Listenreihenfolge (nur für Tests; erzeugt jede Vorlage)."""
        return [self.vorlage(k) for k in self.reihenfolge()]

    def reihenfolge(self):
        return self.ordnung if self.ordnung is not None else range(self.anzahl)

    def grenzseite(self, stichtag=dt.date(2020, 1, 1)):
        """Erste Seite, deren Vorlagen alle `created` vor dem Stichtag haben (bei Reihenfolge nach k)."""
        k = next(k for k in range(self.anzahl) if self.erstellt_tag(k) < stichtag)
        return k // SEITE + (1 if k % SEITE == 0 else 2)

    def system(self):
        return {"id": self.system_url, "type": OPARL + "System", "oparlVersion": OPARL,
                "name": "[Testdaten] Lokaler OParl-Testserver", "body": f"{self.basis}/oparl/bodies",
                "vendor": "[Testdaten]", "product": "[Testdaten]",
                "contactEmail": "testperson.erfunden@example.invalid", "contactName": "[Testdaten] Kontaktperson"}

    def body(self):
        b = self.body_url
        return {"id": b, "type": OPARL + "Body", "system": self.system_url, "name": "[Testdaten] Instance 0001",
                "license": "", "paper": f"{b}/papers", "meeting": f"{b}/meetings",
                "organization": f"{b}/organizations", "person": f"{b}/people",
                "created": "2020-04-24T08:00:00+02:00", "modified": "2026-01-01T08:00:00+01:00"}

    def listen(self):
        b = self.body_url
        return {f"{b}/papers": None, f"{b}/meetings": self.sitzungen,
                f"{b}/organizations": self.organisationen, f"{b}/people": self.personen}


class Testserver:
    """Startet den Server in einem Hintergrund-Thread. `anfragen`: Liste (Pfad, Abfrage, User-Agent, Status);
    `eingang`: Eingangszeit je Anfrage, `ausgang`: Zeit unmittelbar vor dem Senden des letzten Bytes der Antwort
    (früher kann der Client die Antwort nicht vollständig gelesen haben; ein Zeitpunkt nach dem Senden käme bei
    mehreren Server-Threads im selben Prozess je nach Zuteilung einige Millisekunden zu spät); beide time.monotonic,
    für alle Prozesse derselben Maschine vergleichbar.
    `stoerung(pfad, abfrage)` darf einen Statuscode liefern (z. B. 429); `verzoegerung` in Sekunden je Antwort (oder
    eine Funktion (pfad, abfrage) → Sekunden);
    `weiterleitungen`: Pfad → (Status, Ziel) für Antworten mit Location-Kopf (z. B. 301);
    `ohne_created_filter` / `ohne_modified_filter`: created_* bzw. modified_* werden ignoriert;
    `kodierte_parameter`: „404“ (Vorgabe) oder „dekodieren“;
    `abschneiden(pfad)`: True sendet nur die Hälfte des Inhalts bei vollem Content-Length und schließt die Verbindung
    (abgeschnittene Antwort). `pdf_variante(nr)`: None (Vorgabe: Inhalt nach pdf_kopf) oder eine der
    FEHLERVARIANTEN für die Datei <nr> („404“, „defekt“, „gross“ mit `pdf_gross_bytes` Füllbytes, „html“, „anderes“).
    `host`: 127.0.0.1 (Vorgabe) oder eine andere Loopback-Adresse wie 127.0.0.2, die
    oparl_messung.lokal() nicht als lokal ansieht (Tests der Regeln für Anfragen an die Stadt ohne Netz).
    Weitere Parameter gehen an Daten (`vorlagen`, `gesamtzahlen`, `date_versatz`)."""

    def __init__(self, port=0, host="127.0.0.1", **kw):
        assert host.startswith("127."), "nur Loopback-Adressen"
        self.anfragen = []
        self.eingang = []
        self.ausgang = []
        self.stoerung = lambda pfad, abfrage: None
        self.abschneiden = lambda pfad: False
        self.verzoegerung = 0.0
        self.weiterleitungen = {}
        self.ohne_created_filter = False
        self.ohne_modified_filter = False
        self.kodierte_parameter = "404"
        self.pdf_variante = lambda nr: None
        self.pdf_gross_bytes = 300_000
        self.server = ThreadingHTTPServer((host, port), self._handler())
        self.basis = f"http://{host}:{self.server.server_address[1]}"
        self.daten = Daten(self.basis, **kw)
        self.system_url, self.body_url = self.daten.system_url, self.daten.body_url
        self._thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()

    def start(self):
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def antwort(self, pfad, abfrage):
        """(Status, Inhaltstyp, Bytes) für eine Anfrage."""
        assert self.kodierte_parameter in KODIERT
        d = self.daten
        if "%" in abfrage:
            if self.kodierte_parameter == "404":   # wie SessionNet in Wuppertal laut meine-stadt-transparent (ca. 2021)
                return 404, "text/html", b"<html><body>Not Found</body></html>"
            abfrage = unquote(abfrage)
        q = dict(x.partition("=")[::2] for x in abfrage.split("&") if x)   # „+“ bleibt „+“
        url = d.basis + pfad
        if url == d.system_url:
            return 200, "application/json", json.dumps(d.system()).encode()
        if url == d.body_url:
            return 200, "application/json", json.dumps(d.body()).encode()
        if url.startswith(f"{d.body_url}/downloadfiles/") and url.endswith(".pdf"):
            try:
                nr = int(url.rsplit("/", 1)[1][:-4])
            except ValueError:
                return 404, "text/html", b"<html><body>Not Found</body></html>"
            return self._pdf_antwort(nr)
        listen = d.listen()
        if url not in listen:
            return 404, "text/html", b"<html><body>Not Found</body></html>"
        try:
            filter_q = {k: v for k, v in q.items() if not (self.ohne_created_filter and k.startswith("created_"))
                        and not (self.ohne_modified_filter and k.startswith("modified_"))}
            if listen[url] is None:   # Vorlagen: Kennwerte je k, Objekte erst für die Seite
                ks = self._filtern_vorlagen(filter_q)
                return 200, "application/json", json.dumps(self._seite(ks, url, q, d.vorlage)).encode()
            objekte = self._filtern(listen[url], filter_q)
            return 200, "application/json", json.dumps(self._seite(objekte, url, q)).encode()
        except ValueError:
            return 400, "text/html", b"<html><body>Bad Request</body></html>"

    def _pdf_antwort(self, nr):
        """(Status, Inhaltstyp, Bytes) der Datei <nr>: Fehlervariante (pdf_variante) oder Inhalt nach pdf_kopf."""
        variante = self.pdf_variante(nr)
        assert variante in (None, *FEHLERVARIANTEN), variante
        if variante == "404":
            return 404, "text/html", b"<html><body>Not Found</body></html>"
        if variante == "defekt":
            return 200, "application/pdf", DEFEKT
        if variante == "html":
            return 200, "text/html", b"<!DOCTYPE html><html><body>[Testdaten] Anmeldung</body></html>"
        if variante == "anderes":
            return 200, "application/octet-stream", b"PK\x03\x04[Testdaten] keine PDF-Datei"
        inhalt = pdf(*pdf_kopf(nr))
        if variante == "gross":
            inhalt += b"%" + b"0" * self.pdf_gross_bytes + b"\n"
        return 200, "application/pdf", inhalt

    @staticmethod
    def _grenzen(q):
        aus = []
        for name, feld, vergleich in (("created_since", "c", 1), ("created_until", "c", -1),
                                      ("modified_since", "m", 1), ("modified_until", "m", -1)):
            if name in q:
                grenze = _zeit(q[name])
                if grenze.tzinfo is None:
                    raise ValueError(name)
                aus.append((feld, vergleich, grenze))
        return aus

    def _filtern_vorlagen(self, q):
        d, grenzen = self.daten, self._grenzen(q)
        ks = list(d.reihenfolge())
        for feld, vergleich, grenze in grenzen:
            wert = d.erstellt if feld == "c" else d.geaendert
            ks = [k for k in ks if (wert(k) >= grenze if vergleich > 0 else wert(k) <= grenze)]
        return ks

    def _filtern(self, objekte, q):
        for feld, vergleich, grenze in self._grenzen(q):
            schluessel = "_" + feld
            objekte = [o for o in objekte if (o[schluessel] >= grenze if vergleich > 0 else o[schluessel] <= grenze)]
        return objekte

    def _seite(self, objekte, url, q, erzeugen=None):
        seite = int(q.get("page", "1"))
        if seite < 1:
            raise ValueError(seite)
        gesamt = max(1, -(-len(objekte) // SEITE))
        rest = {k: v for k, v in q.items() if k != "page"}

        def link(n):   # unverändert, ohne URL-Kodierung
            return url + "?" + "&".join(f"{k}={v}" for k, v in {**rest, "page": n}.items())

        def adresse(werte):
            return url + ("?" + "&".join(f"{k}={v}" for k, v in werte.items()) if werte else "")
        teil = objekte[(seite - 1) * SEITE: seite * SEITE]   # hinter der letzten Seite: leer
        teil = [erzeugen(k) for k in teil] if erzeugen else [{k: v for k, v in o.items() if not k.startswith("_")}
                                                              for o in teil]
        links = {"first": adresse(rest), "self": adresse(q)}
        if seite < gesamt:
            links["next"] = link(seite + 1)
        pagination = {"elementsPerPage": SEITE, "currentPage": seite}
        if self.daten.gesamtzahlen:
            pagination.update(totalElements=len(objekte), totalPages=gesamt)
            links["last"] = link(gesamt)
            if 1 < seite <= gesamt:
                links["prev"] = link(seite - 1)
        return {"data": teil, "pagination": pagination, "links": links}

    def _handler(self):
        server = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                teile = urlsplit(self.path)
                status, ziel = server.stoerung(teile.path, teile.query), None
                if teile.path in server.weiterleitungen:
                    status, ziel = server.weiterleitungen[teile.path]
                    typ, inhalt = "text/html", b"<html><body>Moved</body></html>"
                elif status:
                    typ, inhalt = "text/html", b"<html><body>Fehler (Testserver)</body></html>"
                else:
                    status, typ, inhalt = server.antwort(teile.path, teile.query)
                server.anfragen.append((teile.path, teile.query, self.headers.get("User-Agent"), status))
                server.eingang.append(time.monotonic())
                pause = (server.verzoegerung(teile.path, teile.query) if callable(server.verzoegerung)
                         else server.verzoegerung)
                if pause:
                    time.sleep(pause)
                self.send_response(status)
                if ziel:
                    self.send_header("Location", ziel)
                self.send_header("Content-Type", typ)
                self.send_header("Content-Length", str(len(inhalt)))
                if server.abschneiden(teile.path):   # Verbindung mitten im Inhalt schließen
                    inhalt = inhalt[:len(inhalt) // 2]
                    self.close_connection = True
                if not inhalt:
                    server.ausgang.append(time.monotonic())
                    self.end_headers()
                else:
                    self.end_headers()
                    self.wfile.write(inhalt[:-1])
                    self.wfile.flush()
                    server.ausgang.append(time.monotonic())   # vor dem letzten Byte (siehe Testserver.ausgang)
                    self.wfile.write(inhalt[-1:])
                    self.wfile.flush()

        return H


def main():
    ap = argparse.ArgumentParser(description="Lokaler OParl-Testserver mit erfundenen Daten")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--gesamtzahlen", action="store_true", help="pagination mit totalElements und totalPages")
    a = ap.parse_args()
    s = Testserver(a.port, gesamtzahlen=a.gesamtzahlen).start()
    print(f"RATSATLAS_OPARL_SYSTEM={s.system_url}\nRATSATLAS_OPARL_BODY={s.body_url}\n(Ende mit Strg+C)",
          file=sys.stderr)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        s.stop()
        print(f"{len(s.anfragen)} Anfragen beantwortet", file=sys.stderr)


if __name__ == "__main__":
    main()
