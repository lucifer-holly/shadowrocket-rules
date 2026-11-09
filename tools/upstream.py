#!/usr/bin/env python3
"""Download data-only upstream updates; a source that fails any check keeps its old snapshot.

A candidate that changes more than the churn limit is applied only with --accept-churn SOURCE:SHA256 after review."""
import argparse
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.parse
import urllib.request
from common import ROOT, read_json, json_text, sha256, parse_rules, load_policy

MAX_BYTES = 8_000_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect requires explicit source review')


def fetch(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'raw.githubusercontent.com' or p.username or p.password or p.query or p.fragment:
        raise ValueError('only explicit GitHub Raw HTTPS data URLs are allowed')
    if any(x in {'.','..'} for x in p.path.split('/')):
        raise ValueError('invalid path')
    request = urllib.request.Request(url, headers={'User-Agent':'PersonalShadowrocketRules/2','Accept':'text/plain'})
    opener = urllib.request.build_opener(NoRedirect)
    for attempt in range(3):
        try:
            with opener.open(request,timeout=20) as resp:
                if resp.status != 200:
                    raise ValueError('expected HTTP 200')
                data = resp.read(MAX_BYTES+1)
            if len(data) > MAX_BYTES or not data:
                raise ValueError('empty or oversized download')
            return data
        except (OSError, ValueError):
            if attempt == 2: raise
            time.sleep(1+attempt)


def source_date(body):
    text = body.decode('utf-8-sig')[:4000]
    m = re.search(r'^#VER=(\d{14})',text,re.M)
    if m:
        return dt.datetime.strptime(m[1],'%Y%m%d%H%M%S').replace(tzinfo=dt.timezone.utc)
    m = re.search(r'^# Last modified: (.+?) UTC\s*$',text,re.M)
    if m:
        return dt.datetime.strptime(m[1],'%d %b %Y %H:%M').replace(tzinfo=dt.timezone.utc)
    m = re.search(r'^#!date\s*=\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*$',text,re.M)
    if m:  # Loon plugin header, written in Beijing time
        return dt.datetime.strptime(m[1],'%Y-%m-%d %H:%M:%S').replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
    raise ValueError('upstream generation timestamp missing: review format change')


def validate_candidate(source, old, body, license_body, policy, now):
    if sha256(license_body) != old['license_sha256']:
        raise ValueError('LICENSE CHANGED: manual redistribution review required')
    stamp = source_date(body)
    age = (now-stamp).total_seconds()/86400
    if age > source.get('max_age_days', policy['max_source_age_days']) or age < -2:
        raise ValueError('source timestamp stale or implausibly in the future')
    rules = parse_rules(body,source['format'])
    if not source['min_rules'] <= len(rules) <= source['max_rules']:
        raise ValueError('unexpected rule count')
    return rules, stamp


def update(root=ROOT, check=False, fetcher=fetch, now=None, accept=None):
    """accept maps a source id to the SHA-256 of a candidate a person has reviewed: that exact file may exceed the churn
    limit, and no other check is waived. The scheduled workflow never passes it."""
    now = now or dt.datetime.now(dt.timezone.utc)
    policy = load_policy(root)
    sources = read_json(root/'sources/upstreams.json')['sources']
    lock = read_json(root/'sources/upstreams.lock.json')
    accept = dict(accept or {})
    for sid, digest in accept.items():
        if sid not in {s['id'] for s in sources} or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('--accept-churn needs SOURCE:SHA256, a configured source and the full hash of the reviewed candidate')
    proposals, errors, rows, changes, blocked = {}, [], [], [], []
    jobs = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for source in sources:
            base = f"https://raw.githubusercontent.com/{source['repository']}/{source['ref']}/"
            jobs[source['id']] = (pool.submit(fetcher,base+source['path']), pool.submit(fetcher,base+source['license_path']))
        for source in sources:
            sid=source['id']; old=lock['sources'][sid]
            try:
                body, lic = (j.result() for j in jobs[sid])
                rules, stamp = validate_candidate(source,old,body,lic,policy,now)
                previous=(root/source['snapshot']).read_bytes()
                if sha256(previous)!=old['sha256']:
                    raise ValueError('local baseline hash mismatch')
                old_rules=parse_rules(previous,source['format'])
                added,removed=rules-old_rules,old_rules-rules
                # Measured against the last accepted snapshot, not the previous upstream release.
                ratio=(len(added)+len(removed))/max(len(old_rules),1)
                digest=sha256(body)
                reviewed=accept.get(sid)
                if reviewed is not None and reviewed!=digest:
                    # Upstream published again after the review: accept nothing that was not looked at.
                    raise ValueError(f'reviewed candidate {reviewed[:12]} is not the downloaded file {digest[:12]}; review the new one')
                if ratio>policy['max_source_change_ratio'] and reviewed is None:
                    raise ChurnBlocked({'source':sid,'sha256':digest,'source_timestamp':stamp.isoformat(),'previous_rules':len(old_rules),
                                        'rules':len(rules),'added':len(added),'removed':len(removed),'change_ratio':round(ratio,4)},
                                       policy['max_source_change_ratio'])
                different=digest!=old['sha256']
                state=('人工审核后接受' if reviewed else '变更候选') if different else '一致'
                rows.append(f'| {sid} | {state} | {len(rules)} | {len(added)} / {len(removed)} |')
                if different:
                    proposals[source['snapshot']]=body
                    entry=dict(old);entry.update(sha256=digest,bytes=len(body),observed_at=now.isoformat(timespec='seconds'),source_timestamp=stamp.isoformat())
                    lock['sources'][sid]=entry
                    changes.append({'source':sid,'change_ratio':round(ratio,4),**({'accepted_after_review':True} if reviewed else {}),
                                'added':[','.join(x) for x in sorted(added)],'removed':[','.join(x) for x in sorted(removed)]})
            except ChurnBlocked as exc:
                blocked.append(exc.info)
                errors.append(f'{sid}: {type(exc).__name__}: {str(exc)[:180]}')
                rows.append(f"| {sid} | 变化过大，保留旧版（待人工审核） | {exc.info['rules']} | {exc.info['added']} / {exc.info['removed']} |")
            except Exception as exc:
                # Do not write remote body/tracebacks/URLs into logs.
                errors.append(f'{sid}: {type(exc).__name__}: {str(exc)[:180]}')
                rows.append(f'| {sid} | 获取/检查失败，保留旧版 | — | — |')
    # Watched files (e.g. pinned third-party scripts) are compared as inert bytes, never parsed or run.
    reviews=[]
    for watch in read_json(root/'sources/watch.json')['sources']:
        try:
            data=fetcher(watch['url'])
            changed=sha256(data)!=watch['sha256']
            if changed:reviews.append(watch['id'])
            rows.append(f"| {watch['id']} | {'有新版本：需审核后才更新，不会自动导入' if changed else '一致'} | — | — |")
        except Exception as exc:
            rows.append(f"| {watch['id']} | 参考源无法获取：{type(exc).__name__}（不影响已有快照） | — | — |")
    report='\n'.join(['# 上游自动更新报告','',f"检查时间：{now.isoformat(timespec='seconds')}",'',
        '通过检查的来源自动更新；未通过的来源保留旧快照，其余来源照常更新。','',
        '| 来源 | 状态 | 规则数 | 新增 / 删除 |','|---|---|---:|---:|',*rows,'',
        *(['以下来源被安全检查拦截，继续使用旧快照：',*['- '+e for e in errors]] if errors else ['所有数据源预检通过。']),
        *(['','变化超过阈值的候选（人工审核后只能接受这一份，方法见 docs/MAINTENANCE.md「增删超过 20%」）：',
           *[f"- {b['source']}：变化 {b['change_ratio']:.1%}（新增 {b['added']}，删除 {b['removed']}，原有 {b['previous_rules']} 条），"
             f"上游生成于 {b['source_timestamp']}，SHA-256 `{b['sha256']}`" for b in blocked]] if blocked else []),
        '', '详细增删见同目录 update.json；提交记录的文件差异显示完整快照变化。',''])
    # Reports always go to ignored cache; a failed source never replaces its snapshot.
    cache=root/'.cache';cache.mkdir(exist_ok=True)
    (cache/'update.md').write_text(report,encoding='utf-8')
    (cache/'update.json').write_text(json_text({'errors':errors,'changes':changes,'reviews':reviews,'blocked':blocked}),encoding='utf-8')
    if proposals and not check:
        proposals['sources/upstreams.lock.json']=json_text(lock).encode()
        # Network/format/license checks finish before filesystem mutation.
        # Atomic replace per file; a killed process fails the hash check on next build.
        for rel,body in proposals.items():
            path=root/rel
            fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.candidate-')
            try:
                with os.fdopen(fd,'wb') as f:f.write(body)
                os.replace(temp,path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
        (root/'reports/update.md').write_text(report,encoding='utf-8')
        (root/'reports/update.json').write_text(json_text({'errors':errors,'changes':changes,'blocked':blocked}),encoding='utf-8')
    if errors:
        raise PartialFailure('upstream sources blocked: '+', '.join(e.split(':')[0] for e in errors)+'; see .cache/update.md')
    return bool(proposals)


class PartialFailure(ValueError):
    """Some sources failed their checks and kept their old snapshots; healthy sources were still applied."""


class ChurnBlocked(ValueError):
    """The candidate passed every other check but differs too much from the accepted snapshot; a person reviews it first."""
    def __init__(self, info, limit):
        self.info = info
        super().__init__(f"rule churn {info['change_ratio']:.1%} (+{info['added']}/-{info['removed']} against "
                         f"{info['previous_rules']} accepted rules) exceeds {limit:.0%}; manual review required")


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--accept-churn',action='append',default=[],metavar='SOURCE:SHA256',
                   help='after a person has reviewed exactly this candidate, let it exceed the churn limit; every other check still applies')
    a=p.parse_args()
    try:
        changed=update(check=a.check,accept=dict(x.partition(':')[::2] for x in a.accept_churn))
        print('Upstream data changed; '+('check only.' if a.check else 'snapshots updated.')) if changed else print('No upstream data change.')
    except PartialFailure as exc:
        # Exit 3: publish what passed, then alert about the blocked sources.
        print(str(exc));raise SystemExit(3)
    except (ValueError,OSError) as exc:
        print(str(exc));raise SystemExit(1)
