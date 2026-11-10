// Kontrast über dem Kartenbild (WCAG 2.1: 1.4.3 Kontrast Minimum), im Browser gerechnet. axe kann Text über dem
// Kartenbild nicht bewerten (`imgNode`, „unvollständig“). Statt der Kacheln werden Kartentöne angenommen (Aufruf mit
// einer Reihe von Grautönen von Schwarz bis Weiß, wcag.test.mjs: Schritte von 16). Beim Überblenden in sRGB steigt die
// Leuchtdichte des Ergebnisses mit jedem Kanal des Untergrunds; Schwarz und Weiß begrenzen also die Leuchtdichte des
// Untergrunds unter jedem Kartenton, auch unter der farbigen OSM-Karte, und die Grautöne dazwischen erreichen jede
// Leuchtdichte in diesem Bereich. Der kleinste Kontrast liegt aber nicht unbedingt an den Grenzen: Liegt die
// Leuchtdichte der Schrift innerhalb des Bereichs, liegt er dazwischen; deshalb die Reihe statt nur der Grenzen. Für
// deckende Schrift genügt Grau, weil nur die Leuchtdichte des Untergrunds zählt; bei durchscheinender Schrift ist das
// eine Näherung.
// Rechnung je sichtbarem Textknoten: Hintergründe der Vorfahren von innen nach außen, bis eine deckende Fläche kommt;
// erreicht die Kette #map, <header>, <main>, <body> oder <html>, liegt darunter das Kartenbild (die Karte füllt das
// Fenster, die Bedienflächen schweben darüber); bei offenem modalem Dialog zusätzlich dessen ::backdrop. Verläufe
// zählen mit jeder Farbstufe einzeln. Deckkraft (opacity) eines Elements und seiner Vorfahren mindert die Deckkraft der
// Schrift und die seiner Hintergründe (Näherung der Gruppenüberblendung; eine Fläche mit opacity < 1 ist nicht
// deckend). Die ungünstigste Kombination gilt; gemeldet wird der Kartenton, bei dem sie auftritt.
// Glas mit backdrop-filter (Unschärfe 20 px, auf dem Telefon 8 px) mittelt das Kartenbild darunter: Dunkle Linien und
// Beschriftungen der Kacheln verschwinden darin, ungünstigster Ton ist die mittelgraue Fläche (graue Kacheln: sehr
// hell bis mittelgrau). Für solche Ketten gilt daher mindestens Mittelgrau (#808080), sonst der angenommene Ton.
// Rand um die Schrift: Nach dem Understanding zu 1.4.3 zählt ein schmaler Rand zur Schrift, als Hintergrund gilt erst
// ein breiter Halo. Als Halo gilt hier ein deckender Rand derselben Farbe (text-shadow ohne Unschärfe in alle vier
// Diagonalen) von mindestens 2 px oder von 1 px zusammen mit unscharfen Schatten derselben Farbe (Unschärfe ≥ 3 px), die
// ihn verbreitern (Beschriftungen der Gebiete: 1 px und 3/3/6 px); solche Schrift wird gegen diesen Halo gerechnet.
// Aufruf: kontrastUeberKarte(basen) mit einer Liste von Kartentönen [r, g, b] (oder einem einzelnen Ton).
export function kontrastUeberKarte(basen) {
  if (typeof basen[0] === "number") basen = [basen];
  const MITTELGRAU = [128, 128, 128];
  const parse = (s) => {
    const m = s && s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const t = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return [t[0], t[1], t[2], t.length > 3 ? t[3] : 1];
  };
  const ueber = (o, u) => [0, 1, 2].map((k) => o[3] * o[k] + (1 - o[3]) * u[k]);  // o über deckendem u
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const kontrast = (a, b) => { const [h, d] = [lum(a), lum(b)].sort((x, y) => y - x); return (h + 0.05) / (d + 0.05); };
  const BODEN = new Set([document.documentElement, document.body, document.querySelector("main"),
    document.querySelector("header"), document.querySelector("#map")]);

  // Deckkraft eines Elements samt Vorfahren (opacity)
  const deckkraft = (el) => { let d = 1; for (let e = el; e; e = e.parentElement) d *= Number(getComputedStyle(e).opacity); return d; };
  const mal = (f, d) => (f ? [f[0], f[1], f[2], f[3] * d] : f);
  // mögliche deckende Hintergrundfarben unter dem Element, Kartenton basis; dazu der wirksame Kartenton (unter Glas mit
  // Unschärfe mindestens Mittelgrau)
  function hintergruende(el, basis) {
    const schichten = [];
    let unscharf = false;
    for (let e = el; e; e = e.parentElement) {
      if (BODEN.has(e)) break;
      const st = getComputedStyle(e);
      if (st.backdropFilter && st.backdropFilter !== "none") unscharf = true;
      const d = deckkraft(e);
      const stufen = [...st.backgroundImage.matchAll(/rgba?\([^)]+\)/g)].map((m) => mal(parse(m[0]), d));
      const farbe = mal(parse(st.backgroundColor), d);
      schichten.push({ farbe, stufen });
      if ((farbe && farbe[3] >= 1) || (stufen.length && stufen.every((s) => s[3] >= 1))) break;
    }
    const ton = unscharf ? basis.map((k, i) => Math.max(k, MITTELGRAU[i])) : basis;
    let karte = ton;
    const dialog = el.closest("dialog[open]");
    if (dialog && dialog.matches(":modal")) {
      const b = parse(getComputedStyle(dialog, "::backdrop").backgroundColor);
      if (b && b[3] > 0) karte = ueber(b, karte);
    }
    let unten = [karte];
    for (const { farbe, stufen } of schichten.reverse()) {
      if (farbe && farbe[3] > 0) unten = unten.map((u) => ueber(farbe, u));
      if (stufen.length) unten = stufen.flatMap((s) => unten.map((u) => ueber(s, u)));
    }
    return { unten, karte: ton };
  }

  // Halo um die Schrift (siehe oben): Farbe, sonst null
  function rand(st) {
    const alle = [...st.textShadow.matchAll(/(rgba?\([^)]+\))\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+([\d.]+)px/g)]
      .map((m) => ({ farbe: parse(m[1]), x: +m[2], y: +m[3], unschaerfe: +m[4] }));
    const schatten = alle.filter((s) => s.farbe[3] >= 1 && s.unschaerfe === 0 && Math.abs(s.x) >= 1 && Math.abs(s.y) >= 1);
    const ecken = new Set(schatten.map((s) => `${Math.sign(s.x)}${Math.sign(s.y)}`));
    if (ecken.size < 4) return null;
    const f = schatten[0].farbe;
    const gleich = (s) => s.farbe.slice(0, 3).every((k, i) => k === f[i]);
    if (!schatten.every(gleich)) return null;
    const breit = [...ecken].every((ecke) => schatten.some((s) => `${Math.sign(s.x)}${Math.sign(s.y)}` === ecke
      && Math.abs(s.x) >= 2 && Math.abs(s.y) >= 2));
    const verbreitert = alle.some((s) => gleich(s) && s.unschaerfe >= 3);
    return breit || verbreitert ? f : null;
  }

  const funde = [];
  let anzahl = 0;
  const pruefe = (el, farbeText, beschreibung) => {
    const st = getComputedStyle(el);
    const deck = deckkraft(el);
    const groesse = parseFloat(st.fontSize), gewicht = Number(st.fontWeight);
    const grenze = groesse >= 24 || (groesse >= 18.66 && gewicht >= 700) ? 3 : 4.5;
    const t = parse(farbeText);
    const r = rand(st);
    let min = Infinity, schlecht = null;
    for (const basis of r ? [null] : basen) {
      const { unten, karte } = r ? { unten: [r], karte: null } : hintergruende(el, basis);
      for (const h of unten) {
        const k = kontrast(ueber([t[0], t[1], t[2], t[3] * deck], h), h);
        if (k < min) { min = k; schlecht = karte; }
      }
    }
    anzahl++;
    if (min < grenze) {
      funde.push(`${schlecht ? `Karte rgb(${schlecht.map(Math.round)}): ` : "Halo: "}${beschreibung}: ${min.toFixed(2)} < ${grenze} (Schrift ${farbeText}, ${groesse}px/${gewicht})`);
    }
  };
  const sichtbar = (el) => {
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return false;
    // nur für Bildschirmleser (.visually-hidden, .site-title auf breiten Bildschirmen): abgeschnitten auf 1 px
    for (let e = el; e && e !== document.body; e = e.parentElement) {
      const st = getComputedStyle(e), q = e.getBoundingClientRect();
      if (st.clip === "rect(0px, 0px, 0px, 0px)" || (st.overflow === "hidden" && (q.width < 2 || q.height < 2))) return false;
    }
    return r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
  };
  const name = (el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${typeof el.className === "string" && el.className
    ? "." + el.className.trim().split(/\s+/).slice(0, 3).join(".") : ""}`;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const el = n.parentElement;
    if (!n.data.trim() || !el || el.closest("script, style, svg, noscript, .leaflet-tile-pane")) continue;
    if (el.closest(":disabled, [aria-disabled=true]")) continue;  // inaktive Bedienelemente sind ausgenommen (1.4.3)
    if (!sichtbar(el)) continue;
    pruefe(el, getComputedStyle(el).color, `${name(el)} „${n.data.trim().slice(0, 40)}“`);
  }
  for (const el of document.querySelectorAll("input[placeholder], textarea[placeholder]")) {
    if (el.value || el.disabled || !sichtbar(el)) continue;
    pruefe(el, getComputedStyle(el, "::placeholder").color, `${name(el)} Platzhalter`);
  }
  return { funde, anzahl };
}

// Fokusrahmen von Bedienelementen, die direkt auf dem Kartenbild liegen (Leaflet-Steuerung, Marker): Der Rahmen
// (outline, --accent-fill) muss gegen die Farben daneben 3:1 erreichen (1.4.11). Auf Mittelgrau erreicht kein
// einfarbiger Rahmen das; deshalb trägt er einen weißen Ring (box-shadow ohne Unschärfe) zwischen Rahmen und Karte.
// Geprüft: Ring vorhanden, deckend und mindestens 2 px breiter als Abstand und Rahmen zusammen (Rahmen liegt innen
// und außen auf dem Ring); Rahmen gegen den Ring ≥ 3:1.
export function fokusringAufKarte() {
  const parse = (s) => { const t = s.match(/rgba?\(([^)]+)\)/)[1].split(/[\s,/]+/).filter(Boolean).map(Number); return [t[0], t[1], t[2], t.length > 3 ? t[3] : 1]; };
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
  const kontrast = (a, b) => { const [h, d] = [lum(a), lum(b)].sort((x, y) => y - x); return (h + 0.05) / (d + 0.05); };
  const a = document.activeElement, st = getComputedStyle(a);
  const umriss = parseFloat(st.outlineWidth), abstand = parseFloat(st.outlineOffset);
  const ringe = [...st.boxShadow.matchAll(/(rgba?\([^)]+\))\s+0px\s+0px\s+0px\s+([\d.]+)px(?!\s*inset)/g)]
    .map((m) => ({ farbe: parse(m[1]), breite: parseFloat(m[2]) }))
    .filter((r) => r.farbe[3] >= 1 && r.breite >= umriss + Math.max(abstand, 0) + 2);
  if (st.outlineStyle === "none" || !(umriss > 0)) return "kein Umriss";
  if (!ringe.length) return `kein deckender Ring unter dem Umriss (box-shadow: ${st.boxShadow})`;
  const k = kontrast(parse(st.outlineColor), ringe[0].farbe);
  return k >= 3 ? "ok" : `Umriss gegen Ring ${k.toFixed(2)} < 3`;
}
