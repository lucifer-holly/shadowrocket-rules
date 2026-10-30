import datetime as dt
import fnmatch
import re
import sys
from pathlib import Path
import unittest
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, load_policy, optimize, is_blocked, read_json
from plugin_import import parse_plugin, select, items, https_hosts
from build import imported_app_ads, blocking_inputs, observed_hosts, app_sections

SAMPLE = r'''#!name=sample
#!date=2026-10-01 08:00:00
[Argument]
switch = switch,true,false
[Rule]
DOMAIN-SUFFIX, ads.example.com, REJECT
DOMAIN,track.example.net,REJECT
DOMAIN-SUFFIX,paypal.com,REJECT
DOMAIN-KEYWORD,adsdk,REJECT
DOMAIN,api.example.org,PROXY
IP-CIDR, 203.0.112.0/16, REJECT, no-resolve
IP-CIDR, 198.51.99.9/32, REJECT, no-resolve
[Rewrite]
^https?:\/\/ad\.cdn\.example\.com\/splash reject-dict
^https?:\/\/img\d+\.example\.com\/ad\/ - reject-img
^https:\/\/api\.notdecrypted\.com\/ad reject
^https:\/\/mclient\.alipay\.com\/ad reject
^https:\/\/feed\.example\.com\/list response-body-json-jq 'del(.ads)'
^https:\/\/feed\.example\.com\/mock mock-response-body data-type=text data="{}"
^https:\/\/feed\.example\.com\/old 302 https://example.com/
^https:\/\/feed\.example\.com\/login reject
[Script]
http-response ^https:\/\/feed\.example\.com\/x script-path=https://example.com/evil.js, requires-body=true
[MITM]
hostname = *.example.com, *.alipay.com, 119.29.29.*, feed.example.com
'''
PROBES = ['https://feed.example.com/login?next=1']


class PluginImportTests(unittest.TestCase):
    def setUp(self):
        self.policy = dict(load_policy(), never_mitm_suffixes=['alipay.com'])
        self.data = parse_plugin(SAMPLE.encode())
        self.out = select(self.data, self.policy, PROBES)

    def test_only_static_reject_data_is_parsed(self):
        self.assertEqual(set(self.data['rewrites']), {
            r'^https?:\/\/ad\.cdn\.example\.com\/splash', r'^https?:\/\/img\d+\.example\.com\/ad\/',
            r'^https:\/\/api\.notdecrypted\.com\/ad', r'^https:\/\/mclient\.alipay\.com\/ad',
            r'^https:\/\/feed\.example\.com\/login'})
        self.assertIn(('DOMAIN-SUFFIX', 'ads.example.com'), self.data['domains'])
        self.assertNotIn(('DOMAIN', 'api.example.org'), self.data['domains'])
        self.assertEqual(self.data['networks'], {'IP-CIDR,198.51.99.9/32,REJECT,no-resolve'})
        self.assertTrue(all(kind in {'RULE', 'IP', 'REWRITE'} for kind, *_ in items(SAMPLE.encode())))

    def test_protected_hosts_probes_and_undecrypted_hosts_are_dropped(self):
        kept = dict(self.out['rewrites'])
        self.assertNotIn(r'^https:\/\/mclient\.alipay\.com\/ad', kept)
        self.assertNotIn(r'^https:\/\/api\.notdecrypted\.com\/ad', kept)
        self.assertNotIn(r'^https:\/\/feed\.example\.com\/login', kept)
        self.assertNotIn(('DOMAIN-SUFFIX', 'paypal.com'), self.out['domains'])
        self.assertEqual(self.out['report']['dropped_probe'], 1)

    def test_decryption_is_narrowed_to_what_kept_rules_need(self):
        self.assertEqual(dict(self.out['rewrites'])[r'^https?:\/\/ad\.cdn\.example\.com\/splash'], 'reject-dict')
        # Fixed host: exact name instead of the plugin wildcard. Variable host: the plugin's wildcard.
        self.assertEqual(self.out['mitm'], ['*.example.com', 'ad.cdn.example.com'])
        self.assertEqual(https_hosts(r'^https?:\/\/(a|b)\.example\.com\/')[1], True)
        self.assertEqual(https_hosts(r'^https?:\/\/a\d+\.example\.com\/')[1], False)

    def test_owner_opt_outs_remove_blocks_rewrites_and_decryption(self):
        out = select(self.data, self.policy, PROBES, exclude_hosts=['cdn.example.com'],
                     exclude_patterns=[r'^https?:\/\/img\d+\.example\.com\/ad\/'])
        self.assertEqual(out['rewrites'], [])
        self.assertEqual(out['mitm'], [])
        self.assertEqual(out['report']['dropped_override'], 2)
        out = select(self.data, self.policy, PROBES, exclude_hosts=['example.com'])
        self.assertNotIn(('DOMAIN-SUFFIX', 'ads.example.com'), out['domains'])
        self.assertNotIn('*.example.com', out['mitm'])

    def test_reviewed_exact_hosts_inside_protected_suffixes_stay_decryptable(self):
        policy = dict(self.policy, never_mitm_suffixes=['alipay.com', 'example.com'],
                      mitm_exceptions=[{'host': 'ad.cdn.example.com', 'reason': 'image host'}])
        out = select(self.data, policy, PROBES)
        self.assertEqual(out['mitm'], ['ad.cdn.example.com'])
        self.assertEqual([p for p, _ in out['rewrites']], [r'^https?:\/\/ad\.cdn\.example\.com\/splash'])
        # Without the exact plugin entry the exception cannot widen decryption, and an owner opt-out still wins.
        self.assertEqual(select(parse_plugin(SAMPLE.replace(', feed.example.com', '').replace('*.example.com, ', '').encode()), policy, PROBES)['mitm'], [])
        self.assertEqual(select(self.data, policy, PROBES, exclude_hosts=['cdn.example.com'])['mitm'], [])

    def test_layout_change_fails_closed(self):
        with self.assertRaises(ValueError):
            parse_plugin(b'[Rule]\nDOMAIN,ad.example.com,REJECT\n')
        with self.assertRaises(ValueError):
            parse_plugin(b'<html>404</html>')


class RealSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()
        cls.out = imported_app_ads(ROOT, cls.policy)
        cls.module = (ROOT / 'dist/modules/app-ads.sgmodule').read_text()

    def test_module_carries_no_scripts_or_body_edits(self):
        for marker in ['[Script]', 'script-path', 'json-jq', 'mock-response', 'response-body', '[Argument]', '[Map Local]']:
            self.assertNotIn(marker, self.module)

    def test_every_kept_rewrite_is_decrypted_by_an_upstream_mitm_entry(self):
        upstream = [h for h in parse_plugin((ROOT / 'vendor/fmz-blockads.plugin').read_bytes())['mitm']]
        # Owner-listed observe_hosts are the only decryption not taken from the plugin.
        for host in sorted(set(self.out['mitm']) - set(self.out['observed'])):
            with self.subTest(host=host):
                self.assertTrue(host in upstream or any(fnmatch.fnmatchcase(host, e) for e in upstream))
        for pattern, _ in self.out['rewrites']:
            hosts, _ = https_hosts(pattern)
            for host in hosts:
                self.assertTrue(any(fnmatch.fnmatchcase(host, e) for e in self.out['mitm']), pattern)

    def test_critical_urls_and_hosts_survive(self):
        for pattern, _ in self.out['rewrites']:
            for url in self.policy['critical_url_probes']:
                self.assertIsNone(re.search(pattern, url), (pattern, url))
        for url in self.policy['critical_url_probes']:
            host = urlsplit(url).hostname
            with self.subTest(host=host):
                self.assertFalse(is_blocked(host, self.out['domains']))
        self.assertGreater(len(self.out['rewrites']), 500)

    def test_observed_hosts_are_only_decrypted(self):
        mitm = next(l for l in self.module.splitlines() if l.startswith('hostname = %APPEND% '))
        for host in self.out['observed']:
            with self.subTest(host=host):
                self.assertIn(host, mitm.split('= %APPEND% ')[1].split(', '))
                self.assertFalse(is_blocked(host, self.out['domains']))
                for pattern, _ in self.out['rewrites']:
                    self.assertNotIn(host, https_hosts(pattern)[0])
        if self.out['observed']:
            self.assertIn('# 只解密、不拦截', self.module)
        else:
            self.assertNotIn('# 只解密、不拦截', self.module)

    def test_observed_hosts_stop_decrypting_after_their_date(self):
        # docs/STATUS.md: the Huya troubleshooting hosts go by 2026-11-05 at the latest; the build enforces it.
        overrides = read_json(ROOT / 'data/app-ads-overrides.json')
        listed = sorted(item['host'] for item in overrides['observe_hosts'])
        for item in overrides['observe_hosts']:
            with self.subTest(host=item['host']):
                self.assertLessEqual(item['until'], '2026-11-05')
        last_day = imported_app_ads(ROOT, self.policy, today=dt.date(2026, 11, 5))
        after = imported_app_ads(ROOT, self.policy, today=dt.date(2026, 11, 6))
        self.assertEqual(last_day['observed'], listed)
        self.assertEqual((after['observed'], after['observe_expired']), ([], listed))
        mitm = dict(app_sections(read_json(ROOT / 'data/apps.json'), after))['MITM']
        self.assertFalse(any(line.startswith('# 只解密') for line in mitm))
        decrypted = mitm[-1].split('= %APPEND% ')[1].split(', ')
        for host in listed:
            with self.subTest(expired=host):
                self.assertNotIn(host, decrypted)
        # Investigation over on 2026-10-30: paths seen in the 10-22 logs, or no traffic since decryption began.
        for host in ['hd.huya.com', 'diy-front.cdn.huya.com', 'diy-assets.msstatic.com']:
            with self.subTest(dropped=host):
                self.assertNotIn(host, self.out['mitm'])
                self.assertNotIn(host, listed)

    def test_observe_entries_need_a_reason_and_a_near_until_date(self):
        today = dt.date(2026, 10, 30)
        entry = {'host': 'img.example.com', 'reason': 'locate the splash image', 'until': '2026-11-05'}
        self.assertEqual(observed_hosts({'exclude_hosts': [], 'observe_hosts': [entry]}, today),
                         ({'img.example.com': dt.date(2026, 11, 5)}, []))
        self.assertEqual(observed_hosts({'exclude_hosts': [], 'observe_hosts': [entry]}, dt.date(2026, 11, 6)),
                         ({}, ['img.example.com']))
        for change in [{'until': None}, {'until': 'soon'}, {'until': '2026-11-21'}, {'reason': ''}]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    observed_hosts({'exclude_hosts': [], 'observe_hosts': [dict(entry, **change)]}, today)
        without_date = {k: v for k, v in entry.items() if k != 'until'}
        for overrides in [{'exclude_hosts': [], 'observe_hosts': [without_date]}, {'exclude_hosts': ['example.com'], 'observe_hosts': [entry]}]:
            with self.assertRaises(ValueError):
                observed_hosts(overrides, today)

    def test_static_domain_rules_live_in_the_domain_modules_only(self):
        # ② carries app-specific rules only; every plugin domain and IP rule is enforced by both variants of ①.
        rules = self.module.split('[Rule]\n')[1].split('\n\n')[0].splitlines()
        self.assertTrue(rules)
        for line in rules:
            self.assertRegex(line, r'^AND,\(\(URL-REGEX,\^http://[^,()\s]+\),\(USER-AGENT,[^,()\s]+\)\),REJECT$')
        base = optimize(blocking_inputs(policy=self.policy, imported=self.out)[0], self.policy)[0]
        lite = optimize(blocking_inputs(subset={'hagezi-light'}, policy=self.policy, imported=self.out)[0], self.policy)[0]
        for rule in self.out['domains']:
            with self.subTest(rule=rule):
                self.assertTrue(is_blocked(rule[1], base) and is_blocked(rule[1], lite))
        for name in ['base', 'lite']:
            text = (ROOT / f'dist/modules/{name}.sgmodule').read_text()
            for network in self.out['networks']:
                self.assertIn('\n' + network + '\n', text)

    def test_banks_and_payments_are_decrypted_only_on_reviewed_image_hosts(self):
        reviewed = {x['host'] for x in self.policy['mitm_exceptions']}
        protected = [h for h in self.out['mitm'] if any(h == s or h.endswith('.' + s) for s in self.policy['never_mitm_suffixes'])]
        self.assertTrue(set(protected) <= reviewed, set(protected) - reviewed)
        for host in ['m.creditcard.ecitic.com', 'wap.spdb.com.cn', 'mbank5.jsbchina.cn', 'mobile.cebbank.com', 'ms.jr.jd.com', 'mapi-app.bestpay.com.cn']:
            with self.subTest(host=host):
                self.assertNotIn(host, self.out['mitm'])
                self.assertFalse(any(host in p.replace('\\', '') for p, _ in self.out['rewrites']))

    def test_safari_fraud_warning_service_is_not_blocked(self):
        base = optimize(blocking_inputs(policy=self.policy, imported=self.out)[0], self.policy)[0]
        for host in ['safebrowsing.apple', 'token.safebrowsing.apple', 'proxy.safebrowsing.apple', 'safebrowsing.g.applimg.com',
                     'safebrowsing.googleapis.com', 'safebrowsing.urlsec.qq.com']:
            with self.subTest(host=host):
                self.assertFalse(is_blocked(host, self.out['domains']) or is_blocked(host, base))


if __name__ == '__main__':
    unittest.main()
