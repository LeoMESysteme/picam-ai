# Freigabe

Syntax-, Qualitäts- und Zustandsregeln aus Konzept.md §7. Der Dot-Matrix-
Leser wendet seine eingefrorenen Abstandsgrenzen selbst an;
`default_gate_config("dotmatrix")` führt dafür keine zweite Segmentmargen-
oder Kontrastschwelle ein. Das Gate prüft weiterhin Lesbarkeit,
Vorzeichenbereich, Dezimalpunkt, Einheit und Betriebszustände.

Der Live-Pfad verlangt zwei gleiche Bilder vor VALID. Bis dahin gilt
`TRANSITION` mit `awaiting_confirmation`. Kurzzeitige Mischziffern können
`TRANSITION` mit `anzeige_wechselt` ergeben, wenn die lesbaren Zellen der
letzten Freigabe entsprechen und die Grenzen für Anzahl und Zeitfenster
eingehalten sind. Dabei wird nie ein Zahlenwert freigegeben. STALE hat
Vorrang; blockierende Zustandsflags bleiben UNREADABLE.

Fehlt dem Locator die Anzeige, umgeht die Pipeline das Gate und schreibt
UNREADABLE. Ohne neue Bilder entsteht kein neuer Bilddatensatz; das Alter
markiert die Live-Oberfläche separat
([Messpfad](../docs/uebersicht/messpfad.md#wie-das-gate-entscheidet)).

::: dispread.validate
