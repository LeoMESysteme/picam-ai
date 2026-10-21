"""Zustandslose Nachfuehrung aus begrenzten Rahmenfenstern und LCD-Rand.

Parameter festgelegt am Entwicklungsdatensatz r13-werteplan-20261021, vor der
getrennten Abnahme eingefroren. Kleine rohe Fenster vermeiden Zeicheninhalt;
Eindeutigkeit, verteilte Inlier und der unabhaengige helle LCD-Rand bleiben
harte Regeln. Keine automatische Abschwaechung bei fehlender Struktur.

Aussengrenze: Quad um Faktor 3 um seinen Mittelpunkt skalieren, zusaetzlich
an beiden Enden auf 100 Rohpixel Abstand begrenzen. Das schmale Band erfasst
die Glasecken, aber nicht Kabel oberhalb oder Tisch jenseits des Rahmens.
Dies ist eine geometrische Vorauswahl, keine allgemeine Gehaeuseerkennung.
Alle Suchpixel samt einem Interpolationspixel bleiben in diesem Band und
jenseits des um 8 Pixel dilatierten Zeichenpolygons.

Streuung wird in lokalen Quadachsen geprueft: mindestens drei Inlier auf
JEDER Seite BEIDER Achsen, jeweils mindestens 20 px vom Mittelpunkt entfernt
(effektiv mindestens sechs, zusaetzlich zur Bereichszahlgrenze vier).
Jeder Inlier wird einzeln weggelassen und der starre Fit erneut berechnet;
bewegt sich dadurch eine OCR-Ecke um mehr als 0.5 px, wird abgelehnt.
Dies schliesst den auf DEV-Fixtures reproduzierten einzelnen Hebelpunkt aus.
Shift ist die Verschiebung des Quadmittelpunktes in Rohpixeln. Rotation ist
der vorwaerts wirkende Winkel, gleiches Vorzeichen wie ECC in track.py:
positive Werte drehen im Bild (y nach unten) im Uhrzeigersinn; ein positiver
Winkel an cv2.getRotationMatrix2D liefert daher eine negative rotation_deg.
Intern TL, TR, BR, BL wie rectify._order_quad, Ausgabe in Eingabereihenfolge.

LCD-Modell: je Seite 18 Normalprofile zwischen 10 und 90 Prozent der
Seitenlaenge, Suche 14..90 px nach aussen. Helligkeitsdifferenz bei +/-1 px,
parabolische Subpixelposition am staerksten Hell-Dunkel-Gradienten, gleiche
Lokalisierung in Referenz und aktuellem Bild. Nur Schritte >=18 Graustufen
bleiben; alle vier Seiten brauchen mindestens sechs Punkte. Im aktuellen
Bild wird innerhalb +/-4 px entlang der mitgedrehten Normalen lokalisiert;
die gefundene Position muss hoechstens 1.0 px von der Vorhersage abweichen.
Alle vier Seiten brauchen mindestens 80 Prozent solcher Nachweise mit
gleicher Polaritaet und mindestens halber Referenzstaerke (weiterhin >=18).
Das ersetzt die zu breite 6-px-Schrittprobe: falsche 1.5-px-Bewegung und
0.3-Grad-Drehung werden auf der Referenz abgelehnt. Keine Grenzlockerung.

15-px-Patches und 12-px-Suchradius lassen kleine Rohbildbewegungen zu;
Peak >=0.75 und Zweitpeak/Peak <=0.95 ausserhalb +/-3 px verlangen erkennbare
und eindeutige Struktur. Inlier mit <=1.5 px Residuum sichern den starren Fit;
Bewegungsgrenzen bleiben 20 px / 3 Grad. Numerische Defaults ausschliesslich
an der benannten Entwicklungsaufnahme und ihren Fixtures festgelegt.

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
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from itertools import combinations

import cv2
import numpy as np

from dispread.detect import Quad
from dispread.track import TrackResult


@dataclass(frozen=True, slots=True)
class FrameTrackingConfig:
    patch_size: int = 15
    search_radius_px: int = 12
    min_peak: float = 0.75
    ambiguity_limit: float = 0.95
    ambiguity_radius_px: int = 3
    min_regions: int = 4
    max_regions: int = 12
    min_spread_px: float = 20.0
    min_inliers_per_side: int = 3
    max_leave_one_out_corner_px: float = 0.5
    min_spacing_px: float = 28.0
    corner_quality: float = 0.02
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
    edge_position_tolerance_px: float = 1.0
    edge_required_share: float = 0.8
    edge_required_sides: int = 4

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> FrameTrackingConfig:
        # Keine fehlenden Grenzen still mit heutigen Defaults auffuellen.
        if not isinstance(data, dict) or set(data) != {field.name for field in fields(cls)}:
            raise ValueError("Unvollstaendige oder unbekannte Rahmenkonfiguration")
        for field in fields(cls):
            if type(data[field.name]) is not type(field.default):
                raise ValueError(f"Ungueltiger Typ fuer Rahmenkonfiguration: {field.name}")
        return cls(**data)

    def __post_init__(self):
        if not all(np.isfinite(getattr(self, field.name)) for field in fields(self)):
            raise ValueError("Pruefgrenzen muessen endlich sein")
        if self.patch_size < 3 or self.patch_size % 2 != 1 or self.search_radius_px < 1:
            raise ValueError("Ungerade Patchgroesse und positiver Suchradius erforderlich")
        if not 0 < self.min_peak <= 1 or not 0 < self.ambiguity_limit < 1:
            raise ValueError("Ungueltige Matchinggrenzen")
        if not 2 <= self.min_regions <= self.max_regions or self.min_spread_px <= 0:
            raise ValueError("Ungueltige Bereichszahl oder Streuung")
        if (self.min_inliers_per_side < 2 or 2*self.min_inliers_per_side > self.max_regions
                or self.max_leave_one_out_corner_px <= 0
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
        FrameTrackingConfig.from_dict(data["config"])
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


def _geometry(shape, quad, config):
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
    cv2.fillConvexPoly(mask, np.rint(zone).astype(np.int32), 0)
    radius = config.patch_size // 2 + config.search_radius_px + config.interpolation_guard_px
    mask = cv2.erode(mask, np.ones((2*radius+1, 2*radius+1), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return zone, outer, mask


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
            if usable and magnitude >= config.edge_min_step:
                point = base + offset * normal
                edges.append(LcdEdge(tuple(point), float(offset), tuple(normal), 1, float(magnitude), side))
    return tuple(edges)


def propose_regions(reference_image, quad, config=FrameTrackingConfig()) -> RegionProposal:
    """Starke, selbst-eindeutige Ecken vorschlagen; fehlende Eignung offenlegen."""
    gray = _gray(reference_image)
    quad = _normalise_quad(quad)
    zone, outer, mask = _geometry(gray.shape, quad, config)
    candidates = cv2.goodFeaturesToTrack(gray, config.max_candidates, config.corner_quality,
                                        config.min_spacing_px, mask=mask, blockSize=3)
    groups = [[] for _ in range(4)]
    ambiguous_count = 0
    if candidates is not None:
        for candidate in candidates.reshape(-1, 2):
            x, y = np.rint(candidate).astype(int)
            h, r = config.patch_size // 2, config.search_radius_px
            patch = _window(gray, (x, y), h)
            search = _window(gray, (x, y), h+r+config.interpolation_guard_px)
            if patch is None or search is None:
                continue
            search = _window(gray, (x, y), h+r)
            _, peak, ambiguous = _peak(cv2.matchTemplate(search, patch, cv2.TM_CCOEFF_NORMED), config)
            if ambiguous or peak < config.min_peak:
                ambiguous_count += 1
                continue
            local = (candidate - quad.mean(axis=0)) @ _axes(quad).T
            group = int(local[0] > 0) * 2 + int(local[1] > 0)
            groups[group].append(FrameRegion((int(x), int(y)), config.patch_size))
    # Reihum aus vier Quadranten: starke Ecken einer Seite verdraengen nie alle anderen.
    ordered = []
    for row in range(max(map(len, groups), default=0)):
        for group in groups:
            if row < len(group):
                ordered.append(group[row])
    regions = tuple(ordered[:config.max_regions])
    edges = _edge_model(gray, quad, config)
    counts = [sum(edge.side == side for edge in edges) for side in range(4)]
    centres = [region.centre for region in regions]
    spread = _spread(centres, quad, config)
    local = (np.asarray(centres).reshape(-1, 2) - quad.mean(axis=0)) @ _axes(quad).T
    reasons = []
    if len(regions) < config.min_regions:
        reasons.append("zu_wenig_rahmenbereiche")
    if not spread:
        reasons.append("rahmenbereiche_einseitig")
    if min(counts) < config.edge_min_points_per_side:
        reasons.append("lcd_rand_fehlt")
    return RegionProposal(regions, edges, _polygon(zone), _polygon(outer), not reasons, tuple(reasons),
                          {"regions": len(regions), "spread_ok": spread, "ambiguous_candidates": ambiguous_count,
                           "edge_points_per_side": counts,
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
        self.edge_points = np.asarray([edge.point for edge in proposal.edges]).reshape(-1, 2)
        self.edge_normals = np.asarray([edge.normal for edge in proposal.edges]).reshape(-1, 2)

    def _edges_visible(self, gray, rotation, translation):
        config = self.config
        points = self.edge_points @ rotation.T + translation
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
        magnitudes = np.array([edge.magnitude for edge in self.proposal.edges])
        polarity = np.array([edge.polarity for edge in self.proposal.edges])
        good = (valid & (np.abs(offsets) <= config.edge_position_tolerance_px)
                & (steps * polarity >= np.maximum(config.edge_min_step, magnitudes * config.edge_magnitude_fraction)))
        sides = np.array([edge.side for edge in self.proposal.edges])
        return sum(bool(np.any(sides == side)) and float(good[sides == side].mean()) >= config.edge_required_share
                   for side in range(4)) >= config.edge_required_sides

    def update(self, image) -> TrackResult:
        config = self.config

        def reject(reason):
            return TrackResult(None, 0.0, 0.0, 0.0, reason)

        gray = _gray(image)
        if gray.shape != self.shape:
            return reject("bildgroesse_abweichend")
        if not self.proposal.ok:
            return reject("vorschlag_ungeeignet")
        h, r = config.patch_size // 2, config.search_radius_px
        indices, targets, peaks = [], [], []
        ambiguous_count = 0
        for index, ((x, y), patch) in enumerate(zip(self.sources.astype(int), self.patches, strict=True)):
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
        fit = _ransac(source, target, config)
        if fit is None:
            return reject("rahmen_unstimmig")
        rotation, translation, inliers = fit
        if not _spread(source[inliers], self.normalised_quad, config):
            return reject("rahmen_unstimmig")
        # Jeder Inlier muss entbehrlich sein: geometrische Hebelwirkung direkt
        # an allen vier OCR-Ecken messen, ohne nachtraegliche Inlier-Neuauswahl.
        stable_source, stable_target = source[inliers], target[inliers]
        predicted = self.quad @ rotation.T + translation
        count = len(stable_source)
        keep = ~np.eye(count, dtype=bool)
        source_sets = np.broadcast_to(stable_source, (count, count, 2))[keep].reshape(count, count-1, 2)
        target_sets = np.broadcast_to(stable_target, (count, count, 2))[keep].reshape(count, count-1, 2)
        loo_rotation, loo_translation = _rigid(source_sets, target_sets)
        loo_quads = self.quad @ loo_rotation.swapaxes(-1, -2) + loo_translation[:, None, :]
        if np.linalg.norm(loo_quads - predicted, axis=-1).max() > config.max_leave_one_out_corner_px:
            return reject("rahmen_unstimmig")
        centre = self.quad.mean(axis=0)
        shift = float(np.linalg.norm(rotation @ centre + translation - centre))
        angle = float(np.degrees(np.arctan2(rotation[1, 0], rotation[0, 0])))
        score = float(np.clip(inliers.sum() / len(self.sources) * np.mean(np.asarray(peaks)[inliers]), 0, 1))
        reason = None
        if shift > config.max_shift_px:
            reason = "shift_out_of_bounds"
        elif abs(angle) > config.max_rotation_deg:
            reason = "rotation_out_of_bounds"
        elif not self._edges_visible(gray, rotation, translation):
            reason = "lcd_rand_fehlt"
        moved = None if reason else _polygon(self.quad @ rotation.T + translation)
        return TrackResult(moved, shift, angle, score, reason)
