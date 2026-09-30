# Einrichtungsassistent für Ernte-Aufstellungen — Implementierungsplan

> **Für Codex:** Aufgaben der Reihe nach umsetzen, jede testgetrieben (erst
> ein fehlschlagender Test, dann der Code). Schritte mit Checkbox (`- [ ]`).
> Parallel dazu erntet der Nutzer mit Claude weiter an der Kamera. Die Regeln
> zur **Parallelarbeit** unten sind verbindlich.

**Ziel:** Eine neue Ernte-Aufstellung soll in 5–10 statt 10–40 Minuten
eingerichtet sein, und schlechte Aufstellungen sollen **vor** der Ernte
auffallen, nicht erst im Leser. Heute macht Claude dafür jeden Schritt von
Hand: Übersichtsbild ansehen, Kontrast messen, Spiegelungen suchen, vier
Stützpunkte im Koordinatenraster ablesen, Punktraster anpassen,
Abtastpunkte prüfen, Stabilität messen. Das wird automatisiert.

**Ergebnis:** `scripts/harvest-setup.py assist` erledigt nach einem
Kommando Fokus-Sweep, Standbild, automatische Punktraster-Anpassung,
Qualitätsprüfungen mit Ampel (OK / WARNUNG / FEHLER), `proposal.json`,
Overlays und die Stabilitätsprüfung. Der Mensch sieht sich die Overlays an
und bestätigt wie bisher mit `confirm`. `confirm` verweigert bei einem
FEHLER, außer mit ausdrücklicher, begründeter Übersteuerung.

**Tech Stack:** Python 3.13 (System-venv), OpenCV, numpy, pytest, ruff.
Keine neuen Abhängigkeiten.

---

## Parallelarbeit (verbindlich)

Der Nutzer erntet währenddessen mit Claude auf **demselben Raspberry Pi**,
mit derselben Kamera und derselben SD-Karte.

1. **Eigener Worktree und Branch:**
   `git -C /home/me-systeme/picam-ai worktree add /home/me-systeme/picam-ai-assist -b feat/einrichtungsassistent master`.
   Nur dort arbeiten. `/home/me-systeme/picam-ai` (Checkout des Nutzers) und
   `/home/me-systeme/picam-ai-ernte` nie anfassen. Nicht nach `master`
   mergen und nicht auf `master` pushen. Den Branch pushen ist erlaubt
   (`git push -u origin feat/einrichtungsassistent`), gemergt wird nach
   Review durch Claude.
2. **Die Kamera nie öffnen:** kein Zugriff auf `/dev/video*`, kein
   `v4l2-ctl`, kein `--mode=real`. Nur ein Prozess kann die StreamCam halten;
   ein zweiter würde eine laufende Ernte abbrechen. Alle Tests arbeiten mit
   synthetischen Bildern oder injizierten Kameraobjekten.
3. **`var/` nur lesen.** `var/` gibt es nur einmal
   (`/home/me-systeme/picam-ai/var`, Symlink in Worktrees), eine zweite
   Kopie existiert nicht. Nichts darin schreiben, verschieben oder löschen.
   Testausgaben nach `tmp_path`.
4. **Schreiblast klein halten:** Während einer Aufnahme verwirft die
   Kamera schon heute 18–30 % der Bilder, weil die SD-Karte nicht nachkommt.
   Kein `pip install`, keine großen Dateien, keine Kopien von Bilddaten. Die
   volle Testsuite (≈ 3,5 Minuten) höchstens nach Abschluss einer Aufgabe
   laufen lassen, sonst nur die betroffenen Testdateien. Liegt eine Datei
   `/home/me-systeme/picam-ai/var/RECORDING_IN_PROGRESS`, mit der vollen
   Suite warten, bis sie verschwindet.
5. venv: `/home/me-systeme/picam-ai/.venv/bin/python` und `…/pytest`,
   Tests aus dem Worktree starten:
   `cd /home/me-systeme/picam-ai-assist && PYTHONPATH=src /home/me-systeme/picam-ai/.venv/bin/pytest -q <datei>`.
   Hat der Worktree kein `.venv`, einen Symlink auf das des
   Haupt-Checkouts anlegen und ihn nicht committen.

## Projektregeln, die hier greifen

* `AGENTS.md` ist verbindlich, vor allem: Unlesbares ablehnen statt raten,
  **kein Erfinden** (fehlt ein Wert, wird abgelehnt, nicht ein Vorgabewert
  eingesetzt), CHANGELOG-Eintrag **im selben Commit** wie Code unter
  `src/`/`scripts/`, Meldungen deutsch (ASCII-Umschrift in Code-Strings wie im
  Bestand erlaubt).
* **Der Leser bleibt, wie er ist.** `src/dispread/ocr/` (Normierung,
  Vorlagen, Schwellen) wird nicht verändert. Stufe 2 des Dot-Matrix-Lesers ist
  eingefroren (VALIDATION.md 2026-09-29), eine Entwicklungsrunde dazu macht
  Claude getrennt. Der Assistent darf `dotmatrix_sampling.sample_image`
  lesend benutzen.
* Schwellen des Assistenten sind **Vorabwerte**. Sie stehen als benannte
  Konstanten mit Kommentar „Vorabwert, aus den Aufstellungen vom
  2026-09-29“ im Code, nicht verstreut.
* Nach jeder Aufgabe: `ruff check src tests examples scripts` sauber, die
  betroffenen Tests grün. Am Ende die volle Suite grün.

## Hintergrund: was heute von Hand passiert

**Geometrie der Anzeige** (Displaytech 161A, 16 Zellen × 1 Zeile, Zeichen
5 × 7 Punkte plus Cursorzeile): Das entzerrte Bild ist 400 × 160 px, das
Raster `left=0, pitch=25, top=17.78, bottom=160` (8 Zeilen: 7 Glyphenzeilen
und die Cursorzeile). Eine Zelle hat 6 Punktspalten (5 Punkte und 1 Lücke),
die Punktspaltenbreite ist `ph = 25/6`, die Zeilenhöhe `pv = (160·8/9 −
160/9)/7`. Punktmitte von Spalte `c` (0…95, `c % 6 != 5`) und Zeile `r`
(0…6): `x = (c + 0.5)·ph`, `y = 160/9 + (r + 0.5)·pv`.

**Warum der Glasdetektor nicht reicht:** `glassquad.glass_quad_in_region`
(`propose` ohne `--quad`) trifft an der StreamCam oft Blende oder Reflexe
statt des Glases. Das Quad kommt deshalb aus einer **Punktraster-Homographie**:
Punkte im Bild finden, jedem Punkt Zelle, Spalte und Zeile zuordnen und die
Homographie Bild → Raster anpassen. Das Quad ist das Urbild des Rechtecks
400 × 160.

**Gemessene Stolpersteine:**
* Das entzerrte Bild ist senkrecht etwa 4-fach gestreckt (Quelle ~370 ×
  47 px → 400 × 160). Isotrope Glättung und Erosion finden dann jeden Punkt
  doppelt, bei halben Zeilen. Die Glättung muss **richtungsabhängig** sein
  (Sigma und Kernel je Achse aus dem Maßstab Quelle → entzerrt), siehe
  Referenzcode.
* Die Iteration braucht eine gute Startlage. Claude liest heute vier
  Stützpunkte im Koordinatenraster ab: die Mitte von Spalte 2 der Zelle 1
  oben und unten sowie Zelle 12 oben links und unten Mitte. Das soll
  automatisch geschehen (Aufgabe 1).
* Ein Quad aus der alten, isotropen Suche tastete bei `sc3` um 0,2
  Punktzeilen zu hoch ab (VALIDATION.md, „Profilkorrektur `sc3b`“).

**Referenzcode** (Claudes Skript, lief erfolgreich bei `sc4`, `sc5`, `ab1`,
`ab2` und `sc3b`, noch mit handgelesenen Stützpunkten):

```python
# Punktraster-Anpassung: python latfit.py FRAME OUTQUAD x,y:c,r ... (4 Stuetzpunkte, Punktmitten)
import json,sys,cv2,numpy as np
img=cv2.imread(sys.argv[1]); out=sys.argv[2]
P=25.0; tt,tb=160/9,160*8/9; pv=(tb-tt)/7; ph=P/6
lat=lambda c,rw: np.stack([(np.asarray(c,float)+0.5)*ph, tt+(np.asarray(rw,float)+0.5)*pv],1)
src_pts=[];cr=[]
for a in sys.argv[3:]:
    xy,c_r=a.split(':'); src_pts.append([float(v) for v in xy.split(',')]); cr.append([float(v) for v in c_r.split(',')])
cr=np.array(cr)
H=cv2.getPerspectiveTransform(np.array(src_pts,np.float32),lat(cr[:,0],cr[:,1]).astype(np.float32))
S=4; W,Hh=400*S,160*S
for it in range(10):
    q=cv2.perspectiveTransform(np.array([[[0,0],[400,0],[400,160],[0,160]]],np.float32),np.linalg.inv(H))[0]
    Hr=cv2.getPerspectiveTransform(q,np.array([[0,0],[W,0],[W,Hh],[0,Hh]],np.float32))
    g=cv2.cvtColor(cv2.warpPerspective(img,Hr,(W,Hh),flags=cv2.INTER_CUBIC),cv2.COLOR_BGR2GRAY).astype(np.float32)
    sy=Hh/np.linalg.norm(q[3]-q[0]); sx=W/np.linalg.norm(q[1]-q[0])
    gb=cv2.GaussianBlur(g,(0,0),sigmaX=0.7*sx,sigmaY=0.7*sy); depth=cv2.GaussianBlur(g,(0,0),sigmaX=6*sx,sigmaY=6*sy)-gb
    mn=cv2.erode(gb,np.ones((int(2*round(1.2*sy)+1),int(2*round(1.2*sx)+1)),np.uint8))
    ys,xs=np.where((gb==mn)&(depth>8))
    src=cv2.perspectiveTransform(np.stack([xs,ys],1).astype(np.float32)[None],np.linalg.inv(Hr))[0]
    tp=cv2.perspectiveTransform(src[None],H)[0]; colc=tp[:,0]/ph-0.5; rowc=(tp[:,1]-tt)/pv-0.5
    c=np.round(colc); rw=np.round(rowc)
    ok=(np.abs(colc-c)<0.3)&(np.abs(rowc-rw)<0.4)&(rw>=0)&(rw<=6)&(c>=0)&(c<96)&((c%6)!=5)
    H,_=cv2.findHomography(src[ok],lat(c[ok],rw[ok]).astype(np.float32),0)
    d=cv2.perspectiveTransform(src[ok][None],H)[0]-lat(c[ok],rw[ok])
    print(it,"dots",len(src),"zugeordnet",int(ok.sum()),"rms %.2f Spalten %.2f Zeilen"%(np.sqrt((d[:,0]**2).mean())/ph,np.sqrt((d[:,1]**2).mean())/pv),"zellen",sorted(set((c[ok]//6).astype(int).tolist())))
rr=rw[ok]; cc=c[ok]
print("zeilen-bias",[round(float(d[rr==r,1].mean()/pv),2) for r in range(7) if (rr==r).any()])
print("zellen-bias",[round(float(d[(cc//6)==k,0].mean()/ph),2) for k in sorted(set((cc//6).astype(int)))])
quad=cv2.perspectiveTransform(np.array([[[0,0],[400,0],[400,160],[0,160]]],np.float32),np.linalg.inv(H))[0]
print("quad",quad.round(1).tolist()); json.dump(quad.tolist(),open(out,"w"))
```

**Gemessene Werte der Aufstellungen** (Grundlage der Vorabschwellen):

| Aufstellung | Punktkontrast* | Gain | px je Punktspalte | Anpassung zugeordnet / RMS (Spalten, Zeilen) | Befund |
| --- | --- | --- | --- | --- | --- |
| `sc3` (`sc3b`) | 34,6 | 5 | 4,29 | 197/198, 0,13 / 0,17 | Punktschwärze fällt über die Zeile ab |
| `sc4` | 27,5 | 13 | 3,43 | 153/153, 0,11 / 0,14 | Schattenband oben |
| `sc5` | 41,3 | 2 | 4,24 | 159/162, 0,10 / 0,14 | gut |
| `ab1` | 42,2 | 1 | 4,32 | 190/193, 0,11 / 0,17 | gut |
| `ab2` | 31,2 | 4 | 3,39 | 175/183, 0,10 / 0,16 | **Spiegelkante durch Leerzelle 8 → Leser lehnt 100 % ab** |
| `sc6` | 20,8 (links 11–13, rechts 22–24) | – | 7,00 | 197/209, 0,13 / 0,14 | gut; Schrift zur Bildecke hin weicher |
| verworfen: Kamera von unten | 8,3 / 8,9 / 9,3 | 9–17 | – | – | blass, Lichtschleier |
| verworfen: Glanzfleck Deckenleuchte | – | – | – | – | weißes Rechteck über den Ziffern |
| verworfen: Spiegelung Monitor | – | – | – | – | dunkler Keil über Zellen 13–15 |
| verworfen: `sc6` erster Stand | – | – | – | – | Glanzfleck, 74–86 % gesättigt über Zellen 10–15 |
| verworfen: `sc6` zweiter Stand | 27,0 | – | 5,59 | 261/453, 0,17 / 0,22 | **Fensterrahmen verdeckt letzte Punktspalte von Zelle 15** (Helligkeit 44 statt 94) → Leser lehnt 100 % ab (`format`) |

\* Punktkontrast = 99. Perzentil von `GaussianBlur(σ=6) − GaussianBlur(σ=0,8)`
im Graubild über dem Textbereich, in Quellpixeln. Das ist Claudes Handmaß,
nicht `SampledImage.contrast` des Lesers. Beide sollen im Bericht stehen.

Stillbilder mit Profil liegen unter
`/home/me-systeme/picam-ai/var/diagnostics/<name>-still/frames/frame_000017.png`
für `sc3`, `sc4`, `sc5`, `ab1`, `ab2` (nur lesen). Bei `sc6` heißt das Bild
`frame_000015.png`. Die zugehörigen
bestätigten Quads stehen in `var/diagnostics/<name>-profile` (bei `sc3`:
`sc3b-profile`). Die Bilder der verworfenen Zwischenstände existieren nicht
mehr.

---

## Aufgabe 1: `src/dispread/dotlattice.py` — Punktraster-Anpassung ohne Handarbeit

**Zweck:** Aus einem Quellbild (1920 × 1080) und einer groben Hinweisbox das
Quad per Punktraster-Homographie bestimmen, mit Gütemaßen, oder begründet
ablehnen.

**Schnittstelle (Vorschlag, anpassbar):**

```python
@dataclass(frozen=True)
class LatticeFit:
    quad: list[list[float]]          # Quellbildpixel, TL, TR, BR, BL
    n_dots: int                      # gefundene Punktkandidaten
    n_assigned: int                  # zugeordnet
    rms_cols: float                  # Restfehler in Punktspalten
    rms_rows: float                  # in Punktzeilen
    cells: tuple[int, ...]           # Zellen mit zugeordneten Punkten
    row_bias: tuple[float, ...]      # mittlerer Rest je Zeile (Zeilen)
    cell_bias: tuple[float, ...]     # mittlerer Rest je Zelle (Spalten)

def fit_lattice(image_bgr, hint_box, *, seeds=None) -> LatticeFit | str
    # str = Ablehnungsgrund, z. B. "zu_wenige_punkte", "keine_startlage",
    # "anpassung_divergiert", "restfehler_zu_gross"
```

- [ ] **1a Kern der Anpassung** aus dem Referenzcode als Funktion
  `refine(image, H_init) -> LatticeFit`: richtungsabhängige Glättung,
  Zuordnung, `findHomography` mit Methode 0 (kleinste Quadrate) auf allen
  Zugeordneten, 10 Iterationen oder bis zur Konvergenz. Tests mit
  synthetischen Bildern: ein gerendertes Display (`tests/dotmatrix_helpers.py`
  `render`, dort mit `GRID` des Tests, hier mit dem 400 × 160-Raster oben),
  per bekannter Homographie in ein 1920 × 1080-Bild gesetzt (Drehung ±15°,
  Perspektive, Maßstab 3,4–4,4 px je Punktspalte, Rauschen σ 3). Die Ecken
  des angepassten Quads liegen ≤ 1 px von der Wahrheit, `rms_cols` < 0,2.
- [ ] **1b Startlage automatisch** (`seeds=None`): innerhalb der Hinweisbox
  Punktkandidaten im **Quellbild** finden (lokale Minima, Tiefe gegen eine
  grobe Glättung). Dann:
  1. die Zeilenrichtung schätzen (Hauptachse der Punktwolke oder
     Hough-Linien durch die Punkte),
  2. den Punktabstand längs und quer dazu aus der Autokorrelation bzw.
     einem Histogramm der Projektionen schätzen (Spaltenabstand ≈
     Zeilenabstand · 0,77 im Display; die Zellperiode entspricht 6
     Spaltenabständen),
  3. die Zeichenzeile quer begrenzen (7 Punktzeilen) und die Zellperiode
     längs über die Lücke nach je 5 Spalten festlegen,
  4. daraus eine affine Startlage bauen und an `refine` geben.

  **Doppeldeutigkeit** um eine Punktspalte, eine Zelle oder eine Zeile ist
  die Hauptgefahr. Deshalb mehrere Kandidaten-Startlagen prüfen (Versatz
  −1/0/+1 Zelle und Zeile) und nur annehmen, wenn eine klar die meisten
  Punkte mit kleinstem Rest erklärt. Sonst `"startlage_mehrdeutig"`
  zurückgeben, nicht raten. Tests: dieselben synthetischen Bilder ohne Seeds.
  Dazu ein Fall mit kaum Zeichen (nur `+` und eine Ziffer) → Ablehnung statt
  eines falschen Rasters.
- [ ] **1c Absicherung der Zuordnung:** Die Zelle 0 muss Punkte haben, denn
  das Vorzeichen `+` ist immer da. Die Zeilen 0–6 müssen belegt sein, die
  Cursorzeile 7 muss leer bleiben. Fällt eine Bedingung, wird abgelehnt.
  **Nachtrag 2026-09-29 (`sc6`):** Zusätzlich dürfen die Leerzellen des
  Formats `gsv2as_v1` keine zugeordneten Punkte haben: Zelle 8 (zwischen
  Zahlenblock und Einheit) und die Zellen 13–15. Ein kleiner Restfehler
  beweist **nicht**, dass das Raster stimmt. Bei `sc6` lag eine Anpassung
  aus handgelesenen Stützpunkten gut zwei Punktspalten daneben und war
  geschert, trotzdem betrug der Restfehler nur 0,17 / 0,21. Das einzige
  Warnzeichen waren Punkte in Leerzelle 8. Regressionsfall: dieselbe
  Anpassung mit den Stützpunkten
  `527.5,515.6:0,3 558,543:7,6 1005,613.7:76,0 974.4,654.4:74,6` gilt für
  den verworfenen zweiten Stand, dessen Bild nicht mehr existiert.
  Deshalb synthetisch nachbauen: ein Raster um zwei Spalten verschoben
  → Ablehnung.
- [ ] **1d Regression auf echten Standbildern (nur lesen):** Ein Test mit
  Marker `@pytest.mark.skipif(not path.exists())` läuft über die fünf
  Standbilder `sc3`, `sc4`, `sc5`, `ab1`, `ab2`, als Hinweisbox die Bounding
  Box des bestätigten Profil-Quads plus 10 % Rand. Das automatisch
  angepasste Quad weicht an jeder Ecke ≤ 1,5 px vom bestätigten ab. Bei
  `sc3` gegen `sc3b-profile` vergleichen, nicht gegen `sc3-profile`.

## Aufgabe 2: `src/dispread/setup_checks.py` — Qualitätsprüfungen mit Ampel

**Zweck:** Aus Standbild und `LatticeFit` Kennzahlen berechnen und je
Prüfung OK / WARNUNG / FEHLER vergeben. Die Kennzahlen stehen immer im
Bericht, die Ampel ist nur die Lesart.

- [ ] **2a Punktkontrast:** Handmaß wie in der Tabelle oben, dazu
  `sample_image(...).contrast` aus dem entzerrten Bild mit dem Raster.
  Vorabschwellen: FEHLER < 15, WARNUNG < 25.
- [ ] **2b Kanten im Hintergrund (Spiegelkanten):** Je Zelle 0–15 im
  entzerrten Bild die Helligkeit der **Nicht-Punkte** betrachten: Punkte,
  deren Wert nahe am Zellhintergrund liegt, oder alle Punkte einer
  Leerzelle. Innerhalb jeder Zelle und zwischen Nachbarzellen die
  Helligkeitsstufe messen, zum Beispiel als Spanne der Hintergrundpunkte je
  Zelle relativ zum Median-Hintergrund oder als stärkster Gradient der
  Hintergrundpunkte. Fällt eine starke Stufe in eine Zelle, ist das FEHLER,
  eine mittlere ist WARNUNG. Maßstab: Bei `ab2` muss Zelle 8 eine WARNUNG
  oder einen FEHLER ergeben, denn dort läuft die Kante, an der der Leser
  gescheitert ist. `sc5` und `ab1` müssen OK sein. Die Schwellen so wählen,
  dass das auf den echten Standbildern gilt, und die gemessenen Werte im
  Test festhalten. Synthetisch: gerendertes Display mit überlagerter
  Helligkeitskante durch eine Leerzelle → Befund. Mit weichem Verlauf ohne
  Kante → OK.
- [ ] **2c Glanz:** Anteil gesättigter Pixel (≥ 250) im Glas, dazu ein
  zusammenhängender heller Fleck deutlich über dem Hintergrund. FEHLER bei
  Sättigung > 2 % (entspricht `MAX_SATURATED` des Lesers) oder bei einem
  Fleck über den Zellen 0–8. Synthetisch testen.
- [ ] **2d Auflösung:** px je Punktspalte, wie `min_source_dot_column_px`
  in `propose`. FEHLER unter 2,6, WARNUNG unter 3,2.
- [ ] **2e Raster:** aus `LatticeFit`. FEHLER bei `rms_cols` > 0,25,
  `rms_rows` > 0,3 oder weniger als 80 % zugeordnet, WARNUNG bei einem
  Betrag über 0,08 in `row_bias` oder `cell_bias`.
- [ ] **2f Stabilität:** zwei Standbilder im Abstand von ≥ 30 s über
  `frame_alignment.estimate_quad_shift`. FEHLER über 0,5 px, WARNUNG über
  0,2 px oder bei einer unzuverlässigen Schätzung. Gemessen wurden bei festen
  Aufstellungen 0,01–0,13 px, bei bewegter Kamera 45–190 px.
- [ ] **2h Rahmen verdeckt Randzellen (Nachtrag `sc6`):** Die äußeren
  Punktspalten (Zelle 0 Spalte 0, Zelle 15 Spalte 4) mit dem Median der
  Nachbarspalten derselben Zelle vergleichen, dazu die Zeilen 0 und 6
  gegen die Innenzeilen. FEHLER, wenn eine Randspalte oder Randzeile in
  einer Leerzelle deutlich dunkler ist (Vorschlag: unter 70 % der
  Nachbarn). Bei `sc6` (zweiter Stand) waren es 44 gegen 94. Synthetisch
  testen, dazu ein Fall mit sauberem Rand (keine Meldung).
- [ ] **2i Gegenlesen mit dem eingefrorenen Leser (Nachtrag `sc6`):** Wenn
  eine Vorlagendatei samt sha256 übergeben wird, liest `assist` die
  Standbilder mit `DotMatrixReader` und meldet Lesequote und
  Ablehnungsgründe. Die Anzeige wird dabei nicht mit einem Sollwert
  verglichen, der Assistent kennt ihn nicht. WARNUNG, wenn mehr als die
  Hälfte der Bilder mit `format` oder `zelle_unbekannt` abgelehnt wird.
  Nur Diagnose, kein FEHLER: eine neue Aufstellung soll ja gerade Neues
  zeigen. Der Leser bleibt unverändert, nur importieren.
- [ ] **2g Gesamturteil:** FEHLER, sobald eine Prüfung FEHLER meldet, sonst
  WARNUNG, sobald eine WARNUNG meldet, sonst OK. Ausgabe als dataclass und
  `to_dict()` für JSON.

## Aufgabe 3: Overlays

- [ ] **3a** `overlay_source.png`: Quellbild mit Quad, zugeordneten
  Punkten (grün) und nicht zugeordneten Kandidaten (rot), dazu die Ampel als
  Text.
- [ ] **3b** `overlay_sampling.png`: entzerrtes Bild ×4 mit den
  Abtastpunkten, Zeilen 0–6 rot und Cursorzeile blau, wie es Claude heute von
  Hand erzeugt. Zellen mit Kantenbefund aus 2b farbig umrandet.
- [ ] **3c** `overlay_checks.png`: kleine Kacheln mit dem Ausschnitt jeder
  auffälligen Zelle. Nicht nötig, wenn es den Umfang sprengt.

## Aufgabe 4: `harvest-setup.py assist` und Anpassung von `propose`/`confirm`

- [ ] **4a `propose --auto-quad`:** statt `--quad` bzw. Glasdetektor die
  Anpassung aus Aufgabe 1 verwenden. Das Raster ist fest
  `0,25,17.78,160`. Die Prüfungen aus Aufgabe 2 (ohne Stabilität) laufen
  mit und landen als `setup_checks` in `proposal.json`. Scheitert die
  Anpassung, Exit ≠ 0 mit Grund.
- [ ] **4b `assist`:** in einem Kommando `--out DIR --device-id … --session-id
  … [--hint-box …] [--stability-s 30]`. Ablauf:
  1. Fokus-Sweep wie `focus`, vorhandenen Code wiederverwenden, mit
     1 s Wartezeit je Fokuswert (Befund M-9: nach großen Sprüngen sonst
     veraltetes Pufferbild),
  2. Standbild aufnehmen (≥ 10 Bilder nach dem Einstellen verwerfen, dann
     ein Bild als PNG unter `DIR/still.png` speichern),
  3. Anpassung und Prüfungen,
  4. nach `--stability-s` Sekunden ein zweites Bild aufnehmen und die
     Stabilität prüfen,
  5. `DIR/proposal.json` mit `setup_checks` schreiben, dazu die Overlays,
  6. eine Zusammenfassung ausgeben: Ampel je Prüfung, Kennzahlen, Pfade und
     der fertige `confirm`-Befehl.

  **Hinweisbox automatisch**, wenn keine angegeben ist: ein grüner Bereich
  mit Punktstruktur, zum Beispiel über `glassquad` oder den Farbton. Findet
  sich keiner, Abbruch mit der Bitte um `--hint-box`. Der Kamerazugriff läuft
  nur über `_open_camera_io` bzw. eine injizierbare Fabrik. Die Tests
  ersetzen sie, wie es `tests/` für `focus` schon tut, per Monkeypatch mit
  synthetischen Bildern.
- [ ] **4c `confirm`:** Enthält `proposal.json` `setup_checks` mit Urteil
  FEHLER, verweigert `confirm` (Exit 2) und nennt die Prüfungen. Mit
  `--override-reason "…"` geht es trotzdem, der Grund landet im Profil.
  Das Profil erhält ein **optionales** Feld `setup_checks` (Urteil,
  Kennzahlen, gegebenenfalls `override_reason`). Das ist rückwärtskompatibel
  wie `reference_frame` (Task 10): Fehlt das Feld, bleibt `to_dict()` gleich,
  damit sich Prüfsummen bestehender Profile nicht ändern. Test: Ein
  bestehendes Profil aus `var/diagnostics/` laden und speichern ergibt
  dieselben Bytes. Das in `tmp_path` machen und nichts in `var/` schreiben.
- [ ] **4d** Die Hilfetexte sind deutsch. Im Skriptkopf den neuen Ablauf
  beschreiben.

## Aufgabe 5: Doku und Abschluss

- [ ] CHANGELOG je Commit mit Code, im Stil des Bestands (Problem /
  Änderung / Konsequenz).
- [ ] `docs/VALIDATION.md`: kurzer Abschnitt „Einrichtungsassistent:
  Regression auf echten Standbildern“ mit einer Tabelle: je Aufstellung
  automatische und bestätigte Ecken (Abweichung), Kennzahlen und Ampel.
  Keine neuen Messungen an der Kamera.
- [ ] Nicht anfassen: `TODO.md`, `docs/status.md`, `docs/open-questions.md`.
  Die pflegt Claude beim Merge.
- [ ] Übergabe: Branch gepusht, im letzten Commit oder in
  `docs/superpowers/plans/2026-09-29-einrichtungsassistent.md` unten eine
  Notiz „Stand der Umsetzung“: was fertig ist, was offen ist, welche
  Schwellen wie begründet sind und was auf echter Hardware noch zu prüfen
  ist. Der erste echte Lauf von `assist` an der Kamera geschieht mit dem
  Nutzer.

## Definition von „fertig“

* `harvest-setup.py assist` läuft in Tests mit injizierter Kamera durch und
  erzeugt `proposal.json` mit `setup_checks` sowie die Overlays.
* Die Anpassung ohne Stützpunkte trifft auf allen fünf echten Standbildern
  das bestätigte Quad auf ≤ 1,5 px.
* Die Kantenprüfung meldet bei `ab2` Zelle 8, bei `sc5` und `ab1` nichts.
* `confirm` verweigert bei FEHLER und nimmt eine Übersteuerung nur mit
  Grund an.
* Keine Änderung unter `src/dispread/ocr/`. Bestehende Profile laden und
  speichern bytegleich.
* `ruff` ist sauber, die volle Suite grün. Der Branch
  `feat/einrichtungsassistent` ist gepusht und nicht gemergt.

## Review-Schwerpunkte (für Claudes Review vor dem Merge)

1. **Falsches Raster um eine Spalte, Zelle oder Zeile verschoben** (die
   Doppeldeutigkeit aus 1b): Wird es sicher erkannt und abgelehnt?
2. **Kantenprüfung:** Schwellen belegt durch die echten Standbilder, nicht
   geraten. Weiche Verläufe (wie bei `sc3`) dürfen nicht als Kante gelten.
3. **Kein Kamerazugriff in Tests**, kein Schreiben in `var/`.
4. **Profil-Rückwärtskompatibilität** (Prüfsummen bestehender Profile).

## Stand der Umsetzung — 2026-09-29

`assist`, `propose --auto-quad`, Punktraster-Anpassung, Qualitätsprüfungen,
Overlays und die FEHLER-Sperre in `confirm` sind implementiert. Tests öffnen
keine Kamera; `var/` wurde nur gelesen. Fünf gespeicherte Standbilder treffen
ohne Stützpunkte das bestätigte Quad mit höchstens 0,25 px Eckabweichung;
auch die automatisch aus dem grünen Punktbereich gebildeten Hinweisboxen
treffen alle fünf Quads mit höchstens 0,25 px. `ab2` meldet die Spiegelkante
in Leerzelle 8, `sc5` und `ab1` keine Kante. Die Profilserialisierung ohne
neues Prüffeld ist bytegleich geprüft. Die Messwerte stehen in
`docs/VALIDATION.md`, Aufbau und Deutung in `docs/lab_journal.md`.

Die Ampelschwellen sind **Vorabwerte aus den Aufstellungen vom 2026-09-29**:
Punktkontrast <15/25 (FEHLER/WARNUNG), Hintergrundkante in Leerzellen
>20/10 und belegten Zellen >20/16, Sättigung >2 % oder zusammenhängender
heller Fleck ab 100 px über den linken Zellen, Auflösung <2,6/3,2 px je Punktspalte,
Raster-RMS >0,25 Spalten oder >0,3 Zeilen beziehungsweise <80 % Zuordnung,
Bias >0,08, Stabilitätsversatz >0,5/0,2 px (unzuverlässige Schätzung:
WARNUNG). Die `ab2`-Kante liegt auf
Frame 17 bei 13,5; `sc5` und `ab1` liegen bei 8 und 5. Das exakt
definierte Kontrastmaß auf Frame 17 ergibt bei `sc5` und `ab2` je 19 statt
der älteren Aufstellungswerte 41,3/31,2; Bild und Auswertebereich jener
Handwerte sind nicht belegt. Die Schwellen sind daher noch nicht allgemein
kalibriert.

Offen für den ersten **gemeinsamen Lauf mit dem Nutzer an echter Hardware**:
Kameraablauf, Bildpuffer und V4L2-Regler prüfen, Overlays ansehen,
Stabilitätsmessung bestätigen und die tatsächliche Einrichtungsdauer
erfassen. Ein Profil wird weiterhin erst nach menschlicher Sichtprüfung
bestätigt. Der Branch wird nicht nach `master` gemergt; Claude prüft ihn
vor der Übernahme.
## Nacharbeit 1 (Review Claude, 2026-09-29, Branch-Stand `9a71d35`)

**Urteil:** zurück an Codex, noch kein Merge. Das Grundgerüst ist brauchbar:
`confirm`-Sperre, Profilfeld (alle 14 vorhandenen Profile bleiben
bytegleich), Overlays, Ablauf von `assist`, kein Kamerazugriff in Tests.
Verschobene Stützpunkte (±1/±2 Spalten, ±1 Zelle, ±1 Zeile, geschert)
werden sicher abgelehnt.

**Messbasis korrigiert:** Die Punktkontrast-Werte 41,3 (`sc5`) und 31,2
(`ab2`) in der Tabelle oben lassen sich nicht nachstellen. Das exakt
definierte Maß ergibt auf allen Standbildern von `sc5` 18,9–19,2 und bei
`ab2` ähnlich. `sc3`, `ab1` und `sc6` passen (34,6 / 42,2 / 20,8). Die
Tabelle war Claudes Handmaß auf einem anderen Bereich. Maßgeblich ist das
exakt definierte Maß.

**Aufträge**, in dieser Reihenfolge:

0. **Zuerst auf das aktuelle `master` rebasen.** Damit kommen die
   Nachträge 1c/2h/2i, `bg_closing_v1` (Leser-Normierung, ändert
   `leser_kontrast`) und `--staging-root` dazu. Die Konflikte in CHANGELOG,
   VALIDATION und project_history sind reine Anhänge.
1. **1c Leerzellen:** In `refine` ablehnen, wenn Zelle 8 oder 13–15
   zugeordnete Punkte oder Quellkandidaten hat. Die Leerzellen als Parameter
   übergeben (Format `gsv2as_v1`), nicht fest verdrahten. Heute nimmt
   `fit_lattice` mit `-` statt `+` in Zelle 0 ein Raster 17,6 px neben jeder
   ganzzahligen Lage an (RMS 0,14 / 0,04, Punkte in Zelle 8)
   (`dotlattice.py:254-256`).
   Tests:
   * Raster synthetisch um 2 Spalten verschoben → Ablehnung.
   * `-` in Zelle 0 → Ablehnung mit eigenem Grund (`vorzeichen_kein_plus`).
2. **Zellen-Bias:** In `refine` ablehnen, wenn |`cell_bias`| oder
   |`row_bias`| über 0,15 liegt. Echte Bilder liegen bei höchstens 0,051.
   Heute wird Inhalt, der um 2 Spalten gegen die Hinweislage versetzt ist,
   angenommen: rechte Ecken 9–12 px daneben, `cell_bias` 0,26, nur WARNUNG
   (`dotlattice.py:257-275`, `setup_checks.py:150`). Test dazu.
3. **Pixelkonstanten skalieren:** alle festen Toleranzen aus dem geschätzten
   Punktabstand ableiten (`dotlattice.py:84, 95-100, 338, 362-367, 428,
   438`). Heute scheitert `sc6` (7 px je Spalte) mit `keine_startlage`.
   `sc6` (`var/diagnostics/sc6-still/frames/frame_000015.png`,
   `sc6-profile`) kommt in die Regression 1d (≤ 1,5 px), dazu synthetisch
   7 px je Spalte.
4. **Kantenprüfung:** nur Wertepaare im Zellinneren auswerten, heute läuft
   das Fenster in die Nachbarglyphe (`setup_checks.py:104-106`). Das `m` in
   Zelle 9 ergibt bei `sc6` einen Fehlalarm von 11,0. Im Zellinneren:
   `ab2` 9, `sc5` 5–6, `sc3` 2–3, `sc4` 1–2, `ab1` 2–2,5, `sc6` 2. Die
   Schwellen so setzen, dass `ab2` FEHLER ergibt und `sc3`–`sc6` sowie `ab1`
   OK (Vorschlag FEHLER > 8, WARNUNG > 6, als Vorabwert gekennzeichnet).
   Messwerte je Aufstellung im Test festhalten.
5. **Kontrast:** in float rechnen, weil `GaussianBlur` auf uint8 rundet
   (`sc4` kippt bei 25,0 bzw. 24,7). WARNUNG auf 17 senken, belegt durch
   `sc5` = 19 und `sc6` = 20, beide gut. FEHLER bleibt bei 15.
6. **2h und 2i** nach dem Plan oben umsetzen, mit synthetischen Tests.
7. **`run_assist`:**
   * das Ergebnis von `check_setup(first, fit)` ausgeben und bei FEHLER vor
     der Stabilitätswartezeit abbrechen,
   * `stability_elapsed_s` messen statt `args.stability_s` einzutragen.
8. **Laufzeit:** `fit_lattice` dauert auf dem Pi 40–78 s, die Suite 14,5
   statt 3,5 min. Die Kandidatensuche beschleunigen (`dotlattice.py:353-380`,
   `_optimize_quad`) oder die langsamen Tests markieren. Ziel: Suite wieder
   etwa 3,5 min.
9. **Tests:**
   * den Bytegleich-Test über alle vorhandenen Profile parametrisieren,
   * einen `assist`-Test mit echter `fit_lattice`/`check_setup`-Kette auf
     einem synthetischen Bild ergänzen.
10. **Doku neu rechnen:** VALIDATION und lab_journal mit dem finalen Code,
    einschließlich `sc6`. Die heutigen Zahlen stammen aus einem Zwischenstand
    (z. B. `sc3` 193/195 Δ 0,25 statt 196/198 Δ 0,06).

Kleinigkeiten:
* Ablehnungsgründe genauer benennen (`plus_nicht_gefunden` statt
  `startlage_mehrdeutig`, wenn Stützpunkte vorgegeben sind).
* Die Prüfung der Cursorzeile lehnt schon bei einem einzigen Kandidaten ab.
  Das ist sicher, aber anfällig für Staub.

## Nacharbeit 2 (Claude, 2026-09-30): Rasterversatz als Pflichtprüfung

Befund (VALIDATION.md 2026-09-30, Rasterversatz): Die von Hand angepassten
Raster von `ab3`/`ab4` (auch `ernte1`, `auf2`, `auf3`) lagen 0,4–0,9
Punktspalten neben den Punktmitten, geschert oder mit falschem
Punktabstand. Das Restmaß der Anpassung (0,17 / 0,26), die Leerzellen und
der Zellen-Bias waren trotzdem unauffällig. Abnahme 2 hat damit falsche
Profile geprüft. Ursache: Die Anpassung sucht Helligkeitsminima, bei
scharfen Bildern sind das oft die Punktränder.

Seit `217dc77` misst `dispread.lattice_offsets` den Versatz mit einem vom
Raster unabhängigen Maß: bekannter Text, Korrelation mit dem ROM-Muster je
Zelle und Halbzelle, Abtastung im Quellbild. `scripts/profile-regrid.py`
korrigiert damit bestehende Profile.

**Auftrag:**
1. **2j Rasterversatz** in `setup_checks.py`, aufbauend auf
   `dispread.lattice_offsets` (nicht neu schreiben).
   * Eingabe: Standbilder aus der Stabilitätsprüfung und der Zellentext aus
     dem seriellen Strom (die Anzeige steht während der Einrichtung).
   * Maß: der größte Betrag des Median-Versatzes, waagerecht je Halbzelle
     (`HALVES`), senkrecht je ganzer Zelle (`FULL`).
   * Schwellen, als Vorabwert gekennzeichnet:
     * FEHLER über 0,25 Punktspalten (mehr als die Verschiebungssuche des
       Lesers abdeckt) oder über 0,25 Punktzeilen,
     * WARNUNG über 0,15.
   * Messwerte echter Aufstellungen (je 20 Proben):
     * `sc5` 0,09, `sc6` 0,05, `sc4` 0,13, `sc3` 0,15, `ab1` 0,17,
       `ab2` 0,18 (waagerecht);
     * falsch: `ab4` 0,90, `auf3` 0,83, `auf2` 0,74, `ab3` 0,48,
       `ernte1` 0,39;
     * nach der Korrektur 0,02–0,09.
2. **Automatisch nachführen:** Nach `fit_lattice` einmal
   `lattice_offsets.refine_quad` über die Standbilder laufen lassen und das
   Ergebnis übernehmen, wenn die Prüfung an zurückgehaltenen Bildern besser
   ist. Danach 2j erneut prüfen.
3. **Tests:** synthetisch geschertes Raster (FEHLER), zu kleiner
   Punktabstand (FEHLER), richtiges Raster (OK). Echte Profile: `ab4-profile`
   gegen `ab4-profile-regrid1.json` (nur lesen, ohne Kamera).
4. `run_assist` gibt 2j im Bericht aus. Bei FEHLER entsteht kein Vorschlag.

### Review 2026-09-30 (Branch-Stand `815c35e`)

**Urteil: zurück an Codex.**
* Nacharbeit 1 ist im Wesentlichen erfüllt.
  * 151 Tests grün, ruff sauber.
  * `fit_lattice` braucht auf dem Pi jetzt 2–16 s.
  * Ganzzahlige Rasterverschiebungen werden sicher abgelehnt.
* **Nacharbeit 2 fehlt vollständig:** keine Prüfung 2j, kein `refine_quad`,
  kein serieller Zellentext in `assist`.

**Warum das blockiert:**
* Auf dem scharfen `ab4`-Standbild nimmt `refine` Startlagen an, die
  +0,3/+0,4 Spalten daneben liegen (RMS 0,164, Ecken 10,6 px neben
  `ab4-profile-regrid1.json`). Gebremst hat das nur die Zuordnungsquote in
  `check_setup`.
* Die automatische Anpassung liegt bei `ab4` 0,12–0,14 Spalten daneben und
  wird über die Zuordnung abgelehnt, also aus dem falschen Grund. Ein Fit
  mit 81 % Zuordnung ginge ungeprüft durch.

**Zusätzlich zu Nacharbeit 2, Punkte 1–4:**
* **Eckkonvention vereinheitlichen:**
  * `dotlattice` rechnet mit 400/160 (`_CORNERS`, `dotlattice.py:18`),
    `rectify` und `lattice_offsets` mit 399/159.
  * Das ist ein Maßstabsfehler von 0,25 %, bis 0,24 Spalten an Zelle 15.
  * Die synthetischen Tests rendern ebenfalls mit 400/160 und sehen den
    Fehler deshalb nicht.
* **`ab3`:** `fit_lattice` meldet `vorzeichen_kein_plus`, obwohl `+` angezeigt
  wird. `_has_minus_sign` (`dotlattice.py:141-172`) ist zu locker, und der
  Bediener bekommt damit die falsche Anweisung.
* **Offline-Fall:** Ein Parameter oder eine Datei für den Zellentext, damit
  2j auch ohne seriellen Port prüfbar ist (Test `ab4-profile` gegen
  `-regrid1`).
* **Kleinigkeiten:**
  * `propose --auto-quad` soll auch `overlay_sampling.png` nennen.
  * Der Bytegleich-Test soll auch `*-profile-regrid1.json` erfassen.

Belege liegen unter `/home/me-systeme/.claude/jobs/5e3104b9/tmp/review-assist/`
(`perturb.log`, `exp1.log`).

## Pausenstand Nacharbeit 1 — 2026-09-29

Der Nutzer hat die Arbeit vor der Abschlussprüfung pausiert. Der isolierte
Worktree bleibt `/home/me-systeme/picam-ai-assist` auf
`feat/einrichtungsassistent`. Auftrag 0 ist erledigt: Rebase auf
`origin/master` bei `ef5cedf`, Konflikte in den fünf Dokumentationsdateien
als Anhänge zusammengeführt. `/home/me-systeme/picam-ai` und
`/home/me-systeme/picam-ai-ernte` wurden nicht bearbeitet; Kamera und
`/dev/video*` blieben geschlossen, `var/` wurde nur gelesen.

**Implementiert, noch nicht vollständig abgenommen:** Nacharbeit 1 Punkte
1–9: explizite Format-Leerzellen, Plus-/Minusprüfung, Bias-Grenze,
skalierte Punktsuche und schnellere Rasteranpassung einschließlich `sc6`;
zellinterne Kante, Float-Kontrast, Rahmenprüfung, optionale Diagnose mit
eingefrorenem Leser; frühes FEHLER-Gate, tatsächlicher Bildabstand,
Profil-Bytegleichheit und `assist`-Kettentest mit injizierter Kamera.
Die Review-Lücken bei Plus-Randspalte und Overlay-Gesamtampel wurden per
Regressionstest behoben und erneut geprüft. Keine Änderung unter
`src/dispread/ocr/`.

**Letzte gezielte Belege:** `tests/test_dotlattice.py`: 26 bestanden in
58,11 s. `tests/test_setup_checks.py`: 29 bestanden. Schneller
CLI-/Profil-Satz: 32 bestanden, ein echter Kettentest zunächst abgewählt;
dieser bestand mit der finalen synthetischen Punktform anschließend separat
in 2,98 s. Der abschließende `ruff check src tests examples scripts` war
sauber. Die volle Suite ist
seit der Nacharbeit **nicht** gelaufen. Es laufen keine Tests/Agenten mehr.

**Morgen fortsetzen:** Zuerst gezielte Tests inklusive des Kettentests
gemeinsam und `ruff check src tests examples scripts`; danach sechs
Standbilder mit finaler `fit_lattice(..., empty_cells=(8,13,14,15))` und
`check_setup` neu auswerten. Die alte Tabelle in `docs/VALIDATION.md` und
die Geometrie-Zahlen im Laborjournal durch die Endwerte ersetzen,
einschließlich `sc6`, `leser_kontrast`, Eckabweichungen und Ampeln. Dann
Gesamtsuite nur ohne `var/RECORDING_IN_PROGRESS`, Doku-Build und
Playwright, Gesamt-Review, Commit/Push prüfen. Der erste echte
Kameralauf bleibt dem gemeinsamen Termin mit dem Nutzer vorbehalten.

`TODO.md`, `docs/status.md` und `docs/open-questions.md` bleiben gemäß
Aufgabe 5 dieses Plans unberührt; Claudes Merge-Schritt pflegt sie.

## Stand Nacharbeit 1 — 2026-09-30

Der Branch wurde erneut auf das heutige `origin/master` (`4f9371f`)
rebasiert. Die Codepunkte 1–9 sind umgesetzt; eine abschließende
Gesamt-Review fand keinen belegten mergekritischen Codefehler. Ein
synthetischer Fall mit zwei Anzeigen und einem schwächer erkannten
Plusanker wird als `startlage_mehrdeutig` abgelehnt. Eine weitere
Score-7-Hypothese aus der Review ließ sich in drei konkreten
Zwei-Punkt-Gegenproben nicht als stille Fehlannahme reproduzieren; die
probeweise Lockerung wurde zurückgenommen.

Nach dem Revert `e301628` verlangt `DotMatrixReader` wieder Vorlagen
mit `bg_closing_v1`; die eingefrorene Stufe-2b-Vorlage ist damit
kompatibel. Der Assistent prüft übergebene Vorlagen und Prüfsumme vor
dem Kamerastart. Er ändert weder Lesercode noch Vorlagen.

Die sechs gespeicherten Standbilder treffen mit Profil-Hinweisbox das
bestätigte Quad auf höchstens **0,48 px**, mit automatisch erkannter
grüner Hinweisbox auf höchstens **0,57 px**. `ab2` meldet Zelle 8 mit
Kantenwert **8,5 als FEHLER**; `sc3`, `sc4`, `sc5`, `ab1` und `sc6`
bleiben ohne Kantenbefund. Rahmen und Glanz sind auf allen sechs
bestätigten Aufstellungen OK. Alle Zahlen und die Bildbasis stehen in
`docs/VALIDATION.md`, Aufbau und Grenzen in `docs/lab_journal.md`.

Der nachträgliche Master-Befund zu falschen Profilrastern bei `ab3` und
`ab4` wurde mit den gespeicherten Profil-Referenzframes geprüft. Die
Nacharbeit lehnt beide ab: `ab3` mit grüner Hinweisbox bei 48,1 %
zugeordneten Punkten, `ab4` bei 67,8 % (Grenze 80 %); mit der groben
Profil-Box scheitert `ab3` schon am Plus, `ab4` bei 73,2 % Zuordnung.
Die alten Profilquads sind kein gültiger Sollwert für eine neue
Geometrie. Korrigierte Profile für `ab3` und `ab4` liegen inzwischen
durch `profile-regrid.py` vor; die automatische Versatzprüfung und
Nachführung im Assistenten sind als **Nacharbeit 2** oben beauftragt.

**Maßgebliche Vorabschwellen nach Nacharbeit 1:** Punktkontrast FEHLER
<15, WARNUNG <17; zellinterne Hintergrundkante in Leerzellen FEHLER >8,
WARNUNG >6, in belegten Zellen FEHLER >20, WARNUNG >16;
Randpunktverdeckung unter 70 % der Nachbarpunkte in Leerzellen und an
der linken Spalte des Pluszeichens; Auflösung FEHLER <2,6 und WARNUNG
<3,2 px je Punktspalte;
Raster-RMS FEHLER >0,25 Spalten oder >0,3 Zeilen beziehungsweise <80 %
Zuordnung, Raster-Bias bereits beim Fit ab Betrag >0,15 abgelehnt;
Stabilität FEHLER >0,5 und WARNUNG >0,2 px bei mindestens 30 s. Die
älteren Schwellen und Kantenwerte im Abschnitt „Stand der Umsetzung —
2026-09-29“ sind **historisch und durch diese Messung ersetzt**. Die
Vorabwerte sind noch nicht allgemein kalibriert.

Der gezielte `test_harvest_assist.py`-Satz bestand nach dem Leser-Revert
mit **20 Tests in 3,09 s**. Ein früherer Gesamtlauf hatte einen
einmaligen 10-s-Zeitüberschreiter bei `tesseract --version`; derselbe
Test bestand isoliert in 0,18 s. Der vollständige Wiederholungslauf
auf der endgültigen Basis `4f9371f` bestand mit **915 Tests,
3 übersprungenen und 1 erwarteten Fehlschlag in 369,82 s**. Ruff und
`git diff --check` sind sauber.
`./scripts/docs-site.sh build -s` meldete keine Probleme, und die
**21 Playwright-Dokutests** bestanden.
Der erste echte `assist`-Lauf samt Einrichtungsdauer bleibt dem
gemeinsamen Hardwaretermin mit dem Nutzer vorbehalten.

## Stand Nacharbeit 2 — 2026-09-30

Die Prüfung 2j, der strenge GSV-2AS-Zellentext aus serieller oder
Offline-Quelle und die Nachführung mit zurückgehaltenem zweitem
Standbild sind umgesetzt. FEHLER in 2j oder in der abschließenden
Gesamtprüfung erzeugen keinen Vorschlag. Jedes Bild muss für sich
mindestens drei belastbare Zellen in beiden Halbzellen und über die
ganze Zelle liefern. Die Eckkonvention 399/159, die `ab3`-Fehlmeldung,
der Overlay-Name und die Bytegleich-Probe der regrid-Profile sind
abgedeckt. Der Leser unter `src/dispread/ocr/` blieb unberührt.

Die lesende `ab4`-Gegenprobe auf Frame 16 ergibt mit dem alten Quad
0,935 Punktspalten / 0,105 Punktzeilen (FEHLER) und mit
`ab4-profile-regrid1.json` 0,047 / 0,046 (OK). Testaufbau und Deutung
stehen in `docs/VALIDATION.md` und `docs/lab_journal.md`. Kamera und
serieller Port wurden nicht geöffnet; `var/` blieb schreibgeschützt.

Die gezielten Integrationsprüfungen nach dem Review bestehen (124
Tests), Ruff und `git diff --check` sind sauber. Nach Ende der Aufnahme
bestand auch der abschließende Gesamtlauf mit **956 Tests, 3
übersprungenen und 1 erwartetem Fehlschlag in 452,92 s**. Zensical
meldete nach diesem Plan-Nachtrag keine Probleme, die 21
Playwright-Dokutests bestanden. Ein echter Hardwarelauf ist weiterhin
nicht erfolgt.

## Nacharbeit 3 (Review Claude, 2026-09-30, Branch-Stand `c233d0b`)

**Urteil: zurück an Codex.**
* Die Prüfung 2j ist gut:
  * Sie baut auf `lattice_offsets` auf und blockiert bei FEHLER.
  * Sie fing jede Rasterstörung ab: ±0,3–0,5 Spalten, ±1 Spalte oder Zeile,
    Scherung 0,05, Punktabstand 0,98–1,02. Bei ab4 misst sie +0,3/+0,4
    Spalten als FEHLER 0,34/0,44.
* Die Punkte 1 und 3–8 aus Nacharbeit 2 sind erfüllt. 198 gezielte Tests
  sind grün, ruff ist sauber.
* **Aber:** Auf keinem der vier echten Standbilder (ab4, ab5, ab6, sc6)
  liefert `assist` einen Vorschlag, auch nicht auf dem validierten sc6.

**Blockierend:**
1. **B1 – `evaluate_quad` sucht andere Punktkandidaten als `refine`/`fit_lattice`.**
   * Ort: `dotlattice.py:398`. `evaluate_quad` nimmt alle 3×3-Minima im
     Quellbild (`_source_candidates`), `refine` erkennt Punkte im
     entzerrten 2×-Bild mit einem Erosionskern in Punktgröße.
   * Beleg, von Claude nachgeprüft: Dasselbe sc6-Quad ergibt über
     `fit_lattice` 193/206 (0,94, OK), über `evaluate_quad` 192/301 (0,64,
     FEHLER).
   * Folge: Jedes nachgeführte Quad scheitert an der Zuordnungsquote,
     obwohl 2j OK ist. Bei sc6 steht 2j auf 0,043, trotzdem kein
     Vorschlag. Bei ab5 korrigiert die Nachführung von 0,32 auf 0,033
     Spalten, trotzdem ergibt sich 346/1905 und FEHLER.
   * `_heldout_improves` übernimmt schon bei einer Verbesserung von 0,001,
     deshalb landet fast jeder Lauf in diesem Pfad.
   * Der Test `test_assist_adopts_refined_quad_only_with_better_heldout_offset`
     ersetzt `evaluate_quad`, `raster_offset_check` und `check_setup` durch
     Attrappen und sieht den Fehler deshalb nicht.
   * **Auftrag:**
     * Eine gemeinsame Kandidatenerkennung für `refine`, `fit_lattice` und
       `evaluate_quad`.
     * Regressionstest mit echtem Standbild:
       * `evaluate_quad(fit.quad)` gibt `n_dots`/`n_assigned` des Fits
         ungefähr wieder.
       * Ein nachgeführtes sc6-Quad ergibt als Gesamturteil OK oder
         WARNUNG.
     * Einen **echten** Assist-Ablauf (Fit → Nachführung → Schlussprüfung)
       ohne Attrappen auf den Standbildern von sc6 und ab5 als Test
       aufnehmen, offline mit `--cell-text`.
     * Die Übernahme erst ab einer spürbaren Verbesserung, z. B. 0,02
       Spalten.
   * Überlegen, ob die Zuordnungsquote neben 2j überhaupt noch
     entscheiden soll. Sie war nur ein Ersatzmaß für den Rasterversatz.
     Mindestens darf sie ein Quad, das 2j besteht, nicht wegen anderer
     Kandidaten verwerfen.
2. **B2 – 2j lässt sich umgehen.**
   * `propose --quad …` und der Glas-Detektor setzen kein `fit`, deshalb
     laufen weder 2j noch `setup_checks` (`harvest-setup.py:371-392`).
   * `run_confirm` (`:515-549`) bestätigt auch Vorschläge ohne
     `rasterversatz`.
   * Genau über handgesetzte Quads sind die falschen Profile ab3 und ab4
     entstanden.
   * **Auftrag:**
     * `propose --quad` führt mit `--cell-text` 2j und `setup_checks` aus.
     * `confirm` verlangt `rasterversatz` mit OK oder WARNUNG, sonst
       `--override-reason`.

**In derselben Runde:**
3. **Serieller Zellentext klammert das Standbild nicht ein**
   (`harvest-setup.py:307-315`, `:855`, `:877`).
   * Der Text kommt aus dem ersten Telegramm nach der Aufnahme. Bei ab6 und
     sc6 wechseln die letzten Ziffern innerhalb von 3 s. Ein falscher Text
     macht aus WARNUNG 0,16 einen FEHLER 0,27. Das ist sicher, kostet aber
     Verfügbarkeit.
   * **Auftrag:** Telegramme vor und nach jedem Standbild lesen und Zellen,
     die in diesem Fenster wechseln, als `?` ausblenden, statt abzubrechen.
4. **`fit_lattice` findet auf echten Standbildern keine Startlage:**
   * ab4 meldet `startlage_mehrdeutig` (grüne und Profil-Hinweisbox),
   * ab6 meldet `keine_startlage` nach 19–37 s.
   * Das ist sicher, aber damit kommen schräge Aufstellungen gar nicht bis
     zur Nachführung. Die Standbilder als Regression aufnehmen.
5. **Test für „3 unterdrückte Nullen“:** `"+000988.5 mV/V"` scheitert schon am
   Regex (8-stelliger Zahlenblock), der Zweig `zeros > 2` in
   `gsv2as_cell_text.py` bleibt ungetestet. Die Zuordnungsregel ist aus
   `import-harvest`/`gate-label` dupliziert; den Kern besser gemeinsam
   nutzen.
6. **Grenze dokumentieren:** 2j misst nur die Zellen 0–7, weil das ROM
   `m`/`V`/`/` nicht kennt. Die Zellen 9–12 werden extrapoliert: sc6-Profil
   und nachgeführtes Quad weichen dort bis 0,25 Spalten voneinander ab.

Belege (Protokolle und Skripte):
`/home/me-systeme/.claude/jobs/5e3104b9/tmp/review-assist2/` (`exp2.log`,
`perturb3.log`, `propose.log`, `evalq.py`).

### Stand Nacharbeit 3 — 2026-09-30

Die blockierenden Punkte B1 und B2 sind im isolierten Feature-Worktree
bearbeitet. Fit und feste Quad-Bewertung erkennen Kandidaten mit
demselben entzerrten Verfahren; `sc6` liefert für dasselbe Quad in
beiden Wegen 196/208 Punkte. Die unabhängige 2j-Prüfung entscheidet
über den Rasterversatz; eine niedrige Zuordnungsquote bleibt bei 2j OK
oder WARNUNG sichtbar, blockiert den Vorschlag aber nicht allein.
Handgesetzte und vom Glasdetektor gefundene Quads mit bekanntem Text
durchlaufen 2j und die Einrichtungsprüfungen. `confirm` verlangt 2j OK
oder WARNUNG oder eine begründete Übersteuerung. Die serielle Aufnahme
wird von Telegrammen eingerahmt; wechselnde Zellen werden auch bei der
Nachführung ausgelassen. Die Nullunterdrückungsregel wird gemeinsam
genutzt, ein syntaktisch gültiger Fall mit drei unterdrückten Nullen
bleibt abgelehnt.

Der echte Offline-Test mit injizierter Kamera nutzt je zwei verschiedene
gespeicherte Frames von `sc6` und `ab5`, prüft die Verbesserung am
zweiten Bild und den geschriebenen Vorschlag. Die finale lesende
Wiederholung ergab 2j 0,043/0,070 (`sc6`) und 0,033/0,061 (`ab5`),
jeweils Schlussurteil WARNUNG. `ab4` bleibt bei mehrdeutiger Startlage,
`ab6` ohne Startlage sicher abgelehnt; eine gelockerte Ankerwahl für
`ab4` ergab ein um 9,14 px falsches Quad und wurde verworfen. Der
direkte Messbereich von 2j endet vor den Einheitszeichen rechts.

Die Echtbildtests lesen die vorhandenen Diagnoseframes unter `var/` und
überspringen sich auf einem Checkout ohne diese lokalen Daten. Ein
synthetischer Kettentest ist stets ausführbar; die Bilddaten werden
gemäß „Parallelarbeit“ nicht in den Branch kopiert. Ein echter Kamera-
oder serieller Hardwarelauf und der Merge stehen weiter aus.

**Abschlussprüfung dieser Runde:** 982 Python-Tests bestanden, 3
übersprungen, 1 erwarteter Fehlschlag; Ruff und `git diff --check`
sauber. Der Zensical-Build meldete keine Probleme, 21 Playwright-
Dokutests bestanden. Die Gesamt-Review fand einen Absturz bei
wechselndem seriellem Text vor der Nachführung; nach einem
fehlgeschlagenen Regressionstest wurde er behoben und gezielt erneut
geprüft. Kamera und serieller Port wurden nicht geöffnet, `var/` blieb
schreibgeschützt.

## Nacharbeit 4 (Review Claude, 2026-09-30, Branch-Stand `5f992cb`) – klein, dann Merge

**Urteil: Merge nach kleinen Fixes.**
* Kein falsches Raster kam mit OK durch, weder bei 17 gestörten Startlagen
  je Standbild (ab5, sc6, ab4) noch bei der Umgehung über `propose --quad`.
* sc6 und ab5 liefern im echten Offline-Ablauf einen Vorschlag:
  * ab5 liegt 0,23 px neben dem validierten Profil.
  * sc6 liegt in den Zellen 0–7 0,13 Spalten daneben. Gegengelesen mit
    `stufe2c` sind die Werte identisch.
* ab4 und ab6 lehnen sauber ab (`startlage_mehrdeutig` bzw.
  `keine_startlage`).
* 292 gezielte Tests grün, ruff sauber, nichts unter `var/` geschrieben.

**Vor dem Merge:**
1. **F1:** Ein verbessertes Quad, das `evaluate_quad` ablehnt, wird ohne
   Meldung verworfen (`harvest-setup.py:941-947`).
   * Die RMS- und Bias-Grenzen in `_evaluate_fit` lehnen 3 von 4
     validierten Profil-Quads ab, obwohl 2j OK meldet:
     * `ab4-profile-regrid1`: `restfehler_zu_gross`,
     * `ab6-profile`: `restfehler_zu_gross`,
     * `sc6-profile`: `bias_zu_gross`.
   * Szenario ab4, Scherung 0,02:
     * Die Nachführung korrigiert auf 0,05 Spalten, aber `evaluate_quad`
       lehnt ab.
     * `assist` schreibt dann einen WARNUNG-Vorschlag mit dem Start-Quad,
       das 0,22 Spalten daneben liegt.
   * **Auftrag:**
     * Den Kandidaten übernehmen und 2j plus `check_setup` entscheiden
       lassen, ohne Veto durch RMS oder Bias.
     * Oder den ganzen Lauf mit Meldung ablehnen.
     * Nie still auf das schlechtere Quad zurückfallen.
     * Dieselbe Ursache macht `propose --quad` für korrekte Quads von ab4,
       ab6 und sc6 unbrauchbar. RMS und Bias sind Ersatzmaße, maßgeblich
       ist 2j.
     * Regressionstest: Die vier validierten Profil-Quads (ab4-regrid1,
       ab5, ab6, sc6) bestehen `propose --quad … --cell-text …` mit OK oder
       WARNUNG.
2. **F2:** `confirm` erfindet `{"overall": "WARNUNG"}`, wenn `setup_checks`
   fehlen (`:581`). Stattdessen ausdrücklich „nicht geprüft“ eintragen
   und den Übersteuerungsgrund speichern.
3. **Rebase auf master.**
   * Nur Doku-Konflikte in `docs/VALIDATION.md` und diesem Plan. Beide
     Seiten übernehmen.
   * Die Zahl in „Messbereich der Prüfung 2j“ korrigieren: Die Zellen
     9–12 weichen bis 0,40 Spalten ab (0,49 mit `?`-Text), nicht 0,25.

**Kann später kommen:**
* **N1:** Die erste Zeile nach `reset_input_buffer` verwerfen, sie kann ein
  Bruchstück sein (`:310`).
* **N2:** Der Echtbild-Test prüft auch den Abstand zum validierten Profil
  und nutzt die grüne Hinweisbox.
* **N3:** Nicht über die 30-s-Pause maskieren, nur je Standbild.
* **Startlage schräger Aufstellungen** (ab4, ab6): Die Regression hält die
  Ablehnung fest, die Suche selbst ist nicht verbessert. Solche
  Aufstellungen richtet man vorerst von Hand mit
  `profile-regrid.py still` ein.

Belege: `/home/me-systeme/.claude/jobs/5e3104b9/tmp/review-assist3/`
(`assist_runs.jsonl`, `pert_*.log`, `pytest.log`).

### Stand Nacharbeit 4 — 2026-09-30

Der Feature-Branch wurde auf `master` mit dem Review-Nachtrag 4
rebasiert. Die Doku-Konflikte in diesem Plan und `docs/VALIDATION.md`
wurden als getrennte historische Abschnitte zusammengeführt; die
Abnahme 3 des Nutzers blieb erhalten. Der Haupt-Checkout und seine
uncommittete Änderung in `PLANNED_FEATURES.md` blieben unberührt.

F1: `evaluate_quad` liefert für feste Quads die RMS- und Bias-Werte
ohne Veto; die automatische Startsuche behält ihre Grenzen. Bei
bestandenem 2j-Befund stuft `check_setup` überschrittene Raster-
Ersatzmaße auf WARNUNG. Ein am zweiten Standbild besseres, aber aus
anderem Grund abgelehntes Quad beendet `assist` mit dem konkreten
Grund; der schlechtere Startfit wird nicht vorgeschlagen. Die vier
bestätigten Profil-Quads (`ab4-regrid1`, `ab5`, `ab6`, `sc6`) bestehen
`propose --quad … --cell-text …` im Offline-Test mit OK oder WARNUNG;
die Zahlen stehen in `docs/VALIDATION.md`.

F2: `confirm` speichert bei fehlenden Einrichtungsprüfungen
`NICHT_GEPRUEFT` und verlangt einen neuen, nichtleeren
`--override-reason`. Die zuvor erfundene WARNUNG entfällt. Der
Reviewwert zur rechts extrapolierten Rasterlage ist in VALIDATION und
Laborjournal auf 0,40 beziehungsweise 0,49 Punktspalten mit `?`-Text
korrigiert.

Gezielt bestanden 155 Integrations- und Lattice-Tests. Die
vollständige Python-Suite bestand mit 995 Tests, 3 Übersprüngen und
1 erwartetem Fehlschlag. Ruff und `git diff --check` waren sauber.
Der Zensical-Build meldete keine Probleme, alle 21 Playwright-
Dokutests bestanden. Eine abschließende Code-Review fand keinen
blockierenden Befund.
Kamera und serieller Port wurden nicht geöffnet; `var/` wurde nur
gelesen. Der erste echte Kameralauf und der Merge stehen aus.
