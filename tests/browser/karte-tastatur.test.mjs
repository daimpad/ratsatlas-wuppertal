// Inhalte der Karte per Tastatur (WCAG 2.1.1 Tastatur, 2.4.3 Fokusreihenfolge, 4.1.2 Name und Rolle) mit erfundenen
// Daten (testseite.py: ein Stadtbezirk, zwei Quartiere, zwei Einzelpunkte als Sammelpunkt, ein Einzelpunkt, drei
// Bebauungspläne; ein Test mit 60 Plänen per page.route): Stadtbezirke, Quartiere, Einzelpunkte und Planflächen sind
// SVG-Pfade; jeder trägt role="button", einen Namen und tabindex (0 im freien Kartenfeld, sonst -1; Pläne nur bis 25
// im Feld, Quartiere in der Ansicht eines Stadtbezirks nur dessen), Eingabe- und Leertaste wirken wie ein Klick, und der
// Fokus fällt danach nicht an <body>; die Maus legt den Fokus nicht auf Pfade. Läuft in Chromium und Firefox
// (BROWSER=firefox, hilfe.mjs); Firefox erreichte die Pfade vor der Umsetzung gar nicht per Tab, Chromium ohne Namen
// und in keinem Browser ließen sie sich aktivieren (inventur/WCAG_vorpruefung.md, Nachtrag 10.11.2026).
// Bildschirmleser: nicht automatisierbar, offen.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe, BROWSER } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

const QUARTIER = "?gebiet=ortsteil:testquartier-a";
const PFAD = ".leaflet-map-pane path";

// fokussiertes Element in Kurzform
const aktiv = (page) => page.evaluate(() => {
  const a = document.activeElement;
  if (!a || a === document.body) return "body";
  return a instanceof SVGPathElement ? `pfad ${a.getAttribute("aria-label")}` : a.id ? `#${a.id}` : a.tagName.toLowerCase();
});

// per Tab ab dem Suchfeld bis zum Pfad, dessen data-ziel mit `ziel` beginnt; Liste der unterwegs erreichten Ziele
async function tabZu(page, ziel, max = 80) {
  await page.locator("#q").focus();
  const weg = [];
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const z = await page.evaluate(() => document.activeElement?.dataset?.ziel || null);
    if (z) weg.push(z);
    if (z?.startsWith(ziel)) return weg;
  }
  assert.fail(`${ziel} nicht per Tab erreicht (${BROWSER}); erreicht: ${weg.join(", ") || "kein Pfad"}`);
}

// alle Ziele der Karte in der Tab-Folge: Tab ab dem Suchfeld, bis der Fokus die Karte hinter sich lässt
async function zieleInTabFolge(page) {
  await page.locator("#q").focus();
  const ziele = [];
  let inKarte = false;
  for (let i = 0; i < 80; i++) {
    await page.keyboard.press("Tab");
    const { ziel, karte } = await page.evaluate(() => ({ ziel: document.activeElement?.dataset?.ziel || null,
      karte: Boolean(document.activeElement?.closest(".leaflet-map-pane")) }));
    if (ziel) ziele.push(ziel);
    if (karte) inKarte = true;
    else if (inKarte) return ziele;
  }
  return ziele;
}

// Prüffunktion im Browser: jeder interaktive Pfad der Karte hat role="button", einen nicht leeren Namen, data-ziel und
// tabindex 0 oder -1; nicht interaktive Pfade (Umriss, Fokusstrich) sind aria-hidden und ohne tabindex; ruhende
// Beschriftungen der Gebiete (.nav-label) sind aria-hidden (Name und Zahl stehen im Namen der Fläche)
function pfadAngaben() {
  const funde = [];
  for (const l of document.querySelectorAll(".nav-label")) if (l.getAttribute("aria-hidden") !== "true") funde.push(`Beschriftung im Baum: ${l.textContent}`);
  for (const p of document.querySelectorAll(".leaflet-map-pane path")) {
    const kurz = `${p.getAttribute("aria-label") || p.getAttribute("class") || "Pfad"}`;
    if (p.classList.contains("leaflet-interactive")) {
      if (p.getAttribute("role") !== "button") funde.push(`Rolle fehlt: ${kurz}`);
      if (!(p.getAttribute("aria-label") || "").trim()) funde.push(`Name fehlt: ${kurz}`);
      if (!p.dataset.ziel) funde.push(`data-ziel fehlt: ${kurz}`);
      if (!["0", "-1"].includes(p.getAttribute("tabindex"))) funde.push(`tabindex ${p.getAttribute("tabindex")}: ${kurz}`);
    } else {
      if (p.getAttribute("aria-hidden") !== "true") funde.push(`nicht verborgen: ${kurz}`);
      if (p.hasAttribute("tabindex")) funde.push(`tabindex an nicht interaktivem Pfad: ${kurz}`);
    }
  }
  return funde;
}

// Taste auf dem fokussierten Pfad drücken; zählt DOM-Klicks auf ihm (genau einer, sonst doppelte Auslösung) und ob
// keydown abgefangen wurde (preventDefault; die Seite selbst scrollt nicht, body overflow: hidden, deshalb wird kein
// Bildlauf gemessen)
async function druecken(page, taste) {
  await page.evaluate(() => {
    const el = document.activeElement;
    window.__klicks = 0;
    window.__abgefangen = null;
    el.addEventListener("click", () => { window.__klicks++; });
    addEventListener("keydown", (e) => { window.__abgefangen = e.defaultPrevented; }, { once: true });
  });
  await page.keyboard.press(taste);
  return page.evaluate(() => ({ klicks: window.__klicks, abgefangen: window.__abgefangen }));
}

const strich = (page) => page.locator(".fokus-saum, .fokus-strich").count();

test("Pfade der Karte: Rolle, Name und tabindex in Startansicht, Quartiersansicht und mit Plänen; axe ohne Verstoß", async () => {
  for (const adresse of ["", QUARTIER, `${QUARTIER}&plaene=1`]) {
    const s = await oeffnen(t.browser, t.voll + adresse);
    const { page } = s;
    if (adresse.includes("plaene")) await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="plan:"]').length === 3);
    assert.deepEqual(await page.evaluate(pfadAngaben), [], adresse || "Start");
    const namen = await page.locator(`${PFAD}[role=button]`).evaluateAll((ps) => ps.map((p) => p.getAttribute("aria-label")));
    assert.ok(namen.includes("Stadtbezirk Testbezirk 1, 5 Vorlagen in den letzten 12 Monaten"), namen.join(" | "));
    // Einzelpunkt: Titel, Ort, Drucksachennummer
    if (adresse) assert.ok(namen.some((n) => /^Umgestaltung der Teststraße in Testquartier A, Teststraße \(Vorlage \S+\)$/.test(n)), `Einzelpunkt: ${namen.join(" | ")}`);
    if (adresse.includes("plaene")) {
      // Zeichenreihenfolge wie vor der Umsetzung: der erste Plan der Quelle liegt oben (DOM- und Tab-Folge umgekehrt)
      assert.deepEqual(namen.filter((n) => n.startsWith("Bebauungsplan")), ["Bebauungsplan Testplan 3", "Bebauungsplan Testplan 2", "Bebauungsplan Testplan 1"]);
    }
    // Sammelpunkt (HTML-Marker): Name mit der sichtbaren Zahl
    if (adresse) assert.match(await page.locator(".marker-cluster").first().getAttribute("aria-label"), /^Sammelpunkt mit 2 Orten/);
    assert.deepEqual(await axe(page), [], `axe ${adresse || "Start"}`);
    await pruefen(s);
  }
});

test("Gegenprobe Prüffunktion: fehlende Rolle, fehlender Name, fehlendes tabindex, sichtbarer Umriss und Beschriftung fallen auf", async () => {
  const s = await oeffnen(t.browser, t.voll + QUARTIER);
  const { page } = s;
  const funde = await page.evaluate((pruef) => {
    const ps = [...document.querySelectorAll('.leaflet-map-pane path.leaflet-interactive')];
    ps[0].removeAttribute("role");
    ps[1].setAttribute("aria-label", " ");
    ps[1].removeAttribute("tabindex");
    document.querySelector(".leaflet-map-pane path:not(.leaflet-interactive)").removeAttribute("aria-hidden");
    document.querySelector(".nav-label")?.removeAttribute("aria-hidden");
    return new Function(`return (${pruef})()`)();
  }, pfadAngaben.toString());
  for (const m of [/^Rolle fehlt/, /^Name fehlt/, /^tabindex null/, /^nicht verborgen/, /^Beschriftung im Baum/]) assert.ok(funde.some((f) => m.test(f)), `${m}: ${funde.join(" | ")}`);
  await pruefen(s);
});

test("Stadtbezirk per Tab und Eingabetaste: Quartiere erscheinen, Fokus auf dem ersten Quartier, Strich bleibt", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await tabZu(page, "bezirk:");
  assert.equal(await aktiv(page), "pfad Stadtbezirk Testbezirk 1, 5 Vorlagen in den letzten 12 Monaten");
  assert.equal(await page.evaluate(() => document.activeElement.matches(":focus-visible")), true, "Fokus sichtbar");
  assert.equal(await strich(page), 2, "Saum und Strich");
  const r = await druecken(page, "Enter");
  assert.deepEqual(r, { klicks: 1, abgefangen: true }, "genau ein Klick, keydown abgefangen");
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="ortsteil:"]').length === 2);
  assert.equal(await aktiv(page), "pfad Quartier Testquartier A im Stadtbezirk Testbezirk 1, 3 Vorlagen in den letzten 12 Monaten", "Fokus auf dem ersten Quartier (alphabetisch)");
  assert.equal(await page.evaluate(() => document.activeElement.matches(":focus-visible")), true, "Fokus sichtbar nach dem Wechsel");
  assert.equal(await strich(page), 2, "Saum und Strich am Quartier");
  // nach der Zoomanimation (moveend) bleibt der Fokus
  await page.waitForTimeout(800);
  assert.match(await aktiv(page), /^pfad Quartier Testquartier A/);
  // Tab geht zum nächsten Quartier
  await page.keyboard.press("Tab");
  assert.equal(await aktiv(page), "pfad Quartier Testquartier B im Stadtbezirk Testbezirk 1, 1 Vorlage in den letzten 12 Monaten");
  await pruefen(s);
});

test("Quartier per Leertaste: Gebiet gewählt, keydown abgefangen, Fokus nicht an <body>; gewähltes Quartier mit aria-current", async () => {
  let s = await oeffnen(t.browser, t.voll);
  let { page } = s;
  await tabZu(page, "bezirk:");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.dataset?.ziel === "ortsteil:testquartier-a");
  await page.keyboard.press("Tab");
  assert.match(await aktiv(page), /^pfad Quartier Testquartier B/);
  const r = await druecken(page, " ");
  assert.deepEqual(r, { klicks: 1, abgefangen: true });
  await page.waitForFunction(() => new URLSearchParams(location.search).get("gebiet") === "ortsteil:testquartier-b", null, { timeout: 5000 });
  await page.waitForTimeout(800);   // Gebiet geladen, Karte verschoben
  const a = await aktiv(page);
  assert.notEqual(a, "body", "Fokus fiel an <body>");
  assert.match(a, /^pfad (Quartier Testquartier B|Stadtbezirk Testbezirk 1)/, "Fokus auf dem Quartier oder seinem Stadtbezirk");
  assert.equal(await strich(page), 2, "Saum und Strich");
  await pruefen(s);
  // aria-current: Quartiere des Stadtbezirks bei gewähltem Testquartier A
  s = await oeffnen(t.browser, t.voll + QUARTIER);
  ({ page } = s);
  await tabZu(page, "bezirk:");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="ortsteil:"]').length === 2);
  const aktuell = await page.locator('path[data-ziel^="ortsteil:"]').evaluateAll((ps) => ps.map((p) => [p.dataset.ziel, p.getAttribute("aria-current")]));
  assert.deepEqual(aktuell, [["ortsteil:testquartier-a", "true"], ["ortsteil:testquartier-b", null]]);
  await pruefen(s);
});

test("Einzelpunkt und Bebauungsplan per Eingabetaste: Detailfeld zeigt den Vorgang bzw. die Planchronik, Fokus bleibt", async () => {
  const s = await oeffnen(t.browser, t.voll + `${QUARTIER}&plaene=1`);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="plan:"]').length === 3);
  await tabZu(page, "vorlage:");
  const punkt = await aktiv(page);
  // offener Tooltip wiederholt nur den Namen: kein aria-describedby (Leaflet setzt es beim Öffnen)
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-describedby")), null, "Einzelpunkt mit Beschreibung");
  assert.deepEqual(await druecken(page, "Enter"), { klicks: 1, abgefangen: true });
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Vorgang", null, { timeout: 3000 });
  const ref = punkt.match(/\(Vorlage (\S+)\)$/)[1];
  assert.match(await page.locator("#detail").innerText(), new RegExp(ref.replace(/[/.]/g, "\\$&")), "Referenz im Detailfeld");
  assert.equal(await aktiv(page), punkt, "Fokus bleibt auf dem Punkt");
  assert.equal(await strich(page), 2);
  await tabZu(page, "plan:Testplan 1");
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => document.activeElement.getAttribute("aria-describedby")), null, "Plan mit Beschreibung");
  assert.deepEqual(await druecken(page, " "), { klicks: 1, abgefangen: true });
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Bebauungsplan", null, { timeout: 3000 });
  assert.match(await page.locator("#detail").innerText(), /Testplan 1/);
  assert.equal(await aktiv(page), "pfad Bebauungsplan Testplan 1", "Fokus bleibt auf der Planfläche");
  await pruefen(s);
});

test("Tab-Halte nur im freien Kartenfeld: verschobene Planfläche tabindex -1 und nicht in der Tab-Folge, zurück 0", async () => {
  const s = await oeffnen(t.browser, t.voll + `${QUARTIER}&plaene=1`);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="plan:"]').length === 3);
  const ti = () => page.locator('path[data-ziel="plan:Testplan 3"]').getAttribute("tabindex");
  assert.equal(await ti(), "0");
  assert.ok((await zieleInTabFolge(page)).includes("plan:Testplan 3"), "Testplan 3 in der Tab-Folge");
  // Karte per Pfeiltaste (Leaflet-Tastatursteuerung auf #map) nach Westen verschieben, bis Testplan 3 aus dem Feld ist
  await page.locator("#map").focus();
  let n = 0;
  while (n < 40 && (await ti()) !== "-1") { await page.keyboard.press("ArrowLeft"); await page.waitForTimeout(150); n++; }
  assert.equal(await ti(), "-1", `nach ${n} Schritten noch im Feld`);
  const folge = await zieleInTabFolge(page);
  assert.ok(!folge.includes("plan:Testplan 3"), `außerhalb des Felds noch in der Tab-Folge: ${folge.join(", ")}`);
  await page.locator("#map").focus();
  for (let i = 0; i < n; i++) { await page.keyboard.press("ArrowRight"); await page.waitForTimeout(150); }
  await page.waitForFunction(() => document.querySelector('path[data-ziel="plan:Testplan 3"]').getAttribute("tabindex") === "0", null, { timeout: 3000 })
    .catch(() => assert.fail("nach dem Zurückschieben nicht wieder tabindex 0"));
  await pruefen(s);
});

test("Sammelpunkt: Leertaste vergrößert wie die Eingabetaste, Fokus danach auf der Karte statt an <body>", async () => {
  const s = await oeffnen(t.browser, t.voll + QUARTIER);
  const { page } = s;
  const vorher = await page.locator(".marker-cluster").count();
  assert.ok(vorher >= 1, "kein Sammelpunkt (Testdaten)");
  await page.locator(".marker-cluster").first().focus();
  assert.deepEqual(await druecken(page, " "), { klicks: 1, abgefangen: true });
  await page.waitForFunction((n) => document.querySelectorAll(".marker-cluster").length < n, vorher, { timeout: 5000 })
    .catch(() => assert.fail("Sammelpunkt nach der Leertaste nicht aufgelöst"));
  await page.waitForTimeout(600);
  assert.equal(await aktiv(page), "#map", "Fokus auf der Karte");
  await pruefen(s);
});

// Durchsicht 10.11.2026 (Messung mit erfundenen Daten in Originalmenge): mit 691 Plänen lagen alle Planflächen vor den
// Kartenknöpfen in der Tab-Folge. Mehr als PLAN_HALTE (25) Pläne im freien Feld: keiner ist Tab-Halt, Hinweis in der
// Legende; vergrößert (wenige im Feld) wieder Tab-Halte. 60 erfundene Planflächen per page.route statt der drei aus
// testseite.py, Rechtecke im Testgebiet um 0°/0°.
test("Viele Bebauungspläne: kein Tab-Halt in der Übersicht, Hinweis in der Legende; vergrößert wieder Tab-Halte", async () => {
  const s = await oeffnen(t.browser, t.voll, { warten: false });
  const { page } = s;
  await page.route("**/flaechen/bebauungsplaene.json", async (route) => {
    const r = await route.fetch(), fc = await r.json();
    fc.features = Array.from({ length: 60 }, (_, i) => {
      const w = -0.004 + (i % 10) * 0.0022, so = -0.004 + Math.floor(i / 10) * 0.0022;
      return { type: "Feature", properties: { name: `Testplan ${i + 1}`, inkraft_seit: "2020-01-01" },
        geometry: { type: "Polygon", coordinates: [[[w, so], [w + 0.0015, so], [w + 0.0015, so + 0.0015], [w, so + 0.0015], [w, so]]] } };
    });
    await route.fulfill({ response: r, json: fc });
  });
  await page.goto(t.voll + "?plaene=1", { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="plan:"]').length === 60);
  const halte = () => page.locator('path[data-ziel^="plan:"][tabindex="0"]').count();
  assert.equal(await halte(), 0, "Planflächen als Tab-Halt in der Übersicht");
  const folge = await zieleInTabFolge(page);
  assert.ok(!folge.some((z) => z.startsWith("plan:")), `Pläne in der Tab-Folge: ${folge.join(", ")}`);
  assert.ok(folge.some((z) => z.startsWith("bezirk:")), "Stadtbezirk bleibt Tab-Halt");
  assert.match(await page.locator(".map-legend:not(.map-sources)").textContent(), /Per Tab erreichbar sind die Pläne, wenn höchstens 25 im Kartenausschnitt liegen/);
  // per Tastatur vergrößern (Plus auf der Karte), bis höchstens 25 Pläne im Feld liegen
  await page.locator("#map").focus();
  for (let i = 0; i < 8 && (await halte()) === 0; i++) { await page.keyboard.press("+"); await page.waitForTimeout(500); }
  const n = await halte();
  assert.ok(n > 0 && n <= 25, `nach dem Vergrößern ${n} Tab-Halte auf Plänen`);
  await pruefen(s);
});

test("Maus: Klick auf Einzelpunkt und Stadtbezirk lässt den Fokus auf der Karte; Klick in überlappende Pläne trifft den ersten", async () => {
  let s = await oeffnen(t.browser, t.voll + `${QUARTIER}&plaene=1`);
  let { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="plan:"]').length === 3);
  const mitte = (sel) => page.locator(sel).first().evaluate((el) => { const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  // Einzelpunkt
  let [x, y] = await mitte('path[data-ziel^="vorlage:"]');
  await page.mouse.click(x, y);
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Vorgang", null, { timeout: 3000 });
  assert.equal(await aktiv(page), "#map", "Fokus nach Mausklick auf den Punkt");
  // Überlappung von Testplan 1 und 2: oben liegt Testplan 1 (Zeichenreihenfolge wie vor der Umsetzung)
  // (ein Punkt der Überlappung, an dem kein Einzelpunkt oder Sammelpunkt liegt)
  const [ox, oy, oben] = await page.evaluate(() => {
    const r = (n) => document.querySelector(`path[data-ziel="plan:Testplan ${n}"]`).getBoundingClientRect();
    const a = r(1), b = r(2), l = Math.max(a.left, b.left), rr = Math.min(a.right, b.right), o = Math.max(a.top, b.top), u = Math.min(a.bottom, b.bottom);
    for (let fx = 0.1; fx < 1; fx += 0.1) for (let fy = 0.1; fy < 1; fy += 0.1) {
      const px = l + (rr - l) * fx, py = o + (u - o) * fy, z = document.elementFromPoint(px, py)?.dataset?.ziel;
      if (z?.startsWith("plan:")) return [px, py, z];
    }
    return [null, null, null];
  });
  assert.equal(oben, "plan:Testplan 1", "oben in der Überlappung");
  [x, y] = [ox, oy];
  await page.mouse.click(x, y);
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Bebauungsplan", null, { timeout: 3000 });
  assert.match(await page.locator("#detail").innerText(), /Testplan 1/);
  assert.equal(await aktiv(page), "#map", "Fokus nach Mausklick auf den Plan");
  await pruefen(s);
  // Stadtbezirk: Fokus vorher auf der Karte, danach nicht an <body>
  s = await oeffnen(t.browser, t.voll);
  ({ page } = s);
  [x, y] = await mitte('path[data-ziel^="bezirk:"]');
  await page.mouse.click(x, y);
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="ortsteil:"]').length === 2);
  await page.waitForTimeout(500);
  assert.equal(await aktiv(page), "#map", "Fokus nach Mausklick auf den Stadtbezirk");
  await pruefen(s);
});

test("Überfahren mit der Maus ändert die Tab-Folge nicht; Mausrad bei Fokus auf dem Stadtbezirk: Fokus auf ein Quartier", async () => {
  let s = await oeffnen(t.browser, t.voll);
  let { page } = s;
  await tabZu(page, "bezirk:");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.dataset?.ziel === "ortsteil:testquartier-a");
  await page.waitForTimeout(800);
  const folge = () => page.locator('path[data-ziel^="ortsteil:"]').evaluateAll((ps) => ps.map((p) => p.dataset.ziel));
  const vorher = await folge();
  assert.deepEqual(vorher, ["ortsteil:testquartier-a", "ortsteil:testquartier-b"]);
  await page.locator("#q").focus();
  // über Testquartier A (nicht fokussiert) und wieder weg
  const [x, y] = await page.evaluate(() => {
    const p = document.querySelector('path[data-ziel="ortsteil:testquartier-a"]'), r = p.getBoundingClientRect();
    for (let fx = 0.2; fx < 0.9; fx += 0.1) for (let fy = 0.2; fy < 0.9; fy += 0.1) {
      const px = r.left + r.width * fx, py = r.top + r.height * fy;
      if (document.elementFromPoint(px, py) === p) return [px, py];
    }
    return [null, null];
  });
  assert.ok(x != null, "kein freier Punkt auf Testquartier A");
  await page.mouse.move(x, y);
  await page.mouse.move(x + 3, y + 3);
  assert.equal(await page.evaluate(() => document.querySelector('path[data-ziel="ortsteil:testquartier-a"]').parentNode.lastElementChild.dataset.ziel), "ortsteil:testquartier-a", "beim Überfahren vorn");
  await page.mouse.move(5, 5);
  assert.deepEqual(await folge(), vorher, "DOM- und Tab-Folge nach dem Überfahren");
  const tabFolge = (await zieleInTabFolge(page)).filter((z) => z.startsWith("ortsteil:"));
  assert.deepEqual(tabFolge, vorher);
  await pruefen(s);
  // Mausrad: Stadtbezirk fokussiert, Karte vergrößert sich in die Quartiersansicht; der Pfad verschwindet
  s = await oeffnen(t.browser, t.voll);
  ({ page } = s);
  await tabZu(page, "bezirk:");
  const box = await page.locator("#map").boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 3 && (await page.locator('path[data-ziel^="bezirk:"]').count()); i++) { await page.mouse.wheel(0, -300); await page.waitForTimeout(500); }
  assert.equal(await page.locator('path[data-ziel^="bezirk:"]').count(), 0, "Quartiersansicht nicht erreicht");
  await page.waitForTimeout(500);
  assert.match(await aktiv(page), /^pfad Quartier /, "Fokus nach dem Wechsel der Ebene");
  await pruefen(s);
});
