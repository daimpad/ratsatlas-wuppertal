"""Live-Prüfung (tools/live_pruefen.py, .github/workflows/live.yml): gegen einen lokalen HTTP-Server auf 127.0.0.1, der
Hauptadresse, Ausweichadresse, Branch deploy (GitHub-API: contents und commits) und die Umleitung http → https nachbildet; Zertifikat als
Attrappe bzw. mit einem lokalen TLS-Server (conftest.tls_server). Keine echten Abrufe: Der Öffner des Skripts lässt im
Test nur 127.0.0.1 zu."""
import importlib.util
import re
import ssl
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pipeline import config

ROOT = config.ROOT
WF = ROOT / ".github" / "workflows" / "live.yml"
SHA = "0123456789abcdef0123456789abcdef01234567"
NEU = "fedcba9876543210fedcba9876543210fedcba98"
SICHERHEIT = {
    "Content-Security-Policy": "frame-ancestors 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000",
}


def _modul():
    spec = importlib.util.spec_from_file_location("live_pruefen", ROOT / "tools" / "live_pruefen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


live = _modul()


@pytest.fixture(autouse=True)
def _nur_lokal(monkeypatch):
    """Der Öffner des Skripts lässt nur 127.0.0.1 zu; jede andere Adresse lässt den Test sofort fehlschlagen."""
    echt = live._OEFFNER

    class Waechter:
        def open(self, req, *a, **k):
            host = urllib.parse.urlsplit(req.full_url).hostname
            if host != "127.0.0.1":
                pytest.fail(f"Anfrage an einen fremden Host im Test: {req.full_url}")
            return echt.open(req, *a, **k)

    monkeypatch.setattr(live, "_OEFFNER", Waechter())


def _seite(titel, canonical, noindex=True):
    robots = '<meta name="robots" content="noindex">' if noindex else '<meta name="robots" content="index, follow">'
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">\n  {robots}\n  <title>{titel}</title>\n'
            f'  <link rel="canonical" href="{canonical}"></head><body></body></html>').encode()


INHALT = "/api/daimpad/ratsatlas-wuppertal/contents/version.txt"     # GitHub-API: version.txt im Branch deploy
COMMIT = "/api/daimpad/ratsatlas-wuppertal/commits/deploy"           # GitHub-API: Kopf des Branches deploy


class Seitenattrappe:
    """Routen: Pfad (ohne Query) → (Status, Kopfzeilen, Inhalt oder Funktion(query) → Inhalt) oder Funktion(query) →
    solches Tupel. `anfragen`: Pfade mit Query; `kopf`: (Pfad, Kopfzeilen) je Anfrage."""

    def __init__(self):
        self.anfragen, self.kopf = [], []
        routen = self.routen = {}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                pfad, _, query = self.path.partition("?")
                self.server.seite.anfragen.append(self.path)
                self.server.seite.kopf.append((self.path, dict(self.headers)))
                eintrag = routen.get(pfad, routen["*"])
                status, kopf, inhalt = eintrag(query) if callable(eintrag) else eintrag
                if callable(inhalt):
                    inhalt = inhalt(query)
                self.send_response(status)
                for k, v in kopf.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(inhalt)))
                self.end_headers()
                self.wfile.write(inhalt)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.seite = self
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        self.haupt, self.spiegel = self.url, self.url + "spiegel/"
        kopf = dict(SICHERHEIT, **{"X-Robots-Tag": "noindex", "Content-Type": "text/html; charset=utf-8"})
        routen.update({
            "*": (404, kopf, _seite("Seite nicht gefunden – Ratsatlas Wuppertal", self.haupt)),
            "/": (200, dict(kopf), _seite("Ratsatlas Wuppertal – Was Rat und Bezirksvertretungen beraten", self.haupt)),
            "/app.js": (200, dict(SICHERHEIT, **{"Content-Type": "text/javascript"}), b"// app"),
            "/version.txt": (200, {}, (SHA + "\n").encode()),
            "/spiegel/": (200, {}, _seite("Ratsatlas Wuppertal – Was Rat und Bezirksvertretungen beraten", self.haupt)),
            INHALT: (200, {}, (SHA + "\n").encode()),
            COMMIT: (404, {}, b"{}"),
            "/http": (301, {"Location": self.haupt}, b""),
        })
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def pruefung(self, **kw):
        self.zeilen = []
        args = dict(haupt=self.haupt, spiegel=self.spiegel, repo="daimpad/ratsatlas-wuppertal",
                    http_url=self.url + "http", quelle_inhalt=self.url + "api/{repo}/contents/version.txt?ref=deploy",
                    quelle_api=self.url + "api/{repo}/commits/deploy",
                    zertifikat=lambda host, port: (80.0, "Feb  1 12:00:00 2027 GMT"),
                    versuche=1, pause_fehler=0, pause=0, timeout=5, ausgabe=self.zeilen.append, token="",
                    stand_abstand=0)
        args.update(kw)
        return live.Pruefung(**args)

    def fehler(self, p):
        return [t for z, t in p.ergebnisse if z == "FEHLER"]


@pytest.fixture
def seite(monkeypatch):
    for name in ("GITHUB_ACTIONS", "HTTPS_PROXY", "https_proxy", "GITHUB_TOKEN"):   # gleich lokal und in CI
        monkeypatch.delenv(name, raising=False)
    s = Seitenattrappe()
    yield s
    s.server.shutdown()
    s.server.server_close()


def test_alles_in_ordnung_ohne_daten(seite):
    p = seite.pruefung()
    assert p.alles() == 0, seite.fehler(p)
    assert all(z == "ok" for z, _ in p.ergebnisse)
    texte = "\n".join(t for _, t in p.ergebnisse)
    for teil in ("keine Daten", "X-Robots-Tag noindex", "Canonical", "Umleitung", "eigene 404-Seite", "Zertifikat",
                 "Stand", "Ausweichadresse"):
        assert teil in texte, teil
    for name in SICHERHEIT:
        assert texte.count(f"Kopfzeile {name} auf ") == 2, name
    pfade = [a.partition("?")[0] for a in seite.anfragen]
    for pfad in live.GESPERRT:
        assert "/" + pfad in pfade, pfad
    assert "/data/export/wuppertal/index.json" in pfade
    # Startseite nur einmal abgerufen (Kopfzeilen aus derselben Antwort); wenige Anfragen insgesamt
    assert pfade.count("/") == 1 and p.anfragen == len(seite.anfragen) <= 20
    assert seite.zeilen[0].startswith("ok      ") and seite.zeilen[-1].endswith(f"0 Fehler, {p.anfragen} Anfragen")


def test_mit_daten_ohne_noindex(seite):
    seite.routen["/data/export/wuppertal/index.json"] = (200, {}, b"{}")
    p = seite.pruefung()
    assert p.alles() == 1
    assert len(seite.fehler(p)) == 1 and "mit Daten" in seite.fehler(p)[0]
    status, kopf, _ = seite.routen["/"]
    kopf.pop("X-Robots-Tag")
    seite.routen["/"] = (status, kopf, _seite("Ratsatlas Wuppertal", seite.haupt, noindex=False))
    p = seite.pruefung()
    assert p.alles() == 0, seite.fehler(p)


def test_ohne_daten_ohne_x_robots_tag(seite):
    seite.routen["/"][1].pop("X-Robots-Tag")
    p = seite.pruefung()
    assert p.alles() == 1 and "X-Robots-Tag" in seite.fehler(p)[0]


def test_ohne_daten_ohne_meta_noindex(seite):
    status, kopf, _ = seite.routen["/"]
    seite.routen["/"] = (status, kopf, _seite("Ratsatlas Wuppertal", seite.haupt, noindex=False))
    p = seite.pruefung()
    assert p.alles() == 1 and "meta" in seite.fehler(p)[0]


def test_datenstand_unklar(seite):
    seite.routen["/data/export/wuppertal/index.json"] = (500, {}, b"")
    p = seite.pruefung()
    assert p.alles() == 1 and "Datenstand unklar" in seite.fehler(p)[0]


def test_kopfzeile_fehlt_auf_app_js(seite):
    seite.routen["/app.js"][1].pop("Strict-Transport-Security")
    p = seite.pruefung()
    assert p.alles() == 1
    assert seite.fehler(p) == [f"Kopfzeile Strict-Transport-Security auf {seite.haupt}app.js: fehlt"]


def test_kopfzeile_mit_falschem_wert(seite):
    seite.routen["/"][1]["X-Content-Type-Options"] = "sniff"
    p = seite.pruefung()
    assert p.alles() == 1 and "X-Content-Type-Options" in seite.fehler(p)[0]


def test_titel_falsch_und_canonical_falsch(seite):
    status, kopf, _ = seite.routen["/"]
    seite.routen["/"] = (status, kopf, _seite("Ratsatlas Bonn", "https://anders.invalid/"))
    p = seite.pruefung()
    assert p.alles() == 2
    assert "Titel" in seite.fehler(p)[0] and "Canonical" in seite.fehler(p)[1]


def test_quelldateien_abrufbar(seite):
    seite.routen["/CLAUDE.md"] = (200, {}, b"# Prompt")
    seite.routen["/.git/HEAD"] = (403, {}, b"")
    p = seite.pruefung()
    assert p.alles() == 2
    assert "CLAUDE.md: Status 200" in seite.fehler(p)[0] and ".git/HEAD: Status 403" in seite.fehler(p)[1]


def test_fehlerseite_ohne_eigenen_titel(seite):
    seite.routen["*"] = (404, {}, b"<html><head><title>404 Not Found</title></head></html>")
    p = seite.pruefung()
    assert p.alles() == 1 and "eigene 404-Seite" in seite.fehler(p)[0]


@pytest.mark.parametrize("antwort", [(302, {"Location": "HAUPT"}), (301, {"Location": "https://anders.invalid/"}),
                                     (200, {})])
def test_umleitung_http_auf_https_fehlt(seite, antwort):
    status, kopf = antwort
    seite.routen["/http"] = (status, {k: v.replace("HAUPT", seite.haupt) for k, v in kopf.items()}, b"")
    p = seite.pruefung()
    assert p.alles() == 1 and "Umleitung" in seite.fehler(p)[0]


def test_umleitung_308_und_ohne_schraegstrich(seite):
    seite.routen["/http"] = (308, {"Location": seite.haupt.rstrip("/")}, b"")
    assert seite.pruefung().alles() == 0


def test_zertifikat(seite, monkeypatch):
    p = seite.pruefung(zertifikat=lambda h, port: (10.2, "Nov 20 12:00:00 2026 GMT"))
    assert p.alles() == 1 and "noch 10 Tage (mindestens 14)" in seite.fehler(p)[0]

    def ungueltig(h, port):
        raise ssl.SSLCertVerificationError("certificate has expired")
    p = seite.pruefung(zertifikat=ungueltig)
    assert p.alles() == 1 and "ungültig" in seite.fehler(p)[0]

    def keine_verbindung(h, port):
        raise ConnectionRefusedError("refused")
    p = seite.pruefung(zertifikat=keine_verbindung)
    assert p.alles() == 1 and "keine Verbindung" in seite.fehler(p)[0]
    # hinter einem TLS-Proxy nicht aussagekräftig: nur Hinweis, keine Verbindung
    aufrufe = []
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    p = seite.pruefung(zertifikat=lambda h, port: aufrufe.append(h) or (1.0, "x"))
    assert p.alles() == 0 and aufrufe == []
    assert ("Hinweis", "Zertifikat 127.0.0.1: hinter Proxy nicht prüfbar (HTTPS_PROXY gesetzt)") in p.ergebnisse


def test_zertifikat_tage_mit_lokalem_tls_server(tls_server):
    port = int(tls_server.url.rsplit(":", 1)[1])
    with pytest.raises(ssl.SSLCertVerificationError):
        live.zertifikat_tage("127.0.0.1", port, timeout=5)
    kontext = ssl.create_default_context(cafile=str(tls_server.zertifikat))
    tage, ablauf = live.zertifikat_tage("127.0.0.1", port, kontext=kontext, timeout=5)
    assert 0 < tage <= 1.01 and ablauf.endswith("GMT")
    assert tls_server.anfragen == []


def test_stand_mit_zwischenspeicher(seite):
    """nginx liefert erst den alten Stand; mit Parameter gegen Zwischenspeicher den neuen."""
    seite.routen[INHALT] = (200, {}, NEU.encode())
    seite.routen["/version.txt"] = (200, {}, lambda q: (NEU if q.startswith("pruefung=") else SHA).encode())
    p = seite.pruefung()
    assert p.alles() == 0, seite.fehler(p)
    versionen = [a for a in seite.anfragen if a.startswith("/version.txt")]
    assert versionen[0] == "/version.txt" and re.fullmatch(r"/version\.txt\?pruefung=\d+", versionen[1])
    # Soll aus der GitHub-API (ohne CDN), bei Abweichung neu abgerufen
    assert [a for a in seite.anfragen if a.startswith(INHALT)] == [INHALT + "?ref=deploy"] * 2
    assert not any("raw" in a for a in seite.anfragen)


def test_stand_soll_zunaechst_alt(seite):
    """Die Quelle des Soll-Stands liefert zunächst den alten Stand (Zwischenspeicher), die Hauptadresse schon den
    neuen: Soll wird bei der Abweichung neu abgerufen, kein Fehler."""
    abrufe = []
    seite.routen[INHALT] = lambda q: abrufe.append(q) or (200, {}, (SHA if len(abrufe) == 1 else NEU).encode())
    seite.routen["/version.txt"] = (200, {}, NEU.encode())
    p = seite.pruefung()
    assert p.alles() == 0, seite.fehler(p)
    assert len(abrufe) == 2 and len([a for a in seite.anfragen if a.startswith("/version.txt")]) == 2


def test_stand_abweichend(seite):
    seite.routen[INHALT] = (200, {}, NEU.encode())
    p = seite.pruefung()
    assert p.alles() == 1
    assert f"= {SHA[:7]}, Branch deploy = {NEU[:7]}" in seite.fehler(p)[0] and "Plesk" in seite.fehler(p)[0]
    assert len([a for a in seite.anfragen if a.startswith("/version.txt")]) == 2
    assert len([a for a in seite.anfragen if a.startswith(INHALT)]) == 2


def test_stand_warten_auf_plesk(seite, monkeypatch):
    """Plesk liefert den neuen Stand erst nach einigen Minuten: Mit stand_versuche (--warten) wird im Abstand
    wiederholt, ohne bleibt es bei einem Versuch (Soll und Ist je zweimal)."""
    pausen = []
    monkeypatch.setattr(live.time, "sleep", pausen.append)
    ist = []
    seite.routen[INHALT] = (200, {}, NEU.encode())
    seite.routen["/version.txt"] = lambda q: ist.append(q) or (200, {}, (NEU if len(ist) >= 4 else SHA).encode())
    p = seite.pruefung()
    assert p.alles() == 1 and len(ist) == 2
    ist.clear()
    p = seite.pruefung(stand_versuche=5, stand_abstand=60)
    assert p.alles() == 0, seite.fehler(p)
    assert len(ist) == 4 and pausen.count(60) == 2 and all(q.startswith("pruefung=") for q in ist[1:])
    # bleibt es beim alten Stand: Fehler nach fünf Versuchen, mit Angabe der Versuche
    ist.clear()
    pausen.clear()
    seite.routen["/version.txt"] = lambda q: ist.append(q) or (200, {}, SHA.encode())
    p = seite.pruefung(stand_versuche=5, stand_abstand=60)
    assert p.alles() == 1 and len(ist) == 6 and pausen.count(60) == 4
    assert "5 Versuche im Abstand von 60 s" in seite.fehler(p)[0]


def test_stand_token_nur_an_github_api(seite):
    p = seite.pruefung(token="geheim-test")
    assert p.alles() == 0, seite.fehler(p)
    mit = sorted({pfad.partition("?")[0] for pfad, kopf in seite.kopf if "Authorization" in kopf})
    assert mit == [INHALT]
    assert all(kopf["Authorization"] == "Bearer geheim-test" and kopf["Accept"] == "application/vnd.github.raw"
               for pfad, kopf in seite.kopf if pfad.startswith(INHALT))
    assert "geheim-test" not in "\n".join(seite.zeilen)
    # ohne Token: keine Kopfzeile Authorization
    seite.kopf.clear()
    assert seite.pruefung(token="").alles() == 0
    assert not any("Authorization" in kopf for _, kopf in seite.kopf)


def test_token_aus_umgebung(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "aus-umgebung")
    assert live.Pruefung(zertifikat=None).token == "aus-umgebung"
    monkeypatch.delenv("GITHUB_TOKEN")
    assert live.Pruefung(zertifikat=None).token == ""


def test_stand_aus_commit_nachricht(seite):
    seite.routen[INHALT] = (404, {}, b"")
    seite.routen[COMMIT] = (200, {}, b'{"commit": {"message": "Seite aus 0123456\\n"}}')
    p = seite.pruefung()
    assert p.alles() == 0, seite.fehler(p)
    assert any("Commit-Nachricht des Branches deploy" in t for _, t in p.ergebnisse)


def test_stand_nicht_ermittelbar(seite):
    seite.routen[INHALT] = (200, {}, b"<html>")
    seite.routen[COMMIT] = (200, {}, b"kein json")
    p = seite.pruefung()
    assert p.alles() == 1 and "nicht ermittelbar" in seite.fehler(p)[0]


def test_ausweichadresse_canonical_auf_spiegel(seite):
    seite.routen["/spiegel/"] = (200, {}, _seite("Ratsatlas Wuppertal", seite.spiegel))
    p = seite.pruefung()
    assert p.alles() == 1 and seite.fehler(p)[0].startswith("Ausweichadresse: Canonical")


def test_hauptadresse_nicht_erreichbar(seite):
    """Geschlossener Port: Fehler je Prüfung, keine Ausnahme; Netzfehler werden wiederholt."""
    seite.server.shutdown()
    seite.server.server_close()
    p = seite.pruefung(versuche=2)
    assert p.alles() > 10
    assert any("keine Antwort" in f for f in seite.fehler(p))
    assert p.anfragen >= 2 * 10


@pytest.mark.parametrize("status", [503, 502, 429])
def test_voruebergehender_fehlerstatus_wird_wiederholt(seite, status):
    """Webhosting während einer Auslieferung (502/503) bzw. Ratenbegrenzung (429): erst Fehler, dann 200."""
    zaehler = []
    start = seite.routen["/"]
    seite.routen["/"] = lambda q: zaehler.append(q) or ((status, {}, b"") if len(zaehler) == 1 else start)
    p = seite.pruefung(versuche=3)
    assert p.alles() == 0, seite.fehler(p)
    assert len(zaehler) == 2
    # dauerhaft 503: nach `versuche` Anfragen ein Fehler; 404 und 403 werden nicht wiederholt
    seite.routen["/"] = lambda q: zaehler.append(q) or (503, {}, b"")
    zaehler.clear()
    p = seite.pruefung(versuche=3)
    assert p.alles() >= 1
    assert len(zaehler) == 3 and any("Hauptadresse" in f and "Status 503" in f for f in seite.fehler(p))
    seite.routen["/"] = start
    seite.routen["/CLAUDE.md"] = lambda q: zaehler.append(q) or (403, {}, b"")
    zaehler.clear()
    seite.pruefung(versuche=3).alles()
    assert len(zaehler) == 1


def test_proxy_im_workflow_ist_fehler(seite, monkeypatch):
    """Hinter einem Proxy entfallen Zertifikat und (bei Netzfehler) Umleitung: lokal Hinweis, im Workflow Fehler."""
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")   # Port 9: keine Antwort, auch nicht auf http
    p = seite.pruefung(http_url="http://127.0.0.1:9/")
    p.zertifikat_pruefen()
    p.umleitung()
    assert [z for z, _ in p.ergebnisse] == ["Hinweis", "Hinweis"]
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    p = seite.pruefung(http_url="http://127.0.0.1:9/")
    p.zertifikat_pruefen()
    p.umleitung()
    assert [z for z, _ in p.ergebnisse] == ["FEHLER", "FEHLER"]
    assert all("im Workflow darf kein Proxy gesetzt sein" in t for _, t in p.ergebnisse)
    assert sum(z.startswith("::error::") for z in seite.zeilen) == 2


def test_github_actions_anmerkung(seite, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    seite.routen["/CLAUDE.md"] = (200, {}, b"")
    p = seite.pruefung()
    assert p.alles() == 1
    assert [z for z in seite.zeilen if z.startswith("::error::")] == ["::error::" + seite.fehler(p)[0]]


def test_main_exit_code_und_umgebung(monkeypatch):
    gesehen = []

    class Attrappe:
        def __init__(self, *a, **k):
            gesehen.append((a, k))

        def alles(self):
            return fehler

    monkeypatch.setattr(live, "Pruefung", Attrappe)
    monkeypatch.setenv("SITE_URL", "https://beispiel.invalid/")
    monkeypatch.delenv("SPIEGEL_URL", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    fehler = 3
    assert live.main([]) == 1
    fehler = 0
    assert live.main(["--repo", "a/b"]) == 0
    assert live.main(["--warten"]) == 0
    einmal, warten = {"stand_versuche": 1, "stand_abstand": 60.0}, {"stand_versuche": 5, "stand_abstand": 60.0}
    assert gesehen == [(("https://beispiel.invalid/", live.SPIEGEL, live.REPO), einmal),
                       (("https://beispiel.invalid/", live.SPIEGEL, "a/b"), einmal),
                       (("https://beispiel.invalid/", live.SPIEGEL, live.REPO), warten)]


def test_hilfsfunktionen():
    assert live.gleicher_stand(SHA, SHA[:7]) and live.gleicher_stand(SHA[:7], SHA)
    assert not live.gleicher_stand(SHA, NEU) and not live.gleicher_stand("lokal", "lokal")
    assert not live.gleicher_stand("", SHA) and not live.gleicher_stand(SHA[:6], SHA)
    assert live.titel("<title>Seite nicht gefunden &ndash; Ratsatlas Wuppertal</title>") == live.TITEL_404
    assert live.mit_schraegstrich("https://a.invalid") == "https://a.invalid/"
    assert live.STADT == config.STADT and live.HAUPT == "https://wuppertal.ratsatlas.de/"
    p = live.Pruefung(zertifikat=None)
    assert (p.host, p.port, p.http_url) == ("wuppertal.ratsatlas.de", 443, "http://wuppertal.ratsatlas.de/")


def test_kopfzeilen_wie_htaccess_und_titel_wie_seite():
    htaccess = (ROOT / "deploy" / "htaccess").read_text(encoding="utf-8")
    for name, teil in live.KOPFZEILEN.items():
        assert re.search(rf'Header always set {name} "[^"]*{re.escape(teil)}', htaccess), name
    assert f"<title>{live.TITEL_404}</title>" in (ROOT / "site" / "404.html").read_text(encoding="utf-8")
    assert f"<title>{live.TITEL} – " in (ROOT / "site" / "index.html").read_text(encoding="utf-8")


# --- .github/workflows/live.yml (statisch) --------------------------------------------------------------------------

def _wf():
    return WF.read_text(encoding="utf-8")


def _code():
    return "\n".join(z for z in _wf().splitlines() if not z.lstrip().startswith("#"))


def test_live_yml_ausloeser():
    kopf = _code().split("\njobs:\n")[0]
    seiten_name = re.search(r"^name: (.*)$", (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"), re.M).group(1)
    assert seiten_name == "Seite veröffentlichen"
    assert re.search(r'^on:\n  workflow_run:\n    workflows: \["Seite veröffentlichen"\]\n    types: \[completed\]\n'
                     r'  schedule:\n    - cron: "(\d+) (\d+) \* \* \*"\n  workflow_dispatch:\n', kopf, re.M)
    minute, stunde = map(int, re.search(r'cron: "(\d+) (\d+) ', kopf).groups())
    # tagsüber (UTC 6–18 Uhr), also nie im OParl-Zeitfenster 23–1 Uhr (MEZ/MESZ); nicht zur vollen Stunde
    assert 6 <= stunde <= 18 and minute not in (0, 30)
    for wort in ("push:", "pull_request"):
        assert wort not in kopf, wort


def test_live_yml_nur_nach_erfolg_auf_main_und_wartezeit():
    code = _code()
    assert "github.event.workflow_run.conclusion == 'success'" in code
    assert "github.event.workflow_run.head_branch == 'main'" in code
    m = re.search(r"if: github.event_name == 'workflow_run'\n\s+run: sleep (\d+)\n", code)
    assert m and int(m.group(1)) >= 120
    assert code.index("sleep") < code.index("python3 tools/live_pruefen.py")
    # nur nach einer Veröffentlichung wiederholt prüfen (--warten), sonst ein Versuch
    assert re.search(r'if \[ "\$AUSLOESER" = workflow_run \]; then\n\s+python3 tools/live_pruefen.py --warten\n'
                     r'\s+else\n\s+python3 tools/live_pruefen.py\n\s+fi', code)
    assert "AUSLOESER: ${{ github.event_name }}" in code and code.count("--warten") == 1


def test_live_yml_gepinnt_rechte_ohne_secrets():
    wf, code = _wf(), _code()
    uses = re.findall(r"uses:\s*(\S+)(.*)$", wf, re.M)
    assert uses
    for aktion, rest in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", aktion) and re.match(r"\s+# v\d", rest), aktion
    assert re.search(r"^permissions:\n  contents: read\n", code, re.M)
    assert re.findall(r"^\s+(\w[\w-]*): (read|write)$", code, re.M) == [("contents", "read"), ("contents", "read")]
    # Token des Laufs (nur Leserecht) genau einmal, für die GitHub-API im Prüfschritt; sonst keine Zugangsdaten
    token = "          GITHUB_TOKEN: ${{ github.token }}\n"
    assert code.count(token) == 1 and code.lower().count("token") == 2
    pruefschritt = code.split("- name: Hauptadresse und Ausweichadresse prüfen\n")[1]
    assert token in pruefschritt.split("run:")[0]
    for wort in ("secrets", "write", "GH_TOKEN", "token", "pip ", "npm "):
        assert wort not in code.replace(token, ""), wort
    assert wf.count("actions/checkout@") == wf.count("persist-credentials: false") == 1
    assert "SITE_URL: ${{ vars.SITE_URL || 'https://wuppertal.ratsatlas.de/' }}" in code
    for host in ("oparl.wuppertal.de", "ris.wuppertal.de", "daten.wuppertal.de", "offenedaten-wuppertal.de",
                 "www.wuppertal.de"):
        assert host not in wf and host not in (ROOT / "tools" / "live_pruefen.py").read_text(encoding="utf-8"), host
