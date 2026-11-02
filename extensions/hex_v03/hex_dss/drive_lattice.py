"""Commands, not endpoint speeds, are the action choices in this lattice."""
import math
import time
import numpy as np
from .drive_motion import simulate,steering_caps,parameters


class DriveLattice:
    def __init__(self,net,c,progress=print):
        started=time.perf_counter();self.net=net;self.c=c;self.nstate=net.n*24
        self.waves=np.arange(0,c['propulsion']['wave_table_max_m']+1e-9,c['propulsion']['wave_table_step_m'])
        self.types=[];self.curve_types=[];self.tables=[];cache={};actions=[]
        for gid,(i,h,j,dh,rel,terminal) in enumerate(net.records):
            curve=net.curves[gid];shape=rel if not terminal else ('terminal',gid)
            cap0=steering_caps(curve,c)[0]
            for vi,v0 in enumerate(c['speeds_kn']):
                if v0>cap0+1e-7:continue
                for command in [6.,12.,18.]:
                    for stop in [False,True]:
                        if terminal and not stop:continue
                        key=(shape,vi,command,stop)
                        if key not in cache:
                            table=np.full((len(self.waves),4),np.nan)
                            anyvalid=False
                            for b,H in enumerate(self.waves):
                                tr,status=simulate(curve,v0,command,stop,0,c['propulsion']['transition_limit_h'],c,constant_H=H)
                                if status==1:
                                    table[b]=[1,tr.duration,tr.trace[-1,2],tr.fuel];anyvalid=True
                                else:table[b,0]=status
                            if not anyvalid:cache[key]=None
                            else:
                                tid=len(self.types);cache[key]=tid;self.types.append((vi,command,stop));self.curve_types.append(curve);self.tables.append(table)
                        tid=cache[key]
                        if tid is not None:actions.append((i*24+h*4+vi,j*24+dh*4,gid,tid))
        a=np.array(actions,np.int32);a=a[np.argsort(a[:,0],kind='stable')]
        self.src,self.dstbase,self.gid,self.tid=a.T.copy()
        self.ptr=np.r_[0,np.cumsum(np.bincount(self.src,minlength=self.nstate))].astype(np.int32)
        self.tables=np.asarray(self.tables)
        self.type_curve_s=np.array([g.s for g in self.curve_types])
        self.type_x=np.array([g.xy[:,0] for g in self.curve_types]);self.type_y=np.array([g.xy[:,1] for g in self.curve_types])
        self.type_caps=np.array([steering_caps(g,c) for g in self.curve_types])
        self.commands=np.array([a[1] for a in self.types]);self.stops=np.array([a[2] for a in self.types],dtype=np.bool_)
        self.initial_speeds=np.array([c['speeds_kn'][a[0]] for a in self.types])
        self.params=parameters(c);self.build_seconds=time.perf_counter()-started
        progress(f'Propulsion lattice: {self.nstate} states, {len(self.src)} actions, {len(self.types)} transfer types')
