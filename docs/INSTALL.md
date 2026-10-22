# 安装与接入

## 保留原有网络配置

可以保留原主配置并叠加广告模块，也可以使用手机与 Mac 共用的一份私人合并配置；两端共用方式见 [配置说明](DEVICE_PROFILES.md)。私人合并配置把自己的 SSH 例外和原有显式 PROXY 规则直接放进主配置，无需单独的私人模块。公开的 `dist/config/main.conf` 只是脱敏模板；私人完整版内部引用本仓库的公共分流规则集来更新，不从公开模板覆盖自己。广告模块只写广告拒绝、路径重写、脚本和有限 MITM 主机，不定义节点、DNS、代理组、GEOIP 或 FINAL，也不把广告库例外强制设为 DIRECT。

原来主配置的 SSH 直连、国内外路由和节点选择继续由原配置负责。**模块规则通常优先于主配置**；若 SSH 使用域名且该域名误入广告库，原主配置的 DIRECT 未必能救回来，需要在 `data/allowlist.json` 添加该域名例外后重建。直接连接服务器 IP 的 SSH 不会匹配本项目的域名规则。

先导入不需要证书的 `base.sgmodule`（约 5.8 MB，14 万条）；资源不足则选择 `lite.sgmodule`（约 2.8 MB，6.6 万条）。不要同时开。文件大小不是 Shadowrocket 运行时内存用量；没有真机内存基准。

## App 模块与 HTTPS 解密

1. 导出并妥善保存原配置备份。
2. 在 Shadowrocket 当前配置的 HTTPS 解密设置中，本地生成 CA（Certificate Authority，证书颁发机构）证书，并按应用提示安装描述文件。
3. 在 iOS「设置 → 通用 → 关于本机 → 证书信任设置」中，信任刚安装的个人 CA；返回 Shadowrocket 启用当前配置的 HTTPS 解密。
4. 导入一个独立 App 模块，更新并重新连接。模块通过 `hostname = %APPEND% ...` 追加有限主机，不含证书，不会代你开启所有域名解密。
5. 冷启动 App 测试广告、登录与关键操作。逐个成功后再决定是否换为 `apps-all.sgmodule`。

禁止把 `hostname` 改为 `*` 来追求“全去广告”。业务 API 的 MITM（Man-in-the-Middle，中间人解密）会接触该主机上的请求，虽然重写只匹配广告路径；遇到证书锁定或 TLS 错误直接关闭对应模块/移除该主机，不能靠忽略服务器证书错误修复。

证书私钥只在自己的设备和私人备份中保管，不上传 GitHub。更换设备时分别处理信任设置，不共享公共 CA 私钥。

## 脚本模块

`response-cleaner.sgmodule` 只处理：

- 哔哩哔哩 JSON 推荐流中有明确广告标记的条目；保留正常视频、直播、分页字段。
- 哔哩哔哩开屏 JSON 的 `show`、`event_list` 数组。
- 知乎推荐流中明确 `type=ad` 的条目。

它不处理 gRPC / Protobuf。对于未知结构、应用错误码、非成功 HTTP 状态、非 JSON 或超过 1 MiB 的响应，原样返回。样例是合成数据，不能代表当前所有 App 版本。

先运行 `tools/configure.py` 配置仓库、上传文件，再导入生成后的模块。脚本来自自己仓库的 `dist/scripts/response-cleaner.<SHA256>.js`，不使用上游 JS URL。SHA-256（Secure Hash Algorithm 256-bit，256 位安全散列算法）用于构建校验及版本命名；Shadowrocket 本身不会根据文件名自动验证脚本内容。

## 主配置接入（可选）

优先采用模块；如果你希望直接在原配置中加入规则集：

1. 在私人 `default.conf` 的 `[Rule]` 内，**SSH/手工直连例外之后、宽泛国内分流/GEOIP/FINAL 之前**放置一行：

   ```text
   # PERSONAL_ADBLOCK_HERE
   ```

2. 在本地运行，输出必须存到忽略目录 `private/` 或仓库之外：

   ```sh
   python3 tools/integrate.py --input /你的私人路径/default.conf --output private/default-adblock.conf
   ```

3. 工具只替换标记那一行，其余字节和顺序保持不变。它不自动修改 HTTPS 解密或安装 App 模块。输出只在自己设备使用，禁止上传。

规则集引用的是你自己的 `dist/rules/base.list`。不要同时通过基础模块再重复加载同一规则集；重复会浪费资源。私人配置原有的 broad DIRECT 可能让部分广告绕过规则，请按实际顺序检查。

## 订阅与更新

[地址表](SUBSCRIPTIONS.md) 是生成结果。仓库地址未配置或未上传前，模板 URL 无法订阅。Public 仓库适合无鉴权的 Raw 订阅；Private 仓库 Raw 链接通常不能供客户端直接长期订阅，不要把 GitHub Token 写进 URL。

GitHub 合并更新后，在 Shadowrocket 中更新远程模块；配置或规则集的更新入口取决于接入方式。仅保持 VPN 连接并不意味着客户端一定定时更新所有模块。更新后重新连接，并检查模块/脚本是否下载成功。
