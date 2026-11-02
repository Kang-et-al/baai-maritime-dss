"""Propulsion commands -> continuous actual speed. No wave speed cap or sea-state ban."""
import math
from dataclasses import dataclass
import numpy as np
from numba import njit
from .motion import Curve


@njit(cache=True)
def acceleration(v,q,H,kappa,tau,vref,up,down):
    a=(q*q-v*v-kappa*H*H)/(2*tau*vref)
    a=min(up,max(-down,a))
    if v<=0 and a<0:return 0.
    return a


@njit(cache=True)
def wave_at(x,y,t,anchors,storms,peak,scale,cutoff):
    j=max(0,min(len(anchors)-2,np.searchsorted(anchors,t)-1))
    w=min(1.,max(0.,(t-anchors[j])/(anchors[j+1]-anchors[j])))
    sx=storms[j,0]*(1-w)+storms[j+1,0]*w
    sy=storms[j,1]*(1-w)+storms[j+1,1]*w
    intensity=storms[j,2]*(1-w)+storms[j+1,2]*w
    d2=(x*1.852-sx)**2+(y*1.852-sy)**2
    if intensity<=0 or d2>(cutoff*intensity)**2:return 0.
    return peak*intensity*math.exp(-d2/(scale*intensity)**2)


@njit(cache=True)
def travel_time(ds,v,a):
    if abs(a)<1e-12:return ds/max(v,1e-12)
    disc=max(0.,v*v+2*a*ds)
    return 2*ds/max(v+math.sqrt(disc),1e-12)


@njit(cache=True)
def integrate(s,x,y,caps,v0,qcommand,stop_at_goal,start_h,max_h,parameters,
              mode,constant_H,anchors,storms,hourly_upper,dt_h,record=False,metrics=None):
    """mode 0 constant H; 1 scenario/world point field; 2 hourly swept-box upper.

    Existing service braking (-down) is retained for terminal stops and steering.
    Wave-induced deceleration follows the force equation; output never jumps.
    """
    kappa,tau,vref,up,down,fuel0,idle,extra,peak,scale,cutoff=parameters
    length=s[-1];v=v0;pos=0.;t=0.;fuel=0.;braking=False
    if v0>caps[0]+1e-6:return -2,0.,v0,0.,0.,np.empty((0,6))
    nmax=int(math.ceil(max_h/dt_h))+20
    trace=np.empty((nmax,6)) if record else np.empty((0,6))
    count=0
    if record:
        initial_H=constant_H
        if mode==1:initial_H=wave_at(x[0],y[0],start_h,anchors,storms,peak,scale,cutoff)
        elif mode==2:initial_H=hourly_upper[max(0,min(len(hourly_upper)-1,int(math.floor(start_h))))]
        trace[0]=np.array([0.,0.,v0,qcommand,initial_H,0.]);count=1
    while t<max_h-1e-10 and pos<length-1e-8:
        if metrics is not None:metrics[3]+=1
        dt=min(dt_h,max_h-t)
        idx=max(0,min(len(s)-2,np.searchsorted(s,pos)-1))
        w=(pos-s[idx])/max(s[idx+1]-s[idx],1e-12)
        px=x[idx]*(1-w)+x[idx+1]*w;py=y[idx]*(1-w)+y[idx+1]*w
        if mode==0:H=constant_H
        elif mode==1:H=wave_at(px,py,start_h+t,anchors,storms,peak,scale,cutoff)
        else:
            rawhour=int(math.floor(start_h+t+1e-9))
            hour=max(0,min(len(hourly_upper)-1,rawhour))
            H=hourly_upper[hour]
            dt=min(dt,max(1e-9,rawhour+1-(start_h+t)))
        # Exact stationary event advance: no force, motion, or weather event is skipped.
        # Under constant (mode 0) / piecewise-constant (mode 2) H, v remains zero
        # until the next weather boundary whenever propulsion cannot beat wave drag.
        if v<1e-12 and qcommand*qcommand<=kappa*H*H:
            if metrics is not None and mode in (0,2):metrics[4]+=1
            if mode==0:dt=max_h-t
            elif mode==2:dt=min(max_h-t,max(1e-9,math.floor(start_h+t+1e-9)+1-(start_h+t)))
        q=qcommand;a=acceleration(v,q,H,kappa,tau,vref,up,down)
        # Anticipatory curve envelope concerns steering only, never wave height.
        nextpos=min(length,pos+max(v,1.)*dt+0.5*up*dt*dt)
        cap=np.interp(nextpos,s,caps)
        allowed=(cap-v)/dt
        if a>allowed:
            allowed=max(-down,allowed)
            demand=allowed*(2*tau*vref)+v*v+kappa*H*H
            if demand<0:q=0.;a=-down
            else:q=min(qcommand,math.sqrt(demand));a=acceleration(v,q,H,kappa,tau,vref,up,down)
        # Find exact switch to finite-distance terminal braking inside this step.
        remain=length-pos
        if stop_at_goal and not braking:
            gap=remain-v*v/(2*down)
            vn=max(0.,v+a*dt);dx=max(0.,v*dt+0.5*a*dt*dt)
            nextgap=remain-dx-vn*vn/(2*down)
            if gap<=1e-7 and v>1e-8:braking=True
            elif gap>0 and nextgap<0:
                lo=0.;hi=dt
                for _ in range(30):
                    mid=(lo+hi)/2;vm=max(0.,v+a*mid)
                    f=remain-(v*mid+0.5*a*mid*mid)-vm*vm/(2*down)
                    if f>0:lo=mid
                    else:hi=mid
                dt=max(1e-8,(lo+hi)/2)
        if braking:q=0.;a=-down
        vn=max(0.,v+a*dt)
        moving_dt=dt
        if a<0 and v+a*dt<0:moving_dt=v/(-a)
        dx=max(0.,v*moving_dt+0.5*a*moving_dt*moving_dt)
        if dx>=remain-1e-9:
            dt=travel_time(remain,v,a);vn=max(0.,v+a*dt);dx=remain
            if stop_at_goal and braking and vn<1e-4:vn=0.
        rate=max(idle,fuel0*(q/12.)**3)
        fuel+=rate*dt+extra*max(vn*vn-v*v,0.)
        pos+=dx;t+=dt;v=vn
        if record:
            if count>=len(trace):return -3,t,v,fuel,pos,trace[:count]
            trace[count]=np.array([t,pos,v,q,H,fuel]);count+=1
        if v>np.interp(pos,s,caps)+0.08:return -2,t,v,fuel,pos,trace[:count] if record else trace
    status=1 if pos>=length-1e-7 else 0
    if status==1 and stop_at_goal and v>1e-3:status=-2
    return status,t,v,fuel,pos,trace[:count] if record else trace


def parameters(c):
    p=c['propulsion'];w=c['weather']
    return np.array([p['wave_drag_kn2_per_m2'],p['response_h'],p['reference_kn'],c['accel_kn_per_h'],c['decel_kn_per_h'],
                     c['fuel_normal_tph'],c['fuel_wait_tph'],c['accel_extra_t_per_kn2'],w['peak_wave_m'],w['scale_km'],w['cutoff_km']],float)


def steering_caps(curve,c):
    cap=np.minimum(18.,math.radians(c['max_yaw_deg_per_min'])*60/np.maximum(abs(curve.k),1e-12))
    if curve.turn>math.pi/12:
        cap=np.where(abs(curve.k)>1e-4,np.minimum(cap,c['sharp_turn_cap_kn'] if curve.turn>math.pi/2 else c['mild_turn_cap_kn']),cap)
    for i in range(len(cap)-2,-1,-1):
        cap[i]=min(cap[i],math.sqrt(cap[i+1]**2+2*c['decel_kn_per_h']*(curve.s[i+1]-curve.s[i])))
    return cap


@dataclass
class DriveTrajectory:
    curve: Curve
    q: float
    stop: bool
    start_h: float
    trace: np.ndarray
    reached: bool
    @property
    def duration(self):return float(self.trace[-1,0])
    @property
    def fuel(self):return float(self.trace[-1,5])
    def sample(self,time_h):
        rel=np.clip(np.asarray(time_h)-self.start_h,0,self.duration)
        i=np.maximum(0,np.minimum(np.searchsorted(self.trace[:,0],rel,side='right')-1,len(self.trace)-2))
        elapsed=rel-self.trace[i,0];span=np.maximum(self.trace[i+1,0]-self.trace[i,0],1e-12)
        a=(self.trace[i+1,2]-self.trace[i,2])/span
        v=np.maximum(0,self.trace[i,2]+a*elapsed)
        distance=np.minimum(self.curve.length,self.trace[i,1]+self.trace[i,2]*elapsed+.5*a*elapsed*elapsed)
        p=np.interp(distance,self.curve.s,self.curve.p)
        return self.curve.points(p),v,np.interp(p,self.curve.p,self.curve.heading)
    def as_dict(self):
        return {'controls_nm':self.curve.controls.tolist(),'curve_s_nm':self.curve.s.tolist(),'curve_parameters':self.curve.p.tolist(),
                'curve_headings_rad':self.curve.heading.tolist(),'q_kn_equivalent':self.q,'stop_at_goal':self.stop,
                'start_h':self.start_h,'duration_h':self.duration,'reached':self.reached,'trace_columns':['relative_h','progress_nm','actual_kn','propulsion_equivalent_kn','wave_m','fuel_t'],
                'trace':self.trace.tolist()}


def simulate(curve,v0,q,stop,start_h,max_h,c,forecast=None,scenario=4,world=None,constant_H=None):
    if world is not None:mode=1;anchors=world.t;storms=world.st
    elif forecast is not None:mode=1;anchors=forecast.anchor_times;storms=forecast.states[scenario]
    else:mode=0;anchors=np.array([0.,1.]);storms=np.zeros((2,3))
    status,t,v,F,pos,trace=integrate(curve.s,curve.xy[:,0],curve.xy[:,1],steering_caps(curve,c),v0,q,stop,start_h,max_h,
                                   parameters(c),mode,0. if constant_H is None else constant_H,anchors,storms,np.zeros(1),
                                   c['propulsion']['integration_h'],True)
    if status<0:return None,status
    return DriveTrajectory(curve,q,stop,start_h,trace,status==1),status


def upper_heights(forecast,boxes,s):
    """Same conservative swept-box construction as before, now a continuous H."""
    out=[];w=forecast.c['weather']
    for sa,sb in zip(forecast.states[s,:-1],forecast.states[s,1:]):
        lo=np.minimum(sa[:2],sb[:2])/1.852;hi=np.maximum(sa[:2],sb[:2])/1.852
        dx=np.maximum(np.maximum(boxes[:,0]-hi[0],lo[0]-boxes[:,2]),0.)
        dy=np.maximum(np.maximum(boxes[:,1]-hi[1],lo[1]-boxes[:,3]),0.)
        I=max(sa[2],sb[2]);d2=(dx*dx+dy*dy)*1.852**2
        h=np.where(d2<=(w['cutoff_km']*I)**2,w['peak_wave_m']*I*np.exp(-d2/(w['scale_km']*max(I,1e-12))**2),0.)
        out.append(h)
    return np.asarray(out,dtype=np.float32)
