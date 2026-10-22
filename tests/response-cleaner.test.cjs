'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../scripts/response-cleaner.js'), 'utf8');
const bili = 'https://app.bilibili.com/x/v2/feed/index?idx=1';
function run(url, body, options = {}) {
  const calls = [];
  const sandbox = {
    $request: { url }, $response: { status: 200, headers: {'Content-Type': 'application/json'}, body: typeof body === 'string' ? body : JSON.stringify(body), ...options },
    $done: obj => calls.push(JSON.parse(JSON.stringify(obj)))
  };
  vm.runInNewContext(code, sandbox, {timeout: 500});
  assert.equal(calls.length, 1, '$done exactly once');
  return calls[0];
}
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/responses.json'), 'utf8'));
for (const item of fixture) test(item.name, () => {
  const result = run(item.url, item.input);
  if (item.passThrough) assert.deepEqual(result, {});
  else assert.deepEqual(JSON.parse(result.body), item.expected);
});
test('malformed JSON passes unchanged', () => assert.deepEqual(run(bili, '{bad'), {}));
test('HTML body passes unchanged', () => assert.deepEqual(run(bili, '<html>login</html>'), {}));
test('error status passes unchanged', () => assert.deepEqual(run(bili, {data:{items:[]}}, {status:403}), {}));
test('non JSON content type passes unchanged', () => assert.deepEqual(run(bili, 'text', {headers:{'content-type':'text/html'}}), {}));
test('large response passes unchanged', () => assert.deepEqual(run(bili, 'x'.repeat(1048577)), {}));
test('unapproved host passes unchanged', () => assert.deepEqual(run('https://app.bilibili.com.evil.test/x/v2/feed/index', {data:{items:[{card_goto:'ad_av'}]}}), {}));
test('login and payment paths pass unchanged', () => {
  for (const url of ['https://app.bilibili.com/login', 'https://api.zhihu.com/pay', 'https://app.bilibili.com/x/v2/feed/index/other'])
    assert.deepEqual(run(url, {data:{items:[{card_goto:'ad_av'}]}}), {});
});
test('deterministic and idempotent', () => {
  const input={code:0,data:{items:[{card_goto:'ad_av'},{card_goto:'av',title:'normal'}]}};
  const out=run(bili,input);assert.deepEqual(run(bili,input),out);assert.deepEqual(run(bili,out.body),{});
});
test('upstream auth error is preserved', () => assert.deepEqual(run(bili,{code:-101,data:{items:[{card_goto:'ad_av'}]}}),{}));

test('invalid lookalike status does not run', () => assert.deepEqual(run(bili,{data:{items:[{card_goto:'ad_av'}]}},{status:2000}),{}));

test('story feeds remove explicit vertical ad cards only', () => {
  const input={code:0,data:{items:[{card_goto:'vertical_ad_av'},{card_goto:'av',ad_info:{}},{card_goto:'live'}]}};
  const result=run('https://app.bilibili.com/x/v2/feed/index/story?x=1',input);
  assert.deepEqual(JSON.parse(result.body),{code:0,data:{items:[{card_goto:'av',ad_info:{}},{card_goto:'live'}]}});
});

test('weibo lookalike host does not run', () => {
  assert.deepEqual(run('https://api.weibo.cn.evil.test/2/statuses/friends/timeline', {statuses:[{mblogtypename:'广告'}]}), {});
});
