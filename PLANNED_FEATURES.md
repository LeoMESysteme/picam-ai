# Geplante Funktionen und Bedienablauf

Stand: 2026-11-26. Die [Arbeitsliste](TODO.md) führt die nächsten Schritte.
Der [Status](docs/status.md) hält die veröffentlichten Versionen und
Gerätebelege fest.

## Windows-Brücke: einfache Einrichtung (Vorgabe 2026-11-06)

Brücke 1.1.0 ist als Windows-Setup und portable Einzel-EXE veröffentlicht.
Die Brücke führt durch Netzwerk- oder UART-Verbindung, Kopplung,
Bereitschaftsprüfung und GSVmulti-Sessionexport. Setup und portable EXE
enthalten die Laufzeit. GSVmulti und bei den beiden Brückenwegen ein
passendes virtuelles COM-Portpaar werden separat eingerichtet.
[Veröffentlichung](https://github.com/LeoMESysteme/picam-ai/releases/tag/v1.1.1) ·
[Ausgabewege und Portwahl](docs/GSVMULTI_PROTOCOL.md)

Produktziel bleibt eine durchgängige Einrichtung am Arbeitsplatz. Dazu
gehören ein zum Pi-Stand passender Download aus der Werkbank, ein
zuverlässig eingerichtetes COM-Portpaar und eine verständliche Prüfung
auf veraltete Brückenversionen. Offene Nachweise betreffen unter anderem
frische Windows-Installationen, vorhandene ältere Python-Installationen,
PnP-Treiberstart, Paketierung und Sessionexport im Zielumfeld.
[Spezifikation vom 06.11.](docs/superpowers/specs/2026-11-06-windows-bruecke-design.md) ·
[Prüfaufgaben](docs/open-questions.md#oq-62)

## Bedienablauf und heutiger Stand

| Schritt | Stand |
| --- | --- |
| Auf dem Pi installieren und Werkbank öffnen | Geführter Installer mit Onboarding, Systemdienst und Verwaltung über `picam`. Die Installation nennt die konkrete HTTPS-Adresse der Werkbank. [Anleitung](docs/INSTALLER.md) |
| Anzeige einrichten und bestätigen | Die Werkbank unter `/live` führt durch Kamera, Rahmen, Raster, Nachführung und Gegenlesen. Die Bestätigung gilt für die konkrete Einrichtung. [Live-Bedienung](docs/anleitung/10-kamera-livevorschau.md) |
| Erkennung starten und Zustand einsehen | Dot-Matrix-Leser, VALID / TRANSITION / UNREADABLE / STALE und JSONL-Audit pro Lauf. [Messpfad und Freigabe](docs/uebersicht/messpfad.md) |
| Ausgabeweg für den Lauf wählen | Aus, Netzwerk über Brücke, UART über Brücke oder UART direkt. Der 13.11. belegt die drei Ausgabewege am damaligen Aufbau. Die allgemeine Telegrammspezifikation bleibt offen. [Protokoll und Prüfgrenzen](docs/GSVMULTI_PROTOCOL.md) · [OQ-07](docs/open-questions.md#oq-07) |

Echte Messwertsprünge bleiben erhalten. Bei unlesbarer Anzeige verweigert
die Freigabe einen neuen gültigen Wert. Die Modell-Konfidenz
ist ohne Kalibriermessung keine Fehlerwahrscheinlichkeit.
[Konzept §7](Konzept.md#7-erkennungssicherheit-und-fehlerbehandlung)

## Weitere Produktziele

* **Werkbank:** Bedienhinweise und Hilfsanimationen ausbauen, etwa für eine
  zu schräge Kameraposition. Das ME-Dashboard soll direkt zur Werkbank
  führen. Verhalten und Grenzen der Nachführung an weiteren Aufstellungen
  prüfen. [Arbeitsliste](TODO.md)
* **GSVmulti-Ausgabe:** Die verbleibenden Format- und Verhaltensfragen mit
  den eingesetzten GSVmulti-Versionen klären. Das vorhandene
  `AsciiCsvFormatter`-Format bleibt mit `provisional=True` gekennzeichnet.
  [OQ-07](docs/open-questions.md#oq-07)
* **Datensätze erweitern:** Auto-Labeling, Timing-Kalibrierung, Ernte und
  Import sind gebaut. Ziel ist eine breitere Abdeckung von Geräten,
  Lichtbedingungen, Vorzeichen und Einheiten. Der Displaybus-Abgriff ist
  als Rückfallebene skizziert.
  [OQ-38](docs/open-questions.md#oq-38) · [OQ-39](docs/open-questions.md#oq-39) ·
  [Displaybus-Skizze](docs/DISPLAYBUS_TAP.md)
* **Betrieb:** Dauerlauf, Audit-Aufbewahrung und Kamerawiederverbindung am
  Aufbau prüfen. Der Ein-Befehl-Installer ist über SSH ausführbar.
  `picam` bietet Konsole und Einzelbefehle für Status, Einrichtung und
  Wartung. Für den Betrieb richtet der Installer einen Systemdienst ein.
  [Installation und Verwaltung](docs/INSTALLER.md)

USER ENTRIES (Alles unter dieser Zeile ist nur vom user. Kein Agent darf unter dieser Zeile schreiben. User Entries sollten regelmäßig in die oberen Notes aufgenommen werden.)

* setup tui (einfacher step by step install von picam-ai)
* anbindung an das me dashboard (so das man von dort aus auf die workbench/live-messpfad kommt)
* cli (über diesen soll man im terminal einstellungen vornehmen und sehen können. bsp. systemd autostart, aktueller status, web ui link für localhost, internes netzwerk, tailscale, start/stop, usw...). soll neben dem web ui das go-to werden was konfiguration und einstellungen, usw.. betrifft. (wird/soll sehr umfangreich werden)
* hilfs animationen in der workbench (bsp: kamera wird als zu schräg erkannt -> pop-up mit einer animation wo die kamera von einem seitlichen winkel in einen frontalen winkel wechselt)
