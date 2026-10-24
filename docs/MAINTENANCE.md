# 维护、自动更新与回滚

## 文件职责

| 路径 | 用途 |
|---|---|
| `sources/upstreams.json` | 三个自动跟踪的数据源（anti-AD、HaGeZi Light、fmz200 插件）的格式、路径、体积/时效边界和许可 |
| `sources/upstreams.lock.json` | 原始数据和 LICENSE 的 SHA-256；首次快照未解析 Git commit ID，不伪造提交锁 |
| `vendor/`、`licenses/` | 可离线重建的原始快照和许可；`fmz-blockads.plugin` 是整份插件快照，构建时只解析静态部分 |
| `tools/plugin_import.py` | 从 fmz 插件快照提取静态 REJECT 域名/IP（构建时并入去广告①，与其他域名库一起去重）与 `reject` 系列重写（进 app-ads），按需收窄解密主机；从不导入脚本 |
| `data/apps.json` | 15 个实验 App 模块的端点、解密主机、正样例和来源；`connection_rules` 是少数按网址和 User-Agent 拦的明文请求 |
| `data/manual-direct.list` | 旧配置开头的手工直连例外，原样保留在主配置最前面；不写私人服务器 IP/私人域名 |
| `data/legacy-proxy.list` | 旧配置全部 257 条显式 PROXY 规则，原样、原顺序，排在国内直连之前 |
| `data/routing.json`、`tools/profiles.py` | 其余代理/直连分组、已改走代理的旧海外直连名单，以及主配置构建 |
| `data/script-routes.json` | 原创响应过滤器的 3 个限定入口 |
| `scripts/response-cleaner.js` | 原创 JSON 过滤代码，不访问网络、存储或凭据 |
| `data/weibo.json` | 微博完整版模块（去广告⑤）：解密主机、直接回空 JSON 的推广接口、脚本处理的接口路径、开屏广告主机和接口（`splash`），以及任何规则都不许匹配的登录/私信/发布地址 |
| `scripts/weibo.js` | 原创微博 JSON 过滤代码；接口表 `ROUTES`、开屏表 `SPLASH` 与 `data/weibo.json` 一一对应，测试会核对 |
| `sources/scripts.lock.json` | 当前脚本审核指纹和历史脚本保留清单 |
| `data/extra-domains.json` | 自己加的广告域名，进入 base/lite；每条写明原因 |
| `data/allowlist.json` | 从广告库中移除的域名例外；不输出 DIRECT，不改变路由 |
| `data/app-ads-overrides.json` | 对自动导入的 App 广告规则的排除项（主机或单条规则），以及临时「只解密」的排查主机 `observe_hosts` |
| `tools/devicelog.py` | 分析 Shadowrocket 导出的请求日志，只显示目标 App 的条目，见 [设备日志](DEVICE_LOGS.md) |
| `AGENTS.md`、`docs/STATUS.md` | 接手维护的说明与当前进度；`CLAUDE.md` 只导入 `AGENTS.md` |
| `data/policy.json` | 公共后缀/共享根保护、禁止解密的主机、关键网址探针、更新幅度、时效和大小阈值 |
| `dist/` | 自动生成的手机用文件及完整性清单 |
| `reports/` | 构建统计、最近一次自动更新的完整增删 |
| `.cache/` | 本轮检测日志和失败诊断，不提交 |
| `private/` | 本地私人配置输出，不提交、不进入交付 ZIP |

## 构建与测试

```sh
make build
make test
```

构建只读本地数据，不联网。去重只在含义相同的 `DOMAIN` / `DOMAIN-SUFFIX` 间合并，并移除被父后缀规则覆盖的子域。保留 exact DOMAIN 的精确语义，不把它擅自扩大到所有子域。

规则例外优先于拒绝：如父后缀会命中需要保留的登录主机，会移除整个父拒绝项。这样牺牲该父项的覆盖范围，保留更精确的广告子域规则。`never_block_suffixes` 是显式共享根保护表，**不是完整 Public Suffix List（公共后缀列表）**。扩大来源或支持全新域后缀时需要补充保护和审查，不能仅靠语法检查保证无误杀。

检查能发现语法错误、重复、样例上的重写/脚本相互覆盖、被域名规则提前拒绝的目标 API、产物漂移、缺失脚本依赖及常见密钥；主配置还检查 257 条代理规则是否完整且排在国内直连之前、是否误写入可路由的私人 DIRECT 地址、是否依赖远程规则集；广告模块检查重写是否命中 `critical_url_probes` 里的登录/支付/内容网址，解密主机是否落在 `never_mitm_suffixes`（`mitm_exceptions` 里审核过的单个主机除外）。它不能证明所有正则互不相交，不能替代业务实测，也不是通用恶意 JS 检测器。

## GitHub Actions 设置

1. Settings → Actions → General → Workflow permissions 选 **Read and write permissions**。更新作业需要 `contents: write`（直接提交到 main）和 `issues: write`（异常提醒）；普通 CI（Continuous Integration，持续集成）只读。
2. `main` 不要设置“必须通过 PR 合并”的分支保护，或者在保护规则里允许 GitHub Actions 推送；否则自动发布会被拒绝并开出提醒 Issue。
3. 合并后手动运行一次 `Upstream auto update`，确认日志与报告正常。
4. 工作流使用固定提交版本的官方 checkout/upload-artifact，不自动升级（已关闭 Dependabot）；GitHub 淘汰旧运行环境导致运行失败时，提醒 Issue 会报出来，届时手动升级版本号。不执行上游脚本或在线转换器。

参考：[GitHub 工作流触发说明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。

## 自动更新与异常提醒

每天北京时间约 12:17（GitHub 可能延迟）运行 `Upstream auto update`：

1. 先校验当前 main；再下载三个来源的纯文本数据和 LICENSE，逐个检查格式、体积、时间、数量、许可哈希和增删幅度（单次不超过 20%）。
2. 通过检查的来源更新快照；**未通过的来源继续用旧快照**，不影响其他来源。
3. 重建全部产物，跑完整校验和测试，全部通过后以仓库主人的身份（GitHub 隐私邮箱，贡献者列表里不会出现机器人）直接提交并推送到 main。推送时 main 若被别人改过，就从最新 main 重新跑，最多三次，不覆盖他人的提交。
4. 有来源被拦截或任何检查失败时，运行会标红，并在仓库开出（或追加到）标题为「上游自动更新需要关注」的 Issue，附带报告；之后某次运行全部正常，会自动关闭这个 Issue。

设备端：手机和 Mac 打开 Shadowrocket 的配置/模块自动更新，就会在下次更新时拿到新规则。

仓库 60 天没有任何提交时，GitHub 会自动停用定时任务。每天的自动更新提交通常能让仓库保持活跃；长期没有新提交时，到 Actions 页面重新启用。

需要你处理的情况只有 Issue 里列出的几类：

- **许可变化**：读新许可、确认可以再分发后，更新 `licenses/` 文件和 `sources/upstreams.lock.json` 的 `license_sha256`。
- **增删超过 20% 或格式变化**：先看上游是否出错。确认是正常改版，就在本地运行 `make update` 时临时调整 `data/policy.json` 的阈值或 `sources/upstreams.json` 的数量边界，检查 diff 后提交。
- **长期失联**：继续使用已托管的快照，不把广告域名的 NXDOMAIN 当成删除理由；需要换源时核对许可与格式，建立快照与哈希后一起提交。

每次自动提交都写入 `reports/update.md` 和 `reports/update.json`（增删明细），需要追查时看提交历史即可。极端情况下进程在多文件替换之间中断，下次哈希校验会拒绝构建并报警，检出上一有效提交即可恢复。

## 调整覆盖范围

| 想做的事 | 改哪里 |
|---|---|
| 新出现的广告域名，直接拦 | `data/extra-domains.json`（进入 base/lite）。主配置分组里已有的域名（如 `weibo.com` 直连）下的子域名也可以直接写：设备日志证实 `DOMAIN-SUFFIX` 和 `DOMAIN` 都能压过主配置的分组规则 |
| 某 App 的广告接口，按路径拦 | `data/apps.json`，附正样例和同主机登录/支付负样例 |
| App 绕过域名直接连 IP，按路径的规则碰不到 | `data/apps.json` 的 `connection_rules`：按明文 HTTP 网址和这个 App 的 User-Agent 拦它的调度请求（例：闲鱼的 `/amdc/mobileDispatch`），附命中和不命中的样例；生成为 app-ads 的 `AND,((URL-REGEX,…),(USER-AGENT,…)),REJECT` |
| 某个域名被误拦 | `data/allowlist.json`（base、lite、app-ads 都会放行） |
| 自动导入的规则让某个 App 出问题 | `data/app-ads-overrides.json` 的 `exclude_hosts` 填该 App 的主机（包含子域），该主机不再被导入规则拦截、重写或解密；只想去掉某一条时填 `exclude_patterns` |
| 再跟踪一个去广告插件 | 在 `sources/upstreams.json` 加一项 `"format": "loon-plugin-static", "role": "app-ads"`，下载快照、写入 `upstreams.lock.json` 的哈希；构建会把它的静态域名并入去广告①、重写并入 app-ads |
| 微博完整版又出现某种广告或推荐卡片 | 抓日志找到接口。路径已在 `data/weibo.json` 里，就改 `scripts/weibo.js` 里对应的处理函数；新接口同时加进 `data/weibo.json` 的 `scripts` 和脚本的 `ROUTES`。两种情况都在 `tests/fixtures/weibo.json` 加样例，并按下文更新脚本哈希与审核说明 |
| 想在日志里看到某个主机的完整地址（找广告接口） | `data/app-ads-overrides.json` 的 `observe_hosts`：只解密，不拦截也不改写；规则写好后删掉这一项 |
| 永不解密或永不误拦的关键站点 | `data/policy.json` 的 `never_mitm_suffixes`、`critical_url_probes`。银行、支付的主域名都要写进 `never_mitm_suffixes` |
| 某家银行的开屏图片放在单独的图片主机上，想让 fmz200 的规则拦它 | 先用日志确认这台主机只放图片（CDN、静态资源），不是登录、转账所在的主机，再把它连同理由写进 `data/policy.json` 的 `mitm_exceptions`；只能写单个主机，不能写通配 |

改完运行 `make build && make test`，提交到 main。

## 第三方脚本（YouTube）

`vendor/maasea-youtube.response.js` 是固定版本的第三方脚本，`sources/scripts.lock.json` 的 `third_party` 记录了它的哈希、许可、审核结论和敏感 API 的出现次数。脚本内容、许可或 API 次数任何一项变化，构建都会停下。上游出新版本时，自动更新只会开出「第三方脚本有新版本，需要审核」的 Issue，不会替换现有副本，因为脚本能接触解密后的 YouTube 请求。审核新版本时：读 diff，确认仍不调用网络/通知接口，更新 vendor 副本、哈希、次数和审核说明，运行 `make test`。

## 添加 App 与响应脚本

先从自己设备获取最小必要的、脱敏的域名和接口信息，确认是不是广告专用。混合业务 API 不整域拒绝。每条路径至少增加正样例，以及同主机登录、支付、订单不匹配的负样例；保持 App 模块独立，以便一键关闭。

`data/apps.json` 中的既有状态都是 `experimental-unverified-on-device`。iOS 验收后请记录 App 版本、iOS/Shadowrocket 版本、日期及广告位置到 `docs/DEVICE_RESULTS.md`，不要只写“永久有效”。自写规则与脚本是人工维护项；fmz 插件的静态规则随上游自动跟踪。该项目不宣称能自动修复所有 App 接口改动。

修改响应脚本时，读完代码和 diff，确认限定入口及未知结构原样返回，再扩展 `tests/fixtures/responses.json`。修改 `sources/scripts.lock.json` 当前 SHA-256 与审核说明之前需人工审核，不提供“下载远程 JS 然后自动批准”的命令。

若脚本曾经发布，把旧 `dist/scripts/...<hash>.js` 的路径、SHA-256 和审核说明加入 `archives` 清单并保留文件。更新当前源文件与 hash 后重建；禁止删除仍被旧模块引用的脚本。编译器不会信任目录中随意出现的额外 JS。

## 版本回滚

- 紧急恢复：手机关闭最近启用的 App/脚本模块；通用模块有误杀则关闭 base，或换 lite。
- GitHub 回滚：对引入问题的提交执行 `git revert`，测试通过后推送到 main；设备更新配置/模块并重连。自动更新若再次带回同一问题，用 `data/allowlist.json` 或 `data/app-ads-overrides.json` 永久排除。
- 临时固定历史：把模块 Raw URL 中的 `main` 改为已知良好提交的完整 SHA，再导入该模块。域名模块已内嵌规则，因此可直接固定整份版本；旧脚本通过保留的哈希文件继续可用。

## 发布前

`make test` 检查产物与常见秘密模式；人工确认没有私人配置/抓包/证书。公共文件只包含公开域名与广告接口。不要把 `.gitignore` 当作已提交秘密的补救；若误提交过密钥，应先撤销并清理历史再公开。
