# Kritischer Blocker: Workbench vor Bridge-/EXE-Weiterentwicklung stabilisieren

**Stand 2026-11-13: Werkbank und Ausgabewege von Herrn Kaulitz abgenommen.** Offene Restpunkte (Nachführung bei Fokusunterschied, Rasterbestimmung) stehen in [TODO.md](../TODO.md) und sind an Codex übergeben. Ursprünglicher Auftrag: **Offen, höchste Arbeitspriorität seit 2026-11-11.** Die wiederholt
fehlschlagende Einrichtung, der gemeldete Fokusrückfall, fehlende Auswege
und zeitweilige Verbindungsverlust blockieren Bridge-/EXE-Weiterentwicklung,
ausführliche Systemtests und die geplante teilweise Abnahme durch Herrn
Kaulitz. Der Nutzer erwartet eine wieder zuverlässig benutzbare Workbench
und passende EXE bei seiner Rückkehr am **Freitag, 2026-11-13**.

Claude soll nach dem Limit-Reset **hiermit beginnen**, bevor frühere
Bridge-Featureaufgaben fortgesetzt werden. Dies ist ein offener
Wiederherstellungsauftrag, keine Behauptung einer bereits erreichten
Fehlerbehebung oder Messfreigabe.

## Sofortiger Einstieg

1. [Ausführlicher Auftrag an Claude](superpowers/handoffs/2026-11-11-einrichtungsfehler-an-claude.md).
2. [Aktueller Status](status.md), danach die dort verlinkten Belegpakete.
3. Tatsächlichen Betriebsstand und getesteten Zielstand feststellen, bevor
   ein einzelner alter Fehler erneut implementiert wird. Der Dienst läuft
   auf `bruecke-run/08ac9b9`; neuere Zweige und uncommittete Arbeiten sind
   gesondert gesichert. Ein Neustart war kein Update.
4. Fehler und positive Kontrollen offline wiederholen. Einen konsistenten
   Workbench-/EXE-Stand herstellen, Fehler mit Regressionstests beheben und
   erst dann Bridge-Ausbau und Abnahme fortsetzen.

## Sichtbare Fehler und Reihenfolge

| Priorität | Fall | Beleg/Aufgabe |
| --- | --- | --- |
| Kritisch | Fehlerhafter Vorschlag ohne Abbruch; auch nach Bestätigung fehlt direktes Neu einrichten | [OQ-71](open-questions.md#oq-71); reproduzierte UI- und Backend-Vorbedingungen |
| Kritisch | Mehrere Aufstellungen scheitern an `keine_startlage`/`startlage_mehrdeutig` | [OQ-69](open-questions.md#oq-69); mehrere Originalbilder und Offline-Rezepte |
| Kritisch | Nutzer sieht nach guter Fokussuche wieder Unschärfe | [OQ-74](open-questions.md#oq-74); Fokusdaten, Importpfade, Bild außerhalb Fokus-ROI; Ursache offen |
| Kritisch | Raster gültig, aber Nachführbereiche unzureichend verteilt | [OQ-70](open-questions.md#oq-70); Vorschlag und Geometrie-Gate |
| Kritisch | Zwei weitere Aufstellungen scheitern an Kantenprüfung Zelle 7 | [OQ-72](open-questions.md#oq-72); Helligkeitsstufe etwa 29,8, Fehlergrenze 20 |
| Kritisch | Oberfläche verzögert bei zunächst flüssigem Kamerabild | [OQ-73](open-questions.md#oq-73); bisher keine Browsermessung unter Setup-Last |
| Kritisch | Kamerabild und Workbench-Verbindung ungefähr sieben Sekunden weg | [OQ-75](open-questions.md#oq-75); [Dienst-/Kernel-/Netzwerklogs](quellen/workbench-outage-2026-11-11.md) |

Die Fehler bilden aus Nutzersicht einen unerwarteten Rückschritt gegenüber
der als fertig betrachteten Workbench. Ob jeweils eine neue Coderegression,
ein alter unvollständig abgedeckter Fall oder ein veralteter Betriebsstand
ursächlich ist, muss anhand der gespeicherten Versionen unterschieden werden.
Nicht alle Symptome haben nachgewiesen dieselbe Ursache.

## Neuester zusätzlicher Fehlerfall

[Aufstellung `170836Z`](quellen/setup-focus-failure-2026-11-11-170836.md):
Raster sofort OK, Kanten-FEHLER in den letzten Leerzellen 14/15,
Stabilitätsmessung nicht gestartet; erneute optische Unschärfemeldung.
Originalbild, Fokusdaten und eingefrorener Code gesichert. Ergänzt OQ-72/74.
Für autonome Arbeit sind zunächst genug unterschiedliche statische Fälle
vorhanden. Zusätzliche Hardwareaufnahmen bei Bedarf gezielt instrumentieren.

## Positive Referenzen erhalten

Es schlagen **nicht alle** Aufstellungen fehl: Der Nutzer hat danach drei
weitere Aufstellungen erfolgreich bestätigt. Sie sind im
[positiven Regressionspaket](quellen/workbench-positive-regression-2026-11-11.md)
einschließlich Originalbildern, Vorschlägen, Profilen und Bestätigungen
gesichert. Ein anschließender Lauf lieferte **2.920 von 3.843 Datensätzen
VALID (75,9823 %)**, ohne Trackingverlust und ohne Audit-/Kamerafehler.
Das vom Nutzer benannte 75-%-Minimum ist auf diesen verarbeiteten
Datensätzen erreicht. Diese funktionierenden Setup-Fälle müssen erhalten bleiben. Der kurze
Lauf von `165234Z` war laut Nutzer nur ein Start-/Stopp-Umweg zum erneuten
Einrichten nach Aufstellungswechsel. Er ist kein unabhängiger negativer
Tracking-Regressionsfall; OQ-76 ist geklärt und OQ-71 entsprechend erweitert.

Zusätzlich sechs historische Kontrollbilder mit bestätigten Quads gesichert;
ihre ursprünglichen Geometrie-Regressionstests bestehen. Daraus keine neue
unabhängige Abnahme ableiten. Alle Fehlerschranken nicht einfach lockern,
um die neue Fehlerliste grün zu machen.

Die spätere Meldung `Zellentext: the ninth cell ...` entstand laut Nutzer
durch versehentlich eingegebenen Text mit „hatte“. Das ist geklärte falsche
Eingabe und **kein weiterer belegter Softwareblocker**.

## Wann der Blocker geschlossen werden kann

* Tatsächlicher, versionierter Dienststand und dazu passende EXE eindeutig
  ausgewiesen; kein unbemerkter Rückfall auf einen älteren Worktree.
* Fehlersackgasse behoben und mit Knopf-/Tastatur-/API-Regressionen geprüft;
  neue Einrichtung ohne Dienstneustart möglich, Diagnose bleibt erhalten.
* Gesicherte Fehlerfälle im vereinbarten Unterstützungsumfang korrekt
  verarbeitet oder mit belegtem, verständlichem Grund zurückgewiesen.
  Rastergeometrie und Gegenlesen zusätzlich zum Fitstatus geprüft.
* Alle drei aktuellen positiven Aufstellungen und sechs historische Kontrollen
  weiterhin erfolgreich; keine Referenzkorrektur, Glättung oder Freigabebypässe.
* Fokusübergang und Verbindungsunterbrechung mit geeigneten Tests behandelt;
  nicht allein aus unveränderten numerischen Reglerwerten schließen.
* Gemeinsamer Workbench-/EXE-Smoke-Test und bestehende Protokoll-/UART-/TLS-
  Regressionen abgeschlossen. Der positive aktuelle Lauf war UART direkt
  und beweist keinen Windows-EXE-/GSVmulti-Empfang.
* Verbleibende physische oder Windows-Abnahmen ehrlich ausgewiesen. Ein
  129,94-s-Lauf und 75 % VALID ersetzen keinen offenen 30-Minuten-Nachweis.

Ohne die ursprünglichen Aufstellungen sind statische Geometrie, Leser,
UI-Zustände, Protokolle und große Teile der Kamera-Steuersequenz prüfbar.
Fehlende Rohbildstapel, Stabilitätsproben und Fokusbilder vor/nach Neustart
lassen sich nicht nachträglich herstellen. Das begrenzt die Hardwareaussage,
hindert aber autonome Codekorrekturen und Regressionen nicht.
