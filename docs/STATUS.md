# 当前状态与交接

最后更新：2026-10-30。每次工作结束时更新本页：做了什么、在等主人什么、临时措施什么时候撤掉。已有的真机结果见 [DEVICE_RESULTS](DEVICE_RESULTS.md)，网络规则做不到的事见 [TROUBLESHOOTING](TROUBLESHOOTING.md)。

## 主人的设备

- iPhone（iOS 27）+ Mac，Shadowrocket「配置」模式，节点是主人自建的 DMIT 服务器。2026-10-28 起只留两个节点：双栈直连节点「主线」（同一域名有 IPv4 和 IPv6 地址）和 CDN 节点「备用」。首页日常选「主线」，不通时主人手动换「备用」（见 [DEVICE_PROFILES](DEVICE_PROFILES.md#节点与-ipv6)）。服务器由另一个对话负责，那边能按分钟查服务器日志里的连接来自 IPv4 还是 IPv6。
- 服务器丢弃 QUIC（UDP 443），App 改走 TCP；日志里 UDP 443 失败是正常的。主配置不加 QUIC 的 REJECT（硬性规则 3）。
- 手机启用：主配置、去广告①（base）、去广告②（app-ads）、去广告⑤（weibo）、本机证书模块；③④按需。Mac 只用主配置。
- 模块分工（2026-10-22 整理）：广告域名、IP 的拦截全部在①，fmz200 插件的静态域名也并进①统一去重；②③④⑤只放各 App 的接口规则和脚本（②里另有按网址 + User-Agent 拦的少数明文请求，见 `connection_rules`）。`tools/validate.py` 检查任何模块的重写或域名拦截都不会抢先挡掉另一个模块的脚本。
- 微博：主人改用「微博」完整版（同一账号在完整版里一切正常），轻享版不再维护。

## 待办与进行中

| 事项 | 现状 | 下一步 |
|---|---|---|
| 主配置：优先 IPv6；不用自动切换分组（2026-10-28，服务器对话两次交接） | 已证实（服务器日志）：主人更新主配置后（11:58 UTC 起），有 IPv6 的移动宽带上「主线」的连接几乎都走 IPv6；之前在 Mac 上关掉 IPv6 时，同一节点改走 IPv4。同日试过故障转移分组 `自动切换 = fallback,主线,备用,url=…generate_204,interval=600,timeout=5,select=0`（298 条代理规则含 `FINAL` 都指向它）：12:08:53 UTC 起服务器按来源地址拦掉主人网络到直连节点 443 端口的连接（IPv4、IPv6 都拦，CDN 回源不受影响），主人在分组里点「测试」后分组仍显示「主线」，网页打不开；服务器日志里分组对「备用」做过 4 次 `generate_204` 健康检查，代理流量却没切过去，直到主人手动切到 CDN。推测和 Shadowrocket 的 fallback 判定方式或 `select=0` 有关，未证实。主人决定不要自动切换：分组和 `tools/validate.py` 里为它开的特例已撤回，规则回到 `PROXY`（首页选哪个节点就走哪个），只保留 `prefer-ipv6 = true` | 等主人：手机和 Mac 各自更新并使用主配置，首页选「主线」日常使用；「主线」不通时手动选「备用」，恢复后选回。节点名不再有要求。以后若要再试自动切换，先在测试配置里验证 fallback 真的会切 |
| 主人的 Wi-Fi 是否真的不可靠 | AGENTS.md 写着「主人的 Wi-Fi 本身有故障」。服务器对话推测（未证实）：10-26～28 服务器的旧 IPv4 被墙、换来的第一个新 IPv4 也被墙，没有 IPv6 的网络（主人家里的 Wi-Fi）上直连节点全部失败，只有 CDN 能用；Wi-Fi 的问题可能部分是这个原因。10-28 已换到干净的 IP。10-22 小红书在 Wi-Fi 上断连早于这次被墙，所以不是全部原因 | 主人方便时用 Wi-Fi 再试几个 App；都正常就把 AGENTS.md 里「测试用蜂窝流量」那条改成按实际情况 |
| 去广告⑤ 微博完整版：信息流和「我」页 | 2026-10-24 主人按步骤更新⑤、点「使用配置」后做了 Safari 自检，显示 `"personal_filter":"weibo"`：脚本在手机上运行。之前「我」页名字删不掉，推测是脚本没下载到（未证实）。主人反馈微博里的其他广告基本没了。自检网址 `https://api.weibo.cn/2/profile/me?personal_filter_selftest=1`：显示 `ok` 和版本日期就是在运行，显示 `校验参数不存在` 就是没运行，排查见 TROUBLESHOOTING「脚本不生效」 | 主人确认「我」页的用户任务、微博购、短剧、稀缺装扮、超友趣是否都没了；还在就用流量打开「我」页抓日志，看 `profile/me` 的地址。界面精简（首页顶部标签 `groups/allgroups/v2`、超话页、底部「+」菜单）等主人说要哪些 |
| 微博开屏广告 | 2026-10-24 查到两层原因。一是 allowlist 里的 `adstrategy.biz.weibo.com` 让构建删掉了上游整段拦截的 `biz.weibo.com`，开屏策略 `/v1/strategy/first_show` 被放行（17:41 日志），已改为①整段拦截。二是开屏来自微博本地缓存的广告：18:51 日志里 7 次冷启动的开屏相关请求全被拦，主人仍每次看到不同的「摇一摇」开屏（摇动后跳淘宝、京东），广告组件仍上报展示、下载素材；主人删除重装后开屏消失。为了以后不再靠重装，同日改为⑤改写开屏接口：①不再拦 `bootpreload`、`bootrealtime`、`sdkapp`、`wbapp` 这 4 台 `uve.weibo.com` 主机（`data/allowlist.json`），⑤解密它们，脚本把 `v*/ad/preload`、`interface/sdk/sdkad.php`、`wbapplua/wbpullad.lua` 返回里的每条广告改到 2037-12-31 才生效、次数清零，微博每次同步就用它覆盖缓存；这几台主机上的其他请求回空 JSON，脚本认不出的返回也回空。字段名参考 iKeLee、墨鱼（ddgksf2013，2025-09）、zmqcherish 的公开脚本，真机上的实际返回还没看过。`uve.weibo.com` 下其余广告主机（fastimage、adimg、click、datacollection）仍由①拦 | 主人更新①⑤后冷启动微博几次，确认仍没有开屏；方便时用流量抓一份启动日志，确认这 4 台主机显示为完整网址（已解密），地址和脚本的 3 个接口对得上。出现开屏：先把这 4 台主机改回由①拦截（撤销这次对 `data/allowlist.json`、`data/extra-domains.json` 的改动），再请主人删除重装 |
| 微博轻享版：用户主页、首页「关注」「推荐」刷不出内容 | 同一账号在完整版正常，说明账号没被限制，问题只在轻享版。日志里这些页面用的 `api.weibo.cn`、`weibointl.api.weibo.cn` 走直连、不解密，当前规则不碰；问题出现在 2026-10-22 解密 `api.weibo.cn` 的约 12 分钟之后，那次改动已撤回 | 主人已改用完整版，先放着。想恢复轻享版就删除重装再登录 |
| 闲鱼开屏广告（重点） | 2026-10-23 第一份日志证实：闲鱼冷启动时先用明文 HTTP 请求 `http://<IP>/amdc/mobileDispatch`（阿里的调度服务），放行后直接连 IP，全程不用 `acs.m.goofish.com`，开屏重写碰不到；主人说之前也是「过一天广告就回来」。已在 app-ads 加只对闲鱼 User-Agent 生效的拦截（`data/apps.json` 的 `connection_rules`）。同日第二份日志：6 个调度地址都被这条规则拦下（Shadowrocket 认这种 AND 规则），主人试了几次都没有开屏。闲鱼仍会直连少量 IP（`59.82.121.x`、`203.119.238.12`），推测是缓存的旧服务器列表或内置地址 | 隔一两天主人再确认开屏没回来。回来了就抓日志；仍直连 IP 的话，先在闲鱼里清缓存，不行再重装清掉旧的服务器列表 |
| Jump 开屏、首页广告和弹窗 | 2026-10-23 临时解密 `switch.jumpvg.com` 后（Jump 能正常用，没有证书锁定）日志里看到：开屏 `/jump/getlaunchad/v2`、首页广告 `/jump/ad/home/screen(/full_v2)`、`/jump/ad/kiko_down_page/conf`、推荐流广告配置 `/jump/recommend/ad_conf`、运营弹窗 `/jump/notice/popup`。这几处都改为回空 JSON（`data/apps.json` 的 `jump`），临时解密已撤；主人反馈改之前几次冷启动里只出现过一次开屏 | 主人更新②后确认开屏、首页弹窗、优惠券弹窗都没了。「Jump小酱」推荐在推荐流 `/jump/recommend/content_v3_1` 的内容里，要写响应过滤，等主人截图确认样子 |
| 虎牙开屏广告（已结束） | 素材下载（`business.msstatic.com/ssp/material/…`、P2P 节点 `business-qnpcdn.msstatic.com`）全部被拦后，开屏仍出现，清缓存无效（10-22、10-24）。2026-10-30 主人按给的测试步骤操作后反馈：**没有开屏了**（是否重装过没有说明）。判断开屏来自 App 本地保存的旧素材（和微博 10-24 相同），现有拦截挡住了新素材；为找素材来源而解密的 5 个图片主机同日撤掉，没留规则 | 开屏再出现：先确认 Shadowrocket 连着、「配置」模式，再删除重装；重装后还有就抓冷启动日志，必要时把图片主机临时加回 `observe_hosts`（写 `until`，最多 21 天） |
| 虎牙活动弹窗 | 10-22 16:51 日志（当时解密了 `diy-assets.msstatic.com`）：启动后约 13 秒，和首页直播封面、功能图标同时加载了活动排行榜面板的图片 `diy-assets.msstatic.com/hyys/activity/261019*.png`；`hd.huya.com` 解密后一次没出现。2026-10-30 主人反馈仍有活动弹窗（没有截图）。同日起②按路径给 `/hyys/activity/` 的图片回透明图（`data/apps.json` 的 `huya`）；这台主机因此被解密，之后的日志能看到它的完整地址。弹窗是不是这组图片，**还没证实**。10-30 20:23 主人反馈活动弹窗没有了，但那份日志里没有 `/hyys/activity/` 的请求，分不清是规则起作用还是活动本身结束了（10-22 那组图片属于 10-19 开始的活动） | 主人更新②后冷启动虎牙几次：弹窗不见了，或只剩没有图的空框，就对上了；还在就截图，并在弹窗出现时抓一份日志（`--app huya --timeline`），看弹窗出现那一刻加载了哪些地址。是网页弹窗才考虑临时观察 `hd.huya.com`（写 `until`；上面可能有充值页，能不解密就不解密）。不要整个拦 `hd.huya.com` |
| 虎牙「每日签到」 | 2026-10-30 主人反馈还有「每日签到」（没有截图）。同日 20:23 日志：启动后约 15 秒和首页内容一起加载了 `diy-assets.msstatic.com/CQHfolder/chenjin_sign.png`，可能是签到入口的图标；约 20 秒时打开了一个网页（虎牙网页的加载动画 `yaoguo/new-loading.webp`），前一秒连过 `www.huya.com`。虎牙的网页主机 `hd`、`zt`、`www.huya.com` 都没解密，连接还可能复用，看不出是哪个页面。推测「每日签到」就是这个网页弹窗，未证实。同日把这三台加进 `observe_hosts`（只解密，`until` 2026-11-06） | 主人更新②，下次「每日签到」出现时截图，并在它出现时抓日志（`--app huya --timeline`），看那一刻打开了哪个页面：是网页弹窗就按路径拦（不整域拦）；是首页的签到入口，就看要不要拦 `CQHfolder/chenjin_sign.png`。然后删掉这三个观察主机；没有结果的话，2026-11-07 起构建自动停止解密 |
| 虎牙未成年模式弹窗 | 2026-10-30 主人反馈仍在。这是国内视频 App 2019 年起普遍做的青少年模式提示，每天首次启动时弹出（[IT之家](https://www.ithome.com/0/491/511.htm) 等报道）。10-22 日志里启动时没有对应地址，`diy-front.cdn.huya.com` 解密后也只看到隐私页 `huyaprivacy2.html`，判断由 App 本地弹出，网络规则去不掉 | 不处理；点「我知道了」关掉。隐私和同意页面不拦 |
| 被拦后的高频重试 | 虎牙的 `cdn.wup.huya.com/launch/queryHttpDns`、`livewebbs2.msstatic.com` 被拦后每秒重试多次 | 影响耗电时再试：域名解析接口改用 `reject-dict`，或评估放行 `livewebbs2` |
| 微信朋友圈、公众号广告 | 2026-10-23 主人反馈：两处广告都只剩文字和占位，图片没了（①拦了 `wxs.qq.com` 的广告素材）。分析公开文章页的代码（[WECHAT](WECHAT.md)）：iOS 微信 8.0.40 起，文章的广告请求经微信原生加密通道发送，代理看不到。当天先在③加了 `getappmsgad` 处理（无效，已撤回），又做了改文章页、隐藏广告位的独立模块⑥；主人实测效果不明显，同日废弃（没有日志，原因未查明），③恢复为只管 B站/知乎，②恢复 fmz200 原有的 `cps_product_info` 规则。朋友圈广告卡片走加密协议，删不掉 | 主人在手机上删掉⑥。不再为微信专门做模块，除非主人另有要求；微信里能做的是「发现页管理」关入口、「个性化广告管理」关个性化、朋友圈广告逐条「不感兴趣」。正文图片或视频打不开时放行 `wximg.wxs.qq.com`、`wxsmw.wxs.qq.com` |
| 上游自动更新的定时运行 | 10-23 那次推迟到 09:23 UTC 才跑，10-24 08:56 UTC 又跑了一次，都成功并自动提交（提交人显示为主人） | 已正常；之后只在出现告警 issue 时处理 |
| 银行 App 开屏与营销弹窗 | 2026-10-23 主人反馈中信银行、建设银行等 App 有开屏广告。②曾从 fmz200 导入 23 个银行和支付主机的解密，违反第 5 条；主人选择银行一律不解密、只放开只放图片的银行静态主机：36 个银行、支付域名进了 `never_mitm_suffixes`，②去掉 21 条手机银行和支付主机上的规则，保留 9 个审核过的图片主机（`mitm_exceptions`）。同日日志（15:29）：**建行**冷启动没有开屏，但启动后弹营销活动；弹窗图片走明文 HTTP `imageadv.ccb.com/adpic/nctm/ad/…`，同时连 `adv.ccb.com`，两者已加进①按域名拦截（不解密）。**中信**只连 `wap.citicbank.cn`、`edata.bank.ecitic.com`、`autoload.bank.ecitic.com`，都没解密，没出现图片主机 `imcs.citicbank.com`；开屏推测来自本地缓存或这几台主机之一，公开资料里查不到它们的用途 | 主人更新①后冷启动建行，看营销弹窗是否消失、登录和查询是否正常；App 卡在启动或报错就告诉我，撤掉 `adv.ccb.com`。中信暂时去不掉；如果主人愿意试，可以临时拦 `autoload.bank.ecitic.com` 并逐项检查登录、转账页面，有异常立刻撤 |
| Netflix 和 Netflix 游戏打不开（已结束） | 2026-10-24 主人反馈 Netflix 游戏 Solitaire、随后 Netflix 本身在配置模式下都打不开；同日主人确认是节点的问题，不是规则（主配置里 Netflix 全部走代理，没有 REJECT）。排查期间把 Netflix 自己的全部域名（netflix.com、netflix.net、nflxext.com、nflximg.net/com、nflxso.net、nflxvideo.net）和崩溃上报 `events.backtrace.io` 加进了 `data/allowlist.json`，①不再拦 Netflix 的上报主机 | 放行保留：Netflix 自己的域名一个不拦，没有副作用。换了能看 Netflix 的节点后如果还打不开，再抓日志查 |
| 中国电信号码认证 `id6.me` | 上游列表拦截；用电信卡时「本机号码一键登录」可能失败，短信登录不受影响 | 主人需要时加进 allowlist |

## 临时措施

| 措施 | 撤除条件 |
|---|---|
| `data/app-ads-overrides.json` 的 `observe_hosts`：`hd.huya.com`、`zt.huya.com`、`www.huya.com` 只解密、不拦截，找「每日签到」网页的地址（2026-10-30 加；原来的 8 个虎牙主机同日已全部撤除） | 看到签到页地址、写好规则后删除；最迟 `until` 2026-11-06，过了这天（UTC 日期）构建自动停止解密，每日自动更新会把变化发布出去。`hd.huya.com` 上可能有充值页，不要延长 |
