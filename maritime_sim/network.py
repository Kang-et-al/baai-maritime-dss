"""원본 CSV에서 활성 네트워크 로드. LCC 투영은 원본 지도와 같은 WGS84 정의."""
import csv
import math
from collections import deque
from pathlib import Path
import numpy as np
from .config import ROOT


def project(lon, lat):
    """WGS84 Lambert conformal conic -> km (lat0=28, lon0=122.5, parallels=20,36)."""
    e = math.sqrt(0.0066943799901413165)
    def mt(deg):
        p = math.radians(deg)
        m = math.cos(p)/math.sqrt(1-e*e*math.sin(p)**2)
        t = math.tan(math.pi/4-p/2)/((1-e*math.sin(p))/(1+e*math.sin(p)))**(e/2)
        return m,t
    m1,t1 = mt(20); m2,t2 = mt(36)
    n = math.log(m1/m2)/math.log(t1/t2)
    f = m1/(n*t1**n)
    rho0 = 6378.137*f*mt(28)[1]**n
    lon = np.asarray(lon, dtype=float); lat = np.asarray(lat, dtype=float)
    p = np.radians(lat)
    t = np.tan(np.pi/4-p/2)/((1-e*np.sin(p))/(1+e*np.sin(p)))**(e/2)
    rho = 6378.137*f*t**n
    theta = n*np.radians(lon-122.5)
    return np.stack([rho*np.sin(theta), rho0-rho*np.cos(theta)], axis=-1)


class Network:
    def __init__(self, directory=None):
        self.directory = Path(directory or ROOT/"data"/"network")
        with (self.directory/"nodes.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["route_component"].lower() == "true"]
        self.ids = np.array([int(r["node_id"]) for r in rows], dtype=int)
        self.index = {int(n): i for i,n in enumerate(self.ids)}
        self.xy = np.array([[float(r["x_nm"])*1.852, float(r["y_nm"])*1.852] for r in rows])
        self.lonlat = np.array([[float(r["longitude"]), float(r["latitude"])] for r in rows])
        self.n = len(rows)
        with (self.directory/"arcs.csv").open(encoding="utf-8-sig", newline="") as f:
            arcs = [r for r in csv.DictReader(f) if r["active"].lower() == "true"]
        self.src = np.array([self.index[int(r["from_node"])] for r in arcs], dtype=int)
        self.dst = np.array([self.index[int(r["to_node"])] for r in arcs], dtype=int)
        self.dist = np.array([float(r["model_distance_nm"]) for r in arcs])
        self.mid = (self.xy[self.src]+self.xy[self.dst])/2
        self.adj = [[] for _ in rows]
        for e,(i,j) in enumerate(zip(self.src,self.dst)):
            self.adj[i].append((int(j),e))

    def shortest_arcs(self, start, goal):
        dist = {start: 0}; q = deque([start])
        while q:
            i=q.popleft()
            if i == goal:
                return dist[i]
            for j,_ in self.adj[i]:
                if j not in dist:
                    dist[j]=dist[i]+1; q.append(j)
        raise ValueError("출발·도착 노드가 연결되어 있지 않습니다")
