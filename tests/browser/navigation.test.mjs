// Leiste und Startfenster nach Bonn (ratsatlas-bonn #219, #221, #222), Wuppertaler Fassung (Entscheidung 17.11.2026):
// Ansichten ohne Schalter „Vorgang“, Menüs „Mitmachen“ und „Über“ als Kacheln, Block „Aktuell in Wuppertal“ im Fenster
// „Los geht's“ (höchstens drei Einträge je Karte, Klick öffnet den Vorgang, auf dem Telefon eingeklappt), drei Rückwege
// (Schriftzug, Link am Ende des Vorgangs, Kachel im Menü „Mitmachen“), Kennzahlen und Verfahrenswege von der Liste aus,
// Tour bis zum Ende; axe (WCAG 2.0/2.1 A und AA) bei 1440, 1024 und 390 px. Erfundene Daten (testseite.py).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

const titel = (page) => page.locator("#detail-heading").textContent();

test("Leiste: Ansichten, Menüs „Mitmachen“ und „Über“, kein Schalter „Vorgang“; Menüs als Kacheln, axe in drei Breiten", async () => {
  for (const [width, height] of [[1440, 900], [1024, 768], [390, 844]]) {
    const s = await oeffnen(t.browser, t.voll, { width, height });
    const { page } = s;
    assert.deepEqual(await page.locator(".nav .menu-btn[data-mega]").evaluateAll((bs) => bs.map((b) => b.dataset.mega)),
      ["mega-mitmachen", "mega-ueber"]);
    assert.equal(await page.locator('.toggle[data-panel="panel-detail"], .toggle[data-panel="panel-prozesse"]').count(), 0);
    assert.equal(await page.locator(".nav-ai").isVisible(), false, "Assistent abgeschaltet");
    if (width < 900) { await page.keyboard.press("Escape"); await page.locator("#nav-burger").click(); }
    for (const id of ["mega-mitmachen", "mega-ueber"]) {
      await page.locator(`.menu-btn[data-mega="${id}"]`).click();
      assert.ok(await page.locator(`#${id}`).isVisible(), `${id} offen (${width} px)`);
      if (width < 900) assert.ok(await page.locator(`#nav-more #${id}`).count(), "klappt im Menü-Blatt auf");
      assert.deepEqual(await axe(page), [], `${id} bei ${width} px`);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `waagrechter Bildlauf ${width} px`);
    }
    const ueber = page.locator("#mega-ueber");
    const karten = await ueber.locator(".card:not([hidden])").evaluateAll((cs) => cs.map((c) => c.querySelector(".card-title").textContent));
    assert.deepEqual(karten, ["Begriffe erklärt", "Tour durch alle Funktionen", "Über den Ratsatlas", "Wie verlässlich sind die Angaben?",
      "Was ist neu?", "Hinweis geben", "Datenpaket (Zip)", "Verortete Vorlagen (GeoJSON)", "Datensatzbeschreibung (DCAT-AP)",
      "Feeds abonnieren und einbinden"]);
    assert.equal(await page.locator('#mega-mitmachen a[href*="bonn"]').count(), 0);
    await pruefen(s);
  }
});

test("Startfenster: „Aktuell in Wuppertal“, Vorlage öffnet den Vorgang, drei Rückwege; auf dem Telefon eingeklappt", async () => {
  let s = await oeffnen(t.browser, t.voll);
  let { page } = s;
  const block = page.locator("#detail .aktuell");
  assert.equal(await block.count(), 1, "Block „Aktuell“");
  assert.match(await block.locator("summary").textContent(), /^Aktuell in Wuppertal/);
  assert.equal(await block.evaluate((d) => d.open), true, "auf dem Desktop aufgeklappt");
  for (const liste of await block.locator(".akt-list").all()) assert.ok(await liste.locator("li").count() <= 3);
  const neu = block.locator(".akt-open");
  assert.ok(await neu.count() >= 1 && await neu.count() <= 3, "neue Vorlagen");
  assert.deepEqual(await axe(page), [], "Startfenster");
  const ref = await neu.first().getAttribute("data-open-ref");
  await neu.first().click();
  await page.waitForFunction((r) => decodeURIComponent(location.hash) === "#" + r, ref);
  assert.equal(await titel(page), "Vorgang");
  // 1. Schriftzug
  await page.click("a.brand");
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Los geht's");
  assert.ok(!page.url().includes("#"), "kein Vorgang mehr in der Adresse");
  // 2. Link am Ende des Vorgangs
  await page.locator("#detail .akt-open").first().click();
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang");
  await page.click("#detail .back-home button");
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Los geht's");
  assert.equal(await page.locator("#detail .aktuell").evaluate((d) => d.open), true);
  // 3. Kachel „Aktuell in Wuppertal“ im Menü „Mitmachen“
  await page.locator("#detail .akt-open").first().click();
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang");
  await page.click('[data-mega="mega-mitmachen"]');
  await page.click('#mega-mitmachen [data-home="aktuell"]');
  assert.equal(await page.locator("#mega-mitmachen").isHidden(), true);
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Los geht's");
  assert.equal(await page.evaluate(() => document.activeElement?.closest("#aktuell") !== null), true, "Fokus auf „Aktuell“");
  await pruefen(s);
  ({ page } = s = await oeffnen(t.browser, t.voll, { width: 390, height: 844 }));
  assert.equal(await page.locator("#detail .aktuell").evaluate((d) => d.open), false, "auf dem Telefon eingeklappt");
  assert.deepEqual(await axe(page), [], "Startfenster 390 px");
  await pruefen(s);
});

test("Kennzahlen und Verfahrenswege von der Liste aus; Tour bis zum Ende ohne Schritte für fehlende Menüs", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await page.locator('.toggle[data-panel="panel-list"]').click();
  await page.locator('#panel-list [data-open-tab="stats"]').click();
  assert.ok(await page.locator("#panel-auswertung").isVisible());
  await page.keyboard.press("Escape");
  await page.locator(".tour-cta[data-tour]").click();
  await page.waitForSelector(".tour-card");
  const titles = [];
  for (let i = 0; i < 30; i++) {
    titles.push(await page.locator("#tour-title").textContent());
    const weiter = page.locator('.tour-card [data-tour-act="next"]');
    if (/Fertig|Ende|Schließen/.test(await weiter.textContent())) { await weiter.click(); break; }
    await weiter.click();
    await page.waitForTimeout(150);
  }
  await page.waitForFunction(() => !document.querySelector(".tour"));
  for (const t_ of ["Menü „Mitmachen“", "Menü „Über“"]) assert.ok(titles.includes(t_), `${t_} fehlt: ${titles.join(" | ")}`);
  for (const t_ of ["Menü „Wer entscheidet“", "Menü „Themen“", "Der Ratsassistent", "Wer entscheidet was?"]) assert.ok(!titles.includes(t_), t_);
  await pruefen(s);
});
