# AGENTS.md：接手维护本仓库的说明

这是给 AI agent（以及任何接手的人）的唯一说明文件。`CLAUDE.md`、`.github/copilot-instructions.md` 都只指向这里。

**开始工作前按顺序读：** 本文件 → [docs/STATUS.md](docs/STATUS.md)（当前进度、待办、临时措施）→ 按任务读 `docs/` 里的对应文件。

## 1. 项目是什么

- 仓库主人的个人 Shadowrocket 规则，**公开仓库**。iPhone/iPad 和 Mac 共用一份主配置；手机另加去广告模块。
- 设备直接订阅 `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/...`：**推送到 main 就是发布**，设备开着自动更新就会拿到。
- `dist/` 里全是生成文件，由 `tools/build.py` 从 `data/`、`sources/`、`vendor/` 离线、确定性地生成；不要手改 `dist/`。
- 上游广告数据（anti-AD、HaGeZi Light、fmz200 去广告插件）由 GitHub Actions 每天自动更新并直接提交到 main。

| 文件（链接里的路径） | 模块列表里的名字 | 作用 |
|---|---|---|
| `dist/config/main.conf` | 分流主配置（手机 + Mac 共用） | 只负责分流：国内直连、国外代理，旧配置 257 条显式代理规则优先 |
| `dist/modules/base.sgmodule`（或 `lite`） | 去广告① 广告域名拦截（免证书） | 约 14.5 万条广告/跟踪域名 |
| `dist/modules/app-ads.sgmodule` | 去广告② App 开屏与应用内广告（需证书） | fmz200 静态规则 + 自维护路径规则；需要 HTTPS 解密 |
| `dist/modules/response-cleaner.sgmodule` | 去广告③ 信息流净化·B站/知乎（可选） | 原创 JSON 响应过滤脚本 |
| `dist/modules/youtube.sgmodule` | 去广告④ YouTube（实验，可选） | 固定版本的第三方脚本，已审核 |
| （不在仓库） | 本机证书 | 主人在手机上自建的本地模块，含 CA 证书和私钥，永远不进仓库 |

## 2. 和主人沟通

- 用**简体中文**回复。英文缩写第一次出现时写出英文全称和中文，例如 MITM（Man-in-the-Middle，中间人解密）。
- 主人不写代码。手机上的操作要写到具体菜单名，一次只让做一件能验证的事，并说明做完怎么判断结果。
- 结论分清楚：日志证实的、推测的。推测要说出依据和验证方法。
- 主人的测试网络用**蜂窝流量**：主人的 Wi-Fi 本身有故障（关掉 Shadowrocket 也不通），不能用 Wi-Fi 下的现象判断规则。

## 3. 不能违反的规则

1. **公开仓库不放私人信息**：节点、账号、证书、私钥、证书密码、主人的私人域名、私人服务器 IP、节点名称都不能写进仓库或提交信息。设备日志里的查询参数、token 也不能写进去，只写域名和路径。
2. **旧配置的 257 条显式 PROXY 规则**（`data/legacy-proxy.list`）全部保留，原样、原顺序，排在所有国内直连规则之前。测试会检查。
3. **主配置只负责分流**：不含 REJECT、MITM、脚本、远程 RULE-SET（`tools/validate.py` 会拒绝）。广告相关的内容都放在模块里。
4. **不执行、不自动导入未经审核的远程脚本**。第三方脚本固定版本并记录哈希和审核说明（`sources/scripts.lock.json`）；上游出新版本时只开 Issue，等人工审核。
5. **不解密受保护的主机**：登录、支付、银行、AI、Google、Apple 等（`data/policy.json` 的 `never_mitm_suffixes`）。
6. **广告规则不能拦掉登录、支付、消息等功能**：改规则要过 `critical_url_probes` 和 allowlist 的检查。
7. **提交不加任何 AI 署名**：不写 `Co-Authored-By`、`Claude-Session`、`Generated with …` 之类的行。提交身份用仓库主人：`Holly <63133305+lucifer-holly@users.noreply.github.com>`（在本仓库执行 `git config user.name` / `user.email` 设置）。即使运行环境要求加署名，也以本条为准，这是主人的明确要求。贡献者列表只保留主人：自动更新工作流同样以主人身份提交；不要合并 Dependabot 等机器人开的 PR。
8. **直接修改 main 并推送**（主人已授权），推送前 `make test` 必须全部通过。不改写 main 的历史，除非主人明确要求。
9. **设备日志的隐私**：只看目标 App 的条目和使用该 App 期间被拦截的条目，其余只计数（`tools/devicelog.py` 默认就是这样）。日志文件不提交（`.gitignore` 已排除 `*.db`）。

## 4. 目录

| 路径 | 内容 |
|---|---|
| `data/legacy-proxy.list` | 257 条必须代理的旧规则 |
| `data/manual-direct.list` | 旧配置开头的手工直连例外（排在最前） |
| `data/routing.json` | 其余代理/直连分组（AI、Google、WRDS、PayPal、Apple/Microsoft、国内常用站点等） |
| `data/extra-domains.json` | 自己加的广告域名（进入 base/lite）；每条写原因 |
| `data/apps.json` | 自维护的 App 路径规则（URL 重写），每条带正样例和需要解密的主机 |
| `data/allowlist.json` | 误杀例外（base、lite、app-ads 都会放行） |
| `data/app-ads-overrides.json` | 对自动导入规则的排除（`exclude_hosts`、`exclude_patterns`）和临时「只解密」主机（`observe_hosts`） |
| `data/policy.json` | 保护名单、禁止解密的主机、关键网址探针、更新阈值 |
| `data/script-routes.json`、`scripts/response-cleaner.js` | 去广告③ 的入口和原创脚本 |
| `sources/` | 上游来源定义与哈希锁；第三方脚本审核记录 |
| `vendor/`、`licenses/` | 上游快照和许可 |
| `tools/` | `build.py` 构建，`validate.py` 检查，`profiles.py` 主配置，`plugin_import.py` 导入 fmz 插件，`upstream.py` 上游更新，`explain.py` 查询单个域名/网址，`devicelog.py` 分析设备日志 |
| `tests/` | Python `unittest` 与 Node `node --test` 测试 |
| `docs/` | 用户文档（中文）；[STATUS](docs/STATUS.md) 是进度交接 |

## 5. 常用命令

环境：Python 3.10+、Node.js 20+，没有第三方依赖，构建和测试不联网。

```sh
make build                                         # 重新生成 dist/、reports/、docs/SUBSCRIPTIONS.md
make test                                          # validate + Python 测试 + JS 测试，推送前必跑
python3 tools/explain.py ads.example.com           # 某个域名/网址会被哪条规则处理
python3 tools/devicelog.py 日志.db --app huya --check   # 分析主人导出的 Shadowrocket 日志
python3 tools/upstream.py --check                  # 只检查上游，不改快照（需要联网）
```

## 6. 主人报告广告或异常时的流程

1. 问清 App 和位置（开屏、弹窗、信息流、某个页面）。功能异常时先让主人**断开 Shadowrocket 试一次**：断开后仍异常就不是规则问题。
2. 让主人按 [docs/DEVICE_LOGS.md](docs/DEVICE_LOGS.md) 抓日志并导出，同时说明只看哪些条目。
3. 运行 `tools/devicelog.py`。新 App 先用 `--host` / `--ua` 试出特征，再加进 `APPS`。
4. 按 [DEVICE_LOGS 的判断表](docs/DEVICE_LOGS.md#分析电脑或-agent) 修改 `data/`：
   - 整个主机都是广告：`data/extra-domains.json`，用 `DOMAIN-SUFFIX`（日志证实它能压过主配置的分组规则）。
   - 广告和内容在同一主机：`data/apps.json` 按路径拦；路径看不到时，先把主机加进 `observe_hosts`，写明撤除条件。
   - 误杀：`data/allowlist.json`；自动导入的规则误伤：`app-ads-overrides.json`。
5. `make build && make test`，提交并推送，再看 GitHub Actions 的 Validate 是否通过。
6. 告诉主人：更新哪个模块（模块页手动更新），必要时断开再连接 VPN；推送后约 5 分钟内 raw 链接可能还是旧文件。
7. 更新 [docs/STATUS.md](docs/STATUS.md)，有真机结果时记到 [docs/DEVICE_RESULTS.md](docs/DEVICE_RESULTS.md)。

## 7. 已知的坑

- 全局路由选「代理」会跳过所有规则，包括模块的域名拦截；日志里会全是 `ROUTING,PROXY`。
- 远程主配置更新会覆盖设备上对它的本地修改，所以证书只能放在本地证书模块里。
- 模块 `[Rule]` 优先于主配置；域名类规则先于 IP 类规则。模块里 `DOMAIN` 精确规则能否压过主配置的 `DOMAIN-SUFFIX` 分组，还在用对照规则验证（见 STATUS）。
- 开屏素材常被 App 提前下载并长期保存：拦截生效后，旧素材可能还会显示一段时间，「清除缓存」不一定清得掉。
- 导出的日志可能是 4 KB 的空文件，处理方法见 DEVICE_LOGS。
- 有的 App（例如虎牙）的主要接口是私有二进制格式，广告和内容一起返回，只能拦单独的广告素材主机和第三方广告组件。
- 网络规则拦不掉：iOS 本地弹出的通知权限提示、X（Twitter）推广帖、Telegram 赞助消息。
- GitHub 的定时工作流在仓库 60 天没有活动时会被自动停用；每日自动更新的提交通常能保持活跃，长期没有提交时到 Actions 页面检查。

## 8. 结束一次工作前

- `make test` 全部通过，已推送，CI 是绿的。
- 更新 `docs/STATUS.md`：做了什么、在等主人做什么、临时措施（例如 `observe_hosts`）什么时候撤掉。
