# Aufgabe 3 — abschließendes Astra-Review

**Spec, Codequalität, Tests und Offline-Evidenz für Task 3 ausdrücklich
freigegeben. Keine offenen Findings.** Das zuvor offene Korpusgate ist
geschlossen. Die Freigabe gilt für den beschriebenen begrenzten B1-Fallback;
sie ist keine Hardwareabnahme oder allgemeine Validierung der Rastererkennung.

## Geprüfter Umfang

Task-3-Brief, Vorbereitung, aktueller Bericht, ursprünglicher Produktdiff,
`task-3-fix1.diff`, `task-3-evidence.diff`, betroffene Tests und Dokumentation,
eingefrorene vier Varianten, Manifest, vollständige Ergebniszeilen, alle drei
neuen Vergleichsdateien, sechs Shardlogs, drei neue Truth-Dateien und Overlays.
Frühere Feststellungen und ihre Schließung stehen in
`task-3-astra-review.md` und `task-3-astra-tests.md`.

Der Produktcode blieb seit der Code-/Testprüfung unverändert und ist
bytegleich zur archivierten A1+B1-Quelle:
`e2fe141232cf6300e4303f5035354aa8c7ee1d7a711966c3b084d7cceee545ec`.
Die isolierte B1-Quelle hat
`187461559dcccae6983b3a15361918c41361bc04f0bb38a8f8bdce33cb9e4202`.
Bereits unabhängig geprüft: Baseline→B1 enthält ausschließlich Task 3;
B1→A1+B1 ist exakt der A1-Diff von Baseline→A1.

## Spec und sichere Steuerung

Die bisherige Suche läuft zuerst mit unverändertem Budget und unveränderten
Annahmeprüfungen. Erst drei tatsächliche `keine_startlage`-Ergebnisse erlauben
eine zweite Unterkantenannahme. Erfolgreiche Fits, Mehrdeutigkeit, Minuszeichen
und andere terminale Ablehnungen bleiben erhalten; auch eine erst später in
`keine_startlage` umgedeutete andere Ablehnung aktiviert den Zusatzlauf nicht.
Fehlende oder identische Hough-Richtungen beenden die Alternative vor der
Kandidatensuche. Die zweite Suche verwendet dieselben Qualitäts-, Plus-,
Leerzellen- und Eindeutigkeitsprüfungen. Keine Annahmegrenze wurde gelockert.

Diese beschränkte Umsetzung erfüllt den B1-Auftrag vertretbar: Sie sucht
nach erfolgloser ursprünglicher Annahme zusätzlich die obere Richtung und
ersetzt nicht pauschal jede Unterkante. Bei bereits akzeptiertem Erstfit
wird eine mögliche konkurrierende Alternativgeometrie nicht gesucht. Diese
Grenze ist ausdrücklich dokumentiert und wird hier nicht als vollständiger
geometrischer Eindeutigkeitsnachweis ausgegeben.

## Unabhängig nachgeprüfte Korpusdaten

Ein eigener lesender Prüfskriptlauf hat alle tatsächlichen Bild- und
Textdateihashes gegen das Manifest geprüft, die versuchsspezifischen Labels
neu aus den Textdateien zugeordnet und sämtliche Varianten verglichen.
Alle Assertions bestanden (Exit 0): 90 eindeutige Pfade, 74 unterschiedliche
Bildhashes, je Variante exakt die Manifestpfade, alle 180 neuen Zeilen mit
passendem Quellhash und ohne Fehlerfeld. Duplikate sind mit ihrem Original
hash- und ergebnisgleich. Alle sechs Logs enthalten jeweils 30 passende
Ergebnisse und enden beim richtigen letzten Shardindex 88, 89 bzw. 90.

| Umfang | Baseline | B1 | A1 | A1+B1 |
| --- | ---: | ---: | ---: | ---: |
| Historische 65 Standbilder | 58 | 59 | 61 | 63 |
| Erweiterte 74 Standbilder | 64 | 66 | 69 | 72 |
| Alle 90 Pfade | 80 | 82 | 85 | 88 |

Die drei gespeicherten Vergleichsdateien wurden zeilenweise gegen eigene
Berechnungen aus den Ergebnisquads geprüft. Keine verlorenen Fits. Maximaler
Eckabstand Baseline→B1: 0 px; Baseline→A1+B1: 0,5224298057906849 px;
A1→A1+B1: 0 px. Beide Oktober-Gegenproben sind in beiden Varianten exakt
baselinegleich. Sie bleiben Bestandserhaltungsbelege, keine gesicherten
Sollgeometrien. Alle fünf früher geprüften A1-Neufits sowie der verschobene
Altfit bleiben gegenüber A1 exakt gleich; die zugehörigen früheren
Gegenprüfungen und Warnungen bleiben anwendbar.

Der Wrapper-Exit 143 ist kein erfolgreicher Prozessabschluss und wird auch
nicht so gewertet. Vollständige, parsebare und durch Manifest, Quellen und
Logs konsistent abgesicherte Ergebnisartefakte tragen hier den abgeschlossenen
Offline-Vergleich unabhängig vom Wrapperstatus. Daraus wird keine
Laufzeitaussage abgeleitet.

## Neue Fits unabhängig geprüft

Alle drei neuen Overlays wurden im Review selbst angesehen. Sichtbare
Zeichen passen zum jeweiligen seriellen Versuchstext; Plus, Dezimalpunkt,
Zellen 0–7, Leerzelle 8, Einheit 9–12 und Punktpositionen zeigen keine falsche
Zellen- oder Punktspaltenzuordnung. Zusätzlich wurde `check_truth.py` im
Review lesend auf den exakt gespeicherten A1+B1-Quads erneut ausgeführt,
ohne die Fits zu wiederholen. Alle drei vollständigen JSON-Ergebnisse stimmen
exakt mit den archivierten Truth-Dateien überein, einschließlich
Readerdetails und Vorlagenhash:

| Bild | Serieller Text | Reader | Offset | max. Betrag dx, Spalten |
| --- | --- | --- | --- | ---: |
| 115232Z/versuch-1 | +0.70502 | OK | OK | 0,1307870370 |
| 142321Z/versuch-1 | +0.60297 | OK | OK | 0,0644531250 |
| 130253Z/still | +0.62969 | OK | WARNUNG | 0,1806640625 |

Die ersten beiden Quads sind in B1 und A1+B1 exakt identisch. Damit decken
diese Gegenprüfungen sämtliche neuen B1-Fits und sämtliche drei zusätzlichen
Fits gegenüber A1 ab. Die Warnung beim dritten Bild bleibt ausdrücklich
bestehen; das Ergebnis wird nicht zu einer uneingeschränkten Validierung
hochgestuft. In den geprüften neuen Fits wurde keine falsche Lage festgestellt.

## Tests, Dokumentation und Findingsabschluss

Die vorherige P2-Testlücke ist geschlossen: direkte Hough-Guards, spätere
Glättungserfolge und terminales Minus ergänzen die vorhandenen Ablehnungs-
und Konkurrenztests. Die gezielten 2+2+18 sowie 6 Tests und Ruff sind im
Taskbericht dokumentiert. Die vollständige Suite wurde nicht erneut gestartet.
Ihr Log bestätigt 4219 bestanden, sechs Fehler, 20 übersprungen, zwei xfailed;
kein Rastertest steht in der Fehlerliste. Die vier Task-1-Fake-/Golden-Fälle
werden im separat geprüften Integrationsfix behandelt. Der isolierte Log
der beiden unveränderten Zeitprüfungen bestätigt 2 bestanden in 11,70 s.
Das ist keine Behauptung eines vollständig grünen erneuten Gesamtlaufs.

CHANGELOG, VALIDATION, Laborjournal, Entscheidungshistorie, OQ-69 und
Recherchepaket nennen Verhalten, Zahlen und Grenzen. Die während dieses
Reviews angemerkt widersprüchliche Ablehnungsformulierung in VALIDATION
ist zu A1+B1=2 und B1=8 korrigiert; der veraltete Hinweis auf eine laufende
Gesamtsuite im Taskbericht ist ebenfalls korrigiert. Beide Stellen wurden
nachgelesen. Der frühere P3-Begriff „gültige Gegenproben“ bleibt behoben.

**Abschluss: Task 3 mängelfrei innerhalb des beschriebenen Scopes freigegeben.**
Das abschließende Review des gesamten Branches und dessen Doku-/Browserchecks
bleiben ein eigener Auftrag. Keine Hardware, Dienste, Produktdateien oder
Eingabedaten wurden durch dieses Review verändert; geschrieben wurde nur
diese Reviewdatei.
