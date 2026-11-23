"""Verifikation (Phase 6, freigegeben am 23.11.2026, CLAUDE.md 9): Stichprobe veröffentlichter Vorlagen gegen die
OParl-API der Stadt und Prüfliste für den Abgleich von Hand mit dem Ratsinformationssystem.

Aufruf: `python3 -m pipeline verify`, nach `build` und `export`, im nächtlichen Lauf von pages.yml (einmal automatisch,
danach auf Knopfdruck). Ersetzt den Bonner Schritt `verify` (pipeline/verify.py, Pilot-Ortsteil und OParl-Lite).

Stichprobe: STICHPROBE Vorlagen aus der Datenbank (config.DB), gezogen mit einem Startwert (Datum des Laufs, im Ergebnis
vermerkt). Je Vorlage genau eine Anfrage über pipeline/abruf.py (eine Verbindung, Abstand, Zeitfenster 23–1 Uhr,
Pausen, User-Agent; gesperrt ohne RATSATLAS_STADT_INFORMIERT), keine weiteren Anfragen. Verglichen werden die Felder, aus
denen Liste, Vorgang und Export entstehen: Nummer, Titel, Datum, Vorlagenart, Federführung (Datenbank), Zahl der
Beratungen (Datenbank) und die Anlagen (Kennungen aus den Rohdaten). Hat die Stadt die Vorlage seit dem Abruf geändert
(`modified` neuer), heißt eine Abweichung „seit dem Abruf geändert“, nicht „abweichend“.

Nur nach einem vollständigen Abruf (STAND.json ohne abruf_fehler, abruf_hinweis oder abruf_uebersprungen); sonst
keine Anfrage.

Abbruch: HTTP 404 gilt als Befund der Vorlage („nicht gefunden“), der Lauf geht weiter. Jeder andere Abbruch beendet die
Stichprobe sofort; die bis dahin geprüften Vorlagen werden geschrieben. Zählt der Abbruch als mögliche Sperre
(sessionnet.moegliche_sperre), wird er im Abrufzustand vermerkt wie ein Abbruch des Abrufs (Nacht mit möglicher Sperre,
12-Stunden-Regel), damit die folgenden Nächte pausieren; der Datenstand (STAND.json) bleibt unberührt.

Ergebnisse in config.EXPORT (kommen ins Datenpaket):
- verifikation_oparl.tsv: je Vorlage und Feld eine Zeile (drucksache, feld, export, oparl_api, ergebnis); Titel mit
  ausgeblendeter Hausnummer wie in allen Exporten (maske).
- verifikation_oparl.json: Zeitpunkt, Startwert, Zahl der Vorlagen, übereinstimmend, abweichend, geändert, Fehler, Ende.
- verifikation_pruefliste.tsv: die ersten PRUEFLISTE Vorlagen der Stichprobe mit Nummer, Titel, Datum, Beratungsfolge
  (Gremium, Sitzungstag) und Link zur ersten Anlage, zum Abgleich von Hand mit https://ris.wuppertal.de/ (Suche nach
  der Drucksachennummer; die Vorlagen der Schnittstelle tragen keinen Link `web`). Kein Abruf von ris.wuppertal.de.

Abweichung für den gemeinsamen Kern: Köln hat keine Stichprobe gegen die Quelle; Bonn (pipeline/verify.py) prüft mit
Pilot-Ortsteil und Ortsangaben der Stufe A, die es in Wuppertal nicht gibt."""
import json
import random
import sqlite3
from datetime import datetime

from . import abruf, config, maske, sessionnet
from .export import _write_tsv

STICHPROBE = 50
PRUEFLISTE = 20
TSV = "verifikation_oparl.tsv"
JSON = "verifikation_oparl.json"
PRUEF_TSV = "verifikation_pruefliste.tsv"
FELDER = (("reference", "reference"), ("name", "name"), ("date", "date"), ("paper_type", "paperType"))


def _rohdaten(ids):
    """Rohobjekte (papers.jsonl) der gewählten Vorlagen: Anlagen und `modified` zum Abruf."""
    out = {}
    if config.PAPERS.is_file():
        with open(config.PAPERS, encoding="utf-8") as f:
            for zeile in f:
                if zeile.strip():
                    p = json.loads(zeile)
                    if p.get("id") in ids:
                        out[p["id"]] = p
    return out


def _anlagen(objekt):
    return ";".join(sorted(a.get("id", "") for a in (objekt or {}).get("auxiliaryFile") or [] if isinstance(a, dict)))


def _zeit(wert):
    try:
        return datetime.fromisoformat(str(wert).replace("Z", "+00:00"))
    except ValueError:
        return None


def _https(url):
    """Link zum Öffnen im Browser: Hosts der Stadt über https:// (die Kennungen der Schnittstelle nennen http://)."""
    try:
        return abruf.abrufadresse(url) if url else ""
    except abruf.Abbruch:
        return url


def _stichprobe(db, n, seed):
    ids = [r[0] for r in db.execute("SELECT id FROM paper ORDER BY id")]
    return random.Random(seed).sample(ids, min(n, len(ids)))


def _sperre_vermerken(e):
    """Mögliche Sperre im Abrufzustand vermerken wie sessionnet._abbruch_vermerken, ohne STAND.json zu ändern."""
    zeit = abruf.uhr().isoformat(timespec="seconds")
    zustand = sessionnet._zustand()
    art, code = getattr(e, "art", ""), getattr(e, "code", None)
    neu = {"letzter_abbruch": {"zuletzt": zeit, "art": art, "code": code, "meldung": f"Verifikation: {e}"[:300]}}
    if sessionnet.moegliche_sperre(e):
        verdacht = zustand.get("sperre_verdacht") or {}
        neu["sperre_verdacht"] = {"naechte": verdacht.get("naechte", 0) + 1, "zuletzt": zeit, "art": art, "code": code,
                                  "meldung": f"Verifikation: {e}"[:300]}
    sessionnet._zustand_aendern(**neu)


def verifizieren(n=STICHPROBE, seed=None):
    if not config.DB.is_file():
        raise SystemExit(f"Verifikation: {config.DB} fehlt – erst `build`.")
    stand = json.loads(config.STAND.read_text(encoding="utf-8")) if config.STAND.is_file() else {}
    offen = [k for k in ("abruf_fehler", "abruf_hinweis", "abruf_uebersprungen") if stand.get(k)]
    if offen:   # nur nach einem vollständigen Abruf in diesem Lauf: sonst keine weitere Anfrage an die Stadt
        print(f"Verifikation übersprungen: der Abruf endete nicht vollständig ({', '.join(offen)}).")
        return None
    seed = int(abruf.uhr().strftime("%Y%m%d")) if seed is None else seed
    db = sqlite3.connect(config.DB)
    db.row_factory = sqlite3.Row
    ids = _stichprobe(db, n, seed)
    roh = _rohdaten(set(ids))
    m = maske.aus_db(db)
    zeilen, ergebnis = [], {"uebereinstimmend": 0, "abweichend": 0, "geaendert": 0, "fehler": 0}
    ende, geprueft = "vollständig", []
    for pid in ids:
        p = db.execute("SELECT * FROM paper WHERE id = ?", (pid,)).fetchone()
        ref = p["reference"]
        try:
            src = abruf.get_json(pid)
        except abruf.Abbruch as e:
            if getattr(e, "art", "") == "http" and getattr(e, "code", None) == 404:
                zeilen.append([ref, "abruf", "", "HTTP 404", "nicht gefunden"])
                ergebnis["fehler"] += 1
                geprueft.append(pid)
                continue
            ende = f"abgebrochen ({getattr(e, 'art', '') or type(e).__name__})"
            if getattr(e, "art", "") not in ("zeitfenster", "parallel", "gesperrt"):
                _sperre_vermerken(e)
            print(f"Verifikation abgebrochen nach {len(geprueft)} Vorlagen: {e}")
            break
        geprueft.append(pid)
        alt, neu = _zeit((roh.get(pid) or {}).get("modified")), _zeit(src.get("modified"))
        geaendert = bool(alt and neu and neu > alt)
        pruef = [(eigen, p[eigen], src.get(fremd)) for eigen, fremd in FELDER]
        pruef.append(("under_direction_of", p["under_direction_of"], (src.get("underDirectionOf") or [None])[0]))
        n_ber = db.execute("SELECT COUNT(*) FROM consultation WHERE paper_id = ?", (pid,)).fetchone()[0]
        pruef.append(("beratungen", n_ber, len(src.get("consultation") or [])))
        pruef.append(("anlagen", _anlagen(roh.get(pid)), _anlagen(src)))
        alle = True
        for feld, eigen, fremd in pruef:
            gleich = str(eigen if eigen is not None else "") == str(fremd if fremd is not None else "")
            alle &= gleich
            if feld == "name":
                eigen, fremd = m(eigen, ref), m(fremd, ref)
            urteil = "ok" if gleich else "seit dem Abruf geändert" if geaendert else "abweichend"
            zeilen.append([ref, feld, eigen if eigen is not None else "", fremd if fremd is not None else "", urteil])
        ergebnis["uebereinstimmend" if alle else "geaendert" if geaendert else "abweichend"] += 1
    if not geprueft:   # nichts geprüft (gesperrt, Zeitfenster, erster Abruf abgebrochen): frühere Ergebnisse bleiben
        db.close()
        print(f"Verifikation: keine Vorlage geprüft ({ende}); frühere Ergebnisse bleiben.")
        return None
    config.EXPORT.mkdir(parents=True, exist_ok=True)
    _write_tsv(config.EXPORT / TSV, ["drucksache", "feld", "export", "oparl_api", "ergebnis"], zeilen)
    meta = {"zeit": abruf.uhr().isoformat(timespec="seconds"), "seed": seed, "stichprobe": len(ids),
            "geprueft": len(geprueft), **ergebnis, "ende": ende, "anfragen": abruf.statistik().get("anfragen", 0)}
    (config.EXPORT / JSON).write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    _pruefliste(db, ids[:PRUEFLISTE], roh, m)
    db.close()
    print(f"Verifikation: {ergebnis['uebereinstimmend']} von {len(geprueft)} Vorlagen stimmen in allen Feldern mit der "
          f"OParl-API überein ({ergebnis['abweichend']} abweichend, {ergebnis['geaendert']} seit dem Abruf geändert, "
          f"{ergebnis['fehler']} nicht gefunden; {ende}) → {config.EXPORT / TSV}")
    return meta


def _pruefliste(db, ids, roh, m):
    zeilen = []
    for nr, pid in enumerate(ids, 1):
        p = db.execute("SELECT reference, name, date FROM paper WHERE id = ?", (pid,)).fetchone()
        folge = "; ".join(f"{o or 'Gremium offen'} {(d or '')[:10]}".strip() for o, d in db.execute(
            "SELECT o.name, m.start_date FROM consultation c LEFT JOIN organization o ON o.id = c.organization_id "
            "LEFT JOIN meeting m ON m.id = c.meeting_id WHERE c.paper_id = ? ORDER BY c.position", (pid,)))
        anlagen = [a for a in (roh.get(pid) or {}).get("auxiliaryFile") or [] if isinstance(a, dict)]
        link = (anlagen[0].get("accessUrl") or anlagen[0].get("downloadUrl") or "") if anlagen else ""
        zeilen.append([nr, p["reference"], m(p["name"], p["reference"]), p["date"] or "", folge,
                       _https(link), "", ""])
    _write_tsv(config.EXPORT / PRUEF_TSV, ["nr", "drucksache", "titel", "datum", "beratungsfolge", "erste_anlage",
                                           "urteil (richtig/falsch/unklar)", "anmerkung"], zeilen)
