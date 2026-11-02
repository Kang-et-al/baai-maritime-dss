"""One decision, persistent scenarios, measured kernels; model config unchanged."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from numba import set_num_threads
from .runtime import save,metadata,fingerprints
from .propulsion import build
from .weather import World,Forecast
from .drive_motion import upper_heights
from .drive_dp import backward_drive,value_at
from .drive_planner import local_candidates,_future,recover_continuous
from .risk import discrete_cost_risk
from .checkpoint import ScenarioStore


def run(output,source,max_new=None):
    output=Path(output);source=Path(source)
    old=json.loads((source/'steps/step_002.json').read_text(encoding='utf-8'))
    state=old['state_before'];c=json.loads((source/'config.json').read_text(encoding='utf-8'))
    assert state['time_h']==3.0
    forecast=Forecast(World(c).observe(state['time_h']),c)
    identity={'state':state,'config':c,'code_data':fingerprints(),
              'forecast_sha256':hashlib.sha256(forecast.states.tobytes()+forecast.anchor_times.tobytes()).hexdigest(),
              'profile':True,'input_source':str(source.resolve())}
    store=ScenarioStore(output/'checkpoint',identity)
    started=time.perf_counter();events=[]
    session_path=output/'sessions.json'
    sessions=json.loads(session_path.read_text()) if session_path.exists() else []
    def log(msg):print(msg,flush=True)
    save(output/'config.json',c);save(output/'input_state.json',state)
    save(output/'run_status.json',{'status':'running','time_limit':'disabled for this single decision only','checkpoint_key':store.key})
    tb=time.perf_counter();lat=build(c,log);build_s=time.perf_counter()-tb
    set_num_threads(c['propulsion']['threads']);tb=time.perf_counter();candidates=local_candidates(state,lat,forecast,c);local_s=time.perf_counter()-tb
    log(f'Exact saved t=3h state; candidates {len(candidates)}; time limit DISABLED')
    save(output/'scenario_progress.json',{'candidate_count':len(candidates),'completed':[s for s in range(9) if store.completed(s)]})
    C=np.full((len(candidates),9),np.inf);Q=C.copy();profiles=[];new=0
    for s in range(9):
        if store.completed(s):
            tb=time.perf_counter();V,fields,profile=store.load(s);reload_s=time.perf_counter()-tb
            log(f'Scenario {s+1}/9 resumed; no DP rerun ({reload_s:.2f}s verification/load)')
            profile=dict(profile,resumed=True,reload_seconds=reload_s)
        else:
            if max_new is not None and new>=max_new:
                result={'status':'checkpoint_pause','completed_scenarios':s,'wall_seconds':time.perf_counter()-started,'reason':'intentional resume validation'}
                sessions.append({'status':'paused','wall_seconds':result['wall_seconds'],'build_seconds':build_s,'local_seconds':local_s,'new_scenarios':new})
                save(session_path,sessions)
                save(output/'run_status.json',result);log(json.dumps(result));return
            tb=time.perf_counter();fields=upper_heights(forecast,lat.net.boxes,s);field_s=time.perf_counter()-tb
            counters=np.zeros((lat.nstate,5),dtype=np.int64);p=c['propulsion'];dt=c['time_step_h'];K=round(c['horizon_h']/dt)
            log(f'Scenario {s+1}/9 DP started; integration {p["dp_integration_h"]*60:g}min unchanged')
            tb=time.perf_counter()
            V=backward_drive(lat.ptr,lat.dstbase,lat.gid,lat.tid,lat.tables,fields,lat.type_curve_s,lat.type_caps,lat.type_x,lat.type_y,
                             lat.commands,lat.stops,lat.initial_speeds,lat.params,K,dt,state['time_h'],c['due_h'],c['late_usd_per_h'],lat.net.goal,
                             (c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*dt,p['wave_table_step_m'],p['transition_limit_h'],p['dp_integration_h'],
                             c['fuel_usd_per_t'],c['time_usd_per_h'],counters)
            dp_s=time.perf_counter()-tb;cnt=counters.sum(axis=0)
            profile={'scenario':s,'field_seconds':field_s,'dp_seconds':dp_s,'transfer_calls':int(cnt[0]),'table_returns':int(cnt[1]),
                     'direct_integrations':int(cnt[2]),'integration_iterations':int(cnt[3]),'stationary_event_skips':int(cnt[4]),'resumed':False}
            tb=time.perf_counter();store.put(s,V,fields,profile);write_s=time.perf_counter()-tb
            profile['checkpoint_write_seconds']=write_s
            # Metrics update doesn't alter the immutable numerical array files.
            marker=json.loads(store.marker(s).read_text());marker['metrics']=profile;save(store.marker(s),marker)
            new+=1;log(f'Scenario {s+1}/9 DP {dp_s:.2f}s, direct integrations {cnt[2]:,}, checkpoint saved')
        tb=time.perf_counter()
        for i,a in enumerate(candidates):
            base=a['node']*24+a['heading']*4
            if a['wait']:T=c['time_step_h'];F=c['fuel_wait_tph']*T;future=float(value_at(V,T/c['time_step_h'],base,0.))
            else:
                tr=a['trajectories'][s];T=tr.duration;F=tr.fuel;future=_future(V,tr,base,forecast.now,c['time_step_h'])
            C[i,s]=F*c['fuel_usd_per_t']+T*c['time_usd_per_h'];Q[i,s]=future
        profile['candidate_lookup_seconds']=time.perf_counter()-tb
        save(output/f'candidate_values_s{s:02d}.json',{'checkpoint_key':store.key,'scenario':s,
             'first_costs_usd':C[:,s].tolist(),'future_costs_usd':[float(v) if np.isfinite(v) else None for v in Q[:,s]]})
        store.close(V,fields);del V,fields
        profiles.append(profile);save(output/'profiling.json',profiles)
        save(output/'scenario_progress.json',{'candidate_count':len(candidates),'completed':[j for j in range(9) if store.completed(j)]})
    tb=time.perf_counter();rows=[]
    for i,a in enumerate(candidates):
        stats=discrete_cost_risk(C[i]+Q[i],forecast.p,c['risk']['alpha'])
        score=None if not np.isfinite(stats.mean) else (1-c['risk']['lambda'])*stats.mean+c['risk']['lambda']*stats.cvar
        rows.append({'candidate':i,'node':a['node'],'q_command_kn':a['q'],'stop_at_goal':a['stop'],'wait':a['wait'],
                     'scenario_first_usd':C[i].tolist(),'scenario_future_usd':[float(v) if np.isfinite(v) else None for v in Q[i]],
                     'objective_usd':score,'mean_total_usd':None if score is None else stats.mean,'cvar_total_usd':None if score is None else stats.cvar,
                     'scenario_connector_h':[c['time_step_h']]*9 if a['wait'] else [t.duration for t in a['trajectories']]})
    risk_s=time.perf_counter()-tb;tb=time.perf_counter();best=None;paths=None
    for score,i in sorted((r['objective_usd'],r['candidate']) for r in rows if r['objective_usd'] is not None):
        a=candidates[i];paths=[]
        for s in range(9):
            V,fields,_=store.load(s)
            v=0. if a['wait'] else float(a['trajectories'][s].trace[-1,2]);end=state['time_h']+(c['time_step_h'] if a['wait'] else a['trajectories'][s].duration)
            route=recover_continuous(lat,V,fields,a['node'],a['heading'],v,end,state['time_h'],c)
            store.close(V,fields);del V,fields
            if route is None:break
            paths.append(route)
        if len(paths)==9:best=i;break
        rows[i]['rollout_failed']=True
    recovery_s=time.perf_counter()-tb
    result={'status':'ok' if best is not None else 'infeasible','requested_state':state,'candidate_count':len(rows),
            'feasible_candidate_count':sum(r['objective_usd'] is not None for r in rows),'candidates':rows,'profiles':profiles,
            'build_seconds':build_s,'local_seconds':local_s,'risk_seconds':risk_s,'recovery_seconds':recovery_s,
            'current_invocation_wall_seconds':time.perf_counter()-started,'total_unique_dp_seconds':sum(p['dp_seconds'] for p in profiles),
            'total_unique_checkpoint_write_seconds':sum(p.get('checkpoint_write_seconds',0) for p in profiles),
            'time_limit':'disabled','model_config_unchanged':True,'risk':c['risk'],'checkpoint_key':store.key,
            'counter_note':'exact per-state/thread-safe work counts; no per-call wall timer, profiling overhead included'}
    if best is not None:
        result.update(chosen_candidate=best,chosen=rows[best],scenario_routes=paths,
                      scenario_first_trajectories=[] if candidates[best]['wait'] else [t.as_dict() for t in candidates[best]['trajectories']])
    save(output/'result.json',result);save(output/'run_status.json',{'status':result['status'],'completed_scenarios':9})
    sessions.append({'status':result['status'],'wall_seconds':result['current_invocation_wall_seconds'],'build_seconds':build_s,'local_seconds':local_s,'new_scenarios':new})
    save(session_path,sessions)
    save(output/'manifest.json',dict(metadata(),checkpoint_key=store.key,operation='single t=3h decision; no voyage execution'))
    log(json.dumps({k:result[k] for k in ['status','candidate_count','feasible_candidate_count','total_unique_dp_seconds','recovery_seconds','current_invocation_wall_seconds']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--source',default='outputs/rolling_typhoon_final');p.add_argument('--max-new-scenarios',type=int)
    a=p.parse_args();run(a.output,a.source,a.max_new_scenarios)
