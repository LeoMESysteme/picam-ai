# GSVmulti: Archivbelege, noch keine freigegebene Sessionvorlage

Stand: 2026-11-06. Die Dateien sind **unveränderte Originalbytes** aus
`docs/quellen/gsvmulti-validation-2026-11-04.zip`, nur lokal umbenannt.
`manifest.json` hält Archivpfad, Mitgliedspfad und SHA-256 jedes Originals
fest. Die Originaldateien enthalten keine privaten Rechnerpfade; eine
inhaltliche Bereinigung war deshalb nicht erforderlich. CRLF und fehlender
Schlusszeilenumbruch bleiben erhalten.

| Lokale Datei | Historischer Beleg |
| --- | --- |
| `uart-demo-11.ucf` | Kanaldatei des direkten UART-Demos vom 04.11.; `Separator = 256` |
| `uart-demo-14.ucf` | Spätere Kanaldatei; `Separator = 0` |
| `uart-demo-11-receiver.txt` | Originale GSVmulti-Textaufzeichnung zum ersten Demo |

Die `.ucf`-Dateien enthalten unter anderem `ComNr`, `ComNo`, `Unit`,
`Frequency`, `Prefix` und `Separator`. Ihre Existenz belegt weder die
Wirkung einer Änderung noch ein allgemeines Sessionformat. Insbesondere
ist `Separator` **kein belegtes universelles Filterbit** (OQ-53).
Eine Skalierung steht nicht in diesen Kanaldateien. Das TXT enthält eine
`Scaling`-Kopfzeile; diese ist kein Beleg für eine editierbare UCF-Skalierung.
Die Textaufzeichnung dient als Originalquelle für einen späteren
Empfangsprüfer; hier wird kein neuer Empfangstest daraus abgeleitet.

Die genaue zur Vorlage gehörige GSVmulti-/Dateiversion und ein kontrollierter
Speichern-/Wiederöffnen-/Empfangsnachweis fehlen. Deshalb stehen
`gsv_version` auf `null`, `allowed_fields` auf `[]` und
`roundtrip_verified` auf `false`. **Automatischer Export bleibt gesperrt.**
Die Manifest-Schemaversion bezeichnet nur diesen Herkunftskatalog und
behauptet keine GSVmulti-Dateiformatversion.

Die Inspektion erkennt ausschließlich die zwei SHA-256-gepinnten Originale.
Sie liest keine externen Freigabeangaben aus einem Pi-Profil und parst kein
allgemeines UCF. `validate_manifest` prüft den Katalog gegen den im Code
festgehaltenen Stand und die lokalen Originalbytes; ein geändertes Manifest
kann keine neue Version, kein Feld und keinen Roundtrip freigeben.

```bash
PYTHONPATH=src:windows/bridge/src ./.venv/bin/python \
  windows/bridge/probes/inspect_session.py \
  tests/fixtures/gsvmulti/session-templates/uart-demo-11.ucf
```

Die Probe verändert keine Datei und öffnet keinen Port. Exitcode **2** heißt:
bekanntes Original, Export blockiert; Exitcode **1** heißt: unbekannte oder
nicht lesbare Datei. Die JSON-Ausgabe enthält `provisional=true` und
`time_claim=false`. Ein erfolgreicher Export-Exitcode existiert noch nicht.

Für Gate N3 weiterhin erforderlich: kontrollierte Originalpaare für Port,
Einheit, Skalierung, Rate, Präfix und Zahlenfilter, zugehörige UI-Werte nach
Wiederöffnen, genaue EXE-/Bibliotheks-/Dateiversionen sowie neuer separater
Demoempfang nach kontrolliertem Portwechsel. Die bisherige Nutzersession
muss dabei erhalten bleiben. Die historischen Originale ersetzen diesen
Windows-Nachweis nicht.
