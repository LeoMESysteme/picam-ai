# Datensatz-Sammelmodus: reale Prüfbilder ohne Kalibrierung sammeln

Ein geführter Bedienablauf in der bestehenden Kamera-Workbench, mit dem sich
reale Prüfbilder unterschiedlicher Messverstärker sammeln lassen — ohne
Segmentraster, ohne bestätigtes Produktionsprofil. Ergänzt den bestehenden
Werkbankablauf, berührt dessen Freigaberegeln aber nicht. Der Live-Messpfad
ist in [Kapitel 10](10-kamera-livevorschau.md#live-seite-live) beschrieben;
serielle Ausgabe an GSVmulti bleibt offen ([OQ-07](../open-questions.md#oq-07)).
Der Sammelmodus ist kein Ersatz für den noch geplanten Dauerbetrieb aus
[Kapitel 9](09-betrieb.md).

> Diese Datei liegt bewusst außerhalb der Nummerierung 0–9 des
> [Lernpfads](README.md), analog zu
> [Kapitel 10](10-kamera-livevorschau.md): sie erklärt einen fertigen,
> bedienbaren Prototyp, nicht eine Bauaufgabe mit „Gerüst, Test, Fallen".

## Start

Wie in [Kapitel 10](10-kamera-livevorschau.md) beschrieben `dispread serve`
starten und im Browser anmelden. Im Header oben rechts **„Datensatz
sammeln"** öffnet den eigenen Bereich; **„logout"** schließt beide Ansichten
gemeinsam. Die normale Kamera-/Einstellansicht bleibt währenddessen erreichbar
über denselben Knopf (Umschalter, kein zweiter Kamerazugriff — es wird
`self.raw` des bereits laufenden Kamerabesitzers verwendet).

## Ablauf

Drei Schritte, nur der jeweils aktuelle ist aufgeklappt; ein erledigter
Schritt klappt zu einer Einzeiler-Zusammenfassung zusammen (z. B. „Gerät:
GSV-2ASD ✓") mit einem „ändern"-Knopf, um ihn erneut zu öffnen.

1. **Schritt 1 — Gerät**: Ein `<select>` listet bereits angelegte Geräte
   (`dataset.device.list`). Ein vorhandenes Gerät auswählen genügt — dafür
   ist **kein** erneutes Anlegen nötig, auch nicht nach einem Neuladen der
   Seite. Die letzte Option „+ neues Gerät anlegen" blendet das Formular ein:
   Anzeigename, die Bestätigung „Dieses konkrete physische Gerät", ein Beleg
   der Identitätsbestätigung sowie — versteckt hinter „Weitere Angaben" —
   optional Modell, eine kurze technische Familienkennung (z. B. `gsv2asd`)
   und Technologie (LED/LCD/VFD/sonstige). Der Server vergibt eine
   unveränderliche UUID — der Anzeigename ist keine Identität und kann später
   geändert werden, die UUID nicht. **Entwicklung oder Abschlusstest wird
   hier festgelegt und ist ab der ersten Aufnahme gesperrt**
   (`update_device` lehnt einen Splitwechsel danach ab).
2. **Schritt 2 — Situation**: Hat das gewählte Gerät bereits genau eine
   Situation, wird sie automatisch fortgesetzt und der Schritt bleibt
   zugeklappt — bei mehreren erscheint eine Liste zum Fortsetzen, bei keiner
   nur das Eingabefeld für eine neue. „Was hat sich geändert?" kurz
   beschreiben (Blickwinkel, Entfernung, Ziffernzahl, Vorzeichen, …).
   Wiederholungsaufnahmen derselben Situation bleiben in derselben Gruppe —
   das ist Absicht, sie zählen bewusst nicht mehrfach als unabhängig.
3. **Schritt 3 — Aufnahme**, sichtbar sobald Gerät und Situation stehen; die
   Kopfzeile zeigt „Gerät: X · Situation: Y" zur Bestätigung.
   1. **„● aufnehmen"** friert das aktuelle Kamerabild ein und zeigt es in
      der Vorschau. Das Livebild läuft im Hintergrund weiter, ändert die
      Vorschau aber nicht mehr.
   2. **Zielbox ziehen**: mit der Maus ein Rechteck über die gewünschte
      Zahlenzeile ziehen. Kein Segmentraster, keine Ziffernzellen nötig — nur
      eine grobe Markierung für spätere Auswertung. Bei mehreren Anzeigen im
      Bild eine kurze Bezeichnung eintragen (z. B. „oben, Spannung").
   3. **Lesbarkeit wählen**: *lesbar* (dann den tatsächlich sichtbaren Text
      eintippen, inklusive Minuszeichen, führenden Nullen und Dezimalzeichen
      — z. B. `-01.25`, `.000`, `28,80`), *unlesbar* oder *unsicher*. Kein
      Referenzwert, kein OCR-Vorschlag — nur was auf der Anzeige tatsächlich
      zu sehen ist.
   4. **„Speichern und weiter"** speichert atomar und bleibt bei Gerät, Split
      und Situation, bis Schritt 1 oder 2 erneut über „ändern" geöffnet wird.
   5. **Ähnlichkeitswarnung**: ist eine neue Aufnahme einer bereits
      gespeicherten Probe derselben Situation optisch sehr ähnlich
      (Heuristik, [OQ-33](../open-questions.md)), erscheint ein Hinweis mit
      Begründungsfeld. Eine echte, bewusste Wiederholung lässt sich dort
      begründet bestätigen; Rohdaten, Warnung und Begründung bleiben in der
      Probe erhalten.
   6. **„als Vertreter dieser Situation markieren"** erscheint direkt nach
      dem Speichern. **Wichtig, sobald eine Situation mehrere Aufnahmen hat:**
      ohne einen ausdrücklich markierten Vertreter schließt der Export
      **alle** Proben dieser Situation aus (Grund `group_without_selection`)
      — bei genau einer Aufnahme je Situation ist der Knopf dagegen nicht
      nötig, sie wird automatisch Vertreter. Aktuell markiert dieser Knopf
      nur die zuletzt gespeicherte Aufnahme; eine Übersicht/Galerie, um auch
      ältere Proben einer Situation nachträglich zum Vertreter zu machen,
      ist noch nicht implementiert (`static/dataset.js`).
4. **„Prüfsatz exportieren"** (feste Zeile am Ende, unabhängig vom
   Schrittstand) erzeugt einen unveränderlichen Export mit Abdeckungsbericht
   (Anzahl Bilder, Geräte, Situationen, fehlende Bedingungen) und einen
   Downloadlink. Ein kleiner Export ist möglich, wird aber deutlich als
   unzureichend markiert, solange die Sammelziele aus
   [Roadmap P2](../ROADMAP.md) nicht erreicht sind.

Ein Schrittwechsel über „ändern" verwirft eine noch offene, nicht
gespeicherte Aufnahme automatisch (`dataset.discard`) — gespeicherte Proben
sind davon nicht betroffen.

Nach einem Browser- oder Serverneustart stehen Geräte und bereits
gespeicherte Proben unverändert wieder zur Verfügung; ein noch nicht
gespeicherter Entwurf (offene Aufnahme) geht verloren und muss neu
aufgenommen werden — genau das ist der Sinn der zeitlichen Begrenzung
offener Aufnahmen (zehn Minuten, siehe unten).

## Was Zielbox und Wert NICHT sind

Zielbox und eingetragener Wert sind reine Entwicklungs-/Prüfdaten. Sie
erreichen niemals `ValueReader`, `ReleaseGate`, den Tracker oder die
serielle Ausgabe — dafür bleibt ausschließlich der bestätigte manuelle
ROI-Pfad zuständig. Der Sammelmodus verspricht keine bessere OCR und ändert
keine Freigabeschwellen.

## Grenzen der Unabhängigkeitsheuristik

- Eine neue UUID oder eine neue Uhrzeit erzeugt für sich allein **keine**
  unabhängige Situation — erst eine bewusst eröffnete neue Situation tut das.
- Die Ähnlichkeitswarnung (OQ-33) ist ein unvalidierter Vorabdefault, kein
  Beweis für oder gegen tatsächliche Bildidentität.
- Pro Situation zählt für den Export nur eine ausdrücklich ausgewählte oder
  (bei genau einer Aufnahme) automatisch die einzige Probe; alle übrigen
  bleiben archiviert, aber nicht Teil des Prüfsatzes. Hat eine Situation
  **mehrere** Aufnahmen und keine davon wurde markiert, exportiert die
  gesamte Situation **null** Bilder — kein Zufallsgriff auf irgendeine der
  Wiederholungen.
- Der Export dedupliziert zusätzlich identische Bildinhalte über den
  *gesamten* Export hinweg (nicht nur je Situation) — das verlangt der echte
  Auswertungs-Loader (siehe unten).

## Limits

Höchstens zwei gleichzeitig offene (noch nicht gespeicherte) Aufnahmen,
insgesamt höchstens 64 MiB Rohbildspeicher dafür, Ablauf nach zehn Minuten.
Eine bereits gespeicherte Aufnahme zählt nicht mehr gegen dieses Limit. Ein
Klick auf „aufnehmen" während des alten Workbench-Modus `run`
(Vorschau mit festen Einstellungen, kein Produktionslauf) wird mit einer klaren
Fehlermeldung abgelehnt, nicht mit einer stillen Moduswechsel.

## Exportkompatibilität prüfen

```bash
./.venv/bin/python scripts/check-dataset-export.py --manifest PFAD/manifest.json
```

Ohne `--experiment-root` prüft das Skript nur Schema, relative Pfade und
Bildhashes lokal und meldet die Kompatibilität mit dem separaten
Erkennungsexperiment (`codex/automatic-seven-segment`, Commit `6a18bdf`)
ausdrücklich als **nicht geprüft**. Mit `--experiment-root
/pfad/zum/experiment-worktree` startet es zusätzlich dessen eigenen
`load_manifest()` in einem eigenen Prozess mit dessen eigener venv.

Aktuelle Exporte verwenden Schema 2 mit `label_origin`. Der externe
Experiment-Loader akzeptiert laut dokumentiertem Stand nur Schema 1;
`test_real_export_is_accepted_by_the_actual_experiment_loader` ist deshalb
`xfail(strict=True)`. Ein lokaler Prüferfolg ist kein Nachweis externer
Kompatibilität. Das Fremdprojekt bleibt bis zur Entscheidung aus
[TODO](../../TODO.md) unverändert.

## Fertig, wenn …

- [x] Ein reales, unkalibriertes Gerät lässt sich anlegen und mehrere
  Situationen mit korrekt zugeordnetem Rohbild und Label sammeln.
- [x] Nach einem Neustart sind Geräte und Proben wieder da; offene Entwürfe
  sind es nicht.
- [x] Ein verschiebbarer, unveränderlicher Prüfsatz lässt sich lokal prüfen
  (`tests/test_dataset_export.py`).
- [ ] Export-Schema 2 wird vom echten Experiment-Loader angenommen; derzeit
  wegen dessen Schema-1-Prüfung erwarteter Fehlschlag (`xfail(strict=True)`).
- [x] Der Sammelmodus besitzt eigene Tests für Speicher, Aufnahme, API,
  Oberfläche und Export. Historische Testzahlen ersetzen keinen aktuellen
  Prüflauf der gesamten Werkbank.
- [x] Ein bereits angelegtes Gerät lässt sich aus einer Liste auswählen statt
  es nach jedem Neuladen neu anlegen zu müssen; die drei Schritte
  Gerät/Situation/Aufnahme sind einzeln nachvollziehbar (Nutzerrückmeldung
  „zu unverständlich und umständlich" aus `docs/status.md`, behoben durch
  `dataset.device.list` + Schrittoberfläche in `static/dataset.js`).
- [x] Eine Situation mit mehreren Aufnahmen lässt sich tatsächlich
  exportieren: "als Vertreter markieren" direkt nach dem Speichern behebt
  den Nutzerfund vom 2026-09-21 ("0 Bilder beim Export", Ursache:
  `dataset.select` war im Backend fertig, aber nie mit einem Knopf in der
  Oberfläche verdrahtet — `test_marking_a_sample_as_representative_makes_the_group_exportable`).
- [ ] **Offen:** eine Übersicht/Galerie je Situation, in der auch *ältere*
  (nicht nur die zuletzt gespeicherte) Proben nachträglich als Vertreter
  markiert werden können, inklusive Ansicht Entwicklungs- vs.
  Abschlusstest-Bestand. Im aktuellen Frontend nicht vorhanden.
- [ ] **Offen:** ein echter interaktiver Klick-Durchlauf im Browser
  ([OQ-34](../open-questions.md#oq-34)); die historische Headless-Störung
  [OQ-21](../open-questions.md#oq-21) ersetzt keine aktuelle Browserabnahme.
- [ ] **Offen:** 30 unabhängige, reale Abschlusstestbilder über mindestens
  sechs Geräte/drei Familien gemäß [Roadmap P2](../ROADMAP.md). Die
  Zielhardware sind LCD-Anzeigen ([OQ-04](../open-questions.md#oq-04));
  zusätzliche LED/VFD-Proben sind Entwicklungsdaten und ersetzen diese
  Zielhardware nicht. Das bleibt Aufgabe des tatsächlichen Sammelbetriebs.
