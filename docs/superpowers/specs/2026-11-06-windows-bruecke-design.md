# Windows-Brücke für GSVmulti: Installation, Verbindung und Betrieb

Stand: 2026-11-06. **Entwurf zur Freigabe, keine Umsetzungsfreigabe.**
Leonhard hat die Architekturvariante Python-Brückenkern + Qt-GUI +
Windows-Installer gewählt. Die folgenden technischen Vorgaben sind, soweit
nicht ausdrücklich als Nutzervorgabe bezeichnet, Vorschläge des Entwurfs.

## 1. Ziel und Rahmen

Laborbediener verbinden einen Pi über UART oder Netzwerk mit GSVmulti,
ohne Python, COM-Zuordnung und Konfigurationsdateien manuell zusammenzubauen.
Die Workbench bietet Anleitung und Verbindungsprofil; eine Windows-Anwendung
richtet die lokale Strecke ein und erzeugt eine passende GSVmulti-Session.
Sie nennt bei Fehlern die nächste sinnvolle Aktion.

Nutzervorgaben: bevorzugt EXE, automatische Installation/Einrichtung,
Wahl UART/Netzwerk, verständliche Bereitschaftsanzeige, mehrere Pi und Netze,
Betrieb mit und ohne Tailscale, möglichst automatisch erzeugte GSVmulti-Session.
Downloads während der Einrichtung sind ausdrücklich erlaubt. Die EXE muss
auch ohne Python und neben alten Versionen funktionieren. Ein Download-/
Ausführungsbefehl ist eine mögliche spätere Alternative, kein zweiter
Installer für die erste Lieferung.

Vorgeschlagener erster Zielumfang: Windows 11 x64, Standardbenutzer im
Betrieb, gesonderte Administratorfreigabe für nötige Systemänderungen;
Pi 5 mit dem bestehenden Dienst. Windows ARM64, 32 Bit und weitere
Windows-Versionen werden zuerst erkannt und als noch nicht unterstützt
benannt; keine stillschweigende Kompatibilitätszusage. Erste GSVmulti-
Vorlage für die vorhandene 2.03-Pro-Installation; genaue EXE-/Bibliotheks-
und Dateiversionen werden beim Vorlagennachweis festgehalten.

Kein Ersatz für die GSVmulti-Lizenz oder die Pi-Erstinstallation. Die
Brücke startet keine Messung, bestätigt keinen Bildvorschlag und ändert
keine laufende Ausgabewahl. Leser, Referenzvergleich, Gate, Formatierung,
Altwert-/Ungültig-Semantik und Messfreigabe bleiben fachlich getrennt.

## 2. Varianten und Auswahl

| Ansatz | Vorteil | Nachteil / Entscheidung |
| --- | --- | --- |
| Bestehender Python-Kern, PySide6/Qt, paketierte Laufzeit, Installer | Brückenlogik und Tests weiterverwenden; unabhängig vom System-Python | Paketierung und Windows-Geräteintegration nötig; von Leonhard gewählt |
| Vollständiger Neubau in C#/.NET | Native Windows-Integration | Brückenlogik übertragen und erneut prüfen; nicht gewählt |
| Reines Python-Downloadskript als Hauptprodukt | Wenig Oberfläche | Wiederholt manuelle Laufzeit-/Portprobleme und erfüllt GUI-Ziel nicht; höchstens alternative Bereitstellung |

Windows-Anwendung und Pi-Messpfad bekommen getrennte Abhängigkeiten und
Builds. Neue Qt-/Paketierungsbibliotheken dürfen nicht in der Pi-venv die
Debian-Kamera-/CV-Pakete überdecken. Der produktive Windows-Build importiert
nur benötigte Brückenmodule. Gewählter Paketierungsansatz im Entwurf:
PyInstaller-Ordnerpaket mit fest getesteter Python-Laufzeit hinter einer
Setup-EXE; Inno Setup als vorgeschlagenes Installationswerkzeug. Versionen
werden im späteren Build-Lock festgelegt. Kein System-Python erforderlich.

## 3. Verantwortung der Bausteine

| Baustein | Verantwortung |
| --- | --- |
| Pi-Dienst | Geräteidentität, Kopplung, authentifizierter Kanal, Lauf-/Ausgabestatus, bestehender Publisher und vollständiges Audit |
| Workbench | Auswahl und Erklärung des Ausgabewegs, Download des generischen Installers und des Pi-Verbindungsprofils, Kopplung freigeben |
| Windows-Brückenkern | Verbindung, Protokoll, Frische-/Ungültigbarriere, COM-Weitergabe und Audit; unabhängig von der GUI testbar |
| Qt-GUI | Einrichtung, Geräteauswahl, Status und nächste Aktion; blockiert die Übertragung nicht mit Dialogen |
| Installationshelfer | Begrenzte privilegierte Treiber-/Portpaararbeiten; keine Messwertverarbeitung als Administrator |
| Sessiongenerator | Geprüfte GSVmulti-Vorlage mit lokal bekannten Ports und zulässigen Einstellungen ausgeben |

Die GUI steuert den Kern über eine interne, versionierte Ereignisschnittstelle.
Widgets führen keine blockierenden seriellen oder Netzwerkoperationen aus.
Ein zweiter Anwendungsstart aktiviert das bestehende Fenster. Erste Lieferung
als sichtbare Benutzeranwendung mit Tray-Betrieb, nicht als Windows-Systemdienst.
Minimieren lässt die Brücke laufen; „Brücke beenden“ erklärt eine aktive
Übertragung und beendet sie erst nach ausdrücklicher Bestätigung. Abmelden
oder Standby können die Übertragung unterbrechen; Wiederanlauf wird geprüft.
Ein dauerhaft unbeaufsichtigter Windows-Dienst ist ein eigener späterer Umfang.

## 4. Installation und Wiederholung

1. Generischer, versionierter Installer; keine Pi-Adresse oder Zugangsdaten
   in einer individuell erzeugten EXE. Veröffentlichung über festgelegten
   Release-Kanal, kein temporärer Labor-Downloadserver.
2. Bestandsaufnahme: OS/Architektur, App-Version, USB-Geräte einschließlich
   PnP-Problemen, virtuelle Portpaare und Treiberstatus. Keine globale Änderung
   von PATH oder bestehenden Python-/Visual-Studio-Installationen.
3. App samt Laufzeit installieren. Benötigte externe Komponenten nur aus
   festgelegten Bezugsquellen mit freigegebener Version/Hash und geprüfter
   Signatur laden. Ein signiertes Release-Manifest beschreibt die Artefakte.
   Ein Hash ohne vertrauenswürdiges Manifest genügt nicht als Herkunftsnachweis.
4. Administratorrechte nur für erforderliche Systemarbeiten anfragen. Bei
   fehlenden Rechten „IT-Freigabe erforderlich“ mit exportierbarer Diagnose;
   keine UAC-/Treiber-/HVCI-Umgehung. App ohne Systemrechte betreibbar, sobald
   Treiber und Portpaar durch IT eingerichtet sind.
5. Vorhandenes geeignetes Paar nach Auswahl übernehmen oder eigenes Paar
   mit freien COM-Namen erstellen. Eigentum und Wiederverwendung getrennt
   speichern. Keine Festannahme COM4/COM5/COM6 und keine Übernahme eines
   gerade anderweitig verwendeten Paars.
6. Selbsttest des Portpaars in beide Richtungen nur bei freien Gegenstellen
   und geschlossener GSVmulti-Verbindung. Danach beide Testhandles schließen.
7. Neustartbedarf anzeigen und Einrichtung danach fortsetzen. Wiederholtes
   Setup repariert/ergänzt statt Paare zu vervielfachen. Bei Abbruch nur eigene
   neue Ressourcen zurücknehmen; keine fremden Treiber/Paare entfernen.

com0com ist der erste Prüf-Kandidat, kein pauschal freigegebener Produktionstreiber.
Vor Produktfreigabe: konkretes Paket, Weitergabe, unbeaufsichtigte Installation,
Windows-Signatur-/HVCI-Verträglichkeit und saubere Deinstallation auf den
Zielsystemen nachweisen. Falls dies scheitert, ist die Produktfreigabe blockiert;
kein stiller Wechsel auf kostenpflichtige Anbieter. Eine Alternative braucht
eine eigene Entscheidung. Anwendungssignierung und Treibersignierung sind
getrennte Voraussetzungen. Signierungsschlüssel und Release-Hosting müssen
vor externer Veröffentlichung verfügbar sein; bis dahin nur klar benannte
interne Testpakete. GSVmulti selbst wird vorausgesetzt und auf passende
Version/PRO-UserDefined-Funktion geprüft, nicht heimlich installiert/lizenziert.

Internet ist für Downloads bei Einrichtung erlaubt. Der eingerichtete
LAN-/UART-Betrieb soll kein Internet benötigen. Proxy-, Download-, Signatur-
oder Speicherfehler müssen Einrichtung fortsetzbar lassen. Bei Updates keine
Übertragung unterbrechen: nur im Ruhezustand nach Bestätigung installieren,
Konfiguration versioniert migrieren, vorige Version zur Rückkehr erhalten.
Gemeinsame Treiber bei Deinstallation erhalten; nur eigene unbenutzte Paare
nach Auswahl entfernen. Keine Messprotokolle stillschweigend löschen.

## 5. Geräteidentität und erster Zugang zum Pi

Pi-Identität ist unabhängig von IP, Hostname und Messgeräte-`device_id`.
Jeder eingerichtete Pi erhält eine zufällige dauerhafte ID und ein eigenes
TLS-Schlüsselpaar. Vorlage/Installationsabbild enthält keine fertige Identität.
Die Provisionierung bindet eine erzeugte Identität zusätzlich an den vor Ort
festgestellten Pi, um kopierte eingerichtete SD-Karten vor normalem Start als
möglichen Klon zu erkennen. Ein solcher Konflikt fordert eine ausdrücklich
bestätigte Neueinrichtung; keine Messdaten löschen und nicht unter fremder
Identität verbinden. Ersetzen eines Geräts ist eine erneute Kopplung.

Für die erste Netzwerkaufnahme ist ein unterstützter Weg nötig: Pi und PC
am selben Ethernet-Netz mit DHCP; alternativ vorab eingerichtetes WLAN über
den Pi-Bootstrap/Imager (OQ-49). Auf diesem Weg veröffentlicht der vorbereitete
Pi seinen Dienst. Ohne vorhandene Verbindung kann die Windows-EXE kein
unbekanntes WLAN auf dem Pi einrichten. Wenn DHCP/Suche blockiert sind,
Anleitung für Netzbetreiber bzw. lokale Pi-TUI mit tatsächlichen Adressen.
Kein automatisches Umkonfigurieren fremder Windows-Netze und kein USB-C-Gadget-
oder WLAN-Hotspot-Setup als versteckte Rückfalllösung.

Pi-Standardhost, Dienstadresse, Anmeldung und Zertifikat müssen konfigurierbar
sein. Festwerte wie die derzeitige Tailscale-IP oder PAM-Benutzer `me-systeme`
sind kein allgemeiner Installationsvertrag. Kopplung erfolgt über einen
bereits autorisierten Workbench-Zugang oder eine lokale, authentisierte
Einrichtungsaktion am Pi; kein Standardkennwort im Windows-Paket.

## 6. Verbindungsprofil und Kopplung

Zwei unterschiedliche Dateien:

* **Pi-Verbindungsprofil** aus der Workbench: neue Dateiendung für diese App,
  Schema-Version, Pi-ID, Anzeigename, vollständiges öffentliches TLS-Zertifikat
  samt SHA-256-Fingerprint, mögliche LAN-/Tailscale-Endpunkte, benötigte
  Protokollversion und optional kurzlebiges Kopplungsangebot.
* **GSVmulti-Sessiondatei** aus der Windows-App: lokal gewählter virtueller
  Gegenport und nachgewiesene GSVmulti-Einstellungen. Kein Pi-Zugangstoken.

Ein Profil ist strukturierte Daten, kein ausführbares Skript: nur erlaubte
Felder/Schemata, begrenzte Größe, geprüfte URLs und keine Befehle oder
Dateipfade zum beliebigen Schreiben ausführen. Per Dateizuordnung öffnet es
die Anwendung; Öffnen allein autorisiert noch keine Messausgabe.

Vertrauensanker: Das Profil wird vom tatsächlich autorisierten Pi-Zugang
heruntergeladen. Bei unbekanntem/ungeprüftem Workbench-Zertifikat ist zuerst
der Fingerprint mit der lokalen Pi-Einrichtung zu vergleichen. mDNS, ein
QR-Code ohne geprüfte Herkunft und ein gefundener Hostname sind kein
Identitätsnachweis. Profile lassen sich auf einen anderen Windows-PC
übertragen; dieser wird als eigener Client gekoppelt.

Vorgeschlagene Kopplung: kryptografisch zufälliges Einmalangebot (256 Bit),
maximal fünf Minuten gültig und auf Pi und gewählten Client/Transport zu
begrenzen. Profil allein ohne Angebot ist unkritische Konfiguration. Nach
Einlösen wird das Angebot entwertet und durch einen getrennt widerrufbaren
Client-Zugang ersetzt. Netzwerkzugang nur über TLS. Windows speichert
Zugangsdaten geschützt mit benutzergebundenem Windows-Speicher; keine
Linux-Passwörter und keine dauerhaften Zugangsdaten in Profilen oder Logs.
Der Pi führt eine widerrufbare Client-Liste; Rate-Limits und Ablauf gelten
auch bei falscher/mehrfacher Einlösung. Wiederholte Kopplung darf kein
zweites gleichzeitiges Ausgaberecht erzeugen.

Netzwerk prüft das TLS-Zertifikat gegen den importierten Fingerprint sowie
Gültigkeit und erwartete Pi-ID. Kein globales Abschalten von Zertifikatsprüfung.
Ein Zertifikats-/Identitätswechsel verlangt erneute überprüfte Kopplung.
Für UART weist der Pi seine Identität durch Signieren einer frischen
Client-Nonce mit dem zum importierten Zertifikat gehörenden Schlüssel nach;
Antwort ist an Protokollversion/Pi-ID/Nonce gebunden. Diese Authentisierung
muss mit einer etablierten Kryptografiebibliothek umgesetzt werden, nicht mit
selbst erfundenem Signaturverfahren. Verfahren und Serialisierung werden
im Protokollanhang vor Implementierung festgelegt und getestet.

UART ist eine lokale physische Verbindung und transportiert Daten nicht
verschlüsselt. Etwaige UART-Zugangsdaten sind ausschließlich auf diesen
Transport beschränkt und berechtigen nicht zum Netzwerkkonto oder zur
Messsteuerung. Erste reine UART-Einrichtung ohne Netzwerkzugriff nutzt ein
zuvor vom Pi exportiertes Profil und lokale Freigabe; kein blindes Vertrauen
in die zuerst am Port gemeldete Identität.

## 7. Netzwerk finden und wiederfinden

Pi veröffentlicht DNS-SD/mDNS mit kurzem gerätespezifischem Hostnamen und
passendem Diensttyp. Öffentliche Discovery enthält nur Name, Dienstadresse,
Version und unkritische Gerätekennung. Sie wird vor jedem produktiven
Verbinden durch die Kopplung überprüft. Suche ist abbrechbar und zeitlich
begrenzt; fehlende Suchtreffer bedeuten nicht automatisch „Pi ausgeschaltet“.

| Situation | Vorgehen |
| --- | --- |
| Gleiches LAN/WLAN | DNS-SD/mDNS und bekannte Namen auf erreichbaren lokalen Schnittstellen |
| DHCP-/Netzwechsel | Namen erneut auflösen; Kandidaten gegen gespeicherte Identität prüfen |
| mDNS blockiert/VLAN | Manuell eingegebener Host/Adresse oder gespeichertes Profil; benötigte Route erklären |
| Tailscale vorhanden | Konfigurierten vollständigen MagicDNS-Namen/Adresse prüfen; optional lokal sichtbare Peers zuordnen |
| Tailscale fehlt/abgemeldet | Nur nach Auswahl Installation/Anmeldung anbieten; normale Tailnet-Freigabe erforderlich |
| Getrennte Netze ohne Tailscale | Vorhandene VPN-/IT-Route oder gemeinsames Netz nötig; keine öffentliche Portfreigabe anlegen |
| IPv6/link-local/mehrere Adapter | Adresstyp und Scope erhalten; erreichbaren Endpunkt desselben Pi prüfen |

Keine Vollscans fremder Netze. ICMP-Ping ist kein notwendiges Erfolgskriterium;
entscheidend sind TLS- und Protokollhandshake. Gleiche Namen mit anderer
Identität werden als Konflikt gezeigt. LAN oder Tailscale kann vor Beginn
gewählt werden; Adressfallback innerhalb desselben gewählten Netzwerkmodus
nur für denselben gekoppelten Pi. Kein unbemerkter Wechsel UART↔Netzwerk oder
auf einen anderen Pi. Unverträgliche Version wird vor Datenausgabe gemeldet.

Vorgeschlagener produktiver Kanal: authentisierter WSS-Endpunkt des
bestehenden HTTPS-Dienstes. Er ist auch ohne laufende Messung für Identität,
Fähigkeiten und Bereitschaft erreichbar. Das heute rohe TCP-Protokoll bleibt
ein expliziter Entwicklungs-/Demoweg, kein ungesicherter Produktfallback.
TLS und Authentisierung enden im Pi-Dienst; der Messpfad wartet nicht auf
GUI, TLS oder Windows und führt bei Kanalstörung sein Audit weiter.

## 8. UART und Windows-Portpaar

Physischer Eingang und virtueller Ausgang sind getrennte Ressourcen.
USB-Auswahl nach VID/PID, Seriennummer und Geräteinstanz; COM-Nummer ist eine
veränderliche Zuordnung. Ohne eindeutige Seriennummer oder bei mehreren
passenden Geräten Auswahl mit Anzeigenamen/USB-Ort verlangen. PnP-Erkennung
muss auch Geräte mit fehlendem Treiber berücksichtigen, nicht nur die Liste
bereits funktionierender COM-Ports.

Standard für den bestehenden Pi-Weg: 115200/8N1, kein Handshake, TX jeweils
zum RX der Gegenstelle und gemeinsames GND; VCC/CTS/RTS frei. Produktanleitung
benutzt eindeutig beschriftete Anschlüsse und den unterstützten Adapter,
keine Zuordnung nur nach Kabelfarbe. Andere Adapter brauchen einen eigenen
Nachweis. Aktuell ttyAMA0 am Pi; Referenz ttyUSB0 wird nicht als Ausgang geöffnet.

Nach Portöffnung folgt ein echter Identitäts-/Protokollhandshake. Erst dann
„Pi verbunden“. Geöffnetes serielles Handle allein ist kein solcher Nachweis.
Timeout meldet mögliche Ursachen (Pi-Dienst, TX/RX/GND, Parameter), aber
behauptet ohne Beleg nicht „TX-Leitung fehlt“. Abziehen invalidiert den
Transport sofort; bei neuer COM-Nummer nur denselben Adapter erneut versuchen.

Ein internes Paarmodell speichert Brückenseite und GSVmulti-Seite getrennt.
Bei Konflikt keine laufende Anwendung beenden oder fremde Ports umbenennen.
Ändert sich nur der physische USB-Port, bleibt die GSVmulti-Session passend;
ändert sich der virtuelle Gegenport, muss eine neue Sessiondatei erzeugt und
übernommen werden. GSVmulti nach verweigertem Wiederöffnen zum bekannten
geordneten Neustart anleiten (OQ-52), keine Prozesse zwangsweise beenden.

## 9. Datenvertrag und Wiederanlauf

Bestehende Kernregeln bleiben: unveränderter ValueRecord, Formatierung nur
über TelegramFormatter, Kennzeichnung provisional, Audit vor Publish,
Invalidierungsbarriere getrennt vom jüngsten Wert. Keine Glättung, keine
Referenzkorrektur, kein historisches Nachsenden. Netzwerk und UART teilen
denselben Brückenkern. Bisher nur für synthetische Demo freigegeben.

Neuer Kopplungs-/Hello-Vertrag wird als Protokollversion 2 eingeführt; keine
stille Neuinterpretation von v1. Fachlich benötigte Nachrichten: Hello mit
Pi-/Client-/Protokollidentität, Fähigkeiten und Berechtigungen; Poll,
Record/Idle/Ended, ACK und strukturierter Fehler. Hello unterscheidet Dienst
bereit, kein Lauf, Ausgabe aus, Demo und fachlich gesperrte DUT-Ausgabe.
Request-/Run-/Frame-/Barrier-Kennungen bleiben eindeutig zugeordnet.
Maximal eine aktive Ausgabe-Client-Lease pro Pi-Lauf/Ausgabeweg, mit Timeout;
zweiter Client erhält einen erklärten Konflikt. Paarbelegung und App-Instanz
werden zusätzlich auf Windows exklusiv geschützt.

Begrenzte Puffer, höchstens ein ausstehendes Angebot plus jüngster Datensatz;
Invalidierungsbarriere hat Vorrang. Zeitbasis und unbekannte Unsicherheit
bleiben erhalten. SYNTHETIC erlaubt keine Alters-/Latenzbehauptung.
Für echte Quellen werden nur zuvor spezifizierte Frischegrenzen und
zulässige Zeitbasen verwendet. Keine Subtraktion ungepaarter Pi-/Windows-Uhren.
Die noch offene Empfängersemantik aus OQ-06/OQ-47 bleibt Freigabeschranke.

COM-ACK belegt ausschließlich vollständige Annahme durch den lokalen
COM-Schreibpfad, nie GSVmulti-Empfang. Kurzer oder unklarer Schreibvorgang
wird nicht blind wiederholt. Nach Prozessabbruch zwischen Schreiben und ACK
ist keine Exactly-once-Zusage möglich: Versuch als unklar auditieren,
zweifelhafte Veröffentlichung nicht erneut ausgeben und beim jüngsten
zulässigen Wert fortsetzen. Vergangene Lücken werden erhalten. Details von
Lease-Wechsel, unklarem Schreiben und Barrieren müssen im Protokollanhang
vor produktiver Freigabe getestet sein; keine Entsperrung allein durch die EXE.

Pi-Neustart und neue Run-ID erzwingen erneute Zuordnung; alte Antworten/
Credentials dürfen nicht auf einen anderen Pi oder Lauf wirken. Kurzer
Verbindungsabbruch versucht nur den explizit gewählten Weg zum selben Pi,
mit begrenztem Backoff. Neue Verbindungsdaten oder ein anderer Transport
werden für einen laufenden Messlauf nicht automatisch eingesetzt.

## 10. Verständliche Oberfläche

Die GUI dient dem Einrichten und Überwachen. Deutsche Sprache, Tastatur-
Bedienbarkeit, Windows-DPI/Skalierung und langer Gerätename gehören zur
Abnahme. Keine ungeprüfte Übernahme des dunklen Kamera-Viewers; konkrete
visuelle Gestaltung ist ein nachfolgender Entwurf innerhalb dieser Funktion.

Erste Einrichtung: Komponenten prüfen → Pi auswählen/koppeln → UART oder
Netzwerk verbinden → GSVmulti-Session erzeugen → Empfang prüfen. Bereits
gekoppelte Geräte können gezielt wiedergewählt werden. Windows-App und
Workbench zeigen denselben ausgewählten Pi und Ausgabeweg; laufende
Konfiguration ist schreibgeschützt. Abbrechen verändert keinen Messlauf.

Status ist mehrdimensional und niemals pauschal „alles grün“:

| Prüfpunkt | Mögliche verständliche Aussage |
| --- | --- |
| Komponenten | Installiert / Administratorfreigabe nötig / Neustart nötig |
| Physischer UART | USB-Adapter anschließen / Treiber fehlt / Auswahl nötig / erkannt |
| Pi | Wird gesucht / falsches Gerät / antwortet nicht / verbunden |
| Ausgabe | Wartet auf Lauf / Ausgabe aus / Demo / DUT-Ausgabe gesperrt |
| Windows-Weitergabe | COM-Port belegt / Weitergabe bestätigt / Schreibfehler / unklar |
| GSVmulti | Sessiondatei erzeugt; bitte öffnen / Übernahme vom Nutzer bestätigt / Empfang belegt / noch nicht nachgewiesen |

Anzeigename, Weg und nächste Aktion bleiben sichtbar. Technische Details
und Diagnoseexport eine Ebene tiefer. Keine dauerhaften wiederholten
Timeout-Popups; Zustand aktualisieren und erneuten Versuch/Abbruch anbieten.
Messwerte nicht als gültig darstellen, wenn der Pi sie als ungültig/stale
meldet. Ein erfolgreicher Hardware-/Transporttest heißt nicht „Messfreigabe“.

## 11. GSVmulti-Sessionerzeugung

Sessiondatei erst nach Festlegung des virtuellen GSVmulti-Gegenports erstellen.
Pro unterstützter Version existiert eine tatsächlich gespeicherte und wieder
geöffnete Referenzvorlage. Der Generator ändert nur nachgewiesene Felder:
Port, Parameter, Zahlenformat, Präfix, Filter, Einheit, Skalierung und Rate.
Unbekannte Kodierung nicht erraten, insbesondere OQ-53. Dateiformat/Endung
folgen dem belegten GSVmulti-Format, nicht einem erfundenen Schema.

Generator validiert Vorlage und Resultat, erstellt eine neue Datei mit
Geräte-/Konfigurationskennung und zeigt die nötige Öffnen-/Importaktion.
Keine vorhandenen GSVmulti-Sessions oder aktive Messung überschreiben.
Unbekannte GSVmulti-Version: Automatik gesperrt, geprüfte manuelle Anleitung
mit klarer Einschränkung. Nur bloße Dateiablage oder laufender Prozess belegt
nicht, dass GSVmulti die Einstellungen tatsächlich übernommen hat.

Empfangstest ist ausdrücklich gestartet, als synthetischer Test markiert
und getrennt von echten Kalibrierdaten. Originale GSVmulti-Datei gegen den
bekannten Stimulus auswerten; erst dann „Empfang belegt“ für genau diesen
Test und diese Konfiguration. Normaler Lauf zeigt ohne weiteren Nachweis nur
COM-Weitergabe. App-Lizenzstatus oder eine fremde Messung nicht verändern.

## 12. Audit, Ressourcen und Pflege

Windows schreibt Verbindungs-/Installations-/Ausgabeereignisse mit eigener
HOST_MONOTONIC-Zeitbasis, UTC-Beobachtungszeit, IDs, Versionen und Fehlern.
Secrets und Passwörter werden redigiert. Rohdaten/Audit für einen
Abnahmeversuch bleiben vollständig. Produktbetrieb braucht begrenzte
Log-Aufbewahrung ohne volllaufende Systemplatte; Detailauswahl mit OQ-60
abstimmen. Diagnoseexport nennt Pi-/App-/Treiber-/GSVmulti-Version,
Portzuordnung und relevante Ereignisse ohne Zugangsdaten.

Kein automatischer Software- oder Treiberwechsel im laufenden Messbetrieb.
GUI-Absturz darf keine ungekennzeichnete alte Wertanzeige hinterlassen;
Brückenkern/COM-Fehler führen zum unterbrochenen Zustand. Windows-Standby,
USB-Energiesparen, Benutzerabmeldung und Pi-Neustart sind reale Abnahmefälle,
keine still zu ändernden Systemeinstellungen.

## 13. Abnahme und Reihenfolge der Nachweise

Vor größerem GUI-Ausbau drei Machbarkeitsnachweise: Windows-Paket ohne
System-Python, zulässige automatisierbare VCOM-Einrichtung, Roundtrip der
GSVmulti-Sessionvorlage. Discovery/Kopplung als eigener Nachweis auf zwei Pi.
Das sind spätere Aufgaben nach Freigabe dieser Spec, keine bereits gebauten
oder freigegebenen Spikes.

| Bereich | Zwingende Fälle / Erfolg |
| --- | --- |
| Laufzeit | Kein Python, nur Python 3.7, mehrere Versionen; gleiche Funktion ohne Änderung vorhandener Installationen |
| Installer | Standard-/Adminnutzer, verweigerte UAC, Proxy/Downloadabbruch, Neustart, Wiederholung, Reparatur, Update/Rückkehr, Deinstallation; fremde Komponenten erhalten |
| Treiber | Frisches Windows 11 x64, aktive Schutzfunktionen, fehlender/gesperrter Treiber, vorhandene belegte Paare; keine pauschale Signaturzusage |
| Geräte | Zwei Pi, gleiche Namen, geklonte SD-Karte, falsche Identität, Zertifikatswechsel, abgelaufenes/verwendetes Kopplungsangebot |
| LAN | DHCP-/Netzwechsel, mehrere Adapter, IPv4/IPv6-Scope, mDNS gesperrt, fehlende Route, blockierter Port |
| Tailscale | Nicht installiert, abgemeldet, falsche Freigabe, DNS-Problem, Pi offline, LAN-Wechsel; keine alternative Geräteauswahl |
| UART | Kein USB, fehlender Treiber, zwei Adapter, neue COM-Nummer, falsche Verdrahtung, Port belegt, Abziehen und Wiederanschließen |
| Parallelität | Zweite App, zweiter PC und doppelte Lease; keine doppelte Weitergabe |
| Störung | Teilwrite, ACK-Verlust, Brücken-/Pi-Abbruch, Standby, Neustart/Run-Wechsel, volle Platte; begrenzte Puffer und keine historischen Aufholfolgen |
| GSVmulti | Genau belegte Version/PRO, Session neu erzeugt/geöffnet, Feldwerte kontrolliert, Originaldatei gegen Demo geprüft; unbekannte Version erklärt abgewiesen |
| Bedienung | Ohne Terminal von Download bis Empfangstest; Fehler verlangen konkrete nächste Aktion, Tastatur/DPI funktionieren |
| Fachlich | Unveränderte Gates und Referenztrennung; keine produktive DUT-Ausgabe bis zu eigenem Ungültig-/Altwert-/Zeitnachweis |

Automatisierte Kern-/Protokoll-/Installerprüfungen ergänzen echte Tests mit
Windows, Treiber und GSVmulti. Windows-Paketierung auf einem Windows-Runner;
Pi und Windows getrennt prüfen. Hardware-/Messnachweise nach VALIDATION und
Laborjournal. Ein späteres produktives Release benötigt zusätzlich
freigegebene Signierung, Hosting und unterstützte Versionsmatrix.

## 14. Verbleibende Entscheidungen und Zuständigkeiten

* Durch diesen Entwurf vorgeschlagen: Windows 11 x64 zuerst, Tray-App,
  PyInstaller-Ordnerpaket/Inno Setup, gekoppelte WSS-Verbindung, keine
  automatische System-/Transportumschaltung.
* Vor Implementierung des jeweiligen Bausteins auszuarbeiten: genaue
  Protokoll-v2-Schemata, UART-Signaturverfahren mit etablierter Bibliothek,
  UI-Ansichten und Release-/Signierungsprozess. Abnahmeschranken oben gelten
  dabei unverändert; neue fachliche Unbekannte als OQ dokumentieren.
* Externe Freigaben: Administrator-/IT-Berechtigung am Zielrechner,
  Verteilung/Signierung der Treiber und Anwendung, genaue unterstützte
  GSVmulti-Versionen nach Vorlagen-Roundtrip. Fehlende Freigabe blockiert
  genau diese Lieferfähigkeit; sie wird nicht als Erfolg angenommen.
* OQ-62: Installer/Sessionassistent; OQ-64: Netzaufnahme und Kopplung;
  OQ-49: Pi-Erstinstallation; OQ-53: Sessionkodierung; OQ-06/OQ-47:
  fachliche Ausgabegrenzen. Architekturwahl löst diese Nachweise nicht.

## Prüfung und Freigabestand

Unabhängiger Builder-Check am 06.11.2026: keine wichtigen offenen
Planungsfragen gemeldet. Er prüfte den Entwurf auf Annahmen, deren falsche
Wahl die Umsetzung wesentlich verändern würde. Technische Machbarkeits-
und Hardware-Nachweise sind damit nicht erbracht.

Architekturwahl durch Leonhard liegt vor; Freigabe dieses vollständigen
Dokuments steht aus. Danach folgt ein Umsetzungsplan mit den oben genannten
Machbarkeitsnachweisen vor dem größeren GUI-Ausbau.

## Quellen und vorhandene Belege

* [Bestehender Brückenvertrag](../../GSVMULTI_PROTOCOL.md#windows-bruecke),
  [Windows-Abhängigkeiten](../../dependencies.md#windows-bruecke),
  [Nutzeranforderung OQ-62](../../open-questions.md#oq-62),
  [Netzaufnahme OQ-64](../../open-questions.md#oq-64).
* [PyInstaller: Laufzeit bündeln](https://pyinstaller.org/en/stable/operating-mode.html),
  [Windows-Build](https://pyinstaller.org/en/stable/),
  [Qt-Deployment](https://doc.qt.io/qtforpython-6/deployment/index.html).
* [Pi-Netzerkennung](https://www.raspberrypi.com/documentation/computers/remote-access.html),
  [Tailscale MagicDNS](https://tailscale.com/docs/features/magicdns),
  [USB-Portmetadaten](https://pyserial.readthedocs.io/en/latest/tools.html),
  [Windows-Treibersignaturen](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/driver-signing).
