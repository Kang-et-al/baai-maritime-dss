"""Version metadata only; never collect credentials or machine-specific paths."""
import platform
import subprocess
import PIL
from .config import ROOT

BASELINE_REF = 'v0.2.0-draft.1'

def git_metadata():
    def git(*args):
        return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.DEVNULL,
                                       timeout=5, text=True).strip()
    try:
        commit = git('rev-parse', 'HEAD')
        return {'commit': commit, 'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
                'dirty': bool(git('status', '--porcelain', '--untracked-files=normal')),
                'baseline_ref': BASELINE_REF}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'branch': None, 'dirty': None, 'baseline_ref': BASELINE_REF}

def runtime_metadata():
    return {'git': git_metadata(), 'pillow': PIL.__version__, 'platform': platform.system()}
