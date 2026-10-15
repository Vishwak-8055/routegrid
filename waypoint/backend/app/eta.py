"""
ETA estimation.

Baseline is physics: distance / speed, adjusted by a time-of-day congestion
curve and any active disruption's delay_factor. On top of that we fit a
small gradient-boosted regressor against synthetic historical trips to
learn a correction multiplier -- this is deliberately a thin layer (the
point is to demonstrate a pluggable learned-correction pattern real
dispatch systems use, not to oversell a model trained on synthetic data as
production-accurate).

If scikit-learn isn't importable, `predict_multiplier` degrades to the
pure heuristic curve with no learned correction -- the service keeps
running either way.
"""
from __future__ import annotations

import math
import random


def _congestion_curve(hour: float) -> float:
    """Two rush-hour bumps (~9am, ~6pm), light traffic overnight."""
    morning = math.exp(-((hour - 9.0) ** 2) / (2 * 1.6 ** 2))
    evening = math.exp(-((hour - 18.0) ** 2) / (2 * 1.8 ** 2))
    return 1.0 + 0.55 * morning + 0.65 * evening


_model = None
_model_ready = False


def _train_model():
    """Synthetic-data gradient boosting model for the learned correction
    term. Trained once, lazily, at first use -- keeps API startup fast."""
    global _model, _model_ready
    try:
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
    except ImportError:
        _model_ready = True  # tried, unavailable -- don't retry every call
        return

    rng = random.Random(42)
    X, y = [], []
    for _ in range(2000):
        distance_km = rng.uniform(0.5, 40)
        hour = rng.uniform(0, 24)
        stop_index = rng.randint(0, 12)  # position within the route so far
        base_curve = _congestion_curve(hour)
        # ground truth: base curve + small fatigue term for later stops +
        # noise, standing in for effects a real historical dataset would
        # actually encode (driver breaks, cumulative schedule drift, etc.)
        true_multiplier = base_curve * (1 + 0.01 * stop_index) + rng.gauss(0, 0.05)
        X.append([distance_km, hour, stop_index])
        y.append(max(0.6, true_multiplier))

    model = GradientBoostingRegressor(n_estimators=60, max_depth=3, learning_rate=0.1)
    model.fit(np.array(X), np.array(y))
    _model = model
    _model_ready = True


def predict_multiplier(distance_km: float, hour: float, stop_index: int = 0) -> float:
    """Returns a multiplier to apply to the free-flow travel time."""
    global _model_ready
    if not _model_ready:
        _train_model()
    if _model is not None:
        try:
            return float(_model.predict([[distance_km, hour, stop_index]])[0])
        except Exception:
            pass
    return _congestion_curve(hour)


def travel_minutes(
    distance_km: float,
    speed_kmh: float,
    hour: float,
    stop_index: int = 0,
    disruption_factor: float = 1.0,
) -> float:
    if distance_km <= 0:
        return 0.0
    free_flow_min = (distance_km / max(speed_kmh, 1.0)) * 60.0
    multiplier = predict_multiplier(distance_km, hour, stop_index)
    return free_flow_min * multiplier * disruption_factor
