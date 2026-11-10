"""Seite rss/: Inhalte abonnieren und weiterverwenden (Entscheidung des Auftraggebers 28.10.2026).

Hauptadresse ist der Feed über die ganze Stadt (publish.GANZ_BONN); darunter drei Zugänge: einfach abonnieren (Feed-Reader),
in eine Website einbinden (Redaktionen), automatisiert weiterverarbeiten (Format, Felder, IDs, Abruf, Python-Beispiel
nur mit der Standardbibliothek). Alle Feeds sind Atom 1.0; die Seite erklärt, dass Atom wie RSS funktioniert.
Kopieren mit Rückmeldung über site/rss.js; ohne Skript ist die Adresse ein markierbares Feld. Feeds je Gebiet und
Thema stehen in einer Liste, leere Feeds nicht.

Themen-Feeds nur, wenn das Zusatzthema „themenseiten“ freigegeben ist (config.ZUSATZTHEMEN; aus ratsatlas-koeln
@d609111). Abweichung von Köln: auch der Hinweis auf dossiers/<thema>.xml und der Link auf thema/ hängen am Schalter.
"""
from html import escape

from . import config
from .publish import GANZ_BONN
from .themenseiten import ALLE as THEMEN

PFAD = "rss/"
AKTUALISIERUNG = "einmal am Tag, frühmorgens"
LAUF = "Zeitpunkt des täglichen Laufs noch nicht festgelegt"   # Bonn: 4:17 UTC; Wuppertaler Zeitplan mit Phase 5
# Ausweichadresse (CLAUDE.md 2). CORS: deploy/htaccess setzt Access-Control-Allow-Origin für xml/json/geojson/ics/tsv/
# jsonld, GitHub Pages ohnehin. Abweichung von ratsatlas-koeln @d609111 (dort „auf der Hauptadresse noch nicht
# eingerichtet“, für Wuppertal veraltet)
SPIEGEL = "https://daimpad.github.io/ratsatlas-wuppertal/"


GANZ_TITEL = f"{config.SEITENNAME} – ganz {config.STADT_NAME}"


def feed_url(site_url, name=GANZ_BONN):
    return f"{site_url}data/export/{config.STADT}/feeds/{name}.xml"


def head(site_url, titel=None, url=None):
    """Verweis für die automatische Feed-Erkennung (link rel="alternate") im Kopf einer Seite."""
    titel = titel or GANZ_TITEL
    return (f'\n  <link rel="alternate" type="application/atom+xml" title="{escape(titel)}" '
            f'href="{escape(url or feed_url(site_url))}">')


def _eintraege(path):
    try:
        return path.read_text(encoding="utf-8").count("<entry>")
    except OSError:
        return 0


def _feeds(site, site_url):
    """Weitere Feeds mit mindestens einem Eintrag: Themen, Quartiere nach Stadtbezirk, Stadtbezirke, ohne Ortsbezug.
    site_url ist hier die Wurzel der Links (relativ, damit sie auch auf dem Spiegel gelten)."""
    import json
    base = site / "data" / "export" / config.STADT
    try:
        index = json.loads((base / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        index = {"ortsteile": [], "bezirke": [], "ohne_ortsbezug": []}
    themen = [(t.titel, f"{site_url}data/export/{config.STADT}/dossiers/{t.key}.xml") for t in THEMEN
              if config.ZUSATZTHEMEN.get("themenseiten") and _eintraege(base / "dossiers" / f"{t.key}.xml")]
    gebiete = {}
    for o in sorted(index["ortsteile"], key=lambda o: (o["stadtbezirk"], o["name"])):
        if _eintraege(base / "feeds" / f"ortsteil-{o['slug']}.xml"):
            gebiete.setdefault(o["stadtbezirk"], []).append((o["name"], feed_url(site_url, f"ortsteil-{o['slug']}")))
    for b in index["bezirke"]:
        if _eintraege(base / "feeds" / f"bezirk-{b['slug']}.xml"):
            gebiete.setdefault(b["name"], []).insert(0, (f"Stadtbezirk {b['name']}, ohne genaueren Ort",
                                                         feed_url(site_url, f"bezirk-{b['slug']}")))
    ohne = [(f"Stadtweit / ohne Ortsbezug {x['jahr']}", feed_url(site_url, f"ohne-{x['jahr']}"))
            for x in index["ohne_ortsbezug"] if _eintraege(base / "feeds" / f"ohne-{x['jahr']}.xml")]
    return themen, gebiete, ohne


def _liste(titel, eintraege, ebene="h3"):
    if not eintraege:
        return ""
    return (f"<{ebene}>{titel}</{ebene}><ul class=\"rss-liste\">"
            + "".join(f'<li><a href="{escape(url)}" type="application/atom+xml" data-feed>{escape(name)}</a></li>'
                      for name, url in eintraege) + "</ul>")


def beispiel(url):
    """Python-Beispiel (nur Standardbibliothek), auch in tests/test_rssseite.py ausgeführt."""
    return f'''import urllib.request
import xml.etree.ElementTree as ET

URL = "{url}"
ATOM = {{"a": "http://www.w3.org/2005/Atom"}}

with urllib.request.urlopen(URL, timeout=30) as antwort:
    feed = ET.parse(antwort).getroot()

for eintrag in feed.findall("a:entry", ATOM):
    kennung = eintrag.findtext("a:id", namespaces=ATOM)  # wie guid
    datum = eintrag.findtext("a:updated", namespaces=ATOM)
    titel = eintrag.findtext("a:title", namespaces=ATOM)
    karte = eintrag.find("a:link[@rel='alternate']", ATOM).get("href")
    print(datum[:10], titel, karte)
'''


def body(site, site_url, root):
    url, link = feed_url(site_url), feed_url(root)   # angezeigt und kopiert absolut, verlinkt relativ
    themen, gebiete, ohne = _feeds(site, root)
    # Ohne Daten (CLAUDE.md 9, 10.11.2026) gibt es noch keine Feeds; die Adressen unten liefern bis dahin nichts
    ohne_daten = "" if (site / "data" / "export" / config.STADT / "index.json").is_file() else (
        '\n    <p id="rss-ohne-daten" role="note"><strong>Noch keine Feeds:</strong> Die Seite enthält noch '
        'keine Daten. Die Feeds entstehen mit dem ersten Datenstand; bis dahin liefern die Adressen auf dieser Seite '
        'nichts.</p>')
    gruppen = "".join(_liste(escape(bezirk), eintraege, "h4") for bezirk, eintraege in sorted(gebiete.items()))
    einbinden = (f'<link rel="alternate" type="application/atom+xml"\n'
                 f'      title="{GANZ_TITEL}"\n      href="{url}">')
    an = bool(config.ZUSATZTHEMEN.get("themenseiten"))   # Zusatzthema (CLAUDE.md 5.4)
    dossiers = ", <code>dossiers/&lt;thema&gt;.xml</code>" if an else ""
    themenlink = f' · <a href="{root}thema/">Themenseiten</a>' if an else ""
    return f"""    <h1>Inhalte abonnieren und weiterverwenden</h1>
    <p class="lead">Erhalten Sie neue Vorlagen und Beratungsergebnisse automatisch oder binden Sie sie in Ihre eigene Website ein. RSS ist offen, kostenlos und braucht kein Benutzerkonto.</p>{ohne_daten}

    <section class="rss-cta" aria-labelledby="rss-adresse-t">
      <h2 id="rss-adresse-t">Feed für ganz {escape(config.STADT_NAME)}</h2>
      <label for="rss-url">Feed-Adresse</label>
      <input id="rss-url" class="rss-url" type="text" readonly value="{escape(url)}" spellcheck="false" autocomplete="off">
      <div class="rss-aktionen">
        <button type="button" class="rss-knopf rss-haupt" data-kopieren="#rss-url" hidden>RSS-Adresse kopieren</button>
        <a class="rss-knopf rss-zweit" href="{escape(link)}" type="application/atom+xml">Feed direkt ansehen</a>
      </div>
      <p class="rss-meldung" id="rss-meldung" role="status" aria-live="polite"></p>
      <p class="meta">Neue Vorlagen und Beratungsergebnisse aus allen Gebieten, die letzten 100 Einträge, aktualisiert {AKTUALISIERUNG}. Ohne Kopierknopf: Adresse im Feld markieren und kopieren (Strg+C, am Mac ⌘+C).</p>
    </section>

    <nav class="thema-sprung" aria-label="Auf dieser Seite"><span>Auf dieser Seite:</span> <a href="#abonnieren">Einfach abonnieren</a> · <a href="#einbinden">In eine Website einbinden</a> · <a href="#technik">Automatisiert weiterverarbeiten</a></nav>

    <section class="rss-zugang" id="abonnieren" aria-labelledby="abonnieren-t">
      <p class="rss-fuer">Für alle, ohne Vorkenntnisse</p>
      <h2 id="abonnieren-t">Einfach abonnieren</h2>
      <ol class="rss-schritte">
        <li><strong>Feed-Reader wählen.</strong> Ein Feed-Reader sammelt Neuigkeiten von Websites. Kostenlos und ohne Konto zum Beispiel: <a href="https://www.thunderbird.net/de/">Thunderbird</a> (E-Mail-Programm, Windows, macOS, Linux), <a href="https://netnewswire.com/">NetNewsWire</a> (Mac, iPhone, iPad), <a href="https://f-droid.org/packages/com.nononsenseapps.feeder/">Feeder</a> (Android).</li>
        <li><strong>Adresse einfügen.</strong> Kopieren Sie die Feed-Adresse oben und fügen Sie sie im Reader bei „Feed hinzufügen“ oder „Abonnieren“ ein.</li>
        <li><strong>Neues erhalten.</strong> Der Reader zeigt neue Einträge von selbst, sobald die Karte sie übernimmt ({AKTUALISIERUNG}). Abbestellen geht jederzeit im Reader; der Ratsatlas erfährt davon nichts.</li>
      </ol>
      <p class="rss-weiter"><button type="button" class="rss-knopf rss-haupt" data-kopieren="#rss-url" hidden>RSS-Adresse kopieren</button> <a href="#weitere">Nur ein Gebiet oder Thema abonnieren</a></p>
      <details class="hh-mehr" id="weitere">
        <summary>Feeds für einzelne Gebiete und Themen</summary>
        <p>Diese Feeds enthalten nur die Vorlagen eines Gebiets oder einer Themenseite. Für einen einzelnen Vorgang gibt es in der <a href="{root}">Karte</a> beim Vorgang unter „Mitmachen“ einen eigenen Feed.</p>
        {_liste("Themenseiten <small>(Zuordnung abgeleitet)</small>", themen)}
        {"<h3>Quartiere nach Stadtbezirk</h3>" + gruppen if gruppen else ""}
        {_liste("Stadtweit, ohne Ortsbezug", ohne)}
      </details>
    </section>

    <section class="rss-zugang" id="einbinden" aria-labelledby="einbinden-t">
      <p class="rss-fuer">Für Redaktionen und Website-Verantwortliche</p>
      <h2 id="einbinden-t">In eine Website einbinden</h2>
      <p>Ihre Website braucht eine Funktion oder Erweiterung, die Feeds einliest, etwa ein „RSS-Block“, ein „Feed-Widget“ oder ein „Aggregator“. In WordPress gibt es dafür den Block „RSS“. Dort tragen Sie die Feed-Adresse ein; die Erweiterung holt neue Einträge selbst.</p>
      <p>Damit Browser und Reader den Feed auf Ihrer Seite finden, genügt eine Zeile im Kopf (<code>&lt;head&gt;</code>) der Seite:</p>
      <pre class="rss-code" id="rss-head" tabindex="0"><code>{escape(einbinden)}</code></pre>
      <p class="rss-weiter"><button type="button" class="rss-knopf rss-zweit" data-kopieren="#rss-head" hidden>Zeile kopieren</button> <a href="#technik">Technische Angaben</a></p>
      <p class="meta">Bitte nennen Sie die Quelle „{escape(config.SEITENNAME)}“. Die Angaben stammen aus dem Ratsinformationssystem der Stadt {escape(config.STADT_NAME)} (OParl-API; Lizenz ungeklärt, Anfrage an die Stadt offen); maßgeblich ist das Original. Für Geodaten gilt: {escape(config.NAMENSNENNUNG)}.</p>
    </section>

    <section class="rss-zugang rss-technik" id="technik" aria-labelledby="technik-t">
      <p class="rss-fuer">Für Entwicklerinnen und Entwickler</p>
      <h2 id="technik-t">Automatisiert weiterverarbeiten</h2>
      <dl class="rss-felder">
        <dt>Format</dt><dd>Atom 1.0 (<a href="https://www.rfc-editor.org/rfc/rfc4287">RFC 4287</a>), UTF-8. Atom erfüllt denselben Zweck wie RSS 2.0; jeder gängige Reader liest beides.</dd>
        <dt>Feed</dt><dd><code>id</code>, <code>title</code>, <code>subtitle</code>, <code>updated</code> (jüngster Eintrag), <code>link rel="self"</code>, <code>link rel="alternate"</code> (Karte), <code>author</code>, <code>rights</code> (Lizenz).</dd>
        <dt>Eintrag</dt><dd><code>id</code>, <code>title</code>, <code>updated</code>, <code>link rel="alternate"</code> (Vorgang in der Karte), <code>link rel="related"</code> (Original im Ratsinformationssystem der Stadt), <code>summary</code> (Art, federführendes Amt, Stand; gekennzeichnete KI-Kurzfassung, wo vorhanden).</dd>
        <dt>Kennung</dt><dd><code>id</code> ist stabil und entspricht <code>guid</code> in RSS: OParl-Adresse der Vorlage und Art des Ereignisses, z. B. <code>…/oparl/papers/2022978#vorlage</code>, <code>…#beratung-2026-06-10-Rat</code>, <code>…#folge-…</code>. Dieselbe Vorlage hat in allen Feeds dieselbe Kennung.</dd>
        <dt>Datum</dt><dd><code>updated</code> ist der Tag des Ereignisses (Datum der Vorlage oder der Sitzung), immer 00:00 UTC; ein eigenes Veröffentlichungsdatum gibt es nicht.</dd>
        <dt>Umfang</dt><dd>Die letzten 100 Einträge je Feed, neueste zuerst; Feeds je Vorgang enthalten alle Ereignisse.</dd>
        <dt>Adressen</dt><dd><code>data/export/{config.STADT}/feeds/{GANZ_BONN}.xml</code>, <code>feeds/ortsteil-&lt;name&gt;.xml</code>, <code>feeds/bezirk-&lt;name&gt;.xml</code>, <code>feeds/ohne-&lt;jahr&gt;.xml</code>, <code>feeds/vorlagen/&lt;drucksache&gt;.xml</code>{dossiers}.</dd>
        <dt>Abruf</dt><dd>Die Feeds ändern sich höchstens einmal am Tag ({LAUF}). Bitte höchstens einmal pro Stunde abrufen, besser einmal am Tag; der Server beantwortet bedingte Abrufe (<code>If-Modified-Since</code>, <code>If-None-Match</code>). Ohne Schlüssel und ohne Anmeldung. Auch aus dem Browser anderer Websites abrufbar (CORS): Feeds und Daten werden mit <code>Access-Control-Allow-Origin: *</code> ausgeliefert, auf der Hauptadresse wie auf dem Spiegel <code>{SPIEGEL}</code> mit denselben Pfaden.</dd>
      </dl>
      <p>Beispiel in Python, nur mit der Standardbibliothek:</p>
      <pre class="rss-code" id="rss-python" tabindex="0"><code>{escape(beispiel(url))}</code></pre>
      <p class="rss-weiter"><button type="button" class="rss-knopf rss-zweit" data-kopieren="#rss-python" hidden>Beispiel kopieren</button> <a href="{escape(link)}" type="application/atom+xml">Feed direkt ansehen</a> · <a href="https://github.com/daimpad/ratsatlas-wuppertal/blob/main/pipeline/publish.py">Erzeugung der Feeds (Quelltext)</a></p>
    </section>
    <p><a href="{root}">Zur Karte</a>{themenlink} · <a href="{root}gebiete/">Alle Gebiete</a></p>
    <script src="{root}rss.js" defer></script>"""


def write(site, site_url, page):
    """Schreibt rss/index.html; gibt den Pfad für die Sitemap zurück."""
    out = site / PFAD / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(site_url, PFAD, f"Inhalte abonnieren und weiterverwenden – {config.SEITENNAME}",
                        f"Feeds des {config.SEITENNAME} abonnieren oder einbinden: neue Vorlagen und Beratungsergebnisse "
                        f"aus ganz {config.STADT_NAME}, je Gebiet und je Thema, offen und ohne Konto.",
                        body(site, site_url, "../"), "../"), encoding="utf-8")   # Feed-Erkennung im Kopf: _page
    return [PFAD]
