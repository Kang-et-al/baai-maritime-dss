"""의미 있는 독립 검증: 완전열거와 DP 비교, 정보 누출 방지, 실제 실행 정합성."""
import functools
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
import numpy as np
from maritime_sim.config import ROOT, load_config, validate
from maritime_sim.network import Network, project
from maritime_sim.weather import World, TrendForecaster, speed_rule
from maritime_sim.planner import TwoStagePlanner, action_cost
from maritime_sim.simulation import Simulation


class TinyNetwork:
    def __init__(self):
        self.ids=np.array([0,1,2]); self.index={0:0,1:1,2:2}; self.n=3
        self.xy=np.array([[0.,0.],[33.336,0.],[66.672,0.]])
        self.src=np.array([0,1,1,2]); self.dst=np.array([1,0,2,1])
        self.dist=np.full(4,18.); self.mid=(self.xy[self.src]+self.xy[self.dst])/2
        self.adj=[[(1,0)],[(0,1),(2,2)],[(1,3)]]


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT/"work").mkdir(parents=True,exist_ok=True)

    def test_network_and_projection(self):
        net=Network()
        self.assertEqual((net.n,len(net.src)),(2286,8600))
        self.assertLess(np.max(np.abs(project(net.lonlat[:,0],net.lonlat[:,1])-net.xy)),0.001)
        self.assertTrue(all(any(k==i for k,_ in net.adj[j]) for i,j in zip(net.src,net.dst)))

    def test_no_future_leak_and_common_interval(self):
        a=load_config(); b=deepcopy(a)
        b["typhoon_waypoints"][2]=[24,130,30,0.1]
        oa,ob=World(a).reveal(0),World(b).reveal(0)
        fa,fb=TrendForecaster().generate(oa,a),TrendForecaster().generate(ob,b)
        np.testing.assert_allclose(fa.states,fb.states)
        for s in range(9): np.testing.assert_allclose(fa.states[s,:4],oa.states)
        self.assertAlmostEqual(float(fa.probabilities.sum()),1.)
        next_obs=World(a).reveal(3)
        self.assertAlmostEqual(next_obs.hours[-1],6)

    def test_calm_forecasts_all_neutral(self):
        c=load_config(); c["mode"]="calm"
        f=TrendForecaster().generate(World(c).reveal(0),c)
        hn,he=f.fields(TinyNetwork(),c)
        self.assertEqual(float(hn.max()),0.)
        self.assertEqual(float(he.max()),0.)

    def test_dp_matches_independent_exhaustive_search(self):
        c=load_config(); c.update(start_node=0,goal_node=2,horizon_h=9)
        net=TinyNetwork(); p=TwoStagePlanner(net,c,5)
        S=2; K=36; L=12
        hn=np.zeros((S,10,3)); he=np.zeros((S,10,4))
        he[0,3:5,2]=3.0       # Temporarily slowed forward edge
        he[1,3:6,2]=5.5       # Temporarily blocked forward edge; wait/detour
        hn[1,4,1]=5.1         # Unsafe node, including arrival/wait constraint
        class F: probabilities=np.array([0.5,0.5])
        V=p.backward(0,F(),hn,he)
        @functools.lru_cache(None)
        def oracle(s,i,q):
            if i==2: return 1000*max(0,q*.25-5)
            if q>=K or hn[s,q//4,i]>=5: return float("inf")
            choices=[]
            if hn[s,(q+1)//4,i]<5:
                choices.append((600*.05+500)*.25+oracle(s,i,q+1))
            for j,e in net.adj[i]:
                h=he[s,q//4,e]
                r=1 if h<2 else 2/3 if h<4 else .5 if h<5 else 0
                for v in [12,18]:
                    if not r or (h>=4 and v==18): continue
                    m=round(18/(r*v*.25))
                    if q+m<=K and hn[s,(q+m)//4,j]<5:
                        cost=(600*.5*(v/12)**3+500)*m*.25
                        choices.append(cost+oracle(s,j,q+m))
            return min(choices,default=float("inf"))
        for s in range(S):
            for q in range(L,K+1):
                for i in range(3):
                    self.assertAlmostEqual(V[s,q,i],oracle(s,i,q))
            if np.isfinite(V[s,L,0]):
                route=p.recover_second(V,s,0,L,0,hn,he)
                actual=sum(a["operating_cost_usd"] for a in route)+p.late(route[-1]["end_h"])
                self.assertAlmostEqual(actual,V[s,L,0])

    def test_first_stage_and_early_arrival_execution(self):
        c=load_config(); c["mode"]="calm"; c["horizon_h"]=12
        net=Network(); goal=net.index[c["goal_node"]]
        c["start_node"]=int(net.ids[net.adj[goal][0][0]])
        with tempfile.TemporaryDirectory(dir=ROOT/"work") as tmp:
            sim=Simulation(c,Path(tmp)/"run")
            record=sim.step()
            self.assertEqual(sim.state["status"],"arrived")
            self.assertLess(sim.state["time_h"],3)
            self.assertTrue(record["plan"]["early_arrival"])
            self.assertAlmostEqual(sim.state["operating_cost_usd"]+sim.state["late_cost_usd"],record["plan"]["expected_total_usd"])
            resumed=Simulation.resume(Path(tmp)/"run")
            self.assertEqual(resumed.state,sim.state)

    def test_resume_matches_continuous_execution_and_config_tamper_rejected(self):
        from maritime_sim.simulation import read_json, save_json
        c=load_config(); c["mode"]="calm"; c["horizon_h"]=12
        net=Network(); goal=net.index[c["goal_node"]]
        seen={goal}; frontier=[goal]
        for _ in range(5):
            frontier=sorted({j for i in frontier for j,_ in net.adj[i]}-seen)
            seen.update(frontier)
        c["start_node"]=int(net.ids[frontier[0]])
        with tempfile.TemporaryDirectory(dir=ROOT/"work") as tmp:
            a=Simulation(c,Path(tmp)/"continuous"); a.step(); a.step()
            b=Simulation(c,Path(tmp)/"resumed"); b.step()
            b=Simulation.resume(Path(tmp)/"resumed"); b.step()
            self.assertEqual(a.state,b.state)
            stored=read_json(Path(tmp)/"resumed"/"config.json")
            stored["fuel_usd_per_t"]=999
            save_json(Path(tmp)/"resumed"/"config.json",stored)
            with self.assertRaises(ValueError): Simulation.resume(Path(tmp)/"resumed")

    def test_invalid_forecast_common_interval_rejected(self):
        c=load_config(); obs=World(c).reveal(0)
        f=TrendForecaster().generate(obs,c)
        f.validate(obs,c)
        f.states[0,0,0]+=1
        with self.assertRaises(ValueError): f.validate(obs,c)

    def test_zero_speed_is_forbidden_before_division(self):
        c=load_config(); r,cap=speed_rule(5,c)
        self.assertEqual(float(r),0.)
        net=TinyNetwork(); c.update(start_node=0,goal_node=2,horizon_h=6)
        p=TwoStagePlanner(net,c,10)
        hn=np.full((4,3),6.); he=np.full((4,4),6.)
        candidates,pred,early=p.first_stage(0,0,hn,he)
        self.assertFalse(candidates); self.assertFalse(early)

    def test_off_grid_duration_is_rejected(self):
        c=load_config(); c["speed_factors"]=[1,0.8,0.5]
        with self.assertRaises(ValueError): validate(c)


if __name__=="__main__": unittest.main()
