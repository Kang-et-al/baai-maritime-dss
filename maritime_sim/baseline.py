"""공유 baseline의 버전·구성 파일·모델·시각화 자산 해시 확인."""
import hashlib
import json
from .config import ROOT,load_config


def verify_baseline():
    lock_path=ROOT/"configs"/"baseline.lock.json"
    lock=json.loads(lock_path.read_text(encoding="utf-8"))
    mismatches=[]
    for relative,expected in lock["sha256"].items():
        path=ROOT/relative
        actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual!=expected: mismatches.append(relative)
    canonical=load_config(ROOT/"configs"/"baseline.json")
    if load_config()!=canonical: mismatches.append("DEFAULT differs from configs/baseline.json")
    return {"baseline_id":lock["baseline_id"],"status":"verified" if not mismatches else "changed",
            "checked_files":len(lock["sha256"]),"mismatches":mismatches,
            "risk":canonical["risk"],"scenario_generator":canonical["scenario_generator"],
            "profile":"configs/baseline.json","reference_tag":"v0.2.0-draft.1",
            "reference_result":"See results/index.csv and the draft release; earlier crossing_replay was mean-only",
            "note":"changed is expected on development branches; use the reference tag for exact source verification"}
