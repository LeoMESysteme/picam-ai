# Automatische Siebensegment-Erkennung — Machbarkeitsvergleich 2026-09-18

Das Ergebnis ist ein reproduzierbarer Offline-Vergleich und ein Lückenbericht.
Es gibt keine freigegebene automatische Leserstrecke und keine UI-Demonstration.
Die Produktionsdecoder, Task-11-Sperre, Kameraeigentümerschaft und serielle
Ausgabe sind unverändert.

## Reproduzieren

Branch `codex/automatic-seven-segment`, Basis `e0c263f`, eigener Worktree.
Die venv wurde mit `--system-site-packages` aus der vorhandenen Projekt-Python-
Installation erzeugt und das Paket mit `--no-deps` installiert. Laufzeitpakete
und Versionen: [dependencies.md](dependencies.md).

```bash
./.venv/bin/python scripts/fetch-automatic-seven-segment-models.py
./.venv/bin/python -m dispread.experimental.runner \
  --manifest experiments/automatic_seven_segment/manifest.json \
  --config experiments/automatic_seven_segment/config.json \
  --output var/automatic-seven-segment-new
```

Der Befehl verifiziert Daten- und Modellhashes, wertet Entwicklung aus, schreibt
`frozen.json` **vor** der Testinferenz und erstellt `readings.jsonl`,
`results.json` sowie beschriftete Overlays mit Quellen-/Lizenz-Sidecars.
Vorhandene Ergebnisverzeichnisse werden nicht überschrieben.

Zur Wiederholung der archivierten Auswahl zusätzlich
`--frozen experiments/automatic_seven_segment/results/frozen.json` angeben.
Abweichende Quellen-, Daten-, Modell-Hashes oder Versionen der erfassten
Python-Pakete (NumPy, ORT, PyYAML, FlatBuffers, Protobuf, pytest, Ruff) werden
abgewiesen. Python 3.13.5, System-OpenCV 4.10.0 und Tesseract 5.5.0 werden
protokolliert, aber nicht automatisch gegen den Freeze geprüft; für eine
vergleichbare Wiederholung sind auch diese Systemversionen beizubehalten. Messdauern können bei derselben Auswahl schwanken; die Auswahl
wird bei `--frozen` nicht anhand neuer Laufzeiten geändert.

## Daten und Aussagegrenzen

[Manifest](../experiments/automatic_seven_segment/manifest.json),
[Daten-/Lizenzbericht](automatic-seven-segment-data.md),
[Kandidateneignung und Deployment](automatic-seven-segment-candidates.md).

Elf Originalbilder: sieben Entwicklung (vier lesbar), vier unabhängige
Testbilder (zwei lesbar, zwei ausgeschaltete Displays). Acht öffentliche,
innerhalb dieses Korpus unterscheidbare physische Geräte; drei zusätzliche
RND-Bilder mit **unbestätigter** Geräteidentität bleiben Entwicklung. Fünf
öffentliche Gerätefamilien, LCD und ein unbeleuchtetes LED-Gerät.

Das Ziel von 30 unabhängigen Testbildern ist verfehlt. Es fehlen insbesondere
beleuchtete LED-Testanzeigen, negative Werte, Dezimalpositionswechsel,
Bewegung/Verdeckung/Wiederfinden und belastbare Bedingungenvielfalt. Keine
Generalisierungs- oder Fehlerratenbehauptung. Eine korrekte Ablehnung eines
leeren Displays zählt als Ablehnung, nicht als korrekte numerische Lesung.

Mehrzeilige Bilder besitzen nur eine bewertete Zielzeile. Alle automatisch
gefundenen Regionen werden ohne Zielkoordinaten/Solltext erkannt und gelesen;
erst danach ordnet der Scorer anhand Box-IoU ≥ 0,5 dem Ziel zu. Das simuliert
eine nachträgliche Zielauswahl und beweist keine UI-Auswahl oder Nachführung.
Nicht zugeordnete Vorschläge sind keine zertifizierten Fehlalarme: auch
Beschriftungen und weitere Displays können echte Textregionen sein. Deshalb
bleiben `false_detections` und `wrong_row_selection` ausdrücklich `null`.

„Known crop“ benutzt die annotierte Zielbox und kann keine automatische
Detektion belegen. Die Produktionsbaseline benutzt, wo vorhanden, zusätzlich
das gespeicherte manuelle Profil; sie hat keinen automatischen Rasterfitter.
Für öffentliche Bilder ohne Profil bleibt sie abgelehnt. Diese unterschiedliche
Voraussetzung wird in jeder Ergebniszeile festgehalten.

## Messmethodik

Realer Raspberry Pi 5, CPU-Inferenz. Verarbeitungsdauern mit
`perf_counter_ns`/CLOCK_MONOTONIC; Datei-Frames tragen `SYNTHETIC`, unbekannte
Zeitunsicherheit ist `null`. **Keine Capture-Latenzaussage.** Ein Durchgang pro
Bild/Modus, p50/p95 sind deskriptive Stichprobenquantile, keine stabilen
Dauerlastgrenzen. OCR aller Vorschläge ist in Vollbild-Gesamtdauer/Throughput
enthalten; „selected processing“ umfasst Originalbildentzerrung, Geometrie-
versuch und OCR der nachträglich zugeordneten Region.

Jeder Kandidat/Split läuft in einem frischen Prozess. Peak-RSS enthält
Bilddekodierung, Modelle und Overlayerstellung; Tesseract-Kindprozesse werden
separat ausgewiesen. Kein Anspruch auf reine Modell-RAM-Größe oder eine
zeitgleich summierte Spitzenlast. Initialisierung ist Konstruktorzeit:
Tesseract lädt seine Gewichte bei jeder OCR-Subprozessausführung erneut, was
in der Verarbeitungsdauer enthalten ist. PP lädt beide Sessions im Konstruktor.
Die anfängliche Detektionsdauer berücksichtigt Konstruktor plus Detektor.

Die Konfidenz bleibt unkalibriert. PP verwendet einen vorab festgelegten
Mindestscore 0,90 je behaltenem Zeichen; Tesseract akzeptiert nur vollständige
numerische Ausgaben ohne Zeichenausblendung. Vorzeichen, Komma/Punkt und
Dezimalposition werden explizit verglichen; führende Dezimalpunkte wie `.000`
sind gültige Displaytexte und bleiben erhalten.

Kein Kandidat erzeugt belegte Segmenttopologie: geometrische Ziffern-Blobs
werden als unsichere Vorschläge gespeichert, `segment_quads=[]`, `ready=false`.
Ein korrekt erkannter OCR-Text wird nicht zu erfundenen Segmentbelegen.

## Durchgeführte Entwicklungsprüfungen

Die drei bestehenden Benchmarkprobleme wurden vor Benutzung geprüft und
isoliert umgangen; der alte Benchmark wurde nicht repariert. Regressionen
prüfen Dezimal-/Vorzeichenfehler, unbekannte physische Identitäten, Split-
überschneidungen, Bildhashes, korrelierte Testbilder und relative Manifestpfade.
Weitere Tests prüfen Originalkoordinaten/45°-Quads, numerische CTC-Ausgaben,
Timeout/Blank-Ablehnung ohne Wiederverwendung alter Werte und die bestehende
Tracking-/Stale-Logik der Produktion.

Unmodifizierte Tesseract-Modelle `ssd` und `ssd_int` halluzinierten auf einem
weißen Entwicklungsbild `1`; `7seg` lieferte ungültigen Text. Ein festgelegter
Kontrastguard verwirft solche Bilder. Synthetisches PP-`-12.3`/Blank-Inferenz-
Smoke und Koordinatentests sind technische Prüfungen, keine unabhängigen
Genauigkeitsmessungen. Der abgebrochene erste Lauf erreichte nur Entwicklung:
45°-Quad-Ecksortierung wurde mit realem Gegenbeispiel korrigiert, danach wurden
alle 180 PP-Entwicklungskandidaten erfolgreich entzerrt.

## Ergebnisse des eingefrorenen Laufs

[Maschinenlesbare Ergebnisse](../experiments/automatic_seven_segment/results/results.json), [Einzellesungen](../experiments/automatic_seven_segment/results/readings.jsonl), [Freeze](../experiments/automatic_seven_segment/results/frozen.json), [Overlays](../experiments/automatic_seven_segment/results/overlays/).

Tesseract-Auswahl vor Testinferenz: **7seg**. Alle Varianten hatten auf Entwicklung null korrekte Vollbildlesungen; 7seg hatte dort keine falsche Annahme. Die Auswahl ist ein Vergleichsvertreter, kein erfolgreicher Kandidat.

| Kandidat | Split / Modus | korrekt | falsch | abgelehnt | verfehlt | Detektion | Verarbeitung p50 / p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7seg | development / full_frame | 0 | 0 | 1 | 6 | 14% | 197.4 / 197.4 |
| 7seg | development / known_crop | 0 | 2 | 5 | 0 | diagnostisch | 114.2 / 372.9 |
| 7seg | heldout / full_frame | 0 | 0 | 0 | 4 | 0% | — / — |
| 7seg | heldout / known_crop | 0 | 0 | 4 | 0 | diagnostisch | 82.3 / 125.3 |
| baseline | development / full_frame | 0 | 0 | 1 | 6 | 14% | 2.1 / 2.1 |
| baseline | development / known_crop | 1 | 0 | 6 | 0 | diagnostisch | 4.6 / 36.9 |
| baseline | heldout / full_frame | 0 | 0 | 0 | 4 | 0% | — / — |
| baseline | heldout / known_crop | 0 | 0 | 4 | 0 | diagnostisch | 1.9 / 2.9 |
| ppocr | development / full_frame | 0 | 1 | 3 | 3 | 57% | 58.6 / 89.2 |
| ppocr | development / known_crop | 0 | 1 | 6 | 0 | diagnostisch | 58.1 / 106.4 |
| ppocr | heldout / full_frame | 0 | 0 | 1 | 3 | 25% | 62.9 / 62.9 |
| ppocr | heldout / known_crop | 0 | 0 | 4 | 0 | diagnostisch | 59.4 / 61.0 |
| ssd | development / full_frame | 0 | 1 | 0 | 6 | 14% | 211.1 / 211.1 |
| ssd | development / known_crop | 0 | 4 | 3 | 0 | diagnostisch | 98.0 / 380.0 |
| ssd_int | development / full_frame | 0 | 1 | 0 | 6 | 14% | 82.8 / 82.8 |
| ssd_int | development / known_crop | 1 | 4 | 2 | 0 | diagnostisch | 73.7 / 352.0 |

Null korrekte Lesungen im Test. PP liest im bekannten Casio-Ausschnitt den Text `22.0`, verwirft ihn aber unter der vorab fixierten Zeichenscore-Schwelle. Bei Fluke liest es im Ausschnitt `30` statt `.000` und lehnt ebenfalls ab. Es gab **keine falsche akzeptierte Testlesung**, aber auch keine akzeptierte korrekte Testlesung. Auf Entwicklung treten dagegen falsche Annahmen mit Dezimal-/Ziffernfehlern und Annahmen leerer Displays auf. Null falsche Testannahmen belegt hier keine Sicherheit.

| Kandidat | Initialisierung ms (Entwicklung / Test) | Peak RSS MiB max | größter Kindprozess-Peak MiB |
| --- | ---: | ---: | ---: |
| baseline | 0.0 / 0.0 | 425.3 | 0.0 |
| ssd_int | 0.1 | 426.4 | 426.4 |
| ssd | 0.1 | 426.7 | 426.7 |
| 7seg | 0.1 / 0.2 | 425.8 | 425.8 |
| ppocr | 819.1 / 802.5 | 614.0 | 0.0 |

| Testkandidat | Detektor p95 ms | Konstruktor + Detektor p95 ms | Vollbild gesamt p95 ms | Durchsatz Bilder/s |
| --- | ---: | ---: | ---: | ---: |
| 7seg | 101.4 | 101.6 | 161.3 | 11.12 |
| baseline | 112.2 | 112.2 | 112.2 | 16.57 |
| ppocr | 831.6 | 1634.1 | 2097.9 | 0.59 |

Verarbeitung ist bei fehlender Zielzuordnung nicht messbar (`null`/„—“), nicht als langsam gemessen. Der Screeninggrund `processing_time` schließt auch dieses fehlende Messergebnis ein. PP hat nur **eine** zugeordnete Testregion: ihr p95 ist damit ein Einzelwert. Geometrie ist in sämtlichen 94 Bild-/Kandidaten-/Modus-Auswertungen unbereit. Die 94 Auswertungen bleiben **elf Originalbilder, vier unabhängige Testbilder**, keine 94 unabhängigen Beispiele. Pro Gerät und Bedingung stehen die Aufschlüsselungen im JSON.

## Empfehlung und nächste Entscheidung

**Synthetisches Training gezielt untersuchen**, in einer separat beauftragten Phase für die hier beobachteten Lücken bei Display-/Zeilenlokalisierung, Segmentgeometrie und kleinen Dezimal-/Vorzeichenelementen. Vor einem belastbaren Erfolgstest ist der unabhängige reale Datensatz zu erweitern; der jetzige Satz reicht nicht zur Aussage über andere Geräte.

Kein Integrationskandidat, keine Produktionsfreigabe und keine UI-Demonstration. Das lokale ONNX-Deployment ist technisch möglich; die vorliegenden Ergebnisse rechtfertigen keinen automatischen Wechsel zu einem externen Dienst. Es wurden keine Daten hochgeladen, kein Modell trainiert und keine Cloudkosten ausgelöst.

## Abschlussprüfung

236 Tests bestanden (einschließlich zwei vorhandener Tests mit lokalen
Originalannotations-Schnappschüssen unter `var/`), Ruff 0.16.6 sauber,
JavaScript-Syntaxprüfung und `git diff --check` erfolgreich. Ohne diese
nichtversionierten Originalannotationsverzeichnisse werden zwei Bestandstests
regulär ausgelassen; die eingefrorenen Experimentdaten bleiben versioniert.

Der dokumentierte `--frozen`-Wiederholungslauf wurde ausgeführt: alle 94
Auswertungen stimmen einschließlich Texten, Ablehnungen, Zielzuordnung,
Kandidatenboxen und Geometrie identisch überein; Laufzeiten sind aus diesem
Identitätsvergleich ausgenommen.
[Verifikationsartefakt](../experiments/automatic_seven_segment/results/replay-verification.json).
