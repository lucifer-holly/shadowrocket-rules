#!/usr/bin/env python3
"""Explain domain blocking or optional URL processing without sending any request."""
import argparse
import re
from urllib.parse import urlsplit
from common import ROOT,read_json,parse_rules,load_policy,optimize,is_blocked,within,exception_for
from build import imported_app_ads, blocking_inputs, weibo_routes

def explain(value):
    host=urlsplit(value).hostname if '://' in value else value
    policy=load_policy();imported=imported_app_ads(ROOT,policy)
    rules,_=blocking_inputs(ROOT,policy=policy,imported=imported);active,_,_=optimize(rules,policy)
    hits=[','.join(x) for x in active if x[1]==host or (x[0]=='DOMAIN-SUFFIX' and within(host,x[1]))]
    result={'host':host,'domain_blocked':bool(hits),'active_matches':hits,'rewrite_matches':[],'script_matches':[],'source_matches':{}}
    result['app_ads_domain_blocked']=is_blocked(host,imported['domains'])
    for s in read_json(ROOT/'sources/upstreams.json')['sources']:
        if s.get('role','domains')!='domains':continue
        src=parse_rules((ROOT/s['snapshot']).read_bytes(),s['format'])
        result['source_matches'][s['id']]=[','.join(x) for x in sorted(src) if x[1]==host or (x[0]=='DOMAIN-SUFFIX' and within(host,x[1]))]
    if '://' in value:
        for ident,app in read_json(ROOT/'data/apps.json').items():
            result['rewrite_matches'] += [ident for r in app['rules'] if re.search(r['pattern'],value)]
        result['rewrite_matches'] += [f'fmz-blockads ({a})' for p,a in imported['rewrites'] if re.search(p,value)][:1]
        result['script_matches']=[r['id'] for r in read_json(ROOT/'data/script-routes.json') if re.search(r['pattern'],value)]
        weibo=read_json(ROOT/'data/weibo.json')
        result['rewrite_matches'] += [f"weibo ({r['action']})" for r in weibo['rewrites'] if re.search(r['pattern'],value)]
        result['script_matches'] += ['weibo-'+ident for ident,pattern in weibo_routes(weibo) if re.search(pattern,value)]
    result['routing']='未被本项目拦截的流量继续使用原主配置；本工具不模拟主配置路由或 HTTPS 解密状态。'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('host_or_url');a=p.parse_args()
    from common import json_text
    print(json_text(explain(a.host_or_url)))
