# Status und Übergabe — Stand 2026-11-12

## Produktstand

- Aktive Kamera: Logitech StreamCam (UVC); die IMX500-Angaben im Hardwareprofil sind historisch.
- Der Live-Messpfad ist softwareseitig umgesetzt. Die reale Prüfung ist auf GSV-2AS / Displaytech 161A, Raumlicht und mV/V begrenzt; der T13-Lauf ist laut letztem dokumentierten Stand noch nicht vollständig abgenommen.
- Die GSVmulti-Ausgabe bleibt Prototyp. UserDefined-Zahlenimport und die gemeinsame TCP-/UART-Brücke sind umgesetzt; ungültige Werte und Altwertpuffer sind nicht ausreichend geprüft. Echte DUT-Ausgabe ist nicht freigegeben. Telegrammspezifikation bleibt offen (OQ-07).
- Die Windows-Brücke ist spezifiziert, aber noch nicht implementiert. Der dokumentierte UART-Versuch blieb ohne COM-Schreibbestätigung; der Pi-Rückkanal war nicht angeschlossen.

## Dokumentationshosting

Der Wiki-Sessionexport ist für Pushes und manuelle Workflowstarts auf `master` vorgesehen. Das Exportbudget beträgt 600 s, die systemd-Grenze 720 s. Ein offener, kürzlich geänderter Messlauf unter `var/live` verschiebt den Export; eine laufende Werkbank ohne Messlauf blockiert ihn nicht. Die Regel und ihre Grenzen stehen in [Doku-Hosting](HOSTING.md#session-archiv-und-explorer).

## Nächste Schritte

1. T13-Abnahme erst nach Klärung der dokumentierten offenen Diagnosepunkte vorbereiten und mit Referenz durchführen.
2. GSVmulti-Ausgabegrenzen und offene Protokollfragen vor einer Messfreigabe belegen.
3. Die Windows-Brücke erst nach Freigabe ihrer Spezifikation umsetzen.

Quellen: [Hardwareprofil](HARDWARE_PROFILE.md), [Projekt-Historie](project_history.md), [GSVmulti-Protokoll](GSVMULTI_PROTOCOL.md), [offene Fragen](open-questions.md), [Doku-Hosting](HOSTING.md).
