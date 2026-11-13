# Smoketest 13.11.2026: EXE (Stand `feat/integration`)

## 1. Bauen
* Branch `feat/integration` als ZIP oder per `git clone -b feat/integration` holen.
* Doppelklick auf `windows\bridge\build-test.cmd`. Er findet Python 3.13 selbst, umgeht die Ausführungsrichtlinie nur für diesen Lauf und öffnet am Ende `dist-test`. Falls Windows beim ersten Mal fragt: „Ausführen“.
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
* In GSVmulti: 10 Hz Zeilen. Ungültiger Takt: Kanal 8_2 = 0, Kanal 8_1 hält den letzten gültigen Wert (ab 13.11. mittags; vor dem ersten gültigen Wert 99999999.0). Kanal 8_4 mit Zeit.

## 5. Wenn es hakt
* App: Symbolleiste „Protokolle exportieren“ (ZIP mit `summary.json` und `details.jsonl`, ohne Zugangsdaten).
* GSVmulti: Session (`.ucf`) und Aufnahme (`.tdms` plus `.tdms_index`) sichern.
* Zeitpunkt, Laufnummer und Bildschirmfoto der App notieren.

## 6. Werkbank (Pi) vor dem Lauf
* Der Pi-Dienst läuft auf dem gemeinsamen Stand `feat/integration`. Welcher Commit es ist, steht in der Übergabe in `docs/status.md`. Adresse und Kopplung bleiben gleich.
* Neu einrichten, ohne Rahmenbereiche von Hand zu entfernen. Anzeige und „+“-Zelle sauber halten: Schmutz oder Kratzer in der Pluszelle führen jetzt eher zu „keine Startlage“.
* Fokus: Die Suche misst jetzt auf der Anzeige. Prüfzeile „fokus“ ansehen. WARNUNG „Fokus ohne LCD-Hinweis“ oder „nach Neustart unschärfer“ notieren.
* Bei FEHLER (Kanten, Startlage, einseitige Rahmenbereiche) zeigt die Einrichtung jetzt Zelle, Grund und Abhilfe. „Neu einrichten“ ist immer erreichbar, auch nach dem Bestätigen. Das Ergebnis jeder Einrichtung notieren (OK, WARNUNG, FEHLER und Grund).

## 7. Werkbank im Lauf (mindestens 10 Minuten, dabei die Last aktiv ändern)
* Laufstart: Format „Vierkanal-Takt“, Takt 10 Hz, Testfreigabe-Haken. Die Checkliste „In GSVmulti“ im Startfenster abhaken.
* Nach dem Kamerastart prüft die Werkbank die Schärfe. Erscheint „Bild nach Kamerastart unschärfer …“, notieren.
* Taktzeile im Lauf beobachten: gültig in %, verpasst. Ziel bei aktiver Laständerung: mindestens 75 % gültig.
* Hinweise „Rahmenbereich N unstimmig“ oder „Bereich N automatisch stillgelegt“ notieren. Eine Stilllegung braucht nach etwa 10 s Unstimmigkeit rund 40 s Prüfung im Hintergrund.
* Kurze Bildausfälle (OQ-75) oder träge Bedienung (OQ-73): Uhrzeit notieren.

## 8. Was ich danach auswerte (Pi-Seite, kein Handgriff nötig)
* Für den Lauf: `records.jsonl`, `output.jsonl`, `tracking_events.jsonl` und `session.json` mit `focus_check`, `tick` und `tracking_region_hint`.
* Bildrate und `frame_gaps` während der Stilllegungsprüfung. Nach dem Laufende darf kein Prozess `region_probe` mehr laufen.
* Die GSVmulti-TDMS gegen das Pi-Audit: Zeilen pro Takt, Fehlwerte, Zeitkanal.
