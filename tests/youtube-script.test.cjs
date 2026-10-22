'use strict';
// The pinned third-party YouTube script must finish once and never touch network or notification APIs.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const lock = JSON.parse(fs.readFileSync(path.join(__dirname, '../sources/scripts.lock.json'), 'utf8'));
const item = lock.third_party.find(x => x.id === 'maasea-youtube-response');
const code = fs.readFileSync(path.join(__dirname, '..', item.path), 'utf8');

function run(url, bytes) {
  const calls = { done: [], http: 0, notify: 0 };
  const sandbox = {
    $request: { url, headers: { 'User-Agent': 'com.google.ios.youtube/19.0 iOS' } },
    $response: { status: 200, headers: { 'Content-Type': 'application/x-protobuf' }, body: bytes },
    $done: obj => calls.done.push(obj),
    $httpClient: new Proxy({}, { get() { calls.http++; return () => {}; } }),
    $notification: { post: () => { calls.notify++; } },
    $persistentStore: { read: () => null, write: () => true },
    console: { log() {} }, setTimeout, clearTimeout, Promise, Uint8Array, ArrayBuffer, TextDecoder, TextEncoder,
  };
  vm.createContext(sandbox);
  vm.runInContext(code, sandbox, { timeout: 2000 });
  return new Promise(resolve => setTimeout(() => resolve(calls), 300));
}

for (const route of ['player', 'browse', 'next', 'search']) {
  test(`youtube ${route}: finishes once without network or notifications`, async () => {
    const calls = await run(`https://youtubei.googleapis.com/youtubei/v1/${route}?prettyPrint=false`, new Uint8Array([0x0a, 0x00]));
    assert.equal(calls.done.length, 1);
    assert.equal(calls.http, 0);
    assert.equal(calls.notify, 0);
  });
}
