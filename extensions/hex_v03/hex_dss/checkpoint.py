"""Transactional, identity-checked scenario checkpoints. No model logic here."""
import hashlib,json,os
from pathlib import Path
import numpy as np
from .runtime import save


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()


class ScenarioStore:
    def __init__(self,path,identity):
        self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
        encoded=json.dumps(identity,ensure_ascii=False,sort_keys=True,allow_nan=False)
        key=hashlib.sha256(encoded.encode()).hexdigest();p=self.path/'identity.json'
        if p.exists():
            old=json.loads(p.read_text(encoding='utf-8'))
            if old['key']!=key:raise ValueError('Checkpoint input/code/forecast mismatch: use a new checkpoint folder')
        else:save(p,{'key':key,'identity':identity})
        self.key=key
    def marker(self,s):return self.path/f'scenario_{s:02d}.json'
    def completed(self,s):return self.marker(s).exists()
    def put(self,s,V,fields,metrics):
        if self.completed(s):raise ValueError('Never overwrite completed checkpoint')
        files={}
        for name,data in [('values',V),('fields',fields)]:
            p=self.path/f's{s:02d}_{name}.npy';tmp=p.with_suffix('.npy.tmp')
            with tmp.open('wb') as f:np.save(f,data);f.flush();os.fsync(f.fileno())
            tmp.replace(p);files[name]={'name':p.name,'sha256':file_hash(p),'bytes':p.stat().st_size}
        save(self.marker(s),{'key':self.key,'scenario':s,'files':files,'metrics':metrics})
    def load(self,s):
        d=json.loads(self.marker(s).read_text(encoding='utf-8'))
        if d['key']!=self.key:raise ValueError('Checkpoint key mismatch')
        arrays=[]
        for name in ['values','fields']:
            f=d['files'][name];p=self.path/f['name']
            if p.parent.resolve()!=self.path.resolve():raise ValueError('Invalid checkpoint filename')
            if p.stat().st_size!=f['bytes'] or file_hash(p)!=f['sha256']:raise ValueError('Incomplete/corrupt checkpoint')
            arrays.append(np.load(p,mmap_mode='r'))
        return arrays[0],arrays[1],d['metrics']
    @staticmethod
    def close(*arrays):
        for a in arrays:
            if getattr(a,'_mmap',None) is not None:a._mmap.close()
