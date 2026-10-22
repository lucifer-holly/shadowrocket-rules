"""Build public routing profiles, without importing private device configurations."""
import ipaddress
import fnmatch
from common import domain, read_json, within

LAN_ROUTES = ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '::1/128', 'fc00::/7', 'fe80::/10')


def routing_lists(root):
    data = read_json(root / 'data/routing.json')
    out = {'PROXY': [], 'DIRECT': []}
    seen = set()
    for group in data['groups']:
        if group['policy'] not in out:
            raise ValueError('invalid public routing policy')
        for host in group['domains']:
            domain(host)
            if host in seen:
                raise ValueError('duplicate public routing domain: ' + host)
            seen.add(host)
            out[group['policy']].append('DOMAIN-SUFFIX,' + host)
    return {f'dist/rules/routing-{policy.lower()}.list':
            '# Original public service routing; GPL-3.0-only. No private destinations.\n' +
            '\n'.join(rows) + '\n' for policy, rows in out.items()}


def routing_references(base):
    return [f'RULE-SET,{base}/dist/rules/routing-proxy.list,PROXY',
            f'RULE-SET,{base}/dist/rules/routing-direct.list,DIRECT',
            'DOMAIN-SUFFIX,cn,DIRECT', 'GEOIP,CN,DIRECT', 'FINAL,PROXY']


def profile(root, base):
    routing_lists(root)  # Validate the routing data even when only compiling the profile.
    rows = [
        '#!name=Personal Shared Routing',
        '#!desc=iPhone/iPad/Mac 共用分流；手机去广告另加模块',
        '# SPDX-License-Identifier: GPL-3.0-only',
        '# Public profile: no nodes, credentials, certificates or personal server addresses.',
        '# Generic public profile. Keep private destinations in a private merged main configuration.',
        '# The private merged configuration also retains all original mandatory PROXY rules.',
        '', '[General]', 'bypass-system = true',
        'skip-proxy = 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, localhost, *.local, captive.apple.com',
        'tun-excluded-routes = 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24, 192.0.2.0/24, 192.88.99.0/24, 192.168.0.0/16, 198.51.100.0/24, 203.0.113.0/24, 224.0.0.0/4, 255.255.255.255/32',
        'dns-server = system', 'fallback-dns-server = system',
        'ipv6 = true', 'prefer-ipv6 = false', 'dns-direct-system = false',
        'icmp-auto-reply = true', 'always-reject-url-rewrite = false',
        'private-ip-answer = true', 'dns-direct-fallback-proxy = false',
        'udp-policy-not-supported-behaviour = REJECT',
        'use-local-host-item-for-proxy = false',
        f'update-url = {base}/dist/config/main.conf',
        '', '[Rule]', '# Standard SSH remains direct, including WRDS SSH.',
        'DST-PORT,22,DIRECT',
        '# A non-standard SSH port is not globally exempted. Keep personal target-IP rules private.',
    ]
    rows += [f'IP-CIDR,{network},DIRECT,no-resolve' for network in LAN_ROUTES]
    rows += ['', '# Explicit public proxy services take precedence over domestic routing.',
             *routing_references(base), '', '[Host]', 'localhost = 127.0.0.1', '']
    return '\n'.join(rows)


def route_for_test(text, host, port=443, destination_ip=None, country=None, rule_sets=None, user_agent=''):
    """Small static policy evaluator, not a Shadowrocket or DNS emulator."""
    section = None
    address = ipaddress.ip_address(destination_ip) if destination_ip else None
    def matches(parts):
        kind, value = parts[:2]
        if kind == 'DST-PORT':
            return port == int(value)
        if kind == 'DOMAIN':
            return host == value
        if kind == 'DOMAIN-SUFFIX':
            return within(host, value)
        if kind == 'DOMAIN-KEYWORD':
            return value in host
        if kind == 'USER-AGENT':
            return fnmatch.fnmatchcase(user_agent, value)
        if kind in {'IP-CIDR', 'IP-CIDR6'}:
            network = ipaddress.ip_network(value)
            return bool(address and address.version == network.version and address in network)
        if kind == 'GEOIP':
            return country == value
        if kind == 'RULE-SET':
            if rule_sets is None or value not in rule_sets:
                raise ValueError('static test missing rule-set data: ' + value)
            return any(matches(row.split(',')) for row in rule_sets[value].splitlines()
                       if row.strip() and not row.lstrip().startswith('#'))
        raise ValueError('unsupported static test rule: ' + kind)
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('['):
            section = line
        if section != '[Rule]' or not line or line.startswith(('#', '[')):
            continue
        parts = line.split(',')
        kind = parts[0]
        if kind == 'FINAL':
            return parts[1]
        if matches(parts):
            return parts[2]
    raise ValueError('profile lacks FINAL')
