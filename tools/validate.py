#!/usr/bin/env python3
"""Offline lint, reproducibility, supply-chain boundaries and public secret scan."""
import fnmatch
import ipaddress
import os
import re
from urllib.parse import urlsplit
from common import ROOT,read_json,sha256,repo_base,load_inputs,load_policy,optimize,is_blocked,domain,within
from build import run, imported_app_ads, weibo_routes
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
    for url in spec['negative']+policy['critical_url_probes']:
        if any(r.search(url) for r in routes+rewrites):raise ValueError('Weibo module matches a protected URL: '+url)
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
    entries,_=load_inputs(root);rules,_,_=optimize(entries,policy)
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
    imported=imported_app_ads(root,policy)
    for key,app in apps.items():
        for rule in app['rules']:
            for url in rule['positive']:
                if is_blocked(urlsplit(url).hostname,imported['domains']):raise ValueError('app-ad domain rule shadows own rewrite: '+url)
    for item in policy['exceptions']:
        if is_blocked(item['domain'],imported['domains']):raise ValueError('protected domain blocked by app-ads: '+item['domain'])
    for route in read_json(root/'data/script-routes.json'):
        compiled=re.compile(route['pattern'])
        if not compiled.search(route['positive']):raise ValueError('script positive route fails')
        if any(re.search(p,route['positive']) for p in patterns):raise ValueError('rewrite shadows response script')
        for h in route['hosts']:
            domain(h)
            if is_blocked(h,rules):raise ValueError('domain blocks response script')
    check_weibo(read_json(root/'data/weibo.json'),policy,[rules,imported['domains']])
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
            if section=='Rule' and not re.fullmatch(r'DOMAIN(?:-SUFFIX)?,[^,]+,REJECT|IP-CIDR6?,[^,]+,REJECT,no-resolve|AND,\(\(DOMAIN,[^,()]+\),\(PROTOCOL,UDP\)\),REJECT-NO-DROP',line):
                raise ValueError('unexpected routing in ad module')
            if section=='URL Rewrite':check_rewrite(line,policy['critical_url_probes'])
            if section=='MITM':
                if not line.startswith('hostname = %APPEND% '):raise ValueError('MITM overwrites main config')
                for host in line[len('hostname = %APPEND% '):].split(', '):check_mitm_host(host,policy['never_mitm_suffixes'],policy.get('mitm_exceptions',[]))
            if section=='Script':
                m=re.search(r'script-path=([^,\s]+)',line)
                if not m or not m[1].startswith(base+'/dist/scripts/'):raise ValueError('script is not self hosted')
                route=re.search(r'pattern=([^,]+),',line)
                if not route or any(re.search(route[1],url) for url in policy['critical_url_probes']):
                    raise ValueError('response script matches a critical login/payment/content URL')
                rel=m[1][len(base)+1:]
                if rel not in manifest:raise ValueError('script dependency is missing')
    scan_public(root)
    return {'base_rules':len(rules),'modules':len(list((root/'dist/modules').rglob('*.sgmodule'))),'device_verified':False}

if __name__=='__main__':
    print('PASS '+str(validate())+'; this is not an iOS device test.')
