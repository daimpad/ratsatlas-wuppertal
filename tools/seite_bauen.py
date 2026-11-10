"""Fertige Seite zusammenstellen, wie sie .github/workflows/pages.yml veröffentlicht: site/ (+ Daten, falls vorhanden)
→ _site/, dann Auffindbarkeit (pipeline/seo.py) und .htaccess aus deploy/htaccess.

Aufruf: python3 tools/seite_bauen.py [ziel]   (Vorgabe: _site; nicht versioniert; SITE_URL aus der Umgebung)
Danach z. B.: python3 -m http.server -d _site 8000

Struktur nach ratsatlas-koeln (origin/main, tools/seite_bauen.py), ohne Kartenkacheln und Dateigrößen im Menü „Daten“
(ohne Daten gibt es nichts herunterzuladen). Ohne Rufe an Server, ohne Zeitstempel (reproduzierbar).

Ohne Daten (data/export/wuppertal/index.json fehlt; CLAUDE.md 9, 10.11.2026): Die Seite zeigt „Daten nicht
verfügbar“ und wird nicht indexiert: noindex in jeder HTML-Seite, X-Robots-Tag in .htaccess, robots.txt ohne Sitemap,
keine Sitemaps. Kein „Disallow: /“, damit Suchmaschinen das noindex lesen können. Mit Daten entfällt das von selbst.

Abgeschaltete Zusatzthemen (config.ZUSATZTHEMEN; CLAUDE.md 5.4, 9): ihre Module werden nicht ausgeliefert. Ohne
Ratsassistent erlaubt die CSP in index.html keine Verbindungen zu dessen Anbietern und zu localhost, und die
Datenschutzerklärung nennt ihn nicht. Am Ende prüft das Skript, dass die Seite vollständig ist."""
import re
import shutil
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
# Mindestinhalt jeder gebauten Seite (sonst bricht der Bau ab, statt eine leere Seite auszuliefern)
PFLICHT = ("index.html", "app.js", "style.css", "datenschutz.html", "404.html", "robots.txt", ".htaccess",
           "data/LICENSE-DATA.md")
X_ROBOTS = ('\n# Ohne Daten nicht indexieren (tools/seite_bauen.py; entfällt, sobald Daten vorliegen)\n'
            '<IfModule mod_headers.c>\n  Header always set X-Robots-Tag "noindex"\n</IfModule>\n')


def mit_daten():
    return (config.EXPORT / config.STADT / "index.json").is_file()


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


def pruefen(ziel):
    fehlt = [d for d in PFLICHT if not (ziel / d).is_file() or not (ziel / d).stat().st_size]
    if fehlt:
        raise SystemExit(f"Seite unvollständig, es fehlt: {', '.join(fehlt)}")
    if "<title>Ratsatlas Wuppertal" not in (ziel / "index.html").read_text(encoding="utf-8"):
        raise SystemExit("index.html ohne Titel „Ratsatlas Wuppertal“")


def main(ziel=ROOT / "_site", site_url=None):
    ziel = Path(ziel)
    daten = mit_daten()
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
    seo.write(ziel, site_url)                         # entfernt og-image.jpg, setzt SITE_URL und Canonical
    if not config.ZUSATZTHEMEN.get("chat"):
        for name, stellen in OHNE_CHAT.items():
            text = (ziel / name).read_text(encoding="utf-8")
            for alt, neu in stellen:
                text = ersetzen(text, alt, neu, name)
            (ziel / name).write_text(text, encoding="utf-8")
    htaccess = (ROOT / "deploy" / "htaccess").read_text(encoding="utf-8")
    if not daten:
        for seite in sorted(ziel.rglob("*.html")):
            seite.write_text(noindex(seite.read_text(encoding="utf-8")), encoding="utf-8")
        (ziel / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        for f in ziel.glob("sitemap*.xml"):
            f.unlink()
        htaccess += X_ROBOTS
    (ziel / ".htaccess").write_text(htaccess, encoding="utf-8")
    pruefen(ziel)
    print(f"Seite → {ziel}" + ("" if daten else " (ohne Daten: noindex)"))


if __name__ == "__main__":
    main(*sys.argv[1:])
