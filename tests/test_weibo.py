import re
import shutil
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, read_json, sha256, load_policy, optimize, is_blocked
import build


class WeiboModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = read_json(ROOT / 'data/weibo.json')
        cls.item = next(x for x in read_json(ROOT / 'sources/scripts.lock.json')['scripts'] if x['path'] == 'scripts/weibo.js')
        cls.module = (ROOT / 'dist/modules/weibo.sgmodule').read_text()
        cls.routes = [p for _, p in build.weibo_routes(cls.spec)]
        cls.rewrites = [r['pattern'] for r in cls.spec['rewrites']]

    def section(self, name):
        return self.module.split(f'[{name}]\n')[1].split('\n\n')[0].strip().splitlines()

    def test_module_only_decrypts_the_weibo_api(self):
        self.assertEqual(self.section('MITM'), ['hostname = %APPEND% api.weibo.cn'])
        self.assertNotIn('[Rule]', self.module)

    def test_scripts_use_the_pinned_reviewed_copy(self):
        lines = self.section('Script')
        self.assertEqual(len(lines), len(self.spec['scripts']))
        for line in lines:
            path = re.search(r'script-path=\S+/(dist/scripts/[^,\s]+)', line)[1]
            self.assertEqual(path, f"dist/scripts/weibo.{self.item['sha256']}.js")
            self.assertEqual(sha256((ROOT / path).read_bytes()), self.item['sha256'])
            self.assertEqual(sha256((ROOT / self.item['path']).read_bytes()), self.item['sha256'])

    def test_routes_cover_exact_paths_only(self):
        for group in self.spec['scripts']:
            for p in group['paths']:
                url = f'https://api.weibo.cn/2/{p}'
                with self.subTest(path=p):
                    self.assertTrue(any(re.search(r, url + '?gsid=x') for r in self.routes))
                    self.assertTrue(any(re.search(r, url) for r in self.routes))
                    self.assertFalse(any(re.search(r, url + '/extra') or re.search(r, url + 'x?gsid=x') for r in self.routes))

    def test_login_messages_posting_and_follow_are_never_matched(self):
        urls = self.spec['negative'] + load_policy()['critical_url_probes'] + [
            'https://api.weibo.cn/2/account/login_sms', 'https://api.weibo.cn/2/direct_messages/new',
            'https://api.weibo.cn/2/statuses/repost', 'https://api.weibo.cn/2/comments/reply',
            'https://api.weibo.cn/2/friendships/destroy', 'https://api.weibo.cn/2/remind/unread_count?x=1']
        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(any(re.search(p, url) for p in self.routes + self.rewrites))

    def test_rewrites_answer_whole_promotion_calls_only(self):
        lines = self.section('URL Rewrite')
        self.assertEqual(len(lines), len(self.spec['rewrites']))
        for rule, line in zip(self.spec['rewrites'], lines):
            self.assertEqual(line, rule['pattern'] + ' - reject-dict')
            self.assertTrue(rule['pattern'].startswith('^https://api\\.weibo\\.cn/2/'))
            for url in rule['positive']:
                with self.subTest(url=url):
                    self.assertRegex(url, rule['pattern'])
                    self.assertFalse(any(re.search(r, url) for r in self.routes))

    def test_domain_rules_keep_the_api_and_block_the_extra_ad_hosts(self):
        rules = optimize(build.blocking_inputs()[0], load_policy())[0]
        self.assertFalse(is_blocked('api.weibo.cn', rules))
        for host in ['wax.weibo.com', 'dsp.edm.weibo.cn', 'adpinpai.video.weibocdn.com']:
            with self.subTest(host=host):
                self.assertTrue(is_blocked(host, rules))
        for host in ['f.video.weibocdn.com', 'weibo.com', 'm.weibo.cn']:
            with self.subTest(allowed=host):
                self.assertFalse(is_blocked(host, rules))

    def test_any_change_to_the_script_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'repo'
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('.git', '.cache', '__pycache__'))
            target = copy / self.item['path']
            target.write_text(target.read_text() + '\n// changed\n')
            with self.assertRaises(ValueError):
                build.outputs(copy)


if __name__ == '__main__':
    unittest.main()
