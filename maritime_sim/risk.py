"""이산 확률분포의 상위 비용 꼬리 CVaR. 경계 시나리오의 확률을 부분 포함한다."""
from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class CostRisk:
    mean: float
    cvar: float
    tail_weights: tuple


def validate_risk(risk):
    if set(risk)!={"lambda","alpha"}:
        raise ValueError("risk must contain exactly lambda and alpha")
    for key in ("lambda","alpha"):
        value=risk[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError(f"risk.{key} must be a finite number")
    if not 0<=risk["lambda"]<=1:
        raise ValueError("risk.lambda must be in [0,1]")
    if not 0<=risk["alpha"]<1:
        raise ValueError("risk.alpha must be in [0,1)")
    return risk


def discrete_cost_risk(costs,probabilities,alpha):
    """CVaR_alpha of losses: min_eta eta + E[(Q-eta)+]/(1-alpha).

    Equivalent weighted average of the worst (1-alpha) probability mass.
    Positive-probability +infinity remains infeasible, including lambda=0 or 1.
    Zero-probability entries have no effect. NaN/-infinity are rejected.
    """
    if isinstance(alpha,bool) or not math.isfinite(alpha) or not 0<=alpha<1:
        raise ValueError("alpha must be in [0,1)")
    q=np.asarray(costs,dtype=float); p=np.asarray(probabilities,dtype=float)
    if q.ndim!=1 or q.size==0 or p.shape!=q.shape:
        raise ValueError("costs and probabilities must be nonempty matching vectors")
    if not np.isfinite(p).all() or np.any(p<0) or not np.isclose(p.sum(),1,rtol=0,atol=1e-12):
        raise ValueError("probabilities must be nonnegative, finite and sum to one")
    if np.isnan(q).any() or np.isneginf(q).any():
        raise ValueError("costs cannot contain NaN or negative infinity")
    active=np.flatnonzero(p>0)
    order=active[np.argsort(-q[active],kind="stable")]
    mass=1-alpha
    before=np.r_[0.,np.cumsum(p[order])[:-1]]
    used=np.minimum(p[order],np.maximum(0.,mass-before))
    weights=np.zeros_like(p); weights[order]=used/mass
    if np.isposinf(q[active]).any():
        return CostRisk(float("inf"),float("inf"),tuple(float(x) for x in weights))
    mean=float(np.dot(p[active],q[active]))
    # Mask zero weights to avoid 0 * infinity for zero-probability entries.
    tail=weights>0
    cvar=float(np.dot(weights[tail],q[tail]))
    return CostRisk(mean,cvar,tuple(float(x) for x in weights))


def candidate_evaluation(first_cost,scenario_costs,probabilities,risk):
    """Keep mean cost and selection objective distinct; never charge C twice."""
    validate_risk(risk)
    stats=discrete_cost_risk(scenario_costs,probabilities,risk["alpha"])
    if not math.isfinite(first_cost) or not math.isfinite(stats.mean):
        remaining=objective=float("inf")
    else:
        weight=risk["lambda"]
        remaining=(1-weight)*stats.mean+weight*stats.cvar
        objective=first_cost+remaining
    finite=lambda v:float(v) if math.isfinite(v) else None
    return {
        "objective_type":"mean_cvar",
        "risk_lambda":risk["lambda"],"cvar_alpha":risk["alpha"],
        "mean_remaining_usd":finite(stats.mean),
        "cvar_remaining_usd":finite(stats.cvar),
        "risk_adjusted_remaining_usd":finite(remaining),
        "expected_total_usd":finite(first_cost+stats.mean),
        "objective_total_usd":finite(objective),
        "cvar_tail_weights":list(stats.tail_weights),
    }
