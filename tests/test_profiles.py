import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, repo_base, read_json, load_inputs, load_policy, optimize, is_blocked
from profiles import profile, route_for_test, rule_list, sections
from validate import check_public_profile


class SharedProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = repo_base()
        cls.text = profile(ROOT, cls.base)
        cls.legacy = rule_list(ROOT / 'data/legacy-proxy.list', 'PROXY')
        cls.manual = rule_list(ROOT / 'data/manual-direct.list', 'DIRECT')
        cls.rules = [l.strip() for l in cls.text.split('[Rule]')[1].split('[Host]')[0].splitlines()
                     if l.strip() and not l.startswith('#')]

    def route(self, host, *args, **kwargs):
        return route_for_test(self.text, host, *args, **kwargs)

    def test_all_257_original_proxy_rules_kept_in_order_before_domestic_direct(self):
        self.assertEqual(len(self.legacy), 257)
        positions = [self.rules.index(row) for row in self.legacy]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[-1], self.rules.index('DOMAIN-SUFFIX,apple.com,DIRECT'))
        self.assertLess(positions[-1], self.rules.index('DOMAIN-SUFFIX,qq.com,DIRECT'))

    def test_original_proxy_rules_win_even_for_mainland_addresses(self):
        for row in self.legacy:
            kind, value = row.split(',')[:2]
            kwargs = {'country': 'CN'}
            if kind == 'DOMAIN':
                host = value
            elif kind == 'DOMAIN-SUFFIX':
                host = 'www.' + value
            elif kind == 'DOMAIN-KEYWORD':
                host = value + '.example.cn'
            elif kind == 'USER-AGENT':
                host, kwargs['user_agent'] = 'www.qq.com', value.replace('*', '/1.0')
            else:
                network = value.split('/')[0]
                host, kwargs['destination_ip'] = network, network
            with self.subTest(rule=row):
                self.assertEqual(self.route(host, **kwargs), 'PROXY')

    def test_manual_direct_exceptions_stay_first(self):
        self.assertEqual(self.rules[:len(self.manual)], self.manual)
        for host in ['update.code.visualstudio.com', 'vscode.download.prss.microsoft.com',
                     'www.tsinghua.edu.cn', 'meeting.tencentmeeting.cn', 'mail.yeah.net', 'www.xiaohongshu.com']:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='US'), 'DIRECT')

    def test_ai_google_youtube_and_wrds_use_proxy_ahead_of_mainland_routing(self):
        hosts = ['chatgpt.com', 'api.openai.com', 'api.anthropic.com', 'claude.ai',
                 'gemini.google.com', 'generativelanguage.googleapis.com', 'www.google.com', 'www.google.cn',
                 'www.youtube.com', 'r1.googlevideo.com', 'copilot.microsoft.com',
                 'wrds-www.wharton.upenn.edu', 'wrds-rstudio.wharton.upenn.edu']
        for host in hosts:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='CN'), 'PROXY')

    def test_ssh_and_wrds_database_have_distinct_routes(self):
        self.assertEqual(self.route('wrds-cloud.wharton.upenn.edu', 22), 'DIRECT')
        self.assertEqual(self.route('example.net', 22), 'DIRECT')
        self.assertEqual(self.route('wrds-pgdata.wharton.upenn.edu', 9737), 'PROXY')
        # A server reached by IP on a custom SSH port: mainland addresses go direct via GEOIP, others use the proxy.
        self.assertEqual(self.route('192.0.2.10', 2222, destination_ip='192.0.2.10', country='CN'), 'DIRECT')
        self.assertEqual(self.route('192.0.2.10', 2222, destination_ip='192.0.2.10', country='US'), 'PROXY')

    def test_paypal_always_uses_proxy(self):
        for host in ['www.paypal.com', 'www.paypalobjects.com', 'paypal.me']:
            self.assertEqual(self.route(host, country='CN'), 'PROXY')

    def test_apple_and_microsoft_split(self):
        direct = ['apps.apple.com', 'iosapps.itunes.apple.com', 'updates.cdn-apple.com', 'is1-ssl.mzstatic.com',
                  'www.icloud.com', 'www.apple.com.cn', 'download.windowsupdate.com', 'www.microsoft.com',
                  'marketplace.visualstudio.com', 'gallerycdn.vsassets.io']
        proxy = ['apple-relay.apple.com', 'www.apple.news', 'copilot.microsoft.com', 'www.bing.com',
                 'login.microsoftonline.com', 'outlook.office365.com', 'login.live.com']
        for host in direct:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='US'), 'DIRECT')
        for host in proxy:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='CN'), 'PROXY')

    def test_domestic_payment_lan_and_fallback(self):
        for host in ['weixin.qq.com', 'www.bilibili.com', 'i0.hdslb.com', 'www.taobao.com', 'www.alipay.com',
                     'wx.tenpay.com', 'www.abchina.com', 'www.zhihu.com', 'unlisted.cn']:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='US'), 'DIRECT')
        self.assertEqual(self.route('203.0.113.5', destination_ip='203.0.113.5', asn=132203), 'DIRECT')
        self.assertEqual(self.route('unlisted.example', country='CN'), 'DIRECT')
        self.assertEqual(self.route('unlisted.example', country='US'), 'PROXY')
        for address in ['192.168.1.2', '10.1.2.3', 'fd00::123', 'fe80::1']:
            self.assertEqual(self.route('internal.example', destination_ip=address), 'DIRECT')

    def test_former_foreign_direct_entries_now_use_proxy_abroad(self):
        for host in read_json(ROOT / 'data/routing.json')['former_direct_now_proxy']['domains']:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='US'), 'PROXY')

    def test_direct_groups_are_not_shadowed_by_earlier_proxy_rules(self):
        for title, rows in sections(ROOT)[2:]:
            for row in rows:
                kind, value, policy = (row.split(',') + ['', ''])[:3]
                if kind == 'DOMAIN-SUFFIX' and policy == 'DIRECT':
                    with self.subTest(group=title, rule=row):
                        self.assertEqual(self.route('www.' + value, country='US'), 'DIRECT')

    def test_public_profile_boundaries(self):
        check_public_profile(self.text, self.base)
        for section in ['[MITM]', '[Script]', '[Proxy]', 'RULE-SET', 'REJECT,']:
            self.assertNotIn(section, self.text)
        bad = [self.text.replace('DST-PORT,22,DIRECT', 'DST-PORT,22,DIRECT\nIP-CIDR,1.1.1.1/32,DIRECT,no-resolve'),
               self.text.replace('update-url = ' + self.base, 'update-url = https://example.com'),
               self.text + '\n[MITM]\nhostname = *\n',
               self.text.replace('GEOIP,CN,DIRECT', 'RULE-SET,https://example.com/r.list,DIRECT\nGEOIP,CN,DIRECT'),
               self.text.replace(self.legacy[-1] + '\n', '').replace('FINAL,PROXY', self.legacy[-1] + '\nFINAL,PROXY')]
        for changed in bad:
            with self.assertRaises(ValueError):
                check_public_profile(changed, self.base)

    def test_ipv6_enabled_with_ipv4_preferred(self):
        # IPv6 stays available, but IPv4 answers are used first so IPv4-only networks keep working.
        self.assertIn('\nipv6 = true\n', self.text)
        self.assertIn('\nprefer-ipv6 = false\n', self.text)

    def test_phone_ad_module_preserves_known_ai_feature_hosts(self):
        rules = optimize(load_inputs()[0], load_policy())[0]
        for host in ['chatgpt.com', 'api.openai.com', 'claude.ai', 'featuregates.org', 'events.statsigapi.net']:
            with self.subTest(host=host):
                self.assertFalse(is_blocked(host, rules))


if __name__ == '__main__':
    unittest.main()
