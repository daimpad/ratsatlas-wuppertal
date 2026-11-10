"""Linkprüfung der gebauten Seite (vorgezogener Teil von Phase 6; CLAUDE.md 9, 10.11.2026; Workflow
.github/workflows/links.yml). Baut keine Seite, sondern prüft ein Verzeichnis, das tools/seite_bauen.py erzeugt hat.

Intern (immer): jeder Verweis in den HTML-Seiten (href, src, srcset, poster, og:image/twitter:image), in CSS (url())
und im Web-App-Manifest (icons, start_url, scope), der auf eine Datei der Seite zeigt: relative Verweise und absolute
Adressen der eigenen Seite (SITE_URL und Ausweichadresse, --eigen). Die Datei muss vorhanden sein (Verzeichnis →
index.html); ein Anker (#name) muss in der Zielseite als id oder <a name> stehen („#“ und „#top“ gelten immer).
Regel „erst mit Daten“: Fehlt der Datenexport (kein data/export/*/index.json), sind fehlende Ziele unter ERST_MIT_DATEN
kein Fehler, sondern werden so ausgewiesen; das sind die Pfade, die erst die Pipeline mit Daten schreibt
(data/export/, data/geo/ aus tools/seite_bauen.py; gebiete/, ortsteil/, stadtbezirk/ aus pipeline/gebietsseiten.py;
vorgang/ aus pipeline/vorgangsseiten.py). Mit Daten sind auch sie Pflicht.

Extern (nur mit --extern): http(s)-Links anderer Hosts, je Adresse einmal. Eine Verbindung zur Zeit, je Host mindestens
ABSTAND Sekunden zwischen zwei Anfragen, HEAD, bei 403/405 einmal GET; Weiterleitungen werden einzeln verfolgt (je
Schritt dieselben Regeln, höchstens MAX_WEITER), Zeitlimit je Anfrage, Obergrenze Anfragen je Lauf; Netzfehler, 429
und 5xx werden einmal wiederholt. 401, 403 und 429 nach allen Versuchen gelten als „unklar“ (Abwehr automatischer
Abrufe), nicht als Fehler.
Nie angefragt und als „nicht geprüft“ ausgewiesen: Server der Stadt Wuppertal (wuppertal.de und Unterdomains,
Hosts auf wuppertal-*.de wie offenedaten-wuppertal.de; Abrufpolitik CLAUDE.md 5.1), auch als Ziel einer Weiterleitung;
die Kachelserver von OpenStreetMap (*.tile.openstreetmap.org, Nutzungsrichtlinie); mailto:, tel: und andere Schemata.
Die Sperre gilt zusätzlich unmittelbar vor jeder Anfrage (_anfragen). Verglichen wird der Host in der Form, mit der
Python verbindet (host_normal: Prozentkodierung dekodiert, IDNA), damit Unicode-Schreibweisen die Sperre nicht umgehen.

Nur Standardbibliothek. Aufruf: python3 tools/links_pruefen.py _site [--extern] [--aus links.tsv]
Ausgabe: TSV mit Seite, Link, Art, Ergebnis, Status, Hinweis, Datum; Zusammenfassung auf stderr. Exit 1 bei Fehlern.
Nicht geprüft werden Links, die erst Skripte im Browser erzeugen (app.js)."""
import argparse
import datetime
import html.parser
import json
import os
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HAUPT = "https://wuppertal.ratsatlas.de/"
SPIEGEL = "https://daimpad.github.io/ratsatlas-wuppertal/"
USER_AGENT = ("ratsatlas-wuppertal-linkpruefung/1.0 (+https://github.com/daimpad/ratsatlas-wuppertal; "
              "contact@nozilla.de)")
ERST_MIT_DATEN = ("data/export/", "data/geo/", "gebiete/", "ortsteil/", "stadtbezirk/", "vorgang/")
ABSTAND = 2.0            # Sekunden zwischen zwei Anfragen an denselben Host (mindestens)
ZEITLIMIT = 20           # Sekunden je Anfrage
MAX_ANFRAGEN = 200       # je Lauf, alle Hosts zusammen
MAX_WEITER = 5           # Weiterleitungen je Link
MAX_BYTES = 65536        # bei GET höchstens so viel lesen
SPALTEN = ("Seite", "Link", "Art", "Ergebnis", "Status", "Hinweis", "Datum")
STADT_HINWEIS = "nicht geprüft (Server der Stadt, Abrufpolitik CLAUDE.md 5.1)"
UNKLAR = {401, 403, 429}
WIEDERHOLEN = {429, 500, 502, 503, 504}
# Hosts, die auf „wuppertal.de“ oder „wuppertal-….de“ enden (auch offenedaten-wuppertal.de, Unterdomains); bewusst weit
_STADT = re.compile(r"wuppertal(-[a-z0-9-]*)?\.de$")
_KACHELN = re.compile(r"(^|\.)tile\.openstreetmap\.org$")


def host_normal(host):
    """Host in der Form, mit der Python verbindet: prozentkodiert wie urllib.request dekodiert, Nicht-ASCII per IDNA
    (wie socket; vollbreite Zeichen, „。“ als Punkt, weiches Trennzeichen u. a. werden so zu ASCII), klein, ohne
    abschließenden Punkt. '' bei nicht umwandelbarem Host (wird dann nie angefragt)."""
    host = urllib.parse.unquote(host or "")
    if not host.isascii():
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            return ""
    return host.rstrip(".").lower()


def host_von(url):
    """Hostname nach host_normal, ohne Port und Anmeldedaten ('' bei unlesbarer Adresse)."""
    try:
        host = urllib.parse.urlsplit(url.strip()).hostname or ""
    except ValueError:
        return ""
    return host_normal(host)


def stadt_host(host):
    """Server der Stadt Wuppertal: Host endet auf wuppertal.de oder wuppertal-….de (Groß-/Kleinschreibung egal)."""
    return bool(_STADT.search(host_normal((host or "").strip())))


def gesperrt(url):
    """Grund, warum eine Adresse nie angefragt wird, sonst None. Unlesbare Adressen werden ebenfalls nie angefragt."""
    host = host_von(url)
    if not host:
        return "nicht geprüft (Adresse nicht lesbar)"
    if stadt_host(host):
        return STADT_HINWEIS
    if _KACHELN.search(host):
        return "nicht geprüft (Kachelserver von OpenStreetMap, Nutzungsrichtlinie)"
    return None


# --- Seiten lesen -----------------------------------------------------------------------------------------------------

class _Leser(html.parser.HTMLParser):
    ATTRIBUTE = {"href", "src", "poster", "data"}
    META = {"og:image", "og:image:url", "twitter:image"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.anker = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.anker.add(a["id"])
        if tag == "a" and a.get("name"):
            self.anker.add(a["name"])
        for name, wert in attrs:
            if wert is None:
                continue
            if name in self.ATTRIBUTE and not (tag == "object" and name != "data"):
                self.links.append(wert.strip())
            elif name in ("srcset", "imagesrcset"):
                self.links += [teil.strip().split()[0] for teil in wert.split(",") if teil.strip()]
        if tag == "meta" and (a.get("property") or a.get("name") or "").lower() in self.META and a.get("content"):
            self.links.append(a["content"].strip())

    handle_startendtag = handle_starttag


def html_lesen(pfad):
    leser = _Leser()
    leser.feed(pfad.read_text(encoding="utf-8", errors="replace"))
    return leser.links, leser.anker


CSS_URL = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")


def css_lesen(pfad):
    return [m.group(2).strip() for m in CSS_URL.finditer(pfad.read_text(encoding="utf-8", errors="replace"))]


def manifest_lesen(pfad):
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except ValueError:
        return []
    links = [daten[k] for k in ("start_url", "scope") if isinstance(daten.get(k), str)]
    return links + [i["src"] for i in daten.get("icons", []) if isinstance(i, dict) and isinstance(i.get("src"), str)]


# --- Prüfung ------------------------------------------------------------------------------------------------------

class Linkpruefung:
    def __init__(self, wurzel, eigen=(HAUPT, SPIEGEL), extern=False, oeffner=None, abstand=ABSTAND,
                 zeitlimit=ZEITLIMIT, max_anfragen=MAX_ANFRAGEN, versuche=2, datum=None, schlafen=time.sleep,
                 uhr=time.monotonic):
        self.wurzel = Path(wurzel).resolve()
        self.eigen = [e if e.endswith("/") else e + "/" for e in eigen if e]
        self.extern, self.abstand, self.zeitlimit = extern, abstand, zeitlimit
        self.max_anfragen, self.versuche = max_anfragen, max(1, versuche)
        self.oeffner = oeffner or urllib.request.build_opener(_OhneWeiterleitung)
        self.datum = datum or datetime.date.today().isoformat()
        self.schlafen, self.uhr = schlafen, uhr
        self.mit_daten = any(self.wurzel.glob("data/export/*/index.json"))
        self.zeilen, self.anfragen, self.angefragt = [], 0, []
        self._anker, self._extern, self._zuletzt = {}, {}, {}

    # Hilfen

    def _rel(self, pfad):
        return pfad.relative_to(self.wurzel).as_posix()

    def _anker_von(self, pfad):
        if pfad not in self._anker:
            self._anker[pfad] = html_lesen(pfad)[1] if pfad.suffix == ".html" else None
        return self._anker[pfad]

    def _zeile(self, seite, link, art, ergebnis, status="", hinweis=""):
        self.zeilen.append((seite, link, art, ergebnis, str(status), hinweis, self.datum))

    # Dateien der Seite

    def dateien(self):
        for pfad in sorted(self.wurzel.rglob("*")):
            if pfad.is_file() and pfad.suffix in (".html", ".css", ".webmanifest"):
                yield pfad

    def links_von(self, pfad):
        if pfad.suffix == ".html":
            return html_lesen(pfad)[0]
        if pfad.suffix == ".css":
            return css_lesen(pfad)
        return manifest_lesen(pfad)

    def alles(self):
        externe = {}
        for pfad in self.dateien():
            seite = self._rel(pfad)
            for link in dict.fromkeys(self.links_von(pfad)):    # je Seite jeden Link einmal, Reihenfolge bleibt
                self.einordnen(pfad, seite, link, externe)
        if self.extern:
            self.extern_pruefen(externe)
        else:
            for url, stellen in externe.items():
                for seite in stellen:
                    self._zeile(seite, url, "extern", "nicht geprüft", "", "ohne --extern")
        return self.fehler()

    def fehler(self):
        return sum(1 for z in self.zeilen if z[3] == "Fehler")

    def einordnen(self, pfad, seite, link, externe):
        if not link:
            self._zeile(seite, link, "intern", "Fehler", "", "leerer Verweis")
            return
        schema = urllib.parse.urlsplit(link).scheme.lower()
        if schema in ("http", "https") or link.startswith("//"):
            url = link if schema else "https:" + link
            ohne = url.split("#")[0].split("?")[0]
            for basis in self.eigen:
                if ohne.startswith(basis) or ohne == basis[:-1]:
                    self.intern(seite, link, self.wurzel / "index.html", url[len(basis) - (ohne == basis[:-1]):],
                                "eigene Adresse")
                    return
            grund = gesperrt(url)
            if not host_von(url):
                self._zeile(seite, link, "extern", "Fehler", "", "Adresse nicht lesbar")
            elif grund:
                self._zeile(seite, link, "extern", "nicht geprüft", "", grund)
            else:
                externe.setdefault(url.split("#")[0], []).append(seite)
            return
        if schema:
            self._zeile(seite, link, schema, "nicht geprüft", "", f"Schema {schema}: nicht angefragt")
            return
        if pfad.suffix == ".css" and link.startswith("#"):
            return                                        # url(#…) in CSS: SVG-Filter bzw. IE-Verhalten, kein Link
        if link.startswith("/"):
            self._zeile(seite, link, "intern", "Fehler", "",
                        "absoluter Pfad: auf der Ausweichadresse (Unterverzeichnis) falsch")
            return
        self.intern(seite, link, pfad, link, "Anker" if link.startswith("#") else "intern")

    def intern(self, seite, link, von, ziel, art):
        """ziel relativ zur Datei von (bei eigenen Adressen: index.html der Wurzel) auflösen und prüfen."""
        teile = urllib.parse.urlsplit(ziel)
        anker = urllib.parse.unquote(teile.fragment) if "#" in ziel else None
        if not teile.path:
            self._anker_pruefen(seite, link, art, von, anker)
            return
        verzeichnis = von.parent.relative_to(self.wurzel).as_posix()
        roh = posixpath.normpath(posixpath.join("" if verzeichnis == "." else verzeichnis,
                                                urllib.parse.unquote(teile.path)))
        if roh == ".." or roh.startswith("../"):
            self._zeile(seite, link, art, "Fehler", "", "zeigt aus der Seite heraus")
            return
        rel = "" if roh == "." else roh
        datei, hinweis = self.wurzel / rel, ""
        if datei.is_dir():
            if not teile.path.endswith("/"):
                hinweis = "Verzeichnis ohne „/“ (Server leitet um)"
            datei = datei / "index.html"
        if not datei.is_file():
            if not self.mit_daten and any(f"{rel}/".startswith(p) for p in ERST_MIT_DATEN):
                self._zeile(seite, link, art, "erst mit Daten", "", f"{rel} entsteht erst mit dem Datenexport")
            else:
                self._zeile(seite, link, art, "Fehler", "", f"{rel or 'index.html'} fehlt")
            return
        self._anker_pruefen(seite, link, art, datei, anker, hinweis)

    def _anker_pruefen(self, seite, link, art, datei, anker, hinweis=""):
        if anker is None or anker == "" or anker.lower() == "top":
            self._zeile(seite, link, art, "ok", "", hinweis)
            return
        vorhanden = self._anker_von(datei)
        if vorhanden is None:
            self._zeile(seite, link, art, "ok", "", "Anker in Nicht-HTML-Datei nicht geprüft")
        elif anker in vorhanden:
            self._zeile(seite, link, art, "ok", "", hinweis)
        else:
            self._zeile(seite, link, art, "Fehler", "", f"Anker #{anker} fehlt in {self._rel(datei)}")

    # Externe Links

    def extern_pruefen(self, externe):
        """Je Adresse einmal; reihum nach Host, damit die Wartezeit je Host selten greift."""
        je_host = {}
        for url in externe:
            je_host.setdefault(host_von(url), []).append(url)
        reihe = []
        while any(je_host.values()):
            for host in list(je_host):
                if je_host[host]:
                    reihe.append(je_host[host].pop(0))
        for url in reihe:
            ergebnis = self.pruefe_url(url)
            for seite in externe[url]:
                self._zeile(seite, url, "extern", *ergebnis)

    def pruefe_url(self, url):
        """(Ergebnis, Status, Hinweis) für eine externe Adresse, mit Weiterleitungen."""
        aktuell, kette = url, []
        for _ in range(MAX_WEITER + 1):
            grund = gesperrt(aktuell)
            if grund:
                return "nicht geprüft", "", (f"Weiterleitung auf {aktuell}: " if kette else "") + grund
            status, ort, fehler = self._mit_wiederholung(aktuell)
            if status is None:
                if fehler == "Obergrenze":
                    return "nicht geprüft", "", f"Obergrenze von {self.max_anfragen} Anfragen je Lauf erreicht"
                return "Fehler", "", f"keine Antwort ({fehler})"
            if status in (301, 302, 303, 307, 308) and ort:
                kette.append(str(status))
                aktuell = urllib.parse.urljoin(aktuell, ort)
                continue
            weiter = f"Weiterleitung {'→'.join(kette)} auf {aktuell}" if kette else ""
            if 200 <= status < 300:
                return "ok", status, weiter
            if status in UNKLAR:
                return "unklar", status, "; ".join(filter(None, [weiter, "Abruf abgewiesen, im Browser prüfen"]))
            return "Fehler", status, weiter
        return "Fehler", "", f"mehr als {MAX_WEITER} Weiterleitungen"

    def _mit_wiederholung(self, url):
        status = ort = fehler = None
        for _ in range(self.versuche):
            status, ort, fehler = self._head_oder_get(url)
            if fehler == "Obergrenze" or (status is not None and status not in WIEDERHOLEN):
                break
        return status, ort, fehler

    def _head_oder_get(self, url):
        status, ort, fehler = self._anfragen(url, "HEAD")
        if status in (403, 405):
            status, ort, fehler = self._anfragen(url, "GET")
        return status, ort, fehler

    def _anfragen(self, url, methode):
        """Eine Anfrage; (Status, Location, Fehler). Prüft die Sperre unmittelbar vor dem Senden, auch gegen den Host,
        den urllib selbst aus der Adresse liest."""
        anfrage = urllib.request.Request(url, method=methode, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        ziel = anfrage.host.rsplit("@", 1)[-1]
        ziel = host_normal(ziel.split("]")[0].lstrip("[") if ziel.startswith("[") else ziel.split(":")[0])
        if gesperrt(url) or not ziel or stadt_host(ziel) or anfrage.type not in ("http", "https"):
            raise RuntimeError(f"gesperrte Adresse: {url}")   # zweite Sicherung, falls ein Aufrufer sie umgeht
        if self.anfragen >= self.max_anfragen:
            return None, None, "Obergrenze"
        host = host_von(url)
        warten = self._zuletzt.get(host, -1e9) + self.abstand - self.uhr()
        if warten > 0:
            self.schlafen(warten)
        self.anfragen += 1
        self.angefragt.append((methode, url))
        try:
            with self.oeffner.open(anfrage, timeout=self.zeitlimit) as r:
                if methode == "GET":
                    r.read(MAX_BYTES)
                return r.status, r.headers.get("Location"), None
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location") if e.headers else None, None
        except (urllib.error.URLError, OSError, ValueError) as e:
            return None, None, str(getattr(e, "reason", e))
        finally:
            self._zuletzt[host] = self.uhr()

    # Ausgabe

    def tsv(self):
        zeilen = ["\t".join(SPALTEN)]
        for z in self.zeilen:
            zeilen.append("\t".join(str(f).replace("\t", " ").replace("\n", " ") for f in z))
        return "\n".join(zeilen) + "\n"

    def zusammenfassung(self):
        zaehler = {}
        for z in self.zeilen:
            zaehler[z[3]] = zaehler.get(z[3], 0) + 1
        teile = ", ".join(f"{n} {e}" for e, n in sorted(zaehler.items()))
        return (f"{len(self.zeilen)} Verweise ({teile}); {self.anfragen} Anfragen; "
                f"{'mit' if self.mit_daten else 'ohne'} Daten")


class _OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Weiterleitungen nicht selbst folgen: Linkpruefung.pruefe_url prüft jedes Ziel vorher gegen die Sperre."""

    def redirect_request(self, *a, **k):
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description="Linkprüfung der gebauten Seite (Ratsatlas Wuppertal)")
    p.add_argument("verzeichnis", help="Ausgabe von tools/seite_bauen.py, z. B. _site")
    p.add_argument("--extern", action="store_true", help="externe http(s)-Links abrufen (nie Server der Stadt)")
    p.add_argument("--aus", help="TSV in diese Datei statt auf stdout")
    p.add_argument("--eigen", action="append",
                   help="eigene Adresse, deren Links als Dateien der Seite geprüft werden (mehrfach; Vorgabe: "
                        "SITE_URL bzw. Hauptadresse und Ausweichadresse)")
    p.add_argument("--max-anfragen", type=int, default=MAX_ANFRAGEN)
    args = p.parse_args(argv)
    if not (Path(args.verzeichnis) / "index.html").is_file():
        p.error(f"{args.verzeichnis}/index.html fehlt: erst python3 tools/seite_bauen.py {args.verzeichnis}")
    eigen = args.eigen or [os.environ.get("SITE_URL") or HAUPT, SPIEGEL]
    pruefung = Linkpruefung(args.verzeichnis, eigen=eigen, extern=args.extern, max_anfragen=args.max_anfragen)
    fehler = pruefung.alles()
    if args.aus:
        Path(args.aus).write_text(pruefung.tsv(), encoding="utf-8")
    else:
        sys.stdout.write(pruefung.tsv())
    print(pruefung.zusammenfassung(), file=sys.stderr)
    for z in pruefung.zeilen:
        if z[3] == "Fehler":
            print(f"FEHLER  {z[0]}: {z[1]} {z[4]} {z[5]}".rstrip(), file=sys.stderr)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
