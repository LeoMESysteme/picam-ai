"""Begrenzte Bedienhilfe bei Trackingverlust, ohne Rueckweg in den Messpfad.

Zeitangaben sind monotone Host-Verarbeitungsdauern, keine Aufnahmelatenzen.
Ein Worker, ein offener Auftrag, ein nativer Ausschnitt um die Quad-Boundingbox
mit 35 Prozent Rand (mindestens 64 Rohpixel), 2000 ORB-Merkmale und hoechstens
500 RANSAC-Schritte begrenzen die Arbeit. Die Referenzmaske skaliert das Quad
um x1.6/y3.0 und spart Zeichen samt aufloesungsabhaengigem Rand aus.
Es gibt keine Bildhistorie und keine Rueckkopplung in die Nachfuehrung.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import cv2
import numpy as np

from dispread.live.frame_tracking import FrameTrackingConfig

LOSS_DELAY_S = 3.0
ESTIMATE_INTERVAL_S = 2.0
UNMATCHED_DELAY_S = 10.0
HINT_KINDS = ('anzeige_bewegt', 'rahmen_verdeckt', 'unbekannt')


def empty_summary():
    return {'count': 0, 'by_kind': dict.fromkeys(HINT_KINDS, 0), 'max_shift_px': None}


class DisplayMotionEstimator:
    """Grobe Bewegung in Rohpixeln, Vorzeichen wie FrameTracker; sonst None.

    Zwoelf Inlier, 60 Prozent Zustimmung, beidseitige Streuung auf beiden
    Quadachsen, kleiner Restfehler und hoechstens 3 Prozent Skalenaenderung
    verhindern eine Bewegungsbehauptung aus einzelnen falschen Merkmalen.
    Diese Diagnose ist kein Nachfuehrungs- oder Genauigkeitsnachweis.
    """

    def __init__(self, reference, quad, *, region_centres=()):
        self._shape = reference.shape[:2]
        quad = np.asarray(quad, dtype=np.float32)
        # Native Pixel erhalten die feine Rahmenstruktur. Derselbe feste Crop
        # in Referenz und aktuellem Bild bewahrt Rohpixel und Drehwinkel.
        margin = max(64, int(np.ceil(np.ptp(quad, axis=0).max() * 0.35)))
        x0, y0 = np.maximum(0, np.floor(quad.min(axis=0) - margin)).astype(int)
        x1, y1 = np.minimum(self._shape[::-1], np.ceil(quad.max(axis=0) + margin)).astype(int)
        self._crop = (slice(y0, y1), slice(x0, x1))
        self._quad = quad - (x0, y0)
        self._regions = np.asarray(region_centres, dtype=np.float32).reshape(-1, 2) - (x0, y0)
        self._reference = self.prepare(reference)
        centre = self._quad.mean(axis=0)
        self._mask = np.zeros(self._reference.shape, np.uint8)
        cv2.fillConvexPoly(self._mask, np.int32((self._quad-centre) * [1.6, 3.0] + centre), 255)
        characters = np.zeros_like(self._mask)
        cv2.fillConvexPoly(characters, np.int32(self._quad), 255)
        # 4% der langen Quadkante: gleicher relativer Zeichenabstand bei
        # anderer Aufnahmeaufloesung und bei vorbeschnittenen Regressionbildern.
        # Die bisherigen Toleranzen galten bei rund 200 px langer Quadkante
        # im 640-px-Bild. Native Aufloesung braucht denselben relativen Massstab.
        self._feature_scale = max(1.0, np.linalg.norm(quad[1]-quad[0]) / 200)
        character_margin = max(1, int(np.ceil(8 * self._feature_scale)))
        characters = cv2.dilate(characters, np.ones((2*character_margin+1, 2*character_margin+1), np.uint8))
        self._mask[characters != 0] = 0
        self._orb = cv2.ORB_create(nfeatures=2000)
        self._features = None

    def prepare(self, image):
        if image is None or image.shape[:2] != self._shape:
            return None
        crop = image[self._crop]
        return crop.copy() if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    def estimate(self, image):
        if image is None or image.shape != self._reference.shape:
            return None
        # Nur der Worker nutzt ORB und den konstant grossen Referenzcache.
        if self._features is None:
            self._features = self._orb.detectAndCompute(self._reference, self._mask)
        reference_keys, reference_desc = self._features
        keys, desc = self._orb.detectAndCompute(image, None)
        if reference_desc is None or desc is None or len(desc) < 12:
            return None
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        pairs = matcher.knnMatch(reference_desc, desc, k=2)
        reverse = matcher.match(desc, reference_desc)
        matches = [a for pair in pairs if len(pair) == 2 for a, b in [pair]
                   if a.distance < 0.75*b.distance and reverse[a.trainIdx].trainIdx == a.queryIdx]
        if len(matches) < 12:
            return None
        src = np.float32([reference_keys[m.queryIdx].pt for m in matches])
        dst = np.float32([keys[m.trainIdx].pt for m in matches])
        matrix, inliers = cv2.estimateAffinePartial2D(
            src, dst, ransacReprojThreshold=2.0*self._feature_scale, maxIters=500, confidence=0.99, refineIters=10)
        if matrix is None or inliers is None or not np.isfinite(matrix).all():
            return None
        good = inliers.ravel() != 0
        if good.sum() < 12 or good.mean() < 0.6 or not 0.97 <= np.linalg.norm(matrix[:, 0]) <= 1.03:
            return None
        src, dst = src[good], dst[good]
        centre = self._quad.mean(axis=0)
        axis = self._quad[1] - self._quad[0]
        axis /= np.linalg.norm(axis)
        axes = np.array([axis, [-axis[1], axis[0]]])
        local = (src-centre) @ axes.T
        extent = np.max(np.abs((self._quad-centre) @ axes.T), axis=0)
        if any(np.count_nonzero(sign*local[:, i] > 0.1*extent[i]) < 2
               for i in range(2) for sign in (-1, 1)):
            return None
        # Nach dem robusten Aehnlichkeitsfit starr nachrechnen: keine Skala melden.
        source_centre, target_centre = src.mean(axis=0), dst.mean(axis=0)
        u, _, vt = np.linalg.svd((src-source_centre).T @ (dst-target_centre))
        rotation = vt.T @ u.T
        if np.linalg.det(rotation) < 0:
            return None
        translation = target_centre - rotation @ source_centre
        residual = np.linalg.norm(src @ rotation.T + translation - dst, axis=1)
        if np.sqrt(np.mean(residual**2)) > 1.5*self._feature_scale or residual.max() > 3*self._feature_scale:
            return None
        # Translation um den Bildursprung ist KEINE Verschiebung des Geraets.
        # Maxima an den tatsaechlich geprueften Orten, in nativen Rohpixeln.
        def displacement(points):
            return float(np.linalg.norm(points @ rotation.T + translation - points, axis=1).max())
        shift = displacement(self._quad)
        region_shift = displacement(self._regions) if len(self._regions) else None
        angle = np.degrees(np.arctan2(rotation[1, 0], rotation[0, 0]))
        return float(shift), float(angle), region_shift


class TrackingAdvice:
    """Thread-sicherer, fluechtiger Hinweis; zaehlt Hinweisketten je Verlust.

    Auch Statuspolls duerfen fertige Ergebnisse abholen, aber niemals Arbeit
    starten. Rueckkehr oder Stop verwerfen Ergebnisse eines alten Verlusts.
    count zaehlt Verlustepisoden mit Hinweis; by_kind deren erstmalige Arten.
    """

    def __init__(self, reference, quad, *, region_centres=()):
        self._estimator = DisplayMotionEstimator(reference, quad, region_centres=region_centres)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='tracking-advice')
        self._lock = Lock()
        self._future = None
        self._generation = 0
        self._job_generation = 0
        self._lost_since = None
        self._last_attempt = None
        self._hint = None
        self._closed = False
        self._episode_kinds = set()
        self._count = 0
        self._by_kind = dict.fromkeys(HINT_KINDS, 0)
        self._max_shift = None

    def _set_hint(self, kind, motion=None):
        if not self._episode_kinds:
            self._count += 1
        if kind not in self._episode_kinds:
            self._by_kind[kind] += 1
            self._episode_kinds.add(kind)
        shift, rotation, region_shift = motion if motion is not None else (None, None, None)
        self._hint = {'kind': kind, 'shift_px': shift, 'rotation_deg': rotation, 'region_shift_px': region_shift}
        if shift is not None:
            self._max_shift = shift if self._max_shift is None else max(shift, self._max_shift)

    def _collect(self, now):
        if self._future is None or not self._future.done():
            return
        future, self._future = self._future, None
        # Auch bei verzoegertem Workerstart keine unmittelbar folgende Schaetzung.
        self._last_attempt = now
        if self._job_generation != self._generation or self._closed or self._lost_since is None:
            return
        failed = False
        try:
            motion = future.result()
        except Exception:  # noqa: BLE001 - Bedienhilfe darf den Messpfad nicht beenden
            motion, failed = None, True
        cfg = FrameTrackingConfig()
        if motion is not None and (max(motion[0], motion[2] or 0) > min(cfg.search_radius_px, cfg.max_shift_px)
                                   or abs(motion[1]) > cfg.max_rotation_deg):
            self._set_hint('anzeige_bewegt', motion)
        elif now - self._lost_since >= UNMATCHED_DELAY_S:
            self._set_hint('unbekannt' if failed or motion is not None else 'rahmen_verdeckt')
        else:
            self._hint = None

    def observe(self, image, *, lost: bool, now: float):
        with self._lock:
            if self._closed:
                return
            if not lost:
                self._generation += 1
                self._lost_since = None
                self._hint = None
                self._episode_kinds.clear()
                self._collect(now)
                return
            if self._lost_since is None:
                self._lost_since = now
            self._collect(now)
            if (now - self._lost_since < LOSS_DELAY_S or self._future is not None
                    or (self._last_attempt is not None and now - self._last_attempt < ESTIMATE_INTERVAL_S)):
                return
            self._last_attempt = now
            self._job_generation = self._generation
            # Nur der native Graucrop wird kopiert; kein Vollbild im Worker.
            small = self._estimator.prepare(image)
            self._future = self._executor.submit(self._estimator.estimate, small)

    def failed(self, now):
        """Session-Grenze faengt jeden observe-Fehler ab und setzt nur Bedienhilfe."""
        with self._lock:
            self._generation += 1
            if self._lost_since is None:
                self._lost_since = now
            self._set_hint('unbekannt')

    def snapshot(self, now):
        with self._lock:
            self._collect(now)
            if self._hint is None:
                return None
            return {**self._hint, 'since_s': max(0.0, now - self._lost_since)}

    def summary(self):
        with self._lock:
            return {'count': self._count, 'by_kind': dict(self._by_kind), 'max_shift_px': self._max_shift}

    def close(self):
        with self._lock:
            self._closed = True
            self._hint = None
            self._executor.shutdown(wait=False, cancel_futures=True)
