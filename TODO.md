# TODO — Stand 2026-09-22, Abend

Diese Datei ist der Wiedereinstieg. Sie soll genug Kontext tragen, dass man
morgen weitermachen kann, **ohne erst zu recherchieren**. Tiefe Begründungen
stehen in den verlinkten Dateien; hier steht, was zu tun ist und warum.

Die verbindliche Einstiegsreihenfolge (`CLAUDE.md`) gilt weiter —
`docs/status.md` ist die erste Datei. Diese hier ist die Arbeitsliste daneben.

---

## ⚠ Zuerst: der Pi braucht einen Reboot

**Die Kamera ist blockiert.** Der Sensor setzt keinen Stream mehr auf; nur ein
Neustart hilft ([OQ-22](docs/open-questions.md)). Ursache ist bekannt und
behoben, aber der aktuelle Zustand überlebt keinen Fix — nur den Reboot.

Symptom zum Wiedererkennen: `rpicam-hello --list-cameras` meldet den IMX500
**vollständig und normal**, aber jeder Streamversuch endet im Timeout, und
`dmesg` zeigt `rp1-cfe … stream on failed in subdev`. Enumeration ≠
Bilddurchlauf.

```bash
sudo reboot
```

### Danach, in dieser Reihenfolge — nicht abkürzen

```bash
# 1. Enumeration (sagt wenig, aber muss stimmen)
rpicam-hello --list-cameras

# 2. Kurzer, echter Bilddurchlauf. NICHT laenger, NICHT groesser.
cd ~/picam-ai
timeout 60 ./.venv/bin/python scripts/sync-record.py \
    --duration 10 --source camera --frame-rate 5 --image-format jpg \
    --output var/diagnostics/smoke-$(date +%H%M%S)

# 3. Nachsehen, ob wirklich Bilder UND Zeitstempel da sind
ls var/diagnostics/smoke-*/frames | wc -l      # muss > 0 sein
head -n1 var/diagnostics/smoke-*/frames.jsonl  # SensorTimestamp muss != 0 sein
```

**Erst wenn Schritt 2 und 3 sauber durchlaufen**, längere Aufzeichnungen
starten. Der Kamerazweig von `sync-record.py` ist **noch nie erfolgreich**
gegen echte Hardware gelaufen.

> **Nicht anfassen:** `--camera-size` über 960×720. Das Skript weist es jetzt
> hart ab; der Weg drumherum (`--allow-large-sensor-mode`) kostet im Zweifel
> den nächsten Reboot. Mehr Ziffernhöhe kommt über `ScalerCrop`, nicht über
> den Sensormodus.
>
> **Und:** einen hängenden Kameraprozess **nicht** sofort abschiessen — der
> Kill ist selbst ein dokumentierter Auslöser der Blockade.

---

## Wo wir stehen

Der **Sollwertkanal steht**: der GSV-2AS liefert über RS232 im ASCII-Modus
Telegramme, deren Zeichenkette der Displayanzeige entspricht, ≈ 1,88/s, über
1125 Telegramme ohne eine einzige Formatabweichung.

Der **Engpass ist nicht mehr die Datenmenge, sondern die Ziffernvielfalt** —
und dafür gibt es seit heute einen funktionierenden Hebel (unten, Aufgabe 2).

Der **Dot-Matrix-Leser steht weiterhin an seinem nicht bestandenen Gate**
(vier Verankerungsverfahren gemessen, bestes 67,9 %, verlangt sind 70 %). Das
wird erst wieder angefasst, wenn ein grösserer Datensatz da ist — mit 11
Proben lässt sich ein Verfahren nicht gleichzeitig entwickeln und validieren.

---

## Die Aufgaben

### 1. Versatz zwischen Telegramm und Anzeige messen — **der Blocker**

Ohne diese Zahl gibt es kein Schutzintervall M, und ohne M darf kein einziges
Bild automatisch gelabelt werden. Alles andere hängt daran.

**Verfahren** (Details: Plan, Task B): Kamera und seriellen Strom gleichzeitig
aufzeichnen, dann **photometrisch** auswerten — gemessen wird nur, *wann* sich
das Glas ändert, nicht *was* dort steht. Das ist der Trick, der die
Zirkularität bricht: der Leser funktioniert ja noch nicht.

**Ein Entwurf der Auswertung liegt bereit**, aber ungetestet — er ist nie
gegen echte Aufzeichnungsdaten gelaufen, weil es noch keine gibt:
`var/diagnostics/gsv-serial-2026-09-22/offset_ensemble_entwurf.py`. Kern:
Anzeigebereich je Bild über `lcd_quad_in_region`
(`src/dispread/workbench/vision.py`, 11/11 auf den GSV-Proben),
Bild-zu-Bild-Differenz, auf jeden Telegrammwechsel ausrichten und über alle
Ereignisse mitteln. Vor dem Gebrauch durchlesen und gegen das tatsächliche
Feldformat von `frames.jsonl` prüfen — der Entwurf entstand, bevor
`sync-record.py` seine Felder festgelegt hatte.

**Zwei Populationen getrennt auswerten** — das ist die Selbstkontrolle: die
wenigen **grossen** Sprünge und das Ensemble der **kleinen** Wechsel. Stimmen
beide überein, trägt das Verfahren. Weichen sie ab, mittelt das kleine
Ensemble Rauschen, und nur die grossen Sprünge sind verwertbar.

**M wird nicht gewählt, sondern gerechnet.** Die Formel steht **vorab
festgeschrieben** im Plan, damit sie nicht an die Ausbeutetabelle angepasst
wird:

```
M = |δ| + d_misch + 3·σ_δ + 40 ms
```

→ `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`, Task B und
Festlegung 3.

---

### 2. Ziffernvielfalt über den Normierungsfaktor holen

**Das ist der Hebel, der heute gefunden und gemessen wurde.** Der Stimulus
taugt nicht als Vielfaltsquelle: das Schutzintervall kostet 44 % der Bilder,
aber **88 % der verschiedenen Zeichenketten** — die Vielfalt steckt in ein bis
zwei Telegramme kurzen Ausschlägen, genau die verwirft das Fenster.

Stattdessen: `set norm` (16) + `set dpoint` (17) über RS232 verändern die
Anzeige bei **festem** Stimulus, und jeder Wert steht beliebig lange still.
Alles Nötige ist gemessen:

* Der ASCII-Strom folgt der Normierung (Verhältnis 1,9963 bei Faktor 2,0).
* `EEnow = 0` → **kein EEPROM-Verschleiss** bei hunderten Wechseln.
* Die Plateaulänge ist vom Faktor **unabhängig** (p50 0,6–1,0 s über drei
  Grössenordnungen) — die Faktorwahl ist frei.
* Die Umrechnungsvorschrift ist gegen das Gerät bestätigt.

**Zu bauen:** ein Ernte-Skript, das Normierungsfaktoren abfährt und dabei
`sync-record.py` laufen lässt. **Bewusst noch nicht gebaut** — es stünde sonst
auf drei Unbekannten gleichzeitig (ungetesteter Kamerazweig, ungemessenes M,
ungemessene Lückenschwelle). Erst Aufgabe 1 und der Kamera-Smoke-Test.

**Rückstellpunkt nicht vergessen:**
`var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json`. Ausgangszustand
ist norm = 1,0, dpoint = 1, unit = mV/V, digits = 6, mode = 2 (ASCII).
Erneut auslesen mit `scripts/gsv-registers.py` (nur Lesebefehle).

Arbeitendes Beispiel für die Befehlsebene:
`var/diagnostics/gsv-serial-2026-09-22/norm_sweep.py` (selbstrücksetzend).

---

### 3. Lückenschwelle des Labelers messen ([OQ-40](docs/open-questions.md))

`scripts/gate-label.py` verlangt `--max-gap-ms` **ohne Vorgabewert** — eine
erfundene Schwelle wäre eine unbelegte Zahl an genau der Stelle, wo
Belegbarkeit zählt.

Warum es zählt: fällt ein Telegramm aus, sieht der Strom durchgehend aus,
obwohl dazwischen ein **anderer** Wert gestanden haben kann. Ein Bild aus
dieser Lücke bekäme ein falsches Label, das wie Wahrheit aussieht.

Datenlage: über 1125 Telegramme min 502 ms, p50 553 ms, p95 555 ms, max
562 ms — sehr eng, **kein einziger Ausfall**. Aber eine Aufzeichnung ohne
Ausfälle sagt nichts darüber, wie ein Ausfall aussieht. Nötig: längere Strecke
**und** eine Messung unter Last (Kamera läuft parallel, USB ausgelastet).

---

### 4. Kleinere offene Punkte

* **`session.json` fehlt bei `SIGTERM`.** Heute beobachtet: zwei hart
  beendete `sync-record.py`-Läufe hinterliessen keine `session.json`, obwohl
  der `finally`-Block sie schreiben soll. Getestet war nur `SIGINT` (Ctrl-C).
  Ein `SIGTERM`-Handler fehlt. Kleine Sache, aber sie kostet im Ernstfall die
  Metadaten einer langen Aufzeichnung.
* **`camera-commissioning.sh` prüft keinen Bilddurchlauf.** Es meldet
  „einsatzbereit", während der Sensor blockiert ist — heute erneut erlebt.
  Steht als Punkt (d) in [OQ-22](docs/open-questions.md). Eine echte
  Aufnahmeprüfung würde genau die Verwechslung verhindern, die heute zwei
  Reboots gekostet hat.
* **Export reicht `label_origin` nicht weiter.** `manifest.json` trägt die
  Herkunft nicht mit; im Export ist der Datensatz also nicht entmischbar.
  Braucht eine eigene `EXPORT_SCHEMA_VERSION` und einen Test.
* **Vorzeichenstelle bleibt unbelegt.** Negative Normierung gibt es erst ab
  Firmware 1.5.06, dieses Gerät hat 1.3.07; die Stimulatoren erzeugen keine
  negativen Werte. Ein Leser, der nie ein `-` gesehen hat, ist dort ungeprüft
  — **das gehört an jede Benchmarkzahl geschrieben**. Einziger bekannter Weg
  wäre `set zero` (Nullpunktabgleich), ein Eingriff in die Messkette des
  Laborgeräts — bewusst nicht angefasst.

---

## Was nicht vergessen werden darf

Diese Regeln sind **vorab festgelegt** worden, damit sie nicht nachträglich an
ein Ergebnis angepasst werden (Plan, Abschnitt „Vorab-Festlegungen"):

1. **Exakte Zeichenkettengleichheit.** Keine Toleranz auf der letzten Stelle,
   kein Runden, kein „nächstgelegener Wert". Fällt die Ausbeute klein aus, ist
   sie klein.
2. **Bilder im Schutzfenster bekommen keinen geratenen Wert** — sie fallen
   raus oder bekommen `label_state="uncertain"`.
3. **M fällt aus der Formel, es wird nicht ausgesucht.**
4. **`independence_group` je Aufnahmesitzung**, nicht je Bild. 4700 Bilder
   einer Ruheaufzeichnung sind **eine** Beobachtung, nicht 4700 — sonst ist
   der Split wertlos und die Prüfmenge nur eine Kopie der Entwicklungsmenge.
5. **Jede Benchmarkzahl nennt die Herkunftsmischung** (`manual` vs.
   `serial_ascii`) und die unbelegte Vorzeichenstelle.

---

## Landkarte — wo steht was

| Frage | Datei |
| --- | --- |
| Aktueller Stand, Blocker | `docs/status.md` |
| Warum so und nicht anders, Plan mit Tasks A–H | `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md` |
| Alle Messzahlen dieses Tages | `docs/VALIDATION.md` (Einträge 2026-09-22) |
| Aufbau, Deutung, Irrwege | `docs/lab_journal.md` |
| Offene Fragen | `docs/open-questions.md` — **OQ-22** (Kamera-Blockade), OQ-38 (Zeitkopplung), OQ-39 (Abdeckung), **OQ-40** (Lückenschwelle); OQ-37 ist beantwortet |
| Dot-Matrix-Leser, nicht bestandenes Gate | `docs/superpowers/plans/2026-09-22-dotmatrix-backend.md` |
| Rohdaten und Messkripte | `var/diagnostics/gsv-serial-2026-09-22/` (gitignored) |

### Werkzeuge, die heute entstanden sind

| Skript | Zweck | Stand |
| --- | --- | --- |
| `scripts/gsv-registers.py` | Registerstand als Rückstellpunkt, **nur Lesebefehle** | läuft, verifiziert |
| `scripts/sync-record.py` | Kamera + serieller Strom, beide CLOCK_BOOTTIME | synthetisch getestet, **Kamerazweig nie erfolgreich gelaufen** |
| `scripts/gate-label.py` | Offline-Gate, entscheidet rein über Zeitstempel | 9 Tests, nie auf echten Daten gelaufen |
| `scripts/migrate-samples-v1-to-v2.py` | Schemamigration | gelaufen, erledigt |
| `scripts/dotmatrix-grid-probe.py` | Rasterfit-Diagnose | läuft, Gate nicht bestanden |

### Fallstricke, die schon Zeit gekostet haben

* **`0x3B`-Präfix** bei GSV-Registerantworten — die Anleitung zählt nur die
  Datenbytes. `scripts/gsv-registers.py` macht es richtig.
* **`start transmission` gehört in dieselbe offene Portsitzung**, sonst
  bleibt der Strom still.
* **`capture_request(wait=2.0)`** ist ein **Timeout in Sekunden**, kein Flag.
  Bei blockiertem Sensor sieht der `TimeoutError` aus wie ein
  Konfigurationsfehler.
* **`create_video_configuration`**, nicht `create_still_configuration` — mit
  `RGB888`, gesetzter `FrameRate` und `queue=False`. Letzteres ist für eine
  Versatzmessung nicht optional.
