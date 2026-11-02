"""Read completed new runs only; no planner or old DP calls."""
import json,math,html
from pathlib import Path
import numpy as np
from hex_dss.config import ROOT

def analyse(mode):
    out=ROOT/f'outputs/selective_voyage_{mode}';status=json.loads((out/'status.json').read_text());assert status['status']=='arrived',status
    rr=[json.loads(p.read_text()) for p in sorted((out/'steps').glob('*.json'))];c=json.loads((out/'config.json').read_text());s=rr[-1]['state_after']
    assert rr[-1]['arrived'] and math.dist([s['x_nm'],s['y_nm']],c['goal_nm'])<1e-5 and s['speed_kn']<1e-3
    for i,r in enumerate(rr):
        before=c['initial'] if i==0 else rr[i-1]['state_after']
        for k in ['time_h','x_nm','y_nm','speed_kn','heading_deg']:assert abs(before[k]-r['state_before'][k])<1e-8
        assert abs(r['execution']['duration_h']-(r['state_after']['time_h']-r['state_before']['time_h']))<1e-8
        assert 0<r['execution']['duration_h']<=3+1e-7
        if i<len(rr)-1:assert abs(r['execution']['duration_h']-3)<1e-7
    h=s['history'];a=np.array([[p['time_h'],p['speed_kn'],p.get('wave_m',0),p.get('q_command_kn',0)] for p in h]);dt=np.diff(a[:,0]);valid=dt>1e-9
    acceleration=np.diff(a[:,1])[valid]/dt[valid]
    # Existing integrate() snaps a reached service-stop residual <1e-4kn to0.
    # Check the speed residual at an actual reached terminal, not an arbitrary
    # widened acceleration tolerance or altered simulation output.
    stop_times=[]
    for r in rr:
        for part in r['execution']['parts']:
            tr=part.get('trajectory')
            if tr and tr['stop_at_goal'] and tr['reached']:stop_times.append(tr['start_h']+tr['duration_h'])
    snap_events=[]
    for i in np.flatnonzero(valid):
        dv=a[i+1,1]-a[i,1];assert dv<=24*dt[i]+1e-7
        residual=max(0.,-dv-24*dt[i])
        if residual>1e-7:
            assert a[i+1,1]==0 and a[i+1,3]==0 and residual<=1e-4+1e-8
            assert any(abs(a[i+1,0]-tt)<1e-7 for tt in stop_times)
            snap_events.append({'time_h':float(a[i+1,0]),'residual_speed_kn':float(residual),'raw_difference_acceleration':float(dv/dt[i])})
    fuel=sum(r['execution']['fuel_t'] for r in rr);cost=sum(r['execution']['cost_usd'] for r in rr)
    assert abs(fuel-s['fuel_t'])<1e-6 and abs(cost-s['operating_cost_usd'])<1e-5
    from shapely.geometry import Polygon,LineString
    import shapely
    polys=[]
    for p in json.loads((ROOT/'data/land_projected.json').read_text()):
        poly=Polygon(np.array(p[0])/1.852,[np.array(hh)/1.852 for hh in p[1:]])
        polys.append(shapely.make_valid(poly) if not poly.is_valid else poly)
    land=shapely.union_all(polys).buffer(c['safety_buffer_nm']);track=LineString([[p['x_nm'],p['y_nm']] for p in h])
    late=1000*max(0,s['time_h']-c['due_h']);times=[r['plan']['solve_seconds'] for r in rr]
    peak_record=max(h,key=lambda p:p.get('wave_m',0))
    result={'mode':mode,'arrived':True,'steps':len(rr),'arrival_h':s['time_h'],'distance_nm':s['distance_nm'],'fuel_t':fuel,
       'operating_cost_usd':cost,'late_cost_usd':late,'total_cost_usd':cost+late,'max_wave_m':float(a[:,2].max()),
       'wave_exposure_h':{str(threshold):float(dt[a[:-1,2]>=threshold].sum()) for threshold in [2,4,6]},
       'near_stationary_h':float(dt[a[:-1,1]<.1].sum()),'max_speed_kn':float(a[:,1].max()),
       'high_propulsion_h':float(dt[a[:-1,3]>=17.9].sum()),
       'high_propulsion_low_speed_high_wave_h':float(dt[(a[:-1,3]>=17.9)&(a[:-1,1]<6)&(a[:-1,2]>=4)].sum()),
       'acceleration_range_kn_per_h':[float(acceleration.min()),float(acceleration.max())],
       'existing_terminal_zero_speed_snap_events':snap_events,
       'track_intersects_land_buffer':bool(land.intersects(track)),'decision_seconds_sum_recorded':sum(times),'decision_seconds_max':max(times),
       'chosen_command_counts':{str(q):sum(r['plan']['chosen']['q_command_kn']==q for r in rr) for q in [0,6,12,18]},
       'waiting_decisions':sum(r['plan']['chosen']['wait'] for r in rr),
       'executed_wait_h':sum(part['duration_h'] for r in rr for part in r['execution']['parts'] if part['status']=='wait'),
       'peak_wave_observation':{key:peak_record.get(key,0) for key in ['time_h','wave_m','speed_kn','q_command_kn']},
       'main_dp_counters':[sum(p['counters'][j] for r in rr for p in r['plan']['profiles']) for j in range(5)],
       'timing_note':'Initial interrupted/restarted decisions exclude pre-restart wall time; counters cover main DP only, not continuous rollout queries.'}
    return result,h,rr,c

def main():
    ty,h1,rr1,c=analyse('typhoon');ca,h2,rr2,_=analyse('calm');out=ROOT/'outputs/selective_voyage_comparison';out.mkdir(exist_ok=True)
    cf1=dict(c);cf2=json.loads((ROOT/'outputs/selective_voyage_calm/config.json').read_text());cf1.pop('mode');cf2.pop('mode');assert cf1==cf2
    identities=[json.loads((ROOT/f'outputs/selective_voyage_{mode}/identity.json').read_text()) for mode in ['typhoon','calm']]
    assert identities[0]['core']==identities[1]['core']
    for name in ['kernel.py','kernel_threaded.py']:assert identities[0]['engine'][name]==identities[1]['engine'][name]
    result={'verification':'passed' if not ty['track_intersects_land_buffer'] and not ca['track_intersects_land_buffer'] else 'land_geometry_issue',
            'same_model_except_weather_mode':True,'typhoon':ty,'calm':ca,'difference_typhoon_minus_calm':{k:ty[k]-ca[k] for k in ['arrival_h','distance_nm','fuel_t','total_cost_usd']}}
    (out/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    rows='\n'.join(f'| {label} | {ca[key]:,.3f} | {ty[key]:,.3f} | {ty[key]-ca[key]:+,.3f} |' for label,key in [('도착시간(h)','arrival_h'),('거리(nm)','distance_nm'),('연료(t)','fuel_t'),('총비용($)','total_cost_usd'),('최대 파고(m)','max_wave_m')])
    md=f'''# 선택적 DP 태풍·무태풍 완주 비교

두 실험 모두 새 선택적 DP로 출항부터 도착까지 계산했다. 3시간마다 관측·시나리오를 갱신했으며, 마지막 도착 구간만 3시간보다 짧을 수 있다. 기존 전체DP·기존 무태풍 결과를 계산에 재사용하지 않았다. 태풍9개 시나리오를 공유메모리 최대9스레드로 평가하고, 무태풍의 동일9개 시나리오는 새로운 선택적 DP1회 결과를 공유했다.

| KPI | 무태풍 | 태풍 | 태풍−무태풍 |
|---|---:|---:|---:|
{rows}

태풍 결정수 {ty['steps']}, 무태풍 결정수 {ca['steps']}. 지연비는 각각 ${ty['late_cost_usd']:,.2f}, ${ca['late_cost_usd']:,.2f}다. 태풍의2/4/6m 이상 노출시간은 {ty['wave_exposure_h']}h, 거의 정체한 시간(실제속도0.1kn 미만)은 {ty['near_stationary_h']:.3f}h다. 이는 전복이나 안전확률 판정이 아니다.

선택 추진명령 횟수: 태풍 {ty['chosen_command_counts']}, 무태풍 {ca['chosen_command_counts']}. 추진명령은 실제속도와 다르며, 파고·선회·제동으로 실제속도가 변한다. 도착·시간연결·연료/비용 합계·가감속 한계를 검사했다. 가감속 검사는 기존 종단 정지의1e-4kn 미만 잔차를0으로 맞추는 규칙을 명시적으로 포함한다. 태풍의 해당 종단 표본은 {len(ty['existing_terminal_zero_speed_snap_events'])}개이며 최대 속도 잔차는 {max([p['residual_speed_kn'] for p in ty['existing_terminal_zero_speed_snap_events']] or [0]):.8f}kn이다. 결과·운동식을 수정하지 않았고 나머지 증분은24kn/h 이내다. 상세 표본은 comparison.json에 보존했다. 실제 표본 항적의 육지 완충구역 교차 여부: 태풍 {ty['track_intersects_land_buffer']}, 무태풍 {ca['track_intersects_land_buffer']}.

실행 기록상 대기는 태풍 {ty['executed_wait_h']:.3f}h, 무태풍 {ca['executed_wait_h']:.3f}h다. 이는 초기 연결 후 같은3시간 구간 안에서 중앙 참고경로의 대기를 실행한 것까지 포함한다. 따라서 첫 단계 대기 후보 선택 횟수0을 실제 대기가 없었다는 뜻으로 해석하지 않는다.

기록된 의사결정 시간 합계는 태풍 {ty['decision_seconds_sum_recorded']:.1f}s, 무태풍 {ca['decision_seconds_sum_recorded']:.1f}s이고, 최대는 {ty['decision_seconds_max']:.1f}s / {ca['decision_seconds_max']:.1f}s다. 스레드 전환 시 중단·재개 전의 벽시계 시간은 일부 결정의 solve_seconds에 합산되지 않으므로 이 합계를 실험 전체 활동시간으로 해석하지 않는다.

현재는 유한 후보·시간/속도 보간DP와 연속 참고경로 재검증을 결합한 오프라인 모의실험이다. 연속 전역 최적성·실선 적합성·해난 안전성을 검증한 것은 아니다. 원래 baseline과 이전 연산 방식, 기존 결과는 보존하고 GitHub에는 업로드하지 않았다.

시점별 관찰은 각 실험의 dashboard.html을, 실제 항적 비교는 비교 폴더의 comparison.html을 사용한다.
'''
    peak=ty['peak_wave_observation']
    md+=f"\n## 실제 파고 저항의 실행 사례\n\n출항 후 {peak['time_h']:.3f}h, 실제 파고 {peak['wave_m']:.3f}m에서 적용 추진 수준은 {peak['q_command_kn']:.1f}kn 상당, 실제 속도는 {peak['speed_kn']:.3f}kn이었다. 추진 명령과 실제 속도를 분리한 운동 모형의 실행 기록이다. 별도 파고별 속도상한이나 통과금지를 적용한 결과가 아니다.\n"
    md+=f"\n실제 고추진(17.9kn 상당 이상) 적용시간은 태풍 {ty['high_propulsion_h']:.3f}h, 무태풍 {ca['high_propulsion_h']:.3f}h다. 태풍의 고추진·실제6kn 미만·파고4m 이상이 동시에 기록된 시간은 {ty['high_propulsion_low_speed_high_wave_h']:.3f}h다. 결정시점의 명령 횟수와 실제 적용시간은 구분한다.\n"
    for record in rr1:
        chosen=record['plan']['chosen']
        if chosen['q_command_kn']!=18:continue
        alternatives=[r for r in record['plan']['candidates'] if r['node']==chosen['node'] and r['stop_at_goal']==chosen['stop_at_goal'] and r['objective_usd'] is not None]
        if len({r['q_command_kn'] for r in alternatives})<2:continue
        md+='\n## 한 시점의 추진 선택 사례\n\n'
        md+=f"출항 후 {record['state_before']['time_h']:.1f}h, 같은 목표 노드{chosen['node']}·같은 정지 여부의 후보를 비교했다. 아래 비용은 실제 누적비용이 아니라 당시 예측9개에 대한 후보 평가다. λ=0이므로 초기비용 평균+잔여비용 평균이 선택 목적값이다.\n\n| 추진(kn 상당) | 초기비용 평균($) | 잔여비용 평균($) | 목적값($) |\n|---|---:|---:|---:|\n"
        for r in sorted(alternatives,key=lambda r:r['q_command_kn']):md+=f"| {r['q_command_kn']:g} | {np.mean(r['scenario_first_usd']):,.2f} | {np.mean(r['scenario_future_usd']):,.2f} | {r['objective_usd']:,.2f} |\n"
        md+='\n이 비교는 동일한 현재 상태에서의 선택 근거를 보여준다. 최종 실제 운항비가 이 예측 평가와 같거나, 이것만으로 연속 공간 전역 최적성이 증명되는 것은 아니다.\n'
        break
    (ROOT/'docs/SELECTIVE_VOYAGE_RESULTS.md').write_text(md,encoding='utf-8')
    # Standalone overlay: both actual tracks and actual storm-centre history.
    B=c['bounds_nm'];scale=min(1000/(B[1]-B[0]),1050/(B[3]-B[2]));pt=lambda xy:(40+(xy[0]-B[0])*scale,1100-(xy[1]-B[2])*scale)
    def points(xys):return ' '.join(f'{pt(p)[0]:.2f},{pt(p)[1]:.2f}' for p in xys)
    svg=[]
    for p in json.loads((ROOT/'data/land_projected.json').read_text()):svg.append(f'<polygon points="{points(np.array(p[0])/1.852)}" fill="#d8e5d1" stroke="#8aa180" stroke-width=".6"/>')
    from hex_dss.weather import World
    world=World(c);ts=np.arange(0,ty['arrival_h']+.1,3);storms=world.storm(ts)
    for t in range(0,int(min(ty['arrival_h'],72))+1,12):
        storm=world.storm(t);I=storm[2]
        for H,color in [(1,'#ffae57'),(2,'#ff7a22'),(4,'#ed3e26'),(6,'#ac1124')]:
            if 10*I>H:
                x,y=pt(storm[:2]/1.852);r=280*I*math.sqrt(math.log(10*I/H))/1.852*scale
                svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" fill-opacity=".08" stroke="{color}" stroke-opacity=".6"/>')
        if I>0:
            x,y=pt(storm[:2]/1.852);svg.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#b62418"/><text x="{x+7}" y="{y-7}" fill="#9b281b" font-size="17">{t}h</text>')
    svg.append(f'<polyline points="{points(storms[:,:2]/1.852)}" fill="none" stroke="#d34522" stroke-width="3" stroke-dasharray="7 5"/>')
    for h,color,dash in [(h2,'#666','8 5'),(h1,'#0752a0','')]:svg.append(f'<polyline points="{points([[p["x_nm"],p["y_nm"]] for p in h])}" fill="none" stroke="{color}" stroke-width="4" stroke-dasharray="{dash}"/>')
    for xy,label,color in [([c['initial']['x_nm'],c['initial']['y_nm']],'부산','#1455b8'),(c['goal_nm'],'홍콩','#16833a')]:
        x,y=pt(xy);svg.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}" stroke="white" stroke-width="2"/><text x="{x+12}" y="{y-12}" font-size="25" font-weight="bold" fill="#071b30">{label}</text>')
    doc='<meta charset="utf-8"><style>body{font:16px Malgun Gothic,sans-serif;max-width:1200px;margin:30px auto;line-height:1.7}svg{width:100%;background:#e9f6ff}pre{white-space:pre-wrap}</style><h1>선택적 DP 완주 비교</h1><p>파랑 실선: 태풍 / 회색 점선: 무태풍 / 주황 점선·범위: 실제 태풍 전개와12시간 간격 파고 등고선</p><svg viewBox="0 0 1100 1150">'+''.join(svg)+'</svg><pre>'+html.escape(md)+'</pre>'
    (out/'comparison.html').write_text(doc,encoding='utf-8')
    # Time profiles expose temporal adaptation even when spatial routes overlap.
    max_t=max(ty['arrival_h'],ca['arrival_h']);chart=['<rect x="55" y="20" width="1000" height="260" fill="#f2f7fc"/>']
    for speed in [0,6,12,18]:
        y=280-speed/20*260
        chart.append(f'<path d="M55 {y}H1055" stroke="#c4d5e5"/><text x="15" y="{y+5}" font-size="14">{speed}</text>')
    for H in [0,2,4,6,8,10]:chart.append(f'<text x="1060" y="{285-H/10*260}" fill="#ce2828" font-size="14">{H}</text>')
    for hh in range(0,int(max_t)+1,12):
        x=55+1000*hh/max_t;chart.append(f'<text x="{x}" y="310" font-size="14">{hh}h</text>')
    for h,key,color,dash,factor in [(h2,'speed_kn','#777','7 4',20),(h1,'speed_kn','#0752a0','',20),(h1,'q_command_kn','#df8a08','3 4',20),(h1,'wave_m','#ce2828','',10)]:
        pts=' '.join(f'{55+p["time_h"]/max_t*1000:.2f},{280-p.get(key,0)/factor*260:.2f}' for p in h[::3])
        chart.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>')
    panel='<h2>시간별 실제 속도·추진·파고</h2><p>파랑: 태풍 실제속도 / 회색 점선: 무태풍 실제속도 / 주황 점선: 태풍 적용 추진 수준(kn 상당) / 빨강: 태풍 실제 파고(오른쪽 기준0~10m, 그래프 높이 전체)</p><svg viewBox="0 0 1100 330">'+''.join(chart)+'</svg>'
    nav='<p><a href="../selective_voyage_typhoon/dashboard.html">태풍 시점별 재생</a> · <a href="../selective_voyage_calm/dashboard.html">무태풍 시점별 재생</a></p>'
    (out/'comparison.html').write_text(doc.replace('<pre>',nav+panel+'<pre>'),encoding='utf-8')
    # Regenerate final replay with latest visualization module.
    from hex_dss.propulsion import build
    from experimental_dp.voyage_report import render
    for mode,rr in [('typhoon',rr1),('calm',rr2)]:
        cfg=json.loads((ROOT/f'outputs/selective_voyage_{mode}/config.json').read_text());lat=build(cfg,lambda _:None)
        render(ROOT/f'outputs/selective_voyage_{mode}',rr,lat,cfg)
    print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
