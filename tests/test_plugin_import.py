import fnmatch
import re
import sys
from pathlib import Path
import unittest
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, load_policy, is_blocked
from plugin_import import parse_plugin, select, items, https_hosts
from build import imported_app_ads

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
        for host in self.out['mitm']:
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


if __name__ == '__main__':
    unittest.main()
