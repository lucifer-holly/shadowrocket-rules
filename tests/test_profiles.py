import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, repo_base, load_inputs, load_policy, optimize, is_blocked
from profiles import profile, route_for_test, routing_lists
from personalize import personalize, mandatory_proxy, sections
from validate import check_public_profile


class SharedProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = repo_base()
        cls.text = profile(ROOT, cls.base)
        cls.rule_sets = {cls.base+'/'+name: text for name, text in routing_lists(ROOT).items()}

    def route(self, host, *args, **kwargs):
        return route_for_test(self.text, host, *args, rule_sets=self.rule_sets, **kwargs)

    def test_services_override_domestic_geoip(self):
        # Test with a hypothetical CN destination to catch ordering regressions.
        hosts = ['chatgpt.com', 'api.openai.com', 'api.anthropic.com', 'claude.ai',
                 'gemini.google.com', 'generativelanguage.googleapis.com', 'www.google.com',
                 'www.youtube.com', 'r1.googlevideo.com', 'copilot.microsoft.com',
                 'wrds-www.wharton.upenn.edu', 'wrds-rstudio.wharton.upenn.edu',
                 'wrds-cloud.wharton.upenn.edu', 'wrds-cloud-sshkey.wharton.upenn.edu']
        for host in hosts:
            with self.subTest(host=host):
                self.assertEqual(self.route(host, country='CN'), 'PROXY')

    def test_ssh_and_wrds_database_have_distinct_routes(self):
        self.assertEqual(self.route('wrds-cloud.wharton.upenn.edu', 22), 'DIRECT')
        self.assertEqual(self.route('wrds-cloud-sshkey.wharton.upenn.edu', 22), 'DIRECT')
        self.assertEqual(self.route('wrds-pgdata.wharton.upenn.edu', 9737), 'PROXY')
        self.assertEqual(self.route('example.net', 22), 'DIRECT')
        # A custom SSH port alone must not exempt unrelated traffic.
        self.assertEqual(self.route('example.net', 31237), 'PROXY')

    def test_domestic_payment_lan_and_fallback(self):
        for host in ['www.baidu.com', 'www.alipay.com', 'tenpay.com', 'login.taobao.com']:
            self.assertEqual(self.route(host), 'DIRECT')
        self.assertEqual(self.route('unlisted.example', country='CN'), 'DIRECT')
        self.assertEqual(self.route('unlisted.example', country='US'), 'PROXY')
        for address in ['192.168.1.2', '10.1.2.3', 'fd00::123', 'fe80::1']:
            self.assertEqual(self.route('internal.example', destination_ip=address), 'DIRECT')

    def test_shared_profile_never_enables_adblocking_or_decryption(self):
        check_public_profile(self.text, self.base)
        self.assertNotIn('[MITM]', self.text)
        self.assertNotIn('[Script]', self.text)
        self.assertEqual(self.text.count('RULE-SET,'), 2)
        self.assertNotIn('/dist/rules/base.list', self.text)
        self.assertEqual(self.route('pagead2.googlesyndication.com'), 'PROXY')

    def test_private_ip_and_wrong_update_url_are_rejected(self):
        for changed in [self.text.replace('DST-PORT,22,DIRECT', 'IP-CIDR,192.0.2.123/32,DIRECT'),
                        self.text.replace('update-url = '+self.base, 'update-url = https://example.com'),
                        self.text+'\n[MITM]\nhostname = *\n']:
            with self.assertRaises(ValueError):
                check_public_profile(changed, self.base)

    def test_phone_ad_module_preserves_known_ai_feature_hosts(self):
        rules = optimize(load_inputs()[0], load_policy())[0]
        for host in ['chatgpt.com', 'api.openai.com', 'claude.ai', 'featuregates.org', 'events.statsigapi.net']:
            with self.subTest(host=host):
                self.assertFalse(is_blocked(host, rules))


class PrivateMergeTests(unittest.TestCase):
    def setUp(self):
        self.base = repo_base()
        self.rule_sets = {self.base+'/'+name: body for name, body in routing_lists(ROOT).items()}
        self.original = ('[General]\nupdate-url = https://example.com/public.conf\ndns-server = system\n'
                         '[Rule]\nDOMAIN-SUFFIX,foreign-academic.example,DIRECT\n'
                         'IP-CIDR,192.0.2.44/32,DIRECT,no-resolve\nDST-PORT,22,DIRECT\n'
                         'DOMAIN,proxy-required.cn,PROXY\nDOMAIN-SUFFIX,required.example,PROXY\n'
                         'DOMAIN-KEYWORD,requiredword,PROXY\nUSER-AGENT,Line*,PROXY\n'
                         'IP-CIDR,198.51.100.7/32,PROXY,no-resolve\nFINAL,PROXY\n'
                         '[Host]\nlocalhost = 127.0.0.1\n')
        self.override = '[Rule]\nDOMAIN-SUFFIX,lab.example,DIRECT\n'
        self.text = personalize(self.original, self.base, self.override)

    def route(self, host, **kwargs):
        return route_for_test(self.text, host, rule_sets=self.rule_sets, **kwargs)

    def test_every_original_proxy_rule_is_kept_ahead_of_domestic_routing(self):
        self.assertEqual(len(mandatory_proxy(self.original)), 5)
        for row in mandatory_proxy(self.original):
            self.assertIn(row, self.text)
            self.assertLess(self.text.index(row), self.text.index('routing-direct.list'))
        for host in ['proxy-required.cn', 'a.required.example', 'requiredword.cn']:
            self.assertEqual(self.route(host, country='CN'), 'PROXY')
        self.assertEqual(self.route('www.qq.com', country='CN', user_agent='Line/1.0'), 'PROXY')
        self.assertEqual(self.route('unlisted.example', destination_ip='198.51.100.7', country='CN'), 'PROXY')

    def test_private_destinations_are_merged_into_main_configuration(self):
        self.assertEqual(self.route('lab.example', country='US'), 'DIRECT')
        self.assertEqual(self.route('private.example', port=31237, destination_ip='192.0.2.44'), 'DIRECT')
        self.assertEqual(self.route('wrds-cloud.wharton.upenn.edu', port=22), 'DIRECT')
        self.assertNotIn('update-url = ', self.text)
        self.assertEqual(sections(self.text)['[Host]'], sections(self.original)['[Host]'])

    def test_foreign_direct_entries_are_not_carried_into_new_policy(self):
        self.assertNotIn('DOMAIN-SUFFIX,foreign-academic.example,DIRECT', self.text)
        for host in ['foreign-academic.example', 'www.apple.com', 'www.microsoft.com', 'www.paypal.com']:
            self.assertEqual(self.route(host), 'PROXY')
        self.assertEqual(self.route('unlisted.cn'), 'DIRECT')
        self.assertEqual(self.route('www.qq.com'), 'DIRECT')

    def test_unhandled_proxy_syntax_and_unsafe_private_input_fail_closed(self):
        invalid = self.original.replace('USER-AGENT,Line*,PROXY', 'UNSUPPORTED,example,PROXY')
        with self.assertRaises(ValueError):
            personalize(invalid, self.base)
        for override in ['[Rule]\nFINAL,DIRECT\n', '[Script]\nremote = something\n']:
            with self.assertRaises(ValueError):
                personalize(self.original, self.base, override)


if __name__ == '__main__':
    unittest.main()
