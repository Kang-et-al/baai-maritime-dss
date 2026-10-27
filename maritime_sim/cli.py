"""python -m maritime_sim: 실행·이어하기·그림 재생성."""
import argparse
from pathlib import Path
from .config import ROOT, load_config
from .simulation import Simulation


def main():
    p=argparse.ArgumentParser(description="부산–홍콩 롤링 해상운항 시뮬레이터")
    sub=p.add_subparsers(dest="command",required=True)
    run=sub.add_parser("run",help="새 실험 또는 저장된 실험 이어하기")
    run.add_argument("--output",type=Path,required=True)
    run.add_argument("--config",type=Path)
    run.add_argument("--mode",choices=["calm","typhoon"])
    count=run.add_mutually_exclusive_group()
    count.add_argument("--steps",type=int)
    count.add_argument("--until-arrival",action="store_true")
    run.add_argument("--resume",action="store_true")
    run.add_argument("--no-render",action="store_true")
    run.add_argument("--experiment",choices=["replay","live"],help="replay: 완주 재생 실험 / live: 단계별 실시간 실험")
    render=sub.add_parser("render",help="저장된 결과에서 그림만 재생성")
    render.add_argument("--run",type=Path,required=True)
    render.add_argument("--steps",type=int,nargs="+")
    info=sub.add_parser("inspect",help="저장 상태 확인")
    info.add_argument("--run",type=Path,required=True)
    sub.add_parser("baseline",help="확정한 baseline 파일·모델·시각화 해시 확인 (실험 실행 없음)")
    args=p.parse_args()
    try:
        if args.command=="run":
            if args.steps is not None and args.steps<1: p.error("--steps must be positive")
            if args.experiment=='replay' and args.steps is not None:
                p.error("완주 재생 실험은 --steps 대신 도착까지 실행합니다")
            if args.resume:
                if args.config or args.mode: p.error("Resume uses saved config; do not supply --config or --mode")
                sim=Simulation.resume(args.output)
            else:
                c=load_config(args.config)
                if args.mode: c["mode"]=args.mode
                sim=Simulation(c,args.output)
            complete=args.until_arrival or args.experiment=='replay'
            count=round(sim.config["simulation_limit_h"]/sim.config["rolling_h"])+1 if complete else (args.steps or 1)
            style=args.experiment or ('replay' if complete else None)
            sim.run(count,render=not args.no_render,experiment_format=style)
            print(f"Dashboard: {(args.output/'dashboard.html').resolve()}")
        elif args.command=="render":
            from .report import render_saved
            for path in render_saved(args.run,args.steps): print(path.resolve())
        elif args.command=="baseline":
            from .baseline import verify_baseline
            import json
            result=verify_baseline()
            print(json.dumps(result,ensure_ascii=False,indent=2))
            if result["status"]!="verified": p.exit(2,"Baseline files differ from the frozen lock.\n")
        else:
            from .simulation import read_json
            import json
            s=read_json(args.run/"state.json"); s.pop("history",None)
            print(json.dumps(s,ensure_ascii=False,indent=2))
    except (ValueError,FileNotFoundError) as e:
        p.exit(2,f"오류: {e}\n")


if __name__=="__main__": main()
