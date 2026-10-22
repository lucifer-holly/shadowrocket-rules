#!/usr/bin/env python3
"""Merge private exceptions and every original mandatory PROXY rule into one private main file."""
import argparse
from pathlib import Path
from common import ROOT, repo_base
from profiles import LAN_ROUTES, routing_references

PROXY_TYPES = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'USER-AGENT', 'IP-CIDR', 'IP-CIDR6'}
DIRECT_TYPES = {'DOMAIN', 'DOMAIN-SUFFIX', 'DST-PORT', 'IP-CIDR', 'IP-CIDR6'}


def sections(text):
    result = {}
    current = None
    for line in text.splitlines(keepends=True):
        clean = line.strip()
        if clean.startswith('[') and clean.endswith(']'):
            if clean in result:
                raise ValueError('duplicate configuration section')
            current = clean
            result[current] = []
        elif current:
            result[current].append(line)
    return result


def active(rows):
    return [x.strip() for x in rows if x.strip() and not x.lstrip().startswith(('#', ';', '//'))]


def mandatory_proxy(text):
    old = sections(text)
    if '[Rule]' not in old:
        raise ValueError('original configuration has no [Rule] section')
    result = []
    for line in active(old['[Rule]']):
        parts = line.split(',')
        if parts[0] == 'FINAL':
            continue
        if 'PROXY' in parts:
            if len(parts) < 3 or parts[2] != 'PROXY' or parts[0] not in PROXY_TYPES:
                raise ValueError('original PROXY rule requires manual parser review')
            result.append(line)
    return list(dict.fromkeys(result))


def personalize(original, base, private_rules=''):
    old = sections(original)
    proxy = mandatory_proxy(original)
    if not proxy:
        raise ValueError('refuse to silently discard an empty mandatory proxy inventory')
    private = []
    for line in active(old['[Rule]']):
        parts = line.split(',')
        if len(parts) >= 3 and parts[2] == 'DIRECT' and parts[0] in {'DST-PORT', 'IP-CIDR', 'IP-CIDR6'}:
            private.append(line)
    overrides = sections(private_rules)
    if set(overrides) - {'[Rule]'}:
        raise ValueError('private rule input must contain only [Rule]')
    for line in active(overrides.get('[Rule]', [])):
        parts = line.split(',')
        if len(parts) < 3 or parts[2] != 'DIRECT' or parts[0] not in DIRECT_TYPES:
            raise ValueError('unexpected private override')
        private.append(line)
    private = list(dict.fromkeys(private))
    networks = {line.split(',')[1].lower() for line in private if line.startswith(('IP-CIDR,', 'IP-CIDR6,'))}
    private += [f'IP-CIDR,{n},DIRECT,no-resolve' for n in LAN_ROUTES if n.lower() not in networks]
    if 'DST-PORT,22,DIRECT' not in private:
        private.insert(0, 'DST-PORT,22,DIRECT')
    new_rules = ['# Private IP/domain and SSH exceptions, merged into this file.', *private, '',
                 f'# All {len(proxy)} original mandatory PROXY rules, ahead of domestic routing.',
                 *proxy, '', '# Remotely maintained public service routes; no advertising code.',
                 *routing_references(base)]
    header = '\n'.join([
        '#!name=Personal Shared Private Routing',
        '#!desc=手机与 Mac 共用；私人直连与原有强制代理规则已合并，手机另加广告模块。',
        '# PRIVATE: contains personal network destinations. Do not upload to public GitHub.',
        '# No personal-routing.sgmodule is needed with this configuration.',
        '# No public update-url: updating from a sanitized public profile would erase private rules.',
        '# Update the referenced routing rule-sets in Shadowrocket for public routing changes.', ''])
    result = [header]
    for section, rows in old.items():
        result.append(section + '\n')
        if section == '[Rule]':
            result.append('\n'.join(new_rules) + '\n\n')
        else:
            # Preserve original settings and certificate sections; never replace private settings from a public URL.
            result += [line for line in rows if not line.lstrip().lower().startswith('update-url')]
    return ''.join(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--private-rules', help='optional local DIRECT overrides to merge once')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    target = Path(args.output).resolve()
    if target == ROOT or (ROOT in target.parents and ROOT/'private' not in target.parents):
        parser.error('private output must be outside the public repository or under ignored private/')
    if target.exists():
        parser.error('refuse to overwrite an existing output')
    original = Path(args.input).read_text(encoding='utf-8-sig')
    overrides = Path(args.private_rules).read_text(encoding='utf-8-sig') if args.private_rules else ''
    result = personalize(original, repo_base(), overrides)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding='utf-8')
    target.chmod(0o600)
    print('Created private main configuration; mandatory proxy rules retained:', len(mandatory_proxy(original)))
