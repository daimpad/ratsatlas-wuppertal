// Browser-Prüfung der Karte (Playwright, Chromium) mit erfundenen Daten (testseite.py): Start ohne Gesamtexport, Start
// mit Übersicht über ganz Wuppertal, abgeschaltete Zusatzthemen, Links mit ?suche= und ?gebiet=, Zeitleiste ohne
// Sitzungsbahnen, Telefon. Barrierefreiheit mit axe-core (WCAG 2.0 und 2.1, A und AA). Jede Anfrage an andere Hosts als
// 127.0.0.1 wird blockiert und lässt den Test fehlschlagen. Abgeleitet aus allris-test @52fe9ca
// (tests/browser/smoke.test.mjs); die Bonner Tests der Zusatzthemen entfallen, solange diese abgeschaltet sind.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe, ohneOrtsteil } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

// ohne Gesamtexport fehlen genau diese Dateien (app.js: index.json, Flächen, Glossar, Zeitleiste; Rückfall data/geo)
const OHNE_EXPORT = [/^\/data\/export\/wuppertal\/(index|zeit)\.json$/, /^\/data\/export\/wuppertal\/flaechen\/(ortsteile|bezirke)\.json$/,
  /^\/data\/export\/glossar\.json$/, /^\/data\/geo\/(quartiere|stadtbezirke)_wuppertal\.geojson$/];

test("Ohne Gesamtexport: Karte startet ohne Fehler, Gebietswahl „Daten nicht verfügbar“, ohne Verstöße", async () => {
  const s = await oeffnen(t.browser, t.leer);
  const { page } = s;
  assert.equal(await page.locator("#f-area").inputValue(), "wuppertal:alle");
  assert.equal(await page.locator("#f-area option:checked").textContent(), "Daten nicht verfügbar");
  assert.equal(await page.locator("#detail-heading").textContent(), "Los geht's");
  // Zeitleiste ohne zeit.json ausgeblendet
  assert.equal(await page.locator('.toggle[data-panel="timeline-wrap"]').isVisible(), false);
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await pruefen(s, OHNE_EXPORT);
});

test("Start: Übersicht über ganz Wuppertal, Fenster „Los geht's“, ohne Verstöße", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await page.waitForFunction(() => document.querySelectorAll(".nav-label-bz").length === 1);
  assert.equal(await page.locator("#detail-heading").textContent(), "Los geht's");
  assert.equal(await page.locator("#f-area").inputValue(), "wuppertal:alle");
  assert.equal(await page.locator("#f-area option:checked").textContent(), "Gebiet wählen");
  assert.equal(await page.locator('#f-area option[value="wuppertal:ganz"]').textContent(), "Ganz Wuppertal");
  assert.equal(await page.locator('#f-area option[value="ortsteil:testquartier-a"]').count(), 1);
  assert.ok(!/gebiet=/.test(page.url()), "die Übersicht schreibt kein Gebiet in die Adresse");
  // Zoomknöpfe der Karte deutsch beschriftet (Leaflet: „Zoom in“/„Zoom out“)
  assert.deepEqual(await page.locator(".leaflet-control-zoom a").evaluateAll((as) => as.map((a) => a.getAttribute("aria-label"))),
    ["Hineinzoomen", "Herauszoomen"]);
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await pruefen(s);
});

test("Abgeschaltete Zusatzthemen: nicht sichtbar, nicht per Tab erreichbar", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  const sichtbar = await page.evaluate(() => [...document.querySelectorAll("[data-funktion][hidden]")]
    .filter((e) => getComputedStyle(e).display !== "none").map((e) => `${e.tagName}[${e.dataset.funktion}]`));
  assert.deepEqual(sichtbar, []);
  assert.ok(await page.locator("[data-funktion][hidden]").count() > 0, "Zusatzthemen in index.html markiert");
  // ein Durchlauf mit Tab erreicht kein Element eines abgeschalteten Zusatzthemas
  const erreicht = [];
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    erreicht.push(await page.evaluate(() => {
      const a = document.activeElement;
      return a && a.closest("[data-funktion][hidden]") ? a.outerHTML.slice(0, 80) : null;
    }));
  }
  assert.deepEqual(erreicht.filter(Boolean), []);
  await pruefen(s);
});

test("Link ?suche=wuppertal: Suche über ganz Wuppertal, Liste offen, ohne Verstöße", async () => {
  const s = await oeffnen(t.browser, t.voll + "?suche=wuppertal");
  const { page } = s;
  assert.equal(await page.locator('input[name="scope"][value="wuppertal"]').isChecked(), true);
  await page.waitForFunction(() => /Treffer in ganz Wuppertal/.test(document.querySelector("#count")?.textContent || ""));
  assert.ok(await page.locator("#papers button[data-gref]").count() > 0, "Treffer aus ganz Wuppertal in der Liste");
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await pruefen(s);
});

test("Link ?gebiet=wuppertal:ganz: Startansicht ganz Wuppertal; alter Link ?gebiet=bonn:ganz fällt auf die Startansicht", async () => {
  let s = await oeffnen(t.browser, t.voll + "?gebiet=wuppertal:ganz");
  assert.equal(await s.page.locator("#f-area").inputValue(), "wuppertal:ganz");
  await pruefen(s);
  s = await oeffnen(t.browser, t.voll + "?gebiet=bonn:ganz");
  assert.equal(await s.page.locator("#f-area").inputValue(), "wuppertal:alle");
  assert.equal(await s.page.locator("#detail-heading").textContent(), "Los geht's");
  assert.doesNotMatch(s.page.url(), /bonn/);
  await pruefen(s);
});

test("Link mit Quartier: Liste, Vorgang mit Prozesslinie, ohne Verstöße", async () => {
  const s = await oeffnen(t.browser, t.voll + "?gebiet=ortsteil:testquartier-a");
  const { page } = s;
  assert.equal(await page.locator("#f-area").inputValue(), "ortsteil:testquartier-a");
  await page.waitForFunction(() => document.querySelectorAll("#papers button[data-ref]").length > 0);
  await page.locator('.toggle[data-panel="panel-list"]').click();
  const first = page.locator("#papers button[data-ref]").first();
  const ref = await first.getAttribute("data-ref");
  await first.click();
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang");
  assert.ok(await page.locator("#detail .steps li").count() > 0, "Prozesslinie mit Stationen");
  assert.equal(decodeURIComponent(new URL(page.url()).hash.slice(1)), ref, "Vorlage in der Adresse");
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await pruefen(s);
});

test("Zeitleiste ohne Sitzungsbahnen: zeichnet, zoomt und verschiebt per Tastatur ohne Fehler", async () => {
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    const s = await oeffnen(t.browser, t.voll + "?gebiet=wuppertal:ganz", { width, height });
    const { page } = s;
    const knopf = page.locator('.toggle[data-panel="timeline-wrap"]');
    if (width < 900) await page.locator("#nav-burger").click();
    await knopf.click();
    await page.waitForFunction(() => !document.querySelector("#timeline-wrap").hidden);
    assert.equal(await page.locator("#timeline-wrap .tl-meet").count(), 0, "keine Sitzungsbahnen (PILOT_GREMIEN leer)");
    assert.ok(await page.locator("#timeline-wrap svg").count() > 0, "Zeitleiste gezeichnet");
    // Bedienfläche der Zeitleiste (tl-stage, tabindex 0): zoomen und verschieben per Tastatur
    await page.locator("#timeline-wrap .tl-stage").focus();
    for (const taste of ["+", "+", "-", "ArrowLeft", "ArrowRight", "Home", "End"]) await page.keyboard.press(taste);
    assert.deepEqual(await axe(page), []);
    await pruefen(s);
  }
});

test("Telefon: Menü mit Gebiet und Flächen, Escape schließt es, ohne Verstöße", async () => {
  const s = await oeffnen(t.browser, t.voll, { width: 390, height: 844 });
  const { page } = s;
  const burger = page.locator("#nav-burger");
  await burger.click();
  assert.equal(await burger.getAttribute("aria-expanded"), "true");
  assert.equal(await page.locator("#f-area").isVisible(), true);
  assert.deepEqual(await axe(page), []);
  await page.keyboard.press("Escape");
  assert.equal(await burger.getAttribute("aria-expanded"), "false");
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await pruefen(s);
});
