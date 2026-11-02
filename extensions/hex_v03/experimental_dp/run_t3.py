"""Unlimited t=3h alternative evaluation. Never imports old solution values into solve."""
import argparse,json,time,hashlib,concurrent.futures,os
from pathlib import Path
import numpy as np
from hex_dss.config import ROOT
from hex_dss.runtime import save,metadata,fingerprints
from hex_dss.propulsion import build
from hex_dss.weather import World,Forecast
from hex_dss.drive_motion import upper_heights
from hex_dss.drive_planner import local_candidates
from hex_dss.risk import discrete_cost_risk
from hex_dss.checkpoint import ScenarioStore
from experimental_dp.kernel import Evaluator,prepare

def worker(s,output):
    output=Path(output);manifest=json.loads((output/'identity.json').read_text());c=manifest['config'];state=manifest['state']
    lat=build(c,lambda _:None);forecast=Forecast(World(c).observe(state['time_h']),c)
    candidates=local_candidates(state,lat,forecast,c)
    fields=upper_heights(forecast,lat.net.boxes,s);t=time.perf_counter();prepared=prepare(lat,c);prep_s=time.perf_counter()-t
    e=Evaluator(lat,fields,c,state['time_h'],True,prepared);vals=[];costs=[];t=time.perf_counter()
    for i,a in enumerate(candidates):
        if a['wait']:T=c['time_step_h'];F=c['fuel_wait_tph']*T;v=0.
        else:tr=a['trajectories'][s];T=tr.duration;F=tr.fuel;v=float(tr.trace[-1,2])
        vals.append(e.query(T/c['time_step_h'],a['node']*24+a['heading']*4,v));costs.append(F*c['fuel_usd_per_t']+T*c['time_usd_per_h'])
        save(output/f'progress_s{s:02d}.json',{'scenario':s,'candidates_completed':i+1,'wall_s':time.perf_counter()-t,'counters':e.counters.tolist(),'stats':e.stats.tolist()})
        print(f'S{s+1} candidate {i+1}/{len(candidates)} elapsed {time.perf_counter()-t:.1f}s',flush=True)
    elapsed=time.perf_counter()-t
    profile={'scenario':s,'dp_seconds':elapsed,'prepare_seconds':prep_s,'transfer_calls':int(e.counters[0]),'table_returns':int(e.counters[1]),
             'direct_integrations':int(e.counters[2]),'integration_iterations':int(e.counters[3]),'stationary_event_skips':int(e.counters[4]),
             'states_solved':int(e.stats[0]),'memo_hits':int(e.stats[1]),'pre_transfer_prunes':int(e.stats[2]),'post_transfer_prunes':int(e.stats[3]),
             'certification':'exact resolved roots; conservative pruning margin 1e-7 USD; epsilon not spent'}
    store=ScenarioStore(output/'checkpoint',manifest);t=time.perf_counter();store.put(s,e.V,fields,profile);profile['checkpoint_seconds']=time.perf_counter()-t
    result={'scenario':s,'future':[None if not np.isfinite(v) else v for v in vals],'first':costs,'profile':profile}
    save(output/f'scenario_{s:02d}.json',result);return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'outputs/rolling_typhoon_final';state=json.loads((source/'steps/step_002.json').read_text())['state_before'];c=json.loads((source/'config.json').read_text())
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'experimental_dp').glob('*.py')}
    identity={'config':c,'state':state,'core':fingerprints(),'engine':hashes,'epsilon_usd':.01,'engine_id':'demand-exact-bounded-v1'}
    if (out/'identity.json').exists():
        if json.loads((out/'identity.json').read_text())!=identity:raise ValueError('Output identity mismatch')
    else:save(out/'identity.json',identity)
    started=time.perf_counter();save(out/'run_status.json',{'status':'running','time_limit':None})
    lat=build(c,lambda msg:print(msg,flush=True));f=Forecast(World(c).observe(3.),c);aa=local_candidates(state,lat,f,c)
    save(out/'candidate_definitions.json',[{'candidate':i,'node':a['node'],'q':a['q'],'stop':a['stop'],'wait':a['wait']} for i,a in enumerate(aa)])
    done={s:json.loads((out/f'scenario_{s:02d}.json').read_text()) for s in range(9) if (out/f'scenario_{s:02d}.json').exists()}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        tasks={pool.submit(worker,s,str(out)):s for s in range(9) if s not in done}
        for task in concurrent.futures.as_completed(tasks):
            s=tasks[task];done[s]=task.result();print(f'Scenario {s+1} completed',flush=True)
            save(out/'run_status.json',{'status':'running','completed':sorted(done),'wall_seconds':time.perf_counter()-started})
    rows=[]
    for i,a in enumerate(aa):
        first=np.array([done[s]['first'][i] for s in range(9)]);future=np.array([np.inf if done[s]['future'][i] is None else done[s]['future'][i] for s in range(9)])
        risk=discrete_cost_risk(first+future,f.p,c['risk']['alpha']);obj=(1-c['risk']['lambda'])*risk.mean+c['risk']['lambda']*risk.cvar if np.isfinite(risk.mean) else None
        rows.append({'candidate':i,'node':a['node'],'q':a['q'],'objective_usd':obj,'future':[None if not np.isfinite(v) else float(v) for v in future]})
    best=min((r for r in rows if r['objective_usd'] is not None),key=lambda r:(r['objective_usd'],r['candidate']))
    # Comparison happens ONLY AFTER all new values have been computed.
    old=json.loads((ROOT/'outputs/typhoon_t3_unlimited_profiled/result.json').read_text());errors=[];feas=True
    for r,b in zip(rows,old['candidates']):
        for x,y in zip(r['future'],b['scenario_future_usd']):
            if (x is None)!=(y is None):feas=False
            if x is not None and y is not None:errors.append(abs(x-y))
    result={'status':'ok','chosen':best,'candidates':rows,'profiles':[done[s]['profile'] for s in range(9)],'wall_seconds':time.perf_counter()-started,
            'workers':args.workers,'epsilon_usd':.01,'max_future_difference_usd':max(errors),'feasibility_matches':feas,
            'chosen_matches':best['candidate']==old['chosen_candidate'],'gap_usd':0.,'continuous_route_recovery':'not rerun; DP decision only; no ship execution',
            'model_unchanged':True,'time_limit':None}
    save(out/'result.json',result);save(out/'manifest.json',metadata());save(out/'run_status.json',{'status':'ok','completed':list(range(9))})
    print(json.dumps({k:v for k,v in result.items() if k not in ['candidates','profiles']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
