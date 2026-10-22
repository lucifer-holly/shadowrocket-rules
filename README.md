# Personal Shadowrocket Adblock

给 iPhone / iPad 使用的个人去广告规则工程，也提供 **手机和 Mac 共用的远程分流主配置**。手机额外启用广告模块，Mac 默认只做分流。保留已有 DMIT 节点和「配置」路由模式；仓库不包含节点、账号、证书或私人服务器地址。

首次交付（2026-10-21）：anti-AD + HaGeZi Light 的本地快照，编译后 143,417 条域名规则；14 个 App 独立模块、15 条路径重写；哔哩哔哩与知乎的 3 条 JSON 响应处理路由。全部为**离线检查与合成样例验证，尚未进行 iOS 真机验证**。域名总数不等于广告拦截率。

## 先用起来

共用主配置订阅：

```text
https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf
```

这条 URL 是脱敏的公共模板，不含私人地址或私人旧配置中的全部例外。需要私人 SSH 和原有强制代理规则时，将它们**合并在一份本地私人主配置**中；两端导入同一份文件即可，不必再加载独立的私人路由模块。私人主配置保留所有原有显式 PROXY 规则，并通过公共规则集 URL 更新常用分流数据，不内置广告库或启用解密。使用方法见 [两端共用配置](docs/DEVICE_PROFILES.md)。私人地址、证书和节点不得上传公共仓库。

1. 备份当前配置；保持原 DMIT 节点和「配置」模式。暂停重叠的第三方去广告模块。
2. 在「配置 → 模块」导入 `dist/modules/base.sgmodule`。该文件内嵌域名表，不需要证书，也不依赖任何上游订阅。若出现内存压力或连接频繁断开，换 `lite.sgmodule`，两者二选一。
3. 需要去 App 开屏时，逐个导入 `dist/modules/apps/` 下的模块。确认功能正常后，可用 `apps-all.sgmodule` 替代独立模块；两种方式二选一。它们使用 HTTPS 路径重写，需要手机本地生成并信任 HTTPS 解密证书。操作见 [安装说明](docs/INSTALL.md)。
4. 信息流与哔哩哔哩开屏 JSON 处理可额外启用 `response-cleaner.sgmodule`。当前地址已指向自己的仓库；脚本仅来自本仓库，文件名固定到内容哈希，不自动下载上游 JS。
5. 在手机更新模块，重新连接，完全退出目标 App 后再打开。检查正常登录、下单、支付、视频播放、Safari、SSH 和国内外路由。发现问题先关闭对应 App 模块。

模块导入入口和证书菜单名称可能随 Shadowrocket/iOS 版本变化。支持的语法针对 Shadowrocket 编译，不把 Loon/QX 文件直接套用；真正的解析和业务行为仍需在手机验收。

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

GitHub Actions 每天北京时间约 **12:17** 检查两个实际收录的数据源，并观察 fmz200 参考插件是否变化。GitHub 定时触发可能延迟，首次上传后先手动运行一次 `Upstream candidate update`。

更新只下载纯文本规则和 LICENSE。通过格式、体积、时间、数量、许可哈希及增删幅度检查后，重建本仓库产物，运行完整测试，再创建**等待你审核的 Pull Request（拉取请求）**。它不会自动合并；你合并后手机更新自己的模块才会使用新规则。

- 源失联、HTML 错误页、空列表、格式变更、超过 14 天未生成、许可变化或超过 20% 的规则增删，均阻止候选发布，保留旧版。
- 已有待审更新 PR 时，不覆盖其分支；本轮仍生成健康报告，等你合并或关闭后再提出新候选。
- App 端点与脚本需要人工维护。fmz200 的整包变化只是复核提醒；不自动吸收其脚本、jq、付费权益或平台专用功能。
- 设置见 [维护说明](docs/MAINTENANCE.md)，包含 Actions 权限、分支保护、失联处理和回滚。

## 常用维护入口

| 任务 | 编辑/执行 |
|---|---|
| 增加广告域名 | `data/extra-domains.json`，写明原因 |
| 修复误杀 | `data/allowlist.json`，添加精确例外并重建 |
| 新增 App 路径 | `data/apps.json`，补充正反样例和限定 MITM 主机 |
| 查看规则是否匹配 | `python3 tools/explain.py ads.example.com` |
| 离线重建 | `make build` |
| 全部离线检查 | `make test` |
| 只检查上游，不改快照 | `python3 tools/upstream.py --check` |
| 本地准备更新候选 | `make update`，审查 Git diff 后自行提交 |
| 上传后检查自己的 Raw 链接 | `python3 tools/check_links.py` |

文件职责与具体命令见 [维护说明](docs/MAINTENANCE.md)。[调研与筛选](docs/RESEARCH.md) 记录了来源、维护证据、许可和取舍；[验收与故障排查](docs/TROUBLESHOOTING.md) 说明技术限制。

## 能做到的范围

域名规则覆盖 App 与 Safari 的独立广告/跟踪请求；可选重写与脚本覆盖列明的接口。Shadowrocket 不负责 Safari 页面元素隐藏、App UI 布局修改，也不能保证过滤证书锁定、加密/Protobuf 响应、本地素材或视频服务端拼接广告。YouTube、抖音等没有“全去广告”的承诺。

仓库采用 GPL-3.0-only；第三方快照保留各自许可与署名，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。许可不明确的脚本没有被打包为运行依赖。
