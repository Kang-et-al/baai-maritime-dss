"""Versioned default policy; no change to the physical model or Bellman operator."""
from dataclasses import asdict, dataclass
import numpy as np
from numba import config as numba_config, get_num_threads, set_num_threads
from hex_dss.drive_dp import backward_drive
from experimental_dp.scenario_groups import references

POLICY_ID = 'effective-scenarios-full-or-selective-v1'


@dataclass(frozen=True)
class SolverPolicy:
    policy_id: str
    backend: str
    scenario_references: tuple
    unique_scenarios: tuple
    scenario_workers: int
    state_threads: int

    def as_dict(self):
        return asdict(self)


def select_policy(states, c):
    refs = tuple(references(states))
    unique = tuple(sorted(set(refs)))
    if not unique:
        raise ValueError('At least one forecast scenario is required')
    deterministic = len(unique) == 1
    threads = min(int(c['propulsion']['threads']), numba_config.NUMBA_NUM_THREADS)
    if threads < 1:
        raise ValueError('propulsion.threads must be positive')
    return SolverPolicy(POLICY_ID, 'full' if deterministic else 'selective', refs,
                        unique, 1 if deterministic else min(9, len(unique)),
                        threads if deterministic else 1)


def full_values(lat, fields, c, now, threads):
    """Original backward DP, with per-state counters avoiding concurrent writes."""
    p = c['propulsion']; dt = c['time_step_h']
    counters = np.zeros((lat.nstate, 5), np.int64)
    previous = get_num_threads()
    try:
        set_num_threads(threads)
        V = backward_drive(lat.ptr, lat.dstbase, lat.gid, lat.tid, lat.tables,
            fields, lat.type_curve_s, lat.type_caps, lat.type_x, lat.type_y,
            lat.commands, lat.stops, lat.initial_speeds, lat.params,
            round(c['horizon_h']/dt), dt, now, c['due_h'], c['late_usd_per_h'],
            lat.net.goal, (c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*dt,
            p['wave_table_step_m'], p['transition_limit_h'], p['dp_integration_h'],
            c['fuel_usd_per_t'], c['time_usd_per_h'], counters)
    finally:
        set_num_threads(previous)
    return V, counters.sum(axis=0)


def total_risk(losses, probabilities, risk):
    from hex_dss.risk import discrete_cost_risk, validate_risk
    validate_risk(risk)
    stats = discrete_cost_risk(losses, probabilities, risk['alpha'])
    if not np.isfinite(stats.mean):
        return None, stats
    weight = risk['lambda']
    return float((1-weight)*stats.mean + weight*stats.cvar), stats
