// Selbsttest der Sperre in hilfe.mjs: Anfragen an andere Hosts als 127.0.0.1 und Verstöße gegen die CSP lassen
// pruefen() fehlschlagen, auch wenn sie unmittelbar vor pruefen() starten (kein Warten dazwischen). Ziele unter .invalid
// (RFC 2606, nie auflösbar) und localhost:1; die Anfragen werden im Browser abgefangen und erreichen kein Netz.
// Ausnahme nur OSM-Kacheln im Muster https://tile.openstreetmap.org/{z}/{x}/{y}.png (hilfe.mjs, lokal beantwortet);
// mit kachelnErlauben: false sind auch sie gesperrt.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen, ruhe } from "./hilfe.mjs";

let t;
before(async () => { t = await starten(); });
after(async () => { await t?.stoppen(); });

// Element bzw. Abruf einfügen und ohne zu warten zurückkehren
const SPAET = {
  img: () => { const e = document.createElement("img"); e.src = "http://fremd.invalid/bild.png"; document.body.append(e); },
  script: () => { const e = document.createElement("script"); e.src = "http://fremd.invalid/skript.js"; document.head.append(e); },
  stylesheet: () => {
    const e = document.createElement("link"); e.rel = "stylesheet"; e.href = "http://fremd.invalid/stil.css"; document.head.append(e);
  },
  fetch: () => { fetch("http://fremd.invalid/daten.json").catch(() => {}); },
  // localhost erlaubt die CSP der Karte (connect-src), die Sperre nicht
  localhost: () => { fetch("http://localhost:1/daten.json").catch(() => {}); },
  // Kachel wie bei „Farbige Karte“: die CSP der Karte erlaubt den Host (img-src), die Sperre bricht vor dem Netz ab.
  // Die Karte lädt ihre Kacheln wie sonst; danach wird die lokale Antwort abgeschaltet (OHNE_KACHELN), sonst beantwortet
  // hilfe.mjs dieses Muster lokal. Gezählt wird dann genau diese eine Anfrage.
  kachel: () => { const e = document.createElement("img"); e.src = "https://tile.openstreetmap.org/0/0/0.png"; document.body.append(e); },
  // Host der OSM-Kacheln, aber kein Kachelmuster: bleibt auch mit lokal beantworteten Kacheln gesperrt
  osmAndere: () => { const e = document.createElement("img"); e.src = "https://tile.openstreetmap.org/robots.png"; document.body.append(e); },
  // Kachelmuster auf anderem OSM-Host: gesperrt
  osmHost: () => { const e = document.createElement("img"); e.src = "https://a.tile.openstreetmap.org/0/0/0.png"; document.body.append(e); },
};
// welcher Mechanismus greift auf der Karte: CSP der Seite oder die Sperre in hilfe.mjs
const ERWARTET = { img: "csp", script: "csp", stylesheet: "csp", fetch: "csp", localhost: "fremd", kachel: "fremd", osmAndere: "fremd", osmHost: "csp" };
const OHNE_KACHELN = new Set(["kachel"]);

for (const [art, ausloesen] of Object.entries(SPAET)) {
  test(`Karte: ${art} auf fremdem Host unmittelbar vor pruefen() → Fehlschlag`, async () => {
    const s = await oeffnen(t.browser, t.voll);
    if (OHNE_KACHELN.has(art)) { await ruhe(s); s.kachelnErlauben = false; }
    await s.page.evaluate(ausloesen);
    await assert.rejects(pruefen(s), assert.AssertionError);
    assert.equal(s[ERWARTET[art]].length, 1, `${art}: fremd ${JSON.stringify(s.fremd)}, csp ${JSON.stringify(s.csp)}`);
  });
}

// ohne CSP (leere Seite): die Sperre allein fängt die Anfragen ab
for (const art of ["img", "script", "fetch"]) {
  test(`Seite ohne CSP: ${art} auf fremdem Host unmittelbar vor pruefen() → gesperrt und Fehlschlag`, async () => {
    const s = await oeffnen(t.browser, "about:blank", { warten: false });
    await s.page.evaluate(SPAET[art]);
    await assert.rejects(pruefen(s), assert.AssertionError);
    assert.deepEqual(s.fremd.map((u) => new URL(u).hostname), ["fremd.invalid"]);
  });
}

test("OSM-Kacheln: Kachelmuster wird lokal beantwortet und gezählt, nicht als fremd", async () => {
  const s = await oeffnen(t.browser, "about:blank", { warten: false });
  const ok = await s.page.evaluate(() => new Promise((fertig) => {
    const e = document.createElement("img");
    e.onload = () => fertig(e.naturalWidth === 1); e.onerror = () => fertig(false);
    e.src = "https://tile.openstreetmap.org/0/0/0.png"; document.body.append(e);
  }));
  assert.equal(ok, true, "Kachel nicht geladen");
  assert.deepEqual(s.kacheln, ["https://tile.openstreetmap.org/0/0/0.png"]);
  await pruefen(s);
});

test("Gegenprobe: ohne fremde Anfrage besteht pruefen()", async () => {
  const s = await oeffnen(t.browser, t.voll);
  await pruefen(s);
});
