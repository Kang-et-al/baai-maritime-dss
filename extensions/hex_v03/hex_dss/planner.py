"""Common continuous first-stage candidates + scenario-specific lattice recourse."""
import math
import time
from dataclasses import dataclass
import numpy as np
from .motion import make_curve,make_profile,Trajectory,wrap,Curve,Profile
from .weather import band
from .risk import discrete_cost_risk
from .dp import backward,recover,interval_band


@dataclass
class Candidate:
    trajectory: Trajectory
    destination_state: int
    q: int
    predicted_fuel: list
    label: str


class Planner:
    def __init__(self,lattice,c): self.lattice=lattice;self.net=lattice.net;self.c=c

    def candidates(self,state,forecast):
        c=self.c;net=self.net;xy=np.array([state['x_nm'],state['y_nm']]);h0=math.radians(state['heading_deg']);u0=state['speed_kn'];now=state['time_h']
        distance=np.linalg.norm(net.xy-xy,axis=1)
        neighbours=np.flatnonzero((distance>0.5)&(distance<=c['spacing_nm']*1.8))
        out=[];seen=set()
        if abs(u0)<1e-8:
            closest=int(np.argmin(distance));hi=int(np.argmin(np.abs(wrap(net.heading-h0))))
            if distance[closest]<1e-7 and abs(wrap(net.heading[hi]-h0))<1e-7:
                curve=Curve(np.tile(xy,(4,1)),np.array([0.,1.]),np.tile(xy,(2,1)),np.array([0.,0.]),np.zeros(2),np.array([h0,h0]),0.)
                duration=c['time_step_h'];ts=now+np.array([0.,duration])
                if all(np.max(forecast.at(s,xy,ts))<5 for s in range(9)):
                    profile=Profile(np.array([0.,duration]),np.zeros(2),duration,c['fuel_wait_tph']*duration,0)
                    out.append(Candidate(Trajectory(curve,profile,now),closest*24+hi*4,1,[profile.fuel]*9,'stationary wait / heading preserved'))
        for j in neighbours:
            bearing=math.atan2(*(net.xy[j]-xy)[::-1])
            hs=[int(np.argmin(np.abs(wrap(net.heading-bearing))))]
            if j==net.goal: hs=[0]
            for hi in hs:
                h1=bearing if j==net.goal else net.heading[hi]
                curve=make_curve(xy,net.xy[j],h0,h1,c)
                if curve is None or not net.land.clear(curve): continue
                bounds=[forecast.bounds(np.array([curve.box]),s)[:,0] for s in range(9)]
                # Same geometry + same actual-speed profile under all scenarios.
                for vi,u1 in enumerate(c['speeds_kn']):
                    if j==net.goal and vi!=0:continue
                    for cruise in [6.,12.,18.]:
                        for b in range(3):
                            p=make_profile(curve,u0,u1,cruise,b,c)
                            if p is None or p.duration>c['max_replan_h']+1e-8:continue
                            q=round(p.duration/c['time_step_h'])
                            key=(int(j),hi,vi,q,round(p.fuel,7),b)
                            if key in seen:continue
                            valid=True
                            for f in bounds:
                                if np.max(f[:int(math.floor(p.duration))+1])>b:valid=False;break
                            if not valid:continue
                            trajectory=Trajectory(curve,p,now)
                            times=now+np.linspace(0,p.duration,max(10,math.ceil(p.duration*120)+1))
                            points,speeds,_=trajectory.sample(times)
                            fuels=[]
                            for s in range(9):
                                hh=forecast.at(s,points,times);bb=band(hh)
                                factor=np.array([1.,2/3,.5,0.])[bb]
                                if np.any(bb==3):valid=False;break
                                required=speeds/factor
                                rate=np.maximum(c['fuel_wait_tph'],c['fuel_normal_tph']*(required/12)**3)
                                accel=c['accel_extra_t_per_kn2']*np.sum(np.maximum(np.diff(p.speeds**2),0))
                                fuels.append(float(np.trapezoid(rate,times)+accel+c['turn_extra_t_per_rad']*curve.turn))
                            if not valid:continue
                            seen.add(key)
                            out.append(Candidate(trajectory,int(j)*24+hi*4+vi,q,fuels,f'node {j} / {u1:g}kn / {math.degrees(h1)%360:g}deg'))
        # Same terminal state/time => same Q; remove componentwise dominated C.
        kept=[]
        for a in out:
            group=[b for b in kept if b.destination_state==a.destination_state and b.q==a.q]
            ca=np.array(a.predicted_fuel)
            if any(np.all(np.array(b.predicted_fuel)<=ca+1e-10) for b in group):continue
            kept=[b for b in kept if not (b.destination_state==a.destination_state and b.q==a.q and np.all(ca<=np.array(b.predicted_fuel)+1e-10))]
            kept.append(a)
        return kept

    def solve(self,state,forecast,progress=None):
        start=time.perf_counter();c=self.c;lat=self.lattice
        tt=time.perf_counter();candidates=self.candidates(state,forecast);localtime=time.perf_counter()-tt
        if not candidates:
            return {'status':'infeasible','reason':'No physically feasible local connector; no snapping or risk relaxation applied','solve_seconds':time.perf_counter()-start},None
        if progress:progress(f'Local connectors: {len(candidates)} ({localtime:.2f}s)')
        Q=np.full((len(candidates),9),np.inf);paths=[[None]*9 for _ in candidates];scenario_times=[]
        K=round(c['horizon_h']/c['time_step_h']);dt=c['time_step_h']
        nodeboxes=np.column_stack([self.net.xy,self.net.xy])
        for s in range(9):
            ss=time.perf_counter()
            fields=forecast.bounds(self.net.boxes,s);nb=forecast.bounds(nodeboxes,s)
            V=backward(lat.ptr,lat.dst,lat.gid,lat.tid,lat.steps,lat.cost,fields,nb,K,dt,state['time_h'],c['due_h'],c['late_usd_per_h'],self.net.goal,
                       (c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*dt)
            for i,a in enumerate(candidates):
                Q[i,s]=V[a.q,a.destination_state]
                if np.isfinite(Q[i,s]):
                    paths[i][s]=recover(lat,V,fields,nb,a.destination_state,a.q,state['time_h'])
            del V
            scenario_times.append(time.perf_counter()-ss)
            if progress:progress(f'Scenario {s+1}/9: {scenario_times[-1]:.2f}s; total {time.perf_counter()-start:.2f}s')
            if time.perf_counter()-start>c['compute_limit_s']:
                return {'status':'time_limit','solve_seconds':time.perf_counter()-start,'completed_scenarios':s+1},None
        rows=[];best=None
        for i,a in enumerate(candidates):
            C=np.array(a.predicted_fuel)*c['fuel_usd_per_t']+a.trajectory.profile.duration*c['time_usd_per_h']
            losses=C+Q[i]
            stats=discrete_cost_risk(losses,forecast.p,c['risk']['alpha'])
            if not np.isfinite(stats.mean):score=None
            else:score=(1-c['risk']['lambda'])*stats.mean+c['risk']['lambda']*stats.cvar
            row={'candidate':i,'label':a.label,'destination_state':a.destination_state,
                 'duration_h':a.trajectory.profile.duration,'distance_nm':a.trajectory.curve.length,
                 'scenario_first_usd':C.tolist(),'scenario_future_usd':[float(x) if np.isfinite(x) else None for x in Q[i]],
                 'mean_total_usd':float(stats.mean) if np.isfinite(stats.mean) else None,
                 'cvar_total_usd':float(stats.cvar) if np.isfinite(stats.cvar) else None,'objective_usd':score}
            rows.append(row)
            if score is not None and (best is None or score<best[0]):best=(score,i)
        result={'status':'ok' if best else 'infeasible','candidate_count':len(rows),'feasible_candidate_count':sum(r['objective_usd'] is not None for r in rows),
                'candidates':rows,'solve_seconds':time.perf_counter()-start,'local_seconds':localtime,'scenario_seconds':scenario_times,
                'risk':c['risk'],'forecast_observation_max_h':forecast.observation_max_h,
                'first_stage_policy':'identical actual-speed trajectory across scenarios; no scenario-specific first action',
                'future_cost_note':'conservative whole-primitive wave band; scenario-wise perfect-information recourse on finite curved state lattice'}
        if best:
            i=best[1];a=candidates[i]
            result.update(chosen_candidate=i,chosen=rows[i],first_trajectory=a.trajectory.as_dict(),scenario_routes=paths[i],
                          next_event_h=min(state['time_h']+c['max_replan_h'],state['time_h']+a.trajectory.profile.duration))
            return result,a.trajectory
        return result,None
