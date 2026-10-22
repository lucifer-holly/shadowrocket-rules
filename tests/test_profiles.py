import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, repo_base, load_inputs, load_policy, optimize, is_blocked
from profiles import profile, route_for_test
from validate import check_public_profile


class SharedProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = repo_base()
        cls.text = profile(ROOT, cls.base)

    def test_services_override_domestic_geoip(self):
        # Test with a hypothetical CN destination to catch ordering regressions.
        hosts = ['chatgpt.com', 'api.openai.com', 'api.anthropic.com', 'claude.ai',
                 'gemini.google.com', 'generativelanguage.googleapis.com', 'www.google.com',
                 'www.youtube.com', 'r1.googlevideo.com', 'copilot.microsoft.com',
                 'wrds-www.wharton.upenn.edu', 'wrds-rstudio.wharton.upenn.edu',
                 'wrds-cloud.wharton.upenn.edu', 'wrds-cloud-sshkey.wharton.upenn.edu']
        for host in hosts:
            with self.subTest(host=host):
                self.assertEqual(route_for_test(self.text, host, country='CN'), 'PROXY')

    def test_ssh_and_wrds_database_have_distinct_routes(self):
        self.assertEqual(route_for_test(self.text, 'wrds-cloud.wharton.upenn.edu', 22), 'DIRECT')
        self.assertEqual(route_for_test(self.text, 'wrds-cloud-sshkey.wharton.upenn.edu', 22), 'DIRECT')
        self.assertEqual(route_for_test(self.text, 'wrds-pgdata.wharton.upenn.edu', 9737), 'PROXY')
        self.assertEqual(route_for_test(self.text, 'example.net', 22), 'DIRECT')
        # A custom SSH port alone must not exempt unrelated traffic.
        self.assertEqual(route_for_test(self.text, 'example.net', 31237), 'PROXY')

    def test_domestic_payment_lan_and_fallback(self):
        for host in ['www.baidu.com', 'www.alipay.com', 'tenpay.com', 'login.taobao.com', 'icloud.com']:
            self.assertEqual(route_for_test(self.text, host), 'DIRECT')
        self.assertEqual(route_for_test(self.text, 'unlisted.example', country='CN'), 'DIRECT')
        self.assertEqual(route_for_test(self.text, 'unlisted.example', country='US'), 'PROXY')
        for address in ['192.168.1.2', '10.1.2.3', 'fd00::123', 'fe80::1']:
            self.assertEqual(route_for_test(self.text, 'internal.example', destination_ip=address), 'DIRECT')

    def test_shared_profile_never_enables_adblocking_or_decryption(self):
        check_public_profile(self.text, self.base)
        self.assertNotIn('[MITM]', self.text)
        self.assertNotIn('[Script]', self.text)
        self.assertNotIn('RULE-SET,', self.text)
        self.assertEqual(route_for_test(self.text, 'pagead2.googlesyndication.com'), 'PROXY')

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


if __name__ == '__main__':
    unittest.main()
