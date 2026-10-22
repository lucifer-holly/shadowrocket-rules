# 手机和 Mac 共用分流配置

手机和 Mac 导入**同一个远程主配置**，它只负责分流。手机再加去广告模块，Mac 默认不加。首页继续选择自己的 DMIT 节点，全局路由保持「配置」。所有文件都在本仓库，不引用别人的链接。

## 链接

| 模块列表里显示的名字 | 设备 | 链接 |
|---|---|---|
| 主配置（「配置」页导入，不是模块） | 手机 + Mac | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf` |
| 去广告① 广告域名拦截（免证书） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/base.sgmodule` |
| 去广告② App 开屏与应用内广告（需证书） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/app-ads.sgmodule` |
| 去广告③ 信息流净化·B站/知乎（需证书，可选） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/response-cleaner.sgmodule` |
| 去广告④ YouTube（实验，需证书，可选） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/youtube.sgmodule` |
| 本机证书（你自己建的本地模块，不在仓库里） | 手机 | — |

- `base` 内存吃紧或 VPN 频繁断开时换 `lite.sgmodule`，两者二选一。
- 名字里的编号就是作用：① 拦广告域名，② App 开屏/应用内广告，③ 信息流净化，④ YouTube。名字里带「需证书」的模块要配合本机证书模块。
- `app-ads` 已包含 `apps-all` 的全部自维护规则；名字以「去广告②」开头的模块只开一个。
- YouTube 模块是实验性的：脚本来自第三方（已审核并固定版本），在 Surge 上测试，Shadowrocket 不保证兼容。YouTube 出现播放或加载异常时先关它。
- 主配置里没有广告规则、证书和脚本，Mac 直接用不会误解密。

## 首次设置

**两台设备都做：**

1. 先导出旧配置作为备份。
2. 配置 → 右上角 `+` → 粘贴主配置链接 → 下载 → 点它 → 使用配置。
3. 首页选 DMIT 节点，全局路由选「配置」。选「代理」时规则全部不执行：去广告模块的域名拦截失效，国内 App 也绕到海外节点。
4. 设置 → 自动更新：打开「配置」的自动后台更新（间隔 1 天）；手机再打开「模块」的自动更新。iOS 还需要在系统设置里允许 Shadowrocket 后台 App 刷新。

**只在手机做：**

5. 模块 → `+` → 粘贴 `base` 链接。先验证网页、AI、微信、登录、支付和 SSH。
6. HTTPS 解密：主配置 `ⓘ` → HTTPS 解密 → 生成新的 CA 证书 → 安装 → 系统设置里安装描述文件 → 通用 → 关于本机 → 证书信任设置，打开信任。
7. **建一个本地证书模块**（远程主配置每次更新都会覆盖本地修改，证书会丢）：主配置 `ⓘ` → HTTPS 解密 → 证书后面的 `ⓘ` → 复制；模块 → 新建模块，粘贴：

   ```text
   #!name=本机证书（只存在手机上，不要上传）
   [MITM]
   enable = true
   ```

   再在 `[MITM]` 下面加两行：`ca-passphrase` 加等号再写 HTTPS 解密页面「密码」一栏显示的值（每台设备生成的证书密码不同）；`ca-p12` 加等号再粘贴刚复制的证书内容。必须先完成第 6 步的安装和信任，再启用这个模块，否则可能提示 `No PKCS12 Certificates`。这个模块含私钥，只留在手机里。
8. 模块 → `+` → 粘贴 `app-ads` 链接；需要时再加 `response-cleaner`、`youtube`。完全退出目标 App 后重新打开，检查开屏、登录、下单和支付。

某个 App 异常时，先断开 Shadowrocket 试一次：断开后仍异常，就不是规则的问题。断开后正常，再逐个排查：先关 `app-ads`，仍异常再关 `base`。

## 主配置的分流顺序

从上到下逐条匹配，先命中先生效（据社区手册，Shadowrocket 编译时域名类规则先于 IP 类规则）：

| 顺序 | 内容 | 策略 |
|---|---|---|
| 1 | 旧配置开头的手工例外：`edu.cn`、腾讯会议、小红书、`yeah.net`、`flagos.io`、VS Code 两个更新地址、`198.18.3.254`、标准 SSH 端口 22 | DIRECT |
| 2 | 旧配置**全部 257 条显式 PROXY 规则**，原样、原顺序 | PROXY |
| 3 | AI（ChatGPT、Claude、Perplexity、Grok 等）、Google/YouTube、WRDS、GitHub/Docker/Hugging Face、PayPal、Microsoft 在线账户与 Office/Outlook、Apple News | PROXY |
| 4 | Apple：App Store、iCloud、系统更新；Microsoft：Windows/Office 下载、系统更新、VS Code 扩展 | DIRECT |
| 5 | 国内常用 App、银行与支付（微信、QQ、支付宝、淘宝、京东、哔哩哔哩、小红书、美团、知乎、微博、抖音等）以及腾讯 IP 段 | DIRECT |
| 6 | 其余 `.cn` 域名、局域网、解析到中国大陆的 IP | DIRECT |
| 7 | 其余流量 | PROXY |

要点：

- **第 2、3 步排在国内直连之前**，所以旧配置要求代理的站点即使解析到国内 IP，也继续走代理。
- 旧配置里的海外学术站点、Steam、PT 站等 DIRECT 项不再整体继承：解析到海外 IP 时走代理，完整名单见 `data/routing.json` 的 `former_direct_now_proxy`。
- 私人服务器 IP 和私人域名不写进公开仓库。位于中国大陆的服务器（包括非 22 端口的 SSH）会被第 6 步的中国大陆 IP 直连覆盖。确实需要额外私人例外时，把规则加进手机的本地证书模块的 `[Rule]` 段；Mac 上同样新建一个本地模块。
- 规则只处理进入 Shadowrocket 的流量。Mac 终端 SSH、Python 数据库连接是否经过客户端，取决于虚拟网卡和系统代理设置。

## 修改与更新

- 分流数据：`data/manual-direct.list`（开头例外）、`data/legacy-proxy.list`（257 条强制代理）、`data/routing.json`（其余分组）。修改后运行 `make build && make test`，提交到 main，设备下次更新时生效。
- 广告数据：anti-AD、HaGeZi Light、fmz200 去广告插件的静态规则，由 GitHub Actions 每天检查，通过全部检查后自动发布到 main；设备开着自动更新就会拿到。某个 App 被导入规则弄坏时，把它的主机加进 `data/app-ads-overrides.json`。
- 回滚：手机先关最近启用的模块；主配置有问题就切回旧配置备份。固定旧版本时，把链接里的 `main` 换成已知良好提交的完整 SHA。

静态测试覆盖 257 条规则的保留与优先级、手工例外、AI/Google/YouTube/WRDS 代理、SSH、PayPal、Apple/Microsoft 分流、国内直连、局域网和公开文件边界。这不是 iOS/macOS 真机验证。
