# Status — Stand 2026-09-09

Wird **überschrieben**, nicht angehängt. Verlauf und Messaufbauten stehen in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).

## Sofort zu wissen

Der noch **nicht committete** Arbeitsbaum enthält jetzt eine zweistufige
OCR-Kalibrierung: äußeres perspektivisches `roi_quad` und inneres `ocr_box` mit
sichtbarem Leseraster. Außerdem umfasst er die zuvor implementierte
Entkopplung des Bildpfads, OCR-Drosselung und `dispread stop`. Der letzte
committete Kamera-Sicherheitsstand ist `d486924`; das persistente
RP2040-Zyklusbudget wurde nicht verändert.

Am Sessionende läuft PID 97945 auf `100.122.154.35:7777` mit 960×720 bei 15 fps
und Profilschema 3. Er wurde vor der letzten Raster-Aktualisierung gestartet
und enthält eine ungespeicherte (`dirty=true`) bestätigte Quad-/OCR-Geometrie;
deshalb wurde er nicht ungefragt beendet. Profil bewusst speichern oder
verwerfen und danach kontrolliert mit `dispread stop` neu starten, damit die
letzte Editor-Korrektur geladen wird. Die ungetrackte Datei
`PLANNED_FEATURES.md` war als fremde Arbeitsbaumänderung sichtbar und wurde
nicht verändert.

## Implementierter Stand

- Der eingefrorene Browsereditor zeigt die grüne Perspektiv-ROI sowie einen
  gelben inneren OCR-Rahmen, Vorzeichenbereich, Ziffernzellen und alle sieben
  tatsächlichen Segment-Abtastpunkte.
- Anklicken eines Rahmens oder `g` wählt ihn aus. Ziehen/Pfeile verschieben den
  aktiven Rahmen; Eckziehen beziehungsweise Shift+Pfeile skalieren ihn.
- Änderungen an Ziffernzahl, Nachkommastellen, Vorzeichen und Rasterverhältnis
  werden während des Editierens aus dem aktuellen Status übernommen. Ein
  cyanfarbener Kreis markiert die profilfeste Dezimalposition. Reine
  Layoutänderungen halten das eingefrorene Bild bestätigbar; Kamera- und andere
  Profiländerungen invalidieren es weiterhin.
- `roi_quad` entzerrt die Displayebene. `ocr_box` schneidet darin nur
  Vorzeichen und Ziffern aus, bevor der Ausschnitt auf 400×160 skaliert und an
  `SevenSegmentReader` gegeben wird. Fokus- und Live-Overlay verwenden dieselbe
  Geometrie.
- Profilschema 3 speichert `ocr_box` normiert im entzerrten ROI-System.
  Schema-1- und Schema-2-Profile werden mit vollem Innenrahmen migriert.
- Annotation schema 2 speichert Quad und OCR-Rahmen mit explizit getrennten
  Koordinatensystemen.
- Nach ROI-Bestätigung entfällt die Vollbild-Kandidatensuche; OpenCV/JPEG hält
  den Controller-Lock nicht, OCR-Vorschau läuft mit 5 Hz. `dispread stop`
  beendet einen neuen Dienst über den lokalen Unix-Socket mit begrenztem
  Kameraabschluss.

Eine automatische Ziffern-Grenzerkennung wurde nicht als bestätigte Geometrie
eingebaut. Ohne mehrere gelabelte Realbilder kann ein Einzelbild leuchtende
Segmente, Blende, Einheit, Reflexionen und Dezimalpunkte nicht sicher trennen.
Der manuelle Rahmen macht keine Vermutung und erfüllt damit die Pflicht,
unbekannte Eingaben abzulehnen statt zu raten. Ein späterer automatischer
Vorschlag bleibt möglich, muss aber durch den Bediener bestätigt und an einem
getrennten Real-Testset bewertet werden.

## Verifiziert

```text
./.venv/bin/pytest -q                                      84 passed
./.venv/bin/ruff check .                                  All checks passed!
node --check src/dispread/workbench/static/workbench.js   erfolgreich
git diff --check                                           erfolgreich
```

Neue Tests belegen Schema-1/2-Migration, ungültige OCR-Rahmen, die Übergabe von
Quad und `ocr_box` aus dem Befehlspfad sowie eine korrekte synthetische Lesung,
wenn die äußere ROI absichtlich Rand enthält und der innere Rahmen das
Ziffernraster kalibriert. Ein weiterer Regressionstest ändert Ziffernzahl und
Nachkommastellen bei offenem Editierbild, prüft das aktualisierte Raster und
bestätigt anschließend erfolgreich. Die vorhandenen Tests für perspektivische
Entzerrung, Controller-Reaktion und lokalen Shutdown bleiben grün.

Das zuvor dokumentierte Offline-Verarbeitungsbudget am gespeicherten
960×720-Realbild bleibt: 30,837 ms/Bild unbestätigt mit Vollbildsuche,
5,801 ms/Bild bestätigt mit gedrosselter OCR und 9,515 ms/Bild bei OCR in jedem
Bild, jeweils 100 Aufrufe mit `time.perf_counter()` / `CLOCK_MONOTONIC`. Das ist
keine Browser-, Kamera- oder Ende-zu-Ende-Latenz.

## Offene reale Abnahme

Das vorhandene BK-5491B-Bild (`-000.13 mV`) wurde vom bisherigen Raster sicher
abgelehnt. Der neue Innenrahmen kann die bekannte Rasterverschiebung beseitigen;
ob die abweichenden VFD-Glyphen danach mit den festen relativen Segmentpunkten
zuverlässig lesbar sind, bleibt OQ-23 und braucht mehrere gelabelte Entwicklungs-
und Testbilder. Referenzwerte bleiben außerhalb von Reader und Gate.

Nach dem nächsten Serverstart müssen grüne ROI und gelber OCR-Rahmen im echten
Windows-Browser kalibriert und OQ-24 (Reaktion, Bildrate, Ctrl-C und
`dispread stop`) real abgenommen werden. Keine neue Abhängigkeit, keine
physische Einstellung und keine dauerhafte Hardwarekonfiguration kamen hinzu.
Das GSVmulti-Format bleibt unbekannt und unverändert.
