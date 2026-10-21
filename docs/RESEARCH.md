# 调研与取舍（2026-10-21）

读取了用户提供的 splash-core 模块和重建版仓库，随后联网检查下列项目。实际收录的两个数据源完整下载、保留许可并记录 SHA-256；最后一次健康检查见 `reports/upstream-health.md`。没有把星数或项目标题当作兼容性证据。

| 项目 | 本次检查到的维护证据 | 许可情况 | 决策 |
|---|---|---|---|
| [anti-AD](https://github.com/privacy-protection-tools/anti-AD) | 可下载 `anti-ad-surge.txt`，版本 `20261020063107`，103,677 条原始规则；GitHub 元数据 pushed_at 为 2026-10-19 UTC | MIT；保留原版权文本 | 收录为中文场景主源，直接解析 Surge DOMAIN/DOMAIN-SUFFIX 语法 |
| [HaGeZi DNS Blocklists](https://github.com/hagezi/dns-blocklists) | Light 快照 Last modified 为 2026-10-20 14:52 UTC，66,425 条；README 提供多档列表 | GPL-3.0；保留完整文本 | 仅选 Light 作通用补充，与 anti-AD 规范化去重；单独生成 Lite |
| [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts) | API 元数据 pushed_at 为 2026-10-01 UTC；实际插件头日期 2026-09-10，当前可下载 | GPL-3.0；项目同时汇集多来源功能 | 只摘录 4 条广告静态端点、限制边界并转换；不直接启用整包，监控变化供人工复核 |
| [Cats-Team/AdRules](https://github.com/Cats-Team/AdRules) | API 元数据 pushed_at 为 2026-10-21 UTC；默认分支 `script` | 默认分支合并工具为 0BSD，不能据此把输出分支及所有上游规则认作 0BSD | 不叠加；已有两源重叠很多，减少许可与格式链条 |
| [AdGuardSDNSFilter](https://github.com/AdguardTeam/AdGuardSDNSFilter) | API 元数据 pushed_at 为 2026-10-21 UTC | GPL-3.0 | 备选来源；当前无需再堆叠第三份通用聚合表 |
| [ddgksf2013/Rewrite](https://github.com/ddgksf2013/Rewrite) / [Scripts](https://github.com/ddgksf2013/Scripts) | API 元数据显示 Rewrite 最近推送 2026-06-15，Scripts 为 2026-10-14 UTC | 本次检查未确认可用于本项目公开再分发的通用脚本许可 | 仅调研，不打包、不远程引用其脚本 |
| [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | 仓库当前可访问，含大量多平台规则和外部资源；本轮部分 API 受到 403 限制，未据此推断停更 | 根许可 GPL-2.0，README 有特别声明，外部资源还须逐项检查 | 不作为当前自动导入源；避免混合出处、特别声明与重复聚合 |
| [app2smile/rules](https://github.com/app2smile/rules) | README 当前可访问，提供 Surge/Loon/QX 的 Bilibili 等模块 | 本轮未确认目标脚本的再分发许可，直接 LICENSE 路径 404 | 不打包；其二进制/gRPC 方案也超出本次原创 JSON 过滤器的范围 |

## 为什么不是整包转换

Loon 的 `[Argument]`、`http-response` 行、jq、mock-response，Quantumult X 的 rewrite 格式和 API，并不等同于 Shadowrocket 原生配置。本次 fmz 插件还包含非去广告的账号/权益相关逻辑；即使整包能解析，也不符合本任务范围。

因此自动渠道只接收指定格式的数据，不吸收脚本 URL。4 条新增静态路径保留原始片段、来源和许可，转换为 Shadowrocket 原生 `pattern - action`，每条附正样例及同主机关键业务负样例。已有十个 App 的路径来自附件，也重新限制边界。使用者仍需真机验证。

原创 JSON 过滤器只做明确广告标记删除与两个已知开屏数组清空，失败时不改响应。对于当前 Bilibili App 走 gRPC 而非对应 JSON 入口的情况，此脚本不会生效；没有把 JSON 样例测试当成全版本覆盖证明。

## 技术参考及验证边界

- [LOWERTOP/Shadowrocket 社区手册](https://github.com/LOWERTOP/Shadowrocket/wiki)：了解模块追加与有限解密等用法。该项目明确为**非官方**；本仓库静态检查不是官方客户端解析器，也未声称在 iOS 上验证兼容性。
- [Quantumult X 作者仓库](https://github.com/crossutility/Quantumult-X)：不同平台脚本与重写机制需要适配，不能通过换扩展名保证兼容。
- [Apple Safari Content Blocker 文档](https://developer.apple.com/documentation/safariservices/creating-a-content-blocker)：Safari 的内容拦截扩展是独立机制；Shadowrocket 网络规则不能代替页面元素隐藏。
- [GitHub 工作流触发](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)、[事件说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)：据当前说明处理自动 PR 检查批准、默认分支调度和失活暂停。

实际测试使用当前下载的原始数据与本地工具；没有对广告接口发送真实业务请求，没有导入用户证书、登录账号或访问付款流程。所有 App 效果和路由仍待用户设备验收。
