#!/usr/bin/env python3
"""One local/CI entrypoint; real hardware and installed-system checks are opt-in."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('suite',nargs='?',default='all',choices=['all','backend','ui','geometry','network','database'])
args=parser.parse_args()
suites=json.loads((root/'tests/suites.json').read_text())
def run(*command):subprocess.run(command,cwd=root,check=True)
if args.suite in ('all','backend'):
    run(sys.executable,'-m','unittest','discover','-s','tests','-p','test_*.py')
if args.suite in ('all','geometry'):
    for test in suites['geometry']:run('node','tests/'+test)
if args.suite in ('all','ui','network'):
    suite='ui' if args.suite=='all' else args.suite
    run(sys.executable,'tests/run_classic_suite.py',*suites[suite])
if args.suite=='database':run(sys.executable,'tests/run_database_ui.py')
