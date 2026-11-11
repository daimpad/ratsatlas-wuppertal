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
        self.groesse = 2       # Objekte je Seite
        self.anfragen = []
        self.papers = [self.paper(i) for i in range(1, 6)]
        self.meetings = [{
            "id": f"{basis}/meetings/1", "type": "https://schema.oparl.org/1.1/Meeting",
            "name": self.GREMIUM_BV, "start": "2026-10-01T17:00:00+02:00",
            "organization": [f"{basis}/organizations/bv4"], "modified": "2026-10-02T08:00:00+02:00",
            "agendaItem": [{"id": f"{basis}/agendaitems/{i}", "number": f"8.{i}", "name": f"TOP {i}",
                            "result": "ungeändert beschlossen" if i % 2 else "Kenntnis genommen", "public": True}
                           for i in range(1, 6)]}]
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

    def stoerung(self, pfad, q):
        """Für Tests überschreibbar: True erzeugt HTTP 404 für diese Anfrage."""
        return False

    def body(self):
        b = self.b
        return {"id": f"{b}/body", "name": "Testkörperschaft", "paper": f"{b}/papers", "meeting": f"{b}/meetings",
                "organization": f"{b}/organizations",
                "legislativeTerm": [{"id": f"{b}/terms/1", "name": "2025–2030", "startDate": "2025-11-01"}]}

    def liste(self, objekte, pfad, q, groesse=None):
        groesse = groesse or self.groesse
        seit = q.get("modified_since")
        if seit:
            objekte = [o for o in objekte if o["modified"] >= seit]
        if self.form == "koeln":   # neueste zuerst: zuletzt angefügte Objekte zuerst
            objekte = objekte[::-1]
        seite = int(q.get("page", 1))
        teil = objekte[(seite - 1) * groesse: seite * groesse]
        links = {}

        def adresse(werte):   # wie SessionNet: ohne URL-Kodierung
            return f"{self.b}{pfad}" + ("?" + "&".join(f"{k}={v}" for k, v in werte.items()) if werte else "")
        if seite * groesse < len(objekte):
            links["next"] = adresse({**q, "page": seite + 1})
        if self.form == "koeln":   # ohne Gesamtzahlen; links nur first, self, next
            return {"data": teil, "pagination": {"elementsPerPage": groesse, "currentPage": seite},
                    "links": {"first": adresse({k: v for k, v in q.items() if k != "page"}), "self": adresse(q),
                              **links}}
        return {"data": teil, "pagination": {"totalElements": len(objekte)}, "links": links}


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
        # wie SessionNet: „+“ bleibt „+“; kodierte Zeitstempel (%3A, %2B) ergeben HTTP 404
        q = dict((k, urllib.parse.unquote(v)) for k, _, v in (x.partition("=") for x in u.query.split("&") if x))
        d.anfragen.append((u.path, q, self.headers.get("User-Agent")))
        if "%3A" in u.query.upper() or "%2B" in u.query.upper() or d.stoerung(u.path, q):
            self.send_response(404)
            self.end_headers()
            return
        antwort = {"/body": d.body,
                   "/papers": lambda: d.liste(d.papers, "/papers", q),
                   "/meetings": lambda: d.liste(d.meetings, "/meetings", q),
                   "/organizations": lambda: d.liste(d.orgs, "/organizations", q)}.get(u.path)
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
                       "VORSTAND": raw / "vorstand_aenderungen.json", "AENDERUNGEN": export / "audit_aenderungen.tsv",
                       "TEXTE": raw / "texte.jsonl", "OPARL_BODY": f"{basis}/body", "ABRUF_ABSTAND": 0.0,
                       "BPLAN": tmp / "fehlt.geojson", "OBJEKTE": tmp / "fehlt.json",
                       "HAUSNUMMERN": tmp / "fehlt_hnr.json", **geo_attrappe(tmp / "geo", geo_namen)}.items():
        setze(config, name, wert)
