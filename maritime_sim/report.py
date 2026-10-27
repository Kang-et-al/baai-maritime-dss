"""외부 지도/API 없이 생성하는 PNG 대시보드와 정적 HTML 보고서."""
import csv
import html
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .config import ROOT
from .simulation import read_json
from .weather import contour_radius
from .network import project


def speed_color(speed, future=False):
    ratio=max(0.,min(1.,speed/18))
    light=(131,196,225) if not future else (177,148,210)
    dark=(5,48,102) if not future else (78,24,140)
    return tuple(round(a+(b-a)*ratio) for a,b in zip(light,dark))


def dashed_line(draw, a, b, fill, width=3, dash=9):
    length=math.dist(a,b)
    if length<0.01: return
    for start in range(0,math.ceil(length),dash*2):
        end=min(length,start+dash)
        p=tuple(a[j]+(b[j]-a[j])*start/length for j in range(2))
        q=tuple(a[j]+(b[j]-a[j])*end/length for j in range(2))
        draw.line([p,q],fill=fill,width=width)


def font(size,bold=False):
    candidates=[ROOT/"maritime_sim"/"assets"/"fonts"/("NanumGothic-Bold.ttf" if bold else "NanumGothic-Regular.ttf"),
                Path("C:/Windows/Fonts")/("malgunbd.ttf" if bold else "malgun.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for p in candidates:
        if p.exists(): return ImageFont.truetype(str(p),size)
    return ImageFont.load_default(size=size)


def money(x):
    return "계획 불가" if x is None else f"${x:,.0f}"


def render_step(output,record,net,config):
    output=Path(output); figures=output/"figures"; figures.mkdir(exist_ok=True)
    W,H=1700,1210
    im=Image.new("RGB",(W,H),"#f4f7fb"); d=ImageDraw.Draw(im)
    before=record["state_before"]; after=record["state_after"]; plan=record["plan"]
    title=f"부산 → 홍콩  |  STEP {record['step']:03d}"
    d.text((42,25),title,font=font(32,True),fill="#15334b")
    d.text((42,77),f"실행 구간 {before['time_h']:g}–{after['time_h']:g}시간  ·  {config['mode']}  ·  {after['status']}",font=font(21),fill="#53687a")
    left,top,right,bottom=45,145,1010,1110
    d.rectangle((left,top,right,bottom),fill="#eaf3f8",outline="#d1dfe8",width=2)
    allxy=net.xy; xmin,xmax=-540*1.852,486*1.852; ymin,ymax=-540*1.852,594*1.852
    scale=min((right-left-24)/(xmax-xmin),(bottom-top-24)/(ymax-ymin))
    cx=(left+right)/2; cy=(top+bottom)/2
    def point(xy):
        return (cx+(float(xy[0])-(xmin+xmax)/2)*scale,
                cy-(float(xy[1])-(ymin+ymax)/2)*scale)
    # Draw onto a clipped map layer so off-map tracks never cover KPI text.
    layer=Image.new("RGBA",(W,H),(0,0,0,0)); p=ImageDraw.Draw(layer)
    land=json.loads((ROOT/"data"/"land_projected.json").read_text(encoding="utf-8"))
    for poly in land:
        p.polygon([point(xy) for xy in poly[0]],fill="#d6dfd8",outline="#b9c8bc")
        for hole in poly[1:]: p.polygon([point(xy) for xy in hole],fill="#eaf3f8")
    for xy in allxy:
        x,y=point(xy); p.ellipse((x-0.8,y-0.8,x+0.8,y+0.8),fill="#b3c9d6")
    im.paste(layer.crop((left+2,top+2,right-2,bottom-2)),(left+2,top+2),layer.crop((left+2,top+2,right-2,bottom-2)))
    overlay=Image.new("RGBA",(W,H),(0,0,0,0)); p=ImageDraw.Draw(overlay)
    # Current actual wave contours, only at the displayed current time.
    state=record["actual_typhoon_at_end"]
    x,y=point(state[:2]); peak=config["weather"]["peak_wave_m"]*state[2]
    forecast=record["forecast"]
    representative=forecast.get("representative_index",4)
    hours=forecast["hours"]
    # Forecast footprints use the same 2m/4m/5m contours as the operational field.
    for s in [1,representative,7] if len(forecast['labels'])==9 else [representative]:
        states=forecast["states_xy_km_intensity"][s]
        for t,z in zip(hours,states):
            if after["time_h"]<t<=after["time_h"]+36 and round(t-after["time_h"])%12==0:
                px,py=point(z[:2])
                for level,alpha in [(2,22),(4,35),(5,50)]:
                    rad=contour_radius(z[2],level,config)*scale
                    if rad>0:
                        p.ellipse((px-rad,py-rad,px+rad,py+rad),fill=(230,135,32,alpha),outline=(200,105,20,85),width=1)
                if s==representative:
                    p.text((px+6,py+3),f"+{t-after['time_h']:g}h",font=font(16),fill=(125,66,20,230))
    for s,states in enumerate(forecast["states_xy_km_intensity"]):
        pts=[point(z[:2]) for t,z in zip(hours,states) if t<=before["time_h"]+51 and z[2]>0.02]
        if len(pts)>1: p.line(pts,fill=(214,115,28,235 if s==representative else 115),width=5 if s==representative else 3)
    # Stronger current storm shading; do not reveal its actual future track.
    tx,ty=point(state[:2])
    for level,alpha in [(2,48),(4,85),(5,120),(7,150)]:
        rad=contour_radius(state[2],level,config)*scale
        if rad>0: p.ellipse((tx-rad,ty-rad,tx+rad,ty+rad),fill=(211,67,42,alpha),outline=(173,48,25,180),width=2)
    # Conditional future ship routes: low alpha, central scenario emphasized.
    for s,route in enumerate(plan["scenario_routes"]):
        if route:
            for a in route:
                pa=point(net.xy[net.index[a['from_node']]]); pb=point(net.xy[net.index[a['to_node']]])
                color=speed_color(a['effective_kn'],True)+(225 if s==representative else 65,)
                dashed_line(p,pa,pb,color,5 if s==representative else 3,dash=7)
    crop=overlay.crop((left+2,top+2,right-2,bottom-2))
    im.paste(crop,(left+2,top+2),crop)
    d=ImageDraw.Draw(im)
    for saved in sorted((output/'steps').glob('step_*.json')):
        past=read_json(saved)
        if past['step']>record['step']: break
        for a in past['plan']['first_actions']:
            pa=point(net.xy[net.index[a['from_node']]]); pb=point(net.xy[net.index[a['to_node']]])
            if pa==pb:
                d.ellipse((pa[0]-4,pa[1]-4,pa[0]+4,pa[1]+4),outline='#07516e',width=2)
            else:
                d.line([pa,pb],fill='white',width=11)
                d.line([pa,pb],fill=speed_color(a['effective_kn']),width=7)
    executed=plan["first_actions"]
    if executed:
        pts=[point(net.xy[net.index[executed[0]["from_node"]]])]
        pts.extend(point(net.xy[net.index[a["to_node"]]]) for a in executed)
        d.line(pts,fill="#24a6aa",width=12)
        for a in executed:
            d.line([point(net.xy[net.index[a['from_node']]]),point(net.xy[net.index[a['to_node']]])],fill=speed_color(a['effective_kn']),width=7)
    bx,by=point(net.xy[net.index[before["node"]]])
    d.rectangle((bx-8,by-8,bx+8,by+8),fill="#f4f7fb",outline="#087f8c",width=3)
    x,y=point(net.xy[net.index[after["node"]]])
    d.ellipse((x-12,y-12,x+12,y+12),fill="#087f8c",outline="white",width=3)
    for nid,label,lon,lat in [(config["start_node"],"부산 · 출발",128.3,36.0),(config["goal_node"],"홍콩 · 도착",113.9,23.2)]:
        px,py=point(net.xy[net.index[nid]])
        if nid==config['start_node']:
            d.ellipse((px-10,py-10,px+10,py+10),outline='#15334b',width=4)
        else:
            d.polygon([(px,py-12),(px+12,py),(px,py+12),(px-12,py)],fill='#7b298a',outline='white',width=2)
        lx,ly=point(project(lon,lat))
        d.text((lx,ly),label,anchor='mm',font=font(29,True),fill="#15334b",stroke_width=3,stroke_fill="#eaf3f8")
    if peak>0.05 and left<x<right:
        tx,ty=point(state[:2])
        if left<tx<right and top<ty<bottom:
            d.ellipse((tx-5,ty-5,tx+5,ty+5),fill="#cb681b")
    x0=1050
    total=after["operating_cost_usd"]+after["late_cost_usd"]
    cards=[("출항 후 경과시간",f"{after['time_h']:g} h"),
           ("현재 위치",f"N{after['node']}"),
           ("누적 연료",f"{after['fuel_t']:.3f} t"),
           ("누적 실제 비용",money(total)),
           ("누적 이동 / 대기",f"{after['distance_nm']:g} nm / {after['waiting_h']:g} h"),
           ("납기 / 현재 초과시간",f"{after['due_h']:g} h / {max(0,after['time_h']-after['due_h']):g} h")]
    for idx,(label,value) in enumerate(cards):
        yy=145+idx*98
        d.rounded_rectangle((x0,yy,1655,yy+86),radius=12,fill="white",outline="#dbe3ed")
        d.text((x0+20,yy+10),label,font=font(18),fill="#53687a")
        d.text((x0+20,yy+36),value,font=font(27,True),fill="#15334b")
    yy=755
    d.text((x0,yy),"이번 의사결정",font=font(23,True),fill="#15334b")
    risk_mode=plan.get("objective_type")=="mean_cvar"
    if risk_mode:
        lines=[f"계산 기준시점: 출항 후 {before['time_h']:g}시간",
               f"Mean-CVaR 평가: {money(plan['objective_total_usd'])}",
               f"이후 평균 {money(plan['mean_remaining_usd'])} / CVaR {money(plan['cvar_remaining_usd'])}",
               f"후보 {plan['candidate_count']}개 · 계산 {plan['solve_seconds']:.2f}초",
               f"λ={plan['risk_lambda']:g} / α={plan['cvar_alpha']:g}"]
    else:
        lines=[f"계산 기준시점: 출항 후 {before['time_h']:g}시간",
               f"잔여 기대비용: {money(plan['expected_total_usd'])}",
               f"후보 {plan['candidate_count']}개 · 시나리오 {len(forecast['labels'])}개",
               f"계산시간: {plan['solve_seconds']:.2f}초"]
    if plan["scenario_routes"]:
        eta=plan["scenario_routes"][representative][-1]["end_h"] if plan["scenario_routes"][representative] else after["time_h"]
        lines.append(f"기준 시나리오 예상 도착: {eta:g}시간")
    for j,line in enumerate(lines): d.text((x0,yy+42+j*(30 if risk_mode else 35)),line,font=font(19),fill="#334e66")
    legend=[("#174e83","실제 항적: 진할수록 빠름 (실효속도)"),("#087f8c","이번 실행 테두리 · 현재 ● / 이전 □"),
            ("#7430a2","미래 선박 경로: 보라 점선"),("#cf792e","예측 영향권: 주황 / 현재 영향권: 빨강")]
    for j,(color,label) in enumerate(legend):
        yy=985+j*32; d.line((x0,yy+10,x0+30,yy+10),fill=color,width=4)
        d.text((x0+42,yy-2),label,font=font(17),fill="#53687a")
    d.text((45,1140),"18해리 격자 · 15분 시간층 · 미래 선박 경로는 각 시나리오가 알려졌다고 가정한 조건부 계획",font=font(18),fill="#53687a")
    d.text((45,1172),"기상 API 미사용 · 합성 파고 / 예시 비용 · 육지: Natural Earth 1:10m · 미래 태풍 예측은 다음 48시간 표시",font=font(17),fill="#53687a")
    path=figures/f"step_{record['step']:03d}.png"; im.save(path)
    return path


def render_archive(output):
    output=Path(output); records=[read_json(p) for p in sorted((output/"steps").glob("step_*.json"))]
    state=read_json(output/"state.json")
    rows=[]
    for r in records:
        s=r["state_after"]; p=r["plan"]
        rows.append({"step":r["step"],"time_h":s["time_h"],"node":s["node"],"status":s["status"],
                     "fuel_t":s["fuel_t"],"actual_cost_usd":s["operating_cost_usd"]+s["late_cost_usd"],
                     "distance_nm":s["distance_nm"],"waiting_h":s["waiting_h"],
                     "expected_remaining_at_decision_usd":p["expected_total_usd"],
                     "objective_at_decision_usd":p.get("objective_total_usd",p["expected_total_usd"]),
                     "mean_future_usd":p.get("mean_remaining_usd"),"cvar_future_usd":p.get("cvar_remaining_usd"),
                     "risk_lambda":p.get("risk_lambda"),"cvar_alpha":p.get("cvar_alpha"),
                     "objective_type":p.get("objective_type","expectation"),"solve_seconds":p["solve_seconds"]})
    if rows:
        with (output/"summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>부산–홍콩 시뮬레이션</title><style>body{font:16px/1.6 system-ui;margin:32px auto;max-width:1400px;padding:0 18px;background:#f4f7fb;color:#15334b}img{width:100%;border-radius:12px}article{background:white;padding:22px;margin:24px 0;border-radius:12px}table{border-collapse:collapse;width:100%}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}a{color:#087f8c}.kpi{font-size:20px}</style>',
           '<h1>부산 → 홍콩 롤링 시뮬레이션</h1>',
           f'<p class="kpi">상태: {html.escape(state["status"])} · 경과 {state["time_h"]:g}시간 · N{state["node"]} · 연료 {state["fuel_t"]:.3f}톤 · 실제 비용 {money(state["operating_cost_usd"]+state["late_cost_usd"])}</p>',
           '<p>첫 3시간만 실행합니다. 보라색 경로는 시나리오별 조건부 미래 계획입니다. 태풍의 숨겨진 실제 미래는 표시하지 않습니다.</p>',
           '<p><a href="summary.csv">KPI CSV</a> · <a href="config.json">실험 설정</a> · <a href="manifest.json">재현 정보</a></p>']
    for r in records:
        n=r["step"]; s=r["state_after"]; plan=r["plan"]
        parts.append(f'<article id="step-{n}"><h2>STEP {n:03d} · {s["time_h"]:g}시간 · N{s["node"]}</h2>')
        if (output/"figures"/f"step_{n:03d}.png").exists():
            parts.append(f'<a href="figures/step_{n:03d}.png"><img loading="lazy" alt="스텝 {n} 대시보드" src="figures/step_{n:03d}.png"></a>')
        else:
            parts.append('<p>그림 미생성: render 명령으로 추가할 수 있습니다.</p>')
        if plan.get("objective_type")=="mean_cvar":
            parts.append(f'<p>Mean-CVaR 평가값: {money(plan["objective_total_usd"])} · 1단계 포함 평균비용: {money(plan["expected_total_usd"])} · 이후 CVaR: {money(plan["cvar_remaining_usd"])} · λ={plan["risk_lambda"]:g}, α={plan["cvar_alpha"]:g} · <a href="steps/step_{n:03d}.json">전체 스텝 데이터</a></p>')
        else:
            parts.append(f'<p>결정 시점 잔여 기대비용: {money(plan["expected_total_usd"])} · <a href="steps/step_{n:03d}.json">전체 스텝 데이터</a></p>')
        parts.append('<details><summary>시나리오별 예상 도착시각</summary><table><tr><th>시나리오</th><th>출항 이후 시간</th></tr>')
        for label,route in zip(r["forecast"]["labels"],plan["scenario_routes"]):
            eta=route[-1]["end_h"] if route else s["time_h"]
            parts.append(f'<tr><td>{html.escape(label)}</td><td>{eta:g}시간</td></tr>')
        parts.append('</table></details></article>')
    parts.append('</html>'); (output/"archive.html").write_text('\n'.join(parts),encoding="utf-8")


def render_index(output):
    render_archive(output)
    from .replay import export_replay
    export_replay(output)


def render_saved(output,steps=None):
    from .network import Network
    output=Path(output); net=Network(); config=read_json(output/"config.json")
    paths=[]
    for path in sorted((output/"steps").glob("step_*.json")):
        r=read_json(path)
        if steps is None or r["step"] in steps:
            paths.append(render_step(output,r,net,config))
    render_index(output)
    return paths
