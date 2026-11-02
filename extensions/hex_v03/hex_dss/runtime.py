import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
import psutil
from .config import ROOT


def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)


def fingerprints():
    paths=sorted((ROOT/'hex_dss').glob('*.py'))+sorted((ROOT/'configs').glob('*.json'))+sorted((ROOT/'data').glob('*.json'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def metadata():
    packages={}
    import importlib.metadata
    for name in ['numpy','Pillow','shapely','numba','psutil']:
        packages[name]=importlib.metadata.version(name)
    def git(*args):
        r=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True)
        return r.stdout.strip() if r.returncode==0 else None
    return {'python':sys.version,'platform':platform.platform(),'packages':packages,'fingerprints':fingerprints(),
            'git':{'commit':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'dirty':bool(git('status','--porcelain'))},
            'baseline_reference':'v0.2.0-draft.1','network_source':'reconstructed hex lattice from copied Natural Earth land snapshot',
            'peak_rss_mb':psutil.Process(os.getpid()).memory_info().peak_wset/2**20 if os.name=='nt' else psutil.Process().memory_info().rss/2**20}

