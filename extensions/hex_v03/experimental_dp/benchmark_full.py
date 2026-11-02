"""Matched 3-process / one-thread full-DP timing, unchanged old numerical kernel."""
import json,time,concurrent.futures
from pathlib import Path
import numpy as np
from numba import set_num_threads
from hex_dss.config import ROOT
from hex_dss.propulsion import build
from hex_dss.weather import World,Forecast
from hex_dss.drive_motion import upper_heights
from hex_dss.drive_planner import local_candidates,solve_dp,_future
from hex_dss.drive_dp import backward_drive
from hex_dss.runtime import save

def worker(s):
    c=json.loads((ROOT/'outputs/rolling_typhoon_final/config.json').read_text());st=json.loads((ROOT/'outputs/rolling_typhoon_final/steps/step_002.json').read_text())['state_before']
    lat=build(c,lambda _:None);f=Forecast(World(c).observe(3.),c);aa=local_candidates(st,lat,f,c)
    set_num_threads(1);fields=upper_heights(f,lat.net.boxes,s);p=c['propulsion'];counts=np.zeros((lat.nstate,5),np.int64)
    t=time.perf_counter()
    V=backward_drive(lat.ptr,lat.dstbase,lat.gid,lat.tid,lat.tables,fields,lat.type_curve_s,lat.type_caps,lat.type_x,lat.type_y,
        lat.commands,lat.stops,lat.initial_speeds,lat.params,round(c['horizon_h']/c['time_step_h']),c['time_step_h'],3.,c['due_h'],c['late_usd_per_h'],lat.net.goal,
        530*c['time_step_h'],p['wave_table_step_m'],p['transition_limit_h'],p['dp_integration_h'],c['fuel_usd_per_t'],c['time_usd_per_h'],counts)
    elapsed=time.perf_counter()-t
    values=[]
    for a in aa:
        if a['wait']:
            from hex_dss.drive_dp import value_at
            v=value_at(V,1.,a['node']*24+a['heading']*4,0.)
        else:v=_future(V,a['trajectories'][s],a['node']*24+a['heading']*4,3.,.25)
        values.append(None if not np.isfinite(v) else float(v))
    r={'scenario':s,'dp_seconds':elapsed,'values':values,'counts':counts.sum(axis=0).tolist()};save(ROOT/f'outputs/t3_full_matched/scenario_{s:02d}.json',r)
    print(f'FULL scenario {s+1} {elapsed:.2f}s',flush=True);return r

if __name__=='__main__':
    out=ROOT/'outputs/t3_full_matched';out.mkdir(exist_ok=True)
    if any(out.iterdir()):raise ValueError('Preserve previous output; use empty output')
    t=time.perf_counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=3) as p:rows=list(p.map(worker,range(9)))
    save(out/'result.json',{'workers':3,'threads_per_worker':1,'wall_seconds':time.perf_counter()-t,'profiles':rows})
