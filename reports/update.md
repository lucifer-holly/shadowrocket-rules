# 上游自动更新报告

检查时间：2026-11-08T11:16:55+00:00

通过检查的来源自动更新；未通过的来源保留旧快照，其余来源照常更新。

| 来源 | 状态 | 规则数 | 新增 / 删除 |
|---|---|---:|---:|
| anti-ad | 变更候选 | 103068 | 662 / 34 |
| hagezi-light | 获取/检查失败，保留旧版 | — | — |
| fmz-blockads | 一致 | 3923 | 0 / 0 |
| maasea-youtube-response | 一致 | — | — |

以下来源被安全检查拦截，继续使用旧快照：
- hagezi-light: ValueError: rule churn exceeds configured threshold; manual review required

详细增删见同目录 update.json；提交记录的文件差异显示完整快照变化。
