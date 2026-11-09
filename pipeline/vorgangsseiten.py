"""Statische Seite je Vorgang (vorgang/<drucksache>/), damit Suchmaschinen einzelne Vorlagen finden.

Umfang (Entscheidungen des Auftraggebers 09.11.2026, Phase 0 „Verständlichkeit“, Abschnitt 4): dieselbe Regel wie die
Vorgangsfeeds (Vorlagen ab dem Vorjahr des Datenstands oder noch offen bzw. in Beratung), ohne Vorlagen aus der
Einwohnerschaft und ihre verbundenen Vorlagen. Der Export setzt dafür das Feld „seite“ (export.export_all); die Seite
der Karte zeigt denselben Link.

Je Seite: Titel (maskiert wie überall), Art, Datum, federführende Stelle, Einreichende, Stand mit Erklärung, Ort nur
mit Namen, Beratungsfolge mit dem Ergebnis wörtlich aus der Quelle, Bezüge, Links zu Karte, Original und PDF, Quellen.
Keine Erzeugungszeitpunkte und keine Kurzfassungen, damit sich der Branch deploy nur bei Inhaltsänderungen ändert."""
import json
from html import escape
from urllib.parse import quote

from . import begriffsseite, config, glossar
from .export import slug
from .gebietsseiten import _date

PFAD = "vorgang/"
ROOT = "../../"
TITEL_MAX = 90   # Zeichen des Vorlagentitels im <title>


def _vorlagen(base):
    """Alle Vorlagen der Gebietsdateien, je Drucksache einmal, mit dem Gebiet, in dem sie zuerst stehen (wie home in
    export.export_all: Ortsteile, Stadtbezirke, ohne Ortsbezug)."""
    index = json.loads((base / "index.json").read_text(encoding="utf-8"))
    dateien = [(f"ortsteil:{o['slug']}", base / "ortsteile" / f"{o['slug']}.json") for o in index["ortsteile"]]
    dateien += [(f"bezirk:{b['slug']}", base / "bezirke" / f"{b['slug']}.json") for b in index["bezirke"]]
    dateien += [(f"ohne:{j['jahr']}", base / "ohne-ortsbezug" / f"{j['jahr']}.json") for j in index["ohne_ortsbezug"]]
    alle, gebiet = {}, {}
    for key, datei in dateien:
        if not datei.exists():
            continue
        for p in json.loads(datei.read_text(encoding="utf-8"))["papers"]:
            if p["reference"] not in alle:
                alle[p["reference"]] = p
                gebiet[p["reference"]] = key
    return alle, gebiet, {o["name"]: o["slug"] for o in index["ortsteile"] if o.get("count")}


def lastmod(p):
    """Jüngstes Datum aus der Quelle (Vorlage, Beratung, Folgevorlage) – für die Sitemap, ohne Erzeugungszeitpunkt."""
    daten = [p.get("date")] + [s.get("date") for s in p.get("steps") or []] + [r.get("date") for r in p.get("subordinated") or []]
    return max((d for d in daten if d), default=None)


def _karte(key, ref):
    return f"{ROOT}?gebiet={quote(key, safe=':')}#{quote(ref)}"


def _orte(p, ortsteile):
    """Orte nur mit Namen (ohne Fundstelle); Ortsteile mit eigener Gebietsseite verlinkt."""
    namen, gesehen = [], set()
    for loc in p.get("locations") or []:
        teile = []
        if loc.get("level") == "bebauungsplan":
            continue   # eigene Zeile „Bebauungsplan“
        if loc.get("level") in ("strasse", "objekt", "punkt") and loc.get("name"):
            teile.append(escape(loc["name"]))
        if loc.get("ortsteil"):
            o = loc["ortsteil"]
            teile.append(f'<a href="{ROOT}ortsteil/{ortsteile[o]}/">{escape(o)}</a>' if o in ortsteile else escape(o))
        elif loc.get("stadtbezirk"):
            teile.append(f"Stadtbezirk {escape(loc['stadtbezirk'])}")
        text = ", ".join(teile)
        if text and text not in gesehen:
            gesehen.add(text)
            namen.append((text, loc.get("stage") != "A"))
    return namen


def _beratung(s):
    teile = [f'<span class="pb-folge-datum">{_date(s["date"]) if s.get("date") else "ohne Termin"}</span>',
             f"<strong>{escape(s['label'])}</strong>"]
    if s.get("role"):
        teile.append(f"({escape(s['role'])})")
    if s.get("result"):
        teile.append(f"– „{escape(s['result'])}“")
    elif s.get("status") == "nicht_öffentlich":
        teile.append("– nicht öffentlich")
    else:
        teile.append("– noch ohne Ergebnis")
    return "        <li>" + " ".join(teile) + "</li>"


def _bezug(r, seiten):
    ziel = (f'<a href="{ROOT}{PFAD}{slug(r["reference"])}/">{escape(r["reference"])}</a>' if r["reference"] in seiten
            else escape(r["reference"]))
    datum = f"{_date(r['date'])}, " if r.get("date") else ""
    return f"        <li>{ziel}: {escape(r.get('name') or '')} <small>({datum}{escape(r.get('paper_type') or '')})</small></li>"


def body(p, key, seiten, ortsteile):
    ref = p["reference"]
    zeile = lambda dt, dd: f"      <dt>{dt}</dt><dd>{dd}</dd>"
    angaben = [zeile("Vorlagennummer", escape(ref)), zeile("Art", escape(p["paper_type"] or "–")),
               zeile("Datum", _date(p.get("date")))]
    feder = [r for r in p.get("responsibility") or [] if r.get("kind") == "federfuehrend"]
    if feder:
        r = feder[0]
        text = escape(r["name"]) + (f" ({escape(r['label'])})" if r.get("label") and r["label"] != r["name"] else "")
        angaben.append(zeile("Federführend", text + (' <span class="pb-abgeleitet">abgeleitet</span>' if r.get("derived") else "")))
    elif p.get("amt"):
        angaben.append(zeile("Federführend", escape(p["amt"])))
    einreichende = [o for o in p.get("originators") or [] if o.get("actor") and o.get("actor_type") != "Verwaltung"]
    if einreichende:
        abgeleitet = any(o.get("derived") for o in einreichende)
        angaben.append(zeile("Eingereicht von", escape(", ".join(dict.fromkeys(o["actor"] for o in einreichende)))
                             + (' <span class="pb-abgeleitet">abgeleitet</span>' if abgeleitet else "")))
    stand = p.get("stand") or "–"
    angaben.append(zeile("Stand", f"<strong>{escape(stand)}</strong>"
                         + (f"<br><small>{escape(glossar.STAENDE[stand])}</small>" if stand in glossar.STAENDE else "")))
    orte = _orte(p, ortsteile)
    if orte:
        angaben.append(zeile("Ort", "; ".join(t for t, _ in orte)
                             + (' <span class="pb-abgeleitet">abgeleitet</span>' if any(a for _, a in orte) else "")))
    plaene = [x["nr"] for x in p.get("plans") or [] if x.get("nr")]
    if plaene:
        angaben.append(zeile("Bebauungsplan", escape(", ".join(dict.fromkeys(plaene)))))

    beratungen = [s for s in p.get("steps") or [] if s.get("typ") in ("beratung", "entscheidung")]
    folge = ("    <h2>Beratungsfolge</h2>\n      <ol class=\"pb-folge\">\n" + "\n".join(_beratung(s) for s in beratungen)
             + "\n      </ol>\n    <p class=\"meta\">Gremien und Termine laut Ratsinformationssystem, Ergebnisse wörtlich aus "
               "dem Ratsinformationssystem (OParl-API). Die Reihenfolge folgt den Terminen.</p>\n") if beratungen else (
        "    <h2>Beratungsfolge</h2>\n    <p>Für diese Vorlage ist keine Beratung in einem Gremium erfasst.</p>\n")
    bezuege = ""
    if p.get("superordinated"):
        bezuege += ("    <h2>Bezieht sich auf</h2>\n      <ul>\n" + "\n".join(_bezug(r, seiten) for r in p["superordinated"])
                    + "\n      </ul>\n")
    if p.get("subordinated"):
        bezuege += ("    <h2>Folgevorlagen</h2>\n      <ul>\n" + "\n".join(_bezug(r, seiten) for r in p["subordinated"])
                    + "\n      </ul>\n")
    knoepfe = [f'<a class="pb-knopf" href="{_karte(key, ref)}">Auf der Karte öffnen</a>']
    if p.get("web"):
        knoepfe.append(f'<a class="pb-knopf pb-knopf-leise" href="{escape(p["web"])}">Original im Ratsinformationssystem</a>')
    if p.get("main_file"):
        knoepfe.append(f'<a class="pb-knopf pb-knopf-leise" href="{escape(p["main_file"])}">Dokument (PDF)</a>')
    knoepfe.append(f'<a class="pb-knopf pb-knopf-leise" href="{ROOT}data/export/{config.STADT}/feeds/vorlagen/{slug(ref)}.xml" '
                   'type="application/atom+xml">Diesen Vorgang abonnieren</a>')
    begriffe = begriffsseite.akkordeon([p["paper_type"], stand, *(s.get("result") for s in beratungen)], ROOT)
    return f"""    <h1>{escape(p["name"] or ref)}</h1>
    <p class="lead">{escape(p["paper_type"] or "Vorlage")} {escape(ref)} aus dem Ratsinformationssystem der Stadt {escape(config.STADT_NAME)}.</p>
    <p class="pb-aktionen">{" ".join(knoepfe)}</p>
    <h2>Angaben</h2>
    <dl class="pb-angaben">
{chr(10).join(angaben)}
    </dl>
{folge}{bezuege}{begriffe}    <p class="meta">Quelle: OParl-API der Stadt {escape(config.STADT_NAME)} (Lizenz ungeklärt, Anfrage an die Stadt offen; Quellobjekt <a href="{escape(p["source_object"])}">{escape(p["source_object"])}</a>), mit Sitzungen und Ergebnissen. Mit „abgeleitet“ markierte Angaben sind erschlossen, etwa der Ort aus dem Titel; Fundstellen und die ganze Prozesslinie stehen im Vorgang auf der Karte. Maßgeblich ist das Original im Ratsinformationssystem.</p>"""


def _kurz(text):
    return text if len(text) <= TITEL_MAX else text[:TITEL_MAX].rsplit(" ", 1)[0] + " …"


def write(site, site_url, page):
    """Schreibt die Seiten je Vorgang; gibt [(Pfad relativ zu site_url, lastmod)] für die Sitemap zurück."""
    base = site / "data" / "export" / config.STADT
    if not (base / "index.json").exists():
        return []
    alle, gebiet, ortsteile = _vorlagen(base)
    seiten = {ref for ref, p in alle.items() if p.get("seite")}
    out = []
    for ref in sorted(seiten):
        p = alle[ref]
        pfad = f"{PFAD}{slug(ref)}/"
        art = p["paper_type"] or "Vorlage"
        beschreibung = (f"{art} {ref} vom {_date(p.get('date'))}"
                        + (f", federführend {p['amt']}" if p.get("amt") else "")
                        + f". Stand: {p.get('stand') or '–'}. Beratungsfolge, Ort und Quellen im {config.SEITENNAME}.")
        datei = site / pfad / "index.html"
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(page(site_url, pfad, f"{ref} {_kurz(p['name'] or '')} – {config.SEITENNAME}", beschreibung,
                              body(p, gebiet[ref], seiten, ortsteile), ROOT), encoding="utf-8")
        out.append((pfad, lastmod(p)))
    print(f"Seiten je Vorgang: {len(out)}")
    return out
