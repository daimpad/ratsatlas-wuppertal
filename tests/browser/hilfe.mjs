// Gemeinsame Hilfen der Browser-Prüfung (Playwright, Chromium oder Firefox, axe-core): Testseite aus erfundenen Daten erzeugen
// (tests/browser/testseite.py), lokal auf 127.0.0.1 ausliefern, Seiten öffnen, jede Anfrage an andere Hosts blockieren
// und als Fehler melden, axe mit WCAG 2.0/2.1 A und AA. Abgeleitet aus den Bonner Tests (allris-test @52fe9ca,
// tests/browser/*.test.mjs: open(), axe()); Wuppertaler Abweichungen: eigene Testseite statt echter Rohdaten, Server im
// Testprozess, Tags wcag21a/wcag21aa, fehlende Dateien (HTTP 404) zählen als Fehler, außer ausdrücklich erwartete;
// ohne bypassCSP (axe per page.evaluate, CSP-Verstöße zählen als Fehler); pruefen() wartet, bis keine Anfrage mehr läuft.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync, mkdtempSync, rmSync, statSync, createReadStream } from "node:fs";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, extname, resolve, sep, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, firefox } from "playwright";

const HIER = dirname(fileURLToPath(import.meta.url));
const AXE = readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const TYPEN = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json", ".geojson": "application/geo+json",
  ".jsonld": "application/ld+json", ".xml": "application/xml", ".ics": "text/calendar", ".tsv": "text/tab-separated-values",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon", ".woff2": "font/woff2",
  ".webmanifest": "application/manifest+json", ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8",
};

// statischer Server nur auf 127.0.0.1 (wie python -m http.server: Ordner → index.html, sonst 404)
function ausliefern(wurzel) {
  const server = createServer((req, res) => {
    let pfad;
    try { pfad = decodeURIComponent(new URL(req.url, "http://127.0.0.1").pathname); } catch { pfad = "/"; }
    let datei = resolve(wurzel, "." + pfad);
    if (datei !== wurzel && !datei.startsWith(wurzel + sep)) { res.writeHead(403).end(); return; }
    try {
      if (statSync(datei).isDirectory()) datei = join(datei, "index.html");
      statSync(datei);
    } catch { res.writeHead(404, { "Content-Type": "text/plain" }).end("nicht gefunden"); return; }
    res.writeHead(200, { "Content-Type": TYPEN[extname(datei)] || "application/octet-stream" });
    createReadStream(datei).pipe(res);
  });
  return new Promise((ok) => server.listen(0, "127.0.0.1", () => ok(server)));
}

// Browser aus BROWSER: chromium (Vorgabe) oder firefox (Schritt „Browser-Prüfung in Firefox“ im Job browser von
// tests.yml: karte-tastatur, tastatur, wcag)
export const BROWSER = process.env.BROWSER === "firefox" ? "firefox" : "chromium";

// Testseite in einem Temp-Ordner erzeugen und ausliefern: voll (mit Gesamtexport, Adressen für ihren Server) und leer
// (nur site/, ohne data/). Python aus PYTHON (Vorgabe python3) mit den Paketen aus requirements.txt.
export async function starten() {
  const ordner = mkdtempSync(join(tmpdir(), "ratsatlas-browser-"));
  const voll = await ausliefernNach(ordner, "voll");
  const leer = await ausliefernNach(ordner, "leer");
  const py = process.env.PYTHON || "python3";
  const lauf = spawnSync(py, [join(HIER, "testseite.py"), ordner, voll.url], { encoding: "utf8", timeout: 120000 });
  assert.equal(lauf.status, 0, `Testseite nicht erzeugt:\n${lauf.stdout}\n${lauf.stderr}`);
  const browser = await (BROWSER === "firefox" ? firefox : chromium).launch();
  return {
    browser, voll: voll.url, leer: leer.url,
    async stoppen() {
      await browser.close();
      voll.server.close(); leer.server.close();
      rmSync(ordner, { recursive: true, force: true });
    },
  };
}

// Gebietskarte ohne Ratsdaten (testseite.py --gebietskarte): erfundene Flächen, gebaut mit tools/seite_bauen.py wie im
// Workflow pages.yml (ohne index.json, noindex); eigener Ordner und Server, unabhängig von starten()
export async function startenGebietskarte() {
  const ordner = mkdtempSync(join(tmpdir(), "ratsatlas-gebietskarte-"));
  const gebiete = await ausliefernNach(ordner, "gebiete");
  const py = process.env.PYTHON || "python3";
  const lauf = spawnSync(py, [join(HIER, "testseite.py"), "--gebietskarte", ordner, gebiete.url], { encoding: "utf8", timeout: 120000 });
  assert.equal(lauf.status, 0, `Gebietskarte nicht erzeugt:\n${lauf.stdout}\n${lauf.stderr}`);
  const browser = await (BROWSER === "firefox" ? firefox : chromium).launch();
  return {
    browser, gebiete: gebiete.url, ordner: join(ordner, "gebiete"),
    async stoppen() {
      await browser.close();
      gebiete.server.close();
      rmSync(ordner, { recursive: true, force: true });
    },
  };
}

async function ausliefernNach(ordner, name) {
  const server = await ausliefern(join(ordner, name));
  return { server, url: `http://127.0.0.1:${server.address().port}/` };
}

// OSM-Kacheln (graue Karte ohne eigene Kacheln, „Farbige Karte“): nur genau dieses Muster wird lokal beantwortet,
// jede andere Adresse auf tile.openstreetmap.org oder anderen Hosts bleibt gesperrt
export const OSM_KACHEL = /^https:\/\/tile\.openstreetmap\.org\/\d{1,2}\/\d+\/\d+\.png$/;
// 1×1-PNG, grau
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGN4BwAA8ADv8GkuoQAAAABJRU5ErkJggg==", "base64");

// Seite in eigenem Kontext öffnen, mit der CSP der Seite (kein bypassCSP). Gesammelt: Skriptfehler und Konsolenfehler
// (fehler), Antworten ≥ 400 (fehlend, Pfade), blockierte Anfragen an andere Hosts als 127.0.0.1 (fremd), lokal
// beantwortete OSM-Kacheln (kacheln; mit kachelnErlauben: false, auch nachträglich über s.kachelnErlauben, gesperrt wie
// jeder fremde Host), Verstöße gegen die
// Content-Security-Policy (csp) und die Zahl laufender Anfragen (offen, für pruefen()). Kein Netzzugriff auf OSM.
export async function oeffnen(browser, url, { width = 1440, height = 900, warten = true, kachelnErlauben = true } = {}) {
  const context = await browser.newContext({ viewport: { width, height } });
  const s = { context, kachelnErlauben, fremd: [], kacheln: [], fehler: [], fehlend: [], csp: [], offen: 0, zuletzt: Date.now() };
  const zaehlen = (d) => { s.offen += d; s.zuletzt = Date.now(); };
  context.on("request", () => zaehlen(1));
  context.on("requestfinished", () => zaehlen(-1));
  context.on("requestfailed", () => zaehlen(-1));
  await context.exposeBinding("__cspVerstoss", (_quelle, v) => { s.csp.push(v); s.zuletzt = Date.now(); });
  await context.addInitScript(() => document.addEventListener("securitypolicyviolation",
    (e) => window.__cspVerstoss(`${e.effectiveDirective}: ${e.blockedURI}`)));
  await context.route("**/*", (route) => {
    const u = new URL(route.request().url());
    if (u.hostname === "127.0.0.1") return route.continue();
    if (s.kachelnErlauben && OSM_KACHEL.test(u.href)) {
      s.kacheln.push(u.href);
      return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    }
    s.fremd.push(u.href);
    return route.abort("blockedbyclient");
  });
  const page = await context.newPage();
  s.page = page;
  page.on("pageerror", (e) => s.fehler.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) s.fehler.push(m.text()); });
  page.on("response", (r) => { if (r.status() >= 400) s.fehlend.push(new URL(r.url()).pathname); });
  await page.goto(url, { waitUntil: "networkidle" });
  // Karte: erst prüfen, wenn app.js gestartet ist (Gebietswahl gefüllt)
  if (warten) await page.waitForFunction(() => document.querySelector("#f-area")?.value);
  return s;
}

// Ruhe abwarten: keine laufende Anfrage und seit RUHE ms kein neues Ereignis. networkidle allein genügt nicht, es kehrt
// sofort zurück, wenn die Seite den Zustand schon einmal erreicht hatte; Anfragen kurz vor pruefen() gingen sonst verloren.
const RUHE = 500;
export async function ruhe(s, grenze = 15000) {
  const beginn = Date.now(), ende = beginn + grenze;
  while (Date.now() < ende) {
    // Ruhe zählt frühestens ab dem Aufruf: Ereignisse eben ausgelöster Anfragen treffen verzögert ein
    if (s.offen <= 0 && Date.now() - Math.max(s.zuletzt, beginn) >= RUHE) return;
    await new Promise((ok) => setTimeout(ok, 50));
  }
  assert.fail(`nach ${grenze} ms laufen noch ${s.offen} Anfragen`);
}

// keine fremden Hosts, keine CSP-Verstöße, keine Skript- oder Konsolenfehler, keine fehlenden Dateien außer den
// erwarteten (Pfadmuster). Der Kontext wird auch bei einem Fehlschlag geschlossen.
export async function pruefen(s, erwartet404 = []) {
  try {
    await s.page.waitForLoadState("networkidle");
    await ruhe(s);
    assert.deepEqual(s.fremd, [], "Anfragen an fremde Hosts");
    assert.deepEqual(s.csp, [], "Verstöße gegen die Content-Security-Policy");
    assert.deepEqual(s.fehler, [], "Fehler im Skript oder in der Konsole");
    assert.deepEqual(s.fehlend.filter((p) => !erwartet404.some((m) => m.test(p))), [], "fehlende Dateien");
  } finally {
    await s.context.close();
  }
}

// axe per page.evaluate (Protokoll des Browsers, nicht der CSP der Seite unterworfen; kein Skript-Element nötig)
export async function axe(page) {
  if (!(await page.evaluate(() => "axe" in window))) await page.evaluate(AXE);
  return page.evaluate(async () => (await window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] }))
    .violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html.slice(0, 100)).join(" | ")}`));
}

// Wortwahl: in Wuppertal „Quartier“ statt der Bonner „Ortsteil“ (Schlüssel und Pfade bleiben). Geprüft werden aller
// Text im Dokument außer Skripten und Stilen, auch versteckter (Menüs, Dialoge), dazu die Attribute, die Bildschirmleser
// oder Tooltips zeigen, und der Seitentitel.
export async function ohneOrtsteil(page) {
  const funde = await page.evaluate(() => {
    const f = [];
    const w = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (n.parentElement?.closest("script, style")) continue;
      if (/Ortsteil/.test(n.data)) f.push(`Text: ${n.data.trim().slice(0, 80)}`);
    }
    for (const e of document.querySelectorAll("*")) {
      for (const a of ["title", "aria-label", "aria-description", "aria-roledescription", "aria-valuetext", "label", "placeholder", "alt"]) {
        const v = e.getAttribute(a);
        if (v && /Ortsteil/.test(v)) f.push(`${e.tagName.toLowerCase()}[${a}]: ${v.slice(0, 80)}`);
      }
    }
    for (const m of document.querySelectorAll('meta[name="description"], meta[property^="og:"]')) {
      if (/Ortsteil/.test(m.content || "")) f.push(`meta: ${m.content.slice(0, 80)}`);
    }
    return f;
  });
  assert.deepEqual(funde, [], "„Ortsteil“ im Text oder in Attributen");
}
