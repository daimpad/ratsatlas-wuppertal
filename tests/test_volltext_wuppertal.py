"""volltext für Wuppertaler Vorlagentexte (Phase 3, 17.11.2026): Kopf bis zur Beratungsfolge „Sitzung am Gremium“,
Gremien und Dienstadressen ausgeblendet, Hauptdokument aus der ersten Anlage mit Text. Erfundener Text, ohne Netz."""
import gzip

from pipeline import config, dokumente, volltext

TEXT = """Seite: 1/2
Beschlussvorlage
Geschäftsbereich
Ressort 999 - Testressort
Drucks.-Nr.:
VO/0001/26
Sitzung am Gremium  Beschlussqualität
03.02.2026 BV Testbezirk Empfehlung/Anhörung
23.02.2026 Rat der Stadt Testhausen Entscheidung
Grund der Vorlage
Ausbau der Probestraße im Testquartier.
Johannes-Rau-Platz 1, 42275 Testhausen
Anlagen
Plan Musterweg
"""


def test_kopf_gremien_und_adressen():
    haupt, anlagen = volltext.clean(TEXT)
    assert "BV Testbezirk" not in haupt and "Sitzung am Gremium" not in haupt.strip()[:0] + haupt
    assert "Probestraße" in haupt and "Johannes-Rau-Platz" not in haupt
    assert "Musterweg" in anlagen and "Musterweg" not in haupt
    assert volltext.header_end(TEXT) > TEXT.index("Rat der Stadt")


def test_haupttext_erste_anlage_mit_text(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "TEXTE_ORDNER", tmp_path)
    for kennung, inhalt in (("datei/2", "Zweite"),):
        with gzip.open(dokumente.textpfad(dokumente.schluessel(kennung)), "wt", encoding="utf-8") as f:
            f.write(inhalt)
    p = {"auxiliaryFile": [{"id": "datei/1"}, {"id": "datei/2"}]}
    assert volltext.haupttext(p) == "Zweite"          # die erste Anlage hat (noch) keinen Text
    assert volltext.haupttext({"auxiliaryFile": []}) is None
