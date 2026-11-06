# Erster Testlauf: Pi ↔ Windows-App ↔ GSVmulti

Interner Testlauf, kein Freigabeverfahren. Er zeigt, ob die Kette technisch
zusammenpasst. **Es werden keine Messwerte an GSVmulti übergeben**: die
DUT-Ausgabe bleibt gesperrt. Nichts in dieser Anleitung wurde bisher auf einem
Windows-PC ausgeführt.

**Stand der App:** Oberfläche und AppController sind vorhanden. Geprüft wurde
unter Linux (offscreen, lokaler TLS-Pi mit Fake-COM); auf Windows ist nichts
davon geprüft, ebenso wenig echte COM-Ports und GSVmulti.

## A. Pi vorbereiten (Entwickler, jeder Schritt mit Freigabe)

Alles in diesem Abschnitt greift in den laufenden Pi ein und wird **nur mit
Freigabe von Leonhard** ausgeführt, nie nebenbei. Kein Reboot, keine
Kernel-Änderung nötig.

**Stand (06.11. 18:04, mit Freigabe von Leonhard bereits erledigt):** Der Pi ist
vorbereitet. Die Schritte 1 bis 3 sind nur nötig, falls neu aufgesetzt wird.

* Identität liegt in `/home/me-systeme/picam-ai/var/workbench/bridge`,
  `pi_id` 565e3468-d378-4380-9753-891abc563c7c, Zertifikat-SHA-256
  `f87b34f0c71637709df5a4660586aad8e90956d5fe017cfac566925b29c1217e`
  (dieser Fingerabdruck wird in Abschnitt C verglichen).
* Die Werkbank läuft als User-Unit `dispread-werkbank-bruecke` (systemd-run) aus
  `/home/me-systeme/picam-ai/.worktrees/bruecke-run` (detached, `feat/bruecke-ui`):
  `serve --host 100.122.154.35 --port 8082 … --socket /tmp/dispread-werkbank-bruecke/control.sock --bridge-directory …/var/workbench/bridge --bridge-endpoint https://100.122.154.35:8082`.
  Die alte Unit `dispread-werkbank-t13` ist gestoppt.
* Der Browser fragt wegen des neuen Zertifikats einmal neu; der Fingerabdruck im
  Browser muss dem Wert oben entsprechen.
* Status prüfen (Socket-Verzeichnis muss Modus 0700 haben):
  `PYTHONPATH=src ./.venv/bin/python -m dispread.workbench.cli bridge status --socket /tmp/dispread-werkbank-bruecke/control.sock`

Nur falls neu aufgesetzt wird (jeder Schritt *mit Freigabe*; nie während eines
laufenden Aufnahmelaufs, Werkbank erst neu starten, wenn die Diagnosekopie aus
/dev/shm fertig ist):

1. **Branch ausrollen** und den Dienst neu starten.
2. **Identität anlegen** (nur wenn `var/workbench/bridge` fehlt):
   `PYTHONPATH=src ./.venv/bin/python -m dispread.workbench.cli bridge identity --provision`
   Fingerabdruck notieren.
3. **Werkbank mit Brücken-Identität starten:** `... serve --host <pi-adresse> --port <port> --bridge-directory var/workbench/bridge --bridge-endpoint https://<pi-adresse>:<port> --bridge-name "Labor-Pi" [--cert ... --key ...]`.
   Ohne `--bridge-endpoint` enthält das Profil keinen Weg; die Adresse muss dann von Hand eingetragen werden.
4. **Nur UART-Weg:** Empfang vorbereiten, im Werkbank-Dialog Schritt 4
   „UART-Empfang“, Knopf „UART-Empfang vorbereiten“, oder per `... bridge prepare-uart`.
   Hinweis der Werkbank: „UART direkt und der Brücken-UART nutzen denselben Port und nie gleichzeitig.“
   Datenport ist `/dev/ttyAMA0`; Pegel nie direkt an RS-232 (OQ-09).

## B. Windows-PC vorbereiten

5. **App bereitstellen.** Auf einem Windows-11-x64-PC mit Python ≥ 3.13 (x64):
   In PowerShell im entpackten bzw. geklonten Ordner `picam-ai`:

   ```powershell
   $py = py -3.13 -c "import sys; print(sys.executable)"   # Pfad zum Python 3.13 x64
   powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\bridge\build-test.ps1 -Python "$py"
   # optional mit Setup: zusätzlich  -Inno "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
   ```

   `-ExecutionPolicy Bypass` gilt nur für diesen einen Aufruf und ändert keine
   Systemeinstellung; nötig, weil heruntergeladene unsignierte Skripte sonst
   blockiert werden. Ohne Git (ZIP-Download) steht als Quelle „unbekannt“.
   Ergebnis in `windows\bridge\dist-test\`: ZIP (entpacken, `GSVmulti-Bruecke.exe`
   starten) und mit `-Inno` ein Setup ohne Administratorrechte. Die Ausgabe nennt
   Pfade und SHA-256; vergleichen Sie den Hash nach dem Kopieren auf den
   GSVmulti-PC. **Unsigniert, unqualifiziert, nur interner Test**: Windows
   SmartScreen oder Virenschutz können warnen. Das ist erwartet; die IT
   entscheidet über die Freigabe.
6. **COM-Portpaar einrichten.** Die App erzeugt keine Paare, und der Treiber ist
   unverifiziert. Richten Sie mit **com0com** von Hand ein Paar ein, z. B.
   `COM21` ↔ `COM22`, und notieren Sie, welche Seite die Brücke und welche
   GSVmulti bekommt. Das Installieren eines Treibers braucht Administratorrechte
   und meist die Freigabe Ihrer IT (Signatur des Treibers prüfen lassen).
7. **App starten.** Erster Start: Fenster „GSVmulti-Brücke“. Zweitstart holt
   nur das vorhandene Fenster nach vorn. Minimieren hält die Brücke im
   Infobereich aktiv.

## C. Kopplung

8. In der Werkbank (`/live`) im Start-Popover bei „GSVmulti-Ausgabe“ den Weg
   **„Netzwerk über Brücke“** (oder „UART über Brücke“) wählen, dann
   **„Brücke einrichten…“**. Der Dialog „Windows-Brücke einrichten“ ist nur im
   Ruhezustand änderbar („Im Lauf nicht änderbar.“).
9. Schritt „Pi-Verbindungsprofil“: **„Profil herunterladen (pi.dispread)“**.
   Datei zum Windows-PC bringen.
10. In der App: Schritt 2 „Pi-Profil öffnen“, Datei auf „Profil hierher ziehen“
    ziehen oder doppelklicken (mit Setup ist `.dispread` zugeordnet).
11. **Fingerabdruck vergleichen.** App: „Vergleichen Sie den Fingerabdruck mit
    der Werkbank (Brücke einrichten › Profil).“ Werkbank: „In der Windows-App
    muss derselbe Fingerabdruck erscheinen.“ Alle 64 Zeichen (Vierergruppen),
    und gegen den Wert aus Schritt 2 prüfen. Stimmt er überein, Haken setzen:
    „Der Fingerabdruck stimmt mit der Werkbank überein.“ Bei Abweichung
    **abbrechen**.
12. Werkbank Schritt „Kopplung freigeben“: **„Kopplungscode erzeugen“**.
    „Code nur in die Windows-App eingeben. Einmal gültig, 5 Minuten.“ In der App
    bei „Kopplungscode“ eingeben (optional „Code anzeigen“), dann **„Code übernehmen“**
    (Enter im Feld genügt; der Knopf bleibt grau, bis Fingerabdruck bestätigt und Code
    eingegeben ist). Danach folgt Schritt 3 mit Fokus auf „Verbinden“ und dem Hinweis
    „Code gespeichert – gekoppelt wird beim Verbinden, jetzt gleich (Code noch m:ss gültig).“
    **Gekoppelt wird erst beim Verbinden.** Nach 5 Minuten (ab Eingabe, lokal gezählt)
    springt die App zurück zu Schritt 2: „Code abgelaufen – in der Werkbank einen neuen
    erzeugen“; es wurde nichts gekoppelt.
13. App Schritt 3 „Weg zum Pi wählen“: Netzwerk: gefundenen Pi oder
    Adresse/Name von Hand („Tailscale wird nur benutzt, wenn Sie hier den
    Tailscale-Namen oder die Adresse eintragen.“). Ein mDNS-Fund ist kein
    Identitätsnachweis. UART: USB-Seriell-Adapter wählen (115200 Baud, 8N1, kein
    Handshake; Verdrahtung wie angezeigt). Dann **„Verbinden“** (hier erfolgt die Kopplung; der Übertragungs-Worker startet erst nach authentifiziertem Pi).
    Während des Aufbaus zeigt die App „Verbindung zu <Pi> wird aufgebaut …“, der Fußknopf heißt
    „Abbrechen“. Bei Fehlern steht die Fehlerleiste oberhalb von Weg und Adresse (z. B.
    „Neuen Code eingeben“, „Anderes Profil öffnen“, „Erneut versuchen“); die Auswahl bleibt bedienbar.
    Erwartet: „Pi verbunden (Identität geprüft)“. Das ist „noch keine
    Messfreigabe“.
14. Portpaar in der App angeben (Schritt 1, „Portpaar prüfen“ bzw. „Vorhandenes Portpaar
    angeben“): Die automatische Prüfung ist in dieser Version nicht verfügbar. Zwei Auswahllisten
    „Brückenseite“ und „GSVmulti-Seite“ (aus Schritt 6), gleiche Ports sind nicht wählbar; „Weiter“
    übernimmt die Auswahl. Spätere Änderung: „Portpaar ändern“ (nur ohne aktive Verbindung).

## D. GSVmulti einrichten

15. Die automatische Session ist gesperrt (OQ-53/N3: keine geprüfte
    GSVmulti-Vorlage). Die Karte „In GSVmulti einstellen“ nennt die im ersten Testlauf
    belegten Werte: Gerät **UserDef**, COM-Port = **GSVmulti-Seite** des Paars, **115200 Baud, 8N1**,
    1 Kanal, Präfix **%**, Einheit **mV/V**, Frequenz **10 Hz** (Muster: Session aus dem Testlauf vom
    06.11.2026, nur Port anpassen). Trennzeichen/Filter nennt die App nicht (OQ-53 offen). Legen Sie eine **eigene Testsession** an, keine produktive
    Session überschreiben. Haken in der App: „In GSVmulti eingestellt …“ („Weiter“ bleibt bis dahin grau, mit Grund).

## E. Empfangstest (synthetische Demo)

16. App Schritt 5: „Ich verwende eine getrennte GSVmulti-Testsession.“ setzen,
    **„Test starten“**. Gesendet werden 600 synthetische Werte mit 10 Hz
    (etwa 60 s). Die Testsession hat keinen Abbrechen-Knopf: abwarten. Läuft auf dem Pi ein Messlauf,
    steht dort „Diese Ansicht aktualisiert sich selbst, sobald der Lauf endet.“; „Ohne Test beenden“
    schließt die Einrichtung ohne Empfangstest.
17. **In GSVmulti selbst prüfen:** Kommen Werte an, wie viele, in welcher
    Reihenfolge, steigt die Zeitachse gleichmäßig? Speichern Sie die Aufzeichnung.
    Optional „Testdatei auswählen …“: die App vergleicht Wert für Wert. „Empfang
    belegt“ gilt nur „für diese Testdatei und Konfiguration“.
18. Ergebnis, GSVmulti-Version, Dateiname und Auffälligkeiten in der Checkliste
    (G) notieren. Vergleichsergebnis der App allein ersetzt nicht die Sicht in
    GSVmulti.

## F. Echter Lauf in der Werkbank

19. Werkbank: Weg **„Netzwerk über Brücke“**, Lauf starten. Erwartet: Die App
    zeigt „Verbunden“ mit „DUT-Ausgabe gesperrt – die Brücke gibt keine Messwerte
    frei“ und die Info „Lauf n läuft. GSVmulti erhält absichtlich keine Messwerte … Das ist kein
    Fehler.“ (GSVmulti-Feld: „erhält im Lauf keine Werte“); die Werkbank zeigt „gesperrt“ und: „DUT-Ausgabe gesperrt: Windows-Abnahme
    fehlt. Verbindung und Diagnose sind vorbereitet; Messwerte werden noch nicht an
    GSVmulti ausgegeben.“ **Es dürfen keine Messwerte in GSVmulti erscheinen.**
    Erscheinen welche, ist das ein Fehler: sofort Lauf stoppen und melden.
20. Störungstests, einzeln. Die Erwartungen stammen aus den Texttabellen, nicht
    aus einer Beobachtung; notieren Sie, was Werkbank und App **tatsächlich** zeigen:
    * **Netz trennen** (LAN-Kabel/WLAN am Windows-PC): Die App zeigt „Pi antwortet
      nicht – Versuch in … s“ und baut neu auf. Werkbank: „Verbindung
      unterbrochen – lokaler Lauf läuft weiter“. Der Lauf auf dem Pi läuft weiter.
    * **App minimieren:** läuft im Infobereich weiter (einmaliger Hinweis), Status
      unverändert.
    * **Pi-Dienst neu starten** (*mit Freigabe*): Verbindung bricht ab, die App
      versucht neu; der Pi-Lauf endet mit dem Dienst.
    * **Neustart der App** nach fertiger Einrichtung: „Nicht verbunden.“ mit „Mit <Pi> verbinden“;
      „Beim Start automatisch mit <Pi> verbinden“ (Standard an, abschaltbar unter „Details“) verbindet
      nur mit demselben Pi, Weg und Endpunkt, startet nie eine Demo.
    * **App beenden:** „Beenden …“ im Fuß oder Tray-Menü; Rückfrage „Brücke beenden?“; Beenden trennt, „Der Lauf auf
      dem Pi läuft weiter.“

## G. Was der Lauf belegt und was nicht

**Er belegt höchstens:** App startet; Kopplung und Verbindung mit
Identitätsprüfung; synthetischer Empfang in einer bestimmten GSVmulti-Version
und Konfiguration; Verhalten bei den Störungen oben.

**Er belegt nicht:** keine Messfreigabe; kein Nachweis für N1 (saubere VM ohne
Python), N2 (qualifizierter Treiber, Installer-Rollback) oder N3 (kontrollierte
GSVmulti-Konfiguration); keine Aussage über Messwerte, Zeitzuordnung oder
Dauerbetrieb; kein Ersatz für die Qualifikation von `build.ps1`.

**Wohin mit Ergebnissen:** Diagnoseexport und Ereignisjournal der App liegen im
Benutzerprofil des Windows-PCs: `%LOCALAPPDATA%\dispread-bridge\` mit
`delivery.sqlite` (Übergabe-Journal) und `diagnostics\`. Den Diagnoseexport
erzeugt der Knopf „Diagnose exportieren“ (ZIP, Ort wählbar). Die Deinstallation
löscht diese Daten nicht. Hängen Sie Export und die ausgefüllte Checkliste an
Ihre Rückmeldung an.
Journal/Diagnose enthalten keine Zugangsdaten („Begrenzt, Zugangsdaten werden
nicht protokolliert.“); prüfen Sie dennoch vor dem Weitergeben.

### Checkliste (ausfüllen)

| Nr. | Prüfpunkt | Ergebnis (ok / Abweichung) | Notiz |
| --- | --- | --- | --- |
| 5 | Build/Setup, SHA-256 notiert | | |
| 6 | com0com-Paar (Seiten notiert) | | |
| 11 | Fingerabdruck identisch | | |
| 12 | Kopplung erfolgreich | | |
| 13 | „Pi verbunden (Identität geprüft)“ | | |
| 15 | GSVmulti-Version / 115200 8N1 | | |
| 17 | Demo: Werte in GSVmulti, Anzahl/Reihenfolge | | |
| 19 | Echter Lauf: keine Werte in GSVmulti | | |
| 20 | Netz getrennt / minimiert / Pi-Neustart / App beendet | | |
