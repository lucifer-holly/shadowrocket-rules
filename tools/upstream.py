#!/usr/bin/env python3
"""Download data-only upstream updates; a source that fails any check keeps its old snapshot."""
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


def update(root=ROOT, check=False, fetcher=fetch, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    policy = load_policy(root)
    sources = read_json(root/'sources/upstreams.json')['sources']
    lock = read_json(root/'sources/upstreams.lock.json')
    proposals, errors, rows, changes = {}, [], [], []
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
                delta=rules.symmetric_difference(old_rules)
                if len(delta)/max(len(old_rules),1)>policy['max_source_change_ratio']:
                    raise ValueError('rule churn exceeds configured threshold; manual review required')
                different=sha256(body)!=old['sha256']
                rows.append(f'| {sid} | '+('变更候选' if different else '一致')+f' | {len(rules)} | {len(rules-old_rules)} / {len(old_rules-rules)} |')
                if different:
                    proposals[source['snapshot']]=body
                    entry=dict(old);entry.update(sha256=sha256(body),bytes=len(body),observed_at=now.isoformat(timespec='seconds'),source_timestamp=stamp.isoformat())
                    lock['sources'][sid]=entry
                    changes.append({'source':sid,'change_ratio':round(len(delta)/max(len(old_rules),1),4),
                                'added':[','.join(x) for x in sorted(rules-old_rules)],'removed':[','.join(x) for x in sorted(old_rules-rules)]})
            except Exception as exc:
                # Do not write remote body/tracebacks/URLs into logs.
                errors.append(f'{sid}: {type(exc).__name__}: {str(exc)[:180]}')
                rows.append(f'| {sid} | 获取/检查失败，保留旧版 | — | — |')
    # Whole plugin is observed as inert bytes only, never parsed or evaluated as code.
    for watch in read_json(root/'sources/watch.json')['sources']:
        try:
            data=fetcher(watch['url'])
            status='一致' if sha256(data)==watch['sha256'] else '发生变化：App 静态端点需人工复核（不导入脚本）'
            rows.append(f"| {watch['id']} | {status} | — | — |")
        except Exception as exc:
            rows.append(f"| {watch['id']} | 参考源无法获取：{type(exc).__name__}（不影响已有快照） | — | — |")
    report='\n'.join(['# 上游自动更新报告','',f"检查时间：{now.isoformat(timespec='seconds')}",'',
        '通过检查的来源自动更新；未通过的来源保留旧快照，其余来源照常更新。','',
        '| 来源 | 状态 | 规则数 | 新增 / 删除 |','|---|---|---:|---:|',*rows,'',
        *(['以下来源被安全检查拦截，继续使用旧快照：',*['- '+e for e in errors]] if errors else ['所有数据源预检通过。']),
        '', '详细增删见同目录 update.json；提交记录的文件差异显示完整快照变化。',''])
    # Reports always go to ignored cache; a failed source never replaces its snapshot.
    cache=root/'.cache';cache.mkdir(exist_ok=True)
    (cache/'update.md').write_text(report,encoding='utf-8')
    (cache/'update.json').write_text(json_text({'errors':errors,'changes':changes}),encoding='utf-8')
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
        (root/'reports/update.json').write_text(json_text({'errors':errors,'changes':changes}),encoding='utf-8')
    if errors:
        raise PartialFailure('upstream sources blocked: '+', '.join(e.split(':')[0] for e in errors)+'; see .cache/update.md')
    return bool(proposals)


class PartialFailure(ValueError):
    """Some sources failed their checks and kept their old snapshots; healthy sources were still applied."""


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    try:
        changed=update(check=a.check)
        print('Upstream data changed; '+('check only.' if a.check else 'snapshots updated.')) if changed else print('No upstream data change.')
    except PartialFailure as exc:
        # Exit 3: publish what passed, then alert about the blocked sources.
        print(str(exc));raise SystemExit(3)
    except (ValueError,OSError) as exc:
        print(str(exc));raise SystemExit(1)
