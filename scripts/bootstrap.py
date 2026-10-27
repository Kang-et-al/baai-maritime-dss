"""Create a portable local environment; invoke with a standard Python 3.12."""
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]

def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('Baseline setup requires Python 3.12.x. Install Python 3.12 and retry.')
    target = ROOT / '.venv'
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(target)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT/'requirements-lock.txt')], check=True)
    subprocess.run([str(python), '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT, check=True)
    print('Ready:', python)
    print('Run from:', ROOT)

if __name__ == '__main__':
    main()
