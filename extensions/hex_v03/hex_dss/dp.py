"""Scenario-separated exact DP over the finite set of feasible motion primitives."""
import math
import numpy as np
from numba import njit


@njit(cache=True)
def interval_band(fields,g,h0,h1):
    worst=0
    for hour in range(h0,h1+1):
        if hour>=fields.shape[0]: return 3
        v=fields[hour,g]
        if v>worst: worst=v
    return worst


@njit(cache=True)
def backward(ptr,dst,gid,tid,steps,cost,fields,node_bands,K,dt,now,due,late,goal,waitcost):
    N=len(ptr)-1
    V=np.full((K+1,N),np.inf)
    for q in range(K+1):
        v=late*max(0.,now+q*dt-due)
        for st in range(goal*24,(goal+1)*24): V[q,st]=v
    for q in range(K-1,-1,-1):
        hour=int(math.floor(q*dt+1e-9))
        nh=int(math.floor((q+1)*dt+1e-9))
        for st in range(N):
            if st//24==goal: continue
            if node_bands[hour,st//24]>=3: continue
            best=np.inf
            if st%4==0 and node_bands[nh,st//24]<3:
                best=waitcost+V[q+1,st]
            for a in range(ptr[st],ptr[st+1]):
                tp=tid[a]; g=gid[a]; destination=dst[a]
                for b in range(3):
                    m=steps[tp,b]
                    if m<=0 or q+m>K: continue
                    future=V[q+m,destination]
                    if not np.isfinite(future): continue
                    endhour=int(math.floor((q+m)*dt+1e-9))
                    if interval_band(fields,g,hour,endhour)>b: continue
                    candidate=cost[tp,b]+future
                    if candidate<best: best=candidate
            V[q,st]=best
    return V


@njit(cache=True)
def best_action(st,q,V,ptr,dst,gid,tid,steps,cost,fields,node_bands,dt,waitcost):
    best=np.inf; which=-2; band=-1; endq=-1
    hour=int(math.floor(q*dt+1e-9))
    if st%4==0 and q+1<len(V) and node_bands[int(math.floor((q+1)*dt+1e-9)),st//24]<3:
        best=waitcost+V[q+1,st];which=-1;endq=q+1
    for a in range(ptr[st],ptr[st+1]):
        tp=tid[a];g=gid[a]
        for b in range(3):
            m=steps[tp,b]
            if m<=0 or q+m>=len(V):continue
            endhour=int(math.floor((q+m)*dt+1e-9))
            if interval_band(fields,g,hour,endhour)>b:continue
            value=cost[tp,b]+V[q+m,dst[a]]
            if value<best:best=value;which=a;band=b;endq=q+m
    return best,which,band,endq


def recover(lattice,V,fields,node_bands,state,q,now):
    c=lattice.c;dt=c['time_step_h'];waitcost=(c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*dt
    path=[];total=0.
    while state//24!=lattice.net.goal and q<len(V)-1:
        value,a,b,nq=best_action(state,q,V,lattice.ptr,lattice.dst,lattice.gid,lattice.tid,lattice.steps,lattice.cost,fields,node_bands,dt,waitcost)
        if not np.isfinite(value): return None
        if not np.isclose(value,V[q,state],atol=1e-6,rtol=1e-9): raise RuntimeError('DP/reconstruction mismatch')
        path.append({'action':int(a),'band':int(b),'start_h':now+q*dt,'end_h':now+nq*dt,'from_state':int(state)})
        total+=waitcost if a==-1 else lattice.cost[lattice.tid[a],b]
        if a>=0:state=int(lattice.dst[a])
        q=int(nq)
    if state//24!=lattice.net.goal:return None
    terminal=c['late_usd_per_h']*max(0,now+q*dt-c['due_h'])
    return {'actions':path,'arrival_h':now+q*dt,'operating_cost_usd':float(total),'late_cost_usd':terminal}
