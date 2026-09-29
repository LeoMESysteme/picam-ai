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
