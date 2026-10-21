import datetime as dt
import importlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from common import *
import build
import upstream
from integrate import integrate,MARKER
from validate import validate,scan_public,check_script

class ParserTests(unittest.TestCase):
    def test_native_semantics(self):
        r=parse_rules(b'# comment\nDOMAIN,Ad.Example.com\nDOMAIN-SUFFIX,ad.net\n','surge')
        self.assertIn(('DOMAIN','ad.example.com'),r)
        self.assertFalse(is_blocked('child.ad.example.com',r))
        self.assertTrue(is_blocked('child.ad.net',r))
    def test_invalid_inputs(self):
        for text in ['<html>404</html>','DOMAIN-KEYWORD,ad','RULE-SET,https://example.com/rules','DOMAIN,x.com,PROXY','DOMAIN-SUFFIX,com','DOMAIN,127.0.0.1','DOMAIN,*.test.com','DOMAIN,foo..com','DOMAIN,foo.com:443']:
            with self.subTest(text=text),self.assertRaises(ValueError):parse_rules(text.encode(),'surge')
    def test_empty_and_unknown_format(self):
        for b,fmt in [(b'# empty','surge'),(b'ad.test.com','abp')]:
            with self.assertRaises(ValueError):parse_rules(b,fmt)
    def test_dedup_parent(self):
        r={('DOMAIN-SUFFIX','ads.test.com'),('DOMAIN','x.ads.test.com'),('DOMAIN-SUFFIX','y.ads.test.com'),('DOMAIN','safe.test.com')}
        out,removed,n=optimize(r,{'never_block_suffixes':[],'exceptions':[]})
        self.assertEqual(n,2);self.assertEqual(len(out),2)
    def test_exceptions_remove_parent_without_direct_rule(self):
        p={'never_block_suffixes':['co.uk'],'exceptions':[{'domain':'pay.test.com','scope':'host','reason':'payment'}]}
        out,removed,_=optimize({('DOMAIN-SUFFIX','test.com'),('DOMAIN','ad.test.com'),('DOMAIN-SUFFIX','co.uk')},p)
        self.assertEqual(out,[('DOMAIN','ad.test.com')]);self.assertEqual(len(removed),2)
    def test_subtree_exception(self):
        p={'never_block_suffixes':[],'exceptions':[{'domain':'safe.com','scope':'subtree','reason':'critical'}]}
        self.assertTrue(exception_for(('DOMAIN','a.safe.com'),p))

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=optimize(load_inputs()[0],load_policy())[0]
        cls.apps=read_json(ROOT/'data/apps.json')
    def test_protected_services_pass(self):
        for h in ['accounts.google.com','passport.jd.com','paypal.com','api.m.jd.com','titan.pinduoduo.com','raw.githubusercontent.com','apple.com','api.pinduoduo.com']:
            with self.subTest(host=h):self.assertFalse(is_blocked(h,self.rules))
    def test_ad_domains_block(self):
        for h in ['doubleclick.net','pagead2.googlesyndication.com','optimus-ads.amap.com','ads-img-qc.xhscdn.com']:
            with self.subTest(host=h):self.assertTrue(is_blocked(h,self.rules))
    def test_all_app_positive_fixtures(self):
        for ident,app in self.apps.items():
            for r in app['rules']:
                for url in r['positive']:
                    with self.subTest(app=ident,url=url):self.assertRegex(url,r['pattern'])
    def test_same_host_login_payment_order_pass(self):
        for app in self.apps.values():
            for r in app['rules']:
                for h in r['hosts']:
                    h=h.replace('*','5')
                    for path in ['/login','/pay','/orders','/oauth/token','/api/sns/v3/note/feed','/gw/mtop.trade.order.create/1.0/']:
                        with self.subTest(host=h,path=path):self.assertIsNone(re.search(r['pattern'],'https://'+h+path))
    def test_jd_query_order_and_boundaries(self):
        p=self.apps['jd']['rules'][0]['pattern']
        for q in ['functionId=xview2Config','a=1&functionId=xview2Config&x=2']:
            self.assertRegex('https://api.m.jd.com/client.action?'+q,p)
        for q in ['functionId=xview2ConfigExtra','otherfunctionId=xview2Config','functionId=login','next=functionId=xview2Config']:
            self.assertIsNone(re.search(p,'https://api.m.jd.com/client.action?'+q))
    def test_host_and_path_suffixes_do_not_match(self):
        for app in self.apps.values():
            for r in app['rules']:
                for url in r['positive']:
                    host=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(url).hostname
                    self.assertIsNone(re.search(r['pattern'],url.replace(host,host+'.evil.test')))
    def test_marker_merge_preserves_every_other_byte(self):
        before='[General]\r\nfoo = bar\r\n[Rule]\r\nIP-CIDR,192.0.2.1/32,DIRECT\r\n'+MARKER+'\r\nGEOIP,CN,DIRECT\r\nFINAL,PROXY\r\n'
        line='RULE-SET,https://example.com/dist/rules/base.list,REJECT'
        self.assertEqual(integrate(before,'https://example.com'),before.replace(MARKER,line))
    def test_marker_required_and_in_rule(self):
        for text in ['[Rule]\nFINAL,PROXY','[General]\n'+MARKER,'[Rule]\n'+MARKER+'\n'+MARKER]:
            with self.assertRaises(ValueError):integrate(text,'https://example.com')
    def test_ci_rejects_unconfigured_or_wrong_repository(self):
        import os
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':'different-owner/different-repo'}):
            with self.assertRaisesRegex(ValueError,'repository differs'):validate()
    def test_repo_artifacts_validate(self):self.assertGreater(validate()['base_rules'],50000)
    def test_script_network_apis_rejected(self):
        for x in ['eval(x)','$httpClient.get(x)','fetch(x)','$persistentStore.write(x)']:
            with self.assertRaises(ValueError):check_script(x)
    def test_private_key_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'bad.txt').write_text('-----BEGIN RSA '+'PRIVATE KEY-----')
            with self.assertRaises(ValueError):scan_public(p)
    def test_generated_drift_is_rejected(self):
        # A temporary copy tests the actual build validator, never modifies the delivery.
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'repo';shutil.copytree(ROOT,p,ignore=shutil.ignore_patterns('.git','.cache','__pycache__'))
            (p/'dist/modules/apps/jd.sgmodule').write_text('tampered')
            with self.assertRaises(ValueError):build.run(p,check=True)

class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for d in ['sources','vendor','licenses','data','reports']:(self.root/d).mkdir()
        self.body=b'#VER=20261021000000\nDOMAIN-SUFFIX,ads.one.com\nDOMAIN-SUFFIX,ads.two.com\n'
        self.lic=b'MIT license test'
        self.s={'id':'test','repository':'example/repo','ref':'main','path':'rules.txt','snapshot':'vendor/rules.txt','format':'surge','license_path':'LICENSE','license_file':'licenses/test.txt','spdx':'MIT','min_rules':1,'max_rules':10}
        (self.root/'vendor/rules.txt').write_bytes(self.body);(self.root/'licenses/test.txt').write_bytes(self.lic)
        self.write('sources/upstreams.json',{'sources':[self.s]})
        self.write('sources/upstreams.lock.json',{'sources':{'test':{'sha256':sha256(self.body),'license_sha256':sha256(self.lic)}}})
        self.write('sources/watch.json',{'sources':[]})
        self.write('data/policy.json',{'never_block_suffixes':[],'max_source_age_days':14,'max_source_change_ratio':0.60})
        self.write('data/allowlist.json',{'entries':[]})
        self.now=dt.datetime(2026,10,21,tzinfo=dt.timezone.utc)
    def tearDown(self):self.tmp.cleanup()
    def write(self,p,data):(self.root/p).write_text(json_text(data))
    def fetcher(self,body=None,lic=None):
        return lambda url: (self.lic if lic is None else lic) if url.endswith('/LICENSE') else (self.body if body is None else body)
    def update(self,f,check=False):return upstream.update(self.root,check,f,self.now)
    def test_no_change(self):self.assertFalse(self.update(self.fetcher()))
    def test_valid_change_prepares_candidate(self):
        newer=self.body+b'DOMAIN-SUFFIX,ads.three.com\n'
        self.assertTrue(self.update(self.fetcher(newer)))
        self.assertEqual((self.root/'vendor/rules.txt').read_bytes(),newer)
        self.assertEqual(read_json(self.root/'sources/upstreams.lock.json')['sources']['test']['sha256'],sha256(newer))
    def test_check_never_modifies_inputs(self):
        self.assertTrue(self.update(self.fetcher(self.body+b'DOMAIN-SUFFIX,ads.three.com\n'),check=True))
        self.assertEqual((self.root/'vendor/rules.txt').read_bytes(),self.body)
    def test_failure_keeps_snapshot_and_lock(self):
        old=(self.root/'sources/upstreams.lock.json').read_bytes()
        for data,lic in [(b'<html>Error</html>',self.lic),(b'# empty',self.lic),(self.body,b'changed license'),(b'#VER=20200101000000\nDOMAIN,old.example.com',self.lic)]:
            with self.subTest(data=data),self.assertRaises(ValueError):self.update(self.fetcher(data,lic))
            self.assertEqual((self.root/'vendor/rules.txt').read_bytes(),self.body)
            self.assertEqual((self.root/'sources/upstreams.lock.json').read_bytes(),old)
    def test_outage_does_not_erase_baseline(self):
        def fail(url):raise OSError('offline')
        with self.assertRaises(ValueError):self.update(fail)
        self.assertEqual((self.root/'vendor/rules.txt').read_bytes(),self.body)
    def test_excessive_churn_rejected(self):
        b=b'#VER=20261021000000\nDOMAIN,new.one.com\nDOMAIN,new.two.com\n'
        with self.assertRaises(ValueError):self.update(self.fetcher(b))
    def test_one_source_failure_prevents_all_writes(self):
        second=dict(self.s,id='second',repository='example/second',snapshot='vendor/second.txt')
        self.write('sources/upstreams.json',{'sources':[self.s,second]})
        lock=read_json(self.root/'sources/upstreams.lock.json')
        lock['sources']['second']=dict(lock['sources']['test'])
        self.write('sources/upstreams.lock.json',lock)
        (self.root/'vendor/second.txt').write_bytes(self.body)
        old=(self.root/'sources/upstreams.lock.json').read_bytes()
        def mixed(url):
            if '/second/' in url:raise OSError('outage')
            return self.lic if url.endswith('/LICENSE') else self.body+b'DOMAIN-SUFFIX,ads.three.com\n'
        with self.assertRaises(ValueError):self.update(mixed)
        self.assertEqual((self.root/'vendor/rules.txt').read_bytes(),self.body)
        self.assertEqual((self.root/'sources/upstreams.lock.json').read_bytes(),old)
    def test_redirect_and_unapproved_url_rejected(self):
        for u in ['http://raw.githubusercontent.com/a/b/main/r','https://evil.test/r','https://raw.githubusercontent.com/a/b/main/r?token=x']:
            with self.assertRaises(ValueError):upstream.fetch(u)
        with self.assertRaises(ValueError):upstream.NoRedirect().redirect_request(None,None,302,'',{},'https://evil.test')
    def test_hagezi_timestamp(self):
        self.assertEqual(upstream.source_date(b'# Last modified: 20 Oct 2026 14:52 UTC\n').day,20)

if __name__=='__main__':unittest.main()
