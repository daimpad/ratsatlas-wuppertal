// Selbsttest der Sperre in hilfe.mjs: Anfragen an andere Hosts als 127.0.0.1 und Verstöße gegen die CSP lassen
// pruefen() fehlschlagen, auch wenn sie unmittelbar vor pruefen() starten (kein Warten dazwischen). Ziele unter .invalid
// (RFC 2606, nie auflösbar) und localhost:1; die Anfragen werden im Browser abgefangen und erreichen kein Netz.
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { starten, oeffnen, pruefen } from "./hilfe.mjs";

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
  // Kachel wie bei „Farbige Karte“: die CSP der Karte erlaubt den Host (img-src), die Sperre bricht vor dem Netz ab
  kachel: () => { const e = document.createElement("img"); e.src = "https://tile.openstreetmap.org/0/0/0.png"; document.body.append(e); },
};
// welcher Mechanismus greift auf der Karte: CSP der Seite oder die Sperre in hilfe.mjs
const ERWARTET = { img: "csp", script: "csp", stylesheet: "csp", fetch: "csp", localhost: "fremd", kachel: "fremd" };

for (const [art, ausloesen] of Object.entries(SPAET)) {
  test(`Karte: ${art} auf fremdem Host unmittelbar vor pruefen() → Fehlschlag`, async () => {
    const s = await oeffnen(t.browser, t.voll);
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

test("Gegenprobe: ohne fremde Anfrage besteht pruefen()", async () => {
  const s = await oeffnen(t.browser, t.voll);
  await pruefen(s);
});
