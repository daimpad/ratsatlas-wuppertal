"""Ortsnamen-Abgleich für Stufe B in Wuppertal (CLAUDE.md 5.2, „Wuppertaler Eigenheiten bei Ortsnamen“).

Neu in Wuppertal, vorgezogen ohne Geodaten der Stadt (Freigabe 10.11.2026, CLAUDE.md 9); getestet nur mit erfundenen
Daten (tests/test_ortsnamen.py). Das Modul liest keine Dateien von selbst und baut keine Netzverbindung auf: Gebiete,
Straßen, Adressen und Flächen werden übergeben. Eingebunden wird es erst in Phase 3 (build._stage_b, volltext,
stufe_c); bis dahin arbeitet pipeline/geocode.py unverändert mit den aus Bonn übernommenen Regeln.

Abgleich (Verzeichnis.treffer):
1. Normalisierung beider Seiten mit derselben Funktion (normalisiere): NFC, casefold („ß“ → „ss“), Bindestriche,
   Gedankenstriche, Schrägstriche und Leerraum → ein Leerzeichen, „…str.“/„…strasse“/„…straße“ (auch getrennt:
   „Probe Straße“, „Probe-Str.“) → „…strasse“. Eine Indextabelle führt jede Stelle auf den Originaltext zurück; die
   Fundstelle behält die Originalschreibweise. Klammerzusätze („Musterweg (Testquartier A)“) entfernt nur das
   Verzeichnis (namensschluessel). Zusammenschreibung („Am Beispielhang“ / „Am Beispiel Hang“) gleicht sie nicht an.
2. Wortgrenzen: Ein Name beginnt und endet nicht innerhalb eines Worts (Buchstabe oder Ziffer); „Barmen“ trifft nicht in
   „Oberbarmen“ und nicht in „Barmener“, wohl aber in „Wuppertal-Barmen“.
3. Groß- und Kleinschreibung: verglichen wird ohne Unterschied; beginnt der Name im Verzeichnis groß, muss auch die
   Fundstelle groß beginnen (Text in Großbuchstaben trifft, „musterweg“ mitten im Satz nicht). Beginnt der Name mit
   Präpositionen oder Artikeln (VORWORT: „Am“, „An der“, „Zum“ …), gilt die Regel für das erste Wort danach („am
   Probehang“ mitten im Satz trifft „Am Probehang“).
4. Längster Treffer zuerst: Kandidaten aller Arten (Ausschluss, Gebietsname, Straße, Teilname) werden gemeinsam nach
   Länge der Fundstelle gewählt, bei gleicher Länge in dieser Reihenfolge; überlappende kürzere entfallen. So siegen
   „Oberbarmen“ über „Barmen“, „Elberfeld-West“ über „Elberfeld“, „Bezirksvertretung Elberfeld-West“ (Ausschluss) über
   beide und die Straße „Barmer Probestraße“ über den Ausschluss „Barmer“. Gleicher Schlüssel als Gebiets- und
   Straßenname: der Gebietsname gilt (wie Bonn, dort „reserved“), die Straße steht in `kandidaten`.
5. Ausschlüsse (AUSSCHLUESSE, wortgleich mit explore/ortsnamen_ausschluss.tsv, Gleichlauf in den Tests): reguläre
   Ausdrücke auf dem Originaltext, Platzhalter {name} = alle Gebietsnamen einschließlich Teilnamen, längste zuerst, mit
   beliebigem Trenner zwischen den Teilen und Wortgrenze dahinter. Wie beim Namensabgleich steht ein Leerzeichen im
   Muster für beliebigen Trenner (Leerraum, Zeilenumbruch, Bindestrich, Schrägstrich), und Groß- und Kleinschreibung
   zählt nicht („BV-Barmen“, „BEZIRKSVERTRETUNG BARMEN“, „Rathaus⏎Barmen“). Abweichung von explore/ortsnamen.py: dort
   ohne Wortgrenze dahinter, mit wörtlichem Leerzeichen und nur in der Schreibweise des Verzeichnisses. Mehrzahl
   („Bezirksvertretungen …“) und Aufzählungen („BV Barmen und Oberbarmen“) erfasst die Liste nicht; offen bis zur Prüfung
   an echten Titeln (Stufe 3), weil die Muster wortgleich mit explore/ortsnamen_ausschluss.tsv bleiben. Gewählte
   Ausschlüsse sperren ihre Zeichen; treffer() weist sie mit Regelnummer und den verdeckten Namen aus.
6. Doppelnamen: der ganze Name auch mit Leerzeichen oder Schrägstrich (über die Normalisierung); Teilnamen aus Bindestrich
   und Schrägstrich, ohne Himmelsrichtungen und „Mitte“ und ohne Teile unter drei Zeichen (TEIL_OHNE_ORT, dieselbe
   Annahme wie explore/ortsnamen.py). Ist ein Teilname zugleich ein voller Name, gilt der volle Name („Elberfeld“ aus
   „Elberfeld-West“ ist der Stadtbezirk Elberfeld); die andere Lesart steht in `kandidaten`. Teilnamen: Konfidenz
   „niedrig“, Methode „ortsteil_teilname“ (wie Köln) bzw. „stadtbezirk_teilname“ (neu).
7. Abgeleitete Formen: nur Genitiv auf „s“ bei Namen aus einem Wort („Vohwinkels“), abschaltbar (genitiv=False). Keine
   automatischen Adjektive (Bonn hängt „er“ an; das ergäbe „Barmener“ und kollidierte mit „Barmer“). Schreibvarianten
   (Gebiet.varianten) und historische Namen (historisch) nur aus übergebenen Tabellen mit Beleg; Vorgabe leer.

Verortung (Verzeichnis.verorte): Zeilen im Format von geocode.Gazetteer.locate (level, name, ortsteil, bezirk, lon, lat,
method, confidence, evidence, source) und zusätzlich source_object; wahlweise kandidaten, hinweis, anteil. `level` ist
das `geometry_level` aus CLAUDE.md 5.2. `evidence` ist die Fundstelle ohne Hausnummer (geprüft in
tests/test_ortsnamen.py; pipeline/check.py prüft bisher nur Ortsangaben der Stufe A, die Prüfung der Stufe B folgt in
Phase 3). Methodennamen wie Bonn und Köln, damit Frontend und spätere Zusammenführung sie kennen. Mehrere Fundstellen
derselben Straße ergeben eine Zeile je Quartier (Fundstellen mit „; “ verbunden); hat eine Hausnummer entschieden, gilt
nur sie. Zeilen der Ebene „adresse“ brauchen in Phase 3 einen eigenen Ortsschlüssel in build._add_location (dort
fielen bisher alle Adressen einer Straße zusammen).
- Mehrdeutige Gebietsnamen: Liegen alle Lesarten in einem Stadtbezirk, gilt der Stadtbezirk (Lesarten in
  `kandidaten`); sonst je Lesart eine Zeile „ortsteil_mehrdeutig“ bzw. „stadtbezirk_mehrdeutig“, Konfidenz niedrig.
- Straßen: Der Straßenschlüssel der Stadt ersetzt die Bonner Abstandsregel aus OSM (gleicher Schlüssel = eine Straße,
  auch über mehrere Quartiere; je Quartier eine Zeile mit `anteil`). Gleicher Name mit verschiedenen Schlüsseln: Eingrenzung
  über ein genanntes Quartier („strasse+ortsteil“), einen genannten Stadtbezirk oder die Stadtbezirke befasster
  Bezirksvertretungen („strasse+bezirk“), sonst „strasse_mehrdeutig“ (niedrig). Straße ohne Adresspunkte, aber mit
  Stadtbezirk im Straßenverzeichnis: nur der Stadtbezirk („strasse_stadtbezirk“, niedrig; neu).
- Hausnummer direkt hinter der Straße (HAUSNUMMER wörtlich aus Bonn und Köln, Jahreszahlen 1900–2100 ausgenommen, bei
  „12-14“ zählt 12). Zusätzlich zu Bonn und Köln, weil hier eine Hauskoordinate entstehen kann: Der Zusatzbuchstabe gilt
  nur direkt angehängt („12a“) oder allein vor Satzende oder Satzzeichen („12 b“), nicht als Anfang des nächsten Worts
  („12 B-Plan“); nach Nummer und Zusatz muss Satzende, ein Satzzeichen, ein Strich (Bereich) oder ein Bindewort aus
  NACH_HAUSNUMMER folgen („und“, „bis“, „in“, „Ecke“ …). Folgt ein anderes Wort („3 Bäume“, „4 Wochen“), gilt die Zahl
  nicht als Hausnummer: nur die Straße mit `hinweis`. Liegt die Adresse in genau einer der gleichnamigen Straßen,
  dann mit `punkt_erlaubt` die Hauskoordinate (level „adresse“, „strasse+hausnummer_punkt“, hoch, wie Köln), sonst nur
  das Quartier der Adresse mit dem Punkt der Straße im Quartier („strasse+hausnummer“, mittel, wie Bonn). Zusatz nicht im
  Verzeichnis, Nummer ohne Zusatz vorhanden: nur das Quartier, nie der Punkt (`hinweis`). Ob ein Punkt erlaubt ist,
  entscheidet die aufrufende Stelle (später eine Wuppertaler Fassung von Kölns hausnummer_punkt_erlaubt: nie bei
  Eingaben nach § 24 GO NRW; Vorlagenarten offen bis Messstufe 5).

Straße-zu-Quartier-Tabelle (strasse_quartier): dieselben Regeln wie explore/geodaten.py (_strasse_quartier: Schlüssel
wie _schluessel, ungültige Flächen nur im Speicher repariert und gezählt), damit die Ergebnisse vergleichbar bleiben;
dazu die Datenschutzregel für den Anzeigepunkt (Einzelheiten im Docstring der Funktion).

Offen bis zu den Messstufen (TECHNIK.md, Abschnitt Geokodierung): Feldnamen (config.GEO_FELDER), Schreibweise der
Gebietsnamen, Koordinatensystem, Eindeutigkeit der Straßenschlüssel, Form des Hausnummernzusatzes, B-Plan-Schema
(config.BPLAN_NUMMER), Ausschlüsse an echten Titeln, Gattungsnamen, historische Namen, `min_anteil`,
`mindestabstand_m`, Bindewörter nach der Hausnummer (NACH_HAUSNUMMER).
"""
import bisect
import collections
import csv
import math
import re
import unicodedata
from dataclasses import dataclass

from . import config

# --- Daten --------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Gebiet:
    """Quartier oder Stadtbezirk. `punkt`: (lon, lat) eines Punkts in der Fläche; `varianten`: ((Schreibweise, Beleg), …)."""
    name: str
    ebene: str                      # „quartier“ oder „stadtbezirk“
    stadtbezirk: str | None = None  # bei Stadtbezirken der eigene Name
    nummer: str | None = None
    punkt: tuple | None = None
    varianten: tuple = ()


@dataclass(frozen=True)
class Strasse:
    name: str
    schluessel: str | None = None
    stadtbezirk: str | None = None


@dataclass(frozen=True)
class Adresse:
    schluessel: str | None
    strasse: str | None
    hausnummer: str
    zusatz: str | None
    lon: float
    lat: float
    stadtbezirk: str | None = None


@dataclass(frozen=True)
class Flaeche:
    """Fläche eines Quartiers oder Stadtbezirks; `geometrie`: shapely-Geometrie oder GeoJSON-Geometrie (dict)."""
    name: str
    stadtbezirk: str | None
    geometrie: object
    nummer: str | None = None


@dataclass(frozen=True)
class Ausschluss:
    nr: str
    art: str
    muster: str
    beleg: str


@dataclass(frozen=True)
class Lesart:
    gebiet: Gebiet
    form: str       # name, teilname, variante, historisch
    alias: str      # Schreibweise im Verzeichnis (für die Regel zur Großschreibung)


@dataclass(frozen=True)
class Treffer:
    start: int
    ende: int
    fundstelle: str
    art: str                 # gebiet, teilname, strasse, ausschluss
    schluessel: str = ""     # normalisierter Name; bei Ausschlüssen leer
    eintraege: tuple = ()    # Lesarten bzw. Straßen; bei Ausschlüssen die verdeckten Fundstellen
    regel: str | None = None
    kandidaten: tuple = ()   # weitere Lesarten (Teilname zugleich voller Name, Straße gleich Gebietsname)


@dataclass(frozen=True)
class StrasseQuartier:
    quartier: str
    stadtbezirk: str | None
    anzahl: int
    anteil: float
    lon: float
    lat: float
    punkt: str = "adressen"   # „adressen“ (Schwerpunkt) oder „quartier“ (Punkt in der Fläche, Datenschutz)


class FeldFehlt(KeyError):
    """Feldname offen (None in config.GEO_FELDER) oder in einer Zeile nicht vorhanden."""


# Ausschlussliste, wortgleich mit explore/ortsnamen_ausschluss.tsv (Phase 1, Stand vor der Prüfung an echten Titeln;
# Erweiterung nur mit Beleg, CLAUDE.md 5.2). Gleichlauf: tests/test_ortsnamen.py
AUSSCHLUESSE = (
    Ausschluss("1", "gremium", r"\bBV {name}",
               "CLAUDE.md 5.2: „BV Barmen“ (Gremienname ohne Raumbezug der Vorlage)"),
    Ausschluss("2", "gremium", r"\bBezirksvertretung {name}",
               "CLAUDE.md 5.2 (Gremienname); Langform von „BV“ angenommen, an den Titeln zu prüfen"),
    Ausschluss("3", "gebaeude", r"\bRathaus {name}",
               "CLAUDE.md 5.2: „Rathaus Barmen“ (Sitzungsort ohne Raumbezug der Vorlage)"),
    Ausschluss("4", "eigenname", r"\bBarmer\b",
               "CLAUDE.md 5.2: „Barmer“ (Krankenkasse); wirkt nur, wenn ein Name des Verzeichnisses im Ausdruck liegt, "
               "gezählt wird jeder Treffer"),
)

# Teile eines Doppelnamens, die allein keinen Ort bezeichnen (Annahme wie explore/ortsnamen.py TEIL_OHNE_ORT)
TEIL_OHNE_ORT = {"Nord", "Süd", "Ost", "West", "Mitte", "Zentrum", "Nordost", "Nordwest", "Südost", "Südwest"}
# Hausnummer direkt nach dem Straßennamen („Probestraße 25“, „Nr. 12a“, „12-14“); nicht „Str. 2. Bauabschnitt“.
# Wörtlich aus pipeline/geocode.py (Bonn) und ratsatlas-koeln @d609111
HAUSNUMMER = re.compile(r"\s+(?:Nr\.\s*)?(\d{1,4})(?=[a-zA-Z]?(?:\s|$|[,;)\-–/]))")
# Zusatzbuchstabe: direkt angehängt oder allein vor Satzende bzw. Satzzeichen (Wuppertaler Ergänzung)
ZUSATZ = re.compile(r"([a-zA-Z])(?![^\W\d_])|\s([a-zA-Z])(?=\s*(?:$|[,;:.)]))")
# Was nach Nummer und Zusatz folgen darf, damit die Zahl als Hausnummer gilt (Wuppertaler Ergänzung; Liste vorläufig,
# an echten Titeln zu prüfen): Satzende, Satzzeichen, Strich oder Schrägstrich (Bereich), Bindewörter
NACH_HAUSNUMMER = re.compile(r"\s*(?:$|[,;:.()\]\-‐‑‒–—/&]|(?:und|u\.|bis|sowie|oder|bzw\.|in|im|an|am|auf|zwischen|"
                             r"gegenüber|Ecke)(?![^\W_]))")
# Mindestabstand des Anzeigepunkts einer Straße im Quartier zu jedem Hauspunkt in Metern (Datenschutz; vorläufig,
# Wert in Phase 3 festlegen)
MINDESTABSTAND_M = 25.0
# Präpositionen und Artikel am Anfang von Namen (Regel 3: Großschreibung am ersten Wort danach)
VORWORT = {"am", "an", "auf", "aufm", "im", "in", "zum", "zur", "zu", "unter", "unterm", "vor", "vorm", "hinter",
           "hinterm", "über", "überm", "bei", "beim", "der", "die", "das", "den", "dem", "des"}
# Stichwörter vor B-Plan-Nummern (sprachlich, aus pipeline/geocode.py PLAN; das Nummernschema ist offen). Bonns
# „satzung“ fehlt bewusst: ob Nummern nach „Satzung“ dem B-Plan-Schema folgen, ist offen bis Messstufe G.
PLAN_STICHWORT = r"(?:beba?u\w*pl[aä]n\w*|b-pl[aä]n\w*|bauleitplan\w*|vorhaben- und erschließungsplan\w*)"

EBENE_METHODE = {"quartier": "ortsteil", "stadtbezirk": "stadtbezirk"}   # Bonner Methoden- und Ebenennamen
KONFIDENZ_FORM = {"name": "mittel", "variante": "mittel", "historisch": "mittel", "teilname": "niedrig"}
_TRENNER = set("-‐‑‒–—/") | {"_"}
_STRASSE = re.compile(r"(?<=[^\W_]) ?(?:strasse|str\.)(?![^\W_])")
_TRENNER_RX = r"[\s\-‐‑‒–—/]+"


# --- Normalisierung -----------------------------------------------------------------------------------------------------

def normalisiere(text):
    """(norm, anfang, ende): normalisierter Text und für jedes seiner Zeichen Anfang und Ende im Originaltext (nach NFC).
    Eine Funktion für Text und Verzeichnis."""
    text = unicodedata.normalize("NFC", text or "")
    zeichen, anf, end = [], [], []
    for i, c in enumerate(text):
        if c.isspace() or c in _TRENNER:
            if zeichen and zeichen[-1] == " ":
                end[-1] = i + 1
                continue
            zeichen.append(" ")
            anf.append(i)
            end.append(i + 1)
            continue
        for f in c.casefold():
            zeichen.append(f)
            anf.append(i)
            end.append(i + 1)
    norm = "".join(zeichen)
    # „…str.“, „…strasse“ (auch nach einem Trenner) → „…strasse“
    teile, a2, e2, pos = [], [], [], 0
    for m in _STRASSE.finditer(norm):
        teile.append(norm[pos:m.start()])
        a2 += anf[pos:m.start()]
        e2 += end[pos:m.start()]
        teile.append("strasse")
        a2 += [anf[m.start()]] * 7
        e2 += [end[m.end() - 1]] * 7
        pos = m.end()
    teile.append(norm[pos:])
    a2 += anf[pos:]
    e2 += end[pos:]
    norm = "".join(teile)
    # Trenner am Rand entfallen
    links = len(norm) - len(norm.lstrip(" "))
    rechts = len(norm.rstrip(" "))
    return norm[links:rechts], a2[links:rechts], e2[links:rechts]


def schluessel(name):
    """Normalisierter Schlüssel eines Namens."""
    return normalisiere(name)[0]


def namensschluessel(name):
    """(Name ohne Klammerzusatz, Zusatz) für Einträge des Verzeichnisses: „Musterweg (Testquartier A)“ →
    („Musterweg“, „Testquartier A“)."""
    m = re.fullmatch(r"\s*(.*?)\s*\(([^()]*)\)\s*", name or "")
    if m and m.group(1):
        return m.group(1), m.group(2).strip()
    return (name or "").strip(), None


def _wortzeichen(c):
    return c.isalnum()


def _passt(name, fund):
    """Regel 3: Beginnt der Name im Verzeichnis groß, muss auch die Fundstelle groß beginnen; bei Präpositionen und
    Artikeln am Anfang (VORWORT) gilt das für das erste Wort danach."""
    worte = [w for w in re.split(_TRENNER_RX, name.strip()) if w]
    k = next((i for i, w in enumerate(worte) if w.casefold() not in VORWORT), 0)
    if not worte or not worte[k][:1].isupper():
        return True
    fworte = [w for w in re.split(_TRENNER_RX, fund.strip()) if w]
    if k and k < len(fworte):
        return fworte[k][:1].isupper()
    return fund[:1].isupper()


def _teilnamen(name):
    """Teile eines Doppelnamens (Bindestrich, Schrägstrich), ohne TEIL_OHNE_ORT und Teile unter drei Zeichen."""
    if not re.search(r"[-/]", name):
        return []
    teile = [t.strip() for t in re.split(r"\s*[-/]\s*", name)]
    return [t for t in teile if len(t) >= 3 and t not in TEIL_OHNE_ORT]


def _flexibel(name):
    """Regulärer Ausdruck für einen Namen im Originaltext mit beliebigem Trenner zwischen den Teilen."""
    teile = [re.escape(t) for t in re.split(_TRENNER_RX, name.strip()) if t]
    return _TRENNER_RX.join(teile)


def _ausschluss_regex(muster, platz):
    """Ausschlussmuster (Wortlaut wie explore/ortsnamen_ausschluss.tsv) für den Abgleich: Leerzeichen = beliebiger Trenner,
    Groß- und Kleinschreibung gleich (dieselben Bedingungen wie der Namensabgleich, Regel 1 und 3)."""
    return re.compile(muster.replace(" ", _TRENNER_RX).replace("{name}", platz), re.IGNORECASE)


def _hausnummer(text, ende):
    """(Nummer, Zusatz) direkt hinter der Straße (Zusatz klein oder ""), keine Jahreszahl; False, wenn auf die Zahl ein
    Wort folgt, das sie nicht als Hausnummer ausweist („Probestraße 3 Bäume“); sonst None."""
    m = HAUSNUMMER.match(text, ende)
    if not m or 1900 <= int(m.group(1)) <= 2100:
        return None
    pos = m.end(1)
    zusatz = ZUSATZ.match(text, pos)
    if zusatz:
        pos = zusatz.end()
    if not NACH_HAUSNUMMER.match(text, pos):
        return False
    return str(int(m.group(1))), ((zusatz.group(1) or zusatz.group(2)).lower() if zusatz else "")


def _nummer(wert):
    wert = str(wert if wert is not None else "").strip()
    return str(int(wert)) if wert.isdigit() else wert


def _schluessel_der_stadt(wert):
    """Straßenschlüssel zum Abgleich wie explore/geodaten.py _schluessel: Ziffernfolgen ohne führende Nullen, ganzzahlige
    Kommazahlen als ganze Zahl („00123“, 123 und 123.0 → „123“), sonst getrimmter Text."""
    s = str(wert).strip()
    if isinstance(wert, float) and wert.is_integer():
        s = str(int(wert))
    return str(int(s)) if s.isdigit() else s


def _strassen_id(schluessel_der_stadt, name):
    """Schlüssel der Stadt vor Name (wie explore/geodaten.py)."""
    if schluessel_der_stadt is not None and str(schluessel_der_stadt).strip():
        return f"s:{_schluessel_der_stadt(schluessel_der_stadt)}"
    return f"n:{schluessel(namensschluessel(name)[0])}" if name else None


# --- Verzeichnis --------------------------------------------------------------------------------------------------------

class Verzeichnis:
    """Namen der Gebiete und Straßen mit den abgeleiteten Tabellen; `tabelle` und `adressindex` aus strasse_quartier.
    `gattung`: Straßennamen, die im Titel oft nicht die Straße meinen (Konfidenz niedrig; Vorgabe leer).
    `historisch`: {historischer Name: (Name eines Gebiets, Beleg)} (Vorgabe leer)."""

    def __init__(self, gebiete, strassen=(), tabelle=None, adressindex=None, ausschluesse=AUSSCHLUESSE,
                 gattung=frozenset(), historisch=None, genitiv=True):
        self.gebiete = list(gebiete)
        self.bezirke = {g.name: g for g in self.gebiete if g.ebene == "stadtbezirk"}
        self.strassen = list(strassen)
        self.tabelle = tabelle or {}
        self.adressindex = adressindex or {}
        self.gattung = {schluessel(namensschluessel(n)[0]) for n in gattung}
        self.index = collections.defaultdict(lambda: {"voll": [], "teil": [], "strassen": []})
        nach_name = {g.name: g for g in self.gebiete}
        namen_regex = []
        for g in self.gebiete:
            formen = [(g.name, "name")] + [(v, "variante") for v, _beleg in g.varianten]
            for alias, form in formen:
                self.index[schluessel(alias)]["voll"].append(Lesart(g, form, alias))
                namen_regex.append(alias)
        for alt, (name, _beleg) in (historisch or {}).items():
            if name in nach_name:
                self.index[schluessel(alt)]["voll"].append(Lesart(nach_name[name], "historisch", alt))
                namen_regex.append(alt)
        for g in self.gebiete:
            for teil in _teilnamen(g.name):
                self.index[schluessel(teil)]["teil"].append(Lesart(g, "teilname", teil))
                namen_regex.append(teil)
        for s in self.strassen:
            name, _zusatz = namensschluessel(s.name)
            if len(name) >= 4:   # wie Bonn: sehr kurze Namen nicht
                self.index[schluessel(name)]["strassen"].append(s)
        if genitiv:
            for key in [k for k, e in self.index.items() if " " not in k and (e["voll"] or e["teil"])]:
                gen = key + "s"
                if key.endswith(("s", "z", "x")) or gen in self.index:
                    continue
                e = self.index[key]
                self.index[gen]["voll"].extend(e["voll"])
                self.index[gen]["teil"].extend(e["teil"])
        self.index = dict(self.index)
        self.laenge = max((len(k) for k in self.index), default=0)
        # Ausschlüsse: {name} = alle Gebietsnamen einschließlich Teilnamen, längste zuerst, Wortgrenze dahinter
        alle = sorted(set(namen_regex), key=lambda n: (-len(n), n))
        platz = "(?:" + "|".join(_flexibel(n) for n in alle) + r")(?![^\W_])" if alle else "(?!)"
        self.ausschluesse = [(a, _ausschluss_regex(a.muster, platz)) for a in ausschluesse]

    # --- Abgleich ---------------------------------------------------------------------------------------------------

    def _kandidaten(self, text):
        norm, anf, end = normalisiere(text)
        n = len(norm)
        starts = [i for i in range(n) if norm[i] != " " and (i == 0 or not (_wortzeichen(norm[i - 1])
                                                                             and _wortzeichen(norm[i])))]
        enden = [j for j in range(1, n + 1) if norm[j - 1] != " " and (j == n or not (_wortzeichen(norm[j - 1])
                                                                                     and _wortzeichen(norm[j])))]
        out = []
        for i in starts:
            k = bisect.bisect_right(enden, i)
            while k < len(enden) and enden[k] - i <= self.laenge:
                j = enden[k]
                k += 1
                eintrag = self.index.get(norm[i:j])
                if not eintrag:
                    continue
                s, e = anf[i], end[j - 1]
                fund = text[s:e]
                voll = tuple(l for l in eintrag["voll"] if _passt(l.alias, fund))
                teil = tuple(l for l in eintrag["teil"] if _passt(l.alias, fund))
                strassen = tuple(x for x in eintrag["strassen"] if _passt(namensschluessel(x.name)[0], fund))
                key = norm[i:j]
                if voll:
                    out.append((s, e, 1, Treffer(s, e, fund, "gebiet", key, voll, kandidaten=teil + strassen)))
                elif strassen:
                    out.append((s, e, 2, Treffer(s, e, fund, "strasse", key, strassen, kandidaten=teil)))
                elif teil:
                    out.append((s, e, 3, Treffer(s, e, fund, "teilname", key, teil)))
        return out

    def treffer(self, text):
        """Gewählte Treffer in der Reihenfolge des Texts, einschließlich gewählter Ausschlüsse (art „ausschluss“, mit
        Regelnummer und den verdeckten Fundstellen in `eintraege`). Positionen beziehen sich auf den Text nach NFC."""
        text = unicodedata.normalize("NFC", text or "")
        kand = self._kandidaten(text)
        for a, rx in self.ausschluesse:
            for m in rx.finditer(text):
                if m.end() > m.start():
                    kand.append((m.start(), m.end(), 0, Treffer(m.start(), m.end(), m.group(0), "ausschluss",
                                                                regel=a.nr)))
        kand.sort(key=lambda k: (-(k[1] - k[0]), k[2], k[0]))
        belegt = [False] * (len(text) + 1)
        gewaehlt = []
        for s, e, _prio, t in kand:
            if any(belegt[s:e]):
                continue
            for x in range(s, e):
                belegt[x] = True
            gewaehlt.append(t)
        # verdeckte Namen in Ausschlüssen (für das Audit); nur Kandidaten mit Anfang im möglichen Bereich (bisect)
        namen = sorted((k for k in kand if k[3].art != "ausschluss"), key=lambda k: (k[0], k[1]))
        anfaenge = [k[0] for k in namen]
        laengste = max((k[1] - k[0] for k in namen), default=0)
        aus = []
        for t in gewaehlt:
            if t.art == "ausschluss":
                lo = bisect.bisect_left(anfaenge, t.start - laengste)
                hi = bisect.bisect_left(anfaenge, t.ende)
                verdeckt = tuple(dict.fromkeys(k[3].fundstelle for k in namen[lo:hi] if k[1] > t.start))
                t = Treffer(t.start, t.ende, t.fundstelle, t.art, t.schluessel, verdeckt, t.regel)
            aus.append(t)
        return sorted(aus, key=lambda t: t.start)

    # --- Verortung --------------------------------------------------------------------------------------------------

    def _gebiet_zeile(self, g, method, conf, evidence, **extra):
        lon, lat = g.punkt if g.punkt else (None, None)
        if g.ebene == "quartier":
            return dict(level="ortsteil", name=g.name, ortsteil=g.name, bezirk=g.stadtbezirk, lon=lon, lat=lat,
                        method=method, confidence=conf, evidence=evidence, source=config.QUELLE_GEO, **extra)
        return dict(level="stadtbezirk", name=g.name, ortsteil=None, bezirk=g.name, lon=lon, lat=lat, method=method,
                    confidence=conf, evidence=evidence, source=config.QUELLE_STADTBEZIRKE, **extra)

    def _bezirke_der_strasse(self, sid, strassen):
        bz = {e.stadtbezirk for e in self.tabelle.get(sid, ()) if e.stadtbezirk}
        return bz | {s.stadtbezirk for s in strassen if s.stadtbezirk}

    def _strasse(self, t, text, named_q, named_bz, bv, punkt_erlaubt):
        """Zeilen für einen Straßentreffer (Straßen und Hausnummern, siehe Docstring des Moduls)."""
        name = namensschluessel(t.eintraege[0].name)[0]
        gruppen = collections.defaultdict(list)   # Straßen-ID → Straßen
        for s in t.eintraege:
            gruppen[_strassen_id(s.schluessel, s.name)].append(s)
        ev = t.fundstelle
        nr = _hausnummer(text, t.ende)
        hinweis = "Zahl hinter dem Straßennamen nicht als Hausnummer gewertet" if nr is False else None
        if nr:
            nummer, zusatz = nr
            exakt = [(sid, self.adressindex[(sid, nummer, zusatz)]) for sid in gruppen
                     if (sid, nummer, zusatz) in self.adressindex]
            ohne_zusatz = [(sid, self.adressindex[(sid, nummer, "")]) for sid in gruppen
                           if zusatz and (sid, nummer, "") in self.adressindex]
            if len(exakt) == 1:
                sid, (q, bz, lon, lat) = exakt[0]
                vorher = sorted({e.quartier for e in self.tabelle.get(sid, ())})
                if punkt_erlaubt:
                    return [dict(level="adresse", name=name, ortsteil=q, bezirk=bz, lon=lon, lat=lat,
                                 method="strasse+hausnummer_punkt", confidence="hoch", evidence=ev,
                                 source=config.QUELLE_ADRESSEN, hnr_vorher=vorher)]
                return self._strasse_im_quartier(name, sid, q, bz, "strasse+hausnummer", ev, bv, vorher)
            if not exakt and len(ohne_zusatz) == 1:
                sid, (q, bz, _lon, _lat) = ohne_zusatz[0]
                vorher = sorted({e.quartier for e in self.tabelle.get(sid, ())})
                return self._strasse_im_quartier(name, sid, q, bz, "strasse+hausnummer", ev, bv, vorher,
                                                 hinweis="Zusatz der Hausnummer nicht im Verzeichnis; nur das Quartier")
            hinweis = ("Hausnummer in mehreren gleichnamigen Straßen" if len(exakt) > 1
                       else "Hausnummer nicht im Verzeichnis")
        rows = self._strasse_ohne_nummer(name, gruppen, ev, named_q, named_bz, bv)
        if hinweis:
            rows = [dict(r, hinweis=hinweis) for r in rows]
        return rows

    def _strasse_zusammen(self, gruppe, text, named_q, named_bz, bv, punkt_erlaubt):
        """Mehrere Fundstellen derselben Straße: Zeilen mit Hausnummer gehen vor (die übrigen Quartiere der Straße
        entfallen); gleiche Zeilen werden eine, ihre Fundstellen mit „; “ verbunden."""
        je = [self._strasse(t, text, named_q, named_bz, bv, punkt_erlaubt) for t in gruppe]
        mit_nr = [r for rows in je for r in rows if "hausnummer" in r["method"]]
        kandidaten = mit_nr or [r for rows in je for r in rows]
        out = {}
        for r in kandidaten:
            key = (r["level"], r["name"], r["ortsteil"], r["bezirk"], r["lon"], r["lat"], r["method"])
            if key in out:
                alt = out[key]
                if r["evidence"] not in alt["evidence"].split("; "):
                    alt["evidence"] += "; " + r["evidence"]
                continue
            out[key] = dict(r)
        return list(out.values())

    def _strasse_im_quartier(self, name, sid, q, bz, method, ev, bv, vorher, hinweis=None):
        """Quartier der Adresse mit dem Anzeigepunkt der Straße in diesem Quartier (nie der Hauspunkt)."""
        e = next((x for x in self.tabelle.get(sid, ()) if x.quartier == q), None)
        conf = "niedrig" if bv and bz not in bv else "mittel"
        zeile = dict(level="strasse", name=name, ortsteil=q, bezirk=bz, lon=e.lon if e else None,
                     lat=e.lat if e else None, method=method, confidence=conf, evidence=ev,
                     source=config.QUELLE_ADRESSEN, hnr_vorher=vorher)
        if hinweis:
            zeile["hinweis"] = hinweis
        return [zeile]

    def _strasse_ohne_nummer(self, name, gruppen, ev, named_q, named_bz, bv):
        gattung = schluessel(name) in self.gattung
        conf = "niedrig" if gattung else "mittel"
        sids = list(gruppen)
        method = "strasse"
        if len(sids) > 1:
            mit_q = [sid for sid in sids if {e.quartier for e in self.tabelle.get(sid, ())} & named_q]
            if len(mit_q) == 1:
                sids, method = mit_q, "strasse+ortsteil"
            else:
                eng = named_bz or bv
                keep = [sid for sid in sids if self._bezirke_der_strasse(sid, gruppen[sid]) & eng] if eng else []
                if len(keep) == 1:
                    sids, method = keep, "strasse+bezirk"
                else:
                    sids, method, conf = keep or sids, "strasse_mehrdeutig", "niedrig"
        rows = []
        for sid in sids:
            eintraege = list(self.tabelle.get(sid, ()))
            if method in ("strasse", "strasse+bezirk") and {e.quartier for e in eintraege} & named_q:
                eintraege, method_sid = [e for e in eintraege if e.quartier in named_q], "strasse+ortsteil"
            elif method == "strasse+ortsteil":
                eintraege, method_sid = [e for e in eintraege if e.quartier in named_q], method
            else:
                method_sid = method
            c = conf
            if method_sid in ("strasse", "strasse+bezirk") and c == "mittel":
                bzs = {e.stadtbezirk for e in eintraege}
                if bv and not (bzs & bv):
                    c = "niedrig"   # Straße liegt nicht im Stadtbezirk der befassten Bezirksvertretung
                elif named_bz and not (bzs & named_bz):
                    c = "niedrig"   # Titel nennt einen anderen Stadtbezirk
            for e in eintraege:
                rows.append(dict(level="strasse", name=name, ortsteil=e.quartier, bezirk=e.stadtbezirk, lon=e.lon,
                                 lat=e.lat, method=method_sid, confidence=c, evidence=ev,
                                 source=config.QUELLE_ADRESSEN, anteil=e.anteil))
            if not eintraege:
                # keine Adresspunkte: nur der Stadtbezirk aus dem Straßenverzeichnis, wenn eindeutig
                bzs = {s.stadtbezirk for s in gruppen[sid] if s.stadtbezirk}
                if len(bzs) == 1 and next(iter(bzs)) in self.bezirke:
                    g = self.bezirke[next(iter(bzs))]
                    rows.append(self._gebiet_zeile(g, "strasse_stadtbezirk", "niedrig", ev, strasse=name,
                                                   hinweis="Straße ohne Adresspunkte; nur der Stadtbezirk"))
                    rows[-1]["source"] = config.QUELLE_STRASSEN
        return rows

    def verorte(self, text, *, bv_bezirke=(), punkt_erlaubt=False, source_object=None):
        """Ortsbezüge eines Texts als Zeilen (Format wie geocode.Gazetteer.locate, dazu source_object). `bv_bezirke`:
        Stadtbezirke befasster Bezirksvertretungen; `punkt_erlaubt`: Hauskoordinate zulässig (aufrufende Stelle)."""
        text = unicodedata.normalize("NFC", text or "")
        bv = set(bv_bezirke)
        treffer = [t for t in self.treffer(text) if t.art != "ausschluss"]

        def lesarten(t):
            return [l for l in t.eintraege] if t.art in ("gebiet", "teilname") else []
        named_q = {l.gebiet.name for t in treffer for l in lesarten(t) if l.gebiet.ebene == "quartier"}
        named_bz = ({l.gebiet.name for t in treffer for l in lesarten(t) if l.gebiet.ebene == "stadtbezirk"}
                    | {l.gebiet.stadtbezirk for t in treffer for l in lesarten(t)
                       if l.gebiet.ebene == "quartier" and l.gebiet.stadtbezirk})
        rows = []
        nach_strasse = collections.defaultdict(list)   # mehrere Fundstellen derselben Straße zusammen
        for t in treffer:
            if t.art == "strasse":
                nach_strasse[t.schluessel].append(t)
        for gruppe in nach_strasse.values():
            rows += self._strasse_zusammen(gruppe, text, named_q, named_bz, bv, punkt_erlaubt)
        gebiet_rows = []   # (Gebiet bzw. Stadtbezirk, Zeile) in Reihenfolge des Texts
        for t in treffer:
            if t.art not in ("gebiet", "teilname"):
                continue
            les = list(dict.fromkeys(t.eintraege))
            kand = [f"{l.gebiet.ebene} {l.gebiet.name}" for l in t.kandidaten if isinstance(l, Lesart)]
            kand += [f"strasse {namensschluessel(s.name)[0]}" for s in t.kandidaten if isinstance(s, Strasse)]
            gebiete = list(dict.fromkeys(l.gebiet for l in les))
            if len(gebiete) == 1:
                l = les[0]
                g = l.gebiet
                method = f"{EBENE_METHODE[g.ebene]}_{l.form}"
                conf = KONFIDENZ_FORM[l.form]
                if g.ebene == "quartier" and bv and g.stadtbezirk not in bv:
                    conf = "niedrig"
                extra = {"kandidaten": kand} if kand else {}
                gebiet_rows.append(self._gebiet_zeile(g, method, conf, t.fundstelle, **extra))
                continue
            bezirke = {g.name if g.ebene == "stadtbezirk" else g.stadtbezirk for g in gebiete}
            alle = [f"{g.ebene} {g.name}" for g in gebiete] + kand
            if len(bezirke) == 1 and None not in bezirke and next(iter(bezirke)) in self.bezirke:
                bz = self.bezirke[next(iter(bezirke))]
                eigene = next((l for l in les if l.gebiet == bz), None)
                form = eigene.form if eigene else ("teilname" if all(l.form == "teilname" for l in les) else "name")
                gebiet_rows.append(self._gebiet_zeile(bz, f"stadtbezirk_{form}", KONFIDENZ_FORM[form], t.fundstelle,
                                                      kandidaten=alle))
            else:
                for g in gebiete:
                    gebiet_rows.append(self._gebiet_zeile(g, f"{EBENE_METHODE[g.ebene]}_mehrdeutig", "niedrig",
                                                          t.fundstelle, kandidaten=alle))
        # Abdeckung wie Bonn: ein schon über eine Straße verortetes Quartier bekommt keine eigene Zeile, ein Stadtbezirk
        # mit Quartiers- oder Straßenzeile keine Stadtbezirkszeile; mehrere Fundstellen desselben Gebiets → eine Zeile
        covered = {r["ortsteil"] for r in rows if r.get("ortsteil")}
        # Hat die Hausnummer entschieden, gilt ein genanntes Quartier derselben Straße als Lagebezeichnung (wie Bonn)
        covered |= {q for r in rows for q in r.get("hnr_vorher", ())}
        quartiere = {}
        for r in gebiet_rows:
            if r["level"] != "ortsteil" or r["ortsteil"] in covered:
                continue
            if r["name"] in quartiere:
                alt = quartiere[r["name"]]
                if r["evidence"] not in alt["evidence"].split("; "):
                    alt["evidence"] += "; " + r["evidence"]
                continue
            quartiere[r["name"]] = r
        rows += quartiere.values()
        covered_bz = {r["bezirk"] for r in rows}
        bezirke = {}
        for r in gebiet_rows:
            if r["level"] != "stadtbezirk" or r["bezirk"] in covered_bz:
                continue
            if r["name"] in bezirke:
                alt = bezirke[r["name"]]
                if r["evidence"] not in alt["evidence"].split("; "):
                    alt["evidence"] += "; " + r["evidence"]
                continue
            bezirke[r["name"]] = r
        rows += bezirke.values()
        for r in rows:
            r["source_object"] = source_object
        return rows


# --- Straße-zu-Quartier-Tabelle -----------------------------------------------------------------------------------------

def _geometrie(g):
    from shapely.geometry import shape
    return shape(g) if isinstance(g, dict) else g


def _meter(a, b):
    """Abstand zweier Punkte (lon, lat) in Grad als Näherung in Metern (abstandstreue Zylinderprojektion; genügt für
    Abstände von einigen Dutzend Metern)."""
    breite = math.radians((a[1] + b[1]) / 2)
    return math.hypot((a[0] - b[0]) * math.cos(breite) * 111_320, (a[1] - b[1]) * 110_574)


def strasse_quartier(adressen, quartiere, *, min_anteil=0.0, mindestabstand_m=MINDESTABSTAND_M):
    """(tabelle, adressindex, befund) aus Adresspunkten und Quartiersflächen, Regeln wie explore/geodaten.py
    (_strasse_quartier):
    - Point-in-Polygon je Adresse; Straße über den Schlüssel der Stadt, sonst über den normalisierten Namen.
    - Punkt auf einer Grenze (in mehreren Flächen oder auf dem Rand): das alphabetisch erste Quartier; gezählt.
    - Anteil = Zahl der Adressen der Straße im Quartier / Zahl der Adressen der Straße mit Quartier (bevorzugt dicht
      bebaute Abschnitte). Quartiere unter `min_anteil` entfallen (vorläufig 0,0; Wert in Phase 3).
    - Anzeigepunkt: Schwerpunkt der Adresspunkte im Quartier; liegt er außerhalb, der nächste Punkt der Fläche; danach
      auf 6 Stellen gerundet. Nie ein einzelner Hauspunkt (Datenschutz): bei weniger als zwei verschiedenen Punkten oder
      einem Anzeigepunkt näher als `mindestabstand_m` an einem Hauspunkt (geprüft nach dem Runden) der Punkt in der
      Fläche des Quartiers (`punkt` = „quartier“). Der Mindestabstand ist vorläufig (MINDESTABSTAND_M), Wert in Phase 3.
    - Ungültige Quartiersflächen werden wie in explore/geodaten.py nur im Speicher repariert (shapely.make_valid) und
      gezählt („ungültige fläche“); die übergebenen Geometrien bleiben unverändert.
    - Vorab: Ausdehnung der Adressen und Quartiere müssen sich überschneiden (Koordinatensystem, Achsenfolge), sonst
      ValueError.
    tabelle: Straßen-ID → [StrasseQuartier] (absteigend nach Anzahl); adressindex: (Straßen-ID, Nummer, Zusatz) →
    (Quartier, Stadtbezirk, lon, lat); befund: Zählungen (ohne Quartier, auf Grenze, ohne Straßenangabe, Stadtbezirk
    der Adresse ungleich Stadtbezirk des Quartiers – nur gezählt, nicht korrigiert –, Schlüssel mit mehreren Namen,
    doppelte Adresse in verschiedenen Quartieren). Namen je Straßen-ID (häufigster) in befund["namen"]."""
    import shapely
    from shapely import STRtree
    from shapely.geometry import MultiPoint, Point
    from shapely.ops import nearest_points

    adressen = list(adressen)
    befund = collections.Counter()
    flaechen = []
    for q in quartiere:
        g = _geometrie(q.geometrie)
        if not g.is_valid:
            befund["ungültige fläche"] += 1
            g = shapely.make_valid(g)   # nur im Speicher
        flaechen.append((q, g))
    if not adressen or not flaechen:
        return {}, {}, {"zaehlung": befund, "namen": {}}
    xs = [a.lon for a in adressen]
    ys = [a.lat for a in adressen]
    qb = [g.bounds for _, g in flaechen]
    qx0, qy0 = min(b[0] for b in qb), min(b[1] for b in qb)
    qx1, qy1 = max(b[2] for b in qb), max(b[3] for b in qb)
    if max(xs) < qx0 or min(xs) > qx1 or max(ys) < qy0 or min(ys) > qy1:
        raise ValueError(f"Ausdehnung der Adressen ({min(xs)}, {min(ys)}, {max(xs)}, {max(ys)}) und der Quartiere "
                         f"({qx0}, {qy0}, {qx1}, {qy1}) überschneidet sich nicht: Koordinatensystem oder Achsenfolge "
                         "prüfen")
    baum = STRtree([g for _, g in flaechen])
    je = collections.defaultdict(lambda: collections.defaultdict(list))   # Straßen-ID → Quartier → [(lon, lat)]
    namen = collections.defaultdict(collections.Counter)
    adressindex = {}
    q_bezirk = {q.name: q.stadtbezirk for q, _ in flaechen}
    q_geom = {q.name: g for q, g in flaechen}
    for a in adressen:
        sid = _strassen_id(a.schluessel, a.strasse)
        if not sid:
            befund["ohne straßenangabe"] += 1
            continue
        if a.strasse:
            namen[sid][namensschluessel(a.strasse)[0]] += 1
        pt = Point(a.lon, a.lat)
        treffer = [flaechen[int(i)] for i in baum.query(pt, predicate="covered_by")]
        if not treffer:
            befund["ohne quartier"] += 1
            continue
        treffer.sort(key=lambda x: x[0].name)
        if len(treffer) > 1 or not treffer[0][1].contains(pt):
            befund["auf grenze"] += 1
        q = treffer[0][0]
        if a.stadtbezirk and q.stadtbezirk and a.stadtbezirk != q.stadtbezirk:
            befund["stadtbezirk abweichend"] += 1
        je[sid][q.name].append((a.lon, a.lat))
        key = (sid, _nummer(a.hausnummer), (a.zusatz or "").strip().lower())
        wert = (q.name, q.stadtbezirk, a.lon, a.lat)
        if key in adressindex and adressindex[key][0] != q.name:
            befund["doppelte adresse"] += 1
            continue
        adressindex.setdefault(key, wert)
    tabelle = {}
    for sid, nach_q in je.items():
        gesamt = sum(len(p) for p in nach_q.values())
        zeilen = []
        for q, punkte in nach_q.items():
            anteil = len(punkte) / gesamt
            if anteil < min_anteil:
                continue
            verschieden = set(punkte)
            geom = q_geom[q]
            art = "adressen"
            if len(verschieden) >= 2:
                mitte = MultiPoint(sorted(verschieden)).centroid
                if not geom.covers(mitte):
                    mitte = nearest_points(geom, mitte)[0]
                xy = (round(mitte.x, 6), round(mitte.y, 6))
                if any(_meter(xy, (round(x, 6), round(y, 6))) < mindestabstand_m for x, y in verschieden):
                    art = "quartier"
            else:
                art = "quartier"
            if art == "quartier":
                rp = geom.representative_point()
                xy = (round(rp.x, 6), round(rp.y, 6))
            zeilen.append(StrasseQuartier(q, q_bezirk[q], len(punkte), round(anteil, 4), xy[0], xy[1], art))
        tabelle[sid] = sorted(zeilen, key=lambda z: (-z.anzahl, z.quartier))
    mehrere = {sid: c for sid, c in namen.items() if len(c) > 1}
    befund["schlüssel mit mehreren namen"] = len(mehrere)
    haupt = {sid: sorted(c.items(), key=lambda x: (-x[1], x[0]))[0][0] for sid, c in namen.items()}
    return tabelle, adressindex, {"zaehlung": befund, "namen": haupt}


def quartier_stadtbezirk(quartiere, bezirke):
    """Quartiere ohne eigenen Stadtbezirk: Stadtbezirk über den Punkt in der Quartiersfläche (Point-in-Polygon). Liefert
    (neue Flächen, Namen ohne Stadtbezirk)."""
    bz = [(b, _geometrie(b.geometrie)) for b in bezirke]
    out, offen = [], []
    for q in quartiere:
        if q.stadtbezirk:
            out.append(q)
            continue
        p = _geometrie(q.geometrie).representative_point()
        hit = sorted(b.name for b, g in bz if g.covers(p))
        if not hit:
            offen.append(q.name)
        out.append(Flaeche(q.name, hit[0] if hit else None, q.geometrie, q.nummer))
    return out, offen


def gebiete_aus_flaechen(flaechen, ebene):
    """Gebiete mit einem Punkt in der Fläche (representative_point) aus Flächen."""
    out = []
    for f in flaechen:
        p = _geometrie(f.geometrie).representative_point()
        out.append(Gebiet(f.name, ebene, f.name if ebene == "stadtbezirk" else f.stadtbezirk, f.nummer,
                          (round(p.x, 6), round(p.y, 6))))
    return out


# --- Felder der Quelle --------------------------------------------------------------------------------------------------

def _feld(zeile, art, rolle, felder):
    name = felder[art].get(rolle)
    if name is None:
        raise FeldFehlt(f"{art}: Feld für „{rolle}“ offen (config.GEO_FELDER, Messstufe G)")
    if name is False:
        return None
    if name not in zeile:
        raise FeldFehlt(f"{art}: Feld „{name}“ ({rolle}) fehlt in der Zeile")
    wert = zeile[name]
    return None if wert in (None, "") else str(wert).strip()


def aus_feldern(zeilen, art, felder=None):
    """Rohzeilen der Stadt in Datenklassen: „strassen“ (CSV-Zeilen → Strasse), „adressen“ (GeoJSON-Features mit Punkt →
    Adresse), „quartiere“ und „stadtbezirke“ (GeoJSON-Features → Flaeche). Feldnamen aus `felder` (Vorgabe
    config.GEO_FELDER); ein offenes Feld (None) oder ein fehlendes Feld bricht mit FeldFehlt ab, es wird nichts geraten."""
    felder = felder or config.GEO_FELDER
    if art not in felder:
        raise FeldFehlt(f"Art „{art}“ nicht in config.GEO_FELDER")
    out = []
    for z in zeilen:
        if art == "strassen":
            out.append(Strasse(_feld(z, art, "name", felder), _feld(z, art, "schluessel", felder),
                               _feld(z, art, "stadtbezirk", felder)))
            continue
        props = z.get("properties")
        geom = z.get("geometry")
        if props is None or not geom:
            raise FeldFehlt(f"{art}: Zeile ohne properties oder geometry")
        if art == "adressen":
            if geom.get("type") != "Point":
                raise FeldFehlt(f"adressen: Geometrie {geom.get('type')} statt Point")
            lon, lat = geom["coordinates"][:2]
            out.append(Adresse(_feld(props, art, "schluessel", felder), _feld(props, art, "strasse", felder),
                               _feld(props, art, "hausnummer", felder), _feld(props, art, "zusatz", felder),
                               float(lon), float(lat), _feld(props, art, "stadtbezirk", felder)))
        else:
            bz = _feld(props, art, "stadtbezirk", felder) if art == "quartiere" else None
            name = _feld(props, art, "name", felder)
            out.append(Flaeche(name, bz if art == "quartiere" else name, geom, _feld(props, art, "nummer", felder)))
    return out


def ausschluesse_aus_tsv(pfad):
    """Ausschlussregeln aus einer TSV-Datei mit den Spalten nr, art, muster, beleg (Format explore/ortsnamen_ausschluss.tsv)."""
    with open(pfad, encoding="utf-8", newline="") as f:
        return tuple(Ausschluss(z["nr"], z["art"], z["muster"], z["beleg"]) for z in csv.DictReader(f, delimiter="\t"))


# --- B-Plan-Nummern -----------------------------------------------------------------------------------------------------

def plan_nummern(text, schema=None):
    """[(Nummer, Fundstelle)] nach einem Stichwort (Bebauungsplan, B-Plan …); `schema`: regulärer Ausdruck für eine
    Nummer (Vorgabe config.BPLAN_NUMMER, offen bis Messstufe G). Ohne Schema eine leere Liste."""
    schema = schema if schema is not None else config.BPLAN_NUMMER
    if not schema:
        return []
    eine = rf"(?<![\w-])(?:{schema})(?![\w-])"
    rx = re.compile(rf"(?i){PLAN_STICHWORT}(?:\s+Nr\.)?[^;]{{0,50}}?({eine}(?:\s*(?:,|und|/|sowie|bzw\.)\s*(?:Nr\.\s*)?"
                    rf"{eine})*)")
    gefunden = {}
    for m in rx.finditer(text or ""):
        for n in re.findall(eine, m.group(1)):
            gefunden.setdefault(re.sub(r"\s+", " ", n).strip(), m.group(0).strip())
    return list(gefunden.items())
