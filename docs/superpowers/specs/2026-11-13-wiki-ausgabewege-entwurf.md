# Entwurf: Wiki-Seite „Ausgabewege zu GSVmulti“

**Status:** Entwurf vom 2026-11-13 (Claude, autonomer Plan Punkt 5). Gedacht als
`docs/uebersicht/ausgabewege.md` mit Navigationseintrag unter „Messpfad und Freigabe“.
Die Wiki-Session (`feat/wiki-lebendig`) baut gerade Navigation und Theme um; deshalb liegt
die Seite hier und wird erst nach deren Merge eingehängt. Wer sie übernimmt: Text unter der
Linie unverändert nach `docs/uebersicht/ausgabewege.md` kopieren, Links von `../../` auf
`../` prüfen, Navigationseintrag in `zensical.toml` ergänzen, strikten Build laufen lassen.

**Quellen:** [Vergleich vom 13.11.](../../quellen/ausgabewege-vergleich-2026-11-13.md),
[UX2-Prüfbericht](../../quellen/ux2-pruefung-2026-11-13/ux2-bericht.md),
[Vierkanal-Spec](2026-11-11-gsvmulti-takt-vierkanal-design.md),
[GSVmulti-Protokoll](../../GSVMULTI_PROTOCOL.md).

**Offen vor der Übernahme:** Am 13.11. hat Herr Kaulitz Werkbank und Wege abgenommen. Die
Oberfläche zeigt aber weiter „Testfreigabe – nicht abgenommen, keine Messfreigabe“, und
`release_block` sperrt die DUT-Ausgabe. Ob und wie das nach der Abnahme geändert wird,
entscheidet Leonhard (TODO). Bis dahin beschreibt die Seite den Stand der Oberfläche.

---

# Ausgabewege zu GSVmulti

Der Pi liest den Prüfling optisch und gibt jeden Messtakt an GSVmulti auf einem
Windows-PC weiter. Dafür gibt es drei Wege. Alle drei liefern dasselbe Telegramm und
dieselbe Kanalbelegung. Sie unterscheiden sich im Kabel, in der Rückmeldung an den Pi und
darin, wie gut sich eine Störung erkennen lässt.

## Die drei Wege auf einen Blick

```text
Netzwerk über Brücke   Pi ──LAN/VPN, TLS──▶ Windows-App ──Portpaar──▶ GSVmulti
UART über Brücke       Pi ──UART-Kabel──▶ USB-Seriell ──▶ Windows-App ──Portpaar──▶ GSVmulti
UART direkt            Pi ──UART-Kabel──▶ USB-Seriell ─────────────────────────▶ GSVmulti
```

Das **Portpaar** ist ein virtuelles Paar serieller Schnittstellen (com0com): Die Windows-App
schreibt auf die eine Seite, GSVmulti liest die andere wie einen echten COM-Port.

| | Netzwerk über Brücke | UART über Brücke | UART direkt |
| --- | --- | --- | --- |
| Hardware am PC | Netzwerk, com0com | USB-Seriell-Adapter, Kabel, com0com | USB-Seriell-Adapter, Kabel |
| Windows-App im Messpfad | ja | ja | nein, nur zum Einrichten |
| Übertragung | TLS über TCP | 460 800 Baud | 115 200 Baud |
| Takt | bis 10 Hz | bis 10 Hz | bis 10 Hz |
| Rückmeldung an den Pi | jede Zeile quittiert | jede Zeile quittiert | keine |
| Empfangstest in der App | ja | ja | nein |
| Verhalten bei Störung | verbindet neu, füllt bis 50 fehlende Takte als ungültig auf | wie Netzwerk | Pi merkt nichts |
| Gemessen am 13.11. | lückenlos, Empfangstest 600/600 | Läufe lückenlos, aber Rahmenfehler auf der Leitung | lückenlos |

## Welcher Weg wofür?

- **Netzwerk über Brücke** ist der robusteste Weg und am besten zu diagnostizieren. Jede
  Zeile wird quittiert, Ausfälle sind im Protokoll sichtbar. Er braucht ein Netz zwischen Pi
  und PC und die Windows-App im Messpfad. **Empfohlen, wenn ein Netz vorhanden ist.**
- **UART direkt** ist am einfachsten: Kabel, Adapter, fertig. Der Pi sendet aber blind.
  Fällt der Adapter aus oder ist GSVmulti nicht bereit, merkt das niemand. Geeignet für
  kurze Versuche ohne Netz.
- **UART über Brücke** verbindet das Kabel mit der Kontrolle durch die App. Bei 460 800 Baud
  traten am 13.11. Rahmenfehler auf (unlesbare Zeilen, Neuverbindungen). Für den Dauerbetrieb
  braucht dieser Weg noch eine Prüfsumme mit Wiederholung oder eine niedrigere Rate
  ([Spec-Entwurf](2026-11-13-uart-pruefsumme-design.md)).

## Was GSVmulti empfängt

Alle Wege senden den **Vierkanal-Takt**: einmal je Takt eine Zeile
`%wert;gültig;takt;zeit` mit Zeilenende CR LF.

| Kanal | Inhalt |
| --- | --- |
| 1 Wert | gelesener Messwert. Bei ungültigem Takt hält Kanal 1 den letzten gültigen Wert; vor dem ersten gültigen Wert steht `99999999.0`. |
| 2 Gültig | `1` = gültig, `0` = ungültig (Übergang, unlesbar, veraltet). **Nur Zeilen mit Gültigkeit 1 auswerten.** |
| 3 Takt | laufende Taktnummer; Lücken zeigen verlorene Takte. |
| 4 Zeit | Aufnahmezeit des Bildes (gültig) bzw. Taktzeit (ungültig); kann an Wechseln zurückspringen, die Zeitachse ergibt sich aus Kanal 3. |

Wer Kanal 1 ohne Kanal 2 auswertet, verwendet bei Lesefehlern veraltete Werte. Deshalb sind
Kanal 2–4 in GSVmulti zwar ausgeblendet, werden aber mit aufgezeichnet.

## Einrichten

**In GSVmulti (alle Wege):**

1. Die Vierkanal-Session aus der Windows-App laden. Kanäle 2–4 sind darin ausgeblendet.
2. *Configure Recording → Advanced → „Record Hidden Channels“* einschalten. Das ist Pflicht
   und wird nicht in der Session gespeichert.
3. Im Recorder die Kanäle der neuen Session wählen. GSVmulti behält sonst die alte Auswahl.
4. *Data Frequency* auf denselben Takt wie an der Werkbank stellen.
5. Für Kanal 1 *Autoscale Y* ausschalten und Min/Max fest einstellen.

**Netzwerk über Brücke:** Windows-App installieren, Pi mit dem Kopplungscode koppeln
(Werkbank → „Brücke einrichten…“), Portpaar wählen, Empfangstest laufen lassen. An der
Werkbank im Laufstart „Netzwerk über Brücke“ wählen.

**UART über Brücke:** wie Netzwerk, aber eigene Kopplung für diesen Weg und den
USB-Seriell-Adapter in der App wählen. An der Werkbank den UART-Empfang vorbereiten.

**UART direkt:** In der Windows-App nur Adapter wählen und die Session erzeugen. An der
Werkbank „UART direkt“ wählen und den Hinweis bestätigen (der Haken wird nie gemerkt). Nach
dem Abziehen des Adapters GSVmulti neu starten.

Den Anschluss am Pi beschreibt die [Hardware-Seite](../../HARDWARE_PROFILE.md): Nutzdaten auf
`/dev/ttyAMA0`, nie GPIO-Pegel direkt an RS-232.

## Wenn etwas nicht ankommt

| Beobachtung | Wahrscheinliche Ursache | Abhilfe |
| --- | --- | --- |
| Aufnahme in GSVmulti 0 Byte | falsche Session (Einkanal) oder Recorder mit alter Kanalauswahl | Session aus der App neu laden, Kanäle im Recorder wählen |
| Kanäle 2–4 fehlen in der Aufnahme | „Record Hidden Channels“ aus | einschalten, gilt nur bis zum Neustart von GSVmulti |
| App meldet `uart_frame_invalid` | Bitfehler auf der UART-Leitung | Kabel kürzen bzw. tauschen, Netzwerk verwenden |
| UART direkt: „serial port occupied“ | UART-Empfang der Brücke hält den Port | Laufstart gibt ihn inzwischen selbst frei; sonst „UART-Empfang beenden“ |
| Nach LAN-Ausfall keine Werte | Brücke verbindet neu | warten; ab 50 fehlenden Takten Lücke im Takt-Kanal |

Für die Fehlersuche exportiert die Windows-App ein Diagnoseprotokoll (`details.jsonl`,
Zeit je Zeile, Zugangsdaten geschwärzt). Auf dem Pi steht jeder Lauf mit Ausgabeprotokoll
unter `var/live/`.
