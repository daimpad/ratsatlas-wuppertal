"""Live-Prüfung der veröffentlichten Seite (Workflow .github/workflows/live.yml; docs/PLESK.md C).

Prüft die Hauptadresse (SITE_URL, Vorgabe https://wuppertal.ratsatlas.de/) und die Ausweichadresse auf GitHub Pages:
Status und Titel, noindex (HTML und X-Robots-Tag), solange keine Daten vorliegen (data/export/wuppertal/index.json
liefert 404), Canonical, Sicherheitskopfzeilen aus deploy/htaccess auf / und app.js, Umleitung http → https, eigene
404-Seite, keine Quelldateien abrufbar, Zertifikat (mindestens 14 Tage Restlaufzeit) und den Stand: version.txt der
Hauptadresse (geschrieben von tools/seite_bauen.py) muss dem Kopf des Branches deploy entsprechen. Den Soll-Stand liefert
die GitHub-API ohne CDN dazwischen (version.txt des Branches deploy über contents, sonst die Commit-Nachricht „Seite aus
<sha7>“ über commits); nicht raw.githubusercontent.com, das bis zu 300 s alte Fassungen aus dem Zwischenspeicher liefern
kann. Mit GITHUB_TOKEN (im Workflow, nur Leserecht) geht das Token nur an die GitHub-API, sonst ohne Token (60 Anfragen je
Stunde und IP). Weicht der Stand ab, werden Soll und Ist sofort einmal neu abgerufen, die Hauptadresse mit einem Parameter
gegen Zwischenspeicher (nginx); mit --warten (nach einer Veröffentlichung, Plesk holt den Branch deploy verzögert) danach
bis zu viermal im Abstand von 60 s.
HTTP 429 und 5xx (z. B. 502/503 vom Webhosting während Plesk neu ausliefert) werden wie Netzfehler wiederholt.

Nach dem Kölner Vorbild (ratsatlas-koeln, .github/workflows/live.yml) und scripts/live_pruefen.sh (ratsatlas.de):
Kopfzeilen mit GET wie ein Browser, nicht mit HEAD (Befund Bonn: netcup/nginx beantwortet HEAD auf anderem Weg).
Nur eigene Server und GitHub; nie Server der Stadt Wuppertal. Nur Standardbibliothek.

Aufruf: python3 tools/live_pruefen.py [--haupt URL] [--spiegel URL] [--repo owner/name] [--warten]
Ausgabe: eine Zeile je Prüfung (ok / FEHLER / Hinweis); Exit-Code 1 bei mindestens einem Fehler.
Hinter einem Proxy (HTTPS_PROXY gesetzt, z. B. lokal in einer Sandbox) ist das Zertifikat nicht prüfbar (ein
TLS-Proxy legt sein eigenes vor) und wird nur als Hinweis gemeldet, ebenso eine fehlende Verbindung für http → https.
Im Workflow (GITHUB_ACTIONS=true) ist ein gesetzter Proxy ein Fehler: Die Prüfungen dürfen dort nicht still entfallen."""
import argparse
import html
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HAUPT = "https://wuppertal.ratsatlas.de/"
SPIEGEL = "https://daimpad.github.io/ratsatlas-wuppertal/"
REPO = "daimpad/ratsatlas-wuppertal"
STADT = "wuppertal"                                  # wie pipeline/config.py STADT
TITEL = "Ratsatlas Wuppertal"
TITEL_404 = "Seite nicht gefunden – Ratsatlas Wuppertal"
# Dürfen nicht ausgeliefert werden: Plesk liefert nur den Branch deploy aus (docs/PLESK.md), nie main
GESPERRT = ("CLAUDE.md", "site/app.js", "explore/STUFEN.md", "pipeline/", ".git/HEAD")
# Sicherheitskopfzeilen aus deploy/htaccess: Name → erwartete Bestandteile des Werts (alle müssen vorkommen);
# Permissions-Policy mit jeder Angabe aus deploy/htaccess (tests/test_live_pruefen.py hält beides gleich)
KOPFZEILEN = {
    "Content-Security-Policy": ("frame-ancestors",),
    "X-Content-Type-Options": ("nosniff",),
    "Referrer-Policy": ("strict-origin-when-cross-origin",),
    "Strict-Transport-Security": ("max-age=",),
    "Permissions-Policy": ("camera=()", "microphone=()", "geolocation=()", "payment=()", "usb=()",
                           "browsing-topics=()"),
}
MIN_TAGE = 14
QUELLE_INHALT = "https://api.github.com/repos/{repo}/contents/version.txt?ref=deploy"
QUELLE_API = "https://api.github.com/repos/{repo}/commits/deploy"
STAND_VERSUCHE_WARTEN, STAND_ABSTAND = 5, 60.0   # --warten: Stand bis zu 5-mal im Abstand von 60 s
WIEDERHOLEN = {429, 500, 502, 503, 504}          # Status, die wie Netzfehler wiederholt werden
USER_AGENT = "ratsatlas-wuppertal-live-pruefung (+https://github.com/daimpad/ratsatlas-wuppertal)"
MAX_BYTES = 2_000_000
SHA = re.compile(r"[0-9a-f]{7,40}")


class _OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Weiterleitungen nicht folgen: Die Seiten sollen direkt 200 liefern, die Umleitung http → https wird geprüft."""

    def redirect_request(self, *a, **k):
        return None


_OEFFNER = urllib.request.build_opener(_OhneWeiterleitung)


class Antwort:
    def __init__(self, status=None, kopf=None, inhalt=b"", fehler=None):
        self.status, self.kopf, self.inhalt, self.fehler = status, kopf, inhalt, fehler

    def wert(self, name):
        return (self.kopf.get(name) if self.kopf is not None else None) or ""

    @property
    def text(self):
        return self.inhalt.decode("utf-8", "replace")

    def beschreibung(self):
        return f"Status {self.status}" if self.status is not None else f"keine Antwort ({self.fehler})"


def titel(text):
    m = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def canonical(text):
    m = re.search(r'<link rel="canonical" href="([^"]*)"', text)
    return m.group(1) if m else ""


def noindex_meta(text):
    m = re.search(r'<meta name="robots" content="([^"]*)"', text)
    return bool(m) and "noindex" in m.group(1).lower()


def gleicher_stand(a, b):
    """Zwei Commit-Angaben (voll oder gekürzt, mindestens 7 Zeichen) bezeichnen denselben Commit."""
    if not (a and b and SHA.fullmatch(a) and SHA.fullmatch(b)):
        return False
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def mit_schraegstrich(url):
    return url if url.endswith("/") else url + "/"


def zertifikat_tage(host, port=443, kontext=None, timeout=20, jetzt=None):
    """Restlaufzeit des Serverzertifikats in Tagen und Ablaufdatum; Zertifikatskette und Name werden geprüft (wirft
    ssl.SSLError, wenn das Zertifikat ungültig ist)."""
    kontext = kontext or ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as roh:
        with kontext.wrap_socket(roh, server_hostname=host) as tls:
            zert = tls.getpeercert()
    ablauf = ssl.cert_time_to_seconds(zert["notAfter"])
    return (ablauf - (time.time() if jetzt is None else jetzt)) / 86400, zert["notAfter"]


class Pruefung:
    def __init__(self, haupt=HAUPT, spiegel=SPIEGEL, repo=REPO, http_url=None, quelle_inhalt=QUELLE_INHALT,
                 quelle_api=QUELLE_API, zertifikat=zertifikat_tage, versuche=3, pause_fehler=10.0, pause=0.5,
                 timeout=20, ausgabe=print, token=None, stand_versuche=1, stand_abstand=STAND_ABSTAND):
        self.haupt, self.spiegel = mit_schraegstrich(haupt), mit_schraegstrich(spiegel)
        teile = urllib.parse.urlsplit(self.haupt)
        self.host, self.port = teile.hostname, teile.port or 443
        self.http_url = http_url or urllib.parse.urlunsplit(("http", teile.netloc, "/", "", ""))
        self.repo, self.quelle_inhalt, self.quelle_api = repo, quelle_inhalt, quelle_api
        # Token nur für die GitHub-API (soll_stand), nie für die geprüften Seiten
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
        self.stand_versuche, self.stand_abstand = max(1, stand_versuche), stand_abstand
        self.zertifikat = zertifikat
        self.versuche, self.pause_fehler, self.pause, self.timeout = versuche, pause_fehler, pause, timeout
        self.ausgabe = ausgabe
        self.ergebnisse = []          # (zustand, text) mit zustand ok / FEHLER / Hinweis
        self.anfragen = 0
        self._zwischen = {}

    # --- Hilfen -----------------------------------------------------------------------------------------------------

    def melden(self, ok, text, hinweis=False):
        zustand = "ok" if ok else ("Hinweis" if hinweis else "FEHLER")
        self.ergebnisse.append((zustand, text))
        self.ausgabe(f"{zustand:<8}{text}")
        if zustand == "FEHLER" and os.environ.get("GITHUB_ACTIONS") == "true":
            self.ausgabe(f"::error::{text}")

    def abrufen(self, url, merken=True, kopf=None):
        """GET ohne Weiterleitung; HTTP-Fehlerstatus sind Antworten. Netzfehler, 429 und 5xx (WIEDERHOLEN) werden bis
        zu `versuche`-mal wiederholt; danach gilt die letzte Antwort."""
        if merken and url in self._zwischen:
            return self._zwischen[url]
        antwort = None
        for i in range(self.versuche):
            if self.anfragen and self.pause:
                time.sleep(self.pause)
            self.anfragen += 1
            anfrage = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache",
                                                           **(kopf or {})})
            try:
                with _OEFFNER.open(anfrage, timeout=self.timeout) as r:
                    antwort = Antwort(r.status, r.headers, r.read(MAX_BYTES))
                break
            except urllib.error.HTTPError as e:
                antwort = Antwort(e.code, e.headers, e.read(MAX_BYTES) if e.fp else b"")
                if e.code not in WIEDERHOLEN:
                    break
            except (urllib.error.URLError, OSError) as e:
                antwort = Antwort(fehler=getattr(e, "reason", e))
            if i + 1 < self.versuche:
                time.sleep(self.pause_fehler)
        if merken:
            self._zwischen[url] = antwort
        return antwort

    def _hinter_proxy(self):
        return bool(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))

    def nicht_pruefbar(self, text):
        """Prüfung hinter einem Proxy nicht möglich: lokal ein Hinweis, im Workflow ein Fehler (sonst entfiele die
        Prüfung dort still, etwa mit einem Self-hosted Runner oder einem env auf Workflow-Ebene)."""
        if os.environ.get("GITHUB_ACTIONS") == "true":
            self.melden(False, f"{text}; im Workflow darf kein Proxy gesetzt sein")
        else:
            self.melden(False, text, hinweis=True)

    # --- Prüfungen der Hauptadresse ---------------------------------------------------------------------------------

    def startseite(self, basis, name):
        a = self.abrufen(basis)
        self.melden(a.status == 200, f"{name} {basis}: {a.beschreibung()}")
        t = titel(a.text)
        self.melden(t.startswith(TITEL), f"{name}: Titel „{t or 'fehlt'}“ beginnt mit „{TITEL}“")
        c = canonical(a.text)
        self.melden(c == self.haupt, f"{name}: Canonical {c or 'fehlt'} = {self.haupt}")
        return a

    def ohne_daten(self):
        """Liegen Daten vor? Aus der Seite abgeleitet: index.json des Datenexports (404 = keine Daten)."""
        url = f"{self.haupt}data/export/{STADT}/index.json"
        a = self.abrufen(url)
        if a.status == 404:
            self.melden(True, f"Datenstand: keine Daten ({url} → 404), noindex erwartet")
            return True
        if a.status == 200:
            self.melden(True, f"Datenstand: Daten vorhanden ({url} → 200), kein noindex erwartet")
            return False
        self.melden(False, f"Datenstand unklar: {url} → {a.beschreibung()}")
        return None

    def indexierung(self, start, ohne):
        if ohne is None:
            return
        meta, kopf = noindex_meta(start.text), "noindex" in start.wert("X-Robots-Tag").lower()
        if ohne:
            self.melden(meta, "ohne Daten: <meta name=\"robots\" content=\"noindex\"> in index.html")
            self.melden(kopf, f"ohne Daten: X-Robots-Tag noindex (ist: {start.wert('X-Robots-Tag') or 'fehlt'})")
        else:
            self.melden(not meta and not kopf, "mit Daten: weder meta robots noindex noch X-Robots-Tag noindex")

    def kopfzeilen(self):
        app = self.abrufen(f"{self.haupt}app.js")
        self.melden(app.status == 200, f"{self.haupt}app.js: {app.beschreibung()}")
        for url, a in ((self.haupt, self.abrufen(self.haupt)), (f"{self.haupt}app.js", app)):
            for name, teile in KOPFZEILEN.items():
                wert = a.wert(name)
                kompakt = re.sub(r"\s+", "", wert.lower())
                fehlt = [t for t in teile if t.lower() not in kompakt]
                self.melden(not fehlt, f"Kopfzeile {name} auf {url}: {wert or 'fehlt'}"
                            + (f" (ohne {', '.join(fehlt)})" if wert and fehlt else ""))

    def umleitung(self):
        a = self.abrufen(self.http_url)
        ziel = a.wert("Location")
        if a.status is None and self._hinter_proxy():
            self.nicht_pruefbar(f"Umleitung {self.http_url} nicht prüfbar hinter Proxy ({a.fehler})")
            return
        self.melden(a.status in (301, 308) and ziel.rstrip("/") == self.haupt.rstrip("/"),
                    f"Umleitung {self.http_url} → {self.haupt}: {a.beschreibung()}, Ziel {ziel or 'keins'}")

    def fehlerseite(self):
        url = f"{self.haupt}gibt-es-nicht-live-pruefung"
        a = self.abrufen(url)
        t = titel(a.text)
        self.melden(a.status == 404 and t == TITEL_404, f"eigene 404-Seite {url}: {a.beschreibung()}, Titel „{t}“")

    def gesperrt(self):
        for pfad in GESPERRT:
            a = self.abrufen(self.haupt + pfad)
            self.melden(a.status == 404, f"nicht abrufbar {self.haupt}{pfad}: {a.beschreibung()}")

    def zertifikat_pruefen(self):
        if self._hinter_proxy():   # ein TLS-Proxy legt sein eigenes Zertifikat vor (lokal am 10.11.2026 so gesehen)
            self.nicht_pruefbar(f"Zertifikat {self.host}: hinter Proxy nicht prüfbar (HTTPS_PROXY gesetzt)")
            return
        try:
            tage, ablauf = self.zertifikat(self.host, self.port)
        except ssl.SSLError as e:
            self.melden(False, f"Zertifikat {self.host}: ungültig ({e})")
            return
        except OSError as e:
            self.melden(False, f"Zertifikat {self.host}: keine Verbindung ({e})")
            return
        self.melden(tage >= MIN_TAGE, f"Zertifikat {self.host}: gültig bis {ablauf}, noch {tage:.0f} Tage "
                                      f"(mindestens {MIN_TAGE})")

    def _github(self, url, accept):
        kopf = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            kopf["Authorization"] = f"Bearer {self.token}"
        return self.abrufen(url.format(repo=self.repo), merken=False, kopf=kopf)

    def soll_stand(self):
        """Commit von main, aus dem der Kopf des Branches deploy gebaut ist (GitHub-API, ohne CDN)."""
        inhalt = self._github(self.quelle_inhalt, "application/vnd.github.raw")
        wert = inhalt.text.strip() if inhalt.status == 200 else ""
        if SHA.fullmatch(wert):
            return wert, "version.txt im Branch deploy"
        api = self._github(self.quelle_api, "application/vnd.github+json")
        if api.status == 200:
            try:
                nachricht = json.loads(api.text)["commit"]["message"]
            except (ValueError, KeyError, TypeError):
                nachricht = ""
            m = re.match(r"Seite aus ([0-9a-f]{7,40})\b", nachricht)
            if m:
                return m.group(1), "Commit-Nachricht des Branches deploy"
        return None, f"version.txt {inhalt.beschreibung()}, Commit {api.beschreibung()}"

    def _stand_einmal(self, parameter):
        """Soll und Ist je einmal abrufen; Ist nur, wenn das Soll bekannt ist."""
        soll, quelle = self.soll_stand()
        if not soll:
            return None, quelle, None, ""
        url = f"{self.haupt}version.txt" + (f"?pruefung={time.time_ns()}" if parameter else "")
        ist = self.abrufen(url, merken=False)
        return soll, quelle, ist, ist.text.strip() if ist.status == 200 else ""

    def stand(self):
        """Soll (Branch deploy) und Ist (version.txt der Hauptadresse) vergleichen. Bei Abweichung sofort beide neu,
        die Hauptadresse mit Parameter gegen Zwischenspeicher; mit stand_versuche > 1 danach weitere Versuche im
        Abstand von stand_abstand Sekunden, jeweils Soll und Ist neu."""
        soll = wert = ist = None
        for versuch in range(self.stand_versuche):
            if versuch:
                time.sleep(self.stand_abstand)
            # erster Versuch zuerst wie ein Besucher ohne Parameter, danach immer mit Parameter
            for parameter in ((False, True) if versuch == 0 else (True,)):
                soll, quelle, ist, wert = self._stand_einmal(parameter)
                if gleicher_stand(wert, soll):
                    break
            if gleicher_stand(wert, soll):
                break
        if not soll:
            self.melden(False, f"Stand des Branches deploy nicht ermittelbar ({quelle})")
            return
        gleich = gleicher_stand(wert, soll)
        versuche = f", {self.stand_versuche} Versuche im Abstand von {self.stand_abstand:.0f} s" \
            if self.stand_versuche > 1 and not gleich else ""
        self.melden(gleich,
                    f"Stand {self.haupt}version.txt = {wert[:7] if wert else ist.beschreibung()}, "
                    f"Branch deploy = {soll[:7]} ({quelle}{versuche})"
                    + ("" if gleich else
                       " – holt Plesk den Branch deploy ab? (Git → Webhook, docs/PLESK.md B.3/B.4)"))

    # --- Ablauf -----------------------------------------------------------------------------------------------------

    def alles(self):
        start = self.startseite(self.haupt, "Hauptadresse")
        self.indexierung(start, self.ohne_daten())
        self.kopfzeilen()
        self.umleitung()
        self.fehlerseite()
        self.gesperrt()
        self.zertifikat_pruefen()
        self.stand()
        self.startseite(self.spiegel, "Ausweichadresse")
        fehler = sum(1 for z, _ in self.ergebnisse if z == "FEHLER")
        self.ausgabe(f"{len(self.ergebnisse)} Prüfungen, {fehler} Fehler, {self.anfragen} Anfragen")
        return fehler


def main(argv=None):
    p = argparse.ArgumentParser(description="Live-Prüfung der veröffentlichten Seite (Ratsatlas Wuppertal)")
    p.add_argument("--haupt", default=os.environ.get("SITE_URL") or HAUPT)
    p.add_argument("--spiegel", default=os.environ.get("SPIEGEL_URL") or SPIEGEL)
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY") or REPO)
    p.add_argument("--warten", action="store_true",
                   help=f"nach einer Veröffentlichung: Stand bis zu {STAND_VERSUCHE_WARTEN}-mal im Abstand von "
                        f"{STAND_ABSTAND:.0f} s prüfen")
    args = p.parse_args(argv)
    pruefung = Pruefung(args.haupt, args.spiegel, args.repo,
                        stand_versuche=STAND_VERSUCHE_WARTEN if args.warten else 1, stand_abstand=STAND_ABSTAND)
    return 1 if pruefung.alles() else 0


if __name__ == "__main__":
    sys.exit(main())
