"""Schalter der Bonner Zusatzthemen (CLAUDE.md 5.4, Entscheidung 09.11.2026): config.ZUSATZTHEMEN → index.json
meta.funktionen → data-funktion in site/ → seo (veröffentlichte Seite). Abgeschaltete Themen erzeugen keine Dateien und
Seiten; die Datenschutzregel für Vorlagen aus der Einwohnerschaft (§ 24 GO NRW, maske.einwohner) gilt auch bei
abgeschaltetem Ratsassistenten. Ohne Netz (lokaler Testserver aus conftest.oparl), ohne Daten der Stadt."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline import (begriffsseite, build, check, config, dossier, einfachseite, gebietsseiten, haushaltsseite,
                      kontext, maske, rssseite, sessionnet, seo, technikseite, vorgangsseiten)

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "site" / "index.html"
# Seiten, die nur ein Zusatzthema erzeugt (seo.write)
SEITEN = {"themenseiten": "thema/", "haushalt": "haushalt/", "einfache_sprache": "einfach/", "technik": "technik/"}


def _alle_aus(monkeypatch):
    for k in list(config.ZUSATZTHEMEN):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, False)


def test_alle_zusatzthemen_sind_standardmaessig_aus():
    """CLAUDE.md 9 (Abschluss Phase 0): alle Bonner Zusatzthemen aus; „technik“ bis Phase 5."""
    erwartet = {"haushalt", "baustellen", "anliegen", "wahlen", "themenseiten", "kontext", "soll", "chat",
                "einfache_sprache", "kurzfassungen", "mitmachen", "besetzung", "technik"}
    assert set(config.ZUSATZTHEMEN) == erwartet
    assert not any(config.ZUSATZTHEMEN.values())


# --- Export und Datenschutz ------------------------------------------------------------------------------------------

def _einwohner_kette(oparl):
    """Vorlage 2 ist eine Anregung nach § 24 GO NRW (erkannt am Titel, EINWOHNER_TITEL, ohne Bezug auf eine Stadt;
    die Wuppertaler Vorlagenarten folgen mit Messstufe 5), Vorlage 4 ihre Folgevorlage."""
    p2, p4 = oparl.papers[1], oparl.papers[3]
    p2["name"] = "Anregung nach § 24 GO NRW: Spielplatz"
    p2["subordinatedPaper"] = [p4["id"]]
    p4["superordinatedPaper"] = [p2["id"]]
    return {p2["reference"], p4["reference"]}


def _vorlagen_im_export(out):
    """Drucksache → Vorlage aus allen Gebietsdateien (ortsteile/, bezirke/, ohne Ortsbezug)."""
    vorlagen = {}
    for f in out.rglob("*.json"):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for p in doc.get("papers", []) if isinstance(doc, dict) and isinstance(doc.get("papers"), list) else []:
            if isinstance(p, dict) and "reference" in p:
                vorlagen[p["reference"]] = p
    return vorlagen


def test_datenschutzregel_wirkt_bei_abgeschaltetem_chat(oparl, monkeypatch):
    from pipeline import export
    _alle_aus(monkeypatch)
    kette = _einwohner_kette(oparl)
    sessionnet.fetch_all()
    build.build()
    export.export()
    out = config.EXPORT / config.STADT
    index = json.loads((out / "index.json").read_text())
    assert index["meta"]["funktionen"]["chat"] is False
    assert not (out / "chat").exists()                      # Ratsassistent aus: keine Daten für ihn
    vorlagen = _vorlagen_im_export(out)
    assert set(vorlagen) == {p["reference"] for p in oparl.papers}
    # keine Vorgangsseite für die Anregung und ihre Folgevorlage, wohl aber für die übrigen Vorlagen
    assert {r for r, p in vorlagen.items() if p.get("seite")} == set(vorlagen) - kette
    # Kurzfassung und Soll-Modell nur mit Freigabe
    assert all("kurzfassung" not in p and p.get("soll") is None for p in vorlagen.values())
    for datei in ("soll.json", "prozessarten.json", "baustellen.json", "kontext.json", "kurzfassungen.tsv"):
        assert not (out / datei).exists(), datei
    dcat = (out / "dcat.jsonld").read_text()
    assert "prozessarten" not in dcat and "baustellen" not in dcat and "kontext" not in dcat
    assert "kurzfassungen" not in dcat


def test_chat_freigegeben_schreibt_daten_des_assistenten(oparl, monkeypatch, tmp_path):
    """Gegenprobe: mit Freigabe entstehen die Dateien des Assistenten; die Datenschutzregel ist dieselbe."""
    from pipeline import export
    _alle_aus(monkeypatch)
    monkeypatch.setitem(config.ZUSATZTHEMEN, "chat", True)
    monkeypatch.setattr(config, "BESETZUNG", tmp_path / "fehlt_besetzung.json")
    kette = _einwohner_kette(oparl)
    sessionnet.fetch_all()
    build.build()
    export.export()
    out = config.EXPORT / config.STADT
    index = json.loads((out / "index.json").read_text())
    assert {k for k, v in index["meta"]["funktionen"].items() if v} == {"chat"}
    assert kette <= set(json.loads((out / "chat" / "einwohner.json").read_text())["drucksachen"])
    vorlagen = _vorlagen_im_export(out)
    assert {r for r, p in vorlagen.items() if p.get("seite")} == set(vorlagen) - kette


def test_datenschutzregel_liegt_im_kernmodul():
    """maske.py lädt chat.py nicht (Ratsassistent abschaltbar); chat.einwohner bleibt als Alias."""
    r = subprocess.run([sys.executable, "-c", "import sys, pipeline.maske, pipeline.volltext; "
                        "print('pipeline.chat' in sys.modules)"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "False", r.stderr
    from pipeline import chat
    assert chat.einwohner is maske.einwohner and chat.EINWOHNER is maske.EINWOHNER
    papers = [{"reference": "A", "paper_type": "Antrag", "name": "Anregung: Spielplatz", "superordinated": [],
               "subordinated": [{"reference": "B"}]},
              {"reference": "B", "paper_type": "Stellungnahme", "name": "Stellungnahme der Verwaltung",
               "superordinated": [{"reference": "A"}], "subordinated": [{"reference": "C"}]},
              {"reference": "C", "paper_type": "Mitteilung", "name": "Mitteilung", "superordinated": [{"reference": "B"}],
               "subordinated": []},
              {"reference": "D", "paper_type": "Beschlussvorlage", "name": "Haushalt", "superordinated": [],
               "subordinated": []}]
    assert maske.einwohner(papers) == ["A", "B", "C"]


# --- Seiten (seo) ----------------------------------------------------------------------------------------------------

def _seo_attrappe(monkeypatch):
    aufrufe = []

    def schreiber(name, pfade=()):
        def f(*a, **k):
            aufrufe.append(name)
            return list(pfade)
        return f
    monkeypatch.setattr(gebietsseiten, "write", schreiber("gebiete"))
    monkeypatch.setattr(dossier, "write", schreiber("themenseite", ["thema/x/"]))
    monkeypatch.setattr(dossier, "uebersicht", schreiber("themenuebersicht", ["thema/"]))
    monkeypatch.setattr(haushaltsseite, "write", schreiber("haushalt", ["haushalt/"]))
    monkeypatch.setattr(rssseite, "write", schreiber("rss", ["rss/"]))
    monkeypatch.setattr(begriffsseite, "write", schreiber("begriffe", ["begriffe/"]))
    monkeypatch.setattr(einfachseite, "write", schreiber("einfach", ["einfach/"]))
    monkeypatch.setattr(technikseite, "write", schreiber("technik", ["technik/"]))
    monkeypatch.setattr(vorgangsseiten, "write", schreiber("vorgaenge"))
    return aufrufe


def test_seo_erzeugt_nur_seiten_freigegebener_themen(tmp_path, monkeypatch):
    _alle_aus(monkeypatch)
    aufrufe = _seo_attrappe(monkeypatch)
    (tmp_path / "index.html").write_text(INDEX_HTML.read_text(encoding="utf-8"), encoding="utf-8")
    seo.write(tmp_path, "https://wuppertal.ratsatlas.de/")
    # Kern: Gebiete, Feeds, Begriffe, Vorgangsseiten
    assert sorted(aufrufe) == ["begriffe", "gebiete", "rss", "vorgaenge"]
    sitemap = (tmp_path / "sitemap-seiten.xml").read_text()
    assert all(f"/{pfad}<" not in sitemap for pfad in SEITEN.values())
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert all(f'href="{pfad}' not in html for pfad in SEITEN.values())
    assert 'data-funktion="themenseiten"' not in html and 'data-funktion="einfache_sprache"' not in html

    aufrufe.clear()
    for k in ("themenseiten", "haushalt", "einfache_sprache", "technik"):
        monkeypatch.setitem(config.ZUSATZTHEMEN, k, True)
    (tmp_path / "index.html").write_text(INDEX_HTML.read_text(encoding="utf-8"), encoding="utf-8")
    seo.write(tmp_path, "https://wuppertal.ratsatlas.de/")
    assert {"themenseite", "themenuebersicht", "haushalt", "einfach", "technik"} <= set(aufrufe)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert all(f'<a class="card" href="{pfad}" data-funktion=' in html for pfad in SEITEN.values())


def test_elemente_der_zusatzthemen_sind_ohne_skript_verborgen():
    """Jedes Element mit data-funktion trägt hidden (app.js applyFunktionen blendet nur Freigegebenes ein); Karten und
    Listeneinträge mit Links auf Seiten der Zusatzthemen halten die Attributfolge, die seo.AUS_FUNKTION erwartet."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    tags = re.findall(r"<[a-z]+\b[^>]*\bdata-funktion=\"\w+\"[^>]*>", html)
    assert len(tags) >= 8
    assert all(re.search(r"\shidden\b", t) for t in tags), [t for t in tags if " hidden" not in t]
    for k, pfad in SEITEN.items():
        assert f'<a class="card" href="{pfad}" data-funktion="{k}" hidden>' in html
    # nach seo.ohne_abgeschaltete bleibt kein Link auf eine nicht erzeugte Seite
    rest = seo.ohne_abgeschaltete(html)
    assert all(f'href="{pfad}' not in rest for pfad in SEITEN.values())
    # keine Volltextsuche über OParl-Lite (in Wuppertal entfallen): kein Bonner Host in der CSP
    assert "machdenstaat" not in re.search(r'Content-Security-Policy" content="([^"]*)"', html).group(1)


def test_volltextsuche_hat_keinen_schalter_und_bleibt_aus(monkeypatch):
    html = '<div><a class="card" href="x/" data-funktion="volltextsuche" hidden>X</a><li data-funktion="soll" hidden>Y</li></div>'
    monkeypatch.setitem(config.ZUSATZTHEMEN, "soll", False)
    assert seo.ohne_abgeschaltete(html) == "<div></div>"
    monkeypatch.setitem(config.ZUSATZTHEMEN, "soll", True)
    assert seo.ohne_abgeschaltete(html) == '<div><li data-funktion="soll" hidden>Y</li></div>'


def test_kernseiten_verlinken_keine_abgeschalteten_seiten(tmp_path, monkeypatch):
    _alle_aus(monkeypatch)
    fuss = gebietsseiten._page("https://wuppertal.ratsatlas.de/", "gebiete/", "T", "D", "<p>x</p>", "../")
    assert "einfach/" not in fuss and "gebiete/" in fuss
    rss = rssseite.body(tmp_path, "https://wuppertal.ratsatlas.de/", "../")
    assert "thema/" not in rss and "dossiers/" not in rss
    monkeypatch.setitem(config.ZUSATZTHEMEN, "einfache_sprache", True)
    monkeypatch.setitem(config.ZUSATZTHEMEN, "themenseiten", True)
    assert 'href="../einfach/"' in gebietsseiten._page("https://wuppertal.ratsatlas.de/", "gebiete/", "T", "D", "", "../")
    rss = rssseite.body(tmp_path, "https://wuppertal.ratsatlas.de/", "../")
    assert 'href="../thema/"' in rss and "dossiers/" in rss


# --- Prüfung (check) -------------------------------------------------------------------------------------------------

def test_check_weist_abgeschaltete_zusatzthemen_aus(monkeypatch, capsys):
    _alle_aus(monkeypatch)

    def nicht_aufrufen():
        raise AssertionError("Kontextdaten trotz Abschaltung geprüft")
    monkeypatch.setattr(kontext, "pruefen", nicht_aufrufen)
    assert check.zusatzthemen() == []
    out = capsys.readouterr().out
    for thema in ("besetzung", "soll", "kontext"):
        assert f"Zusatzthema „{thema}“)\nabgeschaltet" in out, thema

    monkeypatch.setitem(config.ZUSATZTHEMEN, "kontext", True)
    monkeypatch.setattr(kontext, "pruefen", lambda: ["Testbefund"])
    with pytest.raises(SystemExit, match="Kontextdaten: Testbefund"):
        check.zusatzthemen()
