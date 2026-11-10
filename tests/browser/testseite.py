"""Testseite für die Browser-Prüfung (tests/browser/*.test.mjs) aus erfundenen Daten.

Aufruf: python3 tests/browser/testseite.py <ziel> [<adresse>]
Schreibt zwei Fassungen der Seite:
- <ziel>/voll: site/ mit Gesamtexport (data/export) und den Seiten aus `seo.write` (Vorgänge, Begriffe, Gebiete, RSS,
  Sitemaps) für die Adresse <adresse> (Vorgabe http://127.0.0.1:8765/). Die Rohdaten kommen vom lokalen
  OParl-Testserver (tests/oparl_testserver.py) über den Kölner Adapter (sessionnet.fetch_all), danach build und export
  wie im regelmäßigen Lauf.
- <ziel>/leer: nur site/, ohne data/ (Stand vor dem ersten Export).

Keine Anfrage an fremde Hosts: der Endpunkt ist der Testserver auf 127.0.0.1; die modulweiten Öffner der Pipeline
(abruf, net) lassen während der Erzeugung nur Testadressen zu (wie tests/conftest.py). Alle Namen sind erfunden und
als Testnamen erkennbar (CLAUDE.md 1: keine erfundenen Wuppertaler Werte); keine Daten der Stadt, Bonns oder Kölns.
Anders als Bonn (tests.yml, Job browser: echte Rohdaten aus dem Zwischenspeicher oder Abruf) ohne Abruf von
Datenquellen."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for pfad in (ROOT / "tests", ROOT):
    if str(pfad) not in sys.path:
        sys.path.insert(0, str(pfad))

from oparl_testserver import Daten, oparl_server_starten, pfade_umlenken  # noqa: E402

ADRESSE = "http://127.0.0.1:8765/"
GEO_NAMEN = {"quartiere": ("Testquartier A", "Testquartier B"), "bezirk": "Testbezirk 1", "strasse": "Teststraße"}


class TestDaten(Daten):
    """Synthetische Vorlagen wie in den Python-Tests, mit klar erfundenen Namen."""
    GREMIUM_BV = "Bezirksvertretung 1 (Testbezirk 1)"
    TITEL_ORT = "Umgestaltung der Teststraße in Testquartier A"
    UNTERORT = "Testquartier B"


class _NurTestadressen:
    """Hülle um einen modulweiten Öffner: Anfragen an andere Hosts als Testadressen brechen die Erzeugung ab."""

    def __init__(self, oeffner):
        self._oeffner = oeffner

    def open(self, req, *a, **k):
        from pipeline import abruf
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if not abruf.testadresse(url):
            raise RuntimeError(f"Anfrage an einen fremden Host beim Erzeugen der Testseite: {url}")
        return self._oeffner.open(req, *a, **k)

    def __getattr__(self, name):
        return getattr(self._oeffner, name)


def erzeugen(ziel, adresse=ADRESSE):
    """Erzeugt <ziel>/voll und <ziel>/leer (siehe oben); vorhandene Fassungen werden ersetzt. Liefert beide Pfade."""
    from pipeline import abruf, build, config, export, net, seo, sessionnet
    ziel = Path(ziel)
    voll, leer = ziel / "voll", ziel / "leer"
    alt = []

    def setze(obj, name, wert):
        alt.append((obj, name, getattr(obj, name)))
        setattr(obj, name, wert)

    umgebung = {k: os.environ.pop(k) for k in ("RATSATLAS_STADT_INFORMIERT", "RATSATLAS_VOLLABRUF") if k in os.environ}
    server, daten = oparl_server_starten(TestDaten)
    try:
        with tempfile.TemporaryDirectory(prefix="ratsatlas-testseite-") as tmp:
            pfade_umlenken(Path(tmp), daten.b, setze, GEO_NAMEN)
            setze(abruf, "_OEFFNER", _NurTestadressen(abruf._OEFFNER))
            setze(net, "_OEFFNER", _NurTestadressen(net._OEFFNER))
            sessionnet.fetch_all()
            build.build()
            export.export()
            if not (config.EXPORT / config.STADT / "index.json").exists():
                raise RuntimeError("Gesamtexport fehlt (index.json); Abruf vom Testserver gescheitert?")
            for fassung in (voll, leer):
                if fassung.exists():
                    shutil.rmtree(fassung)
            shutil.copytree(ROOT / "site", voll)
            shutil.copytree(config.EXPORT, voll / "data" / "export")
            seo.write(voll, adresse)
    finally:
        server.shutdown()
        server.server_close()
        for obj, name, wert in reversed(alt):
            setattr(obj, name, wert)
        abruf.sperre_freigeben()
        os.environ.update(umgebung)
    shutil.copytree(ROOT / "site", leer)
    return voll, leer


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__.split("\n\n")[1].splitlines()[0])
    # Sperrdatei nie in ~/.cache (wie tests/conftest.py); der Abruf vom Testserver nimmt sie nicht, sicher ist sicher
    sperre = None if os.environ.get("RATSATLAS_SPERRE") else tempfile.mkdtemp(prefix="ratsatlas-sperre-")
    if sperre:
        os.environ["RATSATLAS_SPERRE"] = sperre
    try:
        for pfad in erzeugen(sys.argv[1], *sys.argv[2:]):
            print(pfad)
    finally:
        if sperre:
            shutil.rmtree(sperre, ignore_errors=True)
