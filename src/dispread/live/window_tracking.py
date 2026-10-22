"""Experimenteller Offline-Tracker fuer den LCD-Glasrand, ohne Live-Anbindung.

Farbbilder: Signal max(0, 2*G-R-B), also Gruenanteil ohne neutrale
Reflexe der Einfassung. Graubilder: Grauwertsignal; kein Moduswechsel beim
Update. Damit wird der Glasrand statt der hellen Einfassung verfolgt.
Nur Normalprofile ausserhalb des OCR-Polygons plus 8 px Zeichenabstand werden
abgetastet (einschliesslich bilinearer Interpolation). Im aktuellen Bild ist
ein Schritt stark, wenn er >=25% der lokalen Profilspannweite erreicht und
>=3 mal dem Median benachbarter Profildifferenzen entspricht. Keine absolute
Grauwert- oder Referenzhelligkeitsschwelle im Update: auch dunkle Profile
werden relativ zu ihrem eigenen Kontrast bewertet. Hell -> dunkel ist die
vorgegebene Polaritaet. Unaufgeloeste oder mehrdeutige Peaks werden verworfen.

Default: 18 Profile/Seite bei 10..90%, Referenzsuche 14..90 px nach aussen,
Schrittproben bei +/-2 px; Referenzschritt >=12 Signaleinheiten und
Geradenresiduum <=1.5 px. Updates suchen
+/-16 px, begrenzt durch die Zeichensperre. Mindestens 6 und 55% der Punkte
JEDER Seite sind Pflicht, insbesondere beide kurzen Seiten. Ein gerader Rand
liefert keine tangentiale Korrespondenz! Deshalb ausschliesslich Punkt-zu-
Gerade-Residuen mit mitgedrehten Normalen, niemals Punkt-zu-Punkt-Fits.

Iterative robuste kleinste Quadrate: Huber-Gewichte, danach harte 0.8-px-
Inliergrenze, RMS <=0.5 px. Leave-one-side-out darf keine OCR-Ecke mehr als
0.5 px bewegen. Nur Rotation/Translation, vorwaerts auf das ORIGINAL-Quad;
keine Historie. Grenzen 20 Rohpixel / 3 Grad wie beim eingefrorenen
Rahmentracker (TrackConfig: 0.1 der Arbeitsbreite 200 / 3 Grad).
Score = Inlieranteil, keine Fehlerwahrscheinlichkeit. Defaults ausschliesslich
auf DEV + Nacht, vor Auswertung der getrennten Abnahme festgelegt.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from hashlib import sha256

import cv2
import numpy as np

from dispread.live.frame_tracking import LcdEdge, _gray, _normalise_quad, _polygon, _sample
from dispread.track import TrackResult


@dataclass(frozen=True, slots=True)
class WindowTrackingConfig:
    """Alle Distanzen in Rohpixeln; Regeln und Vorgaben siehe Modultext."""

    character_margin_px: int = 8
    edge_min_offset_px: int = 14
    edge_max_offset_px: int = 90
    samples_per_side: int = 18
    end_fraction: float = 0.1
    step_halfwidth_px: float = 2.0
    reference_min_step: float = 12.0
    reference_line_tolerance_px: float = 1.5
    search_radius_px: int = 16
    min_relative_step: float = 0.25
    min_noise_ratio: float = 3.0
    ambiguity_ratio: float = 0.9
    min_points_per_side: int = 6
    min_side_share: float = 0.55
    residual_limit_px: float = 0.8
    max_rms_px: float = 0.5
    max_leave_one_side_out_corner_px: float = 0.5
    max_shift_px: float = 20.0
    max_rotation_deg: float = 3.0

    def __post_init__(self):
        if any(isinstance(getattr(self, f.name), bool)
               or not isinstance(getattr(self, f.name), (int,) if type(f.default) is int else (int, float))
               or not np.isfinite(getattr(self, f.name)) for f in fields(self)):
            raise ValueError("Ungueltige Fensterkonfiguration")
        if (self.character_margin_px < 8 or self.edge_min_offset_px <= self.character_margin_px + self.step_halfwidth_px + 3
                or self.edge_max_offset_px <= self.edge_min_offset_px or self.search_radius_px < 2
                or not 3 <= self.min_points_per_side <= self.samples_per_side
                or not 0 < self.end_fraction < 0.5 or self.step_halfwidth_px <= 0
                or self.reference_min_step <= 0 or self.reference_line_tolerance_px <= 0
                or not 0 < self.min_relative_step <= 1 or self.min_noise_ratio <= 0
                or not 0 < self.ambiguity_ratio < 1 or not 0 < self.min_side_share <= 1
                or self.residual_limit_px <= 0 or self.max_rms_px <= 0
                or self.max_leave_one_side_out_corner_px <= 0 or self.max_shift_px < 0 or self.max_rotation_deg < 0):
            raise ValueError("Ungueltige Fenstergrenzen")


@dataclass(frozen=True, slots=True)
class WindowModel:
    edges: tuple[LcdEdge, ...]
    ok: bool
    reference_sha256: str
    reference_shape: tuple[int, int]
    quad: tuple[tuple[float, float], ...]
    config: WindowTrackingConfig
    colour: bool


def _signal(image):
    gray = _gray(image)  # Typ und Bildform vor jeder Abtastung pruefen.
    if image.ndim == 2:
        return gray.astype(np.float32)
    b, g, r = (image[:, :, i].astype(np.float32) for i in range(3))
    return np.maximum(0, 2*g-r-b)


def _normals(quad):
    sides = np.roll(quad, -1, axis=0)-quad
    normals = np.column_stack((sides[:, 1], -sides[:, 0]))
    return normals / np.linalg.norm(normals, axis=1)[:, None]


def _locate(gray, bases, normals, distances, quad, config):
    """Nur sichere Profilpixel lesen; ausserhalb liegende Proben nie remappen."""
    points = bases[:, None] + distances[None, :, None]*normals[:, None]
    inner = points - config.step_halfwidth_px*normals[:, None]
    outer = points + config.step_halfwidth_px*normals[:, None]
    qnormals = _normals(quad)
    exclusion = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(exclusion, np.rint(quad).astype(np.int32), 255)
    margin = config.character_margin_px
    exclusion = cv2.dilate(exclusion, np.ones((2*margin+1, 2*margin+1), np.uint8))

    def safe(probes):
        outside = ((probes[:, :, None]-quad) * qnormals).sum(axis=-1).max(axis=-1)
        # 2 px fuer bilineare Nachbarn und die gerundete Zeichensperre.
        inside = ((outside > config.character_margin_px+2) & (probes >= 0).all(axis=-1)
                  & (probes < np.array(gray.shape[::-1])-1).all(axis=-1))
        # Jeden der vier bilinearen Quellpixel gegen die gerasterte Sperre
        # pruefen, einschliesslich Rundung des Polygons (konservatives Quadrat).
        lo = np.floor(probes[inside]).astype(int)
        allowed = np.ones(len(lo), bool)
        for dx in (0, 1):
            for dy in (0, 1):
                allowed &= exclusion[lo[:, 1]+dy, lo[:, 0]+dx] == 0
        inside[inside] = allowed
        return inside

    valid = safe(inner) & safe(outer)
    values = []
    for probes in (inner, outer):
        sampled = np.zeros(valid.shape, dtype=float)
        if valid.any():
            sampled[valid] = _sample(gray, probes[valid][None])[0]
        values.append(sampled)
    steps = values[0]-values[1]
    steps[~valid] = -np.inf
    indices = steps.argmax(axis=1)
    rows = np.arange(len(bases))
    interior = (indices > 0) & (indices < len(distances)-1)
    indices = np.clip(indices, 1, len(distances)-2)
    a, b, c = (steps[rows, indices+d] for d in (-1, 0, 1))
    finite = np.isfinite(a) & np.isfinite(b) & np.isfinite(c)
    curvature = np.zeros(len(bases))
    curvature[finite] = a[finite]-2*b[finite]+c[finite]
    good = interior & finite & (curvature < 0) & (b > 0)
    delta = np.zeros(len(bases))
    delta[good] = np.clip(0.5*(a[good]-c[good])/(a[good]-2*b[good]+c[good]), -0.5, 0.5)
    relative = np.zeros(len(bases), bool)
    for i in range(len(bases)):
        if not good[i]:
            continue
        profile = np.concatenate([v[i, valid[i]] for v in values])
        contrast = np.ptp(profile)
        adjacent = valid[i, 1:] & valid[i, :-1]
        noise = np.median(np.abs(np.diff(values[0][i]))[adjacent])
        other = steps[i].copy()
        other[max(0, indices[i]-3):indices[i]+4] = -np.inf
        relative[i] = (contrast > 0 and b[i] >= config.min_relative_step*contrast
                       and b[i] >= config.min_noise_ratio*noise
                       and other.max() < config.ambiguity_ratio*b[i])
    return distances[indices]+delta, b, good, relative


def propose_window(reference_image, quad, config=WindowTrackingConfig()) -> WindowModel:
    """Staerksten Glas->Rahmen-Schritt ausserhalb der Zeichen suchen."""
    gray = _signal(reference_image)
    quad = _normalise_quad(quad)
    normals = _normals(quad)
    distances = np.arange(config.edge_min_offset_px, config.edge_max_offset_px+1)
    fractions = np.linspace(config.end_fraction, 1-config.end_fraction, config.samples_per_side)
    edges = []
    for side in range(4):
        bases = quad[side]+fractions[:, None]*(quad[(side+1) % 4]-quad[side])
        ns = np.broadcast_to(normals[side], bases.shape)
        offsets, magnitude, valid, _ = _locate(gray, bases, ns, distances, quad, config)
        keep = valid & (magnitude >= config.reference_min_step)
        # Ein zufaellig staerkerer Gehaeuseschritt ist kein Glasrandpunkt.
        for _ in range(3):
            if keep.sum() < config.min_points_per_side:
                break
            indices = np.flatnonzero(keep)
            left, right = np.triu_indices(len(indices), 1)
            slope = np.median((offsets[indices[right]]-offsets[indices[left]]) /
                              (fractions[indices[right]]-fractions[indices[left]]))
            intercept = np.median(offsets[keep]-slope*fractions[keep])
            residual = offsets-(slope*fractions+intercept)
            keep &= np.abs(residual-np.median(residual[keep])) <= config.reference_line_tolerance_px
        for i in np.flatnonzero(keep):
            point = bases[i]+offsets[i]*ns[i]
            edges.append(LcdEdge(tuple(point), float(offsets[i]), tuple(ns[i]), 1, float(magnitude[i]), side))
    counts = [sum(edge.side == side for edge in edges) for side in range(4)]
    return WindowModel(tuple(edges), min(counts) >= config.min_points_per_side,
                       sha256(gray.tobytes()).hexdigest(), gray.shape, _polygon(quad), config, reference_image.ndim == 3)


def _motion(parameters):
    angle = parameters[2]
    return np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])


def _fit(points, targets, normals, centre, limit, *, robust=False):
    """Nichtlinearer Punkt-zu-Gerade-Fit; keine tangentialen Pseudo-Messwerte."""
    parameters = np.zeros(3)
    for _ in range(15):
        rotation = _motion(parameters)
        rotated = (points-centre) @ rotation.T
        ns = normals @ rotation.T
        difference = rotated+centre+parameters[:2]-targets
        residual = np.sum(difference*ns, axis=1)
        tangent = np.column_stack((-ns[:, 1], ns[:, 0]))
        derivative = np.sum(difference*tangent, axis=1) + np.sum(np.column_stack((-rotated[:, 1], rotated[:, 0]))*ns, axis=1)
        design = np.column_stack((ns, derivative))
        weights = np.minimum(1, limit / np.maximum(np.abs(residual), 1e-9)) if robust else np.ones(len(points))
        step, _, rank, _ = np.linalg.lstsq(design*np.sqrt(weights[:, None]), -residual*np.sqrt(weights), rcond=None)
        if rank < 3 or not np.isfinite(step).all():
            return None
        parameters += step
        if np.linalg.norm(step) < 1e-7:
            break
    rotation = _motion(parameters)
    residual = np.sum(((points-centre) @ rotation.T+centre+parameters[:2]-targets)*(normals @ rotation.T), axis=1)
    return parameters, residual


class WindowTracker:
    """Jedes Update unabhaengig; Modell an Bild, Quad und Config gebunden."""

    def __init__(self, reference_image, quad, model, config=WindowTrackingConfig()):
        gray = _signal(reference_image)
        normalised = _normalise_quad(quad)
        if (model.config != config or model.reference_shape != gray.shape
                or model.reference_sha256 != sha256(gray.tobytes()).hexdigest()
                or not np.array_equal(model.quad, normalised)):
            raise ValueError("Fenstermodell passt nicht zu Referenzbild, Quad oder Konfiguration")
        self.config, self.model = config, model
        self.quad = np.asarray(quad, float).copy()
        self.normalised_quad = normalised
        self.points = np.asarray([edge.point for edge in model.edges]).reshape(-1, 2)
        self.normals = np.asarray([edge.normal for edge in model.edges]).reshape(-1, 2)
        self.sides = np.array([edge.side for edge in model.edges])

    def update(self, image) -> TrackResult:
        config = self.config

        def reject(reason):
            return TrackResult(None, 0.0, 0.0, 0.0, reason)

        gray = _signal(image)
        if (not self.model.ok or gray.shape != self.model.reference_shape
                or self.model.colour != (image.ndim == 3)):
            return reject("fensterrand_fehlt")
        distances = np.arange(-config.search_radius_px, config.search_radius_px+1)
        offsets, _, _, good = _locate(gray, self.points, self.normals,
                                      distances, self.normalised_quad, config)
        if not self._enough(good):
            return reject("fensterrand_fehlt")
        points, normals = self.points[good], self.normals[good]
        targets = points+offsets[good, None]*normals
        centre = self.quad.mean(axis=0)
        fit = _fit(points, targets, normals, centre, config.residual_limit_px, robust=True)
        if fit is None:
            return reject("fensterrand_unstimmig")
        _, residual = fit
        inliers = np.abs(residual) <= config.residual_limit_px
        for _ in range(4):
            original_inliers = good.copy()
            original_inliers[good] = inliers
            if not self._enough(original_inliers):
                return reject("fensterrand_unstimmig")
            fit = _fit(points[inliers], targets[inliers], normals[inliers], centre, config.residual_limit_px)
            if fit is None:
                return reject("fensterrand_unstimmig")
            parameters, residual = fit
            rotation = _motion(parameters)
            residual_all = np.sum(((points-centre) @ rotation.T+centre+parameters[:2]-targets)*(normals @ rotation.T), axis=1)
            new_inliers = np.abs(residual_all) <= config.residual_limit_px
            if np.array_equal(inliers, new_inliers):
                break
            inliers = new_inliers
        else:
            return reject("fensterrand_unstimmig")
        if np.sqrt(np.mean(residual**2)) > config.max_rms_px:
            return reject("fensterrand_unstimmig")
        predicted = (self.quad-centre) @ rotation.T+centre+parameters[:2]
        for side in range(4):
            keep = inliers & (self.sides[good] != side)
            leave = _fit(points[keep], targets[keep], normals[keep], centre, config.residual_limit_px)
            if leave is None:
                return reject("fensterrand_unstimmig")
            p, _ = leave
            corners = (self.quad-centre) @ _motion(p).T+centre+p[:2]
            if np.linalg.norm(corners-predicted, axis=1).max() > config.max_leave_one_side_out_corner_px:
                return reject("fensterrand_unstimmig")
        shift = float(np.linalg.norm(parameters[:2]))
        angle = float(np.degrees(parameters[2]))
        score = float(inliers.sum()/len(self.points))
        reason = None
        if shift > config.max_shift_px:
            reason = "shift_out_of_bounds"
        elif abs(angle) > config.max_rotation_deg:
            reason = "rotation_out_of_bounds"
        return TrackResult(None if reason else _polygon(predicted), shift, angle, score, reason)

    def _enough(self, keep):
        return all(keep[self.sides == side].sum() >= max(self.config.min_points_per_side,
                   self.config.min_side_share*(self.sides == side).sum()) for side in range(4))
