import contextlib
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import devicelog

ROWS = [
    ('https://ads.app.example/ssp/material/x.jpg?token=SECRET', 'App/1.0', 'DOMAIN,ads.app.example,REJECT # mynode', 'REJECT', '2026-10-22 10:00:01'),
    ('api.app.example:443', 'TCP Stream', 'DOMAIN-SUFFIX,app.example,DIRECT # mynode', 'DIRECT', '2026-10-22 10:00:02'),
    ('private.other.example:443', 'TCP Stream', 'FINAL,PROXY # mynode', 'PROXY', '2026-10-22 10:00:02'),
    ('http://cdn.other.example/a.png', 'App/1.0 CFNetwork', 'GEOIP,CN,DIRECT # mynode', 'DIRECT', '2026-10-22 10:00:02'),
    ('sdk.adnet.example:443', 'TCP Stream', 'DOMAIN-SUFFIX,adnet.example,REJECT # mynode', 'REJECT', '2026-10-22 10:00:03'),
    ('late.adnet.example:443', 'TCP Stream', 'DOMAIN-SUFFIX,adnet.example,REJECT # mynode', 'REJECT', '2026-10-22 10:05:00'),
]


def export(path, rows):
    """Same layout as a Shadowrocket export: an FTS3 table whose rows live in logging_content."""
    con = sqlite3.connect(path)
    try:
        con.execute('CREATE VIRTUAL TABLE logging USING fts3(url text, ua text, result text, type text, created DATETIME)')
        con.executemany('INSERT INTO logging VALUES (?, ?, ?, ?, ?)', rows)
    except sqlite3.OperationalError:  # SQLite built without FTS3: the reader only needs logging_content.
        con.execute("CREATE TABLE logging_content(docid INTEGER PRIMARY KEY, c0url, c1ua, c2result, c3type, c4created)")
        con.executemany('INSERT INTO logging_content(c0url, c1ua, c2result, c3type, c4created) VALUES (?, ?, ?, ?, ?)', rows)
    con.commit()
    con.close()


class DeviceLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'proxy.db'
        export(self.db, ROWS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_app_rows_and_nearby_rejects_are_shown(self):
        text, code = devicelog.report(self.db, r'app\.example', r'App/')
        self.assertEqual(code, 0)
        for shown in ['ads.app.example', '/ssp/material/x.jpg', 'api.app.example', 'cdn.other.example', 'sdk.adnet.example']:
            self.assertIn(shown, text)
        for hidden in ['SECRET', 'token=', 'mynode', 'private.other.example', 'late.adnet.example']:
            self.assertNotIn(hidden, text)
        text, _ = devicelog.report(self.db, r'app\.example', r'App/', nearby=False, timeline=True)
        self.assertNotIn('sdk.adnet.example', text)
        self.assertIn('时间线', text)

    def test_global_proxy_routing_is_flagged(self):
        db = Path(self.tmp.name) / 'routing.db'
        export(db, [(r[0], r[1], 'ROUTING,PROXY # mynode', 'PROXY', r[4]) for r in ROWS])
        text, _ = devicelog.report(db, r'app\.example')
        self.assertIn('全局路由', text)
        self.assertNotIn('mynode', text)

    def test_empty_export_explains_how_to_export_again(self):
        db = Path(self.tmp.name) / 'empty.db'
        con = sqlite3.connect(db)
        con.execute('PRAGMA journal_mode=WAL')
        con.close()
        text, code = devicelog.report(db, r'app\.example')
        self.assertEqual(code, 2)
        self.assertIn('启用日志记录', text)

    def test_reading_never_changes_or_adds_files(self):
        before = sorted(p.name for p in Path(self.tmp.name).iterdir()), self.db.read_bytes()
        devicelog.report(self.db, r'app\.example')
        self.assertEqual(before, (sorted(p.name for p in Path(self.tmp.name).iterdir()), self.db.read_bytes()))

    def test_cli_preset_and_rule_check_against_the_build(self):
        db = Path(self.tmp.name) / 'huya.db'
        export(db, [('business-qnpcdn.msstatic.com:443', 'TCP Stream', 'GEOIP,CN,DIRECT', 'DIRECT', '2026-10-22 10:00:01'),
                    ('hd.huya.com:443', 'TCP Stream', 'DOMAIN-SUFFIX,huya.com,DIRECT', 'DIRECT', '2026-10-22 10:00:02')])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = devicelog.main([str(db), '--app', 'huya', '--check'])
        self.assertEqual(code, 0)
        self.assertIn('business-qnpcdn.msstatic.com: base 拦截', out.getvalue())
        self.assertIn('hd.huya.com: 只解密', out.getvalue())

    def test_rule_check_handles_apps_that_connect_by_ip(self):
        db = Path(self.tmp.name) / 'xianyu.db'
        ua = '%E9%97%B2%E9%B1%BC/59062879 CFNetwork/3826'
        export(db, [('http://59.82.113.219/amdc/mobileDispatch?appkey=SECRET', ua, 'GEOIP,CN,DIRECT', 'DIRECT', '2026-10-23 11:45:22'),
                    ('acs.m.goofish.com:443', ua, 'DOMAIN-SUFFIX,goofish.com,DIRECT', 'DIRECT', '2026-10-23 11:45:23')])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = devicelog.main([str(db), '--app', 'xianyu', '--check'])
        self.assertEqual(code, 0)
        self.assertIn('59.82.113.219: 未拦截、未解密', out.getvalue())
        self.assertIn('acs.m.goofish.com: app-ads 解密', out.getvalue())
        self.assertNotIn('SECRET', out.getvalue())


if __name__ == '__main__':
    unittest.main()
