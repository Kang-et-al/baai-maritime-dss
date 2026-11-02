import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from hex_dss.config import ROOT
from numba import get_num_threads
from experimental_dp.solver_policy import select_policy, full_values, total_risk
from experimental_dp.test_kernel import SelectiveTests
from experimental_dp import experiment


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.lat,self.c,self.fields,self.prepared=SelectiveTests().problem(3)
        self.lat.net.boxes=np.zeros((1,4))
        (ROOT/"outputs").mkdir(exist_ok=True)

    def forecasts(self, uncertain):
        a=np.zeros((9,4,3))
        if uncertain:
            a[:,:,2]=.5
            a[:,1:,0]=np.arange(9)[:,None]
        return a

    def test_dispatch_uses_environment_not_label(self):
        for mode in ['typhoon','calm']:
            self.c['mode']=mode
            p=select_policy(self.forecasts(False),self.c)
            self.assertEqual((p.backend,p.scenario_workers,len(p.unique_scenarios)),('full',1,1))
            p=select_policy(self.forecasts(True),self.c)
            self.assertEqual((p.backend,p.scenario_workers,p.state_threads),('selective',9,1))

    def test_full_backend_value_and_metrics(self):
        before=get_num_threads()
        got,counters=full_values(self.lat,self.fields,self.c,0.,2)
        self.assertEqual(before,get_num_threads())
        expected=SelectiveTests().full(self.lat,self.c,self.fields)
        np.testing.assert_allclose(got,expected,rtol=0,atol=1e-8)
        self.assertGreater(counters[0],0)

    def test_total_risk_includes_connector_and_honors_lambda(self):
        costs=[110.,210.,310.]
        obj,stats=total_risk(costs,[.2,.5,.3],{'lambda':.5,'alpha':.8})
        self.assertAlmostEqual(obj,.5*stats.mean+.5*310)
        obj,stats=total_risk([float('inf'),1],[.1,.9],self.c['risk'])
        self.assertIsNone(obj)

    def test_rolling_routes_each_backend_and_preserves_records(self):
        # Exercise candidate evaluation, risk, saving, dispatch and resume guard.
        # Physics and full/selective equality are independently tested above/in kernel tests.
        scores=[]
        for uncertain in [False,True]:
            states=self.forecasts(uncertain)
            forecast=SimpleNamespace(states=states,p=np.ones(9)/9,anchor_times=np.arange(4),observation_max_h=0.)
            candidate={'node':0,'heading':0,'q':12.,'stop':False,'wait':False,
                'trajectories':[SimpleNamespace(duration=.5,fuel=.2,trace=np.array([[0,0,6.]])) for _ in range(9)]}
            c=dict(self.c);c['initial']=dict(c['initial'])
            after=dict(c['initial'],x_nm=c['goal_nm'][0],y_nm=c['goal_nm'][1],speed_kn=0.,time_h=3.)
            with tempfile.TemporaryDirectory(dir=ROOT/"outputs") as td, \
                 patch.object(experiment,'load_config',return_value=c), \
                 patch.object(experiment,'build',return_value=self.lat), \
                 patch.object(experiment,'prepare',return_value=self.prepared), \
                 patch.object(experiment,'Forecast',return_value=forecast), \
                 patch.object(experiment,'local_candidates',return_value=[candidate]), \
                 patch.object(experiment,'upper_heights',return_value=self.fields), \
                 patch.object(experiment,'recover',return_value={'actions':[]}), \
                 patch.object(experiment,'fixed_execute',return_value=(after,{})), \
                 patch('experimental_dp.voyage_report.render'):
                snapshot=dict(c['initial'],x_nm=330.2)
                experiment.run('typhoon',td,initial_state=snapshot)
                record=json.loads((Path(td)/'steps/step_001.json').read_text())
                self.assertTrue(record['arrived'])
                self.assertEqual(record['state_before']['x_nm'],330.2)
                self.assertEqual(json.loads((Path(td)/'config.json').read_text())['initial']['x_nm'],342.)
                scores.append(record['plan']['chosen']['objective_usd'])
                self.assertEqual(record['plan']['solver_policy']['backend'],'selective' if uncertain else 'full')
                self.assertEqual(len(record['plan']['profiles']),9 if uncertain else 1)
                self.assertEqual(len(record['plan']['chosen']['scenario_future_usd']),9)
                with self.assertRaisesRegex(ValueError,'NEW output'):
                    experiment.run('typhoon',td)
                experiment.run('typhoon',td,resume=True)
        self.assertAlmostEqual(scores[0],scores[1],places=7)


if __name__=='__main__':unittest.main()
