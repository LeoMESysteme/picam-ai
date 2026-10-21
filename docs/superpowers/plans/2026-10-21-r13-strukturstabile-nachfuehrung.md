# R13: Nachführung vom wechselnden Zahleninhalt trennen

**Freigegeben:** 2026-10-21. **Umsetzung vorgesehen:** 2026-10-23.
**Stand:** Plan gespeichert; Implementierung und neue Messungen noch offen.
Arbeitsliste: [TODO.md](../../../TODO.md),
offene Frage: [OQ-26](../../open-questions.md#oq-26).

## Ziel und Entscheidung

Die drei Subagents haben Bildverarbeitung, Sicherheitsgrenzen und Integration
unabhängig untersucht. Das Ziel: **Große Wertwechsel dürfen die Nachführung
nicht verlieren lassen; bei tatsächlich unsicherer Geometrie wird weiterhin
abgelehnt.**

Ausgangspunkt ist der strenge Werteplan-Lauf
`var/live/live-20261021T151835Z/run-01`: 806 s, 0/11 137 Fehllesungen bei
prüfbaren VALID, aber 8074 Trackingverluste. Bei Faktor 2 und 5 kein VALID
in stabilen Referenzfenstern, bei Faktor 1, 0,5 und 10 nahezu durchgehend
VALID. Keine Ausfallbilder aufgezeichnet; die angenommene Ursache muss
deshalb noch durch Bildbelege abgesichert werden.
[Abschlussauswertung](../../VALIDATION.md#messpfad-live-werteplan-2026-10-21).

Der erste Umfang ist der **GSV-2AS an zwei Kameraaufstellungen**. Die
Einrichtung schlägt automatisch geeignete Rahmenbereiche vor; bei Bedarf
kann die bedienende Person diese manuell auswählen.

| Untersuchte Idee | Bewertung |
| --- | --- |
| ECC-Schwelle senken | Verworfen: könnte falsche Zuordnungen akzeptieren. |
| Ziffern im bisherigen Ausschnitt ausmaskieren | Unzureichend: Der Ausschnitt enthält fast nur Zeichen. |
| Größeren Rahmenbereich mit ECC vergleichen | Kleinerer Umbau, aber schwierige Masken- und Koordinatenbehandlung. |
| Nur LCD-Kanten verfolgen | Nützlich zur Kontrolle; ähnliche oder verdeckte Kanten können mehrdeutig sein. |
| LK-/ORB-Merkmale verfolgen | Möglich, aber Vergleichsfenster können weiterhin Ziffern oder Hintergrund einbeziehen. |
| **Begrenzte Rahmenausschnitte vergleichen und LCD-Rand prüfen** | **Bevorzugter Kandidat:** verwendete Bildbereiche und Zuordnungen lassen sich gezielt prüfen. |

Der Kandidat erhält zuerst eine Eignungsprüfung an echten Bildern. Scheitert
diese, wird die Hauptintegration angehalten; es gibt keinen automatischen
Wechsel zu schwächeren Prüfungen.

## 1. Fehler reproduzierbar machen

- [ ] Eine begrenzte Diagnoseaufzeichnung aus dem vorhandenen `CameraOwner`
  ergänzen: ausgewählte unveränderte Vollbilder, zugehöriger Trackingbefund,
  Frame- und Owner-Sequenz, Aufnahmezeit samt Zeitbasis sowie Profil- und
  Referenzbildhash.
- [ ] Bilder asynchron und mit festen Speichergrenzen nach `/dev/shm`
  schreiben; anschließend sichern. Verluste und Schreibfehler sichtbar
  protokollieren. Keine zweite Kameraöffnung.
- [ ] Kurze Bildfolgen aller fünf Normierungsfaktoren sowie gezielte Bewegung
  und Abdeckung erfassen. Bedienereignisse ausdrücklich markieren; deren
  Meldezeit nicht als exakten physischen Ereigniszeitpunkt ausgeben.
- [ ] Den bisherigen Tracker offline auf diesen Bildern ausführen. Sichtbare
  LCD-Geometrie unabhängig prüfen und mindestens eine reale Fehlerfolge als
  Regression festhalten.

**Weiter geht es erst**, wenn der Fehler reproduziert und ausreichend breite,
eindeutige Rahmenstruktur am Gerät nachgewiesen ist.

## 2. Rahmenbereiche bestätigen und neuen Tracker einbinden

- [ ] OCR-Quad und Trackingbereiche getrennt halten. Automatisch mehrere
  räumlich verteilte Bereiche am Displayrahmen vorschlagen; Tisch, Kabel,
  Hintergrund und Zeichenbereich ausschließen.
- [ ] Manuelle Korrektur auf dem eingefrorenen Einrichtungsbild ermöglichen.
  Auch manuelle Auswahlen müssen dieselben Qualitätsprüfungen bestehen.
- [ ] Die Auswahl an Bildhash und Vorschlagsrevision binden. Veraltete
  Bestätigungen und Änderungen während eines Laufs ablehnen.
- [ ] Ein optionales, versioniertes `live_tracking`-Feld im Profil ergänzen.
  Alte Profile bleiben unverändert les- und speicherbar; alter und neuer
  Trackingmodus werden im Laufartefakt ausdrücklich unterschieden.
- [ ] Den neuen Tracker ausschließlich im Live-Locator verwenden.
  Allgemeiner `QuadTracker`, OCR-Raster, Leser und Gate behalten ihre
  bisherigen Schnittstellen.

Neue Einrichtungen dürfen mit dem neuen Verfahren nur starten, wenn die
bestätigten Rahmenbereiche geeignet sind.

## 3. Bewegung aus festen Rahmenstrukturen bestimmen

- [ ] Kleine Referenzausschnitte direkt aus dem Rohbild vergleichen.
  **15 × 15 Pixel** dienen als technische Startvorgabe; keine Bildpyramide
  oder ungeprüfte Glättung, die Zeichen in den Vergleich hineinzieht.
- [ ] Suchbereiche begrenzen, strukturarme Ausschnitte und mehrdeutige
  Treffer ablehnen. Die tatsächlich ausgewerteten Pixel einschließlich
  Interpolation müssen innerhalb geeigneter Rahmenflächen liegen.
- [ ] Mehrere räumlich getrennte Übereinstimmungen verlangen. Daraus mit
  robuster Ausreißerprüfung ausschließlich **Translation und Rotation**
  bestimmen; keine Skalierung, Scherung oder freie Homographie.
- [ ] Den aktuell sichtbaren LCD-Rand unabhängig gegenprüfen. Ein lediglich
  mitverschobenes Referenzpolygon genügt nicht als Bestätigung.
- [ ] Die akzeptierte Bewegung vorwärts auf das ursprüngliche OCR-Quad
  übertragen. Referenzbild und Referenzgeometrie bleiben fest; bei Verlust
  gibt es keinen Rückgriff auf das letzte gültige Quad.

Matchinggrenzen, Suchraum und Laufzeit werden am Entwicklungsdatensatz
festgelegt, dokumentiert und **vor der getrennten Abnahme eingefroren**.
Unzureichende Struktur oder Laufzeit beendet die Eignungsprüfung. Grundlage
ist das vorhandene
[OpenCV-Template-Matching](https://docs.opencv.org/4.10.0/df/dfb/group__imgproc__object.html);
zusätzliche Bibliotheken sind nicht vorgesehen.

## 4. Sicherheit und Wirksamkeit prüfen

### Automatisierte Regressionen

- [ ] Große Ziffern-, Vorzeichen- und Dezimalpunktwechsel bei fester Geometrie.
- [ ] Display bewegt sich vor unbewegtem Hintergrund; Hintergrund bewegt
  sich bei festem Display.
- [ ] Kleine Translation und Rotation: alle vier Quad-Ecken stimmen
  innerhalb der bestehenden synthetischen Toleranz von ±2 Rohbildpixeln.
- [ ] Gleichförmige oder wiederholte Rahmenstruktur, Teilverdeckung,
  vollständige Verdeckung und Bewegung außerhalb der Grenzen.
- [ ] Nach Wiederkehr erneut normale Mehrbildbestätigung; kein
  fortgeschleppter Wert und keine Verkettungsdrift.
- [ ] Verdeckte Zahlen bei sichtbarem Rahmen: Tracking darf funktionieren,
  eine Zahlenfreigabe nicht.
- [ ] Alte Profile, injizierte Locator-Factories, Diagnoseverluste und
  manipulierte Referenzwerte.

### Reale Wiederholungsprüfung an zwei Aufstellungen

- [ ] Je mindestens zehn Minuten, alle fünf Faktoren; beim zweiten Lauf
  andere Reihenfolge.
- [ ] **0 falsche prüfbare VALID**, mindestens **99 % VALID je stabilem,
  vollständig referenzgedecktem Faktorfenster** außerhalb markierter Störungen.
- [ ] Markierte Bewegungs- und Abdeckversuche: keine VALID bei sichtbar
  unlesbarer Anzeige oder ungesicherter Geometrie.
- [ ] Wiedererfassung nach Wiederkehr innerhalb des zulässigen Bereichs
  spätestens nach **30 verarbeiteten Bildern**, anschließend reguläre
  Wertbestätigung.
- [ ] Ziel mindestens **27 verarbeitete Bilder/s**, keine Audit- oder
  Referenzverluste; Rückstellung bestätigt. Große Sprünge über serielle
  Befehlspausen liefern weiterhin keine belastbare Verzögerungsmessung.

Ein Fehlschlag führt zur Ursachenprüfung und neuer getrennter Abnahme,
nicht zum Nachziehen der Grenzen am Abnahmedatensatz.

## 5. Dokumentation und Freigabe

- [ ] Architekturentscheidung samt verworfenen Alternativen, CHANGELOG,
  Live-Anleitung, Tour und Tour-Fakten gemeinsam aktualisieren.
- [ ] Messzahlen nach VALIDATION, Aufbau und Deutung ins Laborjournal;
  Status und TODO nachführen.
- [ ] OQ-26 bis zur weitergehenden Gerätevalidierung offen halten.
  OQ-44 und OQ-45 bleiben eigene Aufgaben.
- [ ] OQ-Index bei TODO-/OQ-Änderungen aktualisieren; vor dem Merge
  `./scripts/docs-site.sh build -s` und
  `npx playwright test -c playwright.docs.config.ts` ausführen.

## Wiedereinstieg am 2026-10-23

Mit Abschnitt 1 beginnen. Es wurde noch keine Diagnoseaufzeichnung oder
Tracker-Implementierung für diesen Plan begonnen. Den Zustand der Werkbank
und eventuell laufende Messungen vor Tests oder Hardwarezugriff neu prüfen.
Python, pytest und ruff ausschließlich über die Projekt-`.venv` aufrufen;
die Abhängigkeiten bleiben Debian-Systempakete (AGENTS.md).
