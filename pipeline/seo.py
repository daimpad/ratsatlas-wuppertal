"""Auffindbarkeit der Seite: robots.txt, Sitemaps und absolute Adressen (canonical, Open Graph,
strukturierte Daten, Fehlerseite) für die öffentliche Adresse SITE_URL.

sitemap.xml ist ein Index über sitemap-seiten.xml (Karte und statische Seiten) und sitemap-vorgaenge.xml (Seiten je
Vorgang, mit lastmod aus dem jüngsten Datum der Quelle); so genügt eine eingereichte Adresse in der Search Console.

Die Quelldateien in site/ enthalten die Adresse von GitHub Pages; dieser Schritt ersetzt sie in der
zusammengestellten Seite (_site), damit ein Wechsel auf die eigene Domain nur SITE_URL braucht.
Ohne Erzeugungszeitpunkte, damit sich der Branch deploy nur bei Inhaltsänderungen ändert.

Schalter der Bonner Zusatzthemen (config.ZUSATZTHEMEN, ohne_abgeschaltete) aus ratsatlas-koeln @d609111. Wuppertaler
Abweichung für den gemeinsamen Kern: Die Vorgangsseiten (vorgangsseiten.py, sitemap-vorgaenge.xml) gehören zum Kern
(CLAUDE.md 9); AUS_FUNKTION erfasst außer Karten auch Listeneinträge (<li data-funktion=… hidden>), weil die Dialoge
in site/index.html bis Phase 4 noch Bonner Links auf Zusatzthemen enthalten."""
import re
from pathlib import Path
from xml.sax.saxutils import escape

from . import (begriffsseite, config, dossier, einfachseite, gebietsseiten, haushaltsseite, rssseite, technikseite,
               vorgangsseiten)
from .themenseiten import ALLE as THEMENSEITEN

DEFAULT_URL = "https://daimpad.github.io/ratsatlas-wuppertal/"  # Platzhalter in site/, wird durch SITE_URL ersetzt
# Bonner Vorschaubild: aus site/ entfernt (10.11.2026, ersetzt durch vorschaubild.jpg aus tools/vorschaubild.mjs); der
# Eintrag hält es aus der Seite, falls es über eine Zusammenführung zurückkommt (wie ratsatlas-koeln @d609111
# tools/seite_bauen.py:19)
NICHT_AUSLIEFERN = ("og-image.jpg",)
PAGES = ("index.html", "404.html", "datenschutz.html")
SITEMAP = ("", "datenschutz.html")  # Pfade relativ zu SITE_URL
SITEMAP_SEITEN = "sitemap-seiten.xml"
SITEMAP_VORGAENGE = "sitemap-vorgaenge.xml"
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
# Karten (<a class="card" href=… data-funktion=… hidden>) und Listeneinträge (<li data-funktion=… hidden>) abgeschalteter
# Zusatzthemen; die Attributfolge muss in site/ so eingehalten werden
AUS_FUNKTION = re.compile(r'\s*(?:<a class="card" href="[^"]*" data-funktion="(\w+)" hidden>.*?</a>'
                          r'|<li data-funktion="(\w+)" hidden>.*?</li>)', re.S)


def robots(site_url):
    return f"User-agent: *\nAllow: /\n\nSitemap: {site_url}sitemap.xml\n"


def sitemap(site_url, extra=()):
    urls = "".join(f"  <url><loc>{escape(site_url + path)}</loc>{'' if path else '<changefreq>daily</changefreq>'}</url>\n"
                   for path in (*SITEMAP, *extra))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="{NS}">\n'
            f"{urls}</urlset>\n")


def sitemap_vorgaenge(site_url, eintraege):
    """Seiten je Vorgang; lastmod ist das jüngste Datum aus der Quelle, kein Erzeugungszeitpunkt."""
    urls = "".join(f"  <url><loc>{escape(site_url + pfad)}</loc>{f'<lastmod>{datum}</lastmod>' if datum else ''}</url>\n"
                   for pfad, datum in eintraege)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="{NS}">\n{urls}</urlset>\n'


def sitemap_index(site_url, dateien):
    eintraege = "".join(f"  <sitemap><loc>{escape(site_url + d)}</loc></sitemap>\n" for d in dateien)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="{NS}">\n{eintraege}</sitemapindex>\n'


def ohne_abgeschaltete(html):
    """Karten und Listeneinträge abgeschalteter Zusatzthemen (data-funktion, config.ZUSATZTHEMEN) aus der veröffentlichten
    Seite entfernen, damit Suchmaschinen keinen Links auf nicht erzeugte Seiten folgen; die Quelle in site/ bleibt
    vollständig. Schlüssel ohne Eintrag in ZUSATZTHEMEN (z. B. „volltextsuche“) gelten als abgeschaltet."""
    return AUS_FUNKTION.sub(lambda m: m.group(0) if config.ZUSATZTHEMEN.get(m.group(1) or m.group(2)) else "", html)


def write(site=Path("_site"), site_url=None):
    site_url = site_url or config.SITE_URL
    if not site_url.endswith("/"):
        site_url += "/"
    for name in NICHT_AUSLIEFERN:
        (site / name).unlink(missing_ok=True)
    for name in PAGES:
        page = site / name
        if page.exists():
            html = page.read_text(encoding="utf-8").replace(DEFAULT_URL, site_url)
            page.write_text(gebietsseiten.neuer_tab(ohne_abgeschaltete(html)), encoding="utf-8")
    (site / "robots.txt").write_text(robots(site_url), encoding="utf-8")
    areas = gebietsseiten.write(site, site_url)
    an = lambda thema: config.ZUSATZTHEMEN.get(thema)   # Bonner Zusatzthemen nur bei Freigabe (CLAUDE.md 5.4)
    themen = []
    if an("themenseiten"):
        themen = [pfad for t in THEMENSEITEN for pfad in dossier.write(t, site, site_url, gebietsseiten._page)]
        themen = dossier.uebersicht(THEMENSEITEN, site, site_url, gebietsseiten._page) + themen
    if an("haushalt"):
        themen += haushaltsseite.write(site, site_url, gebietsseiten._page)
    # Kern: Feeds, Begriffe, Vorgangsseiten
    themen += rssseite.write(site, site_url, gebietsseiten._page)
    themen += begriffsseite.write(site, site_url, gebietsseiten._page)
    if an("einfache_sprache"):
        themen += einfachseite.write(site, site_url, gebietsseiten._page)
    if an("technik"):   # beschreibt die Workflows; nach Phase 5
        themen += technikseite.write(site, site_url, gebietsseiten._page)
    vorgaenge = vorgangsseiten.write(site, site_url, gebietsseiten._page)
    (site / SITEMAP_SEITEN).write_text(sitemap(site_url, [*themen, *areas]), encoding="utf-8")
    dateien = [SITEMAP_SEITEN]
    if vorgaenge:
        (site / SITEMAP_VORGAENGE).write_text(sitemap_vorgaenge(site_url, vorgaenge), encoding="utf-8")
        dateien.append(SITEMAP_VORGAENGE)
    (site / "sitemap.xml").write_text(sitemap_index(site_url, dateien), encoding="utf-8")
    print(f"robots.txt, Sitemaps und Adressen für {site_url}")
