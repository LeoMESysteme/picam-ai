# Wiki-Gerüst Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Zensical-Wiki führt Einsteiger, Konfigurierende und Entwickler über Startseite, Seitenkopf und Schichten zu ihrem Weg, mit Hover-Infos, Statuschips, interaktiver Kette, Diagrammen aus Tabellen und einem Glossar als globalem Begriffsindex.

**Architecture:** Markdown bleibt Quelle und bleibt auf Forgejo lesbar; alle Bausteine sind progressive Erweiterungen über `<details>`/`<div markdown="1">`-Hüllen, Front Matter und ein einziges Template-Override. Laufzeitdaten kommen aus vorhandenen Artefakten (`search.json`, OQ-Tabelle, Roadmap-Tabelle, Glossarseite) bzw. einer kleinen versionierten `kette.json`; `scripts/wiki-check.py` prüft Formate vor jedem Build.

**Tech Stack:** Zensical 0.0.64 (Minijinja-Templates, `custom_dir`), Vanilla-JS ohne Build-Schritt, Anime.js 4.5.0 lokal, Python 3 für Prüfskript, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-23-wiki-geruest-design.md`, dazu `PRODUCT.md`.

## Global Constraints

- Sprache aller sichtbaren Texte: Deutsch.
- Zensical-Theme, Schrift, Farben, hell/dunkel bleiben; Erweiterungen nutzen `--md-*`-Variablen.
- `nav` in `zensical.toml` und alle Seiten-URLs bleiben unverändert.
- Markdown bleibt auf Forgejo lesbar: **keine** `???`/`!!!`-Admonitions; Schichten als `<details class="wiki-layer …" markdown="1">`, Muster als `<div class="wiki-… " markdown="1">`, jeweils mit Leerzeilen innen.
- Ohne JavaScript bleibt jeder Inhalt lesbar; JS-Bausteine ersetzen nichts, was nur sie zeigen.
- `prefers-reduced-motion` wird respektiert; Anime.js nur aus `docs-site/assets/vendor/anime-4.5.0.umd.min.js`.
- Text- und Chipkontrast ≥ 4,5 : 1 in beiden Themes; schmale Ansicht (375 px) ohne horizontales Scrollen.
- Sofortnavigation (`document$`): jeder Baustein baut je Seite genau einmal auf und räumt beim Seitenwechsel Listener, Observer und Pop-ups auf.
- Keine erfundenen Begriffe, Zahlen, Protokolle; Glossardefinitionen tragen eine Quelle.
- Kein Commit ohne ausdrückliche Freigabe des Nutzers.
- Vor Abschluss: `./scripts/docs-site.sh build -s`, `./.venv/bin/pytest -q tests/test_wiki_check.py`, `npx playwright test -c playwright.docs.config.ts`.

## Review Focus

1. Sofortnavigation zwischen zwei Seiten mit Bausteinen erzeugt doppelte Köpfe, Chips oder Markierungen → genau ein Exemplar je Seite (Test in Task 2).
2. Begriffsmarkierung verändert Links, Code in `pre`, Überschriften oder vorhandene `data-preview`-Links → bleiben unberührt (Test in Task 4).
3. `search.json` fehlt oder lädt langsam → Glossar zeigt Definitionen sofort, Vorkommen mit Lade-/Fehlerzustand (Test in Task 4).
4. Touch: Antippen eines Hinweisziels öffnet das Pop-up statt zu navigieren, zweites Antippen folgt dem Link, Tippen daneben schließt (Test in Task 2).
5. Dunkles Theme: Chips und Pop-ups halten Kontrast (Test in Task 2).

---

### Task 1: Template-Override und Seitenkopf

**Files:**
- Create: `docs-overrides/partials/content.html` (Kopie des Zensical-Partials plus Kopfmarke)
- Create: `docs-site/assets/wiki-core.js`, `docs-site/assets/wiki-page.js`, `docs-site/assets/wiki.css`
- Create: `scripts/wiki-check.py`, `tests/test_wiki_check.py`
- Modify: `zensical.toml` (`[project.theme] custom_dir = "docs-overrides"`, `extra_css`/`extra_javascript` ergänzen, Reihenfolge: `wiki-core.js` vor allen `wiki-*.js`)
- Modify: `scripts/docs-site.sh` (`wiki-check.py` vor dem Build wie `oq-index.py --check`)
- Test: `tests/docs-site.spec.ts`

**Interfaces:**
- Produces: Front-Matter-Feld `weg` ∈ {`bedienen`, `konfigurieren`, `entwickeln`, `projekt`}; Template rendert bei gesetztem `weg` `<p class="wiki-pagehead" data-weg="…"><span class="wiki-pagehead-weg">Für: <Label></span></p>` vor `page.content`. Labels: bedienen „Einrichten und bedienen", konfigurieren „Konfigurieren und verstehen", entwickeln „Entwickeln und anbinden", projekt „Projektstand".
- Produces: Absatzkonventionen `**Vorher lesen:** [Titel](ziel.md)` (erster Absatz nach H1, optional) und `**Weiter mit:** [Titel](ziel.md)` (letzter Absatz).
- Produces (`wiki-core.js`): `window.wiki = { onPage(fn), siteUrl(path), loadHtml(path), loadJson(path), make(tag, cls, text) }`; `onPage(fn)` ruft `fn(article)` je Seite auf und den von `fn` zurückgegebenen Aufräumer beim nächsten Seitenwechsel; `siteUrl` löst relativ zur Skript-URL auf (Muster aus `fortschritt.js`); `loadHtml`/`loadJson` cachen je Sitzung im Speicher.
- Produces (`wiki-check.py`): `check_front_matter(md_text: str, path: str) -> list[str]` (Fehlermeldungen), CLI `--check` mit Exit 1 bei Fehlern.

- [ ] **Step 1: pytest für das Prüfskript** — `test_front_matter_weg_valid` (gültiges `weg: bedienen` → `[]`), `test_front_matter_weg_unknown` (`weg: kunde` → eine Meldung mit Pfad und erlaubten Werten), `test_no_front_matter_ok`.
- [ ] **Step 2: Playwright-Test** `Seitenkopf nennt Weg, Lesezeit und Weiter-Link unter der Überschrift`: Testseite = `docs/CAMERA_COMMISSIONING.html` erst nach Task 9; bis dahin `docs/anleitung/glossar.html` mit vorübergehend gesetztem `weg`. Erwartet: `.wiki-pagehead` ist direkt nächstes Element nach `h1`, enthält „Für: Einrichten und bedienen", `/\d+ min/`, und bei vorhandenem `**Weiter mit:**` einen Link mit gleichem Ziel. Seite ohne `weg` (`docs/status.html`) hat keinen Kopf.
- [ ] **Step 3: Tests laufen lassen** — pytest und Playwright schlagen fehl (Skript/Kopf fehlen).
- [ ] **Step 4: Umsetzen.** Override = Zensical-`partials/content.html` (aus `.venv-docs/lib/python3.13/site-packages/zensical/templates/partials/`) plus Kopfmarke; Lesezeit in `wiki-page.js` aus Wortzahl des Artikels / 200, aufgerundet, mindestens 1; Weg-Label verlinkt auf `index.html#weg-<weg>` (Ziele entstehen in Task 8).
- [ ] **Step 5: Tests grün**, `./scripts/docs-site.sh build -s` ohne Meldungen.

### Task 2: Hinweis-Baustein und Statuschips

**Files:**
- Create: `docs-site/assets/wiki-hint.js`
- Modify: `docs-site/assets/wiki-core.js` (Loader), `docs-site/assets/wiki-page.js` (Chips), `docs-site/assets/wiki.css`
- Test: `tests/docs-site.spec.ts`

**Interfaces:**
- Consumes: `window.wiki` aus Task 1.
- Produces (`wiki-hint.js`): `wiki.hint.register(kind: string, provider: (el) => Promise<Node|null>)`; Ziele sind Elemente mit `data-hint="<kind>"`. Öffnen nach 300 ms Überfahren, sofort bei Fokus; Esc und Verlassen schließen; Touch: erstes Antippen öffnet und verhindert Navigation, zweites folgt dem Link. Ein Pop-up zur Zeit, `role="tooltip"`, `aria-describedby` am Ziel, innerhalb des Viewports positioniert.
- Produces (`wiki-core.js`): `wiki.loadOqIndex() -> Promise<Map<string,{title,status,category}>>` aus der ersten Tabelle von `docs/open-questions.html` (Spalten wie `docs-interactive.js`, Statusabbildung `OQ_STATUS` dorthin verschieben und von beiden nutzen); `wiki.loadPhases() -> Promise<Map<"P0".."P8",{title,state}>>` aus der ersten Tabelle von `docs/ROADMAP.html` (Statuswörter wie `roadmap.js`: erreicht/teilweise/blockiert/offen).
- Produces: Chip `<span class="wiki-chip wiki-chip--<category>">Status</span>` direkt nach Links auf `open-questions.html#oq-NN` und nach Links, deren Text mit `P0`–`P8` beginnt und die auf `ROADMAP.html` zeigen; beide Links bekommen `data-hint="oq"` bzw. `"phase"` (Pop-up: Titel und Status).

- [ ] **Step 1: Playwright-Tests**: `OQ-Verweise tragen Statuschip und Pop-up mit Titel` (auf `docs/GSVMULTI_PROTOCOL.html`: Chip neben OQ-07 mit dem Status aus der OQ-Tabelle; Hover zeigt `role=tooltip` mit dem Titel von OQ-07; Esc schließt); `Hinweise funktionieren per Touch` (isMobile-Kontext: Tap öffnet, URL unverändert; zweiter Tap navigiert); `Sofortnavigation baut Chips genau einmal auf` (zweimal hin und her navigieren, Chips je Link genau 1); `Chips und Pop-ups halten im dunklen Theme Kontrast` (Kontrastberechnung wie im bestehenden Beleglink-Test, ≥ 4,5).
- [ ] **Step 2: Fehlschlag prüfen.**
- [ ] **Step 3: Umsetzen.** Fehlt die OQ-/Roadmap-Seite, bleiben Links unverändert (kein Chip, keine Fehlermeldung im Text).
- [ ] **Step 4: Tests grün**, bestehende OQ-Ansichtstests weiter grün.

### Task 3: Schichtblöcke und Seitenmuster

**Files:**
- Modify: `docs-site/assets/wiki.css`, `docs-site/assets/wiki-page.js`
- Modify: `scripts/wiki-check.py`, `tests/test_wiki_check.py`
- Test: `tests/docs-site.spec.ts`

**Interfaces:**
- Produces (Markdown-Konventionen, verbindlich für Tasks 9 und 10):
  - Schicht: `<details class="wiki-layer wiki-layer--hintergrund" markdown="1">` mit `<summary>Was passiert im Hintergrund</summary>`; Entwicklerschicht `wiki-layer--entwickler` mit `<summary>Für Entwickler</summary>`; `open` auf Entwicklerseiten.
  - Einstellung: `<div class="wiki-setting" markdown="1">` mit zweispaltiger Tabelle, Zeilen genau `Wozu`, `Im Hintergrund`, `Standard`, `Ändern?`, `Quelle`; die Zelle `Ändern?` beginnt mit **Nein**, **Nur wenn** oder **Ja**.
  - Anbindungspunkt: `<div class="wiki-seam" markdown="1">` mit Tabelle, Zeilen `Trennstelle`, `Vertrag`, `Darf geändert werden`, `Bleibt unverändert`, `Tests`; danach optional ein Codeblock.
- Produces: `check_patterns(md_text, path) -> list[str]` prüft Zeilennamen und `Ändern?`-Wort.

- [ ] **Step 1: pytest**: `test_setting_rows_complete`, `test_setting_verdict_word` (Zelle „Vielleicht" → Meldung), `test_seam_rows_complete`.
- [ ] **Step 2: Playwright** `Schichten und Muster sind ohne und mit JavaScript lesbar` auf einer Fixture-Route (Seite per `page.route` mit Beispiel-HTML aus dem gebauten Glossar ersetzen ist zu fragil; stattdessen nach Task 9 auf den Beispielseiten prüfen — Test hier anlegen und mit `test.fixme` markieren, in Task 9 aktivieren): `details.wiki-layer` vorhanden, Summary-Text exakt, Inhalt nach Öffnen sichtbar; `.wiki-setting` zeigt Urteilschip `wiki-verdict--nein|nurwenn|ja`; mit `javaScriptEnabled: false` sind alle Tabellenzeilen sichtbar.
- [ ] **Step 3: Umsetzen.** CSS gibt den beiden Schichtarten je ein Symbol und eine zurückhaltende Randfarbe; der Urteilschip entsteht per JS aus dem ersten fett gesetzten Wort.
- [ ] **Step 4: pytest grün**, Build -s ohne Meldungen.

### Task 4: Glossar als Begriffsindex und Begriffsmarkierung

**Files:**
- Modify: `docs/anleitung/glossar.md` (Format umstellen, bestehende ≈ 40 Begriffe ohne Inhaltsverlust)
- Create: `docs-site/assets/wiki-glossar.js`
- Modify: `docs-site/assets/wiki-core.js`, `docs-site/assets/wiki-page.js`, `docs-site/assets/wiki.css`
- Modify: `scripts/wiki-check.py`, `tests/test_wiki_check.py`, `tests/docs-site.spec.ts`

**Interfaces:**
- Produces (Glossarformat): Front Matter `hide: [toc]` und `weg: bedienen`; Kategorien bleiben `##`; je Begriff `### <Begriff>` (Code-Begriffe in Backticks), danach **erster Absatz = Kurzdefinition** (Pop-up-Text, ≤ 280 Zeichen), **zweiter Absatz = Metazeile** `*Weg:* Bedienen|Konfigurieren|Entwickeln · *Auch:* a, b · *Quelle:* [Text](ziel)` (`Auch` optional, Reihenfolge fest), danach beliebige Details.
- Produces: `check_glossary(md_text) -> list[str]` (Metazeile vorhanden, Weg gültig, Quelle als Link, Kurzdefinition ≤ 280 Zeichen, Begriffe und Synonyme eindeutig, case-insensitiv).
- Produces (`wiki-core.js`): `wiki.loadGlossary() -> Promise<Array<{id, term, aliases[], weg, short, category}>>` aus `docs/anleitung/glossar.html` (h3-IDs aus dem DOM, nicht geraten); `wiki.termMatcher(entries) -> (text) => Array<{entry, index, length}>` — Begriffe in Großbuchstaben bis 5 Zeichen exakt, sonst ohne Groß/klein; Grenzen `(?<![\p{L}\p{N}_])…(?![\p{L}\p{N}_])` mit `u`-Flag; längere Treffer vor kürzeren.
- Produces (Markierung, `wiki-page.js`): in jedem Abschnitt (zwischen `h2`/`h3`) die erste Nennung je Begriff als `<a class="wiki-term" href="…/glossar.html#id" data-hint="term">`; Codespans (`code` außerhalb von `pre`), deren Text exakt einem Begriff oder Synonym entspricht, werden umschlossen. Ausgenommen: `a`, `pre`, `h1`–`h6`, `summary`, `.wiki-*`, `[data-preview]`, Navigation, die Glossarseite selbst.
- Produces (Glossarseite, `wiki-glossar.js`): A–Z-Leiste (Buchstaben ohne Begriffe deaktiviert), Filterfeld über Begriff und Synonyme, Wegfilter (Alle/Bedienen/Konfigurieren/Entwickeln), Zähler `n von m Begriffen`; je Begriff Abschnitt „Vorkommen" nach Seite gruppiert (`path`-Titel aus `search.json`), Anzahl je Seite, je Fundstelle Abschnittstitel als Link `location + ":~:text=" + Treffer`, `data-hint="fundstelle"` mit Kontextsatz (±90 Zeichen, an Satzgrenzen gekürzt, Begriff in `<mark>`); ab 8 Seiten Rest eingeklappt „und N weitere auf M Seiten"; Link „Alle Treffer in der Suche" (öffnet die Zensical-Suche mit dem Begriff; Mechanismus im gebauten `search`-Bundle prüfen, sonst Suchfeld fokussieren, Wert setzen, `input` auslösen). Leerer Filter → Knopf „In der Volltextsuche suchen".
- Vorkommensindex: einmal `search.json` laden, je Eintrag HTML→Text, Wörter normalisieren, Index Erstwort → Einträge; Mehrwortbegriffe per Phrasenprüfung; Glossarseite selbst ausschließen; Berechnung in Häppchen (`requestIdleCallback`/`setTimeout`), Zustand „Vorkommen werden ermittelt…".

- [ ] **Step 1: pytest**: `test_glossary_meta_required`, `test_glossary_weg_values`, `test_glossary_source_link`, `test_glossary_short_length`, `test_glossary_duplicate_alias`.
- [ ] **Step 2: Playwright**: `Glossar filtert über Synonyme und springt per A–Z` (Filter „Region" findet ROI; Klick auf „R" scrollt zum ersten R-Begriff); `Glossar zeigt Vorkommen mit Kontext beim Überfahren` (bei ROI ≥ 2 Seiten, Hover zeigt `mark` mit „ROI"); `Glossar bleibt ohne Suchindex lesbar` (`**/search.json` abbrechen → Definitionen sichtbar, Hinweis „Vorkommen nicht verfügbar"); `Begriffe werden je Abschnitt einmal markiert ohne Links und Code zu verändern` (auf `docs/uebersicht/messpfad.html`: Anzahl `a[href]` außerhalb `.wiki-term` und Text aller `pre` gleich wie vor der Markierung; je Abschnitt höchstens ein `.wiki-term` je Begriff); `Begriff zeigt Kurzdefinition beim Überfahren`; `Glossar ohne JavaScript bleibt lesbar` (`javaScriptEnabled: false`, alle h3 und Metazeilen sichtbar).
- [ ] **Step 3: Glossar umstellen** (bestehende Einträge, Inhalte unverändert, Metazeile ergänzen; Quelle aus vorhandenen Verweisen oder Code).
- [ ] **Step 4: JS umsetzen**; Performance: auf dem Pi Vorkommensberechnung für den aktuellen Index < 3 s (im Test messen und loggen, Schwelle 6 s).
- [ ] **Step 5: Tests grün**; bestehender Test „Glossarbegriff und Dokumentabschnitt zeigen eine Vorschau" bleibt grün.

### Task 5: Glossar ausbauen

**Files:**
- Modify: `docs/anleitung/glossar.md`

**Interfaces:**
- Consumes: Glossarformat und `check_glossary` aus Task 4.

- [ ] **Step 1: Kandidaten sammeln** aus Überschriften, Codespans und Abkürzungen in `docs/`, `README.md`, `Konzept.md`, `docs-site/api/` (Wiederholung ≥ 2 Seiten oder zentrale Bedeutung); Liste mit Fundorten in den Scratchpad, nicht ins Repo.
- [ ] **Step 2: Einträge schreiben** nach Kategorie (Projekt/Fachliches, Kamera und Bild, Zeitbasis, Messpfad und Freigabe, Serielle Schnittstelle und Geräte, Konfiguration, Entwicklung/API). Jede Definition aus Code oder Projektdokument belegt, Quelle verlinkt; Konfigurationsschlüssel mit Weg Konfigurieren; Unbelegtes weglassen. Ziel ≥ 200 Begriffe insgesamt.
- [ ] **Step 3: Prüfen**: `./.venv-docs/bin/python scripts/wiki-check.py --check` ohne Meldung, Build -s ohne Meldung, Glossar-Playwright-Tests grün; Stichprobe von 20 Einträgen gegen ihre Quelle.

### Task 6: Interaktive Verarbeitungskette

**Files:**
- Create: `docs-site/assets/data/kette.json`, `docs-site/assets/wiki-kette.js`
- Modify: `scripts/wiki-check.py`, `tests/test_wiki_check.py`, `docs/anleitung/01-kette-verstehen.md`, `docs-site/assets/wiki.css`, `tests/docs-site.spec.ts`

**Interfaces:**
- Produces (`kette.json`, Schema `kette_v1`): `{"schema":"kette_v1","stufen":[{"id","titel","zustand","zweck","einstellung","anbindung","api","doku"}]}`; Stufen in Reihenfolge `frames, detect, track, rectify, ocr, validate, sink`; `zustand` ∈ {`fertig`, `gebaut`, `teilweise`, `außer Betrieb`}; Inhalte aus dem `Aufbau`-Block in `CLAUDE.md` und den API-Seiten; `anbindung` = Pfad unter `src/dispread/`, `api`/`doku` = Site-Pfade (`.html`).
- Produces: `check_kette(data, root) -> list[str]` (Schema, Reihenfolge, Pfade existieren als Quelle: `anbindung` im Repo, `api` als `docs-site/api/*.md`, `doku` als `.md` unter `docs/`).
- Produces: Platzhalter `<div class="wiki-kette" markdown="1">` mit einem Satz Ersatztext; `wiki-kette.js` zeichnet die Stufen als verbundene Knoten (breit waagerecht, < 720 px senkrecht), Zustand als Chip, `data-hint="kette"` mit Zweck/Einstellung/Anbindung, Klick → `api`. Aufbau mit Anime.js gestaffelt, bei reduzierter Bewegung statisch.

- [ ] **Step 1: pytest** `test_kette_valid`, `test_kette_order`, `test_kette_missing_module`.
- [ ] **Step 2: Playwright** `Verarbeitungskette zeigt sieben Stufen mit Zustand und führt zur API` (auf `docs/anleitung/01-kette-verstehen.html`: 7 Knoten, Hover zeigt Zweck, Klick auf `ocr` → `api/ocr.html`; 375 px ohne Querscrollen).
- [ ] **Step 3: Umsetzen, Tests grün.**

### Task 7: Diagramme aus Tabellen

**Files:**
- Create: `docs-site/assets/wiki-chart.js`
- Modify: `docs/VALIDATION.md` (zwei kleine Übersichtstabellen am Anfang des Abschnitts zu den Live-Läufen), `docs-site/assets/wiki.css`, `tests/docs-site.spec.ts`

**Interfaces:**
- Produces: Hülle `<div class="wiki-chart" data-chart="bar|stacked" data-label="<Spaltenname>" data-unit="<Einheit>" markdown="1">` um eine Markdown-Tabelle; erste Spalte = Kategorie, weitere numerische Spalten = Reihen (deutsches Komma, `%` erlaubt). Das Diagramm erscheint **über** der Tabelle; die Tabelle bleibt sichtbar (einklappbar „Werte als Tabelle"). Nicht parsebare Zelle → kein Diagramm, Tabelle unverändert.
- Inhalte: (a) „Live-Läufe mit Referenz": Lauf, entschiedene VALID, Fehllesungen, Bilder/s — Werte wörtlich aus den drei Einträgen vom 2026-10-21; (b) „Lesestatus nach Anzeigezustand": Zeilen „Ruhige Anzeige" und „Bilder im Wechsel", Spalten VALID/TRANSITION/UNREADABLE in % aus dem 12-min-Lauf.
- Vor Umsetzung `dataviz`-Skill laden; Farben aus den bestehenden Statusfarben, Achsen beschriftet, Werte am Balken.

- [ ] **Step 1: Playwright** `Diagramm entsteht aus der Tabelle und fällt ohne Zahlen auf die Tabelle zurück` (SVG mit so vielen Balken wie Zellen; Tabelle weiter im DOM; per `page.route` eine Zelle durch „x" ersetzt → kein SVG).
- [ ] **Step 2: Umsetzen, Werte gegen die Quelleinträge gegenprüfen, Test grün.**

### Task 8: Startseite als Weiche

**Files:**
- Modify: `README.md`
- Create: `docs-site/assets/wiki-start.js`
- Modify: `docs-site/assets/wiki.css`, `scripts/wiki-check.py`, `tests/test_wiki_check.py`, `tests/docs-site.spec.ts`

**Interfaces:**
- Produces (README-Struktur): nach der Einleitung `<div class="wiki-stand" markdown="1">` mit Liste `**Kamera:** …`, `**Messpfad:** …`, `**GSVmulti:** … [OQ-07](…)`; dann `<div class="wiki-wege" markdown="1">` mit genau drei `###`-Wegen in der Reihenfolge Einrichten und bedienen, Konfigurieren und verstehen, Entwickeln und anbinden, je ein Satz Wer-Beschreibung und 3–4 Links mit Kurztext; dann Tour/Stand-Hinweis; dann „Alle Seiten" wie heute.
- Produces: im Weg „Entwickeln und anbinden" steht der Ketten-Platzhalter aus Task 6 (kompakte Darstellung).
- Produces: `wiki-start.js` macht aus `.wiki-wege` drei Spalten mit IDs `weg-bedienen`, `weg-konfigurieren`, `weg-entwickeln` (Ziele für Task 1), auf schmaler Ansicht untereinander; `.wiki-stand` als Chipzeile (OQ-Chip aus Task 2); „Alle Seiten" in `<details>` (zu, aber im DOM — Navigationstest bleibt gültig).
- Produces: `check_start(md_text) -> list[str]` (beide Hüllen vorhanden, drei Wege in Reihenfolge).

- [ ] **Step 1: pytest** `test_start_has_three_ways_in_order`, `test_start_missing_stand`.
- [ ] **Step 2: Playwright** `Startseite führt in drei Wegen zum ersten Schritt` (drei Spalten mit IDs, je ≥ 3 Links, erster Link je Weg führt zu einer Seite mit passendem `data-weg`); bestehender Test „Startseite verlinkt alle Navigationsziele im Inhalt" bleibt grün; 375 px ohne Querscrollen.
- [ ] **Step 3: README umbauen** — Fakten der Einleitung unverändert, keine neuen Behauptungen; **Umsetzen, Tests grün.**

### Task 9: Beispielseiten je Weg

**Files:**
- Modify: `docs/CAMERA_COMMISSIONING.md` (`weg: bedienen`), `docs/anleitung/10-kamera-livevorschau.md` Abschnitt „Kamera einstellen" (`weg: konfigurieren`), `docs/GSVMULTI_PROTOCOL.md` Abschnitte „Die Naht im Code" und „Der Platzhalter" (`weg: entwickeln`)
- Modify: `tests/docs-site.spec.ts` (fixme aus Task 3 aktivieren, Seitenkopf-Test aus Task 1 auf `CAMERA_COMMISSIONING` umstellen)

**Interfaces:**
- Consumes: Konventionen aus Tasks 1 und 3.

- [ ] **Step 1: Kamera-Inbetriebnahme**: nummerierte Bedienschritte vorn ohne Code-Interna; StreamCam-Details (`focus_automatic_continuous`, `CameraOwner`, USB-ID, `index == 0`) in `wiki-layer--hintergrund`/`--entwickler`; historische IMX500-Abschnitte unverändert, aber unter einer eingeklappten Schicht „Historisch"; `**Weiter mit:**` auf die Kameraregler.
- [ ] **Step 2: Kameraregler** als `wiki-setting`-Karten für jede in „Kamera einstellen" genannte Einstellung; Werte und Regeln nur aus Seite, `CLAUDE.md` (Fokus 48, Automatik zuerst aus) und `src/dispread/camera_settings.py`.
- [ ] **Step 3: Ausgabeprotokoll anbinden** als `wiki-seam` auf `GSVMULTI_PROTOCOL.md`: Trennstelle `sink/protocol`, Vertrag aus dem Code, `gsv_ascii` wirft absichtlich (OQ-07), Tests; Codebeispiel zeigt ein Protokoll nach dem Muster von `ascii_csv.py`, **kein** GSVmulti-Telegramm.
- [ ] **Step 4: Prüfen**: Fakten jeder Seite vorher/nachher abgleichen (keine Aussage verloren), Build -s, alle Wiki-Tests grün.

### Task 10: Pflegelauf, Doku und Abschluss

**Files:**
- Modify: `scripts/docs-maintenance-prompt.md`, `AGENTS.md` (Abschnitt zur Doku-Seite), `TODO.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-10-23-wiki-geruest-design.md` (Abschnitt 5 Datenfluss an Laufzeitindex anpassen)
- Create: `DESIGN.md` (über `/impeccable document`)

- [ ] **Step 1: Pflegeauftrag** um die Konventionen ergänzen (Front Matter `weg`, Schichten, Muster, Glossarformat, Startseiten-Hüllen nie entfernen, neue Begriffe nur mit Quelle) und den Satz „greift dem Umbau nicht vor" durch „hält die Bausteine ein" ersetzen; `./.venv/bin/pytest -q tests/test_docs_maintenance.py` grün.
- [ ] **Step 2: AGENTS.md/TODO/CHANGELOG** nachziehen; TODO nennt die noch nicht umgestellten Seiten.
- [ ] **Step 3: Brief Abschnitt 5** auf „Vorkommen zur Laufzeit aus `search.json`, Format geprüft durch `wiki-check.py`" korrigieren (Abweichung begründet: exakte Anker, kein Zweiphasen-Build, immer aktuell).
- [ ] **Step 4: DESIGN.md** aus dem gebauten Ergebnis ableiten.
- [ ] **Step 5: Vollprüfung**: Build -s, pytest (`tests/test_wiki_check.py`, `tests/test_docs_maintenance.py`), komplette Docs-Playwright-Suite, Sichtprüfung Startseite/Glossar/Beispielseiten hell, dunkel, 375 px.
