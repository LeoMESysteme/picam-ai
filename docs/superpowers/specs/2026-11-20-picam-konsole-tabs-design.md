# picam-Konsole 2: Dashboard und Tabs (Design)

Stand 2026-11-20. Quelle: Wunschliste [`tui-user-wishes.md`](../../quellen/tui-user-wishes.md) von Leonhard,
Entscheidungen im Chat vom 20.11. mittags. Ersetzt die Bereichsliste links
durch eine Tab-Leiste oben. Gestaltung nach dem `tui-design`-Skill.

## Entscheidungen

- Tabs oben, Dashboard ist die Startansicht. Im Dashboard steht die
  Bereichs-/Statusliste **rechts**, links Logo und Lauf.
- Passwort: bleibt das Linux-Passwort des Kontos (PAM). Kein eigener
  Speicher, keine Änderungsfunktion. Konsole und Installer sagen deutlich,
  mit welchem Konto und welchem Passwort man sich an der Werkbank anmeldet.
- Externe IP wird nie abgefragt (keine Anfragen an fremde Dienste).
- Fehlende Backend-Funktionen erscheinen als Aktion „folgt“ (deaktiviert,
  mit Grund), bis sie gebaut sind. Backend-Teile bauen Claude-Subagenten
  (Codex hat ein Ratenlimit): Kamera-Neustart, Laufmetriken (Latenz,
  Margin), Zertifikat erneuern, Deinstallieren.
- Die Konsole bleibt Verwaltung und Fehlersuche, kein zweites Bedienpult:
  Läufe und Einrichtung starten/beenden nur in der Werkbank im Browser.
  Laufdaten zeigt sie lesend (Metrik-Ansicht).

## Aufbau

```
 picam  Dashboard  Lauf  Dienst  Kamera  Ausgabe  Zertifikat  Speicher  Netzwerk  UART  Konto  Protokoll  Einstellungen
 ──────────────────────────────────────────────────────────────────────────────────────────────────────
 <Inhalt des Tabs>
 <Statuszeile: Meldung / Sperrgrund / Drehzeichen>
 <Tastenleiste: Tab-spezifisch + global>
```

- Tasten global: `←/→` bzw. `Tab`/`Shift+Tab` Tab wechseln, `1`–`9` und
  `0` direkt (Dashboard 1, Lauf 2, Dienst 3, Kamera 4, Ausgabe 5,
  Zertifikat 6, Speicher 7, Netzwerk 8, UART 9, Konto 0), `l` Protokoll,
  `c` Einstellungen, `i` Info zum Tab (Popup), `?` Hilfe, `g` neu prüfen,
  `q`/`Ctrl+C` Ende, `Esc` zurück zum Dashboard bzw. Dialog schließen.
- Maus: Tabs und Knöpfe klickbar, nie nötig.
- Tab-spezifische Aktionen sind Knöpfe im Tab **und** eine Taste
  (in der Tastenleiste angezeigt). Deaktivierte Knöpfe nennen den Grund.
- Schmaler als 76 Spalten: Tab-Leiste rollt (aktiver Tab sichtbar),
  Inhalte einspaltig. Unter 48×14: Hinweis „Terminal zu klein“.
- Jede Gefahr wird vor der Aktion im Bestätigungsdialog benannt: genauer
  Befehl, Folgen, Fokus auf „Abbrechen“. Während Lauf/Einrichtung/
  Diagnosekopie (`Snapshot.stop_blocker`) sind Dienst- und Kameraaktionen
  gesperrt; Stoppen trotzdem nur mit `--force` auf der Kommandozeile.

## Dashboard

- Links oben ME-Logo (statisch, alle ~20 s ein Glanzlauf), darunter
  Laufkarte: ruhend „Kein Lauf · Einrichtung bereit“; aktiv
  „● Lauf aktiv · Schritt · Dauer · Ausgabe“ plus Zählwerte und
  60-s-Statusband. Enter/Klick → Tab Lauf. Einrichtung aktiv analog.
- Rechts Statusliste (je Zeile Symbol+Farbe, Name, Wert; Unterpunkt
  eingerückt mit `└`): Werkbank, Lauf (└ Ausgabe), Kamera, Brücke,
  Zertifikat, Speicher, CPU, RAM, Temperatur, Version, offene
  Einrichtungspunkte. Klick/Enter auf eine Zeile öffnet den Tab.
- Knöpfe: Werkbank starten/stoppen, Neu starten, Kamera verbinden/neu
  starten, Brücke: UART-Empfang vorbereiten. Gesperrt mit Grund.
- Ab 34 Zeilen darunter „Letzte Meldungen“ (Dienstprotokoll).
- Warnungen (Speicher knapp, Zertifikat läuft ab, Kalibrierung fehlt)
  als schmale Hinweisbalken über der Laufkarte.

## Fehler als Popup

Wechselt ein Befund neu auf Fehler (Dienst ausgefallen, Kamera Fehler/
hängt, Ausgabe Fehler, Steuerung nicht erreichbar, Prüfung fehlgeschlagen),
öffnet ein Popup: was ist passiert (Klartext), was bedeutet es, Optionen
(z. B. Protokoll ansehen, Neu starten, Kamera neu verbinden, Schließen).
Derselbe Fehler meldet sich erst nach einem Zustandswechsel erneut. Nie
mehr als ein Fehler-Popup gleichzeitig; weitere stehen in der Statuszeile.

## Tabs

| Tab | Inhalt | Aktionen (Quelle) |
|---|---|---|
| Lauf | Zustand, Schritt, Sitzung, Dauer, Ausgabe; Zählwerte gültig/Übergang/unlesbar/veraltet; 60-s-Statusband aus `live.status.run.recent`; letzter Wert mit Alter (veraltet markiert); Verarbeitung `run.proc` (fps, Latenz-Verlauf, Margin – **nicht** „Konfidenz“), CPU | keine Laufsteuerung; Hinweis auf Werkbank-URL |
| Dienst | Unit, Art, Autostart, seit, PID, Version, Vorige, Ort; Erklärung (Info) | Start/Stopp/Neustart (`service.plan/execute`), Update `u`, Rückweg `z`, Protokoll |
| Kamera | Gerät, USB-ID, Hersteller/Modell (Logitech StreamCam), Anschluss USB 3/2, Format/Auflösung, Bilder, Lücken, letzter Start; Timing-Kalibrierung; Lesevorlage | Kamera verbinden (`live.camera`), Kamera neu starten (`live.camera.restart`, folgt) |
| Ausgabe | Unter-Tabs „Aus · UART direkt · UART über Brücke · Netzwerk“; aktiver Weg hervorgehoben, „Aus“ deutlich. Je Weg: Port, Baudrate (direkt 115200 Standard, Brücke 460800), Zustand, Kopplungen, Brückenverbindung | UART-Empfang vorbereiten/stoppen (`bridge.prepare-uart`/`bridge.stop-uart`) |
| Zertifikat | Erklärung „Ausweis der Werkbank für HTTPS und die Windows-Brücke“; Adresse/Namen, gültig bis, Datei, Identität | Erneuern (folgt); kein Abschalten (HTTPS ist Pflicht, Begründung) |
| Speicher | Frei/belegt als Balken; Aufteilung Läufe, Diagnose, Werkbank-Daten, Brücke, Programmversionen, Rest; Reserve | Aufräumen (`picam aufraeumen`, Vorschau zuerst) |
| Netzwerk | Hostname, Schnittstellen mit IPs, Tailscale (falls installiert), Werkbank-Adresse liegt auf Schnittstelle?, Uhr/NTP | nur lesen; Hinweis auf `nmcli`/Tailscale-App |
| UART | Stiftleiste 2×20 als Grafik: Pin 6 GND, Pin 8 TXD0 (GPIO14) markiert, Pin 10 RXD0 „nicht bestätigt“; Warnung: kein RS-232 direkt (Pegelwandler), 6-pol. Block nicht aufstecken; Boot-Konfiguration, Konsole auf UART | Port ändern: nicht vorgesehen (Begründung) |
| Konto | Anmeldung an der Werkbank: Benutzer X mit seinem Linux-Passwort; Gruppen; Nach-Abmeldung (Benutzerdienst) | keine Passwortänderung (Hinweis `passwd`) |
| Protokoll | wie bisher | mitlaufen, nur Probleme |
| Einstellungen | Formular Port/Brückenname/Discovery mit Risiko je Feld; Orte: Konfiguration, Daten, Laufdaten, Brücke, Protokoll (journald), Code | Übernehmen; Deinstallieren (folgt) |

## Daten

Alle Werte kommen aus `probes.collect` (Fakten + `live.status` +
`bridge.status`) oder lokalen, billigen Quellen. Neu in `probes`:
`system_metrics()` (CPU aus `/proc/stat`-Differenz, RAM aus
`/proc/meminfo`, Temperatur aus `/sys/class/thermal`), `storage_usage()`
(Größen je Ort, langsam: eigener Worker, alle 60 s), `network_info()`
(Schnittstellen, Tailscale über `tailscale ip`/`status --json` falls
vorhanden). Nichts wird erfunden; unbekannt heißt „–“.

## Bewegung

Wie bisher dezent: Tabwechsel blendet 0,15 s ein, Laufband und
Drehzeichen nur bei Aktivität, Logo-Glanz selten. `TEXTUAL_ANIMATIONS=none`
schaltet alles ab.

## Tests

Je Tab ein Headless-Test (`run_test`): rendert mit Beispieldaten,
Aktion gesperrt/erlaubt, Bestätigung startet auf „Abbrechen“. Größen
80×24, 60×20, 160×45. Tour-Bilder neu.
