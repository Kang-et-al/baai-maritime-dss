"""Common propulsion/steering policies, scenario-dependent realised motion."""
import math
import time
import tempfile
from pathlib import Path
import numpy as np
from numba import set_num_threads
from .motion import make_curve,wrap
from .drive_motion import simulate,upper_heights,integrate,steering_caps
from .drive_dp import backward_drive,value_at
from .risk import discrete_cost_risk
from .config import ROOT


def solve_dp(lat,forecast,s,c,horizon=None):
    fields=upper_heights(forecast,lat.net.boxes,s)
    p=c['propulsion'];dt=c['time_step_h'];K=round((horizon or c['horizon_h'])/dt)
    V=backward_drive(lat.ptr,lat.dstbase,lat.gid,lat.tid,lat.tables,fields,lat.type_curve_s,lat.type_caps,
                     lat.type_x,lat.type_y,lat.commands,lat.stops,lat.initial_speeds,lat.params,K,dt,forecast.now,c['due_h'],c['late_usd_per_h'],lat.net.goal,
                     (c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*dt,
                     p['wave_table_step_m'],p['transition_limit_h'],p.get('dp_integration_h',p['integration_h']),c['fuel_usd_per_t'],c['time_usd_per_h'])
    return V,fields


def local_candidates(state,lat,forecast,c):
    xy=np.array([state['x_nm'],state['y_nm']]);h0=math.radians(state['heading_deg']);dist=np.linalg.norm(lat.net.xy-xy,axis=1)
    out=[]
    for node in np.flatnonzero((dist>0.5)&(dist<=c['spacing_nm']*1.8)):
        bearing=math.atan2(*(lat.net.xy[node]-xy)[::-1]);hi=int(np.argmin(abs(wrap(lat.net.heading-bearing))))
        h1=bearing if node==lat.net.goal else lat.net.heading[hi]
        curve=make_curve(xy,lat.net.xy[node],h0,h1,c)
        if curve is None or not lat.net.land.clear(curve):continue
        for q in [6.,12.,18.]:
            for stop in [False,True]:
                if node==lat.net.goal and not stop:continue
                trajectories=[]
                for s in range(9):
                    tr,status=simulate(curve,state['speed_kn'],q,stop,state['time_h'],c['propulsion']['transition_limit_h'],c,forecast=forecast,scenario=s)
                    if status!=1:break
                    trajectories.append(tr)
                if len(trajectories)==9:
                    out.append({'node':int(node),'heading':hi,'q':q,'stop':stop,'curve':curve,'trajectories':trajectories,'wait':False})
    # Stationary time advance has no wave ban, heading reset, or free fuel.
    if state['speed_kn']<1e-9:
        node=int(np.argmin(dist));hi=int(np.argmin(abs(wrap(lat.net.heading-h0))))
        if dist[node]<1e-7 and abs(wrap(lat.net.heading[hi]-h0))<1e-7:
            out.append({'node':node,'heading':hi,'q':0.,'stop':True,'trajectories':[], 'wait':True})
    return out


def _future(V,tr,base,now,dt):
    return float(value_at(V,(tr.start_h+tr.duration-now)/dt,base,float(tr.trace[-1,2])))


def recover_continuous(lat,V,fields,node,heading,v,time_abs,now,c):
    """Re-simulate actual continuous states; interpolation never teleports speed/time."""
    result=[];cost=0.;dt=c['time_step_h'];p=c['propulsion'];limit=now+c['horizon_h'];maxsteps=450
    startvalue=float(value_at(V,(time_abs-now)/dt,node*24+heading*4,v))
    for _ in range(maxsteps):
        if node==lat.net.goal:
            late=c['late_usd_per_h']*max(0,time_abs-c['due_h'])
            return {'actions':result,'arrival_h':time_abs,'operating_cost_usd':cost,'late_cost_usd':late,
                    'dp_value_usd':startvalue,'rollout_value_usd':cost+late,'approximation_gap_usd':cost+late-startvalue}
        if time_abs>=limit:return None
        iv=min(2,int(max(0,min(18,v))/6));states=[node*24+heading*4+iv,node*24+heading*4+iv+1]
        best=None;seen=set()
        if v<1e-8:
            future=value_at(V,(time_abs+dt-now)/dt,node*24+heading*4,0.)
            wc=(c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*dt
            if np.isfinite(future):best=(wc+future,None,dt,0.,c['fuel_wait_tph']*dt,None)
        for st in states:
            for a in range(lat.ptr[st],lat.ptr[st+1]):
                gid=int(lat.gid[a]);tid=int(lat.tid[a]);key=(gid,lat.commands[tid],bool(lat.stops[tid]))
                if key in seen:continue
                seen.add(key);curve=lat.net.curves[gid]
                # Same conservative environmental model as future DP; actual speed is not snapped.
                maxH=0.;T=lat.tables[tid,0,1]
                if not np.isfinite(T):continue
                for _j in range(4):
                    h0=max(0,int(math.floor(time_abs-now)));h1=min(len(fields)-1,int(math.floor(time_abs-now+T)))
                    maxH=float(np.max(fields[h0:h1+1,gid]))
                    tr,status=simulate(curve,v,lat.commands[tid],bool(lat.stops[tid]),time_abs,p['transition_limit_h'],c,constant_H=maxH)
                    if status!=1:break
                    if abs(tr.duration-T)<.01:break
                    T=tr.duration
                if status!=1:
                    status,T,vend,F,pos,trace=integrate(curve.s,curve.xy[:,0],curve.xy[:,1],steering_caps(curve,c),v,lat.commands[tid],bool(lat.stops[tid]),time_abs-now,
                                                      p['transition_limit_h'],lat.params,2,0.,np.array([0.,1.]),np.zeros((2,3)),fields[:,gid],p['integration_h'],True)
                    if status!=1:continue
                    from .drive_motion import DriveTrajectory
                    tr=DriveTrajectory(curve,float(lat.commands[tid]),bool(lat.stops[tid]),time_abs,trace,True)
                T=tr.duration;vend=float(tr.trace[-1,2]);F=tr.fuel
                future=value_at(V,(time_abs+T-now)/dt,int(lat.dstbase[a]),vend)
                score=F*c['fuel_usd_per_t']+T*c['time_usd_per_h']+future
                if np.isfinite(score) and (best is None or score<best[0]):best=(score,int(a),T,vend,F,tr)
        if best is None:return None
        score,a,T,vend,F,tr=best
        result.append({'action':-1 if a is None else a,'start_h':time_abs,'end_h':time_abs+T,'from_node':node,
                       'start_speed_kn':v,'end_speed_kn':vend,'fuel_t':F,'q_command':0. if a is None else float(lat.commands[lat.tid[a]]),
                       'stop_at_goal':False if a is None else bool(lat.stops[lat.tid[a]])})
        cost+=F*c['fuel_usd_per_t']+T*c['time_usd_per_h'];time_abs+=T;v=vend
        if a is not None:
            base=int(lat.dstbase[a]);node=base//24;heading=(base%24)//4
    return None


def solve(state,forecast,lat,c,progress=print):
    started=time.perf_counter();set_num_threads(c['propulsion']['threads'])
    candidates=local_candidates(state,lat,forecast,c);local_s=time.perf_counter()-started
    progress(f'Propulsion candidates: {len(candidates)} ({local_s:.2f}s)')
    if not candidates:return {'status':'infeasible','reason':'No local connector policy','solve_seconds':time.perf_counter()-started},None
    L=np.full((len(candidates),9),np.inf);C=L.copy();Q=L.copy();timings=[]
    # Disk-backed scenario value tables let us reconstruct only the selected
    # candidate, instead of every candidate x every scenario. Physics is unchanged.
    cache_root=ROOT/'cache';cache_root.mkdir(exist_ok=True)
    temporary=Path(tempfile.mkdtemp(prefix='drive-values-',dir=cache_root));created=[]
    scenario_refs=[]
    for s in range(9):
        identical=next((j for j in range(s) if np.array_equal(forecast.states[s],forecast.states[j]) or
                        (np.max(forecast.states[s,:,2])==0 and np.max(forecast.states[j,:,2])==0)),None)
        if identical is not None:
            scenario_refs.append(scenario_refs[identical]);C[:,s]=C[:,identical];Q[:,s]=Q[:,identical];L[:,s]=L[:,identical];timings.append(0.)
            progress(f'Scenario {s+1}/9: identical forecast reused');continue
        scenario_refs.append(s)
        ss=time.perf_counter();V,fields=solve_dp(lat,forecast,s,c)
        for i,a in enumerate(candidates):
            base=a['node']*24+a['heading']*4
            if a['wait']:
                T=c['time_step_h'];F=c['fuel_wait_tph']*T;v=0.;end=state['time_h']+T
                future=float(value_at(V,T/c['time_step_h'],base,v))
            else:
                tr=a['trajectories'][s];T=tr.duration;F=tr.fuel;v=float(tr.trace[-1,2]);end=state['time_h']+T
                future=_future(V,tr,base,forecast.now,c['time_step_h'])
            C[i,s]=F*c['fuel_usd_per_t']+T*c['time_usd_per_h'];Q[i,s]=future;L[i,s]=C[i,s]+future
        vp=temporary/f'V{s}.npy';fp=temporary/f'fields{s}.npy'
        np.save(vp,V);np.save(fp,fields);created.extend([vp,fp])
        del V
        timings.append(time.perf_counter()-ss);progress(f'Scenario {s+1}/9: {timings[-1]:.2f}s, elapsed {time.perf_counter()-started:.2f}s')
        if time.perf_counter()-started>c['compute_limit_s']:
            for path in created:path.unlink()
            temporary.rmdir()
            return {'status':'time_limit','solve_seconds':time.perf_counter()-started,'completed_scenarios':s+1},None
    rows=[];best=None
    for i,a in enumerate(candidates):
        risk=discrete_cost_risk(L[i],forecast.p,c['risk']['alpha']);score=None
        if np.isfinite(risk.mean):score=(1-c['risk']['lambda'])*risk.mean+c['risk']['lambda']*risk.cvar
        row={'candidate':i,'node':a['node'],'q_command_kn':a['q'],'stop_at_goal':a['stop'],'wait':a['wait'],
             'scenario_first_usd':[float(v) if np.isfinite(v) else None for v in C[i]],'scenario_future_usd':[float(v) if np.isfinite(v) else None for v in Q[i]],
             'scenario_arrival_speed_kn':[0.]*9 if a['wait'] else [float(tr.trace[-1,2]) for tr in a['trajectories']],
             'scenario_connector_h':[c['time_step_h']]*9 if a['wait'] else [tr.duration for tr in a['trajectories']],
             'objective_usd':score,'mean_total_usd':float(risk.mean) if np.isfinite(risk.mean) else None,'cvar_total_usd':float(risk.cvar) if np.isfinite(risk.cvar) else None}
        rows.append(row)
        if score is not None and (best is None or score<best[0]):best=(score,i)
    chosen_paths=None
    for score,i in sorted((row['objective_usd'],row['candidate']) for row in rows if row['objective_usd'] is not None):
        a=candidates[i];chosen_paths=[]
        for s in range(9):
            ref=scenario_refs[s]
            if s>0 and ref in scenario_refs[:s]:
                chosen_paths.append(chosen_paths[scenario_refs.index(ref)]);continue
            V=np.load(temporary/f'V{ref}.npy',mmap_mode='r');fields=np.load(temporary/f'fields{ref}.npy',mmap_mode='r')
            if a['wait']:v=0.;end=state['time_h']+c['time_step_h']
            else:v=float(a['trajectories'][s].trace[-1,2]);end=state['time_h']+a['trajectories'][s].duration
            route=recover_continuous(lat,V,fields,a['node'],a['heading'],v,end,state['time_h'],c)
            # Windows retains mapped-file locks even after deleting array names
            # when compiled-call wrappers still own references. Close explicitly
            # only after the synchronous rollout has completed all reads.
            V._mmap.close();fields._mmap.close()
            del V,fields
            if route is None:break
            chosen_paths.append(route)
        if len(chosen_paths)==9:best=(score,i);break
        rows[i]['rollout_validation_failed']=True;rows[i]['objective_usd']=None;best=None
    # Delete only exact files created in this unique task-owned cache directory.
    for path in created:
        if path.parent.resolve()!=temporary.resolve():raise RuntimeError('Unexpected cache path')
        path.unlink()
    temporary.rmdir()
    result={'status':'ok' if best else 'infeasible','risk':c['risk'],'solve_seconds':time.perf_counter()-started,'local_seconds':local_s,
            'scenario_seconds':timings,'candidate_count':len(candidates),'feasible_candidate_count':sum(r['objective_usd'] is not None for r in rows),'candidates':rows,
            'observation_max_h':forecast.observation_max_h,'future_value_method':'time/speed bilinear interpolation; continuous-state policy rollout revalidated separately'}
    if best:
        i=best[1];result.update(chosen_candidate=i,chosen=rows[i],scenario_routes=chosen_paths,
                              scenario_first_trajectories=[] if candidates[i]['wait'] else [tr.as_dict() for tr in candidates[i]['trajectories']])
        return result,candidates[i]
    return result,None
