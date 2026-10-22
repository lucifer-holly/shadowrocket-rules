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
