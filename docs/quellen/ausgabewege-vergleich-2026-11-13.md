# Vergleich der drei GSVmulti-Ausgabewege (Stand 2026-11-13)

Quelle für den späteren Wiki-Eintrag. Beruht auf der Windows-Prüfung UX2 vom 13.11.2026
(`docs/quellen/ux2-pruefung-2026-11-13/`) und den Pi-Läufen desselben Tages. Kein Abnahmebeleg.

| | Netzwerk über Brücke | UART über Brücke | UART direkt |
| --- | --- | --- | --- |
| Strecke | Pi → LAN/VPN (TLS) → Windows-App → com0com-Portpaar → GSVmulti | Pi → UART-Kabel → USB-Seriell-Adapter → Windows-App → Portpaar → GSVmulti | Pi → UART-Kabel → USB-Seriell-Adapter → GSVmulti |
| Hardware am PC | Netzwerk, com0com | USB-Seriell-Adapter, Kabel, com0com | USB-Seriell-Adapter, Kabel |
| Windows-App im Messpfad | ja | ja | nein (nur Einrichtungshilfe) |
| Rate | 10 Hz | 460 800 Baud, 10 Hz | 115 200 Baud, 10 Hz (36 Byte je Takt) |
| Vierkanal-Takt, Kanal 1 hält | ja | ja | ja |
| Gemessen 13.11. | Empfangstest 600/600, Läufe 854–2546 Takte lückenlos, kein Abbruch | Läufe 1040/1181/2695 Takte lückenlos; Empfangstest zweimal abgebrochen (3/600, 124/600) | Läufe 2050/1392 Takte lückenlos |
| Störungen | keine; nach LAN-Ausfall sperrte die Brücke (Fix 53fbbd6, Nachprüfung offen) | `uart_frame_invalid`, Kernelzähler ttyAMA0 fe 232; bis 5 Neuverbindungen in 4,5 min | keine Übertragungsfehler sichtbar |
| Verhalten bei Störung | Neuverbindung, bis 50 fehlende Takte als ungültig aufgefüllt | wie Netzwerk; der Empfangstest endet bei jeder Neuverbindung | Pi merkt nichts (nur TX); abgezogener Adapter: Pi schreibt ins Leere, GSVmulti muss neu starten |
| Rückmeldung an den Pi | jede Zeile quittiert (COM-Übergabe) | wie Netzwerk | keine; belegt ist nur die Treiberübergabe |
| Empfangstest in der App | ja | ja, störanfällig | nein |
| Einrichtung | Kopplungscode, Portpaar | eigene Kopplung je Weg, Portpaar, UART-Empfang an der Werkbank | Adapter wählen, Session erzeugen, Werkbank „UART direkt“ bestätigen |
| Abnahme | nicht abgenommen (Testfreigabe) | nicht abgenommen (Testfreigabe) | Prototyp, nicht abgenommen |

**Einordnung.** Netzwerk ist am robustesten und am besten diagnostizierbar, braucht aber Netz
und die App im Messpfad. UART direkt ist am einfachsten und lief bei 115 200 Baud fehlerfrei,
ist aber blind (keine Quittung, kein Empfangstest). UART über Brücke verbindet Kabel und
App-Kontrolle, ist bei 460 800 Baud aber fehleranfällig; für den Produktiveinsatz braucht es
Prüfsumme mit Wiederholung, eine niedrigere Rate oder eine bessere Leitung. Ob Rate oder
Kabel den Unterschied macht, klärt ein Gegentest der Brücke mit 115 200 Baud (Rate heute fest).
