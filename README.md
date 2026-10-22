# Personal Shadowrocket Adblock

个人 Shadowrocket 规则仓库：**手机和 Mac 共用一个远程主配置**（国内直连、国外代理、旧配置要求代理的站点全部继续代理），手机再加去广告模块（域名拦截、开屏与应用内广告）。保留自己的 DMIT 节点和「配置」路由模式。所有文件都放在本仓库，第三方规则以快照形式保存并由 GitHub Actions 每天跟踪；仓库不包含节点、账号、证书或私人服务器地址。

当前数据：主配置保留旧配置全部 257 条显式 PROXY 规则；anti-AD + HaGeZi Light 编译后 143,415 条广告域名；`app-ads` 模块含 fmz200 去广告插件的 1,133 条静态拒绝重写、2,590 条广告域名，以及 15 条自维护路径规则；另有哔哩哔哩与知乎的 3 条 JSON 响应处理。全部为**离线检查与合成样例验证，尚未进行真机验证**。规则数量不等于广告拦截率。

## 先用起来

| 用途 | 设备 | 链接 |
|---|---|---|
| 主配置（「配置」页导入） | 手机 + Mac | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf` |
| 通用广告域名拦截（「模块」页） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/base.sgmodule` |
| 开屏与应用内广告（需证书） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/app-ads.sgmodule` |
| 哔哩哔哩/知乎信息流（可选，需证书） | 手机 | `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/response-cleaner.sgmodule` |

1. 备份旧配置。两台设备都在「配置」页从 URL 添加主配置并使用，首页选 DMIT 节点，路由选「配置」，打开配置与模块的自动后台更新。
2. 手机在「模块」页添加 `base`（资源不足换 `lite`，二选一），先验证网页、AI、微信、登录、支付和 SSH。
3. 手机生成并信任 HTTPS 解密证书，**再建一个只存在手机上的本地证书模块**，否则远程主配置更新后证书会失效。然后添加 `app-ads`，需要时加 `response-cleaner`。
4. 完全退出目标 App 后重新打开，检查开屏、登录、下单、支付和视频播放。异常时先关 `app-ads`，再关 `base`。

逐步操作、证书模块模板、分流顺序见 [两端共用配置](docs/DEVICE_PROFILES.md)；证书与模块细节见 [安装说明](docs/INSTALL.md)。菜单名称可能随 Shadowrocket/iOS 版本变化，真实解析和业务行为需要在设备上验收。

## 建自己的 GitHub 仓库

本地需要 Python 3.10+、Node.js 20+。没有 Python 包或 npm 包依赖。

```sh
python3 tools/configure.py --repo YOUR-USERNAME/shadowrocket-rules
make test
```

把 `YOUR-USERNAME/shadowrocket-rules` 换成你决定使用的公开仓库。上传前再次运行测试。仓库地址已配置为 `lucifer-holly/shadowrocket-rules`。发布后在 Actions 查看校验结果；后续规则更新经拉取请求审核后合并。

[订阅地址表](docs/SUBSCRIPTIONS.md) 会随上面的命令自动生成。基础模块订阅形式：

```text
https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/base.sgmodule
```

这是「模块 URL」，不要加进节点订阅。若使用主配置合并方式，可参考 `dist/config/adblock.fragment.conf`；也提供无节点的 `adblock-example.conf`。示例配置不能替代你原有的私人分流和 SSH 设置，优先用模块。

## 自动更新如何工作

GitHub Actions 每天北京时间约 **12:17** 检查三个第三方数据源：anti-AD、HaGeZi Light、fmz200 去广告插件。GitHub 定时触发可能延迟，首次上传后先手动运行一次 `Upstream candidate update`。

更新只下载纯文本规则和 LICENSE。通过格式、体积、时间、数量、许可哈希及增删幅度检查后，重建本仓库产物并运行完整测试，然后创建**等待你审核的 Pull Request（拉取请求）**；你合并后，设备下次自动更新模块时生效。

- 源失联、HTML 错误页、空列表、格式变更、过期、许可变化或超过 20% 的规则增删，均阻止候选发布，保留旧版。
- fmz200 插件只导入静态 REJECT 域名/IP、`reject` 系列 URL 重写和插件自己列出的解密主机；脚本、jq、正文改写、跳转和账号/权益相关内容一律不导入。解密主机进一步收窄到被导入规则实际需要的范围，并排除登录、支付、银行、AI、Google、Apple 等受保护主机。
- 已有待审更新 PR 时，不覆盖其分支；本轮仍生成健康报告。
- 分流数据（`data/`）由你人工维护，不受上游更新影响。
- 设置见 [维护说明](docs/MAINTENANCE.md)，包含 Actions 权限、分支保护、失联处理和回滚。

## 常用维护入口

| 任务 | 编辑/执行 |
|---|---|
| 增加广告域名 | `data/extra-domains.json`，写明原因 |
| 修复误杀 | `data/allowlist.json`，添加精确例外并重建 |
| 新增 App 路径 | `data/apps.json`，补充正反样例和限定 MITM 主机 |
| 调整分流 | `data/manual-direct.list`、`data/legacy-proxy.list`、`data/routing.json` |
| 查看规则是否匹配 | `python3 tools/explain.py ads.example.com`（含 app-ads） |
| 离线重建 | `make build` |
| 全部离线检查 | `make test` |
| 只检查上游，不改快照 | `python3 tools/upstream.py --check` |
| 本地准备更新候选 | `make update`，审查 Git diff 后自行提交 |
| 上传后检查自己的 Raw 链接 | `python3 tools/check_links.py` |

文件职责与具体命令见 [维护说明](docs/MAINTENANCE.md)。[调研与筛选](docs/RESEARCH.md) 记录了来源、维护证据、许可和取舍；[验收与故障排查](docs/TROUBLESHOOTING.md) 说明技术限制。

## 能做到的范围

域名规则覆盖 App 与 Safari 的独立广告/跟踪请求；可选重写与脚本覆盖列明的接口。Shadowrocket 不负责 Safari 页面元素隐藏、App UI 布局修改，也不能保证过滤证书锁定、加密/Protobuf 响应、本地素材或视频服务端拼接广告。YouTube、抖音等没有“全去广告”的承诺。

仓库采用 GPL-3.0-only；第三方快照保留各自许可与署名，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。许可不明确的脚本没有被打包为运行依赖。
