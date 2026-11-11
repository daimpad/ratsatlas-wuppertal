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

// Impressum (CLAUDE.md 9, 11.11.2026): sichtbarer Link auf https://nozilla.de/impressum/ in der Fußzeile jeder Seite.
// Auf der Karte ist die Quellenzeile die Fußzeile (app.js placeMapControls): Link im Bild, nicht verdeckt, und die
// Quellenzeile überdeckt den Legendenstapel nicht (sie bricht rechts davon um).
const IMPRESSUM = 'a[href="https://nozilla.de/impressum/"]';
// ohne Gesamtexport fehlen diese Dateien erwartungsgemäß (wie smoke.test.mjs)
const OHNE_EXPORT = [/^\/data\/export\/wuppertal\/(index|zeit)\.json$/, /^\/data\/export\/wuppertal\/flaechen\/(ortsteile|bezirke)\.json$/,
  /^\/data\/export\/glossar\.json$/, /^\/data\/geo\/(quartiere|stadtbezirke)_wuppertal\.geojson$/];
const imBildUndOben = (sel) => document.querySelector(sel) && (() => {
  const el = document.querySelector(sel), r = el.getBoundingClientRect();
  if (!r.width || !r.height || r.top < 0 || r.left < 0 || r.bottom > innerHeight || r.right > innerWidth) return false;
  const oben = document.elementFromPoint(r.left + Math.min(r.width / 2, 20), r.top + r.height / 2);
  return Boolean(oben && (oben === el || el.contains(oben)));
})();

test("Impressum in der Fußzeile: Karte mit und ohne Daten, breit und Telefon; sichtbar und nicht verdeckt", async () => {
  for (const url of [t.voll, t.leer]) {
    for (const [width, height] of [[1440, 900], [1024, 768], [390, 844]]) {
      const s = await oeffnen(t.browser, url, { width, height });
      const { page } = s;
      const wo = `${url === t.voll ? "voll" : "leer"} ${width} px`;
      const link = page.locator(`.leaflet-control-attribution ${IMPRESSUM}`);
      assert.equal(await link.count(), 1, wo);
      assert.match(await link.innerText(), /^Impressum/, wo);
      assert.equal(await link.getAttribute("target"), "_blank", wo);
      assert.ok(await page.evaluate(imBildUndOben, `.leaflet-control-attribution ${IMPRESSUM}`), `Impressum nicht sichtbar: ${wo}`);
      if (width > 900) {
        assert.equal(await page.locator(".leaflet-control-attribution a[href=\"datenschutz.html\"]").count(), 1, wo);
        // Legendenstapel unten links bleibt frei (letzte Zeile „Quellen, Lizenzen und Datenstand“)
        assert.ok(await page.evaluate(imBildUndOben, "#sources > summary"), `Quellenzeile verdeckt den Legendenstapel: ${wo}`);
      }
      assert.deepEqual(await axe(page), [], wo);
      await pruefen(s, url === t.leer ? OHNE_EXPORT : []);
    }
  }
});

test("Impressum in der Fußzeile: jede weitere Seite (Sitemap, Vorgang, 404) hat ein <footer> mit sichtbarem Link", async () => {
  const s = await oeffnen(t.browser, t.voll + "begriffe/", { warten: false });
  const { page } = s;
  const locs = async (datei) => [...(await (await page.request.get(t.voll + datei)).text()).matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  const seiten = (await locs("sitemap-seiten.xml")).filter((u) => u !== t.voll);
  const vorgang = (await locs("sitemap-vorgaenge.xml"))[0];
  assert.ok(vorgang, "Vorgangsseite in der Sitemap");
  const urls = [...seiten, vorgang, t.voll + "404.html"];
  for (const pfad of ["datenschutz.html", "rss/", "begriffe/", "gebiete/", "ortsteil/testquartier-a/", "stadtbezirk/testbezirk-1/"]) {
    assert.ok(urls.includes(t.voll + pfad), pfad);
  }
  for (const url of urls) {
    for (const [width, height] of [[1440, 900], [390, 844]]) {
      await page.setViewportSize({ width, height });
      await page.goto(url, { waitUntil: "networkidle" });
      const link = page.locator(`footer ${IMPRESSUM}`);
      assert.equal(await link.count(), 1, `${url} bei ${width} px`);
      assert.match(await link.innerText(), /^Impressum/, url);
      await link.scrollIntoViewIfNeeded();
      assert.ok(await link.isVisible(), `${url} bei ${width} px`);
      assert.ok(await page.evaluate(imBildUndOben, `footer ${IMPRESSUM}`), `verdeckt: ${url} bei ${width} px`);
    }
  }
  await pruefen(s);
});
