"""Fixed 3h execution of the issued common policy; no hidden interim optimisation."""
import json,math,time
from pathlib import Path
import numpy as np
from .propulsion import load_config,build,execute_candidate
from .weather import World,Forecast
from .drive_planner import solve
from .drive_motion import simulate
from .motion import make_curve
from .runtime import save,metadata
from .drive_report import render


def fixed_execute(candidate,plan,state,world,c,lat):
    end=state['time_h']+3;start=dict(state);parts=[];current=dict(candidate)
    continuation=iter(plan['scenario_routes'][4]['actions'])
    while state['time_h']<end-1e-8:
        local=dict(c);local['max_replan_h']=end-state['time_h']
        if current['wait']:
            local['time_step_h']=end-state['time_h']
        state,ex=execute_candidate(current,state,world,local);parts.append(ex)
        if math.dist([state['x_nm'],state['y_nm']],c['goal_nm'])<1e-5 and state['speed_kn']<1e-3:break
        if state['time_h']>=end-1e-8:break
        route=next(continuation,None)
        if route is None:raise RuntimeError('Issued continuation exhausted before update')
        if route['action']<0:
            current={'wait':True};continue
        action=route['action'];base=int(lat.dstbase[action]);target=lat.net.xy[base//24]
        heading=lat.net.curves[lat.gid[action]].heading[-1]
        curve=make_curve([state['x_nm'],state['y_nm']],target,math.radians(state['heading_deg']),heading,c)
        if curve is None or not lat.net.land.clear(curve):raise RuntimeError('Actual continuation is geometrically infeasible')
        current={'wait':False,'curve':curve,'q':route['q_command'],'stop':route['stop_at_goal']}
    samples=sum((p['samples'] for p in parts),[])
    result={'status':'fixed_3h_policy','duration_h':state['time_h']-start['time_h'],
            'fuel_t':sum(p['fuel_t'] for p in parts),'distance_nm':sum(p['distance_nm'] for p in parts),
            'cost_usd':sum(p['cost_usd'] for p in parts),'samples':samples,'trajectory':parts[0]['trajectory'],
            'parts':parts,'policy_note':'first connector then central forecast continuation fixed at issue time; no true-future-based choice'}
    return state,result


def run(mode,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):raise ValueError('Use new output directory')
    c=load_config();c['mode']=mode;c['experiment_schedule']='fixed_3h'
    save(output/'config.json',c);lat=build(c,lambda m:print(m,flush=True));world=World(c);state=dict(c['initial']);records=[];start=time.perf_counter()
    save(output/'manifest.json',dict(metadata(),status='running',schedule='fixed_3h'))
    for step in range(1,113):
        forecast=Forecast(world.observe(state['time_h']),c)
        plan,a=solve(state,forecast,lat,c,lambda m:print(m,flush=True))
        r={'step':step,'state_before':state,'plan':plan,'forecast':{'states':forecast.states.tolist(),'anchor_times':forecast.anchor_times.tolist(),'observation_max_h':forecast.observation_max_h}}
        if a is not None:
            try:after,execution=fixed_execute(a,plan,state,world,c,lat)
            except Exception as exc:
                r['execution_error']=str(exc);save(output/'steps'/f'step_{step:03d}.json',r);raise
            r.update(state_after=after,execution=execution);state=after
            r['arrived']=math.dist([state['x_nm'],state['y_nm']],c['goal_nm'])<1e-5 and state['speed_kn']<1e-3
        records.append(r);save(output/'steps'/f'step_{step:03d}.json',r);save(output/'state.json',state)
        # Plot represents first issued connector; full 3h actual trace is also saved.
        render(output,records,lat,c)
        print(f"ROLLING {mode} STEP {step} t={state['time_h']:.3f} cost={state.get('operating_cost_usd',0):.2f} status={plan['status']}",flush=True)
        save(output/'manifest.json',dict(metadata(),status='arrived' if r.get('arrived') else plan['status'],steps=step,wall_seconds=time.perf_counter()-start,solve_seconds=[q['plan']['solve_seconds'] for q in records]))
        if a is None or r.get('arrived'):break


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['typhoon','calm']);p.add_argument('--output',required=True);a=p.parse_args();run(a.mode,a.output)
