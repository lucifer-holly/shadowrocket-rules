import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, read_json, sha256, load_policy, optimize, is_blocked
import build
import validate


def module_lines(name, section):
    text = (ROOT / f'dist/modules/{name}.sgmodule').read_text()
    if f'[{section}]\n' not in text:
        return []
    return text.split(f'[{section}]\n')[1].split('\n\n')[0].strip().splitlines()


class WechatModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = read_json(ROOT / 'data/wechat.json')
        cls.item = next(x for x in read_json(ROOT / 'sources/scripts.lock.json')['scripts'] if x['path'] == 'scripts/wechat.js')
        cls.routes = [r['pattern'] for r in cls.spec['scripts']]
        cls.rewrites = [r['pattern'] for r in cls.spec['rewrites']]

    def test_module_only_decrypts_the_article_host(self):
        self.assertEqual(module_lines('wechat', 'MITM'), ['hostname = %APPEND% mp.weixin.qq.com'])
        self.assertEqual(module_lines('wechat', 'Rule'), [])

    def test_scripts_use_the_pinned_reviewed_copy_and_size_limits(self):
        lines = module_lines('wechat', 'Script')
        self.assertEqual(len(lines), len(self.spec['scripts']))
        for route, line in zip(self.spec['scripts'], lines):
            path = re.search(r'script-path=\S+/(dist/scripts/[^,\s]+)', line)[1]
            self.assertEqual(path, f"dist/scripts/wechat.{self.item['sha256']}.js")
            self.assertEqual(sha256((ROOT / path).read_bytes()), self.item['sha256'])
            self.assertIn(f"pattern={route['pattern']},requires-body=true,max-size={route['max_size']},", line)
        self.assertLessEqual(max(r['max_size'] for r in self.spec['scripts']), 5242880)

    def test_no_other_module_touches_the_article_host(self):
        for name in ['app-ads', 'apps-all', 'response-cleaner', 'weibo', 'youtube']:
            with self.subTest(module=name):
                text = (ROOT / f'dist/modules/{name}.sgmodule').read_text()
                self.assertNotIn('mp.weixin.qq.com', text)
                self.assertNotIn('mp\\.weixin\\.qq\\.com', text)

    def test_article_functions_are_never_matched(self):
        probes = load_policy()['critical_url_probes']
        for url in self.spec['negative'] + probes:
            with self.subTest(url=url):
                self.assertFalse(any(re.search(p, url) for p in self.rewrites))
                if url not in self.spec['scripts'][0]['probes']:
                    self.assertFalse(any(re.search(p, url) for p in self.routes))

    def test_only_the_article_route_declares_a_critical_probe(self):
        for route in self.spec['scripts']:
            touched = [u for u in load_policy()['critical_url_probes'] if re.search(route['pattern'], u)]
            with self.subTest(route=route['id']):
                self.assertEqual(sorted(touched), sorted(route.get('probes', [])))
                if touched:
                    self.assertEqual(route['id'], 'article')

    def test_article_hosts_are_never_blocked(self):
        rules = optimize(build.blocking_inputs()[0], load_policy())[0]
        for host in ['mp.weixin.qq.com', 'mmbiz.qpic.cn', 'mmbiz.qlogo.cn', 'mpvideo.qpic.cn', 'res.wx.qq.com']:
            with self.subTest(host=host):
                self.assertFalse(is_blocked(host, rules))

    def test_any_change_to_the_script_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'repo'
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('.git', '.cache', '__pycache__'))
            target = copy / self.item['path']
            target.write_text(target.read_text() + '\n// changed\n')
            with self.assertRaises(ValueError):
                build.outputs(copy)


class WechatValidatorTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_json(ROOT / 'data/wechat.json')
        self.policy = load_policy()

    def test_rejects_a_route_reaching_an_undeclared_critical_url(self):
        spec = json.loads(json.dumps(self.spec))
        spec['scripts'][0]['probes'] = []
        with self.assertRaises(ValueError):
            validate.check_wechat(spec, self.policy, [])
        spec = json.loads(json.dumps(self.spec))
        spec['scripts'][1]['pattern'] = '^https://mp\\.weixin\\.qq\\.com/'
        with self.assertRaises(ValueError):
            validate.check_wechat(spec, self.policy, [])

    def test_rejects_rules_that_reach_article_functions(self):
        spec = json.loads(json.dumps(self.spec))
        spec['rewrites'].append({'pattern': '^https://mp\\.weixin\\.qq\\.com/mp/appmsg_comment', 'action': 'reject-dict',
                                 'reason': 'x', 'positive': ['https://mp.weixin.qq.com/mp/appmsg_comment?action=getcomment&__biz=example']})
        with self.assertRaises(ValueError):
            validate.check_wechat(spec, self.policy, [])

    def test_accepts_the_published_spec(self):
        validate.check_wechat(self.spec, self.policy, [])


if __name__ == '__main__':
    unittest.main()
