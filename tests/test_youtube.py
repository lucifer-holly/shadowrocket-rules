import re
import shutil
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import ROOT, read_json, sha256
import build


class YouTubeModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.item = next(x for x in read_json(ROOT / 'sources/scripts.lock.json')['third_party'] if x['id'] == 'maasea-youtube-response')
        cls.module = (ROOT / 'dist/modules/youtube.sgmodule').read_text()

    def test_module_only_decrypts_the_youtube_api_and_blocks_its_quic(self):
        self.assertIn('hostname = %APPEND% youtubei.googleapis.com\n', self.module)
        self.assertNotIn('googlevideo', self.module)
        rules = self.module.split('[Rule]\n')[1].split('\n\n')[0].splitlines()
        self.assertEqual(rules, ['AND,((DOMAIN,youtubei.googleapis.com),(PROTOCOL,UDP)),REJECT-NO-DROP'])

    def test_script_is_the_pinned_reviewed_copy(self):
        path = re.search(r'script-path=\S+/(dist/scripts/[^,\s]+)', self.module)[1]
        self.assertEqual(path, f"dist/scripts/youtube.response.{self.item['sha256']}.js")
        self.assertEqual(sha256((ROOT / path).read_bytes()), self.item['sha256'])

    def test_route_covers_ad_bearing_endpoints_only(self):
        pattern = re.search(r'pattern=(\S+?),requires-body', self.module)[1]
        for url in ['https://youtubei.googleapis.com/youtubei/v1/player?key=x', 'https://youtubei.googleapis.com/youtubei/v1/browse']:
            self.assertRegex(url, pattern)
        for url in ['https://youtubei.googleapis.com/youtubei/v1/account/account_menu', 'https://accounts.google.com/o/oauth2/token',
                    'https://youtubei.googleapis.com.evil.test/youtubei/v1/player']:
            self.assertIsNone(re.search(pattern, url))

    def test_any_change_to_the_script_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / 'repo'
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('.git', '.cache', '__pycache__'))
            target = copy / self.item['path']
            target.write_text(target.read_text() + '\n$httpClient.post({url:"https://example.com"});\n')
            with self.assertRaises(ValueError):
                build.outputs(copy)


if __name__ == '__main__':
    unittest.main()
