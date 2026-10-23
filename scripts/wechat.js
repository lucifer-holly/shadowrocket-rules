/* SPDX-License-Identifier: GPL-3.0-only
 * Original filter for WeChat Official Account articles on mp.weixin.qq.com. No network, persistence or logs.
 * Article page: one style element hides the ad slots, and the ad calls leave the page's table of calls that
 * WeChat 8.0.40+ hands to its own encrypted channel, so they travel as ordinary HTTPS again.
 * Ad call (/mp/getappmsgad): fields whose names contain "advertisement" are deleted.
 * Other URLs, error statuses, oversized bodies and pages or replies that do not look as expected pass unchanged.
 */
(function () {
  'use strict';
  var PAGE_MAX = 5242880;
  var AD_MAX = 1048576;
  var MARK = 'personal-wechat-ad-hide';
  // Bottom, mid-article, sponsor, keyword and comment-area ads all render in .iframe_ad_container frames;
  // the other selectors are the slots that hold them and the promotion cards authors insert (mp-common-cpsad).
  // :has() sits in a rule of its own so an engine without it still applies the first rule.
  var STYLE = '<style id="' + MARK + '">' +
    '.mpda_bottom_container,.iframe_ad_container,.comment-ad-container,mpcpc,mp-sponsor-ad,mp-common-cpsad,' +
    '#js_top_ad_area{display:none!important}.discuss_item:has(.comment-ad-container){display:none!important}</style>';
  var TABLE_KEY = 'window.__ajaxTransferConfig';
  var TABLE = /^window\.__ajaxTransferConfig\s*=\s*\{[^{}]*\};/;
  var TABLE_SHAPE = /^window\.__ajaxTransferConfig\s*=\s*\{(?:\s*'[\w\/-]+'\s*:\s*'\w+'\s*,?)*\s*\};$/;
  // Every entry of the ad scope: getappmsgad and the ad reporting calls.
  var AD_ENTRY = /\s*'mp\/[\w\/-]+'\s*:\s*'mmbizwap_cgi_appmsgad'\s*,?/g;

  function header(name) {
    var value = '';
    Object.keys($response.headers || {}).forEach(function (k) {
      if (k.toLowerCase() === name) value = String($response.headers[k]);
    });
    return value;
  }

  function page(body) {
    var type = header('content-type');
    if (type && !/text\/html/i.test(type)) return null;
    if (body.indexOf(MARK) !== -1) return null;
    var head = /<head(?:\s[^>]*)?>/i.exec(body.slice(0, 8192));
    var tableAt = body.indexOf(TABLE_KEY);
    if (!head || (tableAt === -1 && body.indexOf('id="js_article"') === -1)) return null;
    var at = head.index + head[0].length;
    var out = body.slice(0, at) + STYLE;
    var table = tableAt > at ? TABLE.exec(body.slice(tableAt, tableAt + 20000)) : null;
    if (table) {
      var edited = table[0].replace(AD_ENTRY, '');
      if (edited !== table[0] && TABLE_SHAPE.test(edited)) {
        // Slices of the original page, joined once, keep memory close to one extra copy.
        return out + body.slice(at, tableAt) + edited + body.slice(tableAt + table[0].length);
      }
    }
    return out + body.slice(at);
  }

  function adReply(body) {
    var obj;
    try { obj = JSON.parse(body); } catch (_) { return null; }
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null;
    // Errors and retry signals (base_resp.ret other than 0) stay as they are.
    if (obj.base_resp && obj.base_resp.ret !== undefined && obj.base_resp.ret !== 0) return null;
    var changed = false;
    (function strip(node, depth) {
      if (!node || typeof node !== 'object' || depth > 6) return;
      Object.keys(node).forEach(function (k) {
        if (/advertisement/i.test(k)) { delete node[k]; changed = true; }
        else strip(node[k], depth + 1);
      });
    }(obj, 0));
    return changed ? JSON.stringify(obj) : null;
  }

  function main() {
    if (typeof $request !== 'object' || typeof $response !== 'object') return {};
    var status = String($response.status || $response.statusCode || '200');
    if (!/^(?:200(?:$|\s)|HTTP\/\S+ 200(?:$|\s))/.test(status)) return {};
    var body = $response.body;
    if (typeof body !== 'string') return {};
    var url = String($request.url || '');
    var out = null;
    if (/^https:\/\/mp\.weixin\.qq\.com\/s(?:\/|\?)/.test(url)) {
      if (body.length <= PAGE_MAX) out = page(body);
    } else if (/^https:\/\/mp\.weixin\.qq\.com\/mp\/getappmsgad(?:\?|$)/.test(url)) {
      if (body.length <= AD_MAX) out = adReply(body);
    }
    return out === null ? {} : { body: out };
  }

  var result = {};
  try { result = main(); } catch (_) { result = {}; }
  $done(result);
}());
