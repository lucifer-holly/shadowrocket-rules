/* SPDX-License-Identifier: GPL-3.0-only
 * Original, narrowly scoped JSON response filter (Bilibili, Zhihu, Weibo feeds). No network, persistence or logs.
 * Unknown routes, malformed/large bodies and non-success responses pass unchanged.
 */
(function () {
  'use strict';
  function main() {
    if (typeof $request !== 'object' || typeof $response !== 'object') return {};
    var status = String($response.status || $response.statusCode || '200');
    if (!/^(?:200(?:$|\s)|HTTP\/\S+ 200(?:$|\s))/.test(status)) return {};
    var body = $response.body;
    if (typeof body !== 'string' || body.length > 1048576) return {};
    var contentType = '';
    Object.keys($response.headers || {}).forEach(function (k) {
      if (k.toLowerCase() === 'content-type') contentType = String($response.headers[k]);
    });
    if (contentType && !/json/i.test(contentType)) return {};
    var url = String($request.url || '');
    var bili = /^https:\/\/app\.bilibili\.com\/x\/v2\/feed\/index(?:\/story)?(?:\?|$)/.test(url);
    var splash = /^https:\/\/app\.bilibili\.com\/x\/v2\/splash\/(?:list|show|event\/list2)(?:\?|$)/.test(url);
    var zhihu = /^https:\/\/api\.zhihu\.com\/topstory\/recommend(?:\?|$)/.test(url);
    var weibo = /^https:\/\/api\.weibo\.cn\/2\/(?:statuses\/(?:friends\/timeline|unread_friends_timeline|unread_hot_timeline|container_timeline(?:_unread)?)|groups\/timeline)(?:\?|$)/.test(url);
    if (!bili && !splash && !zhihu && !weibo) return {};
    var obj;
    try { obj = JSON.parse(body); } catch (_) { return {}; }
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return {};
    // Preserve application errors, authentication state and unknown schemas.
    if (!weibo && obj.code !== undefined && obj.code !== 0) return {};
    if (weibo && (obj.error_code !== undefined || obj.errno !== undefined)) return {};
    var changed = false;
    function filter(list, isAd) {
      var clean = list.filter(function (item) { return !isAd(item); });
      if (clean.length !== list.length) changed = true;
      return clean;
    }
    if (bili && obj.data && Array.isArray(obj.data.items)) {
      obj.data.items = filter(obj.data.items, function (item) {
        if (!item || typeof item !== 'object') return false;
        return /^(?:ad_av|ad_web_s|ad_player|vertical_ad_av|vertical_ad_live|vertical_ad_picture)$/.test(item.card_goto || '') ||
          (item.ad_info && typeof item.ad_info === 'object' && !Array.isArray(item.ad_info) && Object.keys(item.ad_info).length > 0);
      });
    }
    if (splash && obj.data && typeof obj.data === 'object') {
      ['show', 'event_list'].forEach(function (key) {
        if (Array.isArray(obj.data[key]) && obj.data[key].length) {
          obj.data[key] = []; changed = true;
        }
      });
    }
    if (zhihu && Array.isArray(obj.data)) {
      obj.data = filter(obj.data, function (item) {
        return item && typeof item === 'object' &&
          (item.type === 'ad' || (item.target && item.target.type === 'ad'));
      });
    }
    if (weibo) {
      // Paid posts are labelled 广告/热推 or carry promotion.type "ad"; ordinary and hot posts stay.
      var weiboAd = function (post) {
        return !!post && typeof post === 'object' &&
          (post.mblogtypename === '广告' || post.mblogtypename === '热推' ||
           (!!post.promotion && typeof post.promotion === 'object' && post.promotion.type === 'ad'));
      };
      if (Array.isArray(obj.statuses)) obj.statuses = filter(obj.statuses, weiboAd);
      if (Array.isArray(obj.items)) {
        obj.items = filter(obj.items, function (item) {
          return !!item && typeof item === 'object' && (weiboAd(item.data) ||
            (item.category === 'group' && item.trend_name === 'recommend_video_card'));
        });
      }
      ['ad', 'advertises'].forEach(function (key) {
        if (Array.isArray(obj[key]) && obj[key].length) {
          obj[key] = []; changed = true;
        }
      });
    }
    return changed ? { body: JSON.stringify(obj) } : {};
  }
  var result = {};
  try { result = main(); } catch (_) { result = {}; }
  $done(result);
}());
