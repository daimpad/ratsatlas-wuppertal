"""Datenpaket (pipeline/paket.py, Phase 5, Entscheidung 23.11.2026): Inhalt fest geregelt, ohne Adressindex, ohne
Protokolle des Dokumentabrufs und ohne Rohdaten; Bebauungspläne byte-gleich; reproduzierbar. Export erfundener Dateien
in einem Temp-Ordner, Geodaten aus data/geo des Repositorys."""
import json
import zipfile

import pytest

from pipeline import config, paket, volltext


@pytest.fixture
def export(tmp_path, monkeypatch):
    ordner = tmp_path / "export"
    (ordner / config.STADT / "feeds").mkdir(parents=True)
    (ordner / config.STADT / "index.json").write_text("{}", encoding="utf-8")
    (ordner / config.STADT / "vorlagen.geojson").write_text("{}", encoding="utf-8")
    (ordner / config.STADT / "feeds" / "alle.xml").write_text("<rss/>", encoding="utf-8")
    (ordner / "audit_geokodierung.tsv").write_text("drucksache\n", encoding="utf-8")
    (ordner / "LICENSE-DATA.md").write_text("Kopie", encoding="utf-8")
    for name in (config.DOKUMENTE_PROTOKOLL.name, config.DOKUMENTE_STATISTIK.name):
        (ordner / name).write_text("https://example.invalid/datei.pdf\n", encoding="utf-8")
    (ordner / "chat").mkdir()
    (ordner / "chat" / "x.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "EXPORT", ordner)
    return ordner


def namen(pfad):
    with zipfile.ZipFile(pfad) as z:
        return {n.removeprefix(paket.ORDNER + "/") for n in z.namelist()}


def test_inhalt(export):
    n = namen(paket.write())
    assert {"LIESMICH.txt", "LICENSE-DATA.md", f"export/{config.STADT}/index.json",
            f"export/{config.STADT}/vorlagen.geojson", "export/audit_geokodierung.tsv"} <= n
    assert {f"geo/{p.name}" for p in paket.INHALT_GEO if p.is_file()} <= n
    # nicht: Feeds, Assistent, Protokolle des Dokumentabrufs, Kopie der Lizenzdatei, Adressindex, Rohdaten, Texte
    assert not [x for x in n if "/feeds/" in x or x.startswith("export/chat/")]
    assert not {f"export/{config.DOKUMENTE_PROTOKOLL.name}", f"export/{config.DOKUMENTE_STATISTIK.name}",
                "export/LICENSE-DATA.md", f"geo/{config.HAUSNUMMERN.name}"} & n
    assert not [x for x in n if x.startswith(("raw/", "export/raw/")) or x.endswith((".pdf", ".txt.gz", ".zip"))]


def test_bebauungsplaene_byte_gleich(export):
    with zipfile.ZipFile(paket.write()) as z:
        for quelle in (config.BPLAN, config.BPLAN_LAUFEND):
            if quelle.is_file():
                assert z.read(f"{paket.ORDNER}/geo/{quelle.name}") == quelle.read_bytes()


def test_volltext_nur_abgeleitete_felder(export, monkeypatch):
    # die versionierte Datei, nicht die Umlenkung aus conftest
    monkeypatch.setattr(config, "VOLLTEXT_ORTE", config.ROOT / "data" / "volltext" / "orte_volltext.json")
    if not config.VOLLTEXT_ORTE.is_file():
        pytest.skip("keine Volltext-Orte im Repository")
    with zipfile.ZipFile(paket.write()) as z:
        daten = json.loads(z.read(f"{paket.ORDNER}/volltext/{config.VOLLTEXT_ORTE.name}"))
    erlaubt = set(volltext.ABLAGE_FELDER)
    for eintrag in daten["vorlagen"].values():
        assert set(eintrag) <= {"befund", "teil", "zeilen"}
        for zeile in eintrag["zeilen"]:
            assert set(zeile) <= erlaubt


def test_haushalt_nur_mit_zusatzthema(export, monkeypatch):
    monkeypatch.setitem(config.ZUSATZTHEMEN, "haushalt", False)
    n = namen(paket.write())
    assert not [x for x in n if x.startswith("haushalt/") or x.endswith("BERICHT_haushalt_phase0.md")]
    monkeypatch.setitem(config.ZUSATZTHEMEN, "haushalt", True)
    if paket.HAUSHALT.is_dir():
        assert [x for x in namen(paket.write()) if x.startswith("haushalt/")]


def test_liesmich_namensnennung_und_lizenz():
    for text in (config.NAMENSNENNUNG, config.NAMENSNENNUNG_BPLAN, config.LIZENZ_OPARL,
                 "Adressen_EPSG4326_JSON.json"):
        assert text in paket.LIESMICH


def test_reproduzierbar(export, tmp_path):
    a, b = paket.write(tmp_path / "a.zip"), paket.write(tmp_path / "b.zip")
    assert a.read_bytes() == b.read_bytes()


def test_ohne_export_abbruch(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORT", tmp_path)
    with pytest.raises(SystemExit):
        paket.write()


def test_paketadresse_auf_der_hauptadresse():
    assert config.PAKET_URL.endswith("data/export/" + paket.DATEI)
