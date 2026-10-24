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

## fmz200/wool_scripts — blockAds plugin, static subset

- Author: fmz200 (奶思) and contributors credited by the upstream project.
- Source: https://github.com/fmz200/wool_scripts/blob/main/Loon/plugin/blockAds.plugin
- License: upstream GPL-3.0, retained as `licenses/fmz200-GPL-3.0.txt`.
- Snapshot: `vendor/fmz-blockads.plugin` (whole file, hashed in `sources/upstreams.lock.json`), tracked automatically like the other data sources. `vendor/fmz-selected.txt` keeps the four original lines adapted earlier into `data/apps.json`.
- Modifications: `tools/plugin_import.py` keeps only static `DOMAIN`/`DOMAIN-SUFFIX`/narrow `IP-CIDR` REJECT rules and `reject`-family URL rewrites, converts them to Shadowrocket module syntax, removes protected hosts and critical-URL matches, and narrows MITM hostnames to those the kept rules need (always a subset of the plugin's own list). The domain and IP rules are merged and deduplicated with the other domain sources into `dist/rules/` and the domain modules (`base`, `lite`); the rewrites and MITM hostnames form `dist/modules/app-ads.sgmodule`.
- This project does not redistribute as runtime code or execute the upstream plugin's scripts, jq filters, body rewrites, redirects, arguments, account handling or entitlement changes.
- Bilibili JSON field/route observations were checked against the same public plugin. The response-cleaner implementation is original, small and narrower in scope; it does not copy the plugin's broader content filtering or account features.
- The WeChat article-ad route (`mp.weixin.qq.com/mp/getappmsgad`) and its `advertisement` field names come from the same plugin, which renames those fields with a body-replace rule that is not imported. The retired WeChat module deleted the fields with its own code (`dist/scripts/wechat.<SHA-256>.js`, kept as an archive); the plugin's `cps_product_info` reject rule is imported into app-ads as before.

## Maasea/sgmodule — YouTube response script (pinned copy)

- Author: Maasea and contributors.
- Source: https://github.com/Maasea/sgmodule (`Script/Youtube/youtube.response.js`).
- License: Apache License 2.0, retained as `licenses/maasea-sgmodule-Apache-2.0.txt`. No NOTICE file is published upstream.
- Redistributed unmodified as `vendor/maasea-youtube.response.js` and published as `dist/scripts/youtube.response.<SHA-256>.js` for `dist/modules/youtube.sgmodule`. The module wiring (route, size limit, QUIC rule, single MITM host) is this project's own.
- The copy is pinned by hash and by an API-usage fingerprint; new upstream versions are reported for review and never imported automatically.

## Weibo endpoint observations

- `scripts/weibo.js` is this project's own GPL-3.0-only code. Endpoint paths, JSON field names and item identifiers (for example `mblogtypename`, `promotion`, `ads_word`, `profile_top`, the 我-page `itemId` values and card types 118/247) were learned from public modules: fmz200/wool_scripts `Loon/plugin/weibo.plugin` and `Scripts/weibo/weibo_ads.js` (GPL-3.0), and, for reading only, zmqcherish/proxy-script `weibo_main.js` and the iKeLee 微博去广告 module listing, whose licences do not permit redistribution.
- No code from these projects is copied, bundled or fetched at runtime; the filtering rules are narrower (explicit ad markers and named modules only) and were written from scratch.
- The splash-ad handling (2026-10-24) relies on endpoint paths and field names of the uve.weibo.com calls (`v*/ad/preload` with `ads[].start_time`/`end_time`/display counts, `interface/sdk/sdkad.php` with its JSON-plus-`OK` answer, `ads[].begintime`/`endtime` and `show_push_splash_ad`, `wbapplua/wbpullad.lua` with `cached_ad.ads[].start_date`/`end_date`) learned, for reading only, from yichahucha/surge `wb_launch.js`, zmqcherish/proxy-script `weibo_launch.js`, ddgksf2013/Scripts `weibo_json.js` and the iKeLee 微博去广告 module listing. The postpone-to-a-future-date approach follows those scripts; the code is this project's own.

## WeChat page observations

- The archived `dist/scripts/wechat.<SHA-256>.js` (module retired 2026-10-23) is this project's own GPL-3.0-only code. The names it relies on — the `window.__ajaxTransferConfig` table and its `mmbizwap_cgi_appmsgad` scope, the ad containers (`.mpda_bottom_container`, `.iframe_ad_container`, `.comment-ad-container`, `mpcpc`, `mp-sponsor-ad`, `mp-common-cpsad`, `#js_top_ad_area`) and the ad positions — were read from the public article page code that WeChat serves to any browser (`mp.weixin.qq.com/s/…` and `res.wx.qq.com/mmbizappmsg/…`), on 2026-10-23. No WeChat code is copied, bundled or fetched at runtime.
- oo226/egern-config pull request 143 (missing `getappmsgad` in logs, caution about rejecting all of `wxs.qq.com`) was read for context only.

## User-provided starting material

The attached splash-core module and initial repository supplied the ten initial app endpoint candidates. This project rewrote them into structured endpoint records with bounded matching, removed uncertain whole-host blocks and discarded the old dynamic-vendoring helper. Unverified endpoint candidates remain explicitly experimental.

Hashes and source paths for actual automatic data imports are in `sources/upstreams.lock.json`. The source bytes, LICENSE texts and relevant notices accompany the complete project; retain them when redistributing generated lists. Projects surveyed but not incorporated are documented in `docs/RESEARCH.md` and are not runtime dependencies.
