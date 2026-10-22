# 交付验证记录

完成时间：2026-10-21T17:36:54+08:00；2026-10-22 主配置与 app-ads 更新后复验

运行环境：Python 3.12.14 / 3.13.16；Node.js v24.19.0 / v22.22.0。Python 使用标准库；Node 测试仅使用内置模块，无运行时包依赖。

| 项目 | 结果 |
|---|---|
| 原始规则解析、精确/后缀语义、例外与父子压缩 | 通过 |
| 重建结果一致性、模块结构、产物/脚本 SHA-256 清单 | 通过 |
| 路径正例、同主机登录/支付/订单负例、重写/脚本样例冲突 | 通过 |
| 数据源失联、HTML、空表、过期、许可变化、过大增删、多源部分失败 | 模拟测试通过；失败保留当前快照 |
| 主配置：257 条显式代理规则完整、原顺序且先于国内直连；手工例外在最前；AI/Google/YouTube/WRDS、PayPal、Apple/Microsoft、SSH、国内与局域网路由；无可路由私人 DIRECT 地址 | 通过（静态评估） |
| app-ads：只含静态拒绝；关键登录/支付/内容网址不被命中；解密主机是上游列表子集且不含受保护主机 | 通过 |
| Python 单元测试 | 49 项通过 |
| JavaScript 响应测试 | 16 项通过 |
| 工作流 YAML 解析与嵌入 Bash 语法 | 通过 |
| 在隔离副本配置实际格式的仓库名并重建、校验自身脚本链接 | 通过 |
| 当前实际上游联网检测 | anti-AD、HaGeZi Light、fmz 参考源均可获取，指纹一致；见 upstream-health.md |
| 公开目录常见秘密模式检查 | 通过；未纳入私人主配置、节点、证书、抓包或账号 |
| Shadowrocket 真机、耗电/内存、广告实际效果 | 未测试，需手机验收 |
| GitHub Actions 实际执行、远端订阅 URL | 准备发布；本地已配置真实仓库地址，远端检查结果以发布后的 Actions 和 Raw 校验为准 |

测试命令：

```sh
python3 tools/build.py --check
python3 tools/validate.py
python3 -m unittest discover -s tests -v
node --test tests/response-cleaner.test.cjs
python3 tools/upstream.py --check
```

统计见 build.json：143,415 条基础域名规则、66,400 条 Lite 规则、14 个 App 模块、15 条自维护 URL 重写、app-ads 中 1,133 条 fmz 静态重写与 2,590 条域名，以及 3 条响应脚本路由。规则数量不是覆盖率指标。没有因这些检查通过而把实验 App 标记为真机有效。
