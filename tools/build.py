#!/usr/bin/env python3
"""Deterministic offline build from hashed local snapshots. Never fetches or executes JS."""
import argparse
from pathlib import Path
from common import ROOT, read_json, json_text, sha256, load_inputs, load_policy, optimize, repo_base, domain
from profiles import profile
from plugin_import import parse_plugin, select


def module(name, sections, note=''):
    lines = [f'#!name=Personal {name}', '#!desc=自维护去广告；'+note,
             '#!category=去广告', '#!system=ios',
             '# SPDX-License-Identifier: GPL-3.0-only; see LICENSE and THIRD_PARTY_NOTICES.md']
    for section, content in sections:
        if content:
            lines += ['', '['+section+']', *content]
    return '\n'.join(lines) + '\n'


def app_sections(apps, imported=None):
    rewrites, hosts = [], set()
    seen = set()
    for ident, app in apps.items():
        rewrites.append(f"# {app['name']} ({ident}); 真机效果未验证")
        for rule in app['rules']:
            line = rule['pattern'] + ' - ' + rule['action']
            if line not in seen:
                rewrites.append(line); seen.add(line)
            hosts.update(rule['hosts'])
    rules = []
    if imported:
        own = {line.split(' - ')[0] for line in seen}
        rewrites.append('# 自动跟踪的第三方插件静态拒绝规则（见 THIRD_PARTY_NOTICES.md）；未导入脚本')
        rewrites += [f'{p} - {a}' for p, a in imported['rewrites'] if p not in own]
        rules = [','.join(r) + ',REJECT' for r in imported['domains']] + imported['networks']
        hosts.update(imported['mitm'])
    return [('Rule', rules), ('URL Rewrite', rewrites), ('MITM', ['hostname = %APPEND% ' + ', '.join(sorted(hosts))])]


def imported_app_ads(root, policy):
    """Static subset of every tracked app-ad plugin, merged; each snapshot hash is verified first."""
    lock = read_json(root/'sources/upstreams.lock.json')['sources']
    overrides = read_json(root/'data/app-ads-overrides.json')
    for host in overrides['exclude_hosts']:
        domain(host)
    merged = {'domains': set(), 'networks': set(), 'rewrites': {}, 'mitm': set(), 'report': {}}
    for source in read_json(root/'sources/upstreams.json')['sources']:
        if source.get('role') != 'app-ads':
            continue
        body = (root/source['snapshot']).read_bytes()
        if sha256(body) != lock[source['id']]['sha256']:
            raise ValueError(source['id']+': snapshot does not match lock')
        part = select(parse_plugin(body), policy, policy['critical_url_probes'],
                      overrides['exclude_hosts'], overrides['exclude_patterns'])
        merged['domains'].update(part['domains']); merged['networks'].update(part['networks'])
        for pattern, action in part['rewrites']:
            merged['rewrites'].setdefault(pattern, action)
        merged['mitm'].update(part['mitm']); merged['report'][source['id']] = part['report']
    if not merged['report']:
        raise ValueError('app-ad plugin source missing')
    return {'domains': sorted(merged['domains']), 'networks': sorted(merged['networks']),
            'rewrites': list(merged['rewrites'].items()), 'mitm': sorted(merged['mitm']), 'report': merged['report']}


def outputs(root=ROOT):
    base = repo_base(root)
    policy = load_policy(root)
    # Rule exceptions never emit DIRECT: routing stays with the existing main configuration.
    rules, counts = load_inputs(root)
    merged, removed, compressed = optimize(rules, policy)
    light, _ = load_inputs(root, {'hagezi-light'})
    light, _, _ = optimize(light, policy)
    header = ['# Personal ads: anti-AD (MIT) + HaGeZi Light (GPL-3.0), modified by this project.',
              '# See THIRD_PARTY_NOTICES.md and licenses/. No proxy nodes or certificates.']
    out = {}
    for label, entries in [('base', merged), ('lite', light)]:
        rows = [','.join(r) for r in entries]
        out[f'dist/rules/{label}.list'] = '\n'.join(header + rows) + '\n'
        out[f'dist/modules/{label}.sgmodule'] = module(label.title(), [('Rule', [r+',REJECT' for r in rows])],
            '域名拦截，无需证书；base 与 lite 二选一')
    apps = read_json(root/'data/apps.json')
    imported = imported_app_ads(root, policy)
    out['dist/modules/app-ads.sgmodule'] = module('App Ads (Experimental)', app_sections(apps, imported),
        '开屏与应用内广告：自维护规则 + fmz200 静态规则；需 HTTPS 解密；与 apps-all、单 App 模块三选一')
    out['dist/modules/apps-all.sgmodule'] = module('Apps (Experimental)', app_sections(apps), '需 HTTPS 解密；与单 App 模块二选一')
    for ident, spec in apps.items():
        out[f'dist/modules/apps/{ident}.sgmodule'] = module(spec['name']+' (Experimental)', app_sections({ident:spec}), '需 HTTPS 解密；逐个启用验证')
    scripts = read_json(root/'sources/scripts.lock.json')['scripts']
    if len(scripts) != 1 or scripts[0]['path'] != 'scripts/response-cleaner.js':
        raise ValueError('script inventory requires manual compiler review')
    src = (root/scripts[0]['path']).read_bytes()
    digest = sha256(src)
    if digest != scripts[0]['sha256'] or not scripts[0]['review']:
        raise ValueError('script changed without reviewed hash')
    script_rel = f'dist/scripts/response-cleaner.{digest}.js'
    out[script_rel] = src.decode('utf-8')
    routes = read_json(root/'data/script-routes.json')
    script_lines = [f"personal-{r['id']} = type=http-response,pattern={r['pattern']},requires-body=true,max-size=1048576,timeout=5,script-path={base}/{script_rel}" for r in routes]
    hosts = sorted({h for r in routes for h in r['hosts']})
    out['dist/modules/response-cleaner.sgmodule'] = module('Response Cleaner (Experimental)',
        [('Script', script_lines), ('MITM', ['hostname = %APPEND% '+', '.join(hosts)])], '哔哩哔哩/知乎 JSON；需 HTTPS 解密，未知结构原样返回')
    out['dist/config/adblock.fragment.conf'] = '# 仅供合并进原 [Rule]；不是完整主配置。\n[Rule]\n'+f'RULE-SET,{base}/dist/rules/base.list,REJECT\n'
    out['dist/config/main.conf'] = profile(root, base)
    out['dist/config/adblock-example.conf'] = '\n'.join([
        '# 示例配置；优先用模块保留原 default.conf。', '# 不含节点；PROXY 使用 Shadowrocket 选择的节点；SSH 规则需自行添加。',
        '[General]', 'bypass-system = true', '', '[Rule]',
        'IP-CIDR,127.0.0.0/8,DIRECT,no-resolve', 'IP-CIDR,10.0.0.0/8,DIRECT,no-resolve',
        'IP-CIDR,172.16.0.0/12,DIRECT,no-resolve', 'IP-CIDR,192.168.0.0/16,DIRECT,no-resolve',
        f'RULE-SET,{base}/dist/rules/base.list,REJECT', 'GEOIP,CN,DIRECT', 'FINAL,PROXY', ''])
    report = {'source_counts':counts,'unique_before_policy':len(rules),'protected_removed':len(removed),
              'covered_by_parent':compressed,'base_rules':len(merged),'lite_rules':len(light),
              'app_modules':len(apps),'url_rewrites':sum(len(x['rules']) for x in apps.values()),
              'imported_app_ads':imported['report'],
              'response_routes':len(routes),'device_verified':False,
              'exceptions': [{'rule':','.join(k),'reason':v} for k,v in sorted(removed.items())]}
    subscription_rows = [
        ('手机与 Mac 共用主配置（「配置」页导入）','dist/config/main.conf'),
        ('通用域名拦截（手机，优先）','dist/modules/base.sgmodule'),
        ('较小域名库（与 base 二选一）','dist/modules/lite.sgmodule'),
        ('开屏与应用内广告（手机，需证书，推荐）','dist/modules/app-ads.sgmodule'),
        ('仅自维护 App 路径规则（与 app-ads 二选一）','dist/modules/apps-all.sgmodule'),
        ('哔哩哔哩/知乎响应处理（实验）','dist/modules/response-cleaner.sgmodule'),
        ('主配置示例（优先保留原配置）','dist/config/adblock-example.conf'),
        ('主配置合并片段','dist/config/adblock.fragment.conf')]
    subscription_rows += [(app['name']+'（独立实验模块）', f'dist/modules/apps/{ident}.sgmodule') for ident,app in apps.items()]
    out['docs/SUBSCRIPTIONS.md'] = '\n'.join([
        '# 订阅地址','',
        '由 project.json 自动生成；当前地址对应自己的仓库。使用方法见 DEVICE_PROFILES.md。',
        '主配置 URL 在「配置」页导入；模块 URL 在「模块」中导入，都不是节点订阅。手机与 Mac 使用同一 main.conf；手机另加广告模块，Mac 默认只用主配置。',
        'base / lite 二选一；app-ads / apps-all / 独立 App 模块三选一；response-cleaner 可额外启用。',
        '', '| 内容 | Raw 地址 |', '|---|---|',
        *[f'| {name} | {base}/{rel} |' for name,rel in subscription_rows], '',
        '脚本只引用本仓库按内容哈希命名的文件；更新需要先审阅合并，再在手机更新模块/配置。',
        '模块内嵌域名表；不依赖手机另行拉取上游规则。规则集方式仅访问本仓库。', ''])
    out['reports/build.json'] = json_text(report)
    # Keep old content-addressed scripts: previously downloaded modules must not lose their dependencies.
    artifacts = {k:sha256(v.encode()) for k,v in out.items() if k.startswith('dist/')}
    for item in read_json(root/'sources/scripts.lock.json').get('archives', []):
        rel = item['path']
        if not rel.startswith('dist/scripts/') or '/' in rel[len('dist/scripts/'):]:
            raise ValueError('invalid archived script path')
        body = (root/rel).read_bytes()
        if sha256(body) != item['sha256'] or not item['review']:
            raise ValueError('archived script integrity/approval missing')
        out[rel] = body.decode('utf-8')
        artifacts[rel] = sha256(body)
    out['dist/manifest.json'] = json_text({'repository':read_json(root/'project.json')['repository'],
        'format_version':1,'files':artifacts,'sources':read_json(root/'sources/upstreams.lock.json')['sources']})
    return out


def run(root=ROOT, check=False):
    out = outputs(root)
    stale = {p.relative_to(root).as_posix() for prefix in ['dist/modules','dist/rules','dist/config']
             for p in (root/prefix).rglob('*') if p.is_file()} - out.keys()
    differences = list(sorted(stale))
    for name, text in out.items():
        path = root/name
        data = text.encode('utf-8')
        if not path.exists() or path.read_bytes() != data:
            differences.append(name)
            if not check:
                path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    if check and differences:
        raise ValueError('generated files differ: '+', '.join(differences))
    if not check:
        for name in stale: (root/name).unlink()
    return out

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    run(check=a.check)
    print('PASS deterministic build' if a.check else 'Built local modules, rule sets and manifests.')
