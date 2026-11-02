"""Read-only verification of the approved source/config/data snapshot."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def check():
    lock=json.loads((ROOT/'version-lock.json').read_text(encoding='utf-8'))
    changed=[n for n,h in lock['sha256'].items() if not (ROOT/n).is_file() or hashlib.sha256((ROOT/n).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=h]
    current={str(p.relative_to(ROOT)).replace("\\","/") for folder,pattern in [('hex_dss','*.py'),('experimental_dp','*.py'),('configs','*.json'),('data','*.json')] for p in (ROOT/folder).glob(pattern)}
    unexpected=sorted(current-set(lock['sha256']))
    environment=[]
    if sys.version_info[:2]!=(3,12):environment.append('Python 3.12.x required')
    for line in (ROOT/'requirements.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):continue
        name,want=line.split('==')
        try:got=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:got='missing'
        if got!=want:environment.append(f'{name}: {got}, expected {want}')
    result={'status':'passed' if not changed and not unexpected and not environment else 'changed',
            'candidate_version':lock['candidate_version'],'changed':changed,'unexpected':unexpected,'environment':environment}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':sys.exit(check())
