import unittest,json
from types import SimpleNamespace
import numpy as np
from numba import set_num_threads
from hex_dss.config import ROOT
from hex_dss.drive_motion import parameters
from hex_dss.drive_dp import backward_drive,value_at
from experimental_dp.kernel import Evaluator,children

class SelectiveTests(unittest.TestCase):
    def problem(self,seed=0):
        rng=np.random.default_rng(seed)
        c=json.loads((ROOT/'configs/hex_propulsion.json').read_text());c.update(horizon_h=4.,due_h=1.,late_usd_per_h=1000.)
        src=np.repeat(np.arange(48),2);dst=np.where(src<24,24,48).astype(np.int32)
        n=len(src);s=np.tile([0.,5.],(n,1));table=np.zeros((n,21,4))
        for a in range(n):table[a,:,:]=[1,rng.uniform(.3,1.3),rng.uniform(0,18),rng.uniform(.1,1)]
        ptr=np.r_[np.arange(0,n+1,2),np.full(24,n)].astype(np.int32)
        lat=SimpleNamespace(nstate=72,ptr=ptr,dstbase=dst,gid=np.arange(n,dtype=np.int32),tid=np.arange(n,dtype=np.int32),tables=table,
            type_curve_s=s,type_caps=np.ones_like(s)*18,type_x=s,type_y=np.zeros_like(s),commands=np.ones(n)*12,stops=np.zeros(n,np.bool_),
            initial_speeds=np.tile([0,6,12,18],12).repeat(2).astype(float),params=parameters(c),net=SimpleNamespace(goal=2),src=src)
        fields=np.zeros((20,n),np.float32)
        prepared=(np.arange(n,dtype=np.int64),np.ones(n)*5,np.array([530*10/18,530*5/18,0.]))
        return lat,c,fields,prepared
    def full(self,a,c,f):
        p=c['propulsion'];dt=c['time_step_h']
        return backward_drive(a.ptr,a.dstbase,a.gid,a.tid,a.tables,f,a.type_curve_s,a.type_caps,a.type_x,a.type_y,a.commands,a.stops,a.initial_speeds,a.params,
            round(c['horizon_h']/dt),dt,0.,c['due_h'],c['late_usd_per_h'],a.net.goal,530*dt,p['wave_table_step_m'],12.,p['dp_integration_h'],600.,500.)
    def test_exact_and_bounded_match_full_random_dags(self):
        set_num_threads(2)
        for seed in range(4):
            a,c,f,pr=self.problem(seed);ref=self.full(a,c,f)
            for bounded in [False,True]:
                e=Evaluator(a,f,c,0,bounded,pr)
                for k in [0,2.3,8.2,15.7,16.]:
                    for base in [0,4,24,28,48]:
                        for v in [0,3.2,12.,18.]:
                            got=e.query(k,base,v);want=value_at(ref,k,base,v)
                            if np.isinf(want):self.assertTrue(np.isinf(got))
                            else:self.assertAlmostEqual(got,want,places=7)
                mask=~np.isnan(e.V);np.testing.assert_allclose(e.V[mask],ref[mask],atol=1e-8,rtol=0)
                self.assertLessEqual(e.stats[0],ref.size)
    def test_interpolation_threshold_and_horizon(self):
        a,c,f,pr=self.problem();e=Evaluator(a,f,c,0,True,pr);ref=self.full(a,c,f)
        for k in [1+1e-11,16+5e-9,16+1e-7]:
            np.testing.assert_allclose(e.query(k,0,6+1e-11),value_at(ref,k,0,6+1e-11))

    def test_dynamic_wave_fallback_matches_full(self):
        a,c,f,pr=self.problem();a.tables[:,1:,0]=0
        f[:2,:]=8
        # Make actual type geometry/speed consistent for dynamic integration.
        a.initial_speeds[:]=0.;a.type_caps[:]=18.
        ref=self.full(a,c,f);e=Evaluator(a,f,c,0,True,pr)
        for k in [0.,2.4,7.3,13.]:
            np.testing.assert_allclose(e.query(k,0,0),value_at(ref,k,0,0),rtol=0,atol=1e-7)
        self.assertGreater(e.counters[2],0)

    def test_bounding_prunes_without_changing_values(self):
        a,c,f,pr=self.problem(9);e=Evaluator(a,f,c,0,True,pr);ref=self.full(a,c,f)
        got=e.query(0,0,0);self.assertAlmostEqual(got,ref[0,0],places=7)
        self.assertGreater(e.stats[2]+e.stats[3],0)
        # Distance lower bounds, corrected for dropped interpolation weights.
        for k in range(16):
            for st in range(48):
                lo=max(0.,(1-1e-9)**(16-k)*pr[2][st//24]-1e-6)
                self.assertLessEqual(lo,ref[k,st]+1e-7)

if __name__=='__main__':unittest.main()
