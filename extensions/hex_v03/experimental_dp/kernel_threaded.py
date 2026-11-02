"""Exact demand DFS with certified nonnegative-cost bounds and lazy actions.

Every finite incumbent is an evaluated action with ALL positive interpolation
successors solved. Pruning is conservative (never epsilon-approximate).
"""
import math
import numpy as np
from numba import njit
from hex_dss.drive_dp import transfer


@njit(cache=True,nogil=True)
def children(tindex,base,v,K):
    ids=np.full(4,-1,np.int64);ws=np.zeros(4)
    if tindex>K+1e-8:return ids,ws
    tindex=max(0.,min(float(K),tindex));lo=int(math.floor(tindex));hi=min(lo+1,K);wt=tindex-lo
    v=max(0.,min(18.,v));iv=min(2,int(math.floor(v/6)));wv=(v-iv*6)/6
    n=0
    for tt,tw in [(lo,1-wt),(hi,wt)]:
        if tw<1e-10:continue
        for vv,vw in [(iv,1-wv),(iv+1,wv)]:
            if vw<1e-10:continue
            ids[n]=tt;ws[n]=tw*vw;n+=1
    # Return time and speed separately encoded as time*4+speed offset.
    n=0
    for tt,tw in [(lo,1-wt),(hi,wt)]:
        if tw<1e-10:continue
        for vv,vw in [(iv,1-wv),(iv+1,wv)]:
            if vw<1e-10:continue
            ids[n]=tt*4+vv;n+=1
    return ids,ws


@njit(cache=True,nogil=True)
def demand(V,root_k,root_st,ptr,dst,gid,tid,tables,fields,samples,caps,x,y,commands,stops,initial_speeds,params,
           K,dt,now,due,late,goal,waitcost,hstep,max_h,dt_int,fuelprice,timeprice,order,lengths,node_lb,counters,stats,bounded=True):
    if not np.isnan(V[root_k,root_st]):stats[1]+=1;return V[root_k,root_st]
    # Explicit frames avoid Python recursion and keep pending transitions reusable.
    ks=np.empty(K+2,np.int64);sts=ks.copy();nxt=ks.copy();pending=ks.copy()
    best=np.empty(K+2);costs=best.copy();ci=np.empty((K+2,4),np.int64);cw=np.zeros((K+2,4))
    depth=0;ks[0]=root_k;sts[0]=root_st;nxt[0]=-2;pending[0]=0
    while depth>=0:
        k=ks[depth];st=sts[depth]
        if nxt[depth]==-2:
            if not np.isnan(V[k,st]):stats[1]+=1;depth-=1;continue
            stats[0]+=1
            if st//24==goal:
                V[k,st]=late*max(0.,now+k*dt-due);depth-=1;continue
            if k==K:
                V[k,st]=np.inf;depth-=1;continue
            best[depth]=np.inf;nxt[depth]=ptr[st]
        if pending[depth]:
            lower=costs[depth];unknown=-1
            for m in range(4):
                if ci[depth,m]<0:continue
                child=ci[depth,m];ck=child//V.shape[1];cs=child%V.shape[1];val=V[ck,cs]
                if np.isnan(val):
                    val=max(0.,(1-1e-9)**(K-ck)*node_lb[cs//24]-1e-6) if bounded else 0.
                    if unknown<0:unknown=m
                lower+=cw[depth,m]*val
            if bounded and lower>best[depth]+1e-7:
                stats[3]+=1;pending[depth]=0;continue
            if unknown>=0:
                child=ci[depth,unknown];depth+=1
                if depth>K:raise ValueError('Non-forward time dependency')
                ks[depth]=child//V.shape[1];sts[depth]=child%V.shape[1];nxt[depth]=-2;pending[depth]=0;continue
            if lower<best[depth]:best[depth]=lower
            pending[depth]=0;continue
        idx=nxt[depth]
        if idx==ptr[st+1]:
            nxt[depth]+=1
            if st%4==0:
                ci[depth,:]=-1;cw[depth,:]=0.;ci[depth,0]=(k+1)*V.shape[1]+st;cw[depth,0]=1.
                costs[depth]=waitcost;pending[depth]=1
            continue
        if idx>ptr[st+1]:
            V[k,st]=best[depth];depth-=1;continue
        nxt[depth]+=1;a=order[idx];tp=tid[a];gg=gid[a]
        # No future score is assumed here: minimum physical operating cost +
        # discounted distance bound at destination (same node for all successors).
        cheap=(timeprice+fuelprice*params[6])*lengths[gg]/18.+max(0.,(1-1e-9)**K*node_lb[dst[a]//24]-1e-6)
        if bounded and cheap>best[depth]+1e-7:stats[2]+=1;continue
        status,T,v,F=transfer(tp,gg,k*dt,tables,fields,samples,caps,x,y,commands,stops,initial_speeds,params,hstep,max_h,dt_int,counters)
        if status!=1 or k+T/dt>K:continue
        ids,ws=children(k+T/dt,dst[a],v,K);ci[depth,:]=-1;cw[depth,:]=0.
        for m in range(4):
            if ids[m]<0:continue
            ck=ids[m]//4;cs=dst[a]+ids[m]%4
            if ck<=k:raise ValueError('Transition must advance at least one time layer')
            ci[depth,m]=ck*V.shape[1]+cs;cw[depth,m]=ws[m]
        costs[depth]=F*fuelprice+T*timeprice;pending[depth]=1
    return V[root_k,root_st]


def prepare(lat,c):
    distances=np.linalg.norm(lat.net.xy-lat.net.xy[lat.net.goal],axis=1)
    lengths=np.array([g.length for g in lat.net.curves])
    if lengths.min()/18<c['time_step_h']-1e-9:raise ValueError('Short edge: DAG bound requires revalidation')
    node_lb=(c['time_usd_per_h']+c['fuel_usd_per_t']*c['fuel_wait_tph'])*distances/18
    order=np.arange(len(lat.src),dtype=np.int64)
    for st in range(lat.nstate):
        lo,hi=lat.ptr[st:st+2]
        aa=order[lo:hi]
        # Ordering only, NOT a bound; never removes a control.
        rank=lat.tables[lat.tid[aa],0,3]*c['fuel_usd_per_t']+lat.tables[lat.tid[aa],0,1]*c['time_usd_per_h']+distances[lat.dstbase[aa]//24]*70
        order[lo:hi]=aa[np.argsort(rank,kind='stable')]
    return order,lengths,node_lb


class Evaluator:
    def __init__(self,lat,fields,c,now,bounded=True,prepared=None):
        self.lat=lat;self.c=c;self.now=now;self.K=round(c['horizon_h']/c['time_step_h']);self.fields=fields
        self.V=np.full((self.K+1,lat.nstate),np.nan);self.counters=np.zeros(5,np.int64);self.stats=np.zeros(4,np.int64)
        self.order,self.lengths,self.lb=prepared or prepare(lat,c);self.bounded=bounded
    def query(self,tindex,base,v):
        ids,ws=children(tindex,base,v,self.K)
        if ids[0]<0:return float('inf')
        total=0.
        a=self.lat;c=self.c;p=c['propulsion']
        for item,w in zip(ids,ws):
            if item<0:continue
            val=demand(self.V,item//4,base+item%4,a.ptr,a.dstbase,a.gid,a.tid,a.tables,self.fields,a.type_curve_s,a.type_caps,a.type_x,a.type_y,
                a.commands,a.stops,a.initial_speeds,a.params,self.K,c['time_step_h'],self.now,c['due_h'],c['late_usd_per_h'],a.net.goal,
                (c['fuel_wait_tph']*c['fuel_usd_per_t']+c['time_usd_per_h'])*c['time_step_h'],p['wave_table_step_m'],p['transition_limit_h'],p['dp_integration_h'],
                c['fuel_usd_per_t'],c['time_usd_per_h'],self.order,self.lengths,self.lb,self.counters,self.stats,self.bounded)
            if not np.isfinite(val):return float('inf')
            total+=w*val
        return float(total)
