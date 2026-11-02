"""State lattice actions and their continuous, time-aligned motion profiles."""
import time
import numpy as np
from .motion import make_profile


class Lattice:
    def __init__(self,net,c):
        started=time.perf_counter(); self.net=net; self.c=c
        self.types=[];self.profiles=[];cache={}; actions=[]
        for gid,(i,h,j,dh,rel,terminal) in enumerate(net.records):
            curve=net.curves[gid]
            shape=rel if not terminal else ('terminal',gid)
            for vi,u0 in enumerate(c['speeds_kn']):
                for ve,u1 in enumerate(c['speeds_kn']):
                    if terminal and ve!=0: continue
                    # The continuous turn profile itself must satisfy endpoint limits.
                    unique=set()
                    for cruise in [6.,12.,18.]:
                        key=(shape,vi,ve,cruise)
                        if key not in cache:
                            pp=[make_profile(curve,u0,u1,cruise,b,c) for b in range(3)]
                            sig=tuple(None if p is None else (round(p.duration,8),round(p.fuel,8)) for p in pp)
                            if all(p is None for p in pp): cache[key]=None
                            else:
                                tid=len(self.types); cache[key]=tid;self.types.append((vi,ve,cruise,sig));self.profiles.append(pp)
                        tid=cache[key]
                        if tid is None: continue
                        sig=self.types[tid][3]
                        if sig in unique: continue
                        unique.add(sig)
                        actions.append((i*24+h*4+vi,j*24+dh*4+ve,gid,tid))
        a=np.asarray(actions,dtype=np.int32)
        order=np.argsort(a[:,0],kind='stable'); a=a[order]
        self.src,self.dst,self.gid,self.tid=a.T.copy()
        self.nstate=net.n*24
        self.ptr=np.r_[0,np.cumsum(np.bincount(self.src,minlength=self.nstate))].astype(np.int32)
        self.steps=np.zeros((len(self.profiles),3),dtype=np.int16)
        self.cost=np.full((len(self.profiles),3),np.inf)
        for tid,pp in enumerate(self.profiles):
            for b,p in enumerate(pp):
                if p is not None:
                    self.steps[tid,b]=round(p.duration/c['time_step_h'])
                    self.cost[tid,b]=p.fuel*c['fuel_usd_per_t']+p.duration*c['time_usd_per_h']
        self.build_seconds=time.perf_counter()-started

    def profile_for(self,action,b):
        return self.profiles[self.tid[action]][b]

