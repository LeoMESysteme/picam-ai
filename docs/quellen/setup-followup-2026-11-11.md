# Folgefehler nach Workbench-Neustart am 2026-11-11

Eine weitere neue Aufstellung ist separat als
[Fall `162902Z`](setup-new-position-2026-11-11-162902.md) gesichert.

[Zusatzarchiv](setup-followup-2026-11-11.zip),
[SHA-256](setup-followup-2026-11-11.sha256).
Ergänzt das [erste Belegpaket](setup-failures-2026-11-11.md), das unverändert
bleibt. Die Originalaufstellung wird zur statischen Wiederholung nicht benötigt.

## Zwei weitere Abbrüche

`live-20261111T161702Z` und `live-20261111T161955Z` enden beide mit:
„Vorpruefung meldet FEHLER: kanten (Zelle 7); Stabilitaetsmessung nicht gestartet“.
Jeweils vorhandenes Standbild, Fokus-/Kameraeinstellungen, Zellentexte und
Fehlerdatei sind gesichert. In beiden Versuchen ist der erste Rasterfit
`keine_startlage`, der zweite `ok`. Der Abbruch liegt anschließend in der
Kantenprüfung, getrennt von der Startsuche und der Nachführverteilung.

Am Standbild von `161702Z` mit archiviertem Code erneut berechnet: Raster
`ok`, 145 von 145 Punkten zugeordnet, Kantenprüfung `FEHLER`, Zellindex 7.
Für diese belegte Zelle beträgt `cell_occupied_step` 29,8053 gegenüber der
damaligen Fehlergrenze 20. Dies prüft eine Helligkeitsstufe im Hintergrund,
nicht ausschließlich Bildschärfe. Ob echter Reflex oder Fehlalarm, bleibt
[OQ-72](../open-questions.md#oq-72). Es wurde keine Schwelle verändert.
Zellindex 7 ist die achte Zelle und hier die letzte Ziffer von `+0.69551`.
Auch `161955Z` wurde offline wiederholt: Raster 145/145, dieselbe
Kantenablehnung für Zelle 7, `cell_occupied_step=29,7929`.

## Verzögerte Oberfläche

Bedienermeldung: Einrichtung langsamer als sonst, Statusaktualisierungen
verzögert, Kamerafeed ausdrücklich nicht betroffen. Vier lokale Abfragen
**nach** dem Abbruch `161702Z`: 172,836 / 6,562 / 1,724 / 2,326 ms.
Gemessen mit `monotonic_ns`, Zeitbasis `HOST_MONOTONIC` auf demselben Host,
Unsicherheit unbekannt. Der erste Aufruf enthält kalte Client-/Import-
Initialisierung; die Werte sind keine reinen Serverlaufzeiten. Es ist weder
eine HTTP-/Browsermessung unter Einrichtungs-Last noch eine Frame-Latenzmessung.
Die Verzögerung während der Einrichtung bleibt [OQ-73](../open-questions.md#oq-73).
Kein neuer Einrichtungslauf für diese Diagnose ausgelöst.

## Tatsächlich laufender Worktree und Fokus

Nach Nutzerfrage zusätzlich geprüft: Dienstprozess 3321848 arbeitet in
`.worktrees/bruecke-run`, Commit `08ac9b9`, mit `PYTHONPATH=src`. In einem
separaten Prozess mit demselben Interpreter, Arbeitsordner und derselben
Umgebung aufgelöste Importpfade zeigen tatsächlich auf diesen Worktree.
Es handelt sich um einen älteren Betriebsstand; neuere Änderungen aus
`feat/bruecke-ui` auf `8335abf` sind nicht ausgerollt. Ein Neustart des
vorhandenen Dienstes hat kein Update ausgeführt. Andere Worktrees enthalten
zusätzlich uncommittete Arbeit und wurden nicht pauschal als Betriebsstand
übernommen.

Die Dateien `live/setup.py`, `focus_sweep.py`, `frames/uvc_source.py` und
`live/camera.py` sind zwischen `bruecke-run`, `bruecke-ui`, `bruecke-takt`
und `bruecke-ux` byte-identisch. Historische Fokuskorrekturen R13-9/R13-12
sind bereits Vorfahren von `08ac9b9`. Daher ist nicht belegt, dass ein
Wechsel auf einen dieser Zweige den gemeldeten Fokusfehler beseitigt.

Bedienermeldung: zunächst scharfes Bild während der Fokussuche, danach wieder
unscharf. `161955Z` protokolliert Ziel 60, beste Schärfe 734,45 und Endprüfung
727,41, mit Anfahrt von unten. Spätere Regler-Rückmeldung bleibt 60,
Autofokus aus. Numerischer Rücksprung und optischer Rückfall sind zu
unterscheiden. Im Code folgt auf die Endprüfung ein Kameraneustart mit
erneutem Setzen der Regler. Dessen Einfluss auf die optische Endlage bleibt
eine Hypothese, [OQ-74](../open-questions.md#oq-74). Bilder vor und nach
dieser Grenze wurden nicht separat gespeichert und können nicht nachträglich
erfunden werden.

## Archivinhalt und Wiederholung

Das ZIP enthält `setup-followup-20261111/`: beide Setup-Verzeichnisse,
Status-/Antwortzeitdaten, Nutzerberichte, Worktree-/Dateihashes,
Importpfadprüfung und Quellcode-/Umgebungskopie aus dem ersten Paket.
`replay-results-161702.jsonl` und `replay-results-161955.jsonl` sind die
tatsächlich ausgeführten Wiederholungen.
Originale werden durch SHA-256 und Manifest gebunden. Frühere Suchbilder
und Rohbilder des Mittelbildstapels fehlen wie im ersten Paket.

```bash
sha256sum -c docs/quellen/setup-followup-2026-11-11.sha256
./.venv/bin/python -m zipfile -e docs/quellen/setup-followup-2026-11-11.zip var/replay-followup
./.venv/bin/python var/replay-followup/setup-followup-20261111/live-20261111T161702Z/replay.py
./.venv/bin/python var/replay-followup/setup-followup-20261111/live-20261111T161702Z/replay.py --case live-20261111T161955Z
```

In einen neuen Zielordner entpacken. Das Rezept greift ausschließlich auf
Dateien zu, entpackt den historischen Code temporär und zeigt Rasterfit und
Vorprüfungen. Mit `--source /pfad/zum/checkout` ist ein späterer Vergleich
möglich. Eine geänderte Rückgabe ist keine Messfreigabe. Keine neue Kamera-
oder Browseraufnahme und kein Code-/Dienstwechsel für diese Diagnose.
