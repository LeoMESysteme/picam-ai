# Offene Punkte

„Jetzt“ zeigt die noch offenen Fragen aus der [Arbeitsliste](../TODO.md) in
deren Reihenfolge. Darunter stehen alle übrigen Fragen.

<!-- OQ-INDEX:START — erzeugt von scripts/oq-index.py, nicht von Hand bearbeiten -->

| OQ | Fokus | Status | Titel |
| --- | --- | --- | --- |
| [OQ-62](#oq-62) | Jetzt | in Arbeit | Wie wird die Windows-Brücke mit EXE, Verbindungsassistent und GSVmulti-Session eingerichtet? |
| [OQ-64](#oq-64) | Jetzt | in Arbeit | Wie findet und koppelt die Windows-Brücke verschiedene Pi über LAN und Tailscale? |
| [OQ-65](#oq-65) | Jetzt | offen | Wie werden Windows-Releases signiert, aktualisiert und gegen Rückstufung geschützt? |
| [OQ-26](#oq-26) | Jetzt | offen | Grenzen der Nachführung an realen Geräten validieren |
| [OQ-07](#oq-07) | Jetzt | teilweise geklärt | GSVmulti-Telegrammspezifikation beschaffen |
| [OQ-06](#oq-06) | Jetzt | teilweise geklärt | Wie werden ungültige Werte in GSVmulti und in der Kalibrierauswertung behandelt? |
| [OQ-50](#oq-50) | Jetzt | teilweise geklärt | Bleiben GSVmulti-Einzelwerte bei Anzeige und Aufzeichnung unverändert? |
| [OQ-51](#oq-51) | Jetzt | teilweise geklärt | Erhält Replace Missing Values ungültige Zeiträume bei UserDefined? |
| [OQ-52](#oq-52) | Jetzt | teilweise geklärt | Warum scheitert das Wiederöffnen nach Device/Channel Close mit Port bereits offen? |
| [OQ-53](#oq-53) | Jetzt | teilweise geklärt | Wie wird der UserDefined-Zahlenfilter in der Session kodiert und wirksam übernommen? |
| [OQ-55](#oq-55) | Jetzt | teilweise geklärt | Warum meldet die UserDefined-Initialisierung einen Clear-Buffer-Fehler? |
| [OQ-58](#oq-58) | Jetzt | teilweise geklärt | Warum ersetzt die frei laufende TCP-Demo auch außerhalb des Abbruchs einen gültigen Wert? |
| [OQ-47](#oq-47) | Jetzt | teilweise geklärt | Welcher Windows-COM-Transport trägt UserDefined ohne Altwertnachlauf? |
| [OQ-60](#oq-60) | Jetzt | offen | Wie werden Läufe gespeichert, exportiert und wieder aufgeräumt? |
| [OQ-59](#oq-59) | Jetzt | offen | Lässt sich ein Lauf nach Anzeigeverschiebung oder Kamerastoß aus einer Bildaufzeichnung nachberechnen? |
| [OQ-61](#oq-61) | Jetzt | offen | Was lebt nur noch im alten Controller und auf der alten Startseite? |
| [OQ-40](#oq-40) | Jetzt | weitgehend geklärt | Schwelle für „Telegrammlücke&quot; im Gate-Labeler ist ungemessen |
| [OQ-02](#oq-02) | — | offen | Welche maximale Zeitabweichung zwischen DUT und Referenz ist zulässig? |
| [OQ-03](#oq-03) | — | offen | Kann die Referenz einen Trigger oder Zeitstempel bereitstellen? |
| [OQ-04](#oq-04) | — | teilweise geklärt | Welche Gerätetypen bilden den ersten freizugebenden Umfang? |
| [OQ-05](#oq-05) | — | offen | Ist eine einmalige Bestätigung durch den Laboranten im Ablauf vorgesehen? |
| [OQ-09](#oq-09) | — | offen | RS-232-/RS-485-Transceiver und galvanische Trennung |
| [OQ-10](#oq-10) | — | offen | Spezialisierte 7-Segment-Traineddata für Tesseract |
| [OQ-11](#oq-11) | — | offen | Workstation für die IMX500-Modellkonvertierung |
| [OQ-13](#oq-13) | — | offen | Anzeigepolarität und der Fall „alle Stellen zeigen 8&quot; |
| [OQ-14](#oq-14) | — | offen | Freigabeschwellen an realen Geräten validieren |
| [OQ-17](#oq-17) | — | offen | Sichtbarer Dezimalpunkt und Profilannahme unterscheiden |
| [OQ-18](#oq-18) | — | offen | Welches neuronale OCR-Modell trägt auf realen Displays? |
| [OQ-19](#oq-19) | — | offen | Freigabeevidenz für weitere OCR-Backends |
| [OQ-20](#oq-20) | — | offen | Auto-Setup gegen Multiplexing echter Anzeigen absichern |
| [OQ-21](#oq-21) | — | offen | HTTPS-Browserabnahme der Workbench |
| [OQ-22](#oq-22) | — | offen | Sensor setzt nach Streamwechsel keinen Stream mehr auf |
| [OQ-23](#oq-23) | — | offen | Festes Segmentraster passt nicht zur realen BK-5491B-VFD-Schrift |
| [OQ-24](#oq-24) | — | in Arbeit | Browserreaktion und Shutdown nach ROI-Bestätigung real abnehmen |
| [OQ-25](#oq-25) | — | offen | Vorschlagsqualität von `fit_quad_in_region`/`fit_ocr_box` an realen Geräten |
| [OQ-27](#oq-27) | — | offen | Rasterfeinschliff je Bild bewusst nicht gebaut |
| [OQ-28](#oq-28) | — | offen | Eindeutigkeit der Autofit-Geometrie |
| [OQ-29](#oq-29) | — | offen | Zeitpunkt von `calibrated_on`/`calibrated_on_frame_sequence` |
| [OQ-30](#oq-30) | — | offen | `roi`-Op ist nicht atomar gegenüber einem fehlschlagenden `QuadTracker`-Aufbau |
| [OQ-32](#oq-32) | — | offen | `_row()`/`edit_row()` haben keinen sicheren Fallback für einen unbekannten `kind` |
| [OQ-33](#oq-33) | — | offen | Ähnlichkeitsschwellwert des Datensatz-Sammelmodus ist unvalidiert |
| [OQ-34](#oq-34) | — | offen | Realer interaktiver Browserdurchlauf des Datensatz-Sammelmodus steht aus |
| [OQ-35](#oq-35) | — | offen | Automatisierte Testwerterzeugung für den Datensatz-Sammelmodus (GPIO/BK-5491B) |
| [OQ-36](#oq-36) | — | offen | Sättigungsbasierte LCD-Quad-Findung nur an einem Gerät gemessen |
| [OQ-38](#oq-38) | — | weitgehend geklärt | Ground-Truth-Quelle für Auto-Labeling: Displaybus oder Geräteschnittstelle? |
| [OQ-39](#oq-39) | — | offen | Ziffernabdeckung des GSV-Datensatzes ist durch den festen Stimulus begrenzt |
| [OQ-41](#oq-41) | — | teilweise geklärt | Telegramm und Anzeige unterscheiden sich in der führenden Null |
| [OQ-42](#oq-42) | — | offen | Wie wird die ROM-Gegenprobe für weitere Aufstellungen belastbar? |
| [OQ-43](#oq-43) | — | offen | Was bedeutet der Zeitstempel der UVC-Kamera: Belichtung oder Pufferempfang? |
| [OQ-48](#oq-48) | — | offen | Lassen sich ausgefallene Übertragungszeiträume historisch in GSVmulti importieren? |
| [OQ-49](#oq-49) | — | offen | Wo wird der SSH-taugliche Ein-Befehl-Installer bereitgestellt? |
| [OQ-56](#oq-56) | — | teilweise geklärt | Ist direkter USB-CDC-ACM-Betrieb am Pi 5 mit stabiler Versorgung praktikabel? |
| [OQ-57](#oq-57) | — | teilweise geklärt | Wie genau hält der lokale Windows-Demosender seine Zielrate ein? |
| [OQ-63](#oq-63) | — | teilweise geklärt | Warum bleibt nach Displaybewegungen dauerhaft der zweite Nachführfit nötig und wie soll das UI ihn anzeigen? |
| [OQ-67](#oq-67) | — | offen | Warum fehlte einmal das written-Ereignis im kombinierten Zustands-/COM-Test? |
| [OQ-68](#oq-68) | — | offen | Auf welchem Windows-Rechner wird der Installer der Brücke automatisch gebaut? |
| [OQ-69](#oq-69) | — | offen | Warum findet die Rastersuche im lesbaren Einrichtungsbild keine Startlage? |
| [OQ-70](#oq-70) | — | teilweise geklärt | Warum scheitert die Einrichtung trotz gültigem Raster an den Nachführbereichen? |
| [OQ-71](#oq-71) | — | offen | Wie kann ein fehlerhafter Einrichtungsvorschlag abgebrochen oder neu gestartet werden? |
| [OQ-72](#oq-72) | — | offen | Warum lehnt die Kantenprüfung die letzte Ziffer der neuen Aufstellung ab? |
| [OQ-73](#oq-73) | — | offen | Warum aktualisiert die Werkbank während der Einrichtung verzögert? |
| [OQ-74](#oq-74) | — | offen | Warum wird das Bild nach erfolgreich geprüfter Fokussuche wieder unscharf? |
| [OQ-75](#oq-75) | — | offen | Warum fielen Kamerabild und Workbench-Verbindung gleichzeitig kurz aus? |
| [OQ-01](#oq-01) | — | geklärt | Welches serielle Format akzeptiert die eingesetzte GSVmulti-Version? |
| [OQ-08](#oq-08) | — | geklärt | An welchem CAM-Anschluss hängt die Kamera? |
| [OQ-12](#oq-12) | — | geklärt | Was ohne angeschlossene Kamera nicht verifizierbar war |
| [OQ-15](#oq-15) | — | geklärt | `tesseract-ocr`, `socat` und `chrony` installieren |
| [OQ-16](#oq-16) | — | geklärt | Vollständigkeit des lokalen Planungsstands |
| [OQ-31](#oq-31) | — | geklärt | Stale-Vorschau-Zustand bei manueller Regler-Bearbeitung nach Autofit |
| [OQ-37](#oq-37) | — | beantwortet | Anzeigeformat des GSV-Sensors bei Werten ab 10 mV/V ungemessen |
| [OQ-44](#oq-44) | — | geklärt | Wie wird die Freigabesicherung eines Testlaufs im Audit erzwungen? |
| [OQ-45](#oq-45) | — | geklärt | Wie werden monotone Verarbeitungsmarken korrekt als Zeitbasis bezeichnet? |
| [OQ-46](#oq-46) | — | geklärt | Warum scheitert der Live-Rahmenfit trotz korrekter Grobverschiebung? |
| [OQ-54](#oq-54) | — | geklärt | Welche GSV-Bibliotheksversionen lädt die getestete Windows-Installation? |
| [OQ-66](#oq-66) | — | geklärt | Warum wählt der Session-Explorer-Test nach Tastaturfokus gelegentlich den falschen Tag? |
| [OQ-76](#oq-76) | — | geklärt | Warum verliert ein Lauf nach bestätigter Einrichtung sämtliche Rahmenmerkmale? |

<!-- OQ-INDEX:END -->

## Zur Pflege

Jede Unbekannte hat eine Nummer `OQ-nn`. **Einträge werden nie gelöscht**, nur
auf `geklärt` oder `verworfen` gesetzt — mit Datum, Antwort und Verweis darauf,
wo die Antwort gelandet ist. So bleibt nachvollziehbar, warum etwas so ist.

Status: `offen` · `in Arbeit` · `teilweise/weitgehend geklärt` · `geklärt`/`beantwortet` · `verworfen`.
OQ-01 bis OQ-06 sind die sechs offenen Entscheidungen aus Konzept.md §11.

Die Übersicht wird mit `./.venv/bin/python scripts/oq-index.py` aus den Einträgen
und den aktiven Aufgaben in [TODO.md](../TODO.md) erzeugt. Das Skript nach
einem neuen OQ, Status- oder TODO-Wechsel ausführen; `--check` prüft den Stand.

---

<span id="oq-01"></span>

## OQ-01 — Welches serielle Format akzeptiert die eingesetzte GSVmulti-Version?

* **Status:** geklärt (2026-11-04) · **Zuständig:** ME-Systeme intern
* **Antwort 2026-11-04:** GSVmulti 2.03 Pro unter Windows 11 akzeptiert
  im geprüften UserDefined-Profil einen gültigen Einkanal-Zahlenstrom
  `%<vorzeichenbehaftete Dezimalzahl mit Punkt>\r\n`, 115200/8N1,
  ein Wert/Position 1, Zahlenfilter ein. Rampen und acht abrupte Sprünge
  unverändert gespeichert; Lauf 11 belegt Skalierung 1 und mV/V in TDMS
  sowie der gespeicherten Session. Einheit ist Empfängermetadatum, kein
  Bestandteil des Zahlentelegramms. [Antwort](GSVMULTI_PROTOCOL.md#userdefined-format),
  [Messbeleg](VALIDATION.md#uart-demo-20261104-11).
  Dies klärt gültige Zahlen dieser Konfiguration, nicht native GSV-Protokolle,
  Ungültigbehandlung, Quellzeiten oder die gemeinsame Windows-Brücke.
  Formatter bleibt provisional; OQ-06/OQ-47/OQ-50/OQ-51 bleiben eigenständig.
* **Ursprünglicher Quellenstand:** Die Herstelleranleitung v2.6, S. 118–121, beschreibt
  `UserDefined` in GSVmulti PRO: selbsttätiger ASCII-/UTF-8-Zahlenstrom über
  realen oder virtuellen COM-Port, 8N1, Dezimalpunkt, CRLF und konfigurierbare
  Präfixe/Kanalpositionen. Der Nutzer bestätigt Windows; das bereitgestellte
  PDF dokumentiert 2.01 Pro. Ein Empfang in dieser Installation ist noch
  nicht nachgewiesen. Siehe [Format und Quellen](GSVMULTI_PROTOCOL.md#userdefined-format).
* **Update 2026-11-04:** Nutzer meldet Windows 11 und GSVmulti 2.03;
  Python 3.15 x64 und COM3 per PowerShell zurückgemeldet. PRO-Lizenz,
  UserDefined-Verfügbarkeit und Empfang bleiben unbestätigt.
* **Weitere Rückmeldung 2026-11-04:** `UserDefined` ist in der eingesetzten
  2.03-Installation ausgegraut. Die Anleitung ordnet den Eingang GSVmulti
  PRO zu (S. 118); eine fehlende/ungültige PRO-Freischaltung ist damit eine
  zu prüfende Ursache, noch keine bestätigte Diagnose. Der Empfangstest
  wartet auf die Klärung der Freischaltung.
* **Klärung der Freischaltung 2026-11-04:** Nutzer hat die PRO-Lizenz
  aktiviert; `UserDefined` ist nun verfügbar. Damit ist diese Voraussetzung
  in GSVmulti 2.03 bestätigt. COM-Portpaar und tatsächlicher Empfang sind
  weiterhin offen. Verweis: [Windows-Teststand](GSVMULTI_PROTOCOL.md#windows-bruecke).
* **UART-Versuch 2026-11-04:** GSVmulti zeigte trotz passender gezeigter
  Kanal-/Präfixkonfiguration Timeout. Bei geschlossenem GSVmulti bestätigt
  der PowerShell-Hex-Ausschnitt sechs korrekte Telegramme auf COM4. Die
  Eingangsbytes sind für diese Proben belegt; die Ursache der fehlenden
  GSVmulti-Übernahme bleibt offen. Nächster kontrollierter Vergleich ist
  der Zahlenfilter. [Beleg](VALIDATION.md#uart-demo-20261104-03).
* **Empfang 2026-11-04:** Nach eingeschaltetem Zahlenfilter zeigt Lauf 04
  erstmals Zahlen in GSVmulti 2.03 Pro. Direkter UART-Demoweg damit sichtbar;
  Einzelwerttreue, Aufzeichnung und Zeitachse bleiben in OQ-50 offen.
  [Beleg](VALIDATION.md#uart-demo-20261104-04).
* **Freigabegrenze:** Die gültige Zahlenformatfrage ist geklärt. Vollständige
  P4-Abnahme bleibt insbesondere wegen fehlender Ungültigmarkierung offen
  (OQ-06/OQ-51); gemeinsame Brücke und Quellzeitnachweis nicht daraus ableiten.
* **Historischer Vorabdefault:** `AsciiCsvFormatter`, als `provisional=True` gekennzeichnet.
  Der gebaute UserDefinedFormatter bleibt ebenfalls provisional.
* **Antwort landet in:** [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md#userdefined-format),
  [VALIDATION](VALIDATION.md#uart-demo-20261104-11)
* OQ-07 führt die weitergehende Spezifikations-/Beschaffungssicht;
  die Ungültigbehandlung liegt in OQ-06.

<span id="oq-02"></span>

## OQ-02 — Welche maximale Zeitabweichung zwischen DUT und Referenz ist zulässig?

* **Status:** offen · **Zuständig:** Labor / QM
* **Blockiert:** die **Abnahme**, nicht das Bauen. Das Messprogramm M1–M8
  läuft unabhängig davon; der Grenzwert wird am Ende gegen die Zahlen gelegt.
* **Antwort landet in:** [TIMING.md](TIMING.md), Abschnitt Unsicherheitsbudget

<span id="oq-03"></span>

## OQ-03 — Kann die Referenz einen Trigger oder Zeitstempel bereitstellen?

* **Status:** offen · **Zuständig:** Labor
* **Blockiert:** Umfang von M6, nicht die Implementierung. `trigger_sequence`
  ist im Datensatz als `None`-fähiges Feld vorgesehen.
* **Günstigstes Experiment:** Handbuch der Kalibriermaschine prüfen, ob es
  einen Triggerausgang oder eine Netzwerk-Zeitquelle gibt. Etwa eine Stunde.
* **Antwort landet in:** [TIMING.md](TIMING.md)

<span id="oq-04"></span>

## OQ-04 — Welche Gerätetypen bilden den ersten freizugebenden Umfang?

* **Status:** teilweise geklärt (Technologie), Gerätezahl/-familie weiter offen
  · **Zuständig:** Labor
* **Blockiert:** Umfang des Datensatzes (P2) und die Abnahmekriterien (P7).
* **Vorabdefault:** mit GSV-2ASD und einem AST-Gerät beginnen; die Architektur
  bleibt anzeigetyp-agnostisch.
* **Günstigstes Experiment:** zwei Wochen Zählstrich am Prüfplatz — welche
  Geräte kommen tatsächlich am häufigsten?
* **Antwort landet in:** [ROADMAP.md](ROADMAP.md), `datasets/README.md`

* **Update 2026-09-21, Technologie vom Nutzer bestätigt:** Alle im
  Produktivbetrieb zu lesenden Anzeigen sind **LCD**
  (`layout.polarity = "dark_on_bright"`), nicht LED/VFD. Das betrifft die
  eigentlichen Messverstärker-Displays (GSV-/AST-Geräte), **nicht** den
  aktuellen Sammelmodus-Entwicklungsbestand: die beiden bisher registrierten
  Geräte "RND-Lab" und "BK Precision" (73 reale Proben, siehe
  [VALIDATION.md](VALIDATION.md) 2026-09-21) sind Laboraufbauten mit
  `technology=LED`, physisch aber teils VFD (BK-5491B, siehe OQ-23-Kopf) —
  keines davon ist LCD. Der bisherige reale Dataset-Benchmark-Lauf prüft
  damit die Pipeline-Mechanik korrekt, ist aber **nicht** repräsentativ für
  die tatsächliche Zielhardware. Konsequenz: Sobald ein LCD-Gerät verfügbar
  ist, gehört es vorrangig in den Sammelmodus aufgenommen - die
  LED/LCD-Vielfaltsvorgabe aus dem Exportziel
  (`docs/status.md`, „mindestens 6 verifizierte Geräte, 3 Familien, LED und
  LCD") ist jetzt weniger eine Vielfaltsvorgabe als eine **Zielhardware-
  Vorgabe**: LCD ist Pflicht, LED/VFD bleiben nur als zusätzliche
  Entwicklungsdaten wertvoll.

<span id="oq-05"></span>

## OQ-05 — Ist eine einmalige Bestätigung durch den Laboranten im Ablauf vorgesehen?

* **Status:** offen · **Zuständig:** Labor
* **Blockiert:** das Bedienkonzept, nicht die Kette. Der `manual_roi`-Pfad ist
  bereits der Primärpfad und setzt die Bestätigung voraus.
* **Vorabdefault:** Bestätigung ist vorgesehen (Konzept §4 „bevorzugter
  Betrieb"), Vollautomatik ist spätere Option.
* **Update 2026-09-10, Implementierungsentscheidung (keine Antwort auf diese
  OQ):** Bedienerwunsch: Die Workbench verlangt jetzt technisch **pro
  Sitzung** eine erneute Bestätigung statt einer dauerhaft ohne weiteren
  Blick gültigen einmaligen Bestätigung — `Controller.__init__` setzt
  `confirmed` einer geladenen Geometrie auf `false` (nur die Laufzeitkopie,
  die gespeicherte Profildatei bleibt unverändert; `roi`/`roi_quad`/`ocr_box`
  bleiben als Startpunkt erhalten), der `run`-Modus ist bis zur erneuten
  Bestätigung gesperrt, und die volle Kandidatensuche läuft auf dem Livebild
  wieder mit. Das ist eine Softwareentscheidung für den Editor-Workflow,
  **keine** Antwort auf die eigentliche, weiterhin offene Labor-/QM-Frage
  dieser OQ (ob eine einmalige Bestätigung je Geräteinstanz betrieblich
  vorgesehen ist) — dafür bräuchte es weiterhin die Antwort aus dem Labor.

<span id="oq-06"></span>

## OQ-06 — Wie werden ungültige Werte in GSVmulti und in der Kalibrierauswertung behandelt?

* **Status:** teilweise geklärt (2026-11-04) · **Zuständig:** ME-Systeme intern + QM
* **Blockiert:** die Freigabe von P4, zusammen mit OQ-01.
* **Vorabdefault:** `InvalidValuePolicy` als austauschbarer Adapterparameter
  mit den drei Varianten `omit_record`, `send_nan`, `status_flag`. Alle drei
  sind implementiert und getestet, die Wahl ist eine Konfiguration.
* **Antwort landet in:** [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md)
* **Ergänzung 2026-10-28:** UserDefined belegt den Zahlenimport, aber weder
  `NaN` noch leere Wertfelder als Ungültigmarkierung. Ein zusätzlicher
  numerischer Statuskanal macht einen anderen Kanal nicht automatisch
  ungültig. Auslassen oder Senderstopp allein belegt nicht, dass GSVmulti
  den letzten Wert rechtzeitig als veraltet kennzeichnet. Anzeige,
  Aufzeichnung und Kalibrierauswertung gemeinsam prüfen; ungültige Zeiträume
  dürfen keine Messfreigabe erhalten. [Prüffälle](GSVMULTI_PROTOCOL.md#ungultige-werte).

* **Testfreigabe mit Bestätigung seit 2026-11-09 (Nutzerentscheidung), keine
  Abnahme:** Echte Werte dürfen auch über die GSVmulti-Brücke (UART und
  Netzwerk) laufen, wenn der Pi-Bediener den Lauf mit
  `acknowledge_unaccepted: true` startet – wie bei UART direkt. Ungültige und
  veraltete Werte werden ausgelassen (`omit_record`, Brücke quittiert
  `omitted`); GSVmulti zeigt dann den letzten Wert unmarkiert weiter, genau so
  steht es im Hinweis. Diese Frage bleibt damit offen.
  [BRIDGE_PROTOCOL_V2.md](BRIDGE_PROTOCOL_V2.md#testfreigabe-echter-werte-seit-2026-11-09-additiv-v2-bleibt-v2)

* **Teilantwort 2026-11-04:** Lauf 08: 30,000983790 s absichtliche
  UART-Sendepause (HOST_MONOTONIC), Screenshot zeigt timeout! bei gestarteter
  Aufnahme; Fortsetzung auf neue −0,750 laut Nutzer ohne Eingriff. TXT/TDMS
  enthalten alle 500 gesendeten Zahlen, aber der nominelle 0,1-s-Modus
  verdichtet die Pause vollständig: weder Zeitlücke noch Ungültigmarkierung
  im Messkanal. Omit/Senderpause allein ist in dieser Konfiguration für
  Kalibrierdaten unzureichend. Timeout-Verzögerung, Altwertanzeige davor,
  explizite Ungültigmarkierung und NaN-Semantik weiter offen; reale DUT-Ausgabe
  bleibt gesperrt. [Antwort und Messbeleg](VALIDATION.md#uart-demo-20261104-08).

* **NaN-Teilbefund 2026-11-04:** Lauf 09 sendet 200 %NaN-Telegramme über
  demo-only SEND_NAN. TXT/TDMS enthalten nur die gültigen Zahlen, weder NaN
  noch einen anderen Fehlwertmarker. Screenshot zeigt Timeout, Nutzer meldet
  anschließendes Weiterlesen ohne Lücke. NaN genügt im getesteten Profil mit
  Zahlenfilter nicht; Ursache nicht auf Parser/Filter isoliert, kein genereller
  Ausschluss für alle Konfigurationen. Weiterer dokumentierter Empfängerweg:
  Replace Missing Values, noch unbewiesen (OQ-51).
  [Antwort und Messbeleg](VALIDATION.md#uart-demo-20261104-09).

* **Optionenvergleich 2026-11-04:** Auch mit ausdrücklich bestätigtem
  Replace Missing Values keine Ungültigmarkierung in TXT/TDMS (Lauf 10).
  OQ-51 teilweise geklärt; Ursache und geeignete UserDefined-Integration
  mit der GSVmulti-Entwicklung klären. Zahlenimport ist kein Nachweis der
  Kalibriertauglichkeit. [Beleg](VALIDATION.md#uart-demo-20261104-10).

* **Weiterer Vergleich vorbereitet 2026-11-04:** Nutzer schlägt Zahlenfilter
  aus vor. Gleiche NaN-Fixture wie Lauf 10, nur diese Option ändern. Filter-
  bedingtes Entfernen ist Hypothese; zuerst Empfang gültiger Zahlen prüfen,
  denn frühere Filter-aus-Versuche zeigten auch dafür Timeout. Noch kein
  Ergebnis oder neuer Senderlauf. [Vorbereitung](lab_journal.md).

* **Filter-aus-Ergebnis 2026-11-04:** Lauf 13 sendet dieselben 700 Payloads
  wie Lauf 10. Nutzer bestätigt durchgehenden Timeout, bereits bei gültigen
  Zahlen vor NaN. Keine erfolgreiche Aufzeichnung belegt. Daraus keine
  isolierte NaN-Aussage ableiten; aktuelle Filter-aus-UCF gegen erfolgreiche
  Filter-ein-UCF vergleichen. Binärpräfix 25 ist dasselbe %-Byte und nicht
  ohne Beleg ein anderer Parserweg. [Messbeleg](VALIDATION.md#uart-demo-20261104-13).

* **Konfigurationsvergleich 2026-11-04:** Gelieferte Filter-aus-UCF aus
  Lauf 13 steht auf 1 Hz und leerer Einheit; erfolgreiche UCF hatte 10 Hz
  und mV/V. Raw Separator 256→0, OpenFlags unverändert. Kein abgesicherter
  Ein-Variablen-Vergleich und kein bewiesener Timeout-Grund; Konfiguration
  vor Wiederholung abgleichen (OQ-53). [Beleg](VALIDATION.md#uart-demo-20261104-13).

* **Korrigierter Vergleich 2026-11-04:** Lauf 14 mit bestätigter10Hz/mV/V-
  UCF liefert laut Nutzer weiter durchgehend Timeout, schon für gültige
  Zahlen. Positive Gegenprobe mit bekannter funktionierender Filter-ein-UCF
  und identischem NaN-Stimulus vorbereitet. Keine NaN-Semantik aus dem
  allgemeinen Empfangsausfall ableiten. [Beleg](VALIDATION.md#uart-demo-20261104-14).

* **Positive Kontrolle 2026-11-04:** Nach erneutem Laden der bekannten
  Filter-ein-Session zeigt Lauf15 wieder gültige Zahlen und speichert440
  passende Werte mit mV/V/Scaling1/10Hz. Keine NaN-/Fehlwertmarker; NaN-
  Abschnitt auf nominelle0,1-s-Grenze verdichtet. Parserursache weiterhin
  offen. Dokumentierter Zeichenpräfix A bei Filter aus als gezielter
  Vergleich zu Lauf14 vorbereitet, noch nicht gesendet.
  [Beleg](VALIDATION.md#uart-demo-20261104-15).

---

<span id="oq-07"></span>

## OQ-07 — GSVmulti-Telegrammspezifikation beschaffen

* **Update 2026-11-04:** Nutzer bestätigt Windows 11 / GSVmulti 2.03,
  aktivierte PRO-Lizenz und verfügbares `UserDefined`. Software-Prototyp
  vorhanden; COM-Portpaar, Empfang, Ungültigbehandlung und Zeitachse sind
  weiterhin nicht abgenommen. [Aktueller Teststand](GSVMULTI_PROTOCOL.md#windows-bruecke).
* **Status:** teilweise geklärt (2026-10-28) · **Zuständig:** ME-Systeme intern
* **Neuer Befund:** Das bereitgestellte PDF
  [GSVmulti und Raspberry Pi](quellen/GSVmulti_Raspberry_Pi_Sensoranbindung.pdf)
  nennt den Weg `UserDefined`. Die verlinkte
  [Herstelleranleitung v2.6](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf#page=118)
  wurde am 2026-10-28 direkt geprüft; S. 118–121 belegen den Zahlenimport.
  Damit entfällt die reine Beschaffungssperre für einen Prototyp.
  Empfang in 2.01 Pro, Ungültigbehandlung und Zeitachse bleiben offen;
  keine Abnahme ist dadurch erfolgt.
  [Bewertung und nächste Schritte](GSVMULTI_PROTOCOL.md).
* **Prototyp gebaut (2026-10-28):** P4-1 `UserDefinedFormatter` und P4-2
  Demo-Sender sind mit pty/Fakes geprüft, ungeprüft am Windows-PC und nicht
  freigegeben. Empfang, Ungültigwirkung und Zeitachse bleiben offen;
  [Testanleitung](GSVMULTI_PROTOCOL.md#windows-test).
* **Live-Prototyp gebaut (2026-10-30):** P4-3 ergänzt Opt-in-Ausgabe nach
  allen Sperren, begrenzten Senderthread und Tx-Audit; pty/Fakes geprüft,
  Windows-Abnahme weiterhin offen. Öffnungsfehler lehnt Start ab, spätere
  Fehler sind im Status sichtbar; keine Messfreigabe.
* **Korrektur der Abrufaussage (2026-09-22):** Die bisherige Formulierung
  „`me-systeme.de` blockt automatische Abrufe mit HTTP 403" ist **zu pauschal**.
  Gemessen am 2026-09-22:
  * **PDF-Anleitungen unter `/produkte/.../anleitungen/` liefern HTTP 200.**
    Heruntergeladen und lokal abgelegt sind jetzt
    `var/datenblaetter/gsv2-bedienungsanleitung.pdf` (GSV-2, enthält das
    RS232-Protokoll des **Geräts**) und `var/datenblaetter/ba-gsvmulti.pdf`
    (GSVmulti-Bedienungsanleitung, Stand 13.08.2011, 10 Seiten). **`var/` ist
    gitignored** — beide Dateien sind lokal, nicht im Repo; dauerhaft sind nur
    die oben genannten URLs.
  * **HTML-Produktseiten liefern weiterhin HTTP 403** (geprüft an
    `https://www.me-systeme.de/en/gsv-2as-05`).
* **Historischer Befund vom 2026-09-22:** Das damals beschaffte GSVmulti-Handbuch von
  2011 ist eine **Bedienungsanleitung der Oberfläche** (Kanal hinzufügen,
  Skalierung, Speichern), **keine Telegrammspezifikation**. Gesucht ist laut
  Konzept §12 ausserdem die Version 2.6, nicht die von 2011. Die
  GSV-2-Anleitung dokumentiert das Protokoll des **Messverstärkers** — was
  GSVmulti als Eingang **akzeptiert**, ist damit nicht belegt, sondern nur
  plausibel. Es wird nichts geraten ([AGENTS.md](../AGENTS.md), „Kein Erfinden
  von Protokollen").
* **Für eine native Geräteemulation weiterhin geeigneter Nachweis:** ein
  vorhandenes GSV-2/GSV-3 im ASCII-Modus an GSVmulti hängen und den realen
  Datenstrom aufzeichnen. Das liefert das tatsächliche Telegramm. **Neu
  verfügbar dafür:** das Laborgerät ist als **GSV-2AS** identifiziert
  ([OQ-38](open-questions.md)) und beherrscht laut Anleitung genau diesen
  ASCII-Modus — das für dieses Experiment nötige Gerät ist also vorhanden.
* **Antwort landet in:** [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md),
  UserDefined als neuer `TelegramFormatter`; `gsv_ascii.py` bleibt der
  absichtlich werfende Platzhalter. Kein Nachbau eines GSV-Geräts für den
  UserDefined-Einstieg erforderlich.

<span id="oq-08"></span>

## OQ-08 — An welchem CAM-Anschluss hängt die Kamera?

* **Status:** geklärt (2026-09-07)
* **Antwort:** CAM/DISP0. Der Sensorknoten erscheint als
  `/axi/pcie@1000120000/rp1/i2c@88000/imx500@1a`, die CAM-I2C-Busse sind 6
  und 10. Erkannt über `camera_auto_detect=1`, ohne explizites Overlay.
* **Gelandet in:** [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)

<span id="oq-09"></span>

## OQ-09 — RS-232-/RS-485-Transceiver und galvanische Trennung

* **Status:** offen · **Zuständig:** Hardware / Beschaffung
* **Historischer Befund vom 2026-09-07:** Kein USB-Seriell-Adapter angeschlossen. Verfügbar waren nur
  `/dev/ttyAMA0` (Datenport, durch `dtparam=uart0=on` aktiv) und
  `/dev/ttyAMA10` alias `/dev/serial0` — letzteres ist der **3-Pin-Debug-Header**
  und nicht der Nutzdatenport.
* **Dokumentabgleich 2026-10-28:** Seit 2026-09-22 ist ein PL2303 an
  `/dev/ttyUSB0` für die eingehende GSV-2AS-Referenz dokumentiert, nicht
  für den GSVmulti-Ausgang. Ein Windows-USB-UART mit 3,3-V-TTL wäre eine
  andere Ausgangsvariante als RS-232/RS-485; Raw TCP benötigt keinen
  GPIO-Transceiver. Die tatsächliche Wahl ist noch offen
  ([Transportvergleich](GSVMULTI_PROTOCOL.md#transport),
  [Hardwareprofil](HARDWARE_PROFILE.md)). Kein neuer Hardwaretest.
* **Konzept §8:** Pi-GPIO-Pegel dürfen **nicht** direkt mit RS-232 verbunden
  werden. Galvanische Trennung ist für den Laboraufbau zu bewerten.
* **Blockiert:** die elektrische Strecke, nicht die Software. Getestet wird bis
  dahin gegen pty.
* **Antwort landet in:** [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)

<span id="oq-10"></span>

## OQ-10 — Spezialisierte 7-Segment-Traineddata für Tesseract

* **Status:** offen
* **Befund:** Debian liefert nur prosa-trainierte Traineddata (`eng`).
  Spezialisierte Sätze wie `ssd` oder `letsgodigital` sind **nicht** in Debian.
  Download müsste off-Pi erfolgen, mit Lizenzprüfung.
* **Relevanz:** gering, solange der klassische Segment-Dekoder trägt. Tesseract
  ist die Vergleichsbasis, nicht der Primärpfad.

<span id="oq-11"></span>

## OQ-11 — Workstation für die IMX500-Modellkonvertierung

* **Status:** offen
* **Befund:** Auf dem Pi ist nur der *Packager* vorhanden (`imx500-package`,
  `fpk2rpk`, `PostConverter.jar` unter `/usr/lib/imx500-tools/`). Der
  *Converter* und `model_compression_toolkit` fehlen; `torch`/`tensorflow`/`onnx`
  sind bewusst nicht installiert.
* **Konsequenz:** Training, Quantisierung und Konvertierung laufen off-Pi. Auf
  dem Pi bleibt nur Paketierung und Deployment.
* **Relevanz:** erst für P8 (optional).

<span id="oq-12"></span>

## OQ-12 — Was ohne angeschlossene Kamera nicht verifizierbar war

* **Status:** geklärt (2026-09-07) — durch die Inbetriebnahme abgearbeitet.
* **Ergebnisse:** siehe [TIMING.md](TIMING.md). Insbesondere: `.rpk`-Warmlauf
  6,8 s, 15,0 Inferenzen/s, `SensorTimestamp` in CLOCK_BOOTTIME,
  `CnnInputTensor` **fehlt** in den Standardmetadaten, Stock-Modelle liefern
  COCO-Labels.

<span id="oq-13"></span>

## OQ-13 — Anzeigepolarität und der Fall „alle Stellen zeigen 8"

* **Status:** offen
* **Befund:** Der Segment-Dekoder schwellt über die gepoolten Segmentmessungen
  aller Stellen. Zwei bekannte Grenzen:
  1. Zeigt die Anzeige ausschließlich `8`, gibt es keine inaktive Klasse, der
     Kontrast ist klein und der Ausschnitt wird **abgelehnt**. Eine
     Falschablehnung ist nach Konzept §7 die zulässige Richtung — geraten wird
     nicht —, aber es ist eine Einschränkung.
  2. Vorausgesetzt ist helle Anzeige auf dunklem Grund (LED). Für LCD mit
     umgekehrter Polarität fehlt die Behandlung. — **geklärt (2026-09-18)**,
     siehe Update unten. Fall 1 bleibt offen.
* **Lösungsansatz:** Polarität ins Geräteprofil aufnehmen; als
  Off-Referenz zusätzlich eine Panelfläche außerhalb der Segmente abtasten.

* **Update 2026-09-18, Fall 2 (Polarität):** `DisplayLayout` hat jetzt ein
  Feld `polarity: "bright_on_dark" | "dark_on_bright"` (Default
  `bright_on_dark`, reproduziert das bisherige Verhalten unveränderten
  gespeicherten Profilen gegenüber). `SevenSegmentReader.read` invertiert das
  Graustufenbild einmalig am Anfang, wenn `polarity == "dark_on_bright"`
  (`src/dispread/ocr/sevenseg.py`) — danach gilt im ganzen Leser wieder
  "hell = an", keine zweite Fallunterscheidung. `profiles.validate_layout`
  lehnt unbekannte Polaritätswerte ab. Die Workbench hat dazu eine
  Auswahlzeile `layout.polarity` (`src/dispread/workbench/fields.py`).
  Getestet in `tests/test_sevenseg.py`
  (`test_lcd_polaritaet_wird_gelesen`,
  `test_falsche_polaritaet_wird_abgelehnt_nicht_falsch_gelesen`,
  `test_unbekannte_polaritaet_wird_abgelehnt`): eine falsch eingestellte
  Polarität lehnt ab, sie liest nicht stillschweigend falsch. Fall 1 (Anzeige
  zeigt ausschließlich "8", keine inaktive Klasse vorhanden) ist davon
  unberührt und bleibt offen.

<span id="oq-14"></span>

## OQ-14 — Freigabeschwellen an realen Geräten validieren

* **Status:** offen
* **Befund:** Alle Schwellen in `GateConfig` sind Vorabdefaults, keine
  validierten Grenzen. Konzept §7 verlangt ausdrücklich, sie an realen, auch
  bisher unbekannten Gerätetypen zu validieren.
* **Blockiert:** die Abnahme. Aufgabe von P3/P7.
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md)

<span id="oq-15"></span>

## OQ-15 — `tesseract-ocr`, `socat` und `chrony` installieren

* **Status:** geklärt (2026-09-21)
* **Befund:** Seit dem Reboot am 2026-09-07 verlangt `sudo` ein Passwort, die
  Installation konnte nicht automatisch erfolgen. Benötigt:
  `sudo apt install -y tesseract-ocr tesseract-ocr-eng socat chrony`
* **Wirkung:** Ohne `tesseract` fehlt die OCR-Vergleichsbasis, ohne `chrony`
  ist Messung M1 (Offset und Drift) nicht protokollierbar. `socat` ist nur
  Komfort — die Tests nutzen `os.openpty()` aus der stdlib.
* **Antwort landet in:** [dependencies.md](dependencies.md)
* **Antwort (2026-09-21):** Alle drei sind auf dem Lab-Pi installiert
  (`tesseract 5.5.0`, `socat`, `chrony 4.6.1-3`) - per `which`/`dpkg -l`
  geprueft. Der Eintrag war nur nicht aktualisiert; kein offener Blocker
  mehr. `dispread.ocr.tesseract_cli` ist geschrieben und ruft die
  tesseract-Binary auf (siehe CHANGELOG 2026-09-21) — ein produktiver,
  erfolgreicher Read gegen echte GSV-Sensor-Fotos steht noch aus (0/11
  Proben liefern bisher einen Wert, siehe docs/status.md).

<span id="oq-16"></span>

## OQ-16 — Vollständigkeit des lokalen Planungsstands

* **Status:** geklärt (2026-09-10)
* **Befund:** Unter anderem `ROADMAP.md`, `dependencies.md`,
  `HARDWARE_PROFILE.md` und `lab_journal.md` werden referenziert, fehlen aber
  im aktuellen Arbeitsbaum unter `docs/`. Auch mehrere im Status genannte
  CLI-/Replay-Komponenten sind lokal nicht vorhanden. Frühere Messangaben
  werden deshalb als dokumentierte Ergebnisse, nicht als neu verifiziert behandelt.
* **Klärung:** Fehlende Dateien wiederherstellen oder Verweise und Meilensteine
  mit dem tatsächlich vorhandenen Stand abgleichen.
* **Antwort (2026-09-10):** `docs/ROADMAP.md`, `docs/dependencies.md`,
  `docs/HARDWARE_PROFILE.md` und `docs/lab_journal.md` liegen inzwischen alle
  mit Inhalt im Arbeitsbaum vor (per `ls docs/` geprüft). Die im Status
  genannte CLI-Komponente existiert: `src/dispread/workbench/cli.py` hat ein
  funktionierendes `stop`-Subkommando (bildet `dispread stop` aus
  `docs/status.md` ab). Die Replay-Komponente ist weiterhin nur ein
  Registry-Eintrag ohne Implementierung (`src/dispread/frames/__init__.py`
  registriert `replay`, es gibt kein `replay_source.py`) — das deckt sich mit
  `CLAUDE.md`, wo `replay://` ausdrücklich als "nur Registry-Eintrag, TODO"
  geführt wird, war also keine Doku-Abweichung.
* **Antwort landet in:** `docs/status.md` und den betroffenen Dokumenten.

<span id="oq-17"></span>

## OQ-17 — Sichtbarer Dezimalpunkt und Profilannahme unterscheiden

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** `SevenSegmentReader.read` setzt `decimal_point_detected` anhand
  des Profils; der Punkt wird nicht im Bild gemessen. Die Einheit kommt
  ebenfalls aus dem Profil, dort bereits mit `unit_source=profile` markiert.
* **Klärung:** Welche Geräte können Punkt, Einheit oder Messbereich während
  eines Laufs wechseln? Bildprüfung und explizite Herkunft der Punktposition
  vorsehen; Profilannahmen dürfen keine optische Erkennung vortäuschen.
* **Antwort landet in:** `docs/tool_review_2026-09-08.md`, später Leser,
  Profile und `docs/VALIDATION.md`.

* **Update 2026-09-21, empirischer Datenpunkt aus dem Sammelmodus
  (`docs/PLAN_2026-09-21-dataset-benchmark.md`):** Die BK-Precision-Situation
  `26692830cde04118b69f5b2c60c40335` mischt innerhalb **einer** Sitzung zwei
  Punktpositionen bei gleicher Ziffernzahl: Werte wie `012.38` (2
  Nachkommastellen) stehen neben `-0.0009`/`-0.0010` (4 Nachkommastellen) -
  das Gerät hat den Messbereich mitten in der Aufnahmesitzung gewechselt.
  Das ist die konkrete Antwort auf die obige Frage „welche Geräte können
  Punkt/Messbereich während eines Laufs wechseln": mindestens das
  BK-5491B tut es, beobachtet, nicht nur befürchtet. Für den Dataset-
  Benchmark (Task 3, `target_layout`) folgt daraus: Nachkommastellen dürfen
  **nie** über eine ganze Faltung eingefroren werden, sondern müssen je
  Zielprobe aus deren eigenem `expected_text` kommen - ein eingefrorenes
  `decimals` hätte hier garantiert die Fehlerklasse `decimal` erzeugt, nicht
  von der Optik verursacht, sondern vom Prüfstand selbst fabriziert.

<span id="oq-18"></span>

## OQ-18 — Welches neuronale OCR-Modell trägt auf realen Displays?

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** ONNX Runtime bietet inzwischen Linux-ARM64-Wheels für CPython
  3.13. Das belegt noch keine Verträglichkeit mit der konkreten System-NumPy-
  Installation und keine Erkennungsqualität oder Laufzeit auf diesem Pi.
* **Klärung:** PP-OCRv5 mobile und PP-OCRv6 tiny/small gegen Tesseract und den
  Segmentleser auf denselben realen Aufnahmen prüfen; Modell, Zeichensatz,
  Vorverarbeitung, Runtime, Lizenz und Prüfsummen festhalten. Keine automatische
  Installation von PyPI-NumPy/OpenCV in die Projekt-venv.
* **Antwort landet in:** `docs/tool_review_2026-09-08.md`, später
  `docs/dependencies.md` und `docs/VALIDATION.md`.

<span id="oq-19"></span>

## OQ-19 — Freigabeevidenz für weitere OCR-Backends

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** `ReleaseGate.evaluate` verlangt `contrast` und `min_margin`
  aus der Segmentanalyse. Ein neuer OCR-Leser ohne diese Diagnosen wird
  abgelehnt. Ein neuronaler Score ist kein Ersatz für einen Segmentabstand.
* **Update 2026-10-21:** Der ursprüngliche Befund beschreibt den
  7-Segment-Pfad. `default_gate_config("dotmatrix")` lässt den
  Dot-Matrix-Leser seine eingefrorenen Vorlagenschwellen selbst anwenden;
  Kontrast und Abstand stammen aus dessen Diagnosen. Dieser Backend-Pfad
  ist gebaut und durch die begrenzte Leser-Abnahme vom 2026-09-30 belegt.
  Beliebige weitere beziehungsweise neuronale Backends sind dadurch
  nicht freigegeben. Konfidenz bleibt eine Qualitätskennzahl ohne
  kalibrierte Fehlerwahrscheinlichkeit.
* **Klärung:** Gemeinsame optische Qualitätsprüfung und je Backend validierte
  Evidenzregeln definieren, ohne fehlende Diagnosen mit erfundenen Werten zu füllen.
* **Antwort landet in:** `docs/tool_review_2026-09-08.md`, später
  Freigabelogik und `docs/VALIDATION.md`.

<span id="oq-20"></span>

## OQ-20 — Auto-Setup gegen Multiplexing echter Anzeigen absichern

* **Status:** offen · erkannt 2026-09-08 beim Workbench-Ausbau
* **Befund:** Die neue begrenzte Belichtungs-/Gain-Suche bewertet Kontrast,
  Überstrahlung und zeitliche Helligkeitsschwankungen im bestätigten Bereich.
  Diese Kriterien beweisen nicht, dass alle multiplexenden Segmente vollständig
  aufgenommen wurden; eine stabile Phasenlage kann fehlende Segmente verbergen.
* **Klärung:** Je realem Gerät geeignete Belichtungsbereiche und Multiplexperiode
  messen; automatische Vorschläge mit optisch bestätigten vollständigen Anzeigen
  vergleichen. Bis dahin bleibt Auto-Setup eine Einstellhilfe mit menschlicher
  Bestätigung, keine automatische Freigabe.
* **Antwort landet in:** `docs/OPTICAL_SETUP.md`, Geräteprofile und
  `docs/VALIDATION.md`; Aufbau in `docs/lab_journal.md`.

<span id="oq-21"></span>

## OQ-21 — HTTPS-Browserabnahme der Workbench

* **Status:** offen · erkannt 2026-09-08 beim Workbench-Ausbau
* **Befund:** Der lokale Chromium-152-Headless-Test lädt HTTPS-Seiten trotz
  erfolgreicher TLS-Handshakes auf Serverseite nicht fertig; Navigation und
  anschließende CDP-Auswertung laufen in Timeouts. Direkte Python-/curl-
  HTTPS-Abfragen laden die Loginseite vollständig. Die konkrete Ursache in
  dieser Browserumgebung ist nicht geklärt.
* **Eingegrenzt am 2026-09-08:** Es ist kein TLS- und kein Zertifikatsproblem.
  Dasselbe Chromium lädt auch eine reine HTTP-Seite eines lokalen
  `python -m http.server` nicht (leerer Body, `net_error -101`, „Page load timed
  out"), während `file://`-Seiten samt JavaScript einwandfrei laufen. Zusätzlich
  feuern Timer im Headless-Modus nur mit `--virtual-time-budget`, nicht mit
  `--timeout`. Browserprüfungen dieser Umgebung laufen deshalb über eine
  `file://`-Seite mit eingespielter echter `/status`-Antwort; das prüft das
  Frontend, aber weder TLS noch Anmeldung noch WebSocket.
* **Klärung:** Mit vertrautem Zertifikat im Windows-Browser anmelden und
  Kamera, echte Shell, TUI sowie Wiederverbindung gemeinsam abnehmen. Falls
  reproduzierbar: Browser-/TLS-Netzwerkdiagnose ergänzen. Keine Sicherheits-
  umgehung oder passwortfreie Produktionsanmeldung als Ersatz einbauen.
* **Antwort landet in:** `docs/anleitung/10-kamera-livevorschau.md`,
  `docs/status.md`; technische Befunde gegebenenfalls `docs/lab_journal.md`.

<span id="oq-22"></span>

## OQ-22 — Sensor setzt nach Streamwechsel keinen Stream mehr auf

* **Status:** offen, für den Betrieb gegenstandslos (IMX500 außer Betrieb seit 2026-09-25) · erkannt 2026-09-08 bei der Fokusdiagnose
* **Befund:** Nach einer Messreihe, die im selben Prozess erst 960×720 und dann
  2028×1520 streamte (`configure` → `start` → `stop` → `configure` → `start`),
  liefert der Sensor **überhaupt keine Bilder mehr**. Jeder weitere Startversuch
  — auch aus einem frischen Prozess und auch mit `rpicam-still` — endet im
  Kernel mit `rp1-cfe 1f00110000.csi: stream on failed in subdev`, begleitet von
  `WARNING ... call_s_stream+0x100/0x118 [videodev]` und
  `videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0 in
  active state`. 8.429 solche Zeilen zwischen 15:20:32 und 15:22:12 Ortszeit.
  Enumeration bleibt intakt: `global_camera_info()` und
  `scripts/camera-commissioning.sh` melden weiter „einsatzbereit" — die
  Diagnose prüft den Bilddurchlauf also **nicht**. Letzte erfolgreiche Aufnahme
  vor dem Reboot 15:14, erster Fehlschlag 15:20:32.
* **Zwischenstand 1 (verworfen): PipeWire/WirePlumber.** Beide hielten
  `/dev/v4l-subdev2`, den imx500-Sensorknoten, und WirePlumber 0.5.8 hatte den
  libcamera-Monitor aktiv — zwei libcamera-Klienten am selben Sensor. Der
  Monitor wurde benutzerseitig abgeschaltet
  (`~/.config/wireplumber/wireplumber.conf.d/50-kein-kameramonitor.conf`,
  `monitor.libcamera = disabled`); danach hält PipeWire den Sensorknoten
  nachweislich **nicht** mehr. **Der Fehler tritt trotzdem weiter auf.** Damit
  ist Kamerakonkurrenz als Ursache widerlegt. Die Abschaltung darf bleiben, sie
  entfernt einen Störfaktor.
* **Zwischenstand 2 (verworfen): hängender Prozess.** Ein beendeter
  Fokusmesser-Lauf blieb nach Strg+C 1:57 min als PID 4681 in
  `futex_wait_queue` stehen und hielt den Sensor. Das ist aber **Folge, nicht
  Ursache**: `Picamera2.stop()` wartet auf Puffer, die der Treiber nie
  zurückgibt. Den Prozess zu töten gibt die Kamera **nicht** frei — der
  anschließende Startversuch scheiterte weiter, und der Kill selbst löste
  erneut `cfe_stop_streaming ... leaving buffer 0 in active state` aus.
* **Stand: es ist ein Treiberfehler, und der Kernel sagt es selbst.**
  `videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0
  in active state`, aufgerufen aus `cfe_stop_streaming+0xd4/0x200 [rp1_cfe]`.
  Jeder Streamabbau — sauber beendet oder per Signal — kann die vb2-Warteschlange
  in diesem Zustand hinterlassen. Danach scheitert jeder weitere Start, in zwei
  Varianten: `stream on failed in subdev` oder
  `/dev/video4[15:cap]: Failed to queue buffer N: Invalid argument`. Zuletzt
  hängt sogar `Picamera2(0)` beim Öffnen. **Nur ein Reboot hilft**; ein
  Modul-Reload wäre die Alternative und verlangt `sudo`.
* **Beste offene Hypothese: die Streamgröße entscheidet.** Sechs Datenpunkte,
  lückenlos konsistent:

  | Zeit | Sitzung | Modus | Ergebnis |
  | --- | --- | --- | --- |
  | 10:31 | Vorschaubeispiel | 960×720 | lief, Folge-Sitzungen weiter möglich |
  | 12:03 | Workbench-Kameradienst | 960×720 | lief, Folge-Sitzungen weiter möglich |
  | 14:03 | Kamera-Smoke-Test | 960×720 | lief, Folge-Sitzungen weiter möglich |
  | 15:14 | Fokusdiagnose | 960×720, dann **2028×1520** | lief; **danach alles blockiert** (15:20:32) |
  | 15:31 | `rpicam-still` | **4056×3040** | lief; **10 s später blockiert** |
  | 15:47 | Fokusmesser | **2028×1520** | lief (Bestwert 75); **danach blockiert** |

  Drei Sitzungen bei 960×720 hintereinander überlebten den Abbau, jede Sitzung
  mit einem der großen Sensormodi war die letzte des Boots.
* **Siebter Datenpunkt, 2026-09-22 — die Regel wurde verletzt und der Fehler
  trat sofort wieder auf.** Nach einem Reboot (Kamera wurde erst danach
  überhaupt wieder enumeriert) startete `scripts/sync-record.py` mit seiner
  damaligen Vorgabe **2028×1520**. Ergebnis: kein einziges Bild, der Prozess
  hing in `capture_request`, wurde per Signal beendet — und ab da setzte der
  Sensor keinen Stream mehr auf. `rpicam-hello -t 3000` erzeugte danach
  **33 × `stream on failed in subdev` in 0,11 s**, mit
  `cfe_stop_streaming+0xd4/0x200 [rp1_cfe]` im Aufrufpfad. Enumeration blieb
  wie gehabt intakt (`rpicam-hello --list-cameras` meldet den Sensor
  vollständig) — die Diagnose prüft den Bilddurchlauf eben nicht.

  Der Datenpunkt fügt der Tabelle nichts Neues hinzu, er **bestätigt sie**:
  grosser Sensormodus → letzte Sitzung des Boots. Bemerkenswert ist nur, dass
  ein neu gebautes Werkzeug die dokumentierte Betriebsgrösse nicht übernommen
  hatte.

  **Konsequenz, umgesetzt:** `scripts/sync-record.py` hat jetzt die Vorgabe
  **960×720** und **weist grosse Sensormodi hart ab** (`--camera-size` über
  1 MPixel → Abbruch mit Verweis auf diesen Eintrag), aufhebbar nur über ein
  ausdrückliches `--allow-large-sensor-mode`. Eine Warnung auf stderr wäre zu
  wenig gewesen: die Folge ist ein Reboot des Labor-Pi.
* **Hypothese am 2026-09-08 abgeschwächt:** In der nächsten Runde liefen bei
  960×720 **mehrere** Sitzungen hintereinander (Fokussieren in mehreren Läufen,
  Bestwert 216,6), dann trat derselbe Fehler wieder auf. Die Streamgröße ist
  also nicht der Schalter, sondern höchstens ein Einflussfaktor: 960×720
  verzögert das Problem, hebt es nicht auf. Es bleibt ein Wettlauf beim
  Streamabbau, der nicht bei jedem Abbau zuschlägt. Damit ist keine
  Konfiguration bekannt, die dauerhaft sicher ist.
* **Konsequenz für die Bildkette, unabhängig von der Ursache:** Der Messbetrieb
  bleibt bei 960×720. Ziffernhöhe wird, falls nötig, über **`ScalerCrop`** geholt
  — digitaler Ausschnitt auf die Anzeige bei gleichbleibender Ausgabegröße; der
  Sensormodus ist ohnehin in beiden Fällen 2028×1520. Am 2026-09-08 gemessen
  wurde das nicht gebraucht: 960×720 erreichte am Testgerät 37 px Ziffernhöhe
  ([VALIDATION.md](VALIDATION.md)).
* **Was die Workbench tun muss, solange der Treiber so ist:** (a) den Stream
  nicht ohne Not neu aufsetzen, (b) beim Beenden nach begrenzter Wartezeit hart
  aussteigen, damit ein hängendes `Picamera2.stop()` das Gerät nicht zusätzlich
  belegt, (c) den blockierten Sensor als solchen melden („Reboot nötig") statt
  als anonymen Timeout, (d) `scripts/camera-commissioning.sh` um eine echte
  Aufnahmeprüfung ergänzen, damit „einsatzbereit" Bilddurchlauf bedeutet.
  **Erneut aufgetreten 2026-09-23, 12:15:23:** 6 × `stream on failed in
  subdev`, dazu um 12:16:15 ein WARN-Trace in `cfe_stop_streaming`. Der Lauf
  war 960×720 mit `ScalerCrop` `1730,966,806,604`. Davor liefen im selben
  Boot mehr als 20 Aufnahmen sauber, auch mit `ScalerCrop`. Vorausgegangen
  war das Drehen am Fokusring. **Wahrscheinlichere Ursache, vom Nutzer
  vermutet und am Kernel-Log bestätigt:** In diesem Boot liefen **20
  erfolgreiche Streamstarts** (`Using a link rate`, 09:54 bis 12:10), der
  **21.** ist gescheitert. Direkt davor steht `imx500_power_on: failed to get
  led gpio`. Das passt zur Grenze vom 2026-09-09 (nach grob 20–25
  Power-Zyklen ist der RP2040 unerreichbar). Der Fokusring als Ursache ist
  damit unwahrscheinlich. **Folge:** Die Streamstarts brauchen ein Budget je
  Boot, und die Werkzeuge müssen mit wenigen, langen Kamerasitzungen
  auskommen. `sync-record.py` meldete den Lauf mit 0 Bildern als vollständig.
  Das ist ein Bug und wird behoben.
  **(d) erledigt 2026-09-23:** Das Skript prüft das Kernel-Log auf
  `stream on failed` und macht eine gebundene Testaufnahme (640×480). Bei
  belegtem Gerät weicht es aus, statt zu kollidieren. Gegen die Hardware
  bestanden.
  **Erneut aufgetreten 2026-09-23, 15:57:10, direkt nach Reboot und
  Commissioning:** Bootzeit 14:24:31; die erste Commissioning-Sitzung um
  15:55 lieferte ein echtes 640×480-Bild. Die unmittelbar folgende
  960×720-Fokussitzung lieferte dagegen 0 Bilder und sofort
  `imx500_power_on: failed to get led gpio` sowie 6 × `stream on failed in
  subdev`. Der Nutzer hatte den Fokusring noch nicht berührt. Zwei
  `Using a link rate`-Zeilen stehen bei der erfolgreichen Sitzung; ob diese
  intern mehr als einen Power-Zyklus verbrauchte oder der Warmstart den
  RP2040 nicht zuverlässig zurücksetzte, ist offen. **Folge:** Das Budget 15
  bleibt eine Sperre gegen bekannte Erschöpfung, darf aber nicht als Zusage
  von 15 erfolgreichen Starts verstanden werden. Diagnose:
  `var/diagnostics/focus-handoff-2026-09-23/` (nicht versioniert), Zahlen in
  `VALIDATION.md`, Aufbau im Laborjournal.
  **Nachtrag 2026-09-23, 16:17:35:** Nach einem weiteren verifizierten
  Warmreboot (Boot-ID `6c6abda2-d316-40da-b557-1124431ade30`) scheiterte
  sogar der **erste** 960×720-Streamstart dieses Boots, ohne vorherige
  Commissioning-Sitzung. Vor dem LED- und CFE-Fehler meldete die
  `rp2040-gpio-bridge` selbst `rp2040_gbdg_wait_until_free failed` und
  `rp2040_gbdg_gpio_dir_out(19, 0) could not ST_CL`. Das
  Streamstart-Budget erklärt den neuen Fehlschlag nicht. Ob ein
  vollständiger Stromzyklus des Pi die Bridge wiederherstellt, bleibt
  offen; wegen anderer Dienste wurde er nicht durchgeführt.
* **Warum das wichtig ist:** Der Kamerathread der Workbench setzt den Stream bei
  jeder Änderung von Breite, Höhe oder Bildrate genau so neu auf
  (`Controller._worker`). Trifft das denselben Treiberzustand, fällt die Kamera
  mitten im Betrieb aus und ist ohne Reboot nicht zurückzuholen. Im Labor wäre
  das ein Ausfall während einer Kalibrierung.
* **Klärung:** (1) Den Größentest oben fahren. (2) Unabhängig davon gehört der
  Befund upstream gemeldet — der Kernel bezeichnet ihn selbst als `driver bug`,
  mit Aufrufpfad `cfe_stop_streaming` im `rp1_cfe`-Treiber, libcamera
  v0.7.2+rpt20260817, libpisp v1.7.0. (3) Solange es unklar ist:
  Auflösung und Bildrate nur bei stehender Kamera ändern, nicht im laufenden
  Messbetrieb — und die Auflösungszeile im setup-Tab entsprechend
  kennzeichnen. (4) `camera-commissioning.sh` um eine echte Aufnahmeprüfung
  ergänzen, damit „einsatzbereit" auch Bilddurchlauf bedeutet.
* **Nicht tun:** Den Fehlschlag im Kamerathread stillschweigend wegfangen und
  weiterlaufen. Ein Sensor, der keinen Stream aufsetzt, ist ein harter Ausfall
  und muss als Fehler sichtbar bleiben.

* **Update 2026-09-09, Nachmittag — korrigiert: nicht RP1/x1201-Kontention,
  sondern der Onboard-RP2040 der AI-Camera hängt sich nach genau
  reproduzierbar ~24 Power-Zyklen auf.** Mit einem minimalen Reproducer ohne
  `dispread` (`Picamera2().configure().start().capture_array().stop().close()`
  im Loop, alle 12 s) liefen **24 Zyklen sauber durch** (uptime 0 bis 442 s,
  über drei Minutengrenzen hinweg), dann scheiterte Zyklus 25 (uptime 472 s)
  und blieb ab da dauerhaft gesperrt. Im Kernel-Log genau zu diesem Zeitpunkt:
  `rp2040-gpio-bridge 10-0040: rp2040_gbdg_i2c_send() rp2040_gbdg_wait_until_free
  failed`, `rp2040_gbdg_gpio_dir_out(19, 0) could not ST_CL`, danach erst
  `imx500 10-001a: setup of GPIO led failed: -121` und `stream on failed in
  subdev`. Das ordnet die Vormittags-Spur ein: `led-gpios`/`reset-gpios`
  hängen nicht an RP1, sondern an einem **eigenen RP2040-Mikrocontroller auf
  dem AI-Camera-Modul selbst**, der Reset/LED/Power-Sequencing über I2C-Bus 10
  (Adresse 0x40) steuert (`rp2040-gpio-bridge`, Modul
  `spi_rp2040_gpio_bridge`). Die Kontentionshypothese mit
  `x1201-monitor`/`/dev/gpiochip0` (RP1) ist damit hinfällig — die Timer waren
  während des gesamten Tests aktiv und liefen erkennbar unabhängig vom
  Wedge-Zeitpunkt (Ticks um :00/:20, Wedge um :48). Stattdessen: der
  RP2040 selbst wird nach genügend Power-Sequencing-Zyklen für den
  I2C-Bridge-Verkehr unerreichbar — ob Firmware-Bug im RP2040, ein
  I2C-Timing-Grenzfall bei schneller Wiederholung oder ein Ressourcenleck,
  ist offen und braucht das RP2040-Firmware-Log (nicht zugänglich) oder einen
  I2C-Bus-Trace. **Das bestätigt und quantifiziert die viel ältere Vermutung
  aus diesem Dokument** („Streamabbau bleibt der Verdächtige, ein Wettlauf,
  der nicht bei jedem Abbau zuschlägt") — nur dass der Auslöser nicht die
  Streamgröße ist, sondern die **Anzahl** der Power-Zyklen, grob 20–25.
  Praktisch bedeutet das: Der Workbench-Kamerathread (`Controller._worker`),
  der bei jeder Auflösungs-/Bildraten-Änderung neu konfiguriert, nähert sich
  diesem Limit mit jeder Einstelländerung im laufenden Betrieb — nicht nur bei
  großen Sensormodi. Ein frischer Reboot setzt den RP2040 zuverlässig zurück
  (dieser Test lief direkt nach einem verifiziert echten Reboot und begann
  sauber); ob auch ein Modul-Reload ohne Reboot reicht, ist nicht getestet.

* **Update 2026-09-09 vormittags (überholt, siehe oben) — Reboot allein hat
  diesmal nicht geholfen; erste Spur GPIO-Kontention über RP1.** Nach einem verifiziert echten, frischen Reboot
  (Kernel-Meldung „Booting Linux on physical CPU”, `btime`/`uptime` bestätigt —
  `who -b`/`journalctl --list-boots` zeigten wegen fehlender batteriegepufferter
  RTC und nachträglichem `chronyd`-Zeitsprung fälschlich noch den alten
  Boot-Zeitpunkt) scheiterte der **erste** Streamversuch bereits sechs Minuten
  nach dem Hochfahren, mit zusätzlichem, bisher nie beobachtetem Symptom davor:
  `imx500 10-001a: setup of GPIO led failed: -121` /
  `imx500_power_on: failed to get led gpio`, dann erst `stream on failed in
  subdev` und der bekannte vb2-Treiberfehler beim Abbau. Diese Zeile fehlt in
  der gesamten bisherigen Journal-Historie (alle vorherigen erfolgreichen
  Sitzungen) komplett — sie ist neu, nicht ein wiederkehrendes Rauschen.
  Ausgeschlossen: eine Paket-Regression (der Kamera-Stack-Umbau `libcamera`
  0.7.2/`libpisp` 1.7.0/`rpicam-apps` 1.13.0 lief bereits am 2026-09-07 vor
  allen erfolgreichen Sitzungen vom 2026-09-08; `apt-daily-upgrade.timer`
  hatte heute noch nicht gefeuert).
  `led-gpios` und `reset-gpios` hängen im Overlay (`imx500-pi5.dtbo`) am
  selben GPIO-Controller-Phandle und werden laut den Strings in `imx500.ko`
  über `devm_gpiod_get_optional()` geholt — diese Fehlermeldung erscheint nur
  bei einem echten Fehler des GPIO-Subsystems, nicht bei einer fehlenden
  optionalen Eigenschaft. Auf demselben Pi läuft minütlich
  `x1201-monitor.service` (Geekworm-x120x-USV, `/usr/local/bin/x1200_once.py`),
  das direkt `/dev/gpiochip0` anfasst — auf dem Pi 5 derselbe RP1-Chip, der
  auch CSI/CFE und die Kamera-GPIOs bedient. Beide heutigen Fehlschläge lagen
  in derselben Minute wie ein `x1201-monitor`-Tick; bei minütlichem Tick für
  sich genommen nicht beweisend, aber mechanistisch naheliegend: zwei
  gleichzeitige RP1-GPIO-Anfragen (Kamera-Power-on vs. USV-Pegelabfrage)
  könnten sich das `-EREMOTEIO` liefern. **Nicht geprüft:** ob ein echter
  Stromzyklus (Netzteil ziehen, nicht `sudo reboot`) zuverlässiger hilft als
  der bisher übliche Warmstart — dazu hätte dieser Pi andere produktive
  MEhub-Dienste unterbrochen, das braucht eine bewusste Freigabe.
  Vorgeschlagene nächste Schritte, aufsteigend im Aufwand:
  1. `x1201-monitor.timer` und `rm520n-*.timer` für einen Testlauf stoppen und
     gezielt in der Minutengrenze mehrfach `dispread serve` starten — bestätigt
     oder widerlegt die Kontentionshypothese ohne Risiko für den Kamerapfad.
  2. Prüfen, ob `imx500_power_on` beim Fehlschlag von `devm_gpiod_get_optional`
     für die LED wirklich früh abbricht (Reset/Regulator/Takt also nie gesetzt
     werden) — würde erklären, warum danach kein Stream zustande kommt; dazu
     reicht ein erneuter Fehlschlag mit `dynamic_debug` auf `imx500.c`, kein
     Kernel-Rebuild nötig.
  3. Erst danach, falls (1) nichts zeigt: ein echter Stromzyklus als
     Gegenprobe zum reinen `reboot` — mit Ansage, da er MEhub mit betrifft.
  Aufbau, vollständige Zeitleiste und Befehle: `docs/lab_journal.md`,
  Eintrag 2026-09-09.

* **Update 2026-09-09, Nachmittag spät — zwei Abmilderungen in
  `workbench/Controller._worker` umgesetzt (beheben die RP2040-Sperre
  nicht, verringern/entschärfen sie nur):** (1) Geometrie-Änderungen
  (Breite/Höhe/Bildrate) werden jetzt über ein 250-ms-Fenster gebündelt,
  bevor der Stream neu aufgebaut wird — eine Auflösungsänderung (bisher zwei
  Befehle, zwei Power-Zyklen) kostet jetzt höchstens einen. (2) Die
  riskanten Kameraaufrufe laufen über einen Wachhund
  (`CAMERA_OP_TIMEOUT_S = 6 s`); hängt einer davon, wird das sofort als
  `CameraWedgedError` mit Verweis auf diese OQ gemeldet, statt den
  Kamerathread endlos schweigend hängen zu lassen — deckt damit den unter
  „Was die Workbench tun muss" Punkt (c) ab. Details:
  [CHANGELOG.md](../CHANGELOG.md) 2026-09-09. Noch offen: ein gezielter Test
  für den neuen Entprell-/Wachhundpfad (bestehende Tests laufen alle mit
  `simulate=True`), und ob (2) auch bei einem hängenden `Picamera2()`-
  Konstruktoraufruf selbst greift — der liegt außerhalb von `_worker`s
  Guard.

* **Update 2026-09-09, spät — bei Raspberry Pi gemeldet, kein Fix ohne Reboot
  bislang verifiziert.** Vollständige Commit-Historie von
  `drivers/spi/spi-rp2040-gpio-bridge.c` geprüft (`gh api`): seit Einführung
  2024-05-21 nur zwei Commits, keiner adressiert diesen Fehler; keine
  offenen oder geschlossenen Issues im `raspberrypi/linux`-Tracker erwähnen
  ihn. Damit ist der Fehler **nirgends dokumentiert** — gemeldet als
  [raspberrypi/linux#7613](https://github.com/raspberrypi/linux/issues/7613)
  mit Reproducer, Kernel-Log-Signatur und allem, was ausgeschlossen wurde
  (RP1-GPIO-Kontention, veraltete RP2040-Firmware, Kernel-6.18.34-Diff).
  Ein möglicher Wiederherstellungsweg ohne vollen Reboot — Unbind/Rebind von
  `10-0040` (RP2040-Bridge) am I2C-Bus, wodurch `cam0_reg` (der von Sensor
  **und** Bridge gemeinsam genutzte, GPIO-rückende Regulator, live per
  `gpiod` als von `cam0_reg` exklusiv gehalten bestätigt) auf `num_users: 0`
  fallen und danach real neu einschalten sollte — liegt vorbereitet als
  Skript vor (`/tmp/rp2040_recover_test.sh` dieser Sitzung, nicht
  versioniert), aber **noch nicht ausgeführt**: das Unbind/Bind
  braucht Root, kein Nicht-Root-Weg existiert nachweislich (kein
  gecachtes `sudo`, kein Setuid-/Polkit-Helfer, alle relevanten
  Sysfs-Pfade `root:root`, die GPIO-Leitung selbst vom Kernel exklusiv
  gehalten). Nächster Schritt bei Gelegenheit: das Skript mit `sudo`
  ausführen und das Ergebnis hier sowie im GitHub-Issue nachtragen —
  unabhängig vom Ausgang, da auch ein Fehlschlag für die Meldung relevant
  ist.

* **Update 2026-09-09, 11:15 — Test durchgeführt, Ergebnis negativ, Zustand
  danach schlechter als vorher.** `sudo`-Zugriff kurz verfügbar (Cache),
  Skript ausgeführt. `echo 10-0040 > .../rp2040-gpio-bridge/unbind` senkte
  `cam0_reg` erwartungsgemäß auf `num_users: 0 / disabled` — die
  Power-Gating-Analyse stimmt. Der anschließende Rebind scheiterte jedoch:
  `i2c_designware 1f00088000.i2c: controller timed out`, dann **`SDA stuck
  at low`** — ein echter I2C-Bus-Lockup, kein reines Treiberproblem. Danach
  wurde die Kamera **nicht mehr erkannt** (`No camera number 0 found`),
  vorher war sie zumindest noch enumeriert, nur blockiert beim Streamen.
  **Schluss: Unbind/Rebind ist keine funktionierende Wiederherstellung ohne
  Reboot — im Test hat es den Zustand verschlechtert.** Vermutung: der
  RP2040 braucht entweder eine längere Aus-Phase als die getesteten ~2 s,
  oder eine bestimmte Reihenfolge/Timing beim I2C-Wiederanlauf, die ein
  simples Unbind/Bind nicht liefert. Nachtrag im Issue:
  [Kommentar](https://github.com/raspberrypi/linux/issues/7613#issuecomment-5599453376).
  Reboot war danach nötig. `/tmp/rp2040_recover_test.sh` nicht ohne
  Weiteres wiederverwenden.

* **Update 2026-09-09, spätabends — hartes Power-Zyklus-Budget in der
  Workbench, verhindert das Auslösen über die eigene Bedienoberfläche.**
  Da keine funktionierende Wiederherstellung existiert und der Fehler
  hardwareseitig ungeloest bleibt, verweigert `Controller` jetzt eine
  echte Aufloesungs-/Bildratenaenderung, sobald `geometry_cycles` das
  Sicherheitsbudget (`MAX_GEOMETRY_CYCLES = 15`, unter dem beobachteten
  ~20-25er-Bereich) erreicht - mit klarer Fehlermeldung statt eines
  spaeteren, unvorhersehbaren Ausfalls. Behebt den RP2040-Fehler nicht,
  verhindert aber zuverlaessig, ihn ueber `dispread` selbst auszuloesen.
  Details: [CHANGELOG.md](../CHANGELOG.md) 2026-09-09 spätabends, Test
  `test_geometry_budget_blocks_change_but_allows_same_value`.

* **Update 2026-09-09, noch später — Lücke im Budget geschlossen: Zähler
  überlebt jetzt einen dispread-Neustart korrekt.** Der Zähler lag nur im
  Prozessspeicher; ein reiner `dispread`-Neustart (ohne Host-Reboot) hätte
  ihn faelschlich auf 0 gesetzt, obwohl der RP2040 die Zyklen laengst
  verbraucht hatte (belegt: Fehlschlag trat in einem frueheren Test auch
  ueber mehrere frische Prozesse hinweg auf derselben Bootsitzung ein).
  Jetzt an die Kernel-Boot-ID gebunden persistiert
  (`camera_cycles.json`) — haelt ueber Prozessneustarts, setzt sich nur bei
  echtem Reboot zurueck. Details:
  [CHANGELOG.md](../CHANGELOG.md) 2026-09-09 noch später.

* **Update 2026-09-09, noch später — mögliche echte Abhilfe auf
  Devicetree-Ebene gefunden, nicht selbst umsetzbar (kein Root, Reboot zum
  Testen nötig).** Der beim Rebind-Test aufgetretene I2C-Bus-Lockup
  (`SDA stuck at low`) betrifft `i2c@88000` (RP1) — dessen Devicetree-Knoten
  hat **keine** `scl-gpios`/`sda-gpios`-Eigenschaften. Linux' eingebaute
  generische GPIO-Bus-Recovery (`i2c_generic_gpio_recovery`, Standardmechanismus
  genau für einen haengenden SDA-Zustand) ist fuer diesen Bus also gar nicht
  verdrahtet — ein Stuck-Zustand kann sich derzeit nicht von selbst
  erholen. Waere dieses Feature per Overlay/Basis-Devicetree ergaenzt
  (setzt voraus, dass RP1s Pinmux SCL/SDA waehrend der Recovery als
  reine GPIOs freigeben kann), koennte der Kernel einen solchen Lockup
  selbststaendig ohne jeden Host-Reboot beheben — unabhaengig davon, was
  die eigentliche RP2040-Ursache ist. Im Issue nachgetragen:
  [Kommentar](https://github.com/raspberrypi/linux/issues/7613#issuecomment-5599575083).
  Nicht selbst umgesetzt: braucht Root zum Bauen/Installieren eines
  Overlays und einen Reboot zum Testen.

* **Nachtrag 2026-09-24 — nach nächtlicher Abschaltung wieder
  funktionsfähig.** Boot `b973b67f-69a7-488a-9870-9e8daea714b8`: Probe von
  IMX500 und RP2040-Brücke sauber, danach sechs erfolgreiche 960×720-
  Streamstarts (bis 20 min Dauer, mit und ohne ScalerCrop) ohne
  `stream on failed`. Ob die Versorgung über Nacht ganz getrennt war, ist
  nicht belegt; ein einzelner guter Kaltstart beweist nicht, dass nur ein
  Stromzyklus hilft. Zahlen: [VALIDATION.md](VALIDATION.md), 2026-09-24.

* **Nachtrag 2026-09-24, 11:11 — im selben Boot erneut blockiert, beim
  8. Streamstart.** Sieben Starts liefen (zuletzt 10 s Vollbild um 11:11:06),
  der achte (ScalerCrop 880,1015,1920,1440, 11:11:31) lieferte 0 Bilder:
  `rp2040_gbdg_wait_until_free failed`, `gpio_dir_out(19, 0) could not
  ST_CL`, `setup of GPIO led failed: -121`, 6 × `stream on failed in
  subdev`, danach eine `WARNING` in `__vb2_queue_cancel` (videobuf2-core.c:2215).
  Der Prozess beendete sich selbst (Timeout 5 s), nichts hing. Gesamte
  Streamdauer des Boots vorher ≈ 36 min. Damit liegt die Grenze hier weit
  unter 20–25 Starts; das Budget von 15 schützt nicht. Kernel-Auszug:
  `var/diagnostics/ernte1-crop/kernel-11-10.txt` (lokal).

* **Nachtrag 2026-09-25 — für den Betrieb gegenstandslos.** Am 2026-09-25
  fiel die Kamera zusätzlich **mitten in einem laufenden Stream** aus
  (I2C `-121`, „Camera frontend has timed out"), nachdem sie mechanisch
  bewegt worden war. Nutzerentscheidung am selben Tag: offizieller Wechsel
  auf die Logitech StreamCam (USB/UVC), die IMX500 ist außer Betrieb
  ([project_history.md](project_history.md), 2026-09-25). Die Frage bleibt
  offen, falls die IMX500 zurückkommt; der Testplan mit dem
  Kernel-Maintainer (raspberrypi/linux#7613) wird nicht weiter verfolgt.

* **Antwort landet in:** `docs/lab_journal.md`, `docs/HARDWARE_PROFILE.md`,
  gegebenenfalls `scripts/camera-commissioning.sh` und `docs/ROADMAP.md`.

<span id="oq-23"></span>

## OQ-23 — Festes Segmentraster passt nicht zur realen BK-5491B-VFD-Schrift

* **Status:** offen · erkannt 2026-09-09 bei der ersten realen
  Workbench-OCR-Prüfung
* **Befund:** Im beschrifteten Realbild
  `var/workbench/diagnostics/fokus-erreicht-960x720.jpg` steht `-000.13 mV`.
  Mit manuell auf Vorzeichen und fünf Stellen gelegter ROI, Layout
  5 Stellen / 2 Nachkommastellen / `mV` und `sign_cell_ratio=0.6` liefert
  `sevenseg/2` jedoch `777?7`, keinen Zahlenwert und die Ablehnungsgründe
  `unreadable_cells:1`, `no_value`. Die Freigabe bleibt korrekt
  `unreadable`; es entstand keine stille gültige Fehlablesung. Das Overlay
  zeigt als Ursache eine nicht ausreichend passende feste Abtastgeometrie:
  insbesondere die schmale VFD-`1` liegt nicht auf denselben relativen
  Segmentpunkten wie der synthetische Generator.
* **Konsequenz:** Die Workbench-Bedienung und die sichere Ablehnung sind
  implementiert, aber eine reale Erkennungsquote ist damit nicht belegt.
  Dieser eine Aufbau darf weder zum Nachstimmen und anschließenden Bewerten
  desselben Bildes noch zur Konfidenzkalibrierung verwendet werden.
* **Klärung:** Einen bestätigten Replay-Datensatz mit getrenntem Entwicklungs-
  und Testsatz erfassen. Dann profilierbare Segmentgeometrie bzw. flächige
  Segmentmessung gegen Tesseract/weitere Backends vergleichen und pro
  Fehlerklasse auswerten. Referenzwerte bleiben außerhalb von
  `ValueReader.read` und `ReleaseGate.evaluate`.
* **Blockiert:** reale Abnahme des Segmentlesers in P3, nicht die
  Workbench-Einrichtung.
* **Antwort landet in:** `src/dispread/ocr/`, Geräteprofile und
  `docs/VALIDATION.md`; Rohbefund im Laborjournal vom 2026-09-09.

* **Update 2026-09-09:** Die Workbench kann jetzt vier Displayecken einzeln
  bestätigen und perspektivisch auf 400×160 entzerren. Das beseitigt einen
  Geometriefehler des bisherigen achsparallelen Ausschnitts, klärt OQ-23 aber
  nicht: Die abweichende VFD-Glyphenform braucht weiterhin mehrere bestätigte
  reale Entwicklungs- und Testbilder.

* **Update 2026-09-09, Rasterkalibrierung:** Ein eigener `ocr_box` kann jetzt
  innerhalb der entzerrten ROI an Vorzeichen und Ziffern ausgerichtet werden.
  Der eingefrorene Editor zeigt dabei Zellen und reale Segment-Abtastpunkte.
  Damit lässt sich die bekannte Rasterverschiebung manuell beseitigen; ob die
  VFD-Glyphen danach mit den festen relativen Segmentpunkten zuverlässig lesbar
  sind, bleibt am getrennten Real-Testset zu klären.

* **Update 2026-09-09, Ziffernabstand:** Bedienerbeobachtung im Browser zeigte
  zu weit auseinanderliegende Segment-Abtastpunkte, weil `cell_boxes` bislang
  keinen Zwischenraum zwischen den Stellen kannte. Neues Layoutfeld
  `digit_gap_ratio` (Default `0.0`, Bedienzeile „ziffernabstand") lässt den
  Abstand jetzt mitkalibrieren; siehe [CHANGELOG.md](../CHANGELOG.md) 2026-09-09
  (Zwischenraum zwischen Ziffernstellen). Das ist eine unabhängige
  Geometriekorrektur und klärt OQ-23 weiterhin nicht abschließend — die
  abweichende VFD-Glyphenform braucht weiterhin einen bestätigten
  Real-Testsatz.

* **Update 2026-09-09, Obergrenze nachgeschärft:** Bedienerrückmeldung: Die
  Obergrenze `digit_gap_ratio <= 1.0` reichte für die reale Anzeige nicht;
  das native Zahlenfeld klemmte dort ohne Rückmeldung. Auf `3.0` angehoben,
  siehe [CHANGELOG.md](../CHANGELOG.md) 2026-09-09. Weiterhin ein
  unvalidierter Vorabdefault wie die übrigen `LAYOUT_RATIOS`-Einträge.

* **Update 2026-09-09, Empfindlichkeit gegen Helligkeits- und
  Punktabweichung:** Bedienerrückmeldung am realen Gerät: Eine Ziffer, die
  etwas schwächer leuchtet als die übrigen, oder ein Abtastpunkt, der nicht
  exakt auf der Segmentmitte liegt, führt spürbar häufig zur Ablehnung
  ("funktioniert nicht mehr richtig"). Zwei mögliche, nicht gegeneinander
  abgegrenzte Ursachen im aktuellen `sevenseg.py`:
  1. `segment_threshold()` schwellt bewusst über die **gepoolten** Segmentmessungen
     aller Stellen (Begründung im Code: verhindert Fehlablehnung bei "8" und
     falsche Panel/Segment-Trennung, siehe OQ-13). Das macht die Schwelle aber
     unempfindlich für eine Stelle, die insgesamt dunkler ist als die
     übrigen - ihre eigenen aktiven Segmente können unter der von den
     helleren Stellen dominierten globalen Schwelle liegen.
  2. `_SAMPLE_HALFWIDTH = 0.06` (Fensterradius je Abtastpunkt, Anteil der
     Zellenbreite) ist klein genug, dass ein leicht daneben liegender Punkt
     bereits Panel- statt Segmentpixel mittelt - dieselbe Rasterungenauigkeit
     wie OQ-23, hier als Messempfindlichkeit statt als Positionsfehler
     sichtbar.
  * **Bewusst nicht angefasst:** `_MIN_CONTRAST`/`_SAMPLE_HALFWIDTH` ohne
    reale Testbilder zu lockern hätte nach Konzept.md §7 das falsche
    Vorzeichen - es senkt die Ablehnungsschwelle blind und kann aus einer
    sicheren Ablehnung eine unsichere, falsch "sichere" Ablesung machen.
    Genau das verbietet AGENTS.md ("keine Vermutung"). `GATE_CONFIRM_FRAMES`
    (siehe oben, [CHANGELOG.md](../CHANGELOG.md) 2026-09-09) mindert nur das
    Flackerbild, nicht diese Empfindlichkeit.
  * **Klärung:** Braucht denselben bestätigten Real-Testsatz wie OQ-23 -
    insbesondere Aufnahmen mit gezielt unterschiedlich hellen Stellen -, um
    zwischen (1) und (2) zu unterscheiden und eine Änderung tatsächlich zu
    validieren statt zu raten.

* **Update 2026-09-09, mit zwei echten Annotationen belegt - Ursache (1)
  bestätigt, (2) nicht die Hauptursache:** Bediener speicherte im neuen
  `annotate`-Modus zwei echte Aufnahmen einer roten LED-Anzeige, beide
  zeigen `11.00` (4 Stellen, 2 Nachkommastellen, `digit_gap_ratio=0.65`,
  Profile `var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd` und
  `.../8a18ee05e31241b9b6702c5bb904ec97`). Der aktuelle Leser liest sie als
  `11?0` bzw. `110?` - exakt die gemeldete Ablehnung.
  * **Direkt nachgemessen** (`_sample()` je Segment vor dem Schwellwert,
    reproduziert über `crop_box`+`SevenSegmentReader.read` wie im echten
    Pfad): Die "aus"-Segmente liegen in beiden Bildern eng gebündelt bei
    Helligkeit 0,20-0,28. Die tatsächlich **an**-Segmente einer echten `0`
    streuen dagegen breit von rund 0,38 bis 0,85 - je nach Aufnahme ist ein
    anderes Segment das dunkelste (Stelle `a` in Bild 1, Stelle `c`/`e` in
    Bild 2). Der eine gepoolte, globale Schwellwert aus
    `segment_threshold()` liegt zwangsläufig irgendwo in dieser breiten
    Spanne und reisst je nach Aufnahme ein anderes, tatsächlich leuchtendes
    Segment mit ab. Damit ist Ursache (1) oben an echten Daten bestätigt.
  * **Gegenprobe zu Ursache (2) (Punkt-/Rasterversatz) durchgeführt:** Ein
    Einzelschritt-Warp direkt vom Rohbild statt der doppelten
    Größenänderung `rectify()` (auf 400×160) gefolgt von `crop_box()`
    (nochmals auf 400×160 hochskaliert) wurde probeweise nachgebaut. Er
    behebt die Fehlablesung nicht zuverlässig - in Bild 1 wird dadurch sogar
    eine zweite Stelle unlesbar, in Bild 2 bleibt weiterhin eine Stelle
    unlesbar, nur eine andere. (2) ist damit nicht die Hauptursache dieses
    konkreten Befunds; die doppelte Größenänderung bleibt aber eine separat
    beobachtete, unnötige Auflösungs-/Schärfeverlustquelle im
    `rectify()`→`crop_box()`-Pfad, unabhängig bewertet.
  * **Vorgeschlagene, noch nicht umgesetzte Lösung (auf Bedienerwunsch
    zurückgestellt, "erstmal nur dokumentieren"):** Grenzfall-Auflösung im
    Decoder - wenn das binäre An/Aus-Muster einer Zelle in keiner Tabelle
    steht, aber genau einem Tabellen-Digit bis auf Segmente entspricht, die
    innerhalb einer kleinen Toleranzbreite um den Schwellwert liegen, dieses
    eine Digit mit entsprechend reduzierter Konfidenz übernehmen - sonst wie
    bisher ablehnen. Enger als `_MIN_CONTRAST`/`_SAMPLE_HALFWIDTH` pauschal
    zu lockern, aber weiterhin eine Änderung an "unlesbar ablehnen statt
    raten" (Konzept.md §7) und deshalb nicht ohne ausdrückliche Freigabe
    umzusetzen.
  * **Klärung:** Umsetzung und Validierung der Grenzfall-Auflösung gegen
    diese zwei Bilder plus die bestehende Testsuite, sobald gewünscht.
    Zusätzliche echte Annotationen (auch mit bewusst unterschiedlicher
    Displayhelligkeit) würden die Validierung deutlich verlässlicher machen
    als zwei Aufnahmen aus derselben Kalibriersitzung.

* **Update 2026-09-11, breitere Messung — Ursache (1) erneut bestätigt, und ein
  neuer, bisher unbekannter Befund.** Zahlen und Verfahren vollständig in
  [VALIDATION.md](VALIDATION.md), Abschnitt „2026-09-11 — Ausgangsmessung
  `sevenseg/2`"; Aufbau und Deutung in [lab_journal.md](lab_journal.md).
  * **Datenlage korrigiert:** Es liegen **neun** Annotationen vor, sechs davon
    mit getipptem Sollwert — dieser Eintrag und OQ-25 nannten bisher zwei.
    Alle sechs stammen weiterhin von **einer** Geräteinstanz; der Satz bleibt
    damit ein Entwicklungssatz, kein Testset.
  * **Ist-Stand:** 5 korrekt, **0 falsch angenommen**, 1 abgelehnt.
  * **Ursache (1) unabhängig erneut belegt, diesmal als Stelle-zu-Stelle-
    Differenz:** In `8a18ee05` misst das tatsächlich leuchtende `e` der letzten
    Stelle 0,38, während dieselben Segmente der Nachbarstelle bis 0,85
    erreichen. Die eine globale Schwelle liegt dazwischen.
  * **Neuer Befund — Segment `a` leuchtet, wo es nicht leuchten sollte:** In
    `6ffc561b` misst Segment `a` der Stelle 0 roh 0,38, während `b`/`c`
    derselben Stelle bei 0,76/0,84 liegen; die Stelle zeigt eine `1`, `a` muss
    also aus sein. Eine panelbezogene Entscheidungsregel dekodiert diese Stelle
    deshalb als `7`. Ursache ungeklärt — Übersprechen zur Nachbarstelle,
    Nachleuchten des VFD oder ein Abtastpunkt, der über die Zellgrenze reicht,
    sind nicht gegeneinander abgegrenzt.
  * **Daraus das Abnahmekriterium für jede künftige Decoder-Änderung:**
    `6ffc561b` Stelle 0 liefert `1` **oder** wird abgelehnt — niemals `7`. Und
    die Zahl der falschen Annahmen bleibt bei **0**; gegen diese Ausgangszahl
    blockiert bereits eine einzige falsche Annahme die Änderung, unabhängig
    davon, wieviele zusätzliche Treffer sie bringt.
  * **Verworfen, mit Grund:** Otsu *innerhalb* einer Zelle als
    Entscheidungsschwelle. Bei sechs aktiven und einem inaktiven Segment
    maximiert es die gewichtete Zwischenklassenvarianz mit einem ausgewogenen
    4:3-Schnitt statt des richtigen 6:1-Schnitts — gemessen wirkungslos.
  * **Flächige Segmentmessung ist mit den heutigen Profilwerten schlechter**
    (3 statt 5 korrekt), weil `thickness_ratio`/`inset_ratio` nie kalibriert
    wurden. Ein Sweep zeigt zwei weit auseinanderliegende Parametersätze mit
    identischer Punktzahl — die Geometrie ist durch sechs Bilder eines Geräts
    **unterbestimmt**. Deshalb kommt die Kalibrierung (Autofit) vor der
    Messänderung, siehe
    [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md).

* **Update 2026-09-21, erstmals gezählt statt an einem Einzelbild vermutet
  (`scripts/dataset-benchmark.py`,
  [PLAN_2026-09-21-dataset-benchmark.md](PLAN_2026-09-21-dataset-benchmark.md)):**
  Gegen **alle 73 lesbaren Proben** des Sammelmodus-Bestands (2 Geräte,
  „RND-Lab" 40, „BK Precision" 33) passt eine grobe Rahmenvorsuche
  (~36 Geometrie-Kandidaten je Probe) **kein einziges Mal** — **0 von 73**,
  achsparallel wie entzerrt, in beiden Geräten. Das bestätigt die frühere
  Einzelbild-Vermutung als gemessenen Befund, nicht mehr als Verdacht: das
  feste relative Segment-Abtastraster passt bei diesem Bestand grundsätzlich
  nicht zur Kameraaufnahme, unabhängig von Geräteserie oder Technologie —
  RND-Lab ist LED, nicht VFD wie BK-5491B, betroffen sind also beide.
  Segmentdiagnose (`segment_report`) an Beispielen zeigt keinen einheitlichen
  Fehlertyp: teils liegt kein einziges Segment über der Schwelle (Stelle 1 in
  `0b5eaacf...`: alle Werte 0,12–0,16, Kontrast zu gering), teils liegt ein
  Muster nahe am Sollmuster, aber nicht identisch (Stelle 2 in
  `0282bca7...`: gemessen `a`/`b`/`f`/`g` aktiv statt `a`/`b`/`c`/`d`/`g` für
  die erwartete „3" — zwei von fünf Segmenten falsch). Das deutet eher auf
  eine grundsätzlich falsche
  Rasterposition/-skalierung als auf eine einzelne Schwellenverschiebung —
  siehe auch OQ-25-Update unten zur Geometrievorsuche selbst. Phase B
  (Leave-one-group-out-Übertragung) konnte dadurch in keiner der 6
  durchgeführten Faltungen (2 von 3 BK-Situationen + 4 RND-Lab-Situationen;
  die dritte BK-Situation „schräg links" hat noch keinen `selected`-Vertreter
  und wurde als Lücke gemeldet, nicht ersetzt) überhaupt eine Übertragungszahl
  liefern — der Vertreter jeder Faltung passte selbst nicht. Rohdaten:
  `docs/VALIDATION.md`, Abschnitt „2026-09-21".
* **Klärung, präzisiert:** Die nächste sinnvolle Stufe ist nicht mehr „mehr
  Bilder sammeln", sondern die Rastergeometrie selbst prüfen — vermutlich
  braucht es eine größere/andere Werte-Spanne in
  `dispread.ocr.autofit._CANDIDATES` als die für synthetische Bilder
  gewählte, oder eine grundsätzlich andere Zellaufteilung (`cell_boxes`)
  für reale Aufnahmen. Das ist jetzt eine Aussage über die Geometrie, keine
  über die Datenmenge mehr.

<span id="oq-24"></span>

## OQ-24 — Browserreaktion und Shutdown nach ROI-Bestätigung real abnehmen

* **Status:** in Arbeit · erkannt 2026-09-09 durch Bedienerrückmeldung
* **Befund:** Der Browser wurde nach ROI-Bestätigung langsam bis unbedienbar;
  auch der gestartete Dienst ließ sich aus der Bedienumgebung nicht mehr
  zuverlässig stoppen. Im bisherigen Controller lief pro 15-fps-Bild die
  Vollbild-Kandidatensuche trotz bestätigter ROI weiter, und die gesamte
  OpenCV-/JPEG-Arbeit hielt den Controller-Lock. Der lokale Statussocket des
  beobachteten Prozesses antwortete noch, die UI-Symptomatik selbst ist in der
  Browserumgebung aber nicht reproduziert/profiliert.
* **Änderung:** Vollbildsuche endet nach Bestätigung, OCR-Vorschau ist auf 5 Hz
  begrenzt, OpenCV-/JPEG-Arbeit liegt außerhalb des Locks. Neuer lokaler Befehl
  `dispread stop`; Kameraabschluss mit Zeitgrenze. Ein isolierter simulierter
  Dienst wurde damit erfolgreich beendet.
* **Update 2026-09-10, präzisiert — „Vollbildsuche endet nach Bestätigung"
  galt zu unbedingt.** Bedienerrückmeldung: Nach einem Neustart mit bereits
  bestätigter ROI/OCR aus einer vorherigen Sitzung lief die Kandidatensuche
  (gelbe Boxen) dauerhaft **nie mehr** — kein visueller Hinweis mehr, ob die
  geladene Geometrie noch zur aktuellen Szene passt, obwohl sie nie gegen das
  aktuell laufende Bild geprüft wurde. Die ursprüngliche Änderung hier war
  richtig gegen die 15-fps-Dauerkosten, aber zu grob: „nach Bestätigung nie
  mehr" statt „nur nicht mehr bei jedem Bild". Jetzt läuft die Suche außerhalb
  des `run`-Modus gedrosselt weiter (`CANDIDATE_INTERVAL_S = 1,0 s`,
  `controller.py`); ein Ladevorgang mit bereits bestätigter Geometrie loggt
  zusätzlich einen Warnhinweis. Die Bestätigung selbst bleibt unangetastet —
  keine automatische Übernahme, kein Auto-Un-Confirm. Kostenmessung:
  [VALIDATION.md](VALIDATION.md), Abschnitt „Kosten der wieder aktivierten,
  gedrosselten Kandidatensuche".
* **Update 2026-09-10, spätabends, erneut präzisiert — die wiederhergestellte
  Suche lief noch über das ganze Bild.** Bedienerrückmeldung direkt auf das
  vorige Update: Am realen Prüfstand (Netzteil mit zwei Anzeigen, zwei
  Monitore im Hintergrund, weitere Messgeräte) schlug die Vergleichssuche
  regelmäßig andere Bildschirme im Bild statt der bestätigten Anzeige vor -
  die vorige Änderung ließ `find_display_candidates` (Vollbildsuche)
  unverändert weiterlaufen, nur gedrosselt statt bei jedem Bild. Jetzt nutzt
  `Controller.publish()` stattdessen `fit_quad_in_region` mit `config["roi"]`
  als Suchfenster-Hinweis - der Suchraum bleibt auf die Umgebung der
  bestätigten ROI beschränkt. Zusätzlich neuer Mindestüberdeckungsfilter
  `MIN_HINT_OVERLAP = 0,2` in `fit_quad_in_region` selbst (`vision.py`): ein
  Kandidat muss den ungepolsterten Hinweisbereich zu mindestens 20 %
  überdecken, sonst kann bei einer großzügig bestätigten ROI weiterhin ein
  zufällig rechteckigeres, aber unbeteiligtes Objekt am Rand des
  aufgeweiteten Suchfensters gewinnen - an einer nachgebauten Ablenker-Szene
  verifiziert (`test_fit_quad_in_region_ignores_unrelated_objects_outside_the_hint`).
  Kostenmessung und Realbild-Nachweis: [VALIDATION.md](VALIDATION.md).
* **Update 2026-09-09, Editorzustand:** Eine Bedienprüfung zeigte, dass das
  eingefrorene OCR-Raster Layoutänderungen nicht übernahm und die erhöhte
  Profilrevision danach `Enter` blockierte. Der Status liefert nun das aktuelle
  Raster; reine Layoutänderungen aktualisieren die offene Editierrevision und
  bleiben bestätigbar. Die reale Browserprüfung braucht einen Neustart des vor
  dieser Korrektur gestarteten Diensts und bleibt deshalb Teil der Klärung.
* **Klärung:** Den realen Dienst kontrolliert neu starten, ROI im Windows-
  Browser als Quad bestätigen, Status-/Bildrate beobachten und sowohl Ctrl-C
  als auch `dispread stop` abnehmen. Erst dann auf `geklärt` setzen. Keine
  Aussage über Kameralatenz aus synthetischen oder `FILE_MTIME`-Bildern.
* **Antwort landet in:** `docs/VALIDATION.md`, `docs/lab_journal.md` und dieser
  Eintrag; Browser-Grundproblem siehe auch OQ-21.

<span id="oq-25"></span>

## OQ-25 — Vorschlagsqualität von `fit_quad_in_region`/`fit_ocr_box` an realen Geräten

* **Status:** offen · erkannt 2026-09-10 beim Bau der automatischen
  Workbench-Vorschläge ([PLAN_2026-09-10-workbench-editor.md](PLAN_2026-09-10-workbench-editor.md))
* **Befund:** Gegen die zwei realen Annotationen aus der Sitzung vom
  2026-09-09 (`var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd`,
  `.../8a18ee05e31241b9b6702c5bb904ec97`) trifft `fit_quad_in_region`
  (`roi.suggest`) die tatsächliche Displayposition zuverlässig (IoU ≈ 0,91
  gegen die bestätigte `roi_quad`, siehe [VALIDATION.md](VALIDATION.md)).
  `fit_ocr_box` (`ocr.suggest`) scheitert an denselben zwei Bildern
  vollständig (IoU 0,0): Die grosszügig bestätigte `roi_quad` umfasst zwei
  übereinanderliegende Anzeigen (`V` und `A`) desselben Netzteils, und die
  Funktion wählt konsequent die falsche (untere `A`-Zeile hat mehr
  Blob-Fläche als die gewünschte obere `V`-Zeile) - die aus Konzept.md §7
  bekannte Haupt-/Nebenanzeige-Verwechslung, hier erstmals an echten Daten
  belegt statt nur befürchtet. Ein Bild zeigt zusätzlich einen
  grossflächigen Glanzfleck als eigenen Blob. Mit einer probeweise enger
  vorgeschlagenen `roi_quad` liefert `fit_ocr_box` stattdessen `None` (sicherer
  Fehlschlag statt falschem Vorschlag), aber weiterhin keinen brauchbaren
  Vorschlag. Zusätzlich unvalidiert: die Filterwerte selbst (Blobhöhen-Spanne,
  Cluster-Lückenschwelle, Schliess-Kernel-Anteil, Flächen-/Seitenverhältnis-
  Grenzen in `fit_quad_in_region`/`fit_ocr_box`) sind Vorabdefaults wie bei
  `DetectionConfig` schon üblich, keine an mehreren realen Geräten
  validierten Grenzen - eine bekannte weitere Schwäche zeigte sich zudem an
  einem sehr schmalen synthetischen Layout (3 Stellen, keine Nachkommastelle),
  siehe Docstring von `fit_ocr_box`.
* **Blockiert:** nichts - `roi.suggest`/`ocr.suggest` bleiben reine,
  unbestätigte Vorschläge, `manual_roi` bleibt Primärpfad. Kein automatisch
  übernommener Wert kann davon betroffen sein.
* **Update 2026-09-10, weiterer Aufrufort (inzwischen wieder abgeloest,
  siehe naechstes Update):** `Controller.command("freeze")` rief `fit_ocr_box`
  zwischenzeitlich ebenfalls automatisch auf. Dieselbe Haupt-/Nebenanzeige-
  Grenze galt dort unveraendert - am oben genannten Netzteil-Beispiel schlug
  auch diese automatische Vermutung die `A`- statt der `V`-Anzeige vor.
* **Update 2026-09-10, spaet nachts:** Der zweistufige Bestaetigungsablauf
  (siehe `CHANGELOG.md`, "TUI-style zweistufiger Bestaetigungsablauf") loest
  den automatischen Aufruf in `freeze()` wieder ab - die OCR-Vermutung
  passiert jetzt explizit beim Uebergang von Stufe A (ROI bestaetigt) zu
  Stufe B (`ocr.suggest`, client-ausgeloest), nicht mehr beim blossen
  Oeffnen des Editors. Die beschriebene Grenze (Haupt-/Nebenanzeige-
  Verwechslung) betrifft weiterhin genau diesen `ocr.suggest`-Aufruf,
  unabhaengig davon, wodurch er ausgeloest wird.
* **Klärung:** Ohne weiteren Bedienerhinweis ist die Haupt-/Nebenanzeige-
  Verwechslung laut Konzept.md §7 strukturell nicht auflösbar - denkbare
  nächste Schritte sind ein zweiter, engerer Bedienerhinweis speziell für
  `ocr_box` oder ein Layout-Feld für "erwartete Zeilenzahl im ROI". Beides
  nicht Teil dieser Stufe. Weitere reale Annotationen (auch mit bewusst
  einzelner Anzeige im Ausschnitt) würden die Validierung deutlich
  verlässlicher machen als zwei Aufnahmen desselben Geräts.
* **Update 2026-09-11, Datenlage korrigiert:** Der Befund oben spricht von
  „den zwei realen Annotationen". Inzwischen liegen **neun** Annotationen vor,
  sechs davon mit getipptem Sollwert (Aufzählung und Messung in
  [VALIDATION.md](VALIDATION.md), Abschnitt „2026-09-11"). Alle stammen
  weiterhin von **einer** Geräteinstanz, die Aussage dieses Eintrags über die
  Vorschlagsqualität bleibt damit unverändert gültig — die Zahl war schlicht
  veraltet. Die IoU-Messung von `fit_quad_in_region`/`fit_ocr_box` wurde
  **nicht** auf die übrigen vier Bilder ausgeweitet; das steht weiterhin aus.
* **Antwort landet in:** `docs/VALIDATION.md`, `src/dispread/workbench/vision.py`.

* **Update 2026-09-21, `fit_quad_in_region` an 73 realen Proben - 0 von 73
  liefern ein Quad** (`scripts/dataset-benchmark.py`, Arm „deskewed" der
  Dataset-Benchmark-Geometrie, siehe OQ-23-Update oben): Für **jede einzelne**
  der 73 lesbaren Sammelmodus-Proben (beide Geräte) lehnt `fit_quad_in_region`
  die von Hand gezogene Zielbox als Hinweisbereich vollständig ab (`None`).
  Anders als bei den zwei Annotationen von 2026-09-10 (IoU ≈ 0,91) trifft die
  Funktion hier **nie**. Wahrscheinlichste Ursache, noch nicht einzeln
  nachgewiesen: die Sammelmodus-Zielboxen sind bewusst locker um die Anzeige
  gezogen (Plan 2026-09-21 misst eine ~5-fache Flächenstreuung allein
  innerhalb einer Situation) und dadurch systematisch zu großzügig für
  `fit_quad_in_region`s `MIN_HINT_OVERLAP=0,2`/Flächenfilter - eine andere
  Belastung als die bestätigten, engeren `roi_quad`-Hinweise aus dem
  Annotationspfad, für die die Funktion ursprünglich gemessen wurde. Betrifft
  ausschließlich den `deskewed`-Arm des Dataset-Benchmarks; `manual_roi`
  bleibt unberührt (reiner Vorschlag, nie automatisch übernommen).
* **Klärung, präzisiert:** Vor einer Änderung an `fit_quad_in_region` selbst
  erst klären, ob die Ursache tatsächlich die lockere Zielbox ist (z. B.
  testweise `MIN_HINT_OVERLAP` senken oder die Zielbox vor dem Aufruf enger
  fitten) statt die Funktion blind nachzuschärfen - siehe AGENTS.md, keine
  Vermutung ohne Messung.

<span id="oq-26"></span>

## OQ-26 — Grenzen der Nachführung an realen Geräten validieren

* **Status:** offen · erkannt 2026-09-11 in
  [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
  (Task 12, aus der Spezifikation übernommen)
* **Befund:** `TrackConfig` in `src/dispread/track.py` legt drei Schwellen für
  die begrenzte Nachführung eines bestätigten Quads fest —
  `max_shift=0.10`, `max_rotation_deg=3.0`, `min_score=0.60`. Wie alle Werte
  in `DetectionConfig` sind das Vorabdefaults, die nicht gegen echte
  Gerätebewegung (Vibration, thermische Drift, versehentlicher
  Bedienereingriff) validiert wurden — nur gegen synthetisches Material
  (`tests/test_track.py`) und die vier realen Clips unter
  `var/workbench/clips/`, die alle von einer einzigen Geräteinstanz
  (`device_id="RND Lab"`) stammen.
* **Klärung:** Braucht mehrere reale Geräteinstanzen mit provozierter
  Bewegung (siehe ROADMAP-P2-Sperrbedingungen), um zu prüfen, ob die drei
  Schwellen echte Fehlausrichtung zuverlässig fangen, ohne bei normaler
  Vibration `tracking_lost` fälschlich auszulösen oder umgekehrt eine echte
  Verschiebung durchzulassen.
* **Update 2026-10-21 (R13):** Der strenge Live-Werteplan-Lauf
  `live-20261021T151835Z/run-01` zeigt ab dem Sprung auf Faktor 2
  `tracking_lost:low_score`; beim folgenden Faktor 0,5 kehrt VALID ohne
  Eingriff zurück. Der Tracker registriert auch wechselnde Ziffern gegen
  das Einrichtungsbild. Das ist reale Evidenz für einen vom Anzeigeinhalt
  abhängigen Fehler, noch kein unabhängiger Ausschluss mechanischer
  Bewegung und kein abgeschlossener Belastungstest. Diagnose und
  Zwischenzahlen stehen in
  [VALIDATION](VALIDATION.md#messlauf-vorbereitung-2026-10-21) und im
  [Laborjournal](lab_journal.md). Die bisherige Zurückstellung „erst bei
  realem Befund untersuchen“ ist damit überholt. Strukturstabile
  Nachführung und eine Wiederholungsprüfung großer Sprünge bleiben offen.
  Der Lauf ist inzwischen mit Grund `bediener` beendet; Rückstellung
  erfolgreich laut `session.json`. Die vollständige Referenzauswertung
  folgt im Abschlussbefund unten.
* **Abschluss 2026-10-21:** 806 s Laufzeit, 0/11 137 Fehllesungen bei
  prüfbaren VALID, aber 8074 Trackingverluste. In stabilen Referenzfenstern
  sind Faktor 2 und 5 zu 100 % UNREADABLE; Faktor 1, 0,5 und 10 nahezu
  durchgehend VALID. Die Person bestätigt unveränderten Aufbau und ca.
  2 s Abdeckung ungefähr nach 6 min; diese ist zeitlich im Audit nicht
  eindeutig isolierbar. Keine Schwellenänderung während des Laufs,
  Rückstellung bestätigt. Die Frage bleibt offen; strukturstabile
  Nachführung muss erst entwickelt und geprüft werden.
  [Zahlen](VALIDATION.md#messpfad-live-werteplan-2026-10-21).
* **Nachtrag 2026-10-30 (R13-25, Reviewkorrektur):** Die zunächst verwendeten
  gemittelten Zweitbilder samt Halb-Pixel-Proben waren zu optimistisch:
  im Hauptfall blieb eine als stabil gemeldete Region in sämtlichen 210
  Laufbildern unter 0,75. Neue Einrichtungen prüfen deshalb die acht
  ungemittelten Aufnahmen der Stabilitätsaufnahme: mindestens sieben
  eindeutige innere Treffer mit Peak ≥0,775 und höchstens 2 px Lageabweichung.
  Die Reserve 0,025 gilt nur bei der Einrichtung; Laufgrenzen bleiben gleich.
  Die Ausfallreserve je Rahmenseite zählt ausschließlich solche Regionen.
  Einzelbilder bleiben nur im Speicher, Kennzahlen und gemitteltes Zweitbild
  bleiben gespeichert. Alte Mittelbilder allein liefern keinen nachträglichen
  Einzelbildnachweis; bestätigte Profile laufen ohne Neuauswahl und mit
  unverändert strikter Laufkonfiguration weiter. Der Vergleich mit den
  Diagnosebildern ist Entwicklung und ersetzt keine unabhängige Abnahme;
  OQ-26 bleibt offen. Die Korrektur ist nicht abgenommen: im geforderten
  Bestand 738→859 Tracks, drei vorherige Tracks verloren; zusätzlich
  bleiben Fehlvorhersagen der Einzelbildprobe. Kein Nullverlust-Nachweis.
  [Kalibrierung und Grenzen](VALIDATION.md#r13-25-stabile-rahmenregionen-2026-10-30),
  [Aufbau und Deutung](lab_journal.md#r13-25-stabile-rahmenregionen).
* **Nachtrag 2026-10-31 (R13-25 Runde 3):** Neue Einrichtungen behalten jetzt
  die bisherige Auswahl und ersetzen nur probefällige Bereiche. Ein Ersatz
  muss in den Einzelbildern lagekonsistent zum starren Konsens liegen, in
  Stufen der unveränderten Laufgrenzen 0,35/0,50/0,65 px. Ohne erfüllbare
  Stufe meldet `nachfuehrung` WARNUNG. Befund: Die Verluste der Runde 2
  kamen aus der Auswahl. Ein großer Austausch verschob die Lage um ≤ 0,14 px
  und kippte Grenzbilder der LCD-Randprüfung. Diese stehen schon mit dem
  alten Satz bei 15/18 Randpunkten, Grenze 14,4. Ersatzbereiche mit
  systematischem Residuum über 0,65 px scheiterten im Lauf als Inlier an
  der Residuengrenze. Stand: Pflichtbestand 738→861 Tracks, 1 verloren
  (`121101/0034`, Rückfallstufe ohne Lageprüfung). Alle 1.492 Bilder 4
  verloren, davon drei Grenzbilder in `113238`. 0 Fehllesungen, Sweep
  0 falsche Quads, aber 22 verlorene synthetische Tracks in `121101`. OQ-26
  bleibt offen: kein Nullverlust, die Probe sagt die Live-Nutzbarkeit
  einzelner Regionen weiterhin nicht verlässlich voraus (Hauptfall
  schlechteste Region 29 %).
  [Runde 3](VALIDATION.md#r13-25-runde-3).
* **Antwort landet in:** `docs/VALIDATION.md`.

<span id="oq-27"></span>

## OQ-27 — Rasterfeinschliff je Bild bewusst nicht gebaut

* **Status:** offen (bewusste Nicht-Entscheidung, kein Fix ausstehend)
* **Befund:** Ein Rasterfeinschliff je Bild (Projektionsprofil zieht die
  Zellgrenzen pro Frame nach) wurde für
  [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
  erwogen und verworfen — Begründung in
  [project_history.md](project_history.md), Eintrag „2026-09-11 — OCR-
  Selbstkalibrierung: verankerte Werkzeuge statt genereller OCR/
  Klassifikator". Phase C dieses Plans (`QuadTracker`) fängt starre Bewegung
  des ganzen Quads bereits ab; ein Feinschliff ohne Verankerung am
  bestätigten Raster würde die Haupt-/Nebenanzeige-Verwechslung aus
  [OQ-25](open-questions.md) in den Lesepfad erben.
* **Klärung:** Offen bleibt, ob ein verankerter (nicht frei laufender)
  Feinschliff für nicht-starre Änderungen im Ausschnitt (z. B. leichte
  Verzerrung durch Temperatur) je gebraucht wird — bislang keine reale
  Messung, die dafür spricht.
* **Antwort landet in:** `src/dispread/ocr/`.

<span id="oq-28"></span>

## OQ-28 — Eindeutigkeit der Autofit-Geometrie

* **Status:** offen · erkannt 2026-09-11 (Task 4 dieses Plans)
* **Befund:** Der Koordinatenabstiegs-Sweep in `fit_layout`
  (`src/dispread/ocr/autofit.py`) fand auf dem realen Annotationssatz zwei
  strukturell unterschiedliche, aber gleich gut punktende Parametersätze
  (siehe [VALIDATION.md](VALIDATION.md), Abschnitt „2026-09-11 — Autofit
  (`fit_layout`) gegen dieselben sechs Annotationen (Task 4)"). `flat_optimum`
  soll genau diesen Fall anzeigen.
* **Klärung:** Ob `flat_optimum` diesen Fall an einem echten Gerät im
  laufenden Betrieb zuverlässig erkennt — statt z. B. knapp daneben zu liegen
  und einen der beiden Sätze unmarkiert zurückzugeben — ist mit einer
  einzigen Geräteinstanz nicht zu beantworten.
* **Antwort landet in:** `docs/VALIDATION.md`.

<span id="oq-29"></span>

## OQ-29 — Zeitpunkt von `calibrated_on`/`calibrated_on_frame_sequence`

* **Status:** offen · erkannt 2026-09-18 in Task 5's Review
  (PLAN_2026-09-11-ocr-selbstkalibrierung.md)
* **Befund:** In `Controller._autofit`
  (`src/dispread/workbench/controller.py`) wird `self.calibrated_on` (und
  darüber `calibrated_on_frame_sequence`, das über die Clipaufnahme aus Task 2
  in `clip.json` landet) gesetzt, sobald `layout.autofit` irgendein passendes
  Ergebnis liefert — nicht erst, wenn der Bediener es über den `roi`-Op
  tatsächlich bestätigt. In Task 5's Review plan-mandated so belassen, nicht
  gefixt. Szenario: Bediener lässt Autofit laufen, sieht ein unüberzeugendes
  Ergebnis (z. B. `flat_optimum=True`), verwirft es, bestätigt stattdessen
  manuell eine unabhängige/handjustierte ROI — `calibrated_on_frame_sequence`
  behauptet in `clip.json` weiterhin irreführend, die bestätigte Geometrie
  stamme aus dem verworfenen Autofit-Versuch.
* **Blockiert:** nichts Sicherheitsrelevantes — das Feld erreicht nur die
  `clip.json`-Provenienz-/Audit-Metadaten, nie `ValueRecord`, die serielle
  Ausgabe oder das Freigabegate (gemäß den Nicht-Zielen dieses Plans).
* **Klärung:** Ob `calibrated_on` erst beim tatsächlichen `roi`-
  Bestätigungsschritt gesetzt werden soll statt beim bloßen Autofit-Treffer.
* **Antwort landet in:** `src/dispread/workbench/controller.py`
  (`_autofit`/`roi`-Op), ggf. `docs/VALIDATION.md` bei einer künftigen
  Messung.

<span id="oq-30"></span>

## OQ-30 — `roi`-Op ist nicht atomar gegenüber einem fehlschlagenden `QuadTracker`-Aufbau

* **Status:** offen · erkannt 2026-09-18 in Task 7's Review
  (PLAN_2026-09-11-ocr-selbstkalibrierung.md)
* **Befund:** Im `roi`-Op-Bestätigungszweig
  (`src/dispread/workbench/controller.py`) wird `self._change(data)`
  (committet `confirmed=True`, erhöht die Revision, kann `run`→`setup`
  zurückschalten) **vor** dem Aufbau von
  `self.tracker = QuadTracker(frame["image"], roi_quad(frame["image"], data))`
  aufgerufen. Schlägt der Tracker-Aufbau fehl (Exception), ist die
  Bestätigung bereits committet, aber es existiert kein Tracker, und der
  auslösende Frame wird nicht aus `self.frames` entfernt. Gefunden in Task 7's
  Review; vom Controller als zutreffend bestätigt — korrigiert die
  ursprüngliche „pre-existing"-Einordnung des Implementierers.
* **Blockiert:** nichts Akutes — die Auswirkung ist selbstlimitierend:
  `self.frames` ist auf 4 Einträge mit FIFO-Verdrängung begrenzt, und der
  Fehler degradiert exakt auf den Vor-Task-7-Zustand (bestätigt, kein
  Tracker, schließt sicher ab, keine Fehlkorrektur).
* **Klärung:** Ein günstiger Fix existiert (Tracker vor `self._change(data)`
  konstruieren, danach erst zuweisen), war aber keine Bedingung für Task 7's
  Abnahme.
* **Antwort landet in:** `src/dispread/workbench/controller.py` (`roi`-Op).

<span id="oq-31"></span>

## OQ-31 — Stale-Vorschau-Zustand bei manueller Regler-Bearbeitung nach Autofit

* **Status:** geklärt (2026-09-18) · erkannt 2026-09-18 in Task 5's Fix-Runde
  (PLAN_2026-09-11-ocr-selbstkalibrierung.md), vom Re-Reviewer bestätigt,
  im Abschlussreview desselben Plans als R8a behoben
* **Befund:** Task 5's Fix-Runde behob eine Bug-Klasse für den Canvas-/
  Geometrie-Editierfluss (ein stehengebliebenes `editing.autofit`-Ergebnis
  wurde beim Bestätigen stillschweigend angewendet, statt verworfen zu
  werden). Der Implementierer flaggte selbst, dass dieselbe Bug-Klasse
  vermutlich auch für die manuelle Layout-Regler-UI in der Einstelltabelle
  gilt: Läuft ein Autofit erfolgreich, editiert der Bediener danach **vor**
  dem Bestätigen ein Layout-Feld direkt über die Regler der Einstelltabelle,
  könnte das stehengebliebene Autofit-Ergebnis diese manuelle Bearbeitung
  beim Bestätigen trotzdem überschreiben. Vom Re-Reviewer als real bestätigt,
  aber als andere Bugoberfläche eingestuft als das in dieser Runde tatsächlich
  Gefixte.
* **Klärung (2026-09-18, Abschlussreview R8a):** Bestätigt und behoben. Jede
  Layout-Änderung aus der Einstelltabelle (`layout.set`/`layout.set_many` in
  `send()`) verwirft einen anstehenden Autofit-Vorschlag über den neuen
  gemeinsamen Pfad `invalidateAutofit()` — derselbe, den Task 5's Fix-Runde
  für den Canvas-Fluss benutzt. Eine noch laufende Autofit-Anfrage gilt dabei
  ebenfalls als überholt (`requestId` wird erhöht), sonst hätte eine spät
  eintreffende Antwort die zwischenzeitliche Handänderung überschrieben — das
  war ein echtes Rennen, nicht nur eine Reihenfolgefrage. Testabdeckung:
  `tests/workbench_client.test.mjs` (R8a, beide Fälle inkl. Polarität),
  angestoßen von `tests/test_workbench_client.py`.
* **Antwort landet in:** `src/dispread/workbench/static/workbench.js`.

<span id="oq-32"></span>

## OQ-32 — `_row()`/`edit_row()` haben keinen sicheren Fallback für einen unbekannten `kind`

* **Status:** offen (Ursprungsbug behoben, zugrunde liegende Lücke nicht) ·
  erkannt 2026-09-18 in Task 8's Review (PLAN_2026-09-11-ocr-selbstkalibrierung.md)
* **Befund:** Task 8's Review fand und behob einen Critical-Bug: eine neue
  Zeile mit `kind="text"` (wörtlich aus dem damaligen — inzwischen
  korrigierten — Plantext kopiert) ließ `dispread tui`
  (`src/dispread/workbench/tui.py`, `edit_row()`) mit `KeyError: 'min'`
  abstürzen, weil nur die Zweige für `kind=="info"` und `kind=="choice"` eine
  sichere Behandlung haben — jeder andere Wert fällt durch zu Code, der
  numerische Editiermetadaten (`row["min"]`/`row["max"]`) voraussetzt. Der
  akute Bug wurde behoben (`kind="info"` statt `"text"`), aber `edit_row()`
  hat weiterhin keine Validierung oder einen sicheren Default für einen
  unbekannten/unbehandelten `kind` — die Gefahr würde beim nächsten neuen
  Zeilentyp lautlos wiederkehren.
* **Klärung:** `edit_row()` (und die zugehörige `_row()`-Zeilenerzeugung in
  `fields.py`) braucht einen expliziten `else`-Zweig, der einen unbekannten
  `kind` ablehnt statt anzunehmen, dass Zahlenmetadaten vorhanden sind.
* **Antwort landet in:** `src/dispread/workbench/tui.py`,
  `src/dispread/workbench/fields.py`.

<span id="oq-33"></span>

## OQ-33 — Ähnlichkeitsschwellwert des Datensatz-Sammelmodus ist unvalidiert

* **Status:** offen · erkannt 2026-09-18 beim Bau des Datensatz-Sammelmodus
  (`src/dispread/workbench/datasets.py`)
* **Befund:** `DatasetStore._find_similar_in_group()` warnt vor einer
  Wiederholungsaufnahme, deren mittlere normierte Graustufendifferenz zu
  einer anderen Probe derselben Situation unter `SIMILARITY_THRESHOLD = 0.02`
  liegt. Der Wert ist ein Vorabdefault wie `LAYOUT_RATIOS` — an keinem realen
  Datensatz kalibriert. Zu niedrig gesetzt, warnt er nie; zu hoch gesetzt,
  nervt er bei echten unabhängigen Wiederholungen mit ähnlicher Beleuchtung.
* **Klärung:** Braucht echte, als unabhängig bestätigte Wiederholungsaufnahmen
  am selben Gerät, um den Schwellwert gegen tatsächlich beobachtete
  Bildähnlichkeit zu kalibrieren — dieselbe Art Realdatensatz, den dieser
  Sammelmodus überhaupt erst beschaffen soll.
* **Antwort landet in:** `src/dispread/workbench/datasets.py`,
  `docs/VALIDATION.md`.

<span id="oq-34"></span>

## OQ-34 — Realer interaktiver Browserdurchlauf des Datensatz-Sammelmodus steht aus

* **Status:** offen · erkannt 2026-09-18 beim Bau des Datensatz-Sammelmodus
* **Befund:** `static/dataset.js` ist durch reine Geometrietests
  (`tests/dataset_client.test.mjs`) und aiohttp-Endpunkttests
  (`tests/test_dataset_api.py`) abgedeckt, aber ein echter interaktiver Klick-
  Durchlauf (Gerät anlegen → Aufnahme → Zielbox ziehen → speichern → Neustart
  → Export) hat in dieser Umgebung nicht stattgefunden — derselbe Grund wie
  OQ-21: der headless Chromium dieser Umgebung lädt laut dortigem Befund auch
  einfache lokale HTTP-Seiten nicht zuverlässig.
* **Klärung:** Abnahme mit einem echten Browser (siehe OQ-21) nachholen,
  inklusive der Szenarien mehrere Zeilen, `-.125`, führende Null, unlesbar,
  unsicher, ungültige Box, Gerätewechsel bei offenem Entwurf, doppelter Save,
  Schreibfehler, zwei Browsertabs, Tokenablauf, abgeschnittener Export.
* **Antwort landet in:** `docs/anleitung/11-datensatz-sammeln.md`,
  `docs/status.md`.

<span id="oq-35"></span>

## OQ-35 — Automatisierte Testwerterzeugung für den Datensatz-Sammelmodus (GPIO/BK-5491B)

* **Status:** offen · erkannt 2026-09-21 auf Nutzeranfrage
  (`PLANNED_FEATURES.md`, Abschnitt „Other features", Zeile zu GPIO-Sensordaten)
* **Idee:** Das Bench-Multimeter BK Precision 5491B (Geräteeintrag im
  Sammelmodus: `identity_evidence="5491B"`, `model="Count Multimeter"`, siehe
  auch [OQ-23](open-questions.md) zur VFD-Anzeige desselben Geräts) über die
  GPIO-Pins des Pi automatisiert mit Testwerten versorgen, um viele reale
  Bilder mit bekanntem Sollwert ohne manuelles Eintippen zu erzeugen —
  optional auch über verschiedene Kamerawinkel hinweg.
* **Erste Einschätzung, ungeprüft an der realen Hardware:** Ein Multimeter
  *misst* ein anliegendes Signal, es *nimmt* über GPIO keinen Sollwert an —
  "GPIO an das Gerät anschließen" trifft die Richtung also nicht ganz. Zwei
  Bausteine, unabhängig kombinierbar:
  1. **Sollwert automatisch auslesen statt eintippen:** Modelle dieser Baureihe
     führen laut allgemeinem Datenblattwissen üblicherweise RS-232 und GPIB
     als Fernsteuerschnittstellen — **an diesem konkreten Gerät nicht
     nachgewiesen.** Falls vorhanden und verkabelt, ließe sich der intern
     gemessene Wert per Befehl abfragen und als Sollwert für die Probe
     verwenden — vertrauenswürdiger als ein selbst erzeugter Sollwert, weil
     es exakt das ist, was das Gerät selbst als seinen Messwert führt (bei
     dem auch die Anzeige gespeist wird). Braucht keine GPIO-Signalerzeugung,
     nur eine serielle/GPIB-Verbindung zum Pi.
  2. **Ein bekanntes Testsignal in den Messeingang einspeisen**, um gezielt
     verschiedene Anzeigewerte durchzufahren: reine Pi-GPIO-Pins liefern
     dafür keine geeignete, kalibrierte Analogspannung — nötig wäre ein
     DAC (z. B. I2C-Baustein) mit passender Pegelanpassung/Impedanz für den
     Messeingang, keine direkte Drahtverbindung GPIO→Messeingang. Dieselbe
     Vorsicht wie in [OQ-09](open-questions.md) (Pi-GPIO-Pegel nicht direkt
     mit einer externen Signalstrecke verbinden, galvanische Trennung
     prüfen) gilt hier analog, auch wenn es kein RS-232 ist.
* **Ungeklärt:** Hat dieses konkrete Gerät ein funktionierendes RS-232-
  oder GPIB-Interface, und liegt ein passendes Kabel/Adapter vor? Soll
  Baustein 1 (Auslesen) allein reichen, oder wird auch Baustein 2
  (Signaleinspeisung) gewünscht? Beides betrifft ausschließlich den
  Sammelmodus (`DatasetStore`/`dataset.capture`/`dataset.save`) - erreicht
  wie andere Zielbox-/Label-Daten nie `ValueReader`, `ReleaseGate` oder die
  Produktionskette.
* **Antwort landet in:** `docs/HARDWARE_PROFILE.md` (Schnittstellenbefund),
  `docs/anleitung/11-datensatz-sammeln.md` (falls umgesetzt).

<span id="oq-36"></span>

## OQ-36 — Sättigungsbasierte LCD-Quad-Findung nur an einem Gerät gemessen

* **Status:** offen · erkannt 2026-09-22 (Spike zu `lcd_quad_in_region`,
  `src/dispread/workbench/vision.py`)
* **Befund:** `fit_quad_in_region` (Canny-Kantenzug) liefert auf den beiden
  LED-/VFD-Laborgeräten kein einziges Quad (0/36 und 0/41, gemessen
  2026-09-22) — das ist der in `docs/VALIDATION.md` (2026-09-21) als 0/73
  dokumentierte Befund, hier reproduziert; die 73 sind die lesbaren Proben
  genau dieser zwei Geräte. Auf dem GSV-Gerät, das zum Zeitpunkt jenes Laufs
  noch nicht existierte, liefert die Funktion 7 von 11.

  `lcd_quad_in_region` liefert dagegen bei 87 von 88 Proben ein Quad. Die
  reine Trefferzahl sagt aber nichts über die Brauchbarkeit; gemessen an der
  Fläche des gelieferten Quads relativ zur markierten Region:

  | Gerät | n | Quad gefunden | Median | innerhalb der Region |
  |---|---|---|---|---|
  | `87564e34…` (GSV, Farb-LCD) | 11 | 11 | 0.96 | alle |
  | `4237c46d…` | 36 | 35 | 1.00 | alle |
  | `91853b73…` | 41 | 41 | 0.75 (0.53–0.98) | 8 ragen hinaus |

  Nur der GSV-Fall ist brauchbar. Bei `4237c46d…` entartet das Quad zur
  markierten Box selbst (Median 1.00) und bringt keine Entkippung; bei
  `91853b73…` ragen 8 von 41 Quads über die markierte Region hinaus. Beide
  sind LED-/VFD-Laborersatzgeräte, laut Nutzer (2026-09-22) für den
  Produktionspfad nicht relevant, weil dort ausschliesslich LCD-Anzeigen
  eingesetzt werden — die Zahlen belegen aber, dass „findet ein Quad" dort
  nicht „findet die Anzeige" bedeutet.
* **Blockiert:** Ob die implementierte Schwelle `saturation_threshold=60`
  auch auf mehreren echten LCD-Geraeten (nicht nur dem einen gemessenen)
  haelt, ist ungeprueft. Die Methode ist bewusst nur als Vorschlag verdrahtet
  (`lcd_quad_in_region`), niemals als automatische Uebernahme - trotzdem
  bleibt unklar, ob sie bei weiteren LCD-Geraeten ebenso zuverlaessig einen
  ausreichend grossen, bezelfreien Bereich liefert.
* **Klärung:** Mit mehreren echten LCD-Geraeten (nicht nur `87564e34…`)
  messen, ob 60 ein brauchbarer Schwellenwert bleibt oder je Geraet/Beleuchtung
  nachjustiert werden muss.
* **Antwort landet in:** `docs/VALIDATION.md` (Messreihe je Geraet),
  `src/dispread/workbench/vision.py` (Docstring/Default von
  `lcd_quad_in_region`, falls sich der Wert aendert).

<span id="oq-37"></span>

## OQ-37 — Anzeigeformat des GSV-Sensors bei Werten ab 10 mV/V ungemessen

* **Status:** **BEANTWORTET 2026-09-22.** Das Format wechselt **nicht**. Über
  14 Normierungsfaktoren von 1,0 bis 9000 — Anzeigewerte `+0.59696` bis
  `+05372.5`, also weit über 10 — zeigt die Anzeige **ausnahmslos 6 Ziffern**,
  der Dezimalpunkt wandert, führende Nullen bleiben stehen (**im Telegramm —
  auf dem Glas ist die führende Null unterdrückt, korrigiert 2026-09-23, siehe
  [OQ-41](open-questions.md)**). Der Zahlenblock
  belegt damit in **14 von 14** Fällen genau **8 Zellen**. Zahlen und Aufbau:
  [VALIDATION.md](VALIDATION.md), Eintrag „Anzeige über den
  Normierungsfaktor steuerbar".

  **Folge für die Rasterverankerung:** die Voraussetzung des Block-Ankers
  (Zahlenblock = 8 Zellen, unabhängig von der Punktposition) hält über den
  gesamten erreichbaren Bereich. Die hier befürchtete Formatänderung tritt
  nicht ein. Der Block-Anker selbst bleibt davon unberührt an seinem
  gemessenen Ergebnis (45,2 %, Gate nicht bestanden).

  **Wie es beantwortet wurde — ohne jeden Stimulus:** über `set norm` (16)
  und `set dpoint` (17), genau wie es die Präzisierung unten vorgeschlagen
  hatte. Der Eingriff war mit Freigabe des Nutzers, jeder Schritt mit
  Rücklesen, und der Ausgangszustand ist wiederhergestellt
  (Rückstellpunkt: `var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json`).

  **Was dabei NICHT beantwortet wurde:** das Verhalten bei **negativen**
  Werten grossen Betrags. Negative Normierung erlaubt die Anleitung erst ab
  Firmware 1.5.06; dieses Gerät hat 1.3.07. Die Vorzeichenstelle bleibt
  unbelegt — siehe [OQ-39](open-questions.md).
* **Ursprünglicher Stand:** offen · erkannt 2026-09-22 (Rückfrage des Nutzers
  beim Entwurf des Block-Ankers für den Dot-Matrix-Leser)
* **Befund:** Alle 11 bestätigten GSV-Proben liegen zwischen `0.00042` und
  `1.05000`, also **unter 1,06**. Alle zeigen durchgängig 6 Ziffern und 5
  Nachkommastellen (`+X.XXXXX mV/V`). Über das Verhalten bei Werten **ab 10**
  sagt der Datensatz nichts.
* **Warum das zählt:** Der geplante Block-Anker der Rasterverankerung
  (`docs/superpowers/plans/2026-09-22-dotmatrix-backend.md`, Task 2) stützt
  sich darauf, dass der Zahlenblock **immer genau 8 Zellen** belegt —
  Vorzeichen + 6 Ziffern + Dezimalpunkt. Das gilt unabhängig davon, *wo* der
  Punkt steht: `+1.05000` und `+10.5000` enden beide bei Zelle 8, Zelle 9
  bleibt leer, die Einheit beginnt bei Zelle 10.

  Behält die Anzeige bei ≥ 10 die 6 Ziffern und verschiebt nur den Punkt,
  hält der Anker. Wechselt sie dagegen auf 7 Ziffern, verschiebt sich die
  Blockgrenze und der Anker bricht. Der Dezimalpunkt als Landmarke mit fester
  Zellposition ist aus demselben Grund bereits verworfen worden — er wandert
  mit der Grösse.
* **Blockiert:** nichts unmittelbar; der Anker lässt sich mit den vorhandenen
  Proben messen. Betrifft die Tragfähigkeit im Feld, sobald reale Messwerte
  den Bereich überschreiten.
* **Klärung:** Den Sensor einmal über 10 mV/V fahren und ein Foto aufnehmen.
  Eine einzige Probe genügt, um zwischen „Punkt wandert, 6 Ziffern bleiben"
  und „Format wechselt" zu unterscheiden. Gleiches gilt sinngemäss für
  negative Werte grosser Beträge.
* **Präzisierung 2026-09-22 — über den Messwert geht es nicht, über die
  Anzeige schon.** Der Vollausschlag des Laborgeräts ist **1,05 mV/V**
  (gemessen, [VALIDATION.md](VALIDATION.md)), und die höchste
  Eingangsempfindlichkeit des GSV-2 endet bei 3,5 mV/V (`Set Range`, Befehl
  50, nur 2 oder 3,5 zulässig; entspricht 3,675 Vollausschlag). **Ein
  Messwert ab 10 mV/V ist an diesem Gerät also physikalisch unerreichbar** —
  mit keinem Stimulus.

  Die Frage zielt aber auf das **Anzeigeformat**, nicht auf die Physik. Die
  Anleitung: „Die Displayanzeige ergibt sich aus Normierungsfaktor x
  Messwert", gesetzt über `set norm` (16), Einheit getrennt über `set unit`
  (15). Ein Normierungsfaktor, der die Anzeige bei unverändertem Sensorsignal
  über 10 bringt, beantwortet OQ-37 damit **ohne jeden Stimulus** — eine
  Konfigurationsänderung, eine Aufnahme, fertig. Da sie persistent ist
  (wie der Mode-Wechsel) und die Anzeige des Laborgeräts verändert, gehört
  sie abgesprochen und danach zurückgestellt.
* **Nebenbefund 2026-09-22:** Drei der 11 Proben (`1.05000`) sind sehr
  wahrscheinlich Bereichsübersteuerung statt Messwert, siehe
  [OQ-39](open-questions.md). Die nutzbare Probenzahl sinkt damit auf 8.
* **Antwort landet in:** `docs/VALIDATION.md`, dem Profilschema (falls die
  Ziffernzahl doch variabel ist) und der Verankerungslogik des
  Dot-Matrix-Lesers.

<span id="oq-38"></span>

## OQ-38 — Ground-Truth-Quelle für Auto-Labeling: Displaybus oder Geräteschnittstelle?

* **Status:** **weitgehend geklärt 2026-09-22** — Gerät identifiziert,
  angeschlossen, auf ASCII umgeschaltet, Telegramm gemessen. **Verbliebene
  Sachfrage: die zeitliche Zuordnung** zwischen Telegramm und Anzeige
  (Punkt 4/5 unten). Das Herkunftsmerkmal im `DatasetStore` (Punkt 6) ist
  seit 2026-09-22 gebaut, mit zwei offenen Lücken (Migration der
  Bestandsproben, Export gibt die Herkunft noch nicht weiter — Details bei
  Punkt 6). · **Zuständig:** Labor
* **Nachtrag 2026-09-23:** Der Export gibt `label_origin` jetzt weiter
  (`EXPORT_SCHEMA_VERSION` 2). Die Lücke aus Punkt 6 ist damit in diesem Repo
  geschlossen. Der externe Loader in `picam-ai-auto-seven-segment` lehnt
  Version 2 noch ab (`evaluation.py:50`). **Optische Gegenprobe gelaufen:** Das
  Telegramm entspricht inhaltlich der Anzeige, **bis auf die führende Null**.
  Die unterdrückt das Glas, das Telegramm nicht, siehe [OQ-41](open-questions.md).
  Die zeitliche Zuordnung (Punkt 4/5) ist weiter offen.
* **Praktische Bestätigung 2026-09-22:** USB-RS232-Adapter (PL2303) an
  `/dev/ttyUSB0`, 38400 8N1 — der Strom kommt an, 5-Byte-Framing sitzt in
  19/19 Frames, ≈ 1,9 Frames/s, und die Werte folgen dem bewegten Stimulus.
  Zahlen in [VALIDATION.md](VALIDATION.md), Aufbau in
  [lab_journal.md](lab_journal.md). **Es wurde nur gelesen.**
* **Frage:** Woher kommt der Sollwert, wenn Proben des Sammelmodus nicht mehr
  von Hand, sondern automatisch gelabelt werden sollen — vom Displaybus des
  Geräts oder von einer seriellen Geräteschnittstelle?

### Ursprüngliche Einschätzung (2026-09-22 vormittags) — überholt

Aus der Fotoserie allein wurde geschlossen: kein Typenschild, kein erkennbarer
RS-232-Treiber, Schnittstelle nicht nachweisbar → **Displaybus empfohlen**,
mit dem Argument, ein intern geführter Messwert könne von der Anzeige
abweichen (Rundung, Stellenzahl, Formatierung). Dieses Argument ist durch die
Herstellerdokumentation widerlegt, siehe unten.

### Was den Befund gedreht hat

Der Nutzer hat am 2026-09-22 nachgereicht, dass das Gerät sich beim Hochfahren
meldet mit:

```
GSV-2AS (GSV21 V1.3.07)
```

Damit ist es ein **reguläres ME-Systeme GSV-2AS**, kein undokumentierter Bau.
Die Bedienungsanleitung „DMS Messverstärker GSV-2 (GSV-2LS, GSV-2AS,
GSV-2FSD)" ist öffentlich abrufbar und liegt lokal unter
`var/datenblaetter/gsv2-bedienungsanleitung.pdf` (+ `.txt`), Quelle:
`https://www.me-systeme.de/produkte/elektronik/gsv-2/anleitungen/gsv2-bedienungsanleitung.pdf`.
**`var/` ist gitignored** — die Datei überlebt keinen frischen Clone; die URL
ist die dauerhafte Quelle.

Aus ihr, wörtlich:

* Gerätefamilie: „GSV-2AS, GSV-2ASD: Aluminiumgehäuse mit **RS232**, RS422,
  CANbus, Display" — deckt sich mit dem Gehäuse auf den Fotos.
* **5-polige Schraubklemme für RS232 / RS422** (Tabelle S. 7):
  `A = GNDC` (Masse), `B = Rx`, `C = Tx`, `D = Rx+/CAN_GND`, `E = Tx+/CAN_L`.
  **Genau diese Klemme ist auf den Fotos vorhanden** — die kleine grüne
  Zusatzklemme neben der 15-poligen Leiste trägt einen Beschriftungsstreifen
  mit `A`/`B`/`C`. Der Abgriffpunkt ist also bereits im Gerät.
* **15-polige Klemme** (Tabelle 1): 1 = GNDB, 2…7 = Brücke (+US, +UF, +UD,
  -UD, -UF, -US), 8 = UE, 9 = UA (Analogausgang), 10 = GNDA, 11 = SW1,
  12 = Tara, 13 = SW2, **14 = UB, 15 = GNDB**. Die Nutzerauskunft
  „14/15 = Stromversorgung" ist damit unabhängig bestätigt.
* **Der GSV sendet von selbst:** „Der GSV schreibt seine Messwerte permanent
  auf die serielle Schnittstelle." Kein Polling nötig.
* Werkseinstellung: **38400 Baud, 8N1**. Umschaltbar (SetBaud); im
  Konfigurationsmodus über Steckbrücke JP2 fest 38400.
* Zwei Ausgabeformate, umschaltbar per `Set Mode` (Befehl 38d): Binär (5 Byte,
  24 bit) oder **ASCII**.
* **Der entscheidende Satz:** im ASCII-Modus „**entspricht** die ausgegebene
  Zeichenkette **der Anzeige im Display**". Format ab Werk: „Vorzeichen, 6
  Stellen mit Dezimalpunkt, Leerzeichen, Einheit, CR, LF", Beispiel
  `+1.2345 kg<CR><LF>`.
* Diese Kopplung ist auch im Befehlssatz verankert: `Set Digits` (61) „setzt
  die Anzahl der im LC-Display dargestellten Ziffern. Wenn die
  ASCII-Datenausgabe aktiviert ist, wird **auch die Anzahl der übertragenen
  Ziffern-Bytes** gesetzt."
* Maximale ASCII-Datenrate bei 38400 Baud: 200 Hz — weit über den 15 fps der
  Kamera.

Das beobachtete Anzeigeformat passt dazu exakt: `-0.00063 mV/V` ist Vorzeichen
+ 6 Stellen mit Dezimalpunkt + Leerzeichen + Einheit, und die 11 bestätigten
Proben zeigen durchgängig 6 Ziffern ([OQ-37](open-questions.md)).

### Geänderte Empfehlung

**RS232 im ASCII-Modus ist jetzt der Primärweg**, der Displaybus rückt auf den
Platz der Rückfallebene und Gegenprobe. Begründung:

* Das tragende Gegenargument ist weg. „Der Bus liefert das Glas, die
  Schnittstelle nur einen internen Wert" gilt für dieses Gerät **nicht** — der
  Hersteller koppelt ASCII-Ausgabe und Anzeige ausdrücklich.
* Der Abgriffpunkt existiert bereits (Klemme B/C/A), dokumentiert und
  spezifiziert. Kein Mitlesen an einem Flachband, kein Eingriff in das Gerät,
  kein Eigenbau.
* Es ist ein Standard-Seriellpfad, für den das Projekt ohnehin Infrastruktur
  hat.

Der Displaybus behält genau einen eigenen Nutzen, den die Serielle nicht
bietet: **Code-zu-Glyph-Paare** zur Klärung der Zeichensatz-ROM-Variante
(`°`/`Ω`/`µ`, siehe CLAUDE.md). Skizze bleibt in
[DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md).

### Was noch offen ist — und warum es nicht übersprungen werden darf

1. **Pegel: RS232, nicht TTL.** Klemme B/C führt RS-232-Pegel. Ein direkter
   Anschluss an Pi-GPIO ist unzulässig — das ist wörtlich
   [OQ-09](open-questions.md). Nötig ist ein USB-RS232-Adapter oder ein
   Transceiver.
2. ~~**Ist der ASCII-Modus an diesem Exemplar aktiv?**~~ **Geklärt und
   erledigt 2026-09-22.** Der Modus stand auf `0x00` (Binär); mit Freigabe des
   Nutzers auf `0x02` (Bit 1 = Text-Modus) gesetzt und zurückgelesen. Der
   Strom liefert seither `+0.46776 mV/V<CR><LF>`, **18/18 Zeilen** passen auf
   `^[+-]\d\.\d{5} mV/V$`. Zahlen in [VALIDATION.md](VALIDATION.md).
   **Die Änderung ist persistent** — Rückweg ist `Set Mode` mit gelöschtem
   Bit 1. Fallstrick für Nachahmer: `Get Mode` antwortet mit **zwei** Bytes
   `3B <wert>`; das `0x3B` ist das Semikolon-Präfix, nicht der Wert.
3. ~~**Sind B/C überhaupt nach draussen verdrahtet?**~~ **Geklärt 2026-09-22
   (Nutzerauskunft):** B und C sind angeschlossen und führen auf einen
   RS232-Steckverbinder. Der Abgriff ist damit ohne jeden Eingriff ins Gerät
   erreichbar. Anschlussbelegung und Adapterwahl stehen in
   [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md).
4. **Zeitliche Kopplung Anzeige ↔ Stream ist nicht dokumentiert.** Dass der
   *Inhalt* übereinstimmt, sagt die Anleitung. Dass er zum *selben Zeitpunkt*
   übereinstimmt, sagt sie nicht. **Verschärft durch die Messung:** der Strom
   läuft mit ≈ 2 Hz, die Kamera mit 15 fps — auf einen Messwert kommen rund
   sieben Bilder. Ohne bekannte Zeitkopplung ist nicht entscheidbar, welchem
   der sieben Bilder der Wert gehört. **Muss gemessen werden.**
5. **Die optische Einschwingzeit des LCD bleibt unverändert relevant.** Das
   Glas hinkt jeder Änderung nach; Bilder im Wechselfenster dürfen nicht
   automatisch gelabelt werden, sondern bekommen `label_state="uncertain"`.
   Siehe [DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md), Abschnitt „Der kritische
   Punkt".
6. ~~**`DatasetStore` hat kein Herkunftsmerkmal für Labels.**~~ **Merkmal
   selbst gebaut, 2026-09-22.** `save_sample` verlangt jetzt das
   Pflichtfeld `label_origin` (`"manual"` | `"serial_ascii"`, kein stiller
   `"manual"`-Default bei Fehlen) und bei `"serial_ascii"` ein typgeprüftes
   `label_origin_detail` (`source_port`, `guard_margin_ms`,
   `plateau_start_ns`, `plateau_end_ns`, `telegram_count`). Beide Felder
   gehen in die Unveränderlichkeitsprüfung ein (anderer `label_origin` auf
   denselben `capture_token` → `RevisionConflict`). `relabel_sample` setzt
   beim manuellen Korrigieren die Herkunft auf `"manual"` zurück und
   protokolliert die vorherige Herkunft in `label_history`
   (`previous_label_origin`/`previous_label_origin_detail`) — Details und
   Begründung: [CHANGELOG.md](../CHANGELOG.md) 2026-09-22 („Herkunftsmerkmal
   `label_origin`"), `src/dispread/workbench/datasets.py`
   (`_validate_label_origin`, `_relabel_sample_locked`),
   `tests/test_datasets.py`. **Automatisches Labeln selbst ist damit nicht
   gebaut** — nur die Voraussetzung dafür. Zwei Lücken bleiben offen:
   1. **Migration der Bestandsproben fehlt.** `SAMPLE_SCHEMA_VERSION` ist auf
      2 gestiegen; jede Probe mit `schema_version == 1` (kein
      `label_origin`, das betrifft alle 88 realen Proben unter
      `var/workbench/datasets/`) wird beim Laden jetzt hart abgelehnt
      (`_load_sample_json`, analog zu `_load_devices`). Ein Migrationsschritt,
      der den Bestandsproben nachträglich `label_origin="manual"` zuweist,
      ist nötig, **bevor** der Sammelmodus wieder auf sie zugreift — und ist
      absichtlich nicht Teil dieser Änderung.
   2. **Export gibt die Herkunft noch nicht weiter.** `_export_locked`/
      `manifest.json` (`EXPORT_SCHEMA_VERSION`) kennen `label_origin` noch
      nicht — die Herkunftsspur endet an der Probe und erreicht den
      Benchmark (noch) nicht. Bräuchte eine eigene Schemaversion und einen
      eigenen Test.
* **Abgrenzung:** Betrifft ausschliesslich den Sammelmodus
  (`DatasetStore`/`dataset.capture`/`dataset.save`). Ein so gewonnener Sollwert
  erreicht wie jedes andere Label **nie** `ValueReader`, `ReleaseGate` oder die
  Produktionskette.
* **Nicht in `hardware.conf`:** Der Abgriff ist ein **zweiter, eingehender**
  serieller Pfad (USB-RS232, 38400 8N1) und hat nichts mit `SERIAL_PORT`/
  `SERIAL_BAUD` zu tun — die beschreiben den **ausgehenden** Datenport nach
  GSVmulti (`/dev/ttyAMA0`, Baudrate offen über
  [OQ-01](open-questions.md)). Wer `SERIAL_BAUD=38400` aus der
  GSV-2AS-Anleitung übernimmt, konfiguriert den falschen Pfad. Die Parameter
  des Abgriffs gehören zum Sammelmodus, nicht nach
  `/etc/dispread/hardware.conf`.
* **Verwandt:** [OQ-35](open-questions.md) (dieselbe Frage am BK-5491B),
  [OQ-39](open-questions.md) (was ein Abgriff **nicht** löst),
  [OQ-09](open-questions.md) (Pegel), [OQ-07](open-questions.md) (die
  GSV-2-Anleitung ist zugleich die Quelle, die dort gesucht wurde).
* **Antwort landet in:** [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)
  (Klemmenbelegung, Schnittstellenparameter),
  [DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md) (Rückfallebene),
  `docs/anleitung/11-datensatz-sammeln.md` (falls umgesetzt).

<span id="oq-39"></span>

## OQ-39 — Ziffernabdeckung des GSV-Datensatzes ist durch den festen Stimulus begrenzt

* **Status:** offen · erkannt 2026-09-22 (bei der Machbarkeitsprüfung zu
  OQ-38) · **wesentlich relativiert am selben Tag**, siehe direkt unten
* **Wichtige Einschränkung dieses Eintrags (2026-09-22, Nutzerauskunft beim
  ersten seriellen Mitschnitt):** Der Nutzer hat mitgeteilt, dass er **die
  extern an den Sensor angeschlossenen Stimulatoren bewegt** — im Mitschnitt
  sichtbar als Wanderung der Rohwerte über `B8A95A`…`EF346B`
  ([VALIDATION.md](VALIDATION.md)). Der Stimulus ist also **nicht fest**. Die
  unten festgehaltene Grenze („neue Bilder zeigen nur noch denselben Wert")
  beruhte auf der früheren Angabe, die verklebte DIP-Platine solle nicht
  bewegt werden, und **gilt so nicht mehr**. Was offen bleibt: **welcher
  Anzeigebereich** mit den beweglichen Stimulatoren erreichbar ist —
  insbesondere negative Werte und Werte ab 10 mV/V
  ([OQ-37](open-questions.md)). Erst diese Antwort sagt, wie viel
  Ziffernabdeckung wirklich zu holen ist.
* **Befund:** Der Messgrössengeber am GSV ist eine **Lochrasterplatine mit
  DIP-Schalter** (Fotos `gsv_angeschlossene_platine1/2.jpg`,
  `…_unterseite.jpg`): ein Widerstandsnetz, handschriftlich beschriftet
  „4: 2 mV/V", „3: 1 mV/V". Sie erzeugt also eine Handvoll **diskreter**
  Brückenwerte. Der Nutzer hat am 2026-09-22 mitgeteilt, dass die Platine
  **verklebt** ist, damit sie nicht bewegt wird, und dass sie vorerst nicht
  benutzt werden soll.
* **Warum das zählt:** Auto-Labeling (OQ-38) vervielfacht die **Bilderzahl**,
  nicht die **Ziffernabdeckung**. Steht der Stimulus fest, zeigen alle künftig
  aufgenommenen Bilder denselben Anzeigewert — die Abdeckung bleibt genau die
  der bereits vorhandenen Proben, gleichgültig wie viele Bilder dazukommen.
  Ein Leser lernt keine Ziffer, die er nie an einer Stelle gesehen hat, an der
  sie vorkommen kann.
* **Was der Abgriff trotzdem bringt** — nicht kleinreden, es ist real:
  1. **Exakte Labels für die zappelnden letzten Stellen.** Im Bestand direkt
     sichtbar: der 0.948er-Cluster streut über `0.94801`…`0.94836`, also in
     den letzten beiden Stellen. Bei 15 fps ist das von Hand nicht zuverlässig
     zu labeln, von der Schnittstelle schon.
  2. **Pose-, Licht-, Fokus- und Glanzvielfalt** in beliebiger Menge, bei
     korrektem Label.
  Beides verbessert die Robustheit, keines die Ziffernabdeckung.
* **Was der Datensatz heute abdeckt** (ausgezählt 2026-09-22 über
  `var/workbench/datasets/samples/*/sample.json`, Gerät
  `87564e345aa047338f954c045bc9df02`, alle 11 `label_state="readable"`):

  | Sollwert | Anzahl |
  | --- | --- |
  | `0.00042` | 1 |
  | `0.00045` | 1 |
  | `0.94801` | 2 |
  | `0.94802` | 1 |
  | `0.94804` | 1 |
  | `0.94809` | 1 |
  | `0.94836` | 1 |
  | `1.05000` | 3 |

  Also **drei Cluster**, nicht ein einzelner Wert: Rauschbereich (~0.0004),
  ein Arbeitspunkt bei ~0.948 und `1.05000`. Führende Ziffern werden damit
  durchaus geübt (9, 4, 8 in vorderen Stellen). Durchgängig 6 Ziffern und 5
  Nachkommastellen ([OQ-37](open-questions.md)).

  **Zwei Lücken, die auffallen:**
  * **Kein einziger negativer Wert** — obwohl die Anzeige zum Zeitpunkt der
    Fotoserie auf `-0.00063 mV/V` stand. Die Vorzeichenstelle ist im Datensatz
    also unbelegt.
  * `1.05000` erscheint **dreimal exakt gleich**. **Rechnerisch belegt am
    2026-09-22:** der Vollausschlag dieses Exemplars ist 1,05 mV/V (der
    Binärwert `B8C62C` ergibt bipolar mit diesem Endwert `+0.46573`, und der
    ASCII-Strom zeigt bei gleicher Stimuluslage `+0.46776`). `FFFFFF` — laut
    Anleitung 105 % des Messbereichs — entspricht damit **exakt `+1.05000`**.
    Diese drei Proben sind also sehr wahrscheinlich **Übersteuerung**, nicht
    Messwerte. **Erstmals beobachtet am 2026-09-22:** im 599-s-Mitschnitt
    (Plateau-Statistik, [VALIDATION.md](VALIDATION.md)) erreicht der Wert
    während einer mechanischen Störung des Aufbaus zweimal genau `+1.05000`
    und kehrt danach zurück. Damit ist der Anschlag nicht mehr nur
    rechnerisch hergeleitet, sondern gesehen. Ein Anschlagwert ist kein Abdeckungsgewinn; die nutzbare
    Probenzahl sinkt damit faktisch von 11 auf 8. Endgültig bestätigen liesse
    sich das mit einem Versuch: Stimulus an den Anschlag fahren und prüfen, ob
    die Anzeige auf `1.05000` stehen bleibt.

  Ungemessen bleiben Werte ab 10 und negative Werte. **Negative Werte sind mit
  den vorhandenen Stimulatoren gar nicht erzeugbar** (Nutzerauskunft
  2026-09-22) — die Vorzeichenstelle bleibt unbelegt, solange kein anderer
  Stimulus dazukommt. Eine **Anzeige ab 10** ist mit stärkerem Stimulus
  ebenfalls nicht zu holen: der Vollausschlag dieses Exemplars ist 1,05 mV/V,
  und selbst die höchste Empfindlichkeit des GSV-2 (3,5 mV/V, `Set Range` 50)
  endet bei 3,675. Siehe dazu den Hinweis in [OQ-37](open-questions.md) — über
  den Normierungsfaktor ist es trotzdem erreichbar.

  Wie die drei Cluster zustande kamen, lässt sich aus den Fotos **nicht**
  ablesen: ob der DIP-Schalter vor dem Verkleben umgestellt wurde oder eine
  andere Quelle im Einsatz war, ist unbekannt und wird hier nicht behauptet.
* **Wesentliche Wendung 2026-09-22 (abends) — die Anzeige ist direkt
  steuerbar, der Stimulus muss gar nicht mitspielen.** Zwei Messungen
  desselben Tages zusammen:

  1. **Der bewegte Stimulus taugt nicht.** 1199 s Mitschnitt bei bewegtem
     Stimulus: 217 verschiedene Zeichenketten im Rohstrom, aber nach dem
     Schutzintervall bleiben bei M = 500 ms nur **25** davon übrig, und
     96,3 % der nutzbaren Zeit entfallen auf vier praktisch gleiche Werte.
     Das Gate kostet 44 % der Bilder, aber **88 % der Vielfalt** — die
     Vielfalt steckt in ein bis zwei Telegramme kurzen Ausschlägen, und
     genau die verwirft das Fenster. Das ist strukturell und wird durch
     längeres Aufzeichnen nicht besser.
  2. **Der Normierungsfaktor löst es.** `set norm` (16) plus `set dpoint`
     (17) verändern die Anzeige bei **festem** Stimulus, und der ASCII-Strom
     folgt nachweislich (Verhältnis 1,9963 bei einem Faktorwechsel auf 2,0).
     Jeder so eingestellte Wert steht **beliebig lange** still — Vielfalt und
     Plateaulänge stehen damit nicht mehr im Widerspruch. `EEnow = 0` am
     Gerät gemessen: die Schreibbefehle nutzen das EEPROM nicht ab.

  Damit ist der Kern dieses Eintrags entschärft: Ziffernabdeckung ist nicht
  mehr an den Stimulus gebunden, sondern planbar. Beide Messungen in
  [VALIDATION.md](VALIDATION.md).

  **Was offen bleibt — und es ist der härtere Rest:** **negative Werte.**
  Negative Normierung gibt es erst ab Firmware 1.5.06, dieses Gerät hat
  1.3.07, und die Stimulatoren erzeugen keine negativen Werte. Die
  **Vorzeichenstelle bleibt unbelegt.** Ein Leser, der ein `-` nie gesehen
  hat, ist an dieser Stelle unbelegt geprüft — das gehört an jede
  Benchmarkzahl geschrieben.

  Zweitens bleibt offen, ob eine über die Normierung erzeugte Ziffernfolge
  dieselbe **Bildstatistik** hat wie eine real gemessene. Für den Leser
  zählt, was auf dem Glas steht, und das ist identisch erzeugt — ein
  systematischer Unterschied ist nicht ersichtlich, aber auch nicht gemessen.
* **Wege zu mehr Vielfalt, die die verklebte Platine nicht anfassen**
  (gesammelt, nicht entschieden — die Auswahl ist eine Laborentscheidung):
  * ein **zweiter** Brückensimulator am selben Sensorkabel, steckbar statt
    verklebt;
  * eine echte Kraft-/Wägezelle mit variabler Last;
  * die Tara-/Nulltaste des Geräts (verschiebt die Anzeige, ändert die
    Ziffernfolge);
  * eine andere Verstärkungs-/Bereichseinstellung, falls zugänglich;
  * ein weiteres GSV-Exemplar mit anderem Anzeigezustand.
* **Blockiert:** nichts unmittelbar. Betrifft die Aussagekraft jeder
  Erkennungsgüte-Zahl, die auf dem so vergrösserten Datensatz gemessen wird —
  eine hohe Trefferquote auf 50 000 Bildern derselben drei Werte ist **keine**
  Aussage über die Erkennung im Feld.
* **Nachtrag 2026-09-24, Ernte 1:** 81 Proben aus 31 Zeichenketten
  importiert. Zelle 6 deckt alle zehn Ziffern ab, Zellen 3–5 je neun,
  Zelle 1 acht, Zelle 2 sieben, Zelle 7 fünf (4, 6–9). Vorzeichen weiter nur
  `+`. Tabelle: [VALIDATION.md](VALIDATION.md), 2026-09-24, „Ernte 1".
  Mehr Ernten mit anderen Seeds schliessen die Lücken; offen bleibt die
  Vorzeichenstelle.
* **Verwandt:** [OQ-37](open-questions.md) (Anzeigeformat ab 10 mV/V),
  [OQ-35](open-questions.md) (Baustein 2: Signaleinspeisung, gleiches Problem
  am BK-5491B), [OQ-38](open-questions.md).
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md) (Abdeckungsangabe zu
  jeder Benchmarkzahl), `docs/anleitung/11-datensatz-sammeln.md`.

<span id="oq-40"></span>

## OQ-40 — Schwelle für „Telegrammlücke" im Gate-Labeler ist ungemessen

* **Status:** weitgehend geklärt (2026-10-30: 800 ms aus 74 min Live-Daten, Stundenmessung offen) · erkannt 2026-09-22 beim Bau von `scripts/gate-label.py`
  · **Zuständig:** Labor
* **Frage:** Ab welchem Telegrammabstand gilt ein Lauf gleicher Werte als
  nicht mehr vertrauenswürdig?
* **Warum das zählt:** Fällt ein Telegramm aus, sieht der Strom durchgehend
  aus, obwohl dazwischen ein **anderer** Wert gestanden haben kann, der nie
  ankam. Ein Bild aus dieser Lücke bekäme dann ein falsches Label, das wie
  Wahrheit aussieht — genau die Fehlerart, die dieses Projekt ausschliesst.
  Der Fall tritt auch **an einem echten Wertwechsel** auf: fehlt dort ein
  Telegramm, sieht ein A→B-Übergang harmlos aus, obwohl dazwischen ein
  drittes C gestanden haben kann.
* **Stand der Umsetzung:** `scripts/gate-label.py` prüft beides — Abstände
  innerhalb eines Laufs **und** den Abstand zum nächsten abweichenden
  Telegramm — gegen `--max-gap-ms`. Das Argument hat **bewusst keinen
  Vorgabewert**: eine erfundene Schwelle wäre eine unbelegte Zahl an der
  Stelle, an der es auf Belegbarkeit ankommt.
* **Datenlage:** Über 1125 Telegramme (599 s) gemessen: Abstand min 502 ms,
  p50 553 ms, p95 555 ms, max 562 ms — also sehr eng verteilt, kein einziger
  Ausfall. Das ist ein guter Ausgangspunkt, aber **eine Aufzeichnung ohne
  Ausfälle sagt nichts darüber, wie ein Ausfall aussieht**, wenn er auftritt.
* **Klärung:** Über eine längere Strecke (Stunden) mitschreiben und die
  Abstandsverteilung auf Ausreisser prüfen; zusätzlich unter Last (Kamera
  läuft parallel, USB ausgelastet) messen, weil dort Pufferüberläufe
  wahrscheinlicher sind. Die Schwelle dann aus der gemessenen Verteilung
  ableiten und **vor** der Ernte festschreiben — wie M, aus demselben Grund.
* **Nachtrag 2026-09-23 — gemessen unter Kameralast:** Die Fehlerart ist
  nicht nur der Ausfall, sondern auch der **Stau**. Einmal in 180 s stand der
  ganze Aufzeichnungsprozess 2,4 s still, und danach kamen fünf Telegramme
  mit fast gleichem `t_boot`. Die Werte sind vollständig, ihre Zeitstempel
  aber nicht. Eine reine `--max-gap-ms`-Prüfung fängt die Lücke, **nicht**
  die gestauchten Stempel danach. Nötig ist zusätzlich eine Untergrenze für
  den Abstand, oder alle Telegramme eines Staus werden verworfen. Ausserhalb
  des Staus: p50 533 ms, p95 534 ms (391 Abstände).
* **Nachtrag 2026-09-23, Ursache und Abhilfe:** Der Stau entstand durch
  blockierende Dateischreibvorgänge beim Rückschreiben auf die SD-Karte.
  Behoben durch getrennte Schreibthreads in `sync-record.py`. Unter
  erzwungener Last blieb der serielle Strom exakt (532–534 ms).
  `gate-label.py` lehnt Stösse jetzt über `--min-gap-ms` ab. **Weiter offen:**
  die Werte für `--min-gap-ms` und `--max-gap-ms`. Unter Kameralast liegen
  über 3 Läufe alle Abstände bei 529–536 ms. Eine Stundenmessung fehlt
  noch.
* **Nachtrag 2026-09-24:** In einer 20-min-Sitzung (15 fps, JPEG, ohne
  Last von aussen) liefen bei t ≈ 13,5 min 8 Bilder in die volle
  Warteschlange (60) und wurden verworfen, gezählt und protokolliert; sonst
  `sensor_sequence` lückenlos. Die folgende 15-min-Sitzung blieb ohne
  Verwurf. Der Schreibstau tritt also auch ohne erzwungene Last auf; für
  3,5-min-Ernten unkritisch, für die Stundenmessung zu beachten.
* **Nachtrag 2026-10-30 — 13 Live-Läufe (23./28.10.), Kamera und Leser
  laufend:** 7 813 Telegramme über 4 426 s (≈ 74 min, längster Lauf 990 s).
  Pausen, die die Werkbank selbst auslöst (Werteplan und Vorprüfung, STOP
  −100 ms bis START +1 200 ms), sind getrennt gezählt.
  * **Ungestörter Strom, 7 245 Abstände:** min 506,0, p50 533,1, p95 535,3,
    p99 538,7, max 561,0 ms. Über 600 ms: **0**. Fehlerhafte Telegramme:
    0, `parse_errors` und `dropped_oldest` überall 0.
  * Die extremen Werte treten als Paar auf: 561 + 506 = 2 Perioden. Das
    Gerät taktet also gleichmäßig weiter, nur ein Stempel auf dem Pi kommt
    bis +27,4 ms später.
  * **Pausen, 555 Abstände:** 153 Pausen von 2 133, 2 666 bzw. 3 199 ms
    (4–6 Perioden). Zwischen 600 und 2 100 ms liegt nichts. Direkt nach
    START kommen 27 Abstände von 422–436 ms, offenbar setzt das Gerät seine
    Taktphase neu. Sie liegen im gesperrten Fenster aus Pause und 695 ms
    Schutzzeit.
  * **Folgerung:** Ein einzelner Ausfall ergibt mindestens 2 × 533,3 −
    27,4 ≈ 1 039 ms. Die bisherige Grenze von 1 000 ms in
    `reference_eval.MAX_GAP_NS` und im Lückenzähler des Rekorders erkennt
    ihn also nur mit ≈ 39 ms Abstand. **Umgesetzt 2026-10-30:** 800 ms,
    gemeinsame Konstante. Das lässt nach beiden Seiten ≈ 240 ms Abstand.
    Die Auswertung aller 13 Läufe ist bytegleich zu vorher; ein Test deckt
    den einzelnen Ausfall ab. Für `gate-label.py` bestätigt das die
    vorläufigen 300/800 ms der Ernte.
  * **Weiter offen:**
    * eine Stundenmessung;
    * ein absichtlich erzeugter Ausfall als Gegenprobe;
    * CPU- und USB-Last (wird nicht aufgezeichnet);
    * Bruchstücke beim Wiederanlauf: Der Rekorder verwirft sie ohne
      Protokoll.

    Ohne Ausfall in 7 245 Abständen liegt die Ausfallrate mit 95 % unter
    ≈ 4·10⁻⁴ je Telegramm (Dreierregel). Die Grenze gilt nur für die
    Datenrate 533 ms. Ändert sich die Rate, muss sie neu bestimmt werden.
    Skript: `oq40_telegramm_luecken.py` (Auswertung im Job-Verzeichnis,
    nicht im Repo).
* **Verwandt:** [OQ-38](open-questions.md) (zeitliche Kopplung, M).
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md) und der
  Vorab-Festlegung des Plans
  `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`.

<span id="oq-41"></span>

## OQ-41 — Telegramm und Anzeige unterscheiden sich in der führenden Null

* **Status:** **teilweise geklärt 2026-09-23.** Punkt (a) ist entschieden und
  umgesetzt: Die Null wird vor dem Vergleich aus dem Telegramm entfernt
  (`telegram_to_display_text` in `scripts/gate-label.py`, Plan Festlegung 1).
  (b) und (c) sind offen. · erkannt 2026-09-23 bei der optischen Gegenprobe
  (OQ-38) · **Zuständig:** Entwicklung
* **Befund (gemessen):** Über 15 Normierungsfaktoren (1,0 bis 9000) trägt das
  ASCII-Telegramm eine führende Null, die das Glas **nicht** zeigt. Zum
  Beispiel wird `+01.8290` auf dem Glas zu `+ 1.8290` und `+05487.0` zu
  `+ 5487.0`. Die Zelle bleibt belegt, als leere Zelle. Alle übrigen Zeichen
  und die Punktposition stimmen überein. Zahlen:
  [VALIDATION.md](VALIDATION.md), Eintrag 2026-09-23.
* **Warum das zählt:** Die Vorab-Festlegung 1 des Plans verlangt **exakte
  Zeichenkettengleichheit** zwischen Label und Anzeige. Übernimmt man das
  Telegramm unverändert als Label, trägt **jedes** Bild mit einem Wert ≥ 1
  ein Zeichen, das nicht auf dem Glas steht. Dieses falsche Label sähe aus
  wie Wahrheit.
* **Offen:** (a) Eine Abbildung Telegramm → Anzeige muss vor der Ernte als
  Vorschrift festgeschrieben werden, gegen die gemessenen Fälle. Beobachtet
  ist: eine `0` an Position 1, der eine Ziffer folgt, wird zur leeren Zelle.
  Das ist eine Abbildung und keine Toleranz, Festlegung 1 bleibt bestehen.
  (b) Welches Zeichen das Label für die leere Zelle trägt (Leerzeichen?),
  muss zum Zellenraster des Lesers passen. (c) Negative Werte sind hier
  ungeprüft, weil die Vorzeichenstelle unerreichbar ist (Firmware 1.3.07).
  Sie dürfen nicht stillschweigend mitgemeint sein.
* **Nachtrag 2026-09-24 — zwei unterdrückte Nullen:** Das Telegramm
  `+00988.5 mV/V` (Aufstellung 3, `var/diagnostics/auf3-run`) erscheint auf
  dem Glas als `+  988.5 mV/V`, mit **zwei** Leerzellen. Die bisherige Regel
  (genau eine Null) hätte `+0988.5 mV/V` gelabelt; die Stichprobe vor dem
  Import hat es gefunden, keine importierte Probe war betroffen. Neue Regel
  `gsv2as_leading_zero_v2` in `scripts/gate-label.py`
  (`telegram_to_display_text`) und `scripts/import-harvest.py`
  (`_cell_text_for_telegram`): alle führenden Nullen des Ganzzahlteils werden
  unterdrückt (Label ohne, Zellsoll mit Leerzelle), ausser der letzten Ziffer
  vor dem Punkt. Belegt sind 0, 1 und 2 unterdrückte Nullen; bei 3 oder mehr
  fehlt ein Glasbeleg, solche Bilder werden abgelehnt
  (`fuehrende_nullen_ungeprueft`). Für 0 und 1 Null bleibt der Text wie in v1.
* **Verwandt:** [OQ-37](open-questions.md), [OQ-38](open-questions.md).
* **Antwort landet in:** Plan `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`
  (Vorab-Festlegungen) und `scripts/gate-label.py`.

<span id="oq-42"></span>

## OQ-42 — Wie wird die ROM-Gegenprobe für weitere Aufstellungen belastbar?

* **Status:** offen · erkannt 2026-09-24 beim ersten echten
  Dot-Matrix-Trainingslauf · **Zuständig:** Labor / Entwicklung
* **Frage:** Wie trennt man Rasterversatz, Unschärfe und einen wirklichen
  Zeichenunterschied, bevor die strenge ROM-Gegenprobe gegebenenfalls
  verändert wird?
* **Befund:** Training auf `auf3` + `ernte1` scheitert für acht Zeichen.
  `auf3` verschob sich zwischen Profilbestätigung und Ernte um etwa
  `dx=0,3`, `dy=4,6` Quellpixel; das Profil ist für die Erntebilder
  unbrauchbar. `ernte1` stimmt allein mit dem ROM überein. Nach Ausschluss
  von `auf3` scheitert der Fold mit Training nur auf `auf2` bei vier Zeichen
  um je einen Punkt; `auf2` ist sichtbar weich. Zahlen und Grenzen:
  [VALIDATION.md](VALIDATION.md), Eintrag „Dot-Matrix-Entwicklungsmessung".
* **Vorabdefault:** Strenge ROM-Regel beibehalten; bei Abweichung Exit 3
  ohne Vorlagendatei oder Auswertungsbericht. Kein Nachstellen der
  ROM-Tabelle oder Schwellen anhand der Auswertung.
* **Klärung:** `auf3` mit neu bestätigtem Raster erneut erfassen oder
  nachvollziehbar relabeln, `auf2` anhand der Glasbilder und Punktmuster
  prüfen. Jede Änderung der ROM-Toleranz zuerst als versionierte
  Spezifikationsentscheidung samt Gegenprobe gegen falsch gelabelte
  Zeichen festhalten; danach Stufe 1 neu laufen lassen.
* **Nachtrag 2026-09-25:** Nutzer hat entschieden: `auf3` auf einem
  Erntebild neu bestätigt, Gegenprobe `rom_check_v2` (1 Punkt Toleranz).
  Danach bricht die festgelegte Messung nur noch im Durchgang „Training
  `auf2`+`auf3`" ab (`4`, 3 Punkte neben der Diagonale — Unschärfe). Diagnose
  aller Kombinationen: nie ein falscher Wert, `ernte1`+`auf2` → `auf3` 67
  richtig / 6 abgelehnt, übrige Kombinationen 100 % abgelehnt
  ([VALIDATION.md](VALIDATION.md), 2026-09-25). Weiter offen: mehr scharfe
  Aufstellungen fürs Training; ob die festgelegte Messung Aufstellungen
  unterhalb einer Schärfegrenze aus dem **Training** ausschliessen darf,
  braucht eine Entscheidung vor dem nächsten Lauf.
* **Nachtrag 2026-09-29 (Entscheidung Nutzer):** Die Zulassung zum Training
  wird vor dem Lauf je Gruppe festgestellt: Eine Gruppe trainiert nur, wenn
  sie **für sich allein** alle Klassen enthält und `rom_check_v2` besteht.
  Nicht zugelassene Gruppen bleiben Testgruppe. Umgesetzt als
  `dotmatrix-eval.py loo --train-eligibility rom_per_group`. Toleranz und
  Schwellen bleiben unverändert. Stand vor dem Lauf, je Gruppe gegen das ROM:
  `ernte1`, `sc3`, `sc4` 0 Punkte, `auf2` max. 2, `auf3` max. 5.
  Ergebnis des Laufs: nie ein falscher Wert, aber `sc3` wird mit Training
  auf `ernte1`+`sc4` vollständig abgelehnt. Offen bleibt, wie viele
  Aufstellungen das Training braucht ([VALIDATION.md](VALIDATION.md),
  2026-09-29).
  Mit `sc5` (vier zugelassene Aufstellungen) lesen `sc4` und `sc5`
  vollständig richtig. `sc3` scheitert weiter, Ursache ist ein
  Kontrastgefälle über das Glas, keine Profillage.
  Mit der Normierung `ink_per_cell_v1` (Punkttiefe je Zelle) werden alle vier
  scharfen Aufstellungen vollständig gelesen, ohne falschen Wert. Die Frage
  der Trainingszulassung ist damit beantwortet. Abnahme Stufe 2 am
  2026-09-29: nicht bestanden, 0 falsch (`ab1` 99/99, `ab2` abgelehnt wegen
  einer Spiegelkante in Leerzelle 8).
* **Antwort landet in:**
  [Dot-Matrix-Spec](superpowers/specs/2026-09-24-dotmatrix-reader-design.md),
  [VALIDATION.md](VALIDATION.md), [lab_journal.md](lab_journal.md).

---

<span id="oq-43"></span>

## OQ-43 — Was bedeutet der Zeitstempel der UVC-Kamera: Belichtung oder Pufferempfang?

* **Status:** offen · erkannt 2026-09-25 beim Wechsel auf die Logitech
  StreamCam · **Zuständig:** Entwicklung
* **Befund:** OpenCV liefert je Bild `CAP_PROP_POS_MSEC` = den
  V4L2-Pufferzeitstempel (uvcvideo `clock=CLOCK_MONOTONIC`, Auflösung µs),
  im Test rund 35–40 ms vor Ankunft im Programm. Ob er den
  Belichtungsbeginn, das Belichtungsende oder den Empfang des letzten
  USB-Pakets markiert, ist nicht dokumentiert und nicht gemessen. Bei der
  IMX500 lag `SensorTimestamp` in BOOTTIME (gemessen), die Semantik war
  ebenfalls offen (Messung M2 in [TIMING.md](TIMING.md)).
* **Warum es zählt:** Der Versatz Telegramm ↔ Glas und damit das
  Schutzfenster M beim Gate-Labeling hängen davon ab. Eine Annahme würde M
  verfälschen.
* **Umgang bis zur Klärung:** empirisch abgedeckt. `display-offset.py`
  misst den Gesamtversatz aus Aufnahmen mit wechselnder Normierung, und
  `timing-calibration.py` schreibt M nach
  `var/calibration/timing-streamcam.json`. Ohne diese Datei startet
  `harvest.py` nicht. Der Zeitstempel trägt `semantics=UNKNOWN`.
* **Klärung:** optional über Hardware-Zeitstempel (`uvcvideo hwtimestamps`)
  oder eine LED-Messung mit bekanntem Schaltzeitpunkt. Solange die
  Kalibrierung trägt, nicht nötig.
* **Antwort landet in:** [TIMING.md](TIMING.md), [VALIDATION.md](VALIDATION.md).

---

<span id="oq-44"></span>

## OQ-44 — Wie wird die Freigabesicherung eines Testlaufs im Audit erzwungen?

* **Status:** geklärt · 2026-10-23 · erkannt 2026-10-21 beim seitenweisen Wiki-Abgleich
* **Befund bei Eröffnung:** `LiveService.start_run` kennzeichnet das Übergehen der
  Lesesperre mit `TESTLAUF.json` und `test_run` in `session.json`.
  `LiveSession.step` schreibt jedoch den unveränderten Pipeline-Datensatz
  nach `records.jsonl`, bevor es Leser-Vermutungen ergänzt. Werden spätere
  Bilder lesbar, ist daher auch `VALID` möglich. Die Oberfläche ergänzt
  den Testlauf-Hinweis, unterdrückt einen frischen gültigen Datensatz aber
  nicht. Eine technisch erzwungene Aussage „Testlauf gibt nie Werte frei“
  ist damit nicht belegt.
* **Bisheriger Umgang bis zur Klärung:** Testlaufdaten nicht für Messungen oder als
  Freigabenachweis verwenden. `records.jsonl` immer zusammen mit den
  Laufmarkierungen lesen; ein einzelner `VALID`-Datensatz hebt die
  Lesesperre der Einrichtung nicht auf. Keine Verhaltensänderung während
  des parallel laufenden Hardwareversuchs.
* **Klärung:** Festlegen, ob ein Testlauf bereits vor dem Audit jeden
  gültigen Wert verwerfen muss oder einen eigenen, auch beim Export
  erhaltenen Datensatzstatus braucht; anschließend die gewählte Sicherung
  mit einem Testlauf aus erst unlesbaren und später lesbaren Bildern
  prüfen. Kein neuer Status ohne Prüfung der bestehenden Verträge.
* **Antwort (2026-10-23):** Ein Testlauf zeigt Vermutungen und gibt niemals
  einen Wert frei. `LiveSession.step()` ersetzt jeden vom Gate als `VALID`
  bewerteten Record **vor dem Audit** durch `UNREADABLE`, `value=None` und
  den ersten Ablehnungsgrund `testlauf_keine_freigabe`; weitere Gründe bleiben
  erhalten. Der unterdrückte Record behält `raw_text`, `frames_confirmed`
  und `confirmation_span_ns` der Ablesung als Diagnose, wie andere
  `UNREADABLE`-Records, aber niemals einen Zahlenwert in `value`.
  Es gibt keinen neuen Vertragsstatus. Die getrennte
  Leser-Vermutung zeigt die ursprüngliche Gate-Entscheidung als Diagnose
  (`gate_status`); sie ist kein freigegebener Wert. `session.json` zählt
  erfolgreich auditierte Unterdrückungen als `summary.testlauf_unterdrueckt`.
  Die Seite zeigt Testbanner und Vermutung, niemals einen Testlaufwert als
  gültig. Normale Läufe behalten ihre bisherigen Auditbytes und Statuswerte.
  Tests mit zunächst unlesbaren und später lesbaren Bildern prüfen Audit,
  Status, Ausgabegrenze und Zähler. Der Referenzabgleich lehnt markierte
  Testläufe weiterhin ab und zählt unterdrückte Records auch ohne
  Laufmarkierung nicht als `VALID`. Historische Testläufe mit `VALID` bleiben
  Testdaten und sind keine Messnachweise.
* **Antwort umgesetzt in:** `src/dispread/live/session.py`,
  `src/dispread/workbench/static/live.js`, `src/dispread/workbench/fields.py`,
  `tests/test_live_session.py`, `tests/test_live_service.py`,
  `tests/test_live_reference_eval.py`, `tests/live_client.test.mjs` und
  [Live-Anleitung](anleitung/10-kamera-livevorschau.md).

---

<span id="oq-45"></span>

## OQ-45 — Wie werden monotone Verarbeitungsmarken korrekt als Zeitbasis bezeichnet?

* **Status:** geklärt am 2026-10-23 · erkannt 2026-10-21 beim seitenweisen Wiki-Abgleich
* **Befund:** `Timestamp.now_monotonic()` in `src/dispread/records.py`
  liest `time.monotonic_ns()`, setzt aber `base=SENSOR_BOOTTIME`.
  MONOTONIC und BOOTTIME dürfen nicht ungeprüft gleichgesetzt werden;
  insbesondere nach Suspend unterscheiden sie sich. Außerdem liest
  `Pipeline._build_record()` MONOTONIC, übernimmt für `result_timestamp.base`
  aber ungeprüft die Zeitbasis der Aufnahme. Das passt bei aktuellen
  V4L2-Livebildern, nicht allgemein bei Replay, synthetischen Bildern
  oder BOOTTIME-Aufnahmen. Das sind Bezeichnungslücken im Code, keine
  neu gemessenen Abweichungen eines Hardwarelaufs.
* **Umgang bis zur Klärung (historisch):** Aus diesen Marken keinen belegten
  BOOTTIME-Zeitbezug ableiten. Insbesondere bleiben synthetische
  Aufnahmezeiten ungeeignet für Latenz- und Synchronitätsaussagen.
  Der Live-Vergleich von V4L2-Aufnahmezeiten mit seriellen Referenzzeiten
  benötigt weiterhin den explizit gemessenen Versatz aus `session.json`.
* **Klärung (durchgeführt):** Aufrufer und Zeitdomänen getrennt erfassen, eine passende
  Bezeichnung beziehungsweise explizite Umrechnung wählen und den
  Unterschied nach einem simulierten Suspend absichern. Das bestehende
  Verhalten nicht allein durch Umetikettieren der Dokumentation freigeben.
* **Antwort (2026-10-23):** `TimeBaseKind.HOST_MONOTONIC = "host_monotonic"`
  bezeichnet Host-CLOCK_MONOTONIC bei der Verarbeitung, niemals eine
  Aufnahmezeit. `Timestamp.now_monotonic()` und jede Pipeline-Ergebniszeit
  verwenden diese Basis; `HOST_DEQUEUE` als Semantik bleibt bestehen.
  Die Aufnahmezeit wird unverändert übernommen. `carries_time_information`
  ist für die reale Host-Uhr wahr; daraus folgt keine Latenzaussage über
  synthetische, Datei- oder Replay-Aufnahmen. `to_boottime_ns` verwendet für
  HOST_MONOTONIC und V4L2_MONOTONIC denselben Sessionversatz und lehnt
  fehlende Versätze oder Suspend ab. SENSOR_BOOTTIME bleibt unverändert.
  Altdateien bleiben ohne Migration mit ihren bisherigen Ergebniszeitbasen
  lesbar. Kein Verbraucher vergleicht Ergebnis- und Aufnahmezeit direkt;
  Referenzvergleiche rechnen Aufnahmezeiten explizit nach BOOTTIME um.
* **Antwort umgesetzt in:** `src/dispread/records.py`,
  `src/dispread/pipeline.py`, `tests/test_records.py`,
  `tests/test_live_tracking.py`, `tests/test_live_session.py`
  sowie [TIMING.md](TIMING.md).

<span id="oq-46"></span>

## OQ-46 — Warum scheitert der Live-Rahmenfit trotz korrekter Grobverschiebung?

* **Status:** geklärt · **Erkannt:** 2026-10-28 · **Geklärt:** 2026-10-28 · **Zuständig:** Entwicklung / Labor
* **Blockierte:** Wirksamkeitsnachweis R13-19b am Live-Stoß vom 28.10.; keine Freigabe.
* **Befund:** Offline auf allen 208 Diagnosebildern von
  `live/live-20261028T110248Z/run-01`: 99 zweite Feinversuche, kein
  zusätzlicher Fit (98 Residuen-, 1 Streuungsablehnung).
  Die Grobschätzung findet ungefähr (+11, −4,4) px;
  bei `0012.png` überschreitet ein Inlier mit 0,655465 px die unveränderte
  Maximumgrenze 0,65 px. Eine korrekte Gesamtbewegung allein reicht nicht.
* **Antwort (2026-10-28):** Kleine reale Maßstabsänderungen erzeugen am
  starren Fit ortsabhängige Residuen. Die unabhängige Gehäusemessung
  zeigt etwa 1,0008…1,0015 bzw. 0,9973…0,9984. Entscheidung Leonhard:
  ausschließlich im zweiten Versuch gleichförmigen Maßstab 0,995…1,005
  erlauben; alle anderen Grenzen unverändert. R13-19c gewinnt offline
  98/99 zweite Versuche im ersten Lauf (107→205/208 Fits) und 20/29 im
  Bewegungslauf (3→23/152), 0/196 Fehllesungen, frühere Erfolge und
  DEV 568/568 bitgleich. Verbleibende lokale Fehler werden weiter
  abgelehnt. Der gemeinsame Rahmen-Bias bleibt: bis 5,220583 px im
  konservativen zweiten Fixture-Raster. Median 16–17 ms statt 49 ms,
  Ziel ≤10 ms verfehlt. Klärung der Ursache ist keine neue Abnahme.
  Review 2026-10-28: Auch bei verdeckter oder leerer Anzeige läuft die
  Grobschätzung bei jeder Ablehnung (etwa 25 ms je Bild), obwohl der zweite
  Versuch dann nicht greift; das kostet Bildrate, keine Sicherheit.
  Möglicher nächster Schritt: Grobschätzung kleiner/billiger rechnen.
* **Nachtrag R13-23, Reviewkorrektur (2026-10-30):** Faktor 4 bleibt,
  eigene Phasenkorrelation/Spektralcache entfernt; wieder OpenCV. Das
  Grob-Gate erhält 6 px Fehlertoleranz (gemessener maximaler Vektorfehler
  4,956 px plus Reserve); der zweite Feinversuch erzwingt selbst weiterhin
  20 px/3°/±0,5 %. Kein fester Halbpixel-/Skalierungsversatz als einfache
  Fehlerursache belegt. Schutzband +12 px, kleine Grobausschnitte sauber
  deaktiviert. Reproduzierter Review-Sweep je 285 Fälle: zuerst 9/5 nur alt,
  jetzt **0/0 nur alt, 76/54 nur neu, 0 falsche Quads >1 px**. DEV 568/568
  mit `coarse_retries=0` ist kein Grobnachweis. Keine Cache-Ersparnis in
  der Lösung. Live 205/208 und 23/152 Fits, 0/196 Fehllesungen
  unverändert. Drei AB/BA-Wiederholungen je einem/vier Threads: zweiter
  Durchgang Median 7,255–7,825 ms, gepaart neu/HEAD 0,473–0,533; Ziel
  ≤10 ms hier erreicht, keine Lastgarantie. Details:
  [Validierung](VALIDATION.md#r13-23-grobsuche-2026-10-30),
  [Laborjournal](lab_journal.md#r13-23-grobsuche).
* **Nachtrag R13-24 (2026-10-30):** Der Ähnlichkeitsversuch läuft jetzt
  auch unter 2 px Grobverschiebung, einschließlich gerundetem Offset (0,0).
  `coarse_min_shift_px` entfällt; beim Laden alter Profile wird nur dieses
  bekannte Feld nach Typ-/Endlichkeits-/Nichtnegativprüfung entfernt.
  Ein Default 0 allein würde gespeicherte 2.0-Profile weiter sperren.
  Grobantwort, obere Bewegungsgrenze und sämtliche Feinprüfungen bleiben
  unverändert. Offline mit Leser und Referenz: schräg 101→210/210,
  frontal 39→66/141, insgesamt 499→636/913 Quads und 429→533 Lesewerte,
  0 Fehllesungen, keine verlorenen Fits, frühere Ergebnisse bitgleich.
  Sweep: 3.042 Fälle, 0 nur vorher, 0 falsche Quads >1 px; 192/192
  Verdeckungs-/Leerbildproben weiterhin abgelehnt, obwohl bei Verdeckung
  180 statt 50 zweite Versuche laufen. Keine neue Abnahme; Laufzeit,
  Reproduktion und Grenzen in der
  [Validierung](VALIDATION.md#r13-24-kleiner-versatz-2026-10-30) und im
  [Laborjournal](lab_journal.md#r13-24-kleiner-versatz).
* **Antwort umgesetzt in:** `src/dispread/live/frame_tracking.py`,
  `tests/test_frame_tracking.py`, `scripts/r13-coarse-eval.py`,
  `scripts/r13-coarse-sweep.py`,
  [Validierung](VALIDATION.md#r13-19c-aehnlichkeit-2026-10-28)
  und [Laborjournal](lab_journal.md#r13-19c-aehnlichkeit).

<span id="oq-47"></span>

## OQ-47 — Welcher Windows-COM-Transport trägt UserDefined ohne Altwertnachlauf?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-10-28 bei der Prüfung des GSVmulti-PDFs; zuvor offen (Stand 2026-10-30).

* **Testfreigabe mit Bestätigung seit 2026-11-09 (Nutzerentscheidung), keine
  Abnahme:** Die Brücke gibt echte Werte nach ausdrücklicher Bestätigung je
  Lauf weiter (UART und Netzwerk), nur VALID an COM, Bytes wie UART direkt.
  Ende zu Ende nur auf Linux belegt (pty-Kabel, lokales TLS, Fake-COM); kein
  Windows-Treiber, kein GSVmulti, kein Altwertverhalten geprüft.

* **Live-Prototyp (2026-10-30):** P4-3 hat höchstens einen offenen
  Senderauftrag, verwirft neue Frames bei Stau mit Tx-Beleg und liefert sie
  nicht nach. Begonnene Telegramme werden mit 1 s Gesamtfrist vervollständigt,
  ohne Pufferverwerfen. Schreib-/Threadfehler sperren die Ausgabe bis zum
  nächsten Lauf; keine automatische
  Wiederverbindung. Nur pty/Fakes geprüft, tatsächlicher Transport,
  Treiberpuffer und Altwertanzeige bleiben offen.

* **Prototyp gebaut (2026-10-28):** Der eigenständige Demo-Sender nutzt
  `UserDefinedFormatter` und JSONL-Belege. Reviewkorrektur 2026-10-30:
  vollständige Writes mit 1 s Gesamtfrist, bei Stau nur den nächsten Frame
  verwerfen; Fehler beendet den Lauf, kein Pufferverwerfen/Aufholburst. Nur pty/Fakes
  geprüft. Treiberpuffer, Empfang und Altwertverhalten am Windows-PC bleiben
  nachzuweisen; [Ablauf und Grenzen](GSVMULTI_PROTOCOL.md#windows-test).
* **Befund:** USB-UART und Raw TCP mit Windows-VCOM sind plausible Wege.
  Ein konkreter Ausgang samt Windows-Port, Treiber/Lizenz, Pufferverhalten
  und Wiederanlauf ist für dieses Projekt noch nicht ausgewählt oder
  nachgewiesen. Das nachgereichte
  [Beispiel-ZIP](quellen/GSVmulti_Raspberry_Pi_Beispiele.zip) wurde im
  Quelltext und mit elf Softwareprüfungen untersucht. COM-Schreibfehler
  landen im TCP-Retry, vollständige überlange Zeilen umgehen die
  Größenprüfung, und das Zahlenprofil prüft kein Alter. Die erste Zeile
  jeder Verbindung wird absichtlich verworfen; ein Empfangstimeout nach
  5 s kann auch legitime Pausen unterbrechen.
  [Reproduktionen und Grenzen](GSVMULTI_PROTOCOL.md#beispielcode).
  TCP-Erreichbarkeit allein belegt keinen GSVmulti-Empfang.
* **Update 2026-11-04:** Die Architektur ist gewählt: pro Lauf Netzwerk
  oder UART, beide über dieselbe eigene Windows-Brücke und ein com0com-Portpaar.
  Verbindungsfehler stoppen das lokale Lesen/Audit nicht; Wiederanlauf sendet
  keine historische Zahlenfolge als aktuelle Werte. Software-Prototyp vorhanden,
  DUT-Ausgabe bis zum Windows-Nachweis strukturell gesperrt. Windows-Treiber,
  Kabelmodell/Pinbelegung, Puffernachlauf und GSVmulti-Empfang sind noch nicht
  geprüft. [Betrieb und Nachweisgrenzen](GSVMULTI_PROTOCOL.md#windows-bruecke).
* **Windows-Befund 2026-11-04:** Nutzer bestätigt die signierte com0com-
  Ausgabe; beide Busgeräte `ROOT\COM0COM\0000` und `0001` melden
  `Status: Error`, `ConfigManagerErrorCode: 52`. Die installierte Ausgabe
  startet auf diesem Zielrechner nicht; Microsoft ordnet Code 52 der
  abgelehnten/nicht verifizierbaren Treibersignatur zu. Das ist ein anderer
  Befund als die .NET-Abhängigkeit der GUI. Exaktes Paket und Zertifikat
  wurden hier nicht unabhängig untersucht. [Einrichtungshindernis](GSVMULTI_PROTOCOL.md#com0com-code52).
* **Treiberinventar 2026-11-04:** Beide Geräte melden aktuell
  CM_PROB_UNSIGNED_DRIVER; com0com3.0.0.0/Vyacheslav Frolov, oem234.inf,
  IsSigned=False, Signer leer. Nutzer nennt signiertes ZIP. Offizielles
  Archiv enthält x86-/x64-Installer, ausgewählte EXE noch offen. INF-Katalog
  und CodeIntegrity-Ablehnungsgrund als Nächstes lesen. Keine konkrete
  Katalog-/Zertifikatsursache bewiesen. [Beleg](GSVMULTI_PROTOCOL.md#com0com-code52).
* **Installerwahl geklärt 2026-11-04:** Nutzer bestätigt x86-Signed-EXE.
  Originalpaket-PE-Prüfung bestätigt32-Bit-Treiber darin, x64-Installer enthält
  64-Bit-Treiber. Korrekturschritt ist Installation der x64-Ausgabe, danach
  Geräte-/Paketstatus erneut lesen. Aktuell gebundene Windows-Datei nicht
  binär geprüft, vollständige Code52-Ursache weiter offen. Aktive INF-Abfrage
  scheitert an nicht vorhandener oem234.inf; Ereignisabfrage deshalb nicht
  ausgeführt. Keine Treiberlöschung anhand des alten Namens.
  [Beleg und Nachweisgrenzen](GSVMULTI_PROTOCOL.md#com0com-code52).
* **Folgeinventar 2026-11-04:** Nach x64-Anleitung identische zwei Geräte
  mit CM_PROB_UNSIGNED_DRIVER/oem234.inf/IsSigned=False; Nutzer nennt nur
  .NET-GUI-Warnung. Öffentlicher Installerskriptpfad trennt GUI-/CLI-Wahl
  von Treiberoperationen. Erfolgreicher Treiberwechsel unbewiesen.
  Nächste Diagnose: PnPUtil-Gerätedetails, Treiber-Servicepfad und unabhängige
  CodeIntegrity-Abfrage, keine weitere blinde Neuinstallation.
* **CodeIntegrity-Beleg 2026-11-04:** PnPUtil erkennt CyberCircuits als
  Signierer von oem234.inf, Gerät0000 bleibt Code52/0xC0000428, Dienst Stopped.
  Zweimal3004 zum fehlenden Image-Hash, einmal3076 ausdrücklich Audit/erlaubt.
  Aktiver Datei-/Katalogbestand noch nicht verglichen; keine konkrete Ursache
  oder erfolgreiche Installation daraus ableiten. Nächster Vergleich per
  SHA256/Authenticode. [Beleg](VALIDATION.md#com0com-ci-20261104).
* **Dateivergleich 2026-11-04:** SHA256 der aktiven com0com.sys stimmt exakt
  mit offiziellem x64-Original überein, Authenticode=Valid/CyberCircuits.
  x86-Rest/abweichender Dateiinhalt an diesem Pfad ausgeschlossen. Kernel-
  Zulassung und Katalogzustand bleiben offen; Statusabfrage von Windows-Build,
  Secure Boot und DeviceGuard/HVCI als Nächstes. Keine Richtlinie geändert.
  [Beleg](VALIDATION.md#com0com-ci-20261104).
* **Schutzstatus/Testkandidat 2026-11-04:** Build26200, Secure Boot und
  Speicherintegrität aktiv, CI erzwungen. Originaldatei/Authenticode gültig,
  Kernel-Ladung weiter blockiert; konkrete Regel unisoliert. Vovsoft-verlinkten
  anderen Build statisch geprüft: Christos-Nikolaou-Zertifikat ab2012,
  anderer PE-Inhalt, HVCI/Zulassung nicht geprüft. Genau ein kontrollierter
  normaler Installationsvergleich vorbereitet, ohne Schutzänderung.
  [Quellen/Grenzen](GSVMULTI_PROTOCOL.md#com0com-code52).
* **Teilantwort 2026-11-04:** Nach angeleitetem Vovsoft-Buildwechsel alle
  sechs gemeldeten PnP-Geräte Code0; Paar1 CNCA1=COM5/CNCB1=COM6. Code52
  aktuell überwunden, Öffnen/Byteübertragung und neue Hash-/Schutzstatus-
  Bestätigung stehen aus. Gemeinsame Brücke, TCP und Altwertnachlauf bleiben
  offen. [Antwort/Beleg](VALIDATION.md#com0com-pnp-ok-20261104).
* **Portpaar-Teilantwort 2026-11-04:** Exakte Zeile je Richtung COM5↔COM6
  vom Nutzer bestätigt; SecureBoot/HVCI weiter aktiv, Treiberhash entspricht
  geprüftem Vovsoft-Kandidaten. Lokale Portpaarfunktion auf diesem Zielrechner
  belegt. Windows-Brücke/TCP, Dauerlauf und Altwertnachlauf bleiben offen.
  [Antwort/Beleg](VALIDATION.md#com0com-pair-ok-20261104).
* **Lokaler Windows-Demobeleg 2026-11-04:**600/600 Zahlen und mV/V/Scaling1
  exakt in TXT/TDMS auf COM6 gespeichert. Der lokale Demomodus benutzt COM5,
  umgeht aber Pi/TCP und internen JSONL-/ACK-Austausch; diese Probe folgt.
  Zeitraster nominell, Windows-Zielrate abweichend (OQ-57).
  [Antwort/Beleg](VALIDATION.md#windows-local-demo-20261104-01).
* **Gemeinsamer TCP-Teilbeleg 2026-11-04:** Pi-Publisher regulär beendet,
  600 Quellwerte/600 Angebote/600 passende COM-written-ACKs. Windows-Payloads
  bytegleich, TXT/TDMS jeweils600 exakte Werte in Quellreihenfolge; mV/V,
  Scaling1 und COM6 bestätigt. Keine Verbindungsfehler während der Zahlenfolge;
  Retry-Timeouts nur davor/danach. Vollständiger gültiger Demo-Dateipfad belegt,
  Ungültig-/Altwert-/Puffer-/Abbruchverhalten und UART über gemeinsame Brücke
  bleiben offen. Nominelles Zeitraster, keine Latenz- oder DUT-Freigabe.
  [Antwort/Beleg](VALIDATION.md#tcp-demo-20261104-01).
* **Wiederanlauf-Vorbereitung 2026-11-04:** Bisheriger endlicher Publisher
  wartet pro Wert auf ACK; er simuliert keine weiterlaufende Quelle bei
  Brückenabbruch. Throwaway-Generator mit unabhängiger Erzeugung lokal über
  TCP/Memory-COM geprüft:100 Quellwerte,50 Veröffentlichungen während der
  Unterbrechung, Wiederanlauf19→69 und anschließend bis99. Keine Zwischen-
  historienfolge, keine Windows-/Frischeabnahme. Windows-Prozessunterbrechung
  mit10s Pause vorbereitet, noch nicht gestartet.
  [Beleg/Grenzen](VALIDATION.md#tcp-reconnect-precheck-20261104-01).
* **Prozess-Wiederanlauf 2026-11-04:** Quelle läuft unabhängig weiter,
  gezielter Windows-Brückenprozessabbruch mit10s Pause und neue Instanz.
 510/510 COM-geschriebene Werte exakt in TXT/TDMS, Anzeige ohne Eingriff
  fortgesetzt; erstes neues Angebot entspricht jüngster Veröffentlichung.
  Keine Zwischenhistorie nachgesendet. Frame356 zusätzlich durch Latest-
  Auswahl ersetzt (OQ-58), GSVmulti verdichtet Unterbrechung weiterhin auf
  nominell0,1s. Netz-/Kabel-/Betriebssystem-Neustart nicht geprüft.
  [Antwort/Grenzen](VALIDATION.md#tcp-reconnect-20261104-01).
* **Direkter UART-Teilbeleg 2026-11-04:** Lauf 08 bestätigt nach
  30 s absichtlicher Sendepause ohne physische Trennung eine automatische
  Fortsetzung laut Nutzer; alle gesendeten Zahlen sind aufgezeichnet.
  Kein Kabel-/Prozessneustart und kein Test der gemeinsamen Windows-Brücke.
  Die Pause fehlt im nominellen Messdateiraster (OQ-06/OQ-50).
  [Beleg](VALIDATION.md#uart-demo-20261104-08).
* **Wiederöffnen 2026-11-04:** Lauf 12 endet ohne erfolgreichen
  Empfängerwiederanlauf. Nach Device/Channel Close meldet GSVmulti Fehler
  805306614: Comport already open; Nutzer meldet Abhilfe erst durch
  vollständiges Beenden/Neustarten. Kein Puffernachlaufnachweis möglich.
  Portbesitz gegen internen DLL-Zustand ist in OQ-52 zu trennen.
  [Beleg](VALIDATION.md#uart-demo-20261104-12).
* **Blockiert:** Ende-zu-Ende-Abnahme von P4, nicht den Bau des Formatters.
  OQ-09 behandelt die elektrische Strecke; OQ-06 die Bedeutung ungültiger
  Werte. Hier geht es um die durchgängige Verbindung und ihren Wiederanlauf.
* **Klärung:** Einen Transport festlegen; tatsächliche Portzuordnung und
  Treiberversion sichern. Startreihenfolgen, Leitungsabbruch, Neustarts von
  Sender/Bridge/GSVmulti, begrenzte Puffer und blockierten Empfänger prüfen.
  Neue Verbindung an einer vollständigen Zeile synchronisieren und
  nachweisen, dass keine vor dem Ausfall erfassten Werte als aktuelle
  Messwerte nachgeliefert werden. Das Alter braucht eigene Belege, da das
  einfache Zahlenprofil keinen Aufnahmezeitstempel trägt.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#transport),
  [Hardwareprofil](HARDWARE_PROFILE.md) bei tatsächlicher Anschlusswahl;
  spätere Messbelege in [VALIDATION.md](VALIDATION.md) und
  [Laborjournal](lab_journal.md).


---

<span id="oq-48"></span>

## OQ-48 — Lassen sich ausgefallene Übertragungszeiträume historisch in GSVmulti importieren?

* **Status:** offen · erkannt 2026-11-04 bei der Planung des Wiederanlaufs
* **Befund:** Lokal erkannte, aber nicht an GSVmulti übertragene Werte bleiben
  im Lauf-Audit erhalten. Der Nutzer möchte prüfen, ob sie nachträglich
  übernommen werden können. Das UserDefined-Zahlenprofil besitzt keinen
  definierten Aufnahmezeitstempel. Ein Aufholburst könnte alte Werte als
  aktuelle Messungen erscheinen lassen und ist deshalb kein zulässiger
  historischer Import. Das Handbuch beschreibt Logger-Textdateien und
  TDMS-Import im File Monitor; daraus folgt keine Unterstützung beliebiger
  CSV-Dateien oder das korrekte Übernehmen unserer Zeitbasis in der
  eingesetzten GSVmulti-Version.
* **Blockiert:** einen späteren Historien-Konverter, nicht den lokalen Lauf
  oder die Verbindungserprobung. Bei Kameraausfall nicht erfasste Werte
  können nicht aus dem Audit rekonstruiert werden.
* **Klärung:** Kontrollierten Ausfall erzeugen, gespeicherte Aufnahmen und
  Übertragungsbelege zusammenführen und ein kleines Importbeispiel mit
  ursprünglichen Zeiten und ungültigen Abschnitten prüfen. Ergebnis als
  möglich, eingeschränkt möglich oder nicht nachgewiesen dokumentieren;
  keinen generischen Dateiimport erfinden.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#windows-bruecke),
  späterer Beispielbeleg in [VALIDATION.md](VALIDATION.md) und
  [Laborjournal](lab_journal.md).

---

<span id="oq-49"></span>

## OQ-49 — Wo wird der SSH-taugliche Ein-Befehl-Installer bereitgestellt?

* **Status:** offen · erkannt 2026-11-04 beim ersten Windows-Setup
* **Befund:** Der Nutzer möchte später einen einzigen Befehl für Download,
  Bestandsprüfung, Installation fehlender Komponenten und Einrichtung
  über die geplante TUI/CLI. Der Einstieg muss online/extern abrufbar sein
  und darf kein lokales Repository voraussetzen. Bei SSH bestimmt der
  Zielhost, ob Pi- oder Windows-Komponenten eingerichtet werden.
* **Blockiert:** die Veröffentlichung des späteren Installers, nicht den
  manuellen aktuellen GSVmulti-Test. Noch kein öffentlicher Installer
  oder funktionierender Download-Befehl zugesichert.
* **Klärung:** Hosting/Release-Quelle, stabile Einstiegsadresse, eventuell
  erforderlichen Zugang, versionierte Artefakte und Integritätsprüfung
  wählen. Wiederholtes Ausführen muss vorhandene Komponenten erhalten;
  Einrichtung ohne GUI, Fehler-/Neustartbehandlung und nichtinteraktiven
  Modus für beide Zielplattformen festlegen. Windows-Treiber müssen auf
  Windows eingerichtet werden, nicht auf dem per SSH erreichten Pi.
* **Antwort landet in:** [Geplante Funktionen](../PLANNED_FEATURES.md),
  späterer Installationsplan und [Abhängigkeiten](dependencies.md).


---

<span id="oq-50"></span>

## OQ-50 — Bleiben GSVmulti-Einzelwerte bei Anzeige und Aufzeichnung unverändert?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-11-04 beim ersten sichtbaren UART-Empfang
* **Befund:** Demo 04 sendet eine 0,001-Rampe mit Zielrate 10/s. GSVmulti
  zeigt −0,134500, also keinen gesendeten Einzelwert, bei gezeigten 1 Hz.
  Die Herstelleranleitung S. 34 beschreibt Mittelwertbildung für numerische
  Anzeigen auf vier Anzeigen/s. Das erklärt Zwischenwerte grundsätzlich;
  das konkrete Fenster, die tatsächliche Import-/Zeitachse und die
  unveränderte Aufzeichnung sind damit nicht nachgewiesen.
  [Messbeleg](VALIDATION.md#uart-demo-20261104-04).
* **Teilantwort 2026-11-04:** TXT und TDMS aus Lauf 05 enthalten 420
  unveränderte, lückenlose Rampenwerte der Senderindizes 180–599 einschließlich
  negativ/Null/positiv. Keine Mittelung in diesen gespeicherten Werten,
  Datenreduktion laut TDMS aus. Fehlender Anfang passt zu später Aufnahme;
  genaue Startgrenze unbekannt. Frequenzmetadatum 1 Hz, Wellenformintervall
  ca. 0,102407 s. Exportspanne 42,908590 s gegenüber 42,160910364 s
  Pi-Schreibereignisspanne derselben Werte; keine verifizierte gemeinsame
  Zeitbasis oder Latenzaussage. Sprungtreue und Zeitrekonstruktion bleiben
  offen. [Antwort und Beleg](VALIDATION.md#uart-demo-20261104-05).
* **Weitere Teilantwort 2026-11-04:** Lauf 06 bestätigt Frequency=10 Hz
  und 467 unveränderte Werte (Senderindizes 133–599), ohne Lücken/Duplikate.
  dt mode bleibt `tf`: Die Herstelleranleitung S. 73–74/155 erklärt die
  Berechnung aus Startzeit, Endzeit und Werteanzahl; Formel gegen TDMS
  bestätigt. Das Frequenzfeld bestimmt in diesem Modus nicht das Zeitinkrement.
  Exportspanne 48,198790 s, Pi-Schreibereignisspanne 47,088755820 s
  (HOST_MONOTONIC); tatsächliche Einzelwertzeiten und Ursache der Differenz
  noch offen. Advanced-Einstellungen vor Änderung prüfen, nominelle 0,1 s
  nicht als gemessene Zeit ausgeben. [Beleg](VALIDATION.md#uart-demo-20261104-06).
* **Sprungnachweis 2026-11-04:** Lauf 07 bestätigt alle acht direkten
  Sprünge und Blocklängen (je 50 Werte) in TXT/TDMS. 446 Werte entsprechen
  exakt Senderindizes 154–599; kein zusätzlicher Zwischenwert. Zeitmodus
  `1/f0` und dt=0,1 s sind bestätigt, ausdrücklich nominell. Tatsächliche
  Quellzeitpunkte und Synchronisierung werden damit nicht nachgewiesen;
  bei konstanten Plateaus bleiben kompensierende Verluste/Wiederholungen
  unbeobachtbar. [Antwort und Beleg](VALIDATION.md#uart-demo-20261104-07).
* **Pausenbefund 2026-11-04:** Lauf 08 belegt, dass das nominelle
  Raster die 30-s-Sendepause nicht erhält: letzte/erste Zahl beider Seiten
  stehen im Export 0,1 s auseinander. Sichtbarer Timeout und automatische
  Fortsetzung sind bestätigt; die Datei enthält keine Ungültigmarkierung
  für die Pause. Das nominelle Raster ist daher kein Beleg kontinuierlicher
  gültiger Messung. [Beleg](VALIDATION.md#uart-demo-20261104-08).
* **NaN-Befund 2026-11-04:** Lauf 09 bestätigt dieselbe Zeitverdichtung
  trotz gesendeter %NaN-Marker: keine NaN-Einträge im Messkanal, gültige
  Blöcke 0,1 s auseinander. Der ungültige Zeitraum ist im nominellen Raster
  nicht erhalten. [Beleg](VALIDATION.md#uart-demo-20261104-09).
* **Blockiert:** belastbare Zeitaussagen und vollständige P4-Abnahme.
  Direkte UART-Demo, gespeicherte Rampen- und getestete Sprungtreue sind
  belegt. Keine Senderglättung als Lösung.
* **Klärung:** GSVmulti-Datenfrequenz zur Senderate prüfen, ohne Datenreduktion
  aufzeichnen (Record every value), Einzelwerte gegen das Sendelog vergleichen;
  Vorzeichen, Null und abrupte Sprünge einschließen. Numerische Anzeige und
  gespeicherte Daten getrennt bewerten; keine Latenz aus SYNTHETIC ableiten.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md),
  [VALIDATION](VALIDATION.md#uart-demo-20261104-08) und
  [Laborjournal](lab_journal.md).


---

<span id="oq-51"></span>

## OQ-51 — Erhält Replace Missing Values ungültige Zeiträume bei UserDefined?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-11-04 nach der NaN-Probe
* **Befund:** Lauf 09 sendet 200 %NaN-Telegramme über die vorhandene
  Demo-Policy. Die Aufnahme enthält weder NaN noch einen anderen Fehlwertmarker;
  GSVmulti zeigt Timeout und setzt gültige Zahlen ohne Zeitlücke fort.
  [Messbeleg](VALIDATION.md#uart-demo-20261104-09).
  Die [Herstelleranleitung S. 74](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6.pdf)
  beschreibt Replace Missing values als Empfängeroption, die per Timeout-Zählung
  fehlende Werte mit 1E+300 markiert. Die Funktion ist für UserDefined in dieser
  Installation noch nicht belegt. Das ist keine Spezifikation, diesen Marker
  über unseren Formatter zu senden.
* **Teilantwort 2026-11-04:** Lauf 10 wiederholt alle 700 Payloads aus
  Lauf 09 bytegleich. Replace Missing Values ist laut ausdrücklicher
  Prüfung/Rückmeldung des Nutzers aktiviert. TXT/TDMS enthalten 428 gültige
  Zahlen, aber weder NaN noch 1E+300-/anderen großen Fehlwertmarker; NaN-
  Zeitraum erneut auf 0,1-s-Übergang verdichtet. In dieser Konfiguration
  kein wirksamer Nachweis der Option. Interne Ursache und unterstützter Weg
  bei UserDefined bleiben offen; mit GSVmulti-Entwicklung anhand des
  [Reproduktionsfalls](GSVMULTI_PROTOCOL.md#userdefined-ungueltig-repro) klären.
  [Messbeleg und Antwort](VALIDATION.md#uart-demo-20261104-10).
* **Beleg mit echten Werten 2026-11-11:** Brückenlauf über Netzwerk mit Testfreigabe,
  555 s. Die TDMS enthält genau die 7 389 vom Pi quittierten Werte, ohne Abweichung, mit festem
  äquidistanter Zeitachse (`dt mode = tf`, Handbuch S. 73): GSVmulti zählt Werte statt Zeit.
  Ausgelassene ungültige Abschnitte (längste 6,9 s) verschwinden ohne Zeitlücke. Lücken können
  nur als Wert im Telegramm überleben; Versuche dazu: `windows/bridge/GSVMULTI-VERSUCHE.md`. Eine Änderung an GSVmulti ist unwahrscheinlich (zentrales Kundenprodukt, Leonhard
  2026-11-11). Deshalb zuerst prüfen, ob sich in GSVmulti selbst etwas einstellen lässt; sonst
  Ausgleich auf unserer Seite (fester Sendetakt, Nachberechnung aus Pi-/Windows-Journal).
  [Beleg](quellen/bruecke-testlauf-2026-11-11/README.md).
* **Blockiert:** Erhaltung und sichere Auswertung ungültiger Abschnitte,
  zusammen mit OQ-06; direkte synthetische Zahlenversuche bleiben möglich.
* **Klärung:** Identische NaN-Folge wie Lauf 09 mit ausschließlich dieser
  Empfängeroption aktiviert testen. TXT und TDMS auf Marker, Anzahl und
  Lage prüfen; kurze ungültige Abschnitte vor dem Timeout gesondert beachten.
  Nachweisen, dass kein Marker als gültiger Messwert in die Kalibrierauswertung
  gelangt. Hersteller nennt Einschränkungen für Schwellenwert-Trigger und
  Software-Spezialsensoren; im Test manuelle Aufnahme und ein UserDefined-Kanal.
  Keine allgemeine Zulässigkeit oder Gültigkeitssemantik daraus voraussetzen.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#ungultige-werte),
  [VALIDATION](VALIDATION.md#uart-demo-20261104-10) und
  [Laborjournal](lab_journal.md).


---

<span id="oq-52"></span>

## OQ-52 — Warum scheitert das Wiederöffnen nach Device/Channel Close mit Port bereits offen?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-11-04 beim COM-Wiederanlaufversuch
* **Befund:** GSVmulti 2.03 Pro meldet nach Device Close bzw. Channel Close
  beim erneuten Öffnen Error 805306614 (0x300000F6): Comport requested for
  opening is already open. Nutzer meldet, dass vollständiges Beenden und
  Neustarten von GSVmulti die Verbindung wieder ermöglicht. Screenshot und
  Bericht unter `var/diagnostics/gsvmulti/uart-direct-demo-20261104-12/`.
* **Probe vor Prozessende 2026-11-04:** Externes SerialPort.Open auf COM4
  wird verweigert, während GSVmulti weiter im Fehlerzustand läuft. Ein
  separat eingegebenes finally scheitert im PowerShell-Prompt; Cleanup und
  Vergleich nach vollständigem GSVmulti-Ende werden angeleitet. Portbesitzer
  und Fehlerursache noch nicht bewiesen.
  [Beleg](VALIDATION.md#uart-demo-20261104-12).
* **Vergleich nach Prozessende 2026-11-04:** Dieselbe externe COM4-Probe
  öffnet nach vollständigem Beenden von GSVmulti erfolgreich. Der Vergleich
  spricht für eine mit GSVmulti/Bibliothek verbundene Port-Ressourcenverwaltung;
  tatsächlicher Handle-Besitzer und interne Ursache bleiben unbewiesen.
  Manueller kompletter Neustart ist ein Nutzer-Workaround, keine erfolgreiche
  In-Prozess-Wiederanlaufabnahme. [Antwort und Beleg](VALIDATION.md#uart-demo-20261104-12).
* **Loggingbeleg 2026-11-04:** LogLevel2 wirksam. Gelieferter Logausschnitt
  enthält zweimal0x300000F6 bei GS Vactivate Extended über OpenSession.
  Bereits initial0xFFFFFFFF bei GS Vclear Buffer; Ursache und Zusammenhang
  offen (OQ-55). Keine explizite Close-/Deactivate-Zeile, kein interner
  Cleanup-Nachweis. [Beleg](VALIDATION.md#userdefined-logging-20261104).
* **Add-Channel-Gegenprobe 2026-11-04:** Auch ohne Sessionladen zweimal
  derselbe Aktivierungsfehler, jetzt über AddChannel_v5.vi. Datenrate1 Hz
  statt10 Hz; kein allgemeiner Konfigurationseinfluss ausgeschlossen.
  Vergleichspaket für den vom Nutzer bestätigten direkten Entwicklungskontakt
  vorbereitet. [Beleg](VALIDATION.md#userdefined-addchannel-logging-20261104).
* **Blockiert:** COM-Schließen/Öffnen-Abnahme und nachfolgende Bewertung des
  Puffernachlaufs (OQ-47). Datenpause bei weiter offenem Port ist ein anderer
  bereits geprüfter Fall.
* **Klärung:** Im Fehlerzustand mit weiter laufendem GSVmulti externes
  SerialPort.Open/Dispose auf COM4 prüfen. Erfolg würde gegen einen zu diesem
  Zeitpunkt exklusiv belegten Windows-Port sprechen; verweigerter Zugriff
  beweist noch keinen bestimmten Eigentümerprozess. Danach dieselbe Probe
  bei vollständig beendetem GSVmulti vergleichen. Keine interne DLL-/Treiber-
  Ursache ohne diese Trennung behaupten. Sender muss dafür nicht laufen.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#userdefined-reopen-fehler),
  [VALIDATION](VALIDATION.md#uart-demo-20261104-12) und
  [Laborjournal](lab_journal.md).


---

<span id="oq-53"></span>

## OQ-53 — Wie wird der UserDefined-Zahlenfilter in der Session kodiert und wirksam übernommen?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-11-04 beim UCF-Vergleich von Lauf 13
* **Befund:** Erfolgreiche Session aus Lauf 11: Unit=mV/V, Frequency=10,
  Separator=256. Gelieferte Filter-aus-Session: Unit leer, Frequency=1,
  Separator=0. COM4/115200, Prefix=37, ein Kanal und OpenFlags=1073741824
  sind identisch. Der Versuch änderte somit neben dem beabsichtigten Filter
  auch Rate und Einheit. Die genaue Separator-Kodierung ist nicht belegt;
  sie darf weder als reine Trennzeichenwahl noch als sicher dekodiertes
  Filterbit ausgegeben werden.
* **Teilantwort 2026-11-04:** Korrigierte UCF mit10Hz und mV/V stimmt bis
  auf Separator0 statt256 mit erfolgreicher Lauf-11-UCF überein. Filter aus
  ist im UI bestätigt, allgemeine Bitkodierung weiter unbewiesen. Lauf 14
  bleibt dennoch durchgehend auf Timeout. Positive Gegenprobe15 mit
  Filter ein und byteidentischem Stimulus liest gültige Zahlen wieder.
  A-Präfix mit Filter aus (Lauf16) bleibt ebenfalls durchgehend auf Timeout.
  Keine allgemeine Kodierung oder interne Parserursache daraus bewiesen.
  [Antwort und Beleg](VALIDATION.md#uart-demo-20261104-14).
* **Beleg 2026-11-06 (Windows-Brücke):** Die Session aus dem ersten Windows-
  Testlauf empfing Demo-Werte über das com0com-Paar auf COM8. Sie weicht von
  der Lauf-11-Vorlage nur in `ComNr`, `Name` und `ComNo` ab, plus einem von
  GSVmulti ergänzten `[CopyPaste]`-Abschnitt mit Standardwerten; Separator=256,
  10 Hz und mV/V sind unverändert. Das zeigt, welche Felder ein Portwechsel
  betrifft. Es ist kein Generator-Roundtrip und klärt die Separator-Kodierung
  nicht. [Beleg](quellen/bruecke-testlauf-2026-11-06/README.md).
* **Blockiert:** belastbaren Ein-Variablen-Vergleich des Filtermodus und
  späteres automatisiertes Übernehmen dieser Sessioneinstellung. Die zuvor
  belegte gültige Filter-ein-Konfiguration (OQ-01) bleibt davon unberührt.
* **Klärung:** Bei aktueller Filter-aus-Definition 10 Hz und mV/V wieder
  setzen, unter neuem Namen speichern und UCF erneut vergleichen. UI-Zustand
  und gespeicherte Werte paarweise sichern. Herstellerbeschreibung der
  Session-/DLL-Parameter prüfen; aus einer einzelnen Differenz kein
  allgemeines Bitprotokoll erfinden. Dann erst weiteren Sendevergleich werten.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md),
  [VALIDATION](VALIDATION.md#uart-demo-20261104-14) und
  [Laborjournal](lab_journal.md).

---

<span id="oq-54"></span>

## OQ-54 — Welche GSV-Bibliotheksversionen lädt die getestete Windows-Installation?

* **Status:** geklärt (2026-11-04) · erkannt 2026-11-04 nach UART-Demo16
* **Befund:** GSVmulti2.03 Pro ist nutzerbestätigt; zunächst waren Dateiversionen
  und Pfade geladener GSV-Bibliotheken unbekannt. Das öffentliche MEGSV-SDK
  mit älterem Header war nicht als diese Laufzeitbibliothek identifiziert.
* **Antwort 2026-11-04:** Nutzer liefert Ausgabe von Get-Process mit Module
  und FileVersionInfo. GSVmultichannel.exe2.3.4, MEGSV.dll1.62.0.64
  (ProductVersion1.62.0.0), MEGSV4w32.dll1.20.0.64,
  MEGSV86w32.dll1.48.1.64 und GSV86CAN.dll1.17.7.64. Alle unter
  C:\Program Files\GSV-Multichannel_v2.03, Bibliotheken im Unterordner data.
  [Versionsinventar und Antwort](GSVMULTI_PROTOCOL.md#geladene-gsv-bibliotheken).
* **Grenze:** Nutzergelieferter Prozess-Snapshot, nur nach GSV-Dateinamen
  gefilterte Module. Kein vollständiges DLL-Inventar, keine Hash-Identität,
  Parserzuständigkeit oder Port-Handle-Zuordnung bewiesen. OQ-52/OQ-53 bleiben
  teilweise geklärt, reale DUT-Ausgabe gesperrt.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#geladene-gsv-bibliotheken),
  [Laborjournal](lab_journal.md) und [Status](status.md).

---

<span id="oq-55"></span>

## OQ-55 — Warum meldet die UserDefined-Initialisierung einen Clear-Buffer-Fehler?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-11-04 im LogLevel2-Ausschnitt
* **Befund:** Bei initialem Open Session UserDevice COM4/Input1/Fdata10,000
  meldet GS Vclear Buffer.vi0xFFFFFFFF; später beim Wiederöffnen zweimal
  0x300000F6. Kein Sender aktiv. Ursache und Zusammenhang unbewiesen;
  allgemeines−1 nicht als bestimmter Timeout-/Pufferfehler interpretieren.
* **Blockiert:** Beurteilung des UserDefined-Initialisierungs-/Pufferpfads;
  OQ-52 bleibt teilweise geklärt, echte DUT-Ausgabe gesperrt.
* **Teilantwort 2026-11-04:** Gegenprobe ohne Sessionladen reproduziert
  beide Fehler über AddChannel_v5.vi. Sessionladen ist somit keine notwendige
  Bedingung. Datenrate1 Hz statt10 Hz, keine neue UCF; andere Konfigurations-
  einflüsse nicht isoliert. Ursache und Zusammenhang offen.
  [Antwort und Beleg](VALIDATION.md#userdefined-addchannel-logging-20261104).
* **Klärung:** Mit zuständiger Entwicklung UserDevice-ClearBuffer-Unterstützung
  und tatsächliche Deaktivierungs-/Cleanup-Aufrufe samt Fehlerrückgaben prüfen.
  Nutzer hat direkten Kontakt. Geprüftes Vergleichspaket lokal vorhanden;
  keine weitere gleichartige Wiederholung vorgesehen, kein Versand.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#userdefined-logging-befund),
  [VALIDATION](VALIDATION.md#userdefined-logging-20261104) und
  [Laborjournal](lab_journal.md).

---

<span id="oq-56"></span>

## OQ-56 — Ist direkter USB-CDC-ACM-Betrieb am Pi 5 mit stabiler Versorgung praktikabel?

* **Status:** teilweise geklärt (2026-11-04) · erkannt 2026-11-04 nach Nutzerfrage zu USB statt UART
* **Befund:** Lokaler Modellnachweis Raspberry Pi5 ModelB Rev1.1.
  Hersteller dokumentiert OTG/Peripheral am USB-C-Port und Serial CDC ACM
  über ConfigFS. Microsoft dokumentiert integrierten Usbser-Treiber für
  passend deklarierte CDC-Geräte. Das belegt Machbarkeit, keinen erfolgreichen
  Aufbau. /sys/class/udc aktuell leer; Gadget nicht aktiviert. Bootkonfiguration
  nur gelesen, vorhandenes dwc2-host-Overlay steht unter cm5, nicht pi5.
* **Teilantwort 2026-11-04:** Nutzer nennt X1201 V1.1, lädt über eigenen
  USB-C; Produktion eventuell ohne UPS. Hersteller untersagt zusätzliche
  Versorgung am Pi-USB-C. Normaler PC-Kabelanschluss parallel zur UPS daher
  nicht freigegeben. VBUS-getrennte Datenverbindung ist Kandidat, nicht
  erprobte Lösung. Kernelbausteine vorhanden, configfs gemountet, kein UDC
  aktiv. [Antwort und Umsetzungsskizze](GSVMULTI_PROTOCOL.md#usb-cdc-umsetzung).
* **Offen:** UPS-Modell jetzt nutzerbestätigt; elektrische Trennung der USB-Datenstrecke,
  ausreichende Leistung über
  gewählten Windows-USB-Port bzw. geeignete alternative Versorgung, Datenkabel,
  Windows-Enumeration und GSVmulti-Verhalten. USB-C ist zugleich Stromanschluss;
  normale Pi-USB-A-Ports sind kein direkter Gadget-Anschluss.
* **Blockiert:** belastbare Auswahl dieser optionalen direkten USB-Strecke.
  Aktueller UART-/Netzwerkplan nicht automatisch ersetzt. Für direkten CDC-COM
  wäre kein com0com-Paar nötig, Netzwerkbetrieb braucht weiterhin eigene Lösung.
* **Klärung:** Zuerst Versorgungs-/Verkabelungsplan und Host-Port klären, dann
  getrennten reversiblen Gadget-Test mit synthetischen Telegrammen planen.
  Keine automatische Neuinstallation, Aktivierung oder GPIO-Stromverdrahtung.
  USB löst weder UserDefined-Ungültigsemantik noch belegte GSVmulti-Fehler.
* **Antwort landet in:** [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#usb-cdc-option),
  [Hardwareprofil](HARDWARE_PROFILE.md#usb-gadget-option) und
  [Laborjournal](lab_journal.md).

---

<span id="oq-57"></span>

## OQ-57 — Wie genau hält der lokale Windows-Demosender seine Zielrate ein?

* **Status:** teilweise geklärt (2026-11-04) · erkannt beim vollständigen600er-Windows-Demolog
* **Befund:** Ziel10Hz, tatsächliche Schreibereignisspanne66,1322657 s über
  599 Intervalle, Mittel9,0576059Hz. Alle600 Zahlen in GSVmulti vorhanden,
  nominelle Exportspanne59,9 s. Kein Datenverlust und keine Latenzmessung.
* **Teilantwort 2026-11-04:** send_demo wartet nach Schreib-/Logarbeit
  jeweils1/rate. Deadline-Kompensation fehlt in diesem Hilfssender;
  Windows-Scheduling-/IO-Anteile nicht getrennt gemessen. Capture-Zeitbasis
  SYNTHETIC; Ereignisintervalle stammen aus Windows-HOST_MONOTONIC.
  [Antwort/Beleg](VALIDATION.md#windows-local-demo-20261104-01).
* **Blockiert:** Annahme einer exakt10Hz getakteten lokalen Demoreferenz.
  Blockiert keine gültigen TCP-Demoversuche. QM-Zeitgrenzen bleiben OQ-02;
  nominelle GSVmulti-Zeitachse weiterhin OQ-50.
* **Klärung:** Taktabweichung wiederholt messen und ggf. Demo-Pacing separat
  korrigieren. Für gemeinsame Brücke Quellrate und Pollingrate unterscheiden;
  nächsten TCP-Versuch mit10Hz-Pi-Quelle und100Hz-Windows-Abfrage separat
  auswerten. Kein künstliches Glätten oder nachträgliches Umdeuten von Zeiten.
* **Antwort landet in:** [VALIDATION](VALIDATION.md#windows-local-demo-20261104-01),
  [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md#windows-demo-timing) und
  [Laborjournal](lab_journal.md).

<span id="oq-58"></span>

## OQ-58 — Warum ersetzt die frei laufende TCP-Demo auch außerhalb des Abbruchs einen gültigen Wert?

* **Status:** teilweise geklärt (2026-11-04) · erkannt im TCP-Wiederanlauftest
* **Befund:** Alle600 Quellwerte auditiert;510 Angebote und matching COM-written-
  ACKs sowie510 exakte TXT/TDMS-Werte.89 Zwischenwerte100…188 beim Abbruch
  nicht nachgesendet. Zusätzlich Frame356=+0,056 nie angeboten, obwohl diese
  Stelle nach der Wiederverbindung liegt. Alle Angebote entsprechen den neuesten
  Publish-start/complete-Sequenzgrenzen. Daher Ersatz vor Transportübergabe,
  kein Verlust zwischen COM-Schreiben und GSVmulti-Datei.
* **Offen:** Konkrete zeitliche Folge von Quelle, Poll/ACK und Scheduling am
  Übergang355→357 isolieren; unter welchen Last-/Ratenbedingungen die gewollte
  Latest-Auswahl einzelne gültige Werte ersetzt. Keine verlustfreie Vollfolge
  aus dem Wiederanlaufversuch ableiten. Keine ungepaarten Uhren subtrahieren.
* **Blockiert:** Aussage verlustfreier Weitergabe einer frei laufenden Quelle;
  nicht den belegten synthetischen Prozesswiederanlauf oder den gesperrten Bau
  der Workbench-Ausgabenaht. Keine neue DUT-Freigabe.
* **Antwort landet in:** [VALIDATION](VALIDATION.md#tcp-reconnect-20261104-01),
  [GSVmulti-Transport](GSVMULTI_PROTOCOL.md#windows-bruecke).
* **Beleg:** source-/recording-comparison.json und Originale in
  var/diagnostics/gsvmulti/tcp-reconnect-20261104-01/; bei Übergabe zusätzlich
  versioniertes Belegarchiv unter docs/quellen/.

---

<span id="oq-59"></span>

## OQ-59 — Lässt sich ein Lauf nach Anzeigeverschiebung oder Kamerastoß aus einer Bildaufzeichnung nachberechnen?

* **Status:** offen · erkannt 2026-11-06 aus Leonhards Idee „Nachberechnungsmodus“
* **Befund:** Bewegt sich die Anzeige oder wackelt die Kamera, korrigiert die
  Werkbank heute grob über die Gesamtverschiebung und danach begrenzt per
  ECC-Nachregistrierung („Korrektur läuft“). Reicht das nicht, gibt es bis zur
  Neueinrichtung keine freigegebenen Werte. Die Idee: Das Kamerabild läuft
  als Sicherheitsnetz parallel mit. Bricht die Nachführung ab, wird ohne
  Lücke weiter aufgezeichnet, während die bedienende Person entscheidet. Nach
  dem Lauf liest der Leser die Aufzeichnung neu und schließt die Lücke mit
  neuer Geometrie. Bei „Neu einrichten“ (verwerfen) wird die Aufzeichnung
  gelöscht.
* **Einschätzung 2026-11-06:** machbar als begrenzter Lückenschluss, nicht
  als durchgehende Vollbildaufzeichnung. Vor einer Entscheidung braucht es
  eine Spec und Messungen am Pi 5.
  * **Vollbild dauerhaft ist zu schwer.** Roh 1920×1080 YUYV bei etwa
    27 Bildern/s sind etwa 110 MB/s. Der Pi 5 hat keinen H.264-Hardware-
    Encoder. JPEG mit Qualität ≈ 90 liegt bei etwa 250–400 KB je Vollbild,
    also 7–11 MB/s oder 25–40 GB/h. Das schließt die SD-Karte aus. SSD oder
    USB3 könnten es fassen, aber die Kodierung je Bild konkurriert um CPU mit
    dem Leser. Schon die Vorschau (960 px, bis 15 Bilder/s) wird zum Schutz
    der Messung gedrosselt.
  * **Tragfähige Form:** ein RAM-Ringpuffer der letzten N Sekunden
    (z. B. 10–30 s), nur ein Ausschnitt um das bestätigte Anzeige-Quad. Die
    Anzeige belegt etwa 560×80 px; der Rand muss großzügig sein, damit eine
    verschobene Anzeige im Ausschnitt bleibt. Ablage in Graustufen oder
    verlustfrei. Beginnt ein Trackingverlust, wird der Ringpuffer gesichert
    und weiter aufgezeichnet, bis die Person entscheidet. Wird neu
    eingerichtet, liest der Leser das gesicherte Stück mit dem neuen Quad
    bzw. Profil und füllt die Lücke. Bei „Neu einrichten“ (verwerfen) oder
    „Lauf stoppen“ ohne Nachberechnung wird das Stück verworfen.
  * **Wahrheitsregeln** ([AGENTS.md](../AGENTS.md#nicht-verhandelbar-konzeptmd-7),
    Konzept §7/§8): Nachberechnete Werte stammen vom selben Leser auf
    gespeicherten Pixeln (verlustfrei oder mit validiertem Codec) und tragen
    ihre ursprünglichen Aufnahmezeitstempel samt Zeitbasis. Die Herkunft
    „nachberechnet“ gehört in Audit und Sitzungsmetadaten. Der
    `ValueRecord` hat genau neun Felder (Konzept §8); ein zusätzliches
    Herkunftsfeld geht nur mit einer Konzeptänderung — **offener Punkt**.
    Nachberechnete Werte erreichen GSVmulti nie live, weil die Ausgabe
    absichtlich keinen Nachhol-Burst kennt; sie gehen nur in Laufdatei und
    Exporte. Der Referenzabgleich bleibt zeitstempelbasiert und funktioniert
    auch nachträglich. Keine Glättung, keine Korrektur über die Referenz.
  * **Vorhandene Bausteine:** Bildquelle `replay://`, die Diagnoseaufnahme
    des Laufs (Ablage in `/dev/shm`, Kopie nach Laufende), Einrichtungs-
    vorschlag und Bestätigung. Diese müssten auch auf einem aufgezeichneten
    Standbild arbeiten.
* **Offen:** Messungen vor der Entscheidung:
  * CPU-Last und übersprungene Bilder mit aktivem Ringpuffer,
  * Bytes je Stunde für den gewählten Ausschnitt und Codec,
  * ob der Leser auf gespeicherten Bildern dasselbe liest wie live,
  * wie oft eine Verschiebung die Anzeige aus dem Ausschnitt schiebt.
  Dazu: Herkunftskennzeichnung ohne zehntes `ValueRecord`-Feld oder mit
  Konzeptänderung; Speicherort und Aufräumen über [OQ-60](#oq-60).
* **Blockiert:** den Bau des Nachberechnungsmodus. Nicht die verbesserte
  automatische Korrektur ([OQ-26](#oq-26)) und nicht die heutigen
  Laufende-Optionen.
* **Klärung:** Spec mit Leonhard, danach Messprototyp hinter einem Schalter;
  Entscheidung anhand der vier Messungen.
* **Antwort landet in:** [Werkbank-Spec](superpowers/specs/2026-11-04-werkbank-redesign-design.md#offene-punkte),
  späterer Spec Nachberechnungsmodus, [VALIDATION](VALIDATION.md) und
  [Roadmap](ROADMAP.md#roadmap-schritte).

---

<span id="oq-60"></span>

## OQ-60 — Wie werden Läufe gespeichert, exportiert und wieder aufgeräumt?

* **Status:** offen · erkannt 2026-11-06 aus Leonhards Vorgaben zu Laufende und Speicher
* **Befund:** Heute schreibt jeder Lauf unter `var/live/` ein vollständiges
  JSONL-Audit und `session.json`; Diagnosebilder sind optional (Haken beim
  Laufstart, in `/dev/shm` abgelegt und nach Laufende kopiert). Es gibt eine
  Platzprüfung vor Einrichtung und Laufstart und das manuelle
  `dispread live aufraeumen` mit Vorschau, aber keine automatische Löschung,
  keinen Download aus der Werkbank und keinen wählbaren Speicherort. Der
  Dialog „Anzeige hat sich bewegt“ bietet Weiter beobachten · Lauf stoppen ·
  Neu einrichten; „Neu einrichten“ beendet den Lauf und lässt seine Dateien
  liegen.
* **Vorgaben Leonhard 2026-11-06:**
  * **Laufende bei nicht korrigierbarer Verschiebung:** (a) „Neu einrichten“
    verwirft die bisherige Aufzeichnung, (b) „Lauf stoppen“ behält den Lauf
    zum Speichern, Exportieren/Herunterladen und Ansehen. Das Löschen in (a)
    ist destruktiv und kommt erst mit der Speicherverwaltung; bis dahin bleiben
    die Dateien liegen.
  * **Speicherort:** immer ein gesetzter Standard; überschreibbar, z. B. Logs
    und Diagnosebilder auf SSD oder USB.
  * **Download als Datei** aus der Werkbank: txt, csv, json, GSVmulti-Format
    und frei definierbare Formatierung.
  * **Aufzeichnungsoptionen**, z. B. ob Diagnosebilder mitlaufen (heute schon
    beim Laufstart wählbar).
* **Offen:**
  * Wird jeder Lauf immer gespeichert, auch Testläufe?
  * Wie verhindert man, dass der lokale Speicher langsam vollläuft
    (Aufbewahrungsfrist, Obergrenze, Warnstufen)? Produktion voraussichtlich
    64-GB-SD ohne SSD.
  * Wie finden unerfahrene Nutzer ihre Daten und löschen sie, ohne Profile,
    Einrichtungsdaten oder einen laufenden Lauf zu treffen?
  * Was genau ist das „GSVmulti-Format“ für den Export? Nur, was belegt ist
    (UserDefined-Zahlenstrom bzw. GSVmulti-TXT); kein Protokoll erfinden
    ([OQ-07](#oq-07)). Exporte tragen `provisional` und Zeitbasis mit.
  * Wie wird ein gewählter Speicherort auf SSD/USB geprüft, wenn der
    Datenträger fehlt oder abgerissen ist (vgl. PCIe-Abriss der SSD)?
* **Blockiert:** das destruktive Verwerfen bei „Neu einrichten“, Download und
  Speicherverwaltung in der Werkbank, die Ablage einer Nachberechnungs-
  aufzeichnung ([OQ-59](#oq-59)). Nicht den laufenden Werkbank-Umbau.
* **Klärung:** Spec „Laufablage, Export und Aufbewahrung“ mit Leonhard
  schreiben; vorhandene Platzprüfung und `aufraeumen` als Grundlage nehmen.
* **Antwort landet in:** [Werkbank-Spec](superpowers/specs/2026-11-04-werkbank-redesign-design.md#offene-punkte),
  [Anleitung Kapitel 10](anleitung/10-kamera-livevorschau.md),
  [Roadmap](ROADMAP.md#roadmap-schritte) und [TODO](../TODO.md).

---

<span id="oq-61"></span>

## OQ-61 — Was lebt nur noch im alten Controller und auf der alten Startseite?

* **Status:** offen · erkannt 2026-11-06 mit der Entscheidung zu OP-2
* **Befund:** Der alte Controller (`src/dispread/workbench/controller.py`)
  veröffentlicht dauerhaft mit 5 Hz (alle 0,2 s), auch wenn nur `/live`
  benutzt wird. Leonhard hat am 2026-11-06 entschieden: Controller und alte
  Werkbank-Startseite werden entfernt oder abgeschaltet, sobald die neue
  Werkbank produktionsreif ist — vorher prüfen, dass nichts Wichtiges nur
  dort lebt. Bei einer ersten Durchsicht hängen an Server und Controller
  noch u. a. Datensatz-Sammelmodus samt Export (`dataset.*`,
  `/dataset/exports/…`), Profilbearbeitung (`profile.*`, `layout.*`),
  Einfrieren/ROI/Autofit, Clip-Aufnahme, Terminals im Browser, MJPEG-Stream
  und Anmeldung. Das ist keine vollständige Liste.
* **Offen:** vollständige Bestandsaufnahme: welche Funktion wird noch
  gebraucht, welche hat auf `/live`, in der CLI oder der geplanten TUI einen
  Ersatz, welche fällt weg. Welche Skripte, Tests und Wiki-Seiten hängen an
  der alten Seite. Ob Anmeldung und Terminals bleiben.
* **Blockiert:** das Entfernen von Controller und alter Seite. Nicht den
  Werkbank-Umbau und nicht dessen Abnahme (Aufgabe 13 misst den
  Controller-Verbrauch nur).
* **Klärung:** nach der Produktionsreife der neuen Werkbank die
  Bestandsaufnahme machen, mit Leonhard entscheiden, dann entfernen oder
  abschalten; CHANGELOG und Wiki im selben Commit nachziehen.
* **Antwort landet in:** [Werkbank-Spec OP-2](superpowers/specs/2026-11-04-werkbank-redesign-design.md#offene-punkte),
  [TODO](../TODO.md) und [CHANGELOG](../CHANGELOG.md).


---

<span id="oq-62"></span>

## OQ-62 — Wie wird die Windows-Brücke mit EXE, Verbindungsassistent und GSVmulti-Session eingerichtet?

* **Status:** in Arbeit · erkannt 2026-11-06 bei der Einrichtung auf einem neuen Windows-PC
* **Nutzervorgabe:** Wahl der GSVmulti-Ausgabe in der Werkbank bietet eine
  Verbindungsanleitung. Bevorzugt fertige Windows-EXE, die benötigte Komponenten
  installiert/einrichtet, UART und Netzwerk auswählbar macht und in einer
  einfachen GUI Bereitschaft oder konkrete fehlende Schritte anzeigt (z. B.
  USB-Adapter anschließen). Mögliches alternatives Angebot: ein einziger
  Download-/Ausführungsbefehl für ein Einrichtungsskript. Werkbank oder EXE
  erzeugt möglichst eine passende GSVmulti-Sessiondatei zum Öffnen/Importieren.
* **Ergänzung 2026-11-06, Laufzeit:** Auf dem neuen PC wählte `py -3`
  ausschließlich Visual-Studio-Python 3.7; der Brückenimport scheiterte an
  `enum.StrEnum` (benötigt Python >= 3.11). Die EXE muss ohne vorinstalliertes
  Python und neben alten Versionen funktionieren, ohne diese zu verändern.
  Eine Skriptalternative prüft die Version vor dem Erstellen der Umgebung
  und richtet eine geeignete isolierte Laufzeit automatisch ein. Kein blindes
  Vertrauen auf `py -3` oder PATH. Abnahmefälle: kein Python, nur Python 3.7,
  mehrere vorhandene Versionen; verständliche Hinweise bei gescheiterter
  Einrichtung statt eines Python-Tracebacks.
* **Architekturwahl 2026-11-06:** Leonhard wählt Python-Brückenkern + Qt-GUI
  + Windows-Installer; Online-Downloads bei Einrichtung sind erlaubt.
  [Spezifikation](superpowers/specs/2026-11-06-windows-bruecke-design.md) ist
  am 06.11. freigegeben; [Umsetzungsplan](superpowers/plans/2026-11-06-windows-bruecke.md)
  ist zur Ausführung freigegeben. EXE-GUI und sichtbare Workbench-Anbindung
  bleiben auf Nutzerwunsch Claude vorbehalten. Architekturwahl klärt nicht Treiberzulassung,
  Sessionformat oder produktive Messfreigabe.
* **Umsetzung 2026-11-06:** Verbindungs-/Bereitschaftskern, geschützter
  CredentialStore, COM-Journal und portable Installeradapter sind lokal
  integriert. Native Windows-Provider und Qualifikation fehlen weiterhin;
  EXE-/Workbench-Oberflächen folgen durch Claude gemäß
  [Übergabe](superpowers/handoffs/2026-11-06-windows-bruecke-claude.md).
* **Offen:** Paketierung und Verteilung, benötigte Treiber und virtuelle
  Portpaare, Installation mit den erforderlichen Windows-Rechten, sichere
  Zuordnung/Erkennung von USB- und virtuellen Ports, Netzwerk-Verbindung
  sowie belegte Sessionerzeugung für die unterstützten GSVmulti-Versionen.
  Kein Sessionformat erfinden; OQ-53 enthält die offene Filterkodierung.
  Bestehende Einstellungen dürfen nicht ungeprüft überschrieben werden.
* **Abgrenzung:** OQ-49 beschreibt den Pi-Bootstrap; hier geht es um den
  Windows-Verbindungsassistenten. Die aktuelle Python-ZIP ist ein Prüfwerkzeug,
  kein fertiger Installer. „Verbunden“ oder COM-Schreibbestätigung beweist
  keinen GSVmulti-Empfang und keine Messfreigabe (OQ-47/OQ-06).
* **Klärung:** Nach den laufenden Abnahmearbeiten den Bedienablauf spezifizieren,
  echte Referenz-Sessiondateien und Import-/Öffnen-Verhalten prüfen, dann
  Installation und Erstverbindung auf einem frisch eingerichteten Windows-PC
  einschließlich fehlendem Adapter und Wiederanlauf abnehmen.
* **Antwort landet in:** [Geplante Funktionen](../PLANNED_FEATURES.md),
  [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md) und einer späteren Umsetzungsspec.


---

<span id="oq-63"></span>

## OQ-63 — Warum bleibt nach Displaybewegungen dauerhaft der zweite Nachführfit nötig und wie soll das UI ihn anzeigen?

* **Status:** teilweise geklärt (2026-11-06) · erkannt beim T13-Störlauf
* **Befund:** Nutzer meldet dauerhafte Nachführung. Letzte 8284 Auditbilder
  benötigen alle die zweite Stufe, 6605 Quads akzeptiert. Leser liefert bis
  zum Stopp weiter gültige Werte; kein blockierter Lauf. Der zustandslose
  Tracker prüft stets gegen die feste Referenz. `track.correcting` bedeutet
  aktuell „zweiter Fit verwendet“, nicht „Auftrag noch nicht abgeschlossen“;
  der Viewer erneuert dadurch fortlaufend den Korrektureffekt.
* **Offen:** Welcher konkrete Erstfit-Fehler und welche Bildänderung die
  dauerhafte zweite Stufe verursachen; Diagnosebilder waren aus, X-Hud nicht
  archiviert. UI muss erfolgreichen zweiten Fit, erfolglose Suche und echte
  Störung verständlich unterscheiden. Keine automatische Referenzübernahme
  oder Abschwächung der Akzeptanzregeln ohne gesonderte fachliche Prüfung.
* **Klärung:** Begrenzten Bild-/HUD-Diagnoselauf mit reproduzierten Bewegungen
  aufzeichnen, Erst-/Zweitfit-Gründe vergleichen und UI-Semantik spezifizieren.
  OQ-26 bleibt die allgemeine Hardware-Validierung; OQ-59 betrifft spätere
  Bildaufzeichnung/Nachberechnung.
* **Teilbefund 2026-11-11 (Brückentest, Lauf `live-20261111T103604Z/run-01`):** Ein einzelner nicht starrer
  Rahmenbereich (Glanzlinie der Fase, in der Werkbank Bereich 6) lässt den Erstfit scheitern; 23 von 25 erst
  im Zweitfit angenommenen Diagnosebildern scheiterten im Erstfit an ihm. Das ist ein konkreter Mechanismus für
  „dauerhaft zweiter Fit nötig“. [Bericht](quellen/bruecke-testlauf-2026-11-11/README.md).
* **Diagnose je Bereich seit 2026-11-11 (reine Diagnose):** `last_regions` trägt je Bereich das Residuum zum
  Erst- und Zweitfit (`res1`/`res2`, px, auch Ausreißer und abgelehnte Bilder), `diagnose/images.jsonl` schreibt
  es je Bild mit. Ein Fenster über 300 Bilder meldet einen Bereich als dauerhaft unstimmig, wenn er in ≥ 30 %
  seiner Bilder die Grenze 0,65 px reißt und der Rest im Median < 0,4 px liegt (`run.region_hint`,
  `summary.tracking_region_hint`). Die Werkbank zeigt den Hinweis ruhig im Lauf und markiert den Bereich in der
  Bereichsbearbeitung der Neueinrichtung. Freigabe, Schwellen und Entscheidungen bleiben bitgleich (Tests auf
  den 222 Diagnosebildern). Offen bleibt die Einrichtungsregel, solche Bereiche gar nicht erst zu wählen.
* **Einrichtungsregel und Stilllegung seit 2026-11-11 (TB, Freigabe Leonhard):**
  * *Einrichtung:* Die automatische Auswahl schließt Kandidaten aus, deren Autokorrelationsgipfel flach ist
    (Krümmung < 0,08) **und** deren Lage unter festen Lichtproben (Gamma, Glanz, Hell) um > 0,12 px wandert.
    Kalibriert an 55 Einrichtungen: Die belegt unstimmigen Glanz- und Fasenbereiche aus 103604Z, 122753Z und
    095426Z werden nicht mehr gewählt; alle 53 zuvor geeigneten Einrichtungen bleiben geeignet (≥ 6 Bereiche
    je Achsenseite). Mit den neuen Vorschlägen bestehen offline 221 von 222 Diagnosebildern in 103604Z und in
    122753Z (vorher 113 bzw. 112). Die Laufzeitprüfung bleibt unverändert.
  * *Stilllegung im Lauf:* Reißt ein einzelner Bereich über ein volles Fenster von 300 Bildern in ≥ 50 % die
    Grenze, liegt der Rest im Median < 0,4 px und läuft er mit keinem anderen Bereich gleich, wird er für den
    Rest des Laufs aus der Nachführung genommen. Grenzen: höchstens 3 Bereiche bzw. 15 %, Mindestzahl,
    Streuung und Reserve wie bei der Einrichtung, dazu eine Schutzprobe am Referenzbild (Halbseiten-Bias-Raster,
    kein angenommenes Quad > 1,0 px falsch, höchstens 0,05 px schlechter als vorher; seit dem Review auch mit
    einem weiteren ausfallenden Bereich nicht häufiger oder schwerer gefährlich). Ohne diese Probe wäre die
    Stilllegung unsicher: Im Fixture setzt eine ganze Seite ohne Bereich 2 oder 11 eine 3,5 px falsche Lage
    durch, und nach {0, 5, 15} würde ein Zusatzausfall von 8/16/17/19 gefährlich (1,46 px). Die Probe läuft in
    einem eigenen Prozess (nice 19, an 1080p 31 s CPU, 41 s bis zur Stilllegung). Jede Stilllegung steht in
    `tracking_events.jsonl`, in `summary.tracking_region_hint.deactivated` und additiv in
    `component_versions.locator_regions_disabled`. Offline auf den Diagnosebildern der alten Profile wird
    Bereich 6 stillgelegt (103604Z: 200/222 statt 113/222; 122753Z: 187/222, mit Bereich 1 218/222).
  * *Zweiter Fit:* Auf den Diagnosebildern sinkt die Zahl der Zweitversuche nach der Stilllegung von 134 auf
    52 (103604Z, Bereich 6 aus) bzw. von 143 auf 46 (122753Z, Bereiche 1 und 6 aus). Die UI-Frage zu
    „Korrektur läuft“ bleibt offen.
* **Antwort landet in:** [Laufauswertung](quellen/werkbank-t13-2026-11-06.md),
  [VALIDATION](VALIDATION.md) und einer späteren UI-/Tracking-Spezifikation.


---

<span id="oq-64"></span>

## OQ-64 — Wie findet und koppelt die Windows-Brücke verschiedene Pi über LAN und Tailscale?

* **Status:** in Arbeit · erkannt 2026-11-06 beim Entwurf der Windows-Einrichtung
* **Nutzerauftrag:** automatische Installation sowie Verbindung per UART
  oder Netzwerk ohne fest angenommene Pi-IP; verschiedene Pi und Netze,
  mit und ohne Tailscale und nachvollziehbare Fehlerbehandlung. Download
  während der Ersteinrichtung ist ausdrücklich erlaubt; ein vollständiges
  Offline-Installationspaket ist aktuell keine Pflicht.
* **Codebefund vor v2-Umsetzung:** `OutputPublisher` öffnet für TCP einen Socket mit eigenem
  Port (Vorgabe 5000) ohne TLS oder Anwendungskopplung. Workbench-CLI hat eine
  konkrete Tailscale-Adresse als Host-Vorgabe; PAM-Anmeldung verwendet
  aktuell den Benutzer `me-systeme`. Für einen allgemeinen Geräteeinsatz
  brauchen auch Pi-Dienst, Identität und Erstkonfiguration eine Spezifikation.
  Der bestehende Messgeräte-`device_id` ersetzt keine eindeutige Pi-Identität.
* **Freigegebener Entwurf 2026-11-06:** generische Windows-Anwendung mit
  gebündelter Laufzeit; universeller Installer und getrenntes Verbindungsprofil
  aus der Workbench; stabile Pi-Identität mit überprüfter Kopplung. LAN-Suche
  per DNS-SD/mDNS plus Host-/Adressfallback, optional Tailscale-FQDN; bei
  Adresswechsel erneut finden und Identität prüfen. Verschlüsselter,
  authentifizierter Netzwerkpfad, vorzugsweise am vorhandenen HTTPS-Dienst.
  Keine automatische Auswahl eines anderen Pi oder eines anderen
  Ausgabewegs während eines Laufs.
* **Offen:** erste Netzaufnahme eines noch nicht erreichbaren Pi (OQ-49),
  Vertrauen bei Erstkopplung, SD-Karten-Klone, mehrere Geräte/NICs, IPv6,
  VLAN/Multicast-Sperren und Client-Isolation, Tailscale-Anmeldung/Freigabe,
  Firewalls, Proxy, Zertifikatswechsel und erlaubte Wiederanlaufsemantik.
  Discovery entdeckt Kandidaten; sie ersetzt weder Erreichbarkeit noch
  Identitätsprüfung. Ohne Route zwischen getrennten Netzen kann eine EXE
  keine Verbindung allein durch eine bekannte IP herstellen.
* **Umsetzung 2026-11-06:** Geräteidentität, widerrufbare Kopplung, v2-
  Dienst/Discovery sowie Windows-WSS-/UART-Kern sind lokal integriert.
  Wiederanlauf prüft dieselbe Pi-Identität und neue Lease, ohne Demo-/
  Zahlenwiederholung; Zertifikatswechsel verlangt neue Kopplung. Auswahl
  des konkreten Endpunkts und Erstkonfiguration bleiben App-/Dienstaufgaben.
  Keine reale Zwei-Pi-/Netzwechselabnahme daraus ableiten.
  [Plan](superpowers/plans/2026-11-06-windows-bruecke.md).
* **Klärung:** Freigegebenen Entwurf umsetzen, Kopplungs-,
  Berechtigungs- und Zustandsvertrag spezifizieren. Tests mit zwei Pi,
  DHCP-/Netzwechsel, gesperrtem Multicast, Ausfall/Neustart und falscher
  Identität; Altwerte/Doppelausgabe strukturell verhindern. OQ-62 führt den
  Windows-Installer und OQ-53 die tatsächliche GSVmulti-Sessionkodierung.
* **Quellen:** [PyInstaller: gebündelter Interpreter](https://pyinstaller.org/en/stable/operating-mode.html),
  [Windows-Build erforderlich](https://pyinstaller.org/en/stable/),
  [Pi-Netzerkennung](https://www.raspberrypi.com/documentation/computers/remote-access.html),
  [MagicDNS](https://tailscale.com/docs/features/magicdns),
  [Windows-Treibersignaturen](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/driver-signing),
  [USB-Portmetadaten](https://pyserial.readthedocs.io/en/latest/tools.html).
* **Antwort landet in:** spätere Windows-Brücken-Spezifikation,
  [GSVmulti-Anbindung](GSVMULTI_PROTOCOL.md), [Abhängigkeiten](dependencies.md)
  und [Geplante Funktionen](../PLANNED_FEATURES.md).


---

<span id="oq-65"></span>

## OQ-65 — Wie werden Windows-Releases signiert, aktualisiert und gegen Rückstufung geschützt?

* **Status:** offen · erkannt 2026-11-06 beim Installer-/Updatekern W3
* **Befund:** Der portable Updatekern prüft ein begrenztes, signiertes
  Manifest, Artefakthashes und explizit konfigurierte HTTPS-Herkünfte. Er
  enthält keinen produktiven Vertrauensschlüssel, Release-Host oder nativen
  Deploymentanbieter. Eine gültige Signatur allein legt noch keine aktuelle
  freigegebene Version bzw. erlaubte Rückstufung fest.
* **Offen:** verantwortlicher Release-Kanal, Bereitstellung und Wechsel des
  Vertrauensschlüssels, Behandlung alter signierter Manifeste, Mindestversion
  und ausdrücklich freigegebene Rückkehr zur Vorgängerversion. Die dafür
  nötigen Kanal-/Versionsdaten sind noch nicht festgelegt. Anwendungssignatur
  und Treibersignatur brauchen zusätzlich echte Windows-Nachweise.
* **Grenze:** Ohne diese Provisionierung und Nachweise bleibt der Produkt-
  Release gesperrt. Interne Probe-Installer und Unit-Tests mit Testschlüsseln
  sind kein verteilter Vertrauensanker. Aktive Ausgabe blockiert Updates;
  vorhandene Konfiguration und Audits dürfen nicht still verloren gehen.
* **Antwort landet in:** [Windows-Spec §4](superpowers/specs/2026-11-06-windows-bruecke-design.md#4-installation-und-wiederholung),
  [Abhängigkeiten und Buildgrenzen](dependencies.md#windows-installer-und-updatevertrage);
  im Repository zusätzlich `windows/bridge/README.md` und
  `windows/bridge/src/dispread_bridge_app/updates.py`.


---

<span id="oq-66"></span>

## OQ-66 — Warum wählt der Session-Explorer-Test nach Tastaturfokus gelegentlich den falschen Tag?

* **Status:** geklärt (2026-11-06) · erkannt 2026-11-06 beim Doku-Regressionslauf der Windows-Brücke
* **Beobachtung:** Gesamtlauf `playwright.docs.config.ts`: 90 bestanden,
  ein Fehler in „Session-Dateidownload bleibt bytegleich; Tastatur und
  Wiki-Theme erreichen den Explorer“. Nach Fokus auf das Diagramm erwartet
  der Test den zuletzt gewählten 23.10.2026, 10:00 UTC, der Tooltip zeigt
  stattdessen 28.10.2026, 10:00 UTC. Es handelt sich um Testfixtures, nicht
  um eine Messung. Die Brückenänderungen berühren weder Test noch Explorer-
  Assets; unabhängige Wiederholungen grenzten die Testvorbedingung ein.
* **Eingegrenzt 2026-11-06:** Diagrammfokus übernimmt eine gültige aktuelle
  Auswahl; Tabellen-Fokus und Pointerenter können sie vorher ändern. Der
  bisherige Test prüfte diese Voraussetzung nach Download/Scrollen nicht.
  Die genaue alte Pointerfolge ist nicht aufgezeichnet, ein UI-Fehler ist
  nicht nachgewiesen.
* **Korrektur:** Maus außerhalb parken, gewünschte Tabellensteuerung
  ausdrücklich fokussieren und aktive Zeile prüfen, danach die unveränderten
  Übernahme-/End-/Home-Prüfungen. Drei echte Wiederholungen bestanden;
  unabhängiges Review ohne Befund. Abschließender Gesamtlauf: 91 bestanden
  in 6,7 Minuten. Keine Änderung am Explorer-Oberflächenverhalten.
* **Antwort 2026-11-06:** Die Prüfung braucht eine ausdrücklich kontrollierte
  aktuelle Auswahl vor dem Diagrammfokus. Diese Voraussetzung ist im Test
  hergestellt; die frühere genaue Pointerfolge bleibt unbeobachtet und wird
  nicht als nachgewiesener UI-Fehler ausgegeben.
* **Antwort liegt in:** `tests/docs-site.spec.ts`, Commit `8efe4a7`;
  Prüfzusammenfassung in [Status](status.md).


---

<span id="oq-67"></span>

## OQ-67 — Warum fehlte einmal das written-Ereignis im kombinierten Zustands-/COM-Test?

* **Status:** offen · erkannt 2026-11-06 beim abschließenden Backendtest
* **Beobachtung:** Ein neu erweiterter lokaler TLS-/Fake-COM-Test
  `test_dut_stays_locked_after_successful_pairing` lief nach DUT → Aus → Demo
  beim zusätzlich erwarteten numerischen `written`-Ereignis in sein Zeitlimit.
  Zwischenlauf: 59 bestanden, ein Fehler. DUT-Sperre und öffentliche
  Statusassertionen waren dabei bereits erfüllt. Für diesen ersten Fehler
  fehlen genaue Worker-/Journal-Zustandsdaten; keine Hardwaremessung.
* **Eingrenzung:** Nach fester Zustandsdiagnose fünf isolierte Wiederholungen
  und derselbe 60-Test-Satz bestanden. Daraus folgt keine nachgewiesene
  Ursache oder Produktfehlerfreiheit. Keine Produktionsfrist erhöht und kein
  Worker-/Transportworkaround eingebaut.
* **Prüfgrenze:** Die finale Zustandsregression verwendet eine ausdrücklich
  leere synthetische Demo, ursprüngliche DUT-Leerausgabe bleibt geprüft.
  Numerische Übergaben prüfen die getrennten unveränderten TLS-/Barriere-/
  Latest-Tests. Abschließender betroffener Lauf: 430 bestanden, vier native
  Windows-Gates übersprungen; unabhängige Nachprüfung akzeptiert diese
  Trennung als Zustandsprüfung, nicht als Diagnose des ersten Timeouts.
* **Klärung:** Bei erneuter Reproduktion feste Worker-/Snapshot-/Journal-
  Zustände und Ereignisfolge sichern; bei physischer G1-Abnahme Zustandswechsel
  und numerische Übergaben gemeinsam aufzeichnen. Unklaren COM-Erfolg weder
  wiederholen noch als sicher erfolgreich darstellen.
* **Antwort landet in:** `tests/test_bridge_end_to_end.py` und
  [Claude-Übergabe](superpowers/handoffs/2026-11-06-windows-bruecke-claude.md);
  tatsächliche Windows-/Hardwarebelege später in [VALIDATION](VALIDATION.md).


---

<span id="oq-68"></span>

## OQ-68 — Auf welchem Windows-Rechner wird der Installer der Brücke automatisch gebaut?

* **Status:** offen · erkannt 2026-11-11 beim Testbau für den Brückentest
* **Befund:** Der Testbau ist für den Bediener zu umständlich und hat viele
  Bruchstellen: Branch in Forgejo wählen, ZIP laden und entpacken,
  Skriptordner suchen, ExecutionPolicy umgehen, 3–4 min Build, EXE suchen.
  Die EXE lässt sich nur unter Windows bauen; der Pi kann das nicht
  übernehmen.
* **Offen:** Gibt es einen Windows-Rechner, der dauerhaft im Labornetz
  erreichbar ist und als Forgejo-Runner `Setup.exe` bei Tag/Merge baut und
  als Release-Anhang ablegt? Wer betreut ihn?
* **Ziel danach:** Die Werkbank bietet im Brücken-Dialog Schritt 1 genau
  den zum Pi-Stand passenden Installer an; die App meldet beim Verbinden,
  wenn sie veraltet ist. Übergang bis dahin: `build.cmd` als
  Doppelklick-Starter. Signatur und Updatekanal: [OQ-65](#oq-65).
* **Antwort landet in:** `TODO.md` (Abschnitt „Danach offen (Brücke)“),
  `windows/bridge/README.md`.

---

<span id="oq-69"></span>

## OQ-69 — Warum findet die Rastersuche im lesbaren Einrichtungsbild keine Startlage?

* **Status:** offen (2026-11-11) · **Priorität:** kritisch, Workbench-Blocker
* **Befund:** Einrichtung `live-20261111T154459Z` im laufenden Worktree
  `bruecke-run` auf `08ac9b9`: Fokus und Belichtung abgeschlossen, danach
  alle drei Startversuche `keine_startlage`. Das gespeicherte Bild zeigt
  eine scharfe, ausreichend große, leicht gedrehte GSV-2AS-Anzeige mit Plus.
  `fit_lattice` reproduziert den Fehler offline mit der automatisch gefundenen
  grünen Hinweisbox. Es entsteht kein Einrichtungsvorschlag.
* **Offen:** Welche Startkandidaten oder nachfolgenden Prüfungen verwerfen
  diese Geometrie? Die pauschale Empfehlung „näher heran“ ist durch das Bild
  nicht belegt. Ein Zusammenhang mit der Windows-EXE ist nicht erkennbar;
  der Abbruch liegt vor der Ausgabe.
* **Belege:** lokal `var/live/live-20261111T154459Z/setup/` mit `still.png`,
  `failure.json`, `cell-text.json` und `camera-settings.json`.
* **Eingrenzung 2026-11-11:** Erster Suchdurchgang erzeugt 1.274 Punktkandidaten,
  wählt einen Plus-Anker bei (484,89; 553,56) außerhalb der grünen Anzeige und
  verwirft alle 32 verfeinerten Kandidaten (7 `plus_nicht_gefunden`,
  23 `leerzelle_belegt`, 2 `zu_wenige_punkte`). Engere Hinweisbox sowie
  reine Offline-Versuche mit auf die Grünkontur begrenzten Plus-Ankern
  reichen nicht zur Behebung. Kein Beleg für eine einzelne bereits gefundene
  Korrektur; keine Schranke geändert oder Rastersicherheit umgangen.
  Diagnosekopie: `var/diagnostics/raster-20261111-live-154459Z/`.
* **Sicherung 2026-11-11:** [Belegpaket mit Quellcode und Offline-Rezept](quellen/setup-failures-2026-11-11.md).
  Zusätzlich `live-20261111T154403Z` (drei Mal `startlage_mehrdeutig`) und
  `live-20261111T155404Z` (erster Fit `keine_startlage`, danach Abbruch)
  gesichert. Alle drei erhaltenen Fehlerbilder liefern auf dem archivierten
  Quellstand erneut ihre protokollierten Ablehnungen. Der Rastererfolg in der
  anderen Aufstellung ist ein gesonderter Vergleichsfall; sein Nachführfehler
  steht unter [OQ-70](#oq-70). Frühere Einzelbilder und Rohstapel fehlen;
  Grenzen der Reproduzierbarkeit sind im Belegpaket ausdrücklich beschrieben.
* **Weitere Aufstellung 2026-11-11:** `live-20261111T162902Z` ebenfalls drei
  Mal `keine_startlage`; [eigenes Standalone-Paket und Claude-Übergabe](quellen/setup-new-position-2026-11-11-162902.md).
  Letztes Originalbild, alle vorhandenen Einstellungen/Texte/Fehler,
  Quellstand und Offline-Rezept gesichert. Fokusfenster und grüne
  Hinweisbox überschneiden sich im gespeicherten Bild nicht (OQ-74).
* **Zwischenstand 2026-11-13:** A1 berücksichtigt Randminima nahe der
  Nachbarzelle gesondert; die unabhängige automatische Startsuche blieb
  in diesem Schritt offen. Bei `115232Z/still-versuch-1` liefert die Unterkanten-Houghlinie
  0,0712 gegenüber 0,0217 oben; ein Ansatz vom Folgebild-Quad kann
  dagegen verfeinert werden. Das Folgebild ist nur ein Geometrieanker,
  sein serieller Maskentext enthält `?`. Belege und Offline-Auswertung:
  [Rasterrecherche](quellen/raster-recherche-2026-11-13/README.md).
* **Nachtrag 2026-11-13:** Eine alternative Unterkantenrichtung wird nach
  drei erfolglosen Startdurchläufen zusätzlich gesucht; bestehende Fits und
  andere Ablehnungen bleiben unberührt. Die zwei Problemaufnahmen liefern
  damit in gezielten Tests einen Fit nahe den jeweiligen Vergleichsquads;
  Bewegung zwischen Aufnahmen bleibt möglich. Im Offline-Korpus ergeben
  B1 und A1+B1 66/74 bzw. 72/74 Fits; alle Baselinefits bleiben erhalten.
  Drei Zusatzfits gegenüber A1 wurden einzeln geprüft; `130253Z/still`
  behält dabei eine Offsetwarnung. Ein bestehender Fit wird nicht auf
  konkurrierende Alternativhypothesen geprüft. Korpusprüfung und Ergebnisse: [Rasterrecherche](quellen/raster-recherche-2026-11-13/README.md).
* **Antwort landet in:** `src/dispread/dotlattice.py`, zugehörigen
  Regressionstests und [Validierung](VALIDATION.md).

<span id="oq-70"></span>

## OQ-70 — Warum scheitert die Einrichtung trotz gültigem Raster an den Nachführbereichen?

* **Status:** teilweise geklärt (2026-11-12) · **Priorität:** kritisch, Workbench-Blocker
* **Befund:** Nutzer meldet nach anderer Aufstellung erneut eine gescheiterte
  Einrichtung. `live-20261111T155557Z` hat einen Vorschlag mit Raster,
  Rasterversatz und Gegenlesen jeweils `OK`, aber `nachfuehrung=FEHLER`:
  „rahmenbereiche nicht ausreichend verteilt“. Der gesicherte Vorschlag ist
  bereits manuell bearbeitet; die ursprüngliche automatische Auswahl ist
  nicht als eigene Vorschlagsrevision gespeichert.
* **Offen:** Liegt die unzureichende Verteilung an fehlender nutzbarer
  Bildstruktur, Bandermittlung, Auswahlstrategie oder Bedienung? Gültiges
  Raster und erfolgreiche einzelne Bereichsprüfungen ersetzen die räumliche
  Verteilung und Reserve nicht. Keine Grenzen allein zum Durchlassen ändern.
* **Belege:** vollständige vorhandene Setup-Dateien, Bereichsänderungsliste,
  Kameraregler und Live-Status im [Belegpaket](quellen/setup-failures-2026-11-11.md).
  Acht ursprüngliche Stabilitäts-Einzelbilder wurden nicht auf Platte
  gespeichert; Zweitmittelbild und ursprüngliche Prüfkennzahlen sind vorhanden.
* **Antwort landet in:** `src/dispread/live/frame_tracking.py`,
  `src/dispread/live/setup.py`, Regressionstests und [Validierung](VALIDATION.md).
* **Ursache (2026-11-12, offline belegt):** Schon der automatische Vorschlag ist einseitig,
  `[[2,7],[12,7]]` (Seiten −x, −y / +x, +y), keine Reserve. Die Bedienung ist nicht die Ursache.
  Das Raumlicht hellt die untere rechte Fase auf. Sie fällt aus der dunklen Rahmenkomponente
  heraus und hinterlässt eine Kerbe (Tiefe 46 px bei (954,690)). Die Solidität sinkt dadurch
  auf 0,9605 < 0,97, und die Bandermittlung fällt auf das feste Band zurück. Bei diesem kleinen
  Quad (548 px) reicht das feste Band links nur von x ≈ 600 bis 654. Dort liegen nur die
  Glasecken; die Fasenstruktur bei x ≈ 575 liegt außerhalb. Die Eckenschwelle im festen Band
  (2 % des Maximums der Glaskanten) lässt die schwache Fasentextur ohnehin nicht zu. Ein
  breiteres festes Band hilft nachweislich nicht (Endrand 140 statt 100 px: −x bleibt 2).
* **Umgesetzt 2026-11-12 (Branch `fix/blocker-oq70`):**
  * Die Soliditätsgrenze 0,97 bleibt. Unterschreitet eine Komponente sie, wird die
    Rahmenkontur je Quadseite aus Strahlen gemessen: alle ≤ 4 px eine Normale nach außen,
    Austritt aus der gefüllten Kontur. Das 0,75-Quantil je Seite (`bezel_notch_quantile`, nur
    Einrichtung) ergibt eine quadparallele Kontur.
  * Liegt außerhalb dieser Kontur eine Fläche, die ein ganzes Such- und Patchfenster
    (41 × 41 px) trägt, bleibt es beim Rückfall `rahmenform_unplausibel`. Das betrifft
    Balken, Kabel und Schatten. Sonst gilt die Komponente innerhalb der Kontur als Rahmen,
    und die Kerbe bleibt außerhalb des Bandes. Kennzahl: `band_kerbe_kontur_px`.
  * `155557Z` ergibt jetzt `[[9,10],[10,10]]` mit Reserve.
  * Auf 63 Einrichtungsbildern ändert sich das Urteil nur bei den drei bisherigen
    Rückfällen mit Kerbe: `155557Z`, `124851Z` (vorher `[[6,12],[10,7]]`, jetzt
    `[[10,10],[10,10]]`) und `20261028T150539Z`. Alle übrigen 60 Vorschläge bleiben
    bitgleich, auch die vier Review-Balken (60/90 px an `124226Z`/`172340Z`). Diese
    fallen weiter zurück, ohne Bereich auf dem Balken.
  * Die Laufprüfung ist unverändert, und das neue Feld bindet keinen Laufstart.
  * Bleibt ein Vorschlag einseitig, nennt die Einrichtung jetzt „nachfuehrbereiche zu
    einseitig verteilt; Kamera leicht drehen oder verschieben und neu einrichten“.
* **Offen:**
  * Am echten Aufbau ist das nicht erprobt.
  * Die Stabilität ist nur mit dem gespeicherten Zweitmittelbild nachgerechnet, nicht mit
    acht Einzelbildern.
  * Ein dunkler Gegenstand, der mehr als ein Viertel einer Rahmenseite außen anliegt,
    verschiebt das Quantil und zählt dann als Rahmen. Das entspricht der bisherigen
    Annahme für Komponenten mit Solidität ≥ 0,97.

<span id="oq-71"></span>

## OQ-71 — Wie kann ein fehlerhafter Einrichtungsvorschlag abgebrochen oder neu gestartet werden?

* **Status:** offen (2026-11-11) · **Priorität:** hoch, Bedienablauf blockiert · **Priorität:** kritisch, Workbench-Blocker
* **Bedienermeldung:** Bei der aktuellen Einrichtung wird Bestätigen angeboten,
  der Server lehnt den fehlerhaften Vorschlag korrekt ab. Danach fehlen
  Abbrechen und Neu einrichten. Die Meldung gehört zum Zustand
  `setup_ready` mit `setup.overall=FEHLER`, nicht zu `setup_failed`.
* **Codebefund auf `08ac9b9`:** `live/shell.js:titleActions` bietet in
  `setup_ready` nur Bestätigen. `setup/confirm.js:fieldsReady` berücksichtigt
  das Fehlerurteil nicht. `LiveService.confirm` lehnt `FEHLER` ab;
  `cancel_setup` akzeptiert ausschließlich `setup_running`. Ein zusätzlicher
  Abbrechen-Knopf allein würde deshalb noch keinen vollständigen Ausweg bieten.
* **Erforderliche Korrektur:** Fehlerhafte Vorschläge im Browser nicht als
  bestätigbar darstellen; Vorschlag verwerfen und Neueinrichtung erreichbar
  machen, mit passender Zustandsbehandlung im Backend. Dabei Diagnosebelege
  erhalten, laufende Einrichtung/Laufzustände korrekt sperren und die
  Ablehnung fehlerhafter Messfreigaben beibehalten. Regressionsprüfung mit
  `setup_ready + FEHLER` vor und nach abgelehnter Bestätigung sowie mit
  `OK`/`WARNUNG` und laufender Einrichtung.
* **Beleg und Einstieg:** [Belegpaket](quellen/setup-failures-2026-11-11.md),
  gesicherter Vorschlag `live-20261111T155557Z`, Nutzerbeobachtung dieser Session.
  Offline mit tatsächlichen UI-Funktionen und Service-Vorbedingungen
  reproduziert (`replay.py --ui`): nur Bestätigen aktiv, beide Aktionen
  abgelehnt, Zustand bleibt `setup_ready`. Kein Browser-/Hardwarelauf.
* **Antwort landet in:** `src/dispread/workbench/static/live/shell.js`,
  `setup/confirm.js`, `src/dispread/live/service.py` und UI-/API-Regressionstests.

* **Ergänzung nach Nutzerklärung 2026-11-11:** Auch nach erfolgreicher
  Bestätigung fehlt direktes „Neu einrichten“. Nutzer musste erst einen
  Lauf starten und stoppen, um eine neue Aufstellung einrichten zu können
  (`165234Z/run-01`). Das ist der Bedien-Umweg, kein zusätzlicher bewiesener
  Lauf-/Trackingfehler (OQ-76 geklärt). Abbruch bei fehlerhaftem Vorschlag
  und direkter Neueinstieg nach Bestätigung müssen beide funktionieren.
* **Umgesetzt 2026-11-12 (Branch `fix/blocker-oq71`, gemergt in `feat/bruecke-ui`):**
  * Bei FEHLER ist Bestätigen gesperrt, für Knopf und Enter; der Grund steht sichtbar daneben.
  * „Neu einrichten“ ist aus dem Vorschlag und nach der Bestätigung erreichbar, nach der Bestätigung mit Rückfrage.
  * Die Belege der verworfenen Einrichtung bleiben erhalten; der Setup-Ordner ist bei Starts in derselben Sekunde eindeutig.
  * Am echten Aufbau ist das noch nicht erprobt.

<span id="oq-72"></span>

## OQ-72 — Warum lehnt die Kantenprüfung die letzte Ziffer der neuen Aufstellung ab?

* **Status:** offen (2026-11-11) · **Priorität:** kritisch, Workbench-Blocker
* **Befund:** Nach dem ausdrücklich beauftragten Workbench-Neustart scheitert
  `live-20261111T161702Z` in der Vorprüfung: `kanten (Zelle 7)`; Stabilitätsprüfung
  nicht gestartet. Fokus und Belichtung abgeschlossen. Erster Rasterversuch
  `keine_startlage`, zweiter `ok`. Die Kantenprüfung untersucht Helligkeitsstufen,
  nicht ausschließlich Fokus oder Bildschärfe. Der Zellindex 7 bezeichnet
  die letzte Zahlzelle des angezeigten Texts `+0.69551`.
* **Offen:** Tatsächliche Reflex-/Helligkeitskante, Geometrie-/Entzerrungseffekt
  oder Fehlalarm der Vorprüfung? Die Rastererfolge ersetzen die Vorprüfung
  nicht; deren Grenzen nicht ohne positiven und negativen Beleg lockern.
* **Belege:** Standbild, Kameraregler, Zellentexte, Fehler und Status unter
  `var/diagnostics/setup-followup-20261111/live-20261111T161702Z/`.
  Wiederholung `live-20261111T161955Z` mit demselben Abbruch ebenfalls
  gesichert. [Zusatzarchiv und Offline-Rezept](quellen/setup-followup-2026-11-11.md).
  Erster Fall offline reproduziert: Raster `ok`, belegte Zelle 7 mit
  Helligkeitsschritt 29,8053 gegenüber Fehlergrenze 20.
* **Antwort landet in:** `src/dispread/setup_checks.py`, Regressionstests
  und [Validierung](VALIDATION.md).

* **Zusatz 2026-11-11:** Neuester Fall `170836Z`: erster Rasterfit OK; Kanten-FEHLER in Leerzellen 14/15, keine Stabilitätsmessung. Anderer Zelltyp als Zelle 7; getrennt prüfen.
  [Originale und Rezept](quellen/setup-focus-failure-2026-11-11-170836.md).
* **Befund und Teilbehebung 2026-11-12 (Branch `fix/blocker-oq72`):**
  * **Was die Prüfung schützt:** `_edge_check` (`setup_checks.py`) misst Helligkeitsstufen des Glases über 8 px, in
    Leerzellen auf einer Grauwert-Schließung, in belegten Zellen auf einer oberen Helligkeitshülle. Gemeint sind
    Spiegelkanten wie `ab2` (2026-09-29): ein Reflex- oder Schattenrand in einer Zelle, an dem die Hintergrundschätzung
    des Lesers kippen kann. In Leerzellen 13–15 droht dann `leerzelle_gestoert`, also Ablehnung, in Zahlzellen eine
    falsch normierte Glyphe.
  * **`161702Z`/`161955Z` Zelle 7: echter Reflex, Grund (a).** Im Bild liegen ein Glanzfleck rechts oben neben der
    „1“ (Glas etwa 132 statt 107) und eine hellere Glasfläche ab der Grenze Zelle 7/8. Die Stufe 29,8 setzt sich aus
    diesem Reflex und einem Strukturanteil zusammen. Der Strukturanteil entsteht, weil die Hülle einer Ziffer vor der
    leeren Trennzelle ansteigt. Er erreicht auch bei guten Aufstellungen 14–15 (`164508Z`, `165234Z`, `165754Z`).
    Glyphenrobuste Gegenmaße trennen schlechter, der Reflex wäre dort nur knapp über den positiven Fällen. Am
    Standbild liest der Leser Zelle 7 noch mit üblichem Abstand (0,99). Ob der Reflex im Lauf über die Ziffer
    wandert, ist offline nicht prüfbar.
  * **`170836Z` Zellen 14/15: echte dunkle Spiegelung, Grund (a).** Ein gekrümmter dunkler Streifen liegt über den
    rechten Leerzellen. Leerzelle 15 hat beim Leser den Abstand 1,35, bei allen anderen 11 Aufstellungen höchstens
    0,96. Das Lesen verliert dort messbar Reserve.
  * **Kanten-WARNUNG an Zelle 13/14 der positiven Fälle** (6,5–7,0 gegen 6): schwache Reflexe am rechten Glasrand,
    Zellabstände des Lesers unauffällig.
  * **Geändert:** Die Grenzen bleiben. `kanten` liefert `flagged_cells` und einen Bedienertext mit Zelle, Lage,
    Stufe, Grenze und Abhilfe, z. B. „Reflex- oder Schattenkante über der Anzeige: Zelle 7 (Zahl) mit Stufe 29,8,
    Fehlergrenze 20. Licht abschatten, spiegelnde Gegenstände entfernen oder Kamera leicht drehen …“. Die
    Abbruchmeldung der Vorprüfung trägt ihn mit. Urteile auf 12 Aufstellungen und 6 historischen Kontrollen sind
    bitgleich. Regression: `tests/test_setup_checks.py` (`test_oq72_*`).
  * **Weiter offen:**
    * Wandert der Reflex im Lauf über die Ziffern? Nur am echten Aufbau prüfbar.
    * Strukturanteil der Belegtmessung an der letzten Ziffer: Eine Neukalibrierung braucht positive und negative
      Laufbelege und wird hier nicht vorgezogen.
    * Wirkung des OQ-74-Fokusfixes auf diese Fälle: nicht nachstellbar, die Bilder sind schon aufgenommen.

<span id="oq-73"></span>

## OQ-73 — Warum aktualisiert die Werkbank während der Einrichtung verzögert?

* **Status:** offen (2026-11-11) · **Priorität:** kritisch, Workbench-Blocker
* **Bedienermeldung:** Einrichtung etwas langsamer als sonst; Aktualisierung
  der Oberfläche verzögert, Kamerafeed ausdrücklich nicht betroffen.
* **Bisher geprüft:** Nach dem Abbruch `live-20261111T161702Z` antworten warme
  lokale Unix-Socket-Abfragen in etwa 1,7–6,6 ms. Erster Aufruf inklusive
  Clientinitialisierung etwa 172,8 ms. Intervalle auf derselben Host-Uhr
  `HOST_MONOTONIC`, Unsicherheit unbekannt. Dies misst weder HTTP-/Browser-
  Reaktion unter Setup-Last noch Kamera-/Frame-Latenz.
* **Offen:** Statusabruf, Browser-Rendering und CPU-/Lock-/Eventloop-Verhalten
  während einer tatsächlichen Einrichtung getrennt beobachten. Keine neue
  Einrichtung allein für diese erste Diagnose gestartet. Ein Zusammenhang
  mit dem Kantenabbruch ist nicht belegt.
* **Belege:** `status-and-local-response-times.json` im selben Diagnoseordner
  wie OQ-72; Quellprüfung des 500-ms-Pollings und des Service-Statuslocks.
  [Zusatzarchiv](quellen/setup-followup-2026-11-11.md) mit den Herkunftsgrenzen
  der Messung; während der betroffenen Einrichtung keine Browsermessung.
* **Antwort landet in:** Live-Client/-Service, gezielter Lastprüfung und
  [Validierung](VALIDATION.md).

<span id="oq-74"></span>

## OQ-74 — Warum wird das Bild nach erfolgreich geprüfter Fokussuche wieder unscharf?

* **Status:** offen (2026-11-11) · **Priorität:** kritisch, Workbench-Blocker
* **Bedienermeldung:** Werkbank findet den richtigen scharfen Fokus und
  wechselt danach sichtbar wieder auf eine unscharfe Lage. Nutzer fragt
  zugleich nach dem tatsächlich verwendeten Worktree.
* **Belegter Stand:** Dienst auf `bruecke-run`, Commit `08ac9b9`; kein
  automatisches Update beim Neustart. Neuere Workbench-Änderungen in
  `feat/bruecke-ui` fehlen dort. Die vier Fokus-/Kameramodule sind im
  laufenden Quellbaum und den geprüften Zweigen `bruecke-ui`, `bruecke-takt`
  und `bruecke-ux` jedoch byte-identisch. Die alten Fokuskorrekturen R13-9
  und R13-12 sind Vorfahren des laufenden Commits.
* **Jüngster Versuch:** `live-20261111T161955Z`, Zielwert 60, beste Schärfe
  734,45, Endprüfung 727,41; Anfahrt von unten protokolliert. Spätere Regler-
  Rückmeldung weiterhin 60, Autofokus aus. Ein zurückgesprungener numerischer
  Fokuswert ist damit nicht belegt; optische Unschärfe ist die Nutzerbeobachtung.
* **Offen:** Nach der Fokus-Endprüfung startet `_run_setup` die Kamera neu
  und setzt den Fokus erneut über die UVC-Quelle. Ob diese Grenze die
  verifizierte optische Endlage verliert (z. B. Motorhysterese), muss mit
  Bildern und Reglerereignissen vor/nach Neustart geprüft werden. Keine
  alleinige Ursache aus dem älteren Worktree ableiten; kein Wechsel allein
  auf Basis des Commit-Datums.
* **Belege:** Worktree-/Dateihashvergleich und aktuelle Reglerrückmeldungen
  unter `var/diagnostics/setup-followup-20261111/`, dort zusätzlich
  Setup-Dateien der beiden neuen Versuche.
  [Zusatzarchiv](quellen/setup-followup-2026-11-11.md). Passender Interpreter,
  Prozessumgebung und Arbeitsordner lösen `service`, `setup` und
  `focus_sweep` tatsächlich unter `bruecke-run/src` auf (`PYTHONPATH=src`).
* **Zusatzbefund `162902Z`:** Im erhaltenen Bild liegt die LCD-Hinweisbox
  bei ungefähr (538,3; 144,6; 800,4; 110,0) px, Fokusfenster bei
  (640; 360; 640; 360) px, Schnittfläche 0. Ziel 46, Endprüfung als
  erfolgreich protokolliert. Fokuszeitpunkt selbst hat kein Bild;
  optische Schärfe und unveränderte Aufstellung über den Kameraneustart
  sind damit nicht unabhängig nachgewiesen. Originale und Geometrieauswertung
  im [neuen Paket](quellen/setup-new-position-2026-11-11-162902.md).
* **Antwort landet in:** Kamera-/Fokus-/Setup-Übergang, Regressionstests,
  [Validierung](VALIDATION.md) und dokumentierter Betriebs-Quellstand.

* **Zusatz 2026-11-11:** Neuester Fall `170836Z`: Nutzer sieht erneut schlechteren Fokus als möglich. Ziel/Rückmeldung 56; beste protokollierte Schärfe 522,219448, Endprüfung 517,933823. Keine Fokus-Bildfolge, numerischer Rücksprung nicht belegt.
  [Originale und Rezept](quellen/setup-focus-failure-2026-11-11-170836.md).
* **Teilbehebung 2026-11-12 (Branch `fix/blocker-oq74`, gemergt in `feat/bruecke-ui`):**
  * **Fokus-ROI:** aus der grünen LCD-Hinweisbox, vorab auf dem neuesten Vorschaubild gesucht, mit 5 % Rand. Ohne Box gilt das mittlere Drittel, und `fokus` meldet WARNUNG. Auf allen sieben Paketbildern überdeckt die ROI die Box zu ≥ 90 %, vorher 0 bzw. 45–53 %.
  * **Endprüfung nach dem letzten Kameraneustart** gegen die beste Suchprobe, helligkeitsnormiert. Unter 0,6 (Vorabwert) wird der Fokus einmal von unten neu gesetzt, sonst gibt es eine WARNUNG.
  * **Laufstart:** dieselbe Prüfung gegen die Einrichtungsreferenz. Bleibt die Schärfe zu gering, erscheint eine sichtbare WARNUNG, der Lauf startet trotzdem. Das Ergebnis steht in `session.json`.
  * **Neue Diagnose:** `still-versuch-N.png`, Fokusausschnitte vor und nach dem Neustart, `focus_end_check`.
  * **Weiter offen:**
    * optisches Motorverhalten beim Neustart: erste echte Einrichtung, `restart_effect`
    * Kalibrierung der Schwelle

* **Nachtrag 2026-11-13:** Der Laufstart sperrt fehlende oder ungültige
  Referenzen und Schärfeverhältnisse außerhalb 0,95–1,05; das ist ein
  vorläufiger Gleichheitsfilter, keine validierte Schärfe- oder Maßstabsgrenze.
  Die Ursache der Unterschiede und die Kalibrierung bleiben offen. Ein Lauf
  mit 1,418 hatte keine Zweitversuche; Schärfe allein beweist keinen Maßstab.
  Details und Offline-Auswertung: [Nachführung](quellen/nachfuehrung-recherche-2026-11-13/README.md).

<span id="oq-75"></span>

## OQ-75 — Warum fielen Kamerabild und Workbench-Verbindung gleichzeitig kurz aus?

* **Status:** offen (2026-11-11) · **Priorität:** kritisch, Teil des Workbench-Blockers
* **Bedienermeldung:** Kamerabild und Verbindung zur Workbench gleichzeitig
  ungefähr sieben Sekunden weg. Dauer vom Nutzer geschätzt, nicht gemessen;
  exakter Beginn und Ende unbekannt. Erste Agent-Prüfung 17:41:15 MEZ.
* **Logs/Status:** PID 3321848, Start 17:16:36 MEZ, `NRestarts=0`, weiterhin
  active/running. Keine zugeordnete neue Kamera-/Dienststartmeldung im
  Anwendungsjournal beim berichteten Ausfall. Kamera später laufend,
  nicht als stalled markiert. Dies widerlegt einen vorübergehenden Ausfall nicht.
* **Weitere Belege:** Kernel meldet USB-U1-/xHCI-Warnungen um 17:29 bei den
  protokollierten früheren Setup-Kameraneustarts. Tailscale-Journal enthält
  Peer-/DERP-/Endpunktwechsel im erfassten Zeitraum. Keine dieser Meldungen
  ist ohne genaues Ereignisfenster als Ursache nachgewiesen. CPU-/IO-/
  Speicherdruckdateien fehlen auf diesem System; Firmware-Abfrage scheiterte,
  Fehlerausgaben sind erhalten.
* **Belege:** `var/diagnostics/workbench-outage-20261111/` mit ursprünglichem
  Anwendungs-/Kerneljournal in Text und JSON, Netzwerkjournal, Service-/
  Kamera-/Speicherstatus, Befehlen, Exitcodes und Quellen der Zeitangaben.
  [Logpaket](quellen/workbench-outage-2026-11-11.md).
* **Antwort landet in:** Dienst-/Kamera-/Verbindungsdiagnose, Fehlerbehebung,
  Regressionen und [Validierung](VALIDATION.md). Nicht allein durch Neustart
  oder einen inzwischen wieder funktionierenden Status als geklärt markieren.


<span id="oq-76"></span>

## OQ-76 — Warum verliert ein Lauf nach bestätigter Einrichtung sämtliche Rahmenmerkmale?

* **Status:** geklärt (2026-11-11)
* **Befund:** `live-20261111T165234Z/run-01` enthält 28 UNREADABLE,
  28 Trackingverluste (`zu_wenig_rahmenmerkmale`), 0 VALID. Originale erhalten.
* **Antwort:** Der Nutzer erklärt am 2026-11-11 ausdrücklich: Der kurze
  Start-/Stopp-Lauf war sein Umweg, um nach bestätigter Einrichtung für
  eine neue Aufstellung wieder einrichten zu können. Dafür fehlte ein
  direkter Knopf. Dieser absichtlich gestartete Lauf bei Aufstellungswechsel
  ist kein unabhängiger Beleg eines Trackingfehlers am eingerichteten Aufbau.
  Die Einordnung als eigenständiger Trackingblocker wird zurückgenommen.
* **Verweis:** [OQ-71](#oq-71) umfasst auch fehlendes Neu einrichten nach
  Bestätigung. [Originale und Bedienerkontext](quellen/workbench-positive-regression-2026-11-11.md).
* **Antwort landet in:** OQ-71, Claude-Übergabe, Validierung und Laborjournal.
