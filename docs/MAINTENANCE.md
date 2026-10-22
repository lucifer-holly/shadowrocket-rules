# 维护、审核与回滚

## 文件职责

| 路径 | 用途 |
|---|---|
| `sources/upstreams.json` | 两个自动更新的纯数据源、格式、路径、体积边界和许可 |
| `sources/upstreams.lock.json` | 原始数据和 LICENSE 的 SHA-256；首次快照未解析 Git commit ID，不伪造提交锁 |
| `vendor/`、`licenses/` | 可离线重建的原始快照和许可；fmz 文件仅保留 4 条静态端点 |
| `sources/watch.json` | fmz 整包字节指纹，仅提醒人工复核；不导入/执行 |
| `data/apps.json` | 14 个实验 App 模块的端点、解密主机、正样例和来源 |
| `data/routing.json`、`tools/profiles.py` | 两端共用主配置的公开服务分流与构建；不导入私人配置 |
| `tools/personalize.py` | 在本地合并私人直连和旧配置全部显式 PROXY 规则；拒绝把输出写入公开仓库目录 |
| `data/script-routes.json` | 原创响应过滤器的 3 个限定入口 |
| `scripts/response-cleaner.js` | 原创 JSON 过滤代码，不访问网络、存储或凭据 |
| `sources/scripts.lock.json` | 当前脚本审核指纹和历史脚本保留清单 |
| `data/allowlist.json` | 从广告库中移除的域名例外；不输出 DIRECT，不改变路由 |
| `data/policy.json` | 公共后缀/共享根保护、更新幅度、时效和大小阈值 |
| `dist/` | 自动生成的手机用文件及完整性清单 |
| `reports/` | 构建统计、已准备候选的完整域名增删 |
| `.cache/` | 本轮检测日志和失败诊断，不提交 |
| `private/` | 本地私人配置输出，不提交、不进入交付 ZIP |

## 构建与测试

```sh
make build
make test
```

构建只读本地数据，不联网。去重只在含义相同的 `DOMAIN` / `DOMAIN-SUFFIX` 间合并，并移除被父后缀规则覆盖的子域。保留 exact DOMAIN 的精确语义，不把它擅自扩大到所有子域。

规则例外优先于拒绝：如父后缀会命中需要保留的登录主机，会移除整个父拒绝项。这样牺牲该父项的覆盖范围，保留更精确的广告子域规则。`never_block_suffixes` 是显式共享根保护表，**不是完整 Public Suffix List（公共后缀列表）**。扩大来源或支持全新域后缀时需要补充保护和审查，不能仅靠语法检查保证无误杀。

检查能发现语法错误、重复、样例上的重写/脚本相互覆盖、被域名规则提前拒绝的目标 API、产物漂移、缺失脚本依赖及常见密钥。它不能证明所有正则互不相交，不能替代业务实测，也不是通用恶意 JS 检测器。

## GitHub Actions 设置

1. 先用 `tools/configure.py --repo owner/repo` 设置真实地址再上传到 `main`，进入 Actions 允许运行工作流。CI 会拒绝 project.json 地址与当前仓库不一致的构建，避免发布失效订阅。
2. 在 Settings → Actions → General 的 Workflow permissions 中，允许 Actions 创建 Pull Request。更新作业需要 `contents: write` 和 `pull-requests: write`；普通 CI（Continuous Integration，持续集成）只读内容。
3. 手动运行 `Upstream candidate update`，确认日志与报告正常。
4. 建议保护 `main`，要求 PR 合并；关闭自动合并。个人仓库如设置必须由另一名审核者批准，唯一维护者可能无法自己完成合并，按实际协作人数配置。
5. 工作流使用固定提交版本的官方 checkout/upload-artifact，并由 Dependabot 提议升级；没有执行上游脚本或在线转换器。

**GitHub Token 的行为：** 根据当前 GitHub 文档，默认 `GITHUB_TOKEN` 创建/更新 PR 时，相应 pull_request 检查会以等待批准的状态创建；在 PR 合并框中点击 **Approve workflows to run** 后运行。更新作业也已在创建 PR 前完成全部检查；若没有出现独立检查，在 Actions → Validate → Run workflow 中选择候选分支手动运行。不要为解决这个问题改用 `pull_request_target` 执行不可信 PR 代码。

参考：[GitHub 工作流触发说明](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。

每日北京时间 12:17 是计划时间，GitHub 可能延迟。公共仓库长时间无活动，定时工作流可能暂停；留意 Actions 状态。没有 GitHub 登录凭据的 ZIP 项目不会自行开始定时任务。

工作流只从受信任 `main` 构建；网络输入只有严格解析的规则文本与 LICENSE。候选分支为 `automation/upstream-<run id>`，不强推，也不覆盖已有待审 PR。已有待审 PR 时仍检查最新来源并保留本轮报告，但等你处理后才发布下一份候选。

## 审核更新

查看 `reports/update.json` 的新增/删除及 `reports/build.json` 的保护项变化，再检查 Git diff。特别留意登录/支付/常用 CDN 是否被加入，或者大量规则突然消失。失败报告在工作流 Summary 和附件 `upstream-report-...` 中，现有发布文件仍可用。

许可字节变化会硬失败；即便只改年份，也需读新文本、确认再分发条件后手动更新许可文件与锁的 `license_sha256`。不要用一键“批准所有基线”掩盖来源变化。

上游中断时，继续使用已经托管的快照；超过 14 天未生成会报警，不把广告域名的 NXDOMAIN 当成自动删除理由。更换来源需核对许可与格式，手动下载、建立快照/哈希，并调整最小数量边界。输入快照和锁文件需一起提交。更新过程中网络/检查失败不会写入输入；极端进程中断若发生在多文件替换之间，下次哈希校验会拒绝构建，重新检出上一有效提交恢复。

## 添加 App 与响应脚本

先从自己设备获取最小必要的、脱敏的域名和接口信息，确认是不是广告专用。混合业务 API 不整域拒绝。每条路径至少增加正样例，以及同主机登录、支付、订单不匹配的负样例；保持 App 模块独立，以便一键关闭。

`data/apps.json` 中的既有状态都是 `experimental-unverified-on-device`。iOS 验收后请记录 App 版本、iOS/Shadowrocket 版本、日期及广告位置到 `docs/DEVICE_RESULTS.md`，不要只写“永久有效”。fmz 的 4 条路径与自写脚本是人工维护项；该项目不宣称能自动修复所有 App 接口改动。

修改响应脚本时，读完代码和 diff，确认限定入口及未知结构原样返回，再扩展 `tests/fixtures/responses.json`。修改 `sources/scripts.lock.json` 当前 SHA-256 与审核说明之前需人工审核，不提供“下载远程 JS 然后自动批准”的命令。

若脚本曾经发布，把旧 `dist/scripts/...<hash>.js` 的路径、SHA-256 和审核说明加入 `archives` 清单并保留文件。更新当前源文件与 hash 后重建；禁止删除仍被旧模块引用的脚本。编译器不会信任目录中随意出现的额外 JS。

## 版本回滚

- 紧急恢复：手机关闭最近启用的 App/脚本模块；通用模块有误杀则关闭 base，或换 lite。
- GitHub 回滚：对引入问题的合并提交执行 Revert PR（回退拉取请求），测试通过后手动合并；手机更新模块并重连。
- 临时固定历史：把模块 Raw URL 中的 `main` 改为已知良好提交的完整 SHA，再导入该模块。域名模块已内嵌规则，因此可直接固定整份版本；旧脚本通过保留的哈希文件继续可用。
- 若使用规则集接入，`RULE-SET` 的 URL 也要固定同一个旧提交；单独回退主配置而仍引用 `main` 规则集并不能固定规则。

## 发布前

`make test` 检查产物与常见秘密模式；人工确认没有私人配置/抓包/证书。公共文件只包含公开域名与广告接口。不要把 `.gitignore` 当作已提交秘密的补救；若误提交过密钥，应先撤销并清理历史再公开。
