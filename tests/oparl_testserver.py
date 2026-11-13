"""Lokaler OParl-Testserver mit synthetischen Daten und Geo-Attrappe (keine Daten der Stadt).

Aus tests/conftest.py herausgezogen (ohne Verhaltensänderung, ohne pytest), damit auch der Erzeuger der Testseite für
die Browser-Prüfung (tests/browser/testseite.py) ihn nutzen kann. Die Fixture `oparl` in conftest.py ruft
`oparl_server_starten` und `pfade_umlenken` auf.

Die Objekte sind erfunden. Ihre Form folgt der Wuppertaler API, soweit sie bekannt ist (Stichprobe CLAUDE.md 3.1,
Messstufe 1 in explore/STUFEN.md): `consultation` mit direktem Verweis auf `meeting` und `agendaItem`, Paginierung über
`links.next` in der Form `?page=N`. Aus Köln übernommen und nicht an Wuppertal angepasst sind die Referenzen „NNNN/JJJJ“
und „AN/NNNN/JJJJ“ (Wuppertal: `VO/NNNN/JJ`, CLAUDE.md 3.1) und `location` mit `subLocality` (in Wuppertal bei 0 von
100 Vorlagen gesetzt); die Tests nutzen diese Werte, darum bleiben sie. `Daten.form = "koeln"` (Name aus Köln, von den
Tests genutzt) liefert die Listen neueste zuerst, also absteigend nach `created` (`created` wächst mit der Nummer der
Vorlage), mit `pagination` nur aus elementsPerPage und currentPage und mit `links` nur aus first, self und next. Das
entspricht in den gemessenen Punkten der ersten Wuppertaler Vorlagenseite (Stufe 1: absteigend nach `created`, nicht
nach `date`, CLAUDE.md 9, 10.11.2026; `pagination` ohne `totalElements` und `totalPages`, explore/STUFEN.md, Ergebnis
Stufe 1); ob `links` in Wuppertal ebenfalls nur first, self und next trägt, misst Stufe 2.
Parameter wie in Wuppertal gemessen (Stufe 2, explore/STUFEN.md): `modified_since` wirkt nur URL-kodiert; unkodiert
wird „+“ als Leerzeichen gelesen, der Zeitstempel ist dann unlesbar und der Filter wird übergangen (alle Objekte). Wie
links.next den Parameter weitergibt, ist für Wuppertal nicht gemessen: `Daten.folgeadresse` „kodiert“ (Vorgabe), „roh“
(mit „+“, die Folgeseite wäre ungefiltert) oder „ohne“ (Parameter fehlt). Einzelne Sitzungen sind unter ihrer Kennung
abrufbar (`/meetings/<n>`); `stoerung` kann statt True (HTTP 404) auch einen Statuscode liefern (z. B. 401).
Anlagen (pipeline/dokumente.py): `Daten.anlage` hängt einer Vorlage eine Datei in Wuppertaler Form an (nur
`auxiliaryFile`, `accessUrl` …/downloadfiles/a/<n>.pdf, `downloadUrl` …/downloadfiles/<n>.pdf, CLAUDE.md 3.1; die Form
der Kennung …/files/<n> ist angenommen) und legt den Inhalt unter `Daten.dateien` ab; `pdf_erzeugen` baut dafür
kleine PDF-Dateien mit erfundenem Text zur Laufzeit (keine PDF-Datei im Repository).
Namen: `Daten` trägt die Namen der Python-Tests (aus Köln übernommen: Kölner Orts- und Gremiennamen als Testdaten
ohne Bezug zu Wuppertal); Unterklassen können sie über die Klassenattribute ersetzen (Browser-Prüfung: klar erfundene
Namen wie „Testquartier A“).
"""
import json
import threading
import urllib.parse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Namen der Geo-Attrappe passend zu `Daten` (Python-Tests)
GEO_NAMEN = {"quartiere": ("Ehrenfeld", "Neuehrenfeld"), "bezirk": "Ehrenfeld", "strasse": "Venloer Straße"}


class Daten:
    # Namen der synthetischen Objekte; in Unterklassen ersetzbar
    GREMIUM_BV = "Bezirksvertretung 4 (Ehrenfeld)"
    TITEL_ORT = "Umgestaltung der Venloer Straße in Ehrenfeld"
    UNTERORT = "Neuehrenfeld"

    def __init__(self, basis):
        self.b = basis
        self.form = "bisher"   # „koeln“: neueste zuerst nach created, ohne Gesamtzahlen (siehe oben)
        self.folgeadresse = "kodiert"   # modified_since in links.next: „kodiert“, „roh“ oder „ohne“ (siehe oben)
        self.groesse = 2       # Objekte je Seite
        self.anfragen = []
        self.roh = []          # Pfad mit Abfrage, wie gesendet (ohne Dekodierung)
        self.papers = [self.paper(i) for i in range(1, 6)]
        self.meetings = [{
            "id": f"{basis}/meetings/1", "type": "https://schema.oparl.org/1.1/Meeting",
            "name": self.GREMIUM_BV, "start": "2026-10-01T17:00:00+02:00",
            "organization": [f"{basis}/organizations/bv4"], "modified": "2026-10-02T08:00:00+02:00",
            "agendaItem": [{"id": f"{basis}/agendaitems/{i}", "number": f"8.{i}", "name": f"TOP {i}",
                            "result": "ungeändert beschlossen" if i % 2 else "Kenntnis genommen", "public": True}
                           for i in range(1, 6)]}]
        # Anlagen: Pfad → (Status, Kopfzeilen, Inhalt) für /downloadfiles/… (`anlage`, `datei_setzen`)
        self.dateien = {}
        self.orgs = [{"id": f"{basis}/organizations/bv4", "name": self.GREMIUM_BV,
                      "organizationType": "Gremium", "modified": "2026-01-01T00:00:00+01:00"},
                     {"id": f"{basis}/organizations/rat", "name": "Rat", "organizationType": "Gremium",
                      "modified": "2026-01-01T00:00:00+01:00"}]

    def paper(self, i, name=None, modified="2026-10-01T10:00:00+02:00"):
        b = self.b
        return {
            "id": f"{b}/papers/{i}", "type": "https://schema.oparl.org/1.1/Paper",
            "reference": f"{1000 + i}/2026" if i % 2 else f"AN/{100 + i}/2026",
            "name": name or (self.TITEL_ORT if i == 1 else f"Synthetische Vorlage {i}"),
            "paperType": "Beschlussvorlage" if i % 2 else "Antrag nach § 3",
            "date": "2026-09-20", "modified": modified,
            "created": (datetime(2026, 9, 1, tzinfo=timezone(timedelta(hours=2))) + timedelta(minutes=i)).isoformat(),
            "location": [{"id": f"{b}/locations/{i}", "subLocality": self.UNTERORT}] if i == 3 else [],
            "consultation": [{"id": f"{b}/consultations/{i}", "meeting": f"{b}/meetings/1",
                              "agendaItem": f"{b}/agendaitems/{i}", "role": "Entscheidung", "authoritative": True}],
        }

    def anlage(self, paper, n, inhalt, name="Anlage (erfunden)", **angaben):
        """Hängt der Vorlage `paper` die Datei Nummer `n` an (auxiliaryFile, Wuppertaler Form wie oben) und legt den
        Inhalt auf dem Server ab. `inhalt`: Bytes oder (Status, Kopfzeilen, Bytes). `size` ist die Länge der Bytes,
        sofern `angaben` nichts anderes setzt. Liefert das File-Objekt."""
        datei = {"id": f"{self.b}/files/{n}", "type": "https://schema.oparl.org/1.1/File", "name": name,
                 "fileName": f"{name}.pdf", "mimeType": "application/pdf",
                 "accessUrl": f"{self.b}/downloadfiles/a/{n}.pdf", "downloadUrl": f"{self.b}/downloadfiles/{n}.pdf"}
        if isinstance(inhalt, bytes):
            datei["size"] = len(inhalt)
        datei.update(angaben)
        paper.setdefault("auxiliaryFile", []).append(datei)
        self.datei_setzen(n, inhalt)
        return datei

    def datei_setzen(self, n, inhalt, content_type="application/pdf"):
        """Inhalt der Datei Nummer `n` unter /downloadfiles/<n>.pdf: Bytes (Status 200) oder (Status, Kopfzeilen,
        Bytes). Ohne Content-Length in den Kopfzeilen sendet der Server die Länge des Inhalts; mit dem Wert None gar
        keine (die Antwort endet mit dem Schließen der Verbindung)."""
        self.dateien[f"/downloadfiles/{n}.pdf"] = inhalt if isinstance(inhalt, tuple) else (
            200, {"Content-Type": content_type}, inhalt)

    def stoerung(self, pfad, q):
        """Für Tests überschreibbar: True erzeugt HTTP 404 für diese Anfrage, eine Zahl diesen Statuscode."""
        return False

    def sitzung(self, pfad):
        """Einzelne Sitzung unter ihrer Kennung (`/meetings/<n>`); None, wenn es sie nicht gibt."""
        return next((m for m in self.meetings if m["id"] == f"{self.b}{pfad}"), None)

    def body(self):
        b = self.b
        return {"id": f"{b}/body", "name": "Testkörperschaft", "paper": f"{b}/papers", "meeting": f"{b}/meetings",
                "organization": f"{b}/organizations",
                "legislativeTerm": [{"id": f"{b}/terms/1", "name": "2025–2030", "startDate": "2025-11-01"}]}

    def liste(self, objekte, pfad, q, groesse=None):
        groesse = groesse or self.groesse
        seit = _zeitpunkt(q.get("modified_since"))
        if seit is not None:   # unlesbar (etwa unkodiertes „+“ als Leerzeichen): Filter übergangen wie in Wuppertal
            objekte = [o for o in objekte if (t := _zeitpunkt(o.get("modified"))) is None or t >= seit]
        if self.form == "koeln":   # neueste zuerst: zuletzt angefügte Objekte zuerst
            objekte = objekte[::-1]
        seite = int(q.get("page", 1))
        teil = objekte[(seite - 1) * groesse: seite * groesse]
        links = {}

        def adresse(werte):   # modified_since nach `folgeadresse`, alle übrigen Werte unverändert
            teile = []
            for k, v in werte.items():
                if k == "modified_since":
                    if self.folgeadresse == "ohne":
                        continue
                    if self.folgeadresse == "kodiert":
                        v = urllib.parse.quote(v, safe="")
                teile.append(f"{k}={v}")
            return f"{self.b}{pfad}" + ("?" + "&".join(teile) if teile else "")
        if seite * groesse < len(objekte):
            links["next"] = adresse({**q, "page": seite + 1})
        if self.form == "koeln":   # ohne Gesamtzahlen; links nur first, self, next
            return {"data": teil, "pagination": {"elementsPerPage": groesse, "currentPage": seite},
                    "links": {"first": adresse({k: v for k, v in q.items() if k != "page"}), "self": adresse(q),
                              **links}}
        return {"data": teil, "pagination": {"totalElements": len(objekte)}, "links": links}


def _zeitpunkt(wert):
    """Zeitpunkt mit Zone aus einem Text; None, wenn er fehlt, unlesbar oder ohne Zone ist."""
    try:
        t = datetime.fromisoformat(wert)
    except (TypeError, ValueError):
        return None
    return t if t.utcoffset() is not None else None


def pdf_erzeugen(seiten):
    """Kleine gültige PDF-Datei (PDF 1.4, Schrift Helvetica) mit einer Textzeile je Seite; `seiten`: Liste von Texten
    (Latin-1). Für erfundene Anlagen der Tests, erzeugt zur Laufzeit."""
    n = len(seiten)
    schrift = 3 + 2 * n
    objekte = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>".encode()]
    for i, text in enumerate(seiten):
        t = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        strom = f"BT /F1 12 Tf 72 720 Td ({t}) Tj ET".encode("latin-1")
        objekte.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {schrift} 0 R "
                       f">> >> /Contents {4 + 2 * i} 0 R >>".encode())
        objekte.append(b"<< /Length %d >>\nstream\n" % len(strom) + strom + b"\nendstream")
    objekte.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    aus = bytearray(b"%PDF-1.4\n")
    stellen = []
    for i, o in enumerate(objekte, 1):
        stellen.append(len(aus))
        aus += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(aus)
    aus += f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n".encode()
    for s in stellen:
        aus += f"{s:010d} 00000 n \n".encode()
    aus += f"trailer\n<< /Size {len(objekte) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(aus)


def geo_attrappe(ziel, namen=None):
    """Synthetische Gebietsflächen und ein Straßenverzeichnis im Bonner Format (ortsteil, ortsteil_bez, bezirk,
    bezirk_bez; streets mit ortsteil, ortsteil_nr, bezirk, lon, lat, length_m, component, source). Namen passend zu
    den synthetischen Testobjekten (`namen`, Vorgabe GEO_NAMEN für `Daten`), Koordinaten frei gewählt (Rechtecke um
    0°/0°). Keine Daten der Stadt. Liefert die Pfade für config.ORTSTEILE, config.STADTBEZIRKE und config.STRASSEN."""
    namen = {**GEO_NAMEN, **(namen or {})}
    (q1, q2), bezirk, strasse = namen["quartiere"], namen["bezirk"], namen["strasse"]
    ziel.mkdir(parents=True, exist_ok=True)

    def rechteck(w, s, o, n):
        return {"type": "Polygon", "coordinates": [[[w, s], [o, s], [o, n], [w, n], [w, s]]]}

    flaechen = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": rechteck(0.0, 0.0, 0.01, 0.01),
         "properties": {"ortsteil": "1", "ortsteil_bez": q1, "bezirk": "4", "bezirk_bez": bezirk}},
        {"type": "Feature", "geometry": rechteck(0.01, 0.0, 0.02, 0.01),
         "properties": {"ortsteil": "2", "ortsteil_bez": q2, "bezirk": "4", "bezirk_bez": bezirk}}]}
    bezirke = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": rechteck(0.0, 0.0, 0.02, 0.01),
         "properties": {"bezirk": "4", "bezirk_bez": bezirk}}]}
    strassen = {"meta": {"source": "synthetische Testdaten", "license": "–", "retrieved_at": None},
                "streets": {strasse: [{"ortsteil": q1, "ortsteil_nr": "1", "bezirk": bezirk,
                                       "lon": 0.005, "lat": 0.005, "length_m": 500.0, "component": 0,
                                       "source": "osm"}]},
                "kreuzungen": {}}
    pfade = {"ORTSTEILE": ziel / "gebiete.geojson", "STADTBEZIRKE": ziel / "stadtbezirke.geojson",
             "STRASSEN": ziel / "strassen.json"}
    for name, daten in (("ORTSTEILE", flaechen), ("STADTBEZIRKE", bezirke), ("STRASSEN", strassen)):
        pfade[name].write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return pfade


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        d = self.server.daten
        u = urllib.parse.urlparse(self.path)
        # wie Wuppertal (Stufe 2): kodierte Werte werden dekodiert, ein unkodiertes „+“ wird zum Leerzeichen
        q = dict((k, urllib.parse.unquote_plus(v)) for k, _, v in (x.partition("=") for x in u.query.split("&") if x))
        d.anfragen.append((u.path, q, self.headers.get("User-Agent")))
        d.roh.append(self.path)
        status = d.stoerung(u.path, q)
        if status:
            self.send_response(404 if status is True else status)
            self.end_headers()
            return
        if u.path in d.dateien:   # Anlage: Status, Kopfzeilen und Inhalt wie hinterlegt
            code, kopf, inhalt = d.dateien[u.path]
            self.send_response(code)
            for k, v in kopf.items():
                if v is not None:   # Content-Length None: ohne Länge, Ende der Antwort mit dem Schließen
                    self.send_header(k, v)
            if "Content-Length" not in kopf:
                self.send_header("Content-Length", str(len(inhalt)))
            self.end_headers()
            try:
                self.wfile.write(inhalt)
            except (BrokenPipeError, ConnectionResetError):   # der Client liest bei zu großen Dateien nicht weiter
                pass
            return
        antwort = {"/body": d.body,
                   "/papers": lambda: d.liste(d.papers, "/papers", q),
                   "/meetings": lambda: d.liste(d.meetings, "/meetings", q),
                   "/organizations": lambda: d.liste(d.orgs, "/organizations", q)}.get(u.path)
        if not antwort and u.path.startswith("/meetings/") and d.sitzung(u.path):
            antwort = lambda: d.sitzung(u.path)   # noqa: E731
        if not antwort:
            self.send_response(404)
            self.end_headers()
            return
        b = json.dumps(antwort()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b)


def oparl_server_starten(klasse=Daten):
    """Startet den OParl-Testserver auf 127.0.0.1 (freier Port) mit Daten der Klasse `klasse`. Liefert (server,
    daten); beenden mit server.shutdown()."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daten = klasse(f"http://127.0.0.1:{server.server_address[1]}")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.daten


def pfade_umlenken(tmp, basis, setze, geo_namen=None):
    """Lenkt alle Pfade der Pipeline (config) in das Verzeichnis `tmp` und den Endpunkt auf den Testserver `basis`.
    `setze(config, name, wert)`: monkeypatch.setattr in der Fixture, sonst setattr."""
    from pipeline import config
    raw, build, export = tmp / "raw", tmp / "build", tmp / "export"
    for name, wert in {"RAW": raw, "BUILD": build, "EXPORT": export, "DB": build / "allris.sqlite",
                       "PAPERS": raw / "papers.jsonl", "ORGANIZATIONS": raw / "organizations.json",
                       "VERWALTUNGSBEREICHE": raw / "verwaltungsbereiche.json", "MEETINGS": raw / "meetings.json",
                       "LEGISLATIVE_TERMS": raw / "legislative_terms.json", "BERATUNGEN": raw / "beratungen.jsonl",
                       "CONSULTATIONS_LITE": raw / "beratungen.jsonl", "STAND": raw / "STAND.json",
                       "ZUSTAND": raw / "zustand_abruf.json", "ABRUFSTATISTIK": export / "abrufstatistik.tsv",
                       "ABRUFSTATISTIK_SEITEN": export / "abrufstatistik_seiten.tsv",
                       "VORSTAND": raw / "vorstand_aenderungen.json", "AENDERUNGEN": export / "audit_aenderungen.tsv",
                       "TEXTE": raw / "texte.jsonl", "OPARL_BODY": f"{basis}/body", "ABRUF_ABSTAND": 0.0,
                       "TEXTE_ORDNER": raw / "texte", "DOKUMENTE_ZUSTAND": raw / "zustand_dokumente.json",
                       "DOKUMENTE_PROTOKOLL": export / "abruf_dokumente.tsv",
                       "DOKUMENTE_STATISTIK": export / "abrufstatistik_dokumente.tsv",
                       "DOKUMENTE_ABSTAND_TAG": 0.0, "DOKUMENTE_ABSTAND_NACHT": 0.0,
                       "BPLAN": tmp / "fehlt.geojson", "OBJEKTE": tmp / "fehlt.json",
                       "HAUSNUMMERN": tmp / "fehlt_hnr.json", **geo_attrappe(tmp / "geo", geo_namen)}.items():
        setze(config, name, wert)
