#!/usr/bin/env python3
"""Insert the base rule-set at an explicit marker in a PRIVATE existing configuration."""
import argparse
from pathlib import Path
from common import ROOT,repo_base
MARKER='# PERSONAL_ADBLOCK_HERE'

def integrate(text,base):
    # Explicit marker preserves the user's chosen SSH/direct exceptions and routing precedence.
    lines=text.splitlines(keepends=True)
    if sum(x.strip()==MARKER for x in lines)!=1:
        raise ValueError('place exactly one '+MARKER+' inside [Rule], below SSH exceptions and above broad routing rules')
    section=None;out=[]
    for line in lines:
        if line.strip().startswith('['):section=line.strip()
        if line.strip()==MARKER:
            if section!='[Rule]':raise ValueError('marker is outside [Rule]')
            ending='\r\n' if line.endswith('\r\n') else '\n'
            out.append(f'RULE-SET,{base}/dist/rules/base.list,REJECT'+ending)
        else:out.append(line)
    return ''.join(out)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    target=Path(a.output).resolve()
    if ROOT in target.parents and ROOT/'private' not in target.parents:
        p.error('private configuration must be saved outside the repo or under ignored private/')
    if target.exists():p.error('output already exists; choose a new private output path')
    with open(a.input,encoding='utf-8',newline='') as f:text=f.read()
    result=integrate(text,repo_base())
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8',newline='') as f:f.write(result)
    print('Private configuration created; do not upload it to GitHub.')
