"""Build public routing profiles, without importing private device configurations."""
import ipaddress
from common import domain, read_json, within

LAN_ROUTES = ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '::1/128', 'fc00::/7', 'fe80::/10')


def profile(root, base):
    data = read_json(root / 'data/routing.json')
    rows = [
        '#!name=Personal Shared Routing',
        '#!desc=iPhone/iPad/Mac 共用分流；手机去广告另加模块',
        '# SPDX-License-Identifier: GPL-3.0-only',
        '# Public profile: no nodes, credentials, certificates or personal server addresses.',
        '# Keep personal-routing.sgmodule local. Select your existing proxy node in Shadowrocket.',
        '# Generic routing policy; not an exact copy of a private device configuration.',
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
        '# A non-standard SSH port is not globally exempted. Use a local target-IP exception.',
    ]
    rows += [f'IP-CIDR,{network},DIRECT,no-resolve' for network in LAN_ROUTES]
    seen = set()
    for group in data['groups']:
        if group['policy'] not in {'DIRECT', 'PROXY'}:
            raise ValueError('invalid public routing policy')
        rows += ['', '# ' + group['name']]
        for host in group['domains']:
            domain(host)
            if host in seen:
                raise ValueError('duplicate public routing domain: ' + host)
            seen.add(host)
            rows.append(f'DOMAIN-SUFFIX,{host},{group["policy"]}')
    rows += ['', '# Domestic destination IPs go direct; all other traffic uses the selected proxy.',
             'GEOIP,CN,DIRECT', 'FINAL,PROXY', '', '[Host]', 'localhost = 127.0.0.1', '']
    return '\n'.join(rows)


def route_for_test(text, host, port=443, destination_ip=None, country=None):
    """Small static policy evaluator, not a Shadowrocket or DNS emulator."""
    section = None
    address = ipaddress.ip_address(destination_ip) if destination_ip else None
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
        match = (kind == 'DST-PORT' and port == int(parts[1]))
        if kind == 'DOMAIN-SUFFIX':
            match = within(host, parts[1])
        elif kind == 'IP-CIDR' and address:
            network = ipaddress.ip_network(parts[1])
            match = address.version == network.version and address in network
        elif kind == 'GEOIP':
            match = country == parts[1]
        if match:
            return parts[2]
    raise ValueError('profile lacks FINAL')
