# Wiki-Gerüst: Wege nach Rolle, Schichten, Glossar als Begriffsindex

Stand: 2026-10-23, **bestätigt** (Umsetzung beauftragt). Grundlage:
`PRODUCT.md` im Projektwurzelverzeichnis (Leser, Leitlinien; nicht Teil
des Wikis) und zwei
Klärungsrunden. Kein Code; dieser Brief legt fest, was gebaut wird und wie
es sich verhalten soll.

## 1. Auftrag und Leser

Modus **Lesen**: Der Besucher will etwas verstehen oder erledigen, nicht
überzeugt werden. Drei Wege mit wachsender Tiefe:

| Weg | Wer kommt | Frage beim Ankommen |
| --- | --- | --- |
| **Einrichten und bedienen** | neue Nutzer, Bediener im Labor | „Wie bekomme ich das zum Laufen und fahre eine Messung?" |
| **Konfigurieren und verstehen** | fortgeschrittene Bediener | „Wofür ist diese Einstellung, was passiert dahinter, soll ich sie ändern?" |
| **Entwickeln und anbinden** | Entwickler, später Fremde | „Wo ist die Trennstelle, was ist der Vertrag, was darf ich ändern?" |

Daneben Kollegen und Vorgesetzte, die über Tour, Roadmap und Status den
Stand ansehen.

## 2. Ergebnis und Beleg

* Ein Einsteiger erreicht von der Startseite in **einem Klick** den ersten
  Schritt seines Wegs und sieht keine Codebeispiele, bevor er sie braucht.
* Jede Seite sagt im Kopf, **für wen** sie ist und **wohin es weitergeht**.
* Wer einen Begriff sucht, findet im Glossar Definition **und** alle Stellen,
  an denen er vorkommt, mit Kontext beim Überfahren, ohne Seiten zu öffnen.
* Zahlen in Diagrammen und Statusanzeigen kommen aus Daten oder Code; die
  offenen Grenzen (OQ-07, GSV-2AS-Beschränkung) bleiben sichtbar.

## 3. Richtung

**Sichtbare Autorität:** das bestehende Zensical-Theme (Schrift, Farben,
Navigation, Statusfarben, hell und dunkel). Es wird **erweitert, nicht
ersetzt** — kein neuer Look, kein Marketing-Auftritt. Die Roadmap-Karte und
die Projekt-Tour zeigen das vorhandene Niveau an Interaktion; neue
Bausteine reihen sich dort ein.

**Struktur-These:** Die linke Navigation bleibt als vollständiges
Nachschlage-Verzeichnis unverändert (Baum und URLs). Die Führung nach Rolle
entsteht **über** ihr: Startseite als Weiche, Seitenkopf als Wegweiser,
Schichten in der Seite als Tiefenregler, Glossar als Querschnitt.

**Brennpunkt:** die Weiche auf der Startseite — drei Wegspalten, darin die
häufigsten Aufgaben als Einstiege.

## 4. Umfang

Gerüst plus je Weg **eine vollständig umgestellte Beispielseite** als
Vorlage; die übrigen Seiten werden später nachgezogen (TODO-Eintrag).

1. **Startseite (`README.md`)**
   * Kopf: ein Satz, was das System tut, und eine Statusleiste aus Daten
     (aktive Kamera, Messpfad-Stand, GSVmulti offen mit OQ-07-Status).
   * Weiche: drei Wegspalten, je drei bis vier Aufgaben als Einstiege
     („Kamera einrichten", „Erste Messung fahren", „Eine Einstellung
     verstehen", „Ein Ausgabeprotokoll anbinden" …). Jede Aufgabe führt zum
     ersten Schritt einer kuratierten Folge.
   * Darunter: Tour-Einstieg, Stand für Kollegen (Status, Roadmap), danach
     das vollständige Seitenverzeichnis wie heute (einklappbar), weil die
     Startseite laut Test und Pflegeauftrag alle Navigationsziele verlinkt.
2. **Seitenkopf** auf jeder Inhaltsseite unter der Überschrift: Weg
   („Für: Bedienen"), geschätzte Lesezeit, „Vorher lesen"/„Weiter mit"
   innerhalb des Wegs. Quelle ist das Front Matter der Seite.
3. **Schichtblöcke** in der Seite: Bedienschritte bleiben oben und knapp.
   Technik steht in zwei einklappbaren Blockarten mit eigenem Symbol:
   „Was passiert im Hintergrund" (für Konfigurierende) und „Für
   Entwickler" (Code, Funktionen, Pfade). Auf Bedienseiten zu, auf
   Entwicklerseiten offen. Inhalt bleibt im HTML (Suche, Druck, ohne JS).
4. **Konfigurations-Erklärung** als Seitenmuster: je Einstellung Name,
   Zweck, was im Hintergrund passiert, Standardwert, **„Ändern?"** mit
   klarer Antwort (nein / nur wenn … / ja), Wirkung, Quelle im Code.
5. **Entwickler-Anbindungspunkt** als Seitenmuster: Trennstelle, Vertrag,
   was man ändern darf und was nicht, welche Tests laufen müssen,
   Codebeispiel.
6. **Hover-Infos aus einem Baustein** (baut auf den vorhandenen
   Glossar-/Abschnittsvorschauen auf): Fachbegriffe (erste Nennung je
   Abschnitt automatisch markiert), Konfigurationsschlüssel, OQ-Verweise
   (Titel und Status), Statuswörter. Per Tastatur fokussierbar, auf Touch
   per Antippen, nie die einzige Stelle einer Information.
7. **Statusanzeigen im Text:** OQ-Verweise und Roadmap-Phasen tragen einen
   kleinen Statuschip aus den vorhandenen Indexdaten (OQ-Index,
   Roadmap-Tabelle).
8. **Interaktive Verarbeitungskette** (`frames → detect → track → rectify →
   ocr → validate → sink`): Stufen mit Bauzustand aus Daten; Überfahren
   zeigt Zweck, wichtigste Einstellung und Anbindungspunkt, Klick führt zur
   API-Seite. Volle Darstellung als senkrechte Liste in „Die Kette
   verstehen", kompakte Darstellung als Fluss auf der Startseite.
9. **Diagramme aus Messdaten** für Validierung und Zeitverhalten, nach dem
   Muster der Fortschrittsseite: Daten werden erzeugt, die Tabelle bleibt
   Quelle und Ansicht ohne JavaScript.
10. **Glossar als globaler Begriffsindex** (Abschnitt 5).

**Beispielseiten:** Bedienen → `docs/CAMERA_COMMISSIONING.md`
(Bedienschritte vorn, StreamCam-Details in Schichten); Konfigurieren →
die Kameraregler (`focus_absolute`, Automatiken) als
Konfigurations-Erklärung; Entwickeln → Ausgabeprotokoll anbinden
(`sink/protocol`, inklusive des absichtlich werfenden `gsv_ascii` und
OQ-07 — **kein** erfundenes Telegramm).

**Unangetastet:** linke Navigation und URLs, Zensical-Theme,
Roadmap-Karte, Projekt-Tour, Fortschrittsseite, OQ-Ansicht, alle
fachlichen Aussagen ohne neuen Beleg.

**Nicht-Ziele:** keine Landingpage mit Werbewirkung, keine nach Rolle
gefilterten Seitenkopien, kein Verstecken von Inhalten vor der Suche,
keine Information nur im Pop-up, keine erfundenen Begriffe, Zahlen oder
Protokolldetails.

## 5. Glossar als Begriffsindex

**Rolle neben der Suche:** Die Zensical-Suche findet jeden Text. Das Glossar
beantwortet zwei andere Fragen: *Was bedeutet der Begriff hier genau?* und
*Wo ist er relevant?* Es ist kuratiert (nur echte Begriffe mit Definition),
die Suche ist vollständig. Beide verweisen aufeinander: Ein Glossareintrag
bietet „Alle Treffer in der Suche"; ein leerer Glossarfilter bietet die
Volltextsuche mit demselben Wort an.

**Aufbau der Seite:**

* A–Z-Leiste und Filterfeld oben (Begriff oder Abkürzung, auch Synonyme:
  „Kameraanbindung" findet „Kamera-Anbindung" und `v4l2://`).
* Je Begriff: Kurzdefinition (die auch im Pop-up erscheint), Weg-Kennung
  (Bedienen / Konfigurieren / Entwickeln), Synonyme, Quelle.
* **Vorkommen:** nach Seite gruppiert, mit Anzahl; jede Fundstelle nennt den
  Abschnitt. Überfahren zeigt den Satz um die Fundstelle mit
  hervorgehobenem Begriff; Klick springt zum Abschnitt und markiert die
  Stelle. Viele Vorkommen werden gekürzt („und 37 weitere auf 9 Seiten").
* Ohne JavaScript: Definitionen alphabetisch lesbar; die Vorkommen brauchen
  JavaScript und den Suchindex.

**Datenfluss:** Definitionen stehen weiter in Markdown (Glossarseite, damit
Menschen und der Pflegelauf sie bearbeiten können), mit stabilen IDs,
Synonymen und Weg-Kennung je Eintrag. Vorkommen werden zur Laufzeit aus dem
Suchindex `search.json` ermittelt (Begriff → Seite, Abschnitt, Kontextsatz).
Damit stammen exakte Anker aus dem gebauten Wiki, es braucht keinen
Zweiphasen-Build und die Vorkommen sind mit dem aktuellen Suchindex immer
aktuell. Das Format der Glossareinträge prüft `scripts/wiki-check.py`
mit `--check` vor dem Build. Die automatische Begriffsmarkierung auf allen
Seiten nutzt dieselben Definitionen und Abgleichregeln.

**Ausbau:** Ziel ist ein Begriffsbestand, der alle im Wiki verwendeten
Fachbegriffe, Konfigurationsschlüssel, Verfahrensnamen und Abkürzungen
abdeckt (heute ≈ 40 Einträge). Ein Kandidatenlauf schlägt Begriffe aus
Überschriften, Code-Spans und Abkürzungen vor; jede Definition wird gegen
Code oder Projektdokumente belegt und verlinkt ihre Quelle. Unbelegtes
bleibt draußen.

## 6. Zustände und Mengen

* Seiten: ≈ 60; Begriffe: heute ≈ 40, Ziel mehrere Hundert; Vorkommen je
  Begriff 1 bis > 200.
* Ohne JavaScript, mit reduzierter Bewegung, schmale Ansicht (Pop-ups
  werden zu antippbaren Einblendungen ohne Querscrollen), helles und
  dunkles Theme, Sofortnavigation (Bausteine bauen sich je Seite neu auf
  und räumen auf).
* Fehlende oder veraltete Daten (Index, Messdaten, OQ-Status): lesbare
  Meldung statt leerer Fläche; der Build lehnt einen veralteten Index ab.

## 7. Interaktion und Layout

* Startseite: drei gleichrangige Wegspalten auf breiten Ansichten, auf
  schmalen untereinander in Wegreihenfolge; Einstiege als Karten oder
  Zeilen mit eindeutigem Ziel, kein Karussell.
* Seitenkopf knapp in einer Zeile unter der Überschrift; „Weiter mit" auch
  am Seitenende.
* Pop-ups mit kurzer Verzögerung beim Überfahren, sofort bei Fokus, Esc
  schließt; nie über der Maus festhängend.
* Bewegung nur, wo sie Zusammenhang zeigt (Kette, Diagrammaufbau,
  Glossarsprung); Anime.js aus der lokalen Kopie.

## 8. Rahmenbedingungen und offene Entscheidungen

* Deutsch; Zensical-Build über `./scripts/docs-site.sh`; Browsertests in
  `tests/docs-site.spec.ts` für jeden neuen Baustein; Dokupflicht nach
  `AGENTS.md`.
* **Pflegelauf:** Der tägliche Codex-Lauf (`scripts/docs-maintenance-prompt.md`)
  darf Startseite, `zensical.toml` und `docs/anleitung/*` ändern, also auch
  Weiche und Glossar. Sein Auftrag muss die Bausteine, Front-Matter-Felder
  und Glossarregeln kennen, bevor sie live gehen.
* `PRODUCT.md` muss committet sein, damit der Pflegelauf sie im Checkout
  findet.
* Offen für die Umsetzung: Mechanismus für das Front Matter im Seitenkopf
  (Template-Erweiterung oder erzeugte Daten); genaue Markdown-Form der
  Glossareinträge; Abgleichregeln für Vorkommen (Groß/klein, Beugung,
  Komposita über Synonyme); welche Mess-Diagramme zuerst.
* Nach dem Bau des Gerüsts `DESIGN.md` aus dem Ergebnis ableiten
  (`/impeccable document`).
