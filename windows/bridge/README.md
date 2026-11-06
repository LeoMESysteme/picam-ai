# Windows-Laufzeitprobe

Stand 2026-11-06: technische Grundlage für N1, **kein bestandener Windows-
Nachweis**. Dieses Verzeichnis enthält eine Konsolenprobe und ein Rezept
für ein internes, unsigniertes PyInstaller-Ordnerpaket. Produkt-GUI und
Produkt-Setup-EXE fehlen weiterhin; ein internes Probe-Setup-Rezept steht unten. DUT-Ausgabe bleibt im bestehenden Kern gesperrt.

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


## Installer-/Update-Verträge W3

`install.py` hält den Zustand einer Portpaar-Einrichtung mit atomarem Austausch,
OS-Dateisperre und einem fortlaufenden Audit fest. `InstallRequest` enthält nur
das ausdrücklich gewählte `PortPair` und einen Abbruchwunsch. Geräteinventar und
`VcomAdapter` werden injiziert; ohne qualifizierten N2-Provider bleibt das Ergebnis
`unverified`. `Installer.ensure_components(request, devices, vcom)` und
`Installer.resume_install(state_path, devices=..., vcom=...)` verwenden dieselbe
Zustandsdatei. Auch die Modulfunktion `resume_install` ist verfügbar. Die Pfade
kommen aus der lokalen Anwendung, niemals aus einem Pi-Verbindungsprofil.

Ein vor einem Prozessabbruch begonnenes Erstellen wird vor einer Wiederholung
mit dem gespeicherten Inventar abgeglichen; genau ein neu gefundenes eigenes
Paar wird wiederverwendet, mehrere erfordern Auswahl. Neustart, UAC-Verweigerung
und Cancel behalten den Zustand. `previous_ready` bezeichnet ausschließlich ein
historisches, zuletzt geprüftes Paar; der aktuelle `result` wird erneut ermittelt.
`ready` bestätigt hier nur den N2-Portpaar-Selbsttest, weder Pi-Verbindung noch
USB-Treiberinstallation, App-Installation oder GSVmulti-Übernahme. Für einen
USB-Treiber existiert noch kein freigegebenes Paket/Installationsverfahren.

`admin_helper.py` ist eine beschränkte Provider-Grenze, **kein ausführbarer
UAC-Starter**. Nur `inventory`, `create_pair`, `repair_owned_pair` und
`remove_unused_owned_pair` sind erlaubt. Die beiden gezielten Aktionen nehmen
nur eine Paar-ID an; Kommandos, URLs und Dateipfade sind verboten. Aktuelles
Eigentum und freie Nutzung werden neu geprüft. Fremde und belegte/ungeprüfte
Paare sowie bestehende Audits bleiben erhalten. Der Provider muss die letzte
Eigentums-/Nutzungsprüfung mit seiner Mutation atomar ausführen. Entfernen ist
als zusätzliche Provider-Methode noch unqualifiziert; es gibt keinen geratenen
Treiberaufruf. Audit-Schreibfehler verhindern jede nachfolgende Mutation.

`updates.py` prüft maximal 64 KiB große Manifeste nach
`packaging/release-manifest.schema.json`: exakte Felder, keine doppelten
JSON-Schlüssel, festes Windows-Ziel, Versions-/Commitform, eindeutige Artefakte,
begrenzt große Dateien und vollständige SHA-256-Werte. Es gibt **keinen
Produkt-Vertrauensschlüssel und keinen vorgewählten Downloadhost**. Aufrufer
müssen einen `TrustedReleaseKey` und feste HTTPS-Ursprünge provisionieren.
Der Standardprüfer verwendet Ed25519 aus `cryptography`; ein qualifizierter
Prüfer kann injiziert werden. Die Prüfung muss bei Fehlern werfen und bei
Erfolg `None` liefern. Testschlüssel existieren ausschließlich in Tests.

Signiert wird das JSON-Objekt ohne `signature`, mit sortierten Schlüsseln,
kompakten Trennzeichen und ASCII-Escapes (Python: `sort_keys=True`,
`separators=(',', ':')`, `ensure_ascii=True`). Der Signaturblock nennt
`algorithm=ed25519`, die lokal bekannte `key_id` und kanonisches Base64 der
64 Signaturbytes. Beim Installationsaufruf wird das Originalmanifest erneut
geprüft; ein selbst konstruiertes `ReleaseInfo` umgeht diese Prüfung nicht.

Downloads verwenden HTTPS mit normalem Proxyzugang und begrenzten Lesegrößen;
Redirects, Quellenwechsel, Größengrenzen und Hashfehler werden abgelehnt.
Teilbytes bleiben als `.partial` erkennbar und werden beim erneuten Versuch
neu geladen. Erst vollständig geprüfte Bytes heißen `.verified`; auch diese
werden beim Wiederanlauf erneut gehasht. Knapper Platz, Downloadabbruch und
Cancel erhalten einen fortsetzbaren Zustand. Aktive Ausgabe blockiert den
Aufruf vor Download und Änderungen. Cache/Zustandsverzeichnisse und die
Ausgabesperre werden vom lokalen Programm festgelegt, nie durch das Manifest.

Ein injizierter `DeploymentBackend` muss alte Version/Konfiguration sichern,
Konfigurationen als versionierte Kopie migrieren, innerhalb seiner nativen
Privileggrenze Hash/Signatur und ruhende Ausgabe erneut prüfen und erst nach
aktueller Prüfung `ready` melden. `backup`, `prepare`, `activate`, `rollback`
und `verify_installed` sind die Adaptergrenze. Nach Prozessabbruch oder
Neustart während Aktivierung wird der gesicherte Stand vor erneutem Versuch
zurückgeholt; fehlgeschlagene Rückkehr meldet `recovery_required`.
**Dieser native Deployer fehlt weiterhin.** Portable Tests mit einem lokalen
Dateisystem-Doppel belegen Zustands-/Rollbackpolitik, keine erfolgreiche
Windows-Installation. Weder Anwendung noch Treiber werden hier signiert,
installiert, entfernt oder extern veröffentlicht.

## Optionales internes Probe-Setup

`packaging/setup.iss` verpackt ausschließlich die bereits geprüfte N1-
Konsolenprobe einschließlich ihres unveränderten, unsignierten Baumanifests.
Es enthält keine Produktoberfläche, Treiberaktionen, Dateizuordnungen oder
privilegierten Helfer. Standard-Inno-Dialoge sind reine Paketierungsfunktion.
Die Installation wäre nach Program Files erhöht; die Probe wird anschließend
vom normalen Benutzer separat gestartet. Setup startet sie nicht erhöht und
fasst Benutzerkonfiguration/Audits nicht an. Es wird nur Windows 11 x64
zugelassen; ARM bleibt ausgeschlossen.

Nach den unverändert verpflichtenden N1-Qualifikationsschritten kann das
interne Rezept mit ausdrücklich gewähltem, lokal qualifiziertem Inno-Compiler
zusätzlich gebaut werden (noch keine hier geprüfte Inno-Version):

```powershell
.\windows\bridge\build.ps1 `
  -BuildPython 'C:\BuildTools\Python313\python.exe' `
  -VerifiedInputs 'C:\BridgeEvidence\verification.json' `
  -BuildInternalProbeSetup `
  -InnoCompiler 'C:\BuildTools\Inno Setup\ISCC.exe'
```

Die Ausgabe bleibt unter `.build/<ID>/internal-probe-setup/`; Name und
`internal-setup-build.json` kennzeichnen sie als unsignierte, noch nicht auf
Windows abgenommene Probe. Das Protokoll enthält Setup-/Compilerhash,
Compilerdateiversion, Rezepthash, Quellcommit und Hash des eingebetteten N1-Manifests.
Rezept, Compiler und Manifest werden vor/nach der Kompilierung verglichen;
auch das vollständige N1-Paketinventar wird erneut gegen dessen Hashliste geprüft.
Es entsteht kein signiertes Release-Manifest. Originale Windows-Belege für
frische VM, UAC-Verweigerung, Reboot und zweimalige Reparatur fehlen;
Schlüssel, Hosting, echte App und freigegebener Treiber bleiben externe Gates.
Ohne bereitgestellten Windows-Runner wird keine Workflowdatei angelegt.

Portable W3-Prüfung, ohne Installation neuer Pakete in der Pi-venv:

```bash
PYTHONPATH=src:windows/bridge/src ./.venv/bin/python -m pytest -q windows/bridge/tests/test_install.py windows/bridge/tests/test_updates.py
```

Paketierungsreferenz: [Inno-Architekturgrenzen](https://jrsoftware.org/ishelp/topic_archidentifiers.htm),
[Admin-Modus](https://jrsoftware.org/ishelp/topic_admininstallmode.htm).

## Oberfläche (`ui/`, nur Entwurf)

`src/dispread_bridge_app/ui/` enthält die Qt-Widgets-Oberfläche nach dem Mock unter
`docs/superpowers/specs/2026-11-06-windows-bruecke-mock/`; sie hängt nur am `ControllerPort`
(`ui/port.py`). `python -m dispread_bridge_app.main --demo-ui [--state=B3]` startet sie mit dem
`FakeController` (Zustände des Mocks, synthetisch) zur Sichtprüfung auf Windows. Tests offscreen:
`QT_QPA_PLATFORM=offscreen PYTHONPATH=src:../../src python -m pytest -q tests/test_ui*.py`.
Nur unter Linux geprüft, keine Windows-Abnahme.

## Interner Testbuild (GUI)

Ein Befehl auf einem Windows-11-x64-PC (Python ≥ 3.13 x64, ausdrücklich angegeben, kein PATH-Suchen):

```powershell
.\windows\bridge\build-test.ps1 -Python 'C:\Python313\python.exe' [-Inno 'C:\...\ISCC.exe']
```

Es entsteht unter `windows/bridge/dist-test/` ein ZIP (`GSVmulti-Bruecke-<version>-<commit12>-test.zip`)
und mit `-Inno` ein Benutzer-Setup ohne Administratorrechte (`packaging/setup-app.iss`). Die EXE
wird einmal im Selbsttest (`--self-test-out`, Importtest ohne Fenster) gestartet; schlägt er fehl,
entsteht kein Paket. **Unsigniert, unqualifiziert, nur interner Test.** Das ist nicht der Weg zu
einem Produkt: `build.ps1` mit `packaging/bridge.spec` (Hash-Locks, Konsolenprobe, N1-Nachweis)
bleibt unverändert der einzige qualifizierte Bauweg. Auf dem Pi (Linux) lässt sich nichts davon
bauen; hier laufen nur statische Tests (`tests/test_packaging_app.py`). Ablauf des ersten
Gesamttests: [TESTLAUF.md](TESTLAUF.md).
