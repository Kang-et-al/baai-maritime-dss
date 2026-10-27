"""유한 시간확장 네트워크의 정확한 DP. World/숨겨진 미래를 참조하지 않는다."""
import math
import time
from dataclasses import replace
import numpy as np
from .weather import speed_rule
from .risk import candidate_evaluation


def fuel_rate(speed, c):
    return c["fuel_normal_tph"]*(speed/c["normal_kn"])**3


def action_cost(speed, duration, c, wait=False):
    fuel=(c["fuel_wait_tph"] if wait else fuel_rate(speed,c))*duration
    return c["fuel_usd_per_t"]*fuel+c["time_usd_per_h"]*duration


def action_record(net, i, j, start, duration, speed, factor, c):
    wait=i==j
    return {"from_node":int(net.ids[i]),"to_node":int(net.ids[j]),
            "start_h":float(start),"end_h":float(start+duration),
            "duration_h":float(duration),"command_kn":float(speed),
            "effective_kn":float(speed*factor),"speed_factor":float(factor),
            "mode":"wait" if wait else ("normal" if abs(speed-c["normal_kn"])<1e-7 else "fast" if abs(speed-c["fast_kn"])<1e-7 else "variable"),
            "fuel_t":float((c["fuel_wait_tph"] if wait else fuel_rate(speed,c))*duration),
            "operating_cost_usd":float(action_cost(speed,duration,c,wait))}


class TwoStagePlanner:
    def __init__(self, network, config, due_h):
        self.net=network; self.c=config; self.due=due_h
        self.goal=network.index[config["goal_node"]]
        if not np.allclose(network.dist,config["arc_distance_nm"]):
            raise ValueError("Configured arc distance differs from the network CSV")

    def late(self,t):
        return self.c["late_usd_per_h"]*max(0,t-self.due)

    def first_stage(self,start,now,hn,he):
        c=self.c; net=self.net; dt=c["time_step_h"]
        L=round(c["rolling_h"]/dt); threshold=c["wave_thresholds_m"][-1]
        states=[{} for _ in range(L+1)]; states[0][start]=0.
        pred={}; early=[]
        for q in range(L+1):
            h=int(math.floor(q*dt+1e-9))
            for i,cost in list(states[q].items()):
                if i==self.goal:
                    early.append((cost+self.late(now+q*dt),q,i)); continue
                if q==L or hn[h,i]>=threshold:
                    continue
                if hn[int(math.floor((q+1)*dt+1e-9)),i]<threshold:
                    a=action_record(net,i,i,now+q*dt,dt,0,1,c)
                    self._relax(states,pred,q,i,q+1,i,cost,a)
                for j,e in net.adj[i]:
                    r,cap=speed_rule(he[h,e],c); r=float(r); cap=float(cap)
                    if r<=0: continue
                    for m in range(1,L-q+1):
                        duration=m*dt
                        speed=net.dist[e]/(r*duration)
                        if speed>cap+1e-8: continue
                        if hn[int(math.floor((q+m)*dt+1e-9)),j]>=threshold: continue
                        a=action_record(net,i,j,now+q*dt,duration,speed,r,c)
                        self._relax(states,pred,q,i,q+m,j,cost,a)
        return states[L],pred,early

    @staticmethod
    def _relax(states,pred,q,i,nq,j,cost,a):
        value=cost+a["operating_cost_usd"]
        if value<states[nq].get(j,float("inf"))-1e-8:
            states[nq][j]=value; pred[(nq,j)]=(q,i,a)

    @staticmethod
    def reconstruct_first(pred,q,i):
        actions=[]
        while q>0:
            q,i,a=pred[(q,i)]; actions.append(a)
        return actions[::-1]

    def backward(self,now,forecast,hn,he):
        c=self.c; net=self.net; dt=c["time_step_h"]
        K=round(c["horizon_h"]/dt); L=round(c["rolling_h"]/dt)
        S=len(forecast.probabilities); threshold=c["wave_thresholds_m"][-1]
        V=np.full((S,K+1,net.n),np.inf,dtype=np.float64)
        times=now+np.arange(K+1)*dt
        V[:,:,self.goal]=c["late_usd_per_h"]*np.maximum(times-self.due,0)
        si=np.arange(S)[:,None]
        outgoing=np.full((net.n,max(len(a) for a in net.adj)),len(net.src),dtype=int)
        for i,edges in enumerate(net.adj):
            outgoing[i,:len(edges)]=[e for _,e in edges]
        waitcost=action_cost(0,dt,c,True)
        durations={}
        for speed in [c["normal_kn"],c["fast_kn"]]:
            durations[speed]=sorted({round(c["arc_distance_nm"]/(r*speed*dt)) for r in c["speed_factors"]})
        cached_h=None
        for q in range(K-1,L-1,-1):
            h=int(math.floor(q*dt+1e-9)); nh=int(math.floor((q+1)*dt+1e-9))
            val=V[:,q,:]
            safe=(hn[:,h,:]<threshold)&(hn[:,nh,:]<threshold)
            val[:]=np.where(safe,waitcost+V[:,q+1,:],np.inf)
            if h!=cached_h:
                factor,cap=speed_rule(he[:,h,:],c)
                mode_rules={speed:(np.rint(c["arc_distance_nm"]/(np.where(factor>0,factor,1)*speed*dt)).astype(int),
                                   (factor>0)&(speed<=cap+1e-8))
                            for speed in [c["normal_kn"],c["fast_kn"]]}
                cached_h=h
            for speed in [c["normal_kn"],c["fast_kn"]]:
                duration,allowed=mode_rules[speed]
                end=np.minimum(q+duration,K)
                ah=np.floor(end*dt+1e-9).astype(int)
                arrival_ok=hn[si,ah,net.dst[None,:]]<threshold
                future=V[si,end,net.dst[None,:]]
                candidate=np.where(allowed&(q+duration<=K)&arrival_ok,
                                   action_cost(speed,duration*dt,c)+future,np.inf)
                padded=np.concatenate([candidate,np.full((S,1),np.inf)],axis=1)
                np.minimum(val,np.min(padded[:,outgoing],axis=2),out=val)
            val[hn[:,h,:]>=threshold]=np.inf
            val[:,self.goal]=self.late(now+q*dt)
        return V

    def recover_second(self,V,s,i,q,now,hn,he):
        net=self.net; c=self.c; dt=c["time_step_h"]; K=V.shape[1]-1
        threshold=c["wave_thresholds_m"][-1]; actions=[]
        while i!=self.goal and q<K:
            h=int(math.floor(q*dt+1e-9)); options=[]
            if hn[s,h,i]>=threshold: raise RuntimeError("Unsafe DP reconstruction state")
            for j,e in net.adj[i]:
                r,cap=speed_rule(he[s,h,e],c); r=float(r); cap=float(cap)
                if r<=0: continue
                for speed in [c["normal_kn"],c["fast_kn"]]:
                    if speed>cap+1e-8: continue
                    m=round(net.dist[e]/(r*speed*dt))
                    if q+m>K or hn[s,int(math.floor((q+m)*dt+1e-9)),j]>=threshold: continue
                    a=action_record(net,i,j,now+q*dt,m*dt,speed,r,c)
                    options.append((a["operating_cost_usd"]+V[s,q+m,j],j,m,a))
            if hn[s,int(math.floor((q+1)*dt+1e-9)),i]<threshold:
                a=action_record(net,i,i,now+q*dt,dt,0,1,c)
                options.append((a["operating_cost_usd"]+V[s,q+1,i],i,1,a))
            if not options: raise RuntimeError("DP reconstruction has no action")
            value,j,m,a=min(options,key=lambda x:x[0])
            if not np.isfinite(value) or not np.isclose(value,V[s,q,i],atol=1e-5,rtol=1e-10):
                raise RuntimeError("DP value and recovered path disagree")
            actions.append(a); i=j; q+=m
        if i!=self.goal: raise RuntimeError("Recovered path did not reach destination")
        return actions

    def solve(self,node_id,now,forecast):
        started=time.perf_counter(); c=self.c
        hn,he=forecast.fields(self.net,c)
        candidates,pred,early=self.first_stage(self.net.index[node_id],now,hn[0],he[0])
        L=round(c["rolling_h"]/c["time_step_h"])
        # Early-arrival states are terminal, not regular boundary candidates.
        candidates.pop(self.goal,None)
        V=None
        if candidates:
            # Identical weather scenarios have identical recourse values. Solve once.
            identical=np.array_equal(hn,np.broadcast_to(hn[:1],hn.shape)) and np.array_equal(he,np.broadcast_to(he[:1],he.shape))
            if identical:
                one=replace(forecast,probabilities=np.array([1.]))
                base=self.backward(now,one,hn[:1],he[:1])
                V=np.broadcast_to(base,(len(forecast.probabilities),)+base.shape[1:])
            else:
                V=self.backward(now,forecast,hn,he)
        rows=[]; best=(float("inf"),None)
        for j,firstcost in sorted(candidates.items()):
            second=V[:,L,j]
            evaluation=candidate_evaluation(firstcost,second,forecast.probabilities,c["risk"])
            value=evaluation["objective_total_usd"]
            row={"node":int(self.net.ids[j]),"first_cost_usd":firstcost,
                 "scenario_remaining_costs_usd":[float(x) if np.isfinite(x) else None for x in second],
                 **evaluation}
            rows.append(row)
            if value is not None and value<best[0]-1e-8: best=(value,j)
        earlybest=min(early,key=lambda x:x[0]) if early else None
        output={"candidates":rows,"solve_seconds":time.perf_counter()-started,
                "candidate_count":len(rows),"scenario_routes":[]}
        output.update(candidate_evaluation(0,[float("inf")],np.array([1.]),c["risk"]))
        if earlybest and earlybest[0]<=best[0]+1e-8:
            value,q,j=earlybest
            output.update(status="ok",early_arrival=True,chosen_node=int(self.net.ids[j]),
                          first_actions=self.reconstruct_first(pred,q,j))
            output.update(candidate_evaluation(value,[0.],np.array([1.]),c["risk"]))
        elif best[1] is None:
            output.update(status="infeasible",early_arrival=False,chosen_node=None,
                          first_actions=[],
                          reason="No feasible candidate in all positive-probability scenarios within this finite horizon.")
        else:
            value,j=best
            routes=[self.recover_second(V,s,j,L,now,hn,he) for s in range(len(forecast.probabilities))]
            output.update(status="ok",early_arrival=False,chosen_node=int(self.net.ids[j]),
                          first_actions=self.reconstruct_first(pred,L,j),
                          scenario_routes=routes)
            output.update(candidate_evaluation(candidates[j],V[:,L,j],forecast.probabilities,c["risk"]))
        output["solve_seconds"]=time.perf_counter()-started
        return output
