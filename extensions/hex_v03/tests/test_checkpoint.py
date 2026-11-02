import tempfile,unittest
from pathlib import Path
import numpy as np
from hex_dss.checkpoint import ScenarioStore


class CheckpointTests(unittest.TestCase):
    def test_roundtrip_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            s=ScenarioStore(d,{'input':1});v=np.arange(24.).reshape(6,4);h=np.ones((3,2),np.float32)
            s.put(0,v,h,{'dp_seconds':2.})
            reopened=ScenarioStore(d,{'input':1});a,b,m=reopened.load(0)
            np.testing.assert_array_equal(a,v);np.testing.assert_array_equal(b,h);self.assertEqual(m['dp_seconds'],2.)
            reopened.close(a,b)
            with self.assertRaises(ValueError):reopened.put(0,v,h,{})
    def test_identity_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s=ScenarioStore(d,{'state':3});s.put(0,np.ones((2,2)),np.ones((1,1)),{})
            with self.assertRaises(ValueError):ScenarioStore(d,{'state':4})
            p=Path(d)/'s00_values.npy';raw=bytearray(p.read_bytes());raw[-1]^=1;p.write_bytes(raw)
            with self.assertRaises(ValueError):s.load(0)
    def test_uncommitted_array_is_not_completed(self):
        with tempfile.TemporaryDirectory() as d:
            s=ScenarioStore(d,{});np.save(Path(d)/'s00_values.npy',np.zeros((2,2)))
            self.assertFalse(s.completed(0))

