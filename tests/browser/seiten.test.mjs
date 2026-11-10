// Statische Seiten aus der Pipeline (begriffsseite.py, gebietsseiten.py, rssseite.py, datenschutz.html) mit erfundenen
// Daten (testseite.py): alle Seiten aus sitemap-seiten.xml außer der Karte, Barrierefreiheit (axe, WCAG 2.0 und 2.1, A
// und AA) bei 1440 und 390 px, ohne waagrechten Bildlauf, Wortwahl „Quartier“. Dazu die Seite begriffe/ mit Ankern und
// die Gebietsseiten mit Rückweg zur Karte. Fremde Hosts blockiert (hilfe.mjs). Ersetzt für Wuppertal die Bonner
// begriffe.test.mjs und rss.test.mjs (allris-test @52fe9ca), soweit sie den Kern betreffen.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe, ohneOrtsteil } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

test("Alle Seiten der Sitemap außer der Karte: erreichbar, ohne Verstöße, ohne waagrechten Bildlauf", async () => {
  const s = await oeffnen(t.browser, t.voll + "begriffe/", { warten: false });
  const { page } = s;
  const sitemap = await (await page.request.get(t.voll + "sitemap-seiten.xml")).text();
  const urls = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]).filter((u) => u !== t.voll);
  for (const pfad of ["datenschutz.html", "rss/", "begriffe/", "gebiete/", "ortsteil/testquartier-a/", "ortsteil/testquartier-b/",
    "stadtbezirk/testbezirk-1/"]) assert.ok(urls.includes(t.voll + pfad), `${pfad} fehlt in der Sitemap`);
  for (const url of urls) {
    for (const [width, height] of [[1440, 900], [390, 844]]) {
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

test("Seite begriffe/: Begriffe mit Ankern, Quartier und Stadtbezirk erklärt, Sprung über den Anker", async () => {
  const s = await oeffnen(t.browser, t.voll + "begriffe/#quartier", { warten: false });
  const { page } = s;
  assert.equal(await page.locator("h1").textContent(), "Begriffe");
  assert.ok(await page.locator("dt[id]").count() > 50, "Begriffe mit Anker");
  const quartier = page.locator("dt#quartier");
  assert.equal(await quartier.count(), 1);
  assert.match(await page.locator("dt#quartier + dd").textContent(), /69 Quartiere/);
  assert.equal(await page.locator("dt#stadtbezirk").count(), 1);
  assert.ok(await quartier.evaluate((e) => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; }),
    "Anker #quartier im Blick");
  await pruefen(s);
});

test("Gebietsseiten: Übersicht verlinkt Quartiere und Stadtbezirk, Quartiersseite führt zur Karte", async () => {
  const s = await oeffnen(t.browser, t.voll + "gebiete/", { warten: false });
  const { page } = s;
  assert.match(await page.locator("body").innerText(), /Quartier/);
  assert.ok(await page.locator('a[href$="stadtbezirk/testbezirk-1/"]').count() > 0, "Link auf den Stadtbezirk");
  await page.locator('a[href$="ortsteil/testquartier-a/"]').first().click();
  await page.waitForURL((u) => u.pathname.endsWith("/ortsteil/testquartier-a/"));
  assert.match(await page.locator("h1").textContent(), /Testquartier A/);
  assert.match(await page.locator("main").innerText(), /Quartier/);
  const karte = page.locator('a[href*="?gebiet=ortsteil:testquartier-a"]').first();
  assert.equal(await karte.count(), 1, "Link auf die Karte mit dem Quartier");
  await karte.click();
  await page.waitForFunction(() => document.querySelector("#f-area")?.value === "ortsteil:testquartier-a");
  await pruefen(s);
});
