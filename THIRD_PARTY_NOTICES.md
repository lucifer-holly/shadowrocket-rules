# Third-party notices / 第三方声明

本仓库的原创工具、数据编排与生成结果按 GNU GPL version 3 only（GPL-3.0-only）提供。根目录 LICENSE 是完整许可。原始第三方文件保留原许可；许可不因放进本仓库而被覆盖。

## anti-AD

- Author / copyright: Copyright (c) 2017-2019 gently; privacy-protection-tools/anti-AD contributors.
- Source: https://github.com/privacy-protection-tools/anti-AD
- Snapshot: `vendor/anti-ad-surge.txt`, source path `anti-ad-surge.txt` on `master`.
- License: MIT, complete original notice: `licenses/anti-ad-MIT.txt`.
- Modifications: normalize/deduplicate domain rules, remove explicit protected-service conflicts, remove entries already covered by a parent suffix; combine with the other credited sources to generate `dist/rules/` and domain modules.

## HaGeZi DNS Blocklists — Multi LIGHT

- Author: HaGeZi and project contributors.
- Source: https://github.com/hagezi/dns-blocklists
- Snapshot: `vendor/hagezi-light.txt`, `wildcard/light-onlydomains.txt` on `main`.
- License: GPL-3.0 as declared upstream, retained as `licenses/hagezi-GPL-3.0.txt`.
- Modifications: translate wildcard-domain semantics into `DOMAIN-SUFFIX`, deduplicate, apply protected-service exceptions, combine with anti-AD. Only Light is included; Normal/Pro/Ultimate are not stacked.
- The complete preferred inputs, transformations and tests are included in this repository, allowing redistribution and offline rebuilding of the resulting lists.

## fmz200/wool_scripts — four selected static endpoint rules

- Author: fmz200 (奶思) and contributors credited by the upstream project.
- Source: https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin
- License: upstream GPL-3.0, retained as `licenses/fmz200-GPL-3.0.txt`.
- Redistributed fragment only: `vendor/fmz-selected.txt` records four original static rule lines (AppSo, 菜鸟, Keep, 携程). `data/apps.json` re-scopes host/path boundaries and adapts them to Shadowrocket `pattern - reject` syntax.
- This project does not redistribute or execute the upstream plugin's scripts, jq filters, account handling, entitlement changes or full platform-specific configuration.
- Bilibili JSON field/route observations were checked against the same public plugin. The response-cleaner implementation is original, small and narrower in scope; it does not copy the plugin's broader content filtering or account features.

## User-provided starting material

The attached splash-core module and initial repository supplied the ten initial app endpoint candidates. This project rewrote them into structured endpoint records with bounded matching, removed uncertain whole-host blocks and discarded the old dynamic-vendoring helper. Unverified endpoint candidates remain explicitly experimental.

Hashes and source paths for actual automatic data imports are in `sources/upstreams.lock.json`. The source bytes, LICENSE texts and relevant notices accompany the complete project; retain them when redistributing generated lists. Projects surveyed but not incorporated are documented in `docs/RESEARCH.md` and are not runtime dependencies.
