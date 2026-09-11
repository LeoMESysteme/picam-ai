# Changelog

Neueste Änderung oben. Je Abschnitt: was war das Problem, was wurde geändert,
was ist die Konsequenz.

## 0.1.0.dev0 — 2026-09-11 (repo-maintenance.sh: toter Lauf committete trotzdem; jetzt auch andere lokale Branches)

### Ein während des Laufs abgestürzter/gekillter Claude-Prozess konnte trotzdem committet werden, und nur `master` wurde gepflegt

**Problem:** Bedienerauftrag: "Das maintenance script soll claude status
checken so das wenn ein run während des runs stirbt nicht einfach trotzdem
commitet wird. Das maintenance skript soll nicht nur main sondern auch
andere branches checken und managen." Zwei getrennte Lücken im ursprünglichen
Wrapper (Commit `82f63ff`): (1) `$CLAUDE_STATUS` wurde erfasst, aber nie
geprüft — schlimmer noch, der Fallback-Zweig für eine nicht parsebare
Commit-Message committete trotzdem mit einer generischen Nachricht statt
abzubrechen. Genau das ist die Signatur eines mittendrin getöteten Laufs
(ein gekillter, dann reaped `claude -p` kann trotzdem Exit 0 liefern). (2)
Der Wrapper kannte nur den bei Cron-Start ausgecheckten Branch (`master`);
`docs/oq22-rp2040-wedge` und `test/clahe-ocr-accuracy` wurden nie geprüft.

**Änderung:** Schleife über alle lokalen Branches (`git for-each-ref
refs/heads/`); je Branch derselbe Ablauf wie zuvor, plus: (a) Abbruch **ohne
Commit** wenn `$CLAUDE_STATUS` ungleich 0 UND Änderungen vorliegen, wenn
Dateien ausserhalb `docs/`/`CHANGELOG.md` angefasst wurden, oder wenn keine
parsebare Commit-Message-Markierung im Output steht — alle drei Fälle gelten
jetzt als Signatur eines gestorbenen Laufs, nicht mehr nur als Spezialfall.
(b) Bei Abbruch: gezielter `git stash push -u -- docs CHANGELOG.md` (nur der
betroffene Pfad, damit unrelated Werkstattunordnung im restlichen Baum nicht
mitgerissen wird), plus ein Eintrag `branch: <name>` in der Markerdatei
`~/.local/state/picam-ai-maintenance/needs-review` — **nur dieser eine
Branch** wird ab sofort übersprungen, bis ein Mensch die Zeile entfernt; alle
anderen Branches laufen im selben und in künftigen Läufen unbeeinflusst
weiter (ein reiner Stash wäre für `git status` unsichtbar und hätte sich auf
demselben Branch Nacht für Nacht unbemerkt wiederholt). (c) Die
Schmutzig-Prüfung (Start des Laufs, vor jedem Branch-Wechsel) ist jetzt auf
`docs/`+`CHANGELOG.md` beschränkt statt auf den ganzen Baum — unrelated nicht
committete Tooling-Dateien blockierten die Routine sonst dauerhaft. (d)
Branches mit identischem `docs/`+`CHANGELOG.md`-Stand (gleicher Baum-Hash)
werden übersprungen, damit dieselbe Korrektur nicht auf drei Branches
gleichzeitig landet und Merge-Konflikte erzeugt. Ein `restore_branch`-Trap
kehrt am Ende immer zum ursprünglich ausgecheckten Branch zurück (nie
erzwungen; verweigert die Rückkehr, falls dabei etwas schiefgelaufen sein
sollte, statt zu forcieren). Verifiziert mit einem Fake-`claude`-Binary gegen
Scratch-Repos: normaler Zweig-Durchlauf inkl. Dedup, gekillter Lauf ohne
Commit-Marker, Exit-Status ungleich 0, Fremdpfad-Änderung (jeweils Stash
statt Commit, gezielter Marker-Eintrag, betroffener Branch bleibt beim
Folgelauf übersprungen) sowie ein Drei-Branch-Lauf, in dem genau ein Branch
scheitert, während die beiden anderen trotzdem committet werden.

**Konsequenz:** Ein toter Lauf hinterlässt nie mehr einen stillen,
schlecht beschrifteten Commit, und ein einzelner scheiternder Branch
blockiert nicht mehr die Pflege der übrigen. Alle drei lokalen Branches
(`master`, `docs/oq22-rp2040-wedge`, `test/clahe-ocr-accuracy`) werden ab
sofort gepflegt statt nur `master`. `docs/status.md` behauptete bisher, die
beiden Skript-Dateien seien noch uncommittet — das war seit `82f63ff` falsch,
korrigiert im gleichen Zug.

## 0.1.0.dev0 — 2026-09-10 spät nachts (TUI-style zweistufiger Bestätigungsablauf; Race-Condition-Fix)

### Klick auf die ROI-Box während einer laufenden Vermutungsanfrage verwarf das Ergebnis

**Problem:** Bedienerrückmeldung: "wenn ich die roi box anklicke verliert er
die vorgeschlagene box und schlägt wieder die letzte confirmte box vor."
Ursache, durch Nachverfolgung bestätigt: `suggest()` (`workbench.js`, `R`-Zug)
rief nacheinander `roi.suggest` und `ocr.suggest` auf; beide rechneten ihre
OpenCV-Arbeit (`fit_quad_in_region`/`fit_ocr_box`) vollständig **innerhalb**
von `Controller.command()`s einzigem `with self.lock:`-Block — anders als
`publish()`, das seine OpenCV-Arbeit bewusst ausserhalb des Locks haelt.
Das machte den Umlauf langsam genug, dass ein Klick/Zug auf die ROI-Box
während der Wartezeit `onpointerdown` den **noch alten** Zustand in `drag`
einfror; ein nachfolgendes `onpointermove` überschrieb damit die gerade
eingetroffene Vermutung mit der veralteten, zuletzt bestätigten Geometrie.
Nirgends wurde die Zeigereingabe waehrend einer laufenden Anfrage gesperrt.

**Änderung:** Bei der Fehlersuche äusserte der Bediener den weitergehenden
Wunsch, die tastaturgesteuerte Bedienung (`R` Hinweisrechteck, `G`
Rahmenwechsel, `Shift+Pfeile` Eckenverschiebung, `Strg+Enter` Bestätigung)
durch einen zweistufigen, knopfbasierten Ablauf zu ersetzen:

- **Stufe A (ROI):** die laufende Live-Kandidatensuche zeigt mehrere duenne,
  einzeln anklickbare Vorschlagsboxen; ein Klick waehlt die passende aus.
  Zwei TUI-Knoepfe (✓/✎) an der aktiven Box: ✎ schaltet in einen Bearbeiten-
  Modus (Koerper verschieben, Ecken ziehen — beides bleibt erhalten, wird
  waehrenddessen zu ✕ zum Abbrechen), ✓ uebernimmt die Position.
- Nach ✓ ruft der Client automatisch `ocr.suggest` mit dieser Position auf
  und wechselt zu **Stufe B (OCR)**: derselbe ✓/✎-Ablauf an der
  OCR-Box. Ein Klick auf die jetzt inaktive ROI-Box fuehrt zurueck zu
  Stufe A, ohne die Kandidatensuche neu zu starten.
- ✓ an der OCR-Box sendet den bestehenden `roi`-Op (Quad+OCR-Box zusammen,
  im `annotate`-Modus zusaetzlich das unveraendert Ground-Truth-Textfeld) —
  weiterhin die einzige Stelle, an der `confirmed` wahr wird.
- **Kernbehebung:** waehrend eine Vermutungs-/Bestaetigungsanfrage laeuft
  (`editing.pending`), ignoriert `canvas.onpointerdown` jede Zeigereingabe
  vollstaendig und alle vier Knoepfe sind deaktiviert — genau das verhindert
  die gemeldete Race Condition strukturell, nicht nur zufaellig.
- `ocr.suggest` rechnet seine OpenCV-Arbeit jetzt ausserhalb des Controller-
  Locks (`Controller._suggest_ocr_box`, vor dem `with self.lock:` in
  `command()` abgefangen) — mirror von `publish()`s Muster.
- Der jetzt ungenutzte `roi.suggest`-Op ist entfernt (Kandidatenauswahl liest
  die ohnehin laufend berechnete Kandidatenliste, keine erneute
  hinweisgebundene Suche mehr). `fit_quad_in_region` selbst bleibt - `publish()`s
  Vergleichssuche (heute frueher ergaenzt) nutzt sie weiter unveraendert.
- `freeze()` liefert jetzt die volle Kandidatenliste statt nur der einen
  besten Vermutung (mit einmaligem Nachsuchlauf, falls nach einer
  Bestätigung in derselben Sitzung keine Kandidaten mehr zwischengespeichert
  sind); die vormittags ergänzte automatische OCR-Vorschlag-Vermutung direkt
  in `freeze()` entfällt wieder — die Vermutung passiert jetzt explizit beim
  Stufenübergang.

**Konsequenz:** Der gemeldete Bug ist strukturell behoben (keine
Zeigereingabe waehrend einer offenen Anfrage moeglich), nicht nur seltener
gemacht. Neue Tests: `test_ocr_suggest_does_not_hold_the_controller_lock_during_detection`
(Kernbehebung, Lock-Freigabe), `test_freeze_returns_all_current_candidates`,
`test_freeze_populates_candidates_even_when_none_were_cached`,
`test_command_rejects_the_removed_roi_suggest_op`. `docs/anleitung/10-kamera-livevorschau.md`
aktualisiert. Manuelle Bedienprüfung im echten Browser steht aus (OQ-21).

## 0.1.0.dev0 — 2026-09-10 nachts (Sitzungsstart erzwingt erneute Bestätigung; OCR-Box-Vorschlag beim Öffnen des Editors)

### Bedienerwunsch: jede Sitzung soll mit laufender Erkennung beginnen, nicht mit stillschweigend übernommener alter Bestätigung

**Problem:** Bedienerrückmeldung, nach Klärung per Rückfrage: Der Bediener
möchte beim Start der Web-UI aktiv laufende ROI-Erkennung sehen, daraus die
richtige Anzeige auswählen bzw. den Rahmen nachziehen, dann bestätigen -
woraufhin der Innenbereich automatisch auf Ziffern durchsucht und eine
OCR-Box vorgeschlagen wird, die er wiederum bestätigt oder korrigiert. Die
bisherige Lösung (gedrosselte, auf die bestätigte ROI eingegrenzte
Vergleichssuche) erfüllte das nicht: eine bereits bestätigte Geometrie blieb
sofort `confirmed` und damit run-fähig, ohne dass der Bediener sie in dieser
Sitzung überhaupt gesehen oder bestätigt hätte.

**Änderung:** `Controller.__init__` setzt nach dem Laden eines bereits
bestätigten Profils `confirmed` auf `false` - nur in der Laufzeitkopie, die
gespeicherte Profildatei bleibt unverändert, und `roi`/`roi_quad`/`ocr_box`
bleiben als Startpunkt für eine schnelle erneute Bestätigung erhalten. Das
reaktiviert automatisch die volle, ungedrosselte Vollbild-Kandidatensuche auf
dem Livebild (`publish()`: unbestätigt sucht wie schon immer jedes Bild) und
sperrt den `run`-Modus, bis der Bediener aktiv erneut bestätigt (Konzept.md
§4: „Bestätigung ist der Akt eines Menschen" - jetzt auch nach einem
Neustart, nicht nur einmalig). Zusätzlich ruft `Controller.command("freeze")`
jetzt automatisch `fit_ocr_box` auf dem aktuellen ROI-Ausschnitt auf und
bietet das Ergebnis direkt als `ocr_box` an (gestrichelt markiert,
`ocr_suggested` im Editier-Zustand) - der zweite Schritt des Kalibrierflusses
läuft damit ohne einen zusätzlichen manuellen `R`-Zug für die OCR-Box. Kein
Kandidat ist weiterhin inert: Rückfall auf den bisher gespeicherten oder
(Stufe 1) geschrumpften Default-Wert. Neue Tests
`test_startup_requires_re_confirmation_of_a_previously_confirmed_profile`,
`test_startup_does_not_touch_an_already_unconfirmed_profile`,
`test_freeze_suggests_a_fresh_ocr_box_for_the_current_quad`,
`test_freeze_falls_back_when_no_ocr_box_can_be_suggested`.

**Konsequenz:** End-to-End an einer echten Annotation nachgestellt (Profil
mit bestätigter Geometrie gespeichert, Controller neu instanziiert): nach dem
Neustart ist `confirmed=false`, die Kandidatensuche läuft wieder
(Vollbildsuche findet die Anzeige), `run`-Modus ist gesperrt, `freeze()`
startet am alten `roi` und bietet sofort eine frische OCR-Box-Vermutung an.
Bekannte, unveränderte Grenze: Die automatische OCR-Box-Vermutung trifft am
selben Netzteil-Beispiel wie in OQ-25 dokumentiert weiterhin gelegentlich die
falsche von zwei übereinanderliegenden Anzeigen - das ist ein reiner
Vorschlag, gestrichelt dargestellt, keine automatische Übernahme; siehe
aktualisierter [OQ-25](docs/open-questions.md). Beantwortet **nicht** die
weiterhin offene Labor-/QM-Frage [OQ-05](docs/open-questions.md), ob eine
einmalige Bestätigung je Geräteinstanz betrieblich vorgesehen ist - das ist
eine Softwareentscheidung für den Editor-Workflow.

## 0.1.0.dev0 — 2026-09-10 abends (unbeaufsichtigte Doku-Pflege-Routine)

### Doku driftet zwischen Arbeitssitzungen, niemand räumt zwischendurch auf

**Problem:** `docs/` wächst nur an (Konzept.md-Autorität, Doku-Pflicht aus
AGENTS.md), aber es gibt keinen Mechanismus, der veraltete oder redundante
Abschnitte zwischen Sitzungen kürzt oder Querverweise repariert. Der Pi ist
nachts aus, der Bediener beginnt morgens direkt mit der Arbeit.

**Änderung:** Neues Skript `scripts/repo-maintenance.sh` (per `@reboot`-
Cron kurz nach dem morgendlichen Boot) ruft `claude -p` unbeaufsichtigt mit
festem Prompt (`scripts/repo-maintenance-prompt.md`) auf. Harte Grenzen im
Prompt: nur `docs/` und `CHANGELOG.md`, nie `Konzept.md`/`AGENTS.md`/
`CLAUDE.md`/`src/`/`tests/`/`examples/`, OQ-Einträge werden nie gelöscht
(nur auf „geklärt" gesetzt). Die Claude-Session läuft mit
`--permission-mode acceptEdits` und `--disallowedTools
"Bash,Agent,WebFetch,WebSearch"` (kein Shell-Zugriff, keine Subagenten,
keine externen Abrufe — nur Datei-Tools und installierte Skills/Plugins).
Der Wrapper committet automatisch, aber nur wenn (a) der Arbeitsbaum vor
dem Lauf sauber war und (b) ausschließlich `docs/`/`CHANGELOG.md` geändert
wurden — sonst bleibt alles unangetastet bzw. uncommittet für manuelle
Prüfung liegen. Läuft im Log unter `~/.local/state/picam-ai-maintenance/`.

**Konsequenz:** Ab dem nächsten Boot räumt sich die Doku morgens selbst
auf, bevor die eigentliche Arbeitssitzung beginnt. Läuft nur an, wenn der
Baum bereits committet war — mischt sich also nie mit laufender manueller
Arbeit. Erster scharfer Lauf noch nicht beobachtet (Cron erst nach diesem
Commit eingerichtet).

## 0.1.0.dev0 — 2026-09-10 spätabends (Vergleichssuche schlug andere Bildschirme vor)

### Die wiederhergestellte Vergleichssuche suchte weiter im ganzen Bild statt nur um die bestätigte ROI

**Problem:** Bedienerrückmeldung direkt auf die spätnachmittägliche Änderung:
Nach einem Neustart mit bestätigter ROI/OCR blieb zwar die alte Geometrie
sichtbar, aber die wieder aktivierte Vergleichssuche schlug weiterhin andere
Bildschirme/ROIs im Bild vor. Ursache: Die spätnachmittägliche Änderung ließ
`find_display_candidates` — die Vollbildsuche — auch nach der Bestätigung
weiterlaufen, nur gedrosselt statt bei jedem Bild. Am realen Testaufbau
(Netzteil mit zwei Anzeigen `V`/`A`, zwei Monitore im Hintergrund, weitere
Messgeräte) fand die Suche regelmäßig ein anderes rechteckiges Objekt im
Bild statt der tatsächlich bestätigten Anzeige.

**Änderung:** Die Vergleichssuche nutzt jetzt `fit_quad_in_region` (aus
Stufe 2 der Vortagsarbeit) mit der bestätigten `config["roi"]` als
Suchfenster-Hinweis statt der Vollbildsuche — der Suchraum bleibt auf die
~25 % aufgeweitete Umgebung der bestätigten ROI beschränkt. Zusätzlich neuer
Mindestüberdeckungsfilter `MIN_HINT_OVERLAP = 0.2` in `fit_quad_in_region`
selbst: ein Kandidat muss den *ungepolsterten* Hinweisbereich zu mindestens
20 % überdecken, sonst wird er verworfen — sonst hätte bei einer großzügig
bestätigten ROI (das aufgeweitete Suchfenster kann dann beträchtlichen
Spielraum haben) weiterhin ein zufällig rechteckigeres, aber unbeteiligtes
Objekt am Rand des Fensters gewinnen können. Neuer, an einer nachgebauten
Ablenker-Szene verifizierter Test
`test_fit_quad_in_region_ignores_unrelated_objects_outside_the_hint` sowie
`test_confirmed_roi_never_triggers_the_whole_frame_candidate_search` und
`test_confirmed_roi_verification_search_is_scoped_to_the_confirmed_region`
(ersetzen den bisherigen, auf `find_display_candidates` gestützten
Drosselungstest). Ergebnis in `Controller.publish()` bleibt ein einzelnes
gelbes Vergleichsquad statt mehrerer Kandidatenboxen; `self.candidates`
bleibt (wie ursprünglich dokumentiert) ausschließlich der unbestätigten
Vollbildsuche vorbehalten, das bestätigte Vergleichsergebnis liegt getrennt
in `self.verify_quad`.

**Konsequenz:** Am realen Beispiel (`var/workbench/annotations/*`) trifft
die eingegrenzte Vergleichssuche mit der bestätigten ROI als Hinweis die
tatsächliche Anzeige (IoU ≈ 0,91, wie schon für `roi.suggest` in
[VALIDATION.md](docs/VALIDATION.md) gemessen) und ignoriert die im selben
Bild sichtbaren Monitore vollständig. Nebenbei günstiger als die vorherige
Vollbildsuche: rund 12,5 ms/Bild im (künstlich erzwungenen) Suchfall statt
16,6 ms, Leerlauf und `run`-Modus unverändert bei rund 8,0–8,1 ms/Bild —
aktualisierte Zahlen in [docs/VALIDATION.md](docs/VALIDATION.md). OQ-24
erneut präzisiert, nicht neu eröffnet.

## 0.1.0.dev0 — 2026-09-10 spätnachmittags (Kandidatensuche nach Neustart mit bestätigter ROI)

### Bestätigte Geometrie hatte nach einem Neustart nie mehr einen visuellen Vergleich

**Problem:** Bedienerrückmeldung: Beim Start der Web-UI ist die zuletzt
eingestellte ROI/OCR-Geometrie weiterhin aktiv (korrekt, `Controller.__init__`
lädt das Default-Profil unverändert), aber es wird nicht mehr automatisch
gesucht. Ursache in der mit OQ-24 (2026-09-09) eingeführten Optimierung:
`find_display_candidates` lief `boxes = () if config["confirmed"] else
find_display_candidates(...)` — sobald einmal bestätigt, für immer aus, auch
über Prozessneustarts hinweg. Der Bediener hatte damit keinerlei visuellen
Hinweis mehr (gelbe Kandidatenbox neben dem grünen bestätigten Rahmen), ob die
geladene Geometrie noch zur aktuell vor der Kamera stehenden Szene passt.

**Änderung:** Neue Konstante `CANDIDATE_INTERVAL_S = 1.0` (`controller.py`).
`publish()` sucht jetzt: vor einer Bestätigung weiterhin bei jedem Bild
(unverändert), nach einer Bestätigung gedrosselt auf höchstens einmal je
Sekunde, und **nie im `run`-Modus** — der Produktionsmodus behält die mit
OQ-24 behobenen Vollbildsuche-pro-Bild-Kosten (30,837 ms/Bild) vollständig
abgeschaltet. Zwischen zwei Suchen bleibt die zuletzt gefundene Kandidatenliste
sichtbar (`cached_candidates`), damit die gelben Boxen nicht mit der
Drosselfrequenz flackern. `Controller._load()` loggt beim Laden einer bereits
bestätigten Geometrie zusätzlich einen Warnhinweis, dass sie noch nicht gegen
die aktuelle Szene verglichen wurde. Die Bestätigung selbst bleibt
unangetastet — kein automatisches Un-Confirm, kein automatischer Ersatz der
Geometrie (Konzept.md §4: „Bestätigung ist der Akt eines Menschen"). Neuer
Test `test_confirmed_roi_throttles_candidate_search_outside_run_mode`,
`test_confirmed_roi_in_run_mode_skips_full_frame_candidate_search` (ersetzt
den bisherigen, zu unbedingten Test) und
`test_loading_a_confirmed_profile_warns_about_unverified_geometry`.

**Konsequenz:** Nach einem Neustart mit bereits bestätigter Geometrie
erscheint jetzt wieder eine gelbe Kandidatenbox neben dem grünen bestätigten
Rahmen, mit der der Bediener vergleichen kann, ob die Geometrie noch passt —
ohne dass irgendetwas automatisch übernommen wird. Kostenmessung (gleiches
Realbild wie die OQ-24-Messung): rund 8,3 ms/Bild im gedrosselten Leerlauf,
16,6 ms/Bild im (künstlich erzwungenen) Suchfall, `run`-Modus unverändert bei
rund 8,3 ms/Bild ohne jede Suche — bei 1 Hz Drosselung im Mittel weit unter
1 ms/Bild zusätzlich, siehe [docs/VALIDATION.md](docs/VALIDATION.md). OQ-24
entsprechend präzisiert (`docs/open-questions.md`), nicht neu eröffnet.

## 0.1.0.dev0 — 2026-09-10 (Workbench-Editor: Klickpriorität, automatische Box-Vorschläge, Ground-Truth-Erfassung)

Setzt [docs/PLAN_2026-09-10-workbench-editor.md](docs/PLAN_2026-09-10-workbench-editor.md)
vollständig um (alle drei dort geplanten Stufen).

### Stufe 1 — Verklicken zwischen `roi_quad` und `ocr_box`

**Problem:** Bedienerrückmeldung: Direkt nach einer frischen `roi`-Bestätigung
startet `ocr_box` deckungsgleich mit `roi_quad` (`[0,0,1,1]`). `nearestHandle`
(`workbench.js`) suchte den nächsten Punkt global über beide Boxen zusammen;
an eng benachbarten Ecken traf der Klick oft die äußere ROI statt der
gewollten inneren OCR-Box.

**Änderung:** `nearestHandle` prüft jetzt zuerst alle `ocr`-Ecken innerhalb des
Trefferradius (18 px), erst wenn keine trifft die `roi`-Ecken — die gelbe Box
liegt auch optisch über der grünen (`draw()` zeichnet `roi` zuerst).
`Controller.command("freeze")` bietet zusätzlich, wenn `ocr_box` noch der
unberührte Default ist, im **zurückgegebenen Editier-Zustand** einen spürbar
kleineren Startwert `[0.15, 0.15, 0.7, 0.7]` an — reine Editor-Sitzungsgröße,
weder `self.config` noch eine Bestätigung ändern sich dadurch. Neue Tests
`test_freeze_offers_a_smaller_default_ocr_box_without_persisting_it`,
`test_freeze_keeps_a_confirmed_ocr_box_unchanged`.

**Konsequenz:** Die beiden Rahmen sind direkt nach dem Einfrieren sichtbar
getrennt und die Trefferlogik bevorzugt den optisch obenliegenden Rahmen —
das gemeldete Verklicken tritt nicht mehr auf. Kein Schema-, Migrations- oder
Persistenzeffekt.

### Stufe 2 — Automatische `roi_quad`-/`ocr_box`-Vorschläge über einen groben Bedienerhinweis

**Problem:** Jede Kalibrierung eines neuen Geräts erforderte vollständiges
manuelles Ziehen aller acht Eckpunkte. Eine Kontursuche ohne jeden Hinweis
kann mehrere ähnlich rechteckige Objekte am Prüfstand nicht unterscheiden
(Konzept.md §7: Haupt-/Nebenanzeige-Verwechslung), Vollautomatik wäre also
unzuverlässiger als ein grober Bedienerhinweis.

**Änderung:** Neue Taste `R` im Editor startet einen von der bestehenden
Ecken-/Körper-Ziehlogik getrennten Interaktionsmodus (`hinting`/`hintDrag` in
`workbench.js`): der Bediener zieht ein grobes achsparalleles Rechteck um das
Display. Beim Loslassen ruft der Client `roi.suggest` (neue Funktion
`fit_quad_in_region` in `workbench/vision.py`: Kantenpipeline wie
`find_display_candidates`, aber `cv2.minAreaRect`/`cv2.boxPoints` statt
`cv2.boundingRect`, damit `roi_quad` ein echtes, auch rotiertes Viereck sein
kann; Eckenreihenfolge über die bestehende `dispread.rectify._order_quad`;
Flächenanteil/Rechteckigkeit wie `DetectionConfig`, Seitenverhältnis bei
vorhandenem Layout zusätzlich aus `DisplayLayout.n_cells` abgeleitet), danach
sofort `ocr.suggest` mit dem übernommenen Quad (neue Funktion `fit_ocr_box`:
Otsu-Schwelle in beiden Polaritäten, Blobs nach Höhe filtern, nach vertikaler
Mitte zu Zeilen gruppieren — lückenbasiert statt über einen laufenden
Mittelwert, sonst zieht ein einzelner Ausreißer die Gruppierung über eine
Kette benachbarter Abstände in die falsche Zeile —, größte Zeile nach
Gesamtfläche behalten). Beide neuen Controller-Ops (`roi.suggest`,
`ocr.suggest`) sind reine, synchrone Vorschlagsfunktionen ohne jede
Persistenz. Unbestätigte Vorschläge werden im Editor gestrichelt und
transparent gezeichnet (`editing.roiSuggested`/`editing.ocrSuggested`) und
fallen weg, sobald die jeweilige Box berührt wird. Findet der Server nichts,
bleibt die Editorgeometrie unverändert und eine Logzeile erklärt das — ein
Fehlschlag ist inert, nie eine schlechte Automatik-Übernahme.

**Konsequenz:** `roi_quad`-Vorschläge treffen die beiden realen
Annotationsbilder aus `var/workbench/annotations/` mit IoU ≈ 0,91 gegen die
tatsächlich bestätigte Geometrie (gemessen, siehe
[docs/VALIDATION.md](docs/VALIDATION.md)). `ocr_box`-Vorschläge sind an
denselben zwei Bildern unzuverlässig (IoU 0,0), weil der dort verwendete
Ausschnitt neben der Hauptanzeige eine baugleiche Nebenanzeige enthält — genau
die aus Konzept.md §7 bekannte, ohne weiteren Hinweis strukturell nicht
auflösbare Verwechslung. Neuer Eintrag [OQ-25](docs/open-questions.md). Die
hier gebaute Kontursuche ist **Workbench-Editorhilfe, nicht** die
`DisplayLocator`/`contour_heuristic`-Implementierung aus der ROADMAP-P0-Zeile
„`contour_heuristic`- und `imx500_detector`-Lokalisierung, `RegionTracker`" —
diese Zeile bleibt unverändert offen. `manual_roi` bleibt Primärpfad; jeder
Vorschlag muss weiterhin über den unveränderten `roi`-Op bei `Strg+Enter`
bestätigt werden.

### Stufe 3 — Getippter Ground-Truth-Wert im `annotate`-Modus

**Problem:** `annotate`-Aufnahmen enthielten bisher nur Geometrie, keinen
abgelesenen Wert, und wurden nirgends zurückgelesen — für eine spätere
Trefferquotenauswertung fehlte der einfachste Baustein: der tatsächlich
angezeigte Wert je Aufnahme.

**Änderung:** Neues, rein additives Feld `ground_truth_text` in
`annotation.json` (`Controller.command`, `op == "roi"`, `self.mode ==
"annotate"`-Zweig), vom Client mitgeschickt und ungeprüft übernommen — keine
Schema-Version, keine `validate()`-Änderung, da `annotation.json` nicht gegen
`profiles.py::validate` geprüft wird. `workbench.js` zeigt beim Bestätigen im
`annotate`-Modus ein kleines Texteingabefeld (`#ground-truth` in
`index.html`/`workbench.css`, analog zum bestehenden
Profil-Speichern-unter-Dialog), bevor der `roi`-Befehl abgeschickt wird;
`viewport.onkeydown` ignoriert Editor-Hotkeys, solange der Fokus auf einem
Eingabefeld liegt.

**Konsequenz:** `annotate`-Aufnahmen sind jetzt (Bild, `roi_quad`, `ocr_box`,
Layout, Ground Truth)-Tupel — genug für einen späteren Trefferquotentest gegen
`SevenSegmentReader`, ohne jede Trainingsinfrastruktur zu versprechen oder zu
bauen. Kein `device_id`-Feld für geräteweise Testsplits — bewusst nicht Teil
dieser Stufe (Konzept §9, ROADMAP P2).

### Verifikation

`./.venv/bin/pytest -q` (101 bestanden, inkl. 20 neuer Tests für
`fit_quad_in_region`/`fit_ocr_box`/`roi.suggest`/`ocr.suggest`/Ground-Truth,
zwei davon `skipif` gegen die realen `var/workbench/annotations/*`-Beispiele),
`./.venv/bin/ruff check src tests examples` und
`node --check src/dispread/workbench/static/workbench.js` grün. Manuelle
Bedienprüfung im echten Browser (Klickpriorität, `R`-Vorschlagsfluss,
gestrichelte Vorschlagsdarstellung, `annotate`-Eingabefeld) steht noch aus —
siehe OQ-21/OQ-24, nicht aus `file://`- oder synthetischen Tests ableitbar.

## 0.1.0.dev0 — 2026-09-09 (Editorstart an erkannter Box; Mehrbildbestätigung gegen Flackern)

### Editieren-Start ignorierte die gerade sichtbare erkannte Displayposition

**Problem:** Bedienerrückmeldung: Beim Doppelklick zum Editieren ging die
zuvor sichtbare "erkannte" ROI-Position verloren. Ursache: Die
Vollbild-Kandidatensuche (`find_display_candidates`) zeichnet vor der
Bestätigung laufend gelbe Vorschlagsboxen ins Live-Bild, aber der `freeze`-
Befehl kannte diese Kandidaten nicht - er startete ein frisches, nie
bestätigtes Profil immer an einer festen Standardbox `[0.2, 0.3, 0.6, 0.3]`
in der Bildmitte, unabhängig davon, wo das System die Anzeige gerade
erkannt hatte.

**Änderung:** `Controller` merkt sich die letzte Kandidatenliste
(`self.candidates`, gesetzt in `publish()`). `freeze` startet ein frisches
Profil jetzt an der besten aktuellen Kandidatenbox (nach Rechteckigkeit und
Fläche sortiert), sofern noch nie eine ROI bestätigt wurde; ein bereits
vorhandener - auch unbestätigter - `roi`-Wert bleibt wie zuvor unangetastet
und wird nicht überschrieben. Neuer Regressionstest
`test_freeze_starts_from_last_detected_candidate`.

**Konsequenz:** Der erste Editierschritt eines frischen Profils beginnt jetzt
in der Nähe der tatsächlichen Anzeige statt in der Bildmitte. Bereits
bestätigte oder zuvor gesetzte Geometrie ist von der Änderung nicht
betroffen.

### Live-Vorschau flackerte bei multiplexenden Anzeigen zwischen falschen Werten

**Problem:** Bedienerrückmeldung: Bei Anzeigen mit sichtbarem Flackern
(Multiplexbetrieb gegen die niedrige Kamerabildrate, OQ-20) sprang die
OCR-Vorschau zwischen falschen Werten hin und her - ein einzelnes Bild kann
mitten in einem Umschaltvorgang liegen. `ReleaseGate` unterstützt bereits
Mehrbildbestätigung (`confirm_frames`, auch in
`examples/16_end_to_end_headless.py` als CLI-Option genutzt), die
Workbench-Vorschau instanziierte ihr Gate aber immer mit dem Default `1` -
keine Bestätigung, jedes Einzelbild zählte sofort als `valid`.

**Änderung:** Neue Konstante `GATE_CONFIRM_FRAMES = 3` in `controller.py`;
die Vorschau verlangt jetzt drei übereinstimmende Bilder, bevor
`gate_status` auf `valid` wechselt (`transition`/`awaiting_confirmation`
davor, weiterhin sichtbar in der Bedienzeile „freigabepruefung"). Ein
abweichender Wert setzt die Bestätigung zurück statt zu glätten oder zu
mitteln (Konzept.md §7) - echte Sprünge bleiben sichtbar, nur ein
Flacker-Frame allein reicht nicht mehr, um kurzzeitig als bestätigt zu
gelten. Bestehender Test `test_publish_reads_synthetic_display_and_exposes_evidence`
angepasst (ruft `publish` jetzt dreimal auf, `last_ocr_at` zurückgesetzt, um
die 5-Hz-Drosselung im Test zu umgehen).

**Konsequenz:** Die Vorschau reagiert bis zu `GATE_CONFIRM_FRAMES *
OCR_INTERVAL_S` (rund 0,6 s) langsamer auf einen neuen stabilen Wert, zeigt
dafür aber deutlich seltener einen durch Multiplex-Flackern verursachten
Fehlwert als `valid` an. Behebt nicht die zugrunde liegende Multiplex-/
Belichtungsfrage aus OQ-20 - dafür bleibt eine reale Messung an typischen
Geräten nötig -, mindert aber ihre sichtbare Auswirkung in der Vorschau.
Die Vorschau bleibt ohnehin nur Anzeige, keine Messwertfreigabe.

## 0.1.0.dev0 — 2026-09-09 (Strg+Enter gegen unbeabsichtigte Bestätigung; Ziffernabstand nachgeschärft)

### Bloßes `Enter` bestätigte ROI/OCR-Rahmen zu leicht unbeabsichtigt

**Problem:** Bedienerrückmeldung: Während der ROI-/OCR-Rahmen-Bearbeitung
wurde das Profil gelegentlich ohne bewusste Bestätigung als `confirmed`
markiert. Ursache: `viewport.onkeydown` löste die Bestätigung
(`command('roi', ...)`, setzt serverseitig `confirmed=True` unbedingt,
`controller.py`) allein durch ein einzelnes `Enter` aus — ohne Rücksicht
darauf, ob gerade noch eine Ziehbewegung lief (`drag` gesetzt), und ohne
jede Rückfrage. Der Kamerabereich behält während der ganzen Editiersitzung
den Tastaturfokus; ein einzelnes `Enter`, etwa aus Gewohnheit nach einer
Pfeiltasten-Korrektur oder nach einem Seitenblick auf die Einstelltabelle,
reichte deshalb aus, um eine noch unfertige Geometrie endgültig zu
übernehmen.

**Änderung:** Die Bestätigung verlangt jetzt `Strg+Enter` (bzw. auf dem Mac
`Cmd+Enter`) statt eines einzelnen `Enter`, und wird zusätzlich ignoriert,
solange eine Ziehbewegung noch läuft. Log-Hinweis, `aria-label` und
Anleitung (`docs/anleitung/10-kamera-livevorschau.md`) wurden entsprechend
aktualisiert.

**Konsequenz:** Bestätigen bleibt ein Tastaturbefehl, verlangt aber eine
bewusste Zweitasten-Kombination statt der im übrigen Formular ohnehin
mehrfach belegten `Enter`-Taste. Das Konzept-§4-Prinzip der einmaligen,
bewussten Bediener-Bestätigung wird damit tatsächlich durchgesetzt statt nur
dokumentiert.

### `digit_gap_ratio`-Obergrenze war zu eng

**Problem:** Die frisch eingeführte Bedienzeile „ziffernabstand" ließ sich
laut Rückmeldung „nur bis zu einem bestimmten Grad" erhöhen; danach passierte
sichtbar nichts mehr. Das war die absichtliche, aber zu knapp gewählte
Obergrenze `LAYOUT_RATIOS["digit_gap_ratio"] = (0.0, 1.0)` — ein
Zwischenraum bis zur vollen Zellenbreite reicht nicht für jede reale Anzeige
oder jeden großzügig gezogenen OCR-Rahmen. Das native Zahlenfeld klemmt am
`max`-Attribut ohne jede Rückmeldung, sobald man per Spinner/Mausrad statt
per Eingabe+Bestätigung erhöht — das erzeugte den Eindruck eines defekten
Reglers statt einer erreichten, gewollten Grenze.

**Änderung:** Obergrenze auf `3.0` angehoben (weiterhin ein unvalidierter
Vorabdefault wie die übrigen `LAYOUT_RATIOS`-Einträge), Schrittweite in der
Bedienzeile von `0.02` auf `0.05` vergröbert.

**Konsequenz:** Deutlich mehr Kopfraum für reale Zwischenraumverhältnisse.
Der Regler bleibt weiterhin endlich begrenzt und klemmt am `max` weiterhin
ohne Rückmeldung, wenn per Spinner statt per Zahleneingabe bedient wird —
das ist ein allgemeines Verhalten aller Zahlenfelder dieser Oberfläche
(auch `ExposureTime`, `AnalogueGain`, `Contrast`, `sign_cell_ratio`), nicht
auf dieses Feld beschränkt, und hier bewusst nicht separat behoben.

## 0.1.0.dev0 — 2026-09-09 (Zwischenraum zwischen Ziffernstellen)

### `digit_gap_ratio` ergänzt das bisher lückenlose Ziffernraster

**Problem:** `DisplayLayout.cell_boxes` teilte den OCR-Rahmen ohne jeden
Zwischenraum durch die Stellenzahl — Ziffernzellen (und die Vorzeichenstelle)
lagen rechnerisch exakt aneinander. Bei der Bedienprüfung im Browser zeigte
sich, dass die gelben Segment-Abtastpunkte an mehreren Stellen zu weit
auseinander lagen, sobald der Bediener den OCR-Rahmen auf eine reale Anzeige
mit sichtbarem physischem Abstand zwischen den Stellen legte: Das Raster nahm
diesen Abstand fälschlich als Teil der Ziffernzelle an, wodurch die festen
relativen Segmentpunkte (`SEGMENT_SAMPLE_POINTS`) neben statt auf den
Segmenten landeten — ein weiterer Beitrag zur unter OQ-23 dokumentierten
Fehlablesung, unabhängig von der VFD-Glyphenform.

**Änderung:** `DisplayLayout` bekommt ein neues Feld `digit_gap_ratio`
(Default `0.0`, reproduziert exakt das bisherige Verhalten). `cell_boxes`,
`sign_box` und der synthetische Renderer (`synthetic_source.render_display`)
verwenden dieselbe Formel für Zellenbreite und -abstand, sodass Generator und
Leser weiterhin dasselbe Raster meinen. Ältere gespeicherte Profile ohne das
Feld werden beim Laden mit dem Default aufgefüllt, keine Vermutung über die
tatsächliche Anzeige. Die Workbench zeigt den Wert als eigene Bedienzeile
„ziffernabstand" neben „vorzeichenbreite", inklusive Presets und Grenzen aus
`LAYOUT_RATIOS`.

**Konsequenz:** Der Bediener kann den Zwischenraum zwischen den Stellen jetzt
am eingefrorenen Realbild sichtbar nachjustieren, statt ein lückenloses
Raster zu unterstellen. Behebt nicht die abweichende VFD-Glyphenform aus
OQ-23 — dafür bleibt ein bestätigter Real-Testsatz nötig —, entfernt aber
eine unabhängige Fehlerquelle in der Geometrie selbst.

## 0.1.0.dev0 — 2026-09-09 (sichtbare OCR-Rasterkalibrierung)

### Äußere Perspektiv-ROI und inneres Ziffernraster getrennt einstellbar

**Problem:** Die perspektivische ROI ließ sich bereits an vier Displayecken
ausrichten, der Segmentleser verteilte seine Zellen aber immer über den gesamten
entzerrten Ausschnitt. Enthielt dieser Rahmen Blende, Einheit oder seitlichen
Leerraum, lagen Zellen und sieben Segment-Abtastpunkte neben den Ziffern. Im
eingefrorenen Editor war das wirksame OCR-Raster außerdem nicht sichtbar.

**Änderung:** Profilschema 3 ergänzt `ocr_box` als normierten Innenausschnitt
der entzerrten ROI; Profile aus Schema 1 und 2 werden mit einem zunächst vollen
Innenausschnitt migriert. Der Browser zeichnet während der Kalibrierung die
grüne Perspektiv-ROI und darüber den gelben OCR-Rahmen, Ziffernzellen,
Vorzeichenbereich und alle tatsächlichen Abtastpunkte. Anklicken oder `g`
wechselt den aktiven Rahmen; Maus und Pfeiltasten verschieben beziehungsweise
skalieren ihn. Der Leser schneidet `ocr_box` vor der Segmentanalyse wirklich
aus, und Fokusansicht sowie Live-Overlay benutzen dieselbe Geometrie. Das
eingefrorene Overlay übernimmt reine Layoutänderungen sofort aus dem laufenden
Status; Ziffernzahl und Vorzeichenbreite bauen das Raster neu auf, die feste
Dezimalposition erscheint als eigener cyanfarbener Marker. Solche Änderungen
aktualisieren die Editierrevision, sodass `Enter` weiterhin funktioniert;
Kamera- und sonstige Profiländerungen machen das Bild weiterhin ungültig.

**Konsequenz:** Der Bediener kann das Leseraster an einem eingefrorenen echten
Frame exakt auf Vorzeichen und Ziffern kalibrieren, ohne die äußere
Perspektivkorrektur zu verlieren. Eine automatische Grenzerkennung aus einem
einzelnen Frame wurde bewusst nicht als Wahrheit übernommen: Leuchtsegmente,
Blende und Einheit sind ohne bestätigte Realbeispiele nicht zuverlässig zu
trennen. Unlesbare Raster bleiben abgelehnt statt automatisch passend geraten.

## 0.1.0.dev0 — 2026-09-09 (perspektivische OCR-ROI und Reaktionsfähigkeit)

### Vier Ecken statt starrer Box; Bildarbeit blockiert die Bedienung nicht mehr

**Problem:** Nach der ROI-Bestätigung rechnete die Workbench weiterhin in
jedem Bild die Vollbild-Kandidatensuche, Entzerrung, OCR, Overlays und
JPEG-Kompression, während sie den zentralen Controller-Lock hielt. Status-,
Editier- und Stopbefehle konnten dadurch hinter der Bildschleife verhungern.
Die ROI war außerdem nur achsparallel; ein schräg aufgenommenes Display ließ
sich nicht passend entzerren. Zum Stoppen gab es keinen lokalen
Workbench-Befehl.

**Änderung:** Die Bildarbeit läuft jetzt weitgehend außerhalb des Locks. Nach
Bestätigung entfällt die Vollbildsuche, die OCR-Vorschau läuft mit 5 Hz und das
15-fps-Kamerabild bleibt flüssig. Die Profilversion 2 speichert zusätzlich ein
normiertes Vierpunkt-`roi_quad`; v1-Rechtecke werden beim Laden automatisch und
verlustfrei migriert. Der Browsereditor bietet vier einzeln verschiebbare
Ecken, `rectify` korrigiert Perspektive und Neigung, und Zellen/Abtastpunkte
werden perspektivisch ins Kamerabild zurückprojiziert. `dispread stop` beendet
den Dienst über den nur lokal zugänglichen Unix-Socket. Auch Kamera-`stop` und
`close` haben beim Shutdown einen Wachhund.

**Konsequenz:** Bestätigte ROIs erzeugen keine dauernde Vollbildsuche mehr;
Status und Stop bleiben während der Bildverarbeitung erreichbar. Eine isolierte
Messung am gespeicherten 960×720-Bild sank von 30,837 ms/Bild vor Bestätigung
auf 5,801 ms/Bild mit bestätigter ROI und gedrosselter OCR. Die perspektivische
Entzerrung ist synthetisch getestet. Sie löst nicht die abweichende reale
VFD-Glyphengeometrie aus OQ-23; dafür werden echte, getrennte Trainings- und
Testbilder benötigt.

## 0.1.0.dev0 — 2026-09-09 (OCR-Bedienung)

### Zahlenerkennung ist in Web-Setup und TUI bedienbar

**Problem:** Der Segmentleser lief bereits auf der bestätigten Kamera-ROI und
lieferte seine Evidenz in `snapshot()["reading"]`, aber Zahlenformat und
Ergebnis waren in der gemeinsamen Einstelltabelle nicht sichtbar. Die
Bedienperson musste das Layout über Profildatei oder lokalen Rohbefehl setzen
und konnte Ablehnungsgründe nicht im Setup prüfen.

**Änderung:** `workbench/fields.py` liefert jetzt Auswahlzeilen für
Ziffernzahl, profilfeste Nachkommastellen, Vorzeichen und bestätigte Einheit
sowie ein Zahlenfeld für die Vorzeichenbreite. Unmögliche Kombinationen werden
vor der Auswahl gesperrt; geladene Sonderwerte bleiben sichtbar. Drei
Anzeigezeilen zeigen Rohtext/Zahlenwert, die Freigabevorschau und erklärbare
Segment-/Ausschnittevidenz. Web und TUI verwenden diese Zeilen ohne eigenen
OCR-Pfad. Integrationstests schicken eine synthetische Anzeige durch
`Controller.publish()` und belegen außerdem, dass eine unbekannte
Dezimalposition abgelehnt statt geraten wird.

**Konsequenz:** Die bestehende Bright-on-dark-7-Segment-Erkennung kann jetzt
vollständig aus der Workbench eingerichtet und diagnostiziert werden. Sie
bleibt bewusst eine Vorschau: kein `ValueRecord`, keine Messwertfreigabe, keine
serielle Ausgabe; Einheit und Dezimalposition stammen weiter aus dem Profil,
und `declares_confidence_calibrated` bleibt `False`. Die erste Prüfung am
beschrifteten BK-5491B-Realbild wurde sicher abgelehnt (`777?7`, kein Wert),
zeigt aber, dass das feste synthetische Segmentraster nicht auf diese
VFD-Schrift übertragbar ist; die Weiterarbeit ist als OQ-23 dokumentiert.

## 0.1.0.dev0 — 2026-09-09 (noch später)

### Power-Zyklus-Budget überlebt jetzt einen dispread-Neustart korrekt (OQ-22)

**Problem:** `geometry_cycles` lebte nur im Prozessspeicher. Der RP2040
merkt sich Power-Zyklen aber pro **Boot**, nicht pro Prozess (belegt: ein
Test mit je einem frischen Python-Prozess pro Zyklus hing trotzdem nach
~24 Zyklen). Ein Neustart von `dispread` allein — ohne Host-Reboot — hätte
den Zähler faelschlich auf 0 gesetzt und so mehr echte Power-Zyklen erlaubt,
als das Sicherheitsbudget vorsieht. Das Sicherheitsversprechen aus der
vorigen Änderung war damit lückenhaft.

**Änderung:** `geometry_cycles` wird jetzt zusammen mit der aktuellen
Kernel-Boot-ID (`/proc/sys/kernel/random/boot_id`) in
`camera_cycles.json` persistiert (`_load_geometry_cycles`,
`_save_geometry_cycles`, `atomic_json`). Stimmt beim Start die gespeicherte
Boot-ID mit der aktuellen überein, wird der Zähler fortgeführt; bei einem
echten Reboot (andere oder fehlende Boot-ID) beginnt er korrekt bei 0.

**Konsequenz:** Das Sicherheitsbudget haelt jetzt auch ueber
`dispread`-Neustarts hinweg, ohne dass ein Host-Reboot noetig ist, um den
Zaehler zu "umgehen". Zwei neue Tests beweisen beide Faelle:
`test_geometry_cycles_survive_process_restart_same_boot` (gleiche Boot-ID
-> Zaehler bleibt) und `test_geometry_cycles_reset_on_new_boot`
(abweichende Boot-ID -> Zaehler auf 0). 67 Tests und `ruff check src tests
examples` grün.

## 0.1.0.dev0 — 2026-09-09 (spätabends)

### Hartes Power-Zyklus-Budget: RP2040-Sperre kann durch Workbench-Bedienung nicht mehr ausgeloest werden (OQ-22)

**Problem:** Bislang konnte eine Bedienperson im `setup`-Tab beliebig oft
Aufloesung oder Bildrate aendern. Jede echte Aenderung kostet einen
RP2040-Power-Zyklus (bestaetigt: unbind/rebind-Test hat den Regulator
tatsaechlich auf 0 Nutzer fallen lassen). Nach real gemessenen ~20-25
Zyklen antwortet der Chip nicht mehr auf I2C - bislang ohne Vorwarnung,
mitten in einer Sitzung.

**Änderung:** Neue Konstante `MAX_GEOMETRY_CYCLES = 15` (Sicherheitsabstand
unter dem beobachteten Bereich). `Controller.geometry_cycles` zaehlt jeden
tatsaechlichen Stream-Neuaufbau in `_worker`. `_check_geometry_budget()`
verweigert `camera.set`/`camera.set_many`, sobald eine **echte** Aenderung
(nicht das Wiederwaehlen des bereits aktiven Werts) das Budget
ueberschreiten wuerde, mit klarer Fehlermeldung statt eines spaeteren,
unvorhersehbaren Ausfalls. `geometry_cycles`/`geometry_cycles_max` stehen
jetzt in `snapshot()`.

**Konsequenz:** Solange nur ueber die Workbench bedient wird, kann die
RP2040-Sperre **nicht mehr unbeabsichtigt ausgeloest werden** - die
Bedienperson bekommt stattdessen rechtzeitig die Aufforderung, `dispread`
(und danach den Host) neu zu starten, statt dass die Kamera mitten in einer
Messreihe unvorhersehbar haengt. Das behebt den RP2040-Fehler selbst nicht,
verhindert aber zuverlaessig, ueber die eigene Bedienoberflaeche
hineinzulaufen. Neuer Test
`test_geometry_budget_blocks_change_but_allows_same_value` beweist beides:
echte Aenderung wird bei erschoepftem Budget verweigert, Wiederwaehlen des
aktiven Werts bleibt erlaubt. 65 Tests und `ruff check src tests examples`
grün.

## 0.1.0.dev0 — 2026-09-09 (später)

### Aufloesungswechsel kostet jetzt deterministisch einen statt zwei Power-Zyklen (OQ-22)

**Problem:** Der `resolution`-Auswahlzeile in `fields.py` sandte Breite und
Hoehe als zwei getrennte `camera.set`-Befehle. Der zuvor ergaenzte
250-ms-Entprellpfad in `_worker` buendelt das meistens zu einem
Stream-Neuaufbau, ist aber eine Zeitfensterheuristik - kein garantiertes
Verhalten, falls die beiden Befehle mit mehr Abstand ankommen.

**Änderung:** Neuer Controller-Befehl `camera.set_many` setzt mehrere
Kamerafelder in genau einer `_change()`-Revision; die per-Feld-Logik aus
`camera.set` ist dafuer in `_apply_camera_key()` ausgelagert (von beiden
Befehlen geteilt, keine Dopplung). Die Aufloesungszeile in `fields.py`
sendet jetzt einen einzigen `camera.set_many`-Befehl mit Breite und Hoehe
zusammen statt zwei `camera.set`-Befehlen.

**Konsequenz:** Ein Aufloesungswechsel kostet garantiert genau einen
RP2040-Power-Zyklus statt (zeitfensterabhaengig) bis zu zwei - unabhaengig
vom Timing zwischen den beiden Feldern. Neuer Test
`test_camera_set_many_is_one_atomic_revision` beweist das direkt: eine
Revision, beide Felder gesetzt. 64 Tests und `ruff check src tests
examples` grün.

## 0.1.0.dev0 — 2026-09-09

### Kamerathread: Geometrie-Aenderungen buendeln, haengende Kamera-Ioctls sichtbar machen (OQ-22)

**Problem:** Ein Diagnose-Reproducer ohne `dispread`-Code hat gezeigt, dass
der RP2040-Bridge-Chip auf der AI-Camera nach rund 20-25 Power-Zyklen
(`stop`/`configure`/`start`) innerhalb einer Bootsitzung nicht mehr auf I2C
antwortet — danach haengt jeder weitere Kamerazugriff, nur ein Reboot hilft
(Details: [OQ-22](docs/open-questions.md)). `Controller._worker` loeste
bislang bei **jeder** einzelnen Aenderung von Breite, Hoehe oder Bildrate
sofort einen Neuaufbau aus; da die Weboberflaeche Breite und Hoehe als zwei
getrennte Befehle sendet, kostete eine Aufloesungsaenderung im Betrieb zwei
Power-Zyklen statt einem. Zusaetzlich hing der Worker bei einer haengenden
Kamera-Ioctl (`configure`/`start`/`stop`/`capture_request`) fuer immer
schweigend, statt den Fehler als das zu melden, was er ist.

**Änderung:** `_worker` puffert Geometrie-Aenderungen ueber ein kurzes
Zeitfenster (`GEOMETRY_DEBOUNCE_S`, 250 ms) und baut den Stream erst neu auf,
wenn Breite/Hoehe/Bildrate sich nicht mehr aendern — mehrere schnelle
Befehle buendeln sich so zu einem Neuaufbau statt mehrerer. Die riskanten
Kameraaufrufe (`stop`, `configure`, `start`, `capture_request`) laufen jetzt
ueber `_guarded()`: ein Wachhund-Thread mit `CAMERA_OP_TIMEOUT_S` (6 s).
Kehrt der Aufruf nicht zurueck, wird das als `CameraWedgedError` gemeldet
("Kamera reagiert nicht (...); vermutlich RP2040-Sperre (OQ-22), Reboot
noetig") statt als endloser Timeout; die anschliessende Aufraeumroutine
verzichtet dann bewusst auf einen weiteren `stop()`/`close()` auf demselben,
bereits blockierten Kameraobjekt.

**Konsequenz:** Reine Belichtungs-/Verstaerkungs-/Kontraständerungen waren
bereits vorher `set_controls()`-only und bleiben unveraendert kostenlos.
Aufloesungs-/Bildratenaenderungen kosten jetzt hoechstens einen Power-Zyklus
statt zwei. Eine echte RP2040-Sperre wird jetzt innerhalb von rund
`CAMERA_OP_TIMEOUT_S` als klarer Fehlerzustand sichtbar (`snapshot()["error"]`)
statt als unbestimmt haengender Kamerathread — behebt die Sperre selbst
nicht, macht sie aber sofort erkennbar. 63 Tests und `ruff check src tests
examples` weiterhin grün; die bestehenden Workbench-Tests laufen alle mit
`simulate=True` und durchlaufen den neuen Entprell-/Wachhundpfad nicht — ein
gezielter Test dafür fehlt noch.

## 0.1.0.dev0 — 2026-09-08

### Zahlenerkennung an der Kamera angeschlossen (Zwischenstand, Bedienung fehlt)

**Problem:** Die Verarbeitungskette aus Konzept §3 war fertig, lief aber nur
gegen synthetische Bilder. Die Workbench besaß Kamera und bestätigte ROI, hat
daraus aber nie einen Wert gelesen — und im Profil fehlte das Zahlenformat, das
der Segmentleser laut Konzept §4 braucht.

**Änderung:** Das Workbench-Profil führt einen `layout`-Block (`digits`,
`decimals`, `has_sign`, `unit` plus Rasterverhältnisse) mit eigener Prüfung in
`profiles.validate_layout` — unmögliche Formate wie „mehr Nachkommastellen als
Stellen" werden abgelehnt. Der Controller entzerrt bei bestätigter ROI jedes
Bild über `rectify` auf feste 400×160, liest es mit `SevenSegmentReader` und
führt die Freigabeprüfung `ReleaseGate` **als Anzeige** mit. Ergebnis, Evidenz
je Stelle, Ablehnungsgründe und Qualität des Ausschnitts stehen in `snapshot()["reading"]`.
Die Abtastpunkte der sieben Segmente werden ins Kamerabild zurückgezeichnet,
hell wenn gemessen aktiv — damit sieht der Bediener, ob das Raster sitzt. Neuer
Befehl `layout.set`.

**Konsequenz:** Aus einem scharfen Kamerabild entsteht ein gelesener Wert samt
Begründung, warum er freigegeben würde oder nicht. **Kein** `ValueRecord`, keine
Freigabe, keine serielle Ausgabe — `released` ist konstant `false`, und die
Zeitangabe der Vorschau-Veralterung ist CLOCK_MONOTONIC und ausdrücklich kein
Messwertzeitbezug. Die Einheit stammt weiter aus dem Profil
(`unit_source=profile`), sie wird nicht gelesen.

**Was noch fehlt:** Die Bedienzeilen in `fields.py` (Zahlenformat als
Auswahlfelder, Ablesung und Ablehnungsgründe als Anzeigezeilen) und die Tests
für den Lesepfad. Der Kern ist gegen einen synthetisch gerenderten Wert geprüft:
gezeichnet `-12.34`, gelesen `-012.34`, Wert −12,34, Freigabeprüfung `valid`
ohne Ablehnungsgründe. Bis das UI steht, ist das Zahlenformat nur über
`layout.set` oder die Profildatei erreichbar. 63 Tests und Ruff grün — die
Tests deckten diesen Pfad noch **nicht** ab.

### Einstelltabelle in der Weboberfläche, Werte werden ausgewählt statt getippt

**Problem:** Die Einrichtung lag nur in `dispread tui`, das der Bediener erst in
der Web-Shell von Hand starten musste. Dort war jedes Feld ein Freitextdialog
mit `json.loads`: `true`/`false` für Belichtungsautomatik und Fokusassistenz,
Zahlen für die Belichtung, aber `mode` und `role` ohne Anführungszeichen. Typ,
Grenzen und Default lagen in den Kamera-Capabilities längst maschinenlesbar vor.

**Änderung:** Neues Modul `workbench/fields.py` beschreibt Zeilen und Aktionen
einmal als Daten (`rows()`, `actions()`, `run_blocked()`); `/status` liefert sie
mit, die Weboberfläche rendert daraus einen festen `setup`-Tab neben den Shells,
der nach der Anmeldung sofort aktiv ist. Auswahlfelder für Modus, Rolle,
Auflösung, Bildrate, Belichtungsautomatik, Fokusassistenz und Profil;
Zahlenfelder mit Kameragrenzen und Schnellwahl für Belichtungszeit, Verstärkung
und Kontrast; Anzeigebereich und Erkennungsfilter als reine Anzeigezeilen.
Gesperrte Zeilen und Aktionen nennen ihren Grund, statt erst am Kommando zu
scheitern. `dispread tui` bleibt für den Betrieb ohne Browser und rendert
dieselbe Quelle mit Auswahllisten statt Freitext. `snapshot()` führt die
vorhandenen Profilnamen mit; Freitext bleibt nur für einen neuen Profilnamen.

**Konsequenz:** Einrichtung ohne zusätzliches Kommando und ohne JSON-Kenntnis;
Web und Terminal können nicht mehr auseinanderlaufen, weil beide dieselben
Optionen lesen. Der Controller bleibt die durchsetzende Instanz — `fields.py`
ist Bedienhilfe, keine Regel. Keine OCR, Messwertfreigabe oder neue
Abhängigkeit. 63 Tests und Ruff grün, darunter der Nachweis, dass jede
angebotene Auswahl vom Controller angenommen wird. setup-Tab mit 21 Prüfpunkten
in Chromium über eine `file://`-Seite mit echter `/status`-Antwort geprüft;
Netzwerknavigation dieses Chromium bleibt defekt (OQ-21). Keine erneute
Hardwaremessung.

### Authentifizierte Kamera-Workbench mit Shell, TUI und Profilen

**Problem:** Der Ein-Datei-Prototyp bot weder echte Shells noch eine gemeinsame
Steuerung für Kameraeinstellungen, gespeicherte Profile und Boxkorrekturen.

**Änderung:** `dispread serve` startet eine HTTPS-Workbench mit Linux-PAM-
Anmeldung für `me-systeme`, echten PTY-Shell-Tabs und lokaler Unix-Socket-API.
`dispread tui` bietet eine tastaturbediente Einstelltabelle. Ein Kamerathread
verwaltet validierte Live-Controls, automatische Einstellvorschläge,
Fokusassistenz, Profilkonflikte und eingefrorene Bilder für ROI/Annotationen.
Der bisherige Beispielaufruf bleibt als Einstieg erhalten. Systemabhängigkeiten
und lokal ausgelieferte xterm-Assets sind dokumentiert.

**Konsequenz:** Einheitliche Steuerung ohne Sliderwand; Browsertrennung beendet
keine Shell. Noch keine OCR, Messwertfreigabe oder Modelltraining. 58 Tests
einschließlich TLS/WebSocket/Shell/TUI grün; realer Kameradienst geprüft.
Chromium-UI mit simuliertem Transport geprüft. Vollständige HTTPS-Browserabnahme
bleibt wegen lokaler Chromium-Navigationsprobleme offen (OQ-21); ebenso
gerätespezifische Auto-Setup-Validierung (OQ-20).

### Barebones-Terminalansicht für die Kameravorschau

**Problem:** Die Vorschauseite enthielt erklärenden Fließtext und kein
eigenes Logfenster.

**Änderung:** Dunkle Monospace-Oberfläche mit Kamera- und Logfenster,
kompaktem Live-Status, Bildnummer und Verarbeitungsrate. Auf schmalen
Bildschirmen stehen die Fenster untereinander. Erklärungen, Verbindungswechsel,
Kamerafehler und periodische Statusmeldungen erscheinen im Browserlog mit
UTC-Zeitangabe. Maximal 300 Zeilen, `clear`, automatisches Scrollen nur am Ende.

**Konsequenz:** Weniger Text außerhalb des Logs. Das Log enthält
Vorschaudiagnostik, keine Shell und keine vollständige Prozess-stdout-Umleitung.
Neun Vorschautests und Ruff grün; Terminalansicht mit simuliertem Feed in
Chromium geprüft. Keine erneute Hardwaremessung.

### Kameralivebild mit Display-Kandidaten über SSH

**Problem:** Für den ersten Versuch fehlte eine Livevorschau auf dem
Windows-Rechner und eine automatische Suche nach möglichen Anzeigebereichen.

**Änderung:** `examples/17_camera_display_preview.py` verbindet Picamera2,
OpenCV-Konturfilter, gelbe Kandidatenboxen und einen lokalen MJPEG-HTTP-Server.
Windows greift über SSH-Portweiterleitung im Browser zu. Nur das neueste Bild
wird vorgehalten; die Seite blendet bei ausbleibendem Bildfortschritt oder
Verbindungsabbruch das Bild aus. Filter sind per Argument einstellbar.

**Konsequenz:** Vorschau ohne zusätzliche Abhängigkeiten; keine OCR oder
Messwertfreigabe. Neun neue Tests prüfen Erkennung, HTTP und Fehlerbehandlung.
Realer Kamerastream lokal geprüft, Windows/SSH und Erkennungsqualität am
Gerät noch offen. Anleitung: `docs/anleitung/10-kamera-livevorschau.md`.

### Kamera in Betrieb genommen und vermessen

**Problem:** Die AI Camera war an CAM/DISP0 angeschlossen, wurde aber nicht
erkannt. `rpicam-hello --list-cameras` meldete `No cameras available!`.

**Änderung:** `scripts/camera-commissioning.sh` prüft die gesamte Kette rein
lesend durch und nennt am Ende die nächste Maßnahme. Ursache war der fehlende
Reboot — `camera_auto_detect` prüft die Anschlüsse ausschließlich beim Booten,
und die Kamera war nach dem letzten Boot angesteckt worden.

**Konsequenz:** Kamera läuft. Zwei Falschmeldungen im Skript beseitigt:
`dtoverlay -l` ist kein Kriterium (firmwareseitig angewandte Overlays
erscheinen dort nicht), und die CAM-I2C-Busnummern sind nicht stabil (hier 6
und 10). Nachweis ist der Sensorknoten im Device-Tree plus die
libcamera-Enumeration. Gemessen: 6,8 s `.rpk`-Warmlauf, 15,0 Inferenzen/s,
`SensorTimestamp` in CLOCK_BOOTTIME — siehe `docs/TIMING.md`.

### Verarbeitungskette aus Konzept §3 aufgebaut

**Problem:** Das Repo enthielt nur das Konzept, keinen Code. Zugleich sind
zentrale Anforderungen offen — das GSVmulti-Telegramm ist unbekannt, es gibt
keinen Datensatz echter Geräte.

**Änderung:** Alle Trennstellen als `Protocol` definiert, mit `frozen`
Datenklassen als Vertrag: `FrameSource`, `DisplayLocator`, `ValueReader`,
`ReleaseGate`, `ValueSink`, `TelegramFormatter`. Implementiert sind
`synthetic://` als Bildquelle, `manual_roi` als Lokalisierung, die
Vierpunkt-Entzerrung, der 7-Segment-Leser mit Per-Segment-Evidenz, die
Freigabelogik, das JSONL-Audit-Log und die serielle Ausgabe mit provisorischem
ASCII-CSV.

**Konsequenz:** Die Kette läuft Ende zu Ende ohne Hardware
(`examples/16_end_to_end_headless.py`, 40/40 korrekt, 40 Telegramme auf der
Leitung). Das echte GSVmulti-Format ist später ein neuer Formatter, keine
Änderung an der Pipeline.

### Bestätigte manuelle ROI als Primärpfad statt IMX500-Detektion

**Problem:** Naheliegend wäre, die Anzeige mit einem der 23 mitgelieferten
IMX500-Modelle zu finden.

**Änderung:** Priorität umgekehrt. Gemessen liefert `network_intrinsics`
COCO-Labels (`person`, `bicycle`, `tv`) — für Messverstärker-Displays
unbrauchbar. Eigene Modelle sind auf diesem Pi nicht konvertierbar, nur der
Packager ist vorhanden.

**Konsequenz:** Werterkennung, Freigabelogik und Ausgabekette konnten sofort
gebaut und gemessen werden. Konzept §10 Ph. 2 nennt den manuellen Ausschnitt
selbst als Rückfalloption. Die Detektion bleibt austauschbar.

### Segmentschwelle aus den Segmentmessungen statt aus dem Bild

**Problem:** Zwei Fehlversuche. Eine Schwelle pro Ziffernzelle verwarf jede
`8` (bei sieben aktiven Segmenten ist der zellinterne Kontrast null). Otsu über
alle Bildpunkte erkannte den Überlauf nicht — eine 7-Segment-Anzeige hat drei
Helligkeitsstufen, und die inaktiven Segmente sind die häufigste.

**Änderung:** Die Schwelle kommt aus den gepoolten Segmentmessungen aller
Stellen.

**Konsequenz:** `8` wird gelesen, Überlauf erkannt, starke Unschärfe führt
nicht mehr zur Ablehnung aller Frames. Bekannte Grenze: zeigt die Anzeige
ausschließlich `8`, wird abgelehnt (OQ-13) — nach Konzept §7 die zulässige
Richtung.

### Invarianten aus Konzept §7 im Code verankert

**Änderung:** Der `ValueRecord`-Konstruktor verweigert einen `STALE`- oder
`UNREADABLE`-Datensatz mit Zahlenwert und eine Ablehnung ohne Begründung.
`ValueReader.read` und `ReleaseGate.evaluate` bekommen den Referenzwert
strukturell nicht als Parameter. Vorzeichen, Dezimalpunkt und Einheit sind
eigenständige Ablehnungskriterien; `sign_region_readable` ist getrennt von
`sign_detected`.

**Konsequenz:** Alle drei „stillen" Fehlermodi aus §7 haben einen Test, der
fehlschlägt, wenn das System sie zeigt — inklusive des Nachweises, dass ein um
20 % verfälschter Referenzwert identische Datensätze erzeugt.

### Zeitbasis als Pflichtfeld

**Problem:** Beim Entwickeln ohne Kamera entstehen Zeitstempel, die keine
Zeitaussage tragen. Der naheliegende Fehler wäre, sie später als reale
Latenzen zu berichten.

**Änderung:** `TimeBaseKind` ist Pflichtfeld in `Frame` und `ValueRecord`, mit
`carries_time_information`. Adapterzustand liegt in einem separaten
`TxReceipt`; der Adapter darf `capture_timestamp` nie verändern.

**Konsequenz:** `report.json` weist `timing_is_meaningful` maschinenlesbar aus.

### Dokumentation als Projektbestandteil

**Änderung:** `docs/status.md` (Momentaufnahme), `project_history.md`
(Entscheidungen), `open-questions.md` (OQ-01 bis OQ-19), `lab_journal.md`
(Experimente inklusive Fehlversuche), `TIMING.md`, `VALIDATION.md`,
`ROADMAP.md`, `HARDWARE_PROFILE.md`, `CAMERA_COMMISSIONING.md`,
`OPTICAL_SETUP.md`, `GSVMULTI_PROTOCOL.md`, `dependencies.md`. Die
Aktualisierungspflicht steht in `AGENTS.md`.

**Konsequenz:** `pyproject.toml` deklarierte zwei Konsolenskripte auf nicht
vorhandene Module — entfernt, weil ein Einsprungpunkt auf ein fehlendes Modul
erst zur Laufzeit scheitert. `CLAUDE.md` markiert je Komponente, was fertig ist.
