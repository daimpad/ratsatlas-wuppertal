"""Rechtsverbindliche Bebauungspläne der Stadt Wuppertal: Ablage in data/geo/ (config.BPLAN) ohne Bearbeitung.

Quelle laut CLAUDE.md 3.2: config.SOURCES[config.QUELLE_BPLAN] (daten.wuppertal.de, rvbBebauungsplanverfahren, EPSG 4326),
Lizenz CC BY-ND 4.0. Open.NRW nennt abweichend „Andere geschlossene Lizenz“ (offen, CLAUDE.md 8); geführt wird die
Angabe aus config.SOURCES. Wegen ND werden die Geometrien weder vereinfacht noch gerundet, repariert oder umprojiziert:
speichern() übernimmt die Features der Quelle mit denselben Werten und in derselben Reihenfolge und ergänzt nur „meta“.

Aufbau nach ratsatlas-koeln @d609111 (pipeline/bplan.py: meta mit source/license/retrieved_at, Schutzregel config_min),
aber ohne _gerundet() und ohne Sortierung. Abweichung für den gemeinsamen Kern: Köln vereinfacht (etwa 0,5 m) und
rundet auf 6 Stellen, dort zulässig (dl-de/by 2.0); hier nicht.

Offen (TODO Messstufe G, explore/STUFEN.md): Abruf über einen an die Abrufpolitik gebundenen Weg (CLAUDE.md 5.1; net.py
verweigert Server der Stadt, abruf.py ist bis zur Information der Stadt gesperrt), Feldnamen, Plannummernschema und
damit Name/Sortierung je Plan für plans.py, Anteil ungültiger Flächen und Dateigröße der 691 Pläne. Bis dahin ruft kein
Schritt dieses Modul auf; getestet wird mit erfundenen Daten.
"""
import json
from datetime import datetime, timezone

from . import config


def config_min(alt):
    """Ein neuer Stand ersetzt den alten nur mit mindestens 90 % der bisherigen Pläne (wie beim OParl-Abruf; aus Köln)."""
    return int(0.9 * alt)


def speichern(sammlung, ziel=None, jetzt=None):
    """Schreibt die FeatureCollection der Quelle nach ziel (Vorgabe config.BPLAN). Die Features bleiben unverändert
    (gleiche Geometrie, gleiche Eigenschaften, gleiche Reihenfolge); Features ohne Geometrie werden nur gezählt.
    Bricht ab, wenn der neue Stand weniger als 90 % des bisherigen enthält; dann bleibt der alte Stand."""
    ziel = ziel or config.BPLAN
    feats = [f for f in sammlung.get("features") or [] if f.get("geometry")]
    ohne = len(sammlung.get("features") or []) - len(feats)
    alt = json.loads(ziel.read_text(encoding="utf-8"))["features"] if ziel.exists() else []
    if len(feats) < config_min(len(alt)):
        raise RuntimeError(f"nur {len(feats)} Pläne statt bisher {len(alt)}; Stand bleibt")
    quelle = config.SOURCES[config.QUELLE_BPLAN]
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps({
        "type": "FeatureCollection",
        "meta": {"source": quelle["url"], "license": quelle["license"], "attribution": config.NAMENSNENNUNG_BPLAN,
                 "retrieved_at": jetzt or datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "geometrie": "unverändert (CC BY-ND 4.0: keine Vereinfachung, Rundung oder Reparatur)",
                 "ohne_geometrie": ohne},
        "features": feats}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(feats)
