// Gebietskarte ohne Ratsdaten (CLAUDE.md 9, 11.11. und 13.11.2026; Veröffentlichung erst nach Freigabe des Plans nach
// Messstufe G): tools/seite_bauen.py baut die Seite ohne index.json, aber mit Flächen (testseite.py --gebietskarte:
// zwei erfundene Stadtbezirke, drei Quartiere, drei Bebauungspläne, einer davon sich selbst schneidend mit zehn
// Nachkommastellen). Geprüft: Startansicht mit Namen der Stadtbezirke und ohne Zahlen, Hinweis „Ratsdaten folgen“ statt
// „Daten nicht verfügbar“, Namensnennung (CC BY 4.0, Bebauungspläne CC BY-ND 4.0), Geometrie der Pläne unverändert,
// noindex, Tastatur (Rolle, Name, tabindex, Eingabetaste wie Klick, Fokus nicht an <body>) und axe ohne Verstoß. Läuft
// in Chromium und Firefox (BROWSER=firefox, hilfe.mjs). Keine Anfragen an fremde Hosts (hilfe.mjs sperrt sie).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { startenGebietskarte, oeffnen, pruefen, axe, ohneOrtsteil, BROWSER } from "./hilfe.mjs";

let t;
before(async () => { t = await startenGebietskarte(); });
after(async () => { await t?.stoppen(); });

// ohne Ratsdaten fehlen genau diese Dateien (index.json, Zeitleiste, Glossar); die Flächen sind da
const OHNE_RATSDATEN = [/^\/data\/export\/wuppertal\/(index|zeit)\.json$/, /^\/data\/export\/glossar\.json$/];
const PFAD = ".leaflet-map-pane path";
const GEBIETE = "Gebiete: Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY 4.0";
const PLAENE = "Bebauungspläne: Datenquelle: Stadt Wuppertal – offenedaten-wuppertal.de, CC BY-ND 4.0";
// Testplan 4 wie in testseite.py (TESTPLAN_FLIEGE): sich selbst schneidend, zehn Nachkommastellen
const FLIEGE = [[[0.0221234567, 0.0021234567], [0.0261234567, 0.0061234567], [0.0261234567, 0.0021234567],
  [0.0221234567, 0.0061234567], [0.0221234567, 0.0021234567]]];

const aktiv = (page) => page.evaluate(() => {
  const a = document.activeElement;
  if (!a || a === document.body) return "body";
  return a instanceof SVGPathElement ? `pfad ${a.getAttribute("aria-label")}` : a.id ? `#${a.id}` : a.tagName.toLowerCase();
});
const namen = (page) => page.locator(`${PFAD}[role=button]`).evaluateAll((ps) => ps.map((p) => p.getAttribute("aria-label")));
// sichtbarer und versteckter Text der Seite ohne Skripte (wie ohneOrtsteil in hilfe.mjs)
const seitentext = (page) => page.evaluate(() => {
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let t = "";
  for (let n = w.nextNode(); n; n = w.nextNode()) if (!n.parentElement?.closest("script, style")) t += ` ${n.data}`;
  return t.replace(/\s+/g, " ");
});

// per Tab ab dem Suchfeld bis zum Pfad, dessen data-ziel mit `ziel` beginnt
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

test("Startansicht: Stadtbezirke mit Namen ohne Zahlen, „Ratsdaten folgen“, Namensnennung, noindex, axe ohne Verstoß", async () => {
  const s = await oeffnen(t.browser, t.gebiete);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="bezirk:"]').length === 2);
  assert.equal(await page.locator("#f-area option:checked").textContent(), "Ratsdaten folgen");
  const text = await seitentext(page);
  assert.doesNotMatch(text, /Daten nicht verfügbar/);
  // keine Vorlagenzahlen und keine leeren Zähler
  assert.doesNotMatch(text, /\d+ Vorlagen?\b|in den letzten 12 Monaten|Vorlagen der letzten/);
  assert.equal(await page.locator(".nav-n").count(), 0, "keine Zahl an den Beschriftungen");
  assert.equal(await page.locator(".nav-legend").count(), 0, "keine Legende der Vorlagenzahlen");
  assert.deepEqual(await page.locator(".nav-label").allTextContents(), ["Testbezirk 1", "Testbezirk 2"]);
  assert.deepEqual((await namen(page)).sort(), ["Stadtbezirk Testbezirk 1", "Stadtbezirk Testbezirk 2"]);
  // Hinweis im Startfenster aus den Flächen gezählt, Datenstand, Liste
  const vorschau = (await page.locator("#detail .vorschau-hinweis").textContent()).replace(/\s+/g, " ");
  assert.match(vorschau, /^Vorschau: Ratsdaten folgen: Die Karte zeigt bisher nur die 2 Stadtbezirke und 3 Quartiere der Stadt Wuppertal und auf Wunsch die rechtsverbindlichen Bebauungspläne\. /);
  assert.equal(await page.locator('#detail .vorschau-hinweis a[href="https://ris.wuppertal.de/"]').count(), 1);
  assert.match(await page.locator("#stand").textContent(), /^Datenstand: noch keine Ratsdaten veröffentlicht\. Die Karte zeigt die 2 Stadtbezirke und 3 Quartiere der Stadt Wuppertal \(Geodaten abgerufen am 15\.11\.2026\)\.$/);
  assert.match(await page.locator("#count").textContent(), /^Ratsdaten folgen: /);
  // Namensnennung in der Kartenzeile, sobald die Flächen gezeichnet sind
  assert.ok((await page.locator(".leaflet-control-attribution").textContent()).includes(GEBIETE));
  // noindex wie ohne Daten (seite_bauen.py), Links auf Dateien, die erst mit Ratsdaten entstehen, ausgeblendet
  assert.equal(await page.locator('meta[name="robots"]').getAttribute("content"), "noindex");
  assert.equal(await page.locator("[data-mit-daten]:not([hidden])").count(), 0);
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await pruefen(s, OHNE_RATSDATEN);
});

test("Stadtbezirk und Quartier per Tastatur: Rolle, Name, Eingabetaste wie Klick, Fokus bleibt auf der Karte", async () => {
  const s = await oeffnen(t.browser, t.gebiete);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="bezirk:"]').length === 2);
  await tabZu(page, "bezirk:Testbezirk 1");
  assert.equal(await aktiv(page), "pfad Stadtbezirk Testbezirk 1");
  assert.equal(await page.evaluate(() => document.activeElement.matches(":focus-visible")), true, "Fokus sichtbar");
  await page.keyboard.press("Enter");
  // Quartiere des Stadtbezirks erscheinen, der Fokus rückt auf das erste (nicht an <body>)
  await page.waitForFunction(() => document.activeElement?.dataset?.ziel === "ortsteil:testquartier-a", null, { timeout: 5000 });
  assert.equal(await aktiv(page), "pfad Quartier Testquartier A im Stadtbezirk Testbezirk 1");
  // Beschriftungen der Stadtbezirke blendet Leaflet aus (Opazität, nach 200 ms entfernt)
  await page.waitForFunction(() => document.querySelectorAll(".nav-label").length === 2);
  assert.deepEqual(await page.locator(".nav-label").allTextContents(), ["Testquartier A", "Testquartier B"]);
  // nur die Quartiere des gewählten Stadtbezirks sind Tab-Halte
  const halte = await page.locator(`${PFAD}[data-ziel^="ortsteil:"][tabindex="0"]`).evaluateAll((ps) => ps.map((p) => p.dataset.ziel).sort());
  assert.deepEqual(halte, ["ortsteil:testquartier-a", "ortsteil:testquartier-b"]);
  // Tooltip ohne „Klick“, mit Stadtbezirk und Hinweis
  const tip = (await page.locator(".nav-tip").innerText()).replace(/\s+/g, " ");
  assert.match(tip, /Testquartier A Quartier im Stadtbezirk Testbezirk 1 Zeigt das Quartier vergrößert · Ratsdaten folgen/);
  assert.doesNotMatch(tip, /Klick/);
  await page.keyboard.press("Tab");
  assert.equal(await aktiv(page), "pfad Quartier Testquartier B im Stadtbezirk Testbezirk 1");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Quartier");
  assert.equal(await aktiv(page), "pfad Quartier Testquartier B im Stadtbezirk Testbezirk 1", "Fokus bleibt auf dem Quartier");
  assert.equal(await page.locator(`${PFAD}[aria-current="true"]`).getAttribute("data-ziel"), "ortsteil:testquartier-b");
  assert.equal(await page.locator("#detail h3").textContent(), "Quartier Testquartier B");
  assert.match((await page.locator("#detail").innerText()).replace(/\s+/g, " "), /Stadtbezirk Testbezirk 1 .*Ratsdaten folgen/);
  // Quelle der Fläche mit Hinweis auf die Vereinfachung (CC BY 4.0: Änderungen kenntlich machen)
  assert.match(await page.locator("#detail details li").textContent(), /Datenquelle: Stadt Wuppertal – offenedaten-wuppertal\.de, CC BY 4\.0; vereinfacht/);
  assert.equal(await page.locator("#announce").textContent(), "Quartier Testquartier B im Stadtbezirk Testbezirk 1 gewählt. Ratsdaten folgen.");
  // Leertaste wirkt wie die Eingabetaste (wie karte-tastatur.test.mjs), Fokus fällt nicht an <body>
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press(" ");
  await page.waitForFunction(() => document.querySelector("#detail h3")?.textContent === "Quartier Testquartier A");
  assert.notEqual(await aktiv(page), "body");
  // „Ganz Wuppertal ansehen“: zurück zu den Stadtbezirken, Wahl aufgehoben
  await page.locator(".map-whole").click();
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="bezirk:"]').length === 2);
  assert.equal(await page.locator(`${PFAD}[aria-current="true"]`).count(), 0);
  assert.deepEqual(await axe(page), []);
  await pruefen(s, OHNE_RATSDATEN);
});

test("Bebauungspläne: Ebene mit Namensnennung CC BY-ND 4.0, Geometrie unverändert, Plan ohne Vorlagenangaben", async () => {
  const s = await oeffnen(t.browser, `${t.gebiete}?plaene=1`);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="plan:"]').length === 3);
  assert.ok((await page.locator(".leaflet-control-attribution").textContent()).includes(PLAENE));
  // Datei der Seite: Features der Quelle unverändert (keine Rundung, keine Reparatur der sich schneidenden Fläche)
  const plaene = await page.evaluate(() => fetch("data/export/wuppertal/flaechen/bebauungsplaene.json").then((r) => r.json()));
  assert.deepEqual(plaene.features.find((f) => f.properties.name === "Testplan 4").geometry.coordinates, FLIEGE);
  assert.equal(plaene.meta.attribution, PLAENE.replace(/^Bebauungspläne: /, ""));
  assert.match(plaene.meta.geometrie, /^unverändert/);
  await page.locator('path[data-ziel="plan:Testplan 4"]').focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#detail h3")?.textContent === "Bebauungsplan Testplan 4");
  const detail = (await page.locator("#detail").textContent()).replace(/\s+/g, " ");
  assert.match(detail, /rechtskräftig seit 01\.06\.2021/);
  assert.doesNotMatch(detail, /OParl|Vorlagen mit dieser Plannummer|Planchronik/);
  assert.deepEqual(await axe(page), []);
  await pruefen(s, OHNE_RATSDATEN);
});

test("Telefon: Gebiete und Hinweis, axe ohne Verstoß", async () => {
  const s = await oeffnen(t.browser, t.gebiete, { width: 390, height: 844 });
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="bezirk:"]').length === 2);
  assert.equal(await page.locator("#f-area option:checked").textContent(), "Ratsdaten folgen");
  assert.doesNotMatch(await seitentext(page), /Daten nicht verfügbar/);
  assert.deepEqual(await axe(page), []);
  await pruefen(s, OHNE_RATSDATEN);
});

test("Tour durch alle Funktionen läuft in der Gebietskarte ohne Fehler bis zum Ende", async () => {
  const s = await oeffnen(t.browser, t.gebiete);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll('path[data-ziel^="bezirk:"]').length === 2);
  await page.locator(".tour-cta").click();
  await page.waitForSelector(".tour-card");
  let schritte = 0;
  while (await page.locator(".tour").count() && schritte < 40) {
    const vorher = await page.locator("#tour-count").textContent();
    await page.locator('.tour-card [data-tour-act="next"]').click();
    await page.waitForFunction((v) => !document.querySelector(".tour") || document.querySelector("#tour-count")?.textContent !== v, vorher);
    schritte++;
  }
  assert.equal(await page.locator(".tour").count(), 0, `Tour nach ${schritte} Schritten nicht beendet`);
  assert.ok(schritte >= 3, `nur ${schritte} Schritte`);
  await pruefen(s, OHNE_RATSDATEN);
});
