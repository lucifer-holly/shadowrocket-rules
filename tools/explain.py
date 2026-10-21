#!/usr/bin/env python3
"""Explain domain blocking or optional URL processing without sending any request."""
import argparse
import re
from urllib.parse import urlsplit
from common import ROOT,read_json,parse_rules,load_inputs,load_policy,optimize,is_blocked,within,exception_for

def explain(value):
    host=urlsplit(value).hostname if '://' in value else value
    rules,_=load_inputs();active,_,_=optimize(rules,load_policy())
    hits=[','.join(x) for x in active if x[1]==host or (x[0]=='DOMAIN-SUFFIX' and within(host,x[1]))]
    result={'host':host,'domain_blocked':bool(hits),'active_matches':hits,'rewrite_matches':[],'script_matches':[],'source_matches':{}}
    for s in read_json(ROOT/'sources/upstreams.json')['sources']:
        src=parse_rules((ROOT/s['snapshot']).read_bytes(),s['format'])
        result['source_matches'][s['id']]=[','.join(x) for x in sorted(src) if x[1]==host or (x[0]=='DOMAIN-SUFFIX' and within(host,x[1]))]
    if '://' in value:
        for ident,app in read_json(ROOT/'data/apps.json').items():
            result['rewrite_matches'] += [ident for r in app['rules'] if re.search(r['pattern'],value)]
        result['script_matches']=[r['id'] for r in read_json(ROOT/'data/script-routes.json') if re.search(r['pattern'],value)]
    result['routing']='未被本项目拦截的流量继续使用原主配置；本工具不模拟主配置路由或 HTTPS 解密状态。'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('host_or_url');a=p.parse_args()
    from common import json_text
    print(json_text(explain(a.host_or_url)))
