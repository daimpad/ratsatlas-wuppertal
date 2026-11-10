"""Tests für explore/strukturdaten/abruf_struktur.py (Phase 0 Strukturdaten) mit lokalem Server auf 127.0.0.1.

Keine echten Abrufe: Anfragen an andere Hosts lassen den Test fehlschlagen, bevor sie gesendet werden. Cache,
Protokoll und Sperrort liegen je Test in tmp_path; 127.0.0.1 ist nur über den Testmodus erlaubt.
"""
import csv
import fcntl
import importlib.util
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "explore" / "strukturdaten" / "abruf_struktur.py"
_spec = importlib.util.spec_from_file_location("abruf_struktur", SKRIPT)
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

CSV = b"a;b\n1;2\n"


class _Server:
    def __init__(self):
        self.anfragen = []   # (methode, pfad, zeit, user-agent)
        server = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def version_string(self):
                return "cloudflare" if self.path.startswith("/cf403s") else super().version_string()

            def _antwort(self, mit_inhalt):
                server.anfragen.append((self.command, self.path, time.time(), self.headers.get("User-Agent")))
                pfad = self.path.split("?")[0]
                basis = f"http://127.0.0.1:{server.port}"
                if pfad == "/ok.csv":
                    self._senden(200, CSV, "text/csv", mit_inhalt)
                elif pfad == "/gross":
                    self._senden(200, b"x" * 5000, "application/octet-stream", mit_inhalt)
                elif pfad in ("/429", "/500", "/404", "/403"):
                    self._senden(int(pfad[1:]), b"fehler", "text/plain", mit_inhalt)
                elif pfad == "/cf403":
                    self._senden(403, b"challenge", "text/html", mit_inhalt, {"cf-mitigated": "challenge"})
                elif pfad == "/cf403s":
                    self._senden(403, b"challenge", "text/html", mit_inhalt)
                elif pfad == "/langsam":
                    time.sleep(1.0)
                    self._senden(200, b"spaet", "text/plain", mit_inhalt)
                elif pfad == "/weiter":
                    self._weiter(f"{basis}/ok.csv")
                elif pfad == "/weiter_relativ":
                    self._weiter("/ok.csv")
                elif pfad == "/weiter_oparl":
                    self._weiter("https://oparl.wuppertal.de/oparl/system")
                elif pfad == "/weiter_fremd":
                    self._weiter("https://example.org/datei.csv")
                elif pfad.startswith("/kette"):
                    n = int(pfad[len("/kette"):] or 0)
                    self._weiter(f"{basis}/kette{n + 1}" if n < 2 else f"{basis}/ok.csv")
                else:
                    self._senden(404, b"", "text/plain", mit_inhalt)

            def _senden(self, code, inhalt, typ, mit_inhalt, extra=None):
                self.send_response(code)
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Type", typ)
                self.send_header("Content-Length", str(len(inhalt)))
                self.end_headers()
                if mit_inhalt:
                    self.wfile.write(inhalt)

            def _weiter(self, ziel):
                self.send_response(302)
                self.send_header("Location", ziel)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_GET(self):
                self._antwort(True)

            def do_HEAD(self):
                self._antwort(False)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def url(self, pfad):
        return f"http://127.0.0.1:{self.port}{pfad}"

    def pfade(self):
        return [a[1] for a in self.anfragen]


@pytest.fixture
def server():
    s = _Server()
    yield s
    s.httpd.shutdown()
    s.httpd.server_close()


class _NurLokal:
    """Öffner, der jede Anfrage an einen anderen Host als 127.0.0.1 ablehnt (Schutz vor echten Abrufen)."""

    def __init__(self, oeffner):
        self._o = oeffner

    def open(self, req, *a, **k):
        if ab.host_von(req.full_url) != "127.0.0.1":
            pytest.fail(f"Anfrage an fremden Host im Test: {req.full_url}")
        return self._o.open(req, *a, **k)


@pytest.fixture(autouse=True)
def umgebung(tmp_path, monkeypatch):
    monkeypatch.setattr(ab, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(ab, "PROTOKOLL", tmp_path / "audit_abruf.tsv")
    monkeypatch.setattr(ab, "SPERRORT", tmp_path / "sperre")
    monkeypatch.setattr(ab, "TESTMODUS", True)
    monkeypatch.setattr(ab, "ABSTAND", 0.0)
    monkeypatch.setattr(ab, "_OEFFNER", _NurLokal(ab._OEFFNER))
    monkeypatch.setattr(ab, "_OEFFNER_LOKAL", _NurLokal(ab._OEFFNER_LOKAL))
    return tmp_path


def _zeilen():
    if not ab.PROTOKOLL.exists():
        return []
    with ab.PROTOKOLL.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def test_feste_vorgaben():
    quelltext = SKRIPT.read_text(encoding="utf-8")
    assert "ABSTAND = 2.0" in quelltext and "OBERGRENZE = 40" in quelltext and "ZEITLIMIT = 30.0" in quelltext
    assert ab.USER_AGENT == ("ratsatlas-wuppertal-strukturdaten/0.1 "
                             "(+https://github.com/daimpad/ratsatlas-wuppertal; contact@nozilla.de)")
    assert ab.OBERGRENZE == 40 and ab.MAX_WEITERLEITUNGEN == 2 and ab.MAX_BYTES_DATEN == 2_000_000
    assert set(ab.ERLAUBTE_HOSTS) == {"www.offenedaten-wuppertal.de", "offenedaten-wuppertal.de", "www.wuppertal.de",
                                      "daten.wuppertal.de", "www.wegweiser-kommune.de"}
    assert ab.SPALTEN == ("quelle", "url", "zeitstempel", "http_status", "bytes", "zeilen", "pruefsumme_sha256",
                          "cache", "bemerkung")


@pytest.mark.parametrize("url", [
    "https://oparl.wuppertal.de/oparl/system",
    "http://oparl.wuppertal.de/oparl/bodies/0001/papers",
    "https://ris.wuppertal.de/",
    "https://RIS.Wuppertal.de./si0040.asp",
    "https://www.ris.wuppertal.de/",
])
def test_verbotene_hosts_ohne_anfrage(url):
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(url)
    assert e.value.art == "verboten"
    with pytest.raises(ab.AbrufFehler):
        ab.hole(url, methode="HEAD")
    assert _zeilen() == [] and not ab.SPERRORT.exists()


@pytest.mark.parametrize("url", [
    "http://www.wuppertal.de/statistik",                 # kein https
    "https://example.org/datei.csv",                     # nicht erlaubter Host
    "https://maps.wuppertal.de/planung",                 # Stadt, aber nicht freigegeben
    "https://www.wuppertal.de:8443/statistik",           # Port
    "https://nutzer:geheim@www.wuppertal.de/",           # Zugangsdaten
    "https://www.wuppertal.de/a b",                      # Leerzeichen
    "ftp://www.wuppertal.de/datei",
])
def test_regeln_ohne_anfrage(url):
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(url)
    assert e.value.art == "regel"
    assert _zeilen() == []


def test_erlaubte_hosts_bestehen_pruefung():
    for host in ab.ERLAUBTE_HOSTS:
        assert ab.pruefe_url(f"https://{host}/pfad?x=1") == host


def test_loopback_nur_im_testmodus(monkeypatch, server):
    monkeypatch.setattr(ab, "TESTMODUS", False)
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/ok.csv"))
    assert e.value.art == "regel" and server.anfragen == []


def test_methode_und_grenze_geprueft(server):
    for kwargs in ({"methode": "POST"}, {"max_bytes": 0}, {"max_bytes": True}):
        with pytest.raises(ab.AbrufFehler) as e:
            ab.hole(server.url("/ok.csv"), **kwargs)
        assert e.value.art == "regel"
    assert server.anfragen == []


def test_abruf_cache_und_protokoll(server):
    url = server.url("/ok.csv")
    status, kopf, daten = ab.hole(url, quelle="Test")
    assert (status, daten) == (200, CSV) and kopf["Content-Type"] == "text/csv"
    assert server.anfragen[0][3] == ab.USER_AGENT
    daten_pfad, kopf_pfad = ab.cache_pfade(url)
    assert daten_pfad.read_bytes() == CSV and kopf_pfad.exists()
    assert daten_pfad.parent == ab.CACHE and daten_pfad.name.startswith(ab._schluessel(url))
    # zweiter Aufruf aus dem Cache: keine Anfrage
    assert ab.hole(url, quelle="Test") == (200, kopf, CSV)
    assert len(server.anfragen) == 1
    kopfzeile = ab.PROTOKOLL.read_text(encoding="utf-8").splitlines()[0]
    assert kopfzeile.split("\t") == list(ab.SPALTEN)
    z = _zeilen()
    assert [r["cache"] for r in z] == ["nein", "ja"]
    import hashlib
    for r in z:
        assert r["quelle"] == "Test" and r["url"] == url and r["http_status"] == "200"
        assert r["bytes"] == str(len(CSV)) and r["zeilen"] == "2"
        assert r["pruefsumme_sha256"] == hashlib.sha256(CSV).hexdigest()
        assert r["zeitstempel"][:4].isdigit() and "+" in r["zeitstempel"]
    assert ab.anfragen_je_host("127.0.0.1") == 1


def test_head_eigener_cache(server):
    url = server.url("/ok.csv")
    status, kopf, daten = ab.hole(url, methode="HEAD")
    assert status == 200 and daten == b"" and kopf["Content-Length"] == str(len(CSV))
    assert ab.hole(url, methode="HEAD")[0] == 200
    assert [a[0] for a in server.anfragen] == ["HEAD"]
    # GET derselben URL ist ein eigener Eintrag
    assert ab.hole(url)[2] == CSV
    assert [a[0] for a in server.anfragen] == ["HEAD", "GET"]
    z = _zeilen()
    assert z[0]["bemerkung"].startswith("HEAD") and z[0]["pruefsumme_sha256"] == ""


def test_fehlerstatus_nicht_im_cache(server):
    status, _, _ = ab.hole(server.url("/404"))
    assert status == 404
    assert not ab.cache_pfade(server.url("/404"))[1].exists()
    assert not ab.gesperrt("127.0.0.1")


def test_obergrenze_aus_protokoll(server, monkeypatch):
    monkeypatch.setattr(ab, "OBERGRENZE", 3)
    for i in range(3):
        assert ab.hole(server.url(f"/ok.csv?i={i}"))[0] == 200
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/ok.csv?i=99"))
    assert e.value.art == "obergrenze" and len(server.anfragen) == 3
    # Cache-Treffer bleiben möglich und zählen nicht
    assert ab.hole(server.url("/ok.csv?i=0"))[0] == 200 and len(server.anfragen) == 3


def test_obergrenze_40_ueber_prozesse(server):
    # 40 gesendete Anfragen eines früheren Laufs im Protokoll, dazu Cache-Treffer und andere Hosts
    for i in range(40):
        ab.protokolliere("alt", server.url(f"/alt{i}"), 200, b"x")
    ab.protokolliere("alt", server.url("/c"), 200, b"x", cache="ja")
    ab.protokolliere("alt", "https://www.wuppertal.de/x", 200, b"x")
    assert ab.anfragen_je_host("127.0.0.1") == 40 and ab.anfragen_je_host("www.wuppertal.de") == 1
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/ok.csv"))
    assert e.value.art == "obergrenze" and server.anfragen == []


def test_abstand_je_host(server, monkeypatch):
    monkeypatch.setattr(ab, "ABSTAND", 0.6)
    ab.hole(server.url("/ok.csv?a"))
    ab.hole(server.url("/ok.csv?b"))
    ab.hole(server.url("/404"))
    zeiten = [a[2] for a in server.anfragen]
    assert len(zeiten) == 3
    assert all(b - a >= 0.55 for a, b in zip(zeiten, zeiten[1:]))
    assert (ab.SPERRORT / "struktur-127.0.0.1.zeit").exists()


def test_abstand_auch_nach_cache_treffer_nicht_verzoegert(server, monkeypatch):
    ab.hole(server.url("/ok.csv"))
    monkeypatch.setattr(ab, "ABSTAND", 5.0)
    start = time.monotonic()
    ab.hole(server.url("/ok.csv"))   # Cache-Treffer: kein Warten
    assert time.monotonic() - start < 1.0


@pytest.mark.parametrize("pfad,code", [("/429", 429), ("/500", 500)])
def test_sperre_nach_429_und_5xx(server, pfad, code):
    status, _, _ = ab.hole(server.url(pfad))
    assert status == code
    assert ab.gesperrt("127.0.0.1")
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/ok.csv"))
    assert e.value.art == "gesperrt"
    with pytest.raises(ab.AbrufFehler):
        ab.hole(server.url(pfad))   # keine Wiederholung
    assert len(server.anfragen) == 1
    z = _zeilen()
    assert len(z) == 1 and z[0]["http_status"] == str(code) and "gesperrt" in z[0]["bemerkung"]
    assert not ab.cache_pfade(server.url(pfad))[1].exists()


def test_sperre_nach_zeitueberschreitung(server, monkeypatch):
    monkeypatch.setattr(ab, "ZEITLIMIT", 0.3)
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/langsam"))
    assert e.value.art == "zeit" and ab.gesperrt("127.0.0.1")
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/ok.csv"))
    assert e.value.art == "gesperrt" and len(server.anfragen) == 1
    assert _zeilen()[0]["http_status"] == "zeitueberschreitung"


def test_sperre_nach_verbindungsfehler(monkeypatch):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()   # niemand lauscht: Verbindung abgelehnt
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(f"http://127.0.0.1:{port}/x")
    assert e.value.art == "verbindung" and ab.gesperrt("127.0.0.1")
    assert _zeilen()[0]["http_status"] == "verbindungsfehler"


def test_weiterleitung_erlaubtes_ziel_gefolgt(server):
    status, _, daten = ab.hole(server.url("/weiter"))
    assert (status, daten) == (200, CSV)
    assert server.pfade() == ["/weiter", "/ok.csv"]
    z = _zeilen()
    assert [r["http_status"] for r in z] == ["302", "200"]
    assert z[0]["bemerkung"] == f"Weiterleitung nach {server.url('/ok.csv')}"
    assert z[1]["url"] == server.url("/ok.csv")
    # Cache unter der angefragten Adresse
    assert ab.hole(server.url("/weiter"))[2] == CSV and len(server.anfragen) == 2
    assert ab.anfragen_je_host("127.0.0.1") == 2


def test_weiterleitung_relativ(server):
    assert ab.hole(server.url("/weiter_relativ"))[0] == 200
    assert server.pfade() == ["/weiter_relativ", "/ok.csv"]


@pytest.mark.parametrize("pfad,ziel", [("/weiter_oparl", "https://oparl.wuppertal.de/oparl/system"),
                                       ("/weiter_fremd", "https://example.org/datei.csv")])
def test_weiterleitung_verbotenes_ziel_nicht_gefolgt(server, pfad, ziel):
    status, kopf, daten = ab.hole(server.url(pfad))
    assert status == 302 and kopf["Location"] == ziel and daten == b""
    assert server.pfade() == [pfad]
    z = _zeilen()
    assert len(z) == 1 and z[0]["bemerkung"] == f"Weiterleitung nach {ziel}"
    assert not ab.cache_pfade(server.url(pfad))[1].exists()


def test_hoechstens_zwei_weiterleitungen(server):
    status, kopf, _ = ab.hole(server.url("/kette"))
    assert status == 302 and kopf["Location"].endswith("/ok.csv")
    assert server.pfade() == ["/kette", "/kette1", "/kette2"]


def test_zu_grosse_antwort_verworfen(server):
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url("/gross"), max_bytes=100)
    assert e.value.art == "groesse" and e.value.kopf["Content-Length"] == "5000"
    assert not ab.cache_pfade(server.url("/gross"))[1].exists()
    z = _zeilen()
    assert len(z) == 1 and z[0]["bytes"] == "0" and z[0]["cache"] == "nein"
    assert not ab.gesperrt("127.0.0.1")
    # HEAD zeigt die Größe ohne Inhalt
    assert ab.hole(server.url("/gross"), methode="HEAD")[1]["Content-Length"] == "5000"


def test_eine_verbindung_je_host(server):
    ab.SPERRORT.mkdir(parents=True)
    with open(ab.SPERRORT / "struktur-127.0.0.1.lock", "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ab.AbrufFehler) as e:
            ab.hole(server.url("/ok.csv"))
        assert e.value.art == "parallel"
    assert server.anfragen == []
    assert ab.hole(server.url("/ok.csv"))[0] == 200   # nach Freigabe wieder möglich


def test_cli(server, tmp_path):
    env = dict(os.environ, RATSATLAS_STRUKTUR_TEST="ja", RATSATLAS_STRUKTUR_CACHE=str(tmp_path / "cli-cache"),
               RATSATLAS_STRUKTUR_PROTOKOLL=str(tmp_path / "cli.tsv"), RATSATLAS_SPERRE=str(tmp_path / "cli-sperre"))
    lauf = subprocess.run([sys.executable, str(SKRIPT), server.url("/ok.csv"), "--quelle", "CLI",
                           "--ausgabe", "kopie.csv"], env=env, capture_output=True, text=True, timeout=60)
    assert lauf.returncode == 0, lauf.stderr
    zeilen = lauf.stdout.splitlines()
    assert zeilen[0] == "status 200"
    cache = Path(zeilen[1].split(" ", 1)[1])
    assert cache.read_bytes() == CSV and cache.parent == tmp_path / "cli-cache"
    assert (tmp_path / "cli-cache" / "kopie.csv").read_bytes() == CSV
    assert "CLI" in (tmp_path / "cli.tsv").read_text(encoding="utf-8")
    # HEAD
    lauf = subprocess.run([sys.executable, str(SKRIPT), server.url("/ok.csv"), "--head"], env=env,
                          capture_output=True, text=True, timeout=60)
    assert lauf.returncode == 0 and "status 200" in lauf.stdout and "content-length 8" in lauf.stdout
    # Ausgabe außerhalb des Caches und verbotener Host: Abbruch ohne Anfrage
    n = len(server.anfragen)
    lauf = subprocess.run([sys.executable, str(SKRIPT), server.url("/ok.csv?neu"), "--ausgabe",
                           str(tmp_path / "draussen.csv")], env=env, capture_output=True, text=True, timeout=60)
    assert lauf.returncode == 2 and not (tmp_path / "draussen.csv").exists()
    lauf = subprocess.run([sys.executable, str(SKRIPT), "https://oparl.wuppertal.de/oparl/system"], env=env,
                          capture_output=True, text=True, timeout=60)
    assert lauf.returncode == 2 and "verboten" in lauf.stderr
    assert len(server.anfragen) == n


def test_daten_wuppertal_hoechstens_2_mb(monkeypatch):
    grenzen = []

    def attrappe(url, host, methode, grenze, quelle):
        grenzen.append((host, grenze))
        return 404, {}, b""
    monkeypatch.setattr(ab, "_eine_anfrage", attrappe)
    ab.hole("https://daten.wuppertal.de/Infrastruktur_Bauen_Wohnen/x.json", max_bytes=50_000_000)
    ab.hole("https://www.wegweiser-kommune.de/openapi", max_bytes=5_000_000)
    assert grenzen == [("daten.wuppertal.de", 2_000_000), ("www.wegweiser-kommune.de", 5_000_000)]


@pytest.mark.parametrize("pfad,kennzeichen", [("/cf403", "cf-mitigated: challenge"), ("/cf403s", "server: cloudflare")])
def test_403_mit_bot_abwehr_sperrt_host(server, pfad, kennzeichen):
    status, kopf, _ = ab.hole(server.url(pfad))
    assert status == 403 and ab.gesperrt("127.0.0.1")
    z = _zeilen()
    assert len(z) == 1 and "gesperrt" in z[0]["bemerkung"] and kennzeichen in z[0]["bemerkung"]
    # Kopfzeilen als Beleg abgelegt, aber kein Cache-Eintrag
    beleg = ab.statuskopf_pfad(server.url(pfad), "GET", 403)
    assert beleg.exists() and not ab.cache_pfade(server.url(pfad))[1].exists()
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole(server.url(pfad))   # keine Wiederholung
    assert e.value.art == "gesperrt" and len(server.anfragen) == 1


def test_403_ohne_bot_abwehr_sperrt_nicht(server):
    import json
    status, _, _ = ab.hole(server.url("/403"))
    assert status == 403 and not ab.gesperrt("127.0.0.1")
    z = _zeilen()
    assert z[0]["bemerkung"].startswith("server: ") and "gesperrt" not in z[0]["bemerkung"]
    beleg = json.loads(ab.statuskopf_pfad(server.url("/403"), "GET", 403).read_text(encoding="utf-8"))
    assert beleg["status"] == 403 and beleg["kopf"]["Content-Type"] == "text/plain"
    # Beleg wird nie als Cache-Treffer verwendet
    assert ab.hole(server.url("/403"))[0] == 403 and len(server.anfragen) == 2


def test_host_mit_und_ohne_www_zusammen():
    assert ab.host_schluessel("www.offenedaten-wuppertal.de") == ab.host_schluessel("offenedaten-wuppertal.de")
    assert ab.host_schluessel("www.wuppertal.de") != ab.host_schluessel("daten.wuppertal.de")
    for i in range(20):
        ab.protokolliere("alt", f"https://www.offenedaten-wuppertal.de/a{i}", 200, b"x")
        ab.protokolliere("alt", f"https://offenedaten-wuppertal.de/b{i}", 200, b"x")
    assert ab.anfragen_je_host("offenedaten-wuppertal.de") == 40
    assert ab.anfragen_je_host("www.offenedaten-wuppertal.de") == 40
    for url in ("https://offenedaten-wuppertal.de/neu", "https://www.offenedaten-wuppertal.de/neu"):
        with pytest.raises(ab.AbrufFehler) as e:
            ab.hole(url)   # vor jeder Anfrage abgelehnt (der Testöffner ließe ohnehin nur 127.0.0.1 zu)
        assert e.value.art == "obergrenze"


def test_sperre_und_verbindung_gemeinsam_fuer_www():
    ab.sperre_host("www.offenedaten-wuppertal.de", "Test")
    assert ab.gesperrt("offenedaten-wuppertal.de")
    with pytest.raises(ab.AbrufFehler) as e:
        ab.hole("https://offenedaten-wuppertal.de/x")
    assert e.value.art == "gesperrt"
    (ab.SPERRORT / "struktur-offenedaten-wuppertal.de.gesperrt").unlink()
    with open(ab.SPERRORT / "struktur-offenedaten-wuppertal.de.lock", "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ab.AbrufFehler) as e:
            ab.hole("https://www.offenedaten-wuppertal.de/x")
        assert e.value.art == "parallel"
    assert _zeilen() == []
