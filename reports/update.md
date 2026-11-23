# 上游自动更新报告

检查时间：2026-11-23T14:38:19+00:00

通过检查的来源自动更新；未通过的来源保留旧快照，其余来源照常更新。

| 来源 | 状态 | 规则数 | 新增 / 删除 |
|---|---|---:|---:|
| anti-ad | 变更候选 | 103309 | 910 / 342 |
| hagezi-light | 变化过大，保留旧版（待人工审核） | 76708 | 1202 / 18651 |
| fmz-blockads | 一致 | 3925 | 0 / 0 |
| maasea-youtube-response | 一致 | — | — |

以下来源被安全检查拦截，继续使用旧快照：
- hagezi-light: ChurnBlocked: rule churn 21.1% (+1202/-18651 against 94157 accepted rules) exceeds 20%; manual review required

变化超过阈值的候选（人工审核后只能接受这一份，方法见 docs/MAINTENANCE.md「增删超过 20%」）：
- hagezi-light：变化 21.1%（新增 1202，删除 18651，原有 94157 条），上游生成于 2026-11-23T08:24:00+00:00，SHA-256 `283e6d7328465b6bf54a4b6e3f5714da4d76ca971bc1715e7ab3032ea5d0f799`

详细增删见同目录 update.json；提交记录的文件差异显示完整快照变化。
