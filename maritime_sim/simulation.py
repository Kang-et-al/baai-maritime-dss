"""상태를 소유하는 시뮬레이터. 계획은 첫 구간만 실행하고 매 스텝 체크포인트 저장."""
import hashlib
import json
import math
import platform
from pathlib import Path
import numpy as np
from . import __version__
from .config import ROOT, load_config
from .network import Network
from .weather import World, TrendForecaster, speed_rule
from .planner import TwoStagePlanner, action_cost, fuel_rate
from .runtime import runtime_metadata


def save_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    temp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def fingerprints():
    files=sorted((ROOT/"maritime_sim").glob("*.py"))+sorted((ROOT/"maritime_sim"/"assets").rglob("*"))+sorted((ROOT/"data"/"network").glob("*"))+sorted((ROOT/"data").glob("*.json"))+[ROOT/"configs"/"baseline.json",ROOT/"configs"/"baseline.lock.json"]
    return {str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files if p.is_file()}


def config_hash(config):
    return hashlib.sha256(json.dumps(config,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()


class Simulation:
    def __init__(self,config,output,forecaster=None,planner_factory=TwoStagePlanner,resume=False):
        self.config=config; self.output=Path(output)
        self.net=Network(); self.world=World(config)
        self.forecaster=forecaster or TrendForecaster()
        start=self.net.index[config["start_node"]]; goal=self.net.index[config["goal_node"]]
        normal_h=self.net.shortest_arcs(start,goal)*config["arc_distance_nm"]/config["normal_kn"]
        self.due=math.ceil(config["due_multiplier"]*normal_h)
        self.planner=planner_factory(self.net,config,self.due)
        if resume:
            stored=read_json(self.output/"manifest.json")
            if stored["fingerprints"]!=fingerprints():
                raise ValueError("Code or network changed. Start a new run to preserve reproducibility.")
            if stored["config_sha256"]!=config_hash(config):
                raise ValueError("Saved experiment configuration changed; start a new run.")
            records=sorted((self.output/"steps").glob("step_*.json"))
            self.state=read_json(records[-1])["state_after"] if records else read_json(self.output/"state.json")
        else:
            if self.output.exists() and any(self.output.iterdir()):
                raise ValueError("Output directory is not empty. Use a new directory or --resume.")
            self.output.mkdir(parents=True,exist_ok=True)
            self.state={"step":0,"time_h":0.,"node":config["start_node"],"status":"running",
                        "fuel_t":0.,"operating_cost_usd":0.,"late_cost_usd":0.,
                        "distance_nm":0.,"waiting_h":0.,"due_h":self.due,
                        "history":[{"time_h":0.,"node":config["start_node"]}]}
            save_json(self.output/"config.json",config)
            save_json(self.output/"manifest.json",{
                "version":__version__,"python":platform.python_version(),"numpy":np.__version__,
                **runtime_metadata(),
                "baseline_id":config["baseline_id"],"scenario_generator":config["scenario_generator"],
                "objective":{"type":"mean_cvar",**config["risk"]},
                "canonical_baseline_match":config==load_config(),
                "fingerprints":fingerprints(),"config_sha256":config_hash(config),"deterministic":True,
                "seed_note":"Seed reserved for future stochastic generators; baseline uses deterministic rules.",
                "cost_currency":"USD","coordinate_system":"WGS84 LCC; stored x/y in km",
                "normal_calm_shortest_h":normal_h,"due_h":self.due})
            save_json(self.output/"state.json",self.state)

    @classmethod
    def resume(cls,output):
        return cls(load_config(Path(output)/"config.json"),output,resume=True)

    def _execute(self,actions):
        c=self.config; dt=c["time_step_h"]; threshold=c["wave_thresholds_m"][-1]
        ticks=[]; previous=self.state["time_h"]
        for a in actions:
            i=self.net.index[a["from_node"]]; j=self.net.index[a["to_node"]]
            if a["from_node"]!=self.state["node"] or not np.isclose(a["start_h"],previous):
                raise RuntimeError("Execution plan is discontinuous")
            waiting=i==j
            if waiting:
                factor=1.
                for t in np.arange(a["start_h"],a["end_h"]+dt/2,dt):
                    if self.world.field(self.net.xy[[i]],t)[0]>=threshold:
                        raise RuntimeError("Actual weather forbids planned waiting")
            else:
                edges=[e for to,e in self.net.adj[i] if to==j]
                if not edges: raise RuntimeError("Plan uses a non-network edge")
                factor,cap=speed_rule(self.world.field(self.net.mid[[edges[0]]],a["start_h"])[0],c)
                factor=float(factor)
                if factor<=0 or a["command_kn"]>float(cap)+1e-8:
                    raise RuntimeError("Actual weather forbids planned movement")
                if not np.isclose(a["command_kn"]*factor*a["duration_h"],self.net.dist[edges[0]]):
                    raise RuntimeError("Actual duration/speed/distance mismatch")
            if self.world.field(self.net.xy[[j]],a["end_h"])[0]>=threshold:
                raise RuntimeError("Arrival node is unsafe")
            fuel=(c["fuel_wait_tph"] if waiting else fuel_rate(a["command_kn"],c))*a["duration_h"]
            cost=action_cost(a["command_kn"],a["duration_h"],c,waiting)
            if not np.isclose(cost,a["operating_cost_usd"],atol=1e-6):
                raise RuntimeError("Expected and actual first-stage costs differ")
            for t in np.arange(a["start_h"]+dt,a["end_h"]+dt/2,dt):
                progress=min(1.,(t-a["start_h"])/a["duration_h"])
                xy=self.net.xy[i]+progress*(self.net.xy[j]-self.net.xy[i])
                ticks.append({"time_h":float(t),"xy_km":xy.tolist(),
                              "from_node":a["from_node"],"to_node":a["to_node"],
                              "progress":float(progress),"command_kn":a["command_kn"]})
            self.state["fuel_t"]+=fuel; self.state["operating_cost_usd"]+=cost
            self.state["distance_nm"]+=0 if waiting else self.config["arc_distance_nm"]
            self.state["waiting_h"]+=a["duration_h"] if waiting else 0
            self.state["node"]=a["to_node"]; self.state["time_h"]=a["end_h"]
            self.state["history"].append({"time_h":a["end_h"],"node":a["to_node"]})
            previous=a["end_h"]
        return ticks

    def step(self):
        if self.state["status"]!="running": return None
        if self.state["time_h"]+self.config["rolling_h"]>self.config["simulation_limit_h"]+1e-8:
            self.state["status"]="time_limit"; save_json(self.output/"state.json",self.state); return None
        before=json.loads(json.dumps(self.state))
        obs=self.world.reveal(before["time_h"])
        forecast=self.forecaster.generate(obs,self.config)
        forecast.validate(obs,self.config)
        plan=self.planner.solve(before["node"],before["time_h"],forecast)
        ticks=[]
        if plan["status"]=="ok":
            ticks=self._execute(plan["first_actions"])
            if self.state["node"]==self.config["goal_node"]:
                self.state["status"]="arrived"
                self.state["late_cost_usd"]=self.config["late_usd_per_h"]*max(0,self.state["time_h"]-self.due)
            elif not np.isclose(self.state["time_h"],before["time_h"]+self.config["rolling_h"]):
                raise RuntimeError("Nonterminal first stage must end exactly at rolling boundary")
            elif self.state["time_h"]>=self.config["simulation_limit_h"]:
                self.state["status"]="time_limit"
        else:
            self.state["status"]="planning_infeasible"
        self.state["step"]+=1
        after=json.loads(json.dumps(self.state))
        record={"step":self.state["step"],"state_before":before,"state_after":after,
                "observation":{"hours":obs.hours.tolist(),"states":obs.states.tolist()},
                "forecast":forecast.as_dict(),"plan":plan,"execution_ticks":ticks,
                "actual_typhoon_at_end":self.world.state(self.state["time_h"]).tolist()}
        # A completed step is authoritative if interruption happens before checkpoint write.
        save_json(self.output/"steps"/f"step_{self.state['step']:03d}.json",record)
        save_json(self.output/"state.json",self.state)
        return record

    def run(self,steps=1,render=True,experiment_format=None):
        from .replay import FORMATS
        from .report import render_index
        presentation=self.output/'presentation.json'
        if experiment_format is not None and experiment_format not in FORMATS:
            raise ValueError('experiment_format must be replay or live')
        if experiment_format or not presentation.exists():
            save_json(presentation,{'format':experiment_format or 'live'})
        style=read_json(presentation)['format']
        records=[]
        for _ in range(steps):
            record=self.step()
            if record is None: break
            if render:
                from .report import render_step
                render_step(self.output,record,self.net,self.config)
            records.append(record)
            if style=='live': render_index(self.output)
            s=self.state
            print(f"step={s['step']:03d} time={s['time_h']:.2f}h node=N{s['node']} "
                  f"status={s['status']} fuel={s['fuel_t']:.3f}t "
                  f"solve={record['plan']['solve_seconds']:.2f}s",flush=True)
            if s["status"]!="running": break
        render_index(self.output)
        return records
