# Doku-Hosting: Cloudflare Pages mit Forgejo-Anmeldung

Die Doku-Seite baut der Forgejo-Runner auf dem Pi (`.github/workflows/docs.yml`)
und veröffentlicht sie unter **https://picam-docs.pages.dev**. Ein Offline-ZIP
wird nicht mehr erzeugt. Lesen darf die Seite nur, wer sich über
Forgejo anmeldet **und das Repo `l.hentschke/picam-ai` lesen darf**.

Ein Push auf `master` baut und veröffentlicht die Seite automatisch. Ein
manuell gestarteter Lauf darf Build, Tests und den Prüfstand ausführen, aber
nie das produktive Deployment überschreiben; ebenso wenig ein Feature-Branch.

```mermaid
flowchart LR
    P[Push] --> R[Runner auf dem Pi<br>baut site/]
    R --> T[Tests des Schutzes] --> V[Deploy Prüfstand<br>verify] --> C1{ohne Login<br>überall 302?}
    C1 -- nein --> X[Deployment löschen,<br>Abbruch]
    C1 -- ja --> D[Deploy Produktion] --> C2{ohne Login<br>überall 302?}
    L[Leser] --> F[Pages Function] -- Login + Repo-Leserecht in Forgejo --> S[Doku-Seite]
```

## Wie der Schutz funktioniert

`cloudflare/functions/_middleware.js` ist eine **Pages Function**. Sie steckt
in jedem Deployment und läuft vor **jeder** Anfrage, auch vor statischen
Dateien und dem Suchindex.

1. Ohne gültige Sitzung leitet sie zur Forgejo-Anmeldung weiter
   (OAuth2 mit PKCE und signiertem `state`).
2. Nach der Rückkehr tauscht sie den Code gegen einen Token und fragt damit
   `GET /api/v1/repos/l.hentschke/picam-ai` ab. Nur bei `permissions.pull == true`
   gibt es eine Sitzung. Den Token verwirft sie danach.
3. Die Sitzung ist ein HMAC-signiertes Cookie (`__Host-`, `Secure`, `HttpOnly`)
   mit 8 h Laufzeit. Wem in Forgejo das Leserecht entzogen wird, verliert den
   Zugang also spätestens nach 8 h.
4. Im Zweifel lehnt sie ab: Fehlt Konfiguration, kommt 500; ist Forgejo nicht
   erreichbar, kommt 502; ist das Cookie ungültig, geht es zurück zur Anmeldung.

Tests: `node --test cloudflare/test/middleware.test.js`. Sie decken ab:

* Ablehnung ohne, mit abgelaufener, manipulierter und fremd signierter Sitzung
* fehlende und schwache Konfiguration
* falschen `state` und fehlendes Leserecht
* offene Weiterleitungen
* den erfolgreichen Durchlauf

Warum kein Cloudflare Access: Zero Trust verlangt eine hinterlegte Kreditkarte,
auch im kostenlosen Plan. Die Pages Function ist im kostenlosen
Workers-Kontingent enthalten (100 000 Anfragen pro Tag) und prüft sogar genauer,
nämlich die Repo-Rechte statt einer E-Mail-Regel. Die abgewogenen Alternativen
stehen in [project_history.md](project_history.md), Eintrag vom 2026-09-23.

## Was eingerichtet ist (2026-09-23)

| Wo | Was |
| --- | --- |
| Cloudflare, Pages-Projekt `picam-docs` | Production branch `master`. Variablen: `OAUTH_CLIENT_ID`; als Secret: `OAUTH_CLIENT_SECRET`, `SESSION_SECRET` |
| Cloudflare, API-Token „picam-docs deploy“ | nur *Pages Write* für dieses Konto, läuft am 2027-09-23 ab |
| Forgejo, OAuth2-Anwendung „Doku-Seite picam-docs“ | vertraulicher Client, Weiterleitung nur `https://picam-docs.pages.dev/_auth/callback` |
| Forgejo, Repo → Einstellungen → Actions | Secret `CLOUDFLARE_API_TOKEN` (Deploy-Token), Variablen `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_PAGES_PROJECT` |

Vorschau-Adressen (`verify.picam-docs.pages.dev`, `<hash>.picam-docs.pages.dev`)
sind ebenfalls geschützt. Anmelden kann man sich dort aber nicht, denn in
Forgejo ist nur die Produktivadresse als Weiterleitung eingetragen. Der
Prüfstand dient nur der automatischen Schutzprüfung.

## Wartung

### Automatische Zensical-Pflege einrichten

Der bisherige Claude-`@reboot`-Eintrag ist deaktiviert. Forgejo startet
`.github/workflows/docs-maintenance.yml` täglich um 06:00 Uhr Berliner Zeit;
ist der Pi aus, wartet der Lauf auf das Runner-Label `picam-codex-docs`.
Manuell gestartete Läufe erzeugen standardmäßig nur einen geprüften Patch als
Action-Artefakt. Mit `mode=publish` dürfen sie nach erfolgreichen Prüfungen
direkt nach `master` pushen. Der bestehende `docs.yml`-Workflow übernimmt
anschließend den Cloudflare-Deploy und dessen Schutzprüfung.

Einmalige Einrichtung auf dem Pi:

1. In Forgejo unter **Repo → Einstellungen → Actions → Runners** einen neuen,
   nur für dieses Repo registrierten Runner anlegen. UUID und Token erhalten
   einen eigenen Eintrag; den Token ausschließlich in einer lokalen Datei mit
   Modus `0600` ablegen, nie in Kommandozeile, Repo oder Chat.
2. `sudo ./scripts/forgejo-codex-runner-install.sh --uuid <UUID> --token-file <DATEI>`
   ausführen. Das Skript installiert die gepinnte Codex CLI, den Systemnutzer
   `picam-codex-runner` und den ressourcenbegrenzten Dienst. Der vorhandene
   `picam-docs`-Runner bleibt für den Cloudflare-Build zuständig.
3. Unter dem neuen Systemnutzer einmalig anmelden:
   ```bash
   sudo -u picam-codex-runner env HOME=/var/lib/picam-codex-runner \
     CODEX_HOME=/var/lib/picam-codex-runner/.codex \
     /opt/picam-codex/node_modules/.bin/codex \
     -c 'cli_auth_credentials_store="file"' login --device-auth
   ```
   Den Gerätecode im eigenen Browser bestätigen. Danach muss
   `auth.json` nur für diesen Benutzer lesbar sein (`0600`); die Datei
   bleibt zwischen Läufen bestehen und wird nie ins Repo kopiert.
4. Einen Forgejo-Bot mit Schreibrecht **nur auf dieses Repo** anlegen und
   dessen PAT als Repo-Secret `DOCS_BOT_TOKEN` hinterlegen. Den Bot-Namen als
   Repo-Variable `DOCS_BOT_USERNAME` setzen. Falls `master` geschützt ist,
   braucht dieser Bot die ausdrücklich erlaubte Push-Berechtigung. Der
   automatische `FORGEJO_TOKEN` kann den Publish-Schritt nicht ersetzen:
   seine Pushes lösen keine weiteren Actions aus.
5. Einen manuellen Lauf mit `mode=preview` starten und den Patch prüfen.
   Danach einen kleinen `mode=publish`-Lauf abnehmen: Bot-Commit, neuer
   `docs.yml`-Lauf, geschütztes Cloudflare-Deployment und Hover-Vorschau.

Der Job nutzt einen frischen Checkout und berührt keine lokalen Worktrees.
Er prüft anfangs täglich drei Anleitungsseiten, bis die erste Runde fertig
ist. Danach ruft er Codex nur bei Änderungen seit dem letzten erfolgreichen
Audit oder für eine wöchentlich wechselnde Anleitungsseite auf. Das Modell
ist standardmäßig `gpt-6-luna`; höchstens zwei lesende Subagents helfen bei unabhängigen
Bereichen. Der Codex-Lauf ist auf 20 Minuten und der Workflow auf 45 Minuten
begrenzt. ChatGPT-Anmeldung hat keine technisch durchsetzbare
10-USD-API-Kostengrenze; die Forgejo-Logs enthalten nur Status und
Token-Nutzung, keine Anmelde- oder Bot-Tokens. Bei Problemen bleiben die privaten Codex-JSONL-Logs
auf dem Runner unter `CODEX_HOME`; bei fehlgeschlagenem Gate gibt es keinen
Push.

* **Aktualisierung:** Änderungen nach `master` pushen. Erst nach erfolgreichem
  OQ-Index-Check, Build, Auth-Test, Prüfstand-Deploy und Schutzprüfung wird Produktion
  aktualisiert.
* **OQ-Übersicht:** Nach Änderungen an OQ-Titel oder Status sowie an aktiven
  Aufgaben/OQ-Verweisen in `TODO.md` mit
  `./.venv/bin/python scripts/oq-index.py` neu erzeugen und die Änderung an
  `docs/open-questions.md` mitcommitten. Den generierten Block und die
  `#oq-nn`-Anker nicht direkt bearbeiten. „Jetzt“ kommt aus den unerledigten
  TODO-Aufgaben; es ist kein eigener OQ-Status.
* **Roadmap:** Phasenstand und Exit-Kriterien in `docs/ROADMAP.md` pflegen.
  Die aufklappbare Ansicht erwartet derzeit die erste Tabelle mit P0–P8,
  den Spalten `Phase`, `Ziel`, `Kamera?`, `GSVmulti-Spec?`,
  `Hartes Exit-Kriterium`, `Stand` in dieser Reihenfolge und den Statuswörtern
  `erreicht`, `teilweise`, `blockiert` oder `offen`. Wenn Phasen oder Spalten
  dazukommen oder Statuswörter wechseln,
  `docs-site/assets/docs-interactive.js` und `tests/docs-site.spec.ts`
  gemeinsam anpassen.
* **Begriffsvorschauen:** `zensical.toml` aktiviert Vorschauen gezielt für
  `docs/anleitung/glossar.md` und `docs/TIMING.md`. Links auf diese Seiten
  zeigen deren kurze Einleitung; Links mit `#`-Anker zeigen den jeweiligen
  Überschriftenabschnitt. Deshalb auch die Seiteneinleitungen knapp halten. Die
  expliziten Glossar-IDs (`#value-record` usw.) beim Umbenennen beibehalten
  oder alle Verweise darauf aktualisieren. Der Abschnitt bis zur nächsten
  Überschrift soll als kurzer Erklärungstext lesbar bleiben. Bei weiteren
  Vorschau-Zielen erst einen kurzen Zielabschnitt schaffen, dann den Pfad in
  `zensical.toml` aufnehmen und einen Browsertest ergänzen.
* **API- und Code-Erklärungen:** Generierte API-Klassen sind für eine
  Inhaltsvorschau zu umfangreich. Bei ausgewählten API-Verweisen einen kurzen
  Markdown-Linktitel ergänzen. Erklärungen zu einzelnen Codezeilen nutzen
  `# (1)!` und die zugehörige nummerierte Erläuterung nach dem Codeblock.
  Links und Erklärungen beim Ändern der Signatur gegen den Quellcode prüfen.
* **Vor dem Merge prüfen:** `./scripts/docs-site.sh build -s` und
  `npx playwright test -c playwright.docs.config.ts`. Der Build stoppt bei
  einem veralteten OQ-Index; die Browserprüfung meldet eine nicht mehr
  funktionierende interaktive Ansicht. Der Forgejo-Playwright-Workflow führt
  beides auch für Pull Requests nach `master` aus.
* **Lokale Vorschau:** `./scripts/docs-site.sh serve`; für einen Build
  `./scripts/docs-site.sh build`. Beides prüft zuerst die OQ-Übersicht gegen
  `TODO.md` und `docs/open-questions.md`.
* **Deploy-Token erneuern** (jährlich): neuen Token mit nur *Pages Write*
  anlegen und das Forgejo-Secret `CLOUDFLARE_API_TOKEN` ersetzen.
* **Alle Sitzungen beenden:** `SESSION_SECRET` im Pages-Projekt durch einen
  neuen Zufallswert (≥ 32 Zeichen) ersetzen und neu deployen.
* **Client-Secret erneuern:** in Forgejo bei der OAuth2-Anwendung neu erzeugen,
  dann `OAUTH_CLIENT_SECRET` im Pages-Projekt setzen und neu deployen.
* **Schutz von Hand prüfen:**
  `./scripts/check-auth-protected.sh https://picam-docs.pages.dev`
* **Abschalten:** die Variable `CLOUDFLARE_PAGES_PROJECT` in Forgejo löschen,
  dann gibt es keine Uploads mehr. Um alles zu entfernen, das Pages-Projekt löschen.

## Grenzen

* **Die Doku liegt bei Cloudflare**, einschließlich Laborjournal und Quelltext
  in der API-Referenz. Der Schutz hält Fremde fern, nicht den Anbieter.
* **Eigener Anmelde-Code:** Die Function ist kein geprüftes Fertigprodukt.
  Änderungen an ihr nur mit Tests, und nach jedem Deploy muss die
  Schutzprüfung grün sein.
* **Wer eingeloggt ist, sieht alles.** Es gibt keine Abstufung innerhalb der Doku.
