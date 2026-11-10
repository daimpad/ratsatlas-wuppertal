# Checkliste Veröffentlichung (für den Auftraggeber)

Stand 10.11.2026. Zugangsdaten zu Netcup und Plesk bleiben beim Auftraggeber und gehören nicht ins Repository (CLAUDE.md 6). Plesk darf nie den Branch `main` ausliefern, sonst ist der ganze Quellcode unter der Domain abrufbar.

Veröffentlicht wird zunächst die Anwendung **ohne Daten**: Die Seite zeigt „Daten nicht verfügbar“ und trägt `noindex`, bis nach den Messungen Daten vorliegen. `.github/workflows/pages.yml` ruft nichts ab und läuft bei jedem Push auf `main` und auf Knopfdruck, und zwar nur für `main` (auf anderen Branches gestartet, bleibt jeder Job aus).

## A. GitHub (einmalig)

1. **GitHub Pages** – Repository → Settings → Pages → Source: „GitHub Actions“.
2. **Variable** (optional, ist Vorgabe) – Settings → Secrets and variables → Actions → Variables: `SITE_URL` = `https://wuppertal.ratsatlas.de/`. Abrufvariablen sind nicht nötig.
3. **Benachrichtigung** – Profil → Settings → Notifications → Actions: „Notify on failed workflows“.
4. **Erster Lauf** – Actions → „Seite veröffentlichen“ → „Run workflow“. Danach gibt es den Branch `deploy` (nur die fertige Seite mit `.htaccess`). Ist Pages noch nicht eingerichtet, scheitert nur der Job `pages`; der Branch `deploy` entsteht trotzdem.

## B. Netcup / Plesk

1. **Domain** – Subdomain `wuppertal.ratsatlas.de` anlegen; DNS (A/AAAA) auf das Webhosting zeigen lassen.
2. **TLS** – SSL/TLS-Zertifikate → Let's Encrypt für `wuppertal.ratsatlas.de`; „HTTP auf HTTPS umleiten“ einschalten.
3. **Git** – Websites & Domains → Git → Repository hinzufügen:
   - Remote-Repository: `https://github.com/daimpad/ratsatlas-wuppertal.git`, Branch `deploy`
   - Bereitstellungsmodus: automatisch; Zielverzeichnis: Dokumentstamm (`httpdocs`)
   - keine zusätzlichen Bereitstellungsaktionen (die Seite ist fertig gebaut)
4. **Webhook** – die von Plesk angezeigte Webhook-Adresse in GitHub eintragen: Repository → Settings → Webhooks → Add webhook, Content type `application/json`, Ereignis „Just the push event“.
5. **Apache und `.htaccess`** – Der Branch enthält `.htaccess` (Komprimierung, Zwischenspeicher, Sicherheitskopfzeilen, CORS für Feeds und JSON; ohne Daten zusätzlich `X-Robots-Tag: noindex`). nginx liefert statische Dateien sonst an Apache vorbei aus, ohne diese Kopfzeilen. Deshalb unter „Apache & nginx-Einstellungen“ die „Intelligente Verarbeitung statischer Dateien“ ausschalten (in Bonn so erprobt; zusätzliche nginx-Anweisungen bietet das Netcup-Paket dort nicht).
6. **Hinweis** – `deploy` wird bei jeder Änderung der Seite ohne Historie neu geschrieben (ein Commit, Force-Push). Plesk muss den Branch dann neu holen; Prüfung in C.6.

## C. Nach der ersten Veröffentlichung

1. Die Startseite zeigt „Daten nicht verfügbar“.
2. Der Quelltext enthält `<meta name="robots" content="noindex">` und `<link rel="canonical" href="https://wuppertal.ratsatlas.de/">`.
3. `curl -sI https://wuppertal.ratsatlas.de/` zeigt `X-Robots-Tag: noindex`, `X-Content-Type-Options: nosniff` und `Strict-Transport-Security`.
4. `/CLAUDE.md`, `/pipeline/` und `/.git/` liefern 404.
5. Die Ausweichadresse https://daimpad.github.io/ratsatlas-wuppertal/ zeigt dieselbe Seite mit Canonical auf die Hauptadresse. Ihre 404-Seite verweist bewusst auf die Hauptadresse (Favicon, Startseite, Datenschutz); vor B ins Leere.
6. Nach einem zweiten Lauf mit geänderter Seite zeigt Plesk unter Git den neuen Commit. Übernimmt Plesk den Force-Push nicht (Fehlermeldung, alter Stand), bitte „Pull Updates“ versuchen und Bescheid geben; das Verfahren wird dann gemeinsam geändert.
7. Datenschutzerklärung und Impressum für die Hauptadresse prüfen (`site/datenschutz.html`). **Offen, zu entscheiden:** Eigene graue Kartenkacheln gibt es noch nicht; die Karte lädt deshalb auch in Grau von tile.openstreetmap.org (IP-Adresse geht an die OpenStreetMap Foundation; so in der Datenschutzerklärung beschrieben). Möglich: eigene Kacheln nach Kölner Vorbild, Karte ohne Hintergrund oder so lassen.
