# 手机和 Mac 共用分流配置

手机和 Mac 可以共用一份完整主配置：把私人直连例外与旧配置中的全部显式 PROXY 规则合并进去，不再需要单独的 `personal-routing.sgmodule`。主配置负责分流，手机再添加去广告模块，Mac 默认不添加。首页继续选择自己已有的节点，路由保持「配置」。

## 地址与首次导入

以下是**不含私人地址或私人旧规则清单的公共模板**，供无需私人例外的设备直接从 URL 添加：

```text
https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf
```

公共模板的 `update-url` 指向同一路径。私人完整版不使用这个更新地址，否则会覆盖掉自己的例外。完整私人配置只需初次导入，后续在客户端更新它内部引用的公共分流规则集与手机广告模块。保留原始配置备份；不要假定本地修改、模块状态和证书会自动合并进远程文件。

私人合并配置的顺序为：私人 SSH/IP/域名直连例外 → 原配置全部显式 PROXY 规则 → 公共代理服务规则集 → 国内常用域名规则集及 `.cn` 直连 → 中国大陆目的地址直连 → 其余代理。**旧配置显式要求代理的站点优先于国内直连，包括关键词、客户端标识和 IP 规则。**

旧配置中普通的海外学术站点、Apple、Microsoft、PayPal 等 DIRECT 项不再整体继承；按“国内常用直连、国外代理”的新要求处理。仍需直连的特殊海外地址应明确加入自己的私人例外。手机广告模块仍可拒绝广告请求，主配置的 PROXY 是未被广告模块拒绝时的路由选择。

## 路由约定

| 流量 | 默认行为 |
|---|---|
| 标准 SSH 端口 22 | DIRECT；包括 WRDS Cloud SSH，与原有习惯一致 |
| 非标准端口 SSH | 自己的目标 IP 直接合并在私人主配置中直连；不全局放行整个端口 |
| WRDS 网页、RStudio 和数据库 | wharton.upenn.edu 走 PROXY；数据库 9737 端口也代理 |
| ChatGPT、Claude、Gemini、Copilot、Google、YouTube | PROXY，优先于中国大陆地址判断 |
| 旧配置显式标记 PROXY 的站点/关键词/IP/客户端标识 | PROXY，优先于国内直连；私人 SSH 例外保留 |
| 局域网、常见国内服务、国内支付域名及其余 `.cn` | DIRECT |
| 常见国际服务，包括 Apple、Microsoft、PayPal | PROXY；原有明确私人直连除外 |
| 其他中国大陆目的地址 | GEOIP,CN,DIRECT |
| 其余流量 | FINAL,PROXY |

WRDS 官方资料：[连接及 MFA](https://wrds-www.wharton.upenn.edu/pages/about/log-in-to-wrds-using-two-factor-authentication/)、[官方 Python 客户端的数据库地址及端口](https://github.com/wharton/wrds/blob/main/wrds/sql.py)。这些路由选择不代替账号授权、MFA 或机构 VPN。

规则只能处理进入 Shadowrocket 的本机流量。Mac 终端 SSH、Python 数据库连接是否进入客户端，取决于虚拟网络/系统代理和应用代理设置；单独启用 HTTP 系统代理不代表所有命令行程序都会使用它。已经在 WRDS Cloud 上运行的程序，其出站网络也不由本机 Shadowrocket 控制。

## 私人例外合并进主配置

私人服务器地址和私人域名不放进公开仓库。可在本地使用以下工具一次合并：

```sh
python3 tools/personalize.py --input /自己的旧配置.conf \
  --private-rules /可选的旧私人路由模块.sgmodule --output private/shared.conf
```

`--private-rules` 可省略，仅用于一次性合并额外的 DIRECT 例外。工具会保留原配置全部显式 PROXY 规则和原有 SSH/IP 直连；原 General、Host、证书和其他非规则部分继续保留，仅移除整份配置的公开 update-url。它不会读取远程代码；遇到未支持的原有代理规则格式会停止，而不是静默丢弃。

生成的 `shared.conf` 是两端需要导入的完整配置。合并后关闭旧私人模块即可，源文件保留备份；运行时不再依赖这个模块。含私人信息的完整版只在自己的设备或私人备份中保管，不提供公开 Raw 地址，也不把 GitHub Token 写入订阅地址。

完整配置通过两个公开纯数据规则集更新：`dist/rules/routing-proxy.list` 与 `dist/rules/routing-direct.list`。旧配置显式代理要求保留在本地主配置里，即使公共规则集变化也不会降为国内直连。新增私人服务器时直接编辑主配置中的私人例外。

## 手机增加广告模块

1. 导入 `base.sgmodule` 或 `lite.sgmodule`，二选一，无需证书。共用主配置没有再次加载基础广告库。
2. 先验证网页、AI、登录、支付和 SSH。再按需逐个导入 `dist/modules/apps/` 的实验模块。
3. 要处理 HTTPS 路径或响应，须在手机当前配置中设置自己的 HTTPS 解密证书并完成系统信任；已有证书在新配置中仍需确认可用。不要把证书或私钥加到公共主配置。
4. `apps-all` 和独立 App 模块二选一；`response-cleaner` 可额外启用。逐一测试，不与旧开屏融合包重复启用。

Mac 只需要同一份私人合并主配置；不要默认启用手机的广告、解密或脚本模块。如果某个模块曾在 Mac 启用，切换主配置后也检查并关闭。

## 更新、检查和回滚

GitHub 合并规则更新不会直接改变设备状态。手机需更新广告模块；两端按需更新引用的分流规则集，重新连接后核对结果。私人完整版不要用公开模板整份覆盖。客户端是否定时刷新取决于自己的设置，仓库 Actions 不能代替设备执行更新。

通过 `data/routing.json` 人工维护公开服务分流。上游广告更新只影响广告文件；不会自动重写公开分流表，也不会吸收未经审核的远程脚本。修改后运行 `make build && make test`。

静态测试覆盖了 SSH 与 WRDS 数据库的不同端口、AI/Google/YouTube 优先级、国内和局域网路由、主配置无广告/解密及公共文件边界。它不是 iOS/macOS 真机验证。出现异常时切回原配置；广告误杀先关闭手机对应广告模块。固定旧版本时使用 GitHub 完整提交 SHA 替代 Raw URL 中的 main，并同时修改配置内 update-url，避免下次更新跳回最新版。
