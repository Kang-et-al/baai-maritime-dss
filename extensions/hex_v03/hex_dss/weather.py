"""Observed-history forecasts only. Planner never receives World."""
from dataclasses import dataclass
import math
import numpy as np


def project(lon, lat):
    e=math.sqrt(0.0066943799901413165)
    def mt(d):
        p=math.radians(d)
        return math.cos(p)/math.sqrt(1-e*e*math.sin(p)**2), math.tan(math.pi/4-p/2)/((1-e*math.sin(p))/(1+e*math.sin(p)))**(e/2)
    m1,t1=mt(20); m2,t2=mt(36); n=math.log(m1/m2)/math.log(t1/t2)
    f=m1/(n*t1**n); rho0=6378.137*f*mt(28)[1]**n
    lon=np.asarray(lon); p=np.radians(lat)
    t=np.tan(math.pi/4-p/2)/((1-e*np.sin(p))/(1+e*np.sin(p)))**(e/2)
    rho=6378.137*f*t**n; theta=n*np.radians(lon-122.5)
    return np.stack([rho*np.sin(theta),rho0-rho*np.cos(theta)],axis=-1)


def heights(xy_nm, storm, c):
    xy=np.asarray(xy_nm)*1.852
    st=np.asarray(storm); intensity=np.maximum(st[...,2],0.)
    d2=np.sum((xy-st[...,:2])**2,axis=-1)
    scale=c['weather']['scale_km']*np.maximum(intensity,1e-12)
    cutoff=c['weather']['cutoff_km']*intensity
    return np.where(d2<=cutoff**2, c['weather']['peak_wave_m']*intensity*np.exp(-d2/scale**2),0.)


def band(h):
    return np.select([np.asarray(h)<2,np.asarray(h)<4,np.asarray(h)<5],[0,1,2],default=3)


@dataclass
class Observation:
    now: float
    times: np.ndarray
    storms: np.ndarray


class World:
    def __init__(self,c):
        self.c=c; w=np.asarray(c['typhoon_waypoints'],float)
        self.t=w[:,0]; self.st=np.column_stack([project(w[:,1],w[:,2]),w[:,3]])
        if c['mode']=='calm': self.st[:,2]=0.
    def storm(self,t):
        return np.stack([np.interp(t,self.t,self.st[:,j]) for j in range(3)],axis=-1)
    def observe(self,now):
        t=np.unique(np.r_[max(0,now-3),np.arange(max(0,now-3),now,0.25),now])
        assert t.max() <= now+1e-10
        return Observation(now,t,self.storm(t))


class Forecast:
    def __init__(self,obs,c):
        self.now=obs.now; self.c=c; f=c['forecast']; current=obs.storms[-1]
        if len(obs.times)>1 and obs.times[-1]>obs.times[0]:
            velocity=(obs.storms[-1,:2]-obs.storms[0,:2])/(obs.times[-1]-obs.times[0])
            trend=(obs.storms[-1,2]-obs.storms[0,2])/(obs.times[-1]-obs.times[0])
        else:
            velocity=np.array(c['initial_forecast_velocity_kmh']); trend=c['initial_forecast_intensity_trend_per_h']
        self.initial=current.copy(); self.velocity=velocity; self.trend=trend
        self.p=np.ones(9)/9
        self.labels=[f'{a}/{b}' for a in ['right','central','left'] for b in ['weak','central','strong']]
        self.anchor_times=self.now+np.arange(math.ceil(c['horizon_h'])+9,dtype=float)
        self.states=self._generate(self.anchor_times)
        self.observation_max_h=float(obs.times[-1])
    def _generate(self,t):
        s=np.maximum(np.asarray(t)-self.now,0); f=self.c['forecast']
        central=self.initial[:2]+self.velocity*f['motion_decay_h']*(1-np.exp(-s[:,None]/f['motion_decay_h']))
        decay=np.exp(-np.maximum(s-f['decay_after_h'],0)/f['intensity_decay_h'])
        strength=np.clip(self.initial[2]+self.trend*f['intensity_trend_h']*(1-np.exp(-s/f['intensity_trend_h'])),0,1)*decay
        direction=self.velocity/max(np.linalg.norm(self.velocity),1e-12)
        if np.linalg.norm(direction)<0.5: direction=np.array([0.,1.])
        normal=np.array([-direction[1],direction[0]])
        result=[]
        for a in [-1,0,1]:
            for b in [-1,0,1]:
                xy=central+a*f['track_offset_km']*np.minimum(s/f['track_ramp_h'],1)[:,None]*normal
                value=np.clip(strength+b*f['intensity_offset']*np.minimum(s/f['intensity_ramp_h'],1)*decay,0,1)
                if self.c['mode']=='calm': value[:]=0
                result.append(np.column_stack([xy,value]))
        return np.asarray(result)
    def storm(self,s,t):
        # Piecewise linear in absolute time; timestamps are never snapped backwards.
        return np.stack([np.interp(t,self.anchor_times,self.states[s,:,j]) for j in range(3)],axis=-1)
    def at(self,s,xy,t): return heights(xy,self.storm(s,t),self.c)
    def bounds(self,boxes,s):
        """Conservative upper wave height over each entire curve box and forecast hour.

        Storm centre lies in endpoint bounding rectangle, intensity <= endpoint max.
        Enlarging the positive wave kernel in intensity gives a true upper bound.
        """
        a=self.states[s,:-1]; b=self.states[s,1:]; out=[]
        for sa,sb in zip(a,b):
            lo=np.minimum(sa[:2],sb[:2])/1.852; hi=np.maximum(sa[:2],sb[:2])/1.852
            dx=np.maximum(np.maximum(boxes[:,0]-hi[0],lo[0]-boxes[:,2]),0)
            dy=np.maximum(np.maximum(boxes[:,1]-hi[1],lo[1]-boxes[:,3]),0)
            intensity=max(sa[2],sb[2]); dist2=(dx*dx+dy*dy)*1.852**2
            scale=self.c['weather']['scale_km']*max(intensity,1e-12)
            cutoff=self.c['weather']['cutoff_km']*intensity
            h=np.where(dist2<=cutoff**2,self.c['weather']['peak_wave_m']*intensity*np.exp(-dist2/scale**2),0.)
            out.append(band(h))
        return np.asarray(out,dtype=np.uint8)
