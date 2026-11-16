"""Kuratierte Ortsliste: Objekte mit Stadtbezug ohne Adresse (CLAUDE.md 5.2, Phase 3 vorab, Freigabe 16.11.2026).

Die Liste (`pipeline/orte_kuratiert.tsv`) nennt je Objekt Name, Schreibvarianten, Art, Art der Verortung, Quartiere,
Stadtbezirke, Geometrie und einen Beleg. Aufgenommen sind nur Objekte, die der Auftrag nennt (Schwebebahn,
Nordbahntrasse, Döppersberg); Talsperren und Schwebebahnstationen kommen erst mit Namen **und** Quelle hinzu. Quartiere,
Stadtbezirke und Geometrie stehen bis nach Messstufe G auf „offen“: Sie werden dann aus den Geodaten der Stadt
abgeleitet, wo das nicht reicht aus OpenStreetMap (ODbL, getrennt gekennzeichnet, CLAUDE.md 3.2). Nichts davon wird
geschätzt.

Arten der Verortung:
- „punkt“ und „flaeche“: ein Objekt an einem Ort; Verortung in seinem Quartier bzw. seinen Quartieren.
- „linie“: langes Objekt über mehrere Quartiere; je Quartier eine Zeile mit niedriger Konfidenz.
- „stadtweit“: das Objekt als Ganzes hat keinen einzelnen Ort (z. B. die Schwebebahn); erkannt und im Audit vermerkt,
  aber nicht verortet.

Abgleich (Ortsliste.treffer): Name und Varianten ohne Unterschied der Groß- und Kleinschreibung, längster Treffer zuerst;
vor dem Namen darf kein Buchstabe stehen, dahinter schon (**Annahme**: Zusammensetzungen wie „Schwebebahnstation“ oder
„Nordbahntrassen-Brücke“ meinen das Objekt). Verortung (Ortsliste.verorte): Zeilen im Format von
ortsnamen.Verzeichnis.verorte; ohne Quartiere bleibt es beim Vermerk „Geometrie offen“.
"""
import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DATEI = Path(__file__).with_name("orte_kuratiert.tsv")
OFFEN = "offen"
VERORTUNG = {"punkt", "flaeche", "linie", "stadtweit"}
METHODE = "ortsliste"


@dataclass
class Ort:
    name: str
    varianten: tuple = ()
    art: str = ""
    verortung: str = "punkt"
    quartiere: tuple = ()        # leer = offen
    stadtbezirke: tuple = ()
    beleg: str = ""
    namen: tuple = field(init=False)

    def __post_init__(self):
        if self.verortung not in VERORTUNG:
            raise ValueError(f"unbekannte Verortung {self.verortung!r} bei {self.name}")
        if not self.beleg:
            raise ValueError(f"Eintrag ohne Beleg: {self.name}")
        self.namen = (self.name,) + tuple(v for v in self.varianten if v)


def _liste(wert):
    wert = (wert or "").strip()
    return () if not wert or wert == OFFEN else tuple(t.strip() for t in wert.split("|") if t.strip())


def laden(pfad=DATEI):
    with open(pfad, encoding="utf-8") as f:
        return [Ort(name=z["name"].strip(), varianten=_liste(z.get("varianten")), art=z.get("art", "").strip(),
                    verortung=z.get("verortung", "").strip(), quartiere=_liste(z.get("quartiere")),
                    stadtbezirke=_liste(z.get("stadtbezirke")), beleg=z.get("beleg", "").strip())
                for z in csv.DictReader(f, delimiter="\t") if (z.get("name") or "").strip()]


class Ortsliste:
    def __init__(self, orte=None):
        self.orte = laden() if orte is None else list(orte)
        paare = sorted(((n, o) for o in self.orte for n in o.namen), key=lambda p: -len(p[0]))
        self._muster = [(re.compile(r"(?<![^\W\d_])" + re.escape(unicodedata.normalize("NFC", n)), re.I), n, o)
                        for n, o in paare]

    def treffer(self, text):
        """[(Ort, Fundstelle, Anfang, Ende)] in Textreihenfolge; längere Namen zuerst, Überlappungen entfallen."""
        text = unicodedata.normalize("NFC", text or "")
        belegt, out = [], []
        for rx, _, ort in self._muster:
            for m in rx.finditer(text):
                if any(m.start() < e and a < m.end() for a, e in belegt):
                    continue
                belegt.append((m.start(), m.end()))
                out.append((ort, m.group(0), m.start(), m.end()))
        return sorted(out, key=lambda t: t[2])

    def verorte(self, text, *, source_object=None):
        """(Zeilen, Vermerke): Zeilen wie ortsnamen.Verzeichnis.verorte (level „objekt“, je Quartier eine Zeile);
        Vermerke für das Audit bei stadtweiten Objekten und offener Geometrie."""
        zeilen, vermerke, gesehen = [], [], set()
        for ort, fund, _, _ in self.treffer(text):
            if ort.name in gesehen:
                continue
            gesehen.add(ort.name)
            if ort.verortung == "stadtweit":
                vermerke.append((ort.name, "stadtweit, nicht verortet"))
                continue
            if not ort.quartiere:
                vermerke.append((ort.name, "Geometrie offen (nach Messstufe G)"))
                continue
            conf = "niedrig" if ort.verortung == "linie" or len(ort.quartiere) > 1 else "mittel"
            bezirke = ort.stadtbezirke if len(ort.stadtbezirke) == len(ort.quartiere) else (None,) * len(ort.quartiere)
            for q, bz in zip(ort.quartiere, bezirke):
                zeilen.append({"level": "objekt", "name": ort.name, "ortsteil": q, "bezirk": bz, "lon": None,
                               "lat": None, "method": METHODE, "confidence": conf, "evidence": fund,
                               "source": "orte_kuratiert", "source_object": source_object})
        return zeilen, vermerke
