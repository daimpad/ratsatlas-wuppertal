"""Seite haushalt/ für Wuppertal (Zusatzthema `haushalt`; Plan vom 17.11.2026, CLAUDE.md 9).

Daten: data/haushalt/produktbereiche.tsv und bezirke.tsv (pipeline/haushalt_wuppertal.py, Band 1 des Haushaltsplans
2026/2027, je Betrag mit Seite) und data/haushalt/massnahmen.geojson (verortete Maßnahmen der Bezirksvertretungen).
Aufbau nach der Bonner Seite (pipeline/haushaltsseite.py; Treemap, Farbstufen, Auswahl ohne Skript), deren Bausteine
hier wiederverwendet werden; abweichend für den gemeinsamen Kern:
- Ansichten: Ansatz 2026, Ansatz 2027 und Ergebnis 2024 (Entscheidung 17.11.2026), ohne Finanzplanung 2028–2030.
- Keine Ebenen 2 und 3 (Produktgruppen aus Band 2 noch nicht übernommen), keine Werte je Einwohner (keine
  Bevölkerungsquelle vereinbart), keine Verweise auf Themenseiten.
- Neu: Abschnitt „Bezirksvertretungen“ aus Anlage 9 (Fallgruppen 1–3) mit den Maßnahmen und ihrem abgeleiteten Ort.
Ausgaben im Plan sind negativ gedruckt; die Treemap zeigt ihren Betrag (positiv), das Ergebnis behält sein Vorzeichen.
"""
import csv
import json
import re
from collections import defaultdict
from html import escape

from . import config
from . import haushaltsseite as bonn
from .dossier import _mio

PFAD = "haushalt/"
DATEN = config.ROOT / "data" / "haushalt"
ANSICHTEN = [("plan", 2026, "Ansatz 2026", "Ansatz 2026"), ("plan", 2027, "Ansatz 2027", "Ansatz 2027"),
             ("ist", 2024, "Ergebnis 2024", "Ergebnis 2024")]
FALLGRUPPEN = {
    "1": ("Mittel, über die die Bezirksvertretung allein entscheidet",
          "Verfügungsmittel („Freie Mittel“) und anteilige Unterhaltungspauschale (§ 37 Abs. 1 und 3 GO NRW)"),
    "2": ("Ansätze, über die die Bezirksvertretung auf Vorschlag der Verwaltung entscheidet",
          "z. B. Schulinventar der Grundschulen, Schulwegsicherung, Zuschüsse an Sportvereine, Unterhaltung von "
          "Sportplätzen, Straßen, Wegen und Plätzen"),
    "3": ("Maßnahmen im Stadtbezirk",
          "Maßnahmen, die dem Stadtbezirk zuordenbar sind; die Bezirksvertretung wird beteiligt (§ 37 Abs. 5 GO NRW)"),
}
NAMENSNENNUNG = "Quelle: Stadt Wuppertal, Haushaltsplan 2026/2027, Band 1"


def _lesen(name):
    pfad = DATEN / name
    if not pfad.exists():
        return []
    with open(pfad, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def daten():
    """Daten im Format der Bonner Seite (produktbereiche, ansichten) und die bezirksbezogenen Zeilen; None ohne Daten."""
    rows = _lesen("produktbereiche.tsv")
    if not rows:
        return None
    stand = json.loads((DATEN / "STAND.json").read_text(encoding="utf-8"))
    wert = {(r["produktbereich"], int(r["zeile"]), r["spalte"]): (int(r["betrag_eur"]), int(r["seite"])) for r in rows}
    namen = {r["produktbereich"]: r["name"] for r in rows if r["produktbereich"] != "Gesamt"}

    def reihe(pb, zeile, vorzeichen=1):
        out = {"plan": {}, "ist": {}}
        for art, jahr, spalte, _ in ANSICHTEN:
            b, s = wert[(pb, zeile, spalte)]
            out[art][jahr] = {"betrag": vorzeichen * b, "seite": s}
        return out

    pbs = []
    for pb in sorted(namen):
        aufwand = reihe(pb, 17, -1)
        pbs.append({"pb": pb, "name": namen[pb], **aufwand, "ertrag": reihe(pb, 10), "ergebnis": reihe(pb, 18)})
    ansichten = [{"key": f"{art}{jahr}", "art": art, "jahr": jahr, "titel": titel} for art, jahr, titel, _ in ANSICHTEN]
    for a in ansichten:
        a["summe"] = sum(p[a["art"]][a["jahr"]]["betrag"] for p in pbs)
        a["ertrag"] = sum(p["ertrag"][a["art"]][a["jahr"]]["betrag"] for p in pbs)
        a["ergebnis"] = sum(p["ergebnis"][a["art"]][a["jahr"]]["betrag"] for p in pbs)
    gesamt = {(z, spalte): wert[("Gesamt", z, spalte)] for z in (10, 17, 18) for _, _, spalte, _ in ANSICHTEN
              if ("Gesamt", z, spalte) in wert}   # Gesamtergebnisplan: (Betrag, Seite) je Zeile und Spalte
    bezirke = defaultdict(list)
    for r in _lesen("bezirke.tsv"):
        bezirke[r["bezirksvertretung"]].append(r)
    massnahmen, meta = {}, {}
    pfad = DATEN / "massnahmen.geojson"
    if pfad.exists():
        geo = json.loads(pfad.read_text(encoding="utf-8"))
        meta = geo.get("meta", {})
        for f in geo["features"]:
            p = f["properties"]
            massnahmen[(p["bezirksvertretung"], p["massnahme"], p["art"])] = p
    return {"produktbereiche": pbs, "ansichten": ansichten, "stand": stand, "bezirke": dict(bezirke),
            "gesamt": gesamt, "massnahmen": massnahmen, "massnahmen_meta": meta}


def _seite(s):
    return f'<a href="../{escape(DATEN_QUELLE)}#page={s}">Band 1, S. {s}</a>' if DATEN_QUELLE else f"Band 1, S. {s}"


DATEN_QUELLE = None   # Link auf das PDF nur, wenn es mit der Seite ausgeliefert wird (bisher nicht)


def _zelle(x):
    return bonn._mio_v(x["betrag"]) if x else "–"


def tabelle_aufwand(d):
    ref = d["ansichten"][0]
    pbs = sorted(d["produktbereiche"], key=lambda p: (-p["plan"][2026]["betrag"], p["pb"]))
    spalten = [("ist", 2024, "Ergebnis 2024"), ("plan", 2026, "Ansatz 2026"), ("plan", 2027, "Ansatz 2027")]
    kopf = "".join(f'<th scope="col">{escape(t)}</th>' for *_, t in spalten)
    zeilen = "\n".join(
        f'        <tr id="pb-{p["pb"]}"><th scope="row">{escape(p["pb"])} {escape(p["name"])}</th>'
        + "".join(bonn._td(_zelle(p[art].get(j)), t) for art, j, t in spalten)
        + bonn._td(bonn._prozent(100 * p["plan"][2026]["betrag"] / ref["summe"]), "Anteil Ansatz 2026")
        + bonn._td(_seite(p["plan"][2026]["seite"]), "Fundstelle") + "</tr>"
        for p in pbs)
    summe = "".join(bonn._td(escape(_mio(sum(p[art][j]["betrag"] for p in pbs))), t) for art, j, t in spalten)
    return f"""      <table class="hh-tabelle">
        <caption>Ordentliche Aufwendungen je Produktbereich (Zeile 17 der Teilergebnispläne)</caption>
        <thead><tr><th scope="col">Produktbereich</th>{kopf}<th scope="col">Anteil Ansatz 2026</th><th scope="col">Fundstelle</th></tr></thead>
        <tbody>
{zeilen}
        <tr class="hh-summe"><th scope="row">Zusammen</th>{summe}<td>100 %</td><td>{_seite(d["gesamt"][(17, "Ansatz 2026")][1]) if (17, "Ansatz 2026") in d["gesamt"] else "–"} (Gesamtergebnisplan)</td></tr>
        </tbody>
      </table>"""


def tabelle_ergebnis(d):
    spalten = [("ist", 2024, "Ergebnis 2024"), ("plan", 2026, "Ansatz 2026"), ("plan", 2027, "Ansatz 2027")]
    kopf = "".join(f'<th scope="col">{escape(t)}</th>' for *_, t in spalten)
    pbs = sorted(d["produktbereiche"], key=lambda p: (p["ergebnis"]["plan"][2026]["betrag"], p["pb"]))
    zeilen = "\n".join(
        f'        <tr id="erg-{p["pb"]}"><th scope="row">{escape(p["pb"])} {escape(p["name"])}</th>'
        + "".join(bonn._td(f'{_zelle(p["ertrag"][art][j])}<br><small>Ergebnis {_zelle(p["ergebnis"][art][j])}</small>', t)
                  for art, j, t in spalten) + "</tr>"
        for p in pbs)
    return f"""      <table class="hh-tabelle">
        <caption>Ordentliche Erträge (Zeile 10) und ordentliches Ergebnis (Zeile 18) je Produktbereich</caption>
        <thead><tr><th scope="col">Produktbereich</th>{kopf}</tr></thead>
        <tbody>
{zeilen}
        </tbody>
      </table>"""


def anzeigename(erlaeuterung):
    """Erläuterung ohne Kennziffern der Quelle („2_“, „4204_“; Entscheidung des Auftraggebers 17.11.2026); die
    Daten (bezirke.tsv, massnahmen.geojson) behalten sie."""
    return re.sub(r"\s+", " ", re.sub(r"\b\d{1,4}_", "", erlaeuterung).replace("_", " ")).strip()


def _euro_v(x):
    return bonn._euro(x).replace("-", "−")


def bezirk(name, zeilen, massnahmen):
    jahre = ["Planung 2026", "Planung 2027", "Planung 2028", "Planung 2029", "Planung 2030"]
    je = defaultdict(lambda: {"art": None, "werte": {}, "seite": None, "fg": None})
    reihenfolge = []
    for r in zeilen:
        k = (r["fallgruppe"], r["art"], r["erlaeuterung"])
        if k not in je:
            reihenfolge.append(k)
        je[k]["werte"][r["spalte"]] = int(r["betrag_eur"])
        je[k]["seite"] = r["seite"]
    teile = []
    for fg in ("1", "2", "3"):
        ks = [k for k in reihenfolge if k[0] == fg]
        if not ks:
            continue
        titel, erklaerung = FALLGRUPPEN[fg]
        kopf = "".join(f'<th scope="col">{j.split()[1]}</th>' for j in jahre)
        def ort(k):
            m = massnahmen.get((name, k[2], k[1]))
            return (f'<br><small>Ort abgeleitet: {escape(m["ort"])} ({escape(m["quartier"] or m["stadtbezirk"] or "")})</small>'
                    if m else "")
        reihen = "\n".join(
            f'          <tr><th scope="row">{escape(anzeigename(k[2]))}<br><small>{escape(k[1])}</small>{ort(k) if fg == "3" else ""}</th>'
            + "".join(bonn._td(_euro_v(je[k]["werte"].get(j, 0)), j) for j in jahre)
            + bonn._td(f"S. {je[k]['seite']}", "Fundstelle") + "</tr>" for k in ks)
        summe2026 = sum(je[k]["werte"].get("Planung 2026", 0) for k in ks)
        teile.append(f"""        <h4>{escape(titel)} <small>({len(ks)} {"Zeile" if len(ks) == 1 else "Zeilen"}, 2026 zusammen {_euro_v(summe2026)})</small></h4>
        <p class="hint">{escape(erklaerung)}</p>
        <table class="hh-tabelle hh-bezirk">
          <thead><tr><th scope="col">Erläuterung und Art</th>{kopf}<th scope="col">Fundstelle</th></tr></thead>
          <tbody>
{reihen}
          </tbody>
        </table>""")
    anker = "bv-" + name.lower().replace(" ", "-")
    return f"""      <details class="hh-mehr" id="{escape(anker)}">
        <summary>Bezirksvertretung {escape(name)}</summary>
{chr(10).join(teile)}
      </details>"""


def body(d):
    a = d["ansichten"]
    wahl = "\n".join(
        f'      <input type="radio" name="hh-ansicht" id="hh-{x["key"]}" class="hh-radio"{" checked" if k == 0 else ""}>'
        f'<label for="hh-{x["key"]}">{escape(x["titel"])} <small>{escape(_mio(x["summe"]))}</small></label>'
        for k, x in enumerate(a))
    karten = "\n".join(f'          <figure class="hh-ansicht hh-v{k}">{bonn.treemap(d, x, "breit")}{bonn.treemap(d, x, "hoch")}</figure>'
                       for k, x in enumerate(a))
    zuschuss = f'{bonn.treemap_zuschuss(d, a[0], "breit")}{bonn.treemap_zuschuss(d, a[0], "hoch")}'
    g = d["gesamt"]
    erg26 = g.get((18, "Ansatz 2026"))   # ordentliches Ergebnis laut Gesamtergebnisplan (Betrag, Seite)
    bezirke = "\n".join(bezirk(n, d["bezirke"][n], d["massnahmen"]) for n in sorted(d["bezirke"]))
    mm = d.get("massnahmen_meta") or {}
    n_mass = len({(n, r["erlaeuterung"]) for n in d["bezirke"] for r in d["bezirke"][n] if r["fallgruppe"] == "3"})
    n_ort = mm.get("verortet", len({(p["bezirksvertretung"], p["massnahme"]) for p in d["massnahmen"].values()}))
    return f"""    <h1>Haushalt auf einen Blick</h1>
    <p class="lead">Wofür die Stadt Wuppertal Geld einplant und wie viel davon über die Bezirksvertretungen läuft – nach dem
      Haushaltsplan 2026/2027. Jede Zahl mit Fundstelle im Plan.</p>
    <details class="hh-mehr">
      <summary>So lesen Sie die Zahlen</summary>
      <dl>
        <dt>Ansatz</dt><dd>Im Haushaltsplan veranschlagter Betrag für ein Jahr; der Rat beschließt ihn mit der Haushaltssatzung.</dd>
        <dt>Ergebnis</dt><dd>Tatsächlich verbuchter Betrag eines abgeschlossenen Jahres (hier 2024).</dd>
        <dt>Produktbereich</dt><dd>Aufgabenfeld der Stadt, z. B. „Soziale Leistungen“; der Plan gliedert sich in 17 Produktbereiche.</dd>
        <dt>Ordentliche Aufwendungen</dt><dd>Laufende Ausgaben eines Jahres (Personal, Sachkosten, Transfers, Abschreibungen); ohne Investitionen.</dd>
        <dt>Zuschussbedarf</dt><dd>Was ein Produktbereich mehr ausgibt, als er selbst einnimmt (negatives ordentliches Ergebnis).</dd>
      </dl>
    </details>
    <h2>Ordentliche Aufwendungen je Produktbereich</h2>
    <div class="hh-wahl">
      <p class="hh-wahl-titel" id="hh-wahl-titel">Ansicht:</p>
{wahl}
      <div class="hh-karten">
        <div class="hh-haupt">
{karten}
          {bonn.legende("an den Aufwendungen der Ansicht")}
        </div>
      </div>
    </div>
{tabelle_aufwand(d)}
    <h2>Erträge und Ergebnis</h2>
    <p>Ordentliches Ergebnis aller Produktbereiche, Ansatz 2026: <strong>{escape(bonn._mio_v(erg26[0])) if erg26 else "–"}</strong>{f" ({_seite(erg26[1])})" if erg26 else ""}.
      Die Fläche zeigt den Zuschussbedarf je Produktbereich (Ansatz 2026); Bereiche mit Überschuss, etwa die allgemeine
      Finanzwirtschaft mit den Steuern, stehen nur in der Tabelle.</p>
    <figure class="hh-erg">{zuschuss}<figcaption>Zuschussbedarf je Produktbereich, Ansatz 2026</figcaption></figure>
{tabelle_ergebnis(d)}
    <h2 id="bezirke">Bezirksvertretungen</h2>
    <p>Der Haushaltsplan nennt je Bezirksvertretung die Mittel, über die sie entscheidet oder bei denen sie beteiligt wird
      (Anlage 9, bezirksbezogene Haushaltsansätze, Planung 2026–2030); Beträge wie im Plan: Ausgaben mit Minuszeichen, Einnahmen (z. B. Zuweisungen von Bund und Land) ohne; eine
      Maßnahme kann mehrere Zeilen haben.
      {n_ort} von {n_mass} Maßnahmen sind auch auf der
      Karte zu sehen (Ebene „Maßnahmen im Haushalt“); ihr Ort ist aus dem Namen der Maßnahme abgeleitet, nicht von der
      Stadt angegeben.</p>
{bezirke}
    <details class="hh-mehr">
      <summary>Quellen, Grenzen und Stand</summary>
      <ul>
        <li>{escape(NAMENSNENNUNG)} (Gesamtergebnisplan, Teilergebnispläne der Produktbereiche, Anlage 9); ausgelesen mit
          pdftotext, Prüfsummen je Spalte stimmen bis auf Rundung (höchstens 2 €).</li>
        <li>Lizenz: Der Haushaltsplan nennt keine Lizenz; als Teil der Haushaltssatzung vermutlich amtliches Werk
          (§ 5 UrhG) – eine Einschätzung, keine Auskunft der Stadt (offen).</li>
        <li>Nicht enthalten: Investitionen, Produktgruppen, Finanzplanung 2028–2030 (nur in den Tabellen der Bezirke), Werte je Einwohner.</li>
        <li>Band 2 (Teilpläne der Produktgruppen) beschriftet 2026 und 2027 abweichend als „Planung“; er wird noch nicht verwendet (offen).</li>
      </ul>
    </details>"""


def write(site, site_url, page):
    """Schreibt haushalt/index.html und haushalt/massnahmen.geojson; gibt den Pfad für die Sitemap zurück."""
    d = daten()
    if not d:
        return []
    out = site / PFAD / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    quelle = DATEN / "massnahmen.geojson"
    if quelle.exists():
        (site / PFAD / "massnahmen.geojson").write_bytes(quelle.read_bytes())
    out.write_text(page(site_url, PFAD, f"Haushalt auf einen Blick – {config.SEITENNAME}",
                        "Ordentliche Aufwendungen, Erträge und Ergebnis der Stadt Wuppertal je Produktbereich und die "
                        "Mittel der Bezirksvertretungen, aus dem Haushaltsplan 2026/2027 mit Fundstelle.", body(d), "../"),
                   encoding="utf-8")
    return [PFAD]
