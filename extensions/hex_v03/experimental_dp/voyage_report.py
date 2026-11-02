"""Offline SVG replay, explicit 1/2/4/6m wave contours, speed-coloured track."""
import json,math
from pathlib import Path
import numpy as np
from hex_dss.weather import project

def render(out,records,lat,c):
    def view(s):
        result={k:v for k,v in s.items() if k!='history'}
        history=s.get('history',[]);result['history']=history[::3]+(history[-1:] if len(history)%3!=1 else [])
        return result
    frames=[]
    for r in records:
        s=r['state_before'];f=r['forecast'];routes=[]
        for route in r['plan']['scenario_routes']:
            pts=[[s['x_nm'],s['y_nm']],lat.net.xy[r['plan']['chosen']['node']].tolist()]
            for a in route['actions']:
                if a['action']>=0:pts.append(lat.net.xy[int(lat.dstbase[a['action']])//24].tolist())
            routes.append(pts)
        frames.append({'state':view(s),'forecast':f,'routes':routes,'solve_s':r['plan']['solve_seconds'],'chosen':r['plan']['chosen'],'candidates':r['plan']['candidates']})
    final=records[-1]['state_after'];frames.append({'state':view(final),'forecast':records[-1]['forecast'],'routes':[],'solve_s':None,'chosen':None})
    land=[]
    for p in json.loads((Path(__file__).resolve().parents[1]/'data/land_projected.json').read_text()):land.append((np.array(p[0])/1.852).tolist())
    payload={'frames':frames,'land':land,'nodes':lat.net.xy.tolist(),'goal':c['goal_nm'],'start':[c['initial']['x_nm'],c['initial']['y_nm']],
             'bounds':c['bounds_nm'],'mode':c['mode'],'storm':np.column_stack([np.array(c['typhoon_waypoints'])[:,0],project(np.array(c['typhoon_waypoints'])[:,1],np.array(c['typhoon_waypoints'])[:,2])/1.852,np.array(c['typhoon_waypoints'])[:,3]]).tolist()}
    payload['complete']=records[-1].get('arrived',False)
    payload['exposure_peak_h']=max(final.get('history',[]) or [{'time_h':0}],key=lambda p:p.get('wave_m',0))['time_h']
    doc='''<!doctype html><meta charset="utf-8"><title>선택적 DP · 3시간 롤링 재생</title><style>body{font:16px 'Malgun Gothic',sans-serif;margin:24px;color:#071b30;background:#f2f7fb}section{background:white;padding:18px;border-radius:12px;margin-bottom:16px}svg{width:100%;max-height:76vh;background:#e8f5fc}input{width:75%}.kpi{display:flex;gap:30px;flex-wrap:wrap}button{padding:7px 16px}</style>
    <section><h1 id="title"></h1><div class="kpi" id="kpi"></div><p>실제 항적: 속도별 청색(저속 연함 → 쾌속 진함) · 시나리오 참고항로: 초록색 · 예측 태풍: 주황 점선</p><p>태풍 영향: 1m(옅은 주황) / 2m / 4m / 6m(진한 빨강) 파고 등고선. 중앙 예측의 향후 48시간 영향 범위를 12시간 간격으로 표시. 파고에 따른 물리적 감속이며 통과금지구역이 아닙니다.</p></section>
    <section><svg id="map" viewBox="0 0 1150 1100"></svg></section><section><button onclick="playing=!playing">재생/정지</button><input id="slider" type="range" min="0" max="MAX" value="0"><span id="time"></span><p id="note"></p></section>
    <script>const D=DATA;const svg=document.getElementById('map'),sl=document.getElementById('slider');let playing=false;const B=D.bounds;let scale=Math.min(1050/(B[1]-B[0]),990/(B[3]-B[2]));const p=a=>[50+(a[0]-B[0])*scale,1040-(a[1]-B[2])*scale];const el=(tag,attrs)=>'<'+tag+' '+Object.entries(attrs).map(([k,v])=>k+'="'+v+'"').join(' ')+'/>';const line=(pts,color,width,opacity=1,dash='')=>el('polyline',{points:pts.map(p).map(x=>x.join(',')).join(' '),fill:'none',stroke:color,'stroke-width':width,opacity,'stroke-dasharray':dash});
    function storm(x,y,I,opacity,dashed=false){if(D.mode==='calm'||I<=0)return '';let z='';for(const [H,col] of [[1,'#ff9e42'],[2,'#ff6f18'],[4,'#e83f26'],[6,'#a80719']]){if(10*I<=H)continue;let r=280*I*Math.sqrt(Math.log(10*I/H))/1.852*scale;let pt=p([x,y]);z+=el('circle',{cx:pt[0],cy:pt[1],r,fill:col,'fill-opacity':opacity,stroke:col,'stroke-opacity':.7,'stroke-width':dashed?1:2,'stroke-dasharray':dashed?'6 5':''});}return z;}
    function show(){let F=D.frames[+sl.value],s=F.state,z='';for(const poly of D.land)z+=el('polygon',{points:poly.map(p).map(a=>a.join(',')).join(' '),fill:'#d5e5d0',stroke:'#829a79','stroke-width':.8});for(const n of D.nodes){let q=p(n);z+=el('circle',{cx:q[0],cy:q[1],r:1,fill:'#658ca0',opacity:.24});}
    if(D.mode!=='calm'){let times=F.forecast.anchor_times,st=F.forecast.states;for(const j of [0,12,24,36,48]){if(j<st[4].length){let a=st[4][j];z+=storm(a[0]/1.852,a[1]/1.852,a[2],.07,true);}}for(const path of st)z+=line(path.slice(0,49).map(a=>[a[0]/1.852,a[1]/1.852]),'#d56113',2,.38,'6 5');let truth=D.storm;let i=0;while(i<truth.length-2&&truth[i+1][0]<s.time_h)i++;let a=truth[i],b=truth[i+1],w=Math.max(0,Math.min(1,(s.time_h-a[0])/(b[0]-a[0])));let x=a[1]*(1-w)+b[1]*w,y=a[2]*(1-w)+b[2]*w,I=a[3]*(1-w)+b[3]*w;z+=storm(x,y,I,.15);z+=line(truth.filter(a=>a[0]<=s.time_h).map(a=>[a[1],a[2]]).concat([[x,y]]),'#b62a15',3,.8);let q=p([x,y]);z+=el('circle',{cx:q[0],cy:q[1],r:7,fill:'#a80719'});}
    for(const route of F.routes)z+=line(route,'#167944',2,.24);let hist=s.history||[];for(let i=1;i<hist.length;i++){let a=hist[i-1],b=hist[i];z+=line([[a.x_nm,a.y_nm],[b.x_nm,b.y_nm]],b.speed_kn>15?'#081d58':b.speed_kn>9?'#1764ab':'#69b8e6',4.5);}for(const [pt,col,label,shape] of [[D.start,'#1455b8','부산','circle'],[D.goal,'#16833a','홍콩','rect'],[[s.x_nm,s.y_nm],'#d00','현재','circle']]){let q=p(pt);z+=shape==='rect'?el('rect',{x:q[0]-7,y:q[1]-7,width:14,height:14,fill:col,stroke:'white','stroke-width':2}):el('circle',{cx:q[0],cy:q[1],r:8,fill:col,stroke:'white','stroke-width':2});if(label!=='현재')z+='<text x="'+(q[0]+12)+'" y="'+(q[1]-14)+'" font-size="27" font-weight="bold" fill="#08223e">'+label+'</text>';}
    svg.innerHTML=z;document.getElementById('title').textContent=(D.mode==='calm'?'무태풍':'태풍')+' · 선택적 DP 롤링 재생'+(D.complete?' (도착 완료)':' (계산 진행 중)');document.getElementById('kpi').innerHTML=['경과 '+s.time_h.toFixed(2)+' h','거리 '+(s.distance_nm||0).toFixed(1)+' nm','연료 '+(s.fuel_t||0).toFixed(2)+' t','누적 운항비 $'+(s.operating_cost_usd||0).toFixed(0),'속도 '+s.speed_kn.toFixed(2)+' kn'].join('　|　');document.getElementById('time').textContent=(+sl.value+1)+' / '+D.frames.length;document.getElementById('note').textContent=F.chosen?'이번 추진 '+F.chosen.q_command_kn+'kn 상당 / 선택 노드 '+F.chosen.node+' / 계산 '+F.solve_s.toFixed(1)+'초 / 예측 발행시각 '+F.forecast.observation_max_h+'h':'최신 실제 상태. 예측은 직전 의사결정 발행시각의 자료입니다.';}
    sl.oninput=show;setInterval(()=>{if(playing){sl.value=(+sl.value+1)%D.frames.length;show();}},1000);show();</script>'''
    table='<section><h2>해당 시점 상위 후보 평가</h2><p>예측 시나리오 기준 비용이며 실제 누적비용과 구분합니다. 현재 λ=0.</p><table style="width:100%;text-align:right;border-collapse:collapse"><thead><tr><th>노드</th><th>추진(kn 상당)</th><th>정지 도착</th><th>초기비용 평균($)</th><th>장기비용 평균($)</th><th>목적값($)</th></tr></thead><tbody id="candidates"></tbody></table></section>'
    doc=doc.replace('<script>const D=',table+'<script>const D=')
    extra="document.getElementById('candidates').innerHTML=(F.candidates||[]).filter(a=>a.objective_usd!==null).sort((a,b)=>a.objective_usd-b.objective_usd).slice(0,8).map(a=>'<tr>'+[a.node,a.q_command_kn,a.stop_at_goal?'예':'아니오',a.scenario_first_usd.reduce((x,y)=>x+y,0)/9,a.scenario_future_usd.reduce((x,y)=>x+y,0)/9,a.objective_usd].map(x=>'<td style=\"padding:8px;border-bottom:1px solid #ddd\">'+(typeof x==='number'?x.toLocaleString(undefined,{maximumFractionDigits:2}):x)+'</td>').join('')+'</tr>').join('');"
    doc=doc.replace('svg.innerHTML=z;',extra+'svg.innerHTML=z;')
    doc=doc.replace('value="0"><span id="time"','value="MAX"><span id="time"')
    if c['mode']=='typhoon':
        peak_button='<button onclick="const peak=D.storm.reduce((a,b)=>a[3]>b[3]?a:b)[0];let best=0;D.frames.forEach((f,i)=>{if(Math.abs(f.state.time_h-peak)<Math.abs(D.frames[best].state.time_h-peak))best=i});sl.value=best;show()">태풍 강도 최대 시점</button>'
        doc=doc.replace('<input id="slider"',peak_button+'<input id="slider"')
        exposure_button='<button onclick="const peak=D.exposure_peak_h;let best=0;D.frames.forEach((f,i)=>{if(Math.abs(f.state.time_h-peak)<Math.abs(D.frames[best].state.time_h-peak))best=i});sl.value=best;show()">선박 최대 파고 노출 구간</button>'
        doc=doc.replace('<input id="slider"',exposure_button+'<input id="slider"')
    (Path(out)/'dashboard.html').write_text(doc.replace('MAX',str(len(frames)-1)).replace('DATA',json.dumps(payload)),encoding='utf-8')
