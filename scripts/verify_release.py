"""Verify frozen files inside a Git ref, independently of development edits."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def verify(ref):
    def show(path):
        return subprocess.check_output(['git', '-C', str(ROOT), 'show', f'{ref}:{path}'])
    lock = json.loads(show('configs/baseline.lock.json'))
    changed = [p for p, expected in lock['sha256'].items()
               if hashlib.sha256(show(p)).hexdigest() != expected]
    return {'ref': ref, 'status': 'changed' if changed else 'verified',
            'checked_files': len(lock['sha256']), 'mismatches': changed}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='v0.2.0-draft.1')
    result = verify(parser.parse_args().ref)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'verified' else 2)
