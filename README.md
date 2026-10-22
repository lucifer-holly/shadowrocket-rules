# Personal Shadowrocket Adblock

个人 Shadowrocket 规则仓库：**手机和 Mac 共用一个远程主配置**（国内直连、国外代理、旧配置要求代理的站点全部继续代理），手机再加去广告模块（域名拦截、开屏与应用内广告）。保留自己的 DMIT 节点和「配置」路由模式。所有文件都放在本仓库，第三方规则以快照形式保存并由 GitHub Actions 每天跟踪；仓库不包含节点、账号、证书或私人服务器地址。

当前数据：主配置保留旧配置全部 257 条显式 PROXY 规则；anti-AD + HaGeZi Light 约 14 万条广告域名（每天自动更新）；`app-ads` 模块含 fmz200 去广告插件的约 1,100 条静态拒绝重写、约 2,600 条广告域名，以及 15 条自维护路径规则；另有哔哩哔哩与知乎的 3 条 JSON 响应处理。已在主人的 iPhone 上用真实请求日志验证了部分 App（见 [真机验收记录](docs/DEVICE_RESULTS.md)），其余只经过离线检查与合成样例测试。规则数量不等于广告拦截率。

## 先用起来

| 模块列表里显示的名字 | 设备 | 链接 |
|---|---|---|
| 主配置（「配置」页导入，不是模块） | 手机 + Mac | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf` |
| 去广告① 广告域名拦截（免证书） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/base.sgmodule` |
| 去广告② App 开屏与应用内广告（需证书） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/app-ads.sgmodule` |
| 去广告③ 信息流净化·B站/知乎（需证书，可选） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/response-cleaner.sgmodule` |
| 去广告④ YouTube（实验，需证书，可选） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/youtube.sgmodule` |
| 本机证书（你自己建的本地模块，不在仓库里） | 手机 | — |

1. 备份旧配置。两台设备都在「配置」页从 URL 添加主配置并使用，首页选 DMIT 节点，路由选「配置」，打开配置与模块的自动后台更新。
2. 手机在「模块」页添加 `base`（资源不足换 `lite`，二选一），先验证网页、AI、微信、登录、支付和 SSH。
3. 手机生成并信任 HTTPS 解密证书，**再建一个只存在手机上的本地证书模块**，否则远程主配置更新后证书会失效。然后添加 `app-ads`，需要时加 `response-cleaner`、`youtube`（实验）。
4. 完全退出目标 App 后重新打开，检查开屏、登录、下单、支付和视频播放。异常时先关 `app-ads`，再关 `base`。

逐步操作、证书模块模板、分流顺序见 [两端共用配置](docs/DEVICE_PROFILES.md)；证书与模块细节见 [安装说明](docs/INSTALL.md)。菜单名称可能随 Shadowrocket/iOS 版本变化，真实解析和业务行为需要在设备上验收。

## 建自己的 GitHub 仓库

本地需要 Python 3.10+、Node.js 20+。没有 Python 包或 npm 包依赖。

```sh
python3 tools/configure.py --repo YOUR-USERNAME/shadowrocket-rules
make test
```

把 `YOUR-USERNAME/shadowrocket-rules` 换成你决定使用的公开仓库。上传前再次运行测试。仓库地址已配置为 `lucifer-holly/shadowrocket-rules`。发布后在 Actions 查看校验结果；上游规则此后每天自动更新。

[订阅地址表](docs/SUBSCRIPTIONS.md) 会随上面的命令自动生成。基础模块订阅形式：

```text
https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/base.sgmodule
```

这是「模块 URL」，不要加进节点订阅。若使用主配置合并方式，可参考 `dist/config/adblock.fragment.conf`；也提供无节点的 `adblock-example.conf`。示例配置不能替代你原有的私人分流和 SSH 设置，优先用模块。

## 自动更新如何工作

GitHub Actions 每天北京时间约 **12:17** 检查三个第三方数据源：anti-AD、HaGeZi Light、fmz200 去广告插件。全部检查和测试通过后，**自动提交到 main**，设备下次自动更新配置/模块时生效，不需要人工合并。

- 源失联、HTML 错误页、空列表、格式变更、过期、许可变化或单次超过 20% 的增删，只拦住出问题的那个来源，它继续使用旧快照；其他来源照常更新。
- 出现拦截或检查失败时，仓库会自动开出「上游自动更新需要关注」Issue，恢复正常后自动关闭。平时不需要看。
- fmz200 插件只导入静态 REJECT 域名/IP、`reject` 系列 URL 重写和插件自己列出的解密主机；脚本、jq、正文改写、跳转和账号/权益相关内容一律不导入。解密主机收窄到被导入规则实际需要的范围，并排除登录、支付、银行、AI、Google、Apple 等受保护主机。
- 分流数据（`data/`）由你维护，不受上游更新影响。新增或排除覆盖范围见 [维护说明](docs/MAINTENANCE.md#调整覆盖范围)。

## 常用维护入口

| 任务 | 编辑/执行 |
|---|---|
| 增加广告域名 | `data/extra-domains.json`，写明原因 |
| 修复误杀 | `data/allowlist.json`，添加精确例外并重建 |
| 自动导入的规则让某 App 出问题 | `data/app-ads-overrides.json` 的 `exclude_hosts` |
| 新增 App 路径 | `data/apps.json`，补充正反样例和限定 MITM 主机 |
| 调整分流 | `data/manual-direct.list`、`data/legacy-proxy.list`、`data/routing.json` |
| 查看规则是否匹配 | `python3 tools/explain.py ads.example.com`（含 app-ads） |
| 分析手机导出的请求日志 | `python3 tools/devicelog.py 日志.db --app huya --check`，见 [设备日志](docs/DEVICE_LOGS.md) |
| 离线重建 | `make build` |
| 全部离线检查 | `make test` |
| 只检查上游，不改快照 | `python3 tools/upstream.py --check` |
| 本地手动跑一次上游更新 | `make update` |
| 上传后检查自己的 Raw 链接 | `python3 tools/check_links.py` |

文件职责与具体命令见 [维护说明](docs/MAINTENANCE.md)。[调研与筛选](docs/RESEARCH.md) 记录了来源、维护证据、许可和取舍；[验收与故障排查](docs/TROUBLESHOOTING.md) 说明技术限制。

## 给接手维护的 AI agent

先读 [AGENTS.md](AGENTS.md)（维护规则、命令、流程），再读 [docs/STATUS.md](docs/STATUS.md)（当前进度和待办）。设备日志的抓取与分析见 [docs/DEVICE_LOGS.md](docs/DEVICE_LOGS.md)。

## 能做到的范围

域名规则覆盖 App 与 Safari 的独立广告/跟踪请求；可选重写与脚本覆盖列明的接口。Shadowrocket 不负责 Safari 页面元素隐藏、App UI 布局修改，也不能保证过滤证书锁定、加密/Protobuf 响应、本地素材或视频服务端拼接广告。YouTube、抖音等没有“全去广告”的承诺。

仓库采用 GPL-3.0-only；第三方快照保留各自许可与署名，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。许可不明确的脚本没有被打包为运行依赖。
