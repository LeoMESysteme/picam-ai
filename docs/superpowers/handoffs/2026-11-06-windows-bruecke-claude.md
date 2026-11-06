# Übergabe an Claude: Windows-Brücke und Workbench-Anbindung

Stand 06.11.2026: technische Umsetzung läuft, dieses Dokument wird vor der
Übergabe mit Commit-/Prüfständen ergänzt. Noch keine Nachricht an einen
anderen Chat versandt.

## Auftrag und Aufteilung

Leonhard hat Spec und Plan freigegeben. Codex übernimmt möglichst viel
Backend, Paketierung und testbare Vorarbeit, selbst bzw. mit Subagents.
**Die EXE-Oberfläche sowie alle sichtbaren Workbench-Anpassungen bleiben
Claude vorbehalten.** Dazu gehören Verbindungsanweisungen je Methode,
Auswahl/Verknüpfung und die verständliche Anzeige der Bereitschaft.

[Spec](../specs/2026-11-06-windows-bruecke-design.md),
[Hauptplan](../plans/2026-11-06-windows-bruecke.md),
[Nachweise](../plans/2026-11-06-windows-bruecke-nachweise.md),
[Pi/Protokoll](../plans/2026-11-06-windows-bruecke-pi.md),
[Windows](../plans/2026-11-06-windows-bruecke-windows.md).

Technischer Arbeitsstand: `codex/windows-bridge-core`, neuer verwalteter
Worktree. Basis `ea29e44`; Änderungen des laufenden Redesign-Worktrees werden
nicht übernommen oder zurückgesetzt. Vor Integration Branch-Diff prüfen.

## Was Claude auf der Oberfläche darstellen muss

* Standardanwender kommen ohne Terminal von Installer/Verbindungsprofil zur
  gewählten Verbindung. Fehlendes USB, Treiber-/Portproblem, fehlende Pi-
  Antwort, falsche Identität und noch nicht gestarteter Lauf sind verschiedene
  Zustände und brauchen verschiedene nächste Aktionen.
* Netzwerk unterstützt LAN/Host-/Adressfallback und optional Tailscale;
  fremde Pi nicht wegen gleicher Namen/IP übernehmen. Ein Pi ohne Netzwerk
  benötigt Erstkonfiguration (OQ-49); kein Suchtrick ersetzt diese.
* Workbench liefert das Pi-Profil; Windows kennt die lokalen COM-Ports und
  erzeugt erst dort eine GSVmulti-Datei aus einer belegten Vorlage.
* COM-Weitergabe ist kein belegter GSVmulti-Empfang, technische Bereitschaft
  ist keine Messfreigabe. Kein pauschales Grün und keine versteckte DUT-
  Entsperrung oder Testdaten in einer echten Messung.
* Laufende Konfiguration schreibgeschützt, Minimieren hält Brücke aktiv;
  tatsächliches Beenden ausdrücklich bestätigen. Keine stillen Transport-
  oder Gerätewechsel.

## Harte externe Nachweise

Eine Linux-Unit-Suite beweist weder Windows-Paketierung noch Treiberstart
oder Sessionimport. N1: echte VM ohne Python/mit altem Python.
N2: tatsächliche Treiber-/VCOM-/Schutzstatus- und Übertragungsprüfung.
N3: belegte Sessionfelder und tatsächlicher GSVmulti-Roundtrip. Die bestehende
historische UCF ist eine funktionierende Kanalvorlage, aber kein Beleg für
eine automatisch geänderte Port-/Vollsessionkonfiguration. OQ-53 bleibt
maßgeblich. Vor diesen Nachweisen keine fertige EXE oder Produktabnahme melden.

GSVmulti-Brücken-DUT-Ausgabe bleibt strukturell gesperrt; Nutzerentscheidung
für die getrennte direkte UART-Ausgabe gilt unverändert. Reale Hardware,
Systeminstallation, Veröffentlichung und Merge nicht aus einer bloßen
Codeprüfung ableiten.

## Technischer Lieferstand und Prüfungen

Bisher versioniert, jeweils nach Taskreview:

| Teil | Lieferstand | Nachweisgrenze |
| --- | --- | --- |
| P1 | Strikter v2-Codec, Profile, kanonische UART-Signaturbytes, begrenzter OutputState | 70 relevante Tests; Auth/Hub separat |
| N1 | Build-/Probe-/Hashfreigabe unter windows/bridge | 79 Tests inklusive Bestand, 1 echter Windows-Skip; keine qualifizierten Locks/EXE |
| N2 | PnP-/USB-Auswahl und injizierbare VCOM-Verwaltung | 48 Tests; echter Treiberprovider unverifiziert und gesperrt |
| N3 | Gepinnte UCF-/TXT-Originale, Herkunftsinspektion | 17 Tests; Versionsbindung/Roundtrip fehlen, Export gesperrt |
| P2 | Geräteidentität, Zertifikat/Signatur, Kopplung und lokale CLI | 26 gezielte Tests, zusätzlich vorher 142/2skip mit Workbench; HTTP folgt |
| W3 | Fortsetzbare Installer-/Updateverträge, begrenzter Helfer, internes Probe-Setup | 47 fokussierte Tests nach Reviewkorrektur; native Anbieter, Signierung und Windows-Gates fehlen |

P2 ist auf `6e9e2e6` abgeschlossen. Öffentliche Verifikation liegt in
`dispread.bridge.identity`; Pi-only Datei-/Hardwareoperationen werden beim
Windows-Import nicht ausgeführt. Einmalangebote sind 256 Bit, höchstens
300 Sekunden gültig, atomar einmalig und client-/transportgebunden.

Lokale technische Vorbereitung (keine Messung):

```bash
./.venv/bin/dispread bridge identity --directory var/workbench/bridge --provision
./.venv/bin/dispread bridge export-profile --directory var/workbench/bridge \
  --output pi-profil.json --name Labor-Pi --pair --transport uart
./.venv/bin/dispread bridge revoke --directory var/workbench/bridge CLIENT_ID
```

Nur auf dem tatsächlich einzurichtenden Pi und unter dessen autorisiertem
OS-Konto ausführen. `--provision` ersetzt bestehende Identitäten nicht.
Das Paarungsprofil rechtzeitig übertragen; beim Ablauf neues Angebot
erzeugen. Eine bestehende Workbench-TLS-Konfiguration bleibt erhalten;
explizite Dienstaktivierung wird im folgenden P3 ergänzt.

Weitere technische Teile und der gesamte Branchreview folgen vor endgültiger
Übergabe. Keine vorläufige Tabelle als Gesamtfertigmeldung verwenden.
Offene Gates und Teilaufgaben bleiben im Hauptplan/status.md sichtbar.

Release-Key/-Kanal und Schutz gegen alte signierte Versionen bleiben in
[OQ-65](../../open-questions.md#oq-65) offen. Keine Testschlüssel übernehmen.
W3 liefert ausdrücklich keinen nativen UAC-Launcher/Deploymentanbieter.
