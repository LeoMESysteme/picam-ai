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

Wird aus den Implementierungs- und Reviewberichten vor Übergabe ergänzt.
Offene Gates und Teilaufgaben bleiben im Hauptplan/status.md sichtbar.
