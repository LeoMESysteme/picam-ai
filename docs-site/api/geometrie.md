# Nachführen und Entzerren

`QuadTracker` registriert jedes Bild gegen das Bestätigungsbild; die
Vierpunkt-Entzerrung rechnet direkt aus dem Originalbild. Der Live-Adapter
`TrackedQuadLocator` liefert bei Grenzverletzung oder zu geringer
Bildähnlichkeit keinen Kandidaten. Die Pipeline schreibt dann unmittelbar
`UNREADABLE` mit `tracking_lost:…`.

Die Nachführung berücksichtigt derzeit auch den Zifferninhalt. Nach einem
großen Wertwechsel ist ein Verlust mit `low_score` belegt; eine
wertunabhängige Trackerregion ist offen
([OQ-26](../docs/open-questions.md#oq-26)).

::: dispread.live.tracking

::: dispread.track

::: dispread.rectify

::: dispread.glassquad
