"""Linkprüfung (tools/links_pruefen.py, .github/workflows/links.yml): intern gegen eine kleine Testseite und gegen die
echte Ausgabe von tools/seite_bauen.py (ohne Daten); extern gegen einen lokalen HTTP-Server auf 127.0.0.1 (Wächter:
nur 127.0.0.1); Server der Stadt und Kachelserver werden nie angefragt (Öffner-Attrappe). Keine echten Abrufe."""
import importlib.util
import re
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pipeline import config, vorgangsseiten

ROOT = config.ROOT
WF = ROOT / ".github" / "workflows" / "links.yml"


def _modul(name, datei):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / datei)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


lp = _modul("links_pruefen", "links_pruefen.py")


def _schreiben(wurzel, dateien):
    for name, text in dateien.items():
        pfad = wurzel / name
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(text, encoding="utf-8")
    return wurzel


def _ergebnis(p, link, seite=None):
    treffer = [z for z in p.zeilen if z[1] == link and (seite is None or z[0] == seite)]
    assert len(treffer) == 1, (link, treffer)
    return treffer[0]


class _Verboten:
    """Öffner-Attrappe für interne Prüfungen: jede Anfrage lässt den Test fehlschlagen."""

    def open(self, req, *a, **k):
        pytest.fail(f"Anfrage im internen Test: {req.full_url}")


# --- intern -------------------------------------------------------------------------------------------------------

TESTSEITE = {
    "index.html": """<!doctype html><html><head><meta charset="utf-8">
  <link rel="stylesheet" href="style.css"><link rel="manifest" href="site.webmanifest">
  <meta property="og:image" content="https://wuppertal.ratsatlas.de/bild.png">
  <link rel="alternate" href="data/export/wuppertal/feeds/ganz-wuppertal.xml"></head><body id="oben">
  <a href="seite.html#teil">gut</a> <a href="seite.html#fehlt">Anker fehlt</a> <a href="#oben">oben</a>
  <a href="#">nach oben</a> <a href="#top">top</a> <a href="#nirgends">kaputt</a>
  <a href="unter/">Verzeichnis</a> <a href="unter">ohne Schrägstrich</a> <a href="fehlt.html">fehlt</a>
  <a href="gebiete/">erst mit Daten</a> <a href="vorgang/vo-1-26/">Vorgang</a> <a href="data/export/x.zip">Zip</a>
  <a href="/wurzel.html">wurzelabsolut</a> <a href="../aussen.html">außerhalb</a>
  <a href="https://wuppertal.ratsatlas.de/seite.html#teil">eigene Adresse</a>
  <a href="https://daimpad.github.io/ratsatlas-wuppertal/nicht-da.html">eigene Adresse fehlt</a>
  <a href="https://wuppertal.ratsatlas.de">eigene Startseite ohne Schrägstrich</a>
  <a href="mailto:contact@nozilla.de">Mail</a> <a href="https://oparl.wuppertal.de/oparl/system">Stadt</a>
  <a href="https://example.org/extern">extern</a> <a href="seite.html?v=2">mit Parameter</a>
  <a href="mit%20leer.html">Prozentkodierung</a>
  <img src="bild.png" srcset="bild.png 1x, fehlt-2x.png 2x" alt="">
  <svg><use href="#oben"></use></svg></body></html>""",
    "seite.html": '<!doctype html><html><body><h2 id="teil">Teil</h2><a name="alt"></a>'
                  '<a href="index.html#oben">zurück</a> <a href="seite.html#alt">alt</a></body></html>',
    "unter/index.html": '<!doctype html><a href="../index.html">hoch</a> <a href="../style.css">CSS</a>',
    "mit leer.html": "<!doctype html>",
    "bild.png": "png",
    "style.css": "a{background:url('bild.png')} b{background:url(fonts/fehlt.woff2)} c{filter:url(#none)}",
    "site.webmanifest": '{"start_url": "./", "icons": [{"src": "bild.png?v=2"}, {"src": "icon-fehlt.png"}]}',
}


def test_intern_testseite_ohne_daten(tmp_path):
    w = _schreiben(tmp_path / "site", TESTSEITE)
    p = lp.Linkpruefung(w, oeffner=_Verboten(), datum="2026-11-10")
    fehler = p.alles()
    assert p.anfragen == 0 and not p.mit_daten
    erwartet = {
        "seite.html#teil": "ok", "seite.html#fehlt": "Fehler", "#oben": "ok", "#": "ok", "#top": "ok",
        "#nirgends": "Fehler", "unter/": "ok", "unter": "ok", "fehlt.html": "Fehler", "gebiete/": "erst mit Daten",
        "vorgang/vo-1-26/": "erst mit Daten", "data/export/x.zip": "erst mit Daten",
        "data/export/wuppertal/feeds/ganz-wuppertal.xml": "erst mit Daten", "/wurzel.html": "Fehler",
        "../aussen.html": "Fehler", "https://wuppertal.ratsatlas.de/seite.html#teil": "ok",
        "https://daimpad.github.io/ratsatlas-wuppertal/nicht-da.html": "Fehler",
        "https://wuppertal.ratsatlas.de": "ok", "https://wuppertal.ratsatlas.de/bild.png": "ok",
        "mailto:contact@nozilla.de": "nicht geprüft", "https://oparl.wuppertal.de/oparl/system": "nicht geprüft",
        "https://example.org/extern": "nicht geprüft", "seite.html?v=2": "ok", "mit%20leer.html": "ok",
        "bild.png": "ok", "fehlt-2x.png": "Fehler",
    }
    for link, ergebnis in erwartet.items():
        assert _ergebnis(p, link, "index.html")[3] == ergebnis, link
    assert "Server der Stadt" in _ergebnis(p, "https://oparl.wuppertal.de/oparl/system")[5]
    assert "Server leitet um" in _ergebnis(p, "unter")[5]
    assert _ergebnis(p, "#nirgends")[2] == "Anker" and "Anker #nirgends fehlt in index.html" in _ergebnis(p, "#nirgends")[5]
    assert _ergebnis(p, "seite.html#alt", "seite.html")[3] == "ok"                # <a name>
    assert _ergebnis(p, "index.html#oben", "seite.html")[3] == "ok"
    assert _ergebnis(p, "../style.css", "unter/index.html")[3] == "ok"
    assert _ergebnis(p, "fonts/fehlt.woff2", "style.css")[3] == "Fehler"           # CSS url()
    assert not [z for z in p.zeilen if z[1] == "#none"]                           # url(#…) in CSS ist kein Link
    assert _ergebnis(p, "icon-fehlt.png", "site.webmanifest")[3] == "Fehler"      # Manifest
    assert _ergebnis(p, "bild.png?v=2", "site.webmanifest")[3] == "ok"
    assert fehler == p.fehler() == sum(1 for z in p.zeilen if z[3] == "Fehler") == 9
    # TSV: Kopf und je Zeile sieben Spalten, Datum in der letzten
    zeilen = p.tsv().splitlines()
    assert zeilen[0] == "Seite\tLink\tArt\tErgebnis\tStatus\tHinweis\tDatum"
    assert all(len(z.split("\t")) == 7 and z.endswith("\t2026-11-10") for z in zeilen[1:])


def test_intern_mit_daten_sind_datenpfade_pflicht(tmp_path):
    w = _schreiben(tmp_path / "site", dict(TESTSEITE, **{"data/export/wuppertal/index.json": "{}"}))
    p = lp.Linkpruefung(w, oeffner=_Verboten())
    p.alles()
    assert p.mit_daten
    assert not [z for z in p.zeilen if z[3] == "erst mit Daten"]
    assert _ergebnis(p, "gebiete/", "index.html")[3] == "Fehler"
    assert _ergebnis(p, "data/export/x.zip", "index.html")[3] == "Fehler"


def test_erst_mit_daten_passt_zur_pipeline():
    """Die Regel nennt genau die Pfade, die erst mit Daten entstehen: Export (seite_bauen), Gebiets- und
    Vorgangsseiten (pipeline/)."""
    quelle = (ROOT / "pipeline" / "gebietsseiten.py").read_text(encoding="utf-8")
    for pfad in ("gebiete/", "ortsteil/", "stadtbezirk/"):
        assert pfad in lp.ERST_MIT_DATEN and f'"{pfad}' in quelle.replace("f\"", "\""), pfad
    assert vorgangsseiten.PFAD in lp.ERST_MIT_DATEN
    assert {"data/export/", "data/geo/"} <= set(lp.ERST_MIT_DATEN)
    assert len(lp.ERST_MIT_DATEN) == 6


def test_echte_seite_ohne_daten_ohne_fehler(tmp_path, monkeypatch):
    """Ausgabe von tools/seite_bauen.py ohne Daten: kein kaputter Verweis; fehlende Ziele nur unter ERST_MIT_DATEN."""
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)
    monkeypatch.setattr(config, "EXPORT", tmp_path / "leer")
    monkeypatch.setattr(config, "SITE_URL", "https://wuppertal.ratsatlas.de/")
    ziel = tmp_path / "_site"
    _modul("seite_bauen", "seite_bauen.py").main(ziel)
    p = lp.Linkpruefung(ziel, oeffner=_Verboten())
    assert p.alles() == 0, [z for z in p.zeilen if z[3] == "Fehler"]
    seiten = {z[0] for z in p.zeilen}
    assert {"index.html", "404.html", "datenschutz.html", "begriffe/index.html", "rss/index.html", "style.css",
            "site.webmanifest"} <= seiten
    assert any(z[2] == "Anker" and z[3] == "ok" for z in p.zeilen)
    assert any(z[2] == "eigene Adresse" for z in p.zeilen)          # 404.html verweist absolut auf die Hauptadresse
    for z in p.zeilen:
        if z[3] == "erst mit Daten":
            assert z[5].split(" ")[0].startswith(("data/export/", "gebiete")), z
        if z[3] == "nicht geprüft":
            assert z[2] in ("mailto", "extern"), z


# --- extern -------------------------------------------------------------------------------------------------------

class _Server:
    """Lokaler HTTP-Server; Routen: Pfad → Funktion(Methode) → (Status, Kopfzeilen)."""

    def __init__(self):
        self.anfragen = []
        routen = self.routen = {}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _antwort(self):
                self.server.s.anfragen.append((self.command, self.path, self.headers.get("User-Agent")))
                status, kopf = routen.get(self.path, lambda m: (404, {}))(self.command)
                self.send_response(status)
                for k, v in kopf.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", "2")
                self.end_headers()
                if self.command == "GET":
                    self.wfile.write(b"ok")

            do_GET = do_HEAD = _antwort

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.s = self
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def server(monkeypatch):
    for name in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        monkeypatch.delenv(name, raising=False)
    s = _Server()
    yield s
    s.server.shutdown()
    s.server.server_close()


class _NurLokal:
    """Wächter um den echten Öffner des Skripts: nur 127.0.0.1, sonst schlägt der Test fehl."""

    def __init__(self):
        self.echt = urllib.request.build_opener(lp._OhneWeiterleitung)

    def open(self, req, *a, **k):
        if urllib.parse.urlsplit(req.full_url).hostname != "127.0.0.1":
            pytest.fail(f"Anfrage an einen fremden Host im Test: {req.full_url}")
        return self.echt.open(req, *a, **k)


class _Uhr:
    def __init__(self):
        self.jetzt, self.pausen = 1000.0, []

    def __call__(self):
        return self.jetzt

    def schlafen(self, s):
        self.pausen.append(s)
        self.jetzt += s


def _extern(server, tmp_path, pfade, **kw):
    links = "".join(f'<a href="{server.url if p.startswith("/") else ""}{p}">x</a>' for p in pfade)
    w = _schreiben(tmp_path / "site", {"index.html": f"<!doctype html><body>{links}</body>"})
    uhr = _Uhr()
    args = dict(extern=True, oeffner=_NurLokal(), schlafen=uhr.schlafen, uhr=uhr, zeitlimit=5)
    args.update(kw)
    p = lp.Linkpruefung(w, **args)
    return p, p.alles(), uhr


def test_extern_head_get_weiterleitung_und_fehler(server, tmp_path):
    server.routen.update({
        "/ok": lambda m: (200, {}),
        "/nur-get": lambda m: (405, {}) if m == "HEAD" else (200, {}),
        "/abgewiesen": lambda m: (403, {}),
        "/weiter": lambda m: (301, {"Location": "/ok"}),
        "/zur-stadt": lambda m: (302, {"Location": "https://WWW.Wuppertal.de:443/rathaus"}),
        "/kreis": lambda m: (302, {"Location": "/kreis"}),
    })
    p, fehler, uhr = _extern(server, tmp_path, ["/ok", "/nur-get", "/abgewiesen", "/weiter", "/zur-stadt", "/kaputt",
                                                "/kreis", "/ok#anker"])
    e = {z[1].replace(server.url, ""): z for z in p.zeilen}
    assert e["/ok"][3:5] == ("ok", "200")
    assert e["/nur-get"][3:5] == ("ok", "200")
    assert e["/abgewiesen"][3:5] == ("unklar", "403")
    assert e["/weiter"][3:5] == ("ok", "200") and "Weiterleitung 301" in e["/weiter"][5]
    assert e["/zur-stadt"][3] == "nicht geprüft" and "Server der Stadt" in e["/zur-stadt"][5]
    assert e["/kaputt"][3:5] == ("Fehler", "404")
    assert e["/kreis"][3] == "Fehler" and "Weiterleitungen" in e["/kreis"][5]
    assert "/ok#anker" not in e                                    # Anker extern: dieselbe Adresse, einmal abgefragt
    assert fehler == 2
    gesendet = [(m, pfad) for m, pfad, _ in server.anfragen]
    assert gesendet.count(("HEAD", "/ok")) == 2                     # /ok direkt und als Ziel von /weiter
    assert ("GET", "/nur-get") in gesendet and ("GET", "/abgewiesen") in gesendet
    assert ("GET", "/ok") not in gesendet                           # HEAD genügt
    assert all("contact@nozilla.de" in ua and "github.com/daimpad/ratsatlas-wuppertal" in ua
               for _, _, ua in server.anfragen)
    # je Host mindestens 2 s Abstand (Uhr-Attrappe): Anzahl Pausen = Anfragen − 1, jede bis zum vollen Abstand
    assert p.anfragen == len(server.anfragen) and len(uhr.pausen) == p.anfragen - 1
    assert all(abs(s - lp.ABSTAND) < 1e-9 for s in uhr.pausen)


def test_extern_abstand_je_host_und_wiederholung(server, tmp_path):
    zaehler = {"n": 0}

    def wackelig(m):
        zaehler["n"] += 1
        return (503, {}) if zaehler["n"] == 1 else (200, {})

    server.routen.update({"/a": lambda m: (200, {}), "/wackelig": wackelig})
    # 503 wird einmal wiederholt; alle Anfragen an denselben Host, also vor jeder weiteren eine Pause
    p, fehler, uhr = _extern(server, tmp_path, ["/a", "/wackelig"])
    assert fehler == 0 and _ergebnis(p, server.url + "/wackelig")[3:5] == ("ok", "200")
    assert [pfad for _, pfad, _ in server.anfragen] == ["/a", "/wackelig", "/wackelig"]
    assert len(uhr.pausen) == 2


def test_extern_obergrenze(server, tmp_path):
    server.routen.update({f"/{i}": (lambda m: (200, {})) for i in range(5)})
    p, fehler, _ = _extern(server, tmp_path, [f"/{i}" for i in range(5)], max_anfragen=3)
    assert fehler == 0 and len(server.anfragen) == 3 == p.anfragen
    assert sum(1 for z in p.zeilen if z[3] == "nicht geprüft" and "Obergrenze" in z[5]) == 2


def test_extern_keine_antwort_ist_fehler(tmp_path, monkeypatch):
    for name in ("http_proxy", "HTTP_PROXY"):
        monkeypatch.delenv(name, raising=False)
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                                       # Port ohne Server: Verbindung abgelehnt
    w = _schreiben(tmp_path / "site", {"index.html": f'<a href="http://127.0.0.1:{port}/x">x</a>'})
    uhr = _Uhr()
    p = lp.Linkpruefung(w, extern=True, oeffner=_NurLokal(), schlafen=uhr.schlafen, uhr=uhr, zeitlimit=2)
    assert p.alles() == 1 and "keine Antwort" in p.zeilen[0][5] and p.anfragen == 2


# --- Server der Stadt: nie anfragen ---------------------------------------------------------------------------------

STADT = ["https://oparl.wuppertal.de/oparl/system", "https://RIS.Wuppertal.DE/", "http://daten.wuppertal.de./x.json",
         "https://www.wuppertal.de:443/rathaus", "https://maps.wuppertal.de/planung", "//offenedaten-wuppertal.de/d",
         "https://OffeneDaten-Wuppertal.de:8443/dataset", "https://neu.unter.wuppertal.de/", "https://wuppertal.de",
         "https://nutzer@oparl.wuppertal.de/", "https://wuppertal-test.de/", "https://tile.openstreetmap.org/1/2/3.png",
         "https://a.tile.openstreetmap.org/1/2/3.png",
         # Unicode- und prozentkodierte Schreibweisen, die Python beim Verbinden (IDNA bzw. urllib) zu Hosts der Stadt macht
         "https://wuppert\u00aal.de/", "https://oparl.wupper\u00adtal.de/oparl/system",
         "https://\uff57\uff55\uff50\uff50\uff45\uff52\uff54\uff41\uff4c.de/", "https://ris.wuppertal\u3002de/",
         "https://daten.wuppertal\uff0ede/", "https://wupp%65rtal.de/", "https://oparl.wupp%C2%ADertal.de/"]


class _Protokoll:
    """Öffner-Attrappe: merkt sich jede Anfrage und antwortet 200, ohne etwas zu senden."""

    def __init__(self):
        self.urls = []

    def open(self, req, *a, **k):
        self.urls.append(req.full_url)

        class R:
            status, headers = 200, {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return b""

        return R()


def test_server_der_stadt_werden_nie_angefragt(tmp_path):
    links = "".join(f'<a href="{u}">x</a>' for u in STADT) + '<a href="https://example.org/">erlaubt</a>'
    w = _schreiben(tmp_path / "site", {"index.html": f"<!doctype html>{links}"})
    attrappe, uhr = _Protokoll(), _Uhr()
    p = lp.Linkpruefung(w, extern=True, oeffner=attrappe, schlafen=uhr.schlafen, uhr=uhr)
    assert p.alles() == 0
    assert attrappe.urls == ["https://example.org/"]                # Gegenprobe: der Öffner wird überhaupt genutzt
    for u in STADT:
        z = _ergebnis(p, u)
        assert z[3] == "nicht geprüft", u
        assert ("Server der Stadt" in z[5]) != ("openstreetmap" in u), u


@pytest.mark.parametrize("url", [u if not u.startswith("//") else "https:" + u for u in STADT]
                         + ["https://example.org\\@oparl.wuppertal.de/", "ftp://example.org/", "https://[::1/"])
def test_anfragen_sperrt_auch_direkt(url):
    """Zweite Sicherung: _anfragen lehnt gesperrte Adressen ab, auch wenn ein Aufrufer die Einordnung umgeht."""
    attrappe = _Protokoll()
    p = lp.Linkpruefung(ROOT, extern=True, oeffner=attrappe, schlafen=lambda s: None)
    with pytest.raises((RuntimeError, ValueError)):
        p._anfragen(url, "HEAD")
    assert attrappe.urls == []


def test_stadt_host():
    for host in ("wuppertal.de", "OPARL.WUPPERTAL.DE", "ris.wuppertal.de.", "offenedaten-wuppertal.de",
                 "a.b.wuppertal.de", "wuppertal-live.de"):
        assert lp.stadt_host(host), host
    for host in ("wuppertal.ratsatlas.de", "github.com", "wuppertal.de.example.org", "wuppertal.com", ""):
        assert not lp.stadt_host(host), host
    assert lp.host_von("https://User@WWW.Wuppertal.DE.:443/x") == "www.wuppertal.de"
    for host in ("wuppert\u00aal.de", "oparl.wupper\u00adtal.de", "\uff57\uff55\uff50\uff50\uff45\uff52\uff54\uff41\uff4c.de",
                 "ris.wuppertal\u3002de", "wupp%65rtal.de"):
        assert lp.stadt_host(host), host
    assert lp.host_von("https://b\u00fccher.example/") == "xn--bcher-kva.example"


def test_host_normal_wie_python_beim_verbinden():
    """host_normal ergibt den Host, den urllib.request und socket (IDNA) tatsächlich anfragen würden."""
    for url in ("https://wuppert\u00aal.de/", "https://oparl.wupper\u00adtal.de/", "https://wupp%65rtal.de/",
                "https://\uff57\uff55\uff50\uff50\uff45\uff52\uff54\uff41\uff4c.de/"):
        roh = urllib.request.Request(url).host
        assert lp.host_normal(roh) == roh.encode("idna").decode("ascii").rstrip(".").lower() == lp.host_von(url), url
    assert lp.host_normal("a\u00e4..b") == ""                               # nicht umwandelbar: nie anfragen
    assert lp.gesperrt("https://a\u00e4..b/") == "nicht geprüft (Adresse nicht lesbar)"


def test_weiterleitung_auf_stadt_wird_nicht_verfolgt(tmp_path):
    class Weiter(_Protokoll):
        def open(self, req, *a, **k):
            self.urls.append(req.full_url)
            raise urllib.error.HTTPError(req.full_url, 301, "Moved", {"Location": "https://ris.wuppertal.de/si0040.asp"},
                                         None)

    import urllib.error
    w = _schreiben(tmp_path / "site", {"index.html": '<a href="https://example.org/alt">x</a>'})
    attrappe = Weiter()
    p = lp.Linkpruefung(w, extern=True, oeffner=attrappe, schlafen=lambda s: None)
    assert p.alles() == 0
    assert attrappe.urls == ["https://example.org/alt"]
    assert p.zeilen[0][3] == "nicht geprüft" and "Weiterleitung auf https://ris.wuppertal.de" in p.zeilen[0][5]


def test_main_exit_code_und_ausgabe(tmp_path, capsys):
    w = _schreiben(tmp_path / "site", {"index.html": '<a href="fehlt.html">x</a> <a href="https://example.org/">e</a>'})
    aus = tmp_path / "links.tsv"
    assert lp.main([str(w), "--aus", str(aus)]) == 1
    tsv = aus.read_text(encoding="utf-8")
    assert "fehlt.html\tintern\tFehler" in tsv and "https://example.org/\textern\tnicht geprüft\t\tohne --extern" in tsv
    assert "FEHLER" in capsys.readouterr().err
    (w / "fehlt.html").write_text("<!doctype html>", encoding="utf-8")
    assert lp.main([str(w)]) == 0
    with pytest.raises(SystemExit):
        lp.main([str(tmp_path / "gibt-es-nicht")])


# --- .github/workflows/links.yml (statisch) -----------------------------------------------------------------------

def _code():
    return "\n".join(z for z in WF.read_text(encoding="utf-8").splitlines() if not z.lstrip().startswith("#"))


def test_links_yml_ausloeser_und_uhrzeit():
    code = _code()
    assert re.search(r"^name: Linkprüfung$", code, re.M)
    kopf = code.split("\njobs:\n")[0]
    m = re.search(r'^on:\n  schedule:\n    - cron: "(\d+) (\d+) (\d+) \* \*"\n  workflow_dispatch:\n', kopf, re.M)
    assert m, kopf
    minute, stunde, tag = map(int, m.groups())
    # monatlich tagsüber (UTC 6–18 Uhr, also nie 23–1 Uhr Berlin), nicht zur vollen oder halben Stunde
    assert 6 <= stunde <= 18 and minute not in (0, 30) and 1 <= tag <= 28
    for wort in ("push:", "pull_request", "workflow_run"):
        assert wort not in kopf, wort


def test_links_yml_gepinnt_rechte_ohne_secrets():
    wf, code = WF.read_text(encoding="utf-8"), _code()
    pins = dict(re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@(\S+)", wf))
    assert pins == {"actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
                    "actions/setup-python": "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
                    "actions/upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9"}
    for aktion, rest in re.findall(r"uses:\s*(\S+)(.*)$", wf, re.M):
        assert re.match(r"\s+# v\d+\.\d+\.\d+$", rest), aktion
    assert re.search(r"^permissions:\n  contents: read\n", code, re.M)
    assert re.findall(r"^\s+(\w[\w-]*): (read|write)$", code, re.M) == [("contents", "read"), ("contents", "read")]
    assert "persist-credentials: false" in code
    assert "secrets" not in code.lower() and "token" not in code.lower() and ": write" not in code
    schritte = ["pip install -r requirements.txt", "python tools/seite_bauen.py _site",
                "python tools/links_pruefen.py _site --extern --aus links.tsv", "actions/upload-artifact@"]
    stellen = [code.index(s) for s in schritte]
    assert stellen == sorted(stellen)
    hochladen = code.split("actions/upload-artifact@")[1]
    assert "if: always()" in hochladen and "path: links.tsv" in hochladen
    assert int(re.search(r"retention-days: (\d+)", hochladen).group(1)) <= 30
    for host in ("oparl.wuppertal.de", "ris.wuppertal.de", "daten.wuppertal.de", "offenedaten-wuppertal.de"):
        assert host not in wf, host
