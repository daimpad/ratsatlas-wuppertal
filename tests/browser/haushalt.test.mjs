// Zusatzthema „haushalt“ (Plan vom 17.11.2026, CLAUDE.md 9): Seite haushalt/ und Kartenebene „Maßnahmen im Haushalt“ mit
// erfundenen Haushaltsdaten (testseite.py --haushalt). Geprüft: Treemaps der drei Ansichten, Auswahl ohne Skript,
// Fundstellen, Abschnitt Bezirksvertretungen mit Fallgruppen und abgeleitetem Ort, offene Punkte (Lizenz, Band 2);
// Kartenebene nur mit Zusatzthema, Markierung je Punkt (zwei Maßnahmen am selben Ort zusammen), Detail mit Hinweis
// „abgeleitet“, Betrag, Bezirksvertretung und Fundstelle, per Tastatur erreichbar; axe (WCAG 2.0/2.1 A und AA) bei 1440,
// 1024 und 390 px, ohne waagrechten Bildlauf. Fremde Hosts blockiert (hilfe.mjs).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { startenHaushalt, oeffnen, pruefen, axe, ohneOrtsteil } from "./hilfe.mjs";

let t;
before(async () => { t = await startenHaushalt(); });
after(async () => { await t?.stoppen(); });

const BREITEN = [[1440, 900], [1024, 768], [390, 844]];

test("Seite haushalt/: Treemaps, Auswahl ohne Skript, Bezirksvertretungen, offene Punkte, axe in drei Breiten", async () => {
  const s = await oeffnen(t.browser, t.haushalt + "haushalt/", { warten: false });
  const { page } = s;
  assert.equal(await page.locator("h1").textContent(), "Haushalt auf einen Blick");
  // drei Ansichten mit je zwei Formaten; ohne Skript wechselt die Auswahl über die Radioknöpfe
  assert.equal(await page.locator(".hh-radio").count(), 3);
  assert.equal(await page.locator(".hh-ansicht svg.hh-svg").count(), 6);
  const sichtbar = () => page.locator(".hh-ansicht").evaluateAll((fs) => fs.map((f) => getComputedStyle(f).display !== "none"));
  assert.deepEqual(await sichtbar(), [true, false, false]);
  await page.locator('label[for="hh-ist2024"]').click();
  assert.deepEqual(await sichtbar(), [false, false, true]);
  const text = (await page.locator("main").textContent()).replace(/\s+/g, " ");
  for (const muster of [/Testbereich Verwaltung/, /Band 1, S\. 11/, /Zuschussbedarf/, /Bezirksvertretung Testbezirk 1/,
    /Lizenz: Der Haushaltsplan nennt keine Lizenz/, /Band 2/]) assert.match(text, muster);
  assert.doesNotMatch(text, /€ je Einwohner|Investitionen der/);   // „Nicht enthalten: … Werte je Einwohner“ steht im Text
  // Bezirk: alle drei Fallgruppen, abgeleiteter Ort bei den verorteten Maßnahmen
  const bv = page.locator("#bv-testbezirk-1");
  await bv.locator("summary").click();
  assert.equal(await bv.locator("h4").count(), 3);
  assert.equal(await bv.locator("text=Ort abgeleitet").count(), 4);
  assert.equal(await page.locator('script[src*="haushalt.js"]').count(), 0, "kein Bonner Zoom-Skript");
  for (const [width, height] of BREITEN) {
    await page.setViewportSize({ width, height });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `waagrechter Bildlauf bei ${width} px`);
    assert.deepEqual(await axe(page), [], `haushalt/ bei ${width} px`);
  }
  await ohneOrtsteil(page);
  await pruefen(s);
});

test("Karte: Ebene „Maßnahmen im Haushalt“ mit Markierung je Punkt, Detail mit Hinweis und Fundstelle, axe in drei Breiten", async () => {
  for (const [width, height] of BREITEN) {
    const s = await oeffnen(t.browser, t.haushalt + "?haushalt=1", { width, height });
    const { page } = s;
    const knopf = page.locator("button.map-haushalt");
    assert.equal(await knopf.count(), 1);
    assert.equal(await knopf.getAttribute("aria-pressed"), "true");
    await page.waitForFunction(() => document.querySelectorAll(".hh-marker").length === 2);
    const marke = page.locator('.hh-marker[title^="Haushalt: 2 Maßnahmen"]');
    assert.equal(await marke.count(), 1);
    assert.equal(await marke.getAttribute("tabindex"), "0");
    await marke.focus();
    await page.keyboard.press("Enter");
    const detail = page.locator("#detail");
    await detail.locator("h3", { hasText: "Teststraße" }).waitFor();
    const text = await detail.innerText();
    for (const muster of [/abgeleitet/, /Ort aus dem Namen der Maßnahme abgeleitet/, /Ausbau der Teststraße/,
      /Testspielplatz an der Teststraße/, /Bezirksvertretung\s+Testbezirk 1/, /Testplan, S\. 30/, /Ausgabe 1\.250\.000\s€ \(2026–2030\)/,
      /Einnahme 500\.000\s€ \(2026–2030\)/]) assert.match(text, muster);
    assert.equal((text.match(/Ausbau der Teststraße/g) || []).length, 1, "Zeilen einer Maßnahme zusammengefasst");
    assert.equal(await detail.locator('a[href="haushalt/#bv-testbezirk-1"]').count(), 2);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `waagrechter Bildlauf bei ${width} px`);
    assert.deepEqual(await axe(page), [], `Karte mit Haushaltsebene bei ${width} px`);
    assert.match(new URL(page.url()).search, /haushalt=1/);
    await pruefen(s);
  }
});

test("Karte: Ebene abschaltbar, ohne Einschalten wird die Datei nicht geladen", async () => {
  const s = await oeffnen(t.browser, t.haushalt);
  const { page } = s;
  const geladen = [];
  page.on("request", (r) => { if (r.url().includes("massnahmen.geojson")) geladen.push(r.url()); });
  await page.waitForTimeout(300);
  assert.equal(await page.locator(".hh-marker").count(), 0);
  assert.deepEqual(geladen, []);
  const knopf = page.locator("button.map-haushalt");
  if (!(await knopf.isVisible())) await page.locator("button.map-menu").click();   // schmale Karte: Ebenen im Menü
  await knopf.click();
  await page.waitForFunction(() => document.querySelectorAll(".hh-marker").length === 2);
  assert.equal(geladen.length, 1);
  await knopf.click();
  assert.equal(await page.locator(".hh-marker").count(), 0);
  assert.doesNotMatch(new URL(page.url()).search, /haushalt=/);
  await pruefen(s);
});

test("Menü „Themen“ mit Zusatzthema: Haushalt und Kartenebene, axe in drei Breiten", async () => {
  for (const [width, height] of BREITEN) {
    const s = await oeffnen(t.browser, t.haushalt, { width, height });
    const { page } = s;
    if (width < 900) { await page.keyboard.press("Escape"); await page.locator("#nav-burger").click(); }
    const menue = page.locator('.menu-btn[data-mega="mega-themen"]');
    assert.equal(await menue.isVisible(), true, `Menü „Themen“ sichtbar (${width} px)`);
    await menue.click();
    const themen = page.locator("#mega-themen");
    assert.equal(await themen.locator('a.card[href="haushalt/"]').isVisible(), true);
    assert.deepEqual(await axe(page), [], `Menü „Themen“ bei ${width} px`);
    await themen.locator("[data-haushalt-ebene]").click();
    await page.waitForFunction(() => document.querySelectorAll(".hh-marker").length === 2);
    assert.equal(await page.locator("button.map-haushalt").getAttribute("aria-pressed"), "true");
    assert.equal(await themen.isVisible(), false, "Menü schließt");
    await pruefen(s);
  }
});
