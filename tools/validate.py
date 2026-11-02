#!/usr/bin/env python3
"""Offline lint, reproducibility, supply-chain boundaries and public secret scan."""
import fnmatch
import ipaddress
import os
import re
from urllib.parse import urlsplit
from common import ROOT,read_json,sha256,repo_base,load_inputs,load_policy,optimize,is_blocked,domain,within
from build import run, imported_app_ads, blocking_inputs, weibo_routes, weibo_splash, YOUTUBE_ROUTE
from profiles import sections as routing_sections

FORBIDDEN_JS = re.compile(r'\b(?:eval|Function|fetch|XMLHttpRequest|require|import)\b|\$(?:httpClient|task|persistentStore|prefs|notification|notify)')

def check_script(text):
    # Defense in depth for this small known script, not a general JavaScript security proof.
    if FORBIDDEN_JS.search(text):
        raise ValueError('script contains an unapproved execution/network/storage API')


def check_public_profile(text, base, root=ROOT):
    allowed_sections = {'General', 'Rule', 'Host', 'URL Rewrite'}
    section = None
    active = []
    update_url = f'update-url = {base}/dist/config/main.conf'
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            if section not in allowed_sections:
                raise ValueError('public profile contains nodes, scripts or decryption settings')
            continue
        if section == 'General' and line.startswith('update-url') and line != update_url:
            raise ValueError('profile update URL must point to this repository')
        if section == 'URL Rewrite' and not re.fullmatch(r"'\^https\?://\S+' 'https://\S+' 30[27]", line):
            raise ValueError('public profile may only carry plain redirects')
        if section != 'Rule':
            continue
        active.append(line)
        fields = line.split(',')
        if fields[0] in {'IP-CIDR', 'IP-CIDR6'} and fields[2] == 'DIRECT' and ipaddress.ip_network(fields[1], strict=False).is_global:
            raise ValueError('public profile contains a routable DIRECT address; keep private servers out of the repository')
        if fields[0] in {'RULE-SET', 'DOMAIN-SET', 'SCRIPT'} or any(f.strip().startswith('REJECT') for f in fields[2:]):
            raise ValueError('shared routing profile must be self-contained and must not block or run scripts')
    if not active or active[-1] != 'FINAL,PROXY' or 'DST-PORT,22,DIRECT' not in active or 'GEOIP,CN,DIRECT' not in active:
        raise ValueError('missing fallback, mainland IP or standard SSH direct rule')
    if update_url not in text.splitlines():
        raise ValueError('missing persistent configuration update URL')
    parts = routing_sections(root)
    legacy = parts[1][1]
    first_direct_group = next(rows[0] for title, rows in parts[2:] if rows and rows[0].endswith(',DIRECT'))
    if any(row not in active for row in legacy) or first_direct_group not in active:
        raise ValueError('missing original mandatory proxy rules')
    if max(active.index(row) for row in legacy) > active.index(first_direct_group):
        raise ValueError('mandatory proxy routing must precede domestic direct routing')


def check_rewrite(line, probes):
    pattern, sep, action = line.rpartition(' - ')
    if not sep or not pattern.startswith('^http') or action not in {'reject','reject-200','reject-dict','reject-img','reject-array'}:
        raise ValueError('unsafe rewrite: '+line[:120])
    compiled = re.compile(pattern)
    if any(compiled.search(url) for url in probes):
        raise ValueError('rewrite matches a critical login/payment/content URL: '+pattern[:120])


def check_mitm_host(host, never_mitm, exceptions=()):
    if re.fullmatch(r'[\d.*]+', host) or host.count('*') > 1:
        raise ValueError('MITM host requires separate review: '+host)
    domain(host.replace('*', 'x1'))
    if host in exceptions:  # exact, separately reviewed hosts such as the YouTube API
        return
    sample = host.replace('*', 'x1')
    if any(within(sample, s) or within(s, host.lstrip('*.')) for s in never_mitm):
        raise ValueError('MITM would decrypt a protected login/payment/AI host: '+host)

def check_connection_rule(rule):
    # Plain HTTP only (visible without decryption), one app's User-Agent, nothing that breaks the rule syntax.
    url,ua=rule['url_regex'],rule['user_agent']
    if not url.startswith('^http://') or re.search(r'[,()\s]',url) or re.search(r'[,()\s]',ua) or len(ua.replace('*',''))<4 or not rule['reason']:
        raise ValueError('unsafe connection rule: '+url[:80])
    matches=lambda s:bool(re.search(url,s['url'])) and fnmatch.fnmatchcase(s['user_agent'],ua)
    if not rule['positive'] or not rule['negative'] or not all(matches(s) for s in rule['positive']) or any(matches(s) for s in rule['negative']):
        raise ValueError('connection rule samples fail: '+url[:80])


def check_weibo(spec, policy, blocklists):
    # Rewrites answer whole calls with {}; scripts edit exact paths; neither may reach login, messages or posting.
    rewrites=[re.compile(r['pattern']) for r in spec['rewrites']]
    routes=[re.compile(p) for _,p in weibo_routes(spec)]
    paths=[p for g in spec['scripts'] for p in g['paths']]
    if len(paths)!=len(set(paths)) or not all(g['reason'] for g in spec['scripts']):
        raise ValueError('Weibo script groups need unique paths and a reason')
    for rule,compiled in zip(spec['rewrites'],rewrites):
        if rule['action']!='reject-dict' or not rule['pattern'].startswith('^https://api\\.weibo\\.cn/2/') or not rule['reason'] or not rule['positive']:
            raise ValueError('unsafe Weibo rewrite: '+rule['pattern'][:120])
        for url in rule['positive']:
            if not compiled.search(url) or any(r.search(url) for r in routes):
                raise ValueError('Weibo rewrite sample fails or overlaps a script route: '+url)
    for path in paths:
        url=f'https://api.weibo.cn/2/{path}'
        if not any(r.search(url+'?gsid=example') for r in routes) or any(r.search(url+'/extra') for r in routes):
            raise ValueError('Weibo script route is not exact: '+path)
        if any(r.search(url+'?gsid=example') for r in rewrites):raise ValueError('rewrite shadows Weibo script: '+path)
    # Splash hosts: the script gets the listed calls, the reject-dict pattern gets every other request, nothing passes.
    splash=spec['splash']
    script,refused=(re.compile(p) for p in weibo_splash(spec))
    hosts=set(splash['hosts'])
    if not splash['reason'] or not hosts<=set(spec['mitm']) or not all(h.endswith('.uve.weibo.com') for h in hosts):
        raise ValueError('Weibo splash hosts must be decrypted uve.weibo.com hosts with a reason')
    if len({c['host'] for c in splash['calls']})!=len(splash['calls']) or not {c['host'] for c in splash['calls']}<=hosts:
        raise ValueError('Weibo splash calls need one listed host each')
    for url in [u for c in splash['calls'] for u in c['positive']]:
        if not script.search(url) or refused.search(url):raise ValueError('Weibo splash call sample fails: '+url)
    for url in splash['refused']+[f'{s}://{h}/{p}' for h in hosts for s in ('http','https') for p in ('','x?y=1')]:
        if script.search(url) or not refused.search(url):raise ValueError('Weibo splash request neither refused nor rewritten: '+url)
    for url in spec['negative']+policy['critical_url_probes']:
        if any(r.search(url) for r in routes+rewrites+[script,refused]):raise ValueError('Weibo module matches a protected URL: '+url)
    for host in spec['mitm']:
        domain(host)
        if any(is_blocked(host,listed) for listed in blocklists):raise ValueError('domain block shadows Weibo module: '+host)


def scan_public(root=ROOT):
    patterns=[re.compile(r'-----BEGIN (?:[A-Z ]*PRIVATE KEY|PKCS12)-----'),
              re.compile(r'(?:ss|ssr|vmess|vless|trojan|hysteria2)://[A-Za-z0-9+/_=-]{8,}'),
              re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
              re.compile(r'(?im)^\s*(?:ca-p12|ca-passphrase|password|private-key)\s*=\s*\S+')]
    errors=[]
    for path in root.rglob('*'):
        if not path.is_file() or any(x in {'.git','.cache','private','__pycache__','node_modules'} for x in path.relative_to(root).parts):continue
        if path.suffix in {'.p12','.pfx','.pem','.key'}:
            errors.append(str(path.relative_to(root))+': prohibited secret file');continue
        text=path.read_text(encoding='utf-8',errors='replace')
        if any(p.search(text) for p in patterns):errors.append(str(path.relative_to(root))+': possible secret')
    if errors:raise ValueError('\n'.join(errors))


def validate(root=ROOT):
    cfg=read_json(root/'project.json');base=repo_base(root)
    if os.environ.get('GITHUB_ACTIONS') == 'true' and cfg['repository'] != os.environ.get('GITHUB_REPOSITORY'):
        raise ValueError('project.json repository differs from this GitHub repository; run tools/configure.py --repo owner/repo')
    run(root,check=True)
    check_public_profile((root/'dist/config/main.conf').read_text(),base,root)
    policy=load_policy(root)
    sources=read_json(root/'sources/upstreams.json')['sources']
    for s in sources:
        if s['spdx'] not in {'MIT','GPL-3.0'}:raise ValueError('unapproved source license')
        for key in ['snapshot','license_file']:
            p=root/s[key]
            if root.resolve() not in p.resolve().parents:raise ValueError('source path traversal')
    imported=imported_app_ads(root,policy)
    entries,_=blocking_inputs(root,policy=policy,imported=imported);rules,_,_=optimize(entries,policy)
    for item in policy['exceptions']:
        if is_blocked(item['domain'],rules):raise ValueError('protected domain blocked: '+item['domain'])
    apps=read_json(root/'data/apps.json')
    patterns=[]
    for key,app in apps.items():
        if not re.fullmatch(r'[a-z][a-z0-9-]*',key):raise ValueError('bad app identifier')
        for rule in app['rules']:
            pattern=rule['pattern'];compiled=re.compile(pattern)
            if not pattern.startswith('^https') or rule['action'] not in {'reject','reject-200','reject-dict','reject-img','reject-array'}:
                raise ValueError('unsafe rewrite')
            if not rule['positive'] or not rule['hosts']:raise ValueError('rewrite missing fixtures/hosts')
            for url in rule['positive']:
                if not compiled.search(url):raise ValueError('positive URL does not match')
                host=urlsplit(url).hostname
                if not any(fnmatch.fnmatchcase(host,h) for h in rule['hosts']):raise ValueError('MITM host missing')
                if is_blocked(host,rules):raise ValueError('domain block shadows URL rewrite: '+host)
            for h in rule['hosts']:
                domain(h.replace('*','1'))
                if h.count('*')>1 or (h.count('*') and not h.startswith('m*.')):
                    raise ValueError('MITM wildcard requires separate review')
            if pattern in patterns:raise ValueError('duplicate/conflicting rewrite')
            patterns.append(pattern)
        for rule in app.get('connection_rules',[]):check_connection_rule(rule)
    for key,app in apps.items():
        for rule in app['rules']:
            for url in rule['positive']:
                if is_blocked(urlsplit(url).hostname,imported['domains']):raise ValueError('app-ad domain rule shadows own rewrite: '+url)
    for item in policy['exceptions']:
        if is_blocked(item['domain'],imported['domains']):raise ValueError('protected domain blocked by app-ads: '+item['domain'])
    for route in read_json(root/'data/script-routes.json'):
        compiled=re.compile(route['pattern'])
        if not compiled.search(route['positive']):raise ValueError('script positive route fails')
        for h in route['hosts']:
            domain(h)
            if is_blocked(h,rules):raise ValueError('domain blocks response script')
    weibo=read_json(root/'data/weibo.json')
    check_weibo(weibo,policy,[rules,imported['domains']])
    # The modules run together: no rewrite in any module and no domain block may pre-empt another module's script.
    rewrites=patterns+[p for p,_ in imported['rewrites']]+[r['pattern'] for r in weibo['rewrites']]
    youtube=[f'https://youtubei.googleapis.com/youtubei/v1/{p}?key=example' for p in ['browse','next','player','search']]
    if not all(re.search(YOUTUBE_ROUTE,url) for url in youtube):raise ValueError('YouTube script samples are stale')
    samples=[r['positive'] for r in read_json(root/'data/script-routes.json')]+youtube
    samples+=[f'https://api.weibo.cn/2/{p}?gsid=example' for g in weibo['scripts'] for p in g['paths']]
    for url in samples:
        if any(re.search(p,url) for p in rewrites):raise ValueError('a rewrite pre-empts a response script: '+url)
        if is_blocked(urlsplit(url).hostname,rules):raise ValueError('a domain block pre-empts a response script: '+url)
    lock=read_json(root/'sources/scripts.lock.json')['scripts']
    for item in lock:
        data=(root/item['path']).read_bytes()
        if sha256(data)!=item['sha256'] or not item['review']:raise ValueError('script approval missing')
        check_script(data.decode())
    for item in read_json(root/'sources/scripts.lock.json').get('archives', []):
        check_script((root/item['path']).read_text())
    manifest=read_json(root/'dist/manifest.json')['files']
    actual={p.relative_to(root).as_posix() for p in (root/'dist').rglob('*') if p.is_file() and p.name!='manifest.json'}
    if actual!=manifest.keys():raise ValueError('dist manifest inventory mismatch')
    for name,digest in manifest.items():
        if sha256((root/name).read_bytes())!=digest:raise ValueError('artifact hash mismatch')
    for path in (root/'dist/modules').rglob('*.sgmodule'):
        text=path.read_text();section=None;seen=set()
        if len(text.encode())>policy['max_module_bytes']:raise ValueError('oversized module')
        for raw in text.splitlines():
            line=raw.strip()
            if not line or line.startswith('#'):continue
            if line.startswith('['):
                section=line[1:-1]
                if section not in {'Rule','URL Rewrite','Script','MITM'}:raise ValueError('module changes routing/DNS settings')
                continue
            if (section,line) in seen:raise ValueError('duplicate module line')
            seen.add((section,line))
            if section=='Rule' and not re.fullmatch(r'DOMAIN(?:-SUFFIX)?,[^,]+,REJECT|IP-CIDR6?,[^,]+,REJECT,no-resolve|AND,\(\(DOMAIN,[^,()]+\),\(PROTOCOL,UDP\)\),REJECT-NO-DROP'
                                                      r'|AND,\(\(URL-REGEX,\^http://[^,()\s]+\),\(USER-AGENT,[^,()\s]+\)\),REJECT',line):
                raise ValueError('unexpected routing in ad module')
            if section=='URL Rewrite':check_rewrite(line,policy['critical_url_probes'])
            if section=='MITM':
                if not line.startswith('hostname = %APPEND% '):raise ValueError('MITM overwrites main config')
                for host in line[len('hostname = %APPEND% '):].split(', '):check_mitm_host(host,policy['never_mitm_suffixes'],[x['host'] for x in policy.get('mitm_exceptions',[])])
            if section=='Script':
                m=re.search(r'script-path=([^,\s]+)',line)
                if not m or not m[1].startswith(base+'/dist/scripts/'):raise ValueError('script is not self hosted')
                route=re.search(r'pattern=([^,]+),',line)
                if not route or any(re.search(route[1],url) for url in policy['critical_url_probes']):
                    raise ValueError('response script matches a critical login/payment/content URL')
                rel=m[1][len(base)+1:]
                if rel not in manifest:raise ValueError('script dependency is missing')
    scan_public(root)
    result={'base_rules':len(rules),'modules':len(list((root/'dist/modules').rglob('*.sgmodule'))),'device_verified':False}
    # Decrypt-only troubleshooting hosts: shown on every run; past their date the build has already stopped decrypting them.
    if imported['observed']:result['observed_until']=imported['observe_until']
    if imported['observe_expired']:result['expired_observe_hosts_to_delete']=imported['observe_expired']
    return result

if __name__=='__main__':
    print('PASS '+str(validate())+'; this is not an iOS device test.')
