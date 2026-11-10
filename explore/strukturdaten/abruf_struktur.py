"""Gedrosselter Abruf für Phase 0 der Strukturdaten (Quellenprüfung; Auftrag PROMPT_strukturdaten_v0.1.md).

Eigenständig, nur Standardbibliothek; unabhängig von explore/abruf.py (dessen Zeitfenster 23–1 Uhr gilt für die
OParl-Messung; Phase 0 läuft tagsüber, gedrosselt, Entscheidung 10.11.2026 in CLAUDE.md 9).

Regeln (vor jeder Anfrage geprüft, Verstoß = AbrufFehler ohne Anfrage):
- nur https, nur Port 443, keine Zugangsdaten in der Adresse, keine Leer- oder Steuerzeichen
- nur Hosts aus ERLAUBTE_HOSTS; oparl.wuppertal.de und ris.wuppertal.de (samt Subdomains) ausdrücklich verboten
- daten.wuppertal.de nur mit HEAD oder höchstens 2 MB (MAX_BYTES_DATEN); sonst Grenze je Aufruf `max_bytes`
- Host-Schlüssel: führendes „www.“ entfernt (www.offenedaten-wuppertal.de und offenedaten-wuppertal.de sind ein
  Host); Sperre, Abstand, Obergrenze und Sperrmarker gelten je Host-Schlüssel
- eine Verbindung je Host: exklusive Dateisperre <SPERRORT>/struktur-<host-schlüssel>.lock für die Dauer einer
  Anfrage; hält ein anderer Prozess sie, Abbruch (Art `parallel`)
- Abstand mindestens ABSTAND (2 s) je Host vom Ende der letzten Antwort (Zeitstempeldatei
  struktur-<host-schlüssel>.zeit)
- höchstens OBERGRENZE (40) Anfragen je Host, gezählt aus dem Protokoll (Zeilen mit cache=nein); Cache-Treffer zählen
  nicht
- 429, 5xx, 403 mit Bot-Abwehr (Kopf Cf-Mitigated oder Server cloudflare), Zeitüberschreitung (ZEITLIMIT 30 s, auch
  für die ganze Antwort) oder Verbindungsfehler: keine Wiederholung, Host gesperrt (Markerdatei
  struktur-<host-schlüssel>.gesperrt; nur von Hand löschen)
- Weiterleitungen werden nicht automatisch verfolgt; das Ziel steht im Protokoll (bemerkung). Gefolgt wird nur, wenn
  das Ziel alle Regeln erfüllt, höchstens MAX_WEITERLEITUNGEN (2) Mal; jede Stufe ist eine eigene, gezählte Anfrage
- Cache unter explore/_cache/strukturdaten/ (nie versioniert): Schlüssel = SHA-256 der angefragten URL;
  <schlüssel>.daten und <schlüssel>.kopf.json für GET, <schlüssel>.head.json für HEAD; nur Antworten mit Status
  200.
  Kopfzeilen anderer Antworten als Beleg in <schlüssel>.<get|head>-<status>.json (nie als Cache-Treffer verwendet);
  bei Status ab 400 stehen Server und Cf-Mitigated zusätzlich in der Bemerkung
- Protokoll explore/strukturdaten/audit_abruf.tsv: jede gesendete Anfrage und jeder Cache-Treffer

SPERRORT: RATSATLAS_SPERRE (z. B. für Tests), sonst ~/.cache/ratsatlas-wuppertal. Cache und Protokoll lassen sich für
Tests über RATSATLAS_STRUKTUR_CACHE und RATSATLAS_STRUKTUR_PROTOKOLL umlenken. RATSATLAS_STRUKTUR_TEST=ja erlaubt
zusätzlich http und https an 127.0.0.1 (beliebiger Port; nur für Tests mit lokalem Server, ohne Proxy).

CLI: python3 abruf_struktur.py <url> [--head] [--ausgabe datei] [--quelle name] [--max-bytes n]
Gibt Status und Pfad der Cache-Datei aus. --ausgabe kopiert den Inhalt, aber nur innerhalb des Cache-Verzeichnisses
(Rohdaten nie außerhalb von explore/_cache/strukturdaten/).
"""
import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import http.client
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

HIER = Path(__file__).resolve().parent
CACHE = Path(os.environ.get("RATSATLAS_STRUKTUR_CACHE", HIER.parent / "_cache" / "strukturdaten"))
PROTOKOLL = Path(os.environ.get("RATSATLAS_STRUKTUR_PROTOKOLL", HIER / "audit_abruf.tsv"))
SPERRORT = Path(os.environ.get("RATSATLAS_SPERRE", Path.home() / ".cache" / "ratsatlas-wuppertal"))
TESTMODUS = os.environ.get("RATSATLAS_STRUKTUR_TEST", "").strip().lower() == "ja"

USER_AGENT = ("ratsatlas-wuppertal-strukturdaten/0.1 "
              "(+https://github.com/daimpad/ratsatlas-wuppertal; contact@nozilla.de)")
ERLAUBTE_HOSTS = ("www.offenedaten-wuppertal.de", "offenedaten-wuppertal.de", "www.wuppertal.de",
                  "daten.wuppertal.de", "www.wegweiser-kommune.de")
VERBOTENE_HOSTS = ("oparl.wuppertal.de", "ris.wuppertal.de")
TESTHOST = "127.0.0.1"
MAX_BYTES_DATEN = 2_000_000   # daten.wuppertal.de: nur HEAD oder kleine Dateien
ABSTAND = 2.0                 # Sekunden je Host, mindestens
OBERGRENZE = 40               # Anfragen je Host insgesamt (aus dem Protokoll)
ZEITLIMIT = 30.0              # Sekunden je Anfrage (Socket und ganze Antwort)
MAX_WEITERLEITUNGEN = 2
BLOCK = 64 * 1024
SPALTEN = ("quelle", "url", "zeitstempel", "http_status", "bytes", "zeilen", "pruefsumme_sha256", "cache",
           "bemerkung")
ZEITZONE = ZoneInfo("Europe/Berlin")
_STEUERZEICHEN = re.compile(r"[\x00-\x20\x7f]")


class AbrufFehler(Exception):
    """Abbruch. `art`: verboten, regel (Adresse/Methode/Größe unzulässig, nicht gesendet), gesperrt (Markerdatei),
    obergrenze, parallel (Sperre gehalten), zeit (Zeitüberschreitung, Host jetzt gesperrt), verbindung (Host jetzt
    gesperrt), groesse (Antwort zu groß, verworfen; `kopf` gesetzt)."""

    def __init__(self, meldung, art, kopf=None):
        super().__init__(meldung)
        self.art = art
        self.kopf = kopf or {}


class _OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OEFFNER = urllib.request.build_opener(_OhneWeiterleitung)
_OEFFNER_LOKAL = urllib.request.build_opener(_OhneWeiterleitung, urllib.request.ProxyHandler({}))


def _jetzt() -> str:
    return dt.datetime.now(ZEITZONE).isoformat(timespec="seconds")


def host_von(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url.strip()).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def host_schluessel(host: str) -> str:
    """Schlüssel für Sperre, Abstand, Obergrenze und Sperrmarker: führendes „www.“ entfernt."""
    host = (host or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def verboten(host: str) -> bool:
    host = host.lower().rstrip(".")
    return any(host == v or host.endswith("." + v) for v in VERBOTENE_HOSTS)


def pruefe_url(url: str) -> str:
    """Liefert den Host, wenn die Adresse abgerufen werden darf; sonst AbrufFehler (ohne Anfrage)."""
    host = host_von(url)
    if verboten(host):
        raise AbrufFehler(f"verbotener Host {host}: {url}", "verboten")
    if _STEUERZEICHEN.search(url.strip()):
        raise AbrufFehler(f"Leer- oder Steuerzeichen in der Adresse: {url!r}", "regel")
    teile = urllib.parse.urlsplit(url.strip())
    if teile.username is not None or teile.password is not None:
        raise AbrufFehler(f"Zugangsdaten in der Adresse: {url}", "regel")
    try:
        port = teile.port
    except ValueError:
        raise AbrufFehler(f"ungültiger Port: {url}", "regel")
    if TESTMODUS and host == TESTHOST:
        if teile.scheme not in ("http", "https"):
            raise AbrufFehler(f"Schema {teile.scheme!r} nicht erlaubt: {url}", "regel")
        return host
    if teile.scheme != "https":
        raise AbrufFehler(f"nur https erlaubt: {url}", "regel")
    if port not in (None, 443):
        raise AbrufFehler(f"nur Port 443 erlaubt: {url}", "regel")
    if host not in ERLAUBTE_HOSTS:
        raise AbrufFehler(f"Host nicht erlaubt: {host or '?'} ({url})", "regel")
    return host


def _schluessel(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def cache_pfade(url: str, methode: str = "GET"):
    """(Datei mit Inhalt oder None, Datei mit Kopf) im Cache für diese URL und Methode."""
    s = _schluessel(url)
    if methode == "HEAD":
        return None, CACHE / f"{s}.head.json"
    return CACHE / f"{s}.daten", CACHE / f"{s}.kopf.json"


def _zeilen(url: str, kopf: dict, daten: bytes) -> str:
    """Zeilenzahl bei CSV/TSV (nach Content-Type oder Endung des Pfads), sonst leer."""
    typ = {k.lower(): v for k, v in kopf.items()}.get("content-type", "").lower()
    pfad = urllib.parse.urlsplit(url).path.lower()
    if not ("csv" in typ or "tab-separated" in typ or pfad.endswith((".csv", ".tsv"))):
        return ""
    if not daten:
        return "0"
    return str(daten.count(b"\n") + (0 if daten.endswith(b"\n") else 1))


def _bereinigt(text) -> str:
    return re.sub(r"[\t\r\n]+", " ", str(text))


def protokolliere(quelle, url, http_status, daten=b"", zeilen="", cache="nein", bemerkung="", methode="GET"):
    PROTOKOLL.parent.mkdir(parents=True, exist_ok=True)
    neu = not PROTOKOLL.exists() or PROTOKOLL.stat().st_size == 0
    pruef = hashlib.sha256(daten).hexdigest() if (daten or methode == "GET") and http_status == 200 else ""
    if methode == "HEAD":
        bemerkung = ("HEAD; " + bemerkung).rstrip("; ")
    zeile = [quelle, url, _jetzt(), http_status, len(daten), zeilen, pruef, cache, bemerkung]
    with PROTOKOLL.open("a", encoding="utf-8", newline="") as f:
        if neu:
            f.write("\t".join(SPALTEN) + "\n")
        f.write("\t".join(_bereinigt(x) for x in zeile) + "\n")


def anfragen_je_host(host: str) -> int:
    """Gesendete Anfragen an diesen Host laut Protokoll (cache=nein); mit und ohne „www.“ zusammengezählt."""
    if not PROTOKOLL.exists():
        return 0
    host = host_schluessel(host)
    n = 0
    with PROTOKOLL.open(encoding="utf-8", newline="") as f:
        for z in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if z.get("cache") == "nein" and host_schluessel(host_von(z.get("url") or "")) == host:
                n += 1
    return n


def _datei(host: str, endung: str) -> Path:
    return SPERRORT / f"struktur-{host_schluessel(host)}.{endung}"


def sperre_host(host: str, grund: str):
    SPERRORT.mkdir(parents=True, exist_ok=True)
    _datei(host, "gesperrt").write_text(f"{_jetzt()}\t{_bereinigt(grund)}\n", encoding="utf-8")


def gesperrt(host: str) -> bool:
    return _datei(host, "gesperrt").exists()


def _warte_abstand(host: str):
    zeit = _datei(host, "zeit")
    try:
        letzte = float(zeit.read_text(encoding="utf-8").strip() or 0)
    except (FileNotFoundError, ValueError):
        return
    rest = ABSTAND - (time.time() - letzte)
    if rest > 0:
        time.sleep(rest)


def _merke_ende(host: str):
    _datei(host, "zeit").write_text(f"{time.time():.3f}\n", encoding="utf-8")


def _lies_cache(url: str, methode: str):
    daten_pfad, kopf_pfad = cache_pfade(url, methode)
    if not kopf_pfad.exists() or (daten_pfad is not None and not daten_pfad.exists()):
        return None
    meta = json.loads(kopf_pfad.read_text(encoding="utf-8"))
    daten = daten_pfad.read_bytes() if daten_pfad is not None else b""
    return meta["status"], meta["kopf"], daten


def _schreibe_cache(url: str, methode: str, status: int, kopf: dict, daten: bytes, endgueltig: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    daten_pfad, kopf_pfad = cache_pfade(url, methode)
    if daten_pfad is not None:
        daten_pfad.write_bytes(daten)
    meta = {"url": url, "endgueltige_url": endgueltig, "methode": methode, "status": status, "kopf": kopf,
            "abgerufen": _jetzt(), "bytes": len(daten), "pruefsumme_sha256": hashlib.sha256(daten).hexdigest()}
    kopf_pfad.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def statuskopf_pfad(url: str, methode: str, status) -> Path:
    """Beleg der Kopfzeilen einer Antwort mit Status ≠ 200 (kein Cache-Eintrag)."""
    return CACHE / f"{_schluessel(url)}.{methode.lower()}-{status}.json"


def _schreibe_statuskopf(url: str, methode: str, status, kopf: dict):
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = {"url": url, "methode": methode, "status": status, "kopf": kopf, "abgerufen": _jetzt()}
    statuskopf_pfad(url, methode, status).write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")


def _bot_abwehr(status, kopf: dict) -> bool:
    """403 mit Kennzeichen einer Bot-Abwehr (Cf-Mitigated oder Server cloudflare)."""
    klein = {k.lower(): v for k, v in kopf.items()}
    return status == 403 and ("cf-mitigated" in klein or "cloudflare" in klein.get("server", "").lower())


def _lies(antwort, grenze: int, start: float, url: str, kopf: dict) -> bytes:
    teile, n = [], 0
    while True:
        if time.monotonic() - start > ZEITLIMIT:
            raise socket.timeout(f"Antwort dauerte länger als {ZEITLIMIT:.0f} s")
        block = antwort.read(BLOCK)
        if not block:
            break
        n += len(block)
        if n > grenze:
            raise AbrufFehler(f"Antwort größer als {grenze} Bytes, verworfen: {url}", "groesse", kopf)
        teile.append(block)
    if time.monotonic() - start > ZEITLIMIT:
        raise socket.timeout(f"Antwort dauerte länger als {ZEITLIMIT:.0f} s")
    return b"".join(teile)


def _eine_anfrage(url: str, host: str, methode: str, grenze: int, quelle: str):
    """Genau eine Anfrage unter der Sperre des Hosts. Liefert (status, kopf, daten); Protokollzeile geschrieben."""
    SPERRORT.mkdir(parents=True, exist_ok=True)
    with open(_datei(host, "lock"), "a+") as sperre:
        try:
            fcntl.flock(sperre, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AbrufFehler(f"anderer Abruf an {host} läuft (Sperre gehalten)", "parallel")
        try:
            if gesperrt(host):
                raise AbrufFehler(f"Host {host} gesperrt ({_datei(host, 'gesperrt')})", "gesperrt")
            if anfragen_je_host(host) >= OBERGRENZE:
                raise AbrufFehler(f"Obergrenze {OBERGRENZE} Anfragen an {host} erreicht", "obergrenze")
            _warte_abstand(host)
            req = urllib.request.Request(url.strip(), method=methode, headers={"User-Agent": USER_AGENT})
            oeffner = _OEFFNER_LOKAL if (TESTMODUS and host == TESTHOST) else _OEFFNER
            start = time.monotonic()
            try:
                try:
                    antwort = oeffner.open(req, timeout=ZEITLIMIT)
                except urllib.error.HTTPError as e:
                    antwort = e
                with antwort:
                    status = antwort.status if hasattr(antwort, "status") else antwort.code
                    kopf = dict(antwort.headers.items()) if antwort.headers else {}
                    if methode == "HEAD":
                        daten = b""
                    else:
                        laenge = {k.lower(): v for k, v in kopf.items()}.get("content-length", "")
                        if laenge.isdigit() and int(laenge) > grenze:
                            raise AbrufFehler(f"Content-Length {laenge} größer als {grenze} Bytes, nicht gelesen: "
                                              f"{url}", "groesse", kopf)
                        daten = _lies(antwort, grenze, start, url, kopf)
            except AbrufFehler as e:
                protokolliere(quelle, url, status, b"", "", "nein", f"verworfen: {e}", methode)
                raise
            except (socket.timeout, TimeoutError) as e:
                protokolliere(quelle, url, "zeitueberschreitung", b"", "", "nein", f"Host gesperrt: {e}", methode)
                sperre_host(host, f"Zeitüberschreitung {url}")
                raise AbrufFehler(f"Zeitüberschreitung, Host {host} gesperrt: {url}", "zeit")
            except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
                grund = getattr(e, "reason", e)
                if isinstance(grund, (socket.timeout, TimeoutError)):
                    protokolliere(quelle, url, "zeitueberschreitung", b"", "", "nein", "Host gesperrt", methode)
                    sperre_host(host, f"Zeitüberschreitung {url}")
                    raise AbrufFehler(f"Zeitüberschreitung, Host {host} gesperrt: {url}", "zeit")
                protokolliere(quelle, url, "verbindungsfehler", b"", "", "nein", f"Host gesperrt: {grund}", methode)
                sperre_host(host, f"Verbindungsfehler {url}: {grund}")
                raise AbrufFehler(f"Verbindungsfehler, Host {host} gesperrt: {url} ({grund})", "verbindung")
            finally:
                _merke_ende(host)
            klein = {k.lower(): v for k, v in kopf.items()}
            bemerkung = ""
            if status == 429 or 500 <= status <= 599 or _bot_abwehr(status, kopf):
                art = " (Bot-Abwehr)" if _bot_abwehr(status, kopf) else ""
                sperre_host(host, f"HTTP {status}{art} {url}")
                bemerkung = f"Host gesperrt nach HTTP {status}{art}"
            elif 300 <= status <= 399:
                bemerkung = "Weiterleitung nach " + klein.get("location", "?")
            if status >= 400:
                hinweise = [f"{n}: {klein[n]}" for n in ("server", "cf-mitigated") if n in klein]
                bemerkung = "; ".join([b for b in [bemerkung] if b] + hinweise)
            if status != 200:
                _schreibe_statuskopf(url, methode, status, kopf)
            protokolliere(quelle, url, status, daten, _zeilen(url, kopf, daten) if status == 200 else "", "nein",
                          bemerkung, methode)
            return status, kopf, daten
        finally:
            fcntl.flock(sperre, fcntl.LOCK_UN)


def hole(url: str, max_bytes: int = 2_000_000, methode: str = "GET", quelle: str = ""):
    """Ruft `url` gedrosselt ab und liefert (status, kopf, bytes). Status 200 kommt bei erneutem Aufruf aus dem Cache.
    Andere HTTP-Status (3xx ohne erlaubtes Ziel, 4xx, 429, 5xx) werden zurückgegeben; 429/5xx und 403 mit Bot-Abwehr
    sperren den Host.
    Regelverstöße, Sperren, Obergrenze, Zeitüberschreitung und Verbindungsfehler: AbrufFehler."""
    methode = methode.upper()
    if methode not in ("GET", "HEAD"):
        raise AbrufFehler(f"Methode {methode} nicht erlaubt", "regel")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise AbrufFehler(f"max_bytes muss eine positive ganze Zahl sein: {max_bytes!r}", "regel")
    url = url.strip()
    host = pruefe_url(url)
    quelle = quelle or host
    treffer = _lies_cache(url, methode)
    if treffer is not None:
        status, kopf, daten = treffer
        protokolliere(quelle, url, status, daten, _zeilen(url, kopf, daten), "ja", "", methode)
        return treffer
    aktuell, aktueller_host = url, host
    for stufe in range(MAX_WEITERLEITUNGEN + 1):
        grenze = min(max_bytes, MAX_BYTES_DATEN) if aktueller_host == "daten.wuppertal.de" else max_bytes
        status, kopf, daten = _eine_anfrage(aktuell, aktueller_host, methode, grenze, quelle)
        if not 300 <= status <= 399:
            break
        ziel = {k.lower(): v for k, v in kopf.items()}.get("location", "")
        if not ziel or stufe == MAX_WEITERLEITUNGEN:
            break
        ziel = urllib.parse.urljoin(aktuell, ziel)
        try:
            ziel_host = pruefe_url(ziel)
        except AbrufFehler:
            break   # Ziel nicht erlaubt: nicht gefolgt (Ziel steht in der Protokollzeile der Weiterleitung)
        aktuell, aktueller_host = ziel, ziel_host
    if status == 200:
        _schreibe_cache(url, methode, status, kopf, daten, aktuell)
    return status, kopf, daten


def _ausgabepfad(name: str) -> Path:
    pfad = Path(name)
    if not pfad.is_absolute():
        pfad = CACHE / pfad
    pfad = pfad.resolve()
    if CACHE.resolve() not in pfad.parents:
        raise AbrufFehler(f"--ausgabe nur innerhalb von {CACHE} (Rohdaten nie außerhalb des Caches)", "regel")
    return pfad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gedrosselter Abruf für Phase 0 der Strukturdaten")
    ap.add_argument("url")
    ap.add_argument("--head", action="store_true", help="nur Kopf (HEAD)")
    ap.add_argument("--ausgabe", help="Kopie des Inhalts, nur innerhalb des Cache-Verzeichnisses")
    ap.add_argument("--quelle", default="", help="Name der Quelle für das Protokoll")
    ap.add_argument("--max-bytes", type=int, default=2_000_000)
    a = ap.parse_args(argv)
    methode = "HEAD" if a.head else "GET"
    try:
        ausgabe = _ausgabepfad(a.ausgabe) if a.ausgabe else None
        status, kopf, daten = hole(a.url, max_bytes=a.max_bytes, methode=methode, quelle=a.quelle)
    except AbrufFehler as e:
        print(f"fehler {e.art}: {e}", file=sys.stderr)
        return 2
    daten_pfad, kopf_pfad = cache_pfade(a.url.strip(), methode)
    im_cache = status == 200 and kopf_pfad.exists()
    print(f"status {status}")
    print(f"cache {(daten_pfad or kopf_pfad) if im_cache else '-'}")
    klein = {k.lower(): v for k, v in kopf.items()}
    for name in ("content-type", "content-length", "last-modified", "location"):
        if name in klein:
            print(f"{name} {klein[name]}")
    if ausgabe is not None and status == 200 and methode == "GET":
        ausgabe.parent.mkdir(parents=True, exist_ok=True)
        ausgabe.write_bytes(daten)
        print(f"ausgabe {ausgabe}")
    return 0 if 200 <= status <= 299 else 1


if __name__ == "__main__":
    sys.exit(main())
