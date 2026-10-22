#!/usr/bin/env python3
"""Deterministic offline build from hashed local snapshots. Never fetches or executes JS."""
import argparse
import re
from pathlib import Path
from common import ROOT, read_json, json_text, sha256, load_inputs, load_policy, optimize, repo_base, domain
from profiles import profile
from plugin_import import parse_plugin, select


def module(name, sections, note=''):
    # The name is what the Shadowrocket module list shows, so it states the function and the slot it fills.
    lines = [f'#!name={name}', '#!desc='+note,
             '#!category=去广告', '#!system=ios',
             '# SPDX-License-Identifier: GPL-3.0-only; see LICENSE and THIRD_PARTY_NOTICES.md']
    for section, content in sections:
        if content:
            lines += ['', '['+section+']', *content]
    return '\n'.join(lines) + '\n'


def app_sections(apps, imported=None):
    # Only what needs decryption: the plugins' static domain and IP rules are part of the domain modules (①).
    rewrites, hosts = [], set()
    seen = set()
    for ident, app in apps.items():
        rewrites.append(f"# {app['name']} ({ident}); 真机效果未验证")
        for rule in app['rules']:
            line = rule['pattern'] + ' - ' + rule['action']
            if line not in seen:
                rewrites.append(line); seen.add(line)
            hosts.update(rule['hosts'])
    if imported:
        own = {line.split(' - ')[0] for line in seen}
        rewrites.append('# 自动跟踪的第三方插件静态拒绝规则（见 THIRD_PARTY_NOTICES.md）；未导入脚本')
        rewrites += [f'{p} - {a}' for p, a in imported['rewrites'] if p not in own]
        hosts.update(imported['mitm'])
    mitm = ['hostname = %APPEND% ' + ', '.join(sorted(hosts))]
    if imported and imported['observed']:
        mitm.insert(0, '# 只解密、不拦截（排查用，日志里能看到完整地址）：' + ', '.join(imported['observed']))
    return [('URL Rewrite', rewrites), ('MITM', mitm)]


def imported_app_ads(root, policy):
    """Static subset of every tracked app-ad plugin, merged; each snapshot hash is verified first."""
    lock = read_json(root/'sources/upstreams.lock.json')['sources']
    overrides = read_json(root/'data/app-ads-overrides.json')
    for host in overrides['exclude_hosts']:
        domain(host)
    # Decrypt-only hosts make the device log show full URLs while an ad endpoint is located; nothing is blocked there.
    observed = set()
    for item in overrides.get('observe_hosts', []):
        host = domain(item['host'])
        if not item['reason'] or any(host == h or host.endswith('.' + h) for h in overrides['exclude_hosts']):
            raise ValueError('observed host needs a reason and must not be an excluded host: ' + host)
        observed.add(host)
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
            'rewrites': list(merged['rewrites'].items()), 'mitm': sorted(merged['mitm'] | observed),
            'observed': sorted(observed), 'report': merged['report']}


def blocking_inputs(root=ROOT, subset=None, policy=None, imported=None):
    """Inputs of the domain modules (①): the plain lists plus the tracked plugins' static domain rules, deduplicated together."""
    policy = policy or load_policy(root)
    imported = imported or imported_app_ads(root, policy)
    rules, counts = load_inputs(root, subset)
    return rules | set(imported['domains']), dict(counts, plugin_domains=len(imported['domains']))


API_TOKENS = ('$httpClient', 'fetch(', '$persistentStore', '$prefs', '$notification', '$notify(', '$task',
              'eval(', 'Function(', 'require(', 'import(')
YOUTUBE_ROUTE = ('^https://youtubei\\.googleapis\\.com/youtubei/v1/(?:browse|next|player|search|reel/reel_watch_sequence'
                 '|guide|account/get_setting|get_watch|log_event|config)(?:\\?|$)')


def youtube_outputs(root, base):
    """Pinned third-party YouTube script: any byte or API-usage change stops the build until reviewed again."""
    item = next(x for x in read_json(root/'sources/scripts.lock.json')['third_party'] if x['id'] == 'maasea-youtube-response')
    body = (root/item['path']).read_bytes()
    if sha256(body) != item['sha256'] or sha256((root/item['license_file']).read_bytes()) != item['license_sha256']:
        raise ValueError('third-party script or licence changed without review')
    text = body.decode('utf-8')
    if {t: text.count(t) for t in API_TOKENS} != item['api_counts'] or not item['review']:
        raise ValueError('third-party script API usage differs from the reviewed fingerprint')
    rel = f"dist/scripts/youtube.response.{item['sha256']}.js"
    # Responses above 2 MiB pass unchanged so protobuf decoding cannot exhaust the 50 MB network-extension memory.
    script = (f'youtube-response = type=http-response,pattern={YOUTUBE_ROUTE},requires-body=true,binary-body-mode=true,'
              f'max-size=2097152,timeout=20,script-path={base}/{rel}')
    module_text = module('去广告④ YouTube（实验，需证书）', [
        ('Rule', ['AND,((DOMAIN,youtubei.googleapis.com),(PROTOCOL,UDP)),REJECT-NO-DROP']),
        ('Script', [script]), ('MITM', ['hostname = %APPEND% youtubei.googleapis.com'])],
        '去除 YouTube App 视频贴片和首页、搜索里的广告；脚本来自 Maasea/sgmodule（Apache-2.0），已审核并固定版本；YouTube 异常时先关闭本模块')
    return {rel: text, 'dist/modules/youtube.sgmodule': module_text}


def reviewed_script(root, item, name):
    """Original script published under its content hash; the lock entry must carry the hash and a review."""
    src = (root/item['path']).read_bytes()
    digest = sha256(src)
    if digest != item['sha256'] or not item['review']:
        raise ValueError('script changed without reviewed hash')
    return f'dist/scripts/{name}.{digest}.js', src.decode('utf-8')


def weibo_routes(spec):
    """One [Script] pattern per group: exact paths under https://api.weibo.cn/2/, nothing below them."""
    return [(group['id'], '^https://api\\.weibo\\.cn/2/(?:' + '|'.join(re.escape(p) for p in group['paths']) + ')(?:\\?|$)')
            for group in spec['scripts']]


def weibo_outputs(root, base, item):
    spec = read_json(root/'data/weibo.json')
    rel, text = reviewed_script(root, item, 'weibo')
    # Weibo timelines can reach a few hundred KB; larger bodies pass unchanged.
    scripts = [f'weibo-{ident} = type=http-response,pattern={pattern},requires-body=true,max-size=3145728,timeout=10,'
               f'script-path={base}/{rel}' for ident, pattern in weibo_routes(spec)]
    rewrites = [f"{r['pattern']} - {r['action']}" for r in spec['rewrites']]
    module_text = module('去广告⑤ 微博完整版（实验，需证书）', [
        ('URL Rewrite', rewrites), ('Script', scripts), ('MITM', ['hostname = %APPEND% ' + ', '.join(spec['mitm'])])],
        '删除微博 App 信息流、评论区、热搜、视频流里标了广告或推广的内容和推荐卡片，热搜保留；需 HTTPS 解密与本机证书模块；微博异常时先关闭本模块')
    return {rel: text, 'dist/modules/weibo.sgmodule': module_text}


def outputs(root=ROOT):
    base = repo_base(root)
    policy = load_policy(root)
    # Rule exceptions never emit DIRECT: routing stays with the existing main configuration.
    imported = imported_app_ads(root, policy)
    rules, counts = blocking_inputs(root, policy=policy, imported=imported)
    merged, removed, compressed = optimize(rules, policy)
    light, _ = blocking_inputs(root, {'hagezi-light'}, policy, imported)
    light, _, _ = optimize(light, policy)
    header = ['# Personal ads: anti-AD (MIT) + HaGeZi Light (GPL-3.0) + fmz200 plugin static rules (GPL-3.0), modified by this project.',
              '# See THIRD_PARTY_NOTICES.md and licenses/. No proxy nodes or certificates.']
    # Rule lists carry no policy; module lines add REJECT.
    networks = [n.replace(',REJECT,', ',') for n in imported['networks']]
    out = {}
    for label, entries in [('base', merged), ('lite', light)]:
        rows = [','.join(r) for r in entries]
        out[f'dist/rules/{label}.list'] = '\n'.join(header + rows + networks) + '\n'
        title = '去广告① 广告域名拦截（免证书）' if label == 'base' else '去广告① 广告域名拦截·精简版（免证书）'
        out[f'dist/modules/{label}.sgmodule'] = module(title, [('Rule', [r+',REJECT' for r in rows] + imported['networks'])],
            '拦截广告与跟踪域名（anti-AD、HaGeZi、fmz200 插件的静态规则），不需要证书；标准版与精简版二选一，内存吃紧时用精简版')
    apps = read_json(root/'data/apps.json')
    out['dist/modules/app-ads.sgmodule'] = module('去广告② App 开屏与应用内广告（需证书）', app_sections(apps, imported),
        '开屏、弹窗与应用内广告的接口规则：fmz200 静态重写 + 自维护规则；域名拦截都在去广告①；需 HTTPS 解密与本机证书模块；与其他「去广告②」模块只开一个')
    out['dist/modules/apps-all.sgmodule'] = module('去广告② 备选·仅自维护 App 规则（需证书）', app_sections(apps),
        '只含自维护的 App 路径规则，用于排查；需 HTTPS 解密；与其他「去广告②」模块只开一个')
    for ident, spec in apps.items():
        out[f'dist/modules/apps/{ident}.sgmodule'] = module(f"去广告② 单 App·{spec['name']}（需证书）", app_sections({ident:spec}),
            '只含这个 App 的规则，用于排查；需 HTTPS 解密；与其他「去广告②」模块只开一个')
    scripts = {s['path']: s for s in read_json(root/'sources/scripts.lock.json')['scripts']}
    if set(scripts) != {'scripts/response-cleaner.js', 'scripts/weibo.js'}:
        raise ValueError('script inventory requires manual compiler review')
    script_rel, script_text = reviewed_script(root, scripts['scripts/response-cleaner.js'], 'response-cleaner')
    out[script_rel] = script_text
    routes = read_json(root/'data/script-routes.json')
    script_lines = [f"personal-{r['id']} = type=http-response,pattern={r['pattern']},requires-body=true,max-size=1048576,timeout=5,script-path={base}/{script_rel}" for r in routes]
    hosts = sorted({h for r in routes for h in r['hosts']})
    out['dist/modules/response-cleaner.sgmodule'] = module('去广告③ 信息流净化·B站/知乎（需证书）',
        [('Script', script_lines), ('MITM', ['hostname = %APPEND% '+', '.join(hosts)])], '删除哔哩哔哩、知乎推荐流里明确标注的广告卡片；需 HTTPS 解密与本机证书模块；未知内容原样返回')
    out.update(youtube_outputs(root, base))
    out.update(weibo_outputs(root, base, scripts['scripts/weibo.js']))
    weibo = read_json(root/'data/weibo.json')
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
              'imported_app_ads':imported['report'],'observed_mitm_hosts':imported['observed'],
              'response_routes':len(routes),
              'weibo_script_paths':sum(len(g['paths']) for g in weibo['scripts']),'weibo_rewrites':len(weibo['rewrites']),
              'device_verified':False,
              'exceptions': [{'rule':','.join(k),'reason':v} for k,v in sorted(removed.items())]}
    subscription_rows = [
        ('手机与 Mac 共用主配置（「配置」页导入）','dist/config/main.conf'),
        ('通用域名拦截（手机，优先）','dist/modules/base.sgmodule'),
        ('较小域名库（与 base 二选一）','dist/modules/lite.sgmodule'),
        ('开屏与应用内广告（手机，需证书，推荐）','dist/modules/app-ads.sgmodule'),
        ('仅自维护 App 路径规则（与 app-ads 二选一）','dist/modules/apps-all.sgmodule'),
        ('哔哩哔哩/知乎响应处理（实验）','dist/modules/response-cleaner.sgmodule'),
        ('YouTube 去广告（实验，第三方脚本已审核并固定版本）','dist/modules/youtube.sgmodule'),
        ('微博完整版去广告与精简（实验，需证书）','dist/modules/weibo.sgmodule'),
        ('主配置示例（优先保留原配置）','dist/config/adblock-example.conf'),
        ('主配置合并片段','dist/config/adblock.fragment.conf')]
    subscription_rows += [(app['name']+'（独立实验模块）', f'dist/modules/apps/{ident}.sgmodule') for ident,app in apps.items()]
    out['docs/SUBSCRIPTIONS.md'] = '\n'.join([
        '# 订阅地址','',
        '由 project.json 自动生成；当前地址对应自己的仓库。使用方法见 DEVICE_PROFILES.md。',
        '主配置 URL 在「配置」页导入；模块 URL 在「模块」中导入，都不是节点订阅。手机与 Mac 使用同一 main.conf；手机另加广告模块，Mac 默认只用主配置。',
        'base / lite 二选一；app-ads / apps-all / 独立 App 模块三选一；response-cleaner、youtube、weibo 可按需额外启用。',
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
