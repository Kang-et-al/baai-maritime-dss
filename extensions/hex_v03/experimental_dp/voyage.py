"""Fixed 3h rolling, selective values and original continuous rollout/execution."""
import json,time,hashlib,types,concurrent.futures,math,argparse
from pathlib import Path
import numpy as np
from hex_dss.config import ROOT
from hex_dss.runtime import save,fingerprints
from hex_dss.propulsion import build,load_config
from hex_dss.weather import World,Forecast
from hex_dss.drive_motion import upper_heights
from hex_dss.drive_planner import local_candidates,recover_continuous
from hex_dss.rolling_experiment import fixed_execute
from hex_dss.risk import discrete_cost_risk
from experimental_dp.kernel_threaded import Evaluator,prepare
from experimental_dp.scenario_groups import references

_context={}

def scenario_job(s,path):
    path=Path(path);c=_context['config'];state=_context['state'];lat=_context['lat'];f=_context['forecast'];aa=_context['candidates']
    fields=upper_heights(f,lat.net.boxes,s)
    t=time.perf_counter();e=Evaluator(lat,fields,c,state['time_h'],prepared=_context['prepared']);Q=[];C=[]
    for a in aa:
        if a['wait']:T=.25;F=c['fuel_wait_tph']*T;v=0.
        else:tr=a['trajectories'][s];T=tr.duration;F=tr.fuel;v=tr.trace[-1,2]
        val=e.query(T/.25,a['node']*24+a['heading']*4,v);Q.append(None if not np.isfinite(val) else val);C.append(F*600+T*500)
    np.save(path/f'V{s}.npy',e.V);np.save(path/f'F{s}.npy',fields)
    row={'scenario':s,'Q':Q,'C':C,'seconds':time.perf_counter()-t,'counters':e.counters.tolist(),'states':int(e.stats[0])}
    save(path/f'scenario{s}.json',row);print(f'{path.name} scenario {s+1} done {row["seconds"]:.1f}s',flush=True);return row

def recover(e,lat,a,s,state,c):
    # Bind a private function's lookup to on-demand values; original function and
    # module globals are unchanged. All continuous rollout logic stays identical.
    env=dict(recover_continuous.__globals__)
    env['value_at']=lambda V,t,base,v:e.query(t,base,v)
    fn=types.FunctionType(recover_continuous.__code__,env)
    tr=None if a['wait'] else a['trajectories'][s]
    return fn(lat,e.V,e.fields,a['node'],a['heading'],0. if tr is None else tr.trace[-1,2],
              state['time_h']+(.25 if tr is None else tr.duration),state['time_h'],c)

def run(mode,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=True);c=load_config();c['mode']=mode;c['experiment_schedule']='fixed_3h_selective'
    # Track numerical dependencies, excluding unrelated test/report additions.
    identity={'config':c,'core':fingerprints(),'engine':{n:hashlib.sha256((ROOT/'experimental_dp'/n).read_bytes()).hexdigest() for n in ['kernel.py','kernel_threaded.py','scenario_groups.py','voyage.py']}}
    if (out/'identity.json').exists():
        previous=json.loads((out/'identity.json').read_text())
        if identity!=previous:
            # Explicit migration from the immediately preceding process wrapper;
            # kernels differ only in nogil compilation, not numerical statements.
            if previous['core']!=identity['core'] or previous['config']!=c or previous['engine'].get('voyage.py') not in ['189b78bf807c75aeaa6b4811cf2db013a3b17802f424f9a601218404df5a3777','7ecf02e4e7a1e3db4d3955fcaef61d5f5bb7b117556ce7c6a00dba1048b86b3c','f4cd0af6f4c24b2c69d3c87b0bfa4fbf1fa4b9bbff9e526876e5d822b0b32679'] or previous['engine']['kernel.py']!=identity['engine']['kernel.py']:
                raise ValueError('Changed model/engine: new output required')
            migration='identity_before_threading.json' if 'kernel_threaded.py' not in previous['engine'] else 'identity_before_thread_capacity.json'
            if previous['engine'].get('voyage.py')=='f4cd0af6f4c24b2c69d3c87b0bfa4fbf1fa4b9bbff9e526876e5d822b0b32679':migration='identity_before_deduplication.json'
            save(out/migration,previous);save(out/'identity.json',identity)
    else:save(out/'identity.json',identity)
    save(out/'config.json',c);lat=build(c,print);prepared=prepare(lat,c);world=World(c)
    records=[json.loads(p.read_text()) for p in sorted((out/'steps').glob('*.json'))] if (out/'steps').exists() else []
    state=records[-1]['state_after'] if records else dict(c['initial']);started=time.perf_counter()
    for step in range(len(records)+1,113):
        if records and records[-1].get('arrived'):break
        t=time.perf_counter();f=Forecast(world.observe(state['time_h']),c);aa=local_candidates(state,lat,f,c)
        work=out/'work'/f'step_{step:03d}';work.mkdir(parents=True,exist_ok=True);save(work/'input.json',{'state':state,'config':c})
        refs=references(f.states);scenarios=sorted(set(refs));done={}
        for s in scenarios:
            if (work/f'scenario{s}.json').exists():done[s]=json.loads((work/f'scenario{s}.json').read_text())
        _context.update(config=c,state=state,lat=lat,forecast=f,candidates=aa,prepared=prepared)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(9,len(scenarios))) as pool:
            futures={pool.submit(scenario_job,s,str(work)):s for s in scenarios if s not in done}
            for future in concurrent.futures.as_completed(futures):
                s=futures[future];done[s]=future.result();save(out/'status.json',{'status':'solving','step':step,'time_h':state['time_h'],'completed_scenarios':list(done)})
        rows=[]
        for i,a in enumerate(aa):
            C=[done[s]['C'][i] for s in refs];Q=[done[s]['Q'][i] for s in refs];loss=[np.inf if v is None else x+v for x,v in zip(C,Q)]
            risk=discrete_cost_risk(loss,f.p,.8);obj=risk.mean if np.isfinite(risk.mean) else None
            rows.append({'candidate':i,'node':a['node'],'q_command_kn':a['q'],'stop_at_goal':a['stop'],'wait':a['wait'],
              'objective_usd':obj,'mean_total_usd':obj,'cvar_total_usd':risk.cvar if obj is not None else None,'scenario_first_usd':C,'scenario_future_usd':Q,
              'scenario_connector_h':[.25]*9 if a['wait'] else [tr.duration for tr in a['trajectories']]})
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
              'solve_seconds':time.perf_counter()-t,'recovery_seconds':time.perf_counter()-recovery_started,'profiles':list(done.values()),'risk':c['risk'],'scenario_references':refs}
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

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['typhoon','calm']);p.add_argument('--output',required=True);a=p.parse_args();run(a.mode,a.output)
