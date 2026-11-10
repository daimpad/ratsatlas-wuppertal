// Bedienung mit der Tastatur (WCAG 2.1: 2.1.1 Tastatur, 2.1.2 keine Tastaturfalle, 2.4.3 Fokusreihenfolge, 2.4.7
// Fokus sichtbar) mit erfundenen Daten (testseite.py): Tab-Reihenfolge über Suche, Gebietswahl, Flächen und Menüs,
// Liste erreichbar, Menüs und Dialoge mit Escape schließbar, Fokus kehrt zurück, sichtbarer Fokus. Fremde Hosts
// blockiert (hilfe.mjs).
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

// Stil aller Elemente ohne Fokus merken (Umriss und Schatten). Ein Fokus gilt erst als sichtbar, wenn sich Umriss oder
// Schatten gegenüber diesem Zustand ändern; ein Schatten, den ein Knopf immer trägt (z. B. .toggle[aria-pressed=true]),
// zählt nicht.
const merken = (page) => page.evaluate(() => {
  const stil = (e) => { const st = getComputedStyle(e); return { umriss: `${st.outlineStyle} ${st.outlineWidth} ${st.outlineColor}`, schatten: st.boxShadow }; };
  window.__stil = stil;
  window.__ohneFokus = new WeakMap([...document.querySelectorAll("*")].map((e) => [e, stil(e)]));
});

// Beschreibung des fokussierten Elements und ob der Fokus sichtbar ist (Umriss oder Schatten anders als ohne Fokus)
const aktiv = (page) => page.evaluate(() => {
  const a = document.activeElement;
  if (!a || a === document.body) return { name: "body", sichtbar: false };
  const st = getComputedStyle(a);
  const name = a.id ? `#${a.id}` : a.dataset.panel ? `toggle:${a.dataset.panel}` : a.dataset.mega ? `menu:${a.dataset.mega}`
    : a.dataset.ref ? `vorlage:${a.dataset.ref}` : `${a.tagName.toLowerCase()}.${a.className}`;
  const vorher = window.__ohneFokus?.get(a);
  if (!vorher) return { name, sichtbar: false, grund: "Stil ohne Fokus nicht gemerkt" };
  const jetzt = window.__stil(a);
  const umriss = st.outlineStyle !== "none" && parseFloat(st.outlineWidth) > 0 && jetzt.umriss !== vorher.umriss;
  const schatten = jetzt.schatten !== "none" && jetzt.schatten !== vorher.schatten;
  return { name, sichtbar: umriss || schatten };
});

async function tabBis(page, ziel, max = 60) {
  const weg = [];
  for (let i = 0; i < max; i++) {
    await page.keyboard.press("Tab");
    const a = await aktiv(page);
    weg.push(a);
    if (ziel(a.name)) return weg;
  }
  assert.fail(`nicht per Tab erreicht; Weg: ${weg.map((a) => a.name).join(" → ")}`);
}

test("Tab-Reihenfolge: Suche, Gebietswahl, Flächen, Menüs, Über; Fokus immer sichtbar", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await merken(page);
  const weg = await tabBis(page, (n) => n === "#about-open");
  const namen = weg.map((a) => a.name);
  assert.deepEqual(namen, ["#q", "#f-area", "toggle:panel-list", "toggle:timeline-wrap", "toggle:panel-detail",
    "menu:mega-auswertung", "menu:mega-mitmachen", "menu:mega-daten", "menu:mega-verstehen", "#about-open"]);
  assert.deepEqual(weg.filter((a) => !a.sichtbar).map((a) => a.name), [], "Elemente ohne sichtbaren Fokus");
  await pruefen(s);
});

test("Suche: Escape schließt die Suchoptionen, Gebietswahl per Tastatur", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await page.keyboard.press("Tab");
  assert.equal((await aktiv(page)).name, "#q");
  await page.keyboard.type("Vorlage");
  await page.waitForFunction(() => !document.querySelector("#mega-suche").hidden);
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#mega-suche").hidden);
  // Gebietswahl: Auswahl per Tastatur löst den Wechsel aus
  await page.locator("#f-area").focus();
  await page.locator("#f-area").selectOption("ortsteil:testquartier-a");
  await page.waitForFunction(() => /gebiet=ortsteil/.test(location.search));
  await pruefen(s);
});

test("Liste per Tastatur: Vorlage öffnen, Escape schließt die Liste", async () => {
  const s = await oeffnen(t.browser, t.voll + "?gebiet=ortsteil:testquartier-a");
  const { page } = s;
  await page.locator('.toggle[data-panel="panel-list"]').focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => !document.querySelector("#panel-list").hidden);
  await merken(page);
  await page.locator('.toggle[data-panel="panel-list"]').focus();
  const weg = await tabBis(page, (n) => n.startsWith("vorlage:"), 30);
  assert.ok(weg.at(-1).sichtbar, "Fokus auf der Vorlage sichtbar");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang");
  assert.deepEqual(await axe(page), []);
  // Escape mit dem Fokus in der Liste schließt sie
  await page.locator("#papers button[data-ref]").first().focus();
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#panel-list").hidden);
  await pruefen(s);
});

test("Menüs und Dialog „Über“: Escape schließt, Fokus kehrt zurück, ohne Verstöße", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  for (const id of ["mega-auswertung", "mega-mitmachen", "mega-daten", "mega-verstehen"]) {
    const menu = page.locator(`.menu-btn[data-mega="${id}"]`);
    await menu.focus();
    await page.keyboard.press("Enter");
    assert.equal(await menu.getAttribute("aria-expanded"), "true", id);
    assert.equal(await page.locator(`#${id}`).isVisible(), true, id);
    assert.deepEqual(await axe(page), [], id);
    await page.keyboard.press("Escape");
    assert.equal(await menu.getAttribute("aria-expanded"), "false", id);
    assert.equal(await page.locator(`#${id}`).isVisible(), false, id);
    assert.equal((await aktiv(page)).name, `menu:${id}`, `Fokus zurück auf das Menü ${id}`);
  }
  await page.locator("#about-open").focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#about").open);
  assert.deepEqual(await axe(page), []);
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector("#about").open);
  assert.equal((await aktiv(page)).name, "#about-open", "Fokus zurück auf „Über“");
  await pruefen(s);
});
