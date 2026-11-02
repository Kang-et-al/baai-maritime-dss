import copy
import math
import unittest
import numpy as np
from hex_dss.config import load
from hex_dss.motion import make_curve,make_profile,Trajectory
from hex_dss.weather import World,Forecast,Observation
from hex_dss.executor import execute
from hex_dss.dp import backward
from hex_dss.risk import discrete_cost_risk


class MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=load();cls.curve=make_curve([0,0],[18,0],0,0,cls.c)

    def test_exact_distance_time_and_end_speed(self):
        p=make_profile(self.curve,12,18,18,0,self.c)
        self.assertIsNotNone(p)
        self.assertAlmostEqual(p.times[-1],p.duration,places=7)
        self.assertAlmostEqual(p.duration/self.c['time_step_h'],round(p.duration/self.c['time_step_h']),places=7)
        self.assertAlmostEqual(float(np.sum((p.speeds[:-1]+p.speeds[1:])/2*np.diff(p.times))),18,places=7)
        self.assertAlmostEqual(p.speeds[0],12);self.assertAlmostEqual(p.speeds[-1],18)

    def test_bounded_acceleration(self):
        for start,end in [(0,18),(18,0),(6,12),(12,6)]:
            p=make_profile(self.curve,start,end,18,0,self.c)
            self.assertIsNotNone(p)
            a=np.diff(p.speeds)/np.diff(p.times)
            self.assertLessEqual(a.max(),24+1e-6);self.assertGreaterEqual(a.min(),-24-1e-6)

    def test_no_instantaneous_acceleration(self):
        p=make_profile(self.curve,0,18,18,0,self.c);tr=Trajectory(self.curve,p,7+23/60)
        _,v,_=tr.sample(tr.start_h+1/3600)
        self.assertGreater(v,0);self.assertLess(v,0.1)

    def test_weather_cap_makes_endpoint_infeasible(self):
        self.assertIsNone(make_profile(self.curve,18,18,18,2,self.c))
        p=make_profile(self.curve,0,6,18,2,self.c)
        self.assertIsNotNone(p);self.assertLessEqual(p.speeds.max(),6+1e-7)

    def test_curved_heading_and_turn_limits(self):
        curve=make_curve([0,0],[9,9*math.sqrt(3)],0,math.pi/3,self.c)
        self.assertIsNotNone(curve)
        p=make_profile(curve,6,6,12,0,self.c);self.assertIsNotNone(p)
        self.assertGreater(curve.length,18)
        self.assertAlmostEqual(curve.heading[0],0);self.assertAlmostEqual(curve.heading[-1],math.pi/3)
        self.assertLessEqual(np.max(abs(curve.k)*p.speeds),math.radians(6)*60+1e-6)

    def test_arbitrary_interrupt_preserves_state(self):
        c=copy.deepcopy(self.c);c['mode']='calm'
        start=7+23/60;p=make_profile(self.curve,6,12,12,0,c);tr=Trajectory(self.curve,p,start)
        state={'time_h':start,'x_nm':0.,'y_nm':0.,'speed_kn':6.,'heading_deg':0.}
        after,ex=execute(state,tr,World(c),c,start+0.137)
        xy,u,h=tr.sample(start+0.137)
        self.assertAlmostEqual(after['time_h'],start+0.137)
        self.assertAlmostEqual(after['x_nm'],xy[0]);self.assertAlmostEqual(after['speed_kn'],u)
        self.assertGreater(after['x_nm'],0);self.assertLess(after['x_nm'],18)
        resumed,ex2=execute(after,tr,World(c),c)
        direct,ex3=execute(state,tr,World(c),c)
        self.assertAlmostEqual(resumed['x_nm'],direct['x_nm']);self.assertAlmostEqual(resumed['speed_kn'],direct['speed_kn'])
        # Numerical fuel quadrature differs only below integration tolerance.
        self.assertAlmostEqual(resumed['fuel_t'],direct['fuel_t'],places=4)

    def test_deceleration_has_no_accel_surcharge(self):
        p=make_profile(self.curve,18,0,18,0,self.c)
        self.assertLessEqual(np.diff(p.speeds).max(),1e-7)

    def test_serialized_trajectory_roundtrip(self):
        p=make_profile(self.curve,6,12,12,0,self.c);a=Trajectory(self.curve,p,7.12345);b=Trajectory.from_dict(a.as_dict())
        for t in np.linspace(a.start_h,a.start_h+p.duration,31):
            for av,bv in zip(a.sample(t),b.sample(t)):np.testing.assert_allclose(av,bv,atol=1e-10)


class InformationTests(unittest.TestCase):
    def test_future_world_change_cannot_change_forecast(self):
        c=load();changed=copy.deepcopy(c);changed['typhoon_waypoints'][1:]=[[12,140,10,1],[24,145,5,1]]
        a=Forecast(World(c).observe(0),c);b=Forecast(World(changed).observe(0),c)
        np.testing.assert_array_equal(a.states,b.states)

    def test_observation_never_reads_forward(self):
        world=World(load());obs=world.observe(7+23/60)
        self.assertLessEqual(obs.times.max(),7+23/60)
        self.assertGreaterEqual(obs.times.min(),0)

    def test_forecasts_match_current_observation(self):
        c=load();obs=World(c).observe(7+23/60);f=Forecast(obs,c)
        for s in range(9):np.testing.assert_allclose(f.storm(s,obs.now),obs.storms[-1])

    def test_swept_box_is_conservative(self):
        c=load();f=Forecast(World(c).observe(0),c)
        centre=f.initial[:2]/1.852;box=np.r_[centre-20,centre+20][None,:]
        bound=f.bounds(box,4)[0,0]
        for t in np.linspace(0,1,15):
            for xy in [centre,centre+[20,20],centre-[20,20]]:
                from hex_dss.weather import band
                self.assertLessEqual(int(band(f.at(4,xy,t))),bound)


class DPTests(unittest.TestCase):
    def tiny(self,weather=0):
        ptr=np.zeros(49,dtype=np.int32);ptr[1:]=1
        dst=np.array([24],np.int32);gid=np.array([0],np.int32);tid=np.array([0],np.int32)
        steps=np.array([[2,3,4]],np.int16);cost=np.array([[10.,20.,30.]])
        field=np.full((8,1),weather,dtype=np.uint8);nb=np.zeros((8,2),np.uint8)
        return backward(ptr,dst,gid,tid,steps,cost,field,nb,12,.25,0.,100.,1000.,1,1.)

    def test_dp_matches_independent_tiny_enumeration(self):
        V=self.tiny();self.assertEqual(V[0,0],min([10,20,30]))
        self.assertTrue(np.isinf(V[11,0]));self.assertEqual(V[10,0],10)

    def test_weather_filters_actions(self):
        self.assertEqual(self.tiny(1)[0,0],20)
        self.assertEqual(self.tiny(2)[0,0],30)
        self.assertTrue(np.isinf(self.tiny(3)[0,0]))

    def test_nonzero_speed_cannot_free_wait(self):
        V=self.tiny();self.assertTrue(np.isinf(V[0,1]))

    def test_lambda_zero_and_cvar_diagnostic(self):
        r=discrete_cost_risk([10,20,100],[1/3]*3,.8)
        self.assertAlmostEqual(r.mean,130/3);self.assertAlmostEqual(r.cvar,100)

    def test_total_cost_risk_includes_first_stage(self):
        p=np.ones(3)/3
        a=discrete_cost_risk(np.array([1.,2,3])+np.array([10.,20,30]),p,.8)
        b=discrete_cost_risk(np.array([10.,20,30]),p,.8)
        self.assertGreater(a.mean,b.mean);self.assertGreater(a.cvar,b.cvar)


if __name__=='__main__':unittest.main()
