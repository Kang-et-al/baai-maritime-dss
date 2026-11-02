"""Reuse map layout, with command/actual-speed comparison and explicit new dynamics."""
import base64
import copy
import html
import json
from pathlib import Path
import numpy as np
from PIL import ImageDraw
from .report import draw_step,font


def render(output,records,lat,c):
    output=Path(output);(output/'figures').mkdir(exist_ok=True);frames=[]
    for r in records:
        path=output/'figures'/f"step_{r['step']:03d}.png"
        if not path.exists():
            old=copy.deepcopy(r);p=old['plan']
            if p['status']=='ok':
                chosen=p['chosen'];exe=r['execution'];tr=exe.get('trajectory')
                if tr is not None:
                    trace=np.array(tr['trace']);controls=tr['controls_nm'];duration=tr['duration_h'];distance=exe['distance_nm']
                else:
                    s=r['state_before'];duration=exe['duration_h'];distance=0.
                    controls=[[s['x_nm'],s['y_nm']]]*4;trace=np.array([[0,0,0,0,0,0],[duration,0,0,0,0,exe['fuel_t']]])
                p['first_trajectory']={'controls_nm':controls,'profile_times_h':trace[:,0].tolist(),'profile_speeds_kn':trace[:,2].tolist(),'duration_h':duration,'distance_nm':distance}
                p['next_event_h']=r['state_after']['time_h']
                p['chosen']['label']=f"node {chosen['node']} / 추진 {chosen['q_command_kn']:g}kn 상당"
                for row in p['candidates']:row['duration_h']=row['scenario_connector_h'][4]
            im=draw_step(old,lat,c);d=ImageDraw.Draw(im)
            d.rectangle((30,15,1620,110),fill='white')
            d.text((35,22),'추진 명령–실제 속도 DSS | 파고 저항 · 가감속 · 육각망',font=font(28,True),fill='#123759')
            d.text((35,70),f"STEP {r['step']:03d} · λ={c['risk']['lambda']:g} · α={c['risk']['alpha']:g} · 파고별 속도 상한·통과 금지 없음",font=font(19),fill='#172b40')
            if p['status']=='ok':
                t=trace[:,0];q=trace[:,3];plot=(1080,650,1580,810)
                pts=[(plot[0]+tt/max(t[-1],.01)*(plot[2]-plot[0]),plot[3]-qq/20*(plot[3]-plot[1])) for tt,qq in zip(t,q)]
                for i in range(0,len(pts)-1,3):d.line(pts[i:i+2],fill='#d47b0b',width=3)
                d.text((1050,850),'실선: 실제 속도 · 점선: 추진 명령',font=font(16),fill='#172b40')
            im.save(path)
        frames.append('data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode())
    rows=[]
    for a in records[-1]['plan'].get('candidates',[]):
        if a['objective_usd'] is None:continue
        rows.append(f"<tr><td>{a['candidate']}</td><td>{a['node']}</td><td>{a['q_command_kn']:g}</td><td>{a['stop_at_goal']}</td><td>{min(a['scenario_connector_h']):.3f}–{max(a['scenario_connector_h']):.3f}</td><td>{a['objective_usd']:,.2f}</td></tr>")
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>추진 명령–실제 속도 DSS</title><style>body{font-family:"Malgun Gothic",sans-serif;color:#172b40;background:#f5f8fb;max-width:1500px;margin:24px auto;padding:0 14px}section{background:white;padding:20px;margin:16px 0;border-radius:10px}img{width:100%;height:auto}p{line-height:1.7}input{width:75%}table{border-collapse:collapse;width:100%}td,th{padding:9px;text-align:left;border-bottom:1px solid #dde5ee}.scroll{overflow:auto}</style><section><h1>추진 명령–실제 속도 · 파고 저항 모델</h1><p>같은 추진 명령도 파고에 따라 속도·이동시간이 달라집니다. 파고 5m 통과 금지와 기상별 속도 상한은 제거했습니다. 선회·가감속·연료·납기·3시간 최대 재계획 조건은 유지합니다.</p><label>의사결정 시점 <input id="frame" type="range" min="0" max="MAX" value="MAX"><span id="value"></span></label></section><section><img id="picture" alt="추진 명령과 실제 속도·운항 계획"></section><section><h2>후보별 평가</h2><div class="scroll"><table><tr><th>후보</th><th>연결 노드</th><th>추진 명령</th><th>도착 정지</th><th>연결 시간(h)</th><th>통합 기대비용</th></tr>ROWS</table></div><p>미래가치는 시간·속도 보간을 사용하는 근사 DP입니다. 물리 상태를 반올림하지 않으며 연속 상태에서 경로를 다시 모의 실행합니다. 미래 점수와 실제 비용은 다릅니다.</p></section><script>const frames=FRAMES;const s=document.getElementById('frame');function show(){document.getElementById('picture').src=frames[+s.value];document.getElementById('value').textContent=(+s.value+1)+' / '+frames.length;}s.addEventListener('input',show);show();</script></html>'''
    (output/'dashboard.html').write_text(doc.replace('MAX',str(len(frames)-1)).replace('ROWS',''.join(rows)).replace('FRAMES',json.dumps(frames)),encoding='utf-8')
