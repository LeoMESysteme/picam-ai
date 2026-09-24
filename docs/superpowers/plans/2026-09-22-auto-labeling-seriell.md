# Plan: Auto-Labeling des GSV-Datensatzes über den seriellen ASCII-Strom

**Stand: 2026-09-22.** Task A (Plateau-Statistik) ist gemessen, Task C
(`label_origin`) gebaut, Tasks D und E sind fertig, aber **nicht ausgeführt**.
Der Blocker ist jetzt Task B — der Versatz zwischen Telegramm und Anzeige —
und der braucht **eine Laborsitzung mit bewusst gefahrenem Stimulus**.

## Ziel

Den Bestand von 11 bestätigten GSV-Proben so weit vergrössern, dass sich ein
Rasterverankerungsverfahren auf einer **Entwicklungsmenge** bauen und auf einer
**davon getrennten Prüfmenge** belegen lässt. Die Sollwerte kommen dabei nicht
mehr aus der Tastatur, sondern aus dem seriellen Telegramm des Geräts.

Das ist die direkte Antwort auf die methodische Grenze, die am 2026-09-22 nach
vier Verankerungsversuchen festgehalten wurde: *11 Proben reichen nicht, um ein
Verfahren gleichzeitig zu entwickeln und zu validieren*
([VALIDATION.md](../../VALIDATION.md), Nachtrag „vierter
Verankerungsversuch"). Jedes weitere Verfahren, das auf denselben 11 Proben
abgestimmt wird, sieht besser aus, ohne besser zu sein.

## Was dieser Plan **nicht** löst

Er vergrössert die **Bilderzahl**, nicht zwangsläufig die
**Ziffernabdeckung**. Eine hohe Trefferquote auf 50 000 Bildern derselben drei
Werte ist keine Aussage über die Erkennung im Feld — das ist
[OQ-39](../../open-questions.md), und es bleibt offen. Task H misst, wie viel
Abdeckung mit den (inzwischen als beweglich bekannten) Stimulatoren wirklich
erreichbar ist; erst danach ist die Frage beantwortbar.

## Ausgangslage (gemessen, nicht angenommen)

| Punkt | Stand |
| --- | --- |
| RS232-Abgriff am GSV-2AS, PL2303 an `/dev/ttyUSB0`, 38400 8N1 | steht, gemessen ([VALIDATION.md](../../VALIDATION.md)) |
| ASCII-Modus aktiv, Telegramm `+0.46776 mV/V<CR><LF>` | gemessen, 18/18 formatkonform |
| Telegrammrate | ≈ 1,8–2,0 /s |
| Kamera | 15 fps → rund sieben Bilder je Telegramm |
| Zeitbasis Kamera | `SensorTimestamp`, CLOCK_BOOTTIME, Semantik **unbekannt** (`controller.py` schreibt `timestamp_semantics: "unknown"`) |
| Zeitbasis Serienabgriff | Ankunftszeit auf dem Pi, CLOCK_BOOTTIME — **dieselbe Domäne** |
| Sollwert = Anzeige | laut Herstellerdoku zugesichert; **optisch nie gegengeprüft** |
| Plateaus der exakten Zeichenkette | gemessen, 1125 Telegramme ([VALIDATION.md](../../VALIDATION.md)) |
| Zeitliche Kopplung Telegramm ↔ Anzeige | **ungemessen** — das ist der Blocker |
| `label_origin` im `DatasetStore` | gebaut (Task C), Bestand noch nicht migriert |
| Bestandsproben | 88 gesamt, davon 11 GSV — seit Task C **gesperrt**, bis Task D läuft |

## Der Kern: das Schutzintervall

### Modell

Die Anzeige zeigt den Wert des Telegramms *k* während
`[t_k + δ, t_{k+1} + δ)`, mit einem unbekannten Versatz δ. Ist |δ| durch ein
**M** nach oben beschränkt, dann gilt für einen Lauf gleicher Werte von
Telegramm *i* bis *j* (nächstes abweichendes Telegramm: *j+1*):

> Die Anzeige zeigt diesen Wert sicher während `[t_i + M, t_{j+1} − M)`.

Ein Bild mit `SensorTimestamp` in diesem Fenster darf den Wert als Label
bekommen. Jedes andere Bild nicht.

### Warum das Fenster **symmetrisch** sein muss

Es ist nicht ausgeschlossen, dass der Gerätecontroller das LC-Display
**vor** dem Absenden des Telegramms beschreibt. Dann steht der neue Wert auf
dem Glas, bevor das Telegramm am Pi ankommt, und ein einseitiges
Vergangenheitsfenster (`[t − M, t]`) liesse genau dort falsche Label zu. Bis
die Reihenfolge gemessen ist, gilt δ beidseitig beschränkt.

### Was M alles enthält — ehrliche Benennung

M ist **kein** „LCD-Einschwingwert". Es ist ein **Ende-zu-Ende-Versatz** und
umfasst mindestens:

1. die geräteinterne Reihenfolge LCD-Schreiben ↔ Telegrammversand,
2. USB-/PL2303-Transport- und Treiberlatenz,
3. die optische Einschwingzeit des STN-Glases (bei dieser Bauart typisch
   ≥ 100 ms, temperaturabhängig),
4. die Belichtungsdauer des Bildes,
5. die **unbekannte Semantik** von `SensorTimestamp` — Belichtungsbeginn oder
   Auslese-Ende unterscheiden sich bei 15 fps um bis zu 66 ms, also dieselbe
   Grössenordnung wie Punkt 3 ([TIMING.md](../../TIMING.md), Messung M2).

Wer die Zahl als „Einschwingzeit des Displays" in die Doku schreibt, behauptet
mehr, als gemessen wurde. Sie gehört mit Vorzeichenkonvention und dieser Liste
nach [VALIDATION.md](../../VALIDATION.md).

## Vorab-Festlegungen — **vor** den Messungen, nicht danach

Diese Regeln werden jetzt festgeschrieben, damit sie nicht nachträglich an das
Ergebnis angepasst werden.

1. **Exakte Zeichenkettengleichheit.** Ein Bild bekommt ein Label nur, wenn
   der Strom über das ganze Fenster **dieselbe 13-Zeichen-Kette** trägt. Keine
   Toleranz auf der letzten Stelle, kein „nächstgelegener Wert", kein Runden.
   Fällt die Ausbeute dadurch klein aus, ist die Ausbeute klein — der Ausweg
   über eine Toleranz erzeugt Label, die wie Wahrheit aussehen, und ist nach
   [AGENTS.md](../../../AGENTS.md) und Konzept §7 ausgeschlossen.

   **Ergänzt 2026-09-23 ([OQ-41](../../open-questions.md)):** Das Telegramm
   trägt eine führende Null, die das Glas nicht zeigt (`+01.8290` → `+ 1.8290`,
   gemessen über 15 Faktoren). Vor dem Vergleich wird deshalb **genau diese
   Null** aus dem Telegramm entfernt, entschieden vom Nutzer: eine `0` direkt
   nach dem Vorzeichen, der eine Ziffer folgt. Das ist eine feste Abbildung
   und keine Toleranz, die Gleichheit bleibt exakt. Rohtelegramm und
   normalisierte Kette werden beide im Label geführt. Negative Werte sind
   davon nicht erfasst, sie sind ungeprüft.
2. **Bilder im Schutzfenster bekommen keinen geratenen Wert.** Sie fallen
   entweder ganz heraus oder erhalten `label_state="uncertain"`. Nie einen
   Wert „aus der Nähe".
3. **M wird nach dieser Formel gebildet, festgeschrieben am 2026-09-22 vor
   der Messung aus Task B:**

   ```
   M = |δ| + d_misch + 3·σ_δ + 40 ms
   ```

   mit δ dem gemessenen Versatz, `d_misch` der gemessenen Dauer des
   Mischbilds, σ_δ der Streuung von δ über die Ereignisse, und 40 ms als
   benanntem Zuschlag für die **unbekannte** `SensorTimestamp`-Semantik
   (halbe Bilddauer bei 15 fps, aufgerundet; siehe
   [TIMING.md](../../TIMING.md), Messung M2).

   **Warum das hier steht und nicht später:** die Ausbeutetabelle aus Task A
   ist bereits bekannt (`M` = 1 s → 51,9 %, `M` = 2 s → 34,0 %). Ein nach der
   Messung „gewähltes" M wäre an dieser Tabelle abgestimmt und nicht mehr am
   Gerät — genau die nachträgliche Anpassung, die dieses Projekt schon einmal
   teuer bezahlt hat. M fällt aus der Formel, es wird nicht ausgesucht.

   Kommt M so gross heraus, dass die Ausbeute unbrauchbar wird, ist das ein
   **Befund**, kein Anlass, die Formel zu ändern.

   **Festgelegt 2026-09-23, vor jeder Ernte: M = 695 ms.** Die Formel
   lieferte je Population 499 / 532 / 664 / 695 ms (VALIDATION.md, Task B).
   Es gilt der **grösste** Wert, entschieden vom Nutzer. Grund: kleine
   Ereigniszahlen (4–23), und die Null-Basislinie fällt nicht vollständig
   durch. Der vorsichtigste Wert ist der einzige, der keine Population
   bevorzugt. Die Ausbeute war bei der Entscheidung nicht bekannt.
4. **`independence_group` je Aufnahmesitzung/Stimuluseinstellung**, nicht je
   Bild. 500 Bilder derselben Sitzung sind eine Beobachtung in vielen
   Ausfertigungen, keine 500 unabhängigen Proben. Zufällig über Bilder
   gesplittet wäre die Prüfmenge nur eine Kopie der Entwicklungsmenge — und
   der Split wäre wertlos.
5. **Jede Benchmarkzahl nennt die Herkunftsmischung.** Wie viele Proben
   `manual`, wie viele `serial_ascii`.

## Aufgaben

### Task A — Plateau-Statistik des Stroms (**Sperrfrage**) — **erledigt 2026-09-22**

**Ergebnis:** Zahlen in [VALIDATION.md](../../VALIDATION.md), Eintrag
„Plateau-Statistik des ASCII-Stroms". 599 s, 1125 Telegramme, 0
Formatabweichungen. Selbst bei M = 1 s bleiben 51,9 % der Wanduhrzeit nutzbar
(≈ 467 Bilder/min bei 15 fps). **Die Sperre ist gelöst** — der Strom steht im
Ruhezustand lange genug still.

**Mit einer Einschränkung, die den Schwerpunkt des Plans verschiebt:** die
gemessene Ausbeute ist **Bilder** pro Minute, nicht **Information** pro
Minute. Im Ruhezustand trägt der Strom praktisch **eine** Zeichenkette
(`+0.46776 mV/V` in 379 von 660 Telegrammen). Nach Festlegung 4
(`independence_group` je Sitzung) ist eine Ruheaufzeichnung **eine**
unabhängige Beobachtung, gleichgültig wie viele Bilder darin liegen — also
genau die Grenze, an der schon 11 Proben gescheitert sind. Die Grösse, die
wirklich zählt, ist **verschiedene Zeichenketten je Minute bewusst gefahrenen
Stimulus**, und sie ist ungemessen. Deshalb ist Task H nicht das Anhängsel,
sondern die eigentliche Hauptsache; und deshalb darf die erste
Kameraaufzeichnung **kein passiver Dauerlauf** sein.

<details>
<summary>Ursprüngliche Aufgabenbeschreibung</summary>

Rein passiver, zeitgestempelter Mitschnitt; **es wird kein Byte gesendet**.
Zu bestimmen:

* Telegrammrate und Abstandsverteilung,
* Formattreue über eine längere Strecke,
* **Verteilung der Plateaulängen der exakten Zeichenkette**,
* daraus die **Ausbeute** je Kandidat-M: nutzbarer Anteil der Wanduhrzeit und
  labelbare Bilder pro Minute.

**Warum das sperrt:** Der 0.948er-Cluster des Bestands streut in den letzten
beiden Stellen. Zappelt die letzte Stelle im Ruhezustand mit ~2 Hz, sind
Plateaus kurz, und bei einem realistischen M bleibt womöglich **nichts**
übrig. Dann ist der Synchronaufzeichner umsonst gebaut.

**Abbruchkriterium:** Ergibt sich bei dem in Task B gemessenen M eine Ausbeute
von praktisch null, wird nicht weitergebaut, sondern zuerst die Ruhe des
Signals verbessert (Geräte-Mittelung, `Set Digits`) — beides sind
**persistente** Konfigurationsänderungen am Laborgerät und gehören vorher
abgesprochen.

</details>

### Die eine Sitzung, die drei Fragen gleichzeitig beantwortet

Tasks B, H und die Ausbeutefrage aus Task A brauchen **nicht** drei
Aufzeichnungen, sondern **eine**: eine Sitzung, in der der Nutzer die
Stimulatoren **langsam über den ganzen erreichbaren Bereich fährt**, mit
einigen bewusst **grossen Sprüngen** und dazwischen **Ruhepausen**.

* die grossen Sprünge → Versatzmessung (Task B),
* der langsame Durchlauf → Abdeckung und verschiedene Zeichenketten
  (Task H, [OQ-39](../../open-questions.md)), insbesondere die Frage, ob
  **negative** Werte überhaupt erreichbar sind,
* die Ruhepausen → die reale Ausbeute bei gefahrenem Stimulus.

Ein passiver Dauerlauf vorweg bringt nichts ausser tausenden Kopien von
`+0.46776 mV/V`.

**Platzbedarf vorher rechnen.** 15 fps × 10 min = 9000 Bilder. Bei 960×720
sind das je nach Format mehrere GB. Frei sind derzeit 23 GB, `var/` belegt
395 MB. Der Aufzeichner soll daher eine Unterabtastung anbieten und der
Platzbedarf vor dem Start geprüft werden — eine vollgelaufene Platte auf dem
Labor-Pi ist ein schlechter Weg, das zu bemerken.

### Task B — Ende-zu-Ende-Versatz photometrisch messen

Der Trick, der die Zirkularität bricht: **die Messung braucht kein OCR.** Um
zu erkennen, *wann* sich das Glas ändert, genügt die Bildänderung im
entzerrten Anzeigebereich — nicht, *was* dort steht. Das ist wichtig, weil der
Leser gerade nicht funktioniert.

1. Kamera und seriellen Strom gleichzeitig aufzeichnen, beide mit
   CLOCK_BOOTTIME.
2. Der Nutzer erzeugt einige **deutliche Sprünge** am Stimulator.
3. Anzeigebereich je Bild über `lcd_quad_in_region`
   (`src/dispread/workbench/vision.py`, 11/11 auf den GSV-Proben) ausschneiden
   und entzerren.
4. Bild-zu-Bild-Differenz bilden → Zeitpunkt des Änderungsbeginns und des
   Wiedererreichens der Ruhe.
5. Gegen den Zeitstempel des ersten abweichenden Telegramms auftragen.

**Abweichung von Schritt 2, festgelegt 2026-09-23 vor der Messung:** die
grossen Sprünge erzeugt der Pi selbst über `set norm` (16) innerhalb der
offenen Portsitzung von `sync-record.py` (`--norm-schedule`), jeder Befehl mit
eigenem CLOCK_BOOTTIME-Zeitstempel protokolliert. Grund: reproduzierbar,
beliebig viele Ereignisse, kein Bediener nötig. Das Risiko: eine
Normierungsänderung könnte Anzeige und Telegramm auf einem **anderen Weg**
erreichen als eine echte Messwertänderung. Wenn möglich kommen deshalb
einige Sprünge von Hand am Stimulator dazu, und zwar als **dritte
Population**. Weicht δ(Normierung) von δ(Stimulator) ab, wird das als Befund
berichtet und nicht als Mittelwert. Formel und Auswertung bleiben
unverändert.

Liefert: den Versatz δ **mit Vorzeichen** (zeigt das Glas vor oder nach dem
Telegramm?) und die Dauer des Mischbilds. Beides zusammen ergibt M über die
Formel in Festlegung 3.

**Zwei Populationen, getrennt auswerten — das ist die Selbstkontrolle des
Verfahrens.** Im Ruhezustand ist fast jeder Wechsel ±1 in der fünften
Nachkommastelle: **eine** Zeichenzelle, zwei ähnliche Glyphen. Ob dieses
photometrische Signal über Kamerarauschen, Autofokus-Suchbewegungen und
Netzflimmern hinauskommt, ist offen — und ein ausbleibender Ausschlag sagt
nicht, *warum* er ausbleibt. Deshalb:

* δ **getrennt** aus den wenigen **grossen** mehrstelligen Sprüngen und aus
  dem Ensemble der **kleinen** Wechsel bestimmen.
* Stimmen beide überein, ist das Verfahren bestätigt.
* Weichen sie ab, mittelt das Ensemble der kleinen Wechsel Rauschen, und nur
  die grossen Sprünge sind verwertbar. Dann wird δ **aus diesen** bestimmt
  und die kleinere Ereigniszahl als Unsicherheit ausgewiesen — nicht der
  bequemere Wert genommen.

**Nebenergebnis, das ausdrücklich mitgenommen wird:** Punkt 3 der Liste oben
klärt zugleich die einzige noch offene Zusage aus
[OQ-38](../../open-questions.md) — dass die Zeichenkette *inhaltlich* der
Anzeige entspricht, ist bisher nur Herstelleraussage und wurde nie optisch
gegengeprüft. Ein Standbild aus dieser Aufzeichnung neben dem zugehörigen
Telegramm erledigt das.

### Task C — Herkunftsmerkmal `label_origin` im `DatasetStore` — **erledigt 2026-09-22**

Pflichtfeld je Probe, `manual` oder `serial_ascii`, kein stiller Default, dazu
ein Detailfeld, das die Herleitung des automatischen Labels festhält
(Port, Schutzintervall, Plateaugrenzen, Telegrammzahl). Ohne dieses Feld sind
von Hand und automatisch gelabelte Proben nach dem ersten Auto-Label nicht
mehr trennbar, und ein systematischer Fehler des Abgriffs wandert unsichtbar
in jede Benchmarkzahl. Deckt [OQ-38](../../open-questions.md) Punkt 6.

**Gebaut:** `LABEL_ORIGINS = ("manual", "serial_ascii")`, Pflichtfeld ohne
Default, `label_origin_detail` bei `serial_ascii` verpflichtend mit geprüften
Schlüsseln (Port, Schutzintervall, Plateaugrenzen, Telegrammzahl), beide
Felder in der Unveränderlichkeitsprüfung, `relabel_sample` setzt die Herkunft
auf `manual` und führt die vorherige in `label_history` mit.
`SAMPLE_SCHEMA_VERSION` 1 → 2, Laden einer Version-1-Probe bricht hart ab.
374 Tests grün.

**Noch offen und benannt:** der Export (`manifest.json`) reicht
`label_origin` noch nicht weiter. Solange das so ist, trägt ein exportierter
Datensatz die Herkunft nicht mit — die Entmischung ist dann nur im Bestand
möglich, nicht im Export.

### Task D — Migration der 88 Bestandsproben — **erledigt** (Trockenlauf 2026-09-23: 0 zu migrieren)

Alle heutigen Proben sind von Hand gelabelt; sie brauchen `label_origin:
"manual"` eingetragen. Das ist eine Änderung an echten Messdaten unter `var/`
— **mit Sicherung vorher und nur nach Absprache**, wie schon bei der
Label-Korrektur am 2026-09-22.

`scripts/migrate-samples-v1-to-v2.py`: Trockenlauf als Vorgabe, Sicherung vor
dem ersten Schreibzugriff mit Vollständigkeitsprüfung, atomares Schreiben,
wiederholbar, Abbruch bei einer einzigen unklaren Datei. Trockenlauf geprüft:
88 Proben, 88 zu migrieren, 0 unklar.

> **Der Sammelmodus steht, bis das gelaufen ist.** `DatasetStore` lehnt seit
> Task C jede Version-1-Probe ab. Ein Befehl:
> `./.venv/bin/python scripts/migrate-samples-v1-to-v2.py --apply`

### Task E — Synchronaufzeichner — **gebaut, gegen echte Hardware gelaufen (Ernte 1, 2026-09-24)**

`scripts/sync-record.py`. Schreibt Bilder **und** zeitgestempelte Telegramme derselben Sitzung
gemeinsam weg. Bewusst getrennt vom Labeln: erst aufzeichnen, dann offline
auswerten. So lässt sich dieselbe Aufzeichnung mit einem anderen M erneut
auswerten, ohne neu zu messen.

Betriebshinweis: Die Kamera kann nur **ein** Prozess halten. Vor dem Start
prüfen, ob ein `dispread serve` läuft — und die RP2040-Sperre aus
[OQ-22](../../open-questions.md) im Blick behalten.

**Was geprüft ist:** der `synthetic`-Pfad, vollständig, plus Abbruch per
Ctrl-C (Daten bleiben gültig), leerer Telegrammstrom (laute Meldung statt
stiller leerer Datei) und nicht öffenbarer Port (Abbruch statt Blindflug mit
nur Kamera). Serieller Test über `os.openpty()`, **kein echter Port**.

**Was ungeprüft ist — und es ist genau der Zweig, der zählt:** der
`camera`-Pfad wurde nie ausgeführt. Dass `request.get_metadata()` an dieser
Hardware wirklich ein `SensorTimestamp` liefert und die Konfiguration mit der
AI Camera trägt, ist aus der Codegleichheit mit `Controller._capture`
übernommen, nicht gemessen. Der erste reale Lauf ist damit selbst ein
Prüfschritt: **kurz** starten (z. B. 10 s) und `frames.jsonl` ansehen, bevor
eine lange Sitzung aufgezeichnet wird.

### Task F — Offline-Labeler — **gebaut, auf echten Daten gelaufen (Ernte 1, 2026-09-24: 837 von 2835 Bildern gelabelt)**

`scripts/gate-label.py`. Wendet die oben festgelegte Gate-Regel offline auf
eine `sync-record.py`-Aufzeichnung an. **Legt keine Proben an** — das bleibt
bewusst eine spätere, getrennte Aufgabe mit Menschenbeteiligung; das Skript
liest nicht einmal `DatasetStore`. Ergebnis: ein Bericht auf stdout (Anzahl
Bilder gesamt/gelabelt/abgelehnt je der vier Ablehnungsgründe einzeln, und —
deutlich herausgestellt, wichtiger als die Bilderzahl — die Zahl
verschiedener Zeichenketten unter den gelabelten Bildern) und eine
Vorschlagsdatei (JSON) mit Bildpfad, exakter Zeichenkette, führendem
Zahlenteil und einem `label_origin_detail`-Block, dessen Feldnamen
wortgleich aus `_SERIAL_ASCII_DETAIL_REQUIRED`
(`src/dispread/workbench/datasets.py`) übernommen sind.

**Falsifikationstest besteht:** `tests/test_gate_label.py` enthält den
geforderten Fall — ein Bild exakt im Wechselfenster wird abgelehnt, nicht
irgendwie gelabelt. Neun test-first geschriebene Tests insgesamt (alle
scheiterten vor der Implementierung), inklusive Randfall Fenstergrenze,
Bild vor/nach dem Telegrammbereich, Telegrammlücke, und einem von Hand
durchgerechneten größeren Szenario.

**Entscheidung beim Lücken-Fall** (Aufgabentext: „der subtile und
wichtigste"): der betroffene Lauf wird an der Lücke **geteilt**, nicht
komplett verworfen — das ist die genauere Lösung, weil nur die tatsächlich
unsichere Stelle verworfen wird. Wichtig, und in einer ersten Fassung
übersehen (bei Review aufgefallen): eine Telegrammlücke kann auch **genau an
einem Wertwechsel** liegen. Fällt dort ein Telegramm aus, sieht der Strom wie
ein gewöhnlicher A→B-Übergang aus, obwohl dazwischen ein dritter, nie
angekommener Wert gestanden haben kann. Der letzte Telegrammabstand vor
einem Wertwechsel wird deshalb ebenfalls gegen `--max-gap-ms` geprüft, nicht
nur Abstände innerhalb eines gleichbleibenden Laufs; ist er zu groß,
schließt der Lauf konservativ mit seinem letzten TELEGRAMM ab (wie ein
echter Lücken-Split), statt mit `t_{j+1} - M`.

**Fenstergrenzen-Festlegung:** halboffen, wie die Klammerschreibweise des
Plans es vorgibt — `t_i + M` eingeschlossen, `t_{j+1} - M` ausgeschlossen.

**Was ungeprüft bleibt:** das Skript wurde nur gegen synthetische
`serial.jsonl`/`frames.jsonl` gefahren, nie gegen eine echte
`sync-record.py`-Aufzeichnung (die braucht Task B/M zuerst). `M` und
`--max-gap-ms` haben weiterhin keinen begründeten Wert — beide müssen vor
dem ersten echten Lauf angegeben werden, das Skript verweigert sich ohne
sie. Für `--max-gap-ms` fehlt noch ein OQ-Eintrag in
`docs/open-questions.md` (nicht Teil dieser Änderung).

### Task G — Unabhängigkeitsgruppen und Split

**Stand 2026-09-24:** Ernte 1 importiert mit einer `independence_group` je
Aufnahmesitzung (81 Proben, Split `development`).

Gruppen je Sitzung vergeben, Entwicklungs- und Prüfmenge auf Gruppenebene
trennen. Erst danach ist eine Zahl aus dem vergrösserten Datensatz eine
Aussage und keine Selbstbestätigung.

### Task H — Abdeckung messen (OQ-39)

Während einer Sitzung, in der der Nutzer die Stimulatoren über den ganzen
erreichbaren Bereich fährt, den Strom mitschreiben und auszählen: welche
Werte, welche Ziffern an welchen Stellen, ob **negative** Werte erreichbar
sind. Das ist eine reine Auswertung des seriellen Mitschnitts und braucht
weder Kamera noch Leser.

## Reihenfolge und Abhängigkeiten

```
A (Plateaus) ──┐
               ├──> M festlegen ──> E (Aufzeichner) ──> F (Labeler) ──> G (Split)
B (Versatz) ───┘                                          ^
                                                          │
C (label_origin) ──> D (Migration der 88) ────────────────┘

H (Abdeckung) läuft unabhängig und beantwortet OQ-39
```

C und D sind die einzigen, die ohne A und B sinnvoll vorangehen können —
sie werden gebraucht, sobald überhaupt ein automatisches Label entsteht.

## Ausdrücklich nicht in diesem Plan

* **Der Dot-Matrix-Leser selbst.** Dieser Plan beschafft Daten; die
  Verankerung ist
  [2026-09-22-dotmatrix-backend.md](2026-09-22-dotmatrix-backend.md) und
  bleibt an ihrem nicht bestandenen Gate stehen, bis Daten da sind.
* **Der Displaybus-Abgriff.** Bleibt Rückfallebene und der einzige Weg zu
  Code-zu-Glyph-Paaren ([DISPLAYBUS_TAP.md](../../DISPLAYBUS_TAP.md)).
* **Jede Änderung an der Produktionskette.** Ein so gewonnener Sollwert ist
  Datensatzmaterial und erreicht `ValueReader`, `ReleaseGate` und die
  Ausgabe **nie**.
* **Persistente Gerätekonfiguration** (`Set Digits`, `Set Norm`, Mittelung).
  Kommt nur nach ausdrücklicher Absprache in Frage, siehe Abbruchkriterium
  in Task A und [OQ-37](../../open-questions.md).
