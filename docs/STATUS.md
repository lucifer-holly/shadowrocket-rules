# 当前状态与交接

最后更新：2026-10-22。每次工作结束时更新本页：做了什么、在等主人什么、临时措施什么时候撤掉。已有的真机结果见 [DEVICE_RESULTS](DEVICE_RESULTS.md)，网络规则做不到的事见 [TROUBLESHOOTING](TROUBLESHOOTING.md)。

## 主人的设备

- iPhone（iOS 27）+ Mac，Shadowrocket「配置」模式，节点是主人自建的 DMIT 服务器。
- 手机启用：主配置、去广告①（base）、去广告②（app-ads）、本机证书模块；③④按需。Mac 只用主配置。

## 待办与进行中

| 事项 | 现状 | 下一步 |
|---|---|---|
| 微博轻享版：用户主页、首页「关注」「推荐」刷不出内容 | 配置模式下热门榜、话题页正常，开屏已去除。日志里这些页面用的 `api.weibo.cn`、`weibointl.api.weibo.cn` 走直连、不解密，当前构建不拦也不改；登录、验证码相关主机也没拦。问题出现在 2026-10-22 解密 `api.weibo.cn` 的约 12 分钟之后，那次改动已撤回，之后断开 Shadowrocket 也打不开，推测是那段时间给 App 或账号留下的异常 | 主人按顺序试：退出登录再登录 → 删除重装 → Safari 打开 `m.weibo.cn` 看主页（网页也打不开就是账号被限制）。恢复后再做首页信息流广告（粉丝头条、微博视频号）：这需要解密 `api.weibo.cn`，先跟主人说明上次的后果，做成可以单独开关的模块 |
| `DOMAIN` 精确规则对照实验 | `sdkmonitor.biz.weibo.com` 故意用 `DOMAIN` 写法，主配置里有 `DOMAIN-SUFFIX,weibo.com,DIRECT` | 下一份微博日志里看它是 REJECT 还是 DIRECT。DIRECT 就把 app-ads 里约 220 条落在主配置分组下的 `DOMAIN` 规则改成 `DOMAIN-SUFFIX`，并改回这一条 |
| 虎牙开屏广告 | 素材下载（`business.msstatic.com/ssp/material/…`、P2P 节点 `business-qnpcdn.msstatic.com`）全部被拦，开屏仍出现，清缓存无效；推测是 App 长期保存的旧素材 | 主人过几天再看；还在就抓一份日志 |
| 虎牙活动弹窗 | 可能来自 `diy-assets.msstatic.com/hyys/activity/…` 的图片或 `hd.huya.com` 的网页，未确认 | 主人截图确认后只拦对应路径；不要整个拦 `hd.huya.com`（活动页、可能还有充值页都在上面） |
| 虎牙未成年提示 | 日志里没有对应请求，可能是本地弹窗 | 暂不处理 |
| 被拦后的高频重试 | 虎牙的 `cdn.wup.huya.com/launch/queryHttpDns`、`livewebbs2.msstatic.com` 被拦后每秒重试多次 | 影响耗电时再试：域名解析接口改用 `reject-dict`，或评估放行 `livewebbs2` |
| Jump：「Jump小酱」推荐、优惠券弹窗 | 未开始 | 需要日志 |
| 中国电信号码认证 `id6.me` | 上游列表拦截；用电信卡时「本机号码一键登录」可能失败，短信登录不受影响 | 主人需要时加进 allowlist |

## 临时措施

| 措施 | 撤除条件 |
|---|---|
| `data/app-ads-overrides.json` 的 `observe_hosts`：8 个虎牙主机只解密、不拦截，让日志能看到完整地址 | 虎牙调查结束，或最迟 2026-11-05 删除 |
