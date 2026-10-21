#!/usr/bin/env python3
"""After publishing, verify your own Raw artifacts against the local manifest; no code execution."""
import concurrent.futures
from common import ROOT,read_json,repo_base,sha256
from upstream import fetch

def main():
    cfg=read_json(ROOT/'project.json')
    if cfg['repository'].startswith('YOUR-USERNAME/'):
        raise SystemExit('Configure and publish the repository first; placeholder URLs cannot be checked.')
    base=repo_base();files=read_json(ROOT/'dist/manifest.json')['files']
    def check(pair):
        rel,digest=pair
        try:
            return rel,sha256(fetch(base+'/'+rel))==digest
        except (ValueError,OSError):return rel,False
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(check,files.items()))
    for rel,ok in results:print(('OK ' if ok else 'FAIL ')+rel)
    if not all(ok for _,ok in results):raise SystemExit(1)
if __name__=='__main__':main()
