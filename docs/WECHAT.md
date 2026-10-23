# 微信广告分析与去广告⑥

分析日期 2026-10-23。依据：四篇公开公众号文章的页面和它们加载的页面代码（`res.wx.qq.com/mmbizappmsg/…`，页面里的模板版本 `fasttmpl_version` 为 8488057），公开的去广告规则（见文末来源），以及主人的真机反馈（朋友圈和公众号广告都只剩文字和占位）。下文分清「代码里看到的」和「推测的」。还没有主人用微信时的设备日志。

缩写：HTML（HyperText Markup Language，网页标记语言）、CSS（Cascading Style Sheets，网页样式表）、JS（JavaScript，网页脚本）、JSON（JavaScript Object Notation，一种数据格式）、XHR（XMLHttpRequest，网页脚本发出的普通网络请求）、JSAPI（网页调用微信原生功能的接口）、iframe（inline frame，网页里嵌的另一个网页）、CPS（Cost Per Sale，按成交返佣的推广）。

## 结论

| 广告位置 | 广告数据从哪来 | 网络规则能做到的 | 本仓库的做法 |
|---|---|---|---|
| 公众号文章：文末、文中、赞助、评论区、关键词、视频贴片 | 文章页向 `/mp/getappmsgad` 要数据；iOS 微信 8.0.40 起这个请求交给微信自己的加密通道发送（代码里看到） | 修改文章页面 | ⑥：隐藏所有广告位；把广告请求改回普通 HTTPS，再删掉广告字段 |
| 公众号文章：商品、小游戏、短剧的推广卡片（CPS） | `/mp/cps_product_info`；卡片画在 `file.daihuo.qq.com` 的 iframe 里 | 拦数据、隐藏卡片 | ⑥：回空 JSON，并隐藏卡片 |
| 朋友圈广告 | 卡片文字和「广告」标签随朋友圈一起走微信自己的加密协议，和收发消息是同一组服务器（推测；公开规则都做不到） | 只能挡图片和视频 | ①已拦 `wxs.qq.com` 下的广告素材；卡片只能在微信里点「广告」→ 不感兴趣 |
| 小程序、小游戏里的广告 | 微信原生的广告组件（推测）；素材同样来自 `wxs.qq.com` | 只能挡素材 | ①已拦；「看广告领奖励」这类功能会领不到 |
| 视频号、直播、搜一搜、看一看 | 微信原生页面和加密通道 | 不能 | 在微信设置里关掉入口（见下文） |
| 支付完成页 | 支付通道 | 不碰 | 支付相关主机永不解密（`data/policy.json`） |

## 公众号文章广告怎么来的（代码里看到的）

1. 文章页 `https://mp.weixin.qq.com/s/…` 和 `/s?__biz=…` 是普通 HTTPS 网页，3.5–4.2 MB，九成是内联脚本。微信用一个隐藏页面（`WeixinPrefecherJSBridge`）预加载文章，预加载走的也是普通 HTTPS。
2. 页面先判断要不要广告（`checkNeedAds`）：同一篇文章的广告在本机缓存一段时间，缓存还有效就不再请求；付费文章不拉广告。
3. 要广告时 POST `/mp/getappmsgad?f=json…`。返回里的 `advertisement_num`、`advertisement_info` 就是广告，每条带 `pos_type`：文末 0、文中 4、赞助 3、视频前 7 / 后 9 / 中 16、关键词 36、评论区 43、图片底部赞助 45。
4. **转发表**：页面里有一行 `window.__ajaxTransferConfig = {…}`，列出交给微信原生通道发送的请求。iOS 微信版本号不低于 0x1800282F（约 8.0.40），而且页面网址不带 `no_transfer=1` 时，表里的请求经 JSAPI `webTransfer` 发出，代理看不到。
   - 表里有 9 个广告请求，作用域都是 `mmbizwap_cgi_appmsgad`：`getappmsgad`、`advertisement_report`、`ad_report`、`ad_monitor`、`ad_video_report`、`ad_biz_info`、`ad_complaint`、`ad`、`ad_app_info`。
   - 其余是正常功能：留言、点赞、阅读数（`getappmsgext`）、赞赏、视频播放、相关文章等。
   - 原生通道失败时，页面退回普通请求（XHR）或微信的 `request` 接口。
   - 所以 fmz200 等社区规则、以及 10-23 一度加进③的那条，在新版微信上碰不到广告数据；oo226/egern-config PR #143 的日志里「全程不见 getappmsgad」也是这个原因。
5. 广告卡片画在 iframe 里：普通广告的页面来自 `https://wxa.wxs.qq.com/tmpl/…/base_tmpl.html`，CPS 卡片来自 `https://file.daihuo.qq.com/mp_cps_goods_card/…`。iframe 初始高度为 0，内容加载出来才撑开。主人看到「有文字、没图片」，说明卡片页面加载出来了，只有图片被①挡住。①明明拦着 `wxs.qq.com`，推测微信用的是本地缓存的卡片模板。
6. 广告位所在的元素：文末 `.mpda_bottom_container`、文中 `<mpcpc>`、赞助 `<mp-sponsor-ad>`、评论区 `.comment-ad-container`、作者插入的推广卡片 `<mp-common-cpsad>`、顶部 `#js_top_ad_area`；所有广告 iframe 都带 `.iframe_ad_container`。

## 去广告⑥ 做了什么

`dist/modules/wechat.sgmodule`，规则在 `data/wechat.json`，脚本是原创的 `scripts/wechat.js`。

- 文章页（`wechat-article`）：
  - 在 `<head>` 后面插一段 CSS，隐藏上面列的广告位。不管广告数据从哪条路来、是不是缓存的，都显示不出来。
  - 把转发表里那 9 个广告请求删掉，其余条目原样保留，广告请求于是回到普通 HTTPS。
  - 页面其余部分逐字节不变。只处理 `text/html`、不超过 5 MiB、`<head>` 在前 8 KB 内，并且带转发表或文章容器 `js_article` 的页面；已处理过的页面、错误页、JSON 原样放行。转发表格式和预期不符时只加样式、不动转发表。
- 广告数据（`wechat-ad`）：删掉 `/mp/getappmsgad` 返回里名字带 advertisement 的字段，和 fmz200 改的字段相同。错误、重试信号、非 JSON 原样返回。
- `cps_product_info` 回空 JSON，和 fmz200 相同。
- 只解密 `mp.weixin.qq.com`。这个主机归⑥管：②不再从插件导入它的规则，校验也不许别的模块解密它。`data/allowlist.json` 保证文章页面、图片（`mmbiz.qpic.cn`、`mmbiz.qlogo.cn`）、视频（`mpvideo.qpic.cn`）、页面脚本（`res.wx.qq.com`）永远不会被上游广告列表拦掉。
- 留言、点赞、阅读数、赞赏、相关文章、视频播放、公众号主页、登录这些地址不匹配任何规则，`tools/validate.py` 和测试会检查。

## 代价和风险

- 文章页要等整页下载完（约 800 KB 压缩数据）才处理，打开可能慢一点。
- 处理一页大约要 15–25 MB 临时内存（估算，没有真机测过）；iOS 给 Shadowrocket 的上限约 50 MB。翻订阅号消息时微信会预加载多篇文章。如果 VPN 断开或 Shadowrocket 重启，先关⑥，或把①换成精简版。
- CPS 推广卡片被隐藏后，作者用它介绍的商品、小游戏也看不到了。微信小店的普通商品卡片、小程序卡片、视频号卡片不受影响。

## 在微信里还能做的

- 关个性化广告：我 → 设置 → 个人信息与权限 → 个性化广告管理（旧版本在「隐私」里面）。广告数量不会变，只是不再按兴趣推。2020–2021 年的报道说只能关半年，现在是否仍然如此未确认。
- 隐藏不用的入口：我 → 设置 → 通用 → 发现页管理，关掉视频号、直播、看一看、搜一搜、游戏等。
- 单条朋友圈广告：点卡片右上角的「广告」，选「不感兴趣」。不同版本的选项名可能不同。

## 怎么验证、怎么排查

1. 主人更新模块后，用流量打开两三篇之前有广告的文章，滑到底看广告位是否消失，留言、点赞、阅读数是否正常。
2. 抓一份日志（[DEVICE_LOGS](DEVICE_LOGS.md)），运行 `python3 tools/devicelog.py 日志.db --app wechat --check`。重点看三点：
   - 有没有 `mp.weixin.qq.com/s` 的完整网址：有，说明文章页经过了解密，样式能加上；
   - `/mp/getappmsgad` 出现没有：出现，说明转发表改动生效、广告请求回到了普通 HTTPS；
   - `wxa.wxs.qq.com` 是否被拒绝。
3. 文章打不开或显示不全：先关⑥再试。关了就好，就是⑥的问题，带日志修。

## 维护

- 微信改版后先复查：用 Safari 的 User-Agent 下载一篇公开文章（微信的 User-Agent 会被拒），检查这几项还在不在：`window.__ajaxTransferConfig` 的格式、`mmbizwap_cgi_appmsgad`、`mpda_bottom_container`、`iframe_ad_container`、`AD_FRAME_DOMAIN`。
  - 转发表格式变了：脚本只加样式、不改表，广告数据照旧到达，但广告位仍被隐藏。
  - 类名变了：样式失效，广告重新出现，页面本身不会坏。
- 改脚本后更新 `sources/scripts.lock.json` 的哈希与审核说明，旧版本按 [MAINTENANCE](MAINTENANCE.md) 归档。

## 来源

- [fmz200/wool_scripts blockAds.plugin](https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin)：「公众号文章下方广告」改 `getappmsgad` 的 advertisement 字段；「公众号去除商品推广」拦 `cps_product_info`。
- [oo226/egern-config#143](https://github.com/oo226/egern-config/pull/143)：日志里不见 `getappmsgad` 而广告仍在；认为整个拦 `wxs.qq.com` 可能误伤公众号图片和视频。
- [garywah 转存的 ddgksf2013 微信模块](https://raw.githubusercontent.com/garywah/Shadowrocket/main/module/WeChat.module)、[V2EX：iOS 如何屏蔽掉微信公众号里面的广告？](https://www.v2ex.com/t/724484)
- 设置路径：[钛媒体：个人信息与权限 → 个性化广告管理](https://www.tmtpost.com/6043256.html)、[观察者网：旧版在「隐私」里](https://www.guancha.cn/economy/2021_11_12_614569.shtml)、[IT之家](https://www.ithome.com/0/525/104.htm)与[澎湃新闻](https://www.thepaper.cn/newsDetail_forward_11713655)：只能关半年、[IT之家：在「通用 → 发现页管理」关闭入口](https://www.ithome.com/0/557/557.htm)
- 其余结论来自对微信公开页面代码的阅读，只记录了接口名、字段名和元素名，没有复制代码。
