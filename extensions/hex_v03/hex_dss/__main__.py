import argparse
import json
import math
import os
import pickle
import time
from pathlib import Path
from .config import ROOT,load
from .runtime import save,metadata,fingerprints
from .network import HexNetwork
from .lattice import Lattice
from .planner import Planner
from .weather import World,Forecast
from .executor import execute


def build(c,progress=print):
    key=json.dumps(c,sort_keys=True)+json.dumps(fingerprints(),sort_keys=True)
    import hashlib
    digest=hashlib.sha256(key.encode()).hexdigest()[:20]
    cache=ROOT/'cache'/f'lattice-{digest}.pickle'
    if cache.exists():
        progress('Loading validated local lattice cache')
        with cache.open('rb') as f:return pickle.load(f)
    progress('Building hex network and continuous motion primitives')
    net=HexNetwork(c).build_geometries()
    progress(f'Hex nodes {net.n}; land-clear curves {len(net.curves)}')
    lat=Lattice(net,c)
    progress(f'States {lat.nstate}; actions {len(lat.src)}; profile types {len(lat.types)}')
    cache.parent.mkdir(exist_ok=True)
    with cache.open('wb') as f:pickle.dump(lat,f,protocol=5)
    return lat


def main():
    p=argparse.ArgumentParser(description='Independent continuous-state hex DSS')
    p.add_argument('command',choices=['decide','run','prepare'])
    p.add_argument('--config');p.add_argument('--output',default='outputs/first_decision')
    p.add_argument('--state',help='JSON with arbitrary time_h/x_nm/y_nm/speed_kn/heading_deg')
    p.add_argument('--steps',type=int,default=1)
    p.add_argument('--resume',action='store_true',help='Continue saved experiment without altering its prior records')
    p.add_argument('--interrupt-at',type=float,help='Absolute interruption time inside first chosen trajectory')
    args=p.parse_args();output=Path(args.output)
    c=load(output/'config.json' if args.resume and args.config is None else args.config)
    if args.steps<1:raise ValueError('--steps must be positive')
    previous=[]
    if args.resume:
        if args.state or args.config:raise ValueError('Resume cannot replace state/config; create a new experiment')
        manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
        if manifest['fingerprints']!=fingerprints():raise ValueError('Code/data/config changed: preserve this run and create a new experiment')
        previous=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((output/'steps').glob('step_*.json'))]
        if previous and previous[-1].get('arrived'):raise ValueError('Experiment already arrived; no further movement is needed')
    def log(msg):print(msg,flush=True)
    started=time.perf_counter();lat=build(c,log);build_s=time.perf_counter()-started
    if args.command=='prepare':return
    if not args.resume and output.exists() and any(output.iterdir()):raise ValueError('Use a NEW output directory; previous results are never overwritten')
    output.mkdir(parents=True,exist_ok=True)
    if args.resume:state=json.loads((output/'state.json').read_text(encoding='utf-8'))
    else:state=dict(c['initial']) if not args.state else json.loads(Path(args.state).read_text(encoding='utf-8-sig'))
    state.setdefault('fuel_t',0.);state.setdefault('operating_cost_usd',0.);state.setdefault('distance_nm',0.)
    if not args.resume:
        save(output/'config.json',c);save(output/'initial_state.json',state)
    world=World(c);planner=Planner(lat,c);records=list(previous)
    count=1 if args.command=='decide' else args.steps
    for step in range(len(previous)+1,len(previous)+count+1):
        if state['time_h']>=c['simulation_limit_h']:break
        forecast=Forecast(world.observe(state['time_h']),c)
        plan,trajectory=planner.solve(state,forecast,log)
        record={'step':step,'state_before':state,'forecast':{'anchor_times':forecast.anchor_times.tolist(),'states':forecast.states.tolist(),'probabilities':forecast.p.tolist(),'labels':forecast.labels,'observation_max_h':forecast.observation_max_h},'plan':plan}
        if trajectory is not None:
            stop=args.interrupt_at if step==len(previous)+1 else None
            after,execution=execute(state,trajectory,world,c,stop)
            record.update(state_after=after,execution=execution)
            if math.dist([after['x_nm'],after['y_nm']],c['goal_nm'])<1e-5 and after['speed_kn']<1e-5:
                record['arrived']=True;after['late_cost_usd']=c['late_usd_per_h']*max(0,after['time_h']-c['due_h'])
            state=after
        save(output/'steps'/f'step_{step:03d}.json',record);records.append(record)
        save(output/'state.json',state)
        from .report import render
        render(output,records,lat,c)
        log(f"STEP {step} status={plan['status']} solve={plan['solve_seconds']:.2f}s state_time={state['time_h']:.6f}h")
        if plan['status']!='ok' or record.get('arrived') or record.get('execution',{}).get('status')!='ok':break
    metrics=metadata();metrics.update(build_seconds=build_s,wall_seconds=time.perf_counter()-started,steps=len(records),
                                   network_nodes=lat.net.n,states=lat.nstate,actions=len(lat.src),profile_types=len(lat.types),
                                   solve_seconds=[r['plan']['solve_seconds'] for r in records],
                                   full_v_table_estimated_mib=(round(c['horizon_h']/c['time_step_h'])+1)*lat.nstate*8/2**20,
                                   result_status=records[-1]['plan']['status'])
    save(output/'manifest.json',metrics)
    log(json.dumps({k:metrics[k] for k in ['build_seconds','wall_seconds','peak_rss_mb','network_nodes','states','actions','solve_seconds','result_status']},indent=2))


if __name__=='__main__':main()
