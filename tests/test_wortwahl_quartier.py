"""Wortwahl „Quartier“ statt der Bonner „Ortsteil“ in sichtbaren Zeichenketten des Kerns (Phase 4, Teil A).

Ergänzt die Browser-Prüfung (tests/browser/hilfe.mjs, ohneOrtsteil): Diese sieht nur, was die Testseite tatsächlich
zeigt; Tooltips beim Überfahren, seltene Meldungen und Zweige ohne Testdaten prüft dieser Test statisch. Kommentare,
Docstrings und Bezeichner (navOrtsteile, clickOrtsteil …) zählen nicht; Schlüssel und Pfade heißen weiter „ortsteil“.
"""
import ast
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
JS = ["site/app.js", "site/tour.js", "site/timeline.js"]
HTML = ["site/index.html", "site/404.html"]
PY = ["pipeline/gebietsseiten.py", "pipeline/vorgangsseiten.py", "pipeline/begriffsseite.py", "pipeline/glossar.py",
      "pipeline/rssseite.py"]
# „Ortsteil“ als eigenes Wort (nicht Teil eines Bezeichners wie navOrtsteile)
WORT = re.compile(r"(?<![A-Za-zÄÖÜäöüß_$])Ortsteil")
# dokumentierte Ausnahme: Feldname der Bonner Quelle im abgeschalteten Zusatzthema anliegen (site/app.js)
AUSNAHMEN = ["nur Kategorie, Tag, Ortsteil und Status übernommen"]


def _ohne_js_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # Zeilenkommentar nur am Zeilenanfang oder nach Leerraum (nicht „https://“ in Zeichenketten)
    return re.sub(r"(^|\s)//.*$", r"\1", text, flags=re.M)


def _funde(text: str) -> list[str]:
    for a in AUSNAHMEN:
        text = text.replace(a, "")
    return [z.strip()[:120] for z in text.splitlines() if WORT.search(z)]


def test_js_und_html_ohne_ortsteil():
    funde = {}
    for rel in JS:
        f = _funde(_ohne_js_kommentare((WURZEL / rel).read_text(encoding="utf-8")))
        if f:
            funde[rel] = f
    for rel in HTML:
        pfad = WURZEL / rel
        if pfad.exists():
            f = _funde(re.sub(r"<!--.*?-->", "", pfad.read_text(encoding="utf-8"), flags=re.S))
            if f:
                funde[rel] = f
    assert funde == {}


def _docstrings(baum: ast.AST) -> set[int]:
    ids = set()
    for k in ast.walk(baum):
        if isinstance(k, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and k.body:
            erst = k.body[0]
            if isinstance(erst, ast.Expr) and isinstance(erst.value, ast.Constant) and isinstance(erst.value.value, str):
                ids.add(id(erst.value))
    return ids


def test_seitenmodule_ohne_ortsteil():
    funde = {}
    for rel in PY:
        baum = ast.parse((WURZEL / rel).read_text(encoding="utf-8"))
        doc = _docstrings(baum)
        f = [k.value[:120] for k in ast.walk(baum)
             if isinstance(k, ast.Constant) and isinstance(k.value, str) and id(k) not in doc and WORT.search(k.value)]
        if f:
            funde[rel] = f
    assert funde == {}


def test_pruefung_erkennt_ortsteil():
    # Gegenprobe der Hilfsfunktionen: sichtbare Zeichenkette wird erkannt, Kommentar und Bezeichner nicht
    js = 'const a = "Klick zeigt den Ortsteil"; // Ortsteil\nnavOrtsteile.addTo(map); /* Ortsteile */'
    assert _funde(_ohne_js_kommentare(js)) == ['const a = "Klick zeigt den Ortsteil";']
    assert _funde(_ohne_js_kommentare("navOrtsteile.eachLayer(f); // Ortsteile")) == []
