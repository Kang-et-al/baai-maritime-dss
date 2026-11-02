import copy
import json
import unittest
import numpy as np
from hex_dss.config import ROOT
from hex_dss.motion import make_curve
from hex_dss.drive_motion import simulate,acceleration


class PropulsionPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=json.loads((ROOT/'configs/hex_propulsion.json').read_text())
        cls.curve=make_curve([0,0],[100,0],0,0,cls.c)

    def test_calm_acceleration_is_continuous_and_bounded(self):
        tr,status=simulate(self.curve,0,12,False,0,2,self.c,constant_H=0)
        self.assertEqual(status,0);self.assertEqual(tr.trace[0,2],0)
        self.assertGreater(tr.trace[-1,2],11.9);self.assertLessEqual(tr.trace[-1,2],12)
        a=np.diff(tr.trace[:,2])/np.diff(tr.trace[:,0])
        self.assertLessEqual(a.max(),24+1e-7)
        self.assertLess(tr.trace[1,2],0.21)

    def test_wave_drag_slows_without_an_initial_speed_rejection(self):
        tr,status=simulate(self.curve,18,12,False,0,2,self.c,constant_H=3)
        self.assertEqual(status,0)
        self.assertLess(tr.trace[-1,2],9)
        self.assertGreater(tr.trace[1,2],17)
        self.assertGreaterEqual((np.diff(tr.trace[:,2])/np.diff(tr.trace[:,0])).min(),-24-1e-7)

    def test_high_wave_stall_burns_fuel_without_forbidden_state(self):
        tr,status=simulate(self.curve,18,18,False,0,2,self.c,constant_H=8)
        self.assertEqual(status,0);self.assertAlmostEqual(tr.trace[-1,2],0)
        self.assertGreater(tr.fuel,3.3)
        self.assertGreater(tr.trace[-1,1],0);self.assertLess(tr.trace[-1,1],10)
        self.assertGreater(tr.trace[-1,0],1.99)

    def test_stalled_at_rest_still_consumes_engine_fuel(self):
        tr,status=simulate(self.curve,0,18,False,0,1,self.c,constant_H=8)
        self.assertEqual(status,0);self.assertEqual(tr.trace[-1,1],0)
        self.assertAlmostEqual(tr.fuel,0.5*(18/12)**3,places=7)
        self.assertLessEqual(len(tr.trace),3)

    def test_recovery_after_waves_drop(self):
        from types import SimpleNamespace
        # Constant storm centre at origin: 8m -> 8m -> 0m; same command throughout.
        f=SimpleNamespace(anchor_times=np.array([0.,1.,2.,3.]),states=np.zeros((9,4,3)))
        f.states[:,:,2]=np.array([.8,.8,0,0])
        tr,status=simulate(self.curve,0,18,False,0,3,self.c,forecast=f)
        self.assertEqual(status,0)
        self.assertEqual(tr.trace[np.searchsorted(tr.trace[:,0],.9),2],0)
        self.assertGreater(tr.trace[-1,2],17)
        self.assertGreater(tr.trace[-1,1],10)

    def test_different_weather_same_command_different_actual_motion(self):
        a,_=simulate(self.curve,0,18,False,0,1,self.c,constant_H=0)
        b,_=simulate(self.curve,0,18,False,0,1,self.c,constant_H=4)
        self.assertGreater(a.trace[-1,1],b.trace[-1,1]);self.assertGreater(a.trace[-1,2],b.trace[-1,2])

    def test_terminal_braking_preserves_exact_goal_and_zero_speed(self):
        curve=make_curve([0,0],[18,0],0,0,self.c)
        tr,status=simulate(curve,0,12,True,0,5,self.c,constant_H=0)
        self.assertEqual(status,1);self.assertAlmostEqual(tr.trace[-1,1],18,places=5)
        self.assertAlmostEqual(tr.trace[-1,2],0,places=4)

    def test_equilibrium_force_balance(self):
        veq=np.sqrt(18**2-9*4**2)
        self.assertAlmostEqual(acceleration(veq,18,4,9,.25,12,24,24),0,places=10)

    def test_steering_constraints_still_apply(self):
        curve=make_curve([0,0],[9,9*np.sqrt(3)],0,np.pi/3,self.c)
        tr,status=simulate(curve,18,18,False,0,3,self.c,constant_H=0)
        self.assertEqual(status,-2)

    def test_time_and_speed_value_interpolation(self):
        from hex_dss.drive_dp import value_at
        V=np.full((2,24),np.inf);V[0,:4]=[0,6,12,18];V[1,:4]=[10,16,22,28]
        self.assertAlmostEqual(value_at(V,.5,0,9),14)
        V[1,1]=np.inf
        self.assertTrue(np.isinf(value_at(V,.5,0,9)))

    def test_dp_transfer_recovers_after_temporary_stall(self):
        from hex_dss.drive_dp import transfer
        from hex_dss.drive_motion import steering_caps,parameters
        curve=make_curve([0,0],[18,0],0,0,self.c)
        calm,status=simulate(curve,0,18,False,0,12,self.c,constant_H=0)
        self.assertEqual(status,1)
        table=np.zeros((1,21,4));table[0,0]=[1,calm.duration,calm.trace[-1,2],calm.fuel]
        fields=np.zeros((20,1),np.float32);fields[0,0]=8
        status,T,v,F=transfer(0,0,0.,table,fields,np.array([curve.s]),np.array([steering_caps(curve,self.c)]),
                              np.array([curve.xy[:,0]]),np.array([curve.xy[:,1]]),np.array([18.]),np.array([False]),np.array([0.]),
                              parameters(self.c),.5,12.,self.c['propulsion']['integration_h'])
        self.assertEqual(status,1);self.assertGreater(T,calm.duration+.9);self.assertGreater(v,15)
        coarse=transfer(0,0,0.,table,fields,np.array([curve.s]),np.array([steering_caps(curve,self.c)]),
                        np.array([curve.xy[:,0]]),np.array([curve.xy[:,1]]),np.array([18.]),np.array([False]),np.array([0.]),
                        parameters(self.c),.5,12.,1/12)
        self.assertEqual(coarse[0],1);self.assertLess(abs(coarse[1]-T),.1)

    def test_new_dp_tiny_dag_cost(self):
        from hex_dss.drive_dp import backward_drive
        from hex_dss.drive_motion import parameters
        from numba import set_num_threads
        set_num_threads(2)
        ptr=np.zeros(49,np.int32);ptr[1:]=1
        dst=np.array([24],np.int32);gid=np.array([0],np.int32);tid=np.array([0],np.int32)
        table=np.zeros((1,21,4));table[:]=[1,1.,0.,1.]
        s=np.array([[0.,18.]]);cap=np.array([[18.,18.]]);x=s.copy();y=np.zeros_like(s)
        V=backward_drive(ptr,dst,gid,tid,table,np.zeros((10,1),np.float32),s,cap,x,y,np.array([12.]),np.array([True]),np.array([0.]),
                         parameters(self.c),8,.25,0.,100.,1000.,1,1.,.5,12.,1/12,100.,20.)
        # Independent enumeration: immediate connector costs 1t*100 + 1h*20;
        # each possible wait strictly increases that cost.
        self.assertAlmostEqual(V[0,0],min(120+n for n in range(5)))
        self.assertTrue(np.isinf(V[5,0]))
        counters=np.zeros((48,5),np.int64)
        W=backward_drive(ptr,dst,gid,tid,table,np.zeros((10,1),np.float32),s,cap,x,y,np.array([12.]),np.array([True]),np.array([0.]),
                         parameters(self.c),8,.25,0.,100.,1000.,1,1.,.5,12.,1/12,100.,20.,counters)
        np.testing.assert_array_equal(V,W)
        self.assertEqual(counters[:,0].sum(),8);self.assertEqual(counters[:,1].sum(),8)


if __name__=='__main__':unittest.main()
