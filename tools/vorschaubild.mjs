// Vorschaubild für geteilte Links (og:image, twitter:image): site/vorschaubild.jpg, 1200 × 630 Pixel, höchstens 300 KB.
//
// Aufruf (einmalig, nicht wiederholt laufen lassen; hinter einem Proxy mit NODE_USE_ENV_PROXY=1):
//   node tools/vorschaubild.mjs            Kacheln von tile.openstreetmap.org, schreibt site/vorschaubild.jpg
//   node tools/vorschaubild.mjs --probe    ohne Netz: Kacheln als graue Fläche, Bild nach $VORSCHAUBILD_PROBE
//                                          (Vorgabe: Temp-Ordner), nicht ins Repository
//
// Ablauf: Seite mit tools/seite_bauen.py in einen Temp-Ordner bauen, auf 127.0.0.1 ausliefern, in Chromium (Playwright)
// mit 1200 × 630 Pixeln und deviceScaleFactor 1 öffnen. Gezeigt wird die Standardansicht der Seite: graue Karte
// (OSM-Kacheln mit dem Filter der Klasse map-gray, site/style.css und site/app.js), Ausschnitt ganz Wuppertal aus
// STADT_MITTE und STADT_ZOOM in site/app.js. Dieser Ausschnitt ist vorläufig bis Messstufe G (Flächen der
// Stadtbezirke); danach kann das Bild mit diesem Skript neu erzeugt werden. Bedienelemente werden ausgeblendet; darüber
// liegen der Schriftzug „Ratsatlas Wuppertal“, als Unterzeile der Rest des Seitentitels aus site/index.html, und die
// Namensnennung „© OpenStreetMap-Mitwirkende“ (Kontrast im Skript geprüft: Text 4,5:1, Schriftzug als große Schrift 3:1,
// jeweils im ungünstigsten Fall Fläche über Schwarz). Gestaltung mit den Tokens aus site/style.css und der lokalen
// Schrift Inter. Lauf am 10.11.2026: 18 Kachelanfragen, 197 619 Bytes, JPEG-Qualität 85.
//
// Netz: Nur Kacheln nach dem Muster OSM_KACHEL auf tile.openstreetmap.org werden abgerufen, höchstens GRENZE Stück je
// Lauf; jede andere fremde Adresse bricht der Browser ab (insbesondere Server der Stadt Wuppertal). Die Kacheln holt
// Node (fetch, ohne Weiterleitungen) mit einem User-Agent, der das Projekt und den Kontakt nennt, und dem Referer der
// Hauptadresse, wie es die Nutzungsbedingungen der OSM-Kacheln verlangen. Keine Geodaten der Stadt im Bild.
// Lizenz des Bildes: Daten © OpenStreetMap-Mitwirkende, ODbL 1.0; für die Kartendarstellung nennt
// openstreetmap.org/copyright keine Lizenz (geprüft 10.11.2026, offen), Kacheln nach der Tile Usage Policy der OSMF.
// Vermerk in NOTICE und data/LICENSE-DATA.md.
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, statSync, createReadStream, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join, extname, resolve, sep, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ZIEL = join(ROOT, "site", "vorschaubild.jpg");
export const BREITE = 1200, HOEHE = 630, MAX_BYTES = 300 * 1024;
export const HAUPTADRESSE = "https://wuppertal.ratsatlas.de/";
// einzige fremde Adresse, die das Skript abruft (tests/test_vorschaubild.py prüft die Hostliste)
export const ERLAUBTE_HOSTS = ["tile.openstreetmap.org"];
export const OSM_KACHEL = /^https:\/\/tile\.openstreetmap\.org\/\d{1,2}\/\d+\/\d+\.png$/;
export const GRENZE = 40;
const USER_AGENT = "ratsatlas-wuppertal-vorschaubild/1.0 (+https://wuppertal.ratsatlas.de/; contact@nozilla.de)";
const TYPEN = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
  ".ico": "image/x-icon", ".woff2": "font/woff2", ".webmanifest": "application/manifest+json",
  ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8", ".xml": "application/xml",
};
// graue Ersatzkachel für --probe (1 × 1 Pixel)
const GRAU = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGN4BwAA8ADv8GkuoQAAAABJRU5ErkJggg==", "base64");

function playwright() {
  const require = createRequire(import.meta.url);
  try { return require(join(ROOT, "tests", "browser", "node_modules", "playwright")); } catch { return require("playwright"); }
}

// statischer Server nur auf 127.0.0.1 (wie tests/browser/hilfe.mjs)
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

// Breite und Höhe aus dem Kopf einer JPEG-Datei (SOF-Marker), wie tests/test_vorschaubild.py
export function jpegMasse(buf) {
  if (buf[0] !== 0xff || buf[1] !== 0xd8) throw new Error("keine JPEG-Datei");
  let i = 2;
  while (i + 9 < buf.length) {
    if (buf[i] !== 0xff) throw new Error("JPEG-Kopf unlesbar");
    const m = buf[i + 1], len = buf.readUInt16BE(i + 2);
    if (m >= 0xc0 && m <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(m)) {
      return { hoehe: buf.readUInt16BE(i + 5), breite: buf.readUInt16BE(i + 7) };
    }
    i += 2 + len;
  }
  throw new Error("JPEG ohne SOF-Marker");
}

async function main() {
  const probe = process.argv.includes("--probe");
  const ordner = mkdtempSync(join(tmpdir(), "ratsatlas-vorschaubild-"));
  const site = join(ordner, "site");
  const bau = spawnSync(process.env.PYTHON || "python3", [join(ROOT, "tools", "seite_bauen.py"), site],
    { encoding: "utf8", timeout: 120000, env: { ...process.env, SITE_URL: HAUPTADRESSE } });
  if (bau.status !== 0) throw new Error(`Seite nicht gebaut:\n${bau.stdout}\n${bau.stderr}`);
  const server = await ausliefern(site);
  const url = `http://127.0.0.1:${server.address().port}/`;
  const browser = await playwright().chromium.launch();
  const kacheln = [], fremd = [];
  try {
    const context = await browser.newContext({ viewport: { width: BREITE, height: HOEHE }, deviceScaleFactor: 1,
      locale: "de-DE", reducedMotion: "reduce" });
    await context.route("**/*", async (route) => {
      const u = new URL(route.request().url());
      if (u.hostname === "127.0.0.1") return route.continue();
      if (OSM_KACHEL.test(u.href) && ERLAUBTE_HOSTS.includes(u.hostname) && kacheln.length < GRENZE) {
        kacheln.push(u.href);
        if (probe) return route.fulfill({ status: 200, contentType: "image/png", body: GRAU });
        try {
          // redirect "error": keiner Weiterleitung folgen, auch nicht auf andere Hosts (der Browser-Router sähe sie nicht)
          const r = await fetch(u.href, { redirect: "error",
            headers: { "User-Agent": USER_AGENT, Referer: HAUPTADRESSE, Accept: "image/png" } });
          return route.fulfill({ status: r.status, contentType: r.headers.get("content-type") || "image/png",
            body: Buffer.from(await r.arrayBuffer()) });
        } catch (e) {
          fremd.push(`${u.href} (Fehler: ${e.cause?.code || e.message})`);
          return route.abort("failed");
        }
      }
      fremd.push(u.href);
      return route.abort("blockedbyclient");
    });
    const page = await context.newPage();
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForFunction(() => document.querySelector("#f-area")?.value);
    // Standardansicht: graue Karte (Klasse map-gray), alle Kacheln geladen
    await page.waitForFunction(() => {
      const m = document.getElementById("map"), t = [...m.querySelectorAll("img.leaflet-tile")];
      return m.classList.contains("map-gray") && t.length > 0 && t.every((i) => i.complete && i.naturalWidth > 0);
    }, null, { timeout: 60000 });
    const titel = await page.title();
    if (!titel.startsWith("Ratsatlas Wuppertal – ")) throw new Error(`unerwarteter Seitentitel: ${titel}`);
    const unterzeile = titel.slice("Ratsatlas Wuppertal – ".length);
    // Bedienelemente ausblenden: alles außer der Karte und ihren Kacheln; darüber Schriftzug und Namensnennung
    await page.addStyleTag({ content: `
      body > *:not(main, .vb-karte, .vb-osm), main > *:not(#map), #map > .leaflet-control-container,
      #map .leaflet-overlay-pane, #map .leaflet-marker-pane, #map .leaflet-shadow-pane, #map .leaflet-tooltip-pane,
      #map .leaflet-popup-pane { display: none !important; }
      .vb-karte { position: fixed; left: 40px; top: 40px; z-index: 2000; padding: 30px 36px 28px;
        background: var(--surface-strong); border: 1px solid var(--border-alt);
        border-radius: var(--radius); box-shadow: var(--shadow-lift); -webkit-backdrop-filter: var(--blur);
        backdrop-filter: var(--blur); font-family: var(--font-body); color: var(--text); overflow: hidden; }
      .vb-karte::before { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 6px; background: var(--cta); }
      .vb-marke { display: flex; align-items: center; gap: 18px; font: 700 58px/1.05 var(--font-display);
        letter-spacing: -0.03em; white-space: nowrap; color: var(--accent-fill); }
      .vb-marke img { width: 60px; height: 60px; flex: none; }
      .vb-marke span { color: var(--text); font-weight: 600; }
      .vb-unter { margin: 14px 0 0; font: 500 26px/1.3 var(--font-body); color: var(--text); }
      .vb-osm { position: fixed; right: 16px; bottom: 14px; z-index: 2000; padding: 6px 12px; background: var(--bg);
        border-radius: var(--radius-s); font: 500 17px/1.2 var(--font-body); color: var(--text); }` });
    await page.evaluate((unterzeile) => {
      const karte = document.createElement("div");
      karte.className = "vb-karte";
      karte.innerHTML = '<div class="vb-marke"><img src="favicon.svg?v=2" alt=""><div>Ratsatlas <span>Wuppertal</span></div></div><p class="vb-unter"></p>';
      karte.querySelector(".vb-unter").textContent = unterzeile;
      const osm = document.createElement("div");
      osm.className = "vb-osm";
      osm.textContent = "© OpenStreetMap-Mitwirkende";
      document.body.append(karte, osm);
    }, unterzeile);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => document.querySelector(".vb-marke img").complete);
    // Kontrast: Namensnennung auf deckender Fläche; Schriftzug auf der Karte im ungünstigsten Fall (Glas über Schwarz)
    const kontrast = await page.evaluate(() => {
      const rgba = (s) => s.match(/[\d.]+/g).map(Number);
      const lum = ([r, g, b]) => [r, g, b].map((c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; })
        .reduce((s, c, i) => s + c * [0.2126, 0.7152, 0.0722][i], 0);
      const ueber = (v, h) => { const a = v[3] ?? 1; return [0, 1, 2].map((i) => v[i] * a + h[i] * (1 - a)); };
      const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
      const osm = getComputedStyle(document.querySelector(".vb-osm"));
      const karte = getComputedStyle(document.querySelector(".vb-karte"));
      const flaeche = ueber(rgba(karte.backgroundColor), [0, 0, 0]);
      return {
        osm: ratio(ueber(rgba(osm.color), ueber(rgba(osm.backgroundColor), [0, 0, 0])), ueber(rgba(osm.backgroundColor), [0, 0, 0])),
        unterzeile: ratio(rgba(getComputedStyle(document.querySelector(".vb-unter")).color), flaeche),
        marke: ratio(rgba(getComputedStyle(document.querySelector(".vb-marke")).color), flaeche),
      };
    });
    // Schriftzug 58 px fett: große Schrift, WCAG 1.4.3 verlangt 3:1; sonst 4,5:1
    const MINDEST = { osm: 4.5, unterzeile: 4.5, marke: 3 };
    for (const [wo, k] of Object.entries(kontrast)) {
      if (k < MINDEST[wo]) throw new Error(`Kontrast ${wo} ${k.toFixed(2)}:1 < ${MINDEST[wo]}:1`);
    }
    if (fremd.length) throw new Error(`fremde Adressen abgebrochen: ${fremd.join(", ")}`);
    let bild, qualitaet = 85;
    for (; qualitaet >= 60; qualitaet -= 5) {
      bild = await page.screenshot({ type: "jpeg", quality: qualitaet });
      if (bild.length <= MAX_BYTES) break;
    }
    const masse = jpegMasse(bild);
    if (masse.breite !== BREITE || masse.hoehe !== HOEHE) throw new Error(`Maße ${masse.breite}×${masse.hoehe}`);
    if (bild.length > MAX_BYTES) throw new Error(`Bild zu groß: ${bild.length} Bytes`);
    // Probe außerhalb des Repositorys (Vorgabe: Temp-Ordner des Systems)
    const ziel = probe ? (process.env.VORSCHAUBILD_PROBE || join(tmpdir(), "vorschaubild-probe.jpg")) : ZIEL;
    writeFileSync(ziel, bild);
    console.log(`${probe ? "Probe" : "Bild"} → ${ziel}: ${bild.length} Bytes, `
      + `JPEG-Qualität ${qualitaet}, Kachelanfragen ${kacheln.length} (Grenze ${GRENZE}), Kontrast `
      + Object.entries(kontrast).map(([w, k]) => `${w} ${k.toFixed(1)}:1`).join(", "));
  } finally {
    await browser.close();
    server.close();
    rmSync(ordner, { recursive: true, force: true });
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(String(e.stack || e)); process.exit(1); });
}
