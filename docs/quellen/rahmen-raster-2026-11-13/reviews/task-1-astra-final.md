# Task 1 — Astra Abschlussreview, Fixrunde 2

**Prüfumfang:** `task-1-fix2.diff`, ergänzter Implementierungsbericht, Zustandsübergänge im Dienst und in der Alert-Logik sowie die neuen Regressionstests. Keine Produktänderungen, Subagents, Commits oder Kamera-/Dienstzugriffe. Keine breite Testwiederholung; nur dieser Bericht wurde geschrieben.

## F1: ADDRESSED

- `LiveService.start_run()` entfernt den aktiven Ablehnungsbefund unter der Zustandssperre, nachdem `session.start()` erfolgreich zurückgekehrt ist. Eine davor gescheiterte Startprüfung löscht ihn nicht. Die gespeicherten Ablehnungsartefakte bleiben erhalten.
- `start_setup()` entfernt ihn beim Übergang in die neue Einrichtung. Vorprüfungen wie Speicher-/Kameraverfügbarkeit liegen davor; eine abgelehnte Einrichtungsanforderung entwertet den bisherigen Befund nicht.
- Die Alert-Logik schließt den bestehenden `start-abgelehnt`-Toast, sobald der Status keinen aktiven Ablehnungsbefund mehr trägt, und setzt die lokale Kennung zurück. Ein neu geladener Client zeigt folglich keine erledigte Warnung. Noch offene Ablehnungen bleiben nach Neuladen sichtbar.
- Backend-Tests prüfen wiederholte Ablehnung, erfolgreichen Folgestart mit erhaltenen Auditdateien und neue Einrichtung. Node-Tests prüfen die Übergänge im bestehenden Client und im neu geladenen Client.

**Eigene fokussierte Verifikation:**

```text
node --test --test-name-pattern='erledigte Startablehnung|abgelehnter Start bleibt' tests/live_effects.test.mjs
2 bestanden, 0 fehlgeschlagen, 17 gezielt übersprungen
```

Die bestehende Node-Modultypwarnung ist unverändert und kein Defekt dieser Änderung. Die vom Implementierer berichteten fünf Backend- und 32 Node-Tests wurden nicht zusätzlich breit wiederholt.

## Freigabe

**Task-1-Spec: FREIGEGEBEN.** Die Anforderungen an zweiseitige Fokusprüfung, sichtbaren Befund, Ablehnung ohne Messlauf, Tracking-Diagnose und Offline-Belege sind im geprüften Umfang erfüllt.

**Task-1-Qualität/Korrektheit: FREIGEGEBEN.** A1–A4 und F1 sind vollständig behoben. Keine offenen Reviewbefunde und keine neuen Defekte im Fixdiff festgestellt. **Explizite mängelfreie Reviewfreigabe für Task 1.**

Diese Freigabe umfasst die geprüfte Task-1-Implementierung samt beiden Fixrunden. Sie ersetzt weder die separat geplanten Integrations-/Docs-Prüfungen noch eine Hardwareabnahme oder Kalibrierung des ausdrücklich vorläufigen Fokusbands. Die unveränderten Grenzen 0,35/0,65 px und die Ablehnung unsicherer Lagen bleiben gewahrt; keine neue Ausreißerverwerfung oder gehaltene Lage wurde eingeführt.
