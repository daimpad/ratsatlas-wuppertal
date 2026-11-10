"""Vorschaubild für geteilte Links (og:image, twitter:image): site/vorschaubild.jpg aus tools/vorschaubild.mjs (graue
Karte, © OpenStreetMap-Mitwirkende), in der gebauten Seite absolut auf SITE_URL wie Canonical; das Bonner
og-image.jpg ist entfernt. Keine Anfragen an Server: das Skript wird nur statisch geprüft, nicht ausgeführt."""
import re
from urllib.parse import urlsplit

import pytest

from pipeline import config
from test_seite_bauen import _bauen, _bauskript

ROOT = config.ROOT
BILD = ROOT / "site" / "vorschaubild.jpg"
SKRIPT = ROOT / "tools" / "vorschaubild.mjs"
HAUPT = "https://wuppertal.ratsatlas.de/"


def jpeg_masse(daten):
    """(Breite, Höhe) aus dem Kopf einer JPEG-Datei (erster SOF-Marker)."""
    assert daten[:2] == b"\xff\xd8", "keine JPEG-Datei"
    i = 2
    while i + 9 < len(daten):
        assert daten[i] == 0xFF, "JPEG-Kopf unlesbar"
        marker, laenge = daten[i + 1], int.from_bytes(daten[i + 2:i + 4], "big")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(daten[i + 7:i + 9], "big"), int.from_bytes(daten[i + 5:i + 7], "big")
        i += 2 + laenge
    raise AssertionError("JPEG ohne SOF-Marker")


def _meta(html, schluessel):
    m = re.search(rf'<meta (?:property|name)="{re.escape(schluessel)}" content="([^"]*)">', html)
    return m and m.group(1)


def test_bild_im_repository():
    daten = BILD.read_bytes()
    assert jpeg_masse(daten) == (1200, 630)
    assert len(daten) <= 300 * 1024


def test_kein_bonner_bild_mehr():
    funde = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("og-image*")
             if not {".git", "node_modules"} & set(p.relative_to(ROOT).parts)]
    assert funde == []


@pytest.mark.parametrize("site_url", [HAUPT, "https://beispiel.invalid/"])
def test_meta_absolut_und_masse_wie_datei(tmp_path, monkeypatch, site_url):
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer", site_url)
    datei = ziel / "vorschaubild.jpg"
    assert datei.is_file() and datei.stat().st_size <= 300 * 1024
    assert not (ziel / "og-image.jpg").exists()
    html = (ziel / "index.html").read_text(encoding="utf-8")
    assert _meta(html, "og:image") == _meta(html, "twitter:image") == site_url + "vorschaubild.jpg"
    assert f'<link rel="canonical" href="{site_url}">' in html
    breite, hoehe = jpeg_masse(datei.read_bytes())
    assert (_meta(html, "og:image:width"), _meta(html, "og:image:height")) == (str(breite), str(hoehe))
    assert _meta(html, "og:image:type") == "image/jpeg"
    assert _meta(html, "twitter:card") == "summary_large_image"
    alt = _meta(html, "og:image:alt")
    assert alt and "Wuppertal" in alt and alt == _meta(html, "twitter:image:alt")
    assert "daimpad.github.io" not in html and "og-image" not in html


def test_pruefen_verlangt_vorschaubild(tmp_path, monkeypatch):
    ziel = _bauen(tmp_path, monkeypatch, tmp_path / "leer")
    bau = _bauskript()
    index = ziel / "index.html"
    html = index.read_text(encoding="utf-8")
    index.write_text(html.replace(f'<meta name="twitter:image" content="{HAUPT}vorschaubild.jpg">', ""),
                     encoding="utf-8")
    with pytest.raises(SystemExit, match="Vorschaubild"):
        bau.pruefen(ziel)
    index.write_text(html, encoding="utf-8")
    (ziel / "vorschaubild.jpg").unlink()
    with pytest.raises(SystemExit, match="vorschaubild.jpg"):
        bau.pruefen(ziel)


def test_skript_fragt_nur_osm_kacheln_an():
    """Statische Prüfung: einzige abgerufene fremde Adresse sind Kacheln von tile.openstreetmap.org (begrenzt), jeder
    andere fremde Host wird abgebrochen; keine Server der Stadt, Seite nur auf 127.0.0.1."""
    text = SKRIPT.read_text(encoding="utf-8")
    hosts = {urlsplit(u).hostname for u in re.findall(r"https?://[A-Za-z0-9.\-]+", text.replace("\\.", "."))}
    assert hosts <= {"tile.openstreetmap.org", "127.0.0.1", "wuppertal.ratsatlas.de", "www.openstreetmap.org"}, hosts
    assert not [h for h in hosts if re.search(r"(^|\.)wuppertal\.de$|wuppertal-[^.]*\.de$", h)]
    assert 'ERLAUBTE_HOSTS = ["tile.openstreetmap.org"]' in text
    assert r"OSM_KACHEL = /^https:\/\/tile\.openstreetmap\.org\/\d{1,2}\/\d+\/\d+\.png$/" in text
    assert re.search(r"export const GRENZE = (\d+);", text) and int(re.search(r"GRENZE = (\d+);", text).group(1)) <= 40
    # genau ein Abruf, nur im Zweig für erlaubte Kacheln unterhalb der Grenze; sonst Abbruch
    assert text.count("fetch(") == 1
    # keine Weiterleitung folgen (fetch folgt sonst selbst, auch auf andere Hosts, am Browser-Router vorbei)
    assert 'fetch(u.href, { redirect: "error",' in text
    zweig = text.index("if (OSM_KACHEL.test(u.href) && ERLAUBTE_HOSTS.includes(u.hostname) && kacheln.length < GRENZE)")
    assert zweig < text.index("fetch(") < text.index('route.abort("blockedbyclient")')
    assert 'if (u.hostname === "127.0.0.1") return route.continue();' in text
    assert 'server.listen(0, "127.0.0.1"' in text
    # graue Standardansicht der Seite, Ausschnitt aus site/app.js, Maße mit deviceScaleFactor 1
    assert 'm.classList.contains("map-gray")' in text and "deviceScaleFactor: 1" in text
    assert "STADT_MITTE" in text and "Messstufe G" in text
    assert "© OpenStreetMap-Mitwirkende" in text


def test_bild_ist_grau():
    """Kartenbereich unten rechts (ohne Schriftzug) ohne Farbe: graue Karte, nicht die farbige."""
    image = pytest.importorskip("PIL.Image")
    with image.open(BILD) as bild:
        ausschnitt = bild.convert("HSV").crop((700, 260, 1150, 560))
        saettigung = sorted(ausschnitt.getchannel("S").tobytes())
    assert saettigung[len(saettigung) // 2] <= 8 and saettigung[int(len(saettigung) * 0.95)] <= 30
