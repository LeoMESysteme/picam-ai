# Nachführung: `rahmen_unstimmig` in den Läufen vom 2026-11-13 — Recherche

Stand 2026-11-13. Nur Analyse, nichts am Repo geändert. Skripte und Bilder liegen neben diesem Bericht
(`replay.py`, `ana.py`, `blur.py`, `cand.py`, `cand2.py`, `patches.png`).

## 1. Ergebnis: Die Licht-/Schatten-Hypothese ist als Hauptursache widerlegt

Die Ursache ist ein **fester Unterschied zwischen Referenzbild (Einrichtung) und Lauf**: anderer Fokuszustand,
dadurch anderer Abbildungsmaßstab (+0,18 %) und andere Schärfe. Die Hand verschiebt höchstens das Zünglein an der Waage.

Belege, Lauf B (`live-20261113T113119Z/run-01`, 216 Diagnosebilder; offline nachgerechnet, alle 216
Entscheidungen stimmen mit dem Live-Lauf überein):

| Befund | Zahl |
|---|---|
| Erstdurchgang (starr) scheitert | **5890 von 5948 Bildern** (`summary.tracking_coarse_retries`); Lauf A: **7524 von 7524** |
| Maßstab des Zweitfits gegen die Referenz | 1,0016 … 1,0021, Median **1,0018**, in abgelehnten und angenommenen Bildern gleich |
| `res1` in abgelehnten vs. angenommenen Bildern | praktisch gleich (Bereich 6: 1,30 / 1,20 px; Bereich 11: 0,94 / 0,96 px) |
| Bereich 11 und 19 nach Zweitfit (`res2`) | 0,16 / 0,14 px — also gesund; ihr `res1` ist reine Maßstabswirkung (0,0018 × 430 px Abstand ≈ 0,8 px) |
| Bereich 6 nach Zweitfit | fester Versatz (−0,55; +0,28) px = **0,62 px**, Bild-zu-Bild-Streuung nur 0,09 / 0,04 px. Grenze 0,65 px |
| Abgelehnte Bilder: wer reißt im Zweitfit? | 118 von 119 nur Bereich 6, sonst keiner |
| Helligkeit der Patches, abgelehnt minus angenommen | unter 0,5 Graustufen bei allen 20 Bereichen; Peakwerte gleich (z. B. 0,79 / 0,79) |

Lesart: Jedes Bild läuft über den Zweitdurchgang. Dort liegt Bereich 6 dauerhaft 0,03 px unter der Grenze;
ein Rauschen von 0,09 px entscheidet über Annahme oder Ablehnung. Das erklärt auch die Verluste bei 25–68 s
ohne Hand. Eine bewegte Hand kann den Wert um Hundertstel Pixel schieben und so die Quote erhöhen, sie ist
aber nicht die Ursache.

Woher der feste Versatz von Bereich 6 kommt: Er liegt auf der hellen Fasenkante (waagrechte Linie,
`patches.png`), ist also entlang der Kante schlecht bestimmt. Das Referenzbild ist sichtbar unschärfer als der
Lauf (Laplace-Varianz am Bereich 74 gegen 554; `focus_check`: „vorher 55 %, danach 140 % der
Einrichtungsschärfe“). Zeichne ich das Laufbild auf Referenzschärfe weich (Gauß σ 0,7–0,9), fällt der Versatz von
0,56 auf 0,14–0,20 px.

Gegenprobe: Tracker mit einem Laufbild als Referenz (gleicher Fokuszustand, automatischer Vorschlag, 20 Bereiche):
**alle 216 Bilder bestehen den starren Erstdurchgang**, größtes Residuum 0,33 px, RMS höchstens 0,13 px —
einschließlich der Bilder mit bewegter Hand. Licht und Hand machen hier also höchstens rund 0,3 px aus.

Lauf A (`live-20261113T111848Z`, keine Bilder): gleiche Signatur, aber nicht beweisbar. Erstdurchgang scheitert
in 100 % der Bilder, Schärfe nach Neustart 65 % der Einrichtung (ohne Neusetzen, Schwelle 0,6). Die gemeldeten
Bereiche 6, 9, 13, 18 liegen 416–486 px vom Quadmittelpunkt (Median aller Bereiche 353 px) — das Muster einer
Maßstabsabweichung, nicht einzelner kranker Bereiche.

Einschränkungen: Diagnosebilder gibt es nur an Verlust-/Wiederkehr-Wechseln (216 von 5948). Der Einfluss der
Hand ist nicht isoliert gemessen. Warum die Einrichtungsaufnahme unschärfer war als der Lauf, ist offen.
Nicht jede Schärfeabweichung macht Maßstab: `live-20261113T111637Z` hatte 142 % Schärfe und 0 % Zweitversuche.

## 2. Nebenbefund: Hinweis und Stilllegung zielen in diesem Fall auf die falschen Bereiche

`region_hint` wertet `res1` aus (Begründung `region_hint.py:11-14`: der Erstfit laufe „für jedes Bild gleich“).
Bei Maßstabsabweichung misst `res1` aber den Abstand zum Mittelpunkt. In B wurden sieben Bereiche gemeldet,
darunter die gesunden 11 und 19. Die Ablehnung der Stilllegung in A (`schutzprobe_verletzt`) war **richtig**:
schon der volle Satz liegt bei 0,949 px von erlaubten 1,0 px, und ohne Bereich 6 plus einem weiteren Ausfall
(Bereiche 3, 7, 11, 15, 19) würde eine um 2,19 px falsche Lage angenommen (`frame_tracking.py:205-213`,
`1492-1508`). Die Probe ist nicht zu streng; sie hätte hier auch nichts geheilt.

## 3. Lösungskandidaten

| Kandidat | Wirkung auf A/B | Risiko für die Sicherheitsziele | Offline-Nachweis |
|---|---|---|---|
| **F. Fokuszustand von Referenz und Lauf angleichen** (neu). F1: Schärfeprüfung am Laufstart zweiseitig (heute nur Untergrenze 0,6, `setup.py:517-544`); außerhalb des Bands neu anfahren oder „neu einrichten“. F2: Einrichtungsbild erst nach derselben Fokus-Anfahrt wie am Laufstart aufnehmen. F3: Anteil Zweitversuche und Maßstab als eigenen Bedienhinweis zeigen („Abbildung weicht von Einrichtung ab“). | Beseitigt die Ursache; Gegenprobe B: 119 → 0 Ablehnungen | Keins für den Messpfad: keine Grenze, kein Fit ändert sich. F1 kann Läufe zusätzlich verweigern | Über alle `var/live/*/session.json`: Schärfeverhältnis gegen Zweitversuchsanteil; Replay wie `cand2.py` |
| **(a) Auswahl: Schärfeprobe bei der Einrichtung.** Kandidat fällt weg, wenn seine Lage unter Weichzeichnung/Schärfung (σ 0,7–1,0) um mehr als x px wandert. Die heutige Lichtprobe (`_photometric_variants`, `frame_tracking.py:1052`) hat Bereich 6 nicht erkannt, weil er nicht licht-, sondern schärfeempfindlich ist | Bereich 6 wäre nicht gewählt worden; die Maßstabsabweichung bleibt (weiter 99 % Zweitversuche, weniger Reserve) | Gering: nur Auswahl, Laufzeitprüfung unverändert. Risiko: Einrichtungen finden zu wenige Bereiche | Die 55 Einrichtungen der TB-Kalibrierung neu vorschlagen; B-Diagnosebilder mit neuem Satz |
| **(b) Lichtfeste Zuordnung.** Vorhanden: `TM_CCOEFF_NORMED` ist mittelwertfrei und normiert (`frame_tracking.py:1632`). Gradienten-/Census-Patches helfen gegen Licht, nicht gegen Schärfeunterschied. Schärfeangleich (beide Bilder auf gemeinsame Schärfe) wirkt: B 119 → 8 Ablehnungen, Quadecken ändern sich höchstens 0,21 px | Mittel | Mittel bis hoch: ändert die Eingabe aller Prüfungen; Residualgrenzen (R13-7) müssten neu hergeleitet und neu abgenommen werden | `cand.py`; danach volle DEV-Aufnahmen, `tc_echtlauf_20261111`, `r19c` |
| **(c) Bis zu k Ausreißer je Bild ausschließen** | B: 118 von 119 Ablehnungen wären Annahmen | Hoch: derselbe Fall, den die Schutzprobe in A abgelehnt hat (bis 2,19 px falsche Lage), dann ohne Probe und je Bild. Verdeckt zudem die eigentliche Ursache | Halbseiten-Bias-Raster (`test_kandidat_koordinierter_lokaler_bias…`) für jede k-Teilmenge |
| **(d) Stilllegung wirksam machen** | Probe ist richtig (Abschnitt 2). Sinnvoll: Hinweis nicht auf `res1` stützen, wenn der Erstdurchgang fast immer scheitert; dann maßstabsbereinigte Residuen nehmen | Gering, wenn nur Diagnose; Stilllegung selbst unverändert | Offline-Auswertung von `images.jsonl` beider Residuen |
| **(e) Zeitliche Ansätze** (letztes Quad halten, erst nach Dauer ablehnen) | Würde Lücken füllen | Nicht vereinbar mit AGENTS.md: ein nicht geprüftes Quad wird weiterverwendet (raten statt ablehnen); `frame_tracking.py:186` „Kein Ergebnis wird ins nächste Bild übernommen“ ist bewusst so | — |

## 4. Empfehlung

1. **Zuerst F** (Fokus-/Schärfezustand angleichen und sichtbar machen), beginnend mit F3 und F1.
   Aufwand grob 1–2 Tage einschließlich Tests; F2 hängt davon ab, warum die Einrichtungsaufnahme unschärfer war (erst klären).
2. **Danach (a)** als Schutz gegen schärfeempfindliche Kantenbereiche, rund 1–2 Tage plus Neukalibrierung an den 55 Einrichtungen.
   Dazu die kleine Korrektur aus (d) am Hinweis.

Nicht empfohlen: (c) und (e). (b) nur, falls F in der Praxis nicht reicht.

Nötige Belege vor jeder Änderung:

- Bestätigungsversuch am Gerät: einrichten und **ohne** Werkbank-Neustart bzw. mit Schärfeverhältnis nahe 100 % laufen lassen,
  Hand bewegen. Erwartung: Zweitversuche nahe 0 %, keine Verluste. Diagnose so einstellen, dass auch angenommene Bilder
  in festen Abständen gespeichert werden.
- Replay der Läufe vom 11.11. (`103604Z`: 65 % Zweitversuche, `122753Z`: 38 %): War dort ebenfalls ein Maßstab ungleich 1 im Spiel?
  Wenn ja, sind die damals als „Glanz/Fase“ kalibrierten Schwellen (TB) neu zu bewerten.
- Messreihe Fokuswert gegen Maßstab (Fokus 46…58, je ein Bild): bestätigt die Fokusatmung als Quelle der 0,18 %.

## Nachtrag 2026-11-13: Offline-Gegenprobe und vorläufiges Startband

Die Zahlen und Stichprobenbeschränkung stehen in [VALIDATION](../../VALIDATION.md).
Der Replay `replay-rahmen.py` nimmt die drei Lauf-IDs als Argumente und liest
nur `var/live`; keine Bilddaten werden kopiert. Die 11.11.-Stichproben zeigen
Maßstäbe nahe eins trotz Zweitversuchen. Der 13.11.-Befund bestätigt den
höheren Maßstab; Schärfe und Maßstab wurden nicht unabhängig variiert. 52
Entwicklungs-`session.json` enthielten keinen Fokusstartvergleich.

Das Startband 0,95–1,05 ist ein konservativer, unkalibrierter Gleichheitsfilter:
Es umfasst 0,982–1,026 mit beobachteten Anteilen von 0,1–7,6 % und sperrt
auch den guten Lauf 1,418/0 %. Fehlende Prüfung sperrt ebenfalls. Kein
kausaler Schluss und keine Änderung der Fitgrenzen folgt daraus.
