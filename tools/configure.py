#!/usr/bin/env python3
"""Set your public GitHub repository and regenerate self-hosted subscription URLs."""
import argparse
from common import ROOT,json_text,repo_base
from build import run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);a=p.parse_args()
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+',a.repo):p.error('use owner/repository')
    if a.repo.split('/')[1] in {'.','..'}:p.error('invalid repository name')
    (ROOT/'project.json').write_text(json_text({'repository':a.repo,'branch':'main'}),encoding='utf-8')
    run()
    print('Configured '+a.repo+'; modules regenerated. No network write performed.')
