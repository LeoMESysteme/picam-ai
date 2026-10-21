# 4 — Geräteprofile

Dieses Kapitel ist im aktuellen Checkout noch eine Bauaufgabe. Es gibt weder
`dispread.profiles.ProfileStore` noch ein `config/profiles/`-Schema. Die
Roadmap führt Profile als offen. Verwechsle sie nicht mit
[`SessionProfile`](../../api/workbench.md), das eine bestätigte Ernte- oder
Live-Aufstellung mit Kamera, Punktraster und Referenzbild beschreibt, oder
mit den älteren Workbench-Profilen unter `var/workbench/profiles/`.

## Was ein Geräteprofil festhalten soll

Ein Geräteprofil soll bestätigte Annahmen über ein bestimmtes Display an
einem bestimmten Aufbau enthalten: Layout, Einheit, Bildgröße und ROI. Die ROI
gehört zum Bildkoordinatensystem der Aufnahme. Sie muss bei abweichender
Auflösung geprüft und darf nicht stillschweigend auf ein anderes Bild
übertragen werden.

Trenne diese Angaben von Laufzeit- und Freigabeschwellen. Schwellen gehören
zur `GateConfig` und sind laut [OQ-14](../open-questions.md) noch nicht
kalibriert. Ein Profil darf außerdem keine GSVmulti-Telegrammstruktur
vorwegnehmen; das Format ist weiterhin offen ([OQ-07](../open-questions.md)).

## Bauaufgabe

Lies zuerst die Datenverträge in [Kapitel 2](02-vertraege.md) und das
autoritativ beschriebene Verhalten in [Konzept §4](../../Konzept.md). Lege
anschließend einen Profilvertrag samt Tests an, bevor du einen JSON-Loader
implementierst. Tests sollten mindestens fehlende Felder, unbekannte
Schema-Versionen, falsche ROI-Geometrie, Einheiten und Größenabweichungen
abdecken. Der Loader muss ungültige Eingaben ablehnen, nicht raten.

Ein sinnvolles Profil braucht einen stabilen Bezeichner und nachvollziehbare
Bestätigung (Person und Zeitpunkt mit Zeitzone). Freitextnotizen können den
Aufbau erläutern, ersetzen aber keine maschinenprüfbaren Felder. Lege erst
nach Festlegung des Vertrags Schema und Beispielprofil an.

## Einordnung im aktuellen Stand

Für ein sofort nutzbares Kamerabild ist die aktive Quelle `v4l2://`; sie
benötigt eine explizite `camera.json` mit Geräteeinstellungen. Die
[Kamera-Livevorschau](10-kamera-livevorschau.md) erklärt den gegenwärtigen
Workbench-Ablauf samt `/live`. Die namentliche Bestätigung dort erzeugt
`profile.json` und `confirmation.json` für diese Sitzung; daraus entsteht
kein allgemeiner `ProfileStore` für wiederkehrende Geräte.

<figure class="tour-figure" data-scene="bedienung-bestaetigen" markdown="1">
<figcaption markdown="span">Was es heute schon gibt: ein bestätigtes Profil für eine Aufnahmesitzung (<code>SessionProfile</code> aus <code>harvest-setup.py confirm</code> oder der Bestätigung auf <code>/live</code>). Es ist kein dauerhaftes Geräteprofil; den <code>ProfileStore</code> beschreibt die Bauaufgabe oben.</figcaption>
</figure>

Wenn du diese Bauaufgabe umsetzt, ergänze den CHANGELOG im selben Commit und
aktualisiere den Roadmap- und Status-Snapshot nach den Projektregeln.
