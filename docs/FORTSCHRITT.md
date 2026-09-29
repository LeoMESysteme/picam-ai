# Fortschritt Ernten und Training

Diese Seite zeigt auf einen Blick, wie weit der Datensatz und der
Dot-Matrix-Leser sind: wie viele Proben je Gruppe vorliegen, was die
einzelnen Ernten geliefert haben, wie sich der Leser über die
`loo`-Läufe entwickelt und wie die Abnahmen ausgegangen sind. Die Zahlen
kommen aus `assets/data/fortschritt.json`, die `scripts/docs-progress-data.py`
aus den Ernte-, `loo`- und Abnahme-Dateien erzeugt. Maßgeblich für jede Zahl
bleibt [VALIDATION.md](VALIDATION.md); das Laborjournal
[lab_journal.md](lab_journal.md) erklärt die einzelnen Läufe.

Überfahren oder Antippen zeigt die Einzelwerte. Ein Klick auf einen
Legendeneintrag blendet die Reihe aus oder wieder ein.

<div class="fs-status" data-fs-status markdown="0">
<p>Die Diagramme brauchen JavaScript.</p>
</div>

## Datensatz je Gruppe

Proben je Gruppe, eingefärbt nach Rolle: Training, Abnahme oder verworfen.

<div class="fs-chart" data-fs-chart="dataset" markdown="0"></div>

## Ernten im Zeitverlauf

Je Ernte-Run die aufgenommenen Bilder, geteilt in beschriftete und nicht
beschriftete, darüber die verworfenen Bilder (Bildverluste bei der Aufnahme).
Die Linie zeigt die Verlustquote.

<div class="fs-chart" data-fs-chart="harvests" markdown="0"></div>

## Leser-Entwicklung (loo)

Zeilen sind Gruppen, Spalten die `loo`-Läufe in ihrer Reihenfolge. Die Zelle
zeigt den Anteil richtig gelesener Proben: grün richtig, grau abgelehnt.
Rot markiert eine Zelle mit mindestens einer falschen Lesung. Ziel ist
überall 0 falsch.

<div class="fs-chart" data-fs-chart="loo" markdown="0"></div>

## Abnahmen

Anteil abgelehnter Proben je Abnahme gegen die Grenze von 20 %, dazu die
Zahl falscher Lesungen gegen das Ziel 0 und das Urteil.

<div class="fs-chart" data-fs-chart="abnahmen" markdown="0"></div>
