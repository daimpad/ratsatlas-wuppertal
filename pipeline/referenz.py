"""Vorlagennummern (`reference`) zerlegen und Vorlagen mit Zusatz ihrer Ausgangsvorlage zuordnen (CLAUDE.md 4.2).

Wuppertaler Schema `VO/NNNN/JJ` (CLAUDE.md 3.1). Ein Teil der Vorlagen trägt einen Zusatz an der Nummer (Messstufe 5,
explore/STUFEN.md: 76 von 774 in der Stichprobe; lokale Auswertung des Rohdaten-Caches 16.11.2026: 151 von 1.610
Vorlagen), meist `VO/NNNN/JJ/1-A`, daneben `…/1-Neuf.`, `…/Neuf.`, `…/1-Erg.`, `…/1-A Neuf.` und Schreibvarianten
(`-A`, ` - A`, `/A-1`, `-A/1`, `\\1-A`, `1A`, `1. Neuf`, `/I-A`, fehlender Schrägstrich vor der Nummer).

Belegt ist nur die gemeinsame Grundnummer. Die Bedeutung der Kürzel ist in der Quelle nicht dokumentiert und gilt hier
als Annahme (KUERZEL): „A“ trägt fast immer die Vorlagenart „Antwort auf Anfragen“, die Vorlage mit der Grundnummer
meist eine „Große Anfrage“; „Neuf.“ und „Erg.“ deuten auf Neufassung und Ergänzung. Die Zahl vor dem Kürzel ist fast
immer 1, einmal 2 (zweite Ergänzung derselben Grundnummer): vermutlich eine laufende Nummer, ebenfalls nicht belegt.

Die Zuordnung (`zuordnung`) verbindet eine Vorlage mit Zusatz nur dann mit der Vorlage der Grundnummer, wenn diese
genau einmal vorhanden ist und der Zusatz nur bekannte Kürzel enthält. In der Datenbank steht sie als abgeleitete
Verknüpfung (`paper_relation.method` = „referenz“, `derived` = 1); Verknüpfungen aus OParl (`superordinatedPaper`,
`subordinatedPaper`) haben Vorrang (pipeline/build.py). Wuppertaler Ergänzung, in Bonn und Köln nicht vorhanden.
"""
import re
from dataclasses import dataclass

METHODE = "referenz"
HINWEIS = "aus der Referenz abgeleitet"

# Kürzel → kanonische Schreibweise; Bedeutung nur als Annahme (nicht in der Quelle dokumentiert)
KUERZEL = {"A": "vermutlich Antwort", "Neuf.": "vermutlich Neufassung", "Erg.": "vermutlich Ergänzung"}
_KUERZEL_FORMEN = {"a": "A", "neuf": "Neuf.", "erg": "Erg."}
_ROEMISCH = {"i": 1, "ii": 2, "iii": 3}

# Grundnummer: VO / Nummer (1–4 Stellen) / Jahr (2 Stellen), Leerzeichen um die Schrägstriche geduldet
_GRUND = re.compile(r"^\s*VO\s*/\s*(\d{1,4})\s*/\s*(\d{2})(?!\d{2})(.*)$", re.IGNORECASE)
_TEIL = re.compile(r"\d+|[A-Za-zÄÖÜäöüß]+\.?")


@dataclass(frozen=True)
class Referenz:
    original: str
    basis: str                 # kanonisch, z. B. „VO/0010/20“
    nummern: tuple = ()        # Zahlen im Zusatz, in der Reihenfolge der Quelle
    kuerzel: tuple = ()        # bekannte Kürzel, kanonisch („A“, „Neuf.“, „Erg.“)
    unbekannt: tuple = ()      # weitere Teile des Zusatzes (z. B. „Öffentl.“)
    teile: tuple = ()          # alle Teile des Zusatzes, normalisiert, in der Reihenfolge der Quelle

    @property
    def hat_zusatz(self):
        return bool(self.teile)

    @property
    def zusatz(self):
        """Normalisierter Zusatz, z. B. „1-A“, „Neuf.“, „1-A-Neuf.“; leer ohne Zusatz."""
        return "-".join(self.teile)

    @property
    def kanonisch(self):
        return f"{self.basis}/{self.zusatz}" if self.teile else self.basis

    @property
    def nummer(self):
        return self.nummern[0] if self.nummern else None

    @property
    def zuordenbar(self):
        """Zusatz mit mindestens einem bekannten Kürzel und ohne unbekannte Teile."""
        return bool(self.kuerzel) and not self.unbekannt


def zerlege(reference):
    """`VO/NNNN/JJ` mit oder ohne Zusatz → Referenz; andere Formen (leer, anderes Schema) → None."""
    m = _GRUND.match(reference or "")
    if not m:
        return None
    nr, jahr, rest = m.groups()
    nummern, kuerzel, unbekannt, teile = [], [], [], []
    roh = _TEIL.findall(rest)
    for i, t in enumerate(roh):
        key = t.rstrip(".").lower()
        folgt_kuerzel = i + 1 < len(roh) and roh[i + 1].rstrip(".").lower() in _KUERZEL_FORMEN
        if t.isdigit():
            nummern.append(int(t))
            teile.append(str(int(t)))
        elif key in _KUERZEL_FORMEN:
            k = _KUERZEL_FORMEN[key]
            if k not in kuerzel:
                kuerzel.append(k)
            teile.append(k)
        elif key in _ROEMISCH and folgt_kuerzel:   # „/I-A“: römische Ziffer vor dem Kürzel als Nummer
            nummern.append(_ROEMISCH[key])
            teile.append(str(_ROEMISCH[key]))
        else:
            unbekannt.append(t)
            teile.append(t)
    return Referenz(reference, f"VO/{int(nr):04d}/{jahr}", tuple(nummern), tuple(kuerzel), tuple(unbekannt),
                    tuple(teile))


def zusatz_text(zusatz, kuerzel=()):
    """Anzeige des Zusatzes mit der Bedeutung der Kürzel als Annahme: „Zusatz „1-A“ (A: vermutlich Antwort)“."""
    if not zusatz:
        return ""
    annahmen = [f"{k}: {KUERZEL[k]}" for k in kuerzel if k in KUERZEL]
    return f"Zusatz „{zusatz}“" + (f" ({'; '.join(annahmen)})" if annahmen else "")


def hinweis(reference_der_zusatzvorlage):
    """Kennzeichnung einer abgeleiteten Verknüpfung für Seite, Feeds und Exporte, z. B.
    „aus der Referenz abgeleitet; Zusatz „1-A“ (A: vermutlich Antwort)“."""
    r = zerlege(reference_der_zusatzvorlage)
    return HINWEIS + (f"; {zusatz_text(r.zusatz, r.kuerzel)}" if r and r.hat_zusatz else "")


def zuordnung(papers):
    """Zusatzvorlage → Ausgangsvorlage für eine Menge von Vorlagen (dicts mit `id` und `reference`).

    Ziel ist die Vorlage mit der Grundnummer, nur wenn sie genau einmal vorkommt. Ausnahme: Trägt der Zusatz neben
    „Neuf.“ ein weiteres Kürzel (z. B. „1-A Neuf.“), ist das Ziel die Vorlage mit demselben Zusatz ohne „Neuf.“
    (z. B. „1-A“), falls sie genau einmal vorkommt; sonst die Grundnummer.
    Rückgabe: {id der Zusatzvorlage: {"parent", "basis", "zusatz", "kuerzel", "evidence"}}."""
    zerlegt = {}
    nach_form = {}
    for p in papers:
        r = zerlege(p.get("reference"))
        if r is None:
            continue
        zerlegt[p["id"]] = r
        nach_form.setdefault(r.kanonisch, []).append(p["id"])

    def eindeutig(form):
        ids = nach_form.get(form) or []
        return ids[0] if len(ids) == 1 else None

    out = {}
    for pid, r in zerlegt.items():
        if not r.hat_zusatz or not r.zuordenbar:
            continue
        ziel, ueber = None, r.basis
        if "Neuf." in r.kuerzel and len(r.kuerzel) > 1:
            ohne = [t for t in r.teile if t != "Neuf."]
            form = f"{r.basis}/{'-'.join(ohne)}"
            ziel = eindeutig(form)
            if ziel:
                ueber = form
        ziel = ziel or eindeutig(r.basis)
        if not ziel or ziel == pid:
            continue
        out[pid] = {"parent": ziel, "basis": ueber, "zusatz": r.zusatz, "kuerzel": r.kuerzel,
                    "evidence": f"{HINWEIS}: {r.original.strip()} → {ueber}; {zusatz_text(r.zusatz, r.kuerzel)}"}
    return out
