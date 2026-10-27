"""실제 세계와 예측기의 정보 경계. 예측기는 공개된 Observation만 받는다."""
from dataclasses import dataclass
import numpy as np
from .network import project


@dataclass(frozen=True)
class Observation:
    start_h: float
    hours: np.ndarray
    states: np.ndarray  # [x_km, y_km, intensity], known interval only
    heading: np.ndarray


class World:
    def __init__(self, config):
        self.config=config
        wp=np.asarray(config["typhoon_waypoints"], dtype=float)
        self.hours=wp[:,0]
        self.states=np.column_stack([project(wp[:,1],wp[:,2]), wp[:,3]])
        if config["mode"] == "calm":
            self.states[:,2]=0

    def state(self, hour):
        return np.array([np.interp(hour,self.hours,self.states[:,j]) for j in range(3)]).T

    def reveal(self, hour):
        end=hour+self.config["rolling_h"]
        # Include exact endpoint, plus hourly field samples.
        hours=np.unique(np.r_[hour, np.arange(np.ceil(hour),end+1e-8,1),end])
        states=self.state(hours)
        direction=states[-1,:2]-states[0,:2]
        if np.linalg.norm(direction)<1e-10:
            history=self.state(np.arange(0, hour+1, 1))
            delta=np.diff(history[:,:2],axis=0)
            nz=np.flatnonzero(np.linalg.norm(delta,axis=1)>1e-10)
            direction=delta[nz[-1]] if len(nz) else np.array(self.config["forecast"]["fallback_heading_xy"],dtype=float)
        if np.linalg.norm(direction)<1e-10:
            direction=np.array([0.,1.])
        return Observation(hour,hours,states,direction/np.linalg.norm(direction))

    def field(self, xy, hour):
        return wave(xy,self.state(np.floor(hour)),self.config)


def wave(xy, state, config):
    """Synthetic wave height: state (...,3), xy (P,2) -> (...,P)."""
    state=np.asarray(state)
    d2=np.sum((state[...,None,:2]-np.asarray(xy)[...,:2])**2,axis=-1)
    w=config["weather"]
    multiplier=np.maximum(state[...,None,2],1e-12) if w.get("radius_scales_with_intensity",False) else 1.
    scale=w["scale_km"]*multiplier
    cutoff=w["cutoff_km"]*multiplier
    return np.where(d2<=cutoff**2,
                    w["peak_wave_m"]*state[...,None,2]*np.exp(-d2/scale**2),0.)


def contour_radius(intensity,height,config):
    """반경 km. 그림도 의사결정에 쓰는 파고장과 동일한 공식을 사용한다."""
    w=config["weather"]; peak=w["peak_wave_m"]*intensity
    if intensity<=0 or peak<=height: return 0.
    multiplier=intensity if w.get("radius_scales_with_intensity",False) else 1.
    return min(w["cutoff_km"]*multiplier,w["scale_km"]*multiplier*np.sqrt(np.log(peak/height)))


class TrendForecaster:
    """공개된 3시간 추세를 기반으로 3경로 x 3강도. 숨겨진 World 인자를 받지 않음."""
    generator_id="trend-path-intensity-3x3-v1"
    def generate(self, obs, config):
        hours=obs.start_h+np.arange(int(np.ceil(config["horizon_h"]))+1)
        boundary=obs.hours[-1]
        s=np.maximum(hours-boundary,0)
        f=config["forecast"]
        velocity=(obs.states[-1,:2]-obs.states[0,:2])/(boundary-obs.start_h)
        gradient=(obs.states[-1,2]-obs.states[0,2])/(boundary-obs.start_h)
        central=obs.states[-1,:2]+velocity[None,:]*f["motion_decay_h"]*(1-np.exp(-s[:,None]/f["motion_decay_h"]))
        decay=np.exp(-np.maximum(s-f["decay_after_h"],0)/f["intensity_decay_h"])
        strength=np.clip(obs.states[-1,2]+gradient*f["intensity_trend_h"]*(1-np.exp(-s/f["intensity_trend_h"])),0,1)*decay
        normal=np.array([-obs.heading[1],obs.heading[0]])
        scenarios=[]; labels=[]
        for a,track in [(-1,"우측"),(0,"기준"),(1,"좌측")]:
            for b,intensity in [(-1,"약함"),(0,"기준"),(1,"강함")]:
                xy=central+a*f["track_offset_km"]*np.minimum(s/f["track_ramp_h"],1)[:,None]*normal
                value=np.clip(strength+b*f["intensity_offset"]*np.minimum(s/f["intensity_ramp_h"],1)*decay,0,1)
                states=np.column_stack([xy,value])
                known=hours<=boundary+1e-8
                for j in range(3):
                    states[known,j]=np.interp(hours[known],obs.hours,obs.states[:,j])
                if config["mode"] == "calm":
                    states[:,2]=0
                scenarios.append(states); labels.append(f"{track} / {intensity}")
        return Forecast(obs.start_h,hours,np.asarray(scenarios),labels,np.full(9,1/9))


@dataclass
class Forecast:
    start_h: float
    hours: np.ndarray
    states: np.ndarray
    labels: list
    probabilities: np.ndarray
    representative_index: int = 4

    def validate(self, obs, config):
        expected=obs.start_h+np.arange(int(np.ceil(config["horizon_h"]))+1)
        if self.states.shape!=(len(self.probabilities),len(expected),3):
            raise ValueError("Forecast shape must be [scenario, hourly time, x/y/intensity]")
        if not np.allclose(self.hours,expected) or not np.isfinite(self.states).all():
            raise ValueError("Forecast must use finite states on the required hourly grid")
        if np.any(self.probabilities<=0) or not np.isclose(self.probabilities.sum(),1):
            raise ValueError("Forecast probabilities must be positive and sum to 1")
        if np.any(self.states[:,:,2]<0) or np.any(self.states[:,:,2]>1):
            raise ValueError("Forecast intensity must be in [0,1]")
        known=self.hours<=obs.hours[-1]+1e-8
        for j in range(3):
            actual=np.interp(self.hours[known],obs.hours,obs.states[:,j])
            if not np.allclose(self.states[:,known,j],actual[None,:]):
                raise ValueError("All forecasts must match the disclosed first interval")
        if len(self.labels)!=len(self.probabilities) or not 0<=self.representative_index<len(self.probabilities):
            raise ValueError("Forecast labels / representative index are invalid")
        return self

    def fields(self, network, config):
        # Weather is held constant within each absolute hour.
        # Same float64 field in planner and executor, including threshold boundaries.
        return (wave(network.xy,self.states,config),
                wave(network.mid,self.states,config))

    def as_dict(self):
        return {"start_h":self.start_h,"hours":self.hours.tolist(),
                "states_xy_km_intensity":self.states.tolist(),"labels":self.labels,
                "probabilities":self.probabilities.tolist(),"representative_index":self.representative_index}


def speed_rule(height, config):
    h=np.asarray(height)
    a,b,c=config["wave_thresholds_m"]
    r=np.select([h<a,h<b,h<c],config["speed_factors"],default=0.)
    cap=np.where(h<b,config["fast_kn"],config["normal_kn"])
    return r,cap
