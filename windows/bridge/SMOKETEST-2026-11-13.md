# Smoketest 13.11.2026: EXE (Stand `feat/integration`)

## 1. Bauen
* Branch `feat/integration` als ZIP oder per `git clone -b feat/integration` holen.
* `powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\bridge\build-test.ps1 -Python <Pfad zu Python 3.13 x64>`
* EXE aus `windows\bridge\dist-test\` starten. Ältere Brücke vorher über das Tray beenden.
* Erwartet: Symbole sichtbar (keine leeren Kästchen), keine aufblitzenden Konsolenfenster.

## 2. Erster Start und Verbinden (nur Netzwerk)
* Moduswahl öffnet sich beim allerersten Start: „Netzwerk über Brücke“ wählen.
* Bestehende Kopplung: „Mit … verbinden“. Sonst Einrichtung mit Profil und Code aus der Werkbank.
* Erwartet: Herzschlagpunkt pulsiert, Kachel Pi „Verbunden“, DUT-Zeile bzw. Testfreigabe-Zeile sichtbar.

## 3. Session
* Einrichtung Schritt 4 oder Einstellungen: „Session erzeugen“, Vorgabe ist Vierkanal.
* Datei in GSVmulti als Session öffnen. Kanal 8_1 trägt mV/V aus der Vorlage, 8_2 bis 8_4 sind ausgeblendet.
* Pflicht in GSVmulti: Configure Recording, Advanced, „Record Hidden Channels“ einschalten. Steht nicht in der Datei.
* Empfohlen: Kanal 8_1 Autoscale Y aus, Min/Max fest.
* Port in der Session muss der GSVmulti-Seite des Portpaars entsprechen (z. B. COM8).

## 4. Vierkanal-Lauf
* Lauf in der Werkbank mit Vierkanal-Takt und Testfreigabe starten.
* Erwartet in der App: Zustandssatz nennt die Testfreigabe, Kacheln Pi und Weitergabe ohne Fehler.
* **Noch nicht in der Oberfläche:** Taktzähler (`ticks_written`, `ticks_invalid`, `ticks_filled`, `tick_disturbed`). Sie stehen im Protokollexport (`summary.json`, Abschnitt `worker`). Nach dem Lauf exportieren und prüfen: `ticks_written` ungefähr Laufdauer × 10 Hz, `tick_disturbed` false.
* **Ebenfalls noch nicht sichtbar:** der Hinweis, wenn das Lauf-Format nicht zur Session passt. Deshalb Session-Format (Vierkanal) und Laufstart (Vierkanal-Takt) von Hand abgleichen.
* In GSVmulti: 10 Hz Zeilen, Fehlwert 99999999.0 bei ungültigen Takten, Kanal 8_4 mit Zeit.

## 5. Wenn es hakt
* App: Symbolleiste „Protokolle exportieren“ (ZIP mit `summary.json` und `details.jsonl`, ohne Zugangsdaten).
* GSVmulti: Session (`.ucf`) und Aufnahme (`.tdms` plus `.tdms_index`) sichern.
* Zeitpunkt, Laufnummer und Bildschirmfoto der App notieren.
