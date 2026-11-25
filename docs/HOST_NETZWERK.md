# Host-Netzwerk: WLAN-Wächter

Der Pi hängt nur am WLAN `me-systeme-1` (`eth0` ohne Kabel). Erreichbar ist er
über Tailscale, und das braucht diese WLAN-Verbindung.

## Warum es den Wächter gibt

Am 13.11.2026 war der Pi von 02:52 bis 09:15 Uhr nicht erreichbar. Abgestürzt
war er nicht, das zeigt das Journal des vorigen Boots:

1. 02:49 Uhr: Die Verbindung nach außen bricht ab (DNS-Timeouts,
   Tailscale-Relay nicht erreichbar).
2. 02:52:51 Uhr: Der Access Point meldet den Pi ab (`reason=6`).
3. Beim Neuverbinden läuft der 4-Way-Handshake in einen Timeout.
   `wpa_supplicant` wertet das als falsches Passwort (`WRONG_KEY`).
4. NetworkManager fragt deshalb einen Secret-Agent nach einem neuen Schlüssel.
   Ohne Desktop-Sitzung antwortet keiner, nach 2 min folgen `no-secrets` und
   `failed`.
5. NetworkManager sperrt danach die automatische Verbindung bis zum Neustart,
   obwohl das Passwort gespeichert ist (`psk-flags=0`, NM 1.52.1). In
   6 Stunden gab es keinen einzigen neuen Versuch.

Eine manuelle Aktivierung mit `nmcli connection up` hebt diese Sperre auf.
Genau das übernimmt der Wächter.

## Was er tut

`picam-wlan-watchdog.timer` startet jede Minute `picam-wlan-watchdog.service`,
erstmals 3 min nach dem Booten. Das Skript
`/usr/local/lib/picam-wlan-watchdog/run` (Quelle:
`scripts/picam-wlan-watchdog`) liest den NM-Gerätezustand von `wlan0`:

| Zustand | Reaktion |
| --- | --- |
| `100` verbunden (auch AP-Modus `MEhub-Setup`) | nichts; Zähler zurücksetzen |
| `10` unmanaged, `20` unavailable (z. B. Funk aus) | nur protokollieren |
| alles andere (getrennt, verbindet, need-auth, failed) | Zähler in `/run/picam-wlan-watchdog.misses` erhöhen |

Nach drei Fehlschlägen hintereinander, also etwa 2–3 min ohne Verbindung,
ruft der Wächter `nmcli --wait 60 connection up id me-systeme-1 ifname wlan0`
auf. Danach beginnt die Zählung von vorn. Ob der Uplink hinter dem AP
funktioniert, prüft der Wächter nicht. Das kann der Pi nicht beheben.

Schnittstelle, Verbindungsname und Schwelle stehen nur in
`systemd/picam-wlan-watchdog.service` (`Environment=`).

## Einrichten, prüfen, abschalten

```bash
sudo ./scripts/picam-wlan-watchdog-install.sh       # installiert und aktiviert
systemctl list-timers picam-wlan-watchdog.timer
journalctl -u picam-wlan-watchdog.service -n 20 --no-pager
sudo systemctl disable --now picam-wlan-watchdog.timer   # Rückbau
```

Solange `wlan0` verbunden ist, schreibt der Dienst nichts ins Journal außer den
systemd-Start/Ende-Zeilen.

## Nebenbefund

`rm520n-connect.service` (MEHub, aktiviert) wartet alle ~70 s vergeblich auf
`/dev/mhi_QMI0`, weil kein 5G-Modem eingebaut ist. Am Netz ändert er nichts,
er füllt nur das Journal. Abschalten:
`sudo systemctl disable --now rm520n-connect.service`.
