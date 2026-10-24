'use strict';
// The Weibo filter must remove only marked ads and named modules, and pass everything else unchanged.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../scripts/weibo.js'), 'utf8');
const spec = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/weibo.json'), 'utf8'));
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/weibo.json'), 'utf8'));
const feed = 'https://api.weibo.cn/2/statuses/container_timeline?gsid=x';
const ad = { items: [{ category: 'feed', data: { mblogtypename: '广告' } }, { category: 'feed', data: { text: 'ok' } }] };

function run(url, body, options = {}) {
  const calls = { done: [], apis: 0 };
  const counted = new Proxy({}, { get() { calls.apis++; return () => {}; } });
  const sandbox = {
    $request: { url },
    $response: { status: 200, headers: { 'Content-Type': 'application/json' }, body: typeof body === 'string' ? body : JSON.stringify(body), ...options },
    $done: obj => calls.done.push(JSON.parse(JSON.stringify(obj))),
    $httpClient: counted, $notification: counted, $persistentStore: counted, console: counted,
  };
  vm.runInNewContext(code, sandbox, { timeout: 1000 });
  assert.equal(calls.done.length, 1, '$done exactly once');
  assert.equal(calls.apis, 0, 'no network, notification, storage or log calls');
  return calls.done[0];
}

for (const item of fixture) test(item.name, () => {
  const result = run(item.url, item.input);
  if (item.passThrough) assert.deepEqual(result, {});
  else assert.deepEqual(JSON.parse(result.body), item.expected);
});

test('script routes and data/weibo.json list the same paths', () => {
  const table = code.match(/var ROUTES = \{([\s\S]*?)\};/)[1];
  const routed = [...table.matchAll(/'([^']+)':/g)].map(m => m[1]).sort();
  const listed = spec.scripts.flatMap(g => g.paths).sort();
  assert.deepEqual(routed, listed);
});

test('API errors and login state pass unchanged', () => {
  for (const body of [{ errno: -100, errmsg: 'login', ...ad }, { error_code: 21327, ...ad }, { error: 'expired', ...ad }])
    assert.deepEqual(run(feed, body), {});
});

test('success markers do not count as errors', () => {
  const result = run(feed, { errno: 0, error_code: '0', ...ad });
  assert.deepEqual(JSON.parse(result.body).items, [{ category: 'feed', data: { text: 'ok' } }]);
});

test('non-JSON, HTML, oversized and failed responses pass unchanged', () => {
  assert.deepEqual(run(feed, '{bad'), {});
  assert.deepEqual(run(feed, '<html>login</html>'), {});
  assert.deepEqual(run(feed, '[1,2]'), {});
  assert.deepEqual(run(feed, ' '.repeat(3145729)), {});
  assert.deepEqual(run(feed, ad, { status: 500 }), {});
  assert.deepEqual(run(feed, ad, { status: 2000 }), {});
});

test('paths outside the route table pass unchanged', () => {
  for (const url of ['https://api.weibo.cn/2/statuses/show?id=1', 'https://api.weibo.cn/2/direct_messages/user_list?x=1',
    'https://api.weibo.cn/2/account/login', 'https://api.weibo.cn/2/profile/statuses/tab?uid=1', 'https://api.weibo.cn/2/page/button?x=1',
    'https://api.weibo.cn/2/statuses/container_timeline/extra', 'https://api.weibo.cn.evil.test/2/statuses/container_timeline',
    'http://api.weibo.cn/2/statuses/container_timeline', 'https://weibointl.api.weibo.cn/portal.php?a=trends'])
    assert.deepEqual(run(url, ad), {}, url);
});

test('the self-test marker on a routed path answers a fixed JSON, whatever Weibo returned', () => {
  // Weibo answers a request without login with HTTP 200 and errno -200.
  const loggedOut = { errmsg: '校验参数不存在', errno: -200, errtype: 'DEFAULT_ERROR', isblock: false };
  for (const [url, path] of [['https://api.weibo.cn/2/profile/me?personal_filter_selftest=1', 'profile/me'],
    ['https://api.weibo.cn/2/checkin/show?gsid=x&personal_filter_selftest=1&v=2', 'checkin/show']]) {
    const answer = JSON.parse(run(url, loggedOut).body);
    assert.equal(answer.personal_filter, 'weibo');
    assert.equal(answer.ok, true);
    assert.equal(answer.path, path);
    assert.match(answer.version, /^\d{4}-\d{2}-\d{2}(?:\.\d+)?$/);
    assert.deepEqual(JSON.parse(run(url, '<html></html>', { status: 403 }).body), answer);
  }
  for (const url of ['https://api.weibo.cn/2/profile/me?personal_filter_selftest=0', 'https://api.weibo.cn/2/profile/me?x_personal_filter_selftest=1',
    'https://api.weibo.cn/2/profile/me?personal_filter_selftest=12', 'https://api.weibo.cn/2/statuses/show?personal_filter_selftest=1',
    'https://api.weibo.cn.evil.test/2/profile/me?personal_filter_selftest=1'])
    assert.deepEqual(run(url, loggedOut), {}, url);
});

// Splash ads: 2037-12-31 00:00:00 and 23:59:59 at UTC+8.
const LATER = 2145801600, LATER_END = 2145887999;
const preload = 'https://bootpreload.uve.weibo.com/v1/ad/preload?uid=x';
const sdkad = 'https://sdkapp.uve.weibo.com/interface/sdk/sdkad.php?wm=x';
const pull = 'https://wbapp.uve.weibo.com/wbapplua/wbpullad.lua?wm=x';

test('splash preload: every ad and creative is postponed to 2037 with nothing left to show; other fields stay', () => {
  const body = { ads: [{ id: 'a', start_time: 1761235200, end_time: 1761321599, daily_display_cnt: 3, total_display_cnt: 9, display_duration: 5,
    creatives: [{ url: 'https://example.test/a.jpg', start_time: 1761235200, end_time: 1761321599 }] }, { id: 'b' }, null], last_ad_show_interval: 600 };
  assert.deepEqual(JSON.parse(run(preload, body).body), { ads: [
    { id: 'a', start_time: LATER, end_time: LATER_END, daily_display_cnt: 0, total_display_cnt: 0, display_duration: 0,
      creatives: [{ url: 'https://example.test/a.jpg', start_time: LATER, end_time: LATER_END }] },
    { id: 'b', start_time: LATER, end_time: LATER_END, daily_display_cnt: 0, total_display_cnt: 0, display_duration: 0 }, null],
    last_ad_show_interval: 600 });
});

test('splash sdkad.php: ads are postponed, the push splash is off, and the trailing OK is kept', () => {
  const body = JSON.stringify({ ads: [{ id: 'a', begintime: '2026-10-24 00:00:00', endtime: '2026-10-25 23:59:59', displaynum: 3, allowdaydisplaynum: 2 }],
    show_push_splash_ad: true, background_delay_display_time: 600 }) + 'OK';
  const out = run(sdkad, body).body;
  assert.ok(out.endsWith('}OK'));
  assert.deepEqual(JSON.parse(out.slice(0, -2)), { ads: [{ id: 'a', begintime: '2037-12-31 00:00:00', endtime: '2037-12-31 23:59:59', displaynum: 0, allowdaydisplaynum: 0 }],
    show_push_splash_ad: false, background_delay_display_time: 600 });
  assert.equal(run(sdkad, JSON.stringify({ ads: [] }) + 'OK').body, JSON.stringify({ ads: [], show_push_splash_ad: false }) + 'OK');
});

test('splash wbpullad.lua: the cached ad list is postponed', () => {
  const body = { cached_ad: { ads: [{ id: 'a', start_date: 1761235200, end_date: 1761321599, show_count: 3, duration: 5 }], version: 7 }, ok: 1 };
  assert.deepEqual(JSON.parse(run(pull, body).body),
    { cached_ad: { ads: [{ id: 'a', start_date: LATER, end_date: LATER_END, show_count: 0, duration: 0 }], version: 7 }, ok: 1 });
});

test('splash calls never pass an answer they cannot rewrite', () => {
  const loggedOut = { errmsg: 'x', errno: -200 };
  for (const url of [preload, sdkad, pull])
    for (const [body, options] of [[loggedOut], [{ ads: 'x', cached_ad: { ads: {} } }], [{}], ['<html>}</html>'], ['{bad}'], [''], ['[{"ads":[]}]'],
      [JSON.stringify({ ads: [] }) + 'OK and more'], [{ ads: [] }, { status: 500 }], [' '.repeat(3145729)]])
      assert.deepEqual(run(url, body, options), { body: '{}' }, url + ' ' + JSON.stringify(body).slice(0, 60));
});

test('splash calls answer the self-test, and other paths on those hosts are left to the module', () => {
  const answer = JSON.parse(run(sdkad + '&personal_filter_selftest=1', '').body);
  assert.equal(answer.personal_filter, 'weibo');
  assert.equal(answer.path, 'sdkapp.uve.weibo.com/interface/sdk/sdkad.php');
  for (const url of ['https://bootrealtime.uve.weibo.com/v2/ad/realtime', 'https://sdkapp.uve.weibo.com/interface/sdk/sdkconfig.php',
    'https://bootpreload.uve.weibo.com/v1/ad/preload/x', 'https://fastimage.uve.weibo.com/v1/ad/preload', 'https://wbapp.uve.weibo.com.evil.test/wbapplua/wbpullad.lua'])
    assert.deepEqual(run(url, { ads: [{ start_time: 1 }] }), {}, url);
});

test('splash table and data/weibo.json list the same calls', () => {
  const table = code.match(/var SPLASH = \{([\s\S]*?)\};/)[1];
  assert.deepEqual([...table.matchAll(/'([^']+)':/g)].map(m => m[1]).sort(), spec.splash.calls.map(c => c.host).sort());
  const bodies = { 'bootpreload.uve.weibo.com': { ads: [] }, 'sdkapp.uve.weibo.com': JSON.stringify({ ads: [] }) + 'OK', 'wbapp.uve.weibo.com': { cached_ad: { ads: [] } } };
  for (const call of spec.splash.calls)
    for (const url of call.positive) assert.notDeepEqual(run(url, bodies[call.host]), { body: '{}' }, url);
});

test('a malformed container id in the request does not trigger the following-list filter', () => {
  const body = { cards: [{ card_group: [{ user: { id: 2, following: false } }] }] };
  assert.deepEqual(run('https://api.weibo.cn/2/cardlist?containerid=231093%E0%A4%A', body), {});
});

test('unexpected shapes pass unchanged', () => {
  for (const body of [{ items: 'x' }, { items: [null, 1, 'a', []] }, { statuses: {} }, { cards: [null, { card_group: 'x' }] }, {}])
    for (const url of [feed, 'https://api.weibo.cn/2/statuses/friends/timeline', 'https://api.weibo.cn/2/page?x=1'])
      assert.deepEqual(run(url, body), {}, url + ' ' + JSON.stringify(body));
});

test('deterministic and idempotent', () => {
  for (const item of fixture.filter(x => !x.passThrough)) {
    const once = run(item.url, item.input);
    assert.deepEqual(run(item.url, item.input), once, item.name);
    assert.deepEqual(run(item.url, once.body), {}, item.name);
  }
});
