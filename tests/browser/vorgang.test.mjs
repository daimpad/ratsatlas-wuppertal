// Seiten je Vorgang (pipeline/vorgangsseiten.py) mit erfundenen Daten (testseite.py): Link „Seite zu dieser Vorlage“
// im Vorgang der Karte, statische Seite ohne Skripte mit Beratungsfolge, Rückweg zur Karte; Barrierefreiheit (axe,
// WCAG 2.0 und 2.1, A und AA) bei 1440 und 390 px, ohne waagrechten Bildlauf. Fremde Hosts blockiert (hilfe.mjs).
// Abgeleitet aus allris-test @52fe9ca (tests/browser/vorgang.test.mjs).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe, ohneOrtsteil } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

test("Vorgang auf der Karte → eigene Seite → zurück zur Karte", async () => {
  const s = await oeffnen(t.browser, t.voll + "?gebiet=ortsteil:testquartier-a#1001%2F2026");
  const { page } = s;
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Vorgang");
  assert.match(await page.locator("#detail").textContent(), /1001\/2026/);
  const link = page.locator('#detail a[href^="vorgang/"]');
  assert.equal(await link.count(), 1, "Link auf die Seite zu dieser Vorlage");
  assert.equal(await link.getAttribute("href"), "vorgang/1001-2026/");
  assert.equal(await link.textContent(), "Seite zu dieser Vorlage");
  await link.click();
  await page.waitForURL((u) => u.pathname.endsWith("/vorgang/1001-2026/"));
  assert.equal(await page.locator("h2", { hasText: "Beratungsfolge" }).count(), 1);
  assert.equal(await page.locator("script").count(), 0);
  assert.match(await page.locator("h1").textContent(), /Umgestaltung der Teststraße/);
  assert.deepEqual(await axe(page), []);
  await ohneOrtsteil(page);
  await page.locator(".pb-aktionen a", { hasText: "Auf der Karte öffnen" }).click();
  await page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Vorgang");
  assert.equal(await page.locator("#f-area").inputValue(), "ortsteil:testquartier-a");
  await pruefen(s);
});

test("Alle Seiten je Vorgang aus der Sitemap: erreichbar, ohne Verstöße, auf dem Telefon ohne waagrechten Bildlauf", async () => {
  const s = await oeffnen(t.browser, t.voll + "sitemap-vorgaenge.xml", { width: 390, height: 844, warten: false });
  const { page } = s;
  const sitemap = await (await page.request.get(t.voll + "sitemap-vorgaenge.xml")).text();
  const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  assert.equal(urls.length, 5, "fünf erfundene Vorlagen");
  for (const url of urls) {
    assert.ok(url.startsWith(t.voll), `Adresse der Testseite: ${url}`);
    for (const [width, height] of [[390, 844], [1440, 900]]) {
      await page.setViewportSize({ width, height });
      const res = await page.goto(url, { waitUntil: "networkidle" });
      assert.equal(res.status(), 200, url);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `waagrechter Bildlauf: ${url}`);
      assert.deepEqual(await axe(page), [], `${url} bei ${width} px`);
      await ohneOrtsteil(page);
    }
  }
  await pruefen(s);
});
