// Seiten je Vorgang (pipeline/vorgangsseiten.py) mit erfundenen Daten (testseite.py): Link „Seite zu dieser Vorlage“
// im Vorgang der Karte, statische Seite ohne Skripte mit Beratungsfolge, Rückweg zur Karte; Barrierefreiheit (axe,
// WCAG 2.0 und 2.1, A und AA) bei 1440 und 390 px, ohne waagrechten Bildlauf. Fremde Hosts blockiert (hilfe.mjs).
// Abgeleitet aus allris-test @52fe9ca (tests/browser/vorgang.test.mjs). Dazu (CLAUDE.md 5.1, Entscheidung 11.11.2026):
// „Unterlagen geändert am …“ aus dem Änderungsprotokoll (testseite.py reicht zu Vorlage 1001/2026 eine Anlage nach)
// und der Hinweis auf einen fehlgeschlagenen oder veralteten Abruf (index.json meta per page.route verändert, Uhr per
// page.clock).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe, ohneOrtsteil } from "./hilfe.mjs";
import { kontrastUeberKarte } from "./kontrast.mjs";

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

const VORGANG = (ref) => `?gebiet=ortsteil:testquartier-a#${encodeURIComponent(ref)}`;
const vorgangOffen = (page) => page.waitForFunction(() => document.querySelector("#detail-heading")?.textContent === "Vorgang");
const DATUM = /^geändert am \d{2}\.\d{2}\.\d{4}$/;

test("Unterlagen geändert: Zeile im Vorgang und auf der Vorgangsseite nur für die Vorlage mit nachgereichter Anlage, ohne Dateinamen", async () => {
  let s = await oeffnen(t.browser, t.voll + VORGANG("1001/2026"));
  let { page } = s;
  await vorgangOffen(page);
  const zeile = page.locator("#detail dl.facts dt", { hasText: "Unterlagen" });
  assert.equal(await zeile.count(), 1);
  const dd = await zeile.evaluate((dt) => dt.nextElementSibling.firstChild.textContent.trim());
  assert.match(dd, DATUM);
  // Erklärung über „?“ (wie bei Art und Stand), ohne Dateinamen
  await page.locator('#detail button[aria-label="Erklärung: Unterlagen geändert"]').click();
  assert.match(await page.locator("#detail .erkl-text:not([hidden])").textContent(), /hinzugefügt, ersetzt oder entfernt/);
  assert.deepEqual(await axe(page), []);
  assert.doesNotMatch(await page.locator("body").innerText(), /Mustermann/);
  await pruefen(s);
  // andere Vorlage im selben Quartier: keine Zeile
  s = await oeffnen(t.browser, t.voll + VORGANG("1005/2026"));
  ({ page } = s);
  await vorgangOffen(page);
  assert.match(await page.locator("#detail").textContent(), /1005\/2026/);
  assert.equal(await page.locator("#detail dl.facts dt", { hasText: "Unterlagen" }).count(), 0);
  await pruefen(s);
  // statische Seiten: dieselbe Zeile bzw. keine
  s = await oeffnen(t.browser, t.voll + "vorgang/1001-2026/", { warten: false });
  ({ page } = s);
  assert.equal(await page.locator("dt", { hasText: "Unterlagen" }).count(), 1);
  assert.equal(await page.locator("dt", { hasText: "Unterlagen" }).evaluate((dt) => dt.nextElementSibling.firstChild.textContent.trim()), dd);
  assert.doesNotMatch(await page.locator("body").innerText(), /Mustermann/);
  await page.goto(t.voll + "vorgang/1005-2026/", { waitUntil: "networkidle" });
  assert.equal(await page.locator("dt", { hasText: "Unterlagen" }).count(), 0);
  await pruefen(s);
  // Protokoll im Export (Datenpaket): Kopf nach CLAUDE.md 5.1 und quellobjekt, ohne Dateinamen
  const tsv = await (await fetch(t.voll + "data/export/audit_aenderungen.tsv")).text();
  assert.match(tsv.split("\n")[0], /^vorlage\tfeld\talt\tneu\tzeitpunkt\tquellobjekt$/);
  assert.ok(/\tauxiliaryFile\t0 Dateien\t1 Datei: /.test(tsv) && !/Mustermann|Erika/.test(tsv), tsv);
});

// index.json mit verändertem meta ausliefern (übrige Dateien unverändert)
async function mitMeta(page, meta) {
  await page.route("**/data/export/wuppertal/index.json", async (route) => {
    const res = await route.fetch();
    const json = await res.json();
    route.fulfill({ response: res, json: { ...json, meta: { ...json.meta, ...meta } } });
  });
}

// Hinweise auf den Datenstand: „Los geht's“, Vorgang, #stand (in den eingeklappten Quellen)
const hinweise = (page) => page.evaluate(() => ({
  intro: document.querySelector("#detail .intro .stand-hinweis")?.textContent.replace(/\s+/g, " ").trim() || null,
  stand: document.getElementById("stand").textContent,
}));

test("Abruf fehlgeschlagen: Hinweis mit Berliner Datum in „Los geht's“, im Vorgang und im Datenstand; Kontrast und axe", async () => {
  const s = await oeffnen(t.browser, t.voll, { warten: false });
  const { page } = s;
  // Fehler 23:30 UTC am 12.11. ist in Berlin der 13.11.; letzter vollständiger Abruf 23:10 UTC am 10.11. = 11.11.
  await mitMeta(page, { abruf_fehler: { zeit: "2026-11-12T23:30:00+00:00", meldung: "HTTP 404" }, abruf_ok: "2026-11-10T23:10:00+00:00" });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector("#f-area")?.value);
  const h = await hinweise(page);
  const satz = "Der letzte Abruf am 13.11.2026 ist fehlgeschlagen; gezeigt wird der letzte gültige Datenstand vom 11.11.2026.";
  assert.ok(h.intro?.startsWith(`Hinweis: ${satz} Neuere Vorlagen und Termine können fehlen`), h.intro);
  assert.ok(h.stand.endsWith(` · ${satz}`), h.stand);
  // ohne Aufklappen sichtbar, Link ins Ratsinformationssystem
  assert.ok(await page.locator("#detail .stand-hinweis").isVisible());
  assert.equal(await page.locator('#detail .stand-hinweis a[href="https://ris.wuppertal.de/"]').count(), 1);
  const { funde } = await page.evaluate(kontrastUeberKarte, [[0, 0, 0], [128, 128, 128], [255, 255, 255]]);
  assert.deepEqual(funde.filter((f) => /Hinweis|Abruf|Ratsinformationssystem/.test(f)), []);
  assert.deepEqual(await axe(page), []);
  // Vorgang
  await page.goto(t.voll + VORGANG("1001/2026"));
  await vorgangOffen(page);
  assert.match((await page.locator("#detail .stand-hinweis").textContent()).replace(/\s+/g, " "), new RegExp(satz.replace(/[.()]/g, "\\$&")));
  assert.deepEqual(await axe(page), []);
  await pruefen(s);
});

test("Abruf nach den Vorlagen abgebrochen (abruf_teilweise): Hinweis nennt einen teilweise aktualisierten Stand, nicht den „letzten gültigen“", async () => {
  const s = await oeffnen(t.browser, t.voll, { warten: false });
  const { page } = s;
  await mitMeta(page, { abruf_fehler: { zeit: "2026-11-12T23:30:00+00:00", meldung: "HTTP 404" }, abruf_ok: "2026-11-10T23:10:00+00:00", abruf_teilweise: true });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForFunction(() => document.querySelector("#f-area")?.value);
  const h = await hinweise(page);
  const satz = "Der letzte Abruf am 13.11.2026 ist fehlgeschlagen; gezeigt wird ein teilweise aktualisierter Datenstand (letzter vollständiger Abruf am 11.11.2026). Bei einzelnen Vorlagen können Beratungen fehlen.";
  assert.ok(h.intro?.startsWith(`Hinweis: ${satz} Neuere Vorlagen und Termine können fehlen`), h.intro);
  assert.ok(h.stand.endsWith(` · ${satz}`), h.stand);
  assert.doesNotMatch(`${h.intro} ${h.stand}`, /letzte gültige Datenstand/);
  assert.deepEqual(await axe(page), []);
  await page.goto(t.voll + VORGANG("1001/2026"));
  await vorgangOffen(page);
  assert.ok((await page.locator("#detail .stand-hinweis").textContent()).replace(/\s+/g, " ").includes(satz));
  await pruefen(s);
});

test("Daten veraltet: Hinweis ab 3 Tagen ohne vollständigen Abruf (Berliner Tage); Gegenproben: frisch, Vorschau, Testdaten", async () => {
  const s = await oeffnen(t.browser, t.voll, { warten: false });
  const { page } = s;
  const ok = "2026-11-10T23:10:00+00:00";   // Berlin: 11.11.2026
  const laden = async (jetzt, meta = {}) => {
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await mitMeta(page, { abruf_fehler: null, abruf_ok: ok, ...meta });
    await page.clock.setFixedTime(new Date(jetzt));
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForFunction(() => document.querySelector("#f-area")?.value);
    return hinweise(page);
  };
  // 13.11. 23:59 Berlin: zwei Tage, noch kein Hinweis; 14.11. 00:01 Berlin (23:01 UTC am 13.11.): drei Tage
  let h = await laden("2026-11-13T22:59:00Z");
  assert.equal(h.intro, null, "nach zwei Tagen");
  assert.doesNotMatch(h.stand, /nicht aktualisiert|fehlgeschlagen/);
  h = await laden("2026-11-13T23:01:00Z");
  const satz = "Die Daten wurden seit dem 11.11.2026 nicht aktualisiert; gezeigt wird der letzte gültige Datenstand.";
  assert.ok(h.intro?.startsWith(`Hinweis: ${satz}`), h.intro);
  assert.ok(h.stand.endsWith(` · ${satz}`), h.stand);
  assert.deepEqual(await axe(page), []);
  // Gegenproben: Vorschau und Testdaten zeigen keinen Hinweis, auch nicht mit Fehler
  for (const art of ["vorschau", "testdaten"]) {
    h = await laden("2026-11-20T10:00:00Z", { [art]: true, abruf_fehler: { zeit: "2026-11-19T23:30:00+00:00", meldung: "x" } });
    assert.equal(h.intro, null, art);
    assert.doesNotMatch(h.stand, /nicht aktualisiert|fehlgeschlagen/, art);
  }
  // ohne abruf_ok (älterer Export): kein Hinweis auf veraltete Daten
  h = await laden("2026-11-20T10:00:00Z", { abruf_ok: undefined });
  assert.equal(h.intro, null, "ohne abruf_ok");
  await pruefen(s);
});
