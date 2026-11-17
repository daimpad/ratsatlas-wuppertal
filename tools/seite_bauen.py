"""Fertige Seite zusammenstellen, wie sie .github/workflows/pages.yml veröffentlicht: site/ (+ Daten, falls vorhanden)
→ _site/, dann Auffindbarkeit (pipeline/seo.py) und .htaccess aus deploy/htaccess.

Aufruf: python3 tools/seite_bauen.py [ziel]   (Vorgabe: _site; nicht versioniert; SITE_URL aus der Umgebung)
Danach z. B.: python3 -m http.server -d _site 8000

Struktur nach ratsatlas-koeln (origin/main, tools/seite_bauen.py), ohne Dateigrößen im Menü „Daten“ (ohne Daten gibt
es nichts herunterzuladen).

Graue Kartenkacheln (Entscheidung 17.11.2026, CLAUDE.md 9; wie Köln): Liegen sie in _kacheln/kacheln/ (Branch kacheln,
von pages.yml geholt, erzeugt von kacheln.yml), kommen sie nach kacheln/ in die Seite, und die Datenschutzerklärung
sagt, dass die graue Karte vom Server dieser Seite kommt (MIT_KACHELN). Ohne sie bleibt der Hinweis auf
tile.openstreetmap.org auch für die graue Karte (app.js fällt dann auf OSM-Kacheln mit Graufilter zurück). Ohne Rufe an Server, ohne Zeitstempel (reproduzierbar).

Ohne Daten (data/export/wuppertal/index.json fehlt; CLAUDE.md 9, 10.11.2026): Die Seite zeigt „Daten nicht
verfügbar“ und wird nicht indexiert: noindex in jeder HTML-Seite, X-Robots-Tag in .htaccess, robots.txt ohne Sitemap,
keine Sitemaps. Kein „Disallow: /“, damit Suchmaschinen das noindex lesen können. Die Datenschutzerklärung sagt, dass
noch keine Ratsdaten gezeigt werden, und der noscript-Block verlinkt keine Dateien, die erst mit Daten entstehen
(OHNE_DATEN). Mit Daten entfällt das von selbst.

Gebietskarte ohne Ratsdaten (CLAUDE.md 9, 11.11., 13.11. und 17.11.2026): Nur mit ausdrücklicher Freigabe (Umgebung
RATSATLAS_GEBIETSKARTE=ja, in pages.yml gesetzt seit 17.11.2026, oder main(..., gebietskarte=True)). Liegen dann keine
Ratsdaten vor, aber die Flächen der Stadtbezirke und Quartiere (config.STADTBEZIRKE, config.ORTSTEILE; dazu
config.BPLAN und config.BPLAN_LAUFEND, falls vorhanden; übernommen mit tools/geodaten_uebernehmen.py), schreibt das
Skript sie wie der Gesamtexport mit pipeline/flaechen.write nach data/export/wuppertal/flaechen/ (Quartiere und
Stadtbezirke vereinfacht und so gekennzeichnet, Bebauungspläne unverändert, CC BY-ND 4.0). app.js zeigt dann die
Gebiete mit Namen und dem Hinweis „Ratsdaten folgen“ statt „Daten nicht verfügbar“. Die Gebietskarte wird indexiert
(Entscheidung 17.11.2026): kein noindex, kein X-Robots-Tag, robots.txt und Sitemaps aus pipeline/seo.py. Fehlt eine
der beiden Dateien, bleibt alles wie ohne Daten (noindex). Die Flächen müssen die Eigenschaften des Bonner Modells
tragen (GEBIETE_FELDER; bei Bebauungsplänen genügt die Plannummer der Quelle, VERFAHREN), sonst bricht der Bau ab.

Abgeschaltete Zusatzthemen (config.ZUSATZTHEMEN; CLAUDE.md 5.4, 9): ihre Module werden nicht ausgeliefert. Ohne
Ratsassistent erlaubt die CSP in index.html keine Verbindungen zu dessen Anbietern und zu localhost, und die
Datenschutzerklärung nennt ihn nicht. Am Ende prüft das Skript, dass die Seite vollständig ist.

version.txt: Commit von main, aus dem die Seite gebaut ist (GITHUB_SHA, sonst git rev-parse HEAD, sonst „lokal“); die
Live-Prüfung (tools/live_pruefen.py) vergleicht sie mit dem Kopf des Branches deploy."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import config, seo  # noqa: E402

ROBOTS_META = re.compile(r'<meta name="robots" content="[^"]*">')
CHARSET = '<meta charset="utf-8">'
NOINDEX = '<meta name="robots" content="noindex">'
# Module der Zusatzthemen, die app.js bzw. die Seiten der Pipeline nur bei Freigabe laden
MODULE = {"chat": "chat", "haushalt": "haushalt.js", "themenseiten": "thema.js", "technik": "technik.js",
          "soll": "prozesse.js", "mitmachen": "beteiligung.js"}
# Ratsassistent abgeschaltet: diese Stellen in index.html und datenschutz.html werden ersetzt (genau einmal vorhanden)
OHNE_CHAT = {
    "index.html": [
        ("connect-src 'self' https://api.anthropic.com https://api.mistral.ai https://openrouter.ai http://localhost:* "
         "http://127.0.0.1:*;", "connect-src 'self';"),
        ("Verbindungen nur zu den Daten der Seite, den unterstützten Anbietern des Ratsassistenten und lokalen Modellen.",
         "Verbindungen nur zu den Daten der Seite (Ratsassistent abgeschaltet)."),
    ],
    "datenschutz.html": [
        (re.compile(r"\n\n    <h2>Ratsassistent \(KI\)</h2>\n.*?(?=\n\n    <h2>)", re.S), ""),
        (re.compile(r"\n      <li><code>ris-assistent-[^\n]*</li>"), ""),
        (re.compile(r"Im Sitzungsspeicher liegt nur auf Wunsch der Schlüssel des Ratsassistenten \([^)]*\)\. "), ""),
    ],
}
# Ohne Daten: Hinweis in der Datenschutzerklärung, dass noch keine Ratsdaten gezeigt werden, und keine Links auf
# Dateien, die erst mit Daten entstehen, im noscript-Block (app.js blendet sie mit data-mit-daten aus); entfällt mit Daten.
# Mit Gebietskarte heißt der Hinweis in der Seite „Ratsdaten folgen“ (app.js), sonst „Daten nicht verfügbar“


def ohne_daten(gebietskarte=False):
    hinweis = "Ratsdaten folgen" if gebietskarte else "Daten nicht verfügbar"
    noscript = ("<p>Noch liegen keine Ratsdaten vor; die Karte zeigt bisher nur die Gebiete der Stadt. " if gebietskarte
                else "<p>Noch liegen keine Daten vor. ")
    return {
        "datenschutz.html": [
            ("<h2>Personenbezogene Angaben in den Ratsdaten</h2>\n    <p>",
             "<h2>Personenbezogene Angaben in den Ratsdaten</h2>\n    <p>Derzeit zeigt die Seite noch keine Ratsdaten "
             f"(Hinweis „{hinweis}“). Dieser Abschnitt gilt, sobald Daten vorliegen.</p>\n    <p>"),
        ],
        "index.html": [
            ('<p>Die Daten gibt es auch ohne Karte: <a href="data/export/ratsatlas-wuppertal-export.zip">Datenpaket (Zip)'
             '</a> · <a href="gebiete/">Vorlagen nach Gebiet</a> · <a href="data/export/wuppertal/vorlagen.geojson">GeoJSON'
             '</a> · ', noscript),
        ],
    }


OHNE_DATEN = ohne_daten()
# Eigene graue Kacheln: Ort im Checkout (pages.yml) und die Stellen der Datenschutzerklärung, die dann zutreffen
KACHELN = ROOT / "_kacheln" / "kacheln"
MIT_KACHELN = {
    "datenschutz.html": [
        ("<p>Schrift, Programmbibliotheken und Daten liegen auf dem Server dieser Seite. Die Bilder der Karte (Kacheln) "
         "lädt Ihr Browser von <strong>tile.openstreetmap.org</strong>, betrieben von der OpenStreetMap Foundation "
         "(Vereinigtes Königreich): immer, wenn Sie „Farbige Karte“ wählen, und für die graue Karte, solange auf dem "
         "Server dieser Seite keine eigenen grauen Kacheln liegen (derzeit ist das so).",
         "<p>Schrift, Programmbibliotheken, Daten und die Bilder der grauen Karte (Kacheln, erzeugt aus "
         "OpenStreetMap-Daten) liegen auf dem Server dieser Seite. Nur wenn Sie „Farbige Karte“ wählen, lädt Ihr "
         "Browser die Kacheln von <strong>tile.openstreetmap.org</strong>, betrieben von der OpenStreetMap Foundation "
         "(Vereinigtes Königreich)."),
        ("<p>Vermeiden lässt sich das derzeit nur, indem Sie die Startseite mit der Karte nicht aufrufen. Die übrigen "
         "Seiten",
         "<p>Vermeiden lässt sich das, indem Sie bei der grauen Karte bleiben (Voreinstellung). Sollten die grauen "
         "Kacheln einmal fehlen, zeigt die Seite ersatzweise die Kacheln von OpenStreetMap in Grau. Die übrigen Seiten"),
    ],
}
# Gebietskarte: Pflichteigenschaften je Fläche (Bonner Modell, wie pipeline/export.py und site/app.js sie lesen) und die
# Dateien, die flaechen.write daraus schreibt (relativ zur fertigen Seite)
# Bebauungspläne: Bonner Modell „name“ oder die Plannummer der Wuppertaler Quelle (Datei unverändert, CC BY-ND 4.0);
# ein Tupel nennt gleichwertige Felder, von denen eines Text tragen muss
GEBIETE_FELDER = {"ORTSTEILE": ("ortsteil_bez", "bezirk_bez"), "STADTBEZIRKE": ("bezirk_bez",),
                  "BPLAN": (("name", "VERFAHREN"),), "BPLAN_LAUFEND": (("name", "VERFAHREN"),)}
GEBIETE_DATEIEN = {"ORTSTEILE": "ortsteile.json", "STADTBEZIRKE": "bezirke.json", "BPLAN": "bebauungsplaene.json",
                   "BPLAN_LAUFEND": "bebauungsplaene_laufend.json"}
FREIWILLIG = ("BPLAN", "BPLAN_LAUFEND")
# Mindestinhalt jeder gebauten Seite (sonst bricht der Bau ab, statt eine leere Seite auszuliefern)
PFLICHT = ("index.html", "app.js", "style.css", "datenschutz.html", "404.html", "robots.txt", ".htaccess",
           "data/LICENSE-DATA.md", "version.txt", "vorschaubild.jpg")
# Vorschaubild für geteilte Links (tools/vorschaubild.mjs): in index.html absolut auf SITE_URL, wie Canonical
VORSCHAUBILD = "vorschaubild.jpg"
BILD_META = ('<meta property="og:image" content="{u}">', '<meta name="twitter:image" content="{u}">',
             '<meta name="twitter:card" content="summary_large_image">')
COMMIT = re.compile(r"[0-9a-f]{40}")
X_ROBOTS = ('\n# Ohne Daten nicht indexieren (tools/seite_bauen.py; entfällt, sobald Daten vorliegen)\n'
            '<IfModule mod_headers.c>\n  Header always set X-Robots-Tag "noindex"\n</IfModule>\n')


def mit_daten():
    return (config.EXPORT / config.STADT / "index.json").is_file()


def gebietskarte_freigegeben():
    """Schalter der Gebietskarte: nur RATSATLAS_GEBIETSKARTE=ja (z. B. aus einer Repository-Variable in pages.yml)."""
    return os.environ.get("RATSATLAS_GEBIETSKARTE", "").strip() == "ja"


def mit_gebieten():
    """Gebietskarte möglich: Flächen der Stadtbezirke und der Quartiere liegen vor (Bebauungspläne sind freiwillig)."""
    return config.STADTBEZIRKE.is_file() and config.ORTSTEILE.is_file()


def dateigroessen(ordner, namen):
    """Größe der geschriebenen Flächen in Bytes, gelesen von der Datei (flaechen.write zählt Zeichen; Umlaute und
    Gedankenstriche belegen in UTF-8 mehr als ein Byte); Reihenfolge wie `namen`."""
    return {n: (ordner / f"{n}.json").stat().st_size for n in namen}


def gebiete_pruefen():
    """Jede Fläche trägt die Eigenschaften des Bonner Modells (GEBIETE_FELDER) mit Text und hat eine Geometrie; sonst
    Abbruch, statt eine Karte mit namenlosen Flächen auszuliefern (Feldnamen der Quelle erst nach Messstufe G)."""
    for name, felder in GEBIETE_FELDER.items():
        pfad = getattr(config, name)
        if name in FREIWILLIG and not pfad.is_file():
            continue
        feats = json.loads(pfad.read_text(encoding="utf-8")).get("features") or []
        if not feats:
            raise SystemExit(f"Gebietskarte: {pfad.name} ohne Flächen")
        for i, f in enumerate(feats):
            props = f.get("properties") or {}
            fehlt = ["/".join(k) if isinstance(k, tuple) else k for k in felder
                     if not any(str(props.get(x) if props.get(x) is not None else "").strip()
                                for x in (k if isinstance(k, tuple) else (k,)))]
            if fehlt or not f.get("geometry"):
                raise SystemExit(f"Gebietskarte: {pfad.name}, Fläche {i + 1} ohne "
                                 f"{', '.join(fehlt) if fehlt else 'Geometrie'} (tools/geodaten_uebernehmen.py)")


def stand():
    """Commit von main für version.txt: GITHUB_SHA (Workflow), sonst git rev-parse HEAD, sonst „lokal“."""
    sha = os.environ.get("GITHUB_SHA", "").strip()
    if COMMIT.fullmatch(sha):
        return sha
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and COMMIT.fullmatch(r.stdout.strip()):
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "lokal"


def noindex(html):
    """Vorhandenes meta robots auf noindex setzen, sonst direkt nach <meta charset="utf-8"> einfügen."""
    if ROBOTS_META.search(html):
        return ROBOTS_META.sub(NOINDEX, html)
    if CHARSET not in html:
        raise ValueError("Seite ohne <meta charset=\"utf-8\">: noindex lässt sich nicht einfügen")
    return html.replace(CHARSET, f"{CHARSET}\n  {NOINDEX}", 1)


def ersetzen(text, alt, neu, wo):
    """alt (Text oder Muster) genau einmal ersetzen; sonst Abbruch, damit eine geänderte Vorlage auffällt."""
    if isinstance(alt, str):
        if text.count(alt) != 1:
            raise ValueError(f"{wo}: Stelle nicht genau einmal gefunden: {alt[:60]}")
        return text.replace(alt, neu)
    text, n = alt.subn(neu, text)
    if n < 1:
        raise ValueError(f"{wo}: Muster nicht gefunden: {alt.pattern[:60]}")
    return text


def pruefen(ziel, gebietskarte=False):
    pflicht = PFLICHT
    if gebietskarte:
        flaechen = f"data/export/{config.STADT}/flaechen/"
        pflicht += tuple(flaechen + GEBIETE_DATEIEN[n] for n in ("ORTSTEILE", "STADTBEZIRKE"))
        if (ziel / "data" / "export" / config.STADT / "index.json").exists():
            raise SystemExit("Gebietskarte mit index.json: Ratsdaten dürfen hier nicht ausgeliefert werden")
    fehlt = [d for d in pflicht if not (ziel / d).is_file() or not (ziel / d).stat().st_size]
    if fehlt:
        raise SystemExit(f"Seite unvollständig, es fehlt: {', '.join(fehlt)}")
    html = (ziel / "index.html").read_text(encoding="utf-8")
    if "<title>Ratsatlas Wuppertal" not in html:
        raise SystemExit("index.html ohne Titel „Ratsatlas Wuppertal“")
    canonical = re.search(r'<link rel="canonical" href="([^"]+)">', html)
    if not canonical:
        raise SystemExit("index.html ohne Canonical")
    fehlt = [m for m in BILD_META if m.format(u=canonical.group(1) + VORSCHAUBILD) not in html]
    if fehlt:
        raise SystemExit(f"index.html: Vorschaubild nicht absolut eingebunden: {', '.join(fehlt)}")


def main(ziel=ROOT / "_site", site_url=None, gebietskarte=None, kacheln_quelle=None):
    ziel = Path(ziel)
    daten = mit_daten()
    freigabe = gebietskarte_freigegeben() if gebietskarte is None else gebietskarte
    gebietskarte = freigabe and not daten and mit_gebieten()
    if not freigabe and not daten and mit_gebieten():
        print("Flächen vorhanden, Gebietskarte nicht freigegeben (RATSATLAS_GEBIETSKARTE): Seite wie ohne Daten")
    if freigabe and not daten and not mit_gebieten():
        fehlt = [p.as_posix() for p in (config.STADTBEZIRKE, config.ORTSTEILE) if not p.is_file()]
        print(f"Gebietskarte freigegeben, aber Flächen fehlen ({', '.join(fehlt)}): Seite wie ohne Daten")
    if gebietskarte:
        gebiete_pruefen()
    kacheln = kacheln_quelle if kacheln_quelle is not None else KACHELN
    mit_kacheln = (Path(kacheln) / "stand.json").is_file()
    shutil.rmtree(ziel, ignore_errors=True)
    shutil.copytree(ROOT / "site", ziel)
    for thema, modul in MODULE.items():
        if not config.ZUSATZTHEMEN.get(thema):
            pfad = ziel / modul
            if pfad.is_dir():
                shutil.rmtree(pfad)
            else:
                pfad.unlink()
    (ziel / "data").mkdir()
    shutil.copy(ROOT / "data" / "LICENSE-DATA.md", ziel / "data" / "LICENSE-DATA.md")
    if daten:
        shutil.copytree(config.EXPORT, ziel / "data" / "export")
        (ziel / "data" / "geo").mkdir()
        for f in sorted((ROOT / "data" / "geo").glob("*.geojson")):
            shutil.copy(f, ziel / "data" / "geo" / f.name)
    if mit_kacheln:
        shutil.copytree(kacheln, ziel / "kacheln")
        for name, stellen in MIT_KACHELN.items():
            text = (ziel / name).read_text(encoding="utf-8")
            for alt, neu in stellen:
                text = ersetzen(text, alt, neu, name)
            (ziel / name).write_text(text, encoding="utf-8")
    groessen = {}
    if gebietskarte:
        from pipeline import flaechen                 # erst hier: shapely nur, wenn Flächen vorliegen
        ordner = ziel / "data" / "export" / config.STADT
        groessen = dateigroessen(ordner / "flaechen", flaechen.write(ordner))
    seo.write(ziel, site_url)                         # setzt SITE_URL in Canonical und Vorschaubild
    if not config.ZUSATZTHEMEN.get("chat"):
        for name, stellen in OHNE_CHAT.items():
            text = (ziel / name).read_text(encoding="utf-8")
            for alt, neu in stellen:
                text = ersetzen(text, alt, neu, name)
            (ziel / name).write_text(text, encoding="utf-8")
    htaccess = (ROOT / "deploy" / "htaccess").read_text(encoding="utf-8")
    if not daten:
        for name, stellen in ohne_daten(gebietskarte).items():
            text = (ziel / name).read_text(encoding="utf-8")
            for alt, neu in stellen:
                text = ersetzen(text, alt, neu, name)
            (ziel / name).write_text(text, encoding="utf-8")
    if not daten and not gebietskarte:               # Gebietskarte wird indexiert (Entscheidung 17.11.2026)
        for seite in sorted(ziel.rglob("*.html")):
            seite.write_text(noindex(seite.read_text(encoding="utf-8")), encoding="utf-8")
        (ziel / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        for f in ziel.glob("sitemap*.xml"):
            f.unlink()
        htaccess += X_ROBOTS
    (ziel / ".htaccess").write_text(htaccess, encoding="utf-8")
    (ziel / "version.txt").write_text(stand() + "\n", encoding="utf-8")
    pruefen(ziel, gebietskarte)
    gebiete = ", ".join(f"{n} {g / 1024:.1f} KiB" for n, g in groessen.items())
    print(f"Seite → {ziel}" + (" mit eigenen grauen Kacheln" if mit_kacheln else " ohne eigene Kacheln") + (
        "" if daten else f" (ohne Ratsdaten, Gebietskarte: {gebiete})" if gebietskarte
                               else " (ohne Daten: noindex)"))


if __name__ == "__main__":
    main(*sys.argv[1:])
