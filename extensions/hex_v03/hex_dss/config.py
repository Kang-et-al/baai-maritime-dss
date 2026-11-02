import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path=None):
    c = json.loads(Path(path or ROOT/'configs/hex_mean.json').read_text(encoding='utf-8-sig'))
    assert c['risk']['lambda'] >= 0 and c['risk']['lambda'] <= 1
    assert 0 <= c['risk']['alpha'] < 1
    for k in ['time_step_h','max_replan_h','accel_kn_per_h','decel_kn_per_h','min_turn_radius_nm']:
        if not math.isfinite(c[k]) or c[k] <= 0:
            raise ValueError(k)
    if c['emergency_policy'] != 'strict_constraints_report_infeasible':
        raise ValueError('Risk relaxation requires explicit new policy and tests')
    return c
