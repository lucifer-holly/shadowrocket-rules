# 当前状态与交接

最后更新：2026-10-24。每次工作结束时更新本页：做了什么、在等主人什么、临时措施什么时候撤掉。已有的真机结果见 [DEVICE_RESULTS](DEVICE_RESULTS.md)，网络规则做不到的事见 [TROUBLESHOOTING](TROUBLESHOOTING.md)。

## 主人的设备

- iPhone（iOS 27）+ Mac，Shadowrocket「配置」模式，节点是主人自建的 DMIT 服务器。
- 手机启用：主配置、去广告①（base）、去广告②（app-ads）、去广告⑤（weibo）、本机证书模块；③④按需。Mac 只用主配置。
- 模块分工（2026-10-22 整理）：广告域名、IP 的拦截全部在①，fmz200 插件的静态域名也并进①统一去重；②③④⑤只放各 App 的接口规则和脚本（②里另有按网址 + User-Agent 拦的少数明文请求，见 `connection_rules`）。`tools/validate.py` 检查任何模块的重写或域名拦截都不会抢先挡掉另一个模块的脚本。
- 微博：主人改用「微博」完整版（同一账号在完整版里一切正常），轻享版不再维护。

## 待办与进行中

| 事项 | 现状 | 下一步 |
|---|---|---|
| 去广告⑤ 微博完整版：脚本在手机上有没有运行 | 第二版（10-22）起：关注列表删没关注的人和推荐标题，信息流按字样删推荐卡片，「我」页按名字和编号删。2026-10-24 主人两次反馈：信息流广告回来了，关注页还有推荐，「我」页的用户任务、微博购、短剧、稀缺装扮、超友趣都还在（早上按名字加进删除名单并发布，中午更新后仍在）。日志证实⑤的重写在生效（`push/active` 被拦），说明模块已更新、`api.weibo.cn` 已解密；日志里看不出脚本有没有运行。这些名字脚本都该删掉，**推测脚本在手机上没有运行**（没下载到，或者手机上还是旧版本），未证实。同日给脚本加了自检：Safari 打开 `https://api.weibo.cn/2/profile/me?personal_filter_selftest=1`，脚本在运行就显示 `{"personal_filter":"weibo","ok":true,"version":"2026-10-24",…}`，没运行就显示微博原样返回的 `{"errmsg":"校验参数不存在",…}`。iKeLee 的公开微博插件（2026-10-02）「我」页仍用 `/2/profile/me`，地址没变 | 等主人更新⑤后做自检。显示 `ok`：冷启动微博再看「我」页，名字还在就用流量打开「我」和「关注」抓日志，确认 `profile/me` 出现，说明数据格式变了，要想办法看到真实返回的结构。显示 `errmsg`：配置 → 点当前配置文件 → 编辑配置 → 脚本 URL，看⑤的脚本是 ✅ 还是 ❎；回到上一层点「使用配置」（重新下载全部脚本）后再自检，仍不行就截图「脚本 URL」页。界面精简（首页顶部标签 `groups/allgroups/v2`、超话页、底部「+」菜单）等脚本确认能运行再做 |
| 微博开屏广告 | 10-22 起没有开屏，10-24 又出现。同日日志（17:41）：开屏策略主机 `adstrategy.biz.weibo.com` 的 `/v3/strategy/ad` 已回空，但同时请求的 `/v1/strategy/first_show` 被放行，`vs.biz.weibo.com` 也放行。原因在本仓库：初始仓库把 `adstrategy.biz.weibo.com` 写进 allowlist（理由是「混合 API」），构建时因此删掉了 anti-AD、HaGeZi 本来整段拦截的 `biz.weibo.com`，整个微博广告业务域名从 10-21 起只拦了后来逐台加的 5 台主机。已改为①整段拦截 `biz.weibo.com`（fmz200、iKeLee 的微博规则也这样拦），并去掉②里这台主机的解密和重写，以及只有这一条规则的「去广告② 单 App·微博」模块。`first_show` 是开屏来源属于推测。**同日 18:51 日志（更新后 7 次冷启动）**：开屏策略和预加载的地址每次都被拦（`adstrategy`、`bootpreload`/`sdkapp`/`wbapp.uve.weibo.com`），主人仍每次看到不同的「摇一摇」开屏，摇动后跳到淘宝、京东（同时段 `tanx.com` 的广告跳转请求被拦，随后是淘宝、京东自己的请求）；广告 SDK 每次仍上报展示（`sdkmonitor`/`sdkaction`/`sdkclick`，被拦），第三次启动时还要下载 7 张广告图（`kadmimage`，被拦）。据此判断开屏来自微博本地缓存的一批广告，拦截挡不住已缓存的；推测是 10-24 下午 `first_show` 放行时，或者 Shadowrocket 断开、切「代理」时缓存的。主人同时反馈「其他软件内部广告去的差不多了」 | 主人删除微博再装（「删除 App」，不是会保留数据的「卸载 App」），装好后先确认 Shadowrocket 已连接、配置模式，再打开微博；以后断开 Shadowrocket 或切「代理」时不要打开微博。装回后还有开屏就再抓日志。长期办法，等脚本自检确认在运行再做：仿照 iKeLee、墨鱼（ddgksf2013，2025-09）的公开脚本，不拦 `bootpreload`、`bootrealtime`、`sdkapp`、`wbapp` 这 4 台 `uve.weibo.com` 主机，改为⑤解密并改写返回，让 App 每次同步都用改过的列表覆盖缓存，泄漏后能自己恢复。公开脚本用到的字段：`bootpreload…/v1/ad/preload` 的 `ads[]`（`start_time`、`end_time`、`daily_display_cnt`、`total_display_cnt`、`display_duration`）；`sdkapp…/interface/sdk/sdkad.php`（返回是 JSON 后面跟着 `OK`）的 `show_push_splash_ad` 和 `ads[]`（`begintime`、`endtime` 是「年-月-日 时:分:秒」字符串，`displaynum`、`allowdaydisplaynum`）；`wbapp…/wbapplua/wbpullad.lua` 的 `cached_ad.ads[]`（`start_date`、`end_date`、`show_count`、`duration`）；`bootrealtime…/v[23]/ad/realtime` 回空；做法是把时间改到很远的将来、次数清零。要写原创脚本，认不出结构时回 `{}`。风险：脚本没在运行时，这几台主机不再被拦，广告会直接进来，所以必须先确认脚本在运行 |
| 微博轻享版：用户主页、首页「关注」「推荐」刷不出内容 | 同一账号在完整版正常，说明账号没被限制，问题只在轻享版。日志里这些页面用的 `api.weibo.cn`、`weibointl.api.weibo.cn` 走直连、不解密，当前规则不碰；问题出现在 2026-10-22 解密 `api.weibo.cn` 的约 12 分钟之后，那次改动已撤回 | 主人已改用完整版，先放着。想恢复轻享版就删除重装再登录 |
| 闲鱼开屏广告（重点） | 2026-10-23 第一份日志证实：闲鱼冷启动时先用明文 HTTP 请求 `http://<IP>/amdc/mobileDispatch`（阿里的调度服务），放行后直接连 IP，全程不用 `acs.m.goofish.com`，开屏重写碰不到；主人说之前也是「过一天广告就回来」。已在 app-ads 加只对闲鱼 User-Agent 生效的拦截（`data/apps.json` 的 `connection_rules`）。同日第二份日志：6 个调度地址都被这条规则拦下（Shadowrocket 认这种 AND 规则），主人试了几次都没有开屏。闲鱼仍会直连少量 IP（`59.82.121.x`、`203.119.238.12`），推测是缓存的旧服务器列表或内置地址 | 隔一两天主人再确认开屏没回来。回来了就抓日志；仍直连 IP 的话，先在闲鱼里清缓存，不行再重装清掉旧的服务器列表 |
| Jump 开屏、首页广告和弹窗 | 2026-10-23 临时解密 `switch.jumpvg.com` 后（Jump 能正常用，没有证书锁定）日志里看到：开屏 `/jump/getlaunchad/v2`、首页广告 `/jump/ad/home/screen(/full_v2)`、`/jump/ad/kiko_down_page/conf`、推荐流广告配置 `/jump/recommend/ad_conf`、运营弹窗 `/jump/notice/popup`。这几处都改为回空 JSON（`data/apps.json` 的 `jump`），临时解密已撤；主人反馈改之前几次冷启动里只出现过一次开屏 | 主人更新②后确认开屏、首页弹窗、优惠券弹窗都没了。「Jump小酱」推荐在推荐流 `/jump/recommend/content_v3_1` 的内容里，要写响应过滤，等主人截图确认样子 |
| 虎牙开屏广告 | 素材下载（`business.msstatic.com/ssp/material/…`、P2P 节点 `business-qnpcdn.msstatic.com`）全部被拦，开屏仍出现，清缓存无效；推测是 App 长期保存的旧素材 | 主人过几天再看；还在就抓一份日志；2026-10-24 主人反馈仍在，那份日志里没有虎牙 |
| 虎牙活动弹窗 | 可能来自 `diy-assets.msstatic.com/hyys/activity/…` 的图片或 `hd.huya.com` 的网页，未确认 | 主人截图确认后只拦对应路径；不要整个拦 `hd.huya.com`（活动页、可能还有充值页都在上面） |
| 虎牙未成年提示 | 日志里没有对应请求，可能是本地弹窗 | 暂不处理 |
| 被拦后的高频重试 | 虎牙的 `cdn.wup.huya.com/launch/queryHttpDns`、`livewebbs2.msstatic.com` 被拦后每秒重试多次 | 影响耗电时再试：域名解析接口改用 `reject-dict`，或评估放行 `livewebbs2` |
| 微信朋友圈、公众号广告 | 2026-10-23 主人反馈：两处广告都只剩文字和占位，图片没了（①拦了 `wxs.qq.com` 的广告素材）。分析公开文章页的代码（[WECHAT](WECHAT.md)）：iOS 微信 8.0.40 起，文章的广告请求经微信原生加密通道发送，代理看不到。当天先在③加了 `getappmsgad` 处理（无效，已撤回），又做了改文章页、隐藏广告位的独立模块⑥；主人实测效果不明显，同日废弃（没有日志，原因未查明），③恢复为只管 B站/知乎，②恢复 fmz200 原有的 `cps_product_info` 规则。朋友圈广告卡片走加密协议，删不掉 | 主人在手机上删掉⑥。不再为微信专门做模块，除非主人另有要求；微信里能做的是「发现页管理」关入口、「个性化广告管理」关个性化、朋友圈广告逐条「不感兴趣」。正文图片或视频打不开时放行 `wximg.wxs.qq.com`、`wxsmw.wxs.qq.com` |
| 上游自动更新的定时运行 | 10-23 那次推迟到 09:23 UTC 才跑，10-24 08:56 UTC 又跑了一次，都成功并自动提交（提交人显示为主人） | 已正常；之后只在出现告警 issue 时处理 |
| 银行 App 开屏与营销弹窗 | 2026-10-23 主人反馈中信银行、建设银行等 App 有开屏广告。②曾从 fmz200 导入 23 个银行和支付主机的解密，违反第 5 条；主人选择银行一律不解密、只放开只放图片的银行静态主机：36 个银行、支付域名进了 `never_mitm_suffixes`，②去掉 21 条手机银行和支付主机上的规则，保留 9 个审核过的图片主机（`mitm_exceptions`）。同日日志（15:29）：**建行**冷启动没有开屏，但启动后弹营销活动；弹窗图片走明文 HTTP `imageadv.ccb.com/adpic/nctm/ad/…`，同时连 `adv.ccb.com`，两者已加进①按域名拦截（不解密）。**中信**只连 `wap.citicbank.cn`、`edata.bank.ecitic.com`、`autoload.bank.ecitic.com`，都没解密，没出现图片主机 `imcs.citicbank.com`；开屏推测来自本地缓存或这几台主机之一，公开资料里查不到它们的用途 | 主人更新①后冷启动建行，看营销弹窗是否消失、登录和查询是否正常；App 卡在启动或报错就告诉我，撤掉 `adv.ccb.com`。中信暂时去不掉；如果主人愿意试，可以临时拦 `autoload.bank.ecitic.com` 并逐项检查登录、转账页面，有异常立刻撤 |
| Netflix 和 Netflix 游戏打不开（已结束） | 2026-10-24 主人反馈 Netflix 游戏 Solitaire、随后 Netflix 本身在配置模式下都打不开；同日主人确认是节点的问题，不是规则（主配置里 Netflix 全部走代理，没有 REJECT）。排查期间把 Netflix 自己的全部域名（netflix.com、netflix.net、nflxext.com、nflximg.net/com、nflxso.net、nflxvideo.net）和崩溃上报 `events.backtrace.io` 加进了 `data/allowlist.json`，①不再拦 Netflix 的上报主机 | 放行保留：Netflix 自己的域名一个不拦，没有副作用。换了能看 Netflix 的节点后如果还打不开，再抓日志查 |
| 中国电信号码认证 `id6.me` | 上游列表拦截；用电信卡时「本机号码一键登录」可能失败，短信登录不受影响 | 主人需要时加进 allowlist |

## 临时措施

| 措施 | 撤除条件 |
|---|---|
| `data/app-ads-overrides.json` 的 `observe_hosts`：8 个虎牙主机只解密、不拦截，让日志能看到完整地址 | 虎牙调查结束，或最迟 2026-11-05 删除 |
