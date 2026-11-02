"""Curved motion primitives with continuous speed and exact time-layer arrival."""
from dataclasses import dataclass
import math
import numpy as np
from numba import njit


def wrap(a): return (a+np.pi)%(2*np.pi)-np.pi


@dataclass
class Curve:
    controls: np.ndarray
    p: np.ndarray
    xy: np.ndarray
    s: np.ndarray
    k: np.ndarray
    heading: np.ndarray
    turn: float
    @property
    def length(self): return float(self.s[-1])
    @property
    def box(self):
        # Bezier convex hull contains the complete continuous curve.
        return np.r_[self.controls.min(axis=0),self.controls.max(axis=0)]
    def points(self,p):
        t=np.asarray(p)[...,None]; z=1-t; b=self.controls
        return z**3*b[0]+3*z*z*t*b[1]+3*z*t*t*b[2]+t**3*b[3]


def make_curve(start,end,h0,h1,c):
    start=np.asarray(start,float); end=np.asarray(end,float); d=np.linalg.norm(end-start)
    if d<0.05: return None
    tangent=0.4*d
    controls=np.array([start,start+tangent*np.array([np.cos(h0),np.sin(h0)]),
                       end-tangent*np.array([np.cos(h1),np.sin(h1)]),end])
    t=np.linspace(0,1,c['curve_samples']); z=1-t
    xy=z[:,None]**3*controls[0]+3*(z*z*t)[:,None]*controls[1]+3*(z*t*t)[:,None]*controls[2]+t[:,None]**3*controls[3]
    dp=3*(z*z)[:,None]*(controls[1]-controls[0])+6*(z*t)[:,None]*(controls[2]-controls[1])+3*(t*t)[:,None]*(controls[3]-controls[2])
    dd=6*z[:,None]*(controls[2]-2*controls[1]+controls[0])+6*t[:,None]*(controls[3]-2*controls[2]+controls[1])
    norm=np.linalg.norm(dp,axis=1)
    if norm.min()<0.01: return None
    k=(dp[:,0]*dd[:,1]-dp[:,1]*dd[:,0])/norm**3
    if np.max(np.abs(k))>1/c['min_turn_radius_nm']+1e-9: return None
    heading=np.unwrap(np.arctan2(dp[:,1],dp[:,0]))
    turn=float(np.sum(np.abs(np.diff(heading))))
    s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    return Curve(controls,t,xy,s,k,heading,turn)


@njit(cache=True)
def _velocity(s,upper,lower,cruise):
    return np.maximum(lower,np.minimum(upper,cruise))


@njit(cache=True)
def _duration(s,v):
    total=0.
    for i in range(len(s)-1):
        if v[i]+v[i+1]<1e-8: return 1e30
        total+=2*(s[i+1]-s[i])/(v[i]+v[i+1])
    return total


@njit(cache=True)
def profile_arrays(s,k,turn,u0,u1,cruise,weather_band,dt,acc,dec,yaw,mildcap,sharpcap,fuel_normal,fuel_idle,extra):
    """v^2 envelopes ensure bounded acceleration and continuous endpoint speeds.

    Time slack is real reduced-speed motion, never free waiting at nonzero speed.
    """
    factor=1. if weather_band==0 else (2/3 if weather_band==1 else 0.5)
    limit=18. if weather_band==0 else (12. if weather_band==1 else 6.)
    n=len(s); cap=np.full(n,min(limit,cruise))
    for i in range(n):
        if abs(k[i])>1e-4:
            cap[i]=min(cap[i],yaw/abs(k[i]))
            if turn>math.pi/2: cap[i]=min(cap[i],sharpcap)
            elif turn>math.pi/12: cap[i]=min(cap[i],mildcap)
    # Cruise is interior speed target; nonzero endpoint speed may be higher.
    if u0>limit+1e-8 or u1>limit+1e-8: return np.empty(0),np.empty(0),0.,0.
    if (abs(k[0])>1e-4 and u0>min(limit,yaw/abs(k[0]),sharpcap if turn>math.pi/2 else mildcap if turn>math.pi/12 else 18)+1e-8):
        return np.empty(0),np.empty(0),0.,0.
    upper=np.minimum(cap,cruise)
    # Allow a speed envelope to join endpoint speeds via proper ramps.
    for i in range(n):
        from_start=math.sqrt(max(0.,u0*u0-2*dec*s[i]))
        from_end=math.sqrt(max(0.,u1*u1-2*acc*(s[-1]-s[i])))
        upper[i]=max(upper[i],from_start,from_end)
        physical=min(limit,yaw/max(abs(k[i]),1e-12))
        if abs(k[i])>1e-4 and turn>math.pi/12: physical=min(physical,sharpcap if turn>math.pi/2 else mildcap)
        if upper[i]>physical+1e-7: return np.empty(0),np.empty(0),0.,0.
    upper[0]=u0; upper[-1]=u1
    for i in range(1,n): upper[i]=min(upper[i],math.sqrt(upper[i-1]**2+2*acc*(s[i]-s[i-1])))
    if abs(upper[-1]-u1)>1e-6: return np.empty(0),np.empty(0),0.,0.
    for i in range(n-2,-1,-1): upper[i]=min(upper[i],math.sqrt(upper[i+1]**2+2*dec*(s[i+1]-s[i])))
    if abs(upper[0]-u0)>1e-6: return np.empty(0),np.empty(0),0.,0.
    lower=np.empty(n)
    for i in range(n):
        lower[i]=max(math.sqrt(max(0.,u0*u0-2*dec*s[i])),math.sqrt(max(0.,u1*u1-2*acc*(s[-1]-s[i]))),0.01)
    lower[0]=u0; lower[-1]=u1
    for i in range(n):
        if lower[i]>upper[i]+1e-6: return np.empty(0),np.empty(0),0.,0.
    tmin=_duration(s,upper)
    target=math.ceil((tmin-1e-9)/dt)*dt
    if target>12: return np.empty(0),np.empty(0),0.,0.
    lo=0.01; hi=30.
    if _duration(s,_velocity(s,upper,lower,lo))<target-1e-7:
        return np.empty(0),np.empty(0),0.,0.
    for _ in range(48):
        mid=(lo+hi)/2
        if _duration(s,_velocity(s,upper,lower,mid))>target: lo=mid
        else: hi=mid
    v=_velocity(s,upper,lower,(lo+hi)/2); times=np.zeros(n); fuel=0.
    for i in range(n-1):
        du2=v[i+1]**2-v[i]**2; ds=s[i+1]-s[i]
        if du2>2*acc*ds+1e-5 or -du2>2*dec*ds+1e-5:
            return np.empty(0),np.empty(0),0.,0.
        segt=2*ds/(v[i]+v[i+1]); times[i+1]=times[i]+segt
        a=v[i]/factor; b=v[i+1]/factor
        # Simpson quadrature of idle floor + steady cubic propulsion curve.
        fa=max(fuel_idle,fuel_normal*(a/12)**3)
        fb=max(fuel_idle,fuel_normal*(b/12)**3)
        fm=max(fuel_idle,fuel_normal*((a+b)/24)**3)
        fuel+=segt*(fa+4*fm+fb)/6+extra*max(du2,0.)
    return times,v,target,fuel


@dataclass
class Profile:
    times: np.ndarray
    speeds: np.ndarray
    duration: float
    fuel: float
    band: int


def make_profile(curve,u0,u1,cruise,b,c):
    t,v,T,F=profile_arrays(curve.s,curve.k,curve.turn,u0,u1,cruise,b,c['time_step_h'],
                         c['accel_kn_per_h'],c['decel_kn_per_h'],math.radians(c['max_yaw_deg_per_min'])*60,
                         c['mild_turn_cap_kn'],c['sharp_turn_cap_kn'],c['fuel_normal_tph'],c['fuel_wait_tph'],c['accel_extra_t_per_kn2'])
    if len(t)==0: return None
    F+=c['turn_extra_t_per_rad']*curve.turn
    return Profile(t,v,T,F,b)


@dataclass
class Trajectory:
    curve: Curve
    profile: Profile
    start_h: float
    def sample(self,time_h):
        t=np.clip(np.asarray(time_h)-self.start_h,0,self.profile.duration)
        i=np.minimum(np.searchsorted(self.profile.times,t,side='right')-1,len(self.profile.times)-2)
        i=np.maximum(i,0); elapsed=t-self.profile.times[i]
        segT=self.profile.times[i+1]-self.profile.times[i]
        a=(self.profile.speeds[i+1]-self.profile.speeds[i])/segT
        speed=self.profile.speeds[i]+a*elapsed
        distance=self.curve.s[i]+self.profile.speeds[i]*elapsed+0.5*a*elapsed**2
        param=np.interp(distance,self.curve.s,self.curve.p)
        xy=self.curve.points(param)
        heading=np.interp(param,self.curve.p,self.curve.heading)
        return xy,speed,heading
    def as_dict(self):
        return {'start_h':self.start_h,'end_h':self.start_h+self.profile.duration,
                'controls_nm':self.curve.controls.tolist(),'profile_times_h':self.profile.times.tolist(),
                'profile_speeds_kn':self.profile.speeds.tolist(),'curve_s_nm':self.curve.s.tolist(),
                'curve_parameters':self.curve.p.tolist(),'curve_headings_rad':self.curve.heading.tolist(),
                'duration_h':self.profile.duration,'distance_nm':self.curve.length,
                'conservative_fuel_t':self.profile.fuel,'weather_band':self.profile.band}
    @classmethod
    def from_dict(cls,data):
        b=np.array(data['controls_nm']);t=np.array(data['curve_parameters']);z=1-t
        xy=z[:,None]**3*b[0]+3*(z*z*t)[:,None]*b[1]+3*(z*t*t)[:,None]*b[2]+t[:,None]**3*b[3]
        dp=3*(z*z)[:,None]*(b[1]-b[0])+6*(z*t)[:,None]*(b[2]-b[1])+3*(t*t)[:,None]*(b[3]-b[2])
        dd=6*z[:,None]*(b[2]-2*b[1]+b[0])+6*t[:,None]*(b[3]-2*b[2]+b[1])
        k=(dp[:,0]*dd[:,1]-dp[:,1]*dd[:,0])/np.maximum(np.linalg.norm(dp,axis=1)**3,1e-20)
        heading=np.array(data['curve_headings_rad'])
        curve=Curve(b,t,xy,np.array(data['curve_s_nm']),k,heading,float(np.sum(np.abs(np.diff(heading)))))
        p=Profile(np.array(data['profile_times_h']),np.array(data['profile_speeds_kn']),data['duration_h'],data['conservative_fuel_t'],data['weather_band'])
        return cls(curve,p,data['start_h'])
