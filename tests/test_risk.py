"""Mean-CVaR의 독립 수치검증과 후보 선택 검증. 전체 항해 실험은 실행하지 않는다."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from maritime_sim.config import ROOT,load_config,validate
from maritime_sim.risk import discrete_cost_risk,candidate_evaluation
from maritime_sim.planner import TwoStagePlanner
from maritime_sim.weather import World,TrendForecaster
from maritime_sim.baseline import verify_baseline


class RiskTests(unittest.TestCase):
    def test_fractional_tail_nonuniform(self):
        r=discrete_cost_risk([0,10,20],[.6,.3,.1],.8)
        self.assertAlmostEqual(r.mean,5)
        self.assertAlmostEqual(r.cvar,15)
        np.testing.assert_allclose(r.tail_weights,[0,.5,.5],atol=1e-12)

    def test_nine_equal_scenarios(self):
        r=discrete_cost_risk(np.arange(1,10),np.ones(9)/9,.8)
        self.assertAlmostEqual(r.cvar,(9+8*.8)/1.8)
        self.assertAlmostEqual(r.tail_weights[-1],5/9)
        self.assertAlmostEqual(r.tail_weights[-2],4/9)
        self.assertAlmostEqual(discrete_cost_risk(np.arange(1,10),np.ones(9)/9,.9).cvar,9)

    def test_matches_eta_minimization(self):
        q=np.array([-4.,2.,13.,13.]);p=np.array([.15,.25,.2,.4])
        for alpha in [0,.2,.5,.8,.95]:
            independent=min(eta+np.dot(p,np.maximum(q-eta,0))/(1-alpha) for eta in q)
            self.assertAlmostEqual(discrete_cost_risk(q,p,alpha).cvar,independent)

    def test_deterministic_shift_first_cost_only_once(self):
        risk={"lambda":.5,"alpha":.8}
        a=candidate_evaluation(2,[0,100],[.9,.1],risk)
        self.assertAlmostEqual(a["expected_total_usd"],12)
        self.assertAlmostEqual(a["cvar_remaining_usd"],50)
        self.assertAlmostEqual(a["objective_total_usd"],32)
        for lam in [0,1]:
            b=candidate_evaluation(2,[7,7],[.4,.6],{"lambda":lam,"alpha":.8})
            self.assertAlmostEqual(b["objective_total_usd"],9)
        shifted=discrete_cost_risk([2,102],[.9,.1],.8)
        self.assertAlmostEqual(shifted.cvar,52)

    def test_infeasible_no_nan_at_lambda_endpoints(self):
        for lam in [0,.5,1]:
            r=candidate_evaluation(5,[10,float('inf')],[.8,.2],{"lambda":lam,"alpha":.8})
            self.assertIsNone(r['objective_total_usd'])
            self.assertIsNone(r['expected_total_usd'])
        self.assertAlmostEqual(discrete_cost_risk([4,float('inf')],[1,0],.8).cvar,4)

    def test_permutation_and_alpha_zero(self):
        a=discrete_cost_risk([5,30,15],[.2,.5,.3],.6)
        b=discrete_cost_risk([15,5,30],[.3,.2,.5],.6)
        self.assertAlmostEqual(a.cvar,b.cvar)
        self.assertAlmostEqual(discrete_cost_risk([5,30,15],[.2,.5,.3],0).cvar,a.mean)

    def test_invalid_parameters(self):
        for key,value in [('lambda',-1),('lambda',1.1),('lambda',float('nan')),('alpha',1),('alpha',-.1),('alpha',True)]:
            c=load_config();c['risk'][key]=value
            with self.assertRaises(ValueError):validate(c)
        for costs,probabilities in [([1,2],[.2,.2]),([1,2],[1.1,-.1]),([float('nan')],[1])]:
            with self.assertRaises(ValueError):discrete_cost_risk(costs,probabilities,.8)

    def test_selection_uses_risk_but_keeps_mean_and_paths_separate(self):
        net=SimpleNamespace(ids=np.arange(4),index={i:i for i in range(4)},dist=np.array([18.]))
        f=SimpleNamespace(probabilities=np.ones(3)/3,fields=lambda *_:(np.zeros((3,4,4)),np.zeros((3,4,1))))
        V=np.zeros((3,13,4));V[:,12,1]=[0,0,90];V[:,12,2]=[35,35,35]
        # Costs and recovered recourse paths are held fixed; only the candidate evaluation changes.
        def solve(weight):
            c=load_config();c.update(goal_node=3);c['risk']['lambda']=weight
            planner=TwoStagePlanner(net,c,20)
            with patch.object(planner,'first_stage',return_value=({1:0.,2:0.},{},[])), \
                 patch.object(planner,'backward',return_value=V), \
                 patch.object(planner,'reconstruct_first',return_value=[]), \
                 patch.object(planner,'recover_second',return_value=[]):
                # Different fields prevent the identical-weather shortcut from collapsing the mocked values.
                hn=np.zeros((3,4,4));hn[1,0,0]=.1
                f.fields=lambda *_:(hn,np.zeros((3,4,1)))
                return planner.solve(0,0,f)
        mean=solve(0);risk=solve(.5)
        self.assertEqual(mean['chosen_node'],1)
        self.assertEqual(risk['chosen_node'],2)
        self.assertEqual(mean['candidates'][0]['scenario_remaining_costs_usd'],risk['candidates'][0]['scenario_remaining_costs_usd'])
        self.assertAlmostEqual(risk['candidates'][0]['expected_total_usd'],30)
        self.assertAlmostEqual(risk['candidates'][0]['objective_total_usd'],60)


class FrozenBaselineTests(unittest.TestCase):
    def test_canonical_profile_and_alias(self):
        self.assertEqual(load_config(),load_config(ROOT/'configs'/'baseline.json'))
        self.assertEqual(load_config(),load_config(ROOT/'configs'/'korea_china_crossing.json'))
        # Source-hash identity is an explicit release check, not a development test.
        self.assertEqual(verify_baseline()['baseline_id'],load_config()['baseline_id'])

    def test_generator_matches_saved_previous_experiment(self):
        fixture=json.loads((ROOT/'tests'/'fixtures'/'crossing_forecast_v1.json').read_text(encoding='utf-8'))
        c=load_config();world=World(c);forecaster=TrendForecaster()
        self.assertEqual(forecaster.generator_id,c['scenario_generator'])
        for item in fixture['snapshots']:
            forecast=forecaster.generate(world.reveal(item['time_h']),c)
            np.testing.assert_allclose(forecast.states[:,item['hour_indices'],:],item['states'],rtol=0,atol=1e-9)
            np.testing.assert_allclose(forecast.probabilities,item['probabilities'],rtol=0,atol=1e-14)


if __name__=='__main__':unittest.main()
