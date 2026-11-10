// WCAG-2.1-AA-Restpunkte aus inventur/WCAG_vorpruefung.md, an der Karte mit erfundenen Daten (testseite.py):
// (a) 1.4.3/1.4.11 Kontrast der Bedienflächen und Beschriftungen über dem Kartenbild (kontrast.mjs, angenommene
// Kartentöne: Grautöne von Schwarz bis Weiß in Schritten von 16) und Fokusrahmen direkt auf der Karte, auch auf
// Gebietsflächen und Einzelpunkten (zweifarbiger Strich); (b) 2.5.3 Beschriftung im Namen bei
// Symbolknöpfen; (c) 2.1.2/2.4.3 Dialoge „Über“, „Was ist neu?“ und Tour: Fokus hinein, Tab bleibt drin, Escape
// schließt, Fokus zurück zum Auslöser; (d) 1.4.4/1.4.10 Zoom 200 % (1280×800 → 640×400 CSS-Pixel) und 320 px Breite:
// kein waagerechter Bildlauf, Bedienelemente im Fenster erreichbar. Bildschirmleser: nicht automatisierbar, offen.
// Fremde Hosts blockiert (hilfe.mjs); Kacheln werden nicht geladen (Testflächen liegen außerhalb des Kachelrahmens),
// der Kartenton wird angenommen statt gemessen. Die Testseite enthält Verortungen der Konfidenz „hoch“ und einen
// Sammelpunkt (HTML-Marker), damit --hoch, die Zahl auf dem Sammelpunkt und dessen Fokusrahmen geprüft werden.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, axe } from "./hilfe.mjs";
import { kontrastUeberKarte, fokusringAufKarte, fokusStrichAufKarte } from "./kontrast.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

// Kartentöne: Grau von 0 bis 255 in Schritten von 16 (kontrast.mjs: Leuchtdichte des Untergrunds im ganzen Bereich)
const GRAUREIHE = [...Array.from({ length: 16 }, (_, i) => i * 16), 255].map((g) => [g, g, g]);
const QUARTIER = "?gebiet=ortsteil:testquartier-a";

// Einblendungen (mega-in, Tour) abwarten, bevor gerechnet wird
const ruhig = (page) => page.evaluate(() => Promise.all(document.getAnimations().filter((a) => a.effect?.getTiming().iterations !== Infinity).map((a) => a.finished.catch(() => {}))));

async function kontrastAlle(page, zustand) {
  await ruhig(page);
  const { funde, anzahl } = await page.evaluate(kontrastUeberKarte, GRAUREIHE);
  assert.ok(anzahl >= 10, `${zustand}: nur ${anzahl} Textstellen geprüft`);
  return funde.map((f) => `${zustand}, ${f}`);
}

test("(a) Kontrast über dem Kartenbild: Text ≥ 4,5:1 (groß 3:1) auf Grautönen von Schwarz bis Weiß", async () => {
  const funde = [];
  // Breiter Bildschirm: Start, Liste, Zeitleiste, Vorgang, Legenden, jedes Menü, Dialoge, Tour
  let s = await oeffnen(t.browser, t.voll + QUARTIER);
  let { page } = s;
  funde.push(...await kontrastAlle(page, "Start Quartier"));
  assert.ok(await page.locator(".marker-cluster").count() >= 1, "Sammelpunkt auf der Karte (Testdaten)");
  await page.locator('.toggle[data-panel="panel-list"]').click();
  await page.locator('.toggle[data-panel="timeline-wrap"]').click();
  // Vorlage mit Konfidenz „hoch“ wählen: --hoch auf dem gewählten Listeneintrag ist der knappste Fall
  await page.locator("#papers button[data-ref]:has(.conf-hoch)").first().click();
  await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang");
  assert.ok(await page.locator('#papers button[aria-current="true"] .conf-hoch').count() === 1, "gewählt: Konfidenz „hoch“");
  await page.evaluate(() => document.querySelectorAll("#map details").forEach((d) => { d.open = true; }));
  funde.push(...await kontrastAlle(page, "Liste, Zeitleiste, Vorgang, Legenden"));
  await page.locator(".map-menu").click();
  funde.push(...await kontrastAlle(page, "Ebenen"));
  for (const id of ["mega-auswertung", "mega-mitmachen", "mega-daten", "mega-verstehen"]) {
    await page.locator(`.menu-btn[data-mega="${id}"]`).click();
    funde.push(...await kontrastAlle(page, id));
  }
  await page.keyboard.press("Escape");
  await page.locator("#q").fill("Vorlage");
  await page.waitForFunction(() => !document.querySelector("#mega-suche").hidden);
  funde.push(...await kontrastAlle(page, "Suche"));
  await page.keyboard.press("Escape");
  await page.locator("#about-open").click();
  funde.push(...await kontrastAlle(page, "Über"));
  await page.locator("#about [data-neu]").click();
  await page.waitForFunction(() => document.querySelector("#neu").open);
  funde.push(...await kontrastAlle(page, "Was ist neu?"));
  await page.keyboard.press("Escape");
  await pruefen(s);
  s = await oeffnen(t.browser, t.voll);
  ({ page } = s);
  funde.push(...await kontrastAlle(page, "Startansicht ganz Wuppertal"));
  await page.locator(".tour-cta").click();
  await page.waitForSelector(".tour-card");
  funde.push(...await kontrastAlle(page, "Tour"));
  await page.keyboard.press("Escape");
  await pruefen(s);
  // Telefon: Start, Menü, Blatt „Karte“
  s = await oeffnen(t.browser, t.voll + QUARTIER, { width: 390, height: 844 });
  ({ page } = s);
  funde.push(...await kontrastAlle(page, "Telefon"));
  await page.locator("#nav-burger").click();
  funde.push(...await kontrastAlle(page, "Telefon, Menü"));
  await page.keyboard.press("Escape");
  await page.locator(".map-menu").click();
  funde.push(...await kontrastAlle(page, "Telefon, Karte"));
  await pruefen(s);
  assert.deepEqual(funde, []);
});

test("(a) Gegenprobe: dünneres Glas, Beschriftung ohne Halo, Leaflet-Blau, --hoch aus Bonn und hellerer Sammelpunkt fallen auf", async () => {
  const s = await oeffnen(t.browser, t.voll + QUARTIER);
  const { page } = s;
  const gegen = await page.addStyleTag({ content: `:root { --surface-strong: rgba(255, 255, 255, 0.5); }
    .leaflet-tooltip.nav-label { text-shadow: 1px 1px 0 #fff, -1px -1px 0 #fff, 1px -1px 0 #fff, -1px 1px 0 #fff; }
    .leaflet-control-attribution a { color: #0078a8; }
    .marker-cluster-small div { background: rgba(167, 139, 250, 0.85) !important; }` });
  const erkannt = (funde, muster) => {
    for (const m of muster) assert.ok(funde.some((f) => m.test(f)), `nicht erkannt: ${m}\n${funde.join("\n")}`);
  };
  // Beschriftung der Gebiete nur mit Rand von 1 px (kein Halo), Quellenzeile (ohne Unschärfe, auf Schwarz), Zahl auf
  // dem Sammelpunkt
  erkannt(await kontrastAlle(page, "Gegenprobe"), [/nav-label/, /Karte rgb\(0,0,0\): a „OpenStreetMap/, /span „2“/]);
  // Glas mit Unschärfe (Liste): wirksamer Kartenton mindestens Mittelgrau
  await page.locator('.toggle[data-panel="panel-list"]').click();
  await page.locator("#papers button[data-ref]:has(.conf-hoch)").first().click();
  erkannt(await kontrastAlle(page, "Gegenprobe Liste"), [/Karte rgb\(128,128,128\): label/]);
  // --hoch mit dem Bonner Ton #1f7a4d auf dem gewählten Listeneintrag (sonst wie gestaltet)
  await gegen.evaluate((e) => e.remove());
  await page.addStyleTag({ content: ":root { --hoch: #1f7a4d; }" });
  const funde = await kontrastAlle(page, "Gegenprobe --hoch");
  assert.ok(funde.some((f) => /Karte rgb\(128,128,128\): span\.conf\.conf-hoch/.test(f)), `--hoch nicht erkannt\n${funde.join("\n")}`);
  assert.deepEqual(funde.filter((f) => !/conf-hoch/.test(f)), []);
  await pruefen(s);
});

// Gegenprobe der Rechnung selbst (ohne Seite): Minimum innerhalb des Bereichs der Kartentöne, opacity auf deckendem
// Hintergrund, Rand von 1 px ohne Verbreiterung zählt nicht als Halo
test("(a) Rechnung: Minimum zwischen Schwarz und Weiß, opacity des Hintergrunds, Halo", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await page.setContent(`<!doctype html><html><body style="margin:0">
    <div id="mitte" style="position:fixed;top:0;left:0;padding:8px"><span style="color:#767676">Mitte</span></div>
    <div id="op" style="position:fixed;top:60px;left:0;padding:8px;background:#333;opacity:.6"><span style="color:#fff">Deckend</span></div>
    <div id="rand" style="position:fixed;top:120px;left:0;padding:8px"><span style="color:#7c3aed;text-shadow:1px 1px 0 #fff,-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff">Rand</span></div>
    <div id="halo" style="position:fixed;top:180px;left:0;padding:8px"><span style="color:#6d28d9;text-shadow:1px 1px 0 #fff,-1px -1px 0 #fff,1px -1px 0 #fff,-1px 1px 0 #fff,0 0 3px #fff">Halo</span></div>
  </body></html>`);
  const r = await page.evaluate(kontrastUeberKarte, GRAUREIHE);
  const nur = (wort) => r.funde.filter((f) => f.includes(`„${wort}“`));
  // #767676 direkt auf der Karte: über Schwarz 4,62:1, über Weiß 4,54:1, das Minimum (≈ 1) liegt dazwischen
  assert.match(nur("Mitte")[0] || "", /Karte rgb\((11[2-9]|12[0-8]),\d+,\d+\): span „Mitte“: 1\.\d\d < 4\.5/);
  // Weiß auf #333 mit opacity .6: früher als deckend gerechnet (5,6:1), über hellem Kartenbild aber unter 4,5:1
  assert.match(nur("Deckend")[0] || "", /Karte rgb\(255,255,255\): span „Deckend“/, "opacity < 1 auf deckendem Hintergrund");
  assert.equal(nur("Rand").length, 1, "Rand von 1 px ist kein Halo");
  assert.deepEqual(nur("Halo"), []);
  await pruefen(s);
});

test("(a) Fokus direkt auf dem Kartenbild: Rahmen mit weißem Ring, Zoomknöpfe innen, Karte mit Rahmen am Rand", async () => {
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    const s = await oeffnen(t.browser, t.voll + QUARTIER, { width, height });
    const { page } = s;
    if (width < 900) await page.locator(".map-menu").click();
    // Steuerung auf der Karte (Ebenen, Legenden, Quellenzeile), ohne die Zoomknöpfe; HTML-Marker (Sammelpunkt)
    const ziele = await page.locator(".leaflet-control-container :is(a[href], button, summary):not(.leaflet-bar a), .leaflet-marker-icon[tabindex]").all();
    assert.ok(await page.locator(".leaflet-marker-icon[tabindex]").count() >= 1, `${width}: kein HTML-Marker (Testdaten)`);
    let geprueft = 0;
    for (const el of ziele) {
      if (!(await el.isVisible()) || await el.evaluate((e) => Boolean(e.closest(".glass")))) continue;
      // Fokus wie aus der Tastatur (:focus-visible): Chromium nach Shift, Firefox nur mit focusVisible (nach el.focus()
      // und Shift nicht, nach Tab schon; Messung 10.11.2026)
      await el.evaluate((e) => e.focus({ focusVisible: true }));
      await page.keyboard.press("Shift");
      const ergebnis = await page.evaluate(fokusringAufKarte);
      assert.equal(ergebnis, "ok", `${width}: ${await el.evaluate((e) => e.outerHTML.slice(0, 90))}`);
      geprueft++;
    }
    assert.ok(geprueft >= 3, `${width}: nur ${geprueft} Bedienelemente auf der Karte geprüft`);
    // Zoomknöpfe: .leaflet-bar schneidet ab, Rahmen deshalb innen; Weiß des Knopfs liegt beiderseits
    if (width > 900) {
      await page.locator(".leaflet-control-zoom-in").evaluate((e) => e.focus({ focusVisible: true }));
      await page.keyboard.press("Shift");
      const z = await page.evaluate(() => {
        const st = getComputedStyle(document.activeElement);
        const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
        const lum = (s) => { const [r, g, b] = s.match(/\d+(\.\d+)?/g).map(Number); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
        const [h, d] = [lum(st.outlineColor), lum(st.backgroundColor)].sort((x, y) => y - x);
        return { abstand: parseFloat(st.outlineOffset), breite: parseFloat(st.outlineWidth), grund: st.backgroundColor, kontrast: (h + 0.05) / (d + 0.05) };
      });
      assert.ok(z.abstand <= -z.breite, `Zoomknopf: Rahmen nicht innen (${JSON.stringify(z)})`);
      assert.ok(z.kontrast >= 3, `Zoomknopf: Rahmen gegen Knopf ${JSON.stringify(z)}`);
    }
    // Karte (Tastatursteuerung von Leaflet): Rahmen im Kartenfeld mit weißem Band
    await page.locator("#map").evaluate((e) => e.focus({ focusVisible: true }));
    await page.keyboard.press("Shift");
    const band = await page.evaluate(() => getComputedStyle(document.getElementById("map"), "::after").boxShadow);
    assert.match(band, /rgb\(124, 58, 237\) 0px 0px 0px 3px inset, rgb\(255, 255, 255\) 0px 0px 0px 7px inset/);
    // Gegenprobe: Sammelpunkt ohne weißen Ring fällt auf
    if (width > 900) {
      await page.addStyleTag({ content: ".leaflet-marker-icon:focus-visible { box-shadow: none !important; }" });
      await page.locator(".leaflet-marker-icon[tabindex]").first().evaluate((e) => e.focus({ focusVisible: true }));
      await page.keyboard.press("Shift");
      assert.match(await page.evaluate(fokusringAufKarte), /^kein deckender Ring/);
    }
    await pruefen(s);
  }
});

// Fokus per Tab auf den ersten Pfad der Karte in der Ebene `ebene` (Gebiete: .leaflet-gebiete-pane, Einzelpunkte:
// .leaflet-overlay-pane); Start im Suchfeld
async function tabAufPfad(page, ebene) {
  await page.locator("#q").focus();
  for (let i = 0; i < 60; i++) {
    await page.keyboard.press("Tab");
    if (await page.evaluate((e) => document.activeElement instanceof SVGPathElement && Boolean(document.activeElement.closest(e)), ebene)) return;
  }
  assert.fail(`kein Pfad in ${ebene} per Tab erreicht`);
}
// Stil des fokussierten Pfads, wie Leaflet ihn setzt (Attribute), ohne d (folgt dem Ausschnitt)
const pfadStil = (page) => page.evaluate(() => Object.fromEntries(["stroke", "stroke-width", "stroke-opacity", "fill", "fill-opacity", "filter", "class"]
  .map((a) => [a, document.activeElement.getAttribute(a)])));

test("(a) Fokus auf Gebietsflächen und Einzelpunkten: zweifarbiger Strich gegen jeden Kartenton, Leaflet-Stil bleibt", async () => {
  // Stadtbezirk in der Startansicht: Strich folgt dem Umriss; beim Überfahren (Glaseffekt) bleiben Fokus und Strich
  // (früher holte Leaflet die Fläche nach vorn und hängte sie dabei um, der Fokus fiel an <body>); danach Stil der
  // Fläche wie vorher und Strich wieder weg
  let s = await oeffnen(t.browser, t.voll);
  let { page } = s;
  await tabAufPfad(page, ".leaflet-gebiete-pane");
  const vorher = await pfadStil(page);
  assert.deepEqual(await page.evaluate(fokusStrichAufKarte, GRAUREIHE), [], "Fläche");
  const r = await page.evaluate(() => { const b = document.activeElement.getBoundingClientRect(); return { x: b.left + b.width / 3, y: b.top + b.height / 3 }; });
  await page.mouse.move(r.x, r.y);
  await page.waitForFunction(() => document.activeElement.getAttribute("filter") === "url(#nav-glow)", null, { timeout: 3000 })
    .catch(async () => assert.fail(`Fokus beim Überfahren verloren: ${await page.evaluate(() => document.activeElement.tagName)}`));
  assert.deepEqual(await page.evaluate(fokusStrichAufKarte, GRAUREIHE), [], "Fläche beim Überfahren");
  await page.mouse.move(5, 895);
  assert.deepEqual(await pfadStil(page), vorher, "Stil nach dem Überfahren");
  const flaeche = await page.evaluateHandle(() => document.activeElement);
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(".fokus-saum, .fokus-strich").count(), 0, "Strich nach dem Verlassen des Fokus");
  assert.deepEqual(await flaeche.evaluate((e) => Object.fromEntries(["stroke", "stroke-width", "stroke-opacity", "fill", "fill-opacity", "filter", "class"]
    .map((a) => [a, e.getAttribute(a)]))), vorher, "Stil nach dem Verlassen des Fokus");
  await pruefen(s);
  // Einzelpunkt im Quartier: Ring außen, Stil des Punkts danach wie vorher
  s = await oeffnen(t.browser, t.voll + QUARTIER);
  ({ page } = s);
  await tabAufPfad(page, ".leaflet-overlay-pane");
  const punkt = await pfadStil(page);
  assert.deepEqual(await page.evaluate(fokusStrichAufKarte, GRAUREIHE), [], "Einzelpunkt");
  await page.keyboard.press("Tab");
  assert.equal(await page.locator(".fokus-strich").count(), 0, "Strich nach dem Verlassen des Fokus");
  await page.keyboard.press("Shift+Tab");
  assert.deepEqual(await pfadStil(page), punkt, "Stil des Punkts");
  // Aktivieren ohne mousedown, wie Hilfstechnik es auslöst: Auswahl hebt den Punkt hervor (highlight), Fokus und Strich
  // bleiben (früher holte bringToFront den Punkt nach vorn, der Fokus fiel an <body>)
  const gewaehlt = await page.evaluateHandle(() => document.activeElement);
  await page.evaluate(() => document.activeElement.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window })));
  await page.waitForFunction((e) => e.getAttribute("stroke-width") === "3", gewaehlt, { timeout: 3000 })
    .catch(() => assert.fail("Punkt nach dem Aktivieren nicht hervorgehoben"));
  assert.equal(await gewaehlt.evaluate((e) => document.activeElement === e), true,
    `Fokus nach dem Aktivieren verloren: ${await page.evaluate(() => document.activeElement.tagName)}`);
  assert.deepEqual(await page.evaluate(fokusStrichAufKarte, GRAUREIHE), [], "Einzelpunkt nach dem Aktivieren");
  // Quartiersfläche: In der Quartiersansicht zeigt die Karte mit den Testdaten die Stadtbezirke (Modus „bezirke“); die
  // Eingabetaste auf dem Stadtbezirk zeigt seine Quartiere und setzt den Fokus auf das erste (karte-tastatur.test.mjs)
  await tabAufPfad(page, ".leaflet-gebiete-pane");
  assert.match(await page.evaluate(() => document.activeElement.getAttribute("aria-label")), /^Stadtbezirk /);
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => /^Quartier /.test(document.activeElement?.getAttribute("aria-label") || ""), null, { timeout: 3000 })
    .catch(async () => assert.fail(`Fokus nicht auf einem Quartier: ${await page.evaluate(() => document.activeElement.outerHTML.slice(0, 80))}`));
  assert.deepEqual(await page.evaluate(fokusStrichAufKarte, GRAUREIHE), [], "Quartier");
  await pruefen(s);
});

test("(a) Gegenprobe Fokus auf Flächen: nur Umriss, violetter Strich und schmaler Saum fallen auf", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  await tabAufPfad(page, ".leaflet-gebiete-pane");
  const mit = async (css) => {
    const tag = await page.addStyleTag({ content: css });
    const f = await page.evaluate(fokusStrichAufKarte, GRAUREIHE);
    await tag.evaluate((e) => e.remove());
    return f.join("\n");
  };
  // alter Stand: nur der Umriss (outline) des Browsers
  assert.match(await mit(".leaflet-pane path.fokus-saum, .leaflet-pane path.fokus-strich { display: none; }"), /^kein zweifarbiger Strich/);
  // --accent-ink statt --text: gegen Weiß 7,1:1, aber Lücke bei hellem Mittelgrau
  assert.match(await mit(".leaflet-pane path.fokus-strich { stroke: var(--accent-ink); }"), /^Karte rgb\(1[4-6]\d,1[4-6]\d,1[4-6]\d\): Saum \d\.\d\d, Strich \d\.\d\d < 3$/);
  assert.match(await mit(".leaflet-pane path.fokus-saum { stroke-width: 5px; }"), /^Saum beiderseits 1 px < 2 px$/);
  assert.deepEqual(await page.evaluate(fokusStrichAufKarte, GRAUREIHE), []);
  await pruefen(s);
});

// 2.5.3 Beschriftung im Namen: Steht sichtbarer Text mit Buchstaben oder Ziffern in einem Bedienelement mit aria-label,
// muss der Name ihn enthalten. Reine Symbole (‹ › × ? ⓘ + −) sind keine Beschriftung; sie sind für Bildschirmleser
// verborgen (aria-hidden), damit der Name nur aus aria-label kommt. Geprüft werden alle sichtbaren Bedienelemente.
function beschriftungImNamen() {
  const funde = [];
  const norm = (s) => s.toLowerCase().replace(/\s+/g, " ").trim();
  const sel = 'a[href], button, summary, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [role="switch"], [role="checkbox"], [role="radio"], [role="option"]';
  for (const el of document.querySelectorAll(sel)) {
    const name = el.getAttribute("aria-label");
    if (!name || !el.checkVisibility() || !el.getClientRects().length) continue;
    // sichtbarer Text, getrennt nach für Bildschirmleser offen bzw. verborgen
    let offen = "";
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (!n.data.trim() || !n.parentElement.checkVisibility()) continue;
      if (!n.parentElement.closest('[aria-hidden="true"]')) offen += " " + n.data;
    }
    const text = norm(offen);
    const beschreibung = el.outerHTML.slice(0, 100);
    if (!text) continue;
    if (/[\p{L}\p{N}]/u.test(text)) { if (!norm(name).includes(text)) funde.push(`Text „${text}“ fehlt im Namen „${name}“: ${beschreibung}`); }
    else funde.push(`Symbol „${text}“ nicht verborgen (aria-hidden): ${beschreibung}`);
  }
  return funde;
}

test("(b) 2.5.3 Beschriftung im Namen: Symbolknöpfe verborgen, sichtbarer Text im Namen; Gegenprobe", async () => {
  const funde = [];
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    const s = await oeffnen(t.browser, t.voll + QUARTIER, { width, height });
    const { page } = s;
    funde.push(...(await page.evaluate(beschriftungImNamen)).map((f) => `${width}: ${f}`));
    if (width > 900) {
      await page.locator('.toggle[data-panel="panel-list"]').click();
      await page.locator('.toggle[data-panel="timeline-wrap"]').click();
      await page.locator("#papers button[data-ref]").first().click();
      await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang");
      assert.ok(await page.locator(".erkl-btn").count() > 0, "Vorgang ohne Erklärknopf");
      funde.push(...(await page.evaluate(beschriftungImNamen)).map((f) => `Vorgang: ${f}`));
      await page.locator("#about-open").click();
      funde.push(...(await page.evaluate(beschriftungImNamen)).map((f) => `Über: ${f}`));
      await page.keyboard.press("Escape");
    } else {
      assert.ok(await page.locator(".attr-info").isVisible(), "ⓘ in der Quellenzeile");
    }
    // axe meldet für diese Knöpfe nur „unvollständig“; nach der Änderung keine Verstöße
    assert.deepEqual(await axe(page), []);
    await pruefen(s);
  }
  assert.deepEqual(funde, []);
  // Gegenprobe: offenes Symbol und fehlender Text fallen auf
  const s = await oeffnen(t.browser, t.voll);
  await s.page.evaluate(() => document.querySelector("#detail").insertAdjacentHTML("afterbegin",
    '<button type="button" aria-label="Schließen">×</button><button type="button" aria-label="Weiter">Nächste Seite</button>'));
  const gegen = await s.page.evaluate(beschriftungImNamen);
  assert.equal(gegen.length, 2, gegen.join("\n"));
  await pruefen(s);
});

// Name des fokussierten Elements; „außen“, wenn es außerhalb des Bereichs liegt (body = Browseroberfläche)
const fokusIn = (page, bereich) => page.evaluate((b) => {
  const a = document.activeElement;
  if (!a || a === document.body) return "body";
  const name = a.id ? `#${a.id}` : a.dataset?.mega ? `menu:${a.dataset.mega}` : `${a.tagName.toLowerCase()}.${a.className}`;
  return document.querySelector(b).contains(a) ? `in ${name}` : `außen ${name}`;
}, bereich);

// Tab und Umschalt+Tab: Fokus bleibt im Dialog (body heißt: Fokus in der Oberfläche des Browsers, bei modalen
// Dialogen erlaubt; die Seite dahinter ist inert)
async function tabBleibtIn(page, bereich, schritte = 30) {
  const weg = [];
  for (const taste of ["Tab", "Shift+Tab"]) {
    for (let i = 0; i < schritte; i++) { await page.keyboard.press(taste); weg.push(await fokusIn(page, bereich)); }
  }
  assert.deepEqual(weg.filter((w) => w.startsWith("außen")), [], `Fokus verlässt ${bereich}`);
  assert.ok(weg.filter((w) => w.startsWith("in")).length > schritte, `Fokus kaum in ${bereich}: ${weg.join(", ")}`);
}

async function dialogPruefen(page, dialog, oeffnen, zurueck) {
  await oeffnen();
  await page.waitForFunction((d) => document.querySelector(d).open, dialog);
  assert.match(await fokusIn(page, dialog), /^in /, `${dialog}: Fokus beim Öffnen im Dialog`);
  await tabBleibtIn(page, dialog);
  await page.keyboard.press("Escape");
  await page.waitForFunction((d) => !document.querySelector(d).open, dialog);
  await page.waitForFunction((z) => document.activeElement?.matches(z), zurueck, { timeout: 2000 })
    .catch(async () => assert.fail(`${dialog}: Fokus nicht zurück auf ${zurueck}, sondern ${await fokusIn(page, "body")}`));
}

test("(c) Dialoge „Über“ und „Was ist neu?“: Fokus hinein, Tab bleibt drin, Escape schließt, Fokus zurück", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  const menue = async (id) => { await page.locator(`.menu-btn[data-mega="${id}"]`).focus(); await page.keyboard.press("Enter"); };
  // „Über“ aus der Leiste
  await dialogPruefen(page, "#about", async () => { await page.locator("#about-open").focus(); await page.keyboard.press("Enter"); }, "#about-open");
  // „Über“ aus dem Menü „Verstehen“ (Menü schließt sich): zurück zum Menüknopf
  await dialogPruefen(page, "#about", async () => { await menue("mega-verstehen"); await page.locator("#mega-verstehen [data-about]").first().focus(); await page.keyboard.press("Enter"); },
    '.menu-btn[data-mega="mega-verstehen"]');
  // „Was ist neu?“ aus dem Menü „Daten“
  await dialogPruefen(page, "#neu", async () => { await menue("mega-daten"); await page.locator("#mega-daten [data-neu]").focus(); await page.keyboard.press("Enter"); },
    '.menu-btn[data-mega="mega-daten"]');
  // „Was ist neu?“ aus „Über“ („Über“ schließt sich): zurück zu „Über“
  await dialogPruefen(page, "#neu", async () => {
    await page.locator("#about-open").focus(); await page.keyboard.press("Enter");
    await page.locator("#about [data-neu]").focus(); await page.keyboard.press("Enter");
  }, "#about-open");
  // Schließen-Knopf statt Escape: ebenfalls zurück
  await page.locator("#about-open").focus();
  await page.keyboard.press("Enter");
  await page.locator("#about-close").focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.activeElement?.id === "about-open");
  await pruefen(s);
});

test("(c) Dialoge auf dem Telefon: Auslöser im Menü verschwindet, Fokus zurück auf „Menü“", async () => {
  const s = await oeffnen(t.browser, t.voll, { width: 390, height: 844 });
  const { page } = s;
  await dialogPruefen(page, "#neu", async () => {
    await page.locator("#nav-burger").click();
    await page.locator('.menu-btn[data-mega="mega-daten"]').click();
    await page.locator("#mega-daten [data-neu]").focus();
    await page.keyboard.press("Enter");
  }, "#nav-burger");
  await pruefen(s);
});

async function tourPruefen(page, starten, zurueck) {
  await starten();
  await page.waitForSelector(".tour-card");
  await page.waitForFunction(() => document.querySelector(".tour-card").contains(document.activeElement));
  assert.equal(await page.evaluate(() => document.activeElement.dataset.tourAct), "next", "Fokus auf „Los geht's“");
  // Seite hinter der Tour inert
  assert.equal(await page.evaluate(() => [...document.querySelectorAll("body > header, body > main")].every((e) => e.inert)), true);
  await tabBleibtIn(page, ".tour-card", 6);
  // weiterblättern: Fokus bleibt in der Karte
  await page.keyboard.press("ArrowRight");
  await page.waitForFunction(() => /^Schritt 2 /.test(document.querySelector("#tour-count")?.textContent || ""));
  await tabBleibtIn(page, ".tour-card", 6);
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector(".tour"));
  await page.waitForFunction((z) => document.activeElement?.matches(z), zurueck, { timeout: 2000 })
    .catch(async () => assert.fail(`Tour: Fokus nicht zurück auf ${zurueck}, sondern ${await fokusIn(page, "body")}`));
  assert.equal(await page.evaluate(() => [...document.querySelectorAll("body > header, body > main")].some((e) => e.inert)), false);
}

test("(c) Tour: Fokus in die Karte, Tab bleibt drin, Escape beendet, Fokus zurück zum Auslöser", async () => {
  const s = await oeffnen(t.browser, t.voll);
  const { page } = s;
  // aus dem Fenster „Los geht's“
  await tourPruefen(page, async () => { await page.locator(".tour-cta").focus(); await page.keyboard.press("Enter"); }, ".tour-cta");
  // aus dem Menü „Verstehen“ (Menü schließt sich): zurück zum Menüknopf
  await tourPruefen(page, async () => {
    await page.locator('.menu-btn[data-mega="mega-verstehen"]').focus(); await page.keyboard.press("Enter");
    await page.locator("#mega-verstehen [data-tour]").focus(); await page.keyboard.press("Enter");
  }, '.menu-btn[data-mega="mega-verstehen"]');
  // aus „Über“ („Über“ schließt sich): zurück zu „Über“
  await tourPruefen(page, async () => {
    await page.locator("#about-open").focus(); await page.keyboard.press("Enter");
    await page.locator("#about [data-tour]").focus(); await page.keyboard.press("Enter");
  }, "#about-open");
  await pruefen(s);
});

// Lage der Bedienelemente: kein waagerechter Bildlauf der Seite, kein sichtbares Bedienelement ragt seitlich aus dem
// Fenster (außer in einem waagerecht rollbaren Bereich und außer Inhalten der Karte: Marker und Flächen liegen je nach
// Ausschnitt auch außerhalb; Karten sind von 1.4.10 ausgenommen, per Tab rückt die Karte sie ins Bild, siehe unten)
const lage = (page) => page.evaluate(() => {
  const d = document.documentElement;
  const rollbar = (e) => { for (let p = e.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if ((o === "auto" || o === "scroll") && p.scrollWidth > p.clientWidth) return true; } return false; };
  const raus = [...document.querySelectorAll('a[href], button, input, select, summary, [tabindex]:not([tabindex="-1"])')]
    .filter((e) => e.checkVisibility() && e.getClientRects().length && !e.closest("[hidden], [inert], .leaflet-map-pane") && !rollbar(e))
    .filter((e) => { const r = e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth + 1; })
    .map((e) => e.outerHTML.slice(0, 80));
  return { breite: Math.max(d.scrollWidth, document.body.scrollWidth), fenster: innerWidth, raus };
});

// Tab durch die Seite: jedes fokussierte Element liegt (nach dem automatischen Rollen) im Fenster und ist nicht von
// einer anderen Fläche verdeckt (2.4.7, 2.4.11 aus WCAG 2.2): An der Mitte seines sichtbaren Teils liefert
// elementFromPoint das Element selbst, einen Nachfahren oder sein <label>. Inhalte der Karte (Gebietsflächen, Punkte,
// Beschriftungen in .leaflet-map-pane) überlagern sich geometrisch (Stadtbezirk um seine Quartiere); ein anderer Inhalt
// der Karte gilt deshalb nicht als Verdeckung eines Inhalts der Karte (Sichtbarkeit des Fokus auf Gebietsflächen:
// eigener Test in (a), zweifarbiger Strich). Bedienflächen über der Karte (Steuerung, Blätter, Menüs) zählen.
const fokusLage = () => {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  const b = a.getBoundingClientRect();
  const name = `${a.outerHTML.slice(0, 80)} (${Math.round(b.left)}, ${Math.round(b.top)})`;
  if (!(b.width > 0 && b.height > 0 && b.right > 0 && b.bottom > 0 && b.left < innerWidth && b.top < innerHeight)) return `außerhalb: ${name}`;
  const x = (Math.max(b.left, 0) + Math.min(b.right, innerWidth)) / 2, y = (Math.max(b.top, 0) + Math.min(b.bottom, innerHeight)) / 2;
  const e = document.elementFromPoint(x, y);
  if (e && (a.contains(e) || [...(a.labels || [])].some((l) => l.contains(e)))) return null;
  if (e && a.closest(".leaflet-map-pane") && e.closest(".leaflet-map-pane")) return null;
  return `verdeckt von ${e ? e.outerHTML.slice(0, 60) : "nichts"}: ${name}`;
};

// Liefert die Funde; `marker`: wie oft der Fokus auf einem Marker oder Sammelpunkt der Karte lag
async function tabImFenster(page, schritte) {
  const funde = [];
  funde.marker = 0;
  for (let i = 0; i < schritte; i++) {
    await page.keyboard.press("Tab");
    const r = await page.evaluate(fokusLage);
    if (r) funde.push(r);
    if (await page.evaluate(() => Boolean(document.activeElement?.closest(".leaflet-marker-icon")))) funde.marker++;
  }
  return funde;
}

test("(d) Zoom 200 % (640×400) und 320 px Breite: kein waagerechter Bildlauf, Bedienelemente erreichbar", async () => {
  for (const [width, height] of [[640, 400], [320, 640]]) {
    const s = await oeffnen(t.browser, t.voll + QUARTIER, { width, height });
    const { page } = s;
    const zustaende = [
      ["Start", async () => {}],
      ["Menü", async () => { await page.locator("#nav-burger").click(); }],
      ["Menü „Daten“", async () => { await page.locator('.menu-btn[data-mega="mega-daten"]').click(); }],
      // „Karte“ per Tastatur bei offenem Fenster „Los geht's“: Das Blatt muss oben liegen, nicht unter der Fläche
      ["Karte", async () => {
        await page.keyboard.press("Escape"); await page.keyboard.press("Escape");
        await page.evaluate(() => window.risKarte.ui.panel("panel-detail", true));
        assert.equal(await page.locator("#panel-detail").isVisible(), true);
        await page.locator(".map-menu").focus(); await page.keyboard.press("Enter");
        await ruhig(page);
        const oben = await page.evaluate(() => {
          const r = document.querySelector("#map-sheet").getBoundingClientRect();
          const e = document.elementFromPoint(r.left + r.width / 2, r.top + Math.min(r.height / 2, 40));
          return Boolean(e && e.closest("#map-sheet"));
        });
        assert.ok(oben, `${width}×${height}: Blatt „Karte“ verdeckt`);
      }],
      ["Liste", async () => { await page.keyboard.press("Escape"); await page.locator("#nav-burger").click(); await page.locator('.toggle[data-panel="panel-list"]').click(); }],
      ["Vorgang", async () => { await page.locator("#papers button[data-ref]").first().click(); await page.waitForFunction(() => document.querySelector("#detail-heading").textContent === "Vorgang"); }],
      ["Über", async () => { await page.keyboard.press("Escape"); await page.evaluate(() => document.querySelector("#about-open").click()); }],
    ];
    for (const [name, schritt] of zustaende) {
      await schritt();
      await ruhig(page);
      const l = await lage(page);
      assert.ok(l.breite <= l.fenster, `${width}×${height} ${name}: Seite ${l.breite} px breit, Fenster ${l.fenster} px`);
      assert.deepEqual(l.raus, [], `${width}×${height} ${name}: Bedienelemente seitlich außerhalb`);
    }
    await page.keyboard.press("Escape");
    // alle Bedienelemente der Seite per Tab im Fenster und nicht verdeckt (Leiste unten, Blätter, Karte). Start im
    // Suchfeld: Es öffnet die Suchoptionen, die beim Verlassen per Tab schließen müssen
    await page.locator("#q").focus();
    assert.equal(await page.locator("#mega-suche").isVisible(), true, "Suchoptionen offen");
    // Die Karte zeigt nach „Vorgang“ den Ausschnitt um die gewählte Vorlage; der Sammelpunkt liegt dann am Rand und
    // muss beim Fokus ins freie Kartenfeld rücken
    const funde = await tabImFenster(page, 40);
    assert.deepEqual([...funde], [], `${width}×${height}: per Tab fokussiert, aber außerhalb des Fensters oder verdeckt`);
    assert.ok(funde.marker >= 1, `${width}×${height}: Sammelpunkt per Tab nicht erreicht`);
    await page.locator("#nav-burger").click();
    await page.locator("#nav-burger").focus();
    assert.deepEqual([...await tabImFenster(page, 25)], [], `${width}×${height}: Menü per Tab, außerhalb des Fensters oder verdeckt`);
    await pruefen(s);
  }
});

test("(d) Suchoptionen schließen, wenn der Fokus sie verlässt; Gegenprobe: verdeckter Fokus fällt auf", async () => {
  const s = await oeffnen(t.browser, t.voll + QUARTIER, { width: 640, height: 400 });
  const { page } = s;
  const offen = () => page.locator("#mega-suche").isVisible();
  // Tab vom Suchfeld durch die Suchoptionen: offen, solange der Fokus darin ist, danach geschlossen
  await page.locator("#q").focus();
  const weg = [];
  for (let i = 0; i < 20 && (await offen()); i++) {
    await page.keyboard.press("Tab");
    weg.push(await page.evaluate(() => Boolean(document.activeElement.closest("#mega-suche, #nav-search"))));
  }
  assert.equal(await offen(), false, "Suchoptionen nach dem Verlassen per Tab noch offen");
  assert.deepEqual(weg.slice(0, -1).filter((w) => !w), [], "Suchoptionen schlossen, solange der Fokus darin war");
  assert.equal(weg.at(-1), false);
  // Umschalt+Tab zurück ins Suchfeld öffnet sie wieder (wie ein Klick hinein)
  await page.keyboard.press("Shift+Tab");
  for (let i = 0; i < 20 && (await page.evaluate(() => document.activeElement.id)) !== "q"; i++) await page.keyboard.press("Shift+Tab");
  assert.equal(await offen(), true);
  // Gegenprobe: Eine Fläche über dem fokussierten Knopf „Karte“ wird erkannt
  await page.keyboard.press("Escape");
  await page.evaluate(() => document.body.insertAdjacentHTML("beforeend", '<div id="deckel" style="position:fixed;inset:0;z-index:99999;background:#fff"></div>'));
  await page.locator(".map-menu").focus();
  assert.match(await page.evaluate(fokusLage), /^verdeckt von <div id="deckel"/);
  await pruefen(s);
});
