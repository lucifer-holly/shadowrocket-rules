# 当前状态与交接

最后更新：2026-10-22。每次工作结束时更新本页：做了什么、在等主人什么、临时措施什么时候撤掉。已有的真机结果见 [DEVICE_RESULTS](DEVICE_RESULTS.md)，网络规则做不到的事见 [TROUBLESHOOTING](TROUBLESHOOTING.md)。

## 主人的设备

- iPhone（iOS 27）+ Mac，Shadowrocket「配置」模式，节点是主人自建的 DMIT 服务器。
- 手机启用：主配置、去广告①（base）、去广告②（app-ads）、去广告⑤（weibo）、本机证书模块；③④按需。Mac 只用主配置。
- 模块分工（2026-10-22 整理）：不需要证书的拦截（广告域名、IP）全部在①，fmz200 插件的静态域名也并进①统一去重；②③④⑤只放需要证书的接口规则和脚本。`tools/validate.py` 检查任何模块的重写或域名拦截都不会抢先挡掉另一个模块的脚本。
- 微博：主人改用「微博」完整版（同一账号在完整版里一切正常），轻享版不再维护。

## 待办与进行中

| 事项 | 现状 | 下一步 |
|---|---|---|
| 去广告⑤ 微博完整版（`dist/modules/weibo.sgmodule`） | 第一版真机可用：无开屏，页面都正常。主人反馈还剩：关注列表里的「根据你的兴趣推荐优质博主」和没关注过的人、全局右下角红包、「我」页的活动/钱包/任务中心/AI伴聊。第二版已处理：关注列表（容器 231093）删 `following` 为 false 的人和推荐标题；信息流按字样删推荐卡片；「我」页按名字删；`push/active` 回空。只用合成样例测过 | 主人更新模块后再看这四处；还在就截图（「我」页截图里能看到要删的名字）。主页、关注流、私信、发微博仍要正常。关注流如果还混入没关注的人的微博，先建议首页「关注」下拉选「最新微博」。界面还可以精简：首页顶部标签（`groups/allgroups/v2`）、超话页、底部「+」菜单，等主人说要哪些 |
| 微博轻享版：用户主页、首页「关注」「推荐」刷不出内容 | 同一账号在完整版正常，说明账号没被限制，问题只在轻享版。日志里这些页面用的 `api.weibo.cn`、`weibointl.api.weibo.cn` 走直连、不解密，当前规则不碰；问题出现在 2026-10-22 解密 `api.weibo.cn` 的约 12 分钟之后，那次改动已撤回 | 主人已改用完整版，先放着。想恢复轻享版就删除重装再登录 |
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
