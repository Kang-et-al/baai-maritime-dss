"""Self-contained Korean dashboard + PNG, exact saved decision records."""
import base64
import html
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from .config import ROOT
from .motion import Trajectory


def font(size,bold=False):
    for name in [('NotoSansKR-Bold.ttf' if bold else 'NotoSansKR-Regular.ttf'),('malgunbd.ttf' if bold else 'malgun.ttf')]:
        p=Path('C:/Windows/Fonts')/name
        if p.exists():return ImageFont.truetype(str(p),size)
    return ImageFont.load_default(size=size)


def draw_step(record,lat,c):
    W,H=1640,1110; im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
    navy='#123759';blue='#1466a3';orange='#da6c13';text='#111827'
    plan=record['plan'];before=record['state_before'];after=record.get('state_after',before)
    d.text((35,22),'해상운항 DSS | 육각망 · 연속 운항 · 이벤트 재계획',font=font(29,True),fill=navy)
    d.text((35,70),f"STEP {record['step']:03d}  요청 {before['time_h']:.4f}h  |  λ={c['risk']['lambda']:g} · α={c['risk']['alpha']:g}  |  {plan['status']}",font=font(19),fill=text)
    rect=(35,118,1020,1035);d.rectangle(rect,fill='#eaf5fc',outline='#b6cedf')
    xmin,xmax,ymin,ymax=c['bounds_nm'];scale=min((rect[2]-rect[0]-35)/(xmax-xmin),(rect[3]-rect[1]-35)/(ymax-ymin))
    cx=(rect[0]+rect[2])/2;cy=(rect[1]+rect[3])/2
    def point(xy):return (cx+(xy[0]-(xmin+xmax)/2)*scale,cy-(xy[1]-(ymin+ymax)/2)*scale)
    layer=Image.new('RGBA',im.size);p=ImageDraw.Draw(layer)
    land=json.loads((ROOT/'data/land_projected.json').read_text())
    for poly in land:
        p.polygon([point(np.asarray(v)/1.852) for v in poly[0]],fill='#e0e5df',outline='#afc1b4')
        for hole in poly[1:]:p.polygon([point(np.asarray(v)/1.852) for v in hole],fill='#eaf5fc')
    for xy in lat.net.xy[:-1]:
        x,y=point(xy);p.ellipse((x-1,y-1,x+1,y+1),fill=(60,100,130,70))
    # Forecast tracks and transparent 2m wave envelopes, not simultaneous actual storms.
    states=np.array(record['forecast']['states']);anchor=np.array(record['forecast']['anchor_times'])
    for s in [1,4,7]:
        points=[point(xy/1.852) for xy in states[s,:49:3,:2]]
        p.line(points,fill=(210,106,20,180),width=3)
    for j in [0,12,24,36]:
        x,y,I=states[4,j];peak=c['weather']['peak_wave_m']*I
        if peak>2:
            r=c['weather']['scale_km']*I*math.sqrt(math.log(peak/2))/1.852*scale
            px,py=point([x/1.852,y/1.852]);p.ellipse((px-r,py-r,px+r,py+r),fill=(231,125,34,38),outline=(210,106,20,160),width=2)
    history=before.get('history',[])
    if len(history)>1:
        for a,b in zip(history,history[1:]):
            ratio=min(1,max(0,b['speed_kn']/18));colour=(int(100-95*ratio),int(180-130*ratio),int(220-115*ratio),255)
            p.line([point([a['x_nm'],a['y_nm']]),point([b['x_nm'],b['y_nm']])],fill=colour,width=5)
    if plan['status']=='ok':
        for s,route in enumerate(plan['scenario_routes']):
            if route is None:continue
            pts=[]
            for a in route['actions']:
                if a['action']<0:continue
                curve=lat.net.curves[lat.gid[a['action']]]
                pts.extend(point(v) for v in curve.xy[::6])
            if len(pts)>1:p.line(pts,fill=(119,73,171,65 if s!=4 else 190),width=2 if s!=4 else 4)
        first=plan['first_trajectory'];points=[point(v) for v in np.array(first['controls_nm'])[[0,3]]]
        # Recover exact first curve from execution samples when available.
        samples=record.get('execution',{}).get('samples',[])
        if samples:
            pts=[point([v['x_nm'],v['y_nm']]) for v in samples]
            if len(pts)>1:p.line(pts,fill=(0,117,171,255),width=6)
        x,y=point(np.array(first['controls_nm'])[-1]);p.ellipse((x-6,y-6,x+6,y+6),fill=(0,117,171,255))
    start=point([c['initial']['x_nm'],c['initial']['y_nm']]);goal=point(c['goal_nm'])
    p.rectangle((start[0]-7,start[1]-7,start[0]+7,start[1]+7),fill=navy)
    p.ellipse((goal[0]-8,goal[1]-8,goal[0]+8,goal[1]+8),fill='#13814d')
    p.text((start[0]-95,start[1]-35),'부산',font=font(24,True),fill=navy)
    p.text((goal[0]+15,goal[1]-40),'홍콩',font=font(24,True),fill='#10623c')
    crop=layer.crop(rect);im.paste(crop,rect[:2],crop)
    d.text((1050,125),'현재 결정',font=font(25,True),fill=navy)
    y=170
    lines=[f"최적화 시간  {plan['solve_seconds']:.2f}초",f"현재 속도  {before['speed_kn']:.2f}kn",f"현재 방향  {before['heading_deg']:.2f}°"]
    if plan['status']=='ok':
        chosen=plan['chosen'];tr=plan['first_trajectory']
        lines += [f"후보  {plan['candidate_count']}개 / 가능 {plan['feasible_candidate_count']}개",f"선택  {chosen['label']}",f"초기 계획시간  {tr['duration_h']:.2f}h",f"곡선 이동거리  {tr['distance_nm']:.2f}nm",f"기대 총비용  ${chosen['mean_total_usd']:,.0f}",f"총비용 CVaR  ${chosen['cvar_total_usd']:,.0f}",f"다음 이벤트  {plan['next_event_h']:.4f}h",f"실제 실행 연료  {record['execution']['fuel_t']:.3f}t"]
    for line in lines:
        d.text((1050,y),line,font=font(17),fill=text);y+=33
    if plan['status']=='ok':
        d.text((1050,595),'초기 계획의 연속 속도',font=font(21,True),fill=navy)
        tr=plan['first_trajectory'];t=np.array(tr['profile_times_h']);v=np.array(tr['profile_speeds_kn'])
        plot=(1080,650,1580,810);d.line((plot[0],plot[1],plot[0],plot[3],plot[2],plot[3]),fill='#677889',width=2)
        pts=[(plot[0]+tt/max(t[-1],.01)*(plot[2]-plot[0]),plot[3]-vv/20*(plot[3]-plot[1])) for tt,vv in zip(t,v)]
        d.line(pts,fill=blue,width=4)
        d.text((1050,620),'kn',font=font(15),fill=text);d.text((plot[0],820),'0h',font=font(16),fill=text);d.text((plot[2]-75,820),f'{t[-1]:.2f}h',font=font(16),fill=text)
        d.text((1050,875),'상위 후보 · 초기 + 장기 기대비용',font=font(20,True),fill=navy)
        yy=915
        rows=sorted([r for r in plan['candidates'] if r['objective_usd'] is not None],key=lambda r:r['objective_usd'])[:3]
        for r in rows:
            d.text((1050,yy),f"#{r['candidate']}  {r['duration_h']:.2f}h  ${r['objective_usd']:,.0f}",font=font(18),fill=text);yy+=31
    d.text((35,1055),'청록: 이번 실행 · 청색: 이전 항적  |  보라: 시나리오 미래계획  |  주황: 태풍 예측·2m 영역',font=font(17),fill=text)
    d.text((35,1080),'교육용 운동·기상 근사 / 미래비용은 실제 누적비용과 다름 / 기상 예측만 표시',font=font(15),fill=text)
    return im


def render(output,records,lat,c):
    output=Path(output);(output/'figures').mkdir(exist_ok=True)
    frames=[]
    for r in records:
        path=output/'figures'/f"step_{r['step']:03d}.png"
        if not path.exists():draw_step(r,lat,c).save(path)
        frames.append('data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode())
    rows=[]
    for r in records[-1]['plan'].get('candidates',[]):
        if r['objective_usd'] is None:continue
        rows.append(f"<tr><td>{r['candidate']}</td><td>{html.escape(r['label'])}</td><td>{r['duration_h']:.2f}</td><td>{np.mean(r['scenario_first_usd']):,.2f}</td><td>{np.mean(r['scenario_future_usd']):,.2f}</td><td>{r['objective_usd']:,.2f}</td></tr>")
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>육각·연속 상태 DSS</title><style>body{margin:24px auto;max-width:1450px;padding:0 16px;font-family:"Malgun Gothic",sans-serif;color:#172b40;background:#f5f8fb}header,section{background:white;padding:20px;margin-bottom:16px;border-radius:10px}h1{font-size:24px}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:8px;border-bottom:1px solid #dde5ee}.scroll{overflow:auto}input{width:80%}p{line-height:1.7}</style><header><h1>육각 격자 · 연속 운항 · 이벤트 기반 재계획</h1><p>기존 baseline과 독립된 로컬 실험 · λ=0 / α=0.8 · 최대 재계획 간격 3시간</p><label>의사결정 시점 <input id="frame" type="range" min="0" max="MAX" value="MAX"><span id="value"></span></label></header><section><img id="picture" alt="해상운항 계획·속도·후보 가치"></section><section><h2>마지막 결정의 후보 평가</h2><p>미래비용은 전체 궤적 구간을 포괄하는 보수적 기상 등급과 시나리오별 DP로 계산합니다. 실제 누적 비용과 구분됩니다.</p><div class="scroll"><table><thead><tr><th>후보</th><th>도착 상태</th><th>초기 h</th><th>초기 기대비용</th><th>미래 기대비용</th><th>통합 평가</th></tr></thead><tbody>ROWS</tbody></table></div></section><script>const frames=FRAMES;const slider=document.getElementById('frame');function show(){document.getElementById('picture').src=frames[+slider.value];document.getElementById('value').textContent=(+slider.value+1)+' / '+frames.length;}slider.addEventListener('input',show);show();</script></html>'''
    doc=doc.replace('MAX',str(len(frames)-1)).replace('ROWS',''.join(rows)).replace('FRAMES',json.dumps(frames))
    (output/'dashboard.html').write_text(doc,encoding='utf-8')
