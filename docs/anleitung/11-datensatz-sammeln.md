# Datensatz-Sammelmodus: reale Prüfbilder ohne Kalibrierung sammeln

Ein geführter Bedienablauf in der bestehenden Kamera-Workbench, mit dem sich
reale Prüfbilder unterschiedlicher Messverstärker sammeln lassen — ohne
Segmentraster, ohne bestätigtes Produktionsprofil. Ergänzt den bestehenden
Betrieb (ROI/Clip/OCR/Nachführung/Serial), berührt dessen Freigaberegeln aber
nicht. Kein Ersatz für `docs/anleitung/09-betrieb.md` oder Task 11 aus
`docs/status.md` — die dortige Sperre bleibt unverändert bestehen.

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

1. **Gerät anlegen** (einmalig je physisches Gerät): Anzeigename, optional
   Modell, eine kurze technische Familienkennung (z. B. `gsv2asd`),
   Technologie (LED/LCD/VFD/sonstige) und die Bestätigung „Dieses konkrete
   physische Gerät". Der Server vergibt eine unveränderliche UUID — der
   Anzeigename ist keine Identität und kann später geändert werden, die UUID
   nicht. **Entwicklung oder Abschlusstest wird hier festgelegt und ist ab
   der ersten Aufnahme gesperrt** (`update_device` lehnt einen Splitwechsel
   danach ab).
2. **Neue Situation**: kurz beschreiben, was sich geändert hat (Blickwinkel,
   Entfernung, Ziffernzahl, Vorzeichen, …). Wiederholungsaufnahmen derselben
   Situation bleiben in derselben Gruppe — das ist Absicht, sie zählen
   bewusst nicht mehrfach als unabhängig.
3. **„● aufnehmen"** friert das aktuelle Kamerabild ein und zeigt es in der
   Vorschau. Das Livebild läuft im Hintergrund weiter, ändert die Vorschau
   aber nicht mehr.
4. **Zielbox ziehen**: mit der Maus ein Rechteck über die gewünschte
   Zahlenzeile ziehen. Kein Segmentraster, keine Ziffernzellen nötig — nur
   eine grobe Markierung für spätere Auswertung. Bei mehreren Anzeigen im
   Bild eine kurze Bezeichnung eintragen (z. B. „oben, Spannung").
5. **Lesbarkeit wählen**: *lesbar* (dann den tatsächlich sichtbaren Text
   eintippen, inklusive Minuszeichen, führenden Nullen und Dezimalzeichen —
   z. B. `-01.25`, `.000`, `28,80`), *unlesbar* oder *unsicher*. Kein
   Referenzwert, kein OCR-Vorschlag — nur was auf der Anzeige tatsächlich zu
   sehen ist.
6. **„Speichern und weiter"** speichert atomar und bleibt bei Gerät, Split
   und Situation, bis „Neue Situation" erneut geöffnet wird.
7. **Ähnlichkeitswarnung**: ist eine neue Aufnahme einer bereits
   gespeicherten Probe derselben Situation optisch sehr ähnlich (Heuristik,
   [OQ-33](../open-questions.md)), erscheint ein Hinweis mit Begründungsfeld.
   Eine echte, bewusste Wiederholung lässt sich dort begründet bestätigen;
   Rohdaten, Warnung und Begründung bleiben in der Probe erhalten.
8. **„Prüfsatz exportieren"** erzeugt einen unveränderlichen Export mit
   Abdeckungsbericht (Anzahl Bilder, Geräte, Situationen, fehlende
   Bedingungen) und einen Downloadlink. Ein kleiner Export ist möglich, wird
   aber deutlich als unzureichend markiert, solange die Sammelziele (siehe
   `docs/status.md`) nicht erreicht sind.

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
  bleiben archiviert, aber nicht Teil des Prüfsatzes.
- Der Export dedupliziert zusätzlich identische Bildinhalte über den
  *gesamten* Export hinweg (nicht nur je Situation) — das verlangt der echte
  Auswertungs-Loader (siehe unten).

## Limits

Höchstens zwei gleichzeitig offene (noch nicht gespeicherte) Aufnahmen,
insgesamt höchstens 64 MiB Rohbildspeicher dafür, Ablauf nach zehn Minuten.
Eine bereits gespeicherte Aufnahme zählt nicht mehr gegen dieses Limit. Ein
Klick auf „aufnehmen" während `run` (Produktionslauf) wird mit einer klaren
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

## Fertig, wenn …

- [x] Ein reales, unkalibriertes Gerät lässt sich anlegen und mehrere
  Situationen mit korrekt zugeordnetem Rohbild und Label sammeln.
- [x] Nach einem Neustart sind Geräte und Proben wieder da; offene Entwürfe
  sind es nicht.
- [x] Ein vom echten Experiment-Loader akzeptierter, verschiebbarer,
  unveränderlicher Prüfsatz lässt sich exportieren
  (`tests/test_dataset_export.py`).
- [x] Normale ROI-/Clip-/OCR-/Tracking-/Serial-Flüsse laufen unverändert
  (bestehende Testsuite, `280+ passed`).
- [ ] **Offen:** ein echter interaktiver Klick-Durchlauf im Browser
  ([OQ-34](../open-questions.md)) — in dieser Entwicklungsumgebung wegen
  [OQ-21](../open-questions.md) nicht durchführbar.
- [ ] **Offen:** 30 unabhängige, reale Abschlusstestbilder über mindestens
  sechs Geräte/drei Familien/LED+LCD (Sammelziel aus `docs/status.md`) — das
  ist Aufgabe des tatsächlichen Sammelbetriebs, nicht dieser Implementierung.
