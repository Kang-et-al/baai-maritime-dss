"""실험 설정과 모델의 시간 정합성 검증. 모든 수치는 config.json으로 교체 가능."""
from copy import deepcopy
import json
from pathlib import Path
from .risk import validate_risk

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = {
    "schema_version": 2,
    "baseline_id": "busan-hongkong-mean-cvar-v1",
    "scenario_generator": "trend-path-intensity-3x3-v1",
    "risk": {"lambda": 0.5, "alpha": 0.8},
    "time_step_h": 0.25, "rolling_h": 3, "horizon_h": 168,
    "simulation_limit_h": 336, "normal_kn": 12, "fast_kn": 18,
    "start_node": 3181, "goal_node": 642, "arc_distance_nm": 18,
    "fuel_normal_tph": 0.5, "fuel_wait_tph": 0.05,
    "fuel_usd_per_t": 600, "time_usd_per_h": 500,
    "late_usd_per_h": 1000, "due_multiplier": 1.1,
    "wave_thresholds_m": [2, 4, 5], "speed_factors": [1, 2/3, 0.5],
    "weather": {"peak_wave_m": 10, "scale_km": 280, "cutoff_km": 840,
                "radius_scales_with_intensity": True},
    "forecast": {"track_offset_km": 100, "track_ramp_h": 24,
                 "intensity_offset": 0.15, "intensity_ramp_h": 12,
                 "motion_decay_h": 48, "intensity_trend_h": 12,
                 "decay_after_h": 24, "intensity_decay_h": 48,
                 "fallback_heading_xy": [0, 1]},
    "typhoon_waypoints": [
        [0, 132, 23, 0.2], [12, 130, 27, 0.55], [24, 127.8, 31, 1],
        [36, 125, 34, 0.95], [48, 123, 36, 0.55], [60, 121, 37, 0.2],
        [72, 120, 38, 0]],
    "mode": "typhoon",
    "seed": 42,
}


def validate(c):
    if c["schema_version"]!=2:
        raise ValueError("Baseline requires schema_version=2; old experiment results remain read-only references")
    if not isinstance(c["baseline_id"],str) or not c["baseline_id"].strip():
        raise ValueError("baseline_id must be a nonempty string")
    if c["scenario_generator"]!="trend-path-intensity-3x3-v1":
        raise ValueError("Unsupported scenario generator; baseline uses trend-path-intensity-3x3-v1")
    validate_risk(c["risk"])
    positive = ["time_step_h", "rolling_h", "horizon_h", "simulation_limit_h",
                "normal_kn", "fast_kn", "arc_distance_nm", "due_multiplier"]
    for key in positive:
        if c[key] <= 0:
            raise ValueError(f"{key} must be positive")
    for key in ["rolling_h", "horizon_h", "simulation_limit_h"]:
        ratio = c[key] / c["time_step_h"]
        if abs(ratio-round(ratio)) > 1e-8:
            raise ValueError(f"{key} must be a multiple of time_step_h")
    if abs(1/c["time_step_h"]-round(1/c["time_step_h"])) > 1e-8:
        raise ValueError("time_step_h must divide the hourly weather grid")
    if c["horizon_h"] <= c["rolling_h"]:
        raise ValueError("horizon_h must exceed rolling_h")
    if abs(c["rolling_h"]-round(c["rolling_h"])) > 1e-8:
        raise ValueError("rolling_h must be whole hours for hourly forecast anchoring")
    if not (0 < c["normal_kn"] <= c["fast_kn"]):
        raise ValueError("normal_kn must not exceed fast_kn")
    if len(c["speed_factors"]) != 3 or any(not 0 < r <= 1 for r in c["speed_factors"]):
        raise ValueError("three speed factors in (0, 1] are required")
    if len(c["wave_thresholds_m"]) != 3 or not all(a < b for a,b in zip(c["wave_thresholds_m"], c["wave_thresholds_m"][1:])):
        raise ValueError("wave thresholds must increase")
    for r in c["speed_factors"]:
        for v in [c["normal_kn"], c["fast_kn"]]:
            steps = c["arc_distance_nm"]/(r*v*c["time_step_h"])
            if abs(steps-round(steps)) > 1e-7:
                raise ValueError("stage-2 durations must be exact integer time steps; no silent rounding")
    for key in ["fuel_normal_tph", "fuel_wait_tph", "fuel_usd_per_t", "time_usd_per_h", "late_usd_per_h"]:
        if c[key] < 0:
            raise ValueError(f"{key} must be nonnegative")
    if c["mode"] not in ("calm", "typhoon"):
        raise ValueError("mode must be calm or typhoon")
    wp = c["typhoon_waypoints"]
    if len(wp) < 2 or wp[0][0] != 0 or any(a[0] >= b[0] for a,b in zip(wp,wp[1:])):
        raise ValueError("waypoints must start at time 0 and increase")
    if any(len(w) != 4 or not 0 <= w[3] <= 1 for w in wp):
        raise ValueError("waypoints are [hour, longitude, latitude, intensity 0..1]")
    for key,value in c["weather"].items():
        if key == "radius_scales_with_intensity":
            if not isinstance(value,bool):
                raise ValueError("radius_scales_with_intensity must be boolean")
            continue
        if value <= 0:
            raise ValueError("weather scales must be positive")
    for key, value in c["forecast"].items():
        if key != "fallback_heading_xy" and value < 0:
            raise ValueError("forecast parameters must be nonnegative")
    for key in ["track_ramp_h", "intensity_ramp_h", "motion_decay_h", "intensity_trend_h", "intensity_decay_h"]:
        if c["forecast"][key] <= 0:
            raise ValueError(f"{key} must be positive")
    return c


def load_config(path=None):
    c = deepcopy(DEFAULT)
    if path:
        custom = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        unknown = set(custom)-set(c)
        if unknown:
            raise ValueError(f"Unknown settings: {sorted(unknown)}")
        for key, value in custom.items():
            if isinstance(c[key], dict):
                if set(value)-set(c[key]):
                    raise ValueError(f"Unknown {key} settings")
                c[key].update(value)
            else:
                c[key] = value
    return validate(c)
