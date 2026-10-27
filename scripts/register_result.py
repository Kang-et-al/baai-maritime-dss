"""Register saved experiment provenance and archive its output for a Release."""
import argparse
import csv
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def register(run, experiment_id, allow_dirty=False, artifact_url=''):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', experiment_id):
        raise ValueError('Use a short alphanumeric experiment ID without slashes.')
    run = Path(run).resolve()
    if not run.is_relative_to((ROOT/'outputs').resolve()):
        raise ValueError('Only folders inside project outputs/ are accepted.')
    read = lambda name: json.loads((run/name).read_text(encoding='utf-8'))
    manifest, state = read('manifest.json'), read('state.json')
    git = manifest.get('git', {})
    unversioned = not git.get('commit') or git.get('dirty') is not False
    if unversioned and not allow_dirty:
        raise ValueError('Saved run used uncommitted code; rerun from a commit or use --allow-dirty.')
    index = ROOT/'results'/'index.csv'
    with index.open(encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    if any(row['experiment_id'] == experiment_id for row in rows):
        raise ValueError('Experiment ID already registered.')
    archive = ROOT/'dist'/f'{experiment_id}.zip'
    archive.parent.mkdir(exist_ok=True)
    if archive.exists():
        raise ValueError('Archive already exists.')
    files = sorted(p for p in run.rglob('*') if p.is_file())
    if any(p.is_symlink() or not p.resolve().is_relative_to(run) for p in files):
        raise ValueError('Archive cannot contain links outside the experiment.')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as handle:
        for path in files:
            handle.write(path, str(Path(experiment_id)/path.relative_to(run)))
    row = dict(experiment_id=experiment_id, baseline_ref=git.get('baseline_ref',''),
               git_commit=git.get('commit',''), config_sha256=manifest['config_sha256'],
               status=state['status'], time_h=state['time_h'],
               total_cost_usd=state['operating_cost_usd']+state['late_cost_usd'],
               artifact_url=artifact_url, notes='DIRTY OR UNVERSIONED' if unversioned else '')
    with index.open('a', encoding='utf-8', newline='') as handle:
        csv.DictWriter(handle, fieldnames=fields, lineterminator='\n').writerow(row)
    return archive

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--allow-dirty', action='store_true')
    parser.add_argument('--artifact-url', default='')
    args = parser.parse_args()
    print(register(args.run, args.id, args.allow_dirty, args.artifact_url))
