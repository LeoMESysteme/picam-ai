# Kurzzeitiger Ausfall von Kamerabild und Workbench-Verbindung

[Logarchiv](workbench-outage-2026-11-11.zip),
[SHA-256](workbench-outage-2026-11-11.sha256), [OQ-75](../open-questions.md#oq-75).
Teil des [kritischen Workbench-Blockers](../WORKBENCH_BLOCKER.md).

Nutzer meldet am 2026-11-11 einen gleichzeitigen Ausfall von Kamerabild und
Workbench-Verbindung für ungefähr sieben Sekunden. Die Dauer ist eine
Nutzerschätzung, nicht gemessen; exakte Start-/Endzeit fehlen. Erste
Agent-Prüfung 17:41:15 MEZ, ausführliche Sicherung 16:44:40 UTC (17:44:40 MEZ).
Aus diesen Erfassungszeiten keine genaue Ereignisdauer ableiten.

## Gesichert und festgestellt

* Anwendungs- und Kerneljournal seit 17:10 MEZ als Text und ursprüngliche
  journald-JSON-Zeilen mit Wanduhr-, Monoton- und Boot-Zuordnung.
* Tailscale-/Netzwerkjournal, Linkzähler, Prozess-/Dienst-/Speicherstatus,
  aktueller Kamera-/Workbench-Status, ausgeführte Befehle, Exitcodes und
  Fehlerausgaben. `/proc/pressure/*` ist nicht verfügbar; Firmware-
  Throttlingabfrage scheiterte. Keine unauffälligen Werte dafür erfinden.
* Dienst bleibt PID 3321848, Start 17:16:36 MEZ, `NRestarts=0`, active/running.
  Kein Neustart durch diese Untersuchung. Kamera nach dem Vorfall wieder
  running, nicht stalled; dies rekonstruiert den Vorfall nicht vollständig.
* Kernel-U1-/xHCI-Warnungen um 17:29 passen zeitlich zu den **früheren**
  protokollierten Setup-Kameraneustarts. Kein Beleg ihrer Ursächlichkeit
  für den später gemeldeten Ausfall.
* Netzwerkjournal enthält Peer-/DERP-/Endpunktwechsel, unter anderem um
  17:40/17:41. Exaktes Ereignisfenster und Zuordnung zum Browser fehlen;
  daraus keine bereits bewiesene Tailscale-Ursache ableiten.

HTTP-Accesslogs und Browserkonsole wurden damals nicht dauerhaft erfasst.
Ob Netzpfad, Browser, Eventloop oder ein anderer vorübergehender Engpass
ursächlich war, bleibt offen. Keine Loglücke mit erfundenen Ereignissen füllen.

Archiv liegt zusätzlich unter `var/diagnostics/workbench-outage-20261111/`.
Manifest und äußerer Hash sichern die Bytes. Statuszeitpunkte sind
Host-Wanduhr UTC, Unsicherheit unbekannt; journald-Monotonwerte gelten nur
auf diesem Host und innerhalb der zugehörigen Boot-ID. Keine Frame- oder
hostübergreifende Latenzaussage.
