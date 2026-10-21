# Wert lesen (`ocr/`)

Aktiv im Live-Pfad ist `DotMatrixReader` für GSV-2AS / Displaytech 161A mit
geprüfter Vorlagen-Prüfsumme und `CharLayout`. Er klassifiziert die
Wertzellen, prüft Restleerzellen und Format und liefert Einzelzelldiagnosen.
Die Einheit stammt aus dem bestätigten Profil. Negative Werte und andere
Geräte sind damit nicht freigegeben.

`raw_text` enthält gegenwärtig die geparste Zahl mit Pluszeichen, keine
vollständige Abschrift der 16 Displayzellen; Ablehnungen liefern leeren
Text. Leser und Gate bekommen keinen Referenzwert. Eine angebotene erhöhte
Lesetoleranz wird während der Einrichtung seriell gegengeprüft und
bestätigt; sie ist weiterhin nicht validiert
([Live-Betrieb](../docs/uebersicht/projekt-tour.md#bedienung-werkbank)).

Daneben bestehen Sieben-Segment mit Per-Segment-Evidenz, tesseract und
Autofit als weitere Bausteine. Ihre Evidenzen und Schwellen sind nicht mit
der Abstandsskala des Dot-Matrix-Lesers gleichzusetzen. Konfidenz bleibt
bei allen Backends eine unkalibrierte Qualitätskennzahl.

::: dispread.ocr
