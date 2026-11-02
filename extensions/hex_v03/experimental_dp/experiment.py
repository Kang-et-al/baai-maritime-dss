"""Approved default solver dispatch; fixed 3h execution, resumable one-step/full voyage."""
import json,time,hashlib,types,concurrent.futures,math,argparse
from pathlib import Path
import numpy as np
from hex_dss.config import ROOT
from hex_dss.runtime import save,fingerprints,metadata
from hex_dss.propulsion import build,load_config
from hex_dss.weather import World,Forecast
from hex_dss.drive_motion import upper_heights
from hex_dss.drive_planner import local_candidates,recover_continuous
from hex_dss.rolling_experiment import fixed_execute
from experimental_dp.kernel_threaded import Evaluator,prepare
from experimental_dp.solver_policy import select_policy, full_values, total_risk, POLICY_ID
from hex_dss.drive_dp import value_at

_context={}

def scenario_job(s,path):
    path=Path(path);c=_context['config'];state=_context['state'];lat=_context['lat'];f=_context['forecast'];aa=_context['candidates']
    fields=upper_heights(f,lat.net.boxes,s)
    t=time.perf_counter();policy=_context['policy'];e=None;Q=[];C=[]
    if policy.backend=='full':
        V,counters=full_values(lat,fields,c,state['time_h'],policy.state_threads)
        query=lambda ti,base,v:float(value_at(V,ti,base,v))
        states_evaluated=(len(V)-1)*(lat.nstate-24)
    else:
        e=Evaluator(lat,fields,c,state['time_h'],prepared=_context['prepared'])
        query=e.query
    for a in aa:
        if a['wait']:T=c['time_step_h'];F=c['fuel_wait_tph']*T;v=0.
        else:tr=a['trajectories'][s];T=tr.duration;F=tr.fuel;v=tr.trace[-1,2]
        val=query(T/c['time_step_h'],a['node']*24+a['heading']*4,v);Q.append(None if not np.isfinite(val) else val);C.append(F*c['fuel_usd_per_t']+T*c['time_usd_per_h'])
    if e is not None:V=e.V;counters=e.counters;states_evaluated=int(e.stats[0])
    np.save(path/f'V{s}.npy',V);np.save(path/f'F{s}.npy',fields)
    row={'scenario':s,'Q':Q,'C':C,'seconds':time.perf_counter()-t,'counters':counters.tolist(),'states':int(states_evaluated),'solver_policy':policy.as_dict()}
    save(path/f'scenario{s}.json',row);print(f'{path.name} scenario {s+1} done {row["seconds"]:.1f}s',flush=True);return row

def recover(e,lat,a,s,state,c):
    # Bind a private function's lookup to on-demand values; original function and
    # module globals are unchanged. All continuous rollout logic stays identical.
    env=dict(recover_continuous.__globals__)
    env['value_at']=lambda V,t,base,v:e.query(t,base,v)
    fn=types.FunctionType(recover_continuous.__code__,env)
    tr=None if a['wait'] else a['trajectories'][s]
    return fn(lat,e.V,e.fields,a['node'],a['heading'],0. if tr is None else tr.trace[-1,2],
              state['time_h']+(c['time_step_h'] if tr is None else tr.duration),state['time_h'],c)

def run(mode,output,steps=1,config=None,initial_state=None,resume=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=True);c=load_config(config);c['mode']=mode;c['experiment_schedule']='fixed_3h_auto_v1'
    if steps is not None and steps<1:raise ValueError('steps must be positive')
    if not resume and any(out.iterdir()):raise ValueError('Use a NEW output folder or explicit --resume')
    if resume and not (out/'identity.json').exists():raise ValueError('No matching run to resume')
    if resume:initial_state=json.loads((out/'initial_state.json').read_text())
    initial_state=dict(c['initial']) if initial_state is None else dict(initial_state)
    # Track numerical dependencies, excluding unrelated test/report additions.
    identity={'config':c,'core':fingerprints(),'engine':{n:hashlib.sha256((ROOT/'experimental_dp'/n).read_bytes()).hexdigest() for n in ['kernel.py','kernel_threaded.py','scenario_groups.py','voyage.py']}}
    identity['policy_id']=POLICY_ID
    identity['initial_state']=initial_state
    identity['engine'].update({n:hashlib.sha256((ROOT/'experimental_dp'/n).read_bytes()).hexdigest() for n in ['experiment.py','solver_policy.py']})
    if (out/'identity.json').exists():
        if json.loads((out/'identity.json').read_text())!=identity:
            raise ValueError('Changed code/config/data/policy: use a new output folder')
    else:save(out/'identity.json',identity)
    save(out/'config.json',c)
    save(out/'initial_state.json',initial_state)
    session_started=time.perf_counter()
    session_id=str(time.time_ns())
    session_meta=metadata();session_meta.update(policy_id=POLICY_ID,identity=identity)
    save(out/'sessions'/f'{session_id}.json',session_meta)
    lat=build(c,print);prepared=prepare(lat,c);world=World(c)
    records=[json.loads(p.read_text()) for p in sorted((out/'steps').glob('*.json'))] if (out/'steps').exists() else []
    state=records[-1]['state_after'] if records else initial_state;started=time.perf_counter()
    for step in range(len(records)+1,len(records)+(steps if steps is not None else 112)+1):
        if state['time_h']>=c['simulation_limit_h']:break
        if records and records[-1].get('arrived'):break
        t=time.perf_counter();f=Forecast(world.observe(state['time_h']),c);aa=local_candidates(state,lat,f,c)
        work=out/'work'/f'step_{step:03d}';work.mkdir(parents=True,exist_ok=True);save(work/'input.json',{'state':state,'config':c})
        policy=select_policy(f.states,c);refs=list(policy.scenario_references);scenarios=list(policy.unique_scenarios);done={}
        save(work/'solver_policy.json',policy.as_dict())
        for s in scenarios:
            if (work/f'scenario{s}.json').exists():done[s]=json.loads((work/f'scenario{s}.json').read_text())
        _context.update(config=c,state=state,lat=lat,forecast=f,candidates=aa,prepared=prepared,policy=policy)
        if policy.backend=='full':
            for s in scenarios:
                if s not in done:done[s]=scenario_job(s,str(work))
        with concurrent.futures.ThreadPoolExecutor(max_workers=policy.scenario_workers) as pool:
            futures={pool.submit(scenario_job,s,str(work)):s for s in scenarios if s not in done}
            for future in concurrent.futures.as_completed(futures):
                s=futures[future];done[s]=future.result();save(out/'status.json',{'status':'solving','step':step,'time_h':state['time_h'],'completed_scenarios':list(done)})
        rows=[]
        for i,a in enumerate(aa):
            C=[done[s]['C'][i] for s in refs];Q=[done[s]['Q'][i] for s in refs];loss=[np.inf if v is None else x+v for x,v in zip(C,Q)]
            obj,risk=total_risk(loss,f.p,c['risk'])
            rows.append({'candidate':i,'node':a['node'],'q_command_kn':a['q'],'stop_at_goal':a['stop'],'wait':a['wait'],
              'objective_usd':obj,'mean_total_usd':float(risk.mean) if obj is not None else None,'cvar_total_usd':risk.cvar if obj is not None else None,'scenario_first_usd':C,'scenario_future_usd':Q,
              'scenario_connector_h':[c['time_step_h']]*len(refs) if a['wait'] else [tr.duration for tr in a['trajectories']]})
        chosen=None;routes=None;recovery_started=time.perf_counter()
        for row in sorted((r for r in rows if r['objective_usd'] is not None),key=lambda r:(r['objective_usd'],r['candidate'])):
            a=aa[row['candidate']];rr=[]
            for s in scenarios:
                e=Evaluator(lat,np.load(work/f'F{s}.npy'),c,state['time_h'],prepared=prepared);e.V=np.load(work/f'V{s}.npy')
                route=recover(e,lat,a,s,state,c)
                del e
                if route is None:break
                rr.append(route)
            if len(rr)==len(scenarios):chosen=a;routes=[rr[scenarios.index(ref)] for ref in refs];selected=row;break
            row['rollout_failed']=True
        if chosen is None:
            save(out/'status.json',{'status':'infeasible_or_rollout_failed','step':step,'time_h':state['time_h']});raise RuntimeError('No continuously recoverable decision')
        plan={'status':'ok','chosen':selected,'chosen_candidate':selected['candidate'],'candidates':rows,'scenario_routes':routes,
              'solve_seconds':time.perf_counter()-t,'recovery_seconds':time.perf_counter()-recovery_started,'profiles':list(done.values()),'risk':c['risk'],'scenario_references':refs,'solver_policy':policy.as_dict()}
        after,execution=fixed_execute(chosen,plan,state,world,c,lat)
        arrived=math.dist([after['x_nm'],after['y_nm']],c['goal_nm'])<1e-5 and after['speed_kn']<1e-3
        record={'step':step,'state_before':state,'state_after':after,'plan':plan,'execution':execution,'arrived':arrived,
                'forecast':{'states':f.states.tolist(),'anchor_times':f.anchor_times.tolist(),'observation_max_h':f.observation_max_h}}
        save(out/'steps'/f'step_{step:03d}.json',record);records.append(record);state=after
        save(out/'state.json',state);save(out/'status.json',{'status':'arrived' if arrived else 'running','step':step,'time_h':state['time_h'],'elapsed_session_s':time.perf_counter()-started})
        from experimental_dp.voyage_report import render
        render(out,records,lat,c)
        # Only temporary numerical files produced by this new run. Keep JSON
        # profiles and completed step records; never touch pre-existing runs.
        for p in work.glob('*.npy'):
            if p.resolve().parent!=work.resolve():raise ValueError('Unsafe temporary path')
            p.unlink()
        print(f'{mode} STEP {step} t={state["time_h"]:.3f} decision={plan["solve_seconds"]:.1f}s arrived={arrived}',flush=True)
        if arrived:break
    session_meta.update(elapsed_session_s=time.perf_counter()-session_started,
                        completed_steps=len(records),latest_state_h=state['time_h'])
    save(out/'sessions'/f'{session_id}.json',session_meta)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['typhoon','calm'])
    p.add_argument('--output',required=True)
    p.add_argument('--config')
    p.add_argument('--state',help='JSON state snapshot, arbitrary time/position/speed/heading')
    p.add_argument('--resume',action='store_true')
    group=p.add_mutually_exclusive_group()
    group.add_argument('--steps',type=int,default=1)
    group.add_argument('--complete',action='store_true')
    a=p.parse_args()
    state=json.loads(Path(a.state).read_text(encoding='utf-8-sig')) if a.state else None
    if a.resume:
        if a.config or a.state:p.error('resume uses the saved config/state')
        a.config=str(Path(a.output)/'config.json')
    run(a.mode,a.output,None if a.complete else a.steps,a.config,state,a.resume)

if __name__=='__main__':main()
