# Entscheidungsvorlage R13 → master (für 2026-10-28)

Stand 2026-10-27. Zweig `feat/r13-display-haertung` (Forgejo), 27 Commits
ohne Merges seit `master` 109d360, 108 Dateien. Volle Testsuite auf
`b5d1b3b`: **2400 bestanden, 8 übersprungen**; Live- und Doku-Browsertests
2/2 und 45/45. Nach dem Einmischen von `master` c7e7c2d (Wiki-Gerüst,
`2f0183d`): **2526 bestanden, 8 übersprungen**. Nichts davon ist in `master`. Die Entscheidung trifft die
Person; diese Vorlage bündelt Belege, Grenzen und offene Fragen.

## Was der Zweig enthält

| Schritt | Inhalt |
| --- | --- |
| R13-1…R13-5 | Rahmenbereich-Tracker (Nachführung am Gehäuserahmen statt am Zifferninhalt), Einbindung in Einrichtung/Profil/Lauf, begrenzte Diagnosebilder, manuelle Bereichskorrektur, Offline-Replay |
| R13-7 | Kandidat: grobe LCD-Randprüfung (2,5 px) statt absoluter Kantenlage, Residuengrenzen RMS ≤ 0,35 / max ≤ 0,65 px |
| R13-8 | Displayhärtung gegen helle Kratzer, ehrliche Gründe `leser:<grund>[:<zelle>]`, Ursachenfenster, Prüfung `displayfehler` |
| R13-9, R13-12 | Fokus nach dem Setzen prüfen; immer von unten anfahren (Motor-Hysterese 2–3 Stufen) |
| R13-10, R13-13 | Startsuche bei schrägem Blick (mehr Randkandidaten, bis 32 Startlagen je Anker), klarer Bedienhinweis |
| R13-11 | Robuster Rahmenvorschlag: Band am dunklen Rahmen mit Formprüfung, Reserve gegen zwei Bereichsausfälle, bis 20 Bereiche |
| R13-14 | Offline-Einrichtung aus Aufnahmen; Live und Ernte verweigern solche Profile |
| R13-15 | Hinweis „Anzeige hat sich bewegt – neu einrichten“ nach ≥ 3 s Verlust |
| R13-16 | Speicherbudget 64-GB-SD: Platzprüfung, Diagnose standardmäßig aus, `dispread live aufraeumen`, Live-Audit je Lauf ohne Rotation |
| R13-17 | OQ-44: Testlauf gibt technisch nie einen Wert frei |
| R13-18 | OQ-45: Ergebniszeit trägt immer `HOST_MONOTONIC` |

## Belege

**Live am 2026-10-23** (eine Person, ein Gerät, Raumlicht, kein formaler
Abnahmelauf; [VALIDATION](../../VALIDATION.md#r13-live-2026-10-23)):

| Lauf | Stand | Fehllesungen | Verfügbarkeit |
| --- | --- | ---: | --- |
| `075343Z` 12 min, Störungen | R13-7 | 0 / 9077 | 52,7 % VALID stabil (Kratzer, danach R13-8) |
| `100613Z` 5,7 min, ruhig | + R13-8 | 0 / 6615 | **99,98 %** VALID stabil, 0 Trackingverluste |
| `121436Z` 10 min, Störungen | + R13-8 | 0 / 10 316 | Hand/Rahmen verdeckt: Wiederkehr nach 2–3 s; Drehung −2,25° (Ecken ~19–21 px) über Suchradius 12 px → korrekt dauerhaft abgelehnt |
| `131121Z` 10 Bereiche | + R13-8 | — | dauerndes `rahmen_unstimmig` ohne Bewegung; offline mit R13-11 behoben (146/148, die 2 abgelehnten zeigen die Hand) |

Über alle Live-Läufe: **0 Fehllesungen**. Die Ausfälle bei Faktor 2 und 5
(`master`, 21.10.: kein VALID in stabilen Fenstern) traten im ruhigen Lauf
`100613Z` und offline auf DEV/E/F mit dem Rahmen-Tracker nicht mehr auf.

**Offline mit dem Rahmenvorschlag aus R13-11** ([VALIDATION](../../VALIDATION.md#r13-r11-2026-10-23)):
DEV, E, F je Faktor 100 % gehalten (DEV 568/568, E 429/429, F 1341/1341);
424 Vergleichsbilder ohne Unterschied im Update-Ergebnis; 27/29 reale
Einrichtungsbilder ergeben geeignete Vorschläge.

## Bekannte Grenzen (vor dem Merge zu kennen)

1. **Blinder Fleck, ergänzt am 2026-10-28 (R13-19c):** Melden alle Rahmenbereiche
   dieselbe falsche Bewegung, während das LCD still steht, werden bis
   **4,7 px** (Fixture) bzw. **4,89 px** (reale Aufstellungen, Review)
   Eckfehler angenommen. Lügt nur eine Hälfte: bis **1,43 px**. Das ist
   keine allgemeine obere Schranke. Der neue zweite Ähnlichkeitsfit
   akzeptiert im konservativen Fixture-Raster bei stillstehendem LCD
   bis **5,220583 px** Eckfehler (s=1,005); bei s=0,995 sind es
   4,466826 px, bei s=1 etwa 4,725129 px. Erster Fehlschlag,
   plausibler Grobvorschlag und gemeinsam falsche Treffer sind injiziert;
   alle weiteren Prüfungen laufen real. Die unveränderte 2,5-px-LCD-Prüfung
   begrenzt auch Maßstabslügen, beweist aber keine Subpixelgenauigkeit.
   Diese neue dokumentierte Grenze muss die Person bei der Entscheidung
   berücksichtigen; sie ist ebenfalls keine allgemeine obere Schranke.
2. **Kein Betrieb ohne Raumlicht.** Der Rahmen-Tracker braucht Licht auf
   Rahmen und Gehäuse und lehnt im Dämmerlicht ab (sicher, nicht verfügbar).
   Der Prototyp LCD-Fenster-Tracker (`exp/r13-fenster-tracker`) ist nicht reif.
3. **Sehr schräge Ansichten** sind ein Grenzfall: Bei „links etwa 18°“
   gelang am 26.10. eine von drei Einrichtungen, zwei lehnten ehrlich ab;
   bis etwa 11,5° gelingt sie.
4. **Bewegungsgrenzen, Stand 2026-10-28 (R13-19c):** Ein zweiter Versuch
   mit Grobschätzung kann die unveränderten Suchfenster über 12 px hinaus
   versetzen. Absolute Grenzen bleiben `max_shift_px` = **20 px** und
   `max_rotation_deg` = **3°** gegen das Referenzquad; darüber wird abgelehnt.
   Nur dieser zweite Versuch darf gemäß Entscheidung Leonhard vom
   2026-10-28 zusätzlich gleichförmigen Maßstab **0,995…1,005** fitten.
   Innerhalb dieser Grenzen müssen alle bisherigen Feinprüfungen bestehen,
   einschließlich RMS ≤0,35 / Maximum ≤0,65 px und LCD-Rand ≤2,5 px.
   Synthetisch gelingen 11,8/15/19 px mit s=0,998/1,002 auf ≤0,5 px
   Eckfehler; 21/23 px und s=0,990/1,010 werden abgelehnt. Die frühere
   13-px-Ablehnung ist ausdrücklich durch korrekte Nachführung ersetzt.
   Offline verbessern sich die Live-Diagnosefits auf **205/208 statt
   107/208** und im Bewegungslauf auf **23/152 statt 3/152**;
   0/196 Fehllesungen, alte Erfolge und DEV 568/568 bitgleich.
   Große Lagen bei 72–98 s und ab 166 s werden in den getesteten Bildern
   abgelehnt; die kleine Lage bleibt teilweise unverfügbar.
   Der zweite Durchgang braucht isoliert Median **16–17 ms statt 49 ms**;
   **Ziel ≤10 ms verfehlt**. [OQ-46](../../open-questions.md#oq-46)
   ist zur Ursache geklärt. Neue unabhängige Abnahme steht weiter aus,
   Einzelbelege in [VALIDATION](../../VALIDATION.md#r13-19c-aehnlichkeit-2026-10-28).
5. **Profile von vor R13-11 müssen neu eingerichtet werden.**
6. Einrichtungsrelevante Aufnahmen nur als PNG (JPEG verschiebt die
   Gitteranpassung um bis zu 13 px).
7. Keine formale Abnahme an zwei Aufstellungen mit dem neuen Vorschlag.
   Die Aufstellung muss die Person wählen; die Kamera steht seit dem 23.10.
   an „links etwa 18°“, wo die Einrichtung meist ablehnt.

## Zu entscheiden

1. **R13 nach `master`?**
   *a)* jetzt mergen, Abnahme an zwei Aufstellungen danach auf `master`;
   *b)* erst die formale Abnahme mit der Person, dann mergen;
   *c)* nur unabhängige Teile übernehmen (OQ-44, OQ-45, Speicherbudget,
   Fokusanfahrt). Diese hängen allerdings an R13-Code und müssten
   herausgelöst werden. Empfehlung: **b**, die Abnahme braucht etwa eine
   Stunde mit der Person und Raumlicht.
2. **Kandidat R13-7 statt eingefrorenem Stand:** Der eingefrorene Stand
   (`52a64a7`) fiel bei Raumlicht durch (absolute LCD-Kantenlage wandert mit
   dem Licht); R13-7 besteht, erkauft das aber mit dem blinden Fleck aus
   Grenze 1. Bitte ausdrücklich bestätigen oder ablehnen.
3. **Nachtbetrieb:** entweder festschreiben „nur mit Raumlicht“ oder den
   Fenster-Tracker weiterverfolgen.
4. **CI auf dem Mess-Pi:** Builds und Browsertests teilen den Pi mit dem
   Messpfad (früher bis 44 s Stillstand); auslagern oder während Läufen
   sperren?
5. **GSVmulti-Protokoll** ([OQ-07](../../open-questions.md#oq-07)): weiter
   blockiert, braucht eine Beschreibung von GSVmulti.
6. **UI/UX-Überarbeitung** der Werkbank: Umfang und Zeitpunkt.

## Bei Zustimmung

Merge durch die Person (Merge-Commit, kein Fast-Forward möglich), danach auf
`master`: volle Suite, `./scripts/docs-site.sh build -s`, Doku-Playwright,
Werkbank neu starten und vorhandene Profile neu einrichten. Die
Zweig-Werkbank `dispread-werkbank-r13` danach beenden.

## Nachtrag 2026-10-26: Hardwareprüfung

* **Fokusanfahrt von unten (R13-12) am Gerät bestätigt:** drei Einrichtungen,
  jedes Mal Fokus 48 und Endprüfung im ersten Versuch bestanden (98–100 %
  der besten Messung). Am 23.10. schlug die Prüfung dort vor R13-12 noch an.
  Zweimal Vollsweep-Rückfall, etwa 70 s länger.
* **Linksansicht etwa 18°:** eine von drei Einrichtungen mit Vorschlag
  (20 Bereiche, Reserve erfüllt, 2 Warnungen), zwei ehrliche Ablehnungen.
* **PNG-Aufnahmen** dieser Ansicht mit Werteplan für die weitere Entwicklung:
  `var/diagnostics/r13-winkel-links18-png-20261026` (nur Replay) und
  `…-png2-20261026` (auch Offline-Einrichtung). Rückstellung jeweils
  bestätigt. Details: [Laborjournal](../../lab_journal.md).
* Freier Platz auf der SD-Karte danach **2,1 GB** (Reserve für eine
  Einrichtung 2 GB). Vor weiteren Aufnahmen muss die Person Platz schaffen.
* Der Pi startete am 24.10. 17:12 und 25.10. 16:14 ohne erkennbaren Anlass
  neu (kein persistentes Journal). Die Zweig-Werkbank wurde jeweils neu
  angelegt.

## Nachtrag 2026-10-27: dritter Neustart, Platz

* **Neustart am 26.10. um 23:13**, wieder ohne erkennbaren Anlass. Keine
  Paketaktualisierung (letzte apt-Aktion 14.10.), kein automatischer Neustart
  konfiguriert, PMIC meldet keinen Stromreset (`power_reset` 0) und keinen
  Überstrom an USB oder SD. Der Bootloader meldet `rsts` 0x20; das deutet
  nach unserer Kenntnis auf einen Software- oder Watchdog-Reset statt eines
  Kaltstarts hin (nicht gegen Quellen geprüft). Der Lastmonitor lief zu dem
  Zeitpunkt nicht. Seit 2026-10-28 09:55 ist das Journal dauerhaft
  (`/etc/systemd/journald.conf.d/50-persistent.conf`, übersteuert
  `Storage=volatile` von Raspberry Pi OS); nach dem nächsten Neustart zeigt
  `journalctl -b -1` das Ende des vorigen Boots. CI-Last scheidet als
  gemeinsamer Auslöser aus: Am 24.10. 17:12 und 25.10. 16:14 lief laut
  Forgejo kein CI-Lauf; beim dritten Neustart lief der Wiederholungslauf
  von Run 216 (23:09–23:25), der dadurch rot wurde.
* **Freier Platz 1,5 GB** (26.10.: 2,1 GB). Hauptursache ist ein
  automatisches Update von Claude Code (Version 2.1.311, +294 MB). Ohne
  `var/` anzufassen ließen sich etwa 0,95 GB freimachen: Claude Code 2.1.307
  und 2.1.309 (zusammen etwa 585 MB, nicht in Gebrauch) und Codex-Release
  0.163.0 (368 MB, weder `current` noch in Gebrauch). Nicht gelöscht; das
  entscheidet die Person.

## Nachtrag 2026-10-28: SSD zur Entlastung, PCIe-Watchdog

* **Platz ist kein Hindernis mehr:** 12 GB frei auf der SD-Karte. Die
  Entwicklungsdaten (Diagnoseaufnahmen, Live-Läufe vor dem 23.10.,
  Altlasten) liegen auf einer NVMe-SSD unter `/mnt/ssd/picam-dev`, dazu
  eine geprüfte Sicherung von ganz `var/`. Die SSD ist nur Entlastung:
  `var/` mit den Produktdaten bleibt auf der SD-Karte, `src/` kennt die
  SSD nicht (Wächtertest), Tests finden Aufnahmen über `DISPREAD_DEV_DATA`.
  Das Journal liegt ebenfalls auf der SSD.
* **Wahrscheinlicher Kandidat für die Neustarts:** Der MEHub-Dienst
  `rm520n-watchdog` setzte seit Tagen alle 10 Minuten den PCIe-Bus zurück,
  weil er kein 5G-Modem fand; er riss dabei auch die SSD ab. Der Timer ist
  abgeschaltet. Nicht belegt; bleiben Neustarts aus, spricht das dafür.
  Details: [Laborjournal](../../lab_journal.md).
* Run 216 fiel am 28.10. mit dem Kopierlauf und dem PCIe-Abriss zusammen.
