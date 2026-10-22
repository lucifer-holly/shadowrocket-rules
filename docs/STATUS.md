# 当前状态与交接

最后更新：2026-10-22。每次工作结束时更新本页：做了什么、在等主人什么、临时措施什么时候撤掉。

## 主人的设备与用法

- iPhone（iOS 27）+ Mac，Shadowrocket「配置」模式，节点是主人自建的 DMIT 服务器。
- 手机启用：主配置、去广告①（base）、去广告②（app-ads）、本机证书模块；③④按需。Mac 只用主配置。
- 测试用蜂窝流量。主人的 Wi-Fi 本身有故障，关掉 Shadowrocket 也不通，不要据此判断规则。

## 已确认有效（真机日志）

- 配置模式下分流正常：微博、虎牙等国内 App 直连。
- 微博开屏广告已去掉：`adstrategy.biz.weibo.com/v\d+/strategy/ad` 返回空数据，另外拦截了 `uve.weibo.com` 和几个 `biz.weibo.com` 广告素材/上报主机。
- 小红书在流量下正常（`apppush*.xiaohongshu.com` 已放行，否则消息页显示未连接）。
- 哔哩哔哩、X 等 App 没有反馈问题。

## 待办与进行中

| 事项 | 现状 | 下一步 |
|---|---|---|
| 微博轻享版：用户主页、展开文章打不开 | 断开 Shadowrocket 也打不开，不是规则造成的（App 或账号侧）。主人决定先放着 | 主人恢复后确认；正常后再做首页信息流广告（粉丝头条、微博视频号），做成可以单独开关的模块。注意 2026-10-22 曾解密 `api.weibo.cn` 约 12 分钟，之后才出现这个问题，已撤回 |
| `DOMAIN` 精确规则的对照实验 | `sdkmonitor.biz.weibo.com` 故意用 `DOMAIN` 写法，主配置有 `DOMAIN-SUFFIX,weibo.com,DIRECT` | 下一份微博日志里看它是 REJECT 还是 DIRECT。如果是 DIRECT，就把 app-ads 里约 220 条落在主配置分组下的 `DOMAIN` 规则改成 `DOMAIN-SUFFIX`，并改回这一条 |
| 虎牙开屏广告 | 素材下载（`business.msstatic.com/ssp/material/…`、P2P 节点 `business-qnpcdn.msstatic.com`）全部被拦，开屏仍出现，清缓存无效。推测是 App 长期保存的旧素材 | 主人过几天再看。还在的话抓一份日志：启动期的图片主机已临时解密，日志能看到完整地址 |
| 虎牙活动弹窗 | 可能来自 `diy-assets.msstatic.com/hyys/activity/…` 的图片或 `hd.huya.com` 的网页，未确认 | 需要主人截图确认，然后只拦对应路径；不要整个拦 `hd.huya.com`（活动、可能还有充值页面都在上面） |
| 虎牙未成年提示 | 日志里没找到对应请求，可能是本地弹窗 | 暂不处理 |
| 临时「只解密」主机（`observe_hosts`） | 8 个虎牙主机：`hd.huya.com`、`diy-front.cdn.huya.com`、`diy-assets.msstatic.com`、`fileserver.cdn.huya.com`、`s1-static.msstatic.com`、`v-huya-img2.msstatic.com`、`anchorpost.msstatic.com`、`huyaimg.msstatic.com` | 虎牙调查结束，或最迟 2026-11-05，从 `data/app-ads-overrides.json` 删除 |
| 被拦后的高频重试 | 虎牙的 `cdn.wup.huya.com/launch/queryHttpDns`、`livewebbs2.msstatic.com` 被拦后每秒重试多次 | 影响耗电时再试：域名解析接口改用 `reject-dict`，或评估放行 `livewebbs2` |
| Jump：「Jump小酱」推荐、优惠券弹窗 | 未开始 | 需要日志 |
| 中国电信号码认证 `id6.me` | anti-AD 和 HaGeZi 都拦了，「本机号码一键登录」用电信卡时可能失败，短信登录不受影响 | 主人需要时加进 allowlist |

## 无法用网络规则解决（已向主人说明）

- App 请求通知权限的系统弹窗：iOS 本地弹出。办法是在 iOS 设置里允许通知但关掉横幅、声音等。
- X（Twitter）推广帖、Telegram 赞助消息：和正常内容在同一个加密接口里。

## 自动化

- `Upstream auto update`（`.github/workflows/update.yml`）每天 04:17 UTC 运行，通过全部检查后直接提交到 main；来源异常时开「上游自动更新需要关注」Issue，恢复后自动关闭；第三方脚本有新版本时开审核 Issue。
- `Validate`（`.github/workflows/validate.yml`）在每次推送时运行。
- Dependabot 已按主人要求关闭。
