"""Gemeinsame Hilfen der Tests: lokaler OParl-Testserver mit synthetischen Daten (keine Daten der Stadt).

Testserver, synthetische Objekte (`Daten`) und Geo-Attrappe stehen in tests/oparl_testserver.py (dort beschrieben);
die Fixture `oparl` startet den Server und lenkt die Pfade der Pipeline um.
Geodaten: `geo_attrappe` schreibt eine synthetische Geo-Attrappe (zwei Rechtecke, ein Stadtbezirk, eine Straße) in das
Testverzeichnis, passend zu den Namen der synthetischen Testobjekte; keine Daten der Stadt, keine echten Koordinaten.
Wuppertal hat kein data/ im Repository (Köln nutzt dort echte Geodaten).
Dazu Fabriken für lokale TLS-Server: `tls_server` (selbst signiertes Zertifikat, dem der Client nicht vertraut) und
`abbrechender_server` (Handshake endet unerwartet oder wird zurückgesetzt).
"""
import os
import shutil
import tempfile

# Sperrdatei der Messskripte (explore/abruf.py) während der Tests nie in ~/.cache, sondern in einem Temp-Ordner, der am
# Ende der Testsitzung entfernt wird (nur, wenn er hier angelegt wurde). Gesetzt vor dem Import der Messskripte, die den
# Ort beim Import lesen; Teilprozesse der Tests reichen RATSATLAS_SPERRE weiter.
_SPERRE_TEMP = None
if not os.environ.get("RATSATLAS_SPERRE"):
    _SPERRE_TEMP = tempfile.mkdtemp(prefix="ratsatlas-sperre-")
    os.environ["RATSATLAS_SPERRE"] = _SPERRE_TEMP
import socket
import socketserver
import ssl
import struct
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from oparl_testserver import Daten, geo_attrappe, oparl_server_starten, pfade_umlenken  # noqa: F401 (Daten, geo_attrappe für Tests)


def pytest_sessionfinish(session, exitstatus):
    if _SPERRE_TEMP:
        shutil.rmtree(_SPERRE_TEMP, ignore_errors=True)


def _testhost(url):
    """Host, den ein Test erreichen darf: Loopback, localhost oder die reservierte Domain .invalid."""
    from pipeline import abruf
    return abruf.testadresse(url)


class _Waechter:
    """Hülle um einen modulweiten Öffner: Anfragen an Hosts außer Loopback und .invalid lassen den Test sofort
    fehlschlagen (ohne zu senden). Schützt vor echten Anfragen an Server der Stadt, Bonns oder Kölns, falls ein
    Rückschritt im Code eine Sperre umgeht (die Tests laufen in CI mit offenem Netz). Tests, die den Öffner selbst
    ersetzen, umgehen die Hülle ausdrücklich."""

    def __init__(self, oeffner):
        self._oeffner = oeffner

    def open(self, req, *a, **k):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if not _testhost(url):
            pytest.fail(f"Anfrage an einen fremden Host im Test: {url}")
        return self._oeffner.open(req, *a, **k)

    def __getattr__(self, name):
        return getattr(self._oeffner, name)


@pytest.fixture(autouse=True)
def _keine_fremden_anfragen(monkeypatch):
    """Für jeden Test: modulweite Öffner von pipeline/abruf.py und pipeline/net.py nur für Loopback und .invalid;
    danach die Sperre gegen gleichzeitige Abrufe (abruf.sperre_halten) lösen, damit sie nicht über den Test hinaus im
    Testprozess gehalten wird (sonst brächen spätere Tests mit Messwerkzeugen als `parallel` ab)."""
    from pipeline import abruf, net
    monkeypatch.setattr(abruf, "_OEFFNER", _Waechter(abruf._OEFFNER))
    monkeypatch.setattr(net, "_OEFFNER", _Waechter(net._OEFFNER))
    yield
    abruf.sperre_freigeben()


@pytest.fixture
def roher_server():
    """Fabrik für lokale TCP-Server auf 127.0.0.1, die abgeschnittene oder unlesbare Antworten senden: `starten(antwort)`
    liest den Kopf jeder Anfrage, sendet `antwort` (Bytes, unverändert) und schließt die Verbindung. Der Server hat
    `anfragen` (erste Zeile jeder Anfrage) und `url`; am Ende des Tests wird er beendet."""
    gestartet = []

    def starten(antwort):
        anfragen = []

        class H(socketserver.BaseRequestHandler):
            def handle(self):
                daten = b""
                while b"\r\n\r\n" not in daten:
                    teil = self.request.recv(4096)
                    if not teil:
                        break
                    daten += teil
                anfragen.append(daten.split(b"\r\n", 1)[0].decode("latin-1"))
                self.request.sendall(antwort)
                self.request.shutdown(socket.SHUT_WR)

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        server.daemon_threads = True
        server.anfragen, server.url = anfragen, f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        gestartet.append(server)
        return server

    yield starten
    for server in gestartet:
        server.shutdown()
        server.server_close()


@pytest.fixture
def tls_server(tmp_path):
    """HTTPS-Server auf 127.0.0.1 mit selbst signiertem Zertifikat (openssl), dem der Client nicht vertraut: Die
    Zertifikatsprüfung scheitert im Handshake, bevor eine HTTP-Anfrage gesendet ist. `anfragen`: empfangene
    HTTP-Anfragen, `url`, `zertifikat` (zum Gegenversuch mit vertrautem Zertifikat)."""
    if not shutil.which("openssl"):
        pytest.skip("openssl fehlt")
    schluessel, zertifikat = tmp_path / "tls_schluessel.pem", tmp_path / "tls_zertifikat.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
                    "-keyout", str(schluessel), "-out", str(zertifikat), "-days", "1", "-subj", "/CN=127.0.0.1",
                    "-addext", "subjectAltName=IP:127.0.0.1"], check=True, capture_output=True, timeout=60)
    anfragen = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            anfragen.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    kontext.load_cert_chain(zertifikat, schluessel)
    server.socket = kontext.wrap_socket(server.socket, server_side=True)
    server.anfragen, server.zertifikat = anfragen, zertifikat
    server.url = f"https://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def abbrechender_server():
    """Fabrik für TCP-Server auf 127.0.0.1, die den TLS-Handshake abbrechen: `starten(reset)` liest den Beginn des
    Handshakes und schließt die Verbindung (unerwartetes Ende) bzw. setzt sie zurück (`reset`, SO_LINGER 0). Der Server
    hat `verbindungen` und `url` (https)."""
    gestartet = []

    def starten(reset=False):
        verbindungen = []

        class H(socketserver.BaseRequestHandler):
            def handle(self):
                verbindungen.append(self.request.recv(4096)[:1])
                if reset:
                    self.request.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                self.request.close()

        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        server.daemon_threads = True
        server.verbindungen, server.url = verbindungen, f"https://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        gestartet.append(server)
        return server

    yield starten
    for server in gestartet:
        server.shutdown()
        server.server_close()


@pytest.fixture
def oparl(tmp_path, monkeypatch):
    """Startet den Testserver und lenkt alle Pfade der Pipeline in ein temporäres Verzeichnis (oparl_testserver.py)."""
    server, daten = oparl_server_starten()
    pfade_umlenken(tmp_path, daten.b, monkeypatch.setattr)
    monkeypatch.delenv("RATSATLAS_STADT_INFORMIERT", raising=False)
    monkeypatch.delenv("RATSATLAS_VOLLABRUF", raising=False)
    yield daten
    server.shutdown()
