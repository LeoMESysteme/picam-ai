# Freigegebener Mock der Werkbank-Neugestaltung

Animierter Klick-Prototyp (Simulation, keine echten Messwerte), am
2026-11-04 von Leonhard Hentschke als Gestaltungsreferenz freigegeben.
Spec: [../2026-11-04-werkbank-redesign-design.md](../2026-11-04-werkbank-redesign-design.md).

Bauen und ansehen:

```bash
./build.sh                       # erzeugt mock.html (bettet plate.b64 ein)
python3 -m http.server 8790      # dann http://<host>:8790/mock.html
```

Sprungmarken: `mock.html#t=10` (Fokus), `#t=46` (Vorschlag), `#t=58`
(Lauf), `#t=69` (Rahmen verdeckt), `#t=78` (Streamstillstand); `&play`
spielt weiter. Leertaste = Abspielen/Pause, ←/→ = Kapitel.

`img/still.jpg` ist das echte Standbild aus `live-20261030T133635Z`;
`plate.b64` ist derselbe LCD-Ausschnitt ohne Zeichen, auf den der Mock
den simulierten Wert in 5×7-Punkten zeichnet.
