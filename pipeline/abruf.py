"""Abruf der Wuppertaler OParl-API nach der Abrufpolitik (CLAUDE.md 5.1); nur Standardbibliothek.

Aus ratsatlas-koeln @d609111 (pipeline/abruf.py); Wuppertaler Abweichungen für den gemeinsamen Kern: Domains der
Stadt (`STADT_DOMAINS`), Texte, und die Umschreibung von http:// auf https:// für Hosts der Stadt (`abrufadresse`,
wie explore/abruf.py), weil die Wuppertaler API ihre Objekt-IDs und links.next mit http:// nennt.


- genau eine Verbindung, mindestens `config.ABRUF_ABSTAND` Sekunden vom Ende einer Antwort bis zur nächsten Anfrage
  (auch nach Fehlern); für nicht lokale Adressen mindestens `MINDESTABSTAND` (2 s): kleinere Werte von
  `RATSATLAS_ABSTAND` werden mit Hinweis angehoben. Gezählt wird ab dem Import: Auch die erste Anfrage eines Prozesses
  folgt frühestens diesen Abstand nach dem Start.
- lokal sind nur Adressen mit Schema http und Host 127.0.0.1, localhost oder ::1 (`lokal()`, über urlsplit; nicht etwa
  http://localhost.example.org/ oder http://127.0.0.1.nip.io/): nur für sie entfallen Freigabe, Zeitfenster und
  Mindestabstand
- nur im nächtlichen Zeitfenster (`config.ABRUF_ZEITFENSTER`, Ortszeit Europe/Berlin); geprüft vor jedem Versuch, auch
  nach einer Pause. Für nicht lokale Adressen gilt nur ein Fenster innerhalb von 23–1 Uhr (`ERLAUBTE_STUNDEN`,
  `fenster_zulaessig`): ein leerer Wert oder ein weiteres Fenster (0-24, 22-2, 23-23) bricht vor der Anfrage mit der Art
  `zeitfenster` ab. Ausgenommen sind nur Testadressen (`testadresse`: Loopback, Domain .invalid), wie in
  explore/oparl_messung.py (Wuppertaler Abweichung von Köln, dort wirkt ein leeres Fenster für jede Adresse)
- gleichzeitige Prozesse: Vor der ersten Anfrage an eine nicht lokale Adresse nimmt ein Prozess eine exklusive Sperre
  (fcntl.flock) auf `RATSATLAS_SPERRE`/abruf.lock (Vorgabe ~/.cache/ratsatlas-wuppertal, derselbe Ort wie
  explore/abruf.py) und hält sie bis zu seinem Ende (`sperre_halten`). Hält ein anderer Prozess sie (zweiter Lauf, andere
  Arbeitskopie, Messstufe), Abbruch der Art `parallel` ohne Anfrage, nicht gezählt, keine mögliche Sperre (Wuppertaler
  Abweichung von Köln)
- nach HTTP 429, 5xx und unlesbaren Antworten (kein JSON, auch zu tief verschachtelt) wachsende Pausen
  (`config.ABRUF_PAUSEN`, bis zu mehreren Stunden), danach Abbruch der Art `aufgegeben`. Einen `Retry-After`-Kopf
  (Sekunden oder HTTP-Datum) hält der Abruf mindestens ein. Sofort `aufgegeben` (ohne Pause): wenn die nächste Pause
  nicht vor dem Ende des laufenden Zeitfensters endet (`fenster_offen_nach`, gerechnet in UTC, also auch über eine
  Zeitumstellung), wenn `Retry-After` länger ist als die längste Pause oder wenn `Retry-After` unlesbar ist. 401, 403
  und 404 brechen sofort ab (Art `http` mit `code`)
- `Retry-After` gilt über die Nacht hinaus: Endet ein Abruf als `aufgegeben` mit einem `Retry-After`, trägt der Abbruch
  `nicht_vor` (jetzt + Retry-After in UTC, höchstens `RETRY_AFTER_HOECHSTENS` = 30 Tage; unlesbar
  `RETRY_AFTER_UNLESBAR` = 7 Tage); sessionnet.py speichert den Zeitpunkt im Zustand und ruft vorher nicht ab. Mehr als
  12 Ziffern (ohne führende Nullen) gelten als unendlich lang (also 30 Tage)
- gültiges JSON in unerwarteter Form (null, [], Zahl, Text statt eines Objekts) ist kein Überlastungssignal: Abbruch
  der Art `unlesbar` nach einer Anfrage, ohne Wiederholung
- Zeitüberschreitung und Verbindungsabbruch gelten als mögliche Sperre: sofortiger Abbruch ohne Wiederholung
  (so zeigte sich in Köln die Sperre von mandari 2026; ratsatlas-koeln
  explore/ergebnisse/sessionnet_befunde.tsv); der nächste Versuch
  folgt im nächsten Zeitfenster. Welche Abbrüche als Nacht mit möglicher Sperre zählen (dann nach drei Nächten in
  Folge sieben Tage Pause), regelt sessionnet.py (`moegliche_sperre`)
- ebenso eine abgeschnittene oder unlesbare Antwort (http.client.HTTPException, kein OSError: IncompleteRead bei
  weniger Bytes als Content-Length oder chunked ohne Abschluss, BadStatusLine, LineTooLong, RemoteDisconnected …),
  auch als Antwort eines Proxys auf CONNECT: Art `sperre`, keine Wiederholung
- scheitert die Zertifikatsprüfung (ssl.SSLCertVerificationError, auch als Grund eines URLError,
  „CERTIFICATE_VERIFY_FAILED“), ist das eine Einstellung der Ausführungsumgebung (Zertifikatsspeicher, CA eines
  Proxys), keine mögliche Sperre: Abbruch der Art `tls` ohne Wiederholung, laut (Warnung, sessionnet.py), gezählt als
  Fehler, nicht als Anfrage (die HTTP-Anfrage wurde nicht gesendet); die 12-Stunden-Regel gilt über
  `letzter_abbruch`. Andere TLS-Fehler (unerwartetes Ende, Reset im Handshake) können eine Sperre sein: Art `sperre`
- eine ungültige Adresse wird nicht gesendet und nicht als Anfrage gezählt: Art `adresse`, keine Sperre. Dazu zählen
  Zeichen außerhalb von ASCII (etwa Umlaute in links.next), ein anderes Schema als http oder https (auch ftp:, file:,
  data:), eine Adresse ohne Host (http:///…, https:papers), ein Port außerhalb 0–65535 und http.client.InvalidURL (z. B.
  ein Leerzeichen). Der Öffner kennt nur http und https (keine Handler für FTP, Dateien und data:)
- jeder andere ValueError vor dem Senden ist ein Einstellungs- oder Programmfehler: Kopfzeile nicht kodierbar
  (UnicodeEncodeError, etwa RATSATLAS_KONTAKT mit Zeichen außerhalb von Latin-1) oder mit Zeilenumbruch, Host nicht als
  IDNA kodierbar, unlesbare Proxy-Adresse. Nichts geht hinaus, nichts wird gezählt; der Fehler wird laut weitergereicht
  (kein Sperrverdacht, keine Pause). Einen User-Agent mit Steuerzeichen lehnt `get_json` schon vor der Anfrage ab
- Weiterleitungen (HTTP 3xx) werden nicht verfolgt (modulweiter Öffner `_OEFFNER` aus `oeffner()` mit
  `_OhneWeiterleitung`; der Standard von urllib bleibt für andere Module unverändert): Abbruch der Art `weiterleitung`
  mit der Ziel-URL in Meldung und `Abbruch.ziel`, gezählt in `statistik()["weiterleitungen"]` und als Fehler
  (Abrufstatistik: Spalten `weiterleitungen` und `fehler`, Ziel in `ergebnis`); sonst kämen ungezählte Anfragen an
  einen anderen Host oder Pfad hinzu. Ebenso bei einem unlesbaren Ziel (etwa „http://[::1“, roh übernommen): Die
  Anfrage hat die Stadt erreicht und wird gezählt, kein Programmfehler
- antwortet ein Proxy der Ausführungsumgebung auf CONNECT nicht mit 200 („Tunnel connection failed: <Code>“), zählt
  der Code:
  - 403, 405, 407 (Ablehnung durch eine Richtlinie oder fehlende Anmeldung): keine Antwort der Stadt; Abbruch der Art
    `proxy` ohne Wiederholung, gezählt in `statistik()["proxy"]` (Spalte `proxy`); keine Nacht mit möglicher Sperre.
    Ein HTTP 407 gilt nur dann als Ablehnung durch den Proxy, wenn urllib für das Schema der Adresse einen Proxy meldet
    (`proxy_gesetzt()`, ohne Ausnahme aus no_proxy); sonst kommt er von der Gegenseite (Art `http`)
  - 429, 503 (Begrenzung oder Überlastung): wie HTTP 429/5xx (Pausen, danach `aufgegeben`)
  - alle übrigen, vor allem 502 und 504 (der Proxy erreicht die Stadt nicht): wie Zeitüberschreitung und
    Verbindungsabbruch Art `sperre` (mögliche Sperre)
- offener User-Agent mit Projektadresse und Kontakt (`config.KONTAKT`, contact@nozilla.de; ein anderer Wert in
  `RATSATLAS_KONTAKT` bricht vor der ersten Anfrage ab)
- Zählwerk je Lauf für die Abrufstatistik (`statistik()`)
- Sperre: ohne `RATSATLAS_STADT_INFORMIERT=ja` keine Anfrage an die Stadt (CLAUDE.md 5.1, 9)
- `stadt()` erkennt Adressen der Stadt (wuppertal.de, offenedaten-wuppertal.de, Host der eingestellten OParl-API);
  pipeline/net.py verweigert damit seine Anfragen an die Stadt, auch als Ziel einer Weiterleitung. Module, die
  direkt über urllib abrufen (kontext.py, anliegen.py, wahlen.py u. a.), erfasst dieser Schutz nicht
- Adressen mit http:// auf einem Host der Stadt (`stadt_host`) werden vor dem Senden auf https:// umgeschrieben
  (`abrufadresse`; CLAUDE.md 3.1: Objekt-IDs mit http://, Abruf über https://). Die IDs bleiben als Schlüssel
  unverändert; sonst endete jeder Abruf an einer 301 auf https als Abbruch der Art `weiterleitung`
- eine Uhr für alle Zeitpunkte (`uhr()`, UTC): Zeitfenster, Retry-After und der Zustand in sessionnet.py; Tests
  ersetzen sie durch eine Scheinuhr
"""
import email.utils
import fcntl
import http.client
import ipaddress
import json
import math
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time as uhrzeit, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

MINDESTABSTAND = 2.0   # Sekunden vom Ende einer Antwort bis zur nächsten Anfrage an nicht lokale Adressen (5.1)
# Ende der letzten Antwort (time.monotonic); beim Import gesetzt, damit auch die erste Anfrage eines Prozesses
# frühestens den Abstand nach dem Start folgt (wie explore/abruf.py)
_letzte = time.monotonic()
_hinweis_abstand = False
_zaehler = {"anfragen": 0, "fehler": 0, "wiederholungen": 0, "bytes": 0, "sekunden": 0.0, "weiterleitungen": 0,
            "proxy": 0}
# Meldung von http.client, wenn der Proxy den Tunnel (CONNECT) nicht aufbaut
_TUNNEL = re.compile(r"Tunnel connection failed: (\d{3})")
# Antworten eines Proxys auf CONNECT: Ablehnung durch eine Richtlinie oder fehlende Anmeldung (Art `proxy`) …
PROXY_ABLEHNUNG = (403, 405, 407)
# … Begrenzung oder Überlastung (wie HTTP 429/5xx); alle übrigen Codes, vor allem 502 und 504 (der Proxy erreicht die
# Stadt nicht), gelten wie Zeitüberschreitung und Verbindungsabbruch als mögliche Sperre
TUNNEL_UEBERLAST = (429, 503)
# Hosts lokaler Testserver (nur mit Schema http)
LOKALE_HOSTS = ("127.0.0.1", "localhost", "::1")
# Domains der Stadt Wuppertal (auch Unterdomains; CLAUDE.md 3.1/3.2: oparl., ris., daten., maps.wuppertal.de;
# offenedaten-wuppertal.de), für `stadt()` und `abrufadresse()`; wie explore/abruf.py
STADT_DOMAINS = ("wuppertal.de", "offenedaten-wuppertal.de")
# Leer- und Steuerzeichen in einer Adresse: abrufadresse() schreibt sie nicht um (wie explore/abruf.py)
RE_STEUERZEICHEN = re.compile(r"[\x00-\x20\x7f]")
ORTSZEIT = ZoneInfo("Europe/Berlin")
# Stunden, die ein Zeitfenster für nicht lokale Adressen höchstens umfassen darf: 23–1 Uhr Ortszeit (CLAUDE.md 5.1,
# vorsichtige Vorgabe bis zur Antwort der Stadt; wie ERLAUBTE_STUNDEN in explore/oparl_messung.py). Engere Fenster sind
# erlaubt, weitere nur für Testadressen (`testadresse`)
ERLAUBTE_STUNDEN = frozenset({23, 0})
# Sperre gegen gleichzeitige Abrufprozesse (wie explore/abruf.py: gleiche Datei, gleicher Ort, damit sich Pipeline und
# Messwerkzeuge gegenseitig ausschließen); der Ort wird beim Nehmen gelesen (RATSATLAS_SPERRE, z. B. für Tests)
SPERRDATEI = "abruf.lock"
_sperre = None   # offene Sperrdatei dieses Prozesses (fcntl.flock), ab der ersten Anfrage an die Stadt bis zum Ende
# Retry-After über die Nacht hinaus (`Abbruch.nicht_vor`): höchstens 30 Tage; ein unlesbarer Wert gilt als 7 Tage
RETRY_AFTER_HOECHSTENS = timedelta(days=30)
RETRY_AFTER_UNLESBAR = timedelta(days=7)


def uhr():
    """Aktuelle Zeit (UTC) für Zeitfenster, Retry-After und den Zustand des Abrufs; Tests ersetzen sie (Scheinuhr)."""
    return datetime.now(timezone.utc)


class Abbruch(RuntimeError):
    """Der Abruf wird beendet; der letzte gültige Datenstand bleibt erhalten. `art`: sperre, proxy, tls, weiterleitung,
    zeitfenster, gesperrt, parallel, http, aufgegeben, unlesbar, adresse, liste oder leer; `ziel`: Ziel einer Weiterleitung; `code`:
    HTTP-Status (bei http, bei aufgegeben nach HTTP 429/5xx oder CONNECT-Antwort 429/503, bei sperre nach einer
    CONNECT-Antwort wie 502/504), sonst None; `nicht_vor`: Zeitpunkt (UTC) aus einem Retry-After, vor dem keine
    Anfrage folgen soll, sonst None."""

    def __init__(self, meldung, art="", ziel="", code=None, nicht_vor=None):
        super().__init__(meldung)
        self.art = art
        self.ziel = ziel
        self.code = code
        self.nicht_vor = nicht_vor


class _OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Folgt keiner Weiterleitung: urllib meldet 3xx dann als HTTPError mit dem Location-Kopf (wie explore/abruf.py).
    Die Methoden http_error_3xx selbst lesen den Kopf nicht: Die geerbten zerlegten ihn vorher (urlparse, urljoin)
    und scheiterten an einem unlesbaren Ziel wie „http://[::1“ mit ValueError, nachdem die Anfrage die Stadt erreicht
    hat."""

    def http_error_302(self, req, fp, code, msg, headers):
        return None   # HTTPDefaultErrorHandler meldet HTTPError mit dem Kopf, ohne ihn zu zerlegen

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def oeffner(proxies=None):
    """Öffner für dieses Modul: nur http und https (ohne Handler für FTP, Dateien, data: und unbekannte Schemata), ohne
    Weiterleitung. `proxies`: None = Proxy aus der Umgebung (beim Bau gelesen), {} = ohne Proxy."""
    o = urllib.request.OpenerDirector()
    for h in (urllib.request.ProxyHandler(proxies), urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
              urllib.request.HTTPDefaultErrorHandler(), _OhneWeiterleitung(), urllib.request.HTTPErrorProcessor()):
        o.add_handler(h)
    return o


# modulweiter Öffner (Proxy aus der Umgebung beim Import); urllib.request.urlopen und der Standard-Öffner bleiben für
# andere Module (Geodaten, Kontextdaten) unverändert
_OEFFNER = oeffner()


def lokal(url):
    """Lokaler Testserver: Schema http und Host 127.0.0.1, localhost oder ::1 (über urlsplit). Adressen wie
    http://localhost.example.org/ oder http://127.0.0.1.nip.io/ gelten nicht als lokal."""
    try:
        teile = urllib.parse.urlsplit(url)
        return teile.scheme == "http" and teile.hostname in LOKALE_HOSTS
    except ValueError:   # z. B. unvollständige IPv6-Adresse
        return False


def testadresse(url):
    """Adresse, die kein Server der Stadt sein kann: Loopback (127.0.0.0/8, ::1, localhost) oder die reservierte Domain
    .invalid (RFC 2606). Nur für sie darf RATSATLAS_ZEITFENSTER leer oder weiter als 23–1 Uhr sein; wie
    explore/oparl_messung.py (testadresse)."""
    try:
        host = (urllib.parse.urlsplit(url or "").hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if host == "localhost" or host == "invalid" or host.endswith(".invalid"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def abrufziel_erlaubt(url):
    """Darf der Abruf der Pipeline diese Adresse ansteuern? Nur Hosts der Stadt (`stadt_host`), lokale Testserver und
    Testadressen. Gilt für die eingestellten Endpunkte (config.OPARL_BODY, config.OPARL_SYSTEM; sessionnet.fetch_all):
    Eine aus einem anderen Projekt übernommene Variable RATSATLAS_OPARL_BODY fragt sonst nach der Freigabe für Wuppertal
    einen fremden Server ab."""
    try:
        host = urllib.parse.urlsplit(url or "").hostname
    except ValueError:
        return False
    return lokal(url) or testadresse(url) or stadt_host(host)


def sperrort():
    """Ordner der Sperrdatei: RATSATLAS_SPERRE, sonst ~/.cache/ratsatlas-wuppertal (außerhalb des Checkouts)."""
    return Path(os.environ.get("RATSATLAS_SPERRE") or Path.home() / ".cache" / "ratsatlas-wuppertal")


def sperre_halten():
    """Exklusive Sperre (fcntl.flock) auf sperrort()/abruf.lock bis zum Ende des Prozesses, genommen vor der ersten
    Anfrage an eine nicht lokale Adresse. Hält ein anderer Prozess sie (auch ein Messwerkzeug aus explore/ oder ein Lauf
    aus einer anderen Arbeitskopie), Abbruch der Art `parallel` ohne Anfrage; nicht gezählt, keine mögliche Sperre.
    Übernommen aus explore/abruf.py (sperre_halten)."""
    global _sperre
    if _sperre is not None:
        return
    ort = sperrort()
    ort.mkdir(parents=True, exist_ok=True)
    pfad = ort / SPERRDATEI
    datei = open(pfad, "a+", encoding="utf-8")
    try:
        fcntl.flock(datei.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:   # BlockingIOError: ein anderer Prozess hält die Sperre
        datei.close()
        raise Abbruch(f"Ein anderer Abrufprozess läuft noch (Sperre {pfad}); keine Anfrage. Läufe und Messstufen nur "
                      "nacheinander starten.", "parallel") from e
    _sperre = datei


def sperre_freigeben():
    """Sperre dieses Prozesses lösen (für Tests; im Betrieb endet sie mit dem Prozess)."""
    global _sperre
    if _sperre is not None:
        try:
            fcntl.flock(_sperre.fileno(), fcntl.LOCK_UN)
        finally:
            _sperre.close()
            _sperre = None


def stadt(url):
    """Adresse eines Servers der Stadt Wuppertal? Host unter STADT_DOMAINS (auch Unterdomains) oder
    der Host der eingestellten OParl-API (`config.OPARL_BODY`, `config.OPARL_SYSTEM`), sofern dieser nicht lokal ist.
    Eine unlesbare Adresse gilt vorsichtshalber als Adresse der Stadt."""
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").rstrip(".")
    except (ValueError, TypeError, AttributeError):
        return True
    if stadt_host(host):
        return True
    eigene = set()
    for adresse in (config.OPARL_BODY, config.OPARL_SYSTEM):
        try:
            if not lokal(adresse):
                eigene.add((urllib.parse.urlsplit(adresse).hostname or "").rstrip("."))
        except ValueError:
            pass
    return bool(host) and host in eigene


def stadt_host(host) -> bool:
    """Liegt der Host unter einer Domain der Stadt (STADT_DOMAINS; die Domain selbst oder eine Unterdomain)? Groß- und
    Kleinschreibung und ein Punkt am Ende zählen nicht (wie explore/abruf.py)."""
    host = (host or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in STADT_DOMAINS)


def abrufadresse(url):
    """Adresse, unter der abgerufen wird: http:// auf einem Host der Stadt (Port fehlt oder 80) wird zu https:// (die
    Wuppertaler OParl-API nennt Objekt-IDs und links.next mit http://, der Abruf über https:// funktioniert laut
    CLAUDE.md 3.1). Pfad und Abfrage bleiben unverändert (keine neue URL-Kodierung); alle übrigen Adressen, auch lokale
    Testserver, ebenso. Die Kennung selbst wird nicht geändert: Schlüssel bleiben die IDs aus der Quelle.
    Übernommen aus explore/abruf.py (abrufadresse); Wuppertaler Abweichung von Köln für den gemeinsamen Kern."""
    if RE_STEUERZEICHEN.search(url.strip()):   # Leer- oder Steuerzeichen: unverändert, adresse_pruefen/http.client
        return url                              # lehnen sie ab
    teile = urllib.parse.urlsplit(url.strip())
    if teile.scheme.lower() == "http" and stadt_host(teile.hostname) and teile.port in (None, 80):
        # aus den bereinigten Teilen bauen (urlsplit entfernt Tab, CR und LF; ein Ausschnitt aus der ungereinigten
        # Zeichenkette ergäbe sonst einen anderen Host); Zugangsdaten im Host-Teil fallen weg
        host = teile.netloc.rsplit("@", 1)[-1].split(":", 1)[0]
        neu = urllib.parse.urlunsplit(("https", host, teile.path, teile.query, teile.fragment))
        kontrolle = urllib.parse.urlsplit(neu)
        if kontrolle.hostname != teile.hostname or kontrolle.port is not None or not stadt_host(kontrolle.hostname):
            raise Abbruch(f"Umschreibung auf https:// ergäbe einen anderen Host, nicht gesendet: {url!r} → {neu!r}",
                          "adresse")
        return neu
    return url


def proxy_gesetzt(url):
    """Meldet urllib.request.getproxies() für das Schema der Adresse einen Proxy, ohne Ausnahme für den Host aus
    no_proxy? Nur dann kann ein HTTP 407 vom Proxy der Ausführungsumgebung stammen."""
    try:
        teile = urllib.parse.urlsplit(url)
        host = teile.hostname or ""
    except ValueError:
        return False
    proxies = urllib.request.getproxies()
    if not proxies.get(teile.scheme):
        return False
    return not urllib.request.proxy_bypass_environment(host, proxies)


def tunnel_status(fehler):
    """Statuscode, mit dem ein Proxy den Tunnel (CONNECT) nicht aufgebaut hat (http.client meldet „Tunnel connection
    failed: 502 Bad Gateway“), sonst None."""
    if isinstance(fehler, urllib.error.HTTPError):
        return None
    m = _TUNNEL.search(str(fehler))
    return int(m.group(1)) if m else None


def proxy_ablehnung(fehler, url=""):
    """Statuscode, mit dem ein Proxy die Verbindung durch eine Richtlinie oder mangels Anmeldung abgelehnt hat, sonst
    None: CONNECT-Antwort 403, 405 oder 407, oder HTTP 407 (Proxy Authentication Required), Letzteres nur, wenn für
    die Adresse (`url`, sonst die des Fehlers) ein Proxy gesetzt ist; ohne Proxy, etwa in GitHub Actions, kommt ein 407
    von der Gegenseite. 502 und 504 (der Proxy erreicht die Stadt nicht) sowie 429 und 503 sind keine Ablehnung in
    diesem Sinn."""
    if isinstance(fehler, urllib.error.HTTPError):
        return 407 if fehler.code == 407 and proxy_gesetzt(url or fehler.filename or "") else None
    code = tunnel_status(fehler)
    return code if code in PROXY_ABLEHNUNG else None


def zertifikatsfehler(fehler):
    """Ist der Fehler eine gescheiterte Zertifikatsprüfung (ssl.SSLCertVerificationError oder ein SSL-Fehler mit
    „CERTIFICATE_VERIFY_FAILED“, auch als Grund eines URLError)? Andere SSL-Fehler (SSLEOFError, Reset im Handshake)
    zählen nicht dazu: Sie können eine Sperre sein."""
    if isinstance(fehler, urllib.error.HTTPError):
        return False
    grund = fehler.reason if isinstance(fehler, urllib.error.URLError) else fehler
    return isinstance(grund, ssl.SSLCertVerificationError) or (
        isinstance(grund, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(grund))


def _tls_abbruch(url, fehler):
    """Zertifikatsprüfung gescheitert: nicht gesendet, also keine Anfrage (der Zähler wird zurückgesetzt), aber ein
    Fehler; Art `tls`, keine mögliche Sperre."""
    _zaehler["anfragen"] -= 1
    return Abbruch(f"Zertifikatsprüfung fehlgeschlagen (TLS): {url} ({fehler}); keine HTTP-Anfrage gesendet. Vermutlich "
                   "eine Einstellung der Ausführungsumgebung (Zertifikatsspeicher, CA eines Proxys); Zertifikat der "
                   "Gegenseite oder Sperrseite nicht ausgeschlossen", "tls")


def _proxy_abbruch(url, code):
    _zaehler["proxy"] += 1
    return Abbruch(f"Ablehnung durch den Proxy der Ausführungsumgebung (HTTP {code} beim Verbindungsaufbau): {url}; "
                   "die Anfrage hat die Stadt nicht erreicht, kein Hinweis auf eine Sperre. Nicht wiederholen, "
                   "Netzfreigabe der Umgebung prüfen", "proxy", code=code)


def abstand(lokal):
    """Abstand in Sekunden vom Ende einer Antwort bis zur nächsten Anfrage: `config.ABRUF_ABSTAND`, für nicht lokale
    Adressen mindestens MINDESTABSTAND (kleinere oder unlesbare Werte werden mit einem Hinweis angehoben)."""
    global _hinweis_abstand
    wert = config.ABRUF_ABSTAND
    if lokal or (math.isfinite(wert) and wert >= MINDESTABSTAND):
        return wert
    if not _hinweis_abstand:
        print(f"Hinweis: RATSATLAS_ABSTAND={wert:g} s liegt unter dem Mindestabstand für Anfragen an die Stadt; "
              f"es gilt {MINDESTABSTAND:g} s (CLAUDE.md 5.1).", file=sys.stderr)
        _hinweis_abstand = True
    return MINDESTABSTAND


def freigegeben(url):
    """Anfragen an Server der Stadt nur nach deren Information; lokale Testserver (`lokal()`) immer. Gilt für jede
    nicht lokale Adresse, nicht nur für Hosts der Stadt (strenger als nötig, wie Köln)."""
    return lokal(url) or os.environ.get("RATSATLAS_STADT_INFORMIERT") == "ja"


def _ortszeit(jetzt=None):
    """`jetzt` als Ortszeit (Europe/Berlin): ohne Angabe die aktuelle Zeit, ohne Zone als Ortszeit gelesen, sonst umgerechnet."""
    if jetzt is None:
        return uhr().astimezone(ORTSZEIT)
    return jetzt.replace(tzinfo=ORTSZEIT) if jetzt.tzinfo is None else jetzt.astimezone(ORTSZEIT)


def _fenster():
    """(von, bis) des Zeitfensters in vollen Stunden Ortszeit; None ohne Zeitfenster."""
    fenster = (config.ABRUF_ZEITFENSTER or "").strip()
    if not fenster:
        return None
    von, bis = (int(x) for x in fenster.split("-"))
    return von, bis


def fenster_zulaessig(url):
    """Ist das eingestellte Zeitfenster für diese Adresse zulässig? Für Testadressen (`testadresse`) jedes, auch ein
    leeres; sonst nur ein Fenster, dessen Stunden in ERLAUBTE_STUNDEN (23–1 Uhr) liegen. Leer, weiter (0-24, 22-2, von =
    bis) oder unlesbar: nicht zulässig."""
    if testadresse(url):
        return True
    fenster = (config.ABRUF_ZEITFENSTER or "").strip()
    if not fenster:
        return False
    try:
        von, bis = (int(x) for x in fenster.split("-"))
    except ValueError:
        return False
    if not (0 <= von <= 24 and 0 <= bis <= 24):
        return False
    stunden = set(range(von, bis)) if von < bis else set(range(von, 24)) | set(range(0, bis))
    return stunden <= ERLAUBTE_STUNDEN


def im_zeitfenster(jetzt=None):
    f = _fenster()
    if f is None:
        return True
    von, bis = f
    h = _ortszeit(jetzt).hour
    return von <= h < bis if von < bis else (h >= von or h < bis)


def fenster_ende(jetzt=None):
    """Ende des laufenden Zeitfensters als Zeitpunkt mit Zone (Ortszeit Europe/Berlin); None ohne Zeitfenster oder bei einem
    Fenster über den ganzen Tag (von = bis). Voraussetzung: `jetzt` liegt im Fenster."""
    f = _fenster()
    if f is None or f[0] == f[1]:
        return None
    von, bis = f
    ort = _ortszeit(jetzt)
    tag = ort.date()
    if von > bis and ort.hour >= von:   # Fenster über Mitternacht, jetzt vor Mitternacht: Ende am nächsten Tag
        tag += timedelta(days=1)
    tag += timedelta(days=bis // 24)
    return datetime.combine(tag, uhrzeit(bis % 24), tzinfo=ORTSZEIT)


def fenster_offen_nach(sekunden, jetzt=None):
    """Ist das Zeitfenster jetzt offen und endet eine Pause von `sekunden` vor dem Ende des laufenden Fensters? Gerechnet
    in UTC (Zeitumstellung); eine Pause, die erst im Fenster einer späteren Nacht endet, zählt nicht als offen."""
    ort = _ortszeit(jetzt)
    if not im_zeitfenster(ort):
        return False
    ende = fenster_ende(ort)
    if ende is None:
        return True
    rest = (ende.astimezone(timezone.utc) - ort.astimezone(timezone.utc)).total_seconds()
    return sekunden < rest


_SEKUNDEN = re.compile(r"[0-9]+")


def retry_after_sekunden(wert, jetzt=None):
    """`Retry-After` in Sekunden (ab `jetzt`, UTC): Sekundenzahl oder HTTP-Datum (RFC 9110); fehlt der Kopf, 0; ein
    Datum in der Vergangenheit ergibt 0. Mehr als 12 Ziffern (ohne führende Nullen): math.inf, länger als jede Pause
    (int() lehnte über 4300 Ziffern ab; gespeichert wird höchstens RETRY_AFTER_HOECHSTENS). Unlesbar (auch negativ):
    None."""
    wert = (wert or "").strip()
    if not wert:
        return 0
    if _SEKUNDEN.fullmatch(wert):
        ziffern = wert.lstrip("0") or "0"
        return int(ziffern) if len(ziffern) <= 12 else math.inf
    try:
        datum = email.utils.parsedate_to_datetime(wert)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if datum is None:
        return None
    if datum.tzinfo is None:   # „-0000“: UTC ohne Angabe der Quelle
        datum = datum.replace(tzinfo=timezone.utc)
    jetzt = jetzt or uhr()
    return max(0, math.ceil((datum - jetzt).total_seconds()))


def nicht_vor(retry_after):
    """Zeitpunkt (UTC), vor dem nach einem Retry-After keine Anfrage folgt: jetzt + Retry-After, höchstens
    RETRY_AFTER_HOECHSTENS (auch für Werte, die als Zeitspanne nicht darstellbar wären); unlesbar (None):
    RETRY_AFTER_UNLESBAR; ohne Retry-After (0): None."""
    if retry_after is None:
        return uhr() + RETRY_AFTER_UNLESBAR
    if retry_after <= 0:
        return None
    return uhr() + timedelta(seconds=min(retry_after, RETRY_AFTER_HOECHSTENS.total_seconds()))


def _aufgegeben(url, letzter_fehler, versuche, grund="", retry_after=0):
    code = getattr(letzter_fehler, "code", None) if isinstance(letzter_fehler, urllib.error.HTTPError) else \
        tunnel_status(letzter_fehler)
    return Abbruch(f"aufgegeben nach {versuche} Versuch(en){grund}: {url} ({letzter_fehler})", "aufgegeben", code=code,
                   nicht_vor=nicht_vor(retry_after))


def adresse_pruefen(url):
    """Grund, aus dem eine Adresse nicht gesendet wird, sonst None: Zeichen außerhalb von ASCII, anderes Schema als
    http oder https, kein Host, unlesbarer Port."""
    if not url.isascii():   # z. B. Umlaute in links.next: http.client scheiterte beim Kodieren
        return "Zeichen außerhalb von ASCII"
    try:
        teile = urllib.parse.urlsplit(url)
        teile.port   # Port außerhalb 0–65535 oder keine Zahl: ValueError
    except ValueError as e:
        return f"unlesbar ({e})"
    if teile.scheme not in ("http", "https"):
        return f"Schema {teile.scheme or '(fehlt)'} statt http oder https"
    if not teile.hostname:
        return "ohne Host"
    return None


def _kopf_pruefen():
    """User-Agent ohne Steuerzeichen (etwa ein Zeilenumbruch in RATSATLAS_KONTAKT) und mit dem festgelegten Kontakt
    (config.KONTAKT; ein anderer Wert in RATSATLAS_KONTAKT steht in config.KONTAKT_ABWEICHEND): sonst ValueError vor der
    Anfrage, ein Einstellungsfehler (laut, kein Sperrverdacht)."""
    abweichend = getattr(config, "KONTAKT_ABWEICHEND", None)
    if abweichend:
        raise ValueError(f"RATSATLAS_KONTAKT={abweichend!r} weicht vom festgelegten Kontakt {config.KONTAKT} ab "
                         "(CLAUDE.md 9); keine Anfrage gesendet")
    if any(ord(z) < 32 or ord(z) == 127 for z in config.USER_AGENT):
        raise ValueError(f"User-Agent enthält Steuerzeichen (RATSATLAS_KONTAKT prüfen): {config.USER_AGENT!r}; keine "
                         "Anfrage gesendet")


def statistik():
    return dict(_zaehler)


def get_json(url, pausen=None):
    """Eine Anfrage nach der Abrufpolitik; liefert das JSON-Objekt."""
    global _letzte
    if not freigegeben(url):
        raise Abbruch(f"Abruf gesperrt: Die Stadt {config.STADT_NAME} ist noch nicht informiert (CLAUDE.md 5.1, 9). "
                      "Freigabe mit RATSATLAS_STADT_INFORMIERT=ja.", "gesperrt")
    _kopf_pruefen()   # Einstellungsfehler: laut, vor jeder Anfrage
    grund = adresse_pruefen(url)
    if grund:   # nichts ginge hinaus (oder an ein anderes Schema): nicht gesendet, nicht gezählt, keine Sperre
        _zaehler["fehler"] += 1
        raise Abbruch(f"ungültige Adresse ({grund}), nicht gesendet: {url}", "adresse")
    try:
        ziel_url = abrufadresse(url)   # http:// → https:// für Hosts der Stadt; `url` bleibt die Kennung
    except Abbruch:
        _zaehler["fehler"] += 1
        raise
    ist_lokal = lokal(url)
    if not ist_lokal and not fenster_zulaessig(url):   # leer oder weiter als 23–1 Uhr: nur für Testadressen
        raise Abbruch(f"Zeitfenster {config.ABRUF_ZEITFENSTER!r} für Server der Stadt nicht zulässig (leer oder weiter "
                      "als 23–1 Uhr, RATSATLAS_ZEITFENSTER; CLAUDE.md 5.1); keine Anfrage", "zeitfenster")
    pausen = config.ABRUF_PAUSEN if pausen is None else pausen
    mindestens = abstand(ist_lokal)
    letzter_fehler = None
    for versuch in range(len(pausen) + 1):
        if not ist_lokal and not im_zeitfenster():
            if letzter_fehler is not None:   # nach 429/5xx/unlesbar: zählt als aufgegeben (mögliche Sperre)
                raise _aufgegeben(url, letzter_fehler, versuch, ", Zeitfenster vorbei")
            raise Abbruch(f"außerhalb des Zeitfensters {config.ABRUF_ZEITFENSTER} Uhr (RATSATLAS_ZEITFENSTER)",
                          "zeitfenster")
        if not ist_lokal:
            sperre_halten()   # anderer Abrufprozess: Abbruch `parallel` vor der Anfrage
        warte = mindestens - (time.monotonic() - _letzte)
        if warte > 0:
            time.sleep(warte)
        start = time.monotonic()
        try:
            req = urllib.request.Request(ziel_url, headers={"User-Agent": config.USER_AGENT,
                                                            "Accept": "application/json"})
        except ValueError as e:   # von adresse_pruefen nicht erkannt: nicht gesendet, keine Sperre
            _zaehler["fehler"] += 1
            raise Abbruch(f"ungültige Adresse, nicht gesendet: {url} ({e})", "adresse") from e
        _zaehler["anfragen"] += 1
        retry_after = 0
        daten = None
        gesendet = False
        try:
            with _OEFFNER.open(req, timeout=90) as r:
                gesendet = True
                daten = r.read()   # weniger Bytes als Content-Length oder chunked ohne Abschluss: IncompleteRead
        except urllib.error.HTTPError as e:
            _zaehler["fehler"] += 1
            if 300 <= e.code < 400:   # Weiterleitung: nicht folgen, Ziel nennen, abbrechen
                _zaehler["weiterleitungen"] += 1
                _zaehler["sekunden"] += time.monotonic() - start
                ort = e.headers.get("Location") if e.headers else None
                try:
                    ziel = urllib.parse.urljoin(ziel_url, ort) if ort else ""
                except ValueError:   # unlesbares Ziel (etwa „http://[::1“): roh übernehmen
                    ziel = ort
                raise Abbruch(f"Weiterleitung HTTP {e.code} nach {ziel or '(ohne Ziel)'} nicht verfolgt: {url}",
                              "weiterleitung", ziel, e.code) from e
            if proxy_ablehnung(e, url):   # HTTP 407, und für die Adresse ist ein Proxy gesetzt
                _zaehler["sekunden"] += time.monotonic() - start
                raise _proxy_abbruch(url, e.code) from e
            if e.code != 429 and e.code < 500:
                _zaehler["sekunden"] += time.monotonic() - start
                raise Abbruch(f"HTTP {e.code}: {url}", "http", code=e.code) from e
            letzter_fehler = e
            retry_after = retry_after_sekunden(e.headers.get("Retry-After") if e.headers else None)
        except http.client.InvalidURL as e:   # vor dem Senden erkannt (z. B. Leerzeichen): keine Anfrage, keine Sperre
            _zaehler["anfragen"] -= 1
            _zaehler["fehler"] += 1
            raise Abbruch(f"ungültige Adresse, nicht gesendet: {url} ({e})", "adresse") from e
        except ValueError as e:
            if zertifikatsfehler(e):   # ssl.SSLCertVerificationError ist auch ein ValueError (sonst als URLError)
                _zaehler["fehler"] += 1
                _zaehler["sekunden"] += time.monotonic() - start
                raise _tls_abbruch(url, e) from e
            # vor dem Senden: Kopfzeile nicht kodierbar (UnicodeEncodeError, etwa RATSATLAS_KONTAKT außerhalb von
            # Latin-1) oder mit Zeilenumbruch, Host nicht als IDNA kodierbar, unlesbare Proxy-Adresse. Kein
            # Sperrsignal, sondern ein Einstellungs- oder Programmfehler: laut weiterreichen, nicht als „unlesbar“
            # werten (keine Pausen); nicht gesendet, also nicht gezählt
            if not gesendet:
                _zaehler["anfragen"] -= 1
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException) as e:
            # HTTPException (kein OSError): Antwort abgeschnitten (IncompleteRead) oder unlesbar (BadStatusLine,
            # LineTooLong …), auch als Antwort des Proxys auf CONNECT – wie ein Verbindungsabbruch
            _zaehler["fehler"] += 1
            if zertifikatsfehler(e):   # Einstellung der Ausführungsumgebung: keine HTTP-Anfrage, keine Sperre
                _zaehler["sekunden"] += time.monotonic() - start
                raise _tls_abbruch(url, e) from e
            code = tunnel_status(e)
            if code not in TUNNEL_UEBERLAST:
                _zaehler["sekunden"] += time.monotonic() - start
                if code in PROXY_ABLEHNUNG:   # Ablehnung durch den Proxy: keine Antwort der Stadt, keine Sperre
                    raise _proxy_abbruch(url, code) from e
                grund = (f"Der Proxy erreicht die Stadt nicht (HTTP {code} beim Verbindungsaufbau)" if code
                         else f"Antwort abgeschnitten oder unlesbar ({type(e).__name__})"
                         if isinstance(e, http.client.HTTPException)
                         else "Zeitüberschreitung oder Verbindungsabbruch")
                raise Abbruch(f"{grund}, mögliche Sperre: {url} ({e}); nächster Versuch im nächsten Zeitfenster",
                              "sperre", code=code) from e
            letzter_fehler = e   # CONNECT-Antwort 429/503 (Begrenzung, Überlastung): wie HTTP 429/5xx
        finally:   # der Abstand gilt ab dem Ende der Antwort, auch nach Fehlern
            _letzte = time.monotonic()
        if daten is not None:
            _zaehler["bytes"] += len(daten)
            try:
                antwort = json.loads(daten)
            except (ValueError, RecursionError) as e:   # unlesbar: kein JSON, falsche Kodierung, zu tief verschachtelt
                _zaehler["fehler"] += 1
                letzter_fehler = e
            else:
                _zaehler["sekunden"] += time.monotonic() - start
                if not isinstance(antwort, dict):   # gültiges JSON in unerwarteter Form: kein Überlastungssignal
                    _zaehler["fehler"] += 1
                    raise Abbruch(f"unerwartete Antwortform (JSON-Objekt erwartet, erhalten: "
                                  f"{type(antwort).__name__}): {url}", "unlesbar")
                return antwort
        _zaehler["sekunden"] += time.monotonic() - start
        if versuch < len(pausen):
            # Sofort aufgeben (zählt als Nacht mit möglicher Sperre), statt eine Pause abzuwarten, die nicht passt;
            # ein Retry-After gilt dann über die Nacht hinaus (Abbruch.nicht_vor)
            if retry_after is None:
                raise _aufgegeben(url, letzter_fehler, versuch + 1, ", Retry-After unlesbar", retry_after)
            if retry_after > max(pausen):
                dauer = f"{retry_after} s" if math.isfinite(retry_after) else "mit mehr als 12 Ziffern"
                raise _aufgegeben(url, letzter_fehler, versuch + 1,
                                  f", Retry-After {dauer} länger als die längste Pause ({max(pausen)} s)", retry_after)
            pause = max(pausen[versuch], retry_after)
            if not ist_lokal and not fenster_offen_nach(pause):
                raise _aufgegeben(url, letzter_fehler, versuch + 1, ", nächste Pause reicht über das Zeitfenster",
                                  retry_after)
            _zaehler["wiederholungen"] += 1
            time.sleep(pause)
    raise _aufgegeben(url, letzter_fehler, len(pausen) + 1, retry_after=retry_after)
