"""완주 재생/단계별 실시간 실험의 동일한 시간 탐색기. 저장 데이터만 사용한다."""
import json
from pathlib import Path
from .config import ROOT
from .network import Network, project
from .simulation import read_json

FORMATS={"replay":"완주 재생 실험", "live":"단계별 실시간 실험"}


def _actions(actions):
    return [[a['from_node'],a['to_node'],round(a['effective_kn'],2),round(a['start_h'],2),round(a['end_h'],2)] for a in actions]


def build_payload(output):
    output=Path(output); config=read_json(output/'config.json'); net=Network()
    records=[read_json(p) for p in sorted((output/'steps').glob('step_*.json'))]
    state=read_json(output/'state.json')
    presentation=read_json(output/'presentation.json') if (output/'presentation.json').exists() else {'format':'live'}
    frames=[]; executed=[]
    def frame(r,s,terminal=False):
        f=r['forecast']; rep=f.get('representative_index',4)
        tracks=[]
        if not terminal:
            indices=[1,rep,7] if len(f['labels'])==9 else [rep]
            for index in indices:
                samples=[]
                for h,z in zip(f['hours'],f['states_xy_km_intensity'][index]):
                    ahead=h-s['time_h']
                    if 0<=ahead<=48 and (round(ahead)%3==0):
                        samples.append([round(z[0],1),round(z[1],1),round(z[2],3),round(h,2)])
                tracks.append(samples)
        current=r['actual_typhoon_at_end'] if terminal or s is r['state_after'] else r['observation']['states'][0]
        return {'step':r['step'],'time':s['time_h'],'node':s['node'],'fuel':round(s['fuel_t'],3),
                'cost':round(s['operating_cost_usd']+s['late_cost_usd'],2),'distance':s['distance_nm'],
                'wait':s['waiting_h'],'due':s['due_h'],'status':s['status'],
                'issued':r['state_before']['time_h'],'expected':r['plan']['expected_total_usd'],
                'objective':r['plan'].get('objective_total_usd',r['plan']['expected_total_usd']),
                'objective_type':r['plan'].get('objective_type','expectation'),
                'mean_future':r['plan'].get('mean_remaining_usd'),
                'cvar_future':r['plan'].get('cvar_remaining_usd'),
                'risk_lambda':r['plan'].get('risk_lambda'),'cvar_alpha':r['plan'].get('cvar_alpha'),
                'storm':[round(x,3) for x in current], 'tracks':tracks,
                'future':[] if terminal else [_actions(route) for route in r['plan']['scenario_routes']],
                'first':[] if terminal or s is r['state_after'] else _actions(r['plan']['first_actions']),
                'representative':rep,'terminal':terminal}
    for r in records:
        frames.append(frame(r,r['state_before']))
        executed.extend(_actions(r['plan']['first_actions']))
    if records:
        terminal=state['status']!='running'
        frames.append(frame(records[-1],records[-1]['state_after'],terminal))
    land=read_json(ROOT/'data'/'land_projected.json')
    # Geometry remains sourced Natural Earth, only precision is reduced for delivery.
    land=[[[[round(x,1),round(y,1)] for x,y in ring] for ring in poly] for poly in land]
    return {'name':FORMATS[presentation['format']],'format':presentation['format'],
            'baseline_id':config.get('baseline_id','legacy-expectation'),
            'run':output.name,'weather':config['weather'],
            'start':config['start_node'],'goal':config['goal_node'],
            'labels':[project(128.3,36).round(1).tolist(),project(113.9,23.2).round(1).tolist()],
            'land':{'type':'MultiPolygon','coordinates':land},
            'xy':{str(int(n)):xy.round(1).tolist() for n,xy in zip(net.ids,net.xy)},
            'executed':executed,'frames':frames,'final':{k:v for k,v in state.items() if k!='history'}}


def export_replay(output,inline_path=None):
    output=Path(output); payload=build_payload(output)
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</','<\\/')
    template=(ROOT/'maritime_sim'/'assets'/'replay.html').read_text(encoding='utf-8')
    fragment=template.replace('__REPLAY_DATA__',encoded)
    (output/'replay_data.json').write_text(encoded,encoding='utf-8')
    # No network resources or fetch needed by the standalone viewer.
    css='''<style>:root{--background:#f4f7fb;--foreground:#15334b;--card:white;--card-foreground:#15334b;--muted:#e8eef3;--muted-foreground:#53687a;--border:#c9d8df;--viz-series-1:#125597;--viz-series-2:#7b35af;--viz-series-3:#ce781e;--viz-series-4:#cc422c;--viz-series-5:#008a8e;--font-size-base:16px;color-scheme:light}body{font:16px/1.5 system-ui;margin:20px auto;max-width:1400px;padding:0 16px;background:var(--background);color:var(--foreground)}button,input{font:inherit}button{padding:8px 14px}.card{background:var(--card);padding:16px;border-radius:12px}.text-muted{color:var(--muted-foreground)}.text-small{font-size:14px}.form-range{width:100%;accent-color:var(--viz-series-1)}.btn{cursor:pointer}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.viz-controls,.viz-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center}</style>'''
    refresh='<script>function liveRefresh(){const r=document.getElementById("baai-voyage-replay");if(r.dataset.viewerFrame===r.dataset.viewerLast)location.reload();else setTimeout(liveRefresh,5000)}setTimeout(liveRefresh,5000)</script>' if payload['format']=='live' and payload['final']['status']=='running' else ''
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>부산–홍콩 시간 재생</title>'+css+fragment+'<p><a href="archive.html">기존 스텝별 그림·기록</a> · <a href="summary.csv">KPI CSV</a> · <a href="config.json">실험 설정</a></p>'+refresh+'</html>'
    (output/'dashboard.html').write_text(page,encoding='utf-8')
    if inline_path:
        # d3-geo identity projects the already projected, sourced geometry for inline display.
        fragment='<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>\n'+fragment
        if len(fragment.encode('utf-8'))>1_000_000:
            raise ValueError('Inline replay exceeds 1 MB; reduce delivered route precision/detail')
        Path(inline_path).write_text(fragment,encoding='utf-8')
    return output/'dashboard.html'
