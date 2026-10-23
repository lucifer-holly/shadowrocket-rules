'use strict';
// The WeChat article filter may only add its style element and drop ad entries from the transfer table;
// the ad call loses advertisement fields only. Everything else must pass unchanged.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../scripts/wechat.js'), 'utf8');
const spec = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/wechat.json'), 'utf8'));
const article = 'https://mp.weixin.qq.com/s/r6pfSU-88e86cUjxp3yFnQ';
const adCall = 'https://mp.weixin.qq.com/mp/getappmsgad?f=json&mockid=&rtx=';
const html = { 'Content-Type': 'text/html; charset=UTF-8' };

// Synthetic page with the structure of a 2026-10 article: head first, the table alone in its own script, then the body.
const TABLE = "window.__ajaxTransferConfig = {  'mp/advertisement_report': 'mmbizwap_cgi_appmsgad',  'mp/getappmsgad': 'mmbizwap_cgi_appmsgad',  'mp/ad': 'mmbizwap_cgi_appmsgad',  'mp/appmsg_comment': 'mmbizwap_cgi_appmsgext',  'mp/getappmsgext': 'mmbizwap_cgi_appmsgext',  'mp/relatedarticle': 'mmbizwap_cgi_misc',  'mp/masonryfeed': 'mmbizwap_cgi_misc'};";
const KEPT = "window.__ajaxTransferConfig = {  'mp/appmsg_comment': 'mmbizwap_cgi_appmsgext',  'mp/getappmsgext': 'mmbizwap_cgi_appmsgext',  'mp/relatedarticle': 'mmbizwap_cgi_misc',  'mp/masonryfeed': 'mmbizwap_cgi_misc'};";
function page(table = TABLE, extra = '') {
  return '<!DOCTYPE html>\n<html class="\n">\n  <head>\n    <meta charset="utf-8">\n<script nonce="1">var a = 1;</script>\n' +
    '<script type="text/javascript" nonce="1" reportloaderror>\n' + table + '\n</script>\n</head>\n<body>' +
    '<div id="js_article" class="rich_media"><div id="js_top_ad_area" class="top_banner"></div>' +
    '<div id="js_content">正文 <mpcpc></mpcpc> 段落</div></div>' + extra + '</body></html>';
}

function run(url, body, options = {}) {
  const calls = { done: [], apis: 0 };
  const counted = new Proxy({}, { get() { calls.apis++; return () => {}; } });
  const sandbox = {
    $request: { url },
    $response: { status: 200, headers: html, body: typeof body === 'string' ? body : JSON.stringify(body), ...options },
    $done: obj => calls.done.push(JSON.parse(JSON.stringify(obj))),
    $httpClient: counted, $notification: counted, $persistentStore: counted, console: counted,
  };
  vm.runInNewContext(code, sandbox, { timeout: 1000 });
  assert.equal(calls.done.length, 1, '$done exactly once');
  assert.equal(calls.apis, 0, 'no network, notification, storage or log calls');
  return calls.done[0];
}

const STYLE_RE = /<style id="personal-wechat-ad-hide">[^<]*<\/style>/;

test('article page: style right after <head>, ad entries out of the table, nothing else touched', () => {
  const input = page();
  const out = run(article, input).body;
  assert.ok(out.startsWith('<!DOCTYPE html>\n<html class="\n">\n  <head><style id="personal-wechat-ad-hide">'));
  for (const s of ['.mpda_bottom_container', '.iframe_ad_container', '.comment-ad-container', 'mpcpc', 'mp-sponsor-ad', 'mp-common-cpsad', '#js_top_ad_area'])
    assert.ok(out.match(STYLE_RE)[0].includes(s), s);
  assert.ok(out.includes(KEPT));
  assert.equal(out.replace(STYLE_RE, '').replace(KEPT, TABLE), input);
});

test('both article address forms are handled, and the result is stable', () => {
  for (const r of spec.scripts.find(x => x.id === 'article').positive) {
    const out = run(r, page()).body;
    assert.ok(STYLE_RE.test(out), r);
    assert.deepEqual(run(r, out), {}, 'second pass changes nothing');
  }
});

test('a table in an unexpected shape stays as it is; the style is still added', () => {
  const odd = "window.__ajaxTransferConfig = {  'mp/getappmsgad': 'mmbizwap_cgi_appmsgad',  'mp/x': {nested: 1}};";
  const out = run(article, page(odd)).body;
  assert.ok(STYLE_RE.test(out));
  assert.ok(out.includes(odd));
  const unusual = "window.__ajaxTransferConfig = {  'mp/getappmsgad': 'mmbizwap_cgi_appmsgad',  'mp/x': 'a' + 'b'};";
  assert.ok(run(article, page(unusual)).body.includes(unusual));
});

test('a page without the table still gets the style when it is an article', () => {
  const out = run(article, page('var other = 1;')).body;
  assert.ok(STYLE_RE.test(out));
  assert.ok(out.includes('var other = 1;'));
});

test('pages that are not articles, or not HTML, pass unchanged', () => {
  const errorPage = '<!DOCTYPE html><html><head><title>未知错误</title></head><body><p>未知错误，请稍后再试</p></body></html>';
  assert.deepEqual(run(article, errorPage), {});
  assert.deepEqual(run(article, page(), { headers: { 'content-type': 'application/json' } }), {});
  assert.deepEqual(run(article + '?action=preload', { base_resp: { ret: 0 }, advertisement_num: 1 }, { headers: { 'Content-Type': 'application/json' } }), {});
  assert.deepEqual(run(article, 'x'.repeat(9000) + page()), {}, 'head beyond the first 8 KB');
  assert.deepEqual(run(article, page() + 'x'.repeat(5242881)), {}, 'larger than 5 MiB');
  assert.deepEqual(run(article, page(), { status: 302 }), {});
  assert.deepEqual(run(article, page(), { status: 2000 }), {});
});

test('the ad call loses advertisement fields only, at any depth', () => {
  const input = { base_resp: { ret: 0 }, advertisement_num: 2, advertisement_info: [{ pos_type: 0, hint_txt: '广告' }],
    appmsgstat: { read_num: 10, like_num: 2 }, comment_enabled: 1, extra: { advertisement_card: { a: 1 }, keep: 1 } };
  const out = JSON.parse(run(adCall, input).body);
  assert.deepEqual(out, { base_resp: { ret: 0 }, appmsgstat: { read_num: 10, like_num: 2 }, comment_enabled: 1, extra: { keep: 1 } });
  assert.deepEqual(run(adCall, JSON.stringify(out)), {}, 'nothing left to remove');
});

test('the ad call is cleaned whatever its content type, but errors and odd bodies pass', () => {
  assert.deepEqual(JSON.parse(run(adCall, { advertisement_num: 1, ok: 1 }, { headers: html }).body), { ok: 1 });
  assert.deepEqual(run(adCall, { base_resp: { ret: 1004 }, advertisement_num: 1 }), {});
  assert.deepEqual(run(adCall, '{bad'), {});
  assert.deepEqual(run(adCall, '[{"advertisement_num":1}]'), {});
  assert.deepEqual(run(adCall, { advertisement_num: 1 }, { status: 500 }), {});
  assert.deepEqual(run(adCall, JSON.stringify({ advertisement_num: 1, pad: 'x'.repeat(1048576) })), {});
});

test('other WeChat calls and lookalike hosts pass unchanged', () => {
  const others = [...spec.negative, 'https://mp.weixin.qq.com/s', 'https://mp.weixin.qq.com/sx?__biz=1',
    'https://mp.weixin.qq.com.evil.test/s/abc', 'http://mp.weixin.qq.com/s/abc', 'https://mp.weixin.qq.com/mp/getappmsgadx?f=json'];
  for (const url of others) {
    assert.deepEqual(run(url, page()), {}, url);
    assert.deepEqual(run(url, { advertisement_num: 1 }), {}, url);
  }
});

test('the routes in data/wechat.json are the ones the script acts on', () => {
  for (const r of spec.scripts) {
    const sample = r.id === 'article' ? page() : { advertisement_num: 1 };
    for (const url of r.positive) assert.ok(run(url, sample).body, url);
    assert.ok(new RegExp(r.pattern).test(r.positive[0]));
  }
});
