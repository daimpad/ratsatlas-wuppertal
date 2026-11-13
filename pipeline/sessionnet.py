"""SessionNet-Adapter: Abruf der OParl-API (Wuppertal, aus ratsatlas-koeln @d609111) ins Bonner Rohdatenformat
(CLAUDE.md 5.1).

Für Wuppertal gelten die Kölner Befunde, auf denen der Adapter beruht, nur als Vorlage; umgestellt nach den Messstufen
(explore/STUFEN.md) und dem freigegebenen Plan für Phase 2 (CLAUDE.md 9, 13.11.2026), Abweichungen von Köln in NOTICE:
- `modified_since` wird URL-kodiert gesendet (Stufe 2: unkodiert unwirksam, kodiert wirksam; Köln umgekehrt), auch in
  jeder Folgeadresse aus links.next (`_filter_in_folgeadresse`). Jede Seite eines inkrementellen Laufs wird geprüft:
  Enthält sie Vorlagen mit `modified` vor der Grenze, wirkt der Filter nicht, und der Lauf bricht ab (Art `filter`),
  statt still die ganze Liste zu laden; der letzte gültige Stand bleibt.
- Vollabruf der Vorlagen mit Zeitfilter (`Zeitfilter`): links.next ab Seite 1 bis zur ersten Seite ganz vor
  config.DATEN_AB nach `created` (Grenzseite), danach config.ABRUF_SICHERHEITSABSTAND weitere Seiten in Folge ohne
  Vorlage im Zeitraum; fachlich behalten werden Vorlagen mit `date` ab config.DATEN_AB (`im_zeitraum`). Seitenprotokoll
  in config.ABRUFSTATISTIK_SEITEN. Die Liste wird nie über ihr Ende (links.next leer) hinaus gelesen; es werden keine
  Seitenadressen gebildet. Eine Fehlantwort ist kein Ende, sondern ein Abbruch wie sonst: HTTP 401 etwa (Stufe 3:
  Seite 250) bricht mit Art `http` ab, zählt als Nacht mit möglicher Sperre und hinterlässt eine Fortsetzung. Als
  Treffer, der die Zählung des Sicherheitsabstands zurücksetzt, gilt nur eine Vorlage mit lesbarem `date` (sonst
  `created`) ab config.DATEN_AB; Vorlagen ohne beides werden behalten (`im_zeitraum`), verlängern den Abruf aber nicht.
- Organisationen immer vollständig (Stufe 4: 240 auf 3 Seiten; `modified_since` ist für diese Liste nicht gemessen).
- Sitzungen nicht als ganze Liste (`fetch_meetings`): die ersten config.ABRUF_SITZUNGSSEITEN Seiten der Liste für
  künftige Termine und die von Beratungen der Vorlagen im Zeitraum verwiesenen Sitzungen einzeln über ihre Kennung
  (ohne Dubletten, aus dem Cache `meetings_roh.jsonl`, fortsetzbar nach einem Abbruch); einzelne Sitzungen mit HTTP
  404/410 oder 401/403 werden vermerkt, erst mehrere in Folge beenden den Lauf; künftige Sitzungen aus der Liste, die
  dort nicht mehr stehen, werden begrenzt einzeln erneuert.
- `schaetzung`: Zahl der Anfragen und Dauer des Vollabrufs aus den Messwerten, ohne Netz.
Die IDs der Quelle (http://) sind Schlüssel; abgerufen wird über https:// (`abruf.abrufadresse`).

Erzeugt dieselben Rohdateien wie der Bonner Abruf, damit build.py, Export und Seite unverändert bleiben:
- `papers.jsonl`      Vorlagen (OParl-Objekte), zusammengeführt über die ID; gelöschte bleiben mit `deleted`
- `organizations.json` und `verwaltungsbereiche.json`
- `meetings.json`     Sitzungen im Bonner Kurzformat; vollständige Sitzungen mit TOPs in `meetings_roh.jsonl`
- `legislative_terms.json`
- `beratungen.jsonl`  Beratung → Sitzung und TOP (in Bonn aus OParl-Lite; in Köln abgeleitet, weil `consultation`
                      direkt auf `meeting` und `agendaItem` verweist und die Sitzungen ihre TOPs enthalten)

Abruf: Listen nur über `links.next`, die Vorlagen nach dem ersten Lauf inkrementell über `modified_since` (Zustand in
`zustand_abruf.json`, mit einem Tag Überlappung). Parameter werden URL-kodiert (Wuppertal, Stufe 2, 10.11.2026; in Köln
beantwortete SessionNet kodierte Zeitstempel mit HTTP 404, ratsatlas-koeln explore/ergebnisse/sessionnet_befunde.tsv).
Schutz gegen Endlosschleifen: Abbruch, wenn links.next auf eine in diesem Lauf gelesene Seite zeigt, eine Seite nur
Kennungen bringt, die in diesem Lauf schon kamen, eine Seite keine neuen Kennungen bringt (in einer Fortsetzung bis zur
erlaubten Seitenverschiebung, siehe unten), mehr als
`config.ABRUF_MAX_SEITEN` Seiten in einem Lauf folgen (eine Fortsetzung zählt neu) oder ein Vollabruf über seine
Fortsetzungen hinweg mehr als `config.ABRUF_MAX_SEITEN_FAKTOR` × `config.ABRUF_MAX_SEITEN` Seiten erreicht (Art
`liste`).
Ende der Liste: `links` oder `links.next` fehlt oder ist leer (null, "", [], {}; SessionNet ist PHP). Ob der Server
den Filter anwendet, wird je Lauf geprüft und in der Abrufstatistik vermerkt.

Ein Vollabruf, der am Ende des Zeitfensters oder durch einen Fehler abbricht, wird in der nächsten Nacht fortgesetzt
(`<liste>_fortsetzung` im Zustand mit dem Zeitpunkt `gespeichert`, Teilstand in `<datei>.teil.jsonl`), und zwar eine
Seite vor der Stelle, an der er abbrach (eine Anfrage mehr): Wurden zwischen den Nächten bis zu einer Seite (25)
gelesener Vorlagen gelöscht, rücken die folgenden nach vorn und gingen sonst verloren; bei mehr Löschungen können
Vorlagen bis zum nächsten Vollabruf fehlen. Köln liefert die Vorlagen neueste zuerst und ohne Gesamtzahlen (Stufe 1,
07.11.2026): Neue Vorlagen zwischen zwei Nächten verschieben die Seiten nach hinten, Seiten der Fortsetzung bringen dann
schon gelesene Vorlagen (zusammengeführt über die Kennung; die wiederholte Seite zählt ebenso). Solche Seiten gelten
bis zur erlaubten Seitenverschiebung nicht als Schleife: 4 Seiten je angefangenem Tag seit `gespeichert`, höchstens 40
(`verschiebung_erlaubt`; nach ausgelassenen Nächten, sieben Tagen Pause oder einem Retry-After entsprechend mehr), bei
25 je Seite also rund 100 (genauer 99: die wiederholte Seite zählt mit) neue Vorlagen je Tag. Bricht eine Fortsetzung
ab, bevor sie die verschobene Zone verlassen hat, bleibt `gespeichert` (die Verschiebung seit dann besteht weiter;
ein künftiger Wert gilt als jetzt), sonst gilt der neue Zeitpunkt. Verlassen ist die Zone erst mit einer ungelesenen
Vorlage, deren `created` älter ist als das der ältesten gelesenen (neueste zuerst heißt in Köln `created` absteigend:
neue Vorlagen sind jünger, der ungelesene Rest ist älter). So zählen nach langer Pause auch zwei Strecken gelesener
Seiten (aus der Vornacht und aus der ersten Nacht, dazwischen neue Vorlagen) zur Zone, und überwiegen Löschungen die
neuen Vorlagen, ist sie gleich mit der ersten Seite verlassen. Ohne lesbares `created` (mit Zone) bleibt
`gespeichert`. Die neuen Vorlagen am Listenanfang holt der nächste inkrementelle Lauf (modified_since ab dem Start des
Vollabrufs).
Zwischen den Nächten gelöschte, schon gelesene Vorlagen bleiben bis zum nächsten Vollabruf bzw. bis zu ihrem Eintrag
mit `deleted` aus modified_since im Stand. Keine
Fortsetzung nach einem Abbruch der Art `liste` (Schleife in links.next), `weiterleitung`, `proxy` oder `adresse`
(ungültige Adresse): Der nächste Lauf beginnt von vorn. Eine unlesbare Fortsetzung (auch eine fehlende oder unlesbare
Teildatei) wird verworfen und gemeldet; der Vollabruf beginnt dann von vorn.

Nacht mit möglicher Sperre (`moegliche_sperre`, Zähler `sperre_verdacht` im Zustand): Zeitüberschreitung,
Verbindungsabbruch, abgeschnittene oder unlesbare Antwort, Proxy erreicht die Stadt nicht (Art `sperre`), HTTP 401,
403 oder 429 (Art `http`), `aufgegeben` nach 429, 5xx, unlesbarer Antwort oder CONNECT-Antwort 429/503 (auch sofort,
wenn die Pause nicht mehr ins Zeitfenster passt oder Retry-After zu lang oder unlesbar ist, abruf.py), außerdem
vorsichtshalber eine Weiterleitung (etwa auf die Sperrseite einer Firewall) und gültiges JSON in unerwarteter Form
(Art `unlesbar`: kein Objekt, Body ohne Listen, Seite ohne Liste `data` oder mit einem nicht leeren `links`, das kein
Objekt ist). Nach drei solchen Nächten ohne vollständigen Lauf dazwischen pausiert der Abruf sieben Tage; ein
vollständiger Lauf setzt den Zähler zurück. Nicht: Ablehnung durch den Proxy der Ausführungsumgebung (`proxy`),
ungültige Adressen (`adresse`) und eine gescheiterte Zertifikatsprüfung (`tls`, vermutlich eine Einstellung der
Ausführungsumgebung; ein Zertifikat der Gegenseite oder eine Sperrseite ist nicht ausgeschlossen), denn diese Anfragen
haben die Stadt nicht als HTTP-Anfrage erreicht, sowie ein Vollabruf deutlich kleiner als der vorhandene Stand (Art
`leer`, Regel aus Bonn: weniger als 90 %). Nächte mit `tls` zählt `tlsfehler` (wie `listenfehler`, Warnung im Log):
nach drei solchen Nächten ohne vollständigen Lauf dazwischen sieben Tage Pause.
Nach jedem Abbruch außer dem Ende des Zeitfensters (auch nach `proxy`, `adresse`, Programm- und Einstellungsfehlern)
folgt in derselben Nacht (12 Stunden, `SPERRE_GLEICHE_NACHT`) kein weiterer Lauf, etwa nach einem Push oder auf
Knopfdruck (`letzter_abbruch` im Zustand; nicht für lokale Testserver).
Retry-After über die Nacht hinaus: Gibt abruf.py wegen eines Retry-After auf, steht `nicht_vor` im Zustand (höchstens
30 Tage, unlesbarer Retry-After 7 Tage); bis dahin wird jeder Lauf übersprungen.
Abbrüche der Art `liste` oder `adresse` (dauerhaft ungültiges links.next oder Schleife: jede Nacht ein Vollabruf bis
zur selben Stelle) zählt `listenfehler` im Zustand (Nächte, nicht Läufe: ein weiterer Abbruch innerhalb von 12
Stunden zählt nicht noch einmal): Hinweis in STAND.json (`abruf_hinweis`) und Warnung im Log des Workflows; nach drei
solchen Nächten ohne vollständigen Lauf dazwischen sieben Tage Pause.
Der Zustand wird vor der ersten Anfrage geprüft: Ist die Datei oder ein Zeitpunkt des letzten Abrufs einer Liste
unlesbar, bricht der Lauf ohne Anfrage laut ab (`ZustandUnlesbar`; so jeder Lauf, bis die Datei geprüft ist). Ein
unlesbarer, zonenloser oder künftiger Zeitpunkt des letzten Sperrverdachts, Listenfehlers oder Abbruchs gilt als
„jetzt“ (in dieser Nacht kein Abruf), eine unlesbare Zahl der Nächte als drei, ein unlesbares `nicht_vor` als jetzt +
7 Tage, eines mehr als 30 Tage voraus als jetzt + 30 Tage; alles wird neu geschrieben und gemeldet. Eine unlesbare
STAND.json wird als `STAND.json.defekt` beiseitegelegt.
Programm- und Einstellungsfehler (etwa eine unerwartete Form tief in einem Objekt, ein RuntimeError ohne Art, ein
Zeilenumbruch im User-Agent) zählen nicht als Sperrverdacht: Sie stehen in STAND.json und brechen den Lauf mit
Traceback ab.
Fällt der Abruf aus, bleibt der letzte gültige Stand; der Fehler steht in `STAND.json` (`abruf_fehler`). Ein
vollständiger Lauf entfernt `abruf_fehler`, `abruf_hinweis` und `abruf_uebersprungen`. Das Ende des Zeitfensters
(etwa bei einem Vollabruf über mehrere Nächte) ist kein Fehler: neutraler Hinweis in `abruf_hinweis`, ein älteres
`abruf_fehler` entfällt. Den Zustand sichert pages.yml gleich nach dem Abrufschritt, auch wenn ein späterer Schritt
scheitert.

Abrufstatistik (`abrufstatistik.tsv`, Spalten STAT_SPALTEN): je Liste eine Zeile und eine Zeile `body` für den Abruf
des Bodys; Zähler aus abruf.statistik() als Differenz je Zeile, darunter `weiterleitungen` und `proxy`.
"""
import csv
import json
import math
import os
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from . import abruf, config
from .fetch import MIN_ANTEIL, _guard, _jsonl_count, _now, _write

UEBERLAPPUNG = timedelta(days=1)
SPERRE_NAECHTE = 3                 # Nächte in Folge mit möglicher Sperre (moegliche_sperre), danach Pause
SPERRE_PAUSE = timedelta(days=7)
SPERRE_GLEICHE_NACHT = timedelta(hours=12)   # nach einem Verdacht kein weiterer Lauf in derselben Nacht
# HTTP-Antworten, nach denen die Nacht als Nacht mit möglicher Sperre zählt (Art `http`; 429 endet sonst als
# `aufgegeben`, das ebenfalls zählt)
SPERRE_HTTP = (401, 403, 429)
STAT_SPALTEN = ["datum", "liste", "modus", "seiten", "objekte", "neu", "geaendert", "geloescht", "filter_wirksam",
                "ausserhalb_zeitraum", "grenzseite", "einzeln", "ende",
                "anfragen", "fehler", "wiederholungen", "weiterleitungen", "proxy", "bytes", "sekunden", "ergebnis"]
# Seitenprotokoll der Vorlagen (config.ABRUFSTATISTIK_SEITEN): je gelesener Seite Zahlen und Spannen, keine Inhalte
SEITEN_SPALTEN = ["datum", "liste", "modus", "seite", "objekte", "im_zeitraum", "date_ab", "date_vor", "date_fehlt",
                  "created_ab", "created_vor", "created_fehlt", "date_min", "date_max", "created_min", "created_max",
                  "folgeadresse_angepasst", "zeitfilter"]
# Zähler aus abruf.statistik(), je Zeile der Abrufstatistik als Differenz
STAT_ZAEHLER = ("anfragen", "fehler", "wiederholungen", "weiterleitungen", "proxy", "bytes", "sekunden")
# Abbruchsarten, nach denen ein Vollabruf nicht fortgesetzt wird (der nächste Lauf beginnt von vorn); `filter` tritt
# nur im inkrementellen Lauf auf (modified_since unwirksam), der keine Fortsetzung kennt
OHNE_FORTSETZUNG = ("liste", "weiterleitung", "proxy", "adresse", "filter")
# Abbruchsarten, die auf eine dauerhaft fehlerhafte Liste deuten (Zähler `listenfehler`), und deren Grenze
LISTENFEHLER = ("liste", "adresse")
LISTENFEHLER_NAECHTE = 3
LISTENFEHLER_PAUSE = timedelta(days=7)
# Nächte mit gescheiterter Zertifikatsprüfung (Zähler `tlsfehler`), danach Pause
TLS_NAECHTE = 3
TLS_PAUSE = timedelta(days=7)
# Listen mit Zeitpunkt des letzten Abrufs im Zustand
LISTEN = ("organizations", "papers", "meetings")
# Seiten ohne neue Kennungen in einer Fortsetzung, die als Seitenverschiebung gelten (neueste zuerst): je angefangenem
# Tag seit dem Speichern der Fortsetzung 4 Seiten, bei 25 je Seite rund 100 (genauer 99, die wiederholte Seite zählt
# mit) neue Vorlagen je Tag (Stufe 1: auf der ersten Seite 25 Vorlagen mit Datum 03. bis 06.11.2026), höchstens 40
# Seiten; ohne lesbaren Zeitpunkt 4. Danach gilt die Seite als Schleife.
VERSCHIEBUNG_JE_TAG = 4
VERSCHIEBUNG_HOECHSTENS = 40


class ZustandUnlesbar(RuntimeError):
    """zustand_abruf.json oder ein Zeitpunkt darin ist unlesbar: keine Anfrage, bis die Datei geprüft ist."""


def moegliche_sperre(fehler):
    """Zählt dieser Abbruch als Nacht mit möglicher Sperre? Art `sperre` (Zeitüberschreitung, Verbindungsabbruch,
    abgeschnittene oder unlesbare Antwort, Proxy erreicht die Stadt nicht), `aufgegeben` (nach 429, 5xx, unlesbarer
    Antwort oder CONNECT-Antwort 429/503) und `http` mit 401, 403 oder 429. Nicht: proxy (Ablehnung in der
    Ausführungsumgebung), tls (Zertifikatsprüfung gescheitert), liste, adresse, andere HTTP-Codes (z. B. 404). Eine
    Weiterleitung (etwa auf die Sperrseite einer vorgeschalteten Firewall) und eine unerwartete Antwortform
    (`unlesbar`) zählen vorsichtshalber mit."""
    art = getattr(fehler, "art", "")
    return art in ("sperre", "aufgegeben", "weiterleitung", "unlesbar") or (
        art == "http" and getattr(fehler, "code", None) in SPERRE_HTTP)


def _warnung(text):
    """Warnung auf stderr; in GitHub Actions als Anmerkung (::warning::), damit sie im Workflow sichtbar wird."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::warning::{text}", file=sys.stderr, flush=True)
    else:
        print(f"Warnung: {text}", file=sys.stderr, flush=True)


def _zeit(wert):
    """Zeitpunkt mit Zone aus einem ISO-Text; None, wenn kein Text, unlesbar oder ohne Zone."""
    if not isinstance(wert, str):
        return None
    try:
        t = datetime.fromisoformat(wert)
    except ValueError:
        return None
    return t if t.utcoffset() is not None else None


def _zustand():
    """Zustand des Abrufs; unlesbare Datei: ZustandUnlesbar (der Lauf bricht ohne Anfrage ab)."""
    if not config.ZUSTAND.exists():
        return {}
    try:
        z = json.loads(config.ZUSTAND.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as e:   # auch UnicodeDecodeError und zu tief verschachtelt
        raise ZustandUnlesbar(f"{config.ZUSTAND.name} unlesbar ({e}); keine Anfrage an die Stadt, bis die Datei geprüft "
                              "oder entfernt ist (ohne Datei: Vollabruf, Zähler der Nächte verloren)") from e
    if not isinstance(z, dict):
        raise ZustandUnlesbar(f"{config.ZUSTAND.name} ist kein JSON-Objekt; keine Anfrage an die Stadt, bis die Datei "
                              "geprüft ist")
    return z


def _zustand_aendern(**werte):
    """Setzt Werte im Zustand (ein Schreibvorgang); None entfernt den Schlüssel."""
    z = _zustand()
    for schluessel, wert in werte.items():
        if wert is None:
            z.pop(schluessel, None)
        else:
            z[schluessel] = wert
    config.RAW.mkdir(parents=True, exist_ok=True)
    _write(config.ZUSTAND, json.dumps(z, ensure_ascii=False, indent=1) + "\n")


def _zustand_setzen(schluessel, wert):
    _zustand_aendern(**{schluessel: wert})


def _zaehler_pruefen(z, schluessel, grenze, jetzt):
    """Zähler der Nächte (`sperre_verdacht`, `listenfehler`) und den letzten Abbruch (`letzter_abbruch`, `grenze`
    None: ohne Zahl der Nächte) vorsichtig lesen: unlesbarer, zonenloser oder künftiger Zeitpunkt `zuletzt` → jetzt (in
    dieser Nacht kein Abruf); unlesbare Zahl der Nächte → `grenze` (Pause). Liefert den Eintrag und die Meldungen zu
    ersetzten Werten."""
    v = z.get(schluessel)
    if not v:
        return {}, []
    meldungen = []
    if not isinstance(v, dict):
        meldungen.append(f"{schluessel} ist kein Objekt ({v!r})")
        v = {}
    v = dict(v)
    n = v.get("naechte")
    if grenze is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 0):
        meldungen.append(f"{schluessel}.naechte unlesbar ({n!r}), gilt als {grenze}")
        v["naechte"] = grenze
    zuletzt = _zeit(v.get("zuletzt"))
    if zuletzt is None or zuletzt > jetzt:
        grund = "in der Zukunft" if zuletzt is not None else "unlesbar oder ohne Zone"
        meldungen.append(f"{schluessel}.zuletzt {grund} ({v.get('zuletzt')!r}), gilt als jetzt")
        v["zuletzt"] = jetzt.isoformat(timespec="seconds")
    return v, meldungen


def _nicht_vor_pruefen(wert, jetzt):
    """Zeitpunkt aus einem Retry-After (`nicht_vor`) vorsichtig lesen: unlesbar, ohne Zone oder Zahl → jetzt + 7 Tage;
    mehr als 30 Tage in der Zukunft → jetzt + 30 Tage (wie beim Speichern begrenzt). Liefert (Wert, Meldung)."""
    if wert is None:
        return None, ""
    t = _zeit(wert)
    if t is None:
        neu = (jetzt + abruf.RETRY_AFTER_UNLESBAR).isoformat(timespec="seconds")
        return neu, f"nicht_vor unlesbar oder ohne Zone ({wert!r}), gilt als {neu}"
    if t > jetzt + abruf.RETRY_AFTER_HOECHSTENS:
        neu = (jetzt + abruf.RETRY_AFTER_HOECHSTENS).isoformat(timespec="seconds")
        return neu, (f"nicht_vor mehr als {abruf.RETRY_AFTER_HOECHSTENS.days} Tage in der Zukunft ({wert!r}), gilt "
                     f"als {neu}")
    return wert, ""


def _zustand_pruefen():
    """Vor der ersten Anfrage: Zustand lesen und prüfen (siehe Moduldoku). Liefert den Zustand mit geprüften Zählern."""
    z = _zustand()
    for liste in LISTEN:
        if liste in z and _zeit(z[liste]) is None:
            raise ZustandUnlesbar(f"Zeitpunkt des letzten Abrufs von {liste} in {config.ZUSTAND.name} unlesbar oder "
                                  f"ohne Zone ({z[liste]!r}); keine Anfrage an die Stadt, bis der Wert geprüft ist")
    jetzt = abruf.uhr()
    neu, meldungen = {}, []
    for schluessel, grenze in (("sperre_verdacht", SPERRE_NAECHTE), ("listenfehler", LISTENFEHLER_NAECHTE),
                               ("tlsfehler", TLS_NAECHTE), ("letzter_abbruch", None)):
        v, m = _zaehler_pruefen(z, schluessel, grenze, jetzt)
        if m:
            neu[schluessel] = v
            meldungen += m
    v, m = _nicht_vor_pruefen(z.get("nicht_vor"), jetzt)
    if m:
        neu["nicht_vor"] = v
        meldungen.append(m)
    if neu:
        z.update(neu)
        _zustand_aendern(**neu)
        _warnung(f"{config.ZUSTAND.name}: " + "; ".join(meldungen) + " (neu geschrieben)")
    return z


def _pause_grund(z, lokal):
    """Grund, den Lauf ohne Anfrage zu überspringen (12-Stunden-Regel nach jedem Abbruch, Retry-After über die Nacht
    hinaus, Pausen nach drei Nächten), sonst None. 12-Stunden-Regel und Retry-After gelten nicht für lokale Testserver."""
    jetzt = abruf.uhr()
    verdacht = z.get("sperre_verdacht") or {}
    if verdacht and not lokal:
        # nach einer Nacht mit möglicher Sperre in derselben Nacht kein weiterer Lauf (z. B. Push oder Knopfdruck)
        seit = jetzt - _zeit(verdacht["zuletzt"])
        if seit < SPERRE_GLEICHE_NACHT:
            return (f"möglicher Sperrverdacht vor {int(seit.total_seconds() // 60)} Minuten; in derselben Nacht kein "
                    "weiterer Abruf")
    letzter = z.get("letzter_abbruch") or {}
    if letzter and not lokal:
        # nach jedem anderen Abbruch (außer dem Ende des Zeitfensters), auch nach einem Programmfehler, ebenso
        seit = jetzt - _zeit(letzter["zuletzt"])
        if seit < SPERRE_GLEICHE_NACHT:
            return (f"Abbruch ({letzter.get('art') or 'unbekannt'}) vor {int(seit.total_seconds() // 60)} Minuten; in "
                    "derselben Nacht kein weiterer Abruf")
    nicht_vor = _zeit(z.get("nicht_vor"))
    if nicht_vor is not None and not lokal and jetzt < nicht_vor:
        return (f"Retry-After der Stadt: kein Abruf vor {nicht_vor.isoformat(timespec='minutes')} "
                f"(höchstens {abruf.RETRY_AFTER_HOECHSTENS.days} Tage)")
    if verdacht.get("naechte", 0) >= SPERRE_NAECHTE:
        bis = _zeit(verdacht["zuletzt"]) + SPERRE_PAUSE
        if jetzt < bis:
            return (f"Abruf pausiert bis {bis.date().isoformat()}: {verdacht['naechte']} Nächte in Folge mit möglicher "
                    "Sperre (Verbindungsabbruch, abgeschnittene oder unlesbare Antwort, HTTP 401/403/429, Weiterleitung "
                    "oder aufgegeben nach 429/5xx); bitte Kontakt zur Stadt aufnehmen")
    for schluessel, grenze, pause, grund in (
            ("listenfehler", LISTENFEHLER_NAECHTE, LISTENFEHLER_PAUSE, "Abbruch wegen einer fehlerhaften Liste "
             "(ungültige Folgeadresse in links.next oder Schleife); bitte die Liste prüfen"),
            ("tlsfehler", TLS_NAECHTE, TLS_PAUSE, "Zertifikatsprüfung fehlgeschlagen (vermutlich Einstellung der "
             "Ausführungsumgebung; Zertifikat der Gegenseite oder Sperrseite nicht ausgeschlossen); bitte prüfen")):
        fehler = z.get(schluessel) or {}
        if fehler.get("naechte", 0) >= grenze:
            bis = _zeit(fehler["zuletzt"]) + pause
            if jetzt < bis:
                return f"Abruf pausiert bis {bis.date().isoformat()}: {fehler['naechte']} Nächte in Folge {grund}"
    return None


def _stand():
    """STAND.json; eine unlesbare Datei wird als STAND.json.defekt beiseitegelegt (mit Warnung) und neu begonnen."""
    if not config.STAND.exists():
        return {}
    try:
        s = json.loads(config.STAND.read_text(encoding="utf-8"))
        if isinstance(s, dict):
            return s
        grund = "kein JSON-Objekt"
    except (ValueError, RecursionError) as e:
        grund = str(e)
    defekt = config.STAND.with_name(config.STAND.name + ".defekt")
    os.replace(config.STAND, defekt)
    _warnung(f"{config.STAND.name} unlesbar ({grund}); beiseitegelegt als {defekt.name}, neu begonnen")
    return {}


def _stand_setzen(**werte):
    s = _stand()
    s.update(werte)
    config.RAW.mkdir(parents=True, exist_ok=True)
    _write(config.STAND, json.dumps(s, ensure_ascii=False, indent=1) + "\n")


def _stand_entfernen(*schluessel):
    """Entfernt Einträge aus STAND.json (etwa `abruf_fehler` nach einem vollständigen Lauf)."""
    s = _stand()
    if any(k in s for k in schluessel):
        for k in schluessel:
            s.pop(k, None)
        _write(config.STAND, json.dumps(s, ensure_ascii=False, indent=1) + "\n")


def _stamp(schluessel):
    _stand_setzen(**{schluessel: _now()})


def _kodiert(wert):
    """Wert eines Parameters URL-kodiert (alle Zeichen außer Buchstaben, Ziffern und -._~): 2026-11-04T08:45:43+00:00
    wird zu 2026-11-04T08%3A45%3A43%2B00%3A00, wie urllib.parse.urlencode in Stufe 2 (explore/oparl_messung.py)."""
    return urllib.parse.quote(str(wert), safe="")


def _mit_parametern(url, **params):
    """Hängt Parameter URL-kodiert an (Wuppertal, Stufe 2: `modified_since` wirkt nur kodiert; unkodiert liest der
    Server „+“ vermutlich als Leerzeichen und übergeht den Filter). Abweichung von Köln (dort unkodiert)."""
    params = {k: v for k, v in params.items() if v}
    if not params:
        return url
    return url + ("&" if "?" in url else "?") + "&".join(f"{k}={_kodiert(v)}" for k, v in params.items())


def _filter_in_folgeadresse(naechste, seit):
    """Folgeadresse eines inkrementellen Laufs mit `modified_since` in kodierter Form: Wie der Server links.next bildet
    (kodiert, roh mit „+“ oder ohne den Parameter), ist für Wuppertal nicht gemessen; roh oder fehlend wäre die Folgeseite
    ungefiltert. Ersetzt bzw. ergänzt daher nur diesen einen Parameter durch den gesendeten Wert; alles andere bleibt.
    Liefert (Adresse, angepasst)."""
    if not seit or not isinstance(naechste, str):
        return naechste, False
    adresse, raute, anker = naechste.partition("#")
    basis, _, abfrage = adresse.partition("?")
    teile = [t for t in abfrage.split("&") if t]
    gesetzt = f"modified_since={_kodiert(seit)}"
    neu = [gesetzt if t.split("=", 1)[0] == "modified_since" else t for t in teile]
    if gesetzt not in neu:
        neu.append(gesetzt)
    ergebnis = basis + "?" + "&".join(neu) + raute + anker
    return ergebnis, ergebnis != naechste


class Teilabbruch(abruf.Abbruch):
    """Abbruch mitten in einer Liste; trägt den gelesenen Teil für die Fortsetzung (`zuletzt`: die zuletzt gelesene
    Seite, dort beginnt die Fortsetzung; `verlassen`: eine Fortsetzung hat die verschobene Zone verlassen, also eine
    ungelesene Vorlage gelesen, die älter ist als die älteste schon gelesene)."""

    def __init__(self, ursache, objekte, naechste, seiten, zuletzt=None, verlassen=False, zeitfilter=None):
        super().__init__(str(ursache), getattr(ursache, "art", ""), getattr(ursache, "ziel", ""),
                         getattr(ursache, "code", None), getattr(ursache, "nicht_vor", None))
        self.objekte, self.naechste, self.seiten, self.zuletzt = objekte, naechste, seiten, zuletzt
        self.verlassen = verlassen
        # Zustand des Zeitfilters vor der zuletzt gelesenen Seite (dort beginnt die Fortsetzung und liest sie erneut)
        self.zeitfilter = zeitfilter


def verschiebung_erlaubt(gespeichert, jetzt=None):
    """Seiten ohne neue Kennungen, die in einer Fortsetzung als Seitenverschiebung gelten: VERSCHIEBUNG_JE_TAG je
    angefangenem Tag seit `gespeichert` (Zeitpunkt der Fortsetzung), höchstens VERSCHIEBUNG_HOECHSTENS; fehlt der
    Zeitpunkt, ist er unlesbar oder künftig: VERSCHIEBUNG_JE_TAG."""
    t, jetzt = _zeit(gespeichert), jetzt or abruf.uhr()
    if t is None or t > jetzt:
        return VERSCHIEBUNG_JE_TAG
    tage = max(1, math.ceil((jetzt - t) / timedelta(days=1)))
    return min(VERSCHIEBUNG_JE_TAG * tage, VERSCHIEBUNG_HOECHSTENS)


def _erstellt(objekt):
    """`created` eines Objekts als Zeitpunkt mit Zone; None, wenn es fehlt, unlesbar oder ohne Zone ist."""
    return _zeit(objekt.get("created"))


def _stichtag():
    return date.fromisoformat(config.DATEN_AB)


def _datum(objekt):
    """`date` einer Vorlage als Kalendertag; None, wenn es fehlt oder unlesbar ist (die ersten zehn Zeichen zählen, damit
    auch ein Zeitpunkt statt eines Tages gelesen wird)."""
    wert = objekt.get("date")
    if not isinstance(wert, str) or len(wert) < 10:
        return None
    try:
        return date.fromisoformat(wert[:10])
    except ValueError:
        return None


def _erstellt_tag(objekt):
    """Kalendertag von `created` in Ortszeit Europe/Berlin (wie Stufe 3, Annahme); None ohne lesbares `created`."""
    t = _erstellt(objekt)
    return t.astimezone(abruf.ORTSZEIT).date() if t is not None else None


def im_zeitraum(objekt, stichtag=None):
    """Gehört die Vorlage in den Zeitraum ab config.DATEN_AB (CLAUDE.md 2)? Maßgeblich ist `date`; ohne lesbares `date`
    der Kalendertag von `created`; ohne beides wird sie behalten (nicht entscheidbar, Annahme: lieber eine ältere zu
    viel als eine fehlende)."""
    stichtag = stichtag or _stichtag()
    tag = _datum(objekt) or _erstellt_tag(objekt)
    return tag is None or tag >= stichtag


def _seitenwerte(daten, stichtag):
    """Zahlen und Spannen einer Seite für das Seitenprotokoll (nur Kalendertage, keine Inhalte)."""
    datum = [_datum(o) for o in daten]
    erstellt = [_erstellt_tag(o) for o in daten]
    da = [d for d in datum if d is not None]
    er = [d for d in erstellt if d is not None]
    return {"objekte": len(daten), "im_zeitraum": sum(1 for o in daten if im_zeitraum(o, stichtag)),
            "date_ab": sum(1 for d in da if d >= stichtag), "date_vor": sum(1 for d in da if d < stichtag),
            "date_fehlt": len(datum) - len(da),
            "created_ab": sum(1 for d in er if d >= stichtag), "created_vor": sum(1 for d in er if d < stichtag),
            "created_fehlt": len(erstellt) - len(er),
            "date_min": min(da).isoformat() if da else "", "date_max": max(da).isoformat() if da else "",
            "created_min": min(er).isoformat() if er else "", "created_max": max(er).isoformat() if er else ""}


class Zeitfilter:
    """Ende des Vollabrufs der Vorlagen (CLAUDE.md 5.1; Phase 2, 13.11.2026). Die Liste ist absteigend nach `created`
    sortiert (Stufe 1 und 3). Grenzseite: die erste Seite, deren Vorlagen alle ein lesbares `created` vor dem Stichtag
    haben (eine Vorlage ohne lesbares `created` verhindert das, vorsichtig). Danach zählt der Filter die Seiten in Folge
    ohne Treffer (lesbares `date`, sonst `created`, ab dem Stichtag); eine Seite mit Treffer setzt die Zählung auf 0
    zurück.
    Fertig, wenn `abstand` solche Seiten nach der Grenzseite gelesen sind. Der Zustand (`zustand`) geht in die
    Fortsetzung eines unterbrochenen Vollabrufs ein."""

    def __init__(self, stichtag=None, abstand=None, grenzseite=None, ohne_treffer=0):
        self.stichtag = stichtag or _stichtag()
        self.abstand = config.ABRUF_SICHERHEITSABSTAND if abstand is None else abstand
        self.grenzseite, self.ohne_treffer = grenzseite, ohne_treffer
        self.fertig = False
        self.status = ""

    def zustand(self):
        return {"grenzseite": self.grenzseite, "ohne_treffer": self.ohne_treffer}

    def seite(self, daten, nummer):
        """Wertet eine gelesene Seite aus; liefert True, wenn der Vollabruf hier enden kann. Treffer sind nur Vorlagen mit
        lesbarem `date` (sonst `created`) ab dem Stichtag: Eine Vorlage ohne beides wird behalten, setzt die Zählung
        aber nicht zurück (sonst liefe der Abruf bei vielen solchen Vorlagen bis zum Ende der Liste)."""
        treffer = sum(1 for o in daten if (t := _datum(o) or _erstellt_tag(o)) is not None and t >= self.stichtag)
        if self.grenzseite is None:
            erstellt = [_erstellt_tag(o) for o in daten]
            if daten and all(t is not None and t < self.stichtag for t in erstellt):
                self.grenzseite = nummer
                self.status = f"Grenzseite ({treffer} im Zeitraum)"
            else:
                self.status = "vor der Grenzseite"
        elif treffer:
            self.ohne_treffer = 0
            self.status = f"nach der Grenzseite, {treffer} im Zeitraum (Zählung zurückgesetzt)"
        else:
            self.ohne_treffer += 1
            self.status = f"Sicherheitsabstand {self.ohne_treffer}/{self.abstand}"
        self.fertig = self.grenzseite is not None and self.ohne_treffer >= self.abstand
        return self.fertig


def _seitennummer(url, ersatz):
    """Nummer der Seite aus dem Parameter `page` der Adresse (erste Seite ohne Parameter: 1); sonst `ersatz`."""
    try:
        werte = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    except ValueError:
        return ersatz
    seite = (werte.get("page") or [None])[0]
    if seite is None:
        return 1
    return int(seite) if seite.isdigit() else ersatz


def _leer(wert):
    """Leerer Wert (null, "", [], {}): SessionNet ist in PHP geschrieben, ein leeres Objekt kann als [] ankommen."""
    return wert is None or (isinstance(wert, (str, list, dict)) and not wert)


def _seite_pruefen(seite, url):
    """Form einer Listenseite, geprüft dort, wo sie ankommt: `data` ist eine Liste von Objekten mit Kennung (Text),
    `links` fehlt, ist leer (wie fehlend) oder ein Objekt, `links.next` fehlt, ist leer (Ende der Liste) oder Text.
    Liefert die Folgeadresse oder None (Ende). Sonst Abbruch der Art `unlesbar` (gültiges JSON in unerwarteter Form,
    etwa ein nicht leeres links, das kein Objekt ist: keine Wiederholung, zählt als Nacht mit möglicher Sperre)."""
    daten, links = seite.get("data"), seite.get("links")
    if not isinstance(daten, list) or not all(isinstance(o, dict) and isinstance(o.get("id"), str) and o["id"]
                                              for o in daten):
        grund = "data ist keine Liste von Objekten mit Kennung"
    elif _leer(links):
        return None
    elif not isinstance(links, dict):
        grund = "links ist kein Objekt"
    elif _leer(links.get("next")):
        return None
    elif isinstance(links["next"], str):
        return links["next"]
    else:
        grund = "links.next ist kein Text"
    raise abruf.Abbruch(f"unerwartete Antwortform ({grund}): {url}", "unlesbar")


def liste(url, seit=None, start=None, objekte=None, seiten=0, verschiebung=VERSCHIEBUNG_JE_TAG, zeitfilter=None,
          protokoll=None, hoechstens=None, ergebnis=None):
    """Alle Objekte einer OParl-Liste über links.next; `seit` setzt modified_since. `start`, `objekte` und `seiten`
    setzen einen abgebrochenen Vollabruf fort. Liefert (Objekte, Seiten); ein Abbruch kommt als Teilabbruch. `seiten`
    zählt die Seiten insgesamt (Statistik, Fortsetzung); die Grenze `config.ABRUF_MAX_SEITEN` gilt je Lauf, sonst
    erreichte ein großer Vollabruf sie in einer späteren Nacht und begänne von vorn. Über die Fortsetzungen hinweg gilt
    die Gesamtgrenze `config.ABRUF_MAX_SEITEN_FAKTOR` × `config.ABRUF_MAX_SEITEN` (Liste, die endlos neue Kennungen
    erzeugt). In einer Fortsetzung (`start`) gelten bis zu `verschiebung` Seiten ohne neue Kennungen als
    Seitenverschiebung (neue Vorlagen am Listenanfang, wiederholte erste Seite), nicht als Schleife; eine Seite, deren
    Kennungen alle schon in diesem Lauf kamen, und eine wiederholte Adresse bleiben eine Schleife. Ein Teilabbruch
    vermerkt, ob die Fortsetzung die verschobene Zone verlassen hat (`verlassen`, für `gespeichert`): erst mit einer
    ungelesenen Vorlage, deren `created` älter ist als das der ältesten gelesenen (ohne lesbares `created` nie).
    Wuppertal: Mit `seit` wird jede Seite geprüft; Objekte mit `modified` vor `seit` (Filter unwirksam) brechen mit der
    Art `filter` ab, und `modified_since` steht kodiert in jeder Folgeadresse. `zeitfilter` (Zeitfilter) beendet den
    Vollabruf der Vorlagen nach Grenzseite und Sicherheitsabstand; `hoechstens` beendet die Liste nach so vielen Seiten
    dieses Aufrufs (erste Seiten der Sitzungsliste); `protokoll` (Liste) erhält je Seite eine Zeile (SEITEN_SPALTEN ohne
    datum, liste, modus); `ergebnis` (dict) erhält `ende`: „Listenende“, „Zeitfilter“ oder „Seitenzahl“."""
    naechste = start or _mit_parametern(url, modified_since=seit, limit=config.ABRUF_SEITENGROESSE)
    objekte = list(objekte or [])
    ids, gesehen, dieser_lauf = {o.get("id") for o in objekte}, set(), set()
    verschoben, zuletzt = 0, None   # Seiten ohne neue Kennungen in einer Fortsetzung; zuletzt gelesene Seite
    # Fortsetzung: älteste gelesene Vorlage (created); eine ungelesene ältere liegt hinter der verschobenen Zone
    grenze = min((t for t in map(_erstellt, objekte) if t is not None), default=None) if start else None
    verlassen = False
    gesamt = config.ABRUF_MAX_SEITEN_FAKTOR * config.ABRUF_MAX_SEITEN
    seit_zeit = _zeit(seit) if seit else None
    # Zustand des Zeitfilters vor der zuletzt gelesenen Seite (für die Fortsetzung, die diese Seite erneut liest)
    zf_vor = zeitfilter.zustand() if zeitfilter else None
    angepasst = False   # Folgeadresse dieser Seite um modified_since ergänzt oder berichtigt
    ende = "Listenende"
    while naechste:
        if hoechstens is not None and len(gesehen) >= hoechstens:
            ende = "Seitenzahl"
            break
        try:
            if naechste in gesehen:   # Schutz gegen zyklische Verweise
                raise abruf.Abbruch(f"links.next zeigt auf eine bereits gelesene Seite: {naechste}", "liste")
            if len(gesehen) >= config.ABRUF_MAX_SEITEN:   # Seiten dieses Laufs
                raise abruf.Abbruch(f"mehr als {config.ABRUF_MAX_SEITEN} Seiten in einem Lauf (RATSATLAS_MAX_SEITEN)",
                                    "liste")
            if seiten >= gesamt:   # Seiten insgesamt, auch aus früheren Läufen (Fortsetzung)
                raise abruf.Abbruch(f"mehr als {gesamt} Seiten insgesamt über Fortsetzungen hinweg "
                                    f"({config.ABRUF_MAX_SEITEN_FAKTOR} × RATSATLAS_MAX_SEITEN); die Liste erzeugt "
                                    "womöglich endlos neue Kennungen", "liste")
            gesehen.add(naechste)
            seite = abruf.get_json(naechste)
            weiter = _seite_pruefen(seite, naechste)
        except abruf.Abbruch as e:
            raise Teilabbruch(e, objekte, naechste, seiten, zuletzt, verlassen, zf_vor) from e
        seiten += 1
        daten = seite["data"]
        if seit_zeit is not None:   # inkrementell: wirkt modified_since auf dieser Seite?
            aelter = sum(1 for o in daten if (t := _zeit(o.get("modified"))) is not None and t < seit_zeit)
            if aelter:
                raise Teilabbruch(abruf.Abbruch(
                    f"modified_since unwirksam: {aelter} von {len(daten)} Objekten auf Seite {seiten} mit modified vor "
                    f"{seit}; inkrementeller Lauf abgebrochen, statt die ganze Liste zu laden (letzter gültiger Stand "
                    f"bleibt): {naechste}", "filter"), objekte, None, seiten, zuletzt, verlassen, zf_vor)
        kennungen = {o["id"] for o in daten}
        neu = [o for o in daten if o["id"] not in ids]
        if daten and not neu:
            if not start or kennungen <= dieser_lauf:   # dieselben Objekte mit neuem links.next (SessionNet-Sammelserver)
                grund = f"Seite ohne neue Kennungen, links.next läuft im Kreis: {naechste}"
            elif verschoben >= verschiebung:
                grund = (f"mehr als {verschiebung} Seiten ohne neue Kennungen in der Fortsetzung (erlaubte "
                         f"Seitenverschiebung): {naechste}")
            else:
                grund = None
                verschoben += 1   # Fortsetzung: die Seiten sind durch neue Vorlagen am Listenanfang verschoben
            if grund:
                raise Teilabbruch(abruf.Abbruch(grund, "liste"), objekte, None, seiten, zuletzt, verlassen, zf_vor)
        elif grenze is not None and any((t := _erstellt(o)) is not None and t < grenze for o in neu):
            verlassen = True
        dieser_lauf |= kennungen
        ids.update(o.get("id") for o in neu)
        objekte += neu
        vorher = zeitfilter.zustand() if zeitfilter else None
        fertig = zeitfilter.seite(daten, _seitennummer(naechste, seiten)) if zeitfilter else False
        if protokoll is not None:
            stichtag = zeitfilter.stichtag if zeitfilter else _stichtag()
            protokoll.append({"seite": _seitennummer(naechste, seiten), **_seitenwerte(daten, stichtag),
                              "folgeadresse_angepasst": "ja" if angepasst else "",
                              "zeitfilter": zeitfilter.status if zeitfilter else ""})
        zuletzt, zf_vor = naechste, vorher
        naechste, angepasst = _filter_in_folgeadresse(weiter, seit)
        if fertig and naechste:
            ende = "Zeitfilter"
            break
    if ergebnis is not None:
        ergebnis["ende"] = ende
    return objekte, seiten


def _seit(schluessel):
    """modified_since für den nächsten Lauf: letzter Stand minus Überlappung; None = vollständiger Abruf."""
    letzter = _zustand().get(schluessel)
    if not letzter or os.environ.get("RATSATLAS_VOLLABRUF") == "ja":
        return None
    t = _zeit(letzter)
    if t is None:   # vor der ersten Anfrage geprüft (_zustand_pruefen); hier nur zur Sicherheit
        raise ZustandUnlesbar(f"Zeitpunkt des letzten Abrufs von {schluessel} unlesbar: {letzter!r}")
    t = t.astimezone(timezone.utc) - UEBERLAPPUNG
    return t.strftime("%Y-%m-%dT%H:%M:%S%z").replace("+0000", "+00:00")


def _filter_wirksam(objekte, seit):
    """Prüft, ob der Server modified_since anwendet: keine Objekte mit älterem Änderungszeitpunkt. Ein unlesbares oder
    zonenloses `modified` (Angabe der Quelle) wird gezählt, nicht als Fehler behandelt."""
    if not seit:
        return ""
    grenze = datetime.fromisoformat(seit)
    aelter = unlesbar = 0
    for o in objekte:
        if o.get("modified") in (None, ""):
            continue
        t = _zeit(o["modified"])
        if t is None:
            unlesbar += 1
        elif t < grenze:
            aelter += 1
    ergebnis = "ja" if not aelter else f"nein ({aelter} ältere)"
    return ergebnis + (f"; {unlesbar} mit unlesbarem modified" if unlesbar else "")


def _zusammenfuehren(pfad, neu_objekte, voll, zeitraum=False):
    """Führt Objekte über die ID mit dem vorhandenen Stand zusammen; liefert (alle, neu, geändert, gelöscht, außerhalb).
    `zeitraum`: Vorlagen außerhalb des Zeitraums (`im_zeitraum`) werden verworfen und, falls sie im Stand stehen (etwa
    nach einer Änderung von `date`), daraus entfernt; gelöschte (`deleted`) bleiben als Vermerk."""
    alt = {}
    if pfad.exists():
        with open(pfad, encoding="utf-8") as f:
            alt = {o["id"]: o for o in map(json.loads, f) if o.get("id")}
    draussen = []
    if zeitraum:
        stichtag = _stichtag()
        draussen = [o for o in neu_objekte if not o.get("deleted") and not im_zeitraum(o, stichtag)]
        neu_objekte = [o for o in neu_objekte if o.get("deleted") or im_zeitraum(o, stichtag)]
    if voll:
        try:
            _guard(pfad.name, len(neu_objekte), len(alt))
        except RuntimeError as e:   # Vollabruf deutlich kleiner als der vorhandene Stand: Abbruch, keine Sperre
            raise abruf.Abbruch(str(e), "leer") from e
    neu = sum(1 for o in neu_objekte if o["id"] not in alt)
    geaendert = sum(1 for o in neu_objekte if o["id"] in alt and o != alt[o["id"]])
    geloescht = sum(1 for o in neu_objekte if o.get("deleted"))
    stand = {} if voll else dict(alt)
    for o in draussen:
        stand.pop(o.get("id"), None)
    stand.update({o["id"]: o for o in neu_objekte if o.get("id")})
    return list(stand.values()), neu, geaendert, geloescht, len(draussen)


def _statistik_sicher(zeile):
    """Wie _statistik, aber ein Schreibfehler (OSError) verdrängt nicht den eigentlichen Abbruch (der sonst nicht als
    Nacht mit möglicher Sperre gezählt würde): nur eine Warnung."""
    try:
        _statistik(zeile)
    except OSError as e:
        _warnung(f"Abrufstatistik nicht geschrieben ({e}); Zeile: {zeile}")


def _statistik(zeile):
    """Hängt eine Zeile an die Abrufstatistik an. Eine ältere Datei mit anderem Kopf (z. B. ohne `weiterleitungen` und
    `proxy`) wird zuvor auf STAT_SPALTEN umgestellt; fehlende Werte bleiben leer."""
    config.EXPORT.mkdir(parents=True, exist_ok=True)
    zeilen, modus = [zeile], "a"
    if not config.ABRUFSTATISTIK.exists():
        modus = "w"
    else:
        with open(config.ABRUFSTATISTIK, encoding="utf-8", newline="") as f:
            r = csv.DictReader(f, delimiter="\t")
            if r.fieldnames != STAT_SPALTEN:   # ältere Datei: neu schreiben, Werte nach Spaltennamen übernehmen
                zeilen, modus = [*r, zeile], "w"
    with open(config.ABRUFSTATISTIK, modus, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, STAT_SPALTEN, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        if modus == "w":
            w.writeheader()
        w.writerows(zeilen)


def _seitenprotokoll(zeilen, kopf):
    """Hängt die Zeilen einer Liste an das Seitenprotokoll an (config.ABRUFSTATISTIK_SEITEN); ein Schreibfehler
    (OSError) verdrängt keinen Abbruch, nur eine Warnung."""
    if not zeilen:
        return
    try:
        config.EXPORT.mkdir(parents=True, exist_ok=True)
        pfad = config.ABRUFSTATISTIK_SEITEN
        neu = not pfad.exists()
        if not neu:
            with open(pfad, encoding="utf-8", newline="") as f:
                neu = next(csv.reader(f, delimiter="\t"), None) != SEITEN_SPALTEN
            if neu:   # anderer Kopf: alte Datei beiseitelegen
                os.replace(pfad, pfad.with_name(pfad.name + ".alt"))
        with open(pfad, "w" if neu else "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, SEITEN_SPALTEN, delimiter="\t", lineterminator="\n", extrasaction="ignore")
            if neu:
                w.writeheader()
            w.writerows({**kopf, **z} for z in zeilen)
    except OSError as e:
        _warnung(f"Seitenprotokoll nicht geschrieben ({e})")


def _differenz(zeile, vorher):
    """Trägt die Zähler aus abruf.statistik() seit `vorher` in die Zeile ein."""
    nachher = abruf.statistik()
    zeile.update({k: (round(nachher[k] - vorher[k], 1) if k == "sekunden" else nachher[k] - vorher[k])
                  for k in STAT_ZAEHLER})


def _teil(pfad):
    return pfad.with_name(pfad.name.split(".")[0] + ".teil.jsonl")


def _zeitfilter_lesbar(wert):
    """Zustand des Zeitfilters in einer Fortsetzung: Objekt mit `grenzseite` (None oder Zahl ≥ 1) und `ohne_treffer`
    (Zahl ≥ 0)."""
    if not isinstance(wert, dict) or set(wert) != {"grenzseite", "ohne_treffer"}:
        return False
    g, n = wert["grenzseite"], wert["ohne_treffer"]
    zahl = lambda x, m: isinstance(x, int) and not isinstance(x, bool) and x >= m   # noqa: E731
    return (g is None or zahl(g, 1)) and zahl(n, 0)


def _fortsetzung(schluessel, pfad):
    """Gespeicherte Fortsetzung eines Vollabrufs und der gelesene Teil: (Fortsetzung, Objekte, Meldung). Ist sie
    unlesbar (Form, Zeitpunkt, fehlende oder unlesbare Teildatei), wird sie verworfen: (None, None, Meldung)."""
    fort = _zustand().get(f"{schluessel}_fortsetzung")
    if fort is None:
        return None, None, ""
    teil, grund, bisher = _teil(pfad), "", []
    seiten = fort.get("seiten", 0) if isinstance(fort, dict) else None
    if not isinstance(fort, dict):
        grund = "kein Objekt"
    elif not isinstance(fort.get("naechste"), str) or not fort["naechste"]:
        grund = "Folgeadresse fehlt"
    elif isinstance(seiten, bool) or not isinstance(seiten, int) or seiten < 0:
        grund = f"Seitenzahl unlesbar ({seiten!r})"
    elif _zeit(fort.get("start")) is None:
        grund = f"Startzeitpunkt unlesbar ({fort.get('start')!r})"
    elif seiten and not teil.exists():
        grund = f"Teildatei {teil.name} fehlt"
    elif "zeitfilter" in fort and not _zeitfilter_lesbar(fort["zeitfilter"]):
        grund = f"Zustand des Zeitfilters unlesbar ({fort['zeitfilter']!r})"
    elif teil.exists():
        try:
            bisher = [json.loads(z) for z in teil.read_text(encoding="utf-8").splitlines() if z.strip()]
            if not all(isinstance(o, dict) and isinstance(o.get("id"), str) for o in bisher):
                grund = f"Teildatei {teil.name} enthält Zeilen ohne Kennung"
        except (ValueError, RecursionError) as e:
            grund = f"Teildatei {teil.name} unlesbar ({e})"
    if not grund:
        return fort, bisher, ""
    meldung = f"Fortsetzung von {schluessel} verworfen ({grund}); der Vollabruf beginnt von vorn"
    _warnung(meldung)
    _zustand_setzen(f"{schluessel}_fortsetzung", None)
    teil.unlink(missing_ok=True)
    return None, None, meldung


def _abruf_liste(name, url, pfad, schluessel, zeitraum=False, inkrementell=True):
    """Abruf einer Liste mit Statistik; schreibt die zusammengeführten Objekte als JSONL. Ein abgebrochener Vollabruf wird
    beim nächsten Lauf an der gelesenen Stelle fortgesetzt. `inkrementell`: nach dem ersten Lauf mit modified_since
    (nur Vorlagen; Organisationen immer vollständig). `zeitraum` (Vorlagen): Vollabruf mit Zeitfilter, Vorlagen
    außerhalb des Zeitraums verworfen (auch inkrementell), Seitenprotokoll."""
    vorher = abruf.statistik()
    start = datetime.now(timezone.utc)
    fort, bisher, verworfen = _fortsetzung(schluessel, pfad)
    seit = None if fort or not inkrementell else _seit(schluessel)
    zeile = {"datum": _now(), "liste": name, "modus": "voll, fortgesetzt" if fort else "inkrementell" if seit else
             "voll, Fortsetzung verworfen" if verworfen else "voll"}
    zf = Zeitfilter(**((fort or {}).get("zeitfilter") or {})) if zeitraum and not seit else None
    protokoll = [] if zeitraum else None
    info = {}
    try:
        if fort:
            start = _zeit(fort["start"])
            objekte, seiten = liste(url, start=fort["naechste"], objekte=bisher, seiten=fort.get("seiten", 0),
                                    verschiebung=verschiebung_erlaubt(fort.get("gespeichert")), zeitfilter=zf,
                                    protokoll=protokoll, ergebnis=info)
        else:
            objekte, seiten = liste(url, seit, zeitfilter=zf, protokoll=protokoll, ergebnis=info)
        alle, neu, geaendert, geloescht, draussen = _zusammenfuehren(pfad, objekte, voll=not seit, zeitraum=zeitraum)
        _write(pfad, "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in alle))
        _zustand_setzen(schluessel, start.isoformat(timespec="seconds"))
        _zustand_setzen(f"{schluessel}_fortsetzung", None)
        _teil(pfad).unlink(missing_ok=True)
        zeile.update(seiten=seiten, objekte=len(alle), neu=neu, geaendert=geaendert, geloescht=geloescht,
                     filter_wirksam=_filter_wirksam(objekte, seit), ergebnis="ok",
                     ausserhalb_zeitraum=draussen if zeitraum else "", ende=info.get("ende", ""))
        return alle
    except Teilabbruch as e:
        # Vollabruf: gelesenen Teil sichern und morgen eine Seite zurück fortsetzen (fängt bis zu einer Seite
        # Löschungen ab); eine veraltete Folgeseite (HTTP 4xx gleich zu Beginn der Fortsetzung) oder ein Abbruch aus
        # OHNE_FORTSETZUNG (Schleife, Weiterleitung, Proxy, Adresse) verwirft die Fortsetzung, dann beginnt der
        # nächste Lauf von vorn
        veraltet = fort and e.art == "http" and e.seiten == fort.get("seiten", 0)
        verwerfen = veraltet or e.art in OHNE_FORTSETZUNG
        if not seit and e.naechste and e.seiten and not verwerfen:
            config.RAW.mkdir(parents=True, exist_ok=True)
            _write(_teil(pfad), "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in e.objekte))
            # `gespeichert` bleibt, solange eine Fortsetzung die verschobene Zone nicht verlassen hat (keine ungelesene
            # Vorlage, älter als die älteste gelesene): Die Verschiebung seit der ersten Speicherung besteht weiter;
            # ein künftiger Wert gilt als jetzt
            jetzt = abruf.uhr()
            alt = _zeit(fort.get("gespeichert")) if fort else None
            gespeichert = fort["gespeichert"] if alt is not None and alt <= jetzt and not e.verlassen else (
                jetzt.isoformat(timespec="seconds"))
            fortsetzung = {"naechste": e.zuletzt or e.naechste, "seiten": e.seiten,
                           "start": start.isoformat(timespec="seconds"), "gespeichert": gespeichert}
            if zf is not None and e.zeitfilter is not None:   # Zustand vor der Seite, mit der die Fortsetzung beginnt
                fortsetzung["zeitfilter"] = e.zeitfilter
            _zustand_setzen(f"{schluessel}_fortsetzung", fortsetzung)
            zeile["ergebnis"] = f"unterbrochen nach {e.seiten} Seiten, Fortsetzung im nächsten Lauf: {e}"[:300]
        else:
            if verwerfen:
                _zustand_setzen(f"{schluessel}_fortsetzung", None)
                _teil(pfad).unlink(missing_ok=True)
            zeile["ergebnis"] = f"abbruch: {e}"[:300]
        zeile.update(seiten=e.seiten, objekte=len(e.objekte))
        raise
    except abruf.Abbruch as e:
        zeile["ergebnis"] = f"abbruch: {e}"[:300]
        raise
    except Exception as e:
        zeile["ergebnis"] = f"programmfehler: {type(e).__name__}: {e}"[:300]
        raise
    finally:
        if zf is not None:
            zeile["grenzseite"] = zf.grenzseite if zf.grenzseite is not None else "nicht erreicht"
        _differenz(zeile, vorher)
        _statistik_sicher(zeile)
        if protokoll:
            _seitenprotokoll(protokoll, {"datum": zeile["datum"], "liste": name, "modus": zeile["modus"]})


def _abruf_body():
    """Abruf des Bodys mit eigener Zeile `body` in der Abrufstatistik. Der Body muss die Listen `paper`, `meeting` und
    `organization` als Adressen nennen, sonst Abbruch der Art `unlesbar`."""
    vorher = abruf.statistik()
    zeile = {"datum": _now(), "liste": "body"}
    try:
        body = abruf.get_json(config.OPARL_BODY)
        fehlt = [f for f in ("paper", "meeting", "organization") if not isinstance(body.get(f), str) or not body[f]]
        if fehlt:
            raise abruf.Abbruch(f"unerwartete Antwortform (Body ohne Liste {', '.join(fehlt)}): {config.OPARL_BODY}",
                                "unlesbar")
        zeile.update(objekte=1, ergebnis="ok")
        return body
    except abruf.Abbruch as e:
        zeile["ergebnis"] = f"abbruch: {e}"[:300]
        raise
    except Exception as e:
        zeile["ergebnis"] = f"programmfehler: {type(e).__name__}: {e}"[:300]
        raise
    finally:
        _differenz(zeile, vorher)
        _statistik_sicher(zeile)


def fetch_organizations(body):
    """Organisationen immer vollständig (Wuppertal: 240 auf 3 Seiten, Stufe 4; modified_since für diese Liste nicht
    gemessen). Abweichung von Köln (dort inkrementell)."""
    pfad = config.RAW / "organizations.jsonl"
    orgs = [o for o in _abruf_liste("organizations", body["organization"], pfad, "organizations", inkrementell=False)
            if not o.get("deleted")]
    _write(config.ORGANIZATIONS, json.dumps(orgs, ensure_ascii=False))
    vb = [o for o in orgs if o.get("organizationType") == "Verwaltungsbereich"]
    _write(config.VERWALTUNGSBEREICHE, json.dumps(vb, ensure_ascii=False))
    _stamp("organizations")
    print(f"{len(orgs)} Organisationen, davon {len(vb)} Verwaltungsbereiche")
    return orgs


def _einladung(m):
    inv = m.get("invitation")
    return inv.get("accessUrl") if isinstance(inv, dict) else None


def _kennung(wert):
    """Verweis als Schlüssel: nur Text (eine Liste oder ein Objekt an dieser Stelle ergibt keinen Treffer)."""
    return wert if isinstance(wert, str) else None


def sitzungsverweise(papers):
    """Kennungen der Sitzungen, auf die Beratungen der Vorlagen verweisen (`consultation.meeting`), ohne Dubletten in
    der Reihenfolge des ersten Vorkommens; gelöschte Vorlagen zählen nicht."""
    gesehen = {}
    for p in papers:
        if p.get("deleted"):
            continue
        for c in p.get("consultation") or []:
            k = _kennung(c.get("meeting")) if isinstance(c, dict) else None
            if k:
                gesehen.setdefault(k, None)
    return list(gesehen)


def _sitzung_neu_holen(m, jetzt):
    """Muss eine Sitzung aus dem Cache erneut geholt werden? Ja, wenn sie fehlt, ihr `start` unlesbar ist, in der
    Zukunft oder höchstens config.SITZUNG_NACHLAUF_TAGE zurück liegt (Ergebnisse der TOPs kommen nach der Sitzung);
    gelöschte nicht."""
    if m is None:
        return True
    if m.get("deleted"):
        return False
    t = _zeit(m.get("start"))
    return t is None or t >= jetzt - timedelta(days=config.SITZUNG_NACHLAUF_TAGE)


def _host(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _jsonl_lesen(pfad):
    """Objekte einer JSONL-Datei nach Kennung; fehlende Datei: leer."""
    if not pfad.exists():
        return {}
    with open(pfad, encoding="utf-8") as f:
        return {o["id"]: o for o in map(json.loads, f) if isinstance(o, dict) and isinstance(o.get("id"), str)}


def fetch_meetings(body, papers):
    """Sitzungen (Entscheidung 13.11.2026), nicht die ganze Liste:
    1. die ersten config.ABRUF_SITZUNGSSEITEN Seiten der Sitzungsliste (künftige Termine; Stufe 4),
    2. die von Beratungen der Vorlagen verwiesenen Sitzungen (`sitzungsverweise`) einzeln über ihre Kennung, ohne
       Dubletten und ohne die schon aus Schritt 1 geholten; aus dem Cache `meetings_roh.jsonl` nur, was fehlt oder noch
       neu zu holen ist (`_sitzung_neu_holen`). Nur Kennungen auf dem Host des Bodys; andere werden gezählt, nicht
       angefragt. HTTP 404/410 einer einzelnen Sitzung wird vermerkt (Zustand `sitzungen_fehlend`, erneut nach
       config.SITZUNG_FEHLT_TAGE Tagen) und übersprungen; config.SITZUNG_FEHLT_IN_FOLGE in Folge beenden den Lauf
       (Art `http`, kein Sperrverdacht: Einzeladresse prüfen). HTTP 401/403 einer einzelnen Sitzung (etwa nicht
       öffentlich) wird ebenso vermerkt (`sitzungen_verweigert`, erneut nach config.SITZUNG_FEHLT_TAGE Tagen, dann am
       Ende der Reihenfolge); erst config.SITZUNG_ABGEWIESEN_IN_FOLGE neu abgewiesene in Folge beenden den Lauf als
       mögliche Sperre (wie die Messstufen: zwei 401 in Folge), ihre Sitzungen werden im nächsten Lauf erneut
       angefragt. Eine schon zuvor abgewiesene Sitzung zählt dabei nicht mit. Jeder andere Abbruch beendet den Lauf wie
       sonst.
    3. künftige Sitzungen im Cache, die nur aus den ersten Seiten der Liste stammen, auf die keine Vorlage verweist und
       die in diesem Lauf nicht mehr dort standen: einzeln erneuert (Absagen, Verschiebungen), die nächsten zuerst,
       höchstens config.SITZUNG_KUENFTIGE_HOECHSTENS je Lauf; HTTP 404/410 entfernt sie aus dem Cache.
    Der Cache wird auch bei einem Abbruch geschrieben: Die nächste Nacht setzt dort fort (Vollabruf über mehrere Nächte).
    `meetings.json` (Bonner Kurzformat) und die Beratungen entstehen erst nach einem vollständigen Schritt."""
    vorher = abruf.statistik()
    pfad = config.RAW / "meetings_roh.jsonl"
    zeile = {"datum": _now(), "liste": "meetings"}
    cache = _jsonl_lesen(pfad)
    zeile["modus"] = (f"erste {config.ABRUF_SITZUNGSSEITEN} Seiten, verwiesene einzeln" + ("" if cache else ", Cache leer"))
    jetzt = abruf.uhr()
    zustand = _zustand()
    fehlend = zustand.get("sitzungen_fehlend")
    fehlend = {k: v for k, v in fehlend.items() if isinstance(k, str) and _zeit(v) is not None} if isinstance(
        fehlend, dict) else {}
    # abgewiesene Sitzungen (HTTP 401/403): Kennung → {zuletzt, serie}; serie = gehörte zu einer Serie, die den Lauf
    # beendete (im nächsten Lauf erneut, am Ende)
    verweigert = zustand.get("sitzungen_verweigert")
    verweigert = {k: v for k, v in verweigert.items() if isinstance(k, str) and isinstance(v, dict)
                  and _zeit(v.get("zuletzt")) is not None} if isinstance(verweigert, dict) else {}
    vorher_ids = set(cache)
    einzeln = fremd = luecken = abgewiesen = seiten = erneuert = 0
    info = {}
    try:
        geholt = set()
        if config.ABRUF_SITZUNGSSEITEN > 0:
            try:
                aus_liste, seiten = liste(body["meeting"], hoechstens=config.ABRUF_SITZUNGSSEITEN, ergebnis=info)
            except Teilabbruch as e:
                seiten = e.seiten
                raise
            for m in aus_liste:
                cache[m["id"]] = m
                geholt.add(m["id"])
        host = _host(config.OPARL_BODY)
        verweise = sitzungsverweise(papers)
        verwiesen = set(verweise)
        frist = timedelta(days=config.SITZUNG_FEHLT_TAGE)
        neu, wiederholen = [], []
        for k in verweise:
            if k in geholt or not _sitzung_neu_holen(cache.get(k), jetzt):
                continue
            seit_fehlt = _zeit(fehlend.get(k))
            if seit_fehlt is not None and jetzt - seit_fehlt < frist:
                continue
            v = verweigert.get(k)
            if v is not None:
                if not v.get("serie") and jetzt - _zeit(v["zuletzt"]) < frist:
                    continue
                wiederholen.append(k)   # abgewiesene ans Ende: eine dauerhaft abgewiesene blockiert keinen Lauf
                continue
            neu.append(k)
        # künftige Sitzungen nur aus den ersten Seiten der Liste (nicht verwiesen, diesmal nicht dort): einzeln erneuert
        # (Absage, Verschiebung), die nächsten zuerst, höchstens config.SITZUNG_KUENFTIGE_HOECHSTENS
        kuenftige = sorted((m for k, m in cache.items() if k not in geholt and k not in verwiesen
                            and not m.get("deleted") and (t := _zeit(m.get("start"))) is not None and t >= jetzt
                            and (k not in verweigert or jetzt - _zeit(verweigert[k]["zuletzt"]) >= frist)),
                           key=lambda m: _zeit(m.get("start")))
        kuenftige = [m["id"] for m in kuenftige[:max(0, config.SITZUNG_KUENFTIGE_HOECHSTENS)]]
        fehlt_in_folge = 0
        serie = []   # neu abgewiesene Sitzungen in Folge
        for k in neu + wiederholen + kuenftige:
            if _host(k) != host:
                fremd += 1
                continue
            try:
                m = abruf.get_json(k)
            except abruf.Abbruch as e:
                if e.art == "http" and e.code in (404, 410):
                    luecken += 1
                    fehlt_in_folge += 1
                    serie = []
                    if k in verwiesen:
                        fehlend[k] = jetzt.isoformat(timespec="seconds")
                    else:   # künftige Sitzung aus der Liste, nicht mehr in der Quelle
                        cache.pop(k, None)
                    if fehlt_in_folge >= config.SITZUNG_FEHLT_IN_FOLGE:
                        raise abruf.Abbruch(f"{fehlt_in_folge} Sitzungen in Folge mit HTTP 404/410: Einzeladresse der "
                                            f"Sitzungen prüfen (zuletzt {k})", "http", code=e.code) from e
                    continue
                if e.art == "http" and e.code in (401, 403):
                    abgewiesen += 1
                    fehlt_in_folge = 0
                    if k not in verweigert:
                        serie.append(k)
                    verweigert[k] = {"zuletzt": jetzt.isoformat(timespec="seconds"), "serie": False}
                    if len(serie) >= config.SITZUNG_ABGEWIESEN_IN_FOLGE:
                        for s_k in serie:
                            verweigert[s_k]["serie"] = True
                        raise abruf.Abbruch(f"{len(serie)} Sitzungen in Folge abgewiesen (zuletzt HTTP {e.code}), "
                                            f"mögliche Sperre: {k}", "http", code=e.code) from e
                    continue
                raise
            fehlt_in_folge = 0
            serie = []
            einzeln += 1
            if k in kuenftige:
                erneuert += 1
            if not isinstance(m.get("id"), str) or not m["id"]:
                raise abruf.Abbruch(f"unerwartete Antwortform (Sitzung ohne Kennung): {k}", "unlesbar")
            cache[m["id"]] = m
            geholt.add(m["id"])
            fehlend.pop(k, None)
            verweigert.pop(k, None)
        meetings = [m for m in cache.values() if not m.get("deleted")]
        keep = ("id", "name", "meetingState", "cancelled", "start", "end", "organization", "web")
        _write(config.MEETINGS, json.dumps(
            [{**{k: m.get(k) for k in keep}, "invitation": _einladung(m),
              "agenda_items": len(m.get("agendaItem") or [])} for m in meetings], ensure_ascii=False))
        terms = body.get("legislativeTerm") or []
        terms = [t for t in terms if isinstance(t, dict)]
        _write(config.LEGISLATIVE_TERMS, json.dumps(terms, ensure_ascii=False))
        _zustand_setzen("meetings", jetzt.isoformat(timespec="seconds"))
        _stamp("meetings")
        zeile["ergebnis"] = "ok" + (
            f"; {luecken} {'Sitzung' if luecken == 1 else 'Sitzungen'} mit HTTP 404/410 übersprungen" if luecken
            else "") + (
            f"; {abgewiesen} {'Sitzung' if abgewiesen == 1 else 'Sitzungen'} mit HTTP 401/403 übersprungen"
            if abgewiesen else "") + (
            f"; {erneuert} künftige {'Sitzung' if erneuert == 1 else 'Sitzungen'} aus der Liste erneuert"
            if erneuert else "") + (f"; {fremd} {'Verweis' if fremd == 1 else 'Verweise'} auf einen anderen Host nicht angefragt"
                        if fremd else "")
        print(f"{len(meetings)} Sitzungen ({einzeln} einzeln, {seiten} Seiten der Liste), {len(terms)} Wahlperioden")
        return meetings
    except abruf.Abbruch as e:
        zeile["ergebnis"] = f"abbruch: {e}"[:300]
        raise
    except Exception as e:
        zeile["ergebnis"] = f"programmfehler: {type(e).__name__}: {e}"[:300]
        raise
    finally:
        # auch nach einem Abbruch: Geholtes sichern, damit die nächste Nacht dort fortsetzt
        try:
            config.RAW.mkdir(parents=True, exist_ok=True)
            _write(pfad, "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in cache.values()))
            _zustand_setzen("sitzungen_fehlend", fehlend or None)
            _zustand_setzen("sitzungen_verweigert", verweigert or None)
        except Exception as f:   # Schreib- oder Zustandsfehler verdrängen den eigentlichen Abbruch nicht
            _warnung(f"Cache der Sitzungen nicht geschrieben ({type(f).__name__}: {f})")
        zeile.update(seiten=seiten, objekte=len(cache), neu=len(set(cache) - vorher_ids), einzeln=einzeln,
                     ende=info.get("ende", ""))
        _differenz(zeile, vorher)
        _statistik_sicher(zeile)


def fetch_papers(body):
    """Vorlagen ab config.DATEN_AB: Vollabruf mit Zeitfilter, danach inkrementell mit kodiertem modified_since."""
    papers = _abruf_liste("papers", body["paper"], config.PAPERS, "papers", zeitraum=True)
    _stamp("papers")
    print(f"{len(papers)} Vorlagen → {config.PAPERS}")
    return papers


def beratungen(papers, meetings):
    """Beratung → Sitzung und TOP im Format, das build.py aus OParl-Lite kennt. Fehlt in der Beratung die
    Organisation, wird sie aus der Sitzung übernommen und als abgeleitet markiert (`_organization_quelle`)."""
    sitzung = {m["id"]: m for m in meetings}
    top = {}
    for m in meetings:
        for t in m.get("agendaItem") or []:
            if isinstance(t, dict) and _kennung(t.get("id")):
                top[t["id"]] = (t, m)
    zeilen, ohne_sitzung, ergaenzt = [], 0, 0
    for p in papers:
        for c in p.get("consultation") or []:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            t, m_top = top.get(_kennung(c.get("agendaItem")), (None, None))
            m = sitzung.get(_kennung(c.get("meeting"))) or m_top
            if not c.get("organization") and m and m.get("organization"):
                c["organization"] = list(m["organization"]) if isinstance(m["organization"], list) else [m["organization"]]
                c["_organization_quelle"] = "sitzung"
                ergaenzt += 1
            if not m and not t:
                ohne_sitzung += 1
                continue
            zeilen.append({
                "uri": c["id"],
                "meeting": {"uri": m["id"], "name": m.get("name"), "startDate": m.get("start"),
                            "cancelled": bool(m.get("cancelled"))} if m else None,
                "agendaItem": {"uri": t["id"], "number": t.get("number"), "name": t.get("name"),
                               "result": t.get("result"), "public": t.get("public")} if t else None,
            })
    if len(zeilen) < MIN_ANTEIL * _jsonl_count(config.BERATUNGEN):   # unvollständig: Abbruch, keine Sperre
        raise abruf.Abbruch(f"Beratungen: nur {len(zeilen)} statt bisher {_jsonl_count(config.BERATUNGEN)}", "leer")
    _write(config.BERATUNGEN, "".join(json.dumps(z, ensure_ascii=False) + "\n" for z in zeilen))
    # Ergänzte Organisationen in papers.jsonl übernehmen, damit build.py sie liest
    _write(config.PAPERS, "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in papers))
    _stamp("consultations_lite")
    print(f"{len(zeilen)} Beratungen mit Sitzung oder TOP, {ohne_sitzung} ohne, {ergaenzt} Gremien aus der Sitzung")


def _einstellungen_pruefen():
    """Sicherheitsabstand des Zeitfilters mindestens 1 Seite (sonst endete der Vollabruf an der Grenzseite, und Vorlagen
    mit `date` ab 2020 und älterem `created` fehlten, Stufe 3), Seiten der Sitzungsliste nicht negativ, Stichtag lesbar.
    Sonst ValueError vor der ersten Anfrage."""
    if isinstance(config.ABRUF_SICHERHEITSABSTAND, bool) or not isinstance(config.ABRUF_SICHERHEITSABSTAND, int) or (
            config.ABRUF_SICHERHEITSABSTAND < 1):
        raise ValueError(f"RATSATLAS_SICHERHEITSABSTAND={config.ABRUF_SICHERHEITSABSTAND!r}: mindestens 1 Seite "
                         "(Stufe 3: Vorlagen mit date ab 2020 auch auf der Grenzseite); keine Anfrage gesendet")
    if not isinstance(config.ABRUF_SITZUNGSSEITEN, int) or config.ABRUF_SITZUNGSSEITEN < 0:
        raise ValueError(f"RATSATLAS_SITZUNGSSEITEN={config.ABRUF_SITZUNGSSEITEN!r}: 0 oder mehr; keine Anfrage gesendet")
    _stichtag()


def fetch_all():
    """Vollständiger bzw. inkrementeller Lauf. Ein Abbruch (abruf.Abbruch) hält den letzten gültigen Stand und vermerkt
    den Fehler; Abbrüche nach `moegliche_sperre` zählen als Nacht mit möglicher Sperre, Abbrüche der Art `liste` oder
    `adresse` als Nacht mit fehlerhafter Liste, das Ende des Zeitfensters nur als Hinweis. Alles andere (auch ein
    RuntimeError ohne Art) ist ein Programm- oder Einstellungsfehler: vermerkt, laut mit Traceback, kein Sperrverdacht.
    Nach jedem Abbruch außer dem Ende des Zeitfensters folgt in derselben Nacht kein weiterer Lauf (`letzter_abbruch`)."""
    config.RAW.mkdir(parents=True, exist_ok=True)
    _einstellungen_pruefen()   # Einstellungsfehler: laut, vor jeder Anfrage
    # Sperre und Zeitfenster sind kein Ausfall: der Lauf wird übersprungen, ohne den Stand als fehlgeschlagen zu markieren
    lokal = abruf.lokal(config.OPARL_BODY)
    grund = (f"Abruf gesperrt: Die Stadt {config.STADT_NAME} ist noch nicht informiert (RATSATLAS_STADT_INFORMIERT)"
             if not abruf.freigegeben(config.OPARL_BODY) else
             f"Zeitfenster {config.ABRUF_ZEITFENSTER!r} für Server der Stadt nicht zulässig (leer oder weiter als "
             f"23–1 Uhr)" if not lokal and not abruf.fenster_zulaessig(config.OPARL_BODY) else
             f"außerhalb des Zeitfensters {config.ABRUF_ZEITFENSTER} Uhr" if not lokal and not abruf.im_zeitfenster()
             else None)
    if not grund and not lokal:
        # Endpunkte nur bei der Stadt (oder Testadressen): eine aus einem anderen Projekt übernommene Variable
        # RATSATLAS_OPARL_BODY/-SYSTEM ist ein Einstellungsfehler, laut vor der ersten Anfrage (Wuppertaler Abweichung)
        fremd = [u for u in (config.OPARL_BODY, config.OPARL_SYSTEM) if not abruf.abrufziel_erlaubt(u)]
        if fremd:
            meldung = (f"Endpunkt außerhalb der Stadt {config.STADT_NAME} (RATSATLAS_OPARL_BODY/RATSATLAS_OPARL_SYSTEM "
                       f"prüfen): {', '.join(fremd)}; keine Anfrage")
            _stand_setzen(abruf_fehler={"zeit": _now(), "meldung": meldung[:300]})
            raise ValueError(meldung)
        try:   # ein anderer Abrufprozess (zweiter Lauf, Messstufe) läuft: übersprungen, kein Fehler, kein Zustand
            abruf.sperre_halten()
        except abruf.Abbruch as e:
            grund = str(e)
    zustand = {}
    if not grund:
        try:
            zustand = _zustand_pruefen()
        except ZustandUnlesbar as e:   # keine Anfrage; laut, bis jemand die Datei prüft (jeder Lauf bricht so ab)
            _stand_setzen(abruf_fehler={"zeit": _now(), "meldung": str(e)[:300]})
            raise
        grund = _pause_grund(zustand, lokal)
    if grund:
        _stand_setzen(abruf_uebersprungen={"zeit": _now(), "grund": grund})
        print(f"Abruf übersprungen ({grund}); letzter Stand bleibt.")
        return
    try:
        body = _abruf_body()
        fetch_organizations(body)
        papers = fetch_papers(body)
        meetings = fetch_meetings(body, papers)
        beratungen(papers, meetings)
        _stamp("abruf_ok")
        _zustand_aendern(sperre_verdacht=None, listenfehler=None, tlsfehler=None, letzter_abbruch=None, nicht_vor=None)
        # Meldungen früherer Läufe gelten nicht mehr (die Seite zeigte sonst dauerhaft „fehlgeschlagen“)
        _stand_entfernen("abruf_fehler", "abruf_hinweis", "abruf_uebersprungen")
    except abruf.Abbruch as e:
        _abbruch_vermerken(e, zustand)
    except Exception as e:
        # Programm- oder Einstellungsfehler (auch eine unerwartete Form tief in einem Objekt, ein RuntimeError ohne Art
        # wie RecursionError oder ZustandUnlesbar mitten im Lauf): kein Sperrverdacht; vermerken und mit Traceback
        # abbrechen, damit der Fehler im Workflow sichtbar wird. In derselben Nacht kein weiterer Lauf.
        try:
            _zustand_setzen("letzter_abbruch", {"zuletzt": abruf.uhr().isoformat(timespec="seconds"),
                                                "art": "programmfehler", "code": None,
                                                "meldung": f"{type(e).__name__}: {e}"[:300]})
        except Exception as f:   # z. B. Zustand unlesbar: den eigentlichen Fehler nicht verdrängen
            _warnung(f"Abbruch nicht im Zustand vermerkt ({type(f).__name__}: {f})")
        _stand_setzen(abruf_fehler={"zeit": _now(), "meldung": f"Programmfehler ({type(e).__name__}: {e})"[:300]})
        raise


def _naechte_zaehlen(zustand, schluessel, jetzt, eintrag, neu):
    """Nächte zählen, nicht Läufe (`listenfehler`, `tlsfehler`): Ein weiterer Abbruch innerhalb von 12 Stunden zählt
    nicht noch einmal. Setzt beim Zählen neu[schluessel]; liefert die Zahl der Nächte."""
    bisher = zustand.get(schluessel) or {}
    zuletzt = _zeit(bisher.get("zuletzt"))
    if zuletzt is not None and jetzt - zuletzt < SPERRE_GLEICHE_NACHT:
        return bisher.get("naechte", 1)
    neu[schluessel] = {"naechte": bisher.get("naechte", 0) + 1, **eintrag}
    return neu[schluessel]["naechte"]


def _abbruch_vermerken(e, zustand):
    """Abbruch vermerken: zuerst den Zustand (letzter Abbruch für die 12-Stunden-Regel, Nacht mit möglicher Sperre nach
    `moegliche_sperre`, Retry-After über die Nacht hinaus, Nacht mit fehlerhafter Liste nach LISTENFEHLER), dann
    STAND.json. Das Ende des Zeitfensters (etwa bei einem Vollabruf über mehrere Nächte) ist kein Fehler: nur ein
    neutraler Hinweis, keine 12-Stunden-Regel."""
    jetzt = abruf.uhr()
    zeit = jetzt.isoformat(timespec="seconds")
    art = getattr(e, "art", "")
    if art == "parallel":   # ein anderer Abrufprozess hält die Sperre: keine Anfrage gesendet, kein Fehler dieses Laufs
        _stand_setzen(abruf_uebersprungen={"zeit": _now(), "grund": str(e)[:300]})
        print(f"Abruf übersprungen ({e}); letzter Stand bleibt.")
        return
    if art == "zeitfenster":
        hinweis = f"Das Zeitfenster endete während des Abrufs; Fortsetzung in der nächsten Nacht. {e}"[:400]
        _stand_entfernen("abruf_fehler")
        _stand_setzen(abruf_hinweis={"zeit": _now(), "meldung": hinweis})
        print(f"Abruf unterbrochen (Ende des Zeitfensters), Fortsetzung in der nächsten Nacht: {e}")
        return
    neu = {"letzter_abbruch": {"zuletzt": zeit, "art": art, "code": getattr(e, "code", None),
                               "meldung": str(e)[:300]}}
    eintrag = {"zuletzt": zeit, "art": art, "meldung": str(e)[:300]}
    if art == "tls":   # vermutlich Einstellung der Ausführungsumgebung, keine Sperrnacht: laut, damit sie behoben wird
        naechte = _naechte_zaehlen(zustand, "tlsfehler", jetzt, eintrag, neu)
        _warnung(f"Zertifikatsprüfung fehlgeschlagen ({naechte}. Nacht ohne vollständigen Lauf; nach {TLS_NAECHTE} "
                 f"Nächten {TLS_PAUSE.days} Tage Pause); vermutlich eine Einstellung der Ausführungsumgebung (CA eines "
                 f"Proxys), Zertifikat der Gegenseite oder Sperrseite nicht ausgeschlossen; in derselben Nacht kein "
                 f"weiterer Lauf. {e}"[:500])
    if moegliche_sperre(e):
        verdacht = zustand.get("sperre_verdacht") or {}
        neu["sperre_verdacht"] = {"naechte": verdacht.get("naechte", 0) + 1, "zuletzt": zeit, "art": art,
                                  "code": getattr(e, "code", None), "meldung": str(e)[:300]}
    nicht_vor = getattr(e, "nicht_vor", None)
    if nicht_vor is not None:   # Retry-After über die Nacht hinaus; ein späterer gespeicherter Zeitpunkt bleibt
        alt = _zeit(zustand.get("nicht_vor"))
        if alt is None or nicht_vor > alt:
            neu["nicht_vor"] = nicht_vor.isoformat(timespec="seconds")
    hinweis = None
    if art == "filter":   # modified_since unwirksam: laut, kein Sperrverdacht; jede Nacht nur bis zur ersten Seite
        hinweis = (f"Inkrementeller Abruf abgebrochen: modified_since wirkt nicht (Antwort mit älteren Vorlagen). Der "
                   f"letzte gültige Stand bleibt; ein Vollabruf nur bewusst (RATSATLAS_VOLLABRUF=ja), nach Prüfung der "
                   f"Schnittstelle. {e}")[:400]
        _warnung(hinweis)
    if art in LISTENFEHLER:
        naechte = _naechte_zaehlen(zustand, "listenfehler", jetzt, eintrag, neu)
        hinweis = (f"Abbruch wegen einer fehlerhaften Liste ({art}), {naechte}. Nacht ohne vollständigen Lauf; keine "
                   f"Fortsetzung, jede Nacht beginnt der Vollabruf von vorn. Nach {LISTENFEHLER_NAECHTE} Nächten "
                   f"{LISTENFEHLER_PAUSE.days} Tage Pause. {e}")[:400]
        _warnung(hinweis)
    _zustand_aendern(**neu)
    werte = {"abruf_fehler": {"zeit": _now(), "meldung": str(e)[:300]}}
    if hinweis:
        werte["abruf_hinweis"] = {"zeit": _now(), "meldung": hinweis}
    _stand_setzen(**werte)
    print(f"Abruf abgebrochen, letzter gültiger Stand bleibt: {e}")
    if os.environ.get("RATSATLAS_STRENG") == "ja":
        raise e


# Messwerte für die Schätzung des Vollabrufs (explore/STUFEN.md, Ergebnisse der Stufen 1–4); Antwortzeiten in Sekunden,
# jeweils der höchste gemessene Wert. Je Eintrag (Wert, Beleg)
MESSWERTE = {
    "grenzseite": (87, "Stufe 3 (11.11.2026): erste Vorlagenseite ganz vor 2020 nach created; 8.560 Vorlagen auf "
                       "den Seiten 1–86"),
    "organisationsseiten": (3, "Stufe 4 (12.11.2026): 240 Organisationen, Listenende erreicht"),
    "antwort_body": (0.52, "Stufe 1 (09.11.2026)"),
    "antwort_vorlagenseite": (4.61, "Stufe 2 (10.11.2026), höchster Wert; Stufe 1: 4,11; Stufe 3: 3,94–4,45"),
    "antwort_organisationsseite": (1.83, "Stufe 4 (12.11.2026), höchster Wert; Stufe 2: 0,67; Stufe 4: 1,08"),
    "antwort_sitzungsseite": (1.95, "Stufe 2 (10.11.2026), höchster Wert; Stufe 4: 1,59"),
}
# Rechenbeispiele für die Zahl der verwiesenen Sitzungen, solange sie nicht gemessen ist (keine Messwerte)
SITZUNGEN_BEISPIELE = (1000, 2000, 3000)


def _fensterlaenge():
    """Länge des Zeitfensters in Sekunden (config.ABRUF_ZEITFENSTER, volle Stunden); None ohne Zeitfenster."""
    f = abruf._fenster()
    if f is None:
        return None
    von, bis = f
    return ((bis - von) % 24 or 24) * 3600


def schaetzung(sitzungen=None, sicherheitsabstand=None, sitzungsseiten=None, grenzseite=None):
    """Zahl der Anfragen und Dauer des ersten Vollabrufs aus den Messwerten (MESSWERTE), ohne Netz. `sitzungen`: Zahl
    der von Beratungen der Vorlagen ab 2020 verwiesenen Sitzungen (nicht gemessen; None = offen, die Summe gilt dann
    ohne Einzelabrufe der Sitzungen). Untergrenze: Der Zeitfilter liest mindestens bis zur Grenzseite plus den
    Sicherheitsabstand; jede Seite mit Vorlagen im Zeitraum nach der Grenzseite verlängert ihn. Die Grenzseite wächst mit
    neuen Vorlagen seit der Messung (rund eine Seite je 100). Antwortzeit einer einzelnen Sitzung: nicht gemessen,
    Annahme wie eine Seite der Sitzungsliste (obere Schätzung). Liefert ein dict mit Posten, Summen und Annahmen."""
    k = config.ABRUF_SICHERHEITSABSTAND if sicherheitsabstand is None else sicherheitsabstand
    n = config.ABRUF_SITZUNGSSEITEN if sitzungsseiten is None else sitzungsseiten
    g = MESSWERTE["grenzseite"][0] if grenzseite is None else grenzseite
    abstand = max(config.ABRUF_ABSTAND, abruf.MINDESTABSTAND)
    w = {s: MESSWERTE[s][0] for s in MESSWERTE}
    posten = [
        ("Body", 1, w["antwort_body"]),
        ("Organisationen (vollständig)", w["organisationsseiten"], w["antwort_organisationsseite"]),
        (f"Vorlagen: Seiten 1–{g} (Grenzseite) und {k} Seiten Sicherheitsabstand", g + k, w["antwort_vorlagenseite"]),
        (f"Sitzungsliste: erste {n} Seiten", n, w["antwort_sitzungsseite"]),
    ]
    if sitzungen is not None:
        posten.append(("Sitzungen einzeln (verwiesene, ohne die aus der Liste)", sitzungen, w["antwort_sitzungsseite"]))
    anfragen = sum(z for _, z, _ in posten)
    sekunden = sum(z * (abstand + t) for _, z, t in posten)
    fenster = _fensterlaenge()
    naechte = math.ceil(sekunden / fenster) if fenster else None
    return {"posten": [{"posten": p, "anfragen": z, "sekunden": round(z * (abstand + t))} for p, z, t in posten],
            "anfragen": anfragen, "sekunden": round(sekunden), "naechte": naechte, "abstand": abstand,
            "fenster_sekunden": fenster, "sitzungen": sitzungen,
            "annahmen": [
                "Zahl der verwiesenen Sitzungen " + ("offen (nicht gemessen; nach Stufe 5 aus der Stichprobe "
                                                     "abschätzbar)" if sitzungen is None else f"gesetzt: {sitzungen}"),
                "Antwortzeit einer einzelnen Sitzung nicht gemessen; angesetzt wie eine Seite der Sitzungsliste",
                f"Untergrenze für die Vorlagen: Grenzseite {g} aus Stufe 3 (11.11.2026), seitdem neue Vorlagen schieben "
                "sie nach hinten (rund eine Seite je 100); Seiten mit Vorlagen im Zeitraum nach der Grenzseite "
                "verlängern den Sicherheitsabstand",
                "je Fortsetzung in einer weiteren Nacht eine Anfrage mehr (die zuletzt gelesene Seite erneut)",
            ]}


def _naechte_text(n):
    return f"{n} Nacht" if n == 1 else f"{n} Nächte"


def schaetzung_ausgeben():
    """Schritt `schaetzung` (python -m pipeline schaetzung): Schätzung ohne Netz ausgeben; RATSATLAS_SITZUNGEN=<Zahl>
    setzt die Zahl der verwiesenen Sitzungen, sonst Rechenbeispiele (SITZUNGEN_BEISPIELE, keine Messwerte)."""
    wert = os.environ.get("RATSATLAS_SITZUNGEN", "").strip()
    if wert and not wert.isdigit():
        raise SystemExit(f"RATSATLAS_SITZUNGEN={wert!r}: ganze Zahl erwartet")
    s = schaetzung(int(wert) if wert else None)
    print("Schätzung des ersten Vollabrufs (ohne Netz, aus explore/STUFEN.md)")
    print(f"Abstand {s['abstand']:g} s; Zeitfenster {config.ABRUF_ZEITFENSTER} Uhr"
          + (f" ({s['fenster_sekunden'] // 60} min)" if s["fenster_sekunden"] else ""))
    for p in s["posten"]:
        print(f"  {p['anfragen']:>6} Anfragen  {p['sekunden'] / 60:7.1f} min  {p['posten']}")
    print(f"  {s['anfragen']:>6} Anfragen  {s['sekunden'] / 60:7.1f} min  zusammen"
          + (f", {_naechte_text(s['naechte'])}" if s["naechte"] else ""))
    if not wert:
        print("Rechenbeispiele mit Einzelabrufen der Sitzungen (Zahl nicht gemessen, keine Messwerte):")
        for beispiel in SITZUNGEN_BEISPIELE:
            b = schaetzung(beispiel)
            print(f"  {beispiel:>5} Sitzungen: {b['anfragen']:>6} Anfragen, {b['sekunden'] / 3600:4.1f} h"
                  + (f", {_naechte_text(b['naechte'])}" if b["naechte"] else ""))
    print("Messwerte:")
    for name, (wert_, beleg) in MESSWERTE.items():
        print(f"  {name} = {wert_}: {beleg}")
    print("Annahmen:")
    for a in s["annahmen"]:
        print(f"  - {a}")
    return s
