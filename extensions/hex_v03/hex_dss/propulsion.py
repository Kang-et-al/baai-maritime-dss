"""CLI for the new propulsion-response engine; old hex engine stays unchanged."""
import argparse
import hashlib
import json
import math
import pickle
import time
from pathlib import Path
import numpy as np
from .config import ROOT
from .runtime import save,metadata,fingerprints
from .network import HexNetwork
from .drive_lattice import DriveLattice
from .drive_planner import solve,solve_dp
from .drive_motion import simulate
from .weather import Forecast,World


def load_config(path=None):
    c=json.loads(Path(path or ROOT/'configs/hex_propulsion.json').read_text(encoding='utf-8-sig'))
    if c['risk']!={'lambda':0.0,'alpha':0.8}: # Other risk preferences remain supported.
        from .risk import validate_risk
        validate_risk(c['risk'])
    return c


def build(c,progress=print):
    key=hashlib.sha256((json.dumps(c,sort_keys=True)+json.dumps(fingerprints(),sort_keys=True)).encode()).hexdigest()[:20]
    path=ROOT/'cache'/f'drive-{key}.pickle'
    if path.exists():
        progress('Loading local propulsion lattice cache')
        with path.open('rb') as f:return pickle.load(f)
    progress('Building unchanged hex geometry + propulsion transfer tables')
    net=HexNetwork(c).build_geometries();progress(f'Hex nodes {net.n}; curves {len(net.curves)}')
    lat=DriveLattice(net,c,progress)
    path.parent.mkdir(exist_ok=True)
    with path.open('wb') as f:pickle.dump(lat,f,protocol=5)
    return lat


def execute_candidate(a,state,world,c,interrupt=None):
    stop_time=state['time_h']+c['max_replan_h']
    if interrupt is not None:stop_time=min(stop_time,interrupt)
    if a['wait']:
        elapsed=min(c['time_step_h'],stop_time-state['time_h']);fuel=elapsed*c['fuel_wait_tph']
        after=dict(state);after['time_h']+=elapsed
        trace=[{'time_h':state['time_h'],'x_nm':state['x_nm'],'y_nm':state['y_nm'],'speed_kn':0.,'q_command_kn':0.,'heading_deg':state['heading_deg']},
               {'time_h':after['time_h'],'x_nm':state['x_nm'],'y_nm':state['y_nm'],'speed_kn':0.,'q_command_kn':0.,'heading_deg':state['heading_deg']}]
        distance=0.;status='wait';tr=None
    else:
        tr,status=simulate(a['curve'],state['speed_kn'],a['q'],a['stop'],state['time_h'],stop_time-state['time_h'],c,world=world)
        if tr is None:raise RuntimeError('Chosen policy violates unchanged steering constraints in actual execution')
        elapsed=tr.duration;fuel=tr.fuel;distance=float(tr.trace[-1,1]);status='arrived_connector' if tr.reached else 'replan_due'
        xy,v,h=tr.sample(tr.start_h+tr.trace[:,0]);trace=[]
        for row,p,speed,heading in zip(tr.trace,xy,v,h):
            trace.append({'time_h':tr.start_h+float(row[0]),'x_nm':float(p[0]),'y_nm':float(p[1]),'speed_kn':float(speed),
                          'q_command_kn':float(row[3]),'wave_m':float(row[4]),'heading_deg':float(np.degrees(heading)%360)})
        after=dict(state);after.update(time_h=state['time_h']+elapsed,x_nm=float(xy[-1,0]),y_nm=float(xy[-1,1]),speed_kn=float(v[-1]),heading_deg=float(np.degrees(h[-1])%360))
    after['fuel_t']=state.get('fuel_t',0)+fuel;after['distance_nm']=state.get('distance_nm',0)+distance
    after['operating_cost_usd']=state.get('operating_cost_usd',0)+fuel*c['fuel_usd_per_t']+elapsed*c['time_usd_per_h']
    after['history']=state.get('history',[])+trace
    return after,{'status':status,'duration_h':elapsed,'distance_nm':distance,'fuel_t':fuel,'cost_usd':fuel*c['fuel_usd_per_t']+elapsed*c['time_usd_per_h'],
                  'samples':trace,'trajectory':None if tr is None else tr.as_dict()}


def main():
    parser=argparse.ArgumentParser(description='Propulsion-command / actual-speed hex DSS')
    parser.add_argument('command',choices=['decide','run','prepare','benchmark'])
    parser.add_argument('--config');parser.add_argument('--output',default='outputs/propulsion_first')
    parser.add_argument('--steps',type=int,default=1);parser.add_argument('--state');parser.add_argument('--resume',action='store_true')
    parser.add_argument('--interrupt-at',type=float);parser.add_argument('--benchmark-hours',type=float,default=24)
    args=parser.parse_args();output=Path(args.output)
    c=load_config(output/'config.json' if args.resume else args.config)
    previous=[]
    if args.resume:
        manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        if manifest['fingerprints']!=fingerprints():raise ValueError('Source changed: use a new experiment')
        previous=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((output/'steps').glob('*.json'))]
        if args.state or args.config:raise ValueError('Resume cannot replace initial state/config')
    elif args.command not in ['prepare','benchmark'] and output.exists() and any(output.iterdir()):raise ValueError('Use a NEW output folder')
    started=time.perf_counter();lat=build(c,lambda m:print(m,flush=True));build_s=time.perf_counter()-started
    if args.command=='prepare':return
    state=dict(c['initial']) if not args.state else json.loads(Path(args.state).read_text(encoding='utf-8-sig'))
    if args.resume:state=json.loads((output/'state.json').read_text(encoding='utf-8'))
    world=World(c)
    if args.command=='benchmark':
        from numba import set_num_threads
        set_num_threads(c['propulsion']['threads']);t=time.perf_counter()
        V,fields=solve_dp(lat,Forecast(world.observe(state['time_h']),c),0,c,args.benchmark_hours)
        print(json.dumps({'benchmark_hours':args.benchmark_hours,'seconds':time.perf_counter()-t,'V_MiB':V.nbytes/2**20}),flush=True);return
    output.mkdir(parents=True,exist_ok=True)
    if not args.resume:save(output/'config.json',c);save(output/'initial_state.json',state)
    records=list(previous);count=1 if args.command=='decide' else args.steps
    for step in range(len(previous)+1,len(previous)+count+1):
        forecast=Forecast(world.observe(state['time_h']),c)
        plan,a=solve(state,forecast,lat,c,lambda m:print(m,flush=True))
        r={'step':step,'state_before':state,'forecast':{'states':forecast.states.tolist(),'anchor_times':forecast.anchor_times.tolist(),'observation_max_h':forecast.observation_max_h},'plan':plan}
        if a is not None:
            after,execution=execute_candidate(a,state,world,c,args.interrupt_at if step==len(previous)+1 else None)
            r.update(state_after=after,execution=execution)
            r['arrived']=math.dist([after['x_nm'],after['y_nm']],c['goal_nm'])<1e-5 and after['speed_kn']<1e-3
            state=after
        records.append(r);save(output/'steps'/f'step_{step:03d}.json',r);save(output/'state.json',state)
        from .drive_report import render
        render(output,records,lat,c)
        print(f"STEP {step}: {plan['status']} solve {plan['solve_seconds']:.2f}s",flush=True)
        if a is None or r['arrived'] or state['time_h']>=c['simulation_limit_h']:break
    m=metadata();m.update(engine='propulsion-response-v2',build_seconds=build_s,wall_seconds=time.perf_counter()-started,
                         network_nodes=lat.net.n,states=lat.nstate,actions=len(lat.src),solve_seconds=[r['plan']['solve_seconds'] for r in records])
    save(output/'manifest.json',m);print(json.dumps({k:m[k] for k in ['build_seconds','wall_seconds','peak_rss_mb','solve_seconds']},indent=2),flush=True)


if __name__=='__main__':main()
