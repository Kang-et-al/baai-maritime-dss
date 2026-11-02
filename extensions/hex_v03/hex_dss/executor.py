"""Continuous execution; arbitrary interrupts do not snap position, heading or speed."""
import math
import numpy as np
from .weather import heights,band


def execute(state,trajectory,world,c,until=None):
    finish=min(trajectory.start_h+trajectory.profile.duration,state['time_h']+c['max_replan_h'])
    if until is not None:finish=min(finish,float(until))
    if finish<state['time_h']-1e-9:raise ValueError('Cannot execute backwards')
    times=np.unique(np.r_[state['time_h'],np.arange(state['time_h'],finish,1/120),finish,
                         trajectory.start_h+trajectory.profile.times[(trajectory.start_h+trajectory.profile.times>=state['time_h']) & (trajectory.start_h+trajectory.profile.times<=finish)]])
    xy,u,h=trajectory.sample(times)
    if np.linalg.norm(xy[0]-np.array([state['x_nm'],state['y_nm']]))>1e-6 or abs(u[0]-state['speed_kn'])>1e-6:
        raise ValueError('Execution discontinuity')
    waves=heights(xy,world.storm(times),c);bb=band(waves)
    cap=np.array([18.,12.,6.,0.])[bb]
    bad=np.flatnonzero((bb==3)|(u>cap+1e-6))
    status='ok'
    if len(bad):
        # Report actual violation, not a fabricated successful safe execution.
        cut=int(bad[0]);times=times[:cut+1];xy=xy[:cut+1];u=u[:cut+1];h=h[:cut+1];bb=bb[:cut+1];waves=waves[:cut+1]
        status='actual_weather_violation'
    factor=np.array([1.,2/3,.5,np.nan])[bb]
    if np.any(bb==3):rate=np.where(bb==3,c['fuel_wait_tph'],np.maximum(c['fuel_wait_tph'],c['fuel_normal_tph']*(u/np.nan_to_num(factor,nan=1)/12)**3))
    else:rate=np.maximum(c['fuel_wait_tph'],c['fuel_normal_tph']*(u/factor/12)**3)
    fuel=float(np.trapezoid(rate,times)+c['accel_extra_t_per_kn2']*np.sum(np.maximum(np.diff(u*u),0)))
    elapsed=float(times[-1]-times[0]);distance=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum())
    after=dict(state);after.update(time_h=float(times[-1]),x_nm=float(xy[-1,0]),y_nm=float(xy[-1,1]),speed_kn=float(u[-1]),heading_deg=float(np.degrees(h[-1])%360))
    after['fuel_t']=state.get('fuel_t',0)+fuel
    after['operating_cost_usd']=state.get('operating_cost_usd',0)+fuel*c['fuel_usd_per_t']+elapsed*c['time_usd_per_h']
    after['distance_nm']=state.get('distance_nm',0)+distance
    samples=[{'time_h':float(t),'x_nm':float(p[0]),'y_nm':float(p[1]),'speed_kn':float(v),'heading_deg':float(np.degrees(a)%360),'wave_m':float(w)} for t,p,v,a,w in zip(times,xy,u,h,waves)]
    after['history']=state.get('history',[])+samples
    return after,{'status':status,'elapsed_h':elapsed,'fuel_t':fuel,'distance_nm':distance,'samples':samples}

