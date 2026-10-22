# 手机和 Mac 共用分流配置

两端订阅同一份 `dist/config/main.conf`。主配置只负责路由；手机再添加去广告模块，Mac 默认不添加。主配置不启用脚本、URL 重写或 HTTPS 解密，也不定义代理节点。首页继续选择自己已有的节点，路由保持「配置」。

## 地址与首次导入

在 Shadowrocket 的「配置」页从 URL 添加：

```text
https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf
```

配置内的 `update-url` 指向同一路径，后续在客户端更新远程配置即可。保留最初的配置备份；更新前备份本地修改、模块启用状态和解密证书。不要把本地修改当作会自动合并进远程版本。

这是一份重新编排的通用分流配置，**不是私人旧配置的逐条副本**。国内域名及中国大陆目的地址直连，未列出的其他目标代理；旧配置中针对特定学术站点、服务器和私人域名的手工选择，需要自己保留为本地例外。要求原有分流完全不变时，继续沿用原配置并单独订阅广告模块即可。

## 路由约定

| 流量 | 默认行为 |
|---|---|
| 标准 SSH 端口 22 | DIRECT；包括 WRDS Cloud SSH，与原有习惯一致 |
| 非标准端口 SSH | 按普通规则处理；自己的目标 IP 通过本地模块直连 |
| WRDS 网页、RStudio 和数据库 | wharton.upenn.edu 走 PROXY；数据库 9737 端口也代理 |
| ChatGPT、Claude、Gemini、Copilot、Google、YouTube | PROXY，优先于中国大陆地址判断 |
| 局域网、常见国内服务和支付域名 | DIRECT |
| 其他中国大陆目的地址 | GEOIP,CN,DIRECT |
| 其余流量 | FINAL,PROXY |

WRDS 官方资料：[连接及 MFA](https://wrds-www.wharton.upenn.edu/pages/about/log-in-to-wrds-using-two-factor-authentication/)、[官方 Python 客户端的数据库地址及端口](https://github.com/wharton/wrds/blob/main/wrds/sql.py)。这些路由选择不代替账号授权、MFA 或机构 VPN。

规则只能处理进入 Shadowrocket 的本机流量。Mac 终端 SSH、Python 数据库连接是否进入客户端，取决于虚拟网络/系统代理和应用代理设置；单独启用 HTTP 系统代理不代表所有命令行程序都会使用它。已经在 WRDS Cloud 上运行的程序，其出站网络也不由本机 Shadowrocket 控制。

## 私人路由只导入本地

私人服务器地址和私人域名不放进公开配置。可用本地 `personal-routing.sgmodule` 保存原有例外，在手机和 Mac 各导入一次，并确认更新远程配置后仍然启用。

该私人模块仅含目标 IP/私人域名的 DIRECT 规则，不含 `FINAL`、DNS、证书或脚本，不会让所有网站改成直连。不要上传它到本仓库，也不要给它填入公共的更新地址。新增服务器时只在自己的副本添加对应目标，不把整个非标准端口全局放行。

公开仓库不提供私人模块下载地址。私人模块无需随广告库更新；它只在服务器地址或手工例外变化时修改。

## 手机增加广告模块

1. 导入 `base.sgmodule` 或 `lite.sgmodule`，二选一，无需证书。共用主配置没有再次加载基础广告库。
2. 先验证网页、AI、登录、支付和 SSH。再按需逐个导入 `dist/modules/apps/` 的实验模块。
3. 要处理 HTTPS 路径或响应，须在手机当前配置中设置自己的 HTTPS 解密证书并完成系统信任；已有证书在新配置中仍需确认可用。不要把证书或私钥加到公共主配置。
4. `apps-all` 和独立 App 模块二选一；`response-cleaner` 可额外启用。逐一测试，不与旧开屏融合包重复启用。

Mac 只需要共用主配置和自己的私人路由模块；不要默认启用手机的广告、解密或脚本模块。如果某个模块曾在 Mac 启用，切换主配置后也检查并关闭。

## 更新、检查和回滚

GitHub 合并规则更新不会直接改变设备状态。手机需更新广告模块；两端按需更新主配置，重新连接后核对结果。客户端是否定时刷新取决于自己的设置，仓库 Actions 不能代替设备执行更新。

通过 `data/routing.json` 人工维护公开服务分流。上游广告更新只影响广告文件；不会自动重写公开分流表，也不会吸收未经审核的远程脚本。修改后运行 `make build && make test`。

静态测试覆盖了 SSH 与 WRDS 数据库的不同端口、AI/Google/YouTube 优先级、国内和局域网路由、主配置无广告/解密及公共文件边界。它不是 iOS/macOS 真机验证。出现异常时切回原配置；广告误杀先关闭手机对应广告模块。固定旧版本时使用 GitHub 完整提交 SHA 替代 Raw URL 中的 main，并同时修改配置内 update-url，避免下次更新跳回最新版。
