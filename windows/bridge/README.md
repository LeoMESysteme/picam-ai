# Windows-Laufzeitprobe

Stand 2026-11-06: technische Grundlage für N1, **kein bestandener Windows-
Nachweis**. Dieses Verzeichnis enthält eine Konsolenprobe und ein Rezept
für ein internes, unsigniertes PyInstaller-Ordnerpaket. Produkt-GUI und
Setup-EXE fehlen absichtlich. DUT-Ausgabe bleibt im bestehenden Kern gesperrt.

Die Probe importiert `dispread.gsv_bridge`, pySerial und PySide6, erzeugt
eine verborgene `QApplication` und beendet sich mit einem JSON-Bericht.
Sie öffnet kein COM-Gerät, keinen Netzwerkkanal und kein Fenster. Nur eine
gebündelte Windows-x64-Laufzeit mit dem eigenen Qt-Windows-Plugin besteht
den Selbsttest. `provisional=true`, `time_claim=false` gelten auch hier.

## Getrennte Umgebungen

Auf dem Pi bleibt die vorhandene Projekt-`.venv` mit
`--system-site-packages` erhalten; hier keine Qt-/PyInstaller-Pakete
installieren. Windows-Builds benötigen Windows 11 x64 und einen ausdrücklich
gewählten Python-Interpreter >=3.13 x64. `build.ps1` sucht weder `python`
noch `py.exe` über PATH. Bestehendes Python, PATH und Visual Studio werden
nicht verändert. Jede Ausführung erstellt eine neue isolierte Windows-
Build-venv unter `.build/<ID>/.build-venv`.

## Noch fehlende Build-Eingaben

`requirements-runtime.in` und `requirements-build.in` sind ausschließlich
Auflösungsaufträge. Es gibt noch keine tatsächlich Windows-geprüfte
Python-/Qt-/PyInstaller-Kombination. Deshalb liegen **keine erfundenen
Lockdateien oder Hashes** bei. Das Buildskript verweigert den Build ohne:

1. `requirements-runtime.lock`: vollständiger Laufzeitgraph als exakte
   `Paket==Version --hash=sha256:...`-Einträge.
2. `requirements-build.lock`: vollständiger Baugraph einschließlich derselben
   Laufzeitpakete, PyInstaller, pytest und Werkzeugen aus der `.in`-Datei.
   Die Laufzeit-Einträge müssen mit Version und Hashliste identisch sein.
3. Einen lokal geprüften Verifikationsdatensatz mit exakt passender
   Interpreterversion und Hashes beider Lockdateien sowie vorhandenen
   Originalbelegen des erfolgreichen Windows-Kandidatenbaus und beider
   VM-Prüfungen. Dieser Datensatz ist eine lokale Prüfentscheidung;
   er ersetzt keine vertrauenswürdige Signatur oder Release-Freigabe.

Die erste Qualifikation geschieht in einer **separaten, wegwerfbaren
Windows-Kandidatenumgebung**, außerhalb des freigegebenen Buildpfads:
Abhängigkeiten für den gewählten Interpreter auflösen, vollständige
Wheeldateien aus der festgelegten Quelle sichern, Pins und SHA-256 daraus
erzeugen, deren Herkunft prüfen, `packaging/bridge.spec` mit PyInstaller
bauen und auf beiden VM-Zuständen testen. Ausgaben, Versionen und originale
Berichte sichern. Erst nach erfolgreicher Prüfung konkrete Locks und den
Verifikationsdatensatz übernehmen. `build.ps1` hat keinen Schalter, der
Hashprüfung oder fehlende Windows-Belege umgeht.

Struktur des extern bereitzustellenden Datensatzes; die Platzhalter sind
ausdrücklich keine gültigen Eingaben:

```json
{
  "schema_version": 1,
  "status": "windows_probe_verified",
  "target": "windows11-x64",
  "python_version": "EXAKTE_GETESTETE_VERSION",
  "verified_by": "PRUEFENDE_PERSON_UND_DATUM",
  "locks": {
    "requirements-build.lock": "SHA256_DER_DATEI",
    "requirements-runtime.lock": "SHA256_DER_DATEI"
  },
  "evidence": [
    {"path": "candidate-build.txt", "sha256": "SHA256_DES_ORIGINALS"},
    {"path": "vm-no-python.json", "sha256": "SHA256_DES_ORIGINALS"},
    {"path": "vm-python37-unchanged.json", "sha256": "SHA256_DES_ORIGINALS"}
  ]
}
```

Belegpfade sind relativ zum Datensatz. Die technische Prüfung prüft Bytes,
Ziel, Version und Freigabestatus; die inhaltliche Beurteilung der externen
Windows-Belege bleibt bei der prüfenden Person. Die Platzhalter lassen sich
nicht durch bloßes Vorhandensein der Dateien freigeben.

## Wiederholbarer Bau nach Qualifikation

Im Windows-Checkout, mit ausdrücklich angegebenen vorhandenen Pfaden:

```powershell
.\windows\bridge\build.ps1 `
  -BuildPython 'C:\BuildTools\Python313\python.exe' `
  -VerifiedInputs 'C:\BridgeEvidence\verification.json' `
  -SelfTest
```

Das Skript prüft zuerst Host, Interpreter, Locks und Belegoriginale. Es lädt
nur Wheels von `https://pypi.org/simple` mit pip `--require-hashes` und
`--only-binary=:all:` und installiert danach ausschließlich aus dem lokalen
Wheelverzeichnis. pip-Konfiguration wird für Kindprozesse mit
`PIP_CONFIG_FILE=NUL` deaktiviert; die vorherige Umgebungsvariable wird
anschließend wiederhergestellt. Downloads mit falschem Hash und fehlende Abhängigkeiten
brechen ab. `pip check` und ein Vergleich aller installierten Versionen mit
dem freigegebenen Baugraphen folgen vor PyInstaller.

Die Paketprobe läuft anschließend als eigener Prozess mit einem PATH aus
Windows-Systemverzeichnissen und ohne Python-/Qt-Umgebungsüberschreibungen.
`-SelfTest` ist als ausdrücklicher Aufruf zulässig; der Selbsttest ist auch
ohne diesen Schalter immer Pflicht. Ein fehlender Interpreter im Paket,
ein fehlendes Qt-Plugin oder ein fehlgeschlagener Selbsttest sperren die
Ausgabe. Python-/Qt-Versionen sind erst nach einem echten Bau belegt.

`dist/dispread-bridge-<Commit>-<ID>/build-manifest.json` enthält Quellcommit,
Quellhashes, installierte Paketversionen, Lock- und Verifikationshashes sowie
SHA-256 für jede Paketdatei außer dem Manifest selbst. Quellhashes werden
vor dem Bau aufgenommen und vor Abschluss erneut verglichen; Änderungen
während des Baus sperren die Ausgabe. Quellhashes bezeichnen die konkreten
Eingabebytes und behaupten keinen sauberen Git-Arbeitsstand.

Originale des Verifikationsdatensatzes, der Locks und der Windows-Belege
liegen unter `build-evidence/`; der aktuelle Probebericht liegt daneben.
Der geprüfte Verifikationsdatensatz wird als unveränderter Byte-Schnappschuss
gesichert. Die Hashliste der tatsächlichen Beleg- und Lockkopien muss vor
dem Abschluss zu diesem Datensatz passen; Änderungen sperren die Ausgabe.
Nach erneuter Inventar-/Hashprüfung wird das vollständige Verzeichnis auf
demselben Dateisystem umbenannt. Bestehende Pakete werden nie ersetzt.
Abbrüche bleiben als `.partial-*`/`.verified-stage-*` sowie unter `.build/`
erkennbar. Ein fehlgeschlagener Download oder Bau wird mit einer neuen ID
erneut gestartet; es gibt keinen unkontrollierten Fortsetzungsmodus.

Das Manifest ist unsigniert (`release_signed=false`). Es schützt hier die
lokale Vollständigkeitsprüfung; Herkunftsnachweis und externe Veröffentlichung
benötigen den separat freizugebenden Signierungs-/Releaseprozess.

## Windows-Abnahme N1

Auf dem Buildhost nach dem erfolgreichen Bau die Tests mit dessen eigener
Build-venv ausführen. `DISPREAD_FROZEN_PROBE` muss auf die tatsächliche EXE
zeigen; fehlt sie auf Windows, ist der Test **rot**:

```powershell
$env:DISPREAD_FROZEN_PROBE = 'C:\Checkout\windows\bridge\dist\PAKET\dispread-bridge-probe.exe'
& 'C:\Checkout\windows\bridge\.build\ID\.build-venv\Scripts\python.exe' `
  -m pytest -q windows/bridge/tests/test_packaging.py
```

Das vollständige Ordnerpaket zusätzlich auf zwei saubere Windows-11-x64-
VM-Zustände kopieren: ohne Python und neben einem unveränderten Python 3.7.
Auf den Ziel-VMs ist weder pytest noch Build-Python erforderlich:

```powershell
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
Remove-Item Env:PYTHONHOME, Env:PYTHONPATH, Env:QT_PLUGIN_PATH, Env:QT_QPA_PLATFORM, Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
& 'C:\Probe\dispread-bridge-probe.exe' --self-test
$LASTEXITCODE
```

Erwartet: Exit 0, ein JSON-Objekt mit `ok=true`, `bridge_import_ok=true`,
`system_python_used=false`, `qt_platform="windows"`,
`qt_plugin_bundled=true`; keine Kamera-/CV-/PAM-Importe im Modulinventar.
Installation/Version/PATH des Python 3.7 vor und nach der Probe vergleichen
und Originalberichte sichern. Das lokale Linux-Ergebnis ersetzt keinen
dieser Nachweise. Tatsächliche Befehle/Versionen/Ergebnisse anschließend
nach `docs/VALIDATION.md` und `docs/lab_journal.md` übernehmen.

## Lokale Vertragsprüfung

Aus dem Repository, mit der bestehenden Pi-venv und ohne neue Pakete:

```bash
PYTHONPATH=src ./.venv/bin/python -m pytest -q windows/bridge/tests/test_packaging.py
```

Der echte EXE-Test wird ausschließlich auf Nicht-Windows übersprungen.
Der leichte Quellimport läuft mit explizitem Repository-Pfad in einem
isolierten Kindinterpreter und benötigt weder `PYTHONPATH` noch eine
Installation des Repository-Pakets in der Build-venv.
Die übrigen Tests prüfen Fehlerfälle und synthetische Bauartefakte;
deren Fixture-Hashes und Berichte sind keine echten Windows-Belege.

Primärquellen zum Rezept:
[PyInstaller-Spec und Ordnerpaket](https://pyinstaller.org/en/stable/spec-files.html),
[Qt/PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html),
[pip: Hashprüfung und ausschließlich Wheels](https://pip.pypa.io/en/stable/topics/secure-installs/).
