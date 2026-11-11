# GSVmulti-Versuche: Lücken und Fehlwerte bei UserDefined (OQ-51)

**Ziel:** Herausfinden, wie ungültige Abschnitte und die echte Zeit in einer GSVmulti-Aufnahme erhalten bleiben, ohne GSVmulti zu ändern.

**Hintergrund** ([Recherche](../../.superpowers/sdd/2026-11-06-bruecke-ui/gsvmulti-fehlwerte-recherche.md) und [Beleg 11.11.](../../docs/quellen/bruecke-testlauf-2026-11-11/README.md)):
- Die TDMS ist äquidistant (Handbuch S. 73). GSVmulti zählt also Werte und misst keine Zeit.
- Eine Lücke kann deshalb nur als Wert im Telegramm überleben.

**Sender:** `tools/gsvmulti_versuche.py` schreibt erfundene Testwerte mit festen 10 Hz auf COM7. GSVmulti hört auf COM8. Pi und Brücken-App werden dafür nicht gebraucht.
- Die Brücken-App vorher **beenden**, sonst ist COM7 belegt.
- Jeder Lauf schreibt ein Protokoll `versuch-<n>-<zeit>.jsonl` mit Tick, Soll- und Istzeit und Telegramm.

```powershell
cd ...\picam-ai\windows\bridge
py -3.13 -m pip install pyserial
py -3.13 tools\gsvmulti_versuche.py --port COM7 --versuch 1
```

**Allgemein:**
- Vor jedem Versuch die Session speichern.
- Nach einer Änderung der Wertezahl oder des Trennzeichens GSVmulti komplett neu starten (OQ-52).
- Die Aufnahme erst nach dem Senderstart beginnen und vor dem Sendeende stoppen.
- Den `dt mode` notieren.
- Nach jedem Versuch die TDMS (+ `_index`) und das JSONL-Protokoll aufheben.

## Versuch 1: Vier Kanäle in einem Telegramm (Erfolgsaussicht hoch)

**Einstellung:** UserDef, Präfix `%`, Number of values = **4**, Trennzeichen **Semikolon**, „Filter-Out Non-Numeric“ aus. Bei „Add Channel“ alle Eingangskanäle öffnen, Frequenz 10 Hz.

**Telegramm** (600 Ticks): `%0.50001;1;1;1789123456.123456` = Wert; gültig (1/0); Sequenz; Uhrzeit des Senders in s.

**Erfolg:**
- Die TDMS hat 4 Kanäle und 600 Zeilen.
- Die Sequenz läuft lückenlos von 1 bis 600.
- Der Zeitkanal hat mindestens 6 Nachkommastellen und ist identisch mit dem Protokoll.

## Versuch 2: Fester Takt erhält eine Lücke (hoch, braucht Versuch 1)

**Einstellung:** wie in Versuch 1, zuerst mit `dt mode` = `1/f0`, dann noch einmal mit `tf`.

**Telegramme:**
- 100 gültige Ticks,
- 50 ungültige (Wert `0`, gültig `0`; Sequenz und Zeit laufen weiter),
- 100 gültige.

Die `0` ist nur ein Platzhalter für diesen Test, im Messpfad nie.

**Erfolg:**
- 250 Zeilen.
- Der Gültigkeitskanal zeigt genau 50 Nullen an der richtigen Stelle.
- Zeilennummer × dt stimmt auf 0,1 s mit dem Zeitkanal überein.

## Versuch 3: Marker im Wertkanal (mittel)

**Einstellung:** einkanalig wie heute (Number of values = 1).

**Telegramme:**
- Abwechselnd je 50 Ticks `%0.5` und 50 Ticks Marker.
- Marker der Reihe nach: `1E+300`, `1e300`, `+1.0E+300`, `99999999.0`, `NaN`, `+NaN`, `Inf`.

**Beobachten:**
- Welche Schreibweise steht unverändert in der TDMS/TXT?
- Zeigt GSVmulti den Wert oder ein Timeout?
- Wie verhält sich die Grafik (Autoscale)?

**Erfolg:** Mindestens ein Marker erscheint in der Aufnahme, und die Folgewerte gehen dabei nicht verloren.

## Versuch 4: Aufnahme per Schwelle starten und beenden (mittel)

**Einstellung:** wie in Versuch 1. Dazu:
- Configure Recording → Trigger Recording: Start automatisch bei „Value exceeds threshold“ auf **Kanal 2** (gültig), Schwelle 0,5.
- Ende bei „drops below“.
- Replace Missing aus.

**Telegramme:** 5 s ungültig, dann 60 s gültig, dann 5 s ungültig, durchgehend mit 10 Hz.

**Erfolg:**
- Die Aufnahme beginnt mit dem ersten gültigen Tick und endet mit dem letzten.
- Sie hat 600 ± 1 Zeilen.

## Versuch 5: Pausen ohne Bytes (niedrig, Gegenprobe)

**Einstellung A:** Replace Missing values an, vierkanalig wie in Versuch 1.

**Einstellung B:** Data Reduction „One value per time interval“ 1 s, Mean.

**Telegramme:** je 100 gültige Ticks, dazwischen Pausen von 2, 4, 8 und 30 s, in denen gar nichts gesendet wird.

**Erfolg:** Die Pause bleibt als Marker-Zeile oder Zeitlücke sichtbar. Zu erwarten ist das nach Lauf 08/10 nicht; dann ist die Frage für UserDef abschließend negativ beantwortet.

## Ergebnisse

Belege liegen in [`docs/quellen/gsvmulti-versuche-2026-11-11/`](../../docs/quellen/gsvmulti-versuche-2026-11-11/).

**Versuch 1a (2026-11-11):** Session noch einkanalig (`NumChan = 1`, `Frequency = 1`, `Separator = 256`), Sender mit vierkanaligen Telegrammen.
- **Ergebnis:** 600 von 600 Telegrammen aufgezeichnet, in Reihenfolge und ohne Verlust. GSVmulti nimmt aus `%wert;gültig;seq;zeit` den **ersten Wert** und ignoriert den Rest.
- Ein einkanalig eingestelltes GSVmulti verträgt damit das Mehrkanal-Telegramm.
- Der Sender war höchstens 42 ms verspätet.
- Die Zeitachse ist äquidistant (`tf`, 0,1019 s), weil die Aufnahme um etwa 1 s länger lief als das Senden.
- Offen bleibt der eigentliche Versuch 1 mit `NumChan = 4` und dem Trennzeichen Semikolon.
