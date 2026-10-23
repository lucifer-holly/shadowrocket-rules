"""Small, strict rule compiler. Python standard library only; never executes inputs."""
import hashlib
import ipaddress
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def json_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n'

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def domain(value):
    # Reject URLs, IPs, ports, wildcards and single-label/public-root candidates.
    if not isinstance(value, str) or value != value.strip() or not value.isascii():
        raise ValueError('domain must be clean ASCII/punycode')
    value = value.lower()
    labels = value.split('.')
    if len(value) > 253 or len(labels) < 2 or not re.fullmatch(r'[a-z][a-z0-9-]*', labels[-1]):
        raise ValueError('invalid domain: ' + value)
    if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x) for x in labels):
        raise ValueError('invalid domain: ' + value)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError('IP is not a domain')

def within(host, parent):
    return host == parent or host.endswith('.' + parent)

def parse_rules(body, fmt):
    if fmt == 'loon-plugin-static':
        from plugin_import import items  # Lazy import: plugin_import depends on this module.
        result = items(body)
        if not result:
            raise ValueError('empty rules')
        return result
    text = body.decode('utf-8-sig')
    if '<html' in text[:500].lower() or '<!doctype' in text[:500].lower():
        raise ValueError('HTML returned instead of rules')
    result = set()
    for num, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', '!', '//')):
            continue
        try:
            if fmt == 'surge':
                parts = line.split(',')
                if len(parts) != 2 or parts[0] not in {'DOMAIN', 'DOMAIN-SUFFIX'}:
                    raise ValueError('unsupported rule; conversion requires review')
                kind, host = parts
            elif fmt == 'suffix-domains':
                kind, host = 'DOMAIN-SUFFIX', line
            else:
                raise ValueError('unsupported input format')
            result.add((kind, domain(host)))
        except ValueError as exc:
            raise ValueError(f'line {num}: {exc}') from exc
    if not result:
        raise ValueError('empty rules')
    return result

def load_policy(root=ROOT):
    p = read_json(root / 'data/policy.json')
    p['exceptions'] = read_json(root / 'data/allowlist.json')['entries']
    for item in p.get('mitm_exceptions', []):
        domain(item['host'])
        if '*' in item['host'] or not item['reason']:
            raise ValueError('decryption exception needs an exact host and a reason')
    for item in p['exceptions']:
        domain(item['domain'])
        if item['scope'] not in {'host', 'subtree'} or not item['reason']:
            raise ValueError('bad exception')
    return p

def exception_for(rule, policy):
    kind, host = rule
    if host in policy['never_block_suffixes']:
        return 'public suffix/shared service root'
    for item in policy['exceptions']:
        allowed = item['domain']
        if host == allowed or (kind == 'DOMAIN-SUFFIX' and within(allowed, host)):
            return item['reason']
        if item['scope'] == 'subtree' and within(host, allowed):
            return item['reason']
    return None

def optimize(rules, policy):
    removed = {r: exception_for(r, policy) for r in rules if exception_for(r, policy)}
    eligible = rules - removed.keys()
    suffixes = {h for k, h in eligible if k == 'DOMAIN-SUFFIX'}
    result = set()
    for kind, host in eligible:
        labels = host.split('.')
        ancestors = ('.'.join(labels[i:]) for i in range(0 if kind == 'DOMAIN' else 1, len(labels)))
        if not any(a in suffixes for a in ancestors):
            result.add((kind, host))
    return sorted(result), removed, len(eligible) - len(result)

def is_blocked(host, rules):
    host = domain(host)
    lookup = set(rules)
    return ('DOMAIN', host) in lookup or any(
        ('DOMAIN-SUFFIX', '.'.join(host.split('.')[i:])) in lookup
        for i in range(len(host.split('.')) - 1))

def load_inputs(root=ROOT, subset=None):
    manifest = read_json(root / 'sources/upstreams.json')['sources']
    lock = read_json(root / 'sources/upstreams.lock.json')['sources']
    all_rules, counts = set(), {}
    for source in manifest:
        sid = source['id']
        # App-ad plugin data has its own module; only plain domain lists feed base/lite.
        if source.get('role', 'domains') != 'domains' or subset is not None and sid not in subset:
            continue
        entry = lock[sid]
        body = (root / source['snapshot']).read_bytes()
        license_body = (root / source['license_file']).read_bytes()
        if sha256(body) != entry['sha256'] or sha256(license_body) != entry['license_sha256']:
            raise ValueError(f'{sid}: snapshot/license does not match lock')
        parsed = parse_rules(body, source['format'])
        if not source['min_rules'] <= len(parsed) <= source['max_rules']:
            raise ValueError(f'{sid}: unreasonable rule count')
        counts[sid] = len(parsed)
        all_rules.update(parsed)
    for item in read_json(root / 'data/extra-domains.json')['rules']:
        if item['type'] not in {'DOMAIN', 'DOMAIN-SUFFIX'} or not item['reason']:
            raise ValueError('bad local rule')
        all_rules.add((item['type'], domain(item['domain'])))
    return all_rules, counts

def repo_base(root=ROOT):
    cfg = read_json(root / 'project.json')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+', cfg['repository']):
        raise ValueError('invalid GitHub repository')
    if cfg['repository'].split('/')[1] in {'.','..'}:
        raise ValueError('invalid repository name')
    if cfg['branch'] != 'main':
        raise ValueError('this workflow publishes from main')
    return f"https://raw.githubusercontent.com/{cfg['repository']}/main"
