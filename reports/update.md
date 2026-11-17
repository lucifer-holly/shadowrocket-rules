# 上游自动更新报告

检查时间：2026-11-17T13:26:23+00:00

通过检查的来源自动更新；未通过的来源保留旧快照，其余来源照常更新。

| 来源 | 状态 | 规则数 | 新增 / 删除 |
|---|---|---:|---:|
| anti-ad | 变更候选 | 101832 | 984 / 1808 |
| hagezi-light | 变更候选 | 92878 | 916 / 222 |
| fmz-blockads | 变化过大，保留旧版（待人工审核） | 2639 | 1 / 1285 |
| maasea-youtube-response | 一致 | — | — |

以下来源被安全检查拦截，继续使用旧快照：
- fmz-blockads: ChurnBlocked: rule churn 32.8% (+1/-1285 against 3923 accepted rules) exceeds 20%; manual review required

变化超过阈值的候选（人工审核后只能接受这一份，方法见 docs/MAINTENANCE.md「增删超过 20%」）：
- fmz-blockads：变化 32.8%（新增 1，删除 1285，原有 3923 条），上游生成于 2026-11-16T22:26:12+08:00，SHA-256 `160a9e6cbe36125a605e855f7351dee61063af38cbb11a39816e94c2eea45ae7`

详细增删见同目录 update.json；提交记录的文件差异显示完整快照变化。
