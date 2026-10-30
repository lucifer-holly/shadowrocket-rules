# 订阅地址

由 project.json 自动生成；当前地址对应自己的仓库。使用方法见 DEVICE_PROFILES.md。
主配置 URL 在「配置」页导入；模块 URL 在「模块」中导入，都不是节点订阅。手机与 Mac 使用同一 main.conf；手机另加广告模块，Mac 默认只用主配置。
base / lite 二选一；app-ads / apps-all / 独立 App 模块三选一；response-cleaner、youtube、weibo 可按需额外启用。

| 内容 | Raw 地址 |
|---|---|
| 手机与 Mac 共用主配置（「配置」页导入） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/main.conf |
| 通用域名拦截（手机，优先） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/base.sgmodule |
| 较小域名库（与 base 二选一） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/lite.sgmodule |
| 开屏与应用内广告（手机，需证书，推荐） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/app-ads.sgmodule |
| 仅自维护 App 路径规则（与 app-ads 二选一） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps-all.sgmodule |
| 哔哩哔哩/知乎响应处理（实验） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/response-cleaner.sgmodule |
| YouTube 去广告（实验，第三方脚本已审核并固定版本） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/youtube.sgmodule |
| 微博完整版去广告与精简（实验，需证书） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/weibo.sgmodule |
| 主配置示例（优先保留原配置） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/adblock-example.conf |
| 主配置合并片段 | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/config/adblock.fragment.conf |
| 淘宝（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/taobao.sgmodule |
| 京东（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/jd.sgmodule |
| 小红书（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/xiaohongshu.sgmodule |
| 美团（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/meituan.sgmodule |
| 知乎（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/zhihu.sgmodule |
| 闲鱼（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/xianyu.sgmodule |
| 高德地图（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/amap.sgmodule |
| 哔哩哔哩（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/bilibili.sgmodule |
| 拼多多（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/pdd.sgmodule |
| 菜鸟（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/cainiao.sgmodule |
| Keep（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/keep.sgmodule |
| 携程（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/ctrip.sgmodule |
| AppSo（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/appso.sgmodule |
| Jump（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/jump.sgmodule |
| 虎牙（独立实验模块） | https://raw.githubusercontent.com/lucifer-holly/shadowrocket-rules/main/dist/modules/apps/huya.sgmodule |

脚本只引用本仓库按内容哈希命名的文件；更新需要先审阅合并，再在手机更新模块/配置。
模块内嵌域名表；不依赖手机另行拉取上游规则。规则集方式仅访问本仓库。
