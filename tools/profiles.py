"""Build the shared, self-contained main configuration from public routing data."""
import ipaddress
import fnmatch
from common import domain, read_json, within

LAN_ROUTES = ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16', '::1/128', 'fc00::/7', 'fe80::/10')
# The original configuration's LAN rules, kept verbatim (they resolve domains that point at LAN hosts).
ORIGINAL_LAN = ('192.168.0.0/16', '10.0.0.0/8', '172.16.0.0/12', '127.0.0.0/8')
RULE_TYPES = {'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD', 'USER-AGENT', 'IP-CIDR', 'IP-CIDR6', 'DST-PORT'}
GENERAL = [
    'bypass-system = true',
    'skip-proxy = 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, localhost, *.local, captive.apple.com',
    'tun-excluded-routes = 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.0.0.0/24, 192.0.2.0/24, 192.88.99.0/24, 192.168.0.0/16, 198.51.100.0/24, 203.0.113.0/24, 224.0.0.0/4, 255.255.255.255/32, 239.255.255.250/32',
    'dns-server = system', 'fallback-dns-server = system',
    # IPv6 first: AAAA answers win where the network has IPv6, IPv4 is used where it has none. Server logs confirmed
    # both on 2026-10-28 (the dual-stack node went over IPv6 on IPv6 broadband, over IPv4 with the Mac's IPv6 off).
    'ipv6 = true', 'prefer-ipv6 = true', 'dns-direct-system = false',
    'icmp-auto-reply = true', 'always-reject-url-rewrite = false',
    'private-ip-answer = true', 'dns-direct-fallback-proxy = false',
    'udp-policy-not-supported-behaviour = REJECT',
    'use-local-host-item-for-proxy = false',
]
URL_REWRITE = ["'^https?://(www.)?g.cn($|/.*)' 'https://www.google.com$2' 302",
               "'^https?://(www.)?google.cn($|/.*)' 'https://www.google.com$2' 302"]


def rule_list(path, policy):
    """Read a verbatim rule list; every active line must use the expected policy."""
    rows = []
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split(',')
        if len(parts) < 3 or parts[0] not in RULE_TYPES or parts[2] != policy:
            raise ValueError(f'{path.name}: unexpected rule: {line}')
        rows.append(line)
    if len(rows) != len(set(rows)):
        raise ValueError(f'{path.name}: duplicate rule')
    return rows


def sections(root):
    """Ordered [Rule] sections. Explicit PROXY rules always precede every domestic DIRECT group."""
    data = read_json(root / 'data/routing.json')
    seen_domains = {}
    proxy_groups, direct_groups = [], []
    for group in data['groups']:
        if group['policy'] not in {'PROXY', 'DIRECT'}:
            raise ValueError('invalid public routing policy')
        for host in group['domains']:
            domain(host)
            if host in seen_domains:
                raise ValueError('duplicate public routing domain: ' + host)
            seen_domains[host] = group['policy']
        rows = [f"DOMAIN-SUFFIX,{host},{group['policy']}" for host in group['domains']]
        (proxy_groups if group['policy'] == 'PROXY' else direct_groups).append((group['name'], rows))
    for host in data['former_direct_now_proxy']['domains']:
        domain(host)
        if host in seen_domains:
            raise ValueError('former direct domain is still listed in a routing group: ' + host)
    asn = [f"IP-ASN,{int(item['asn'])},DIRECT,no-resolve" for item in data['asn_direct']]
    lan = [f'IP-CIDR,{n},DIRECT' for n in ORIGINAL_LAN]
    lan += [f'IP-CIDR,{n},DIRECT,no-resolve' for n in LAN_ROUTES if n not in ORIGINAL_LAN]
    result = [('手工直连例外（原配置开头，优先于所有代理规则）', rule_list(root / 'data/manual-direct.list', 'DIRECT')),
              ('原配置全部显式代理规则（原样、原顺序）', rule_list(root / 'data/legacy-proxy.list', 'PROXY')),
              *proxy_groups, *direct_groups,
              ('腾讯 IP 直连', asn), ('其余 .cn 域名', ['DOMAIN-SUFFIX,cn,DIRECT']), ('局域网', lan),
              ('中国大陆 IP 直连', ['GEOIP,CN,DIRECT']), ('其余流量走代理', ['FINAL,PROXY'])]
    # Drop exact repeats so an explicit legacy rule and a curated group never emit the same line twice.
    emitted, out = set(), []
    for title, rows in result:
        rows = [r for r in rows if not (r in emitted or emitted.add(r))]
        out.append((title, rows))
    return out


def profile(root, base):
    rows = [
        '#!name=分流主配置（手机 + Mac 共用）',
        '#!desc=iPhone/iPad/Mac 共用分流；国内直连、国外代理；手机去广告另加模块',
        '# SPDX-License-Identifier: GPL-3.0-only',
        '# 公开配置：不含节点、账号、证书或私人服务器地址。首页继续选择自己的节点，路由选「配置」。',
        '# 远程更新会覆盖本地修改；HTTPS 解密证书请放在手机本地的证书模块里。',
        '', '[General]', *GENERAL, f'update-url = {base}/dist/config/main.conf', '', '[Rule]']
    for title, rules in sections(root):
        if rules:
            rows += [f'# {title}', *rules, '']
    rows += ['[Host]', 'localhost = 127.0.0.1', '', '[URL Rewrite]', *URL_REWRITE, '']
    return '\n'.join(rows)


def route_for_test(text, host, port=443, destination_ip=None, country=None, user_agent='', asn=None):
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
        if kind == 'IP-ASN':
            return asn == int(value)
        if kind == 'GEOIP':
            return country == value
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
