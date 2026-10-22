"""Extract static ad rejections from a Loon plugin snapshot. Scripts, jq, body edits and redirects are never imported."""
import fnmatch
import ipaddress
import re
from urllib.parse import urlsplit
from common import domain, exception_for, within

try:
    from re import _parser as sre_parse, _constants as sre_const
except ImportError:  # Python < 3.11
    import sre_parse, sre_constants as sre_const

REJECT_ACTIONS = ('reject', 'reject-200', 'reject-img', 'reject-dict', 'reject-array')
EXAMPLE_CAP = 64


# Two fill styles: if both give the same hosts, the host part of a pattern is fixed rather than variable.
FILLS = ({'word': 'a', 'digit': '1', 'extra': 0}, {'word': 'z', 'digit': '7', 'extra': 2})


def _class_options(items, fill):
    options = []
    for op, av in items:
        if op is sre_const.NEGATE:
            return [fill['word'] + 'q']
        if op is sre_const.LITERAL:
            options.append(chr(av))
        elif op is sre_const.RANGE:
            options.append(chr(av[0] if fill['extra'] == 0 else av[1]))
        elif op is sre_const.CATEGORY:
            options.append(fill['digit'] if av is sre_const.CATEGORY_DIGIT else fill['word'])
    return options[:3] or [fill['word']]


def _examples(seq, fill):
    out = ['']
    for op, av in seq:
        if op is sre_const.LITERAL:
            options = [chr(av)]
        elif op is sre_const.NOT_LITERAL:
            options = [fill['word'] if chr(av) != fill['word'] else 'b']
        elif op is sre_const.ANY:
            options = [fill['word']]
        elif op is sre_const.IN:
            options = _class_options(av, fill)
        elif op is sre_const.BRANCH:
            options = [s for branch in av[1] for s in _examples(branch, fill)]
        elif op is sre_const.SUBPATTERN:
            options = _examples(av[-1], fill)
        elif op is getattr(sre_const, 'ATOMIC_GROUP', None):
            options = _examples(av, fill)
        elif op in (sre_const.MAX_REPEAT, sre_const.MIN_REPEAT, getattr(sre_const, 'POSSESSIVE_REPEAT', None)):
            low, high, sub = av
            body = _examples(sub, fill)
            counts = [low] + ([1] if low == 0 and high >= 1 else [])
            if high > 1:
                counts = [min(c + fill['extra'], high) for c in counts]
            options = [b * n for n in dict.fromkeys(counts) for b in body]
        else:  # anchors, lookarounds and back-references add no characters to an example
            options = ['']
        out = [a + b for a in out for b in options][:EXAMPLE_CAP]
    return out


def example_urls(pattern, fill=FILLS[0]):
    """A few URLs the pattern can match, used to find the hosts a rewrite needs decrypted."""
    return [u for u in _examples(sre_parse.parse(pattern), fill) if re.search(pattern, u)]


def https_hosts(pattern):
    """(hosts, fixed): HTTPS hosts from examples, and whether the host part of the pattern is fixed."""
    found = []
    for fill in FILLS:
        hosts = set()
        for url in example_urls(pattern, fill):
            parsed = urlsplit(url)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
                return None, False
            if parsed.scheme == 'https':
                hosts.add(parsed.hostname.lower())
        found.append(hosts)
    return found[0] | found[1], found[0] == found[1]


def plugin_sections(text):
    result, section = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('[') and line.endswith(']'):
            section = line
            result.setdefault(section, [])
        elif section and line and not line.startswith(('#', ';', '//')):
            result[section].append(line)
    return result


def parse_plugin(body):
    """Return the static subset: domain/IP rejections, reject rewrites and the plugin's MITM hosts."""
    text = body.decode('utf-8-sig') if isinstance(body, bytes) else body
    if '<html' in text[:500].lower():
        raise ValueError('HTML returned instead of a plugin')
    parts = plugin_sections(text)
    if not {'[Rule]', '[Rewrite]', '[MITM]'} <= parts.keys():
        raise ValueError('plugin layout changed: [Rule], [Rewrite] and [MITM] are required')
    domains, networks, rewrites = set(), set(), {}
    for line in parts['[Rule]']:
        fields = [f.strip() for f in line.split(',')]
        if len(fields) < 3 or fields[2] != 'REJECT':
            continue
        if fields[0] in {'DOMAIN', 'DOMAIN-SUFFIX'} and len(fields) == 3:
            try:
                domains.add((fields[0], domain(fields[1])))
            except ValueError:
                continue
        elif fields[0] in {'IP-CIDR', 'IP-CIDR6'} and fields[3:] == ['no-resolve']:
            network = ipaddress.ip_network(fields[1], strict=False)
            if network.prefixlen >= (24 if network.version == 4 else 64) and network.is_global:
                networks.add(f'{fields[0]},{network},REJECT,no-resolve')
    for line in parts['[Rewrite]']:
        tokens = line.split()
        if len(tokens) == 3 and tokens[1] == '-':
            tokens = [tokens[0], tokens[2]]
        if len(tokens) != 2 or tokens[1] not in REJECT_ACTIONS or not tokens[0].startswith('^http'):
            continue
        try:
            re.compile(tokens[0])
        except re.error:
            continue
        rewrites.setdefault(tokens[0], tokens[1])
    mitm = []
    for line in parts['[MITM]']:
        if line.lower().startswith('hostname'):
            mitm += [h.strip().lower() for h in line.split('=', 1)[1].split(',') if h.strip()]
    return {'domains': domains, 'networks': networks, 'rewrites': rewrites, 'mitm': list(dict.fromkeys(mitm))}


def items(body):
    """Flat comparable set for update churn checks."""
    data = parse_plugin(body)
    result = {('RULE',) + d for d in data['domains']} | {('IP', n) for n in data['networks']}
    result |= {('REWRITE', p, a) for p, a in data['rewrites'].items()}
    return result


def _mitm_entry_ok(entry, never_mitm):
    if entry.count('*') > 1 or entry.startswith('*.') and entry.count('.') < 2 or ':' in entry:
        return False
    if re.fullmatch(r'[\d.*]+', entry):  # IP-literal decryption (e.g. HTTPDNS) is not imported
        return False
    try:
        domain(entry.replace('*', 'x1'))
    except ValueError:
        return False
    sample = entry.replace('*', 'x1')
    return not any(within(sample, s) or within(s, entry.lstrip('*.')) for s in never_mitm)


def select(data, policy, probes=()):
    """Choose importable rules: no protected hosts, no critical-URL matches, decryption only where the plugin itself decrypts."""
    never_mitm = policy['never_mitm_suffixes']
    entries = [e for e in data['mitm'] if _mitm_entry_ok(e, never_mitm)]
    exact = set(entries)
    report = {'dropped_protected_domain': 0, 'dropped_probe': 0, 'dropped_no_mitm': 0, 'dropped_bad_example': 0}
    domains = []
    for rule in sorted(data['domains']):
        if exception_for(rule, policy):
            report['dropped_protected_domain'] += 1
        else:
            domains.append(rule)
    rewrites, hosts = [], set()
    for pattern, action in data['rewrites'].items():
        compiled = re.compile(pattern)
        if any(compiled.search(url) for url in probes):
            report['dropped_probe'] += 1
            continue
        https, fixed = https_hosts(pattern)
        if https is None or not example_urls(pattern):
            report['dropped_bad_example'] += 1
            continue
        needed, ok = set(), True
        for host in https:
            cover = [e for e in entries if fnmatch.fnmatchcase(host, e)]
            if not cover:
                ok = False
                break
            # A fixed host is decrypted exactly; a variable host keeps the plugin's own wildcard entry.
            needed.update([host] if fixed or host in exact else cover)
        if not ok:  # an HTTPS variant the plugin never decrypts cannot take effect
            report['dropped_no_mitm'] += 1
            continue
        rewrites.append((pattern, action))
        hosts |= needed
    report.update(domains=len(domains), networks=len(data['networks']), rewrites=len(rewrites), mitm_hosts=len(hosts))
    return {'domains': domains, 'networks': sorted(data['networks']), 'rewrites': rewrites, 'mitm': sorted(hosts), 'report': report}
