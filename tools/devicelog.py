#!/usr/bin/env python3
"""Summarise a Shadowrocket proxy-log export (数据 > 代理 > 导出, a SQLite file) for one app.

Read-only and offline. Only rows that belong to the chosen app are printed, plus rejected rows
recorded while the app was in use (often the app's own ad SDKs). Every other row is only counted.
Query strings and the node name after " # " are never printed: they can hold tokens or private names.
"""
import argparse
import collections
import re
import sqlite3
import sys
from pathlib import Path

# Host and User-Agent patterns of apps already worked on. Extend when a new app is investigated.
APPS = {
    'weibo': (r'weibo|sina|miaopai|yizhibo|xiaoka\.tv|yixia', r'weibo'),
    'huya': (r'huya|msstatic', r'kiwi/|HYSDK|huya'),
    'xiaohongshu': (r'xiaohongshu|xhscdn|xhslink', r'xiaohongshu|discover/'),
    'bilibili': (r'bilibili|biliapi|bilivideo|hdslb', r'bili'),
    'zhihu': (r'zhihu|zhimg', r'zhihu'),
    'youtube': (r'youtube|googlevideo|ytimg|youtubei', r'youtube'),
    # 闲鱼's User-Agent is the URL-encoded app name; it also connects straight to IPs after the AMDC dispatch.
    'xianyu': (r'goofish|xianyu|idlefish', r'%E9%97%B2%E9%B1%BC|闲鱼|idlefish'),
    'jump': (r'vgjump|jumpvg', r'^Jump/'),
    # Bank apps: hosts only; their decryption is limited to reviewed image hosts (data/policy.json mitm_exceptions).
    'citic': (r'citicbank|ecitic', r'citic'),
    'ccb': (r'ccb\.com|ccb\.cn', r'ccb'),
    # Articles, their ad frames and ad media; Moments ads arrive unseen with the chat traffic (*.weixin.qq.com long/short links).
    'wechat': (r'weixin|wechat|wxs\.qq\.com|qpic\.cn|qlogo\.cn|servicewechat|daihuo\.qq\.com', r'MicroMessenger|WeChat'),
}
EMPTY_EXPORT = ('导出的文件里没有记录表（通常只有 4 KB）：导出时新记录还在临时文件里。\n'
                '让用户先关掉「启用日志记录」，断开 VPN，从后台划掉 Shadowrocket 再打开，然后导出最新的日志；'
                '仍然为空就改用截图。见 docs/DEVICE_LOGS.md。')


def host_of(url):
    return re.split(r'[:/?#]', re.sub(r'^[a-z]+://', '', url or ''), maxsplit=1)[0].lower()


def clean_url(url):
    return re.split(r'[?#]', url or '', maxsplit=1)[0]


def clean_rule(result):
    return (result or '').split(' #')[0].strip()


def load_rows(path):
    uri = Path(path).resolve().as_uri() + '?mode=ro&immutable=1'
    con = sqlite3.connect(uri, uri=True)
    try:
        tables = {name for (name,) in con.execute("select name from sqlite_master where type in ('table', 'view')")}
        if 'logging_content' not in tables:
            return None
        return con.execute('select c0url, c1ua, c2result, c3type, c4created from logging_content order by docid').fetchall()
    finally:
        con.close()


DECRYPTING_MODULES = {'app-ads': 'app-ads 解密', 'weibo': '微博模块解密', 'response-cleaner': 'B站/知乎模块解密', 'youtube': 'YouTube 模块解密'}


def rule_check(hosts):
    """Which part of the current build touches each host: the domain modules (①) block it, or a module decrypts it."""
    import fnmatch
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import ROOT, load_policy, optimize, is_blocked
    from build import imported_app_ads, blocking_inputs
    policy = load_policy()
    imported = imported_app_ads(ROOT, policy)
    base = optimize(blocking_inputs(ROOT, policy=policy, imported=imported)[0], policy)[0]
    mitm = {}
    for name in DECRYPTING_MODULES:
        module = (ROOT / f'dist/modules/{name}.sgmodule').read_text(encoding='utf-8')
        mitm[name] = next((l.split('= %APPEND% ', 1)[1].split(', ') for l in module.splitlines()
                           if l.startswith('hostname = %APPEND% ')), [])
    import ipaddress
    networks = [ipaddress.ip_network(n.split(',')[1], strict=False) for n in imported['networks']]
    lines = []
    for host in sorted(hosts):
        try:  # Apps that connect by IP address: only the IP rules of ① can match.
            ip = ipaddress.ip_address(host)
            blocked = any(ip.version == n.version and ip in n for n in networks)
        except ValueError:
            blocked = is_blocked(host, base)
        tags = ['base 拦截'] if blocked else []
        for name, label in DECRYPTING_MODULES.items():
            if any(fnmatch.fnmatchcase(host, h) for h in mitm[name]):
                tags.append('只解密（排查用）' if name == 'app-ads' and host in imported['observed'] else label)
        lines.append(f'  {host}: ' + ('、'.join(tags) if tags else '未拦截、未解密'))
    return lines


def report(path, host_re, ua_re='', pad=2, timeline=False, nearby=True, check=False, max_urls=80):
    rows = load_rows(path)
    if rows is None:
        return EMPTY_EXPORT, 2
    host_pat = re.compile(host_re, re.I)
    ua_pat = re.compile(ua_re, re.I) if ua_re else None
    belongs = lambda r: bool(host_pat.search(host_of(r[0]))) or bool(ua_pat and ua_pat.search(r[1] or ''))
    app = [r for r in rows if belongs(r)]
    out = ['== 概况',
           f'记录 {len(rows)} 条，{rows[0][4] if rows else "-"} → {rows[-1][4] if rows else "-"}；'
           f'按策略：{dict(collections.Counter(r[3] for r in rows))}',
           f'目标 App 的记录 {len(app)} 条；其余 {len(rows) - len(app)} 条只计数，不显示。']
    routed = sum(1 for r in rows if clean_rule(r[2]).startswith('ROUTING,'))
    if rows and routed / len(rows) > 0.9:
        out.append('注意：几乎每条都是 ROUTING,…——首页「全局路由」不是「配置」，规则和模块的域名拦截都没有执行。')
    if not app:
        return '\n'.join(out + ['没有匹配到目标 App 的记录，检查 App 名或 --host / --ua。']), 0

    groups, first = collections.Counter(), {}
    for url, ua, result, typ, created in app:
        key = (typ, host_of(url), clean_rule(result))
        groups[key] += 1
        first.setdefault(key, created[11:])
    out += ['', '== 目标 App 的请求（按主机归并；TCP Stream 表示没解密，只看得到域名）']
    for (typ, host, rule), n in sorted(groups.items(), key=lambda kv: (kv[0][0], -kv[1])):
        out.append(f'{n:5}  {first[(typ, host, rule)]}  {typ:6} {host}  |  {rule}')

    urls, ufirst = collections.Counter(), {}
    for url, ua, result, typ, created in app:
        if re.match(r'https?://', url or ''):
            key = (typ, clean_url(url), (ua or '')[:24])
            urls[key] += 1
            ufirst.setdefault(key, created[11:])
    if urls:
        out += ['', '== 能看到完整地址的请求（已解密的 HTTPS 或明文 HTTP；查询参数已去掉）']
        ordered = sorted(urls.items(), key=lambda kv: ufirst[kv[0]])
        for (typ, url, ua), n in ordered[:max_urls]:
            out.append(f'{n:5}  {ufirst[(typ, url, ua)]}  {typ:6} {url}  [{ua}]')
        if len(ordered) > max_urls:
            out.append(f'  …其余 {len(ordered) - max_urls} 个地址省略（--max-urls 调整）')

    if nearby:
        start, end = shift(min(r[4] for r in app), -pad), shift(max(r[4] for r in app), pad)
        near, nfirst = collections.Counter(), {}
        for url, ua, result, typ, created in rows:
            if typ == 'REJECT' and not belongs((url, ua)) and start <= created <= end:
                key = (host_of(url), clean_rule(result))
                near[key] += 1
                nfirst.setdefault(key, created[11:])
        if near:
            out += ['', f'== 同一时间段被拦截的其他请求（{start[11:]}–{end[11:]}，可能是 App 内的第三方广告组件）']
            for (host, rule), n in sorted(near.items(), key=lambda kv: -kv[1]):
                out.append(f'{n:5}  {nfirst[(host, rule)]}  {host}  |  {rule}')

    if timeline:
        out += ['', '== 时间线（连续重复已合并）']
        prev, n = None, 0
        for url, ua, result, typ, created in app + [(None,) * 5]:
            key = None if url is None else (typ, clean_url(url) if re.match(r'https?://', url) else host_of(url), clean_rule(result).split(',')[0])
            if prev and key == prev[1:]:
                n += 1
                continue
            if prev:
                out.append(f'{n:4}x {prev[0]}  {prev[1]:6} {prev[3]:13} {prev[2]}')
            prev, n = (None if key is None else (created[11:], *key)), 1

    if check:
        out += ['', '== 当前构建对这些主机的处理（主配置分流另见 profiles.route_for_test）']
        out += rule_check({host for _, host, _ in groups})
    return '\n'.join(out), 0


def shift(stamp, seconds):
    # Exports seen so far use "YYYY-MM-DD HH:MM:SS"; anything after the seconds is ignored.
    import datetime as dt
    t = dt.datetime.strptime(stamp[:19], '%Y-%m-%d %H:%M:%S') + dt.timedelta(seconds=seconds)
    return t.strftime('%Y-%m-%d %H:%M:%S')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('log', help='Shadowrocket 导出的日志文件（SQLite）')
    p.add_argument('--app', choices=sorted(APPS), help='预设的 App 主机/UA 特征')
    p.add_argument('--host', help='主机名正则（不用 --app 时必填）')
    p.add_argument('--ua', default='', help='User-Agent 正则，用来认出不带 App 名的请求')
    p.add_argument('--pad', type=int, default=2, help='“同一时间段”前后各放宽几秒（默认 2）')
    p.add_argument('--timeline', action='store_true', help='按时间列出目标 App 的请求')
    p.add_argument('--no-nearby', action='store_true', help='不显示同一时间段里其他被拦截的请求')
    p.add_argument('--check', action='store_true', help='对照当前构建：哪些主机被拦截或解密')
    p.add_argument('--max-urls', type=int, default=80, help='完整地址最多列多少个（默认 80）')
    a = p.parse_args(argv)
    if not a.app and not a.host:
        p.error('需要 --app 或 --host')
    host_re, ua_re = APPS[a.app] if a.app else (a.host, a.ua)
    if a.app and a.ua:
        ua_re = a.ua
    text, code = report(a.log, host_re, ua_re, a.pad, a.timeline, not a.no_nearby, a.check, a.max_urls)
    print(text)
    return code


if __name__ == '__main__':
    sys.exit(main())
