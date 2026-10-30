"""Zustandslose Nachfuehrung aus begrenzten Rahmenfenstern und LCD-Rand.

Vorschlag geaendert R13-11 (Band, Hysterese, Reserve); Feinpruefung unveraendert.
R13-19c: zweiter Suchversuch mit eng begrenztem Massstab; neue Abnahme noetig.
R13-24: Aehnlichkeitsversuch auch ohne Mindestverschiebung, einschliesslich (0,0).
Profile vor R13-11 muessen neu eingerichtet werden.

Update-Kandidat R13-7, festgelegt am Entwicklungsdatensatz; C/D
(r13-abnahme-c/d-hell-20261022) waren Anlass und gelten nicht als Abnahme;
R13-7-Abnahme r13-abnahme-e/f-*. Fuer R13-11 ist eine weitere getrennte
Abnahme noetig. Keine Freigabe. Kleine rohe Fenster vermeiden
Zeicheninhalt; Eindeutigkeit, verteilte Inlier und der unabhaengige helle
LCD-Rand bleiben harte Regeln. Keine automatische Abschwaechung bei fehlender
Struktur.

Bedienregel fuer neu hinzugefuegte Mittelpunkte: vor der Pruefung auf das staerkste
3x3-lokale Shi-Tomasi-Maximum oberhalb derselben Strukturschwelle im
euklidischen Radius MANUAL_SNAP_RADIUS_PX = 3 Rohpixel einrasten. Bei
gleicher Staerke gewinnt der naechste Punkt, danach die Bildreihenfolge.
Dies erleichtert die Eingabe und ist keine Akzeptanzregel: alle bestehenden
Pruefungen laufen anschliessend am verwendeten Mittelpunkt unveraendert.
Beibehaltene Bereiche werden ohne erneutes Einrasten am gespeicherten
Mittelpunkt geprueft, unabhaengig von ihrer automatischen/manuellen Herkunft.

Vorschlagsband: aus dem LCD-Randmodell wird die dunkle Rahmenkomponente
bestimmt. Schwelle: 90%-Quantil 20/35/50 px ausserhalb der starken Fensterkanten
plus 24 Graustufen, nach oben durch die Otsu-Schwelle begrenzt; 15x15-Oeffnung trennt duenne Verbindungen (Kabel).
Nur eine randfreie Komponente mit geschlossener Aussenkontur um Quad UND
Fensterkanten, 2..12-facher Quadflaeche und Soliditaet >=0.97
(Konturflaeche / konvexe Huellflaeche) ist plausibel. Ihre gefuellte
Aussenkontur (auch helle Fasen) wird um 2 px erodiert. Hinzu kommt die bisherige
Fenstereckenzone. Ohne plausiblen Rahmen gilt das bisherige feste Band:
Quadskalierung 3, an den Enden auf 100 Rohpixel begrenzt. band_quelle und
band_rueckfallgrund legen die Entscheidung offen. Zeichenpolygon weiterhin
um 8 px dilatiert; ALLE Suchpixel samt Interpolationspixel bleiben im Band.
Die Oeffnung trennt duenne Verbindungen nach aussen; ein Kabel vor der
Rahmenflaeche liegt innerhalb des Bandes und wird dadurch nicht ausgeschlossen.
Vorschlagsmatching verlangt Zweitpeak/Peak <=0.90 UND Peakabstand >=0.10;
die Laufzeitgrenze bleibt 0.95. Shi-Tomasi-Schwelle bleibt fuer die
Fensterzone 0.02, fuer neue Rahmenflaechen 0.005 (relative Schwelle je Zone).
Neue Fasenstruktur muss zudem vier bekannte Halb-Pixel-Bewegungen
(je Achse +/-0.5 px, bilinear) auf <=0.10 px lokalisieren, mit derselben
Laufzeit-Mindestkorrelation und Eindeutigkeit. So werden selbst-eindeutige,
aber schlecht lokalisierbare Kanten abgelehnt; unveraendert fuer Fensterpunkte.
Die Probe ist fuer Fensterpunkte eine Auswahlpraeferenz, keine zusaetzliche
Ablehnung. Bis zu 20 Bereiche, unveraenderter
Abstand, reihum aus vier Quadranten. Bevorzugt werden Punkte mit Hebelarm
an beiden Achsen, danach an einer, dann die bestandene Bewegungsprobe und
Strukturstaerke. Nur fuer den Vorschlag zaehlt eine Achsenseite ab 35 Prozent
ihrer Ausdehnung vom Quadmittelpunkt bis zur aeusseren Bandkontur (mindestens
20 px). Diese strengere Streuung muss nach beliebigen zwei Bereichsausfaellen
weiter gelten (mindestens fuenf solche Bereiche je Achsenseite).

Streuung wird in lokalen Quadachsen geprueft: mindestens drei Inlier auf
JEDER Seite BEIDER Achsen, jeweils mindestens 20 px vom Mittelpunkt entfernt
(effektiv mindestens sechs, zusaetzlich zur Bereichszahlgrenze vier).
Jeder Inlier wird einzeln weggelassen und der starre Fit erneut berechnet;
bewegt sich dadurch eine OCR-Ecke um mehr als 0.5 px, wird abgelehnt.
Dies schliesst den auf DEV-Fixtures reproduzierten einzelnen Hebelpunkt aus.
Nach RANSAC, Streuung und Leave-one-out gelten zusaetzlich fuer die euklidischen
Residuen ALLER Inlier des endgueltigen starren Fits: RMS <= 0.35 px UND
Maximum <= 0.65 px, sonst rahmen_unstimmig. Genauigkeit wird damit explizit
ueber die Konsistenz der Rahmenbereiche geprueft. R13-7, DEV r13-werteplan-20261021:
568 Fits, 6346 Inlier; Residuen-99.9%-Quantil 0.503581 px, Maximum 0.527865 px;
RMS-99.9%-Quantil je Bild 0.286432 px, Maximum 0.286613 px. Die Grenzen geben
0.063568 px RMS- bzw. 0.146419 px Residuen-Marge zum jeweiligen 99.9%-Quantil.
Die Nachtkopie (39 Bilder) liefert keinen Fit (rahmen_mehrdeutig), also keine
Residualbelege und keinen Grund zur Lockerung. Ausschliesslich diese beiden
Entwicklungsaufnahmen bestimmen die neuen Residualgrenzen.
Konsistenz kann keine gemeinsam falsche Bewegung aller Bereiche erkennen,
waehrend das Glas stillsteht; dafuer bleibt nur die grobe Randpruefung.
Shift ist die Verschiebung des Quadmittelpunktes in Rohpixeln. Rotation ist
der vorwaerts wirkende Winkel, gleiches Vorzeichen wie ECC in track.py:
positive Werte drehen im Bild (y nach unten) im Uhrzeigersinn; ein positiver
Winkel an cv2.getRotationMatrix2D liefert daher eine negative rotation_deg.
Intern TL, TR, BR, BL wie rectify._order_quad, Ausgabe in Eingabereihenfolge.

LCD-Modell: je Seite 18 Normalprofile zwischen 10 und 90 Prozent der
Seitenlaenge, Suche 14..90 px nach aussen. Helligkeitsdifferenz bei +/-1 px,
parabolische Subpixelposition am staerksten Hell-Dunkel-Gradienten, gleiche
Lokalisierung in Referenz und aktuellem Bild. Nur starke Referenzschritte
>=2 * edge_min_step (36 Graustufen) bleiben. Eine Seite mit weniger als sechs
starken Punkten ist schwach, steht in den Vorschlagsmetriken und wird im
aktuellen Bild nicht geprueft. Mindestens drei starke Seiten und mindestens
eine aus jedem Paar oben/unten und links/rechts sind erforderlich, sonst
lcd_rand_fehlt. Seitenindizes: 0 oben, 1 rechts, 2 unten, 3 links.
Im aktuellen Bild wird innerhalb +/-4 px entlang der mitgedrehten Normalen lokalisiert;
die gefundene Position muss hoechstens 2.5 px von der Vorhersage abweichen.
Dies ist eine GROBE Plausibilitaetspruefung gegen Fehlverriegelung um mehrere
Pixel, kein Subpixel-Genauigkeitsnachweis: die absolute Grauwertkante wandert
mit dem Licht (gemessen bis etwa 0.9 px bei Raumlicht, mehrere px bei Daemmerung).
JEDE starke Seite braucht mindestens 80 Prozent solcher Nachweise mit
gleicher Polaritaet und mindestens halber Referenzstaerke (weiterhin >=18).
Polaritaet, Staerke, Seitenanteile und die Schwachseitenregel bleiben gleich.
Die schwache Unterseite
des DEV-Aufbaus (18.7..34.7 Graustufen bei harter Grenze 18) liefert keine
belastbare Positionsinformation und verursachte allein falsche Ablehnungen
bei Helligkeit x0.8 oder 3x3-Gaussfilter. Der Ausschluss folgt dieser
grundsaetzlichen Verfuegbarkeitsentscheidung.

R13-19c: Der erste Durchgang ist numerisch unveraendert starr. Nur bei
rahmen_unstimmig, zu_wenig_rahmenmerkmale oder rahmen_mehrdeutig folgt eine
zustandslose Grobschaetzung gegen das Referenzgraubild: Phasenkorrelation
auf einem vierfach verkleinerten Ausschnitt innerhalb outer_limit (R13-23:
ganzzahliger AREA-Faktor auf uint8). Referenzhochpass und Hann-Maske werden
einmal vorbereitet; cv2.phaseCorrelate korreliert die Bilder. Laplace unterdrueckt die
feste Maskenkante. Die Zeichenzone bleibt samt maximaler Translation,
Drehbewegung, maximalem Massstab und Filter-Nachbarpixeln ausgespart, auch im bewegten Bild.
Nur endliche Antworten mit response > coarse_min_response (Default 0.15)
und Betrag <= max_shift_px + 6 px erlauben
einen zweiten Versuch. Die 6 px beruecksichtigen nur den Grobfehler;
der Feinversuch setzt die absolute max_shift_px-Grenze selbst durch.
Derselbe Feinpfad sucht um Quelle plus ganzzahlig
gerundete Grobverschiebung, auch (0,0); Ziele sind absolute Bildkoordinaten.
Seit R13-24 gibt es keine Mindestverschiebung: der Aehnlichkeitsfit kann auch
bei stillstehendem Quadmittelpunkt einen kleinen Massstabsfehler korrigieren.
Patches, Peak/Eindeutigkeit, Streuung, Leave-one-out, beide Residualgrenzen und
absolute Bewegung gegen das urspruengliche Quad bleiben gleich. Nur der
zweite Versuch nutzt einen orientierungserhaltenden Aehnlichkeitsfit:
RANSAC ueber alle Minimalpaare mit Drehung und gleichfoermigem Massstab,
anschliessend Umeyama-Endfit und Leave-one-out mit Massstab. Minimalpaare
und Endfit muessen 1-coarse_max_scale_deviation <= s <=
1+coarse_max_scale_deviation erfuellen (Default und hoechstens 0.005).
Das Ausgabequad und die LCD-Randpunkte werden mit s*R und Translation
abgebildet; Randnormalen nur mit R. Randtoleranz weiterhin 2.5 px.
Ein unbrauchbarer Vorschlag behaelt die erste Ablehnung; ein abgelehnter
zweiter Versuch liefert seinen eigenen Grund. last_coarse ist None ohne
Schaetzung, sonst (dx, dy, response, used, scale); used bedeutet zweiter Feinversuch,
keinen Akzeptanznachweis. Kein Ergebnis wird ins naechste Bild uebernommen.
scale ist None ohne begrenzten Endfit, sonst dessen Massstab (auch wenn
eine spaetere Pruefung ablehnt). Die Grobschaetzung ist kein zusaetzlicher
Sicherheitsbeleg und behebt den oben beschriebenen blinden Fleck nicht.
Auch eine richtige Grobschaetzung kann an den unveraenderten Residualgrenzen
scheitern (Live-DEV 2026-10-28).
Neuer blinder Fleck, 2026-10-28: Bei stillstehendem LCD und gemeinsam
falschen Rahmentreffern akzeptiert der isolierte zweite Durchgang im
portablen Fixture-Raster bis 5.220583 px Quadeckenfehler bei s=1.005,
4.466826 px bei s=0.995 und 4.725129 px bei s=1. Je Massstab 3757
Hypothesen: Winkel -1.2..1.2 Grad (0.2), dx/dy -4..4 px (0.5).
Erster Fehlschlag, plausibler Grobvorschlag und exakte falsche Treffer
sind injiziert; Fit, Leave-one-out und LCD-Pruefung laufen unveraendert.
Die 2.5-px-Randpruefung verwirft je Massstab ueber 2000 Hypothesen,
auch groessere legale Aehnlichkeitsluegen, die ohne sie angenommen werden.
Dies ist eine dokumentierte Rastergrenze, keine allgemeine obere Schranke
und keine neue Abnahme (tests: r19c_gemeinsam_falsche_aehnlichkeit).
Alte R13-11-Configs duerfen die neuen Grobfelder auslassen; diese
werden beim Laden mit Defaults ergaenzt. Alle alten Pflichtfelder und die
Referenz-/Quad-/SHA-Bindung bleiben strikt; Profile vor R13-11 bleiben abgelehnt.
Das entfallene coarse_min_shift_px wird beim Laden alter Configs nach
Typ-/Endlichkeits-/Nichtnegativpruefung entfernt, auch im gespeicherten Vorschlag.

15-px-Patches und 12-px-Suchradius lassen kleine Rohbildbewegungen zu;
Peak >=0.75 und Zweitpeak/Peak <=0.95 ausserhalb +/-3 px verlangen erkennbare
und eindeutige Struktur. Inlier mit <=1.5 px Residuum sichern den starren Fit;
Bewegungsgrenzen bleiben 20 px / 3 Grad. Numerische Update-Defaults ausschliesslich
an der benannten Entwicklungsaufnahme und ihren Fixtures festgelegt;
ausgenommen die vom Controller vorgegebene grobe Randtoleranz 2.5 px.
R13-11-Vorschlagsdefaults nutzen auch die benannten Einrichtungsbilder
(insbesondere frontal live-20261023T124226Z); E/F sind fuer R13-11 kein
unabhaengiger Abnahmebeleg.

Eingaben: ausschliesslich uint8, Graustufen (H,W), BGR (H,W,3) oder BGRA
(H,W,4), Alpha wird ignoriert. Float-/andere Typen oder Formen fuehren in
Vorschlag, Konstruktor und update zu ValueError vor OpenCV-Matching.
Vorschlaege sind an normalisiertes Quad, Config-Dict, Graubildform und
SHA256 des Referenzgraubilds gebunden; ungeeignete/anders grosse aktuelle
Bilder werden mit eigenem Grund abgelehnt. Randfenster werden uebersprungen.

Score = Inlierzahl / vorgeschlagene Regionen * mittlerer Inlierpeak, [0, 1];
er ist nur informativ und keine Fehlerwahrscheinlichkeit.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from hashlib import sha256
from itertools import combinations

import cv2
import numpy as np

from dispread.detect import Quad
from dispread.track import TrackResult

MANUAL_SNAP_RADIUS_PX = 3
# Nur fuer das Vorab-Gate, niemals fuer den absoluten Feinfit:
# gemessener maximaler Vektorfehler 4.956 px + mindestens 1.044 px Reserve
# (zwei echte Referenzen, reiner Translationssweep; VALIDATION R13-23).
_COARSE_ERROR_MARGIN_PX = 6.0


@dataclass(frozen=True, slots=True)
class FrameTrackingConfig:
    patch_size: int = 15
    search_radius_px: int = 12
    min_peak: float = 0.75
    ambiguity_limit: float = 0.95
    ambiguity_radius_px: int = 3
    min_regions: int = 4
    max_regions: int = 20
    proposal_ambiguity_limit: float = 0.90
    proposal_min_peak_margin: float = 0.10
    reserve_regions: int = 2
    bezel_max_localisation_error_px: float = 0.10
    bezel_threshold_margin: float = 24.0
    bezel_opening_px: int = 15
    bezel_erosion_px: int = 2
    bezel_min_area_ratio: float = 2.0
    bezel_max_area_ratio: float = 12.0
    bezel_min_solidity: float = 0.97
    proposal_lever_arm_fraction: float = 0.35
    min_spread_px: float = 20.0
    min_inliers_per_side: int = 3
    max_leave_one_out_corner_px: float = 0.5
    max_inlier_rms_px: float = 0.35
    max_inlier_residual_px: float = 0.65
    min_spacing_px: float = 28.0
    corner_quality: float = 0.02
    bezel_corner_quality: float = 0.005
    max_candidates: int = 200
    ransac_tolerance_px: float = 1.5
    max_shift_px: float = 20.0
    max_rotation_deg: float = 3.0
    character_margin_px: int = 8
    outer_scale: float = 3.0
    outer_end_margin_px: float = 100.0
    interpolation_guard_px: int = 1
    edge_min_offset_px: int = 14
    edge_max_offset_px: int = 90
    edge_samples_per_side: int = 18
    edge_end_fraction: float = 0.1
    edge_step_halfwidth_px: float = 1.0
    edge_min_step: float = 18.0
    edge_min_points_per_side: int = 6
    edge_magnitude_fraction: float = 0.5
    edge_search_radius_px: int = 4
    edge_position_tolerance_px: float = 2.5
    edge_required_share: float = 0.8
    edge_required_sides: int = 3
    coarse_min_response: float = 0.15
    coarse_max_scale_deviation: float = 0.005

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> FrameTrackingConfig:
        # Nur R13-19b/c ergaenzen: alte Feinpruefgrenzen bleiben Pflicht.
        optional = {"coarse_min_response", "coarse_max_scale_deviation"}
        if isinstance(data, dict) and "coarse_min_shift_px" in data:
            data = dict(data)
            legacy_shift = data.pop("coarse_min_shift_px")
            if type(legacy_shift) is not float or not np.isfinite(legacy_shift) or legacy_shift < 0:
                raise ValueError("Ungueltige alte Grob-Mindestverschiebung")
        names = {field.name for field in fields(cls)}
        if not isinstance(data, dict) or not names - optional <= set(data) <= names:
            raise ValueError("Unvollstaendige oder unbekannte Rahmenkonfiguration")
        data = {**{field.name: field.default for field in fields(cls) if field.name in optional}, **data}
        for field in fields(cls):
            if type(data[field.name]) is not type(field.default):
                raise ValueError(f"Ungueltiger Typ fuer Rahmenkonfiguration: {field.name}")
        return cls(**data)

    def __post_init__(self):
        if not all(np.isfinite(getattr(self, field.name)) for field in fields(self)):
            raise ValueError("Pruefgrenzen muessen endlich sein")
        if not 0 < self.coarse_min_response <= 1:
            raise ValueError("Ungueltige Grobschaetzungsgrenzen")
        if not 0 < self.coarse_max_scale_deviation <= 0.005:
            raise ValueError("Massstabsabweichung muss positiv und hoechstens 0.005 sein")
        if self.patch_size < 3 or self.patch_size % 2 != 1 or self.search_radius_px < 1:
            raise ValueError("Ungerade Patchgroesse und positiver Suchradius erforderlich")
        if not 0 < self.min_peak <= 1 or not 0 < self.ambiguity_limit < 1:
            raise ValueError("Ungueltige Matchinggrenzen")
        if (not 0 < self.proposal_ambiguity_limit < self.ambiguity_limit
                or not 0 < self.proposal_min_peak_margin < 1
                or self.bezel_max_localisation_error_px <= 0
                or self.reserve_regions < 2 or not 0 < self.bezel_corner_quality <= self.corner_quality
                or self.bezel_opening_px < 3 or self.bezel_opening_px % 2 != 1
                or self.bezel_erosion_px < 1 or not 0 < self.bezel_threshold_margin < 255
                or not 0 < self.bezel_min_solidity <= 1
                or not 0 < self.proposal_lever_arm_fraction < 1
                or not 1 < self.bezel_min_area_ratio < self.bezel_max_area_ratio):
            raise ValueError("Ungueltige Vorschlagsgrenzen")
        if not 2 <= self.min_regions <= self.max_regions or self.min_spread_px <= 0:
            raise ValueError("Ungueltige Bereichszahl oder Streuung")
        if (self.min_inliers_per_side < 2 or 2*self.min_inliers_per_side > self.max_regions
                or self.max_leave_one_out_corner_px <= 0
                or self.max_inlier_rms_px <= 0 or self.max_inlier_residual_px <= 0
                or self.ransac_tolerance_px <= 0 or self.max_shift_px < 0 or self.max_rotation_deg < 0
                or self.min_spacing_px <= 0 or self.interpolation_guard_px < 1
                or self.character_margin_px < 0 or self.outer_scale <= 1 or self.outer_end_margin_px <= 0
                or self.ambiguity_radius_px < 0 or self.ambiguity_radius_px >= self.search_radius_px
                or not 0 < self.corner_quality <= 1 or self.max_candidates < self.min_regions):
            raise ValueError("Ungueltige Geometrie- oder Suchgrenzen")
        if (not 1 <= self.edge_required_sides <= 4 or not 0 < self.edge_required_share <= 1
                or not 0 < self.edge_magnitude_fraction <= 1 or self.edge_min_step <= 0
                or not 1 <= self.edge_min_points_per_side <= self.edge_samples_per_side
                or not 0 < self.edge_end_fraction < 0.5 or self.edge_step_halfwidth_px <= 0
                or self.edge_search_radius_px < 2
                or not 0 < self.edge_position_tolerance_px < self.edge_search_radius_px or self.edge_max_offset_px <= self.edge_min_offset_px):
            raise ValueError("Ungueltige LCD-Randgrenzen")
        if self.edge_min_offset_px <= self.character_margin_px + self.edge_step_halfwidth_px + self.edge_search_radius_px:
            raise ValueError("LCD-Randsuche beruehrt Zeichenbereich")


@dataclass(frozen=True, slots=True)
class FrameRegion:
    centre: tuple[int, int]
    size: int


@dataclass(frozen=True, slots=True)
class LcdEdge:
    point: tuple[float, float]
    offset: float
    normal: tuple[float, float]
    polarity: int
    magnitude: float
    side: int


@dataclass(frozen=True, slots=True)
class RegionProposal:
    regions: tuple[FrameRegion, ...]
    edges: tuple[LcdEdge, ...]
    character_zone: Quad
    outer_limit: tuple[tuple[float, float], ...]
    ok: bool
    reasons: tuple[str, ...]
    metrics: dict[str, object]
    config: dict[str, object]
    normalised_quad: Quad
    reference_shape: tuple[int, int]
    reference_sha256: str

    def to_dict(self) -> dict:
        """Verlustfrei in reine JSON-Typen ueberfuehren, ohne Rundung."""
        return json.loads(json.dumps(asdict(self), allow_nan=False))

    @classmethod
    def from_dict(cls, data: dict) -> RegionProposal:
        if set(data) != {field.name for field in fields(cls)}:
            raise ValueError("Unvollstaendiger oder unbekannter Rahmenvorschlag")
        data = dict(data)
        data["config"] = FrameTrackingConfig.from_dict(data["config"]).to_dict()
        data["regions"] = tuple(FrameRegion(tuple(r["centre"]), r["size"]) for r in data["regions"])
        data["edges"] = tuple(LcdEdge(**{**edge, "point": tuple(edge["point"]),
                                       "normal": tuple(edge["normal"])}) for edge in data["edges"])
        for name in ("character_zone", "outer_limit", "normalised_quad"):
            data[name] = tuple(tuple(point) for point in data[name])
        data["reference_shape"] = tuple(data["reference_shape"])
        data["reasons"] = tuple(data["reasons"])
        return cls(**data)


def _gray(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("Bild muss ein uint8-Array sein")
    if image.ndim not in (2, 3) or min(image.shape[:2]) == 0 or (image.ndim == 3 and image.shape[2] not in (3, 4)):
        raise ValueError("Bild muss Graustufen, BGR oder BGRA enthalten")
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _normalise_quad(quad):
    points = np.asarray(quad, dtype=float)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Quad muss vier endliche Eckpunkte enthalten")
    sides = np.roll(points, -1, axis=0) - points
    following = np.roll(sides, -1, axis=0)
    cross = sides[:, 0]*following[:, 1] - sides[:, 1]*following[:, 0]
    if not (np.all(cross > 1e-6) or np.all(cross < -1e-6)):
        raise ValueError("Quad muss konvex und nicht entartet sein")
    # Wie rectify._order_quad: TL, TR, BR, BL, im Bild im Uhrzeigersinn.
    # Zyklische Ordnung vermeidet doppelte Ecken bei gleichen Summen/Differenzen.
    if cross[0] < 0:
        points = points[::-1]
    first = min(range(4), key=lambda i: (points[i].sum(), points[i, 1], points[i, 0]))
    return np.roll(points, -first, axis=0).copy()


def _window(gray, centre, radius):
    x, y = centre
    height, width = gray.shape
    if x-radius < 0 or y-radius < 0 or x+radius >= width or y+radius >= height:
        return None
    return gray[y-radius:y+radius+1, x-radius:x+radius+1]


def _axes(quad):
    axis = (quad[1] + quad[2] - quad[0] - quad[3]) / 2
    axis /= np.linalg.norm(axis)
    return np.array([axis, [-axis[1], axis[0]]])


def _polygon(points):
    return tuple((float(x), float(y)) for x, y in points)


def _geometry(gray, quad, config):
    shape = gray.shape
    centre = quad.mean(axis=0)
    outer = (quad - centre) * config.outer_scale + centre
    axes = _axes(quad)
    local = (quad - centre) @ axes.T
    lo, hi = local.min(axis=0), local.max(axis=0)
    lo[0] -= config.outer_end_margin_px
    hi[0] += config.outer_end_margin_px
    lo[1] *= config.outer_scale
    hi[1] *= config.outer_scale
    cap = np.array([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]]) @ axes + centre
    _, outer = cv2.intersectConvexConvex(outer.astype(np.float32), cap.astype(np.float32))
    outer = outer.reshape(-1, 2)
    # Offset jeder Seite, mit Schnitt der benachbarten Geraden: echte Dilatation.
    sides = np.roll(quad, -1, axis=0) - quad
    normals = np.column_stack((sides[:, 1], -sides[:, 0]))
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    offsets = np.sum(normals * quad, axis=1) + config.character_margin_px
    zone = np.array([np.linalg.solve(normals[[i-1, i]], offsets[[i-1, i]]) for i in range(4)])
    mask = np.zeros(shape, np.uint8)
    cv2.fillConvexPoly(mask, np.rint(outer).astype(np.int32), 255)
    fixed_band = mask.copy()
    bezel, metrics = _bezel_band(gray, quad, config)
    if bezel is not None:
        mask |= bezel
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Aussenkontur nur fuer das Overlay; die Auswahl benutzt die Pixelmaske.
        outer = max(contours, key=cv2.contourArea).reshape(-1, 2)
    cv2.fillConvexPoly(mask, np.rint(zone).astype(np.int32), 0)
    radius = config.patch_size // 2 + config.search_radius_px + config.interpolation_guard_px
    mask = cv2.erode(mask, np.ones((2*radius+1, 2*radius+1), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    cv2.fillConvexPoly(fixed_band, np.rint(zone).astype(np.int32), 0)
    fixed_band = cv2.erode(fixed_band, np.ones((2*radius+1, 2*radius+1), np.uint8),
                           borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return zone, outer, mask, metrics, fixed_band


def _bezel_band(gray, quad, config):
    """Nur eine geschlossene, randfreie dunkle Rahmenkomponente zulassen."""
    metrics = {"band_quelle": "festes_band", "band_rueckfallgrund": "lcd_rand_fehlt"}
    edges = _edge_model(gray, quad, config)
    if not edges:
        return None, metrics
    points = np.array([edge.point for edge in edges])
    normals = np.array([edge.normal for edge in edges])
    # Direkt an der Kante liegt oft eine schwarze Nut. Weiter aussen
    # repraesentieren drei Probenabstaende die helleren Rahmenflaechen.
    samples = _sample(gray, points[:, None] + np.array([20, 35, 50])[None, :, None] * normals[:, None])
    otsu, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU)
    threshold = min(float(otsu), float(np.percentile(samples, 90)) + config.bezel_threshold_margin)
    metrics["band_schwelle"] = threshold
    dark = np.uint8(gray <= threshold) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((config.bezel_opening_px,)*2, np.uint8))
    _, labels, stats, _ = cv2.connectedComponentsWithStats(dark)
    seeds = np.rint(points + 20*normals).astype(int)
    valid = ((seeds >= 0).all(axis=1) & (seeds < gray.shape[::-1]).all(axis=1))
    candidates = set(labels[seeds[valid, 1], seeds[valid, 0]]) - {0}
    quad_mask = np.zeros_like(gray)
    cv2.fillConvexPoly(quad_mask, np.rint(quad).astype(np.int32), 255)
    area = cv2.contourArea(quad.astype(np.float32))
    plausible = []
    metrics["band_rueckfallgrund"] = "rahmen_nicht_geschlossen"
    # Bei mehreren verworfenen Komponenten den Grund der groessten offenlegen.
    for label in sorted(candidates, key=lambda label: (stats[label, cv2.CC_STAT_AREA], label)):
        metrics["band_rueckfallgrund"] = "rahmen_nicht_geschlossen"
        metrics.pop("band_flaeche_quad", None)
        metrics.pop("band_soliditaet", None)
        x, y, w, h, _ = stats[label]
        if x == 0 or y == 0 or x+w == gray.shape[1] or y+h == gray.shape[0]:
            metrics["band_rueckfallgrund"] = "rahmen_am_bildrand"
            continue
        component = np.uint8(labels == label) * 255
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        contour_area = cv2.contourArea(contour)
        ratio = contour_area / area
        solidity = contour_area / max(cv2.contourArea(cv2.convexHull(contour)), 1.0)
        metrics.update(band_flaeche_quad=ratio, band_soliditaet=solidity)
        if not config.bezel_min_area_ratio <= ratio <= config.bezel_max_area_ratio:
            metrics["band_rueckfallgrund"] = "rahmenflaeche_unplausibel"
            continue
        if solidity < config.bezel_min_solidity:
            metrics["band_rueckfallgrund"] = "rahmenform_unplausibel"
            continue
        filled = np.zeros_like(gray)
        cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
        edge_pixels = np.rint(points).astype(int)
        if (not np.all(filled[quad_mask != 0])
                or not np.all(filled[edge_pixels[:, 1], edge_pixels[:, 0]])):
            continue
        plausible.append((ratio, solidity, filled))
    if len(plausible) != 1:
        if len(plausible) > 1:
            metrics["band_rueckfallgrund"] = "rahmen_mehrdeutig"
        return None, metrics
    ratio, solidity, filled = plausible[0]
    radius = config.bezel_erosion_px
    bezel = cv2.erode(filled, np.ones((2*radius+1,)*2, np.uint8))
    metrics.update(band_quelle="dunkler_rahmen", band_rueckfallgrund=None,
                   band_flaeche_quad=ratio, band_soliditaet=solidity)
    return bezel, metrics


def _proposal_match(response, config):
    """Strengere Eindeutigkeit nur bei der Einrichtung; _peak bleibt eingefroren."""
    _, peak, ambiguous = _peak(response, config)
    _, _, _, (x, y) = cv2.minMaxLoc(response)
    other = response.copy()
    r = config.ambiguity_radius_px
    other[max(0, y-r):y+r+1, max(0, x-r):x+r+1] = -1
    second = float(other.max())
    return bool(not ambiguous and peak >= config.min_peak
                and second <= peak * config.proposal_ambiguity_limit
                and peak - second >= config.proposal_min_peak_margin)


def _peak(response, config):
    _, peak, _, (x, y) = cv2.minMaxLoc(response)
    other = response.copy()
    r = config.ambiguity_radius_px
    other[max(0, y-r):y+r+1, max(0, x-r):x+r+1] = -1
    second = float(other.max())
    ambiguous = peak <= 0 or second / peak > config.ambiguity_limit
    delta = np.zeros(2)
    for axis, index in enumerate((x, y)):
        limit = response.shape[1-axis]
        if 0 < index < limit-1:
            a, b, c = response[y, x-1:x+2] if axis == 0 else response[y-1:y+2, x]
            denominator = float(a - 2*b + c)
            if denominator < 0:
                delta[axis] = np.clip(0.5 * float(a-c) / denominator, -0.5, 0.5)
    return np.array([x, y]) + delta, float(peak), ambiguous


def _spread(points, quad, config):
    if len(points) == 0:
        return False
    local = (np.asarray(points) - quad.mean(axis=0)) @ _axes(quad).T
    return bool(np.all((local <= -config.min_spread_px).sum(axis=0) >= config.min_inliers_per_side)
                and np.all((local >= config.min_spread_px).sum(axis=0) >= config.min_inliers_per_side))


def _sample(gray, points):
    points = np.asarray(points, np.float32)
    return cv2.remap(gray, points[..., 0], points[..., 1], cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT).astype(float)


def _locate_edges(gray, bases, normals, distances, config):
    """Staerksten Hell-Dunkel-Gradienten subpixelgenau entlang der Normalen finden."""
    points = bases[:, None] + distances[None, :, None] * normals[:, None]
    inner = points - normals[:, None] * config.edge_step_halfwidth_px
    outer = points + normals[:, None] * config.edge_step_halfwidth_px
    height, width = gray.shape
    valid = ((inner >= 0).all(axis=2) & (outer >= 0).all(axis=2)
             & (inner < (width-1, height-1)).all(axis=2) & (outer < (width-1, height-1)).all(axis=2))
    steps = _sample(gray, inner) - _sample(gray, outer)
    steps[~valid] = -np.inf
    indices = steps.argmax(axis=1)
    rows = np.arange(len(bases))
    interior = (indices > 0) & (indices < len(distances)-1)
    indices = np.clip(indices, 1, len(distances)-2)
    a, b, c = (steps[rows, indices+offset] for offset in (-1, 0, 1))
    usable = interior & np.isfinite(a) & np.isfinite(b) & np.isfinite(c) & (a-2*b+c < 0)
    delta = np.zeros(len(bases))
    delta[usable] = np.clip(0.5*(a[usable]-c[usable]) / (a[usable]-2*b[usable]+c[usable]), -0.5, 0.5)
    return distances[indices] + delta, b, usable


def _edge_model(gray, quad, config):
    edges = []
    gray = gray.astype(np.float32)
    distances = np.arange(config.edge_min_offset_px, config.edge_max_offset_px + 1)
    fractions = np.linspace(config.edge_end_fraction, 1-config.edge_end_fraction, config.edge_samples_per_side)
    for side in range(4):
        start, end = quad[side], quad[(side+1) % 4]
        tangent = (end-start) / np.linalg.norm(end-start)
        normal = np.array([tangent[1], -tangent[0]])
        bases = start + fractions[:, None] * (end-start)
        normals = np.broadcast_to(normal, bases.shape)
        offsets, magnitudes, valid = _locate_edges(gray, bases, normals, distances, config)
        for base, offset, magnitude, usable in zip(bases, offsets, magnitudes, valid, strict=True):
            if usable and magnitude >= 2 * config.edge_min_step:
                point = base + offset * normal
                edges.append(LcdEdge(tuple(point), float(offset), tuple(normal), 1, float(magnitude), side))
    return tuple(edges)


def propose_regions(reference_image, quad, config=FrameTrackingConfig()) -> RegionProposal:
    """Starke, selbst-eindeutige Ecken vorschlagen; fehlende Eignung offenlegen."""
    gray = _gray(reference_image)
    quad = _normalise_quad(quad)
    zone, outer, mask, band_metrics, fixed_band = _geometry(gray, quad, config)
    groups = [[] for _ in range(4)]
    ambiguous_count = 0
    strength, threshold = _proposal_strength(gray, mask, fixed_band, config)
    # Je Zone dieselbe relative Schwellenbasis wie bei manuellen Punkten.
    candidates = []
    for candidate_mask, quality in ((fixed_band, config.corner_quality),
                                    (mask & ~fixed_band, config.bezel_corner_quality)):
        found = cv2.goodFeaturesToTrack(gray, config.max_candidates, quality,
                                       config.min_spacing_px, mask=candidate_mask, blockSize=3)
        if found is not None:
            candidates.extend(found.reshape(-1, 2))
    candidates.sort(key=lambda point: (-float(strength[int(point[1]), int(point[0])]), point[1], point[0]))
    spaced = []
    limits = _proposal_spread_limits(quad, outer, config)
    for candidate in candidates:
        if any(np.linalg.norm(candidate - point) < config.min_spacing_px for point in spaced):
            continue
        spaced.append(candidate)
        if len(spaced) > config.max_candidates:
            break
        x, y = np.rint(candidate).astype(int)
        if strength[y, x] <= threshold[y, x]:
            continue
        h, r = config.patch_size // 2, config.search_radius_px
        patch = _window(gray, (x, y), h)
        search = _window(gray, (x, y), h+r+config.interpolation_guard_px)
        if patch is None or search is None:
            continue
        search = _window(gray, (x, y), h+r)
        if not _proposal_match(cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED), config):
            ambiguous_count += 1
            continue
        stable = _bezel_motion_ok(gray, (x, y), config)
        if not fixed_band[y, x] and not stable:
            continue
        local = (candidate - quad.mean(axis=0)) @ _axes(quad).T
        group = int(local[0] > 0) * 2 + int(local[1] > 0)
        arms = int(np.count_nonzero((local <= -limits[0]) | (local >= limits[1])))
        groups[group].append((-arms, not stable, FrameRegion((int(x), int(y)), config.patch_size)))
    # Reihum aus vier Quadranten: starke Ecken einer Seite verdraengen nie alle anderen.
    for group in groups:
        group.sort(key=lambda candidate: candidate[:2])
    ordered = [group[row][2] for row in range(max(map(len, groups), default=0))
               for group in groups if row < len(group)]
    regions = tuple(ordered[:config.max_regions])
    return _region_proposal(gray, quad, zone, outer, regions, ambiguous_count, config, band_metrics)


def proposal_from_regions(reference_image, quad, centres, config=FrameTrackingConfig(), *, kept_centres=()) -> RegionProposal:
    """Manuelle Mittelpunkte mit denselben Masken und Qualitaetsgrenzen pruefen.

    centre_results in metrics enthaelt zuerst kept_centres, dann centres,
    jeweils in Eingabereihenfolge; abgelehnte Punkte werden nie als
    Trackingbereich verwendet. kept_centres werden ohne Snapping geprueft.
    Fuer neue centres nach Rundung auf Rohpixel
    gilt die Snapping-Bedienregel im Modultext; requested_centre erhaelt die
    Eingabe, centre/used_centre den geprueften Punkt (used_centre=None ohne
    Maximum). Masken werden erst am gefundenen Punkt geprueft.
    """
    gray = _gray(reference_image)
    quad = _normalise_quad(quad)
    zone, outer, mask, band_metrics, fixed_band = _geometry(gray, quad, config)
    character = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(character, np.rint(zone).astype(np.int32), 255)
    # Shi-Tomasi: dieselbe 2-D-Struktur und relative Schwelle wie
    # goodFeaturesToTrack(blockSize=3, qualityLevel=corner_quality, mask=mask).
    strength, threshold = _proposal_strength(gray, mask, fixed_band, config)
    local_maximum = cv2.dilate(strength, np.ones((3, 3), np.uint8))
    regions, results = [], []
    ambiguous_count = 0
    h, r = config.patch_size // 2, config.search_radius_px
    radius = h + r + config.interpolation_guard_px
    for index, centre in enumerate([*kept_centres, *centres]):
        point = np.asarray(centre)
        if point.shape != (2,) or point.dtype.kind not in 'iuf' or not np.isfinite(point).all():
            raise ValueError("Bereich braucht zwei endliche Pixelkoordinaten")
        x, y = map(int, np.rint(point))
        used = [x, y]
        if index >= len(kept_centres):
            snap_radius = MANUAL_SNAP_RADIUS_PX
            left, top = max(0, x-snap_radius), max(0, y-snap_radius)
            right, bottom = min(gray.shape[1], x+snap_radius+1), min(gray.shape[0], y+snap_radius+1)
            candidates = []
            for cy in range(top, bottom):
                for cx in range(left, right):
                    distance_squared = (cx-x)**2 + (cy-y)**2
                    if (distance_squared <= snap_radius**2 and strength[cy, cx] > threshold[cy, cx]
                            and strength[cy, cx] == local_maximum[cy, cx]):
                        candidates.append((-float(strength[cy, cx]), distance_squared, cy, cx))
            used = None
            if candidates:
                _, _, y, x = min(candidates)
                used = [x, y]
        reason = None
        if used is None:
            reason = "zu_wenig_struktur"
        elif _window(gray, (x, y), radius) is None:
            reason = "am_bildrand"
        elif np.any(_window(character, (x, y), radius)):
            reason = "im_zeichenbereich"
        elif not mask[y, x]:
            reason = "ausserhalb_rahmenband"
        elif strength[y, x] <= threshold[y, x] or strength[y, x] != local_maximum[y, x]:
            reason = "zu_wenig_struktur"
        else:
            patch, search = _window(gray, (x, y), h), _window(gray, (x, y), h+r)
            if not _proposal_match(cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED), config):
                ambiguous_count += 1
                reason = "mehrdeutig"
            elif not fixed_band[y, x] and not _bezel_motion_ok(gray, (x, y), config):
                reason = "zu_wenig_struktur"
            elif any(np.linalg.norm(np.asarray(region.centre) - (x, y)) < config.min_spacing_px for region in regions):
                reason = "zu_nah"
        results.append({"requested_centre": point.tolist(), "centre": [x, y], "used_centre": used,
                        "ok": reason is None, "reason": reason})
        if reason is None:
            regions.append(FrameRegion((x, y), config.patch_size))
    proposal = _region_proposal(gray, quad, zone, outer, tuple(regions), ambiguous_count, config, band_metrics)
    proposal.metrics["centre_results"] = results
    return proposal


def _proposal_strength(gray, mask, fixed_band, config):
    strength = cv2.cornerMinEigenVal(gray, blockSize=3, ksize=3)
    threshold = np.full(gray.shape, float(strength[mask != 0].max()) * config.bezel_corner_quality if np.any(mask) else 0.0)
    for candidate_mask, quality in ((fixed_band, config.corner_quality),
                                    (mask & ~fixed_band, config.bezel_corner_quality)):
        if np.any(candidate_mask):
            threshold[candidate_mask != 0] = float(strength[candidate_mask != 0].max()) * quality
    return strength, threshold


def _bezel_motion_ok(gray, centre, config):
    """Neue Fasenstruktur muss bekannte Halb-Pixel-Bewegungen lokalisieren."""
    h, r = config.patch_size // 2, config.search_radius_px
    search = _window(gray, centre, h+r+1)
    patch = _window(gray, centre, h)
    if search is None or patch is None:
        return False
    for dx, dy in ((0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5)):
        moved = cv2.warpAffine(search, np.float32([[1, 0, dx], [0, 1, dy]]), search.shape[::-1])[1:-1, 1:-1]
        position, peak, ambiguous = _peak(cv2.matchTemplate(moved, patch, cv2.TM_CCOEFF_NORMED), config)
        if (ambiguous or peak < config.min_peak
                or np.linalg.norm(position - r - (dx, dy)) > config.bezel_max_localisation_error_px):
            return False
    return True


def _proposal_spread_limits(quad, outer, config):
    """Hebelarm je Achsenseite aus der Bandkontur, nur fuer den Vorschlag."""
    local = (np.asarray(outer) - quad.mean(axis=0)) @ _axes(quad).T
    extents = np.array([-local.min(axis=0), local.max(axis=0)])
    return np.maximum(config.min_spread_px, extents * config.proposal_lever_arm_fraction)


def _reserve_ok(centres, quad, config, limits):
    local = (np.asarray(centres).reshape(-1, 2) - quad.mean(axis=0)) @ _axes(quad).T
    required = config.min_inliers_per_side + config.reserve_regions
    return bool(len(centres) - config.reserve_regions >= config.min_regions
                and np.all((local <= -limits[0]).sum(axis=0) >= required)
                and np.all((local >= limits[1]).sum(axis=0) >= required))


def _region_proposal(gray, quad, zone, outer, regions, ambiguous_count, config, band_metrics):
    edges = _edge_model(gray, quad, config)
    counts = [sum(edge.side == side for edge in edges) for side in range(4)]
    strong_sides = [side for side, count in enumerate(counts) if count >= config.edge_min_points_per_side]
    weak_sides = [side for side in range(4) if side not in strong_sides]
    centres = [region.centre for region in regions]
    local = (np.asarray(centres).reshape(-1, 2) - quad.mean(axis=0)) @ _axes(quad).T
    limits = _proposal_spread_limits(quad, outer, config)
    side_counts = np.array([(local <= -limits[0]).sum(axis=0),
                            (local >= limits[1]).sum(axis=0)])
    spread = bool(np.all(side_counts >= config.min_inliers_per_side))
    reserve_ok = _reserve_ok(centres, quad, config, limits)
    reasons = []
    if len(regions) < config.min_regions:
        reasons.append("zu_wenig_rahmenbereiche")
    if not spread:
        reasons.append("rahmenbereiche_einseitig")
    if spread and not reserve_ok:
        reasons.append("rahmenbereiche_ohne_reserve")
    if (len(strong_sides) < max(3, config.edge_required_sides)
            or not any(side in strong_sides for side in (0, 2))
            or not any(side in strong_sides for side in (1, 3))):
        reasons.append("lcd_rand_fehlt")
    return RegionProposal(regions, edges, _polygon(zone), _polygon(outer), not reasons, tuple(reasons),
                          {**band_metrics, "regions": len(regions), "spread_ok": spread, "ambiguous_candidates": ambiguous_count,
                           "reserve_ok": reserve_ok, "reserve_removals": config.reserve_regions,
                           "regions_per_axis_side": side_counts.tolist(),
                           "proposal_spread_limits_px": limits.tolist(),
                           "reserve_required_per_side": config.min_inliers_per_side + config.reserve_regions,
                           "edge_points_per_side": counts,
                           "edge_sides_strong": strong_sides, "edge_sides_weak": weak_sides,
                           "local_min_px": local.min(axis=0).tolist() if len(local) else None,
                           "local_max_px": local.max(axis=0).tolist() if len(local) else None},
                          asdict(config), _polygon(quad), gray.shape, sha256(gray.tobytes()).hexdigest())


def _rigid(source, target):
    # Kabsch ohne Skala, auch fuer einen Stapel von Leave-one-out-Teilproblemen.
    a, b = source.mean(axis=-2), target.mean(axis=-2)
    covariance = (source-a[..., None, :]).swapaxes(-1, -2) @ (target-b[..., None, :])
    u, _, vt = np.linalg.svd(covariance)
    rotation = vt.swapaxes(-1, -2) @ u.swapaxes(-1, -2)
    vt[..., -1, :] *= np.where(np.linalg.det(rotation) < 0, -1, 1)[..., None]
    rotation = vt.swapaxes(-1, -2) @ u.swapaxes(-1, -2)
    return rotation, b - np.einsum("...ij,...j->...i", rotation, a)


def _ransac(source, target, config):
    # Alle Minimalpaare deterministisch und vektorisiert, kein Zufallszustand.
    pairs = np.array(list(combinations(range(len(source)), 2)))
    ds, dt = source[pairs[:, 1]] - source[pairs[:, 0]], target[pairs[:, 1]] - target[pairs[:, 0]]
    angles = np.arctan2(dt[:, 1], dt[:, 0]) - np.arctan2(ds[:, 1], ds[:, 0])
    co, si = np.cos(angles), np.sin(angles)
    rotations = np.array([[co, -si], [si, co]]).transpose(2, 0, 1)
    translations = target[pairs].mean(axis=1) - np.einsum("nij,nj->ni", rotations, source[pairs].mean(axis=1))
    residuals = np.linalg.norm(np.einsum("nij,kj->nki", rotations, source) + translations[:, None] - target, axis=2)
    inliers = residuals <= config.ransac_tolerance_px
    counts = inliers.sum(axis=1)
    costs = np.minimum(residuals, config.ransac_tolerance_px).sum(axis=1)
    best = np.lexsort((costs, -counts))[0]
    selected = inliers[best]
    for _ in range(2):
        if selected.sum() < config.min_regions:
            return None
        rotation, translation = _rigid(source[selected], target[selected])
        refined = np.linalg.norm(source @ rotation.T + translation - target, axis=1) <= config.ransac_tolerance_px
        if np.array_equal(refined, selected):
            return rotation, translation, selected
        selected = refined
    # Kein Fit mit nachtraeglich geaenderter Inliermenge akzeptieren.
    return None


def _similarity(source, target):
    # Umeyama, orientierungserhaltend; auch gestapelte Leave-one-out-Fits.
    a, b = source.mean(axis=-2), target.mean(axis=-2)
    centred_source, centred_target = source-a[..., None, :], target-b[..., None, :]
    covariance = centred_source.swapaxes(-1, -2) @ centred_target
    u, singular, vt = np.linalg.svd(covariance)
    sign = np.where(np.linalg.det(vt.swapaxes(-1, -2) @ u.swapaxes(-1, -2)) < 0, -1, 1)
    vt[..., -1, :] *= sign[..., None]
    rotation = vt.swapaxes(-1, -2) @ u.swapaxes(-1, -2)
    scale = (singular[..., 0] + sign*singular[..., 1]) / (centred_source**2).sum(axis=(-2, -1))
    transform = scale[..., None, None]*rotation
    return rotation, b - np.einsum("...ij,...j->...i", transform, a), scale


def _similarity_ransac(source, target, config):
    # Alle Minimalpaare, gleiche Konsens-/Kostenregel wie im starren Pfad.
    pairs = np.array(list(combinations(range(len(source)), 2)))
    ds, dt = source[pairs[:, 1]] - source[pairs[:, 0]], target[pairs[:, 1]] - target[pairs[:, 0]]
    lengths = np.linalg.norm(ds, axis=1)
    scales = np.divide(np.linalg.norm(dt, axis=1), lengths, out=np.zeros_like(lengths), where=lengths > 0)
    limit = config.coarse_max_scale_deviation
    valid = (scales >= 1-limit) & (scales <= 1+limit)
    if not valid.any():
        return None
    pairs, ds, dt, scales = pairs[valid], ds[valid], dt[valid], scales[valid]
    angles = np.arctan2(dt[:, 1], dt[:, 0]) - np.arctan2(ds[:, 1], ds[:, 0])
    co, si = np.cos(angles), np.sin(angles)
    transforms = scales[:, None, None]*np.array([[co, -si], [si, co]]).transpose(2, 0, 1)
    translations = target[pairs].mean(axis=1) - np.einsum("nij,nj->ni", transforms, source[pairs].mean(axis=1))
    residuals = np.linalg.norm(np.einsum("nij,kj->nki", transforms, source) + translations[:, None] - target, axis=2)
    inliers = residuals <= config.ransac_tolerance_px
    counts = inliers.sum(axis=1)
    costs = np.minimum(residuals, config.ransac_tolerance_px).sum(axis=1)
    selected = inliers[np.lexsort((costs, -counts))[0]]
    for _ in range(2):
        if selected.sum() < config.min_regions:
            return None
        rotation, translation, scale = _similarity(source[selected], target[selected])
        if not 1-limit <= scale <= 1+limit:
            return None
        refined = np.linalg.norm(source @ (scale*rotation).T + translation - target, axis=1) <= config.ransac_tolerance_px
        if np.array_equal(refined, selected):
            return rotation, translation, selected, float(scale)
        selected = refined
    return None


@dataclass(frozen=True, slots=True)
class CoarseEstimate:
    """Letzte Grobschaetzung in Rohpixeln; used bezeichnet den zweiten Feinversuch."""

    dx: float
    dy: float
    response: float
    used: bool = False
    scale: float | None = None


class FrameTracker:
    """Jedes Bild unabhaengig gegen die urspruengliche Referenz pruefen."""

    def __init__(self, reference_image, quad, proposal, config=FrameTrackingConfig()):
        gray = _gray(reference_image)
        normalised = _normalise_quad(quad)
        if (proposal.config != asdict(config) or proposal.reference_shape != gray.shape
                or not np.array_equal(proposal.normalised_quad, normalised)
                or proposal.reference_sha256 != sha256(gray.tobytes()).hexdigest()):
            raise ValueError("Vorschlag passt nicht zu Referenzbild, Quad oder Konfiguration")
        self.config = config
        self.quad = np.asarray(quad, dtype=float).copy()
        self.normalised_quad = normalised
        self.proposal = proposal
        self.shape = gray.shape
        h = config.patch_size // 2
        patches = []
        for region in proposal.regions:
            safe = _window(gray, region.centre, h+config.search_radius_px+config.interpolation_guard_px)
            patch = _window(gray, region.centre, h)
            patches.append(patch.copy() if safe is not None and region.size == config.patch_size else None)
        self.patches = tuple(patches)
        self.sources = np.asarray([region.centre for region in proposal.regions], dtype=float).reshape(-1, 2)
        counts = [sum(edge.side == side for edge in proposal.edges) for side in range(4)]
        self.edges = tuple(edge for edge in proposal.edges if counts[edge.side] >= config.edge_min_points_per_side)
        self.edge_points = np.asarray([edge.point for edge in self.edges]).reshape(-1, 2)
        self.edge_normals = np.asarray([edge.normal for edge in self.edges]).reshape(-1, 2)
        self.last_coarse: CoarseEstimate | None = None
        # Fester Ausschnitt und feste Maske; kein Zustand aus aktuellen Bildern.
        outer = np.asarray(proposal.outer_limit)
        lo = np.maximum(np.floor(outer.min(axis=0)).astype(int), 0)
        hi = np.minimum(np.ceil(outer.max(axis=0)).astype(int)+1, gray.shape[::-1])
        # Fuer Hann und Laplace mindestens 2x2 Grobpixel; unbrauchbare
        # kleine Ausschnitte deaktivieren nur die optionale Grobsuche.
        self._coarse_reference = None
        self._coarse_mask = None
        if np.any(hi-lo < 8):
            return
        # Bis zu drei Randpixel abschneiden: exakter AREA-Faktor 4 statt
        # teurem gebrochenem Flaechenfilter. Hann bleibt am Ausschnittrand 0.
        hi -= (hi-lo) % 4
        self._coarse_crop = (slice(lo[1], hi[1]), slice(lo[0], hi[0]))
        mask = np.zeros(gray.shape, np.uint8)
        cv2.fillPoly(mask, [np.rint(outer).astype(np.int32)], 1)
        characters = np.zeros_like(mask)
        cv2.fillConvexPoly(characters, np.rint(proposal.character_zone).astype(np.int32), 1)
        # Bewegte Zeichen ausschliessen: Translation, Drehung, Skala und
        # zwoelf Rohpixel: sieben fuer AREA/Laplace, fuenf Reserve.
        radius = np.linalg.norm(self.quad - self.quad.mean(axis=0), axis=1).max()
        guard = int(np.ceil(config.max_shift_px + 2*radius*np.sin(np.radians(config.max_rotation_deg)/2)
                            + radius*config.coarse_max_scale_deviation)) + 12
        characters = cv2.dilate(characters, np.ones((2*guard+1,)*2, np.uint8))
        mask[characters != 0] = 0
        mask = mask[self._coarse_crop].astype(np.float32)
        # Vierfach kleiner, auf beiden Achsen exakt derselbe Rohpixelfaktor.
        coarse_size = tuple(np.array(mask.shape[::-1]) // 4)
        self._coarse_factors = np.array(mask.shape[::-1]) / coarse_size
        mask = cv2.resize(mask, coarse_size, interpolation=cv2.INTER_AREA)
        self._coarse_mask = mask * cv2.createHanningWindow(mask.shape[::-1], cv2.CV_32F)
        self._coarse_reference = self._coarse_image(gray)

    def _coarse_image(self, gray):
        # Hochpass vermeidet einen dominanten Nullshift der festen Maskenkante.
        crop = cv2.resize(gray[self._coarse_crop], self._coarse_mask.shape[::-1],
                          interpolation=cv2.INTER_AREA).astype(np.float32)
        return cv2.Laplacian(crop, cv2.CV_32F) * self._coarse_mask

    def _estimate_coarse(self, gray) -> CoarseEstimate:
        if self._coarse_reference is None:
            return CoarseEstimate(0.0, 0.0, 0.0)
        image = self._coarse_image(gray)
        if not np.any(image) or not np.any(self._coarse_reference):
            return CoarseEstimate(0.0, 0.0, 0.0)
        (dx, dy), response = cv2.phaseCorrelate(self._coarse_reference, image)
        dx, dy = np.array((dx, dy))*self._coarse_factors
        return CoarseEstimate(float(dx), float(dy), float(response))

    def _edges_visible(self, gray, rotation, translation, scale=1.0):
        config = self.config
        if not self.edges:
            return False
        points = self.edge_points @ (scale*rotation).T + translation
        normals = self.edge_normals @ rotation.T
        distances = np.arange(-config.edge_search_radius_px, config.edge_search_radius_px+1)
        # Nur das Rand-ROI in Float konvertieren; dieselben bilinearen Proben,
        # ohne pro Update das gesamte Kamerabild in Float zu kopieren.
        padding = config.edge_search_radius_px + config.edge_step_halfwidth_px + 1
        lo = np.maximum(np.floor(points.min(axis=0)-padding).astype(int), 0)
        hi = np.minimum(np.ceil(points.max(axis=0)+padding).astype(int)+1, gray.shape[::-1])
        if np.any(hi <= lo):
            return False
        roi = gray[lo[1]:hi[1], lo[0]:hi[0]].astype(np.float32)
        offsets, steps, valid = _locate_edges(roi, points-lo, normals, distances, config)
        magnitudes = np.array([edge.magnitude for edge in self.edges])
        polarity = np.array([edge.polarity for edge in self.edges])
        good = (valid & (np.abs(offsets) <= config.edge_position_tolerance_px)
                & (steps * polarity >= np.maximum(config.edge_min_step, magnitudes * config.edge_magnitude_fraction)))
        sides = np.array([edge.side for edge in self.edges])
        return all(float(good[sides == side].mean()) >= config.edge_required_share for side in np.unique(sides))

    def update(self, image) -> TrackResult:
        self.last_coarse = None
        gray = _gray(image)
        first = self._fine_update(gray)
        if first.reason not in {"rahmen_unstimmig", "zu_wenig_rahmenmerkmale", "rahmen_mehrdeutig"}:
            return first
        estimate = self._estimate_coarse(gray)
        self.last_coarse = estimate
        config = self.config
        if (not np.isfinite((estimate.dx, estimate.dy, estimate.response)).all()
                or estimate.response <= config.coarse_min_response
                or np.hypot(estimate.dx, estimate.dy) > config.max_shift_px + _COARSE_ERROR_MARGIN_PX):
            return first
        offset = tuple(np.rint((estimate.dx, estimate.dy)).astype(int))
        if offset == (0, 0) and first.reason != "rahmen_unstimmig":
            # Gleiche Fenster, gleiche Treffer: zu wenige oder mehrdeutige
            # Merkmale wiederholen sich exakt; nur ein Fit kann sich aendern.
            return first
        self.last_coarse = replace(estimate, used=True)
        return self._fine_update(gray, offset, similarity=True)

    def _fine_update(self, gray, offset=(0, 0), *, similarity=False) -> TrackResult:
        config = self.config

        def reject(reason):
            return TrackResult(None, 0.0, 0.0, 0.0, reason)

        if gray.shape != self.shape:
            return reject("bildgroesse_abweichend")
        if not self.proposal.ok:
            return reject("vorschlag_ungeeignet")
        h, r = config.patch_size // 2, config.search_radius_px
        indices, targets, peaks = [], [], []
        ambiguous_count = 0
        centres = self.sources.astype(int)
        if offset != (0, 0):
            centres += offset
        for index, ((x, y), patch) in enumerate(zip(centres, self.patches, strict=True)):
            search = _window(gray, (x, y), h+r)
            if patch is None or search is None:
                continue
            position, peak, ambiguous = _peak(cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED), config)
            # Ein Randmaximum kann ausserhalb weiter steigen. Ohne beide
            # Nachbarn ist weder ein Peak noch seine Subpixelposition belegt.
            if peak < config.min_peak or np.any(position <= 0) or np.any(position >= 2*r):
                continue
            if ambiguous:
                ambiguous_count += 1
                continue
            indices.append(index)
            targets.append(position + (x-r, y-r))
            peaks.append(peak)
        if len(indices) < config.min_regions:
            return reject("rahmen_mehrdeutig" if ambiguous_count else "zu_wenig_rahmenmerkmale")
        source, target = self.sources[indices], np.asarray(targets)
        fit = _similarity_ransac(source, target, config) if similarity else _ransac(source, target, config)
        if fit is None:
            return reject("rahmen_unstimmig")
        rotation, translation, inliers = fit[:3]
        scale = fit[3] if similarity else 1.0
        if similarity and self.last_coarse is not None:
            self.last_coarse = replace(self.last_coarse, scale=scale)
        transform = scale*rotation if similarity else rotation
        if not _spread(source[inliers], self.normalised_quad, config):
            return reject("rahmen_unstimmig")
        # Jeder Inlier muss entbehrlich sein: geometrische Hebelwirkung direkt
        # an allen vier OCR-Ecken messen, ohne nachtraegliche Inlier-Neuauswahl.
        stable_source, stable_target = source[inliers], target[inliers]
        predicted = self.quad @ transform.T + translation
        count = len(stable_source)
        keep = ~np.eye(count, dtype=bool)
        source_sets = np.broadcast_to(stable_source, (count, count, 2))[keep].reshape(count, count-1, 2)
        target_sets = np.broadcast_to(stable_target, (count, count, 2))[keep].reshape(count, count-1, 2)
        if similarity:
            loo_rotation, loo_translation, loo_scale = _similarity(source_sets, target_sets)
            loo_rotation = loo_scale[:, None, None]*loo_rotation
        else:
            loo_rotation, loo_translation = _rigid(source_sets, target_sets)
        loo_quads = self.quad @ loo_rotation.swapaxes(-1, -2) + loo_translation[:, None, :]
        if np.linalg.norm(loo_quads - predicted, axis=-1).max() > config.max_leave_one_out_corner_px:
            return reject("rahmen_unstimmig")
        residuals = np.linalg.norm(stable_source @ transform.T + translation - stable_target, axis=1)
        if (np.sqrt(np.mean(residuals**2)) > config.max_inlier_rms_px
                or residuals.max() > config.max_inlier_residual_px):
            return reject("rahmen_unstimmig")
        centre = self.quad.mean(axis=0)
        shift = float(np.linalg.norm(transform @ centre + translation - centre))
        angle = float(np.degrees(np.arctan2(rotation[1, 0], rotation[0, 0])))
        score = float(np.clip(inliers.sum() / len(self.sources) * np.mean(np.asarray(peaks)[inliers]), 0, 1))
        reason = None
        if shift > config.max_shift_px:
            reason = "shift_out_of_bounds"
        elif abs(angle) > config.max_rotation_deg:
            reason = "rotation_out_of_bounds"
        elif not self._edges_visible(gray, rotation, translation, scale):
            reason = "lcd_rand_fehlt"
        moved = None if reason else _polygon(self.quad @ transform.T + translation)
        return TrackResult(moved, shift, angle, score, reason)
