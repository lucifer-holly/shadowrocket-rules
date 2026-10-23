# 微信广告分析（记录）

**去广告⑥（微信公众号文章模块）已于 2026-10-23 废弃**：主人实测效果不明显。没有当时的设备日志，原因未查明。这里留下分析结果，下次再遇到微信广告时不必从头查。

依据：四篇公开公众号文章的页面和它们加载的页面代码（`res.wx.qq.com/mmbizappmsg/…`，页面里的模板版本 `fasttmpl_version` 为 8488057），公开的去广告规则（见文末来源），以及主人的真机反馈。

## 结论

| 广告位置 | 广告数据从哪来 | 网络规则能做到的 | 现状 |
|---|---|---|---|
| 公众号文章：文末、文中、赞助、评论区、关键词、视频贴片 | 文章页向 `/mp/getappmsgad` 要数据；iOS 微信 8.0.40 起这个请求交给微信自己的加密通道发送（代码里看到） | 理论上能改文章页隐藏广告位；⑥试过，效果不明显 | 不处理；①挡掉广告图片 |
| 公众号文章：商品、小游戏、短剧的推广卡片（按成交返佣） | `/mp/cps_product_info`，不经原生通道 | 能拦数据 | ②里 fmz200 的规则照旧拦 |
| 朋友圈广告 | 卡片文字和「广告」标签随朋友圈一起走微信自己的加密协议，和收发消息是同一组服务器（推测；公开规则都做不到） | 只能挡图片和视频 | ①已拦 `wxs.qq.com` 下的广告素材 |
| 小程序、小游戏里的广告 | 微信原生的广告组件（推测）；素材也来自 `wxs.qq.com` | 只能挡素材 | ①已拦；「看广告领奖励」可能领不到 |
| 视频号、直播、搜一搜、看一看 | 微信原生页面和加密通道 | 不能 | 在微信设置里关入口 |
| 支付完成页 | 支付通道 | 不碰 | 支付相关主机永不解密 |

## 公众号文章广告怎么来的（代码里看到的）

- 文章页 `https://mp.weixin.qq.com/s/…`、`/s?__biz=…` 是普通 HTTPS 网页，3.5–4.2 MB，九成是内联脚本；微信会用隐藏页面（`WeixinPrefecherJSBridge`）预加载文章。
- 页面先判断要不要广告（`checkNeedAds`），同一篇文章的广告在本机缓存一段时间；要广告时 POST `/mp/getappmsgad`，返回里的 `advertisement_num`、`advertisement_info` 就是广告，`pos_type` 依次是文末 0、文中 4、赞助 3、视频前 7 / 后 9 / 中 16、关键词 36、评论区 43、图片底部赞助 45。
- 页面里的 `window.__ajaxTransferConfig` 列出交给微信原生通道发送的请求：iOS 微信版本号不低于 0x1800282F（约 8.0.40）时，`getappmsgad` 等 9 个广告请求（作用域 `mmbizwap_cgi_appmsgad`）和留言、点赞、阅读数等请求都经 JSAPI `webTransfer` 发出，代理看不到；原生通道失败才退回普通请求。所以 fmz200 改 `getappmsgad` 的规则、以及当天一度加进③的同类处理，在新版微信上碰不到广告数据。
- 广告卡片画在 iframe（网页里嵌的另一个网页）里：普通广告来自 `https://wxa.wxs.qq.com/tmpl/…/base_tmpl.html`，推广卡片来自 `https://file.daihuo.qq.com/mp_cps_goods_card/…`。主人看到「有文字、没图片」，推测卡片页面来自微信本地缓存，只有图片被①挡住。
- 广告位所在的元素：文末 `.mpda_bottom_container`、文中 `<mpcpc>`、赞助 `<mp-sponsor-ad>`、评论区 `.comment-ad-container`、推广卡片 `<mp-common-cpsad>`、顶部 `#js_top_ad_area`，广告 iframe 都带 `.iframe_ad_container`。

## 试过的做法和结果

- 去广告⑥只解密 `mp.weixin.qq.com`：在文章页 `<head>` 后插一段样式隐藏上面这些广告位；把转发表里的 9 个广告请求删掉，让它们回到普通 HTTPS，再删 `getappmsgad` 返回的 advertisement 字段。用四篇公开文章离线测过，页面其余部分逐字节不变，每篇约 5 毫秒。
- 主人实测「效果很不明显」，当天废弃。可能的原因（都未证实）：文章页走了预加载或缓存、没经过脚本；页面超过脚本的 5 MiB 上限；主人看到的主要是朋友圈广告（⑥本来就管不到）。
- 废弃时保留了已发布的脚本 `dist/scripts/wechat.<SHA-256>.js`（`sources/scripts.lock.json` 的 `archives`），手机上没删掉的旧模块不会因为脚本 404 报错；`data/allowlist.json` 里文章页面、图片、视频、页面脚本这几个主机的放行也保留。
- 以后如果再做：先让主人抓一份打开文章时的日志（`python3 tools/devicelog.py 日志.db --app wechat --check`），确认 `mp.weixin.qq.com/s` 的完整网址是否出现，再决定改不改页面。

## 在微信里能做的

- 关个性化广告：我 → 设置 → 个人信息与权限 → 个性化广告管理（旧版本在「隐私」里面）。广告数量不会变，只是不再按兴趣推；2020–2021 年的报道说只能关半年，现在是否仍然如此未确认。
- 隐藏不用的入口：我 → 设置 → 通用 → 发现页管理，关掉视频号、直播、看一看、搜一搜、游戏等。
- 单条朋友圈广告：点卡片右上角的「广告」，选「不感兴趣」，不同版本的选项名可能不同。

## 来源

- [fmz200/wool_scripts blockAds.plugin](https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin)：「公众号文章下方广告」改 `getappmsgad` 的 advertisement 字段；「公众号去除商品推广」拦 `cps_product_info`。
- [oo226/egern-config#143](https://github.com/oo226/egern-config/pull/143)：日志里不见 `getappmsgad` 而广告仍在；认为整个拦 `wxs.qq.com` 可能误伤公众号图片和视频。
- [garywah 转存的 ddgksf2013 微信模块](https://raw.githubusercontent.com/garywah/Shadowrocket/main/module/WeChat.module)、[V2EX：iOS 如何屏蔽掉微信公众号里面的广告？](https://www.v2ex.com/t/724484)
- 设置路径：[钛媒体](https://www.tmtpost.com/6043256.html)、[观察者网](https://www.guancha.cn/economy/2021_11_12_614569.shtml)、[IT之家](https://www.ithome.com/0/525/104.htm)与[澎湃新闻](https://www.thepaper.cn/newsDetail_forward_11713655)（只能关半年）、[IT之家：发现页管理](https://www.ithome.com/0/557/557.htm)
- 其余结论来自对微信公开页面代码的阅读，只记录了接口名、字段名和元素名，没有复制代码。
