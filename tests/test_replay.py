import tempfile
import unittest
from pathlib import Path
import numpy as np
from maritime_sim.config import ROOT,load_config
from maritime_sim.weather import wave,contour_radius
from maritime_sim.simulation import Simulation
from maritime_sim.network import Network
from maritime_sim.replay import build_payload,export_replay
from maritime_sim.simulation import read_json,save_json


class ReplayTests(unittest.TestCase):
    def test_dynamic_radius_and_contour_agree_with_wave(self):
        c=load_config(ROOT/'configs'/'korea_china_crossing.json')
        for intensity in [.3,.6,1]:
            radius=contour_radius(intensity,2,c)
            z=np.array([0.,0.,intensity])
            h=wave(np.array([[radius,0]]),z,c)[0]
            self.assertAlmostEqual(h,2,places=9)
        r1=contour_radius(.6,2,c);r2=contour_radius(1,2,c)
        self.assertGreater(r2,r1)
        self.assertEqual(float(wave(np.array([[0.,0.]]),np.array([0.,0.,0.]),c)[0]),0)

    def test_replay_has_initial_and_terminal_without_future_leak(self):
        c=load_config();c['mode']='calm';c['horizon_h']=12
        n=Network();g=n.index[c['goal_node']]
        c['start_node']=int(n.ids[n.adj[g][0][0]])
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as tmp:
            s=Simulation(c,Path(tmp)/'run');s.run(1,render=False,experiment_format='replay')
            payload=build_payload(s.output)
            self.assertEqual(payload['format'],'replay')
            self.assertEqual(len(payload['frames']),2)
            self.assertEqual(payload['frames'][0]['time'],0)
            self.assertTrue(payload['frames'][-1]['terminal'])
            self.assertEqual(payload['frames'][-1]['future'],[])
            self.assertEqual(payload['frames'][-1]['first'],[])
            self.assertEqual(payload['frames'][0]['objective_type'],'mean_cvar')
            self.assertEqual(payload['frames'][0]['risk_lambda'],c['risk']['lambda'])
            self.assertEqual(payload['frames'][0]['cvar_alpha'],c['risk']['alpha'])
            self.assertIn('objective_at_decision_usd',(s.output/'summary.csv').read_text(encoding='utf-8-sig'))
            text=(s.output/'dashboard.html').read_text(encoding='utf-8')
            self.assertIn('type="range"',text)
            self.assertNotIn('location.reload()',text)
            self.assertNotIn('__REPLAY_DATA__',text)

            # Emulate a saved legacy record only inside this temporary test directory.
            # A mean-only historical record must never inherit today's risk settings.
            record_path=s.output/'steps'/'step_001.json'
            record=read_json(record_path)
            for key in ['objective_type','objective_total_usd','risk_lambda','cvar_alpha',
                        'mean_remaining_usd','cvar_remaining_usd','risk_adjusted_remaining_usd','cvar_tail_weights']:
                record['plan'].pop(key,None)
            save_json(record_path,record)
            legacy=read_json(s.output/'config.json')
            for key in ['baseline_id','scenario_generator','risk']:legacy.pop(key,None)
            legacy['schema_version']=1;save_json(s.output/'config.json',legacy)
            archived=build_payload(s.output)
            self.assertEqual(archived['baseline_id'],'legacy-expectation')
            self.assertEqual(archived['frames'][0]['objective_type'],'expectation')
            self.assertIsNone(archived['frames'][0]['cvar_future'])
            self.assertIsNone(archived['frames'][0]['risk_lambda'])


if __name__=='__main__':unittest.main()
