# 设备日志：抓取、导出与分析

规则改得对不对，最终要看手机上的请求日志：日志会写出每个请求的地址、命中的规则和结果。本页前半部分给手机上的操作，后半部分给分析的人（或 agent）。

## 什么时候需要日志

- 某个 App 还有广告：开屏、弹窗、信息流。
- 某个 App 页面空白、加载失败，怀疑被规则误拦。**先断开 Shadowrocket 试一次**：断开后仍然异常，就不是规则的问题，不用抓日志。

## 抓取（手机）

1. 首页「全局路由」确认是「配置」。选「代理」时规则全部不执行，日志里每条都会是 `ROUTING,PROXY`。
2. 「数据」→「代理」→ 打开「启用日志记录」。
3. 从后台划掉目标 App 再打开，复现问题：等开屏、弹窗出现，或点进出问题的页面，再停 10 秒。
4. 关掉「启用日志记录」，首页断开 VPN，从后台划掉 Shadowrocket 再打开。
5. 「数据」→「代理」→ 点开最新的日志 → 右上角 `•••` → 导出。
6. 重新连上 VPN，再把文件发出去。

导出的文件只有 4 KB 时，里面没有记录：新记录还在临时文件里，没写进导出的文件。重做第 4 步再导出；还不行就改用截图，截带 App 名的条目，尤其是写着 REJECT 的行。

## 隐私约定

日志里有这段时间所有 App 的域名。分析时只看：

- 目标 App 的条目（域名或 User-Agent 能认出是这个 App）；
- 使用这个 App 的那段时间里被拦截的条目（通常是 App 内的第三方广告组件）。

其余条目只统计数量。日志文件不提交到仓库（`.gitignore` 已排除 `*.db`）；仓库里只写域名和路径，不写查询参数、token、节点名。

## 看懂日志

| 「规则」一栏 / 地址 | 含义 |
|---|---|
| `ROUTING,PROXY`、`ROUTING,DIRECT` | 全局路由不是「配置」，规则没有执行 |
| `DOMAIN-SUFFIX,…,REJECT`、`DOMAIN,…,REJECT` | 模块的域名拦截命中 |
| `URL-REGEX,…,REJECT`（或 `REJECT-200` 等） | 模块的 URL 重写命中（这个主机已解密） |
| `DOMAIN-SUFFIX,…,DIRECT`、`GEOIP,CN,DIRECT`、`FINAL,PROXY` | 主配置的分流结果 |
| 地址只有 `主机:443`，User-Agent 是 `TCP Stream` | 没有解密，只看得到域名 |
| 完整的 `https://…` 地址 | 已解密（主机在 MITM 列表里） |

真机日志确认过（2026-10-22～24）：

- 模块的 `DOMAIN-SUFFIX` 和 `DOMAIN` 拦截都能压过主配置里更宽的分组规则，例如 `uve.weibo.com`、`sdkmonitor.biz.weibo.com` 的拦截都压过了 `weibo.com` 直连。
- 阿里系 App（闲鱼）启动时先用明文 HTTP 向 `http://<IP>/amdc/mobileDispatch` 要服务器列表，拿到后直接连 IP。日志里只剩 `IP:443` 的 TCP Stream，按域名的解密和重写全部失效。办法是按 User-Agent 拦掉这个 App 的调度请求，让它退回走域名（`data/apps.json` 的 `connection_rules`）。
- Shadowrocket 认 `AND,((URL-REGEX,…),(USER-AGENT,…)),REJECT` 这种规则：闲鱼的 6 个调度地址都被它拦下，日志「规则」一栏会显示整条规则。
- 请求被拦截后，有的 App 会高频重试（虎牙 3 分钟上百次），这不代表规则失效。
- 2026-10-28 当天有几个小时，主配置里走代理的规则在日志「规则」一栏显示为 `…,自动切换`（试用过的故障转移分组，已撤回，见 [两端共用配置](DEVICE_PROFILES.md#节点与-ipv6)）；其余时间都是 `…,PROXY`。
- 主人的服务器丢弃 QUIC（UDP 443），App 会改走 TCP：日志里 UDP 443 连接失败或没有响应是正常的，不是规则的问题。
- 开屏相关的请求全被拦，开屏却每次换着出现：看广告组件的展示上报和素材下载是否还在发生（微博是 `sdkmonitor`、`sdkaction`、`sdkclick`、`kadmimage.biz.weibo.com`）。还在发生，就是 App 在播本地缓存的广告（2026-10-24 微博，删除重装后消失），处理见 [故障排查](TROUBLESHOOTING.md)。
- 开屏素材常被 App 提前下载并长期保存，拦截后可能还会显示一段时间，「清除缓存」不一定清得掉。

## 分析（电脑或 agent）

```sh
python3 tools/devicelog.py 日志.db --app huya --check
python3 tools/devicelog.py 日志.db --host 'example|examplecdn' --ua 'ExampleApp/' --timeline
```

- `--app` 预设：weibo、huya、xiaohongshu、bilibili、zhihu、youtube、xianyu、jump、wechat、citic（中信银行）、ccb（建设银行）。新 App 用 `--host` / `--ua`，确认特征后加进 `tools/devicelog.py` 的 `APPS`。
- `--check` 对照当前构建，列出每个主机是被去广告①拦截（`base 拦截`，含 fmz200 插件的静态域名），还是被哪个模块解密，或者都没有。
- 工具只读，不改文件；不显示与 App 无关的条目、查询参数和节点名。

判断方法：

| 看到的情况 | 处理 |
|---|---|
| 几乎全是 `ROUTING,…` | 让主人把全局路由改回「配置」 |
| 启动前几秒有 DIRECT 主机，名字或路径像广告素材（ad、ssp、dsp、splash、material…） | 整个主机都是广告：加进 `data/extra-domains.json`（写 `DOMAIN-SUFFIX`） |
| 广告和正常内容在同一个主机上 | 按路径拦：`data/apps.json`；路径看不到时，把主机加进 `data/app-ads-overrides.json` 的 `observe_hosts` 临时解密，下一份日志就能看到完整地址 |
| App 自己的功能请求被 REJECT（消息长连接、内容接口） | `data/allowlist.json`；如果是自动导入的规则误伤，用 `app-ads-overrides.json` 的 `exclude_hosts` / `exclude_patterns` |
| App 的请求只剩 `IP:443`、看不到它的域名，规则写对了也不生效 | App 绕过了域名。先找它启动时的调度请求（阿里系是明文的 `/amdc/mobileDispatch`），在 `data/apps.json` 的 `connection_rules` 里按网址和 User-Agent 只拦这个 App 的 |
| 规则已经写了，日志里却没生效 | 手机可能还是旧模块：手动更新模块，断开再连接 VPN；GitHub raw 链接有约 5 分钟缓存 |
