"""Graue Kartenkacheln (Entscheidung 17.11.2026; aus ratsatlas-koeln @74eb11c): site/app.js (KACHEL_RAHMEN) und
pipeline/kacheln/rahmen.py stimmen überein und decken das Wuppertaler Stadtgebiet ab; der Workflow fragt keine Server
der Stadt und keine Kacheln von tile.openstreetmap.org an; tools/seite_bauen.py übernimmt vorhandene Kacheln und passt
die Datenschutzerklärung an. Ohne Netz."""
import importlib.util
import json
import re
import sys
from pathlib import Path

from shapely.geometry import shape
from shapely.ops import unary_union

from pipeline import config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline" / "kacheln"))
import rahmen  # noqa: E402


def test_rahmen_gleich_in_seite_und_pipeline():
    js = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    m = re.search(r"const KACHEL_RAHMEN = (\{[^\n]*\});", js)
    seite = json.loads(re.sub(r"(\d+):", r'"\1":', m.group(1)))
    assert {int(k): v for k, v in seite.items()} == {
        z: list(rahmen.kachelbereich(z)) for z in range(rahmen.ZMIN, rahmen.ZMAX + 1)}


def test_rahmen_umfasst_stadtgebiet_und_gleich_stadt_bbox():
    feats = json.loads(config.STADTBEZIRKE.read_text(encoding="utf-8"))["features"]
    lo1, la1, lo2, la2 = unary_union([shape(f["geometry"]) for f in feats]).bounds
    s = rahmen.STADT
    assert s[0] <= lo1 + 1e-3 and s[1] <= la1 + 1e-3 and s[2] >= lo2 - 1e-3 and s[3] >= la2 - 1e-3
    sued, west, nord, ost = config.STADT_BBOX
    assert s == (west, sued, ost, nord)


def test_kachelzahl_und_rahmen_wachsen_mit_zoom():
    zahl = 0
    for z in range(rahmen.ZMIN, rahmen.ZMAX + 1):
        x1, y1, x2, y2 = rahmen.kachelbereich(z)
        assert x1 <= x2 and y1 <= y2
        zahl += (x2 - x1 + 1) * (y2 - y1 + 1)
    assert zahl == 6399                              # im Kommentar von kacheln.yml genannt
    assert "6.399 Kacheln" in (ROOT / ".github" / "workflows" / "kacheln.yml").read_text(encoding="utf-8")


def test_keine_stadt_und_keine_osm_kacheln_im_workflow_und_ausschnitt():
    texte = [(ROOT / ".github" / "workflows" / "kacheln.yml").read_text(encoding="utf-8")]
    texte += [p.read_text(encoding="utf-8") for p in (ROOT / "pipeline" / "kacheln").glob("*.py")]
    texte += [(ROOT / "pipeline" / "kacheln" / n).read_text(encoding="utf-8") for n in ("rendern.mjs", "render.html")]
    for t in texte:
        assert not re.search(r"https?://[^\s\"'`]*wuppertal\.de", t), "Server der Stadt"
        assert not re.search(r"https?://[^\s\"'`]*tile\.openstreetmap\.org", t), "OSM-Kachelserver"
        # keine Rahmen, Mitten oder User-Agents der Vorlagen (Bonn, Köln); die Herkunft darf genannt sein
        for alt in ("BONN =", "6.7725", "7.1166", "50.7036", "ratsatlas-koeln/", "ratsatlas-bonn/", "bonn.pmtiles"):
            assert alt not in t, alt
    ausschnitt = (ROOT / "pipeline" / "kacheln" / "ausschnitt.py").read_text(encoding="utf-8")
    assert "ratsatlas-wuppertal" in ausschnitt and "sys.exit(\"Kachelausschnitt" not in ausschnitt


def _bauskript():
    spec = importlib.util.spec_from_file_location("seite_bauen", ROOT / "tools" / "seite_bauen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_seite_bauen_uebernimmt_kacheln_und_passt_datenschutz_an(tmp_path, monkeypatch):
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)
    monkeypatch.setattr(config, "EXPORT", tmp_path / "leer")
    monkeypatch.delenv("RATSATLAS_GEBIETSKARTE", raising=False)
    kacheln = tmp_path / "kacheln"
    (kacheln / "16").mkdir(parents=True)
    (kacheln / "16" / "1.png").write_bytes(b"\x89PNG")
    (kacheln / "stand.json").write_text('{"build": "20261101.pmtiles"}', encoding="utf-8")
    bau = _bauskript()
    mit = bau.main(tmp_path / "mit", kacheln_quelle=kacheln, gebietskarte=False) or tmp_path / "mit"
    ohne = bau.main(tmp_path / "ohne", kacheln_quelle=tmp_path / "fehlt", gebietskarte=False) or tmp_path / "ohne"
    assert (mit / "kacheln" / "16" / "1.png").is_file() and not (ohne / "kacheln").exists()
    ds_mit = (mit / "datenschutz.html").read_text(encoding="utf-8")
    ds_ohne = (ohne / "datenschutz.html").read_text(encoding="utf-8")
    assert "die Bilder der grauen Karte (Kacheln, erzeugt aus OpenStreetMap-Daten) liegen auf dem Server" in ds_mit
    assert "Nur wenn Sie „Farbige Karte“ wählen" in ds_mit and "derzeit ist das so" not in ds_mit
    assert "Vermeiden lässt sich das, indem Sie bei der grauen Karte bleiben" in ds_mit
    assert "derzeit ist das so" in ds_ohne and "bei der grauen Karte bleiben" not in ds_ohne
