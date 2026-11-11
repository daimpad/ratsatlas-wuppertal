"""Änderungsprotokoll der Vorlagen (CLAUDE.md 5.1): nachgelieferte, ersetzte oder entfernte Unterlagen sichtbar machen.

Schritt `aenderungen` (python3 -m pipeline aenderungen; in `all` nach `fetch`, vor `build`). Er sendet keine Anfrage,
sondern vergleicht je Lauf die Rohdaten `papers.jsonl` mit dem Vorstand (`config.VORSTAND`, Stand des vorigen Laufs)
und hängt jede Änderung an `config.AENDERUNGEN` (`audit_aenderungen.tsv`) an. Verglichen werden je Vorlage:
- `modified` (Wert der Quelle),
- die Dateiliste: `mainFile` und `auxiliaryFile` (Wuppertal: nur `auxiliaryFile`, CLAUDE.md 3.1), je Datei mit Kennung
  (`id`, sonst `accessUrl`) und Fingerabdruck aus Adressen, Größe, Prüfsummen, Typ und Zeitpunkten (FINGERABDRUCK),
- die Beratungsfolge (`consultation` in ihrer Reihenfolge: Kennung, Sitzung, TOP, Rolle, abschließend, Gremium; ein
  aus der Sitzung ergänztes Gremium, `_organization_quelle` = „sitzung“, zählt nicht, es stammt nicht aus der Vorlage:
  ergänzt und nicht ergänzt gelten als „kein Gremium in der Vorlage“, damit ein Lauf ohne Ergänzung, etwa nach einem
  Abbruch beim Abruf der Sitzungen, keine Scheinänderung erzeugt; gleiche Darstellung in `alt` und `neu` ergibt nie
  eine Zeile).
Ergebnisse der TOPs stehen in den Sitzungen, nicht in der Vorlage, und zählen nicht.

Datenschutz (CLAUDE.md 2): Dateinamen (`name`, `fileName`) können Personennamen enthalten (etwa Anregungen nach § 24
GO NRW). Sie stehen weder im Protokoll noch im Vorstand; der Vorstand hält nur einen gekürzten SHA-256-Wert, damit eine
Umbenennung als „Dateiname geändert (nicht protokolliert)“ erscheint. Titel stehen ebenfalls nicht im Protokoll (sie
können Adressen enthalten); die Spalte `vorlage` trägt die Drucksachennummer. Volltexte (`text`) bleiben außen vor.

Spalten (SPALTEN): `vorlage`, `feld`, `alt`, `neu`, `zeitpunkt` nach CLAUDE.md 5.1, dazu `quellobjekt` (OParl-Kennung
der Vorlage) für die Rückführbarkeit (CLAUDE.md 1) und als Schlüssel für die Anzeige. `zeitpunkt` ist ein Wert je Lauf
(UTC, wie STAND.json). Werte in `feld`:
- `modified`: alt und neu wie in der Quelle;
- `mainFile`, `auxiliaryFile`: die Menge der Dateien hat sich geändert (hinzugefügt oder entfernt), alt und neu als
  „n Dateien: Kennung | Kennung …“;
- `mainFile.angaben`, `auxiliaryFile.angaben`: gleiche Kennung, anderer Fingerabdruck (ersetzt oder umbenannt), je
  Datei die geänderten Angaben;
- `consultation`: Reihenfolge oder Angaben der Beratungen geändert, alt und neu als „n Beratungen: …“.
Tabulatoren und alle Zeichen, die als Zeilenende gelten können (wie `str.splitlines`), werden in Werten durch
Leerzeichen ersetzt; die Datei wird ohne CSV-Anführungszeichen geschrieben und gelesen (`csv.QUOTE_NONE`), damit
`cut`, `awk` und zeilenweise Leser jede Zeile als genau einen Datensatz sehen.

Ohne Vorstand (erster Lauf) entsteht nur der Vorstand und die Kopfzeile, keine Änderung; ein unlesbarer Vorstand wird
als `….defekt` beiseitegelegt (Warnung) und wie ein erster Lauf behandelt. Neue Vorlagen und Vorlagen, die nicht mehr
in den Rohdaten stehen oder als gelöscht (`deleted`) markiert sind, erzeugen keine Zeile (Umgang mit zurückgezogenen
Vorlagen offen, CLAUDE.md 8). Ein Lauf ohne neue Rohdaten (Abruf übersprungen oder vor dem Schreiben von
`papers.jsonl` ausgefallen) erzeugt keine Zeile. Bricht der Abruf erst nach den Vorlagen ab (etwa bei den Sitzungen,
sessionnet.fetch_all), stehen die neu geholten Vorlagen schon in `papers.jsonl`: Ihre echten Änderungen erscheinen in
diesem Lauf, der nächste vollständige Lauf wiederholt sie nicht.
Reihenfolge beim Schreiben: erst das Protokoll, dann der Vorstand; scheitert der zweite Schritt, erscheint die Änderung
im nächsten Lauf noch einmal, geht aber nicht verloren.

Anzeige: `unterlagen_geaendert()` liefert je Vorlage den Tag der jüngsten Änderung der Dateiliste (export.py,
„Unterlagen geändert am …“ in Vorgang und Vorgangsseite). Tag: das neue `modified` der Vorlage aus demselben Lauf
(Datum der Quelle, Europe/Berlin), wenn es nicht nach dem Lauf liegt; sonst der Tag des Laufs.

Abweichung für den gemeinsamen Kern: Köln (ratsatlas-koeln @d609111 und origin/main @90928bc) und Bonn haben kein
Änderungsprotokoll der Vorlagen (Köln nur `_plan_changes` für Bebauungspläne). Das Modul arbeitet auf dem Bonner
Rohdatenformat (`papers.jsonl`) und ist vom Adapter unabhängig, damit es in den gemeinsamen Kern passt."""
import csv
import hashlib
import json
import os
import re
import sys

from . import config
from .fetch import _now, _write
from .process import local_day

SPALTEN = ["vorlage", "feld", "alt", "neu", "zeitpunkt", "quellobjekt"]
DATEIFELDER = ("mainFile", "auxiliaryFile")
# Angaben einer Datei, die eine Ersetzung anzeigen; ohne Namen und Volltext (siehe oben)
FINGERABDRUCK = ("accessUrl", "downloadUrl", "size", "sha1Checksum", "sha512Checksum", "mimeType", "date", "modified",
                 "deleted")
NAMENSFELDER = ("name", "fileName")
NAME = "_name"   # Schlüssel des gekürzten Prüfwerts der Namen im Fingerabdruck
BERATUNG = ("id", "meeting", "agendaItem", "role", "authoritative")


def _warnung(text):
    """Warnung im Log; in GitHub Actions als Annotation (wie sessionnet._warnung)."""
    print(f"::warning::{text}" if os.environ.get("GITHUB_ACTIONS") == "true" else f"Warnung: {text}", file=sys.stderr)


# Tabulator und alle Zeilenenden nach str.splitlines (\n \r \v \f \x1c–\x1e \x85 U+2028 U+2029)
_TRENNER = re.compile("[\t\n\r\v\f\x1c-\x1e\x85\u2028\u2029]")
# TSV ohne CSV-Anführungszeichen (Werte sind durch _sauber frei von Tabulatoren und Zeilenenden)
TSV = {"delimiter": "\t", "quoting": csv.QUOTE_NONE, "quotechar": None}


def _sauber(wert):
    """Wert als eine Zeile der TSV: Tabulatoren und Zeilenenden als Leerzeichen; Nicht-Text als JSON."""
    if wert is None:
        return ""
    return _TRENNER.sub(" ", wert if isinstance(wert, str) else json.dumps(wert, ensure_ascii=False))


def _dateien(p, feld):
    """{Kennung: Fingerabdruck} der Dateien eines Felds; Kennung `id`, sonst `accessUrl`. Ein bloßer Verweis (Text)
    zählt mit leerem Fingerabdruck; Einträge ohne Kennung zählen nicht."""
    werte = p.get(feld)
    werte = [werte] if isinstance(werte, (dict, str)) else werte if isinstance(werte, list) else []
    out = {}
    for f in werte:
        if isinstance(f, str):
            out[f] = {}
            continue
        if not isinstance(f, dict):
            continue
        kennung = f.get("id") if isinstance(f.get("id"), str) and f["id"] else f.get("accessUrl")
        if not isinstance(kennung, str) or not kennung:
            continue
        fp = {k: f[k] for k in FINGERABDRUCK if f.get(k) is not None}
        namen = [f.get(k) for k in NAMENSFELDER]
        if any(namen):
            fp[NAME] = hashlib.sha256(json.dumps(namen, ensure_ascii=False).encode()).hexdigest()[:16]
        out[kennung] = fp
    return out


def _beratungen(p):
    out = []
    for c in p.get("consultation") or []:
        if not isinstance(c, dict):
            continue
        e = {k: c.get(k) for k in BERATUNG}
        # Schlüssel immer gesetzt: ergänzt (aus der Sitzung) und fehlend sind gleich
        e["organization"] = None if c.get("_organization_quelle") == "sitzung" else c.get("organization")
        out.append(e)
    return out


def eintrag(p):
    """Eintrag des Vorstands für eine Vorlage (nur Vergleichswerte, keine Namen)."""
    return {"reference": p.get("reference"), "modified": p.get("modified"),
            "dateien": {f: _dateien(p, f) for f in DATEIFELDER}, "beratungen": _beratungen(p)}


def _menge(dateien):
    n = len(dateien)
    return f"{n} {'Datei' if n == 1 else 'Dateien'}" + (": " + " | ".join(sorted(dateien)) if n else "")


def _angaben(kennung, alt, neu):
    """(alt, neu) für eine Datei mit gleicher Kennung und anderem Fingerabdruck: nur die geänderten Angaben; ein
    geänderter Name nur als Hinweis."""
    felder = [k for k in FINGERABDRUCK if alt.get(k) != neu.get(k)]
    teil = lambda fp: ", ".join(f"{k} {_sauber(fp.get(k)) or '–'}" for k in felder)
    a, n = teil(alt), teil(neu)
    if alt.get(NAME) != neu.get(NAME):
        a = ", ".join(x for x in (a, "Dateiname (nicht protokolliert)") if x)
        n = ", ".join(x for x in (n, "Dateiname geändert (nicht protokolliert)") if x)
    return f"{kennung}: {a}", f"{kennung}: {n}"


def _folge(beratungen):
    def eine(c):
        org = c.get("organization")
        org = ", ".join(map(str, org)) if isinstance(org, list) else org
        teile = [f"Rolle {_sauber(c.get('role')) or '–'}", *([f"Gremium {_sauber(org)}"] if org else []),
                 f"Sitzung {_sauber(c.get('meeting')) or '–'}", f"TOP {_sauber(c.get('agendaItem')) or '–'}",
                 *(["abschließend"] if c.get("authoritative") else [])]
        return f"{_sauber(c.get('id')) or '–'} ({'; '.join(teile)})"
    n = len(beratungen)
    return f"{n} {'Beratung' if n == 1 else 'Beratungen'}" + (": " + " | ".join(map(eine, beratungen)) if n else "")


def vergleich(pid, alt, neu, zeit):
    """Zeilen des Protokolls für eine Vorlage (Vorstand `alt` gegen `neu`, beide aus `eintrag`)."""
    zeilen = []
    zeile = lambda feld, a, n: zeilen.append({"vorlage": _sauber(neu.get("reference")), "feld": feld, "alt": _sauber(a),
                                              "neu": _sauber(n), "zeitpunkt": zeit, "quellobjekt": _sauber(pid)})
    if alt.get("modified") != neu.get("modified"):
        zeile("modified", alt.get("modified"), neu.get("modified"))
    for feld in DATEIFELDER:
        a, n = (alt.get("dateien") or {}).get(feld) or {}, (neu.get("dateien") or {}).get(feld) or {}
        if set(a) != set(n):
            zeile(feld, _menge(a), _menge(n))
        geaendert = [_angaben(k, a[k], n[k]) for k in sorted(set(a) & set(n)) if a[k] != n[k]]
        if geaendert:
            zeile(f"{feld}.angaben", " | ".join(x for x, _ in geaendert), " | ".join(y for _, y in geaendert))
    folge_alt, folge_neu = _folge(alt.get("beratungen") or []), _folge(neu.get("beratungen") or [])
    if folge_alt != folge_neu:   # nur sichtbare Unterschiede (ein Vorstand älterer Form oder ["x"] statt "x" nicht)
        zeile("consultation", folge_alt, folge_neu)
    return zeilen


def _vorstand():
    """Vorlagen des Vorstands oder None (kein Vorstand). Ein unlesbarer Vorstand wird als `….defekt` beiseitegelegt."""
    if not config.VORSTAND.exists():
        return None
    try:
        v = json.loads(config.VORSTAND.read_text(encoding="utf-8"))
        if isinstance(v, dict) and isinstance(v.get("vorlagen"), dict):
            return v["vorlagen"]
        grund = "unerwartete Form"
    except (ValueError, RecursionError) as e:
        grund = str(e)
    defekt = config.VORSTAND.with_name(config.VORSTAND.name + ".defekt")
    os.replace(config.VORSTAND, defekt)
    _warnung(f"{config.VORSTAND.name} unlesbar ({grund}); beiseitegelegt als {defekt.name}, Vergleich beginnt neu "
             "(in diesem Lauf keine Änderungen)")
    return None


def _anhaengen(zeilen):
    """Hängt Zeilen an das Protokoll an (Kopfzeile beim ersten Mal). Eine ältere Datei mit anderem Kopf wird auf
    SPALTEN umgestellt (Werte nach Spaltennamen, wie die Abrufstatistik in sessionnet._statistik)."""
    config.AENDERUNGEN.parent.mkdir(parents=True, exist_ok=True)
    alle, modus = zeilen, "a"
    if not config.AENDERUNGEN.exists():
        modus = "w"
    else:
        with open(config.AENDERUNGEN, encoding="utf-8", newline="") as f:
            r = csv.DictReader(f, **TSV)
            if r.fieldnames != SPALTEN:
                alle, modus = [*r, *zeilen], "w"
    if modus == "a" and not alle:
        return
    with open(config.AENDERUNGEN, modus, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, SPALTEN, lineterminator="\n", extrasaction="ignore", **TSV)
        if modus == "w":
            w.writeheader()
        w.writerows(alle)


def protokollieren(jetzt=None):
    """Schritt `aenderungen`: vergleicht papers.jsonl mit dem Vorstand, hängt Änderungen an das Protokoll an und
    schreibt den neuen Vorstand. Liefert die Zahl der Zeilen. Ohne papers.jsonl (noch kein Abruf) bleibt alles, wie es
    ist."""
    if not config.PAPERS.exists():
        print("Änderungsprotokoll: keine Vorlagen (papers.jsonl fehlt); nichts zu vergleichen.")
        return 0
    zeit = jetzt or _now()
    with open(config.PAPERS, encoding="utf-8") as f:
        # wie build.py: je Kennung der letzte Eintrag, gelöschte ausgenommen
        papers = {p["id"]: p for p in map(json.loads, filter(str.strip, f)) if isinstance(p, dict) and p.get("id")}
    neu = {pid: eintrag(p) for pid, p in papers.items() if not p.get("deleted")}
    vorstand = _vorstand()
    zeilen = [z for pid in sorted(neu) if vorstand is not None and isinstance(vorstand.get(pid), dict)
              for z in vergleich(pid, vorstand[pid], neu[pid], zeit)]
    _anhaengen(zeilen)
    config.VORSTAND.parent.mkdir(parents=True, exist_ok=True)
    _write(config.VORSTAND, json.dumps({"zeitpunkt": zeit, "vorlagen": neu}, ensure_ascii=False) + "\n")
    print(f"Änderungsprotokoll: {len(zeilen)} Änderungen an {len({z['quellobjekt'] for z in zeilen})} Vorlagen"
          + (" (erster Vergleich: Vorstand angelegt)" if vorstand is None else "") + f" → {config.AENDERUNGEN}")
    return len(zeilen)


_GEAENDERT = {}


def _tag(wert):
    try:
        return local_day(wert)
    except (TypeError, ValueError):
        return None


def unterlagen_geaendert():
    """{Kennung der Vorlage: Tag (JJJJ-MM-TT)} der jüngsten Änderung ihrer Dateiliste laut Protokoll (siehe oben).
    Zwischengespeichert, solange sich die Datei nicht ändert; fehlt sie, leer."""
    try:
        st = config.AENDERUNGEN.stat()
    except OSError:
        return {}
    schluessel = (str(config.AENDERUNGEN), st.st_mtime_ns, st.st_size)
    if _GEAENDERT.get("schluessel") == schluessel:
        return _GEAENDERT["werte"]
    with open(config.AENDERUNGEN, encoding="utf-8", newline="") as f:
        zeilen = list(csv.DictReader(f, **TSV))
    modified = {(z.get("quellobjekt"), z.get("zeitpunkt")): z.get("neu") for z in zeilen if z.get("feld") == "modified"}
    werte = {}
    for z in zeilen:
        pid, zeit = z.get("quellobjekt"), z.get("zeitpunkt")
        if not pid or (z.get("feld") or "").split(".")[0] not in DATEIFELDER:
            continue
        lauf = _tag(zeit)
        if not lauf:
            continue
        quelle = _tag(modified.get((pid, zeit)))
        tag = quelle if quelle and quelle <= lauf else lauf
        if tag > werte.get(pid, ""):
            werte[pid] = tag
    _GEAENDERT.update(schluessel=schluessel, werte=werte)
    return werte
