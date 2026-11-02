"""Semi-Lagrangian time/speed value interpolation; no physical state snapping."""
import math
import numpy as np
from numba import njit,prange
from .drive_motion import integrate


@njit(cache=True)
def value_at(V,tindex,base,v):
    if tindex>len(V)-1+1e-8:return np.inf
    tindex=max(0.,min(len(V)-1.,tindex));lo=int(math.floor(tindex));hi=min(lo+1,len(V)-1);wt=tindex-lo
    v=max(0.,min(18.,v));iv=min(2,int(math.floor(v/6)));wv=(v-iv*6)/6
    result=0.
    for tt,tw in [(lo,1-wt),(hi,wt)]:
        if tw<1e-10:continue
        for vv,vw in [(iv,1-wv),(iv+1,wv)]:
            if vw<1e-10:continue
            a=V[tt,base+vv]
            if not np.isfinite(a):return np.inf
            result+=tw*vw*a
    return result


@njit(cache=True)
def transfer(tid,gid,start_rel,tables,fields,samples,caps,x,y,commands,stops,initial_speeds,params,hstep,max_h,dt_int,metrics=None):
    if metrics is not None:metrics[0]+=1
    # Fixed-point conservative whole-curve height. No rejection at a wave threshold.
    row=tables[tid,0];T=row[1];v=row[2];F=row[3]
    if not np.isfinite(T):return -2,0.,0.,0.
    b=0
    for _ in range(6):
        h0=int(math.floor(start_rel+1e-9));h1=min(fields.shape[0]-1,int(math.floor(start_rel+T+1e-9)))
        H=0.
        for hour in range(h0,h1+1):H=max(H,fields[hour,gid])
        nb=min(tables.shape[1]-1,int(math.ceil(H/hstep-1e-9)))
        if nb==b:
            if metrics is not None:metrics[1]+=1
            return 1,T,v,F
        b=max(b,nb);row=tables[tid,b]
        if row[0]!=1:break
        T=row[1];v=row[2];F=row[3]
    # A stalled constant-height transfer can still recover as the storm moves.
    dummy=np.array([0.,1.]);st=np.zeros((2,3))
    if metrics is not None:metrics[2]+=1
    status,T,v,F,pos,_trace=integrate(samples[tid],x[tid],y[tid],caps[tid],initial_speeds[tid],commands[tid],stops[tid],start_rel,max_h,
                                     params,2,0.,dummy,st,fields[:,gid],dt_int,False,metrics)
    return status,T,v,F


@njit(cache=True,parallel=True)
def backward_drive(ptr,dst,gid,tid,tables,fields,samples,caps,x,y,commands,stops,initial_speeds,params,
                   K,dt,now,due,late,goal,waitcost,hstep,max_h,dt_int,fuelprice,timeprice,metrics=None):
    N=len(ptr)-1;V=np.full((K+1,N),np.inf)
    for q in range(K+1):
        for st in range(goal*24,(goal+1)*24):V[q,st]=late*max(0.,now+q*dt-due)
    for q in range(K-1,-1,-1):
        for st in prange(N):
            if st//24==goal:continue
            best=np.inf
            if st%4==0:best=waitcost+V[q+1,st]
            for a in range(ptr[st],ptr[st+1]):
                tp=tid[a]
                local_metrics=None if metrics is None else metrics[st]
                status,T,v,F=transfer(tp,gid[a],q*dt,tables,fields,samples,caps,x,y,commands,stops,initial_speeds,params,hstep,max_h,dt_int,local_metrics)
                if status!=1 or q+T/dt>K:continue
                future=value_at(V,q+T/dt,dst[a],v)
                candidate=F*fuelprice+T*timeprice+future
                if candidate<best:best=candidate
            V[q,st]=best
    return V
