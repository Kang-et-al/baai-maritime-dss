import unittest,concurrent.futures
import numpy as np
from pathlib import Path
from experimental_dp.test_kernel import SelectiveTests
from experimental_dp.kernel_threaded import Evaluator
from hex_dss.drive_dp import value_at

class ThreadedTests(unittest.TestCase):
    def test_exact_scenario_groups_preserve_nine_weights(self):
        from experimental_dp.scenario_groups import references
        from hex_dss.propulsion import load_config
        from hex_dss.weather import World,Forecast
        from hex_dss.risk import discrete_cost_risk
        c=load_config();c['mode']='typhoon'
        self.assertEqual(references(Forecast(World(c).observe(24),c).states),list(range(9)))
        f=Forecast(World(c).observe(75),c);refs=references(f.states)
        self.assertEqual(refs,[0,0,2,0,0,5,0,0,8])
        for s,ref in enumerate(refs):
            if s!=ref:self.assertTrue(np.all(f.states[s,:,2]==0) and np.all(f.states[ref,:,2]==0))
        expanded=[7,7,9,7,7,11,7,7,13];mapping={0:7,2:9,5:11,8:13}
        a=discrete_cost_risk(expanded,f.p,.8);b=discrete_cost_risk([mapping[r] for r in refs],f.p,.8)
        self.assertEqual(a,b)
        c['mode']='calm';self.assertEqual(references(Forecast(World(c).observe(75),c).states),[0]*9)
    def test_only_compilation_gil_flag_changed(self):
        p=Path(__file__).parent
        self.assertEqual((p/'kernel.py').read_text(),(p/'kernel_threaded.py').read_text().replace('@njit(cache=True,nogil=True)','@njit(cache=True)'))
    def test_nine_concurrent_scenarios_match_full(self):
        fixture=SelectiveTests();a,c,f,pr=fixture.problem(6);ref=fixture.full(a,c,f)
        def job(_):
            e=Evaluator(a,f,c,0,True,pr)
            for k in [0,2.3,7.7,15.9]:
                for base in [0,24,48]:
                    for v in [0,3.1,12.,18.]:
                        np.testing.assert_allclose(e.query(k,base,v),value_at(ref,k,base,v),atol=1e-7,rtol=0)
            return True
        with concurrent.futures.ThreadPoolExecutor(9) as pool:self.assertTrue(all(pool.map(job,range(9))))

if __name__=='__main__':unittest.main()
