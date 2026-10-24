/* SPDX-License-Identifier: GPL-3.0-only
 * Original JSON response filter for the Weibo iOS app (api.weibo.cn). No network, persistence or logs.
 * Removes what the API itself marks as an ad or promotion, plus a few named recommendation modules.
 * Hot-search rows stay unless marked as promoted; groups holding a profile header are never removed.
 * Unknown paths, API errors, non-JSON bodies and unexpected shapes pass unchanged.
 * Self-test: a routed path opened with ?personal_filter_selftest=1 (e.g. in Safari) answers a fixed JSON naming VERSION.
 */
(function () {
  'use strict';
  var MAX_BODY = 3145728;
  var VERSION = '2026-10-24';
  var SELF_TEST = /[?&]personal_filter_selftest=1(?:[&#]|$)/;

  function isObj(x) { return !!x && typeof x === 'object' && !Array.isArray(x); }
  function str(x) { return typeof x === 'string' ? x : ''; }
  function each(list, fn) { if (Array.isArray(list)) list.forEach(fn); }

  // Removes matching entries from holder[key]; true when something was removed.
  function prune(holder, key, test) {
    var list = holder[key];
    if (!Array.isArray(list)) return false;
    var kept = list.filter(function (x) { return !test(x); });
    if (kept.length === list.length) return false;
    holder[key] = kept;
    return true;
  }

  function dropKeys(holder, keys) {
    var changed = false;
    if (!isObj(holder)) return false;
    keys.forEach(function (k) {
      if (holder[k] !== undefined) { delete holder[k]; changed = true; }
    });
    return changed;
  }

  // A post (mblog) that the API labels as paid content.
  function isAdPost(p) {
    if (!isObj(p)) return false;
    var label = str(p.mblogtypename);
    if (label.indexOf('广告') > -1 || label.indexOf('热推') > -1) return true;
    if (isObj(p.promotion) && p.promotion.type === 'ad') return true;
    if (isObj(p.content_auth_info) && str(p.content_auth_info.content_auth_title).indexOf('广告') > -1) return true;
    if (isObj(p.ads_material_info) && p.ads_material_info.is_ads) return true;
    if (p.is_ad === 1 || p.ad_state === 1) return true;
    return isObj(p.page_info) && isObj(p.page_info.actionlog) && p.page_info.actionlog.source === 'ad';
  }

  // Card entries: promoted hot-search rows, wide banner ads (118 image, 247 video), ad posts inside cards.
  function isAdCard(c) {
    if (!isObj(c)) return false;
    if (c.card_type === 118 || c.card_type === 247 || c.promotion) return true;
    if (/ads_word|is_ad_pos/.test(str(c.itemid))) return true;
    if (isObj(c.actionlog) && str(c.actionlog.ext).indexOf('ads_word') > -1) return true;
    return isAdPost(c.mblog);
  }

  // Brand and shop strips attached to otherwise normal posts.
  function stripPost(p) {
    if (!isObj(p)) return false;
    var changed = dropKeys(p, ['common_struct', 'semantic_brand_params']);
    return dropKeys(p.extend_info, ['shopwindow_cards', 'ad_semantic_brand']) || changed;
  }

  function postOf(item) {
    if (!isObj(item)) return null;
    return isObj(item.data) ? item.data : (isObj(item.status) ? item.status : null);
  }

  function isPost(p) {
    return isObj(p) && (p.mblogid !== undefined || p.idstr !== undefined || (isObj(p.user) && p.text !== undefined));
  }

  // The visible name of a module or entry, whichever field this app version uses.
  function label(x) {
    if (!isObj(x)) return '';
    var parts = [];
    [x.title, x.name, x.desc, x.card_type_name, isObj(x.header) ? x.header.title : null].forEach(function (t) {
      if (typeof t === 'string') parts.push(t);
      else if (isObj(t)) parts.push(str(t.content), str(t.text));
    });
    return parts.join(' ');
  }

  var REC_PHRASES = /推荐优质博主|可能感兴趣|感兴趣的人|推荐关注|为你推荐/;

  // Recommendation modules inserted into feeds and profile pages; posts and profile headers are never matched,
  // and a group holding posts is matched only by its trend name, never by wording.
  function isRecommendModule(item) {
    if (!isObj(item) || item.category === 'feed' || isPost(postOf(item))) return false;
    var json = JSON.stringify(item);
    if (json.indexOf('profile_top') > -1) return false;
    if (/^(?:super_topic_recommend_card|recommend_video_card)$/.test(str(item.trend_name))) return true;
    var holdsPosts = Array.isArray(item.items) && item.items.some(function (x) { return isPost(postOf(x)); });
    return !holdsPosts && REC_PHRASES.test(json);
  }

  // Older timelines: { statuses: [post], ad: [], advertises: [], trends: ... }.
  function timeline(o) {
    var changed = false;
    ['ad', 'advertises'].forEach(function (k) {
      if (Array.isArray(o[k]) && o[k].length) { o[k] = []; changed = true; }
    });
    if (dropKeys(o, ['trends'])) changed = true;
    if (prune(o, 'statuses', isAdPost)) changed = true;
    each(o.statuses, function (s) { if (stripPost(s)) changed = true; });
    return changed;
  }

  // Container feeds (home, recommended, profile pages): { items: [{ category, data }] }.
  function feed(o) {
    var changed = prune(o, 'items', function (item) {
      return isAdPost(postOf(item)) || isRecommendModule(item);
    });
    each(o.items, function (item) { if (stripPost(postOf(item))) changed = true; });
    return changed;
  }

  var ME_HIDDEN = /^(?:mine_attent_title|100505_-_meattent_pic|100505_-_meattent_-_\d+|100505_-_newusertask|100505_-_vipkaitong|100505_-_hongbao2022|100505_-_adphoto|100505_-_advideo|100505_-_hongrenjie2022|100505_-_weibonight2023)$/;
  // Names on the 我 page the owner does not use; entries such as 相册, 赞/收藏, 浏览记录, 草稿箱 and 设置 stay.
  var ME_JUNK = /钱包|任务|伴聊|AI|活动|红包|会员|商城|小店|购物|微博购|游戏|直播|短剧|装扮|卡券|免流|抽奖|福利|充值|推广|广告|订单|日历|主队|友趣|双十一|双11/;
  var ME_JUNK_IDS = /^100505_-_(?:pay|ordercenter|promote)$/;

  function isJunkEntry(x) {
    return isObj(x) && (ME_JUNK_IDS.test(str(x.itemId)) || ME_JUNK.test(label(x)));
  }

  // The 我 page: wallet, tasks, AI chat, events, red packets and membership upsell, by module or by entry.
  function mePage(o) {
    var changed = dropKeys(o, ['vipHeaderBgImage']);
    var emptied = [];
    each(o.items, function (item) {
      if (!isObj(item)) return;
      if (item.itemId === 'profileme_mine') {
        if (isObj(item.header)) {
          ['vipView', 'vipCenter'].forEach(function (k) {
            if (item.header[k]) { item.header[k] = null; changed = true; }
          });
        }
        // The 关注 count opens the people you follow instead of recommendations.
        each(item.items, function (d) {
          var m = isObj(d) && d.itemId === 'mainnums_friends' && isObj(d.click) && Array.isArray(d.click.modules) ? d.click.modules[0] : null;
          if (isObj(m) && str(m.scheme).indexOf('231093_-_selfrecomm') > -1) {
            m.scheme = m.scheme.replace('231093_-_selfrecomm', '231093_-_selffollowed');
            changed = true;
          }
        });
        return;
      }
      ['items', 'images'].forEach(function (key) {
        if (Array.isArray(item[key]) && item[key].length && prune(item, key, isJunkEntry)) {
          changed = true;
          if (!item[key].length) emptied.push(item);
        }
      });
    });
    return prune(o, 'items', function (item) {
      if (!isObj(item) || item.itemId === 'profileme_mine') return false;
      var id = str(item.itemId);
      if (emptied.indexOf(item) > -1 || ME_HIDDEN.test(id) || ME_JUNK.test(label(item))) return true;
      return id === '100505_-_newcreator' && item.type !== 'grid'; // creator-centre carousel
    }) || changed;
  }

  // Below a post: related recommendations, product placement, follow banners.
  function postExtend(o) {
    var changed = dropKeys(o, ['trend', 'head_cards', 'top_cards', 'semantic_brand_params', 'ad_tag_nature']);
    ['follow_data', 'page_alerts'].forEach(function (k) {
      if (o[k]) { o[k] = null; changed = true; }
    });
    return dropKeys(o.extend_info, ['shopwindow_cards', 'ad_semantic_brand']) || changed;
  }

  var AD_TYPES = /^(?:广告|廣告|推荐|推薦|热推|荐读|相关内容|相关评论)$/;
  var PROMO_ACCOUNTS = /^(?:超话社区|微博开新年|微博热搜|微博视频)$/;

  function isAdComment(x) {
    if (!isObj(x)) return false;
    if (x.type === 'trend' || x.commentAdType || AD_TYPES.test(str(x.adType))) return true;
    var d = x.data;
    return isObj(d) && (AD_TYPES.test(str(d.adType)) || isAdPost(d));
  }

  function commentItems(o) { return prune(o, 'items', isAdComment); }

  // Post detail page: keeps the post itself and the comments, drops inserted recommendations and banners.
  function postDetail(o) {
    var changed = false;
    var header = isObj(o.pageHeader) && isObj(o.pageHeader.data) ? o.pageHeader.data : null;
    var hasPost = header && Array.isArray(header.items) && header.items.some(function (x) { return isObj(x) && x.category === 'detail'; });
    if (hasPost && prune(header, 'items', function (x) {
      if (!isObj(x) || x.category === 'detail') return false;
      // Cards such as lotteries or polls stay unless marked as ads.
      return x.category === 'group' || x.type === 'share' || isAdCard(x.data) || isAdPost(x.data);
    })) changed = true;
    if (isObj(o.detailInfo) && dropKeys(o.detailInfo.extend, ['follow_data'])) changed = true;
    return commentItems(o) || changed;
  }

  // Comment lists: { datas: [{ type, adType, data }] }.
  function comments(o) {
    return prune(o, 'datas', function (x) {
      if (!isObj(x)) return false;
      if (x.type === 6 || AD_TYPES.test(str(x.adType))) return true; // 6: the 「为你推荐更多精彩内容」 divider
      var d = x.data;
      return isObj(d) && (isAdPost(d) || (isObj(d.user) && PROMO_ACCOUNTS.test(str(d.user.name))));
    });
  }

  function reposts(o) {
    var changed = prune(o, 'reposts', isAdPost);
    return prune(o, 'hot_reposts', isAdPost) || changed;
  }

  function forwards(o) {
    return prune(o, 'items', function (x) { return isObj(x) && (x.type === 'trend' || isAdPost(x.data)); });
  }

  function isRecUser(c) { return isObj(c) && isObj(c.user) && c.user.following === false; }
  function isRecHeading(c) { return isObj(c) && !isObj(c.user) && REC_PHRASES.test(label(c)); }

  // A whole section such as 「根据你的兴趣推荐优质博主」 goes only when nobody in it is followed.
  function isRecSection(c) {
    return isObj(c) && Array.isArray(c.card_group) && REC_PHRASES.test(label(c)) &&
      !c.card_group.some(function (x) { return isObj(x) && isObj(x.user) && x.user.following === true; });
  }

  // Your own following list: anyone you do not follow, and the headings above them, are recommendations.
  function followingList(o) {
    var changed = false;
    var emptied = [];
    each(o.cards, function (c) {
      if (!isObj(c) || !Array.isArray(c.card_group) || !c.card_group.length) return;
      if (prune(c, 'card_group', function (x) { return isRecUser(x) || isRecHeading(x); })) {
        changed = true;
        if (!c.card_group.length) emptied.push(c);
      }
    });
    return prune(o, 'cards', function (c) {
      return emptied.indexOf(c) > -1 || isRecUser(c) || isRecSection(c) || (isRecHeading(c) && !Array.isArray(c.card_group));
    }) || changed;
  }

  function containerId(o, url) {
    var id = isObj(o.cardlistInfo) ? str(o.cardlistInfo.containerid) : '';
    var m = id ? null : /[?&]containerid=([^&#]*)/.exec(url);
    try { return m ? decodeURIComponent(m[1]) : id; } catch (_) { return id; }
  }

  // Card lists (hot search, topic pages, following list): { cards: [{ card_group: [...] }] }.
  function cards(o, url) {
    var changed = prune(o, 'cards', isAdCard);
    each(o.cards, function (c) { if (isObj(c) && prune(c, 'card_group', isAdCard)) changed = true; });
    if (/^231093/.test(containerId(o, url)) && followingList(o)) changed = true;
    return (Array.isArray(o.items) && discover(o)) || changed;
  }

  // Discover, hot-search and search-result lists: { items: [{ category, data, items }] }.
  function discover(holder) {
    var changed = prune(holder, 'items', function (x) {
      if (!isObj(x)) return false;
      var d = x.data;
      if (isAdPost(d)) return true;
      if (x.category === 'feed') return false;
      // Cards: promoted rows, banner ads and the discover-page carousels.
      return isAdCard(d) || (isObj(d) && /^(?:finder_window|discover_gallery)$/.test(str(d.itemid)));
    });
    each(holder.items, function (x) {
      if (!isObj(x)) return;
      if (Array.isArray(x.items) && discover(x)) changed = true;
      var d = x.data;
      if (!isObj(d)) return;
      if (prune(d, 'group', isAdCard)) changed = true; // hot-search module (card_type 17)
      each(d.channel_list, function (c) { if (isObj(c) && prune(c, 'group', isAdCard)) changed = true; }); // newer module (235)
      if (stripPost(d)) changed = true;
    });
    return changed;
  }

  // The rotating 「大家正在搜」 words in the search box, then the list itself.
  function searchPayload(p) {
    var changed = isObj(p.loadedInfo) && dropKeys(p.loadedInfo, ['searchBarContent']);
    return discover(p) || changed;
  }

  function finder(o) {
    var changed = false;
    each(isObj(o.channelInfo) ? o.channelInfo.channels : null, function (c) {
      if (isObj(c) && isObj(c.payload) && searchPayload(c.payload)) changed = true;
    });
    if (isObj(o.header) && isObj(o.header.data) && discover(o.header.data)) changed = true;
    return changed;
  }

  function videoStream(o) {
    var changed = prune(o, 'statuses', isAdPost);
    each(o.statuses, function (s) {
      if (isObj(s) && dropKeys(s.video_info, ['shopping', 'float_info', 'forward_redpacket_info'])) changed = true;
    });
    return changed;
  }

  // The fake red dot on the video tab.
  function videoRemind(o) {
    if (!o.exist_remind && !o.image) return false;
    o.exist_remind = false;
    o.bubble_dismiss_time = 0;
    o.image_dismiss_time = 0;
    ['image', 'tag_image_english', 'tag_image_english_dark', 'tag_image_normal', 'tag_image_normal_dark'].forEach(function (k) {
      if (o[k] !== undefined) o[k] = '';
    });
    return true;
  }

  function messages(o) {
    return prune(o, 'messages', function (m) { return isObj(m) && isObj(m.msg_card) && !!m.msg_card.ad_tag; });
  }

  function checkin(o) {
    if (!o.show) return false;
    o.show = 0;
    return true;
  }

  // Exact paths under https://api.weibo.cn/2/; data/weibo.json routes the same paths to this script.
  var ROUTES = {
    'statuses/friends/timeline': timeline, 'statuses/friends_timeline': timeline,
    'statuses/unread_friends_timeline': timeline, 'statuses/unread_hot_timeline': timeline,
    'groups/timeline': timeline,
    'statuses/container_timeline': feed, 'statuses/container_timeline_unread': feed,
    'statuses/container_timeline_hot': feed, 'statuses/container_timeline_topicpage': feed,
    'profile/container_timeline': feed,
    'profile/me': mePage,
    'statuses/extend': postExtend,
    'statuses/container_detail': postDetail,
    'statuses/container_detail_comment': commentItems, 'statuses/container_detail_mix': commentItems,
    'comments/build_comments': comments, 'comments/mix_comments': comments,
    'statuses/repost_timeline': reposts, 'statuses/container_detail_forward': forwards,
    'page': cards, 'cardlist': cards, 'video/community_tab': cards,
    'flowpage': discover, 'searchall': discover,
    'search/finder': finder, 'search/container_timeline': searchPayload, 'search/container_discover': searchPayload,
    'video/tiny_stream_video_list': videoStream, 'video/tiny_stream_mid_detail': videoStream,
    'video/full_screen_stream': videoStream, 'statuses/video_mixtimeline': videoStream,
    'video/remind_info': videoRemind,
    'messageflow': messages,
    'checkin/show': checkin
  };

  function main() {
    if (typeof $request !== 'object' || typeof $response !== 'object') return {};
    var url = String($request.url || '');
    var m = /^https:\/\/api\.weibo\.cn\/2\/([^?#]+)(?:[?#]|$)/.exec(url);
    var handler = m && Object.prototype.hasOwnProperty.call(ROUTES, m[1]) ? ROUTES[m[1]] : null;
    if (!handler) return {};
    // The app never sends this marker; whatever Weibo answered, the owner sees that this version runs on the phone.
    if (SELF_TEST.test(url)) return { body: JSON.stringify({ personal_filter: 'weibo', ok: true, version: VERSION, path: m[1] }) };
    var status = String($response.status || $response.statusCode || '200');
    if (!/^(?:200(?:$|\s)|HTTP\/\S+ 200(?:$|\s))/.test(status)) return {};
    var body = $response.body;
    if (typeof body !== 'string' || body.length > MAX_BODY) return {};
    var obj;
    try { obj = JSON.parse(body); } catch (_) { return {}; }
    if (!isObj(obj)) return {};
    // Preserve API errors and login state.
    if ([obj.errno, obj.error_code].some(function (v) { return v !== undefined && v !== 0 && v !== '0'; }) || typeof obj.error === 'string') return {};
    return handler(obj, url) ? { body: JSON.stringify(obj) } : {};
  }

  var result = {};
  try { result = main(); } catch (_) { result = {}; }
  $done(result);
}());
