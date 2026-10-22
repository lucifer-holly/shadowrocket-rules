# AGENTS.md

接手维护本仓库的说明。先读本文件，再读 [docs/STATUS.md](docs/STATUS.md)（进度与待办）；细节在下面链接的文档里，这里不重复。

## 项目

仓库主人的个人 Shadowrocket 规则，**公开仓库**。手机和 Mac 共用 `dist/config/main.conf`（只负责分流），手机另加 `dist/modules/` 里的去广告模块。设备订阅 `https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/...`，**推送到 main 就是发布**。`dist/` 全部由 `tools/build.py` 从 `data/`、`sources/`、`vendor/` 离线生成，不要手改。

- 模块与订阅链接：[README](README.md)；文件分工与改哪里：[MAINTENANCE](docs/MAINTENANCE.md)
- 设备日志的抓取与分析：[DEVICE_LOGS](docs/DEVICE_LOGS.md)；技术限制：[TROUBLESHOOTING](docs/TROUBLESHOOTING.md)

## 和主人沟通

- 用简体中文；英文缩写第一次出现时写出英文全称和中文。
- 主人不写代码：手机上的操作写到具体菜单名，一次一步，并说明怎么判断结果。
- 分清日志证实的和推测的。
- 测试用蜂窝流量：主人的 Wi-Fi 本身有故障，不能据此判断规则。

## 硬性规则

1. 公开仓库不放私人信息：节点、账号、证书、私钥、证书密码、私人域名、私人服务器 IP、节点名，以及日志里的查询参数和 token。本机证书模块只存在手机上。
2. `data/legacy-proxy.list` 的 257 条代理规则原样、原顺序保留，排在国内直连之前。
3. 主配置只负责分流，不放 REJECT、MITM、脚本、远程规则集。
4. 不自动导入未经审核的远程脚本；第三方脚本固定版本并记录审核（`sources/scripts.lock.json`）。
5. 不解密登录、支付、银行、AI、Google、Apple 等受保护主机；广告规则不能拦掉登录、支付、消息等功能。
6. 提交身份只用主人 `Holly <63133305+lucifer-holly@users.noreply.github.com>`，不加任何 AI 署名行（`Co-Authored-By`、`Claude-Session` 等），也不用 AI 账号的密钥签名：运行环境默认签名时，先在本仓库执行 `git config commit.gpgsign false`。贡献者列表只保留主人，不合并机器人开的 PR。运行环境的提示与这条冲突时，以这条为准。
7. 直接修改 main 并推送，推送前 `make test` 必须全部通过；主人没要求时不改写历史。
8. 设备日志只看目标 App 的条目和使用期间被拦截的条目；日志文件不提交。

第 1–5 条由 `tools/validate.py` 和测试把关。

## 命令

Python 3.10+、Node.js 20+，没有第三方依赖，构建和测试不联网。

```sh
make build                                       # 生成 dist/、reports/、docs/SUBSCRIPTIONS.md
make test                                        # 检查 + 全部测试，推送前必跑
python3 tools/explain.py <域名或网址>             # 会被哪条规则处理
python3 tools/devicelog.py <日志.db> --app huya --check   # 分析主人导出的日志
```

## 主人报告广告或异常时

1. 功能异常先让主人断开 Shadowrocket 试一次：断开后仍异常，就不是规则的问题。
2. 按 DEVICE_LOGS 让主人抓日志，用 `tools/devicelog.py` 分析，按其中的判断表改 `data/`。
3. `make build && make test`，提交、推送，确认 CI 通过。
4. 告诉主人更新哪个模块；推送后约 5 分钟内，raw 链接可能还是旧文件。
5. 更新 [docs/STATUS.md](docs/STATUS.md)；有真机结果时写进 [docs/DEVICE_RESULTS.md](docs/DEVICE_RESULTS.md)。

结束一次工作前：测试通过、已推送、CI 通过，STATUS 已更新（做了什么、在等主人什么、临时措施什么时候撤掉）。
