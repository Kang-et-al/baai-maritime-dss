"""Create an additive GitHub overlay, without modifying a repository or network."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DOCS=['CURRENT_MATHEMATICAL_STRUCTURE_KO.md','VERSION_SPEC.md','BASELINE_DIFF.md',
      'TEAM_HEX_GUIDE.md','RELEASE_VALIDATION.md','UPLOAD_PREPARATION.md','CHANGELOG.md',
      'SELECTIVE_DP.md','SELECTIVE_DP_RESULTS.md','SELECTIVE_VOYAGE_RESULTS.md','VOYAGE_DECISION_AUDIT.md']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    target=Path(a.output).resolve()
    if target.exists():raise ValueError('Use a new preparation folder')
    subprocess.run([str(Path(__import__('sys').executable)),str(ROOT/'scripts/check_version.py')],check=True)
    dirty=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    if dirty.strip():raise ValueError('Commit local source/docs first; do not package an unidentified working tree')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    paths=[ROOT/n for n in ['README.md','AGENTS.md','PROJECT_CONTEXT.md','requirements.txt','pyproject.toml','.gitignore','version-lock.json']]
    paths += [ROOT/'docs'/n for n in DOCS]
    for folder,pattern in [('hex_dss','*.py'),('experimental_dp','*.py'),('tests','*.py'),('configs','*.json'),('data','*.json'),('examples/reference','*.json')]:
        paths+=list((ROOT/folder).glob(pattern))
    paths += [ROOT/'scripts'/n for n in ['check_version.py','prepare_upload.py']]
    manifest={}
    for src in sorted(set(paths)):
        rel=Path('extensions/hex_v03')/src.relative_to(ROOT)
        dest=target/'github-overlay'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dest)
        manifest[rel.as_posix()]=hashlib.sha256(dest.read_bytes()).hexdigest()
    for src in sorted((ROOT/'sharing').rglob('*')):
        if not src.is_file():continue
        rel=src.relative_to(ROOT/'sharing')
        dest=target/'github-overlay'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        manifest[rel.as_posix()]=hashlib.sha256(dest.read_bytes()).hexdigest()
    info={'candidate_version':'v0.3.0-draft.1','published':False,'source_commit':commit,
          'baseline_reference':'v0.2.0-draft.1','integration_prefix':'extensions/hex_v03',
          'remote_operations_performed':False,'sha256':manifest}
    (target/'manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=target/'github-overlay.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name in manifest:z.write(target/'github-overlay'/name,name)
        z.write(target/'manifest.json','HEX_V03_UPLOAD_MANIFEST.json')
    for name,digest in manifest.items():
        assert hashlib.sha256((target/'github-overlay'/name).read_bytes()).hexdigest()==digest
    print(json.dumps({'output':str(target),'source_commit':commit,'files':len(manifest),'zip_bytes':archive.stat().st_size},indent=2))

if __name__=='__main__':main()
