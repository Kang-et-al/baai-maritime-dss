"""Hex lattice + exact physical destination, checked against supplied land polygons."""
import json
import math
import time
import numpy as np
import shapely
from shapely.geometry import Polygon,Point,LineString
from .config import ROOT
from .motion import make_curve


class Land:
    def __init__(self,c):
        data=json.loads((ROOT/'data/land_projected.json').read_text(encoding='utf-8'))
        polys=[]
        for p in data:
            poly=Polygon(np.array(p[0])/1.852,[np.array(h)/1.852 for h in p[1:]])
            if not poly.is_valid: poly=shapely.make_valid(poly)
            polys.append(poly)
        self.raw=shapely.union_all(polys)
        self.buffered=self.raw.buffer(c['safety_buffer_nm'])
        shapely.prepare(self.raw); shapely.prepare(self.buffered)
    def sea(self,xy): return not self.buffered.intersects(Point(xy))
    def clear(self,curve): return not self.buffered.intersects(LineString(curve.xy))


class HexNetwork:
    def __init__(self,c):
        started=time.perf_counter(); self.c=c; self.land=Land(c); self.heading=np.arange(6)*np.pi/3
        origin=np.array([c['initial']['x_nm'],c['initial']['y_nm']]); d=c['spacing_nm']; xmin,xmax,ymin,ymax=c['bounds_nm']
        points=[]; axial=[]
        # Offset keeps the exact supplied Busan gateway on the lattice, without moving it.
        for r in range(-100,101):
            y=origin[1]+r*d*math.sqrt(3)/2
            if y<ymin or y>ymax: continue
            for q in range(-100,101):
                x=origin[0]+d*(q+r/2)
                if xmin<=x<=xmax and self.land.sea([x,y]): points.append([x,y]); axial.append((q,r))
        self.xy=np.asarray(points,float); self.axial=axial; self.lookup={v:i for i,v in enumerate(axial)}
        if not self.land.sea(origin): raise ValueError('Busan gateway is land under supplied coastline; explicit gateway decision required')
        self.goal=len(self.xy); self.xy=np.vstack([self.xy,np.array(c['goal_nm'])])
        if not self.land.sea(self.xy[self.goal]): raise ValueError('Exact Hong Kong gateway lies on buffered land')
        self.n=len(self.xy); self.start=self.lookup[(0,0)]
        self.build_seconds=time.perf_counter()-started

    def build_geometries(self):
        started=time.perf_counter(); dirs=[(1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1)]
        records=[]; curves=[]
        for i,ax in enumerate(self.axial):
            for h in range(6):
                for rel in [0,-1,1,-2,2]:
                    direction=(h+rel)%6; dq,dr=dirs[direction]; j=self.lookup.get((ax[0]+dq,ax[1]+dr))
                    if j is None: continue
                    curve=make_curve(self.xy[i],self.xy[j],self.heading[h],self.heading[direction],self.c)
                    if curve is not None and self.land.clear(curve):
                        records.append((i,h,j,direction,rel,False)); curves.append(curve)
                # Exact destination connector; only terminal speed zero is allowed later.
                dist=np.linalg.norm(self.xy[i]-self.xy[self.goal])
                if 0.25<dist<=self.c['spacing_nm']*1.8:
                    endh=math.atan2(*(self.xy[self.goal]-self.xy[i])[::-1])
                    curve=make_curve(self.xy[i],self.xy[self.goal],self.heading[h],endh,self.c)
                    if curve is not None and self.land.clear(curve):
                        records.append((i,h,self.goal,0,99,True));curves.append(curve)
        self.records=records;self.curves=curves; self.boxes=np.array([v.box for v in curves])
        self.geometry_seconds=time.perf_counter()-started
        return self
